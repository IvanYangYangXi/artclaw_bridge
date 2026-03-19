"""
chat_panel.py - ArtClaw Chat Panel (Qt)
========================================

通用聊天面板，Maya / Max 共享。
通过 DCC adapter 适配各软件的主窗口和线程调度。

功能:
  - 消息列表（流式逐字显示，累积文本覆盖）
  - 输入框（Enter 发送，Shift+Enter 换行）
  - / 命令补全下拉
  - 快捷输入面板（可配置常用短语）
  - 连接状态指示
  - Markdown 基础渲染（代码块 + 加粗）
"""

from __future__ import annotations

import json
import logging
import os
from typing import List, Optional

try:
    from PySide2.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
        QPushButton, QLabel, QFrame, QListWidget, QListWidgetItem,
        QSizePolicy, QApplication, QToolButton, QMenu, QAction,
    )
    from PySide2.QtCore import Qt, Slot, QTimer, QSize, Signal
    from PySide2.QtGui import QFont, QTextCursor, QKeyEvent
    HAS_QT = True
except ImportError:
    HAS_QT = False

logger = logging.getLogger("artclaw.ui")

_panel_instance: Optional["ChatPanel"] = None

# 最大消息数（参考 UE 的 MaxMessages = 500）
MAX_MESSAGES = 500


class ChatPanel(QWidget):
    """ArtClaw 聊天面板"""

    def __init__(self, parent=None, adapter=None):
        super().__init__(parent)
        self._adapter = adapter
        self._bridge_manager = None
        self._is_streaming = False
        self._streaming_text = ""  # 当前流式累积文本
        self._message_count = 0
        self._quick_inputs: List[dict] = []
        self._last_ai_cursor_pos: int = -1  # 最后一条 AI 消息的起始位置

        self.setWindowTitle("ArtClaw Chat")
        self.setMinimumSize(400, 500)
        self.resize(450, 650)
        self.setWindowFlags(Qt.Window)

        self._setup_ui()
        self._setup_bridge()
        self._load_quick_inputs()
        self._update_window_title()

    def _update_window_title(self):
        """根据 DCC 名称设置窗口标题"""
        if self._adapter:
            try:
                sw_name = self._adapter.get_software_name()
                self.setWindowTitle(f"ArtClaw Chat - {sw_name}")
            except Exception:
                pass

    def _setup_ui(self):
        """构建界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # --- 状态栏 ---
        status_layout = QHBoxLayout()
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color: #888; font-size: 14px;")
        self._status_label = QLabel("未连接")
        self._status_label.setStyleSheet("color: #888; font-size: 11px;")

        self._connect_btn = QPushButton("连接")
        self._connect_btn.setFixedWidth(60)
        self._connect_btn.clicked.connect(self._on_connect_clicked)

        self._new_btn = QPushButton("新对话")
        self._new_btn.setFixedWidth(60)
        self._new_btn.clicked.connect(self._on_new_chat_clicked)

        status_layout.addWidget(self._status_dot)
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()
        status_layout.addWidget(self._new_btn)
        status_layout.addWidget(self._connect_btn)
        layout.addLayout(status_layout)

        # --- 分隔线 ---
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #555;")
        layout.addWidget(line)

        # --- 消息区域 ---
        self._message_area = QTextEdit()
        self._message_area.setReadOnly(True)
        self._message_area.setStyleSheet(
            "QTextEdit { background: #2B2B2B; color: #E0E0E0; border: none; "
            "font-size: 13px; padding: 8px; font-family: 'Consolas', 'Microsoft YaHei'; }"
        )
        self._message_area.setPlaceholderText("对话消息将显示在这里...")
        layout.addWidget(self._message_area, stretch=1)

        # --- 快捷输入区 ---
        self._quick_input_layout = QHBoxLayout()
        self._quick_input_layout.setSpacing(4)
        layout.addLayout(self._quick_input_layout)

        # --- / 命令补全列表 ---
        self._slash_list = QListWidget()
        self._slash_list.setMaximumHeight(150)
        self._slash_list.setStyleSheet(
            "QListWidget { background: #3C3C3C; color: #E0E0E0; border: 1px solid #555; "
            "font-size: 12px; } QListWidget::item:selected { background: #5285A6; }"
        )
        self._slash_list.hide()
        self._slash_list.itemClicked.connect(self._on_slash_item_clicked)
        layout.addWidget(self._slash_list)

        # --- 输入区域 ---
        input_layout = QHBoxLayout()

        self._input_box = QTextEdit()
        self._input_box.setMaximumHeight(80)
        self._input_box.setPlaceholderText("输入消息... (Enter 发送, Shift+Enter 换行)")
        self._input_box.setStyleSheet(
            "QTextEdit { background: #3C3C3C; color: #E0E0E0; border: 1px solid #555; "
            "border-radius: 4px; font-size: 13px; padding: 6px; "
            "font-family: 'Consolas', 'Microsoft YaHei'; }"
        )
        self._input_box.textChanged.connect(self._on_input_changed)
        self._input_box.installEventFilter(self)

        self._send_btn = QPushButton("发送")
        self._send_btn.setFixedSize(60, 36)
        self._send_btn.setStyleSheet(
            "QPushButton { background: #5285A6; color: white; border: none; "
            "border-radius: 4px; font-size: 12px; font-weight: bold; }"
            "QPushButton:hover { background: #6295B6; }"
            "QPushButton:pressed { background: #4275A6; }"
            "QPushButton:disabled { background: #555; color: #888; }"
        )
        self._send_btn.clicked.connect(self._on_send_clicked)

        input_layout.addWidget(self._input_box)
        input_layout.addWidget(self._send_btn, alignment=Qt.AlignBottom)
        layout.addLayout(input_layout)

        # 整体暗色主题
        self.setStyleSheet("ChatPanel { background: #333; }")

        # Slash 命令定义
        self._slash_commands = [
            ("/connect", "连接 OpenClaw Gateway"),
            ("/disconnect", "断开连接"),
            ("/status", "查看连接状态"),
            ("/clear", "清空聊天记录"),
            ("/cancel", "取消当前 AI 请求"),
            ("/diagnose", "运行连接诊断"),
            ("/new", "开始新对话"),
            ("/help", "显示帮助"),
        ]

    def _setup_bridge(self):
        """初始化 Bridge 连接"""
        try:
            from core.bridge_dcc import DCCBridgeManager
            self._bridge_manager = DCCBridgeManager.instance()

            if self._bridge_manager.signals:
                self._bridge_manager.signals.connection_changed.connect(self._on_connection_changed)
                self._bridge_manager.signals.ai_message.connect(self._on_ai_message)
                self._bridge_manager.signals.response_complete.connect(self._on_response_complete)

            if self._bridge_manager.is_connected():
                self._update_status(True)
        except Exception as e:
            logger.warning(f"Bridge setup failed: {e}")

    # --- 快捷输入 ---

    def _get_quick_input_path(self) -> str:
        try:
            from core.config import get_data_dir
            dcc = self._adapter.get_software_name() if self._adapter else "dcc"
            ver = self._adapter.get_software_version() if self._adapter else ""
            return os.path.join(get_data_dir(dcc, ver), "quick_inputs.json")
        except Exception:
            return ""

    def _load_quick_inputs(self):
        path = self._get_quick_input_path()
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._quick_inputs = json.load(f)
            except Exception:
                self._quick_inputs = []
        else:
            self._quick_inputs = [
                {"name": "选中信息", "content": "描述一下我当前选中的对象"},
                {"name": "场景概览", "content": "分析一下当前场景的结构"},
                {"name": "帮我优化", "content": "帮我优化选中对象的拓扑"},
            ]

        self._rebuild_quick_inputs()

    def _rebuild_quick_inputs(self):
        # 清空现有按钮
        while self._quick_input_layout.count():
            item = self._quick_input_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for qi in self._quick_inputs:
            btn = QPushButton(qi["name"])
            btn.setStyleSheet(
                "QPushButton { background: #4A4A4A; color: #CCC; border: 1px solid #555; "
                "border-radius: 3px; padding: 2px 8px; font-size: 11px; }"
                "QPushButton:hover { background: #5A5A5A; color: white; }"
            )
            btn.setFixedHeight(24)
            content = qi["content"]
            btn.clicked.connect(lambda _checked=False, c=content: self._fill_input(c))
            self._quick_input_layout.addWidget(btn)

        # 创建 Skill 按钮
        skill_btn = QPushButton("+ 创建技能")
        skill_btn.setStyleSheet(
            "QPushButton { background: #2D6B4D; color: #CCC; border: 1px solid #3A7D5C; "
            "border-radius: 3px; padding: 2px 8px; font-size: 11px; }"
            "QPushButton:hover { background: #3A7D5C; color: white; }"
        )
        skill_btn.setFixedHeight(24)
        skill_btn.setToolTip("用自然语言描述想要的技能，AI 会自动生成")
        skill_btn.clicked.connect(lambda _checked=False: self._on_create_skill())
        self._quick_input_layout.addWidget(skill_btn)

        # 自定义按钮
        edit_btn = QPushButton("...")
        edit_btn.setStyleSheet(
            "QPushButton { background: #3C3C3C; color: #999; border: 1px solid #555; "
            "border-radius: 3px; padding: 2px 6px; font-size: 11px; }"
            "QPushButton:hover { background: #4A4A4A; color: white; }"
        )
        edit_btn.setFixedHeight(24)
        edit_btn.setFixedWidth(28)
        edit_btn.setToolTip("编辑快捷输入")
        edit_btn.clicked.connect(lambda _checked=False: self._on_edit_quick_inputs())
        self._quick_input_layout.addWidget(edit_btn)

        self._quick_input_layout.addStretch()

    def _fill_input(self, text: str):
        self._input_box.setPlainText(text)
        self._input_box.setFocus()

    def _on_create_skill(self):
        """创建技能 — 填充提示并发送"""
        self._input_box.setPlainText(
            "帮我创建一个 ArtClaw 技能: "
        )
        self._input_box.setFocus()
        # 光标移到末尾
        cursor = self._input_box.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._input_box.setTextCursor(cursor)

    def _on_edit_quick_inputs(self):
        """编辑快捷输入配置"""
        from PySide2.QtWidgets import QDialog, QDialogButtonBox, QTextEdit as QTE, QVBoxLayout as QVL

        dlg = QDialog(self)
        dlg.setWindowTitle("编辑快捷输入")
        dlg.setMinimumSize(400, 300)
        dlg_layout = QVL(dlg)

        hint = QLabel(
            '每行一个，格式: 按钮名称|发送内容\n'
            '示例: 选中信息|描述一下我当前选中的对象'
        )
        hint.setStyleSheet("color: #AAA; font-size: 11px;")
        dlg_layout.addWidget(hint)

        editor = QTE()
        editor.setStyleSheet(
            "QTextEdit { background: #2B2B2B; color: #E0E0E0; border: 1px solid #555; "
            "font-size: 12px; padding: 6px; font-family: 'Consolas', 'Microsoft YaHei'; }"
        )
        # 填充当前配置
        lines = []
        for qi in self._quick_inputs:
            lines.append(f'{qi["name"]}|{qi["content"]}')
        editor.setPlainText("\n".join(lines))
        dlg_layout.addWidget(editor)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        dlg_layout.addWidget(buttons)

        if dlg.exec_() == QDialog.Accepted:
            new_inputs = []
            for line in editor.toPlainText().strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                if "|" in line:
                    name, content = line.split("|", 1)
                    new_inputs.append({"name": name.strip(), "content": content.strip()})
                else:
                    new_inputs.append({"name": line[:8], "content": line})

            self._quick_inputs = new_inputs
            self._rebuild_quick_inputs()

            # 保存到文件
            path = self._get_quick_input_path()
            if path:
                try:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(self._quick_inputs, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.warning(f"保存快捷输入失败: {e}")

    # --- 事件处理 ---

    def eventFilter(self, obj, event):
        if obj is self._input_box and hasattr(event, "key"):
            from PySide2.QtCore import QEvent
            if event.type() == QEvent.KeyPress:
                key = event.key()
                mods = event.modifiers()

                # Enter 发送（无 Shift）
                if key in (Qt.Key_Return, Qt.Key_Enter) and not (mods & Qt.ShiftModifier):
                    # 如果 slash 列表可见，选择当前项
                    if self._slash_list.isVisible() and self._slash_list.currentItem():
                        self._on_slash_item_clicked(self._slash_list.currentItem())
                        return True
                    self._on_send_clicked()
                    return True

                # Tab 补全 slash 命令
                if key == Qt.Key_Tab and self._slash_list.isVisible():
                    current = self._slash_list.currentItem()
                    if current:
                        self._on_slash_item_clicked(current)
                    return True

                # Escape 关闭补全
                if key == Qt.Key_Escape and self._slash_list.isVisible():
                    self._slash_list.hide()
                    return True

                # 上下键导航补全列表
                if self._slash_list.isVisible():
                    if key == Qt.Key_Up:
                        row = self._slash_list.currentRow() - 1
                        if row >= 0:
                            self._slash_list.setCurrentRow(row)
                        return True
                    elif key == Qt.Key_Down:
                        row = self._slash_list.currentRow() + 1
                        if row < self._slash_list.count():
                            self._slash_list.setCurrentRow(row)
                        return True

        return super().eventFilter(obj, event)

    def _on_input_changed(self):
        """输入框文本变化 — 更新 slash 命令补全"""
        text = self._input_box.toPlainText()
        if text.startswith("/") and "\n" not in text:
            self._update_slash_suggestions(text)
        else:
            self._slash_list.hide()

    def _update_slash_suggestions(self, text: str):
        self._slash_list.clear()
        prefix = text.lower()
        matches = [(cmd, desc) for cmd, desc in self._slash_commands if cmd.startswith(prefix)]

        if not matches:
            self._slash_list.hide()
            return

        for cmd, desc in matches:
            self._slash_list.addItem(f"{cmd}  —  {desc}")

        self._slash_list.setCurrentRow(0)
        self._slash_list.setFixedHeight(min(len(matches) * 24 + 4, 150))
        self._slash_list.show()

    def _on_slash_item_clicked(self, item):
        text = item.text().split("  —  ")[0].strip()
        self._input_box.setPlainText(text + " ")
        cursor = self._input_box.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._input_box.setTextCursor(cursor)
        self._slash_list.hide()

    @Slot()
    def _on_connect_clicked(self):
        if self._bridge_manager and self._bridge_manager.is_connected():
            self._bridge_manager.disconnect()
            self._add_system_message("已断开连接")
        else:
            self._add_system_message("正在连接...")
            if self._bridge_manager:
                self._bridge_manager.connect()

    @Slot()
    def _on_new_chat_clicked(self):
        self._message_area.clear()
        self._message_count = 0
        if self._bridge_manager:
            self._bridge_manager.reset_session()
        self._add_system_message("新对话已开始")

    @Slot()
    def _on_send_clicked(self):
        text = self._input_box.toPlainText().strip()
        if not text:
            return

        self._input_box.clear()
        self._slash_list.hide()

        if text.startswith("/"):
            self._handle_slash_command(text)
            return

        self._add_message("user", text)

        if self._bridge_manager:
            if not self._bridge_manager.is_connected():
                self._add_system_message("未连接，正在尝试连接...")
                self._bridge_manager.connect()

            self._is_streaming = True
            self._streaming_text = ""
            self._send_btn.setEnabled(False)
            self._send_btn.setText("等待...")
            self._add_message("assistant", "思考中...")
            self._bridge_manager.send_message(text)
        else:
            self._add_system_message("[错误] Bridge 未初始化")

    @Slot(bool, str)
    def _on_connection_changed(self, connected: bool, detail: str):
        self._update_status(connected)
        if connected:
            self._add_system_message("已连接到 OpenClaw Gateway")
        elif detail and detail not in ("shutdown", ""):
            self._add_system_message(f"连接断开: {detail}")

    @Slot(str, str)
    def _on_ai_message(self, state: str, text: str):
        """AI 流式消息（delta text 是累积全文，直接覆盖）"""
        if state == "delta" and self._is_streaming:
            self._streaming_text = text
            self._update_last_message("assistant", text)

    @Slot(str)
    def _on_response_complete(self, result: str):
        self._is_streaming = False
        self._send_btn.setEnabled(True)
        self._send_btn.setText("发送")
        self._update_last_message("assistant", result)

    # --- UI 辅助 ---

    def _update_status(self, connected: bool):
        if connected:
            self._status_dot.setStyleSheet("color: #4CAF50; font-size: 14px;")
            self._status_label.setText("已连接")
            self._status_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
            self._connect_btn.setText("断开")
        else:
            self._status_dot.setStyleSheet("color: #888; font-size: 14px;")
            self._status_label.setText("未连接")
            self._status_label.setStyleSheet("color: #888; font-size: 11px;")
            self._connect_btn.setText("连接")

    def _add_message(self, sender: str, content: str):
        """添加消息"""
        self._message_count += 1

        # 限制消息数
        if self._message_count > MAX_MESSAGES:
            cursor = self._message_area.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, 3)
            cursor.removeSelectedText()
            self._message_count -= 1

        color, label = self._get_sender_style(sender)
        html = self._format_message(label, color, content)

        cursor = self._message_area.textCursor()
        cursor.movePosition(QTextCursor.End)

        # 记录 AI 消息的起始位置（用于流式覆盖）
        if sender == "assistant":
            self._last_ai_cursor_pos = cursor.position()

        cursor.insertHtml(html)
        cursor.insertBlock()
        self._message_area.setTextCursor(cursor)
        self._message_area.ensureCursorVisible()

    def _update_last_message(self, sender: str, content: str):
        """更新最后一条 AI 消息（流式覆盖）"""
        if self._last_ai_cursor_pos < 0:
            # 没有记录位置，fallback 到追加
            self._add_message(sender, content)
            return

        cursor = self._message_area.textCursor()
        # 选中从上次 AI 消息起始位置到文档末尾
        cursor.setPosition(self._last_ai_cursor_pos)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()

        color, label = self._get_sender_style(sender)
        html = self._format_message(label, color, content)
        cursor.insertHtml(html)
        cursor.insertBlock()
        self._message_area.setTextCursor(cursor)
        self._message_area.ensureCursorVisible()

    def _get_sender_style(self, sender: str):
        if sender == "user":
            return "#7CB3F2", "你"
        elif sender == "assistant":
            return "#C0C0C0", "AI"
        else:
            return "#888", "系统"

    def _format_message(self, label: str, color: str, content: str) -> str:
        """格式化消息 HTML，支持基础 Markdown"""
        # 处理代码块
        formatted = _render_markdown(content)
        return (
            f'<div style="margin: 4px 0;">'
            f'<span style="color: {color}; font-weight: bold;">{label}:</span> '
            f'<span style="color: #E0E0E0;">{formatted}</span>'
            f'</div>'
        )

    def _add_system_message(self, content: str):
        self._add_message("system", content)

    def _handle_slash_command(self, command_text: str):
        parts = command_text.split(maxsplit=1)
        cmd = parts[0].lower()

        if cmd == "/connect":
            self._on_connect_clicked()
        elif cmd == "/disconnect":
            if self._bridge_manager:
                self._bridge_manager.disconnect()
                self._add_system_message("已断开连接")
        elif cmd == "/status":
            connected = self._bridge_manager.is_connected() if self._bridge_manager else False
            status = "已连接" if connected else "未连接"
            lines = [f"连接状态: {status}"]
            if self._adapter:
                lines.append(f"软件: {self._adapter.get_software_name()} {self._adapter.get_software_version()}")
            try:
                from core.mcp_server import get_mcp_server
                server = get_mcp_server()
                if server and server.is_running:
                    lines.append(f"MCP Server: {server.server_address} ({len(server._tools)} 工具)")
                else:
                    lines.append("MCP Server: 未运行")
            except Exception:
                pass
            self._add_system_message("\n".join(lines))
        elif cmd == "/clear":
            self._message_area.clear()
            self._message_count = 0
        elif cmd == "/cancel":
            if self._bridge_manager:
                self._bridge_manager.cancel()
                self._is_streaming = False
                self._send_btn.setEnabled(True)
                self._send_btn.setText("发送")
                self._add_system_message("已取消当前请求")
        elif cmd == "/new":
            self._on_new_chat_clicked()
        elif cmd == "/diagnose":
            self._add_system_message("运行环境健康检查...")
            try:
                from core.health_check import run_health_check
                report = run_health_check()
            except ImportError:
                if self._bridge_manager:
                    report = self._bridge_manager.run_diagnostics()
                else:
                    report = "健康检查模块未找到"
            self._add_system_message(report)
        elif cmd == "/help":
            lines = ["可用命令:"]
            for slash_cmd, desc in self._slash_commands:
                lines.append(f"  {slash_cmd:<14} {desc}")
            self._add_system_message("\n".join(lines))
        else:
            # 未知 / 命令 → 发送给 AI
            self._add_message("user", command_text)
            if self._bridge_manager:
                self._bridge_manager.send_message(command_text)

    def closeEvent(self, event):
        self.hide()
        event.ignore()


# --- Markdown 渲染 ---

def _render_markdown(text: str) -> str:
    """基础 Markdown → HTML 渲染"""
    lines = text.split("\n")
    result = []
    in_code_block = False
    code_lines = []

    for line in lines:
        if line.strip().startswith("```"):
            if in_code_block:
                # 结束代码块
                code_html = _escape_html("\n".join(code_lines))
                result.append(
                    f'<div style="background: #1E1E1E; padding: 6px 8px; '
                    f'border-radius: 4px; margin: 4px 0; font-family: Consolas, monospace; '
                    f'font-size: 12px; white-space: pre;">{code_html}</div>'
                )
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
        elif in_code_block:
            code_lines.append(line)
        else:
            formatted = _escape_html(line)
            # 行内代码
            import re
            formatted = re.sub(
                r'`([^`]+)`',
                r'<span style="background: #1E1E1E; padding: 1px 4px; border-radius: 2px; '
                r'font-family: Consolas, monospace; font-size: 12px;">\1</span>',
                formatted
            )
            # 加粗
            formatted = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', formatted)
            result.append(formatted)

    # 未关闭的代码块
    if in_code_block and code_lines:
        code_html = _escape_html("\n".join(code_lines))
        result.append(
            f'<div style="background: #1E1E1E; padding: 6px 8px; '
            f'border-radius: 4px; font-family: Consolas, monospace; '
            f'font-size: 12px; white-space: pre;">{code_html}</div>'
        )

    return "<br>".join(result)


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# --- 公开接口 ---

def show_chat_panel(parent=None, adapter=None) -> Optional[ChatPanel]:
    if not HAS_QT:
        logger.error("PySide2 not available")
        return None

    global _panel_instance
    if _panel_instance is not None:
        _panel_instance.show()
        _panel_instance.raise_()
        _panel_instance.activateWindow()
        return _panel_instance

    _panel_instance = ChatPanel(parent=parent, adapter=adapter)
    _panel_instance.show()
    return _panel_instance
