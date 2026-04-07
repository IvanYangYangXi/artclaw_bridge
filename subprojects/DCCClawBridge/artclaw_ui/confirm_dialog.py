"""
confirm_dialog.py - ArtClaw DCC File Operation Confirmation Dialog

Provides ConfirmDialog for user approval of risky AI operations,
and ConfirmPoller to watch for pending confirm requests on disk.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional, List, Tuple

try:
    from artclaw_ui.qt_compat import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QCheckBox, QFrame, QScrollArea, QWidget, QTextEdit,
        QSizePolicy
    )
    from artclaw_ui.qt_compat import Signal, Qt, QTimer
    from artclaw_ui.qt_compat import QFont, QColor
except ImportError:
    raise ImportError("Qt (PySide2/PySide6) is required.")

from artclaw_ui.theme import COLORS, get_theme

logger = logging.getLogger(__name__)

RISK_COLORS = {
    "high": "#e74c3c",
    "medium": "#f39c12",
    "low": "#2ecc71",
}

CONFIRM_REQUEST_FILE = "_confirm_request.json"
CONFIRM_RESPONSE_FILE = "_confirm_response.json"


class ConfirmDialog(QDialog):
    """Dialog asking the user to approve or reject an AI-requested operation."""

    def __init__(
        self,
        risk_level: str,
        operations: List[dict],
        code_preview: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._risk_level = risk_level.lower()
        self._operations = operations
        self._code_preview = code_preview
        self._approved = False
        self._dont_ask_again = False

        self.setWindowTitle("操作确认")
        self.setMinimumWidth(480)
        self.setModal(True)
        self._apply_theme()
        self._build_ui()

    # ------------------------------------------------------------------ #
    # UI                                                                    #
    # ------------------------------------------------------------------ #

    def _apply_theme(self):
        theme = get_theme()
        self.setStyleSheet(theme.get("dialog", ""))

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # Risk level label
        risk_color = RISK_COLORS.get(self._risk_level, "#f39c12")
        risk_lbl = QLabel(f"⚠ 风险级别: {self._risk_level.upper()}")
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        risk_lbl.setFont(font)
        risk_lbl.setStyleSheet(f"color: {risk_color};")
        layout.addWidget(risk_lbl)

        # Description
        desc_lbl = QLabel("AI 请求执行以下操作，是否批准？")
        desc_lbl.setStyleSheet(f"color: {COLORS.get('text_primary', '#e0e0e0')};")
        layout.addWidget(desc_lbl)

        # Operations list
        if self._operations:
            ops_frame = QFrame()
            ops_frame.setStyleSheet(
                f"background: {COLORS.get('bg_secondary', '#2a2a2a')};"
                f"border-radius: 4px; border: 1px solid {COLORS.get('border', '#3a3a3a')};"
            )
            ops_layout = QVBoxLayout(ops_frame)
            ops_layout.setSpacing(2)
            ops_layout.setContentsMargins(8, 6, 8, 6)
            for op in self._operations:
                op_type = op.get("type", "")
                op_path = op.get("path", "")
                line = QLabel(f"{op_type}: {op_path}")
                line.setStyleSheet(f"color: {COLORS.get('text_secondary', '#888')}; font-size: 11px;")
                line.setWordWrap(True)
                ops_layout.addWidget(line)
            layout.addWidget(ops_frame)

        # Code preview
        if self._code_preview:
            layout.addWidget(self._make_separator())
            preview_lbl = QLabel("代码预览:")
            preview_lbl.setStyleSheet(f"color: {COLORS.get('text_secondary', '#888')}; font-size: 11px;")
            layout.addWidget(preview_lbl)

            preview_text = self._code_preview[:800]
            if len(self._code_preview) > 800:
                preview_text += "\n... (已截断)"
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setPlainText(preview_text)
            text_edit.setFixedHeight(140)
            text_edit.setStyleSheet(
                f"font-family: Consolas, monospace; font-size: 11px;"
                f"background: {COLORS.get('bg_tertiary', '#1a1a1a')};"
                f"color: {COLORS.get('text_primary', '#e0e0e0')}; border: none;"
            )
            layout.addWidget(text_edit)

        # Separator
        layout.addWidget(self._make_separator())

        # Don't ask again checkbox
        self._chk_dont_ask = QCheckBox("不再提示此风险级别")
        self._chk_dont_ask.setStyleSheet(f"color: {COLORS.get('text_secondary', '#888')};")
        layout.addWidget(self._chk_dont_ask)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_reject = QPushButton("拒绝")
        btn_reject.setFixedSize(80, 32)
        btn_reject.setStyleSheet(
            f"background-color: {COLORS.get('accent_red', '#e74c3c')}; color: white; border-radius: 4px;"
        )
        btn_reject.clicked.connect(self._on_reject)

        btn_approve = QPushButton("批准")
        btn_approve.setFixedSize(80, 32)
        btn_approve.setStyleSheet(
            f"background-color: {COLORS.get('accent_green', '#2ecc71')}; color: white; border-radius: 4px;"
        )
        btn_approve.clicked.connect(self._on_approve)

        btn_row.addWidget(btn_reject)
        btn_row.addWidget(btn_approve)
        layout.addLayout(btn_row)

    def _make_separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet(f"color: {COLORS.get('border', '#3a3a3a')};")
        return line

    # ------------------------------------------------------------------ #
    # Actions                                                               #
    # ------------------------------------------------------------------ #

    def _on_approve(self):
        self._approved = True
        self._dont_ask_again = self._chk_dont_ask.isChecked()
        self.accept()

    def _on_reject(self):
        self._approved = False
        self._dont_ask_again = self._chk_dont_ask.isChecked()
        self.reject()

    def get_result(self) -> Tuple[bool, bool]:
        """Returns (approved, dont_ask_again)."""
        return self._approved, self._dont_ask_again


# ------------------------------------------------------------------ #
# ConfirmPoller                                                         #
# ------------------------------------------------------------------ #

class ConfirmPoller:
    """Polls a data directory for _confirm_request.json every 200ms."""

    def __init__(self, parent_widget: Optional[QWidget] = None):
        self._parent = parent_widget
        self._data_dir: Optional[str] = None
        self._timer = QTimer()
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._poll)
        self._silent_medium = False
        self._silent_high = False

    def start(self, data_dir: str):
        self._data_dir = data_dir
        self._timer.start()
        logger.info("ConfirmPoller started, watching: %s", data_dir)

    def stop(self):
        self._timer.stop()
        logger.info("ConfirmPoller stopped")

    def set_silent(self, medium: bool, high: bool):
        self._silent_medium = medium
        self._silent_high = high

    def _poll(self):
        if not self._data_dir:
            return
        request_path = os.path.join(self._data_dir, CONFIRM_REQUEST_FILE)
        response_path = os.path.join(self._data_dir, CONFIRM_RESPONSE_FILE)

        if not os.path.isfile(request_path):
            return

        try:
            with open(request_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read confirm request: %s", exc)
            self._write_response(response_path, "no")
            self._remove_request(request_path)
            return

        risk_level = data.get("risk_level", "medium").lower()
        auto_approve = (
            (risk_level == "medium" and self._silent_medium)
            or (risk_level == "high" and self._silent_high)
        )

        if auto_approve:
            logger.info("Auto-approving [%s] in silent mode", risk_level)
            self._write_response(response_path, "yes")
            self._remove_request(request_path)
            return

        # Show dialog
        operations = data.get("operations", [])
        code_preview = data.get("code_preview", "")
        dlg = ConfirmDialog(risk_level, operations, code_preview, self._parent)
        dlg.exec_()
        approved, dont_ask_again = dlg.get_result()

        if dont_ask_again:
            if risk_level == "medium":
                self._silent_medium = True
            elif risk_level == "high":
                self._silent_high = True

        self._write_response(response_path, "yes" if approved else "no")
        self._remove_request(request_path)

    def _write_response(self, path: str, answer: str):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"response": answer}, f)
            logger.debug("Wrote confirm response: %s -> %s", path, answer)
        except OSError as exc:
            logger.error("Failed to write confirm response: %s", exc)

    def _remove_request(self, path: str):
        try:
            os.remove(path)
        except OSError:
            pass
