// UnityClawDashboard.cs
// Unity Editor Dashboard 窗口 - M1: 实时连接状态 + 执行日志面板
//
// 改进（M1）:
//   - 实时连接状态：MCP端口、CommandServer端口、Unity版本
//   - 执行日志面板：最近 50 条滚动列表
//   - 错误高亮：失败日志红色标记

using System;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

namespace ArtClaw.Unity
{
    /// <summary>
    /// ArtClaw Bridge Dashboard 窗口。
    /// 显示连接状态、执行日志、快捷操作。
    /// </summary>
    public class UnityClawDashboard : EditorWindow
    {
        // ════════════════════════════════════════
        // 常量
        // ════════════════════════════════════════

        private const int MAX_LOG_DISPLAY = 50;
        private const float LOG_REFRESH_INTERVAL = 1.0f;

        // ════════════════════════════════════════
        // 样式
        // ════════════════════════════════════════

        private static readonly GUIStyle TitleStyle = new GUIStyle(EditorStyles.boldLabel)
        {
            fontSize = 14,
            alignment = TextAnchor.MiddleLeft,
        };

        private static readonly GUIStyle StatusOkStyle = new GUIStyle(EditorStyles.label)
        {
            normal = { textColor = new Color(0.2f, 0.85f, 0.4f) },
            fontStyle = FontStyle.Bold,
        };

        private static readonly GUIStyle StatusErrorStyle = new GUIStyle(EditorStyles.label)
        {
            normal = { textColor = new Color(0.9f, 0.3f, 0.3f) },
            fontStyle = FontStyle.Bold,
        };

        private static readonly GUIStyle LogEntryStyle = new GUIStyle(EditorStyles.miniLabel)
        {
            richText = true,
            wordWrap = false,
        };

        // ════════════════════════════════════════
        // 状态
        // ════════════════════════════════════════

        private bool _isRunning;
        private int _mcpPort = 8088;
        private int _commandServerPort = 8089;
        private string _unityVersion = "...";
        private string _projectName = "...";
        private bool _isPlaying;
        private bool _isCompiling;
        private int _executionCount;

        private Vector2 _logScrollPos;
        private List<LogDisplayEntry> _displayLogs = new List<LogDisplayEntry>();
        private float _lastRefreshTime;
        private bool _logsExpanded = true;

        // ════════════════════════════════════════
        // 入口
        // ════════════════════════════════════════

        [MenuItem("ArtClaw/Dashboard #&A")]
        public static void ShowWindow()
        {
            var window = GetWindow<UnityClawDashboard>("ArtClaw Bridge");
            window.minSize = new Vector2(380, 400);
            window.Show();
        }

        // ════════════════════════════════════════
        // GUI
        // ════════════════════════════════════════

        private void OnEnable()
        {
            RefreshHealth();
        }

        private void OnGUI()
        {
            // 标题
            GUILayout.Space(8);
            GUILayout.Label("ArtClaw Bridge · Unity", TitleStyle);
            GUILayout.Space(4);

            DrawStatusSection();
            GUILayout.Space(6);

            DrawControlsSection();
            GUILayout.Space(6);

            DrawLogSection();

            GUILayout.FlexibleSpace();
            DrawFooter();
        }

        private void DrawStatusSection()
        {
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);

            // 连接状态行
            EditorGUILayout.BeginHorizontal();
            GUILayout.Label("连接状态:", GUILayout.Width(80));
            Color statusColor = _isRunning ? new Color(0.2f, 0.85f, 0.4f) : new Color(0.85f, 0.3f, 0.3f);
            GUI.color = statusColor;
            GUILayout.Label(_isRunning ? "● 运行中" : "○ 已停止", _isRunning ? StatusOkStyle : StatusErrorStyle);
            GUI.color = Color.white;
            GUILayout.FlexibleSpace();
            EditorGUILayout.EndHorizontal();

            // Unity 版本
            EditorGUILayout.BeginHorizontal();
            GUILayout.Label("Unity 版本:", GUILayout.Width(80));
            GUILayout.Label(_unityVersion, EditorStyles.miniLabel);
            GUILayout.FlexibleSpace();
            EditorGUILayout.EndHorizontal();

            // 项目名
            EditorGUILayout.BeginHorizontal();
            GUILayout.Label("项目:", GUILayout.Width(80));
            GUILayout.Label(_projectName, EditorStyles.miniLabel);
            GUILayout.FlexibleSpace();
            EditorGUILayout.EndHorizontal();

            // 端口信息
            EditorGUILayout.BeginHorizontal();
            GUILayout.Label("端口:", GUILayout.Width(80));
            GUILayout.Label($"MCP {_mcpPort} | CommandServer {_commandServerPort}", EditorStyles.miniLabel);
            GUILayout.FlexibleSpace();
            EditorGUILayout.EndHorizontal();

            // 播放/编译状态
            EditorGUILayout.BeginHorizontal();
            GUILayout.Label("状态:", GUILayout.Width(80));

            if (_isCompiling)
            {
                GUI.color = new Color(1f, 0.8f, 0.2f);
                GUILayout.Label("编译中...", EditorStyles.miniLabel);
                GUI.color = Color.white;
            }
            else if (_isPlaying)
            {
                GUI.color = new Color(0.3f, 0.7f, 1f);
                GUILayout.Label("播放中", EditorStyles.miniLabel);
                GUI.color = Color.white;
            }
            else
            {
                GUILayout.Label("就绪", EditorStyles.miniLabel);
            }

            GUILayout.FlexibleSpace();

            // 执行计数
            GUILayout.Label($"执行: {_executionCount}", EditorStyles.miniLabel);

            EditorGUILayout.EndHorizontal();
            EditorGUILayout.EndVertical();
        }

        private void DrawControlsSection()
        {
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            GUILayout.Label("控制", EditorStyles.boldLabel);

            EditorGUILayout.BeginHorizontal();

            GUI.enabled = !_isRunning;
            if (GUILayout.Button("启动", GUILayout.Height(26)))
            {
                UnityClawBridgeBootstrap.StartMCPServer();
                _isRunning = true;
            }
            GUI.enabled = _isRunning;
            if (GUILayout.Button("停止", GUILayout.Height(26)))
            {
                UnityClawBridgeBootstrap.StopMCPServer();
                _isRunning = false;
            }
            GUI.enabled = true;

            if (GUILayout.Button("刷新状态", GUILayout.Height(26)))
            {
                RefreshHealth();
            }

            EditorGUILayout.EndHorizontal();
            EditorGUILayout.EndVertical();
        }

        private void DrawLogSection()
        {
            _logsExpanded = EditorGUILayout.Foldout(_logsExpanded, $"执行日志 ({_displayLogs.Count})", true);
            if (!_logsExpanded) return;

            EditorGUILayout.BeginVertical(EditorStyles.helpBox);

            // 工具栏
            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button("清空", GUILayout.Width(50)))
            {
                _displayLogs.Clear();
            }
            if (GUILayout.Button("刷新", GUILayout.Width(50)))
            {
                RefreshLogsFromServer();
            }

            GUILayout.FlexibleSpace();

            // 统计
            int successCount = 0, failCount = 0;
            foreach (var log in _displayLogs)
            {
                if (log.Success) successCount++;
                else failCount++;
            }
            GUI.color = new Color(0.2f, 0.85f, 0.4f);
            GUILayout.Label($"✓ {successCount}", EditorStyles.miniLabel);
            GUI.color = new Color(0.9f, 0.3f, 0.3f);
            GUILayout.Label($"✗ {failCount}", EditorStyles.miniLabel);
            GUI.color = Color.white;

            EditorGUILayout.EndHorizontal();

            GUILayout.Space(4);

            // 日志列表
            if (_displayLogs.Count == 0)
            {
                GUILayout.Label("暂无执行日志", EditorStyles.centeredGreyMiniLabel);
            }
            else
            {
                _logScrollPos = EditorGUILayout.BeginScrollView(_logScrollPos, GUILayout.Height(200));

                for (int i = _displayLogs.Count - 1; i >= 0; i--)
                {
                    var log = _displayLogs[i];
                    DrawLogEntry(log);
                }

                EditorGUILayout.EndScrollView();
            }

            EditorGUILayout.EndVertical();
        }

        private void DrawLogEntry(LogDisplayEntry log)
        {
            EditorGUILayout.BeginHorizontal(EditorStyles.helpBox);

            // 状态图标
            if (log.Success)
            {
                GUI.color = new Color(0.2f, 0.85f, 0.4f);
                GUILayout.Label("✓", GUILayout.Width(20));
            }
            else
            {
                GUI.color = new Color(0.9f, 0.3f, 0.3f);
                GUILayout.Label("✗", GUILayout.Width(20));
            }
            GUI.color = Color.white;

            // 时间戳
            GUILayout.Label(log.Timestamp, GUILayout.Width(70));

            // 代码预览
            string codePreview = log.Code;
            if (codePreview.Length > 60)
                codePreview = codePreview.Substring(0, 60) + "...";

            GUI.enabled = !log.Success;
            GUI.color = log.Success ? Color.white : new Color(1f, 0.6f, 0.6f);
            GUILayout.Label(codePreview, LogEntryStyle);
            GUI.color = Color.white;
            GUI.enabled = true;

            GUILayout.FlexibleSpace();

            // 查看详情按钮
            if (GUILayout.Button("详情", GUILayout.Width(40)))
            {
                ShowLogDetail(log);
            }

            EditorGUILayout.EndHorizontal();
        }

        private void DrawFooter()
        {
            EditorGUILayout.BeginHorizontal();
            GUILayout.FlexibleSpace();
            GUILayout.Label($"v1.0.0 | Unity {Application.unityVersion}", EditorStyles.miniLabel);
            EditorGUILayout.EndHorizontal();
        }

        // ════════════════════════════════════════
        // 数据刷新
        // ════════════════════════════════════════

        private void OnInspectorUpdate()
        {
            // 每秒刷新一次
            if (Time.realtimeSinceStartup - _lastRefreshTime > LOG_REFRESH_INTERVAL)
            {
                _lastRefreshTime = Time.realtimeSinceStartup;
                RefreshHealth();
                RefreshLogsFromServer();
                Repaint();
            }
        }

        private void RefreshHealth()
        {
            try
            {
                var url = $"http://127.0.0.1:{_commandServerPort}/health";
                var www = new UnityEngine.WWW(url);
                float deadline = Time.realtimeSinceStartup + 2f;
                while (!www.isDone && Time.realtimeSinceStartup < deadline) { }

                if (www.isDone && string.IsNullOrEmpty(www.error))
                {
                    var json = www.text;
                    var data = JsonUtility.FromJson<HealthResponse>(json);

                    _isRunning = data.status == "ok";
                    _unityVersion = data.unity_version ?? "...";
                    _projectName = data.project_name ?? "...";
                    _isPlaying = data.is_playing;
                    _isCompiling = data.is_compiling;
                    _executionCount = data.execution_count;
                    _commandServerPort = data.port;
                }
                else
                {
                    _isRunning = false;
                }
            }
            catch
            {
                _isRunning = false;
            }
        }

        private void RefreshLogsFromServer()
        {
            try
            {
                var url = $"http://127.0.0.1:{_commandServerPort}/logs";
                var www = new UnityEngine.WWW(url);
                float deadline = Time.realtimeSinceStartup + 2f;
                while (!www.isDone && Time.realtimeSinceStartup < deadline) { }

                if (www.isDone && string.IsNullOrEmpty(www.error))
                {
                    var json = www.text;
                    var data = JsonUtility.FromJson<LogsResponse>(json);

                    _displayLogs.Clear();
                    if (data.logs != null)
                    {
                        foreach (var entry in data.logs)
                        {
                            _displayLogs.Add(new LogDisplayEntry
                            {
                                Timestamp = entry.timestamp ?? "--:--:--",
                                Success = entry.success,
                                Code = entry.code_preview ?? "",
                                Error = entry.error ?? "",
                                Result = entry.result?.ToString() ?? "",
                            });
                        }

                        // 限制显示数量
                        while (_displayLogs.Count > MAX_LOG_DISPLAY)
                            _displayLogs.RemoveAt(0);
                    }
                }
            }
            catch { }
        }

        private void ShowLogDetail(LogDisplayEntry log)
        {
            string title = log.Success ? "执行详情" : "错误详情";
            string message = log.Success
                ? $"代码:\n{log.Code}\n\n结果:\n{log.Result}"
                : $"代码:\n{log.Code}\n\n错误:\n{log.Error}";

            EditorUtility.DisplayDialog(title, message, "关闭");
        }

        // ════════════════════════════════════════
        // JSON 响应结构
        // ════════════════════════════════════════

        [Serializable]
        private class HealthResponse
        {
            public string status;
            public string unity_version;
            public string project_name;
            public bool is_playing;
            public bool is_compiling;
            public int execution_count;
            public int port;
        }

        [Serializable]
        private class LogsResponse
        {
            public List<LogEntry> logs;
        }

        [Serializable]
        private class LogEntry
        {
            public string timestamp;
            public bool success;
            public string code_preview;
            public object result;
            public string error;
        }

        private class LogDisplayEntry
        {
            public string Timestamp;
            public bool Success;
            public string Code;
            public string Error;
            public string Result;
        }
    }

    /// <summary>持久化设置（存储于 EditorPrefs）</summary>
    public static class UnityClawBridgeSettings
    {
        private const string KEY_AUTO_START = "ArtClaw.AutoStart";

        public static bool AutoStart
        {
            get => EditorPrefs.GetBool(KEY_AUTO_START, true);
            set => EditorPrefs.SetBool(KEY_AUTO_START, value);
        }
    }
}
