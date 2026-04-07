"""
manage_panel.py - ArtClaw DCC 管理面板
========================================

提供 Skill 管理和 MCP 管理的统一入口面板。
包含顶部 Tab 切换栏和内容区域。

用法:
    ManagePanel.show_as_window(parent_widget)
"""

from __future__ import annotations

import logging
from typing import Optional

try:
    from artclaw_ui.qt_compat import (
        QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
        QFrame, QDialog, QSizePolicy, QSpacerItem, QApplication,
    )
    from artclaw_ui.qt_compat import Qt, QPoint
    from artclaw_ui.qt_compat import QFont
    HAS_QT = True
except ImportError:
    HAS_QT = False

from artclaw_ui.theme import get_theme
from artclaw_ui.utils import get_artclaw_config

logger = logging.getLogger("artclaw.ui.manage_panel")

# 延迟导入，避免循环引用
_SkillTab = None
_McpTab = None


def _get_skill_tab_class():
    global _SkillTab
    if _SkillTab is None:
        from artclaw_ui.skill_tab import SkillTab
        _SkillTab = SkillTab
    return _SkillTab


def _get_mcp_tab_class():
    global _McpTab
    if _McpTab is None:
        from artclaw_ui.mcp_tab import McpTab
        _McpTab = McpTab
    return _McpTab


_TAB_SKILL = 0
_TAB_MCP = 1

_panel_instance: Optional["ManagePanel"] = None


class ManagePanel(QWidget):
    """ArtClaw 管理面板 — Skill 管理 / MCP 管理"""

    def __init__(self, parent=None):
        super().__init__(parent)
        cfg = get_artclaw_config()
        dcc = cfg.get("dcc_name", "maya")
        self._t = get_theme(dcc)
        self._current_tab = _TAB_SKILL

        self._skill_tab: Optional[QWidget] = None
        self._mcp_tab: Optional[QWidget] = None

        self._build_ui()
        self._switch_tab(_TAB_SKILL)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        t = self._t
        self.setObjectName("ManagePanel")
        self.setStyleSheet(
            f"QWidget#ManagePanel {{ background-color: {t['bg_primary']}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- Tab bar ----
        tab_bar = QWidget()
        tab_bar.setFixedHeight(38)
        tab_bar.setStyleSheet(f"background-color: {t['bg_tertiary']};")
        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(8, 4, 8, 4)
        tab_layout.setSpacing(4)

        self._btn_skill = QPushButton("Skill 管理")
        self._btn_skill.setFixedHeight(28)
        self._btn_skill.setCursor(Qt.PointingHandCursor)
        self._btn_skill.clicked.connect(lambda: self._switch_tab(_TAB_SKILL))

        self._btn_mcp = QPushButton("MCP 管理")
        self._btn_mcp.setFixedHeight(28)
        self._btn_mcp.setCursor(Qt.PointingHandCursor)
        self._btn_mcp.clicked.connect(lambda: self._switch_tab(_TAB_MCP))

        tab_layout.addWidget(self._btn_skill)
        tab_layout.addWidget(self._btn_mcp)
        tab_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self._btn_refresh = QPushButton("刷新")
        self._btn_refresh.setFixedHeight(28)
        self._btn_refresh.setFixedWidth(56)
        self._btn_refresh.setCursor(Qt.PointingHandCursor)
        self._btn_refresh.setStyleSheet(
            f"QPushButton {{ background-color: {t['btn_secondary_bg']}; color: {t['text']};"
            f" border: 1px solid {t['border']}; border-radius: 4px; padding: 2px 8px; }}"
            f"QPushButton:hover {{ background-color: {t['btn_secondary_hover']}; }}"
        )
        self._btn_refresh.clicked.connect(self._on_refresh)
        tab_layout.addWidget(self._btn_refresh)

        root.addWidget(tab_bar)

        # ---- Separator ----
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {t['border']}; border: none;")
        root.addWidget(sep)

        # ---- Content area ----
        self._content_area = QWidget()
        self._content_area.setStyleSheet(f"background-color: {t['bg_primary']};")
        content_layout = QVBoxLayout(self._content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        self._content_layout = content_layout

        root.addWidget(self._content_area, 1)

        self._update_tab_styles()

    # ------------------------------------------------------------------
    # Tab switching
    # ------------------------------------------------------------------

    def _switch_tab(self, tab_index: int):
        self._current_tab = tab_index

        # Clear content area
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().hide()

        if tab_index == _TAB_SKILL:
            if self._skill_tab is None:
                SkillTab = _get_skill_tab_class()
                self._skill_tab = SkillTab(parent=self._content_area)
            self._content_layout.addWidget(self._skill_tab)
            self._skill_tab.show()
        else:
            if self._mcp_tab is None:
                McpTab = _get_mcp_tab_class()
                self._mcp_tab = McpTab(parent=self._content_area)
            self._content_layout.addWidget(self._mcp_tab)
            self._mcp_tab.show()

        self._update_tab_styles()

    def _update_tab_styles(self):
        t = self._t
        active_style = (
            f"QPushButton {{ background-color: {t['accent']}; color: #FFFFFF;"
            f" border: none; border-radius: 4px; padding: 2px 12px; font-weight: bold; }}"
        )
        inactive_style = (
            f"QPushButton {{ background-color: transparent; color: {t['text_dim']};"
            f" border: 1px solid {t['border']}; border-radius: 4px; padding: 2px 12px; }}"
            f"QPushButton:hover {{ background-color: {t['bg_hover']}; color: {t['text']}; }}"
        )
        self._btn_skill.setStyleSheet(active_style if self._current_tab == _TAB_SKILL else inactive_style)
        self._btn_mcp.setStyleSheet(active_style if self._current_tab == _TAB_MCP else inactive_style)

    def _on_refresh(self):
        if self._current_tab == _TAB_SKILL and self._skill_tab is not None:
            self._skill_tab.refresh()
        elif self._current_tab == _TAB_MCP and self._mcp_tab is not None:
            self._mcp_tab.refresh()

    # ------------------------------------------------------------------
    # Class-level window factory
    # ------------------------------------------------------------------

    @classmethod
    def show_as_window(cls, parent=None) -> "ManagePanel":
        """创建或复用独立窗口，非模态显示。"""
        global _panel_instance
        if _panel_instance is not None:
            try:
                _panel_instance.raise_()
                _panel_instance.activateWindow()
                return _panel_instance
            except RuntimeError:
                _panel_instance = None

        dialog = QDialog(parent)
        dialog.setWindowTitle("ArtClaw 管理")
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowMaximizeButtonHint)
        dialog.resize(720, 560)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        panel = cls(parent=dialog)
        layout.addWidget(panel)

        # Center on parent or screen
        if parent:
            p_geom = parent.frameGeometry()
            center = p_geom.center()
            dialog.move(center.x() - dialog.width() // 2,
                        center.y() - dialog.height() // 2)
        else:
            screen = QApplication.primaryScreen()
            if screen:
                sg = screen.availableGeometry()
                dialog.move(sg.center().x() - dialog.width() // 2,
                            sg.center().y() - dialog.height() // 2)

        dialog.finished.connect(lambda: _clear_panel_instance())
        _panel_instance = panel

        dialog.show()
        return panel


def _clear_panel_instance():
    global _panel_instance
    _panel_instance = None
