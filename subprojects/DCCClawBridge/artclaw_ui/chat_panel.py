"""
chat_panel.py - ArtClaw Chat Panel (Qt)
========================================

通用聊天面板，Maya / Max 共享。
通过 DCC adapter 适配各软件的主窗口和线程调度。
"""

from __future__ import annotations

import logging
from typing import Optional

try:
    from PySide2.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
        QPushButton, QLabel, QScrollArea, QFrame, QSplitter,
        QApplication,
    )
    from PySide2.QtCore import Qt, Slot, QTimer
    from PySide2.QtGui import QFont, QColor, QTextCursor
    HAS_QT = True
except ImportError:
    HAS_QT = False

logger = logging.getLogger("artclaw.ui")

# 全局面板引用（防止重复创建）
_panel_instance: Optional["ChatPanel"] = None


class ChatPanel(QWidget):
    """ArtClaw 聊天面板"""

    def __init__(self, parent=None, adapter=None):
        super().__init__(parent)
        self._adapter = adapter
        self._bridge_manager = None

        self.setWindowTitle("ArtClaw Chat")
        self.setMinimumSize(400, 500)
        self.resize(450, 650)
        self.setWindowFlags(Qt.Window)

        self._setup_ui()
        self._setup_bridge()

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

        status_layout.addWidget(self._status_dot)
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()
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
            "font-size: 13px; padding: 8px; }"
        )
        self._message_area.setPlaceholderText("对话消息将显示在这里...")
        layout.addWidget(self._message_area, stretch=1)

        # --- 输入区域 ---
        input_layout = QHBoxLayout()

        self._input_box = QTextEdit()
        self._input_box.setMaximumHeight(80)
        self._input_box.setPlaceholderText("输入消息... (Enter 发送, Shift+Enter 换行)")
        self._input_box.setStyleSheet(
            "QTextEdit { background: #3C3C3C; color: #E0E0E0; border: 1px solid #555; "
            "border-radius: 4px; font-size: 13px; padding: 6px; }"
        )
        self._input_box.installEventFilter(self)

        self._send_btn = QPushButton("发送")
        self._send_btn.setFixedSize(60, 36)
        self._send_btn.setStyleSheet(
            "QPushButton { background: #5285A6; color: white; border: none; "
            "border-radius: 4px; font-size: 12px; }"
            "QPushButton:hover { background: #6295B6; }"
            "QPushButton:pressed { background: #4275A6; }"
        )
        self._send_btn.clicked.connect(self._on_send_clicked)

        input_layout.addWidget(self._input_box)
        input_layout.addWidget(self._send_btn, alignment=Qt.AlignBottom)
        layout.addLayout(input_layout)

        # 整体暗色主题
        self.setStyleSheet(
            "ChatPanel { background: #333; }"
        )

    def _setup_bridge(self):
        """初始化 Bridge 连接"""
        try:
            from core.bridge_dcc import DCCBridgeManager
            self._bridge_manager = DCCBridgeManager.instance()

            if self._bridge_manager.signals:
                self._bridge_manager.signals.connection_changed.connect(
                    self._on_connection_changed
                )
                self._bridge_manager.signals.ai_message.connect(
                    self._on_ai_message
                )
                self._bridge_manager.signals.response_complete.connect(
                    self._on_response_complete
                )

            # 更新状态
            if self._bridge_manager.is_connected():
                self._update_status(True)

        except Exception as e:
            logger.warning(f"Bridge setup failed: {e}")

    # --- 事件处理 ---

    def eventFilter(self, obj, event):
        """拦截输入框的 Enter 键"""
        if obj is self._input_box and hasattr(event, "key"):
            from PySide2.QtCore import QEvent
            if event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Return and not event.modifiers() & Qt.ShiftModifier:
                    self._on_send_clicked()
                    return True
        return super().eventFilter(obj, event)

    @Slot()
    def _on_connect_clicked(self):
        """连接/断开按钮"""
        if self._bridge_manager and self._bridge_manager.is_connected():
            self._bridge_manager.disconnect()
            self._add_system_message("已断开连接")
        else:
            self._add_system_message("正在连接...")
            if self._bridge_manager:
                self._bridge_manager.connect()

    @Slot()
    def _on_send_clicked(self):
        """发送消息"""
        text = self._input_box.toPlainText().strip()
        if not text:
            return

        self._input_box.clear()

        # 检查本地命令
        if text.startswith("/"):
            self._handle_slash_command(text)
            return

        # 显示用户消息
        self._add_message("user", text)

        # 发送给 AI
        if self._bridge_manager:
            if not self._bridge_manager.is_connected():
                self._add_system_message("未连接到 OpenClaw，正在尝试连接...")
                self._bridge_manager.connect()

            self._add_system_message("思考中...")
            self._bridge_manager.send_message(text)
        else:
            self._add_system_message("[错误] Bridge 未初始化")

    @Slot(bool, str)
    def _on_connection_changed(self, connected: bool, detail: str):
        """连接状态变更"""
        self._update_status(connected)
        if connected:
            self._add_system_message("已连接到 OpenClaw Gateway")
        else:
            if detail and detail != "shutdown":
                self._add_system_message(f"连接断开: {detail}")

    @Slot(str, str)
    def _on_ai_message(self, state: str, text: str):
        """AI 流式消息"""
        if state == "delta":
            self._update_streaming_message(text)

    @Slot(str)
    def _on_response_complete(self, result: str):
        """AI 响应完成"""
        # 移除 "思考中..." 并显示最终回复
        self._finalize_streaming_message(result)

    # --- UI 辅助方法 ---

    def _update_status(self, connected: bool):
        """更新状态指示"""
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
        """添加消息到消息区域"""
        cursor = self._message_area.textCursor()
        cursor.movePosition(QTextCursor.End)

        if sender == "user":
            color = "#7CB3F2"
            label = "你"
        elif sender == "assistant":
            color = "#C0C0C0"
            label = "AI"
        else:
            color = "#888"
            label = "系统"

        html = (
            f'<div style="margin: 4px 0;">'
            f'<span style="color: {color}; font-weight: bold;">{label}:</span> '
            f'<span style="color: #E0E0E0;">{_escape_html(content)}</span>'
            f'</div>'
        )

        cursor.insertHtml(html)
        cursor.insertBlock()
        self._message_area.setTextCursor(cursor)
        self._message_area.ensureCursorVisible()

    def _add_system_message(self, content: str):
        """添加系统消息"""
        self._add_message("system", content)

    def _update_streaming_message(self, text: str):
        """更新流式消息（累积文本）"""
        # 简化实现：直接替换最后一条消息
        # TODO: 更精细的流式更新
        pass

    def _finalize_streaming_message(self, text: str):
        """完成流式消息，显示最终结果"""
        self._add_message("assistant", text)

    def _handle_slash_command(self, command_text: str):
        """处理 / 命令"""
        parts = command_text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "/connect":
            self._on_connect_clicked()
        elif cmd == "/disconnect":
            if self._bridge_manager:
                self._bridge_manager.disconnect()
                self._add_system_message("已断开连接")
        elif cmd == "/status":
            connected = self._bridge_manager.is_connected() if self._bridge_manager else False
            status = "已连接" if connected else "未连接"
            self._add_system_message(f"连接状态: {status}")
            if self._adapter:
                info = f"软件: {self._adapter.get_software_name()} {self._adapter.get_software_version()}"
                self._add_system_message(info)
        elif cmd == "/clear":
            self._message_area.clear()
        elif cmd == "/cancel":
            if self._bridge_manager:
                self._bridge_manager.cancel()
                self._add_system_message("已取消当前请求")
        elif cmd == "/diagnose":
            self._add_system_message("运行连接诊断...")
            if self._bridge_manager:
                report = self._bridge_manager.run_diagnostics()
                self._add_system_message(report)
        elif cmd == "/help":
            help_text = (
                "可用命令:\n"
                "  /connect    - 连接 OpenClaw\n"
                "  /disconnect - 断开连接\n"
                "  /status     - 查看状态\n"
                "  /clear      - 清空聊天\n"
                "  /cancel     - 取消等待\n"
                "  /diagnose   - 连接诊断\n"
                "  /help       - 显示帮助"
            )
            self._add_system_message(help_text)
        else:
            # 未知的 / 命令 → 发送给 AI
            self._add_message("user", command_text)
            if self._bridge_manager:
                self._bridge_manager.send_message(command_text)

    def closeEvent(self, event):
        """窗口关闭时隐藏而不是销毁"""
        self.hide()
        event.ignore()


def _escape_html(text: str) -> str:
    """转义 HTML 特殊字符"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )


def show_chat_panel(parent=None, adapter=None) -> Optional[ChatPanel]:
    """
    显示 Chat Panel（单例模式）。

    Args:
        parent: 父窗口（DCC 主窗口）
        adapter: DCC adapter 实例
    """
    if not HAS_QT:
        logger.error("PySide2 not available — cannot show Chat Panel")
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
