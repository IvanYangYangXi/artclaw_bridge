"""
ArtClaw Bridge - AI Agent integration for ComfyUI
=====================================================

ComfyUI 自定义节点入口文件。

此包不注册任何可见的 ComfyUI 节点（NODE_CLASS_MAPPINGS 为空），
仅在 ComfyUI 启动时启动 MCP WebSocket Server，
使 AI Agent（如 OpenClaw）能通过 run_python 工具操作 ComfyUI。

安装方式:
  将此包放置到 ComfyUI/custom_nodes/artclaw_bridge/
  或通过 ComfyUI-Manager 安装

启动后:
  MCP Server 在 ws://127.0.0.1:8087 监听
  Agent 通过 run_python 工具在 ComfyUI 进程内执行任意 Python 代码
"""

import logging

logger = logging.getLogger("artclaw.comfyui")

# ── 启动 Bridge ──

try:
    from .startup import start_bridge
    start_bridge(delay=2.0)
    logger.info("ArtClaw: ComfyUI Bridge 启动中...")
except Exception as e:
    logger.error(f"ArtClaw: Bridge 启动失败: {e}")

# ── ComfyUI 自定义节点导出（必须存在，可以为空）──

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

# ComfyUI 日志中会显示已加载的自定义节点
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
