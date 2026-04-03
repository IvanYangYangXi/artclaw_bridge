"""
chat_input.py - ArtClaw DCC Chat Input Widget
==============================================

多行输入框 + Slash 命令补全弹出层。

功能：
  - QTextEdit 输入框（最高 80px）
  - Enter 发送（默认），Shift+Enter 换行
  - 可切换 Ctrl+Enter 发送模式
  - Slash 命令补全：/connect /disconnect /status /clear /cancel
                    /diagnose /new /help /plan /compact /review /undo
  - Tab 自动补全，Esc 关闭弹窗，↑↓ 导航
  - Ctrl+V 优先尝试剪贴板图片粘贴，再回退为文本
"""

from __future__ import annotations

import logging
from typing import Optional, List, Tuple

try:
    from PySide2.QtWidgets import (
        QWidget, QVBoxLayout, QTextEdit,
        QListWidget, QListWidgetItem, QAbstractItemView,
        QSizePolicy,
    )
    from PySide2.QtCore import Qt, Signal, QPoint
    from PySide2.QtGui import QKeyEvent, QTextCursor, QImage
    HAS_QT = True
except ImportError:
    HAS_QT = False

logger = logging.getLogger("artclaw.ui.input")

# ── Slash command registry ────────────────────────────────────────────────────
# (command, description, is_local)
# local commands are handled by the panel, not forwarded to AI
SLASH_COMMANDS: List[Tuple[str, str, bool]] = [
    ("/connect",    "连接 OpenClaw Gateway",  True),
    ("/disconnect", "断开 Gateway 连接",       True),
    ("/status",     "查看当前连接状态",          True),
    ("/clear",      "清空聊天记录",             True),
    ("/cancel",     "取消当前 AI 请求",         True),
    ("/resume",     "恢复接收中断的 AI 回复",   True),
    ("/diagnose",   "运行连接诊断",             True),
    ("/help",       "显示帮助信息",             True),
    ("/plan",       "显示执行计划（本地）",       True),
    ("/new",        "开始新对话（发给 AI）",      False),
    ("/compact",    "压缩上下文（发给 AI）",      False),
    ("/review",     "Review 代码（发给 AI）",    False),
    ("/undo",       "撤销上次操作（发给 AI）",    False),
]

LOCAL_COMMANDS = {cmd for cmd, _, is_local in SLASH_COMMANDS if is_local}
_MAX_POPUP_HEIGHT = 200
_INPUT_MAX_HEIGHT = 80


class _InputTextEdit(QTextEdit):
    """内部 QTextEdit，覆写 keyPressEvent 以拦截 Enter / Tab / Ctrl+V 等。"""

    # 由父 Widget 注入
    _owner: "ChatInputWidget"

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        owner = self._owner

        key = event.key()
        mods = event.modifiers()

        # ── Ctrl+V: image paste first ─────────────────────────────────────
        if key == Qt.Key_V and (mods & Qt.ControlModifier):
            if owner._try_image_paste():
                return
            # fall through to default text paste

        # ── Navigation inside slash popup ────────────────────────────────
        if owner._popup_visible():
            if key == Qt.Key_Escape:
                owner._hide_popup()
                return
            if key == Qt.Key_Tab:
                owner._autocomplete()
                return
            if key == Qt.Key_Up:
                owner._popup_move(-1)
                return
            if key == Qt.Key_Down:
                owner._popup_move(1)
                return
            if key in (Qt.Key_Return, Qt.Key_Enter) and not (mods & Qt.ShiftModifier):
                owner._autocomplete()
                return

        # ── Send / Newline ────────────────────────────────────────────────
        if key in (Qt.Key_Return, Qt.Key_Enter):
            enter_sends = owner._enter_to_send
            ctrl_mode = not enter_sends  # Ctrl+Enter mode when enter_to_send=False

            if enter_sends:
                if mods & Qt.ShiftModifier:
                    # Shift+Enter → newline always
                    super().keyPressEvent(event)
                else:
                    owner._submit()
            else:
                # Ctrl+Enter mode
                if mods & Qt.ControlModifier:
                    owner._submit()
                else:
                    super().keyPressEvent(event)
            return

        super().keyPressEvent(event)


class ChatInputWidget(QWidget):
    """聊天输入区域

    包含：多行 QTextEdit + Slash 命令补全弹出层

    Signals
    -------
    message_submitted(text)        : 普通消息（已去掉首尾空白）
    slash_command(cmd, args)       : 本地 slash 命令
    paste_attempted()              : 剪贴板图片粘贴尝试通知
    """

    message_submitted = Signal(str)
    slash_command = Signal(str, str)
    paste_attempted = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._enter_to_send = True

        self._build_ui()
        self._apply_styles()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Slash popup (above input, hidden by default)
        self._popup = QListWidget()
        self._popup.setMaximumHeight(_MAX_POPUP_HEIGHT)
        self._popup.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._popup.setSelectionMode(QAbstractItemView.SingleSelection)
        self._popup.setFocusPolicy(Qt.NoFocus)
        self._popup.itemClicked.connect(self._on_popup_item_clicked)
        self._popup.hide()
        layout.addWidget(self._popup)

        # Text input
        self._editor = _InputTextEdit()
        self._editor._owner = self
        self._editor.setMaximumHeight(_INPUT_MAX_HEIGHT)
        self._editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._editor)

    def _apply_styles(self) -> None:
        try:
            from artclaw_ui.theme import COLORS
            bg_in = COLORS.get("bg_input", "#3C3C3C")
            bg2 = COLORS.get("bg_secondary", "#4A4A4A")
            border = COLORS.get("border", "#555555")
            accent = COLORS.get("accent", "#5285A6")
            text = COLORS.get("text", "#E0E0E0")
        except Exception:
            bg_in, bg2, border, accent, text = "#3C3C3C", "#4A4A4A", "#555555", "#5285A6", "#E0E0E0"

        self._editor.setStyleSheet(f"""
            QTextEdit {{
                background: {bg_in};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                font-size: 13px;
                padding: 6px;
                font-family: 'Consolas', 'Microsoft YaHei';
            }}
            QTextEdit:focus {{
                border-color: {accent};
            }}
        """)

        self._popup.setStyleSheet(f"""
            QListWidget {{
                background: {bg2};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                font-size: 12px;
                padding: 2px;
            }}
            QListWidget::item {{
                padding: 3px 6px;
            }}
            QListWidget::item:selected {{
                background: {accent};
                color: white;
            }}
            QListWidget::item:hover {{
                background: rgba(255,255,255,0.08);
            }}
        """)

    # ── Popup management ──────────────────────────────────────────────────────

    def _popup_visible(self) -> bool:
        return self._popup.isVisible()

    def _show_popup(self, matches: List[Tuple[str, str, bool]]) -> None:
        self._popup.clear()
        for cmd, desc, _ in matches:
            item = QListWidgetItem(f"{cmd}  —  {desc}")
            item.setData(Qt.UserRole, cmd)
            self._popup.addItem(item)
        if self._popup.count() > 0:
            self._popup.setCurrentRow(0)
            self._popup.show()
        else:
            self._popup.hide()

    def _hide_popup(self) -> None:
        self._popup.hide()
        self._popup.clear()

    def _popup_move(self, delta: int) -> None:
        count = self._popup.count()
        if count == 0:
            return
        row = self._popup.currentRow()
        new_row = max(0, min(count - 1, row + delta))
        self._popup.setCurrentRow(new_row)

    def _autocomplete(self) -> None:
        item = self._popup.currentItem()
        if item is None:
            return
        cmd: str = item.data(Qt.UserRole)
        cursor = self._editor.textCursor()
        # replace the current line's slash-prefix with the full command
        cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.MoveAnchor)
        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
        cursor.insertText(cmd + " ")
        self._editor.setTextCursor(cursor)
        self._hide_popup()

    # ── Text change → popup filter ────────────────────────────────────────────

    def _on_text_changed(self) -> None:
        text = self._editor.toPlainText()
        # Only check the last line (multi-line aware)
        lines = text.split("\n")
        last_line = lines[-1] if lines else ""

        if last_line.startswith("/"):
            prefix = last_line.split()[0] if " " in last_line else last_line
            matches = [
                (cmd, desc, loc)
                for cmd, desc, loc in SLASH_COMMANDS
                if cmd.startswith(prefix)
            ]
            if matches:
                self._show_popup(matches)
                return
        self._hide_popup()

    # ── Item click in popup ───────────────────────────────────────────────────

    def _on_popup_item_clicked(self, item: "QListWidgetItem") -> None:
        cmd: str = item.data(Qt.UserRole)
        cursor = self._editor.textCursor()
        cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.MoveAnchor)
        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
        cursor.insertText(cmd + " ")
        self._editor.setTextCursor(cursor)
        self._hide_popup()
        self._editor.setFocus()

    # ── Submit ────────────────────────────────────────────────────────────────

    def _submit(self) -> None:
        text = self._editor.toPlainText().strip()
        if not text:
            return
        self._hide_popup()

        if text.startswith("/"):
            parts = text.split(None, 1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            self._editor.clear()
            if cmd in LOCAL_COMMANDS:
                self.slash_command.emit(cmd, args)
            else:
                # AI commands – submit as regular message so the panel
                # can decide whether to forward them
                self.slash_command.emit(cmd, args)
        else:
            self._editor.clear()
            self.message_submitted.emit(text)

    # ── Clipboard image paste ─────────────────────────────────────────────────

    def _try_image_paste(self) -> bool:
        """尝试从剪贴板粘贴图片。返回 True 表示已处理（不再走文字粘贴）"""
        try:
            from PySide2.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            mime = clipboard.mimeData()
            if mime and mime.hasImage():
                self.paste_attempted.emit()
                return True
        except Exception as exc:
            logger.debug("image paste check: %s", exc)
        return False

    # ── Public API ────────────────────────────────────────────────────────────

    def clear(self) -> None:
        """清空输入框"""
        self._editor.clear()
        self._hide_popup()

    def set_text(self, text: str) -> None:
        """设置输入框内容"""
        self._editor.setPlainText(text)
        cursor = self._editor.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._editor.setTextCursor(cursor)

    def get_text(self) -> str:
        """获取当前输入内容（原始，含换行）"""
        return self._editor.toPlainText()

    def set_placeholder(self, text: str) -> None:
        """设置 placeholder 文本"""
        self._editor.setPlaceholderText(text)

    def set_enter_to_send(self, enabled: bool) -> None:
        """True=Enter发送(默认); False=Ctrl+Enter发送"""
        self._enter_to_send = enabled
        if enabled:
            self._editor.setPlaceholderText("输入消息... (Enter 发送，Shift+Enter 换行)")
        else:
            self._editor.setPlaceholderText("输入消息... (Ctrl+Enter 发送，Enter 换行)")
