"""
houdini_shelf.py - Houdini Shelf Tool 启动入口
================================================

作为 Houdini Shelf Tool 的脚本入口，提供 ArtClaw 的
启动 / 停止 / 切换 功能。

使用方式:
  1. 在 Houdini 中创建 Shelf Tool
  2. Script 内容: import houdini_shelf; houdini_shelf.toggle_artclaw()
  3. 或在 Python Shell 中直接调用

前提:
  - DCCClawBridge 目录已加入 sys.path
  - 运行在 Houdini Python 环境中
"""

from __future__ import annotations

import logging
import traceback

logger = logging.getLogger("artclaw.houdini")

# ── 全局状态 ──

_global_state = {
    "adapter": None,
    "running": False,
}


def start_artclaw() -> bool:
    """
    启动 ArtClaw — 创建 Adapter、启动 MCP Server、打开 Chat Panel。

    Returns:
        True 启动成功, False 启动失败
    """
    global _global_state

    if _global_state["running"]:
        logger.warning("ArtClaw: Already running")
        show_panel()
        return True

    try:
        from adapters.houdini_adapter import HoudiniAdapter

        adapter = HoudiniAdapter()
        adapter.on_startup()
        adapter._open_chat_panel()

        _global_state["adapter"] = adapter
        _global_state["running"] = True

        logger.info("ArtClaw: Started successfully")
        return True

    except Exception as exc:
        logger.error(f"ArtClaw: Start failed: {exc}")
        traceback.print_exc()
        _global_state["adapter"] = None
        _global_state["running"] = False
        return False


def stop_artclaw() -> None:
    """停止 ArtClaw — 关闭 MCP Server、断开 Bridge、清理资源。"""
    global _global_state

    adapter = _global_state.get("adapter")
    if adapter is not None:
        try:
            adapter.on_shutdown()
        except Exception as exc:
            logger.error(f"ArtClaw: Shutdown error: {exc}")
            traceback.print_exc()

    _global_state["adapter"] = None
    _global_state["running"] = False
    logger.info("ArtClaw: Stopped")


def show_panel() -> None:
    """
    显示 / 重新打开 Chat Panel。

    如果 Panel 已被关闭，重新创建并显示。
    如果 ArtClaw 未运行，则先启动。
    """
    if not _global_state["running"]:
        start_artclaw()
        return

    adapter = _global_state.get("adapter")
    if adapter is not None:
        try:
            adapter._open_chat_panel()
            logger.info("ArtClaw: Chat Panel reopened")
        except Exception as exc:
            logger.error(f"ArtClaw: Failed to reopen Chat Panel: {exc}")
            traceback.print_exc()


def toggle_artclaw() -> None:
    """切换 ArtClaw 状态 — 运行中则停止，未运行则启动。"""
    if _global_state["running"]:
        stop_artclaw()
    else:
        start_artclaw()


def is_running() -> bool:
    """检查 ArtClaw 是否正在运行。"""
    return _global_state["running"]


def get_adapter():
    """获取当前 adapter 实例（未运行时返回 None）。"""
    return _global_state.get("adapter")
