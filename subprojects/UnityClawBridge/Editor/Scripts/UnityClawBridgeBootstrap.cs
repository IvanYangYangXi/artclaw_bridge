// UnityClawBridgeBootstrap.cs
// Unity Editor 插件入口 - 生命周期管理 + Python MCP 进程桥接

using System;
using System.Diagnostics;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace ArtClaw.Unity
{
    [InitializeOnLoad]
    public static class UnityClawBridgeBootstrap
    {
        private static Process _pythonProcess;
        private const int MCP_DEFAULT_PORT = 8088;

        // Python 脚本路径（硬编码，不依赖 Assembly）
        private static string PythonScriptPath =>
            Path.Combine(Application.dataPath, "..", "Assets", "UnityClawBridge", "Python", "bootstrap.py");

        static UnityClawBridgeBootstrap()
        {
            EditorApplication.delayCall += () =>
            {
                if (SessionState.GetBool("ArtClaw_AutoStart", true))
                    StartMCPServer();
            };
            AssemblyReloadEvents.beforeAssemblyReload += OnBeforeAssemblyReload;
        }

        private static void OnBeforeAssemblyReload()
        {
            StopMCPServer();
        }

        public static void StartMCPServer()
        {
            if (_pythonProcess != null && !_pythonProcess.HasExited)
            {
                UnityEngine.Debug.Log("[ArtClaw] MCP Server 已在运行");
                return;
            }

            // 启动前先清理 MCP 端口（8088）的僵尸占用
            KillPortOccupant(MCP_DEFAULT_PORT);

            string pythonExe = FindPythonExecutable();
            if (string.IsNullOrEmpty(pythonExe))
            {
                UnityEngine.Debug.LogError("[ArtClaw] 未找到 Python，请确保 Python 3.9+ 已安装");
                return;
            }

            string scriptPath = PythonScriptPath;
            if (!File.Exists(scriptPath))
            {
                UnityEngine.Debug.LogError("[ArtClaw] 找不到 bootstrap.py: " + scriptPath);
                return;
            }

            var psi = new ProcessStartInfo
            {
                FileName = pythonExe,
                Arguments = "\"" + scriptPath + "\" --port " + MCP_DEFAULT_PORT + " --plugin-root \"" + Path.GetDirectoryName(scriptPath) + "\"",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                WorkingDirectory = Path.GetDirectoryName(scriptPath),
            };

            _pythonProcess = new Process { StartInfo = psi, EnableRaisingEvents = true };
            _pythonProcess.OutputDataReceived += (_, e) =>
            {
                if (!string.IsNullOrEmpty(e.Data))
                    UnityEngine.Debug.Log("[ArtClaw|Py] " + e.Data);
            };
            _pythonProcess.ErrorDataReceived += (_, e) =>
            {
                if (!string.IsNullOrEmpty(e.Data))
                    UnityEngine.Debug.Log("[ArtClaw|Py] " + e.Data);
            };
            _pythonProcess.Exited += (_, _) =>
            {
                UnityEngine.Debug.Log("[ArtClaw] Python MCP Server 进程已退出");
                _pythonProcess = null;
            };

            _pythonProcess.Start();
            _pythonProcess.BeginOutputReadLine();
            _pythonProcess.BeginErrorReadLine();
            UnityEngine.Debug.Log("[ArtClaw] MCP Server 已启动 (PID=" + _pythonProcess.Id + ", 端口=" + MCP_DEFAULT_PORT + ")");
        }

        public static void StopMCPServer()
        {
            if (_pythonProcess == null || _pythonProcess.HasExited) { _pythonProcess = null; return; }
            try
            {
                _pythonProcess.Kill();
                _pythonProcess.WaitForExit(3000);
                UnityEngine.Debug.Log("[ArtClaw] MCP Server 已停止");
            }
            catch (Exception e) { UnityEngine.Debug.LogWarning("[ArtClaw] 停止出错: " + e.Message); }
            finally { _pythonProcess = null; }
        }

        public static bool IsRunning => _pythonProcess != null && !_pythonProcess.HasExited;

        // 菜单
        [MenuItem("ArtClaw/启动 MCP Server")] static void MenuStart() => StartMCPServer();
        [MenuItem("ArtClaw/停止 MCP Server")] static void MenuStop() => StopMCPServer();
        [MenuItem("ArtClaw/重启 MCP Server")] static void MenuRestart() { StopMCPServer(); EditorApplication.delayCall += StartMCPServer; }

        private static string FindPythonExecutable()
        {
            foreach (string cand in new[] { "python", "python3" })
            {
                try
                {
                    var p = Process.Start(new ProcessStartInfo { FileName = cand, Arguments = "--version", UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true, CreateNoWindow = true });
                    p?.WaitForExit(2000);
                    if (p?.ExitCode == 0) return cand;
                    p?.Dispose();
                }
                catch { }
            }
            return null;
        }

        private static void KillPortOccupant(int port)
        {
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = "netstat",
                    Arguments = "-ano",
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    CreateNoWindow = true,
                };
                var proc = Process.Start(psi);
                if (proc == null) return;
                string output = proc.StandardOutput.ReadToEnd();
                proc.WaitForExit(3000);

                int myPid = Process.GetCurrentProcess().Id;

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
                        var occupant = Process.GetProcessById(pid);
                        if (occupant.HasExited) continue;
                        UnityEngine.Debug.Log($"[ArtClaw] 端口 {port} 被进程 {pid}({occupant.ProcessName}) 占用，正在终止...");
                        occupant.Kill();
                        occupant.WaitForExit(3000);
                        UnityEngine.Debug.Log($"[ArtClaw] 进程 {pid} 已终止");
                    }
                    catch (ArgumentException) { }
                    catch (Exception) { }
                }
            }
            catch { }
        }
    }
}
