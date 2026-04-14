"""
chat_toolbar.py - ArtClaw DCC Chat Toolbar
===========================================

消息列表下方工具栏。
布局: [新对话] [管理] | spacer | [📎附件] [⏹停止] [发送/等待...]

- 停止按钮：仅在等待 AI 响应时启用，红色调
- 发送按钮：等待时显示"等待..."并变色；就绪时蓝色
- 管理按钮：打开 Skill/MCP 管理窗口
- 附件按钮：打开文件选择器
"""

from __future__ import annotations

import logging
from typing import Optional

from artclaw_ui.qt_compat import *  # noqa: F401,F403
HAS_QT = True

from artclaw_ui.i18n import T

logger = logging.getLogger("artclaw.ui.toolbar")

# ── Style constants ──────────────────────────────────────────────────────────
_BTN_BASE = (
    "QPushButton {{ background: {bg}; color: {fg}; border: 1px solid {border}; "
    "border-radius: 4px; font-size: 12px; padding: 4px 10px; min-width: 0px; }}"
    "QPushButton:hover {{ background: {hover}; }}"
    "QPushButton:pressed {{ background: {pressed}; }}"
    "QPushButton:disabled {{ background: #444; color: #666; border-color: #444; }}"
)


def _btn_style(bg: str, fg: str, border: str, hover: str, pressed: str) -> str:
    return _BTN_BASE.format(bg=bg, fg=fg, border=border, hover=hover, pressed=pressed)


class ToolbarWidget(QWidget):
    """聊天工具栏

    Signals
    -------
    new_chat_clicked  : 点击"新对话"
    manage_clicked    : 点击"管理"
    attach_clicked    : 点击"附件"（已选文件路径作为参数）
    stop_clicked      : 点击"停止"
    send_clicked      : 点击"发送"
    """

    # ── Signals ──────────────────────────────────────────────────────────────
    new_chat_clicked = Signal()
    manage_clicked = Signal()
    tool_manager_clicked = Signal()
    attach_clicked = Signal(str)    # file path
    stop_clicked = Signal()
    send_clicked = Signal()
    resume_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._is_waiting = False
        self._send_enabled = True

        self._build_ui()
        self._apply_styles()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        def _auto_width(btn: QPushButton, min_w: int = 50, pad: int = 28):
            """根据文本宽度自适应设置 fixedWidth（pad 包含 QSS padding+border）"""
            try:
                fm = btn.fontMetrics()
                tw = fm.horizontalAdvance(btn.text()) + pad
            except Exception:
                tw = min_w
            btn.setFixedWidth(max(tw, min_w))

        # Left group
        self._new_btn = QPushButton(T("new_chat_btn"))
        self._new_btn.setFixedHeight(28)
        _auto_width(self._new_btn, 60)
        self._new_btn.clicked.connect(self.new_chat_clicked)

        self._manage_btn = QPushButton(T("manage_btn"))
        self._manage_btn.setFixedHeight(28)
        _auto_width(self._manage_btn, 50)
        self._manage_btn.clicked.connect(self.manage_clicked)

        self._tool_manager_btn = QPushButton(T("tool_manager_btn"))
        self._tool_manager_btn.setFixedHeight(28)
        _auto_width(self._tool_manager_btn, 50)
        self._tool_manager_btn.clicked.connect(self.tool_manager_clicked)

        layout.addWidget(self._new_btn)
        layout.addWidget(self._manage_btn)
        layout.addWidget(self._tool_manager_btn)

        # 附件按钮 — 靠左，紧跟管理按钮
        self._attach_btn = QPushButton(T("attach_btn"))
        self._attach_btn.setFixedHeight(28)
        _auto_width(self._attach_btn, 50)
        self._attach_btn.clicked.connect(self._on_attach_clicked)
        layout.addWidget(self._attach_btn)

        layout.addStretch()

        # Right group
        self._stop_btn = QPushButton("⏹ " + T("stop"))
        self._stop_btn.setFixedHeight(28)
        _auto_width(self._stop_btn, 55)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self.stop_clicked)

        self._resume_btn = QPushButton(T("resume_btn"))
        self._resume_btn.setFixedHeight(28)
        _auto_width(self._resume_btn, 50)
        self._resume_btn.setEnabled(True)
        self._resume_btn.clicked.connect(self.resume_clicked)

        self._send_btn = QPushButton(T("send"))
        self._send_btn.setFixedSize(70, 28)
        self._send_btn.clicked.connect(self.send_clicked)

        layout.addWidget(self._stop_btn)
        layout.addWidget(self._resume_btn)
        layout.addWidget(self._send_btn)

    def _apply_styles(self) -> None:
        try:
            from artclaw_ui.theme import COLORS
            bg2 = COLORS.get("bg_secondary", "#4A4A4A")
            border = COLORS.get("border", "#555555")
            accent = COLORS.get("accent", "#5285A6")
            accent_h = COLORS.get("accent_hover", "#6295B6")
            accent_p = COLORS.get("accent_pressed", "#4275A6")
        except Exception:
            bg2, border = "#4A4A4A", "#555555"
            accent, accent_h, accent_p = "#5285A6", "#6295B6", "#4275A6"

        self.setStyleSheet(f"ToolbarWidget {{ background: {bg2}; border-top: 1px solid {border}; }}")

        # Default button style (new / manage / attach)
        default_style = _btn_style(
            bg="#3C3C3C", fg="#C0C0C0", border=border,
            hover="#505050", pressed="#2A2A2A"
        )
        for btn in (self._new_btn, self._manage_btn, self._attach_btn):
            btn.setStyleSheet(default_style)
        self._tool_manager_btn.setStyleSheet(default_style)

        # Stop button style (red-ish, disabled by default)
        self._stop_style = _btn_style(
            bg="#5C2020", fg="#FF8080", border="#7C3030",
            hover="#7C3030", pressed="#4C1010"
        )
        self._stop_style_disabled = (
            "QPushButton { background: #3C3C3C; color: #666; border: 1px solid #444; "
            "border-radius: 4px; font-size: 12px; padding: 4px 10px; }"
        )
        self._stop_btn.setStyleSheet(self._stop_style_disabled)

        # Resume button style (green)
        self._resume_style = _btn_style(
            bg="#2C5C2C", fg="#80FF80", border="#3C7C3C",
            hover="#3C7C3C", pressed="#1C4C1C"
        )
        self._resume_btn.setStyleSheet(self._resume_style)

        # Send button styles
        self._send_ready_style = _btn_style(
            bg=accent, fg="white", border=accent_p,
            hover=accent_h, pressed=accent_p
        )
        self._send_waiting_style = _btn_style(
            bg="#3C3C3C", fg="#888888", border="#555",
            hover="#3C3C3C", pressed="#3C3C3C"
        )
        self._send_btn.setStyleSheet(self._send_ready_style)

    # ── Private slots ─────────────────────────────────────────────────────────

    def _on_attach_clicked(self) -> None:
        try:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "选择附件",
                "",
                "所有文件 (*.*)"
            )
            if path:
                self.attach_clicked.emit(path)
        except Exception as exc:
            logger.warning("attach file picker error: %s", exc)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_waiting(self, is_waiting: bool) -> None:
        """切换等待状态（发送/停止/恢复按钮联动）"""
        self._is_waiting = is_waiting
        if is_waiting:
            self._send_btn.setText(T("waiting_btn"))
            self._send_btn.setEnabled(False)
            self._send_btn.setStyleSheet(self._send_waiting_style)
            self._stop_btn.setEnabled(True)
            self._stop_btn.setStyleSheet(self._stop_style)
            self._resume_btn.setEnabled(False)
        else:
            self._send_btn.setText(T("send"))
            self._send_btn.setEnabled(self._send_enabled)
            self._send_btn.setStyleSheet(self._send_ready_style)
            self._stop_btn.setEnabled(False)
            self._stop_btn.setStyleSheet(self._stop_style_disabled)
            self._resume_btn.setEnabled(True)

    def set_send_enabled(self, enabled: bool) -> None:
        """控制发送按钮可用性（等待时此方法不影响 waiting 状态）"""
        self._send_enabled = enabled
        if not self._is_waiting:
            self._send_btn.setEnabled(enabled)

    def refresh_language(self) -> None:
        """语言切换后刷新所有按钮文本"""
        self._new_btn.setText(T("new_chat_btn"))
        self._manage_btn.setText(T("manage_btn"))
        self._tool_manager_btn.setText(T("tool_manager_btn"))
        self._attach_btn.setText(T("attach_btn"))
        self._stop_btn.setText("⏹ " + T("stop"))
        self._resume_btn.setText(T("resume_btn"))
        if self._is_waiting:
            self._send_btn.setText(T("waiting_btn"))
        else:
            self._send_btn.setText(T("send"))
