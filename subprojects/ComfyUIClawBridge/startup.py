"""
startup.py - ComfyUI ArtClaw Bridge 启动逻辑
================================================

在 ComfyUI 进程中启动 MCP WebSocket Server。

启动流程:
  1. 设置 sys.path（让 DCCClawBridge 的 core/ 和 adapters/ 可导入）
  2. 创建 ComfyUIAdapter 实例
  3. 调用 mcp_server.start_mcp_server() 在独立线程启动 WebSocket
  4. MCP Server 注册 run_python 工具，Agent 可通过 exec 操作 ComfyUI

端口: 8087（ComfyUI 专用，参见端口分配表）
"""

from __future__ import annotations

import atexit
import logging
import os
import sys
import threading
import time

logger = logging.getLogger("artclaw.comfyui.startup")

# 全局状态
_global_state = {
    "adapter": None,
    "running": False,
}


def _setup_paths() -> bool:
    """将 DCCClawBridge 目录加入 sys.path。

    路径关系:
      ComfyUIClawBridge/startup.py (this file)
      DCCClawBridge/               (同级目录)
        ├── adapters/
        └── core/
    """
    this_dir = os.path.dirname(os.path.abspath(__file__))

    # 查找 DCCClawBridge 的优先级:
    # 1. 旁边的 artclaw_bridge_dcc/ (install.py 部署模式)
    # 2. 旁边的 DCCClawBridge/ (开发模式/symlink)
    # 3. 环境变量 ARTCLAW_BRIDGE_PATH
    # 4. .env 文件中的 ARTCLAW_DCC_BRIDGE_PATH
    parent_dir = os.path.dirname(this_dir)
    
    candidates = [
        os.path.join(parent_dir, "artclaw_bridge_dcc"),   # install 部署
        os.path.join(parent_dir, "DCCClawBridge"),         # 开发模式
    ]
    
    # 从 .env 文件读取
    env_file = os.path.join(this_dir, ".env")
    if os.path.isfile(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ARTCLAW_DCC_BRIDGE_PATH="):
                        candidates.insert(0, line.split("=", 1)[1].strip())
        except Exception:
            pass
    
    # 环境变量
    env_path = os.environ.get("ARTCLAW_BRIDGE_PATH", "")
    if env_path:
        candidates.append(os.path.join(env_path, "subprojects", "DCCClawBridge"))
    
    dcc_bridge_dir = None
    for candidate in candidates:
        if os.path.isdir(os.path.join(candidate, "adapters")):
            dcc_bridge_dir = candidate
            break

    if dcc_bridge_dir and os.path.isdir(os.path.join(dcc_bridge_dir, "adapters")):
        if dcc_bridge_dir not in sys.path:
            sys.path.insert(0, dcc_bridge_dir)

        # 也需要 core/ 在 path 上（bridge_core.py 等用裸 import）
        core_dir = os.path.join(dcc_bridge_dir, "core")
        if os.path.isdir(core_dir) and core_dir not in sys.path:
            sys.path.insert(0, core_dir)

        logger.info(f"ArtClaw: DCCClawBridge path = {dcc_bridge_dir}")
        return True

    logger.warning(f"ArtClaw: DCCClawBridge not found (tried: {candidates})")
    return False


def _start_bridge():
    """启动 MCP Server（在延迟线程中调用，确保 ComfyUI 已完成初始化）"""
    if _global_state["running"]:
        return

    try:
        from adapters.comfyui_adapter import ComfyUIAdapter
        from core.mcp_server import start_mcp_server

        # 创建 adapter
        adapter = ComfyUIAdapter()
        _global_state["adapter"] = adapter

        # 将 adapter 注册到 builtins（供 bridge_dcc.py 等全局访问）
        import builtins
        builtins._artclaw_adapter = adapter

        # 调用 adapter on_startup（设置 DCC 名称等）
        adapter.on_startup()

        # 启动 MCP Server（独立线程运行 WebSocket）
        # 端口 8087: ComfyUI 专用（参见端口分配表: UE=8080, Maya=8081, Max=8082, Blender=8083, Houdini=8084, SP=8085, SD=8086, ComfyUI=8087）
        if start_mcp_server(adapter=adapter, port=8087):
            _global_state["running"] = True
            logger.info("ArtClaw: MCP Server started on port 8087")

            # 注册 atexit 清理
            atexit.register(_shutdown_bridge)
        else:
            logger.error("ArtClaw: MCP Server failed to start")

    except Exception as e:
        logger.error(f"ArtClaw: Bridge startup error: {e}", exc_info=True)


def _shutdown_bridge():
    """清理 MCP Server 和 adapter"""
    adapter = _global_state.get("adapter")
    if adapter:
        try:
            adapter.on_shutdown()
        except Exception:
            pass
    _global_state["adapter"] = None
    _global_state["running"] = False
    logger.info("ArtClaw: Bridge shutdown")


def start_bridge(delay: float = 2.0):
    """启动 ArtClaw Bridge。

    延迟 delay 秒后启动，确保 ComfyUI 核心模块已完成初始化
    （nodes 注册、folder_paths 设置等）。

    Args:
        delay: 延迟秒数（默认 2 秒）
    """
    if not _setup_paths():
        logger.error("ArtClaw: 无法找到 DCCClawBridge，Bridge 未启动")
        return

    def _delayed_start():
        time.sleep(delay)
        logger.info(f"ArtClaw: 延迟 {delay}s 后启动 Bridge...")
        _start_bridge()

    thread = threading.Thread(
        target=_delayed_start, daemon=True, name="ArtClaw-Startup"
    )
    thread.start()
    logger.info(f"ArtClaw: Bridge 将在 {delay}s 后启动")
