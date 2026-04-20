﻿// UnityClawDashboard.cs
// Unity Editor Dashboard 窗口 - M1: 实时连接状态 + 执行日志面板

using System;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;

namespace ArtClaw.Unity
{
    public class UnityClawDashboard : EditorWindow
    {
        private const int MAX_LOG_DISPLAY = 50;
        private const float LOG_REFRESH_INTERVAL = 1.0f;

        private static GUIStyle _titleStyle;
        private static GUIStyle TitleStyle => _titleStyle ??= new GUIStyle(EditorStyles.boldLabel)
        {
            fontSize = 14,
            alignment = TextAnchor.MiddleLeft,
        };

        private static GUIStyle _statusOkStyle;
        private static GUIStyle StatusOkStyle => _statusOkStyle ??= new GUIStyle(EditorStyles.label)
        {
            normal = { textColor = new Color(0.2f, 0.85f, 0.4f) },
            fontStyle = FontStyle.Bold,
        };

        private static GUIStyle _statusErrorStyle;
        private static GUIStyle StatusErrorStyle => _statusErrorStyle ??= new GUIStyle(EditorStyles.label)
        {
            normal = { textColor = new Color(0.9f, 0.3f, 0.3f) },
            fontStyle = FontStyle.Bold,
        };

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

        [MenuItem("ArtClaw/Dashboard #&A")]
        public static void ShowWindow()
        {
            var window = GetWindow<UnityClawDashboard>("ArtClaw Bridge");
            window.minSize = new Vector2(380, 400);
            window.Show();
        }

        private void OnEnable() => RefreshHealth();

        private void OnGUI()
        {
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

            EditorGUILayout.BeginHorizontal();
            GUILayout.Label("连接状态:", GUILayout.Width(80));
            Color statusColor = _isRunning ? new Color(0.2f, 0.85f, 0.4f) : new Color(0.85f, 0.3f, 0.3f);
            GUI.color = statusColor;
            GUILayout.Label(_isRunning ? "● 运行中" : "○ 已停止", _isRunning ? StatusOkStyle : StatusErrorStyle);
            GUI.color = Color.white;
            GUILayout.FlexibleSpace();
            EditorGUILayout.EndHorizontal();

            EditorGUILayout.BeginHorizontal();
            GUILayout.Label("Unity 版本:", GUILayout.Width(80));
            GUILayout.Label(_unityVersion, EditorStyles.miniLabel);
            GUILayout.FlexibleSpace();
            EditorGUILayout.EndHorizontal();

            EditorGUILayout.BeginHorizontal();
            GUILayout.Label("项目:", GUILayout.Width(80));
            GUILayout.Label(_projectName, EditorStyles.miniLabel);
            GUILayout.FlexibleSpace();
            EditorGUILayout.EndHorizontal();

            EditorGUILayout.BeginHorizontal();
            GUILayout.Label("端口:", GUILayout.Width(80));
            GUILayout.Label($"MCP {_mcpPort} | CommandServer {_commandServerPort}", EditorStyles.miniLabel);
            GUILayout.FlexibleSpace();
            EditorGUILayout.EndHorizontal();

            EditorGUILayout.BeginHorizontal();
            GUILayout.Label("状态:", GUILayout.Width(80));

            if (_isCompiling)
            {
                GUI.color = new Color(1f, 0.8f, 0.2f);
                GUILayout.Label("编译中...", EditorStyles.miniLabel);
            }
            else if (_isPlaying)
            {
                GUI.color = new Color(0.3f, 0.7f, 1f);
                GUILayout.Label("播放中", EditorStyles.miniLabel);
            }
            else
            {
                GUILayout.Label("就绪", EditorStyles.miniLabel);
            }
            GUI.color = Color.white;

            GUILayout.FlexibleSpace();
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
                RefreshHealth();

            EditorGUILayout.EndHorizontal();
            EditorGUILayout.EndVertical();
        }

        private void DrawLogSection()
        {
            _logsExpanded = EditorGUILayout.Foldout(_logsExpanded, $"执行日志 ({_displayLogs.Count})", true);
            if (!_logsExpanded) return;

            EditorGUILayout.BeginVertical(EditorStyles.helpBox);

            EditorGUILayout.BeginHorizontal();
            if (GUILayout.Button("清空", GUILayout.Width(50)))
                _displayLogs.Clear();
            if (GUILayout.Button("刷新", GUILayout.Width(50)))
                RefreshLogsFromServer();

            GUILayout.FlexibleSpace();

            int ok = 0, fail = 0;
            foreach (var l in _displayLogs) { if (l.Success) ok++; else fail++; }
            GUI.color = new Color(0.2f, 0.85f, 0.4f);
            GUILayout.Label($"✓ {ok}", EditorStyles.miniLabel);
            GUI.color = new Color(0.9f, 0.3f, 0.3f);
            GUILayout.Label($"✗ {fail}", EditorStyles.miniLabel);
            GUI.color = Color.white;
            EditorGUILayout.EndHorizontal();

            GUILayout.Space(4);

            if (_displayLogs.Count == 0)
            {
                GUILayout.Label("暂无执行日志", EditorStyles.centeredGreyMiniLabel);
            }
            else
            {
                _logScrollPos = EditorGUILayout.BeginScrollView(_logScrollPos, GUILayout.Height(200));
                for (int i = _displayLogs.Count - 1; i >= 0; i--)
                    DrawLogEntry(_displayLogs[i]);
                EditorGUILayout.EndScrollView();
            }

            EditorGUILayout.EndVertical();
        }

        private void DrawLogEntry(LogDisplayEntry log)
        {
            EditorGUILayout.BeginHorizontal(EditorStyles.helpBox);

            GUI.color = log.Success ? new Color(0.2f, 0.85f, 0.4f) : new Color(0.9f, 0.3f, 0.3f);
            GUILayout.Label(log.Success ? "✓" : "✗", GUILayout.Width(20));
            GUI.color = Color.white;

            GUILayout.Label(log.Timestamp, GUILayout.Width(70));

            string preview = log.Code.Length > 60 ? log.Code.Substring(0, 60) + "..." : log.Code;
            GUILayout.Label(preview, EditorStyles.miniLabel);
            GUILayout.FlexibleSpace();

            if (GUILayout.Button("详情", GUILayout.Width(40)))
                EditorUtility.DisplayDialog(
                    log.Success ? "执行详情" : "错误详情",
                    log.Success ? $"代码:\n{log.Code}\n\n结果:\n{log.Result}" : $"代码:\n{log.Code}\n\n错误:\n{log.Error}",
                    "关闭");

            EditorGUILayout.EndHorizontal();
        }

        private void DrawFooter()
        {
            EditorGUILayout.BeginHorizontal();
            GUILayout.FlexibleSpace();
            GUILayout.Label($"v1.0.0 | Unity {Application.unityVersion}", EditorStyles.miniLabel);
            EditorGUILayout.EndHorizontal();
        }

        private void OnInspectorUpdate()
        {
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
                using (var request = UnityWebRequest.Get($"http://127.0.0.1:{_commandServerPort}/health"))
                {
                    var op = request.SendWebRequest();
                    float deadline = Time.realtimeSinceStartup + 2f;
                    while (!op.isDone && Time.realtimeSinceStartup < deadline) { }
                    if (request.result != UnityWebRequest.Result.Success) { _isRunning = false; return; }
                    var data = JsonUtility.FromJson<HealthResponse>(request.downloadHandler.text);
                    _isRunning = data.status == "ok";
                    _unityVersion = data.unity_version ?? "...";
                    _projectName = data.project_name ?? "...";
                    _isPlaying = data.is_playing;
                    _isCompiling = data.is_compiling;
                    _executionCount = data.execution_count;
                    _commandServerPort = data.port;
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
                using (var request = UnityWebRequest.Get($"http://127.0.0.1:{_commandServerPort}/logs"))
                {
                    var op = request.SendWebRequest();
                    float deadline = Time.realtimeSinceStartup + 2f;
                    while (!op.isDone && Time.realtimeSinceStartup < deadline) { }
                    if (request.result != UnityWebRequest.Result.Success) return;
                    var data = JsonUtility.FromJson<LogsResponse>(request.downloadHandler.text);
                    _displayLogs.Clear();
                    if (data.logs != null)
                    {
                        foreach (var e in data.logs)
                        {
                            _displayLogs.Add(new LogDisplayEntry
                            {
                                Timestamp = e.timestamp ?? "--:--:--",
                                Success = e.success,
                                Code = e.code_preview ?? "",
                                Error = e.error ?? "",
                                Result = e.result ?? "",
                            });
                        }
                        while (_displayLogs.Count > MAX_LOG_DISPLAY)
                            _displayLogs.RemoveAt(0);
                    }
                }
            }
            catch { }
        }

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
            public string result;
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

