"""
settings_dialog.py - ArtClaw DCC Settings Dialog

Provides SettingsDialog for configuring language, send mode, context window,
agent switching, silent mode, plan mode, and skills management.
"""
from __future__ import annotations

import logging
from typing import Optional, List

try:
    from PySide2.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QCheckBox, QFrame, QScrollArea, QWidget, QButtonGroup,
        QSizePolicy, QSpacerItem
    )
    from PySide2.QtCore import Signal, Qt
    from PySide2.QtGui import QFont
except ImportError:
    raise ImportError("PySide2 is required. Install via Maya/Max built-in or pip.")

from artclaw_ui.theme import COLORS, get_theme
from artclaw_ui.utils import get_artclaw_config, save_artclaw_config

logger = logging.getLogger(__name__)

CONTEXT_WINDOW_OPTIONS = [
    (128000, "128K"),
    (200000, "200K"),
    (500000, "500K"),
]


def _separator() -> QFrame:
    """Create a horizontal separator line."""
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    line.setStyleSheet(f"color: {COLORS.get('border', '#3a3a3a')};")
    return line


def _section_label(text: str) -> QLabel:
    """Create a bold section header label."""
    lbl = QLabel(text)
    font = QFont()
    font.setBold(True)
    lbl.setFont(font)
    lbl.setStyleSheet(f"color: {COLORS.get('text_primary', '#e0e0e0')};")
    return lbl


class SettingsDialog(QDialog):
    """Settings dialog for ArtClaw DCC plugin."""

    language_changed = Signal()
    send_mode_changed = Signal(bool)
    agent_changed = Signal(str)
    plan_mode_changed = Signal(bool)
    manage_requested = Signal()
    context_window_changed = Signal(int)
    silent_mode_changed = Signal(str, bool)

    def __init__(self, bridge_manager=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._bridge_manager = bridge_manager
        self._agents: List[dict] = []
        self._plan_mode_on = False
        self._silent_medium = False
        self._silent_high = False
        self._ctx_buttons: List[QPushButton] = []
        self._agent_buttons: List[QPushButton] = []
        self._current_agent_id: Optional[str] = None

        self.setWindowTitle("设置")
        self.setMinimumWidth(400)
        self.setModal(True)
        self._apply_theme()
        self._build_ui()
        self._load_config()

    # ------------------------------------------------------------------ #
    # UI Construction                                                       #
    # ------------------------------------------------------------------ #

    def _apply_theme(self):
        theme = get_theme()
        self.setStyleSheet(theme.get("dialog", ""))

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(16, 16, 16, 16)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(content)
        root.addWidget(scroll)

        # Language
        layout.addWidget(_section_label("语言 / Language"))
        self._btn_language = QPushButton()
        self._btn_language.setFixedHeight(30)
        self._btn_language.clicked.connect(self._toggle_language)
        layout.addWidget(self._btn_language)
        layout.addWidget(_separator())

        # Send mode
        layout.addWidget(_section_label("发送方式"))
        self._chk_enter_send = QCheckBox("Enter 直接发送")
        self._chk_enter_send.setToolTip("勾选 = Enter 直接发送；不勾选 = Ctrl+Enter 发送")
        self._chk_enter_send.stateChanged.connect(
            lambda state: self.send_mode_changed.emit(state == Qt.Checked)
        )
        layout.addWidget(self._chk_enter_send)
        layout.addWidget(_separator())

        # Context window size
        layout.addWidget(_section_label("上下文窗口大小"))
        ctx_row = QHBoxLayout()
        ctx_row.setSpacing(6)
        for size_val, label in CONTEXT_WINDOW_OPTIONS:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setProperty("ctx_size", size_val)
            btn.setCheckable(True)
            btn.clicked.connect(self._on_ctx_size_clicked)
            ctx_row.addWidget(btn)
            self._ctx_buttons.append(btn)
        ctx_row.addStretch()
        layout.addLayout(ctx_row)
        layout.addWidget(_separator())

        # Agent switch
        agent_header = QHBoxLayout()
        agent_header.addWidget(_section_label("Agent"))
        agent_header.addStretch()
        self._btn_refresh_agents = QPushButton("刷新")
        self._btn_refresh_agents.setFixedSize(50, 24)
        self._btn_refresh_agents.clicked.connect(self._refresh_agents)
        agent_header.addWidget(self._btn_refresh_agents)
        layout.addLayout(agent_header)
        self._agent_list_widget = QWidget()
        self._agent_list_layout = QVBoxLayout(self._agent_list_widget)
        self._agent_list_layout.setSpacing(4)
        self._agent_list_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._agent_list_widget)
        layout.addWidget(_separator())

        # Silent mode
        layout.addWidget(_section_label("静默模式"))
        silent_row = QHBoxLayout()
        silent_row.setSpacing(6)
        self._btn_silent_medium = QPushButton("中风险静默 OFF")
        self._btn_silent_medium.setCheckable(True)
        self._btn_silent_medium.setFixedHeight(28)
        self._btn_silent_medium.clicked.connect(
            lambda checked: self._on_silent_toggled("medium", checked)
        )
        self._btn_silent_high = QPushButton("高风险静默 OFF")
        self._btn_silent_high.setCheckable(True)
        self._btn_silent_high.setFixedHeight(28)
        self._btn_silent_high.clicked.connect(
            lambda checked: self._on_silent_toggled("high", checked)
        )
        silent_row.addWidget(self._btn_silent_medium)
        silent_row.addWidget(self._btn_silent_high)
        silent_row.addStretch()
        layout.addLayout(silent_row)
        layout.addWidget(_separator())

        # Plan mode
        layout.addWidget(_section_label("计划模式"))
        self._btn_plan_mode = QPushButton("Plan 模式 OFF")
        self._btn_plan_mode.setCheckable(True)
        self._btn_plan_mode.setFixedHeight(30)
        self._btn_plan_mode.clicked.connect(self._on_plan_mode_toggled)
        layout.addWidget(self._btn_plan_mode)
        layout.addWidget(_separator())

        # Skills management
        layout.addWidget(_section_label("技能管理"))
        btn_manage = QPushButton("Skill/MCP 管理")
        btn_manage.setFixedHeight(30)
        btn_manage.clicked.connect(self._on_manage_clicked)
        layout.addWidget(btn_manage)

        layout.addStretch()

        # Bottom close button
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.setFixedSize(80, 30)
        btn_close.clicked.connect(self.accept)
        bottom_row.addWidget(btn_close)
        root.addLayout(bottom_row)

    # ------------------------------------------------------------------ #
    # Config Load / Save                                                    #
    # ------------------------------------------------------------------ #

    def _load_config(self):
        cfg = get_artclaw_config()
        lang = cfg.get("language", "zh")
        self._btn_language.setText("中文" if lang == "zh" else "English")

        enter_send = cfg.get("enter_send", True)
        self._chk_enter_send.setChecked(enter_send)

        ctx_size = cfg.get("context_window_size", 128000)
        # 迁移旧值: 128*1024=131072 → 128000, 200*1024=204800 → 200000, 500*1024=512000 → 500000
        _MIGRATE = {131072: 128000, 204800: 200000, 512000: 500000}
        if ctx_size in _MIGRATE:
            ctx_size = _MIGRATE[ctx_size]
            cfg["context_window_size"] = ctx_size
            save_artclaw_config(cfg)
        self._set_active_ctx_button(ctx_size)

        self._silent_medium = cfg.get("silent_mode_medium", False)
        self._silent_high = cfg.get("silent_mode_high", False)
        self._update_silent_buttons()

        plan_on = cfg.get("plan_mode", False)
        self._plan_mode_on = plan_on
        self._btn_plan_mode.setChecked(plan_on)
        self._update_plan_button()

        self._current_agent_id = cfg.get("current_agent_id")
        self._refresh_agents()

    def _set_active_ctx_button(self, size: int):
        for btn in self._ctx_buttons:
            active = btn.property("ctx_size") == size
            btn.setChecked(active)
            btn.setStyleSheet(
                f"background-color: {COLORS.get('accent_blue', '#1e90ff')}; color: white;"
                if active else ""
            )

    # ------------------------------------------------------------------ #
    # Event Handlers                                                        #
    # ------------------------------------------------------------------ #

    def _toggle_language(self):
        cfg = get_artclaw_config()
        current = cfg.get("language", "zh")
        new_lang = "en" if current == "zh" else "zh"
        cfg["language"] = new_lang
        save_artclaw_config(cfg)
        self._btn_language.setText("中文" if new_lang == "zh" else "English")
        self.language_changed.emit()
        logger.info("Language toggled to: %s", new_lang)

    def _on_ctx_size_clicked(self):
        btn = self.sender()
        if not btn:
            return
        size = btn.property("ctx_size")
        cfg = get_artclaw_config()
        cfg["context_window_size"] = size
        save_artclaw_config(cfg)
        self._set_active_ctx_button(size)
        self.context_window_changed.emit(size)
        logger.info("Context window size set to: %d", size)

    def _refresh_agents(self):
        # Clear existing buttons
        for btn in self._agent_buttons:
            btn.deleteLater()
        self._agent_buttons.clear()

        if not self._bridge_manager:
            lbl = QLabel("(无可用 Bridge Manager)")
            lbl.setStyleSheet(f"color: {COLORS.get('text_secondary', '#888')};")
            self._agent_list_layout.addWidget(lbl)
            return

        try:
            self._agents = self._bridge_manager.list_agents() or []
        except Exception as exc:
            logger.warning("Failed to list agents: %s", exc)
            self._agents = []

        cfg = get_artclaw_config()
        self._current_agent_id = cfg.get("current_agent_id")

        for agent in self._agents:
            agent_id = agent.get("id", "")
            name = agent.get("name", agent_id)
            emoji = agent.get("emoji", "🤖")
            is_current = agent_id == self._current_agent_id
            label = f"{emoji} {name} ({agent_id}){' [当前]' if is_current else ''}"
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setProperty("agent_id", agent_id)
            if is_current:
                btn.setStyleSheet(
                    f"background-color: {COLORS.get('accent_blue', '#1e90ff')}; color: white;"
                )
            btn.clicked.connect(self._on_agent_clicked)
            self._agent_list_layout.addWidget(btn)
            self._agent_buttons.append(btn)

    def _on_agent_clicked(self):
        btn = self.sender()
        if not btn:
            return
        agent_id = btn.property("agent_id")
        if self._bridge_manager:
            try:
                self._bridge_manager.set_agent(agent_id)
            except Exception as exc:
                logger.warning("Failed to set agent %s: %s", agent_id, exc)
        cfg = get_artclaw_config()
        cfg["current_agent_id"] = agent_id
        save_artclaw_config(cfg)
        self._current_agent_id = agent_id
        self.agent_changed.emit(agent_id)
        self._refresh_agents()
        logger.info("Agent switched to: %s", agent_id)

    def _on_silent_toggled(self, level: str, checked: bool):
        cfg = get_artclaw_config()
        if level == "medium":
            self._silent_medium = checked
            cfg["silent_mode_medium"] = checked
        else:
            self._silent_high = checked
            cfg["silent_mode_high"] = checked
        save_artclaw_config(cfg)
        self._update_silent_buttons()
        self.silent_mode_changed.emit(level, checked)
        logger.info("Silent mode [%s] set to: %s", level, checked)

    def _update_silent_buttons(self):
        med_on = self._silent_medium
        self._btn_silent_medium.setChecked(med_on)
        self._btn_silent_medium.setText(f"中风险静默 {'ON' if med_on else 'OFF'}")
        self._btn_silent_medium.setStyleSheet(
            f"background-color: {COLORS.get('accent_green', '#2ecc71')}; color: white;"
            if med_on else ""
        )
        high_on = self._silent_high
        self._btn_silent_high.setChecked(high_on)
        self._btn_silent_high.setText(f"高风险静默 {'ON' if high_on else 'OFF'}")
        self._btn_silent_high.setStyleSheet(
            f"background-color: {COLORS.get('accent_red', '#e74c3c')}; color: white;"
            if high_on else ""
        )

    def _on_plan_mode_toggled(self, checked: bool):
        self._plan_mode_on = checked
        cfg = get_artclaw_config()
        cfg["plan_mode"] = checked
        save_artclaw_config(cfg)
        self._update_plan_button()
        self.plan_mode_changed.emit(checked)
        logger.info("Plan mode set to: %s", checked)

    def _update_plan_button(self):
        on = self._plan_mode_on
        self._btn_plan_mode.setText(f"Plan 模式 {'ON' if on else 'OFF'}")
        self._btn_plan_mode.setStyleSheet(
            f"background-color: {COLORS.get('accent_purple', '#9b59b6')}; color: white;"
            if on else ""
        )

    def _on_manage_clicked(self):
        self.manage_requested.emit()
        logger.info("Manage skills/MCP requested")
