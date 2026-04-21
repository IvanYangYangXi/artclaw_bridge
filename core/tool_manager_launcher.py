"""
tool_manager_launcher.py - ArtClaw Tool Manager 启动器
======================================================

从 DCC 插件或 UE 内部调用，自动检测并启动 Tool Manager 服务。
不依赖 bat 脚本，直接用 venv python 启动，兼容 CREATE_NO_WINDOW 场景。
"""

import json
import os
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path

TOOL_MANAGER_PORT = 9876
TOOL_MANAGER_URL = f"http://localhost:{TOOL_MANAGER_PORT}"


def _get_project_root() -> str:
    """从 ~/.artclaw/config.json 读取 project_root"""
    cfg_path = Path.home() / ".artclaw" / "config.json"
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return cfg.get("project_root", "")
        except Exception:
            pass
    return ""


def is_running() -> bool:
    """检查 Tool Manager 是否已在运行"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        result = s.connect_ex(("127.0.0.1", TOOL_MANAGER_PORT)) == 0
        s.close()
        return result
    except Exception:
        return False


def _find_python(tm_dir: Path) -> str:
    """查找可用的 Python 解释器，优先使用 venv。
    
    注意：在 UE 嵌入环境中 sys.executable 指向 UnrealEditor.exe，
    绝对不能用作 subprocess 的 Python 解释器！
    """
    # 1. venv python
    venv_python = tm_dir / "venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    # Linux/Mac
    venv_python_unix = tm_dir / "venv" / "bin" / "python"
    if venv_python_unix.exists():
        return str(venv_python_unix)
    
    # 2. 系统 python（不用 sys.executable，在 DCC 内可能指向 DCC 本身）
    import shutil
    for name in ("python", "python3"):
        found = shutil.which(name)
        if found and "UnrealEditor" not in found and "maya" not in found.lower():
            return found
    
    # 3. 最后 fallback — 只在确认不是 DCC 可执行文件时才用 sys.executable
    if sys.executable and not any(
        dcc in os.path.basename(sys.executable).lower()
        for dcc in ("unreal", "maya", "3dsmax", "blender", "houdini", "substance", "comfyui")
    ):
        return sys.executable
    
    return ""  # 找不到，让调用方报错


def start_server(open_browser: bool = True) -> dict:
    """
    启动 Tool Manager 服务。
    
    Returns:
        dict: {"ok": bool, "already_running": bool, "error": str|None}
    """
    if is_running():
        if open_browser:
            webbrowser.open(TOOL_MANAGER_URL)
        return {"ok": True, "already_running": True, "error": None}

    project_root = _get_project_root()
    if not project_root:
        return {
            "ok": False,
            "already_running": False,
            "error": "project_root not set in ~/.artclaw/config.json",
        }

    tm_dir = Path(project_root) / "subprojects" / "ArtClawToolManager"
    if not tm_dir.exists():
        return {
            "ok": False,
            "already_running": False,
            "error": f"Tool Manager directory not found: {tm_dir}",
        }

    python_exe = _find_python(tm_dir)
    if not python_exe:
        return {
            "ok": False,
            "already_running": False,
            "error": "No suitable Python interpreter found. Please create venv in ArtClawToolManager or install Python on PATH.",
        }

    try:
        # 直接用 python 启动，不经过 bat/cmd
        # -m src.server.main 需要 cwd 在 ArtClawToolManager 目录
        creation_flags = 0
        if sys.platform == "win32":
            # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
            creation_flags = 0x08000000 | 0x00000200

        subprocess.Popen(
            [python_exe, "-m", "src.server.main"],
            cwd=str(tm_dir),
            creationflags=creation_flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
    except Exception as exc:
        return {
            "ok": False,
            "already_running": False,
            "error": f"Failed to start: {exc}",
        }

    # 等待服务启动
    if open_browser:
        import time
        for _ in range(10):
            time.sleep(1)
            if is_running():
                break
        webbrowser.open(TOOL_MANAGER_URL)

    return {"ok": True, "already_running": False, "error": None}


def launch(open_browser: bool = True) -> dict:
    """启动 Tool Manager 并打开浏览器（主入口）"""
    return start_server(open_browser=open_browser)
