// CommandServer.cs
// Unity C# 端 HTTP 命令服务器 - 使用 TcpListener（避免 HttpListener/HTTP.sys 僵尸端口问题）
// 接收 Python 端代码请求，在 EditorApplication.update 中执行 Roslyn 编译
// 依赖: Editor/Assemblies/ 下的 Roslyn DLL

using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Threading;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using UnityEditor;
using UnityEngine;

namespace ArtClaw.Unity
{
    [InitializeOnLoad]
    public static class CommandServer
    {
        private const int HTTP_PORT_DEFAULT = 8089;
        private const int MAX_EXEC_PER_FRAME = 5;
        private const int MAX_LOG_ENTRIES = 100;
        private static int _httpPort = HTTP_PORT_DEFAULT;
        public static int ActivePort => _httpPort;
        private static string _cachedProductName;
        private static bool _cachedIsPlaying;
        private static bool _cachedIsCompiling;
        private static string _cachedUnityVersion;

        private static readonly ConcurrentQueue<PendingCommand> _commandQueue = new ConcurrentQueue<PendingCommand>();
        private static readonly ConcurrentDictionary<string, CommandResult> _results = new ConcurrentDictionary<string, CommandResult>();

        private static List<MetadataReference> _roslynRefs;
        private static int _scriptCounter;

        public static readonly RingBuffer<LogEntry> ExecutionLog = new RingBuffer<LogEntry>(MAX_LOG_ENTRIES);

        private static TcpListener _listener;
        private static Thread _listenerThread;
        private static volatile bool _running;

        static CommandServer()
        {
            _cachedProductName = Application.productName;
            _cachedUnityVersion = Application.unityVersion;
            InitRoslynGlobals();
            Start();
            EditorApplication.update += OnEditorUpdate;
            AssemblyReloadEvents.beforeAssemblyReload += Stop;
            EditorApplication.quitting += Stop;
        }

        private static void InitRoslynGlobals()
        {
            _roslynRefs = new List<MetadataReference>();
            foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                if (asm.IsDynamic || string.IsNullOrEmpty(asm.Location)) continue;
                try { _roslynRefs.Add(MetadataReference.CreateFromFile(asm.Location)); }
                catch { }
            }
        }

        // ════════════════════════════════════════
        // 服务器生命周期
        // ════════════════════════════════════════

        public static void Start()
        {
            if (_listener != null) return;

            _httpPort = HTTP_PORT_DEFAULT;
            KillPortOccupant(_httpPort);

            for (int attempt = 0; attempt < 10; attempt++)
            {
                if (attempt > 0)
                    System.Threading.Thread.Sleep(1000);

                try
                {
                    _listener = new TcpListener(IPAddress.Loopback, _httpPort);
                    // 允许重用 TIME_WAIT 状态的端口，解决 Unity 重启后僵尸端口问题
                    _listener.Server.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);
                    _listener.Start();
                    break;
                }
                catch (SocketException)
                {
                    _listener = null;
                }
            }

            if (_listener == null)
            {
                Debug.LogError($"[ArtClaw] CommandServer 无法绑定端口 {_httpPort}（已重试 10 次）");
                return;
            }

            _listenerThread = new Thread(ListenLoop) { IsBackground = true, Name = "ArtClaw.CommandServer" };
            _listenerThread.Start();
            Debug.Log($"[ArtClaw] CommandServer 已启动 http://127.0.0.1:{_httpPort}/ (Roslyn, Unity {Application.unityVersion})");
        }

        public static void Stop()
        {
            EditorApplication.update -= OnEditorUpdate;
            _running = false;
            if (_listener != null)
            {
                try { _listener.Stop(); } catch { }
                _listener = null;
            }
            if (_listenerThread != null)
            {
                try { _listenerThread.Join(2000); } catch { }
                _listenerThread = null;
            }
        }

        private static void KillPortOccupant(int port)
        {
            try
            {
                var psi = new System.Diagnostics.ProcessStartInfo
                {
                    FileName = "netstat",
                    Arguments = "-ano",
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    CreateNoWindow = true,
                };
                var proc = System.Diagnostics.Process.Start(psi);
                if (proc == null) return;
                string output = proc.StandardOutput.ReadToEnd();
                proc.WaitForExit(3000);

                int myPid = System.Diagnostics.Process.GetCurrentProcess().Id;

                foreach (var line in output.Split('\n'))
                {
                    if (!line.Contains("LISTENING")) continue;
                    var parts = line.Trim().Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
                    if (parts.Length < 5) continue;
                    string addr = parts[1];
                    int colon = addr.LastIndexOf(':');
                    if (colon < 0) continue;
                    if (!int.TryParse(addr.Substring(colon + 1), out int listenPort)) continue;
                    if (listenPort != port) continue;
                    if (!int.TryParse(parts[parts.Length - 1], out int pid)) continue;
                    if (pid == myPid) continue;

                    try
                    {
                        var occupant = System.Diagnostics.Process.GetProcessById(pid);
                        if (occupant.HasExited) continue;
                        Debug.Log($"[ArtClaw] 端口 {port} 被进程 {pid}({occupant.ProcessName}) 占用，正在终止...");
                        occupant.Kill();
                        occupant.WaitForExit(3000);
                        Debug.Log($"[ArtClaw] 进程 {pid} 已终止");
                    }
                    catch (ArgumentException) { }
                    catch (Exception) { }
                }
            }
            catch { }
        }

        // ════════════════════════════════════════
        // TCP 监听循环
        // ════════════════════════════════════════

        private static void ListenLoop()
        {
            _running = true;
            while (_running)
            {
                try
                {
                    var client = _listener.AcceptTcpClient();
                    ThreadPool.QueueUserWorkItem(_ => HandleTcpClient(client));
                }
                catch (SocketException) { break; }
                catch (ObjectDisposedException) { break; }
                catch { }
            }
        }

        // ════════════════════════════════════════
        // HTTP 请求处理（ThreadPool 线程 - 手动解析 HTTP）
        // ════════════════════════════════════════

        private static void HandleTcpClient(TcpClient client)
        {
            try
            {
                using (client)
                using (var stream = client.GetStream())
                {
                    stream.ReadTimeout = 10000;
                    stream.WriteTimeout = 10000;

                    // 读取 HTTP 请求
                    var buf = new byte[8192];
                    var ms = new MemoryStream();
                    int contentLength = 0;
                    bool headersDone = false;
                    string method = "";
                    string path = "";

                    while (true)
                    {
                        int n = stream.Read(buf, 0, buf.Length);
                        if (n == 0) return;
                        ms.Write(buf, 0, n);

                        if (!headersDone)
                        {
                            string partial = Encoding.UTF8.GetString(ms.ToArray(), 0, (int)ms.Length);
                            int headerEnd = partial.IndexOf("\r\n\r\n", StringComparison.Ordinal);
                            if (headerEnd >= 0)
                            {
                                headersDone = true;
                                string headerSection = partial.Substring(0, headerEnd);
                                var lines = headerSection.Split(new[] { "\r\n" }, StringSplitOptions.None);
                                if (lines.Length > 0)
                                {
                                    var rp = lines[0].Split(' ');
                                    if (rp.Length >= 2) { method = rp[0]; path = rp[1]; }
                                }
                                foreach (var hl in lines)
                                {
                                    if (hl.StartsWith("Content-Length:", StringComparison.OrdinalIgnoreCase))
                                        int.TryParse(hl.Substring(15).Trim(), out contentLength);
                                }
                            }
                        }

                        if (headersDone)
                        {
                            string all = Encoding.UTF8.GetString(ms.ToArray(), 0, (int)ms.Length);
                            int hdrEnd = all.IndexOf("\r\n\r\n", StringComparison.Ordinal);
                            int bodyLen = (int)ms.Length - hdrEnd - 4;
                            if (bodyLen >= contentLength) break;
                        }
                    }

                    string raw = Encoding.UTF8.GetString(ms.ToArray(), 0, (int)ms.Length);
                    int bodyStart = raw.IndexOf("\r\n\r\n", StringComparison.Ordinal);
                    string body = bodyStart >= 0 ? raw.Substring(bodyStart + 4) : "";

                    path = path.Split('?')[0].TrimEnd('/');
                    string responseJson = Route(method, path, body);

                    // 写 HTTP 响应
                    byte[] bodyBytes = Encoding.UTF8.GetBytes(responseJson);
                    var resp = new StringBuilder();
                    resp.Append("HTTP/1.1 200 OK\r\n");
                    resp.Append("Content-Type: application/json; charset=utf-8\r\n");
                    resp.Append("Content-Length: ").Append(bodyBytes.Length).Append("\r\n");
                    resp.Append("Connection: close\r\n");
                    resp.Append("\r\n");
                    byte[] headerBytes = Encoding.UTF8.GetBytes(resp.ToString());
                    stream.Write(headerBytes, 0, headerBytes.Length);
                    stream.Write(bodyBytes, 0, bodyBytes.Length);
                }
            }
            catch { }
        }

        private static string Route(string method, string path, string body)
        {
            try
            {
                if (method == "POST" && path == "/execute")
                    return HandleExecute(body);
                if (method == "POST" && path == "/batch_execute")
                    return HandleBatchExecute(body);
                if (method == "GET" && path.StartsWith("/result/"))
                    return HandleResult(path.Substring("/result/".Length));
                if (method == "GET" && path == "/health")
                    return HandleHealth();
                if (method == "GET" && path == "/logs")
                    return HandleLogs();
                if (method == "POST" && path == "/validate")
                    return HandleValidate(body);
                return JsonObj("error", "Not Found");
            }
            catch (Exception e)
            {
                return JsonObj("error", e.Message);
            }
        }

        private static string HandleExecute(string body)
        {
            string id = ExtractJsonString(body, "id");
            string code = ExtractJsonString(body, "code");
            if (string.IsNullOrEmpty(id) || string.IsNullOrEmpty(code))
                return JsonObj("error", "缺少 id 或 code 字段");
            _commandQueue.Enqueue(new PendingCommand { Id = id, Code = code });
            return "{\"queued\":true,\"id\":" + JsonStr(id) + "}";
        }

        private static string HandleBatchExecute(string body)
        {
            var payloads = ParseBatchPayload(body);
            if (payloads == null || payloads.Count == 0)
                return JsonObj("error", "批量请求为空");

            var ids = new HashSet<string>();
            foreach (var p in payloads)
            {
                if (!string.IsNullOrEmpty(p.Id) && !string.IsNullOrEmpty(p.Code))
                {
                    _commandQueue.Enqueue(new PendingCommand { Id = p.Id, Code = p.Code });
                    ids.Add(p.Id);
                }
            }

            var deadline = DateTime.UtcNow.AddSeconds(60);
            while (DateTime.UtcNow < deadline)
            {
                bool allDone = true;
                foreach (var id in ids)
                    if (!_results.ContainsKey(id)) { allDone = false; break; }
                if (allDone) break;
                Thread.Sleep(20);
            }

            var sb = new StringBuilder("[");
            int idx = 0;
            foreach (var id in ids)
            {
                if (idx > 0) sb.Append(',');
                if (_results.TryRemove(id, out var r))
                {
                    sb.Append("{\"id\":").Append(JsonStr(id)).Append(",\"done\":true,");
                    sb.Append("\"success\":").Append(string.IsNullOrEmpty(r.Error) ? "true" : "false").Append(',');
                    sb.Append("\"result\":").Append(r.Result ?? "null").Append(',');
                    sb.Append("\"error\":").Append(JsonStr(r.Error ?? "")).Append(',');
                    sb.Append("\"output\":").Append(JsonStr(r.Output ?? "")).Append('}');
                }
                else
                {
                    sb.Append("{\"id\":").Append(JsonStr(id)).Append(",\"done\":false,");
                    sb.Append("\"error\":").Append(JsonStr("执行超时")).Append('}');
                }
                idx++;
            }
            sb.Append(']');
            return sb.ToString();
        }

        private static string HandleResult(string id)
        {
            if (_results.TryGetValue(id, out var result))
            {
                _results.TryRemove(id, out _);
                var sb = new StringBuilder("{\"done\":true,");
                sb.Append("\"success\":").Append(string.IsNullOrEmpty(result.Error) ? "true" : "false").Append(',');
                sb.Append("\"result\":").Append(result.Result ?? "null").Append(',');
                sb.Append("\"error\":").Append(JsonStr(result.Error ?? "")).Append(',');
                sb.Append("\"output\":").Append(JsonStr(result.Output ?? "")).Append('}');
                return sb.ToString();
            }
            return "{\"done\":false}";
        }

        private static string HandleHealth()
        {
            var sb = new StringBuilder("{\"status\":\"ok\",\"version\":\"1.0.0\",");
            sb.Append("\"port\":").Append(_httpPort).Append(',');
            sb.Append("\"unity_version\":").Append(JsonStr(_cachedUnityVersion ?? "")).Append(',');
            sb.Append("\"project_name\":").Append(JsonStr(_cachedProductName ?? "")).Append(',');
            sb.Append("\"is_playing\":").Append(_cachedIsPlaying ? "true" : "false").Append(',');
            sb.Append("\"is_compiling\":").Append(_cachedIsCompiling ? "true" : "false").Append(',');
            sb.Append("\"execution_count\":").Append(ExecutionLog.Count).Append('}');
            return sb.ToString();
        }

        private static string HandleLogs()
        {
            var logs = ExecutionLog.ToArray();
            var sb = new StringBuilder("{\"logs\":[");
            for (int i = 0; i < logs.Length; i++)
            {
                if (i > 0) sb.Append(',');
                var e = logs[i];
                sb.Append("{\"timestamp\":").Append(JsonStr(e.Timestamp.ToString("HH:mm:ss.fff"))).Append(',');
                sb.Append("\"success\":").Append(e.Success ? "true" : "false").Append(',');
                string preview = e.Code.Length > 100 ? e.Code.Substring(0, 100) + "..." : e.Code;
                sb.Append("\"code_preview\":").Append(JsonStr(preview)).Append(',');
                sb.Append("\"result\":").Append(e.Result != null ? JsonStr(e.Result) : "null").Append(',');
                sb.Append("\"error\":").Append(JsonStr(e.Error ?? "")).Append('}');
            }
            sb.Append("]}");
            return sb.ToString();
        }

        private static string HandleValidate(string body)
        {
            string code = ExtractJsonString(body, "code");
            try
            {
                var syntaxTree = CSharpSyntaxTree.ParseText(code);
                var compilation = CSharpCompilation.Create("ValidateScript",
                    new[] { syntaxTree }, _roslynRefs,
                    new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));
                var diagnostics = compilation.GetDiagnostics();
                var errors = diagnostics.Where(d => d.Severity == DiagnosticSeverity.Error).ToList();
                var sb = new StringBuilder("{\"valid\":").Append(errors.Count == 0 ? "true" : "false");
                if (errors.Count > 0)
                {
                    sb.Append(",\"errors\":[");
                    for (int i = 0; i < errors.Count; i++)
                    {
                        if (i > 0) sb.Append(',');
                        var d = errors[i];
                        var pos = d.Location.GetLineSpan().StartLinePosition;
                        sb.Append("{\"line\":").Append(pos.Line + 1).Append(",\"column\":").Append(pos.Character + 1);
                        sb.Append(",\"message\":").Append(JsonStr(d.GetMessage())).Append(",\"id\":").Append(JsonStr(d.Id)).Append('}');
                    }
                    sb.Append(']');
                }
                sb.Append('}');
                return sb.ToString();
            }
            catch (Exception e)
            {
                return "{\"valid\":false,\"errors\":[{\"message\":" + JsonStr(e.Message) + "}]}";
            }
        }

        // ════════════════════════════════════════
        // 主线程命令消费
        // ════════════════════════════════════════

        private static void OnEditorUpdate()
        {
            _cachedIsPlaying = EditorApplication.isPlaying;
            _cachedIsCompiling = EditorApplication.isCompiling;

            int processed = 0;
            while (processed < MAX_EXEC_PER_FRAME && _commandQueue.TryDequeue(out var cmd))
            {
                ExecuteCommand(cmd);
                processed++;
            }
        }

        private static void ExecuteCommand(PendingCommand cmd)
        {
            try
            {
                var scriptName = $"Script_{Interlocked.Increment(ref _scriptCounter)}";
                var wrappedCode = $@"
using System;
using UnityEngine;
using UnityEditor;
using UnityEngine.SceneManagement;
using UnityEditor.SceneManagement;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Text;

public static class {scriptName}
{{
    public static object Execute()
    {{
        {cmd.Code}
        return null;
    }}
}}";
                var syntaxTree = CSharpSyntaxTree.ParseText(wrappedCode);
                var compilation = CSharpCompilation.Create(scriptName,
                    new[] { syntaxTree }, _roslynRefs,
                    new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));

                using var peStream = new MemoryStream();
                var emitResult = compilation.Emit(peStream);

                if (!emitResult.Success)
                {
                    var errors = emitResult.Diagnostics
                        .Where(d => d.Severity == DiagnosticSeverity.Error)
                        .Select(d => d.ToString()).ToArray();
                    var error = string.Join("\n", errors);
                    _results[cmd.Id] = new CommandResult { Error = error };
                    ExecutionLog.Add(new LogEntry { Success = false, Code = cmd.Code, Error = error });
                    return;
                }

                peStream.Seek(0, SeekOrigin.Begin);
                var assembly = Assembly.Load(peStream.ToArray());
                var type = assembly.GetType(scriptName);
                var method = type?.GetMethod("Execute");
                if (method == null)
                {
                    _results[cmd.Id] = new CommandResult { Error = "找不到 Execute 入口方法" };
                    ExecutionLog.Add(new LogEntry { Success = false, Code = cmd.Code, Error = "找不到入口方法" });
                    return;
                }

                var result = method.Invoke(null, null);
                var resultJson = result != null ? SerializeResult(result) : null;
                _results[cmd.Id] = new CommandResult { Result = resultJson };
                ExecutionLog.Add(new LogEntry { Success = true, Code = cmd.Code, Result = resultJson });
            }
            catch (Exception e)
            {
                var error = FormatException(e);
                _results[cmd.Id] = new CommandResult { Error = error };
                ExecutionLog.Add(new LogEntry { Success = false, Code = cmd.Code, Error = error });
                Debug.LogWarning($"[ArtClaw] 执行异常 (id={cmd.Id}): {error}");
            }
        }

        // ════════════════════════════════════════
        // 结果序列化（主线程）
        // ════════════════════════════════════════

        private static string SerializeResult(object value)
        {
            if (value == null) return "null";
            if (value is UnityEngine.Object uo)
            {
                var sb = new StringBuilder("{\"type\":").Append(JsonStr(uo.GetType().Name));
                sb.Append(",\"name\":").Append(JsonStr(uo.name));
                string path = uo is GameObject go ? AssetDatabase.GetAssetPath(go) : null;
                sb.Append(",\"path\":").Append(path != null ? JsonStr(path) : "null");
                sb.Append(",\"instanceId\":").Append(uo.GetInstanceID()).Append('}');
                return sb.ToString();
            }
            if (value is Vector2 v2) return $"{{\"x\":{v2.x},\"y\":{v2.y}}}";
            if (value is Vector3 v3) return $"{{\"x\":{v3.x},\"y\":{v3.y},\"z\":{v3.z}}}";
            if (value is Vector4 v4) return $"{{\"x\":{v4.x},\"y\":{v4.y},\"z\":{v4.z},\"w\":{v4.w}}}";
            if (value is Color c) return $"{{\"r\":{c.r},\"g\":{c.g},\"b\":{c.b},\"a\":{c.a}}}";
            if (value is int i) return i.ToString();
            if (value is float f) return f.ToString("R");
            if (value is double d) return d.ToString("R");
            if (value is bool b) return b ? "true" : "false";
            if (value is string s) return JsonStr(s);
            if (value is System.Collections.IEnumerable en && !(value is string))
            {
                var items = new List<string>();
                foreach (var item in en) items.Add(SerializeResult(item));
                return "[" + string.Join(",", items) + "]";
            }
            return JsonStr(value.ToString());
        }

        private static string FormatException(Exception e)
        {
            if (e is AggregateException ae && ae.InnerExceptions.Count > 0)
                e = ae.InnerExceptions[0];
            var sb = new StringBuilder();
            sb.AppendLine($"[{e.GetType().Name}] {e.Message}");
            if (e.StackTrace != null)
            {
                foreach (var line in e.StackTrace.Split('\n'))
                    if (line.Contains("roslyn") || line.Contains("CommandServer") || line.Contains("at Submission#"))
                        sb.AppendLine($"  {line.Trim()}");
            }
            return sb.ToString().TrimEnd();
        }

        // ════════════════════════════════════════
        // JSON 工具（纯字符串，线程安全）
        // ════════════════════════════════════════

        private static string JsonStr(string s)
        {
            if (s == null) return "null";
            var sb = new StringBuilder(s.Length + 8);
            sb.Append('"');
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\b': sb.Append("\\b"); break;
                    case '\f': sb.Append("\\f"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 32) sb.AppendFormat("\\u{0:X4}", (int)c);
                        else sb.Append(c);
                        break;
                }
            }
            sb.Append('"');
            return sb.ToString();
        }

        private static string JsonObj(string key, string value)
        {
            return "{" + JsonStr(key) + ":" + JsonStr(value) + "}";
        }

        private static string ExtractJsonString(string json, string key)
        {
            string pattern = "\"" + key + "\"";
            int keyIdx = json.IndexOf(pattern, StringComparison.Ordinal);
            if (keyIdx < 0) return null;
            int colonIdx = json.IndexOf(':', keyIdx + pattern.Length);
            if (colonIdx < 0) return null;
            int valStart = colonIdx + 1;
            while (valStart < json.Length && json[valStart] == ' ') valStart++;
            if (valStart >= json.Length) return null;
            if (json[valStart] == '"')
            {
                var sb = new StringBuilder();
                int i = valStart + 1;
                while (i < json.Length)
                {
                    if (json[i] == '\\')
                    {
                        if (i + 1 < json.Length) { sb.Append(json[i + 1]); i += 2; }
                        else break;
                    }
                    else if (json[i] == '"') break;
                    else { sb.Append(json[i]); i++; }
                }
                return sb.ToString();
            }
            int valEnd = valStart;
            while (valEnd < json.Length && json[valEnd] != ',' && json[valEnd] != '}' && json[valEnd] != ']')
                valEnd++;
            return json.Substring(valStart, valEnd - valStart).Trim();
        }

        private static List<PendingCommand> ParseBatchPayload(string json)
        {
            var result = new List<PendingCommand>();
            if (string.IsNullOrWhiteSpace(json)) return result;
            int i = 0;
            while (i < json.Length)
            {
                int start = json.IndexOf("{\"id\"", i, StringComparison.Ordinal);
                if (start < 0) break;
                int end = json.IndexOf("}", start);
                if (end < 0) break;
                string item = json.Substring(start, end - start + 1);
                string id = ExtractJsonString(item, "id");
                string code = ExtractJsonString(item, "code");
                if (!string.IsNullOrEmpty(id) && !string.IsNullOrEmpty(code))
                    result.Add(new PendingCommand { Id = id, Code = code });
                i = end + 1;
            }
            return result;
        }

        // ════════════════════════════════════════
        // 内部数据结构
        // ════════════════════════════════════════

        private class PendingCommand { public string Id; public string Code; }
        private class CommandResult { public string Result; public string Error; public string Output; }

        public class RingBuffer<T>
        {
            private readonly T[] _buffer;
            private int _head, _count;
            private readonly int _capacity;
            private readonly object _lock = new object();

            public RingBuffer(int capacity) { _capacity = capacity; _buffer = new T[capacity]; }

            public void Add(T item)
            {
                lock (_lock)
                {
                    _buffer[_head] = item;
                    _head = (_head + 1) % _capacity;
                    if (_count < _capacity) _count++;
                }
            }

            public int Count { get { lock (_lock) { return _count; } } }

            public T[] ToArray()
            {
                lock (_lock)
                {
                    var result = new T[_count];
                    for (int i = 0; i < _count; i++)
                        result[i] = _buffer[(_head - _count + i + _capacity) % _capacity];
                    return result;
                }
            }
        }

        public class LogEntry
        {
            public DateTime Timestamp = DateTime.Now;
            public bool Success;
            public string Code;
            public string Result;
            public string Error;
        }
    }
}
