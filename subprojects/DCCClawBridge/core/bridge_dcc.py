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

# ---------------------------------------------------------------------------
# 导入 bridge_core / bridge_diagnostics
# 优先级:
#   1. 自包含部署: bridge_core.py 已复制到当前 core/ 目录 (同级文件)
#   2. 开发模式: 通过相对路径找到 core/ 目录
# ---------------------------------------------------------------------------

# 确保 core/ 目录在 sys.path 上（bridge_core.py 用裸导入）
_core_dir = os.path.dirname(os.path.abspath(__file__))
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)

try:
    # 自包含部署: 安装器已将 bridge_core.py 等复制到 core/ 目录
    from bridge_core import OpenClawBridge, BridgeLogger  # noqa: E402
    from bridge_diagnostics import diagnose_connection  # noqa: E402
except ImportError:
    # 开发模式: 通过相对路径回溯到 core/
    _bridge_pkg_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "core")
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
    _dcc_name: str = "dcc"  # 由 adapter 设置: maya / max

    @classmethod
    def instance(cls) -> "DCCBridgeManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_dcc_name(cls, name: str):
        """设置当前 DCC 名称 (maya/max)，影响 session key"""
        cls._dcc_name = name.lower()

    def __init__(self):
        self._bridge: Optional[OpenClawBridge] = None
        self.signals = _BridgeSignals() if _BridgeSignals else None
        self._context_injected = False  # 是否已注入过 DCC 上下文

    def connect(self) -> bool:
        """连接到 OpenClaw Gateway"""
        if self._bridge and self._bridge.is_connected():
            return True

        self._bridge = OpenClawBridge(
            client_id=f"{self._dcc_name}-editor",
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

        # 记忆摘要注入
        enriched = self._enrich_with_briefing(message)

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

        self._bridge.send_message_async(enriched, _on_result)

    def _enrich_with_briefing(self, message: str) -> str:
        """在用户消息前附加 DCC 上下文 + 记忆摘要"""
        prefix_parts = []

        # DCC 环境上下文（只在 session 首条消息注入）
        if not self._context_injected:
            try:
                import builtins
                adapter = getattr(builtins, '_artclaw_adapter', None)
                if adapter:
                    sw_name = adapter.get_software_name()
                    sw_ver = adapter.get_software_version()
                    # 工具前缀映射
                    _PREFIX_MAP = {
                        "maya": "mcp_maya-primary_",
                        "3dsmax": "mcp_max-primary_",
                        "max": "mcp_max-primary_",
                    }
                    my_prefix = _PREFIX_MAP.get(sw_name.lower(), f"mcp_{sw_name.lower()}-primary_")
                    # 构建其他工具列表（排除当前软件）
                    _ALL_TOOLS = {
                        "mcp_ue-editor-agent_": "UE",
                        "mcp_maya-primary_": "Maya",
                        "mcp_max-primary_": "Max",
                    }
                    other_tools = "、".join(
                        f"{prefix}（{label}）"
                        for prefix, label in _ALL_TOOLS.items()
                        if prefix != my_prefix
                    )
                    prefix_parts.append(
                        f"[DCC Context - 重要]\n"
                        f"当前对话环境: {sw_name} {sw_ver}\n"
                        f"当前软件工具前缀: {my_prefix}\n\n"
                        f"工具使用规则:\n"
                        f"- 对当前软件内的场景和资产操作使用 {my_prefix}run_python\n"
                        f"- 获取编辑器上下文请用 {my_prefix}run_python 的 get_context=true\n"
                        f"- 如果明确要求执行其他 DCC 软件的操作，使用对应软件的工具\n"
                        f"- 本地文件操作（读取用户提供的图片/文本/代码等）请直接读取，不需要通过 run_python\n"
                        f"- 其他不需要当前 DCC 环境执行的任务，请根据上下文判断使用什么工具\n"
                        f"- 其他软件工具前缀: {other_tools}"
                    )
                    self._context_injected = True
            except Exception:
                pass

        # 记忆摘要
        try:
            from memory_store import DCCMemoryStore
            import builtins
            adapter = getattr(builtins, '_artclaw_adapter', None)
            if adapter and hasattr(adapter, '_memory_store') and adapter._memory_store:
                briefing = adapter._memory_store.manager.export_briefing(max_tokens=1500)
                if briefing and "记忆库为空" not in briefing:
                    prefix_parts.append(briefing)
        except Exception:
            pass

        # Pinned Skills 提示
        pinned_hint = self._build_pinned_hint()
        if pinned_hint:
            prefix_parts.append(pinned_hint)

        if prefix_parts:
            prefix = "\n\n".join(prefix_parts)
            return f"{prefix}\n\n[User Message]\n{message}"
        return message

    def cancel(self):
        """取消当前 AI 请求"""
        if self._bridge:
            self._bridge.cancel_current()

    def reset_session(self):
        """重置会话 — 创建新 session"""
        if not self._bridge:
            return

        # 清空 session key，下次发消息时生成新的带时间戳 key = 新 session
        self._bridge.reset_session()
        self._context_injected = False

    def get_session_key(self) -> str:
        """获取当前 session key"""
        return self._bridge.get_session_key() if self._bridge else ""

    def set_session_key(self, key: str):
        """设置 session key（会话切换）"""
        if self._bridge:
            self._bridge.set_session_key(key)

    # --- Agent 切换 + 会话管理 (Phase 3) ---

    def get_agent_id(self) -> str:
        """获取当前 Agent ID"""
        return self._bridge.get_agent_id() if self._bridge else ""

    def set_agent(self, agent_id: str):
        """切换 Agent，重置 session。"""
        if self._bridge:
            self._bridge.set_agent(agent_id)
            self._context_injected = False

    def list_agents(self) -> list:
        """查询可用 Agent 列表（同步）。
        返回 [{"id": ..., "name": ..., "emoji": ...}, ...]
        """
        if not self._bridge:
            self.connect()
        return self._bridge.list_agents() if self._bridge else []

    def fetch_history(self, session_key: str) -> list:
        """从 Gateway 拉取会话历史（同步）。
        返回 [{"sender": ..., "content": ...}, ...]
        """
        if not self._bridge:
            self.connect()
        return self._bridge.fetch_history(session_key) if self._bridge else []

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

    @staticmethod
    def _build_pinned_hint() -> str:
        """读取 pinned_skills，生成一句自然语言提示告诉 AI 优先使用这些 Skill。"""
        try:
            import json as _json
            config_path = os.path.join(os.path.expanduser("~"), ".artclaw", "config.json")
            if not os.path.exists(config_path):
                return ""
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = _json.load(f)
            pinned = cfg.get("pinned_skills", [])
            if not pinned:
                return ""
            names = ", ".join(pinned[:5])
            return (
                f"[Pinned Skills] 用户钉选了以下技能: {names}。"
                f"当用户请求涉及这些技能的功能时，请优先加载并按照对应 Skill 的操作指南执行。"
            )
        except Exception:
            return ""


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
