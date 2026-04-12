# Ref: docs/features/phase5-dcc-integration.md
"""
Maya Quick Panel for ArtClaw Tool Manager.

Provides Maya-specific context gathering and a PySide2/6 Qt panel
that shows recent tools and server status.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..common.panel_base import ArtClawQuickPanel


class MayaQuickPanel(ArtClawQuickPanel):
    """Quick Panel tailored for Autodesk Maya."""

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    def get_dcc_context(self) -> Dict[str, Any]:
        """Return current Maya scene context.

        Safely wraps ``maya.cmds`` calls so the class can be imported
        outside of Maya for testing.
        """
        try:
            import maya.cmds as cmds  # type: ignore[import-unmanaged]

            selected: List[str] = cmds.ls(sl=True) or []
            scene: str = cmds.file(q=True, sceneName=True) or ""
            version: str = cmds.about(version=True) or "unknown"
        except Exception:
            selected = []
            scene = ""
            version = "unknown"

        return {
            "dcc": "maya2024",
            "version": version,
            "selected": selected,
            "scene": scene,
        }

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def open_web_manager(self, context: Optional[Dict[str, str]] = None) -> None:
        """Open the web manager pre-populated with Maya context."""
        ctx = context or self.get_dcc_context()
        url_params: Dict[str, str] = {
            "dcc": ctx.get("dcc", "maya2024"),
            "version": ctx.get("version", ""),
            "file": ctx.get("scene", ""),
        }
        selected = ctx.get("selected", [])
        if selected:
            url_params["selected"] = ",".join(selected[:20])
        super().open_web_manager(url_params)

    # ------------------------------------------------------------------
    # Qt Panel
    # ------------------------------------------------------------------

    def create_qt_panel(self):
        """Create and return a Qt widget panel for docking in Maya.

        Attempts PySide2 first (Maya 2022-2024), then PySide6 (Maya 2025+).
        Returns a ``QWidget`` instance ready to be shown or docked.
        """
        try:
            from PySide2 import QtWidgets  # type: ignore[import-unmanaged]
        except ImportError:
            from PySide6 import QtWidgets  # type: ignore[import-unmanaged]

        # Root widget
        panel = QtWidgets.QWidget()
        panel.setWindowTitle("ArtClaw Tools")
        panel.setMinimumWidth(260)

        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header
        header = QtWidgets.QLabel("ArtClaw Tools")
        header.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #E0E0E0;"
        )
        layout.addWidget(header)

        # Status
        self._status_label = QtWidgets.QLabel("Checking server...")
        self._status_label.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(self._status_label)

        # Separator
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        layout.addWidget(sep)

        # Recent tools header
        recent_header = QtWidgets.QLabel("Recent Tools")
        recent_header.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #B0B0B0;"
        )
        layout.addWidget(recent_header)

        # Recent tools list
        self._tools_list = QtWidgets.QListWidget()
        self._tools_list.setMaximumHeight(150)
        self._tools_list.setStyleSheet(
            "QListWidget { background: #3C3C3C; border: 1px solid #555;"
            " border-radius: 4px; }"
            "QListWidget::item { padding: 4px 8px; color: #E0E0E0; }"
            "QListWidget::item:hover { background: #4A4A4A; }"
        )
        layout.addWidget(self._tools_list)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()

        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self._on_refresh)
        btn_layout.addWidget(refresh_btn)

        open_btn = QtWidgets.QPushButton("Open Manager")
        open_btn.clicked.connect(lambda: self.open_web_manager())
        btn_layout.addWidget(open_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

        self._panel = panel
        return panel

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_refresh(self) -> None:
        """Slot: refresh server status and recent tools list."""
        available = self.is_server_available()
        if available:
            self._status_label.setText("Server: Connected")
            self._status_label.setStyleSheet(
                "font-size: 11px; color: #4CAF50;"
            )
            tools = self.get_recent_tools(5)
            self._tools_list.clear()
            for t in tools:
                name = t.get("name", t.get("id", "Unknown"))
                self._tools_list.addItem(name)
        else:
            self._status_label.setText("Server: Offline")
            self._status_label.setStyleSheet(
                "font-size: 11px; color: #F44336;"
            )

    # ------------------------------------------------------------------
    # Event reporting
    # ------------------------------------------------------------------

    def report_event(
        self,
        event_type: str,
        timing: str = "post",
        data: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Report a DCC event to the trigger engine."""
        event_data: Dict[str, Any] = {
            "dcc_type": "maya2024",
            "event_type": event_type,
            "timing": timing,
            "data": data or {},
        }
        return self._client.post("/dcc-events", data=event_data)
