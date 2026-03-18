"""
bridge_dcc.py - DCC 通用 OpenClaw Bridge 适配器
=================================================

为 PySide2/Qt 环境（Maya / 3ds Max 等 DCC）提供 bridge_core.py 的适配。
与 UE 的 openclaw_bridge.py 对应，但：
  - 日志: Python logging → DCC Script Editor
  - 数据回传: Qt signal/slot 直接通知（不走文件轮询）
  - 不依赖 unreal 模块

使用方式 (Maya):
    from core.bridge_dcc import DCCBridgeManager
    manager = DCCBridgeManager.instance()
    manager.connect()
    manager.send_message("hello")  # 通过 Qt signal 回传
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import uuid
from typing import Optional

# 确保 openclaw-mcp-bridge 目录在 sys.path 中
_bridge_pkg_dir = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "openclaw-mcp-bridge")
)
if os.path.isdir(_bridge_pkg_dir) and _bridge_pkg_dir not in sys.path:
    sys.path.insert(0, _bridge_pkg_dir)

from bridge_core import OpenClawBridge, BridgeLogger  # noqa: E402
from bridge_diagnostics import diagnose_connection  # noqa: E402

# Qt imports — PySide2 在 Maya 2022+/Max 2022+ 内置
try:
    from PySide2.QtCore import QObject, Signal, Slot, QTimer
except ImportError:
    # 降级: 无 Qt 环境时用纯回调模式
    QObject = object
    Signal = None
    Slot = lambda f: f
    QTimer = None


logger = logging.getLogger("artclaw.bridge")


# ---------------------------------------------------------------------------
# DCC 日志适配器
# ---------------------------------------------------------------------------

class _DCCBridgeLogger(BridgeLogger):
    """将 bridge 日志路由到 Python logging（DCC Script Editor 可见）"""

    def info(self, msg: str):
        logger.info(msg)

    def warning(self, msg: str):
        logger.warning(msg)

    def error(self, msg: str):
        logger.error(msg)

    def debug(self, msg: str):
        logger.debug(msg)


# ---------------------------------------------------------------------------
# Qt Signal 包装
# ---------------------------------------------------------------------------

if Signal is not None:
    class _BridgeSignals(QObject):
        """Qt signals for bridge events — 在 DCC 主线程中安全消费"""

        # 连接状态变更: (connected: bool, detail: str)
        connection_changed = Signal(bool, str)

        # 收到 AI 流式文本: (state: str, text: str)
        # state: "delta" / "thinking" / "final" / "error" / "aborted"
        ai_message = Signal(str, str)

        # 收到 AI thinking 文本: (state: str, text: str)
        ai_thinking = Signal(str, str)

        # 最终响应完成: (result: str)
        response_complete = Signal(str)
else:
    _BridgeSignals = None


# ---------------------------------------------------------------------------
# DCC Bridge Manager (单例)
# ---------------------------------------------------------------------------

class DCCBridgeManager:
    """
    DCC 通用的 OpenClaw Bridge 管理器。

    通过 Qt signal/slot 将 AI 响应推送到 UI 层，
    避免 UE 那种文件轮询方式。

    使用:
        manager = DCCBridgeManager.instance()
        manager.signals.ai_message.connect(my_on_message)
        manager.connect()
        manager.send_message("帮我导出选中物体")
    """

    _instance: Optional["DCCBridgeManager"] = None

    @classmethod
    def instance(cls) -> "DCCBridgeManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._bridge: Optional[OpenClawBridge] = None
        self.signals = _BridgeSignals() if _BridgeSignals else None

    def connect(self) -> bool:
        """连接到 OpenClaw Gateway"""
        if self._bridge and self._bridge.is_connected():
            return True

        self._bridge = OpenClawBridge(
            logger=_DCCBridgeLogger(),
            on_status_changed=self._on_status_changed,
        )

        return self._bridge.start()

    def disconnect(self):
        """断开连接"""
        if self._bridge:
            self._bridge.stop()
            self._bridge = None

    def is_connected(self) -> bool:
        return self._bridge is not None and self._bridge.is_connected()

    def send_message(self, message: str):
        """
        异步发送消息给 AI。
        响应通过 signals.ai_message / signals.response_complete 回传。
        """
        if not self._bridge:
            self.connect()

        if not self._bridge:
            if self.signals:
                self.signals.response_complete.emit(
                    "[错误] OpenClaw Bridge 未初始化，请确认 OpenClaw 正在运行。"
                )
            return

        # 设置流式回调
        self._bridge.on_ai_message = self._on_ai_message
        self._bridge.on_ai_thinking = self._on_ai_thinking

        def _on_result(result: str):
            if self.signals:
                self.signals.response_complete.emit(result)
            # 清理回调
            if self._bridge:
                self._bridge.on_ai_message = None
                self._bridge.on_ai_thinking = None

        self._bridge.send_message_async(message, _on_result)

    def cancel(self):
        """取消当前 AI 请求"""
        if self._bridge:
            self._bridge.cancel_current()

    def reset_session(self):
        """重置会话 (清除 session key)"""
        if self._bridge:
            self._bridge._session_key = ""

    def run_diagnostics(self) -> str:
        """运行连接诊断，返回报告文本"""
        return diagnose_connection(logger=_DCCBridgeLogger())

    # --- 内部回调 ---

    def _on_status_changed(self, connected: bool, detail: str):
        logger.info(f"Bridge status: {'connected' if connected else 'disconnected'} ({detail})")
        if self.signals:
            self.signals.connection_changed.emit(connected, detail)

    def _on_ai_message(self, state: str, text: str):
        if self.signals:
            self.signals.ai_message.emit(state, text)

    def _on_ai_thinking(self, state: str, text: str):
        if self.signals:
            self.signals.ai_thinking.emit(state, text)


# ---------------------------------------------------------------------------
# 便捷函数 (与 openclaw_bridge.py 的公开接口对齐)
# ---------------------------------------------------------------------------

def connect() -> bool:
    return DCCBridgeManager.instance().connect()


def disconnect():
    DCCBridgeManager.instance().disconnect()


def is_connected() -> bool:
    return DCCBridgeManager.instance().is_connected()


def send_message(message: str):
    DCCBridgeManager.instance().send_message(message)


def cancel():
    DCCBridgeManager.instance().cancel()
