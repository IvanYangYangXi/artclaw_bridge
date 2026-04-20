"""
chat_panel_actions.py - ChatPanel 操作处理器
================================================

从 chat_panel.py 拆分出来的 Action/Slash 处理方法。
通过 mixin 模式注入 ChatPanel。

修复:
- _on_stop: 使用 remove_system_message + finalize_streaming
- _on_new_chat: 正确重置 session（对齐 UE OnNewChatClicked）
- _on_resume: 改进历史恢复逻辑
"""

from __future__ import annotations

import logging

from artclaw_ui.i18n import T

logger = logging.getLogger("artclaw.ui")

HELP_TEXT = (
    "=== 帮助 ===\n"
    "连接管理:\n"
    "  /connect     连接到 OpenClaw\n"
    "  /disconnect  断开连接\n"
    "  /diagnose    运行连接诊断\n"
    "  /status      显示当前状态\n"
    "聊天:\n"
    "  /clear       清空聊天记录\n"
    "  /cancel      取消当前请求\n"
    "  /resume      恢复接收中断的 AI 回复\n"
    "  /help        显示帮助\n"
    "  /plan        切换 Plan 模式\n"
    "AI 命令:\n"
    "  /new         开始新对话\n"
    "  /compact     压缩上下文\n"
    "  /review      审查选中内容\n"
    "  /undo        撤销上次操作"
)


class ChatPanelActionsMixin:
    """ChatPanel 的 Slash 命令 + 操作处理方法 mixin"""

    def _on_slash_command(self, cmd: str, args: str):
        self._input.clear()
        if cmd == "/clear":
            self._msg_list.clear()
            self._msg_list.add_message("system", T("chat_cleared"))
        elif cmd == "/cancel":
            self._on_stop()
        elif cmd == "/resume":
            self._on_resume()
        elif cmd == "/connect":
            self._on_connect()
        elif cmd == "/disconnect":
            self._on_disconnect()
        elif cmd == "/diagnose":
            self._on_diagnose()
        elif cmd == "/status":
            self._show_status()
        elif cmd == "/help":
            self._msg_list.add_message("system", T("help_text"))
        elif cmd == "/plan":
            if args:
                self._plan_mgr.plan_mode = True
                self._on_send_message(args)
            else:
                self._plan_mgr.plan_mode = not self._plan_mgr.plan_mode
                self._msg_list.add_message("system", T("plan_on") if self._plan_mgr.plan_mode else T("plan_off"))
        elif cmd == "/new":
            self._on_new_chat()
        else:
            full = f"{cmd} {args}".strip()
            self._msg_list.add_message("user", full)
            self._send_to_ai(full)

    def _on_connect(self):
        if not self._bridge:
            self._msg_list.add_message("system", "[错误] Bridge 未初始化")
            return
        self._msg_list.add_message("system", T("connecting"))
        connected = self._bridge.connect()
        self._status_bar.update_connection(connected)
        msg = T("connect_ok") if connected else T("connect_fail")
        self._msg_list.add_message("system", msg)

    def _on_disconnect(self):
        if self._bridge:
            self._bridge.disconnect()
        self._status_bar.update_connection(False)
        self._msg_list.add_message("system", T("disconnected_msg"))

    def _on_diagnose(self):
        self._msg_list.add_message("system", T("running_diag"))
        if self._bridge:
            result = self._bridge.run_diagnostics()
            self._msg_list.add_message("system", result)
        else:
            self._msg_list.add_message("system", "[错误] Bridge 未初始化")

    def _on_stop(self):
        """停止 AI 回复 — 对齐 UE OnStopClicked。"""
        if not self._is_waiting:
            self._msg_list.add_message("system", T("no_request"))
            return

        # 1) 通知 bridge 取消
        if self._bridge:
            self._bridge.cancel()

        # 2) 重置等待状态
        self._is_waiting = False
        self._has_active_stream = False
        self._toolbar.set_waiting(False)

        # 3) 移除T("thinking")和流式/思考消息
        self._msg_list.remove_system_message(T("thinking"))
        # 移除尾部的 streaming/thinking 消息
        msgs = self._msg_list._messages
        widgets = self._msg_list._widgets
        while msgs and msgs[-1].sender in ("thinking", "streaming"):
            msgs.pop()
            if widgets:
                widgets.pop().deleteLater()

        # 4) 重置流式追踪
        self._msg_list._streaming_widget = None

        # 5) 添加停止通知
        self._msg_list.add_message("system", T("stopped"))

    def _on_resume(self):
        """恢复接收中断的 AI 回复 — 从 Gateway 拉取完整会话历史"""
        if self._is_waiting:
            self._msg_list.add_message("system", "AI 正在回复中，请等待或点击停止...")
            return

        if not self._bridge:
            self._msg_list.add_message("system", "[错误] Bridge 未初始化")
            return

        # 获取当前会话的 session key — 优先从 bridge 获取（Gateway 格式）
        session_key = ""
        if self._bridge._bridge:
            session_key = self._bridge._bridge.get_session_key()

        if not session_key:
            entry = self._session_mgr.active_entry
            if entry:
                session_key = entry.session_key

        if not session_key or session_key.startswith("local-"):
            self._msg_list.add_message("system", T("no_session"))
            return

        self._msg_list.add_message("system", T("resuming"))

        # 从 Gateway 拉取完整会话历史
        messages = self._session_mgr.fetch_history(session_key, self._bridge)
        if not messages:
            self._msg_list.add_message("system", T("no_history"))
            return

        # 用 Gateway 完整历史替换当前面板
        self._msg_list.clear()
        for m in messages:
            sender = m.get("sender", "system")
            content = m.get("content", "")
            self._msg_list.add_message(sender, content)
        self._msg_list.add_message("system", T("resume_done"))

    def _on_new_chat(self):
        """新对话 — 对齐 UE OnNewChatClicked。"""
        # 0) 清空附件
        self._attach_mgr.clear()

        # 0b) 取消正在执行的 Plan
        if self._plan_mgr.current_plan:
            if self._plan_mgr.current_plan.is_executing and self._is_waiting:
                self._on_stop()
            self._plan_mgr.current_plan = None

        # 1) 保存当前活跃会话的 session key
        if self._bridge and self._bridge._bridge:
            real_key = self._bridge._bridge.get_session_key()
            if real_key and self._session_mgr.active_entry:
                self._session_mgr.active_entry.session_key = real_key

        # 2) 清屏
        self._msg_list.clear()
        self._msg_list.add_message("system", T("new_chat"))

        # 3) 重置 Bridge session
        if self._bridge:
            self._bridge.reset_session()
            self._bridge._context_injected = False

        # 4) 创建新会话条目
        self._session_mgr.new_session_local()
        self._status_bar.set_session_label(self._session_mgr.get_active_label())

        # 5) 保存
        if self._bridge:
            self._session_mgr.save_last_session(self._bridge)

        # 6) 刷新会话菜单
        self._refresh_session_menu()

    def _on_manage(self):
        from artclaw_ui.manage_panel import ManagePanel
        ManagePanel.show_as_window(parent=self)

    def _on_open_tool_manager(self):
        """启动 ArtClaw Tool Manager 后台服务并打开浏览器"""
        # 确保 core/ 在 sys.path（tool_manager_launcher 位于 core/）
        import sys, os
        _core_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _core_core = os.path.join(_core_dir, "core")
        if os.path.isdir(_core_core) and _core_core not in sys.path:
            sys.path.insert(0, _core_core)

        try:
            from tool_manager_launcher import launch
            result = launch(open_browser=True)
            if not result["ok"]:
                self._msg_list.add_message(
                    "system", f"[Tool Manager] 启动失败: {result['error']}"
                )
            elif not result["already_running"]:
                self._msg_list.add_message(
                    "system", "[Tool Manager] 正在启动服务，请稍候..."
                )
        except ImportError:
            # Fallback: tool_manager_launcher not in sys.path
            import webbrowser
            webbrowser.open("http://localhost:9876")

    def _on_settings(self):
        from artclaw_ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(bridge_manager=self._bridge, parent=self)
        dlg.send_mode_changed.connect(self._input.set_enter_to_send)
        dlg.manage_requested.connect(lambda: self._open_manage_from_settings(dlg))
        dlg.agent_changed.connect(self._on_agent_changed)
        dlg.plan_mode_changed.connect(self._on_plan_mode_changed)
        dlg.context_window_changed.connect(self._on_context_window_changed)
        dlg.silent_mode_changed.connect(self._on_silent_mode_changed)
        dlg.language_changed.connect(self._on_language_changed)
        dlg.platform_changed.connect(self._on_platform_changed)
        dlg.exec_()

    def _open_manage_from_settings(self, settings_dlg):
        """从设置弹窗打开管理面板 — 先关闭设置弹窗避免层级遮挡"""
        settings_dlg.accept()
        self._on_manage()

    def _on_agent_changed(self, agent_id: str):
        if not self._bridge:
            return
        old_id = self._bridge.get_agent_id()
        if old_id:
            self._session_mgr.cache_for_agent_switch(old_id)
        self._bridge.set_agent(agent_id)
        self._session_mgr.restore_from_agent_switch(agent_id)
        if not self._session_mgr.entries:
            self._session_mgr.init_first_session()
        self._msg_list.clear()
        active = self._session_mgr.entries[self._session_mgr.active_index]
        for m in active.cached_messages:
            self._msg_list.add_message(m.sender, m.content)
        self._status_bar.set_session_label(self._session_mgr.get_active_label())
        self._msg_list.add_message("system", f"已切换到 Agent: {agent_id}")
        try:
            agents = self._bridge.list_agents()
            for a in agents:
                if a.get("id") == agent_id:
                    self._status_bar.set_agent_label(
                        a.get("emoji", ""), a.get("name", agent_id))
                    break
        except Exception:
            pass

    def _on_plan_mode_changed(self, enabled: bool):
        self._plan_mgr.plan_mode = enabled

    def _on_context_window_changed(self, size: int):
        self._status_bar.update_context_usage(0, size)

    def _on_silent_mode_changed(self, level: str, enabled: bool):
        med = getattr(self._confirm_poller, '_silent_medium', False)
        high = getattr(self._confirm_poller, '_silent_high', False)
        if level == "medium":
            self._confirm_poller.set_silent(enabled, high)
        elif level == "high":
            self._confirm_poller.set_silent(med, enabled)

    def _on_language_changed(self):
        """语言切换 — 立即刷新 UI 文本"""
        from artclaw_ui.i18n import init_language, get_lang
        init_language()  # 重新从 config 读取语言
        lang = get_lang()

        # 刷新工具栏按钮文本
        self._toolbar.refresh_language()

        # 刷新状态栏
        if hasattr(self._status_bar, 'refresh_language'):
            self._status_bar.refresh_language()

        if lang == "zh":
            self._msg_list.add_message("system", "语言已切换为中文")
        else:
            self._msg_list.add_message("system", "Language changed to English")

    def _on_platform_changed(self, platform_type: str):
        """平台切换 → 断开并重连到新平台 Gateway（MCP-only 平台跳过连接）。"""
        if not self._bridge:
            return

        # 显示切换中状态
        try:
            from bridge_config import get_available_platforms, get_gateway_url
            platforms = get_available_platforms()
            name_map = {p["type"]: p.get("display_name", p["type"])
                        for p in platforms}
            display_name = name_map.get(platform_type, platform_type)
        except Exception:
            display_name = platform_type

        self._msg_list.add_message("system",
            f"正在切换到 {display_name}...")

        # 检查新平台是否有 Gateway（MCP-only 平台没有 gateway_url）
        try:
            gateway_url = get_gateway_url()
        except Exception:
            gateway_url = ""

        # 断开旧连接
        self._bridge.disconnect()
        self._bridge._context_injected = False

        if not gateway_url:
            # MCP-only 平台（Cursor/Claude Code/WorkBuddy 等）
            # 不尝试 WebSocket 连接，只更新配置
            self._msg_list.add_message("system",
                f"已切换到 {display_name}\n"
                f"该平台通过自身 UI 进行对话，DCC 插件仅记录平台配置。\n"
                f"Skill/配置路径已更新。")
            self._status_bar.update_connection(False)

            # 仍然刷新 Skill 目录
            try:
                from core.skill_runtime import get_skill_runtime
                rt = get_skill_runtime()
                if rt:
                    count = rt.reload_skills_dir()
                    logger.info(f"Skills reloaded after platform switch: {count}")
            except Exception as e:
                logger.warning(f"Failed to reload skills after platform switch: {e}")
        else:
            # Gateway 平台 → 正常重连
            connected = self._bridge.connect()

            if connected:
                # 从新平台查询 agent 列表并切换到第一个可用 agent
                try:
                    agents = self._bridge.list_agents()
                    if agents:
                        first_agent = agents[0]
                        agent_id = first_agent.get("id", "")
                        if agent_id:
                            self._bridge.set_agent(agent_id)
                            self._status_bar.set_agent_label(
                                first_agent.get("emoji", ""),
                                first_agent.get("name", agent_id))
                            logger.info(f"Platform switch: agent set to {agent_id}")
                except Exception as e:
                    logger.warning(f"Failed to query agents after platform switch: {e}")

                # 重置 session（新平台 = 全新开始，清空旧会话列表）
                self._bridge.reset_session()
                self._session_mgr.entries.clear()
                self._session_mgr.agent_session_cache.clear()
                self._session_mgr.init_first_session()
                self._status_bar.set_session_label(self._session_mgr.get_active_label())

                self._msg_list.clear()
                self._msg_list.add_message("system",
                    f"已切换到 {display_name}")

                # 刷新 Skill 安装目录（不同平台 Skills 路径不同）
                try:
                    from core.skill_runtime import get_skill_runtime
                    rt = get_skill_runtime()
                    if rt:
                        count = rt.reload_skills_dir()
                        logger.info(f"Skills reloaded after platform switch: {count}")
                except Exception as e:
                    logger.warning(f"Failed to reload skills after platform switch: {e}")
            else:
                self._msg_list.add_message("system",
                    f"切换到 {display_name} 失败：Gateway 未响应")

        # 更新状态栏
        self._status_bar.update_connection(connected)
        if hasattr(self._status_bar, 'refresh_language'):
            self._status_bar.refresh_language()

    def _on_attach_file(self):
        self._attach_mgr.add_from_file_dialog(self)

    def _on_paste_attempt(self):
        if self._attach_mgr.add_from_clipboard():
            return
        self._attach_mgr.add_from_clipboard_path()

    def _on_attachments_changed(self, count: int):
        self._attach_preview.rebuild()

    def _on_create_skill(self):
        guide = ("I want to create a new skill that can help me with "
                 "DCC editor tasks. Please guide me through the process.")
        self._input.set_text(guide)

    def _show_status(self):
        connected = self._bridge.is_connected() if self._bridge else False
        status = T("connected") if connected else T("disconnected")
        mode = T("enter_send") if self._input._enter_to_send else T("ctrl_enter_send")
        msg_count = len(self._msg_list._messages)
        session_key = ""
        if self._bridge and self._bridge._bridge:
            session_key = self._bridge._bridge.get_session_key() or "N/A"
        self._msg_list.add_message("system",
            f"Status: {status}\nMessages: {msg_count}\nSend: {mode}\nSession: {session_key[:40]}")
