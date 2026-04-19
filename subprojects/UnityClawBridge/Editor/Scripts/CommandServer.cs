// CommandServer.cs
// Unity C# 端 HTTP 命令服务器 - 接收 Python 端代码请求，在 EditorApplication.update 中执行
// M1: 集成 Roslyn C# Scripting 执行引擎
//
// 改进（M1）:
//   - Roslyn 执行引擎：支持完整 C# 代码执行
//   - 持久命名空间：跨调用保持变量
//   - 上下文注入：Selection/Scene/AssetDatabase 等快捷变量
//   - Undo 支持：每次执行前 RecordObject
//   - validate_script：语法预验证

using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Net;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.CodeAnalysis.CSharp.Scripting;
using Microsoft.CodeAnalysis.Scripting;
using Newtonsoft.Json;
using UnityEditor;
using UnityEngine;

namespace ArtClaw.Unity
{
    /// <summary>
    /// Unity 主线程命令执行服务器（Roslyn 执行引擎）。
    ///
    /// 架构：
    ///   Python MCP Server --HTTP POST /execute--> CommandServer
    ///   CommandServer --EditorApplication.update--> Roslyn 执行
    ///   Roslyn --→ Unity API
    ///   Python MCP Server --HTTP GET /result/{id}--> CommandServer
    ///
    /// 端口：8089（默认，端口冲突时自动递增）
    /// </summary>
    [InitializeOnLoad]
    public static class CommandServer
    {
        private const int HTTP_PORT_DEFAULT = 8089;
        private const int MAX_EXEC_PER_FRAME = 5;
        private const int MAX_LOG_ENTRIES = 100;
        private static int _httpPort = HTTP_PORT_DEFAULT;
        public static int ActivePort => _httpPort;

        // 待执行命令队列
        private static readonly ConcurrentQueue<PendingCommand> _commandQueue =
            new ConcurrentQueue<PendingCommand>();

        // 已完成结果字典（id → 结果）
        private static readonly ConcurrentDictionary<string, CommandResult> _results =
            new ConcurrentDictionary<string, CommandResult>();

        // ── Roslyn 执行引擎（M1 新增）──
        private static ScriptOptions _scriptOptions;
        private static object _scriptGlobals;
        private static readonly object _globalsLock = new object();

        // ── 执行日志（M1.3 Dashboard 用）──
        public static readonly RingBuffer<LogEntry> ExecutionLog = new RingBuffer<LogEntry>(MAX_LOG_ENTRIES);

        // ── HTTP 服务器 ──
        private static HttpListener _listener;
        private static Thread _listenerThread;

        // ════════════════════════════════════════
        // 初始化
        // ════════════════════════════════════════

        static CommandServer()
        {
            InitRoslynGlobals();
            Start();
            EditorApplication.update += OnEditorUpdate;
            AssemblyReloadEvents.beforeAssemblyReload += Stop;
        }

        private static void InitRoslynGlobals()
        {
            _scriptGlobals = new ScriptGlobals();
            _scriptOptions = ScriptOptions.Default
                .WithReferences(typeof(UnityEngine.Object).Assembly,
                               typeof(EditorUtility).Assembly,
                               typeof(UnityEditor.SceneManagement.EditorSceneManager).Assembly,
                               typeof(JsonConvert).Assembly)
                .WithImports("UnityEngine", "UnityEditor",
                            "UnityEngine.SceneManagement", "UnityEditor.SceneManagement",
                            "System", "System.Collections", "System.Collections.Generic",
                            "System.Linq", "System.Text");
        }

        // ════════════════════════════════════════
        // 启动/停止
        // ════════════════════════════════════════

        public static void Start()
        {
            if (_listener != null && _listener.IsListening) return;

            for (int attempt = 0; attempt < 10; attempt++)
            {
                _httpPort = HTTP_PORT_DEFAULT + attempt;
                _listener = new HttpListener();
                _listener.Prefixes.Add($"http://127.0.0.1:{_httpPort}/");
                try
                {
                    _listener.Start();
                    break;
                }
                catch (HttpListenerException)
                {
                    _listener = null;
                    if (attempt == 9)
                    {
                        Debug.LogError($"[ArtClaw] CommandServer 无法找到可用端口（尝试了 {HTTP_PORT_DEFAULT}~{_httpPort}）");
                        return;
                    }
                }
            }

            _listenerThread = new Thread(ListenLoop) { IsBackground = true, Name = "ArtClaw.CommandServer" };
            _listenerThread.Start();
            Debug.Log($"[ArtClaw] CommandServer 已启动 http://127.0.0.1:{_httpPort}/ (Roslyn v4.11.0)");
        }

        public static void Stop()
        {
            EditorApplication.update -= OnEditorUpdate;
            try { _listener?.Stop(); } catch { }
            _listener = null;
        }

        // ════════════════════════════════════════
        // HTTP 监听
        // ════════════════════════════════════════

        private static void ListenLoop()
        {
            while (_listener != null && _listener.IsListening)
            {
                try
                {
                    var context = _listener.GetContext();
                    ThreadPool.QueueUserWorkItem(_ => HandleRequest(context));
                }
                catch (HttpListenerException) { break; }
                catch (Exception e)
                {
                    Debug.LogWarning($"[ArtClaw] HTTP 监听异常: {e.Message}");
                }
            }
        }

        private static void HandleRequest(HttpListenerContext ctx)
        {
            var req = ctx.Request;
            var resp = ctx.Response;

            try
            {
                string path = req.Url.AbsolutePath.TrimEnd('/');
                string method = req.HttpMethod.ToUpper();

                if (method == "POST" && path == "/execute")
                {
                    HandleExecute(req, resp);
                }
                else if (method == "POST" && path == "/batch_execute")
                {
                    HandleBatchExecute(req, resp);
                }
                else if (method == "GET" && path.StartsWith("/result/"))
                {
                    string id = path.Substring("/result/".Length);
                    HandleResult(id, resp);
                }
                else if (method == "GET" && path == "/health")
                {
                    HandleHealth(resp);
                }
                else if (method == "GET" && path == "/logs")
                {
                    HandleLogs(resp);
                }
                else if (method == "POST" && path == "/validate")
                {
                    HandleValidate(req, resp);
                }
                else
                {
                    WriteJson(resp, 404, new { error = "Not Found" });
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[ArtClaw] 请求处理异常: {e.Message}");
                try { WriteJson(resp, 500, new { error = e.Message }); } catch { }
            }
            finally
            {
                try { resp.Close(); } catch { }
            }
        }

        private static void HandleExecute(HttpListenerRequest req, HttpListenerResponse resp)
        {
            string body = ReadBody(req);
            var payload = JsonConvert.DeserializeObject<ExecutePayload>(body);

            if (string.IsNullOrEmpty(payload?.id) || string.IsNullOrEmpty(payload?.code))
            {
                WriteJson(resp, 400, new { error = "缺少 id 或 code 字段" });
                return;
            }

            var cmd = new PendingCommand { Id = payload.id, Code = payload.code };
            _commandQueue.Enqueue(cmd);
            WriteJson(resp, 200, new { queued = true, id = payload.id });
        }

        private static void HandleBatchExecute(HttpListenerRequest req, HttpListenerResponse resp)
        {
            string body = ReadBody(req);
            var payloads = JsonConvert.DeserializeObject<List<ExecutePayload>>(body);

            if (payloads == null || payloads.Count == 0)
            {
                WriteJson(resp, 400, new { error = "批量请求为空" });
                return;
            }

            foreach (var p in payloads)
            {
                if (!string.IsNullOrEmpty(p?.id) && !string.IsNullOrEmpty(p?.code))
                    _commandQueue.Enqueue(new PendingCommand { Id = p.id, Code = p.code });
            }

            var ids = new HashSet<string>(payloads.ConvertAll(p => p.id));
            var deadline = DateTime.UtcNow.AddSeconds(60);
            while (DateTime.UtcNow < deadline)
            {
                bool allDone = true;
                foreach (var id in ids)
                    if (!_results.ContainsKey(id)) { allDone = false; break; }
                if (allDone) break;
                Thread.Sleep(20);
            }

            var results = new List<object>();
            foreach (var id in ids)
            {
                if (_results.TryRemove(id, out var r))
                    results.Add(new { id, done = true, success = string.IsNullOrEmpty(r.Error), result = r.Result, error = r.Error, output = r.Output });
                else
                    results.Add(new { id, done = false, error = "执行超时" });
            }

            WriteJson(resp, 200, new { results });
        }

        private static void HandleResult(string id, HttpListenerResponse resp)
        {
            if (_results.TryGetValue(id, out var result))
            {
                _results.TryRemove(id, out _);
                WriteJson(resp, 200, new
                {
                    done = true,
                    success = string.IsNullOrEmpty(result.Error),
                    result = result.Result,
                    error = result.Error,
                    output = result.Output,
                });
            }
            else
            {
                WriteJson(resp, 200, new { done = false });
            }
        }

        private static void HandleHealth(HttpListenerResponse resp)
        {
            WriteJson(resp, 200, new
            {
                status = "ok",
                version = "1.0.0",
                port = _httpPort,
                unity_version = Application.unityVersion,
                project_name = Application.productName,
                is_playing = EditorApplication.isPlaying,
                is_compiling = EditorApplication.isCompiling,
                execution_count = ExecutionLog.Count,
            });
        }

        private static void HandleLogs(HttpListenerResponse resp)
        {
            var logs = ExecutionLog.ToArray();
            var entries = new List<object>();
            foreach (var e in logs)
            {
                entries.Add(new
                {
                    timestamp = e.Timestamp.ToString("HH:mm:ss.fff"),
                    success = e.Success,
                    code_preview = e.Code.Length > 100 ? e.Code.Substring(0, 100) + "..." : e.Code,
                    result = e.Result?.ToString(),
                    error = e.Error,
                });
            }
            WriteJson(resp, 200, new { logs = entries });
        }

        /// <summary>
        /// 语法预验证（M1.1 新增）
        /// POST /validate { "code": "..." } → { "valid": bool, "errors": [...] }
        /// </summary>
        private static void HandleValidate(HttpListenerRequest req, HttpListenerResponse resp)
        {
            string body = ReadBody(req);
            var payload = JsonConvert.DeserializeObject<ValidatePayload>(body);
            var code = payload?.code ?? "";

            try
            {
                var diagnostics = CSharpScript.Create(code, _scriptOptions).GetCompilation().GetDiagnostics();
                var errors = new List<object>();
                foreach (var d in diagnostics)
                {
                    if (d.Severity == Microsoft.CodeAnalysis.DiagnosticSeverity.Error)
                    {
                        errors.Add(new
                        {
                            line = d.Location.GetLineSpan().StartLinePosition.Line + 1,
                            column = d.Location.GetLineSpan().StartLinePosition.Character + 1,
                            message = d.GetMessage(),
                            id = d.Id,
                        });
                    }
                }
                WriteJson(resp, 200, new { valid = errors.Count == 0, errors });
            }
            catch (Exception e)
            {
                WriteJson(resp, 200, new { valid = false, errors = new[] { new { message = e.Message } } });
            }
        }

        // ════════════════════════════════════════
        // 主线程命令消费
        // ════════════════════════════════════════

        private static void OnEditorUpdate()
        {
            int processed = 0;
            while (processed < MAX_EXEC_PER_FRAME && _commandQueue.TryDequeue(out var cmd))
            {
                ExecuteCommand(cmd);
                processed++;
            }
        }

        private static void ExecuteCommand(PendingCommand cmd)
        {
            var sb = new StringBuilder();
            var oldOut = Console.Out;

            // 上下文注入（每次执行前刷新）
            RefreshGlobals();

            try
            {
                // 记录 Undo（如果操作了 Unity 对象）
                RecordUndoIfNeeded(cmd.Code);

                // Roslyn 执行
                var task = CSharpScript.RunAsync(
                    cmd.Code,
                    _scriptOptions,
                    _scriptGlobals,
                    typeof(ScriptGlobals));

                task.Wait(TimeSpan.FromSeconds(30)); // 超时保护

                if (task.IsFaulted)
                {
                    var error = FormatException(task.Exception);
                    _results[cmd.Id] = new CommandResult { Error = error, Output = sb.ToString() };
                    ExecutionLog.Add(new LogEntry { Success = false, Code = cmd.Code, Error = error });
                    Debug.LogWarning($"[ArtClaw] 执行失败 (id={cmd.Id}): {error}");
                }
                else if (task.IsCanceled)
                {
                    _results[cmd.Id] = new CommandResult { Error = "执行超时（30秒）", Output = sb.ToString() };
                    ExecutionLog.Add(new LogEntry { Success = false, Code = cmd.Code, Error = "执行超时" });
                }
                else
                {
                    var state = task.Result;
                    var resultJson = state.ReturnValue != null ? SerializeResult(state.ReturnValue) : null;
                    _results[cmd.Id] = new CommandResult
                    {
                        Result = resultJson,
                        Output = sb.ToString(),
                    };

                    // 更新全局变量
                    lock (_globalsLock)
                    {
                        if (state.Variables != null)
                        {
                            foreach (var v in state.Variables)
                            {
                                UpdateGlobal(v.Name, v.Value);
                            }
                        }
                    }

                    ExecutionLog.Add(new LogEntry
                    {
                        Success = true,
                        Code = cmd.Code,
                        Result = resultJson,
                    });
                }
            }
            catch (Exception e)
            {
                var error = FormatException(e);
                _results[cmd.Id] = new CommandResult { Error = error, Output = sb.ToString() };
                ExecutionLog.Add(new LogEntry { Success = false, Code = cmd.Code, Error = error });
                Debug.LogWarning($"[ArtClaw] 执行异常 (id={cmd.Id}): {error}");
            }
        }

        // ════════════════════════════════════════
        // 上下文注入
        // ════════════════════════════════════════

        /// <summary>
        /// 刷新全局变量（每次执行前调用）
        /// </summary>
        private static void RefreshGlobals()
        {
            lock (_globalsLock)
            {
                if (_scriptGlobals is ScriptGlobals g)
                {
                    g.Selection = Selection.activeGameObject;
                    g.SelectedObjects = Selection.objects;
                    g.ActiveScene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
                    g.ActiveTransform = Selection.activeTransform;
                    g.ActiveGameObject = Selection.activeGameObject;
                    g.ActiveObject = Selection.activeObject;
                    g.AssetDatabase = null; // marker
                    g.ProjectWindow = EditorGUIUtility.GetObjectPickerControl() == ObjectPickerActiveControlID.ProjectBrowser
                        ? "Project Browser" : null;
                }
            }
        }

        private static void UpdateGlobal(string name, object value)
        {
            // 持久化用户定义的变量到全局对象
            lock (_globalsLock)
            {
                var type = typeof(ScriptGlobals);
                var field = type.GetField(name);
                if (field != null)
                {
                    field.SetValue(_scriptGlobals, value);
                }
            }
        }

        private static void RecordUndoIfNeeded(string code)
        {
            // 简单的启发式：包含 GameObject/Component/SerializedObject 等关键字时记录 Undo
            var undoKeywords = new[] { "Create", "Delete", "AddComponent", "Destroy", "Rename", "Move", "transform", "gameObject" };
            foreach (var kw in undoKeywords)
            {
                if (code.Contains(kw, StringComparison.OrdinalIgnoreCase))
                {
                    Undo.RecordObject(Selection.activeObject ?? new UnityEngine.Object(), "ArtClaw Script Execution");
                    break;
                }
            }
        }

        // ════════════════════════════════════════
        // 结果序列化
        // ════════════════════════════════════════

        private static object SerializeResult(object value)
        {
            if (value == null) return null;

            if (value is UnityEngine.Object uo)
            {
                return new
                {
                    type = uo.GetType().Name,
                    name = uo.name,
                    path = uo is GameObject go ? AssetDatabase.GetAssetPath(go) : null,
                    instanceId = uo.GetInstanceID(),
                    hideFlags = uo.hideFlags.ToString(),
                };
            }

            if (value is UnityEngine.Vector2 v2) return new { x = v2.x, y = v2.y };
            if (value is UnityEngine.Vector3 v3) return new { x = v3.x, y = v3.y, z = v3.z };
            if (value is UnityEngine.Vector4 v4) return new { x = v4.x, y = v4.y, z = v4.z, w = v4.w };
            if (value is UnityEngine.Color c) return new { r = c.r, g = c.g, b = c.b, a = c.a };

            if (value is System.Collections.IEnumerable enumerable && !(value is string))
            {
                var list = new List<object>();
                foreach (var item in enumerable)
                    list.Add(SerializeResult(item));
                return list;
            }

            try { return JsonConvert.DeserializeObject(JsonConvert.SerializeObject(value)); }
            catch { return value.ToString(); }
        }

        private static string FormatException(Exception e)
        {
            if (e is AggregateException ae && ae.InnerExceptions.Count > 0)
                e = ae.InnerExceptions[0];

            var sb = new StringBuilder();
            sb.AppendLine($"[{e.GetType().Name}] {e.Message}");

            if (e is Microsoft.CodeAnalysis.CSharp.Scripting.CSharpScriptException csEx)
            {
                if (csEx.LineNumber > 0)
                    sb.AppendLine($"  位置: 行 {csEx.LineNumber}, 列 {csEx.Column}");
                if (!string.IsNullOrEmpty(csEx.ErrorCode))
                    sb.AppendLine($"  代码: {csEx.ErrorCode}");
            }

            if (e.StackTrace != null)
            {
                var lines = e.StackTrace.Split('\n');
                foreach (var line in lines)
                {
                    if (line.Contains("roslyn") || line.Contains("CommandServer") || line.Contains("at Submission#"))
                        sb.AppendLine($"  {line.Trim()}");
                }
            }

            return sb.ToString().TrimEnd();
        }

        // ════════════════════════════════════════
        // 工具方法
        // ════════════════════════════════════════

        private static void WriteJson(HttpListenerResponse resp, int statusCode, object obj)
        {
            string json = JsonConvert.SerializeObject(obj);
            byte[] bytes = Encoding.UTF8.GetBytes(json);
            resp.StatusCode = statusCode;
            resp.ContentType = "application/json; charset=utf-8";
            resp.ContentLength64 = bytes.Length;
            resp.OutputStream.Write(bytes, 0, bytes.Length);
        }

        private static string ReadBody(HttpListenerRequest req)
        {
            using var reader = new System.IO.StreamReader(req.InputStream, req.ContentEncoding);
            return reader.ReadToEnd();
        }

        // ════════════════════════════════════════
        // 内部数据结构
        // ════════════════════════════════════════

        private class ExecutePayload
        {
            public string id;
            public string code;
        }

        private class ValidatePayload
        {
            public string code;
        }

        private class PendingCommand
        {
            public string Id;
            public string Code;
        }

        private class CommandResult
        {
            public object Result;
            public string Error;
            public string Output;
        }

        // ════════════════════════════════════════
        // 全局上下文对象（Roslyn globals）
        // ════════════════════════════════════════

        public class ScriptGlobals
        {
            // 选中对象
            public UnityEngine.GameObject Selection;
            public UnityEngine.Object[] SelectedObjects;
            public UnityEngine.Transform ActiveTransform;
            public UnityEngine.GameObject ActiveGameObject;
            public UnityEngine.Object ActiveObject;

            // 场景
            public UnityEngine.SceneManagement.Scene ActiveScene;

            // 快捷方法
            public UnityEngine.SceneManagement.SceneManager_ Scene => new UnityEngine.SceneManagement.SceneManager_();

            // AssetDatabase marker
            public object AssetDatabase;

            // ProjectBrowser marker
            public string ProjectWindow;
        }

        // ════════════════════════════════════════
        // 环形缓冲区（执行日志）
        // ════════════════════════════════════════

        public class RingBuffer<T>
        {
            private readonly T[] _buffer;
            private int _head;
            private int _count;
            private readonly int _capacity;
            private readonly object _lock = new object();

            public RingBuffer(int capacity)
            {
                _capacity = capacity;
                _buffer = new T[capacity];
                _head = 0;
                _count = 0;
            }

            public void Add(T item)
            {
                lock (_lock)
                {
                    _buffer[_head] = item;
                    _head = (_head + 1) % _capacity;
                    if (_count < _capacity) _count++;
                }
            }

            public int Count => _count;

            public T[] ToArray()
            {
                lock (_lock)
                {
                    var result = new T[_count];
                    for (int i = 0; i < _count; i++)
                    {
                        int idx = (_head - _count + i + _capacity) % _capacity;
                        result[i] = _buffer[idx];
                    }
                    return result;
                }
            }
        }

        public class LogEntry
        {
            public DateTime Timestamp = DateTime.Now;
            public bool Success;
            public string Code;
            public object Result;
            public string Error;
        }
    }
}
