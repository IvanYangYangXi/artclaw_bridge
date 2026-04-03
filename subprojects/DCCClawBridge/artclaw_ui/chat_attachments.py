"""
chat_attachments.py - ArtClaw DCC Chat Attachment Management

Provides AttachmentManager for managing pending file/image attachments,
and AttachmentPreviewWidget for displaying them in the chat UI.
"""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

try:
    from PySide2.QtWidgets import (
        QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
        QScrollArea, QFrame, QFileDialog, QSizePolicy
    )
    from PySide2.QtCore import Signal, Qt
    from PySide2.QtGui import QPixmap
    from PySide2.QtWidgets import QApplication
except ImportError:
    raise ImportError("PySide2 is required.")

from artclaw_ui.theme import COLORS, get_theme
from artclaw_ui.utils import format_file_size, is_image_file, get_mime_type

logger = logging.getLogger(__name__)


@dataclass
class PendingAttachment:
    """Represents a single pending attachment."""
    file_path: str
    display_name: str
    mime_type: str
    file_size: int
    is_image: bool
    is_temp: bool = False  # True if file was created in temp dir by this manager


class AttachmentManager:
    """Manages the list of pending attachments for a chat message."""

    MAX_SIZE = 10 * 1024 * 1024  # 10 MB

    def __init__(self):
        self.pending: List[PendingAttachment] = []
        self._temp_dir: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Temp Dir                                                              #
    # ------------------------------------------------------------------ #

    def get_temp_dir(self) -> str:
        if self._temp_dir is None or not os.path.isdir(self._temp_dir):
            self._temp_dir = tempfile.mkdtemp(prefix="artclaw_attach_")
        return self._temp_dir

    # ------------------------------------------------------------------ #
    # Add Methods                                                           #
    # ------------------------------------------------------------------ #

    def add_from_clipboard(self) -> bool:
        """Try to read an image from clipboard. Save as PNG to temp dir."""
        try:
            clipboard = QApplication.clipboard()
            img = clipboard.image()
            if img is None or img.isNull():
                return False
            temp_path = os.path.join(
                self.get_temp_dir(), f"clipboard_{uuid.uuid4().hex[:8]}.png"
            )
            pixmap = QPixmap.fromImage(img)
            if not pixmap.save(temp_path, "PNG"):
                logger.warning("Failed to save clipboard image to %s", temp_path)
                return False
            size = os.path.getsize(temp_path)
            if size > self.MAX_SIZE:
                os.remove(temp_path)
                logger.warning("Clipboard image too large: %d bytes", size)
                return False
            attachment = PendingAttachment(
                file_path=temp_path,
                display_name=os.path.basename(temp_path),
                mime_type="image/png",
                file_size=size,
                is_image=True,
                is_temp=True,
            )
            self.pending.append(attachment)
            logger.info("Added clipboard image: %s", temp_path)
            return True
        except Exception as exc:
            logger.warning("Clipboard image read failed: %s", exc)
            return False

    def add_from_clipboard_path(self) -> bool:
        """Check if clipboard text is a valid file path and add it."""
        try:
            clipboard = QApplication.clipboard()
            text = clipboard.text().strip()
            if not text or not os.path.isfile(text):
                return False
            return self._add_file(text, is_temp=False)
        except Exception as exc:
            logger.warning("Clipboard path read failed: %s", exc)
            return False

    def add_from_file_dialog(self, parent: Optional[QWidget] = None) -> int:
        """Open file dialog and add selected files. Returns number added."""
        paths, _ = QFileDialog.getOpenFileNames(
            parent,
            "选择附件",
            "",
            "所有文件 (*.*)"
        )
        added = 0
        for path in paths:
            if self._add_file(path, is_temp=False):
                added += 1
        return added

    def _add_file(self, path: str, is_temp: bool) -> bool:
        """Internal: add a file by path."""
        if not os.path.isfile(path):
            logger.warning("File not found: %s", path)
            return False
        size = os.path.getsize(path)
        if size > self.MAX_SIZE:
            logger.warning("File too large (%d bytes): %s", size, path)
            return False
        attachment = PendingAttachment(
            file_path=path,
            display_name=os.path.basename(path),
            mime_type=get_mime_type(path),
            file_size=size,
            is_image=is_image_file(path),
            is_temp=is_temp,
        )
        self.pending.append(attachment)
        logger.info("Added attachment: %s (%d bytes)", path, size)
        return True

    # ------------------------------------------------------------------ #
    # Remove / Clear                                                        #
    # ------------------------------------------------------------------ #

    def remove(self, index: int):
        """Remove attachment at index, deleting temp files."""
        if 0 <= index < len(self.pending):
            att = self.pending.pop(index)
            if att.is_temp and os.path.isfile(att.file_path):
                try:
                    os.remove(att.file_path)
                    logger.debug("Deleted temp file: %s", att.file_path)
                except OSError as exc:
                    logger.warning("Failed to delete temp file %s: %s", att.file_path, exc)

    def clear(self):
        """Remove all attachments, cleaning up temp files."""
        for att in list(self.pending):
            if att.is_temp and os.path.isfile(att.file_path):
                try:
                    os.remove(att.file_path)
                except OSError:
                    pass
        self.pending.clear()
        if self._temp_dir and os.path.isdir(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            except OSError:
                pass
            self._temp_dir = None

    # ------------------------------------------------------------------ #
    # Query Methods                                                         #
    # ------------------------------------------------------------------ #

    def get_prefix_text(self) -> str:
        """Return [Attachments] prefix block or empty string."""
        if not self.pending:
            return ""
        lines = ["[Attachments - 用户附件文件，请直接读取以下路径]"]
        for att in self.pending:
            lines.append(f"- {att.display_name} ({att.mime_type}): {att.file_path}")
        lines.append("[/Attachments]")
        lines.append("")
        lines.append("")
        return "\n".join(lines)

    def get_display_names(self) -> List[str]:
        return [att.display_name for att in self.pending]

    def get_display_paths(self) -> List[str]:
        """返回带类型标记的完整路径列表（用于对话框显示）"""
        result = []
        for att in self.pending:
            tag = "IMG" if att.is_image else "FILE"
            result.append(f"[{tag}] {att.file_path}")
        return result


# ------------------------------------------------------------------ #
# Preview Widget                                                        #
# ------------------------------------------------------------------ #

class AttachmentPreviewWidget(QWidget):
    """Horizontal scrollable preview of pending attachments."""

    attachments_changed = Signal(int)

    def __init__(self, manager: AttachmentManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._manager = manager
        self._build_ui()
        self.setVisible(False)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFixedHeight(64)
        self._scroll.setFrameShape(QFrame.NoFrame)

        self._cards_widget = QWidget()
        self._cards_layout = QHBoxLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(4, 4, 4, 4)
        self._cards_layout.setSpacing(6)
        self._cards_layout.addStretch()
        self._scroll.setWidget(self._cards_widget)
        layout.addWidget(self._scroll)

    def refresh(self):
        """Rebuild card widgets from manager state."""
        # Remove all cards (except stretch at end)
        while self._cards_layout.count() > 1:
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, att in enumerate(self._manager.pending):
            card = self._make_card(i, att)
            self._cards_layout.insertWidget(i, card)

        visible = len(self._manager.pending) > 0
        self.setVisible(visible)
        self.attachments_changed.emit(len(self._manager.pending))

    def _make_card(self, index: int, att: PendingAttachment) -> QWidget:
        card = QWidget()
        card.setFixedHeight(52)
        card.setStyleSheet(
            f"background: {COLORS.get('bg_secondary', '#2a2a2a')};"
            f"border-radius: 4px;"
            f"border: 1px solid {COLORS.get('border', '#3a3a3a')};"
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # Icon label
        icon_lbl = QLabel("🖼" if att.is_image else "📄")
        icon_lbl.setFixedWidth(20)
        layout.addWidget(icon_lbl)

        # Info
        info = QVBoxLayout()
        info.setSpacing(0)
        name_lbl = QLabel(att.display_name)
        name_lbl.setMaximumWidth(120)
        name_lbl.setStyleSheet(f"color: {COLORS.get('text_primary', '#e0e0e0')}; font-size: 11px;")
        size_lbl = QLabel(format_file_size(att.file_size))
        size_lbl.setStyleSheet(f"color: {COLORS.get('text_secondary', '#888')}; font-size: 10px;")
        info.addWidget(name_lbl)
        info.addWidget(size_lbl)
        layout.addLayout(info)

        # Remove button
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(18, 18)
        remove_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #888; border: none; font-size: 12px; }"
            "QPushButton:hover { color: #e74c3c; }"
        )
        remove_btn.setProperty("att_index", index)
        remove_btn.clicked.connect(self._on_remove)
        layout.addWidget(remove_btn)

        return card

    def _on_remove(self):
        btn = self.sender()
        if not btn:
            return
        index = btn.property("att_index")
        self._manager.remove(index)
        self.refresh()
