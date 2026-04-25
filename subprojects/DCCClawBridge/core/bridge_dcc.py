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

# Qt imports — PySide2 在 Maya 2022+/Max 2022+ 内置，PySide6 供 Blender 等使用
try:
    from PySide2.QtCore import QObject, Signal, Slot, QTimer
except ImportError:
    try:
        from PySide6.QtCore import QObject, Signal, Slot, QTimer
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

        # 工具调用: (tool_name: str, tool_id: str, arguments_json: str)
        tool_call = Signal(str, str, str)

        # 工具结果: (tool_name: str, tool_id: str, content: str, is_error: bool)
        tool_result = Signal(str, str, str, bool)

        # Token 用量更新: (used: int, total: int)
        usage_update = Signal(int, int)

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

        connected = self._bridge.start()

        if connected:
            # 修复旧格式 session key（local- 前缀无法接收 Gateway 事件）
            sk = self._bridge.get_session_key()
            if sk and not sk.startswith("agent:"):
                self._bridge.reset_session()
                logger.info(f"Reset legacy session key: {sk[:30]}")

            # 设置持久回调 — 在整个连接生命周期内生效
            self._bridge.on_ai_message = self._on_ai_message
            self._bridge.on_ai_thinking = self._on_ai_thinking
            self._bridge.on_usage_update = self._on_usage_update
            # NOTE: tool 事件通过 MCP Server 侧回调推送 (见 mcp_server.py _connect_tool_events_to_bridge)

        return connected

    def disconnect(self):
        """断开连接"""
        if self._bridge:
            self._bridge.stop()
            self._bridge = None

    def is_connected(self) -> bool:
        return self._bridge is not None and self._bridge.is_connected()

    def send_message(self, message: str):
        """
        异步发送消息给 AI（后台线程阻塞等待，主线程不阻塞）。

        使用 bridge_core.send_message_async()（后台线程中 send_message 阻塞等待 final）。
        流式回调在 connect() 时一次性设置，持续生效。
        """
        if not self._bridge:
            self.connect()

        if not self._bridge:
            if self.signals:
                self.signals.response_complete.emit(
                    "[错误] OpenClaw Bridge 未初始化，请确认 OpenClaw 正在运行。"
                )
            return

        # 确保连接存在
        if not self._bridge.is_connected():
            connected = self._bridge.start()
            if not connected:
                if self.signals:
                    self.signals.response_complete.emit(
                        "[错误] 无法连接到 OpenClaw Gateway，请确认 OpenClaw 正在运行。"
                    )
                return

        # 确保 session key 是 Gateway 格式（防止旧实例遗留的 local- 前缀）
        sk = self._bridge.get_session_key()
        if sk and sk.startswith("local-"):
            self._bridge.reset_session()
            self._context_injected = False

        # 记忆摘要注入
        enriched = self._enrich_with_briefing(message)

        # 重置流式状态
        self._streaming_text_len = 0
        # 重置 tool 轮询状态
        self._emitted_tool_ids = set()
        self._transcript_poll_line = self._get_transcript_line_count()

        # 启动 transcript 轮询（每 1s 检查新增 tool 事件）
        self._start_transcript_poll()

        def _on_result(result: str):
            """send_message 完成回调（从后台线程调用）"""
            # 停止轮询定时器
            self._stop_transcript_poll()
            # 最终一次性补全（确保不遗漏）
            try:
                self._supplement_tool_events()
            except Exception as _e:
                self._log.warning(f"_supplement_tool_events error: {_e}")
            if self.signals:
                self.signals.response_complete.emit(result)
            # 查询 session token 用量
            self._query_session_usage()

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
                    # 工具前缀映射（必须与 openclaw.json mcp-bridge servers 名一致）
                    _PREFIX_MAP = {
                        "maya": "mcp_maya-primary_",
                        "3dsmax": "mcp_max-primary_",
                        "max": "mcp_max-primary_",
                        "substance_designer": "mcp_sd-editor_",
                        "substance_painter": "mcp_sp-editor_",
                        "blender": "mcp_blender-editor_",
                        "houdini": "mcp_houdini-editor_",
                        "comfyui": "mcp_comfyui-editor_",
                    }
                    my_prefix = _PREFIX_MAP.get(sw_name.lower(), f"mcp_{sw_name.lower()}-primary_")
                    # 构建其他工具列表（排除当前软件）
                    _ALL_TOOLS = {
                        "mcp_ue-editor-agent_": "UE",
                        "mcp_maya-primary_": "Maya",
                        "mcp_max-primary_": "Max",
                        "mcp_sd-editor_": "Substance Designer",
                        "mcp_sp-editor_": "Substance Painter",
                        "mcp_blender-editor_": "Blender",
                        "mcp_houdini-editor_": "Houdini",
                        "mcp_comfyui-editor_": "ComfyUI",
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
                        f"- {sw_name} 场景/资产的查询与操作使用 {my_prefix}run_python\n"
                        f"- 涉及其他 DCC 软件（{other_tools}）时，使用对应软件的工具\n"
                        f"- 本地文件读写、以及其他不依赖 {sw_name} 环境的任务，直接使用自身能力处理"
                    )
                    self._context_injected = True
            except Exception:
                pass

        # 记忆摘要
        try:
            from core.memory_store import get_memory_store
            store = get_memory_store()
            if store:
                briefing = store.manager.export_briefing(max_tokens=1500)
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
        
        # 清空持久化执行命名空间（新对话不继承旧对话的变量）
        try:
            import builtins
            adapter = getattr(builtins, '_artclaw_adapter', None)
            if adapter and hasattr(adapter, 'clear_exec_namespace'):
                adapter.clear_exec_namespace()
                logger.debug("Exec namespace cleared on session reset")
        except Exception:
            pass

        # 清空 RetryTracker 状态（新对话不继承旧对话的重试计数）
        try:
            from core.mcp_server import get_mcp_server
            server = get_mcp_server()
            if server and server._retry_tracker:
                server._retry_tracker.clear()
        except Exception:
            pass

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
        if connected:
            logger.info("Bridge status: connected")
        else:
            logger.info(f"Bridge status: disconnected ({detail})")
        if self.signals:
            self.signals.connection_changed.emit(connected, detail)

    def _on_ai_message(self, state: str, text: str):
        """处理 AI 消息回调。

        bridge_core 有两条事件路径:
        1. agent events → _handle_agent_event → on_ai_message("delta", incremental_text)
        2. chat events  → _handle_chat_event  → on_ai_message(state, cumulative_text)

        两条路径都可能触发 delta，用 _streaming_text_len 去重。
        """
        if not self.signals or not text:
            return

        if state == "delta":
            text_len = len(text)
            prev_len = getattr(self, '_streaming_text_len', 0)
            if text_len > prev_len:
                self._streaming_text_len = text_len
                self.signals.ai_message.emit(state, text)
            elif text_len == prev_len:
                # 相同长度 — 可能是重复事件，跳过
                pass
            else:
                # 新文本比之前短 — 可能是新的回复周期，重置计数
                self._streaming_text_len = text_len
                self.signals.ai_message.emit(state, text)
        elif state in ("final", "error", "aborted"):
            self._streaming_text_len = 0
            self.signals.ai_message.emit(state, text)

    def _on_ai_thinking(self, state: str, text: str):
        if self.signals:
            self.signals.ai_thinking.emit(state, text)

    # NOTE: _on_tool_call / _on_tool_result 已移除
    # Gateway chat 事件不包含 toolCall/toolResult blocks，
    # tool 事件改由 MCP Server 侧回调推送 (见 mcp_server.py _connect_tool_events_to_bridge)
    # 非 MCP 工具由 _supplement_tool_events 从 transcript 补全

    def _supplement_tool_events(self):
        """从本地 transcript 文件补全非 MCP 工具调用事件。

        MCP 工具（run_ue_python / run_python）通过 MCP Server 回调推送 tool_call/tool_result。
        非 MCP 工具（exec, read, web_search 等）由 Gateway 内部执行，不经过 MCP Server。
        本方法在响应完成后读取 transcript，提取缺失的 toolCall/toolResult 并发射信号。
        """
        if not self.signals or not self._bridge:
            return
        session_key = self._bridge.get_session_key()
        if not session_key:
            return

        try:
            parts = session_key.split(":")
            if len(parts) < 2 or parts[0] != "agent":
                return
            agent_id = parts[1]
            openclaw_dir = os.path.join(os.path.expanduser("~"), ".openclaw")
            sessions_json = os.path.join(openclaw_dir, "agents", agent_id, "sessions", "sessions.json")

            if not os.path.exists(sessions_json):
                return

            with open(sessions_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            info = data.get(session_key, {})
            transcript = info.get("sessionFile", "")
            if not transcript:
                sid = info.get("sessionId", "")
                if sid:
                    transcript = os.path.join(openclaw_dir, "agents", agent_id, "sessions", f"{sid}.jsonl")
            if not transcript or not os.path.exists(transcript):
                return

            with open(transcript, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # 只处理最后 30 行，从最后一条 user 消息之后开始
            recent = lines[-30:] if len(lines) > 30 else lines
            last_user = -1
            for idx, line in enumerate(recent):
                try:
                    entry = json.loads(line)
                    msg = entry.get("message", {})
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        last_user = idx
                except (json.JSONDecodeError, ValueError):
                    continue

            start = last_user + 1 if last_user >= 0 else 0
            # 获取已由 MCP 推送的 tool id 集合
            emitted = getattr(self, "_emitted_tool_ids", set())
            count = 0

            for line in recent[start:]:
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                msg = entry.get("message", {})
                if not isinstance(msg, dict):
                    continue

                role = msg.get("role", "")
                content = msg.get("content", [])
                if not isinstance(content, list):
                    content = []

                # --- role="toolResult" 消息（Gateway transcript 格式）---
                if role == "toolResult":
                    tid = msg.get("toolCallId", "")
                    if f"r:{tid}" in emitted:
                        continue
                    emitted.add(f"r:{tid}")
                    tname = msg.get("toolName", "")
                    is_error = msg.get("isError", False)
                    rc = ""
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            rc += item.get("text", "")
                    if len(rc) > 2000:
                        rc = rc[:2000] + "...[truncated]"
                    self.signals.tool_result.emit(tname, tid, rc, is_error)
                    count += 1
                    continue

                # --- content blocks 中的 toolCall ---
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type", "")

                    if btype == "toolCall":
                        tid = block.get("id", "")
                        if tid in emitted:
                            continue
                        emitted.add(tid)
                        tname = block.get("name", "")
                        targs = block.get("arguments", {})
                        if isinstance(targs, dict):
                            targs = json.dumps(targs, ensure_ascii=False)
                        elif not isinstance(targs, str):
                            targs = str(targs)
                        self.signals.tool_call.emit(tname, tid, targs)
                        count += 1

                    elif btype == "toolResult":
                        tid = block.get("toolCallId", "")
                        if f"r:{tid}" in emitted:
                            continue
                        emitted.add(f"r:{tid}")
                        tname = block.get("toolName", "")
                        is_error = block.get("isError", False)
                        rc = block.get("content", "")
                        if isinstance(rc, list):
                            rc = "\n".join(
                                item.get("text", "")
                                for item in rc if isinstance(item, dict)
                            )
                        elif not isinstance(rc, str):
                            rc = str(rc)
                        if len(rc) > 2000:
                            rc = rc[:2000] + "...[truncated]"
                        self.signals.tool_result.emit(tname, tid, rc, is_error)
                        count += 1

            self._emitted_tool_ids = emitted
            if count > 0:
                self._log.info(f"Supplemented {count} non-MCP tool events from transcript")

        except Exception as e:
            self._log.warning(f"_supplement_tool_events failed: {e}")

    def _start_transcript_poll(self):
        """启动 transcript 文件轮询定时器（每 1s），实时发现新 tool 事件。"""
        self._stop_transcript_poll()  # 防止重复
        try:
            from PySide2.QtCore import QTimer
        except ImportError:
            try:
                from PySide6.QtCore import QTimer
            except ImportError:
                return
        self._transcript_timer = QTimer()
        self._transcript_timer.setInterval(1000)
        self._transcript_timer.timeout.connect(self._poll_transcript_tools)
        self._transcript_timer.start()

    def _get_transcript_line_count(self) -> int:
        """获取当前 transcript 文件行数，用于初始化增量读取位置。"""
        try:
            if not self._bridge:
                return 0
            session_key = self._bridge.get_session_key()
            if not session_key:
                return 0
            parts = session_key.split(":")
            if len(parts) < 2 or parts[0] != "agent":
                return 0
            agent_id = parts[1]
            openclaw_dir = os.path.join(os.path.expanduser("~"), ".openclaw")
            sessions_json = os.path.join(openclaw_dir, "agents", agent_id, "sessions", "sessions.json")
            if not os.path.exists(sessions_json):
                return 0
            with open(sessions_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            info = data.get(session_key, {})
            transcript = info.get("sessionFile", "")
            if not transcript:
                sid = info.get("sessionId", "")
                if sid:
                    transcript = os.path.join(openclaw_dir, "agents", agent_id, "sessions", f"{sid}.jsonl")
            if not transcript or not os.path.exists(transcript):
                return 0
            with open(transcript, "r", encoding="utf-8") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def _stop_transcript_poll(self):
        """停止 transcript 轮询定时器。"""
        timer = getattr(self, '_transcript_timer', None)
        if timer is not None:
            try:
                timer.stop()
                timer.deleteLater()
            except Exception:
                pass
            self._transcript_timer = None

    def _poll_transcript_tools(self):
        """定时器回调：增量读取 transcript 文件中的新 tool 事件。"""
        if not self.signals or not self._bridge:
            return
        session_key = self._bridge.get_session_key()
        if not session_key:
            return

        try:
            parts = session_key.split(":")
            if len(parts) < 2 or parts[0] != "agent":
                return
            agent_id = parts[1]
            openclaw_dir = os.path.join(os.path.expanduser("~"), ".openclaw")
            sessions_json = os.path.join(openclaw_dir, "agents", agent_id, "sessions", "sessions.json")
            if not os.path.exists(sessions_json):
                return

            with open(sessions_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            info = data.get(session_key, {})
            transcript = info.get("sessionFile", "")
            if not transcript:
                sid = info.get("sessionId", "")
                if sid:
                    transcript = os.path.join(openclaw_dir, "agents", agent_id, "sessions", f"{sid}.jsonl")
            if not transcript or not os.path.exists(transcript):
                return

            with open(transcript, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # 增量：只处理上次读到位置之后的新行
            start = getattr(self, '_transcript_poll_line', 0)
            if start >= len(lines):
                return
            new_lines = lines[start:]
            self._transcript_poll_line = len(lines)

            emitted = getattr(self, '_emitted_tool_ids', set())
            for line in new_lines:
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                msg = entry.get("message", {})
                if not isinstance(msg, dict):
                    continue

                role = msg.get("role", "")
                content = msg.get("content", [])
                if not isinstance(content, list):
                    content = []

                if role == "toolResult":
                    tid = msg.get("toolCallId", "")
                    if f"r:{tid}" in emitted:
                        continue
                    emitted.add(f"r:{tid}")
                    tname = msg.get("toolName", "")
                    is_error = msg.get("isError", False)
                    rc = ""
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            rc += item.get("text", "")
                    if len(rc) > 2000:
                        rc = rc[:2000] + "...[truncated]"
                    self.signals.tool_result.emit(tname, tid, rc, is_error)
                    continue

                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "toolCall":
                        tid = block.get("id", "")
                        if tid in emitted:
                            continue
                        emitted.add(tid)
                        tname = block.get("name", "")
                        targs = block.get("arguments", {})
                        if isinstance(targs, dict):
                            targs = json.dumps(targs, ensure_ascii=False)
                        elif not isinstance(targs, str):
                            targs = str(targs)
                        self.signals.tool_call.emit(tname, tid, targs)

            self._emitted_tool_ids = emitted

        except Exception as e:
            self._log.debug(f"_poll_transcript_tools: {e}")

    def _on_usage_update(self, usage: dict):
        if self.signals:
            # Gateway 推送的 usage 格式: {totalTokens, inputTokens, outputTokens, ...}
            total_tokens = usage.get("totalTokens", 0) or usage.get("total_tokens", 0)
            # 上下文窗口大小从 config 读取
            try:
                from artclaw_ui.utils import get_artclaw_config
                cfg = get_artclaw_config()
                ctx_total = cfg.get("context_window_size", 128000)
            except Exception:
                ctx_total = 128000
            self.signals.usage_update.emit(total_tokens, ctx_total)

    def _query_session_usage(self):
        """响应完成后，通过 sessions.list RPC 查询 session token 用量。
        对齐 UE 端 openclaw_chat._query_session_usage()。
        """
        if not self._bridge or not self._bridge.is_connected():
            return

        def _worker():
            try:
                import asyncio

                # 构建一次性 WebSocket 连接查询 sessions.list
                from bridge_config import get_gateway_config
                gw = get_gateway_config()
                port = gw.get("port", 18789)
                token = gw.get("auth", {}).get("token", "")
                gateway_url = f"ws://127.0.0.1:{port}"
                session_key = self._bridge.get_session_key()

                if not session_key:
                    return

                # 使用 bridge_core 的 RPC 直接查询（不需要单独的 websocket 连接）
                # bridge_core._loop 仍在运行，通过 run_coroutine_threadsafe 调度
                if self._bridge._loop and self._bridge._loop.is_running():
                    import concurrent.futures
                    future = asyncio.run_coroutine_threadsafe(
                        self._bridge._rpc_request("sessions.list", {}, timeout=10.0),
                        self._bridge._loop
                    )
                    result = future.result(timeout=15.0)

                    if isinstance(result, dict):
                        sessions = result.get("sessions", [])
                        for s in sessions:
                            if not isinstance(s, dict):
                                continue
                            s_key = s.get("key", "")
                            if s_key == session_key or session_key in s_key or s_key in session_key:
                                ctx_tokens = s.get("contextTokens", 0)
                                total_tokens = s.get("totalTokens", 0)
                                if total_tokens > 0 and self.signals:
                                    try:
                                        from artclaw_ui.utils import get_artclaw_config
                                        cfg = get_artclaw_config()
                                        ctx_window = cfg.get("context_window_size", 128000)
                                    except Exception:
                                        ctx_window = 128000
                                    # contextTokens = Gateway 报告的模型上下文窗口
                                    # totalTokens = 本次对话实际使用 token 数
                                    # 优先使用用户配置的上下文上限（更保守）
                                    capacity = ctx_window if ctx_window > 0 else (ctx_tokens if ctx_tokens > 0 else 128000)
                                    self.signals.usage_update.emit(total_tokens, capacity)
                                    logger.info(f"Session usage: {total_tokens}/{capacity}")
                                return
            except Exception as exc:
                logger.debug(f"Session usage query failed: {exc}")

        threading.Thread(target=_worker, daemon=True, name="OCUsageQuery").start()

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
