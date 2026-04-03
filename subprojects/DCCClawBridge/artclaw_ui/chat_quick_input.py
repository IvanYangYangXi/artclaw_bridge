"""
chat_quick_input.py - ArtClaw DCC Quick Input Panel

Provides QuickInputPanel for managing and inserting predefined text snippets,
and QuickInputEditDialog for creating/editing quick input items.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Optional

try:
    from PySide2.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QDialog, QLineEdit, QTextEdit, QScrollArea, QFrame,
        QSizePolicy, QGroupBox, QApplication
    )
    from PySide2.QtCore import Signal, Qt
    from PySide2.QtGui import QFont
except ImportError:
    raise ImportError("PySide2 is required.")

from artclaw_ui.theme import COLORS, get_theme
from artclaw_ui.utils import get_artclaw_config

logger = logging.getLogger(__name__)

QUICK_INPUTS_FILE = "quick_inputs.json"


def _get_quick_inputs_path() -> str:
    cfg = get_artclaw_config()
    data_dir = cfg.get("data_dir", os.path.expanduser("~/.artclaw"))
    return os.path.join(data_dir, QUICK_INPUTS_FILE)


@dataclass
class QuickInput:
    """A single quick input snippet."""
    id: str
    name: str
    content: str

    @staticmethod
    def new(name: str, content: str) -> "QuickInput":
        return QuickInput(id=str(uuid.uuid4()), name=name, content=content)


def load_quick_inputs() -> List[QuickInput]:
    path = _get_quick_inputs_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [QuickInput(**item) for item in data.get("quickInputs", [])]
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        logger.warning("Failed to load quick inputs: %s", exc)
        return []


def save_quick_inputs(items: List[QuickInput]):
    path = _get_quick_inputs_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"quickInputs": [asdict(qi) for qi in items]}, f, ensure_ascii=False, indent=2)
        logger.debug("Saved %d quick inputs to %s", len(items), path)
    except OSError as exc:
        logger.error("Failed to save quick inputs: %s", exc)


# ------------------------------------------------------------------ #
# Edit Dialog                                                           #
# ------------------------------------------------------------------ #

class QuickInputEditDialog(QDialog):
    """Modal dialog for creating or editing a quick input item."""

    def __init__(
        self,
        item: Optional[QuickInput] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._item = item
        self._result_item: Optional[QuickInput] = None

        self.setWindowTitle("编辑快捷输入")
        self.setMinimumWidth(360)
        self.setModal(True)
        self._apply_theme()
        self._build_ui()

        if item:
            self._name_input.setText(item.name)
            self._content_input.setPlainText(item.content)

    def _apply_theme(self):
        theme = get_theme()
        self.setStyleSheet(theme.get("dialog", ""))

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # Name
        name_lbl = QLabel("名称:")
        name_lbl.setStyleSheet(f"color: {COLORS.get('text_primary', '#e0e0e0')};")
        layout.addWidget(name_lbl)
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("快捷输入名称")
        self._name_input.setFixedHeight(30)
        layout.addWidget(self._name_input)

        # Content
        content_lbl = QLabel("内容:")
        content_lbl.setStyleSheet(f"color: {COLORS.get('text_primary', '#e0e0e0')};")
        layout.addWidget(content_lbl)
        self._content_input = QTextEdit()
        self._content_input.setPlaceholderText("输入快捷文本内容...")
        self._content_input.setFixedHeight(100)
        layout.addWidget(self._content_input)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("取消")
        btn_cancel.setFixedSize(70, 28)
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("保存")
        btn_save.setFixedSize(70, 28)
        btn_save.setStyleSheet(
            f"background-color: {COLORS.get('accent_blue', '#1e90ff')}; color: white; border-radius: 3px;"
        )
        btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _on_save(self):
        name = self._name_input.text().strip()
        content = self._content_input.toPlainText().strip()
        if not name:
            self._name_input.setFocus()
            return
        if self._item:
            self._result_item = QuickInput(
                id=self._item.id,
                name=name,
                content=content,
            )
        else:
            self._result_item = QuickInput.new(name, content)
        self.accept()

    def get_result(self) -> Optional[QuickInput]:
        return self._result_item


# ------------------------------------------------------------------ #
# Quick Input Panel                                                     #
# ------------------------------------------------------------------ #

class QuickInputPanel(QWidget):
    """Collapsible panel displaying quick input buttons."""

    input_selected = Signal(str)
    create_skill_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._items: List[QuickInput] = []
        self._collapsed = True  # 默认折叠
        self._build_ui()
        self._load()

    # ------------------------------------------------------------------ #
    # UI Construction                                                       #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header row
        header = QWidget()
        header.setFixedHeight(32)
        header.setStyleSheet(
            f"background: {COLORS.get('bg_secondary', '#2a2a2a')};"
            f"border-radius: 4px 4px 0 0;"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 0, 8, 0)
        header_layout.setSpacing(6)

        self._toggle_btn = QPushButton("▶")
        self._toggle_btn.setFixedSize(20, 20)
        self._toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #888; border: none; font-size: 10px; }"
        )
        self._toggle_btn.clicked.connect(self._toggle_collapse)
        header_layout.addWidget(self._toggle_btn)

        lbl = QLabel("快捷输入")
        lbl.setStyleSheet(f"color: {COLORS.get('text_primary', '#e0e0e0')}; font-size: 12px;")
        header_layout.addWidget(lbl)
        header_layout.addStretch()

        # "..." edit all button
        btn_edit_all = QPushButton("···")
        btn_edit_all.setFixedSize(24, 20)
        btn_edit_all.setStyleSheet(
            "QPushButton { background: transparent; color: #888; border: none; font-size: 14px; }"
            "QPushButton:hover { color: #e0e0e0; }"
        )
        btn_edit_all.setToolTip("管理全部快捷输入")
        btn_edit_all.clicked.connect(self._on_edit_all)
        header_layout.addWidget(btn_edit_all)

        btn_add = QPushButton("+添加")
        btn_add.setFixedHeight(22)
        btn_add.setStyleSheet(
            f"background-color: {COLORS.get('accent_blue', '#1e90ff')}; color: white;"
            "border-radius: 3px; font-size: 11px; padding: 0 6px;"
        )
        btn_add.clicked.connect(self._on_add)
        header_layout.addWidget(btn_add)

        root.addWidget(header)

        # Body (collapsible)
        self._body = QWidget()
        self._body.setStyleSheet(
            f"background: {COLORS.get('bg_primary', '#1e1e1e')};"
            f"border: 1px solid {COLORS.get('border', '#3a3a3a')};"
            "border-top: none; border-radius: 0 0 4px 4px;"
        )
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(6, 6, 6, 6)
        body_layout.setSpacing(4)

        # Wrap layout container
        self._items_widget = QWidget()
        self._items_layout = QVBoxLayout(self._items_widget)
        self._items_layout.setContentsMargins(0, 0, 0, 0)
        self._items_layout.setSpacing(3)
        body_layout.addWidget(self._items_widget)

        root.addWidget(self._body)
        self._body.setVisible(False)  # 默认折叠

    def _rebuild_items(self):
        """Rebuild the item rows from self._items."""
        while self._items_layout.count():
            item = self._items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, qi in enumerate(self._items):
            row = self._make_item_row(i, qi)
            self._items_layout.addWidget(row)

    def _make_item_row(self, index: int, qi: QuickInput) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Name button (main action)
        btn_name = QPushButton(qi.name)
        btn_name.setFixedHeight(24)
        btn_name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_name.setStyleSheet(
            f"QPushButton {{ background: {COLORS.get('bg_secondary', '#2a2a2a')};"
            f"color: {COLORS.get('text_primary', '#e0e0e0')}; border-radius: 3px;"
            f"font-size: 11px; padding: 0 6px; border: 1px solid {COLORS.get('border', '#3a3a3a')}; }}"
            f"QPushButton:hover {{ background: {COLORS.get('accent_blue', '#1e90ff')}; color: white; }}"
        )
        btn_name.setProperty("qi_index", index)
        btn_name.setToolTip(qi.content[:200] if qi.content else "")
        btn_name.clicked.connect(self._on_item_clicked)
        layout.addWidget(btn_name, 1)

        # Edit button
        btn_edit = QPushButton("✎")
        btn_edit.setFixedSize(22, 24)
        btn_edit.setStyleSheet(
            "QPushButton { background: transparent; color: #888; border: none; font-size: 12px; }"
            "QPushButton:hover { color: #e0e0e0; }"
        )
        btn_edit.setProperty("qi_index", index)
        btn_edit.clicked.connect(self._on_item_edit)
        layout.addWidget(btn_edit)

        # Delete button
        btn_del = QPushButton("✕")
        btn_del.setFixedSize(22, 24)
        btn_del.setStyleSheet(
            "QPushButton { background: transparent; color: #888; border: none; font-size: 12px; }"
            "QPushButton:hover { color: #e74c3c; }"
        )
        btn_del.setProperty("qi_index", index)
        btn_del.clicked.connect(self._on_item_delete)
        layout.addWidget(btn_del)

        return row

    # ------------------------------------------------------------------ #
    # Actions                                                               #
    # ------------------------------------------------------------------ #

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self._body.setVisible(not self._collapsed)
        self._toggle_btn.setText("▶" if self._collapsed else "▼")

    def _load(self):
        self._items = load_quick_inputs()
        self._rebuild_items()

    def _save(self):
        save_quick_inputs(self._items)

    def _on_add(self):
        dlg = QuickInputEditDialog(item=None, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            new_item = dlg.get_result()
            if new_item:
                self._items.append(new_item)
                self._save()
                self._rebuild_items()

    def _on_item_clicked(self):
        btn = self.sender()
        if not btn:
            return
        idx = btn.property("qi_index")
        if 0 <= idx < len(self._items):
            self.input_selected.emit(self._items[idx].content)

    def _on_item_edit(self):
        btn = self.sender()
        if not btn:
            return
        idx = btn.property("qi_index")
        if 0 <= idx < len(self._items):
            dlg = QuickInputEditDialog(item=self._items[idx], parent=self)
            if dlg.exec_() == QDialog.Accepted:
                updated = dlg.get_result()
                if updated:
                    self._items[idx] = updated
                    self._save()
                    self._rebuild_items()

    def _on_item_delete(self):
        btn = self.sender()
        if not btn:
            return
        idx = btn.property("qi_index")
        if 0 <= idx < len(self._items):
            self._items.pop(idx)
            self._save()
            self._rebuild_items()

    def _on_edit_all(self):
        """Re-open edit dialog cycling through all items (simple: open add dialog)."""
        self._on_add()
