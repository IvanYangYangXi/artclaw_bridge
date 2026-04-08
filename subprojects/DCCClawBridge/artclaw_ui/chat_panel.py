"""
chat_panel.py - ArtClaw DCC 聊天面板 (主组装器)
=================================================

组装所有子模块（状态栏、消息列表、输入框、工具栏、快捷输入、
附件、会话管理、Plan 等），连接信号，管理 Bridge 生命周期。

Maya / Max 共享，通过 DCC adapter 适配各软件。

修复对齐 UE 实现:
- 发送消息不再导致 disconnected
- 流式消息正确更新和结束
- T("thinking") 消息正确移除
- session key 使用 Gateway 格式
"""

from __future__ import annotations

import logging
from typing import Optional

from artclaw_ui.qt_compat import *  # noqa: F401,F403
HAS_QT = True

from artclaw_ui.theme import get_theme
from artclaw_ui.utils import get_artclaw_config
from artclaw_ui.i18n import T, init_language
from artclaw_ui.chat_panel_actions import ChatPanelActionsMixin

logger = logging.getLogger("artclaw.ui")

_panel_instance: Optional["ChatPanel"] = None


class ChatPanel(ChatPanelActionsMixin, QWidget):
    """ArtClaw DCC 聊天面板 — 组装所有子模块"""

    def __init__(self, parent=None, adapter=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window)
        # 独立窗口模式（无父窗口，如 Blender）：关闭时销毁，触发 destroyed 信号
        if parent is None:
            self.setAttribute(Qt.WA_DeleteOnClose, True)
        self._adapter = adapter
        init_language()  # 初始化 i18n
        cfg = get_artclaw_config()
        dcc = cfg.get("dcc_name", "maya")
        self._t = get_theme(dcc)
        self._dcc_name = dcc

        self._bridge = None
        self._is_waiting = False
        # 追踪是否有活跃的流式消息（比 _streaming_widget 更可靠）
        self._has_active_stream = False

        # 子模块
        from artclaw_ui.chat_attachments import AttachmentManager
        from artclaw_ui.chat_session import SessionManager
        from artclaw_ui.plan_panel import PlanManager
        from artclaw_ui.confirm_dialog import ConfirmPoller

        self._session_mgr = SessionManager()
        self._attach_mgr = AttachmentManager()
        self._plan_mgr = PlanManager()
        self._confirm_poller = ConfirmPoller()

        self._build_ui()
        self._connect_signals()
        self._init_bridge()
        self._init_session()
        self._start_pollers()

        # 从配置恢复发送方式
        enter_send = cfg.get("enter_send", True)
        self._input.set_enter_to_send(enter_send)

    # ==============================================================
    # UI Construction
    # ==============================================================

    def _build_ui(self):
        from artclaw_ui.chat_messages import MessageListWidget
        from artclaw_ui.chat_status_bar import StatusBarWidget
        from artclaw_ui.chat_toolbar import ToolbarWidget
        from artclaw_ui.chat_input import ChatInputWidget
        from artclaw_ui.chat_quick_input import QuickInputPanel
        from artclaw_ui.chat_attachments import AttachmentPreviewWidget

        t = self._t
        self.setStyleSheet(f"background-color: {t['bg_primary']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._status_bar = StatusBarWidget()
        root.addWidget(self._status_bar)

        self._msg_list = MessageListWidget()
        root.addWidget(self._msg_list, 1)

        self._quick_input = QuickInputPanel()
        root.addWidget(self._quick_input)

        self._attach_preview = AttachmentPreviewWidget(self._attach_mgr)
        root.addWidget(self._attach_preview)

        self._input = ChatInputWidget()
        root.addWidget(self._input)

        self._toolbar = ToolbarWidget()
        root.addWidget(self._toolbar)

    # ==============================================================
    # Signal Wiring
    # ==============================================================

    def _connect_signals(self):
        # Input
        self._input.message_submitted.connect(self._on_send_message)
        self._input.slash_command.connect(self._on_slash_command)
        self._input.paste_attempted.connect(self._on_paste_attempt)

        # Toolbar
        self._toolbar.send_clicked.connect(self._on_send_clicked)
        self._toolbar.stop_clicked.connect(self._on_stop)
        self._toolbar.new_chat_clicked.connect(self._on_new_chat)
        self._toolbar.manage_clicked.connect(self._on_manage)
        self._toolbar.attach_clicked.connect(self._on_attach_file)
        self._toolbar.resume_clicked.connect(self._on_resume)

        # Status bar
        self._status_bar.connect_clicked.connect(self._on_connect)
        self._status_bar.disconnect_clicked.connect(self._on_disconnect)
        self._status_bar.diagnose_clicked.connect(self._on_diagnose)
        self._status_bar.settings_clicked.connect(self._on_settings)
        self._status_bar.session_menu_clicked.connect(self._on_session_menu)

        # Quick input
        self._quick_input.input_selected.connect(self._input.set_text)
        self._quick_input.create_skill_clicked.connect(self._on_create_skill)

        # Attachment
        self._attach_preview.attachments_changed.connect(self._on_attachments_changed)

    # ==============================================================
    # Bridge Init
    # ==============================================================

    def _init_bridge(self):
        try:
            from core.bridge_dcc import DCCBridgeManager
            self._bridge = DCCBridgeManager.instance()

            if self._bridge.signals:
                self._bridge.signals.connection_changed.connect(self._on_connection_changed)
                self._bridge.signals.ai_message.connect(self._on_ai_message)
                self._bridge.signals.ai_thinking.connect(self._on_ai_thinking)
                self._bridge.signals.tool_call.connect(self._on_tool_call)
                self._bridge.signals.tool_result.connect(self._on_tool_result)
                self._bridge.signals.usage_update.connect(self._on_usage_update)
                self._bridge.signals.response_complete.connect(self._on_response_complete)

            cfg = get_artclaw_config()
            if cfg.get("auto_connect", True):
                connected = self._bridge.connect()
                self._status_bar.update_connection(connected)
        except Exception as ex:
            logger.error("Bridge 初始化失败: %s", ex)
            self._msg_list.add_message("system", f"[错误] Bridge 初始化失败: {ex}")

    def _init_session(self):
        if self._bridge:
            self._session_mgr.restore_or_init(self._bridge)
        else:
            self._session_mgr.init_first_session()
        self._status_bar.set_session_label(self._session_mgr.get_active_label())

        # 上下文窗口默认值
        cfg = get_artclaw_config()
        ctx_size = cfg.get("context_window_size", 128 * 1024)
        self._status_bar.update_context_usage(0, ctx_size)

        if self._bridge:
            try:
                agents = self._bridge.list_agents()
                agent_id = self._bridge.get_agent_id()
                for a in agents:
                    if a.get("id") == agent_id:
                        self._status_bar.set_agent_label(
                            a.get("emoji", ""), a.get("name", agent_id))
                        break
            except Exception:
                pass

    def _start_pollers(self):
        cfg = get_artclaw_config()
        data_dir = cfg.get("data_dir", "")
        if data_dir:
            self._confirm_poller.set_silent(
                cfg.get("silent_mode_medium", False),
                cfg.get("silent_mode_high", False))
            self._confirm_poller.start(data_dir)

        # MCP + 连接状态轮询 (每 5 秒，对齐 UE 的 BridgeStatusPollHandle)
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._poll_status)
        self._status_timer.start(5000)
        # 立即检查一次
        QTimer.singleShot(500, self._poll_status)

    def _poll_status(self):
        """定期轮询 MCP Server 运行状态 + Bridge 连接状态 + Session token 用量"""
        # MCP 状态
        mcp_ready = False
        try:
            from core.mcp_server import get_mcp_server
            s = get_mcp_server()
            mcp_ready = bool(s and s.is_running)
        except Exception:
            pass
        self._status_bar.update_mcp_status(mcp_ready)

        # Bridge 连接状态
        if self._bridge:
            connected = self._bridge.is_connected()
            self._status_bar.update_connection(connected)

        # Session token 用量（对齐 UE 的 BridgeStatusPoll）
        self._poll_session_usage()

    def _poll_session_usage(self):
        """通过 sessions.list RPC 查询当前 session 的 token 用量。
        对齐 UE 端 BridgeStatusPoll 的 _session_usage.json 轮询。
        """
        if not self._bridge or not self._bridge.is_connected():
            return
        core = self._bridge._bridge
        if not core or not core._loop or not core._loop.is_running():
            return
        sk = core.get_session_key()
        if not sk:
            return

        # 检查是否有未完成的查询（避免堆积）
        if getattr(self, '_usage_query_pending', False):
            return

        import asyncio

        async def _query(bc, session_key):
            try:
                resp = await bc._rpc_request("sessions.list", {}, timeout=5.0)
                if isinstance(resp, dict):
                    for s in resp.get("sessions", []):
                        if not isinstance(s, dict):
                            continue
                        s_key = s.get("key", "")
                        if s_key == session_key or session_key in s_key or s_key in session_key:
                            return s.get("totalTokens", 0), s.get("contextTokens", 0)
                return 0, 0
            except Exception:
                return 0, 0

        self._usage_query_pending = True
        fut = asyncio.run_coroutine_threadsafe(_query(core, sk), core._loop)

        # 用 QTimer 轮询 future 完成状态（不阻塞主线程）
        def _check_result():
            if not fut.done():
                QTimer.singleShot(100, _check_result)
                return
            self._usage_query_pending = False
            try:
                total, ctx = fut.result(timeout=0)
                if total > 0:
                    # 优先使用用户配置的上下文上限，Gateway 的 contextTokens 作 fallback
                    cfg = get_artclaw_config()
                    ctx_window = cfg.get("context_window_size", 128 * 1024)
                    capacity = ctx_window if ctx_window > 0 else (ctx if ctx > 0 else 128 * 1024)
                    self._status_bar.update_context_usage(total, capacity)
            except Exception:
                pass

        QTimer.singleShot(100, _check_result)

    # ==============================================================
    # Message Sending
    # ==============================================================

    def _on_send_clicked(self):
        text = self._input.get_text().strip()
        if text:
            self._input.clear()
            self._on_send_message(text)

    def _on_send_message(self, text: str):
        if not text.strip():
            return

        if text.startswith("/"):
            parts = text.split(" ", 1)
            cmd = parts[0].lower()
            args = parts[1].strip() if len(parts) > 1 else ""
            self._on_slash_command(cmd, args)
            return

        if self._is_waiting:
            self._msg_list.add_message("system", T("ai_waiting"))
            return

        display = text
        att_paths = self._attach_mgr.get_display_paths()
        if att_paths:
            display = "\n".join(att_paths) + "\n" + text
        self._msg_list.add_message("user", display)

        if self._plan_mgr.plan_mode and not self._plan_mgr.current_plan:
            self._plan_mgr._last_request = text
            plan_prompt = (
                "Please create a step-by-step plan for the following task.\n"
                "Output ONLY the plan in this exact JSON format:\n"
                '```json\n{"plan":{"steps":[{"index":1,"title":"...","description":"..."}]}}\n```\n'
                f"Task: {text}"
            )
            self._send_to_ai(plan_prompt)
            return

        final = self._attach_mgr.get_prefix_text() + text
        self._attach_mgr.clear()
        self._send_to_ai(final)

    def _send_to_ai(self, message: str):
        if not self._bridge:
            self._msg_list.add_message("system", "[错误] 未连接到 OpenClaw")
            return

        # 检查连接状态
        if not self._bridge.is_connected():
            self._msg_list.add_message("system", "[错误] 未连接到 OpenClaw，正在尝试重连...")
            connected = self._bridge.connect()
            if not connected:
                self._msg_list.add_message("system", "[错误] 重连失败，请检查 OpenClaw 是否运行")
                return

        self._is_waiting = True
        self._has_active_stream = False
        self._toolbar.set_waiting(True)
        self._msg_list.add_message("system", T("thinking"))
        self._bridge.send_message(message)

    # ==============================================================
    # Bridge Callbacks
    # ==============================================================

    @Slot(bool, str)
    def _on_connection_changed(self, connected: bool, detail: str):
        self._status_bar.update_connection(connected)
        if not connected and detail:
            # 只在非等待状态下显示断连消息，避免发送消息时产生误导
            # bridge_core 重连时也会触发 disconnected，不应干扰正常流程
            if not self._is_waiting:
                self._msg_list.add_message("system", f'{T("conn_lost")}: {detail}')

    @Slot(str, str)
    def _on_ai_message(self, state: str, text: str):
        """处理 AI 消息流。

        state:
          - "delta": 流式增量/累积文本
          - "final": 完整响应（由 response_complete 处理）
          - "error": 错误消息
          - "aborted": 中止
        """
        if not text:
            return

        if state == "delta":
            # 响应已完成时，拒绝迟到的 delta（Qt signal 跨线程延迟导致）
            if not self._is_waiting:
                return
            # 如果还有T("thinking")消息，先移除
            if not self._has_active_stream:
                self._msg_list.remove_system_message(T("thinking"))
                self._has_active_stream = True
            self._msg_list.update_streaming_message("streaming", text)
        elif state == "final":
            # final 由 _on_response_complete 处理，这里忽略
            pass
        elif state == "error":
            self._msg_list.remove_system_message(T("thinking"))
            self._msg_list.add_message("system", f"[错误] {text}")
        elif state == "aborted":
            self._msg_list.remove_system_message(T("thinking"))
            self._msg_list.add_message("system", "[已中止]")

    @Slot(str, str, str)
    def _on_tool_call(self, tool_name: str, tool_id: str, arguments: str):
        # 工具调用到达时，先移除T("thinking")
        if not self._has_active_stream:
            self._msg_list.remove_system_message(T("thinking"))
            self._has_active_stream = True
        self._msg_list.add_tool_call(tool_name, tool_id, arguments)

    @Slot(str, str, str, bool)
    def _on_tool_result(self, tool_name: str, tool_id: str, content: str, is_error: bool):
        self._msg_list.add_tool_result(tool_name, tool_id, content, is_error)

    @Slot(int, int)
    def _on_usage_update(self, used: int, total: int):
        self._status_bar.update_context_usage(used, total)

    @Slot(str, str)
    def _on_ai_thinking(self, state: str, text: str):
        # 响应已完成时，拒绝迟到的 thinking（Qt signal 跨线程延迟导致）
        if not self._is_waiting:
            return
        if not self._has_active_stream:
            self._msg_list.remove_system_message(T("thinking"))
            self._has_active_stream = True
        self._msg_list.update_streaming_message("thinking", text)

    @Slot(str)
    def _on_response_complete(self, result: str):
        """AI 响应完成 — 清理状态、结束流式消息。"""
        self._is_waiting = False
        self._has_active_stream = False
        self._toolbar.set_waiting(False)

        # 移除可能残留的 thinking 消息
        self._msg_list.remove_system_message(T("thinking"))

        # 用完整的 result 文本更新 streaming widget，确保不丢失最后几个字
        # bridge_core 的 _wait_for_final 返回的 result 是完整文本，
        # 但 Qt signal 的跨线程延迟可能导致最后几个 delta 没被 streaming widget 消费
        if result and not result.startswith("[错误]") and not result.startswith("[Error]"):
            self._msg_list.update_streaming_content_if_longer(result)

        # 结束流式消息（streaming → assistant）
        had_streaming = self._msg_list.finalize_streaming()

        # 如果没有流式消息到达（signal 未触发），直接添加最终结果
        if not had_streaming and result and not result.startswith("[错误]") and not result.startswith("[Error]"):
            self._msg_list.add_message("assistant", result)

        # Plan mode handling
        if self._plan_mgr.plan_mode and not self._plan_mgr.current_plan:
            self._plan_mgr.try_parse_plan(result)
        if self._plan_mgr.current_plan and self._plan_mgr.current_plan.is_executing:
            self._plan_mgr.handle_step_result(result)

        if self._bridge:
            self._session_mgr.save_last_session(self._bridge)
            self._refresh_session_menu()

        # 更新 session entry 的 session key（可能在首次发送后由 Gateway 分配）
        if self._bridge and self._bridge._bridge:
            real_key = self._bridge._bridge.get_session_key()
            if real_key and self._session_mgr.active_entry:
                old_key = self._session_mgr.active_entry.session_key
                if old_key != real_key:
                    self._session_mgr.active_entry.session_key = real_key
                    self._session_mgr.save_last_session(self._bridge)

    # ==============================================================
    # Cleanup
    # ==============================================================

    # ==============================================================
    # Session Menu
    # ==============================================================

    def _cache_current_messages(self):
        """将当前消息列表缓存到 active session entry"""
        entry = self._session_mgr.active_entry
        if entry and hasattr(self._msg_list, '_messages'):
            entry.cached_messages = [
                {"sender": m.sender, "content": m.content}
                for m in self._msg_list._messages
            ]

    def _on_session_menu(self):
        """点击会话按钮 → 弹出独立弹窗式会话列表"""
        from artclaw_ui.chat_session import SessionMenuWidget
        if hasattr(self, '_session_menu') and self._session_menu and self._session_menu.isVisible():
            self._session_menu.close()
            self._session_menu = None
            return

        self._session_menu = SessionMenuWidget(self._session_mgr, parent=None)
        self._session_menu.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self._session_menu.setAttribute(Qt.WA_DeleteOnClose, False)
        self._session_menu.session_selected.connect(self._on_session_selected)
        self._session_menu.session_deleted.connect(self._on_session_deleted)
        self._session_menu.new_session_clicked.connect(self._on_session_menu_new)

        # 用屏幕绝对坐标定位在 session 按钮下方
        btn = self._status_bar._session_btn
        global_pos = btn.mapToGlobal(btn.rect().bottomLeft())
        menu_width = min(300, self.width() - 20)
        menu_height = min(400, max(150, len(self._session_mgr.entries) * 30 + 60))
        self._session_menu.setFixedSize(menu_width, menu_height)
        self._session_menu.move(global_pos.x(), global_pos.y() + 2)
        self._session_menu.show()

    def _on_session_selected(self, index: int):
        """会话列表中选择某个会话"""
        if not self._bridge:
            return

        # 先缓存当前消息
        self._cache_current_messages()

        entry = self._session_mgr.switch_session(index, self._bridge)
        if entry is None:
            return

        # 更新 UI
        self._msg_list.clear()
        self._bridge._context_injected = False

        # 优先从 Gateway 恢复历史
        restored = False
        if entry.session_key and not entry.session_key.startswith("local-") and not entry.session_key == "":
            messages = self._session_mgr.fetch_history(entry.session_key, self._bridge)
            if messages:
                for m in messages:
                    self._msg_list.add_message(m.get("sender", "system"), m.get("content", ""))
                restored = True

        # 否则用缓存消息
        if not restored and entry.cached_messages:
            for m in entry.cached_messages:
                self._msg_list.add_message(m.get("sender", "system"), m.get("content", ""))

        self._status_bar.set_session_label(self._session_mgr.get_active_label())

        if hasattr(self, '_session_menu') and self._session_menu:
            self._session_menu.hide()

    def _on_session_deleted(self, index: int):
        """删除某个会话"""
        is_active = (index == self._session_mgr.active_index)
        self._session_mgr.delete_session(index)

        if is_active and self._session_mgr.entries:
            # 切到新的 active
            new_entry = self._session_mgr.active_entry
            if new_entry and self._bridge:
                self._bridge.set_session_key(new_entry.session_key)
                self._msg_list.clear()
                for m in new_entry.cached_messages:
                    self._msg_list.add_message(m.get("sender", "system"), m.get("content", ""))
        elif not self._session_mgr.entries:
            # 没有会话了，创建一个新的
            self._session_mgr.init_first_session()
            self._msg_list.clear()
            if self._bridge:
                self._bridge.reset_session()

        self._status_bar.set_session_label(self._session_mgr.get_active_label())

        if hasattr(self, '_session_menu') and self._session_menu:
            self._session_menu.refresh()

    def _on_session_menu_new(self):
        """从会话菜单点击"新对话" """
        if hasattr(self, '_session_menu') and self._session_menu:
            self._session_menu.hide()
        self._on_new_chat()

    def _refresh_session_menu(self):
        """刷新会话菜单（如果打开了的话）"""
        if hasattr(self, '_session_menu') and self._session_menu and self._session_menu.isVisible():
            self._session_menu.refresh()

    def closeEvent(self, event):
        global _panel_instance
        if hasattr(self, '_status_timer') and self._status_timer:
            self._status_timer.stop()
        self._confirm_poller.stop()
        if self._bridge:
            self._session_mgr.save_last_session(self._bridge)
        # 清空全局引用，允许下次 show_panel 创建新实例
        if _panel_instance is self:
            _panel_instance = None
        super().closeEvent(event)


# ======================================================================
# Public API
# ======================================================================

def show_chat_panel(parent=None, adapter=None) -> ChatPanel:
    """创建或复用聊天面板"""
    global _panel_instance
    if _panel_instance is not None:
        try:
            # 检查 C++ 对象是否仍然存活
            _panel_instance.isVisible()
            _panel_instance.show()
            _panel_instance.raise_()
            return _panel_instance
        except (RuntimeError, AttributeError):
            _panel_instance = None
    panel = ChatPanel(parent=parent, adapter=adapter)
    panel.setWindowTitle("ArtClaw Chat")
    panel.resize(420, 700)
    panel.show()
    _panel_instance = panel
    return panel


def get_chat_panel() -> Optional[ChatPanel]:
    return _panel_instance
