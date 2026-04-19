// UnityClawBridgeBootstrap.cs
// Unity Editor 插件入口 - 生命周期管理 + Python MCP 进程桥接
// 对应 UEClawBridge 的 EditorAgentSubsystem

using System;
using System.Diagnostics;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace ArtClaw.Unity
{
    /// <summary>
    /// UnityClawBridge 编辑器启动引导类。
    /// 负责：启动 Python MCP Server、监控进程、提供菜单入口。
    /// </summary>
    [InitializeOnLoad]
    public static class UnityClawBridgeBootstrap
    {
        // Python 进程句柄
        private static Process _pythonProcess;

        // MCP Server 端口（Unity 标准端口为 8088）
        private const int MCP_DEFAULT_PORT = 8088;

        // Python 脚本路径（相对于插件目录）
        private static string PythonScriptPath =>
            Path.Combine(PluginRoot, "Python", "bootstrap.py");

        // 插件根目录
        private static string PluginRoot =>
            Path.GetFullPath(Path.Combine(Application.dataPath, "..", "Packages", "com.artclaw.unity-claw-bridge"));

        static UnityClawBridgeBootstrap()
        {
            // 编辑器启动时自动运行
            EditorApplication.delayCall += OnEditorReady;
            AssemblyReloadEvents.beforeAssemblyReload += OnBeforeAssemblyReload;
        }

        private static void OnEditorReady()
        {
            if (UnityClawBridgeSettings.AutoStart)
            {
                StartMCPServer();
            }
        }

        private static void OnBeforeAssemblyReload()
        {
            StopMCPServer();
        }

        /// <summary>启动 Python MCP Server 进程</summary>
        public static void StartMCPServer()
        {
            if (_pythonProcess != null && !_pythonProcess.HasExited)
            {
                UnityEngine.Debug.Log("[ArtClaw] MCP Server 已在运行");
                return;
            }

            if (!File.Exists(PythonScriptPath))
            {
                UnityEngine.Debug.LogError($"[ArtClaw] 找不到 Python 脚本: {PythonScriptPath}");
                return;
            }

            string pythonExe = FindPythonExecutable();
            if (string.IsNullOrEmpty(pythonExe))
            {
                UnityEngine.Debug.LogError("[ArtClaw] 未找到 Python 可执行文件，请确保 Python 3.9+ 已安装");
                return;
            }

            var psi = new ProcessStartInfo
            {
                FileName = pythonExe,
                Arguments = $"\"{PythonScriptPath}\" --port {MCP_DEFAULT_PORT} --plugin-root \"{PluginRoot}\"",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                WorkingDirectory = Path.Combine(PluginRoot, "Python"),
            };

            // 注入 ARTCLAW_PROJECT_ROOT 环境变量供 Python 端回溯 core/
            string artclawRoot = Path.GetFullPath(Path.Combine(PluginRoot, "..", "..", "..", ".."));
            psi.EnvironmentVariables["ARTCLAW_PROJECT_ROOT"] = artclawRoot;

            _pythonProcess = new Process { StartInfo = psi, EnableRaisingEvents = true };
            _pythonProcess.OutputDataReceived += (_, e) =>
            {
                if (!string.IsNullOrEmpty(e.Data))
                    UnityEngine.Debug.Log($"[ArtClaw|Py] {e.Data}");
            };
            _pythonProcess.ErrorDataReceived += (_, e) =>
            {
                if (!string.IsNullOrEmpty(e.Data))
                    UnityEngine.Debug.LogWarning($"[ArtClaw|Py] {e.Data}");
            };
            _pythonProcess.Exited += (_, _) =>
            {
                UnityEngine.Debug.LogWarning("[ArtClaw] Python MCP Server 进程意外退出");
                _pythonProcess = null;
            };

            _pythonProcess.Start();
            _pythonProcess.BeginOutputReadLine();
            _pythonProcess.BeginErrorReadLine();

            UnityEngine.Debug.Log($"[ArtClaw] MCP Server 已启动 (PID={_pythonProcess.Id}, 端口={MCP_DEFAULT_PORT})");
        }

        /// <summary>停止 Python MCP Server 进程</summary>
        public static void StopMCPServer()
        {
            if (_pythonProcess == null || _pythonProcess.HasExited)
            {
                _pythonProcess = null;
                return;
            }
            try
            {
                _pythonProcess.Kill();
                _pythonProcess.WaitForExit(3000);
                UnityEngine.Debug.Log("[ArtClaw] MCP Server 已停止");
            }
            catch (Exception e)
            {
                UnityEngine.Debug.LogWarning($"[ArtClaw] 停止 MCP Server 时出错: {e.Message}");
            }
            finally
            {
                _pythonProcess = null;
            }
        }

        /// <summary>是否运行中</summary>
        public static bool IsRunning => _pythonProcess != null && !_pythonProcess.HasExited;

        // ── 菜单 ──

        [MenuItem("ArtClaw/启动 MCP Server")]
        static void MenuStart() => StartMCPServer();

        [MenuItem("ArtClaw/停止 MCP Server")]
        static void MenuStop() => StopMCPServer();

        [MenuItem("ArtClaw/打开 Dashboard")]
        static void MenuDashboard() => UnityClawDashboard.ShowWindow();

        [MenuItem("ArtClaw/重启 MCP Server")]
        static void MenuRestart()
        {
            StopMCPServer();
            EditorApplication.delayCall += StartMCPServer;
        }

        // ── 内部工具 ──

        private static string FindPythonExecutable()
        {
            foreach (string candidate in new[] { "python", "python3", "py" })
            {
                try
                {
                    var p = Process.Start(new ProcessStartInfo
                    {
                        FileName = candidate,
                        Arguments = "--version",
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        CreateNoWindow = true,
                    });
                    p?.WaitForExit(2000);
                    if (p?.ExitCode == 0) return candidate;
                }
                catch { /* 忽略，尝试下一个 */ }
            }
            return null;
        }
    }
}
