"""
chat_status_bar.py - ArtClaw DCC Chat Status Bar
==================================================

顶部状态栏：连接状态、Agent 标签、会话下拉、上下文用量、设置入口。
Row 1: 状态按钮 | Agent按钮 | 会话按钮 | spacer | 上下文用量 | 设置按钮
Row 2: 状态摘要文本（连接状态 + MCP + 服务器地址）
Row 3 (collapsible): 连接/断开/诊断/查看日志 按钮
"""

from __future__ import annotations

import logging
from typing import Optional

from artclaw_ui.qt_compat import *  # noqa: F401,F403
HAS_QT = True

logger = logging.getLogger("artclaw.ui.status_bar")

# 上下文用量颜色阈值
CTX_GREEN_MAX = 0.60
CTX_YELLOW_MAX = 0.80


class StatusBarWidget(QWidget):
    """聊天面板顶部状态栏

    Rows
    ----
    Row 1 : [●状态] [🤖 Agent名] [💬 会话▼] <spacer> [上下文: X%] [⚙设置]
    Row 2 : 状态摘要文本
    Row 3 : [连接] [断开] [诊断] [查看日志]  ← collapsible by clicking Row1 status btn
    """

    # ── Signals ──────────────────────────────────────────────────────────────
    connect_clicked = Signal()
    disconnect_clicked = Signal()
    diagnose_clicked = Signal()
    settings_clicked = Signal()
    session_menu_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        from artclaw_ui.i18n import T
        self._T = T
        self._connected = False
        self._mcp_ready = False
        self._row3_visible = False
        self._ctx_used = 0
        self._ctx_total = 0

        self._build_ui()
        self._apply_styles()
        self.update_connection(False)

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(2)

        # Row 1
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        _compact_btn_ss = (
            "QPushButton { color: #C0C0C0; background: transparent; border: none;"
            " font-size: 11px; padding: 0px 4px; min-width: 0; min-height: 0; }"
            "QPushButton:hover { color: #FFFFFF; background: rgba(255,255,255,0.08); border-radius: 3px; }"
        )

        self._status_btn = QPushButton(f"● {self._T('disconnected')}")
        self._status_btn.setFlat(True)
        self._status_btn.setFixedHeight(22)
        self._status_btn.setCursor(Qt.PointingHandCursor)
        self._status_btn.setStyleSheet(_compact_btn_ss)
        self._status_btn.clicked.connect(self._toggle_row3)

        self._agent_btn = QPushButton("🤖 Agent")
        self._agent_btn.setFlat(True)
        self._agent_btn.setFixedHeight(22)
        self._agent_btn.setCursor(Qt.PointingHandCursor)
        self._agent_btn.setStyleSheet(_compact_btn_ss)
        self._agent_btn.clicked.connect(self.settings_clicked)

        self._session_btn = QPushButton("💬 ▼")
        self._session_btn.setFlat(True)
        self._session_btn.setFixedHeight(22)
        self._session_btn.setCursor(Qt.PointingHandCursor)
        self._session_btn.setStyleSheet(_compact_btn_ss)
        self._session_btn.clicked.connect(self.session_menu_clicked)

        self._ctx_label = QLabel(f"{self._T('context_usage')}: --")
        self._ctx_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._settings_btn = QPushButton(self._T("settings_btn"))
        self._settings_btn.setFlat(True)
        self._settings_btn.setFixedHeight(22)
        self._settings_btn.setCursor(Qt.PointingHandCursor)
        self._settings_btn.clicked.connect(self.settings_clicked)

        row1.addWidget(self._status_btn)
        row1.addWidget(self._agent_btn)
        row1.addWidget(self._session_btn)
        row1.addStretch()
        row1.addWidget(self._ctx_label)
        row1.addWidget(self._settings_btn)
        root.addLayout(row1)

        # Row 2 – summary text
        self._summary_label = QLabel(self._T("disconnected"))
        self._summary_label.setWordWrap(False)
        root.addWidget(self._summary_label)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("statusSep")
        root.addWidget(sep)

        # Row 3 – action buttons (collapsible)
        self._row3_widget = QWidget()
        row3 = QHBoxLayout(self._row3_widget)
        row3.setContentsMargins(0, 2, 0, 2)
        row3.setSpacing(4)

        self._conn_btn = QPushButton(self._T("connect"))
        self._conn_btn.setFixedHeight(22)
        self._conn_btn.setMaximumWidth(60)
        self._conn_btn.clicked.connect(self.connect_clicked)

        self._disconn_btn = QPushButton(self._T("disconnect"))
        self._disconn_btn.setFixedHeight(22)
        self._disconn_btn.setMaximumWidth(60)
        self._disconn_btn.clicked.connect(self.disconnect_clicked)

        self._diag_btn = QPushButton(self._T("diagnose"))
        self._diag_btn.setFixedHeight(22)
        self._diag_btn.setMaximumWidth(60)
        self._diag_btn.clicked.connect(self.diagnose_clicked)

        self._logs_btn = QPushButton(self._T("view_logs"))
        self._logs_btn.setFixedHeight(22)
        self._logs_btn.setMaximumWidth(72)
        self._logs_btn.clicked.connect(self._open_logs)

        row3.addWidget(self._conn_btn)
        row3.addWidget(self._disconn_btn)
        row3.addWidget(self._diag_btn)
        row3.addWidget(self._logs_btn)
        row3.addStretch()

        self._row3_widget.setVisible(False)
        root.addWidget(self._row3_widget)

    def _apply_styles(self) -> None:
        try:
            from artclaw_ui.theme import COLORS
            bg = COLORS.get("bg_secondary", "#4A4A4A")
            border = COLORS.get("border", "#555555")
            text_dim = COLORS.get("text_dim", "#888888")
            accent = COLORS.get("accent", "#5285A6")
        except Exception:
            bg, border, text_dim, accent = "#4A4A4A", "#555555", "#888888", "#5285A6"

        self.setStyleSheet(f"""
            StatusBarWidget {{
                background: {bg};
                border-bottom: 1px solid {border};
            }}
            QPushButton:hover {{
                color: #FFFFFF;
                background: rgba(255,255,255,0.08);
                border-radius: 3px;
            }}
            QLabel {{
                color: {text_dim};
                font-size: 11px;
            }}
            QFrame#statusSep {{
                color: {border};
                max-height: 1px;
            }}
        """)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _toggle_row3(self) -> None:
        self._row3_visible = not self._row3_visible
        self._row3_widget.setVisible(self._row3_visible)

    def _open_logs(self) -> None:
        """尝试打开日志文件（仅做简单提示）"""
        try:
            from artclaw_ui.utils import get_artclaw_config
            cfg = get_artclaw_config()
            log_path = cfg.get("log_path", "")
            if log_path:
                import os
                os.startfile(log_path)
        except Exception as exc:
            logger.debug("open logs: %s", exc)

    def _ctx_color(self, ratio: float) -> str:
        if ratio < CTX_GREEN_MAX:
            return "#4CAF50"
        if ratio < CTX_YELLOW_MAX:
            return "#FF9800"
        return "#F44336"

    def _rebuild_summary(self) -> None:
        conn_text = self._T("connected") if self._connected else self._T("disconnected")
        mcp_text = self._T("mcp_ready") if self._mcp_ready else self._T("mcp_not_ready")
        self._summary_label.setText(f"{conn_text}  ·  {mcp_text}")

    # ── Public API ────────────────────────────────────────────────────────────

    def update_connection(self, connected: bool) -> None:
        """更新连接状态显示"""
        self._connected = connected
        _base = "background: transparent; border: none; font-size: 11px; padding: 0px 4px; min-width: 0; min-height: 0;"
        if connected:
            self._status_btn.setText(f"● {self._T('connected')}")
            self._status_btn.setStyleSheet(
                f"QPushButton {{ color: #4CAF50; {_base} }}"
                "QPushButton:hover { color: #FFFFFF; background: rgba(255,255,255,0.08); border-radius: 3px; }"
            )
            self._conn_btn.setEnabled(False)
            self._disconn_btn.setEnabled(True)
        else:
            self._status_btn.setText(f"● {self._T('disconnected')}")
            self._status_btn.setStyleSheet(
                f"QPushButton {{ color: #888888; {_base} }}"
                "QPushButton:hover { color: #FFFFFF; background: rgba(255,255,255,0.08); border-radius: 3px; }"
            )
            self._conn_btn.setEnabled(True)
            self._disconn_btn.setEnabled(False)
        self._rebuild_summary()

    def update_mcp_status(self, ready: bool) -> None:
        """更新 MCP 状态"""
        self._mcp_ready = ready
        self._rebuild_summary()

    def update_context_usage(self, used: int, total: int) -> None:
        """更新上下文用量标签

        Parameters
        ----------
        used:  已用 tokens
        total: 总容量 tokens
        """
        self._ctx_used = used
        self._ctx_total = total
        if total <= 0:
            self._ctx_label.setText(f"{self._T('context_usage')}: --")
            self._ctx_label.setStyleSheet("color: #888888; font-size: 11px;")
            return
        ratio = used / total
        pct = int(ratio * 100)
        used_k = used // 1024
        total_k = total // 1024
        color = self._ctx_color(ratio)
        self._ctx_label.setText(f"{self._T('context_usage')}: {pct}% ({used_k}K/{total_k}K)")
        self._ctx_label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")

    def set_agent_label(self, emoji: str, name: str) -> None:
        """设置 Agent 显示名称"""
        label = f"{emoji} {name}" if emoji else name
        self._agent_btn.setText(label)

    def set_session_label(self, text: str) -> None:
        """设置当前会话标签"""
        self._session_btn.setText(f"💬 {text} ▼")

    def refresh_language(self) -> None:
        """语言切换后刷新按钮文本"""
        # Row3 buttons
        self._conn_btn.setText(self._T("connect"))
        self._disconn_btn.setText(self._T("disconnect"))
        self._diag_btn.setText(self._T("diagnose"))
        self._logs_btn.setText(self._T("view_logs"))
        # Row1 buttons
        self._settings_btn.setText(self._T("settings_btn"))
        # Status + summary
        if self._connected:
            self._status_btn.setText(f"● {self._T('connected')}")
        else:
            self._status_btn.setText(f"● {self._T('disconnected')}")
        self._rebuild_summary()
