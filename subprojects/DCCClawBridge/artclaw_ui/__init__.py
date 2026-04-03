"""
__init__.py - ArtClaw UI 包入口
================================

暴露 show_chat_panel 作为主要入口点，供 DCC 插件直接调用。

使用示例（Maya/Max 插件中）：
    from artclaw_ui import show_chat_panel
    show_chat_panel(dcc_name="maya", dcc_version="2024")
"""

from __future__ import annotations

import logging

logger = logging.getLogger("artclaw.ui")

# 版本号
__version__ = "0.2.0"

# 延迟导入，避免在没有 Qt 的环境下 import 报错
_chat_panel_module = None


def _get_chat_panel_module():
    """懒加载 chat_panel 模块"""
    global _chat_panel_module
    if _chat_panel_module is None:
        try:
            from . import chat_panel as _mod
            _chat_panel_module = _mod
        except ImportError as e:
            logger.error("加载 chat_panel 失败：%s", e)
            return None
    return _chat_panel_module


def show_chat_panel(
    dcc_name: str = "maya",
    dcc_version: str = "",
    parent=None,
) -> None:
    """
    显示 ArtClaw 聊天面板主窗口。

    参数：
        dcc_name:    DCC 软件名称（'maya' | 'max' | 'generic'）
        dcc_version: DCC 版本号（如 '2024'），用于数据目录隔离
        parent:      Qt 父窗口（可选）
    """
    mod = _get_chat_panel_module()
    if mod is None:
        logger.error("chat_panel 模块不可用，无法显示面板")
        return

    try:
        mod.show_chat_panel(dcc_name=dcc_name, dcc_version=dcc_version, parent=parent)
    except Exception as e:
        logger.exception("show_chat_panel 发生异常：%s", e)


# 便捷导出
__all__ = [
    "__version__",
    "show_chat_panel",
]
