"""
chat_session.py - ArtClaw DCC Multi-Session Management
=======================================================

多会话管理：SessionEntry 数据类 + SessionManager + SessionMenuWidget。

SessionManager 职责：
  - 维护 SessionEntry 列表（每个 Entry 对应一路 Gateway 会话）
  - 按 Agent 隔离缓存（切换 Agent 时保存/恢复会话列表）
  - 持久化上次使用的 session key → _last_session.json
  - 与 DCCBridgeManager 联动（set_session_key / reset_session）

SessionMenuWidget：弹出式会话列表（标签 + X 删除）
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, TYPE_CHECKING

try:
    from PySide2.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QScrollArea,
        QFrame, QSizePolicy,
    )
    from PySide2.QtCore import Qt, Signal
    HAS_QT = True
except ImportError:
    HAS_QT = False

if TYPE_CHECKING:
    from core.bridge_dcc import DCCBridgeManager

logger = logging.getLogger("artclaw.ui.session")

_LAST_SESSION_FILE = "_last_session.json"


# ── Data ──────────────────────────────────────────────────────────────────────

@dataclass
class SessionEntry:
    """单条会话记录"""
    session_key: str
    label: str
    created_at: str                     # ISO-format datetime string
    is_active: bool = False
    cached_messages: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_key": self.session_key,
            "label": self.label,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SessionEntry":
        return cls(
            session_key=d.get("session_key", ""),
            label=d.get("label", "未知会话"),
            created_at=d.get("created_at", ""),
        )


# ── Manager ───────────────────────────────────────────────────────────────────

class SessionManager:
    """多会话管理器（非 QObject，可在任意线程实例化）"""

    def __init__(self) -> None:
        self.entries: List[SessionEntry] = []
        self.active_index: int = -1
        self.agent_session_cache: Dict[str, List[SessionEntry]] = {}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _data_dir(self) -> str:
        try:
            from artclaw_ui.utils import get_artclaw_config
            cfg = get_artclaw_config()
            return cfg.get("data_dir", os.path.expanduser("~/.artclaw"))
        except Exception:
            return os.path.expanduser("~/.artclaw")

    def _last_session_path(self) -> str:
        return os.path.join(self._data_dir(), _LAST_SESSION_FILE)

    def _make_label(self) -> str:
        return "对话 " + datetime.now().strftime("%m-%d %H:%M")

    def _make_key(self) -> str:
        """生成本地临时 session key（在 Gateway 为其分配前使用）"""
        return "local-" + datetime.now().strftime("%Y%m%d%H%M%S%f")

    @property
    def active_entry(self) -> Optional[SessionEntry]:
        if 0 <= self.active_index < len(self.entries):
            return self.entries[self.active_index]
        return None

    # ── Init & restore ────────────────────────────────────────────────────────

    def init_first_session(self) -> SessionEntry:
        """创建默认第一条会话（无历史时调用）"""
        entry = SessionEntry(
            session_key=self._make_key(),
            label=self._make_label(),
            created_at=datetime.now().isoformat(),
            is_active=True,
        )
        self.entries = [entry]
        self.active_index = 0
        return entry

    def restore_or_init(self, bridge_manager: "DCCBridgeManager") -> SessionEntry:
        """从 _last_session.json 恢复，失败则初始化新会话"""
        path = self._last_session_path()
        try:
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                session_key = data.get("session_key", "")
                label = data.get("label", self._make_label())
                if session_key:
                    entry = SessionEntry(
                        session_key=session_key,
                        label=label,
                        created_at=data.get("created_at", datetime.now().isoformat()),
                        is_active=True,
                    )
                    self.entries = [entry]
                    self.active_index = 0
                    try:
                        bridge_manager.set_session_key(session_key)
                    except Exception as e:
                        logger.warning("restore session key error: %s", e)
                    return entry
        except Exception as e:
            logger.warning("restore_or_init error: %s", e)
        return self.init_first_session()

    def save_last_session(self, bridge_manager: "DCCBridgeManager") -> None:
        """保存当前会话 key 到 _last_session.json"""
        entry = self.active_entry
        if entry is None:
            return
        path = self._last_session_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(entry.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("save_last_session error: %s", e)

    # ── Session operations ────────────────────────────────────────────────────

    def new_session(self, bridge_manager: "DCCBridgeManager") -> SessionEntry:
        """保存当前，创建新会话并重置 bridge"""
        # deactivate current
        if self.active_entry:
            self.active_entry.is_active = False

        entry = SessionEntry(
            session_key=self._make_key(),
            label=self._make_label(),
            created_at=datetime.now().isoformat(),
            is_active=True,
        )
        self.entries.append(entry)
        self.active_index = len(self.entries) - 1

        try:
            bridge_manager.reset_session()
        except Exception as e:
            logger.warning("new_session bridge error: %s", e)

        self.save_last_session(bridge_manager)
        return entry

    def new_session_local(self) -> SessionEntry:
        """仅在 UI 侧创建新会话条目，不操作 bridge（由调用者自行管理 bridge）。

        对齐 UE 的 OnNewChatClicked 流程：
        - bridge reset 由 chat_panel._on_new_chat 直接调用
        - session key 会在首次发消息后由 Gateway 分配并回填
        """
        if self.active_entry:
            self.active_entry.is_active = False

        entry = SessionEntry(
            session_key="",  # 空 key — 首次发消息后由 Gateway 分配
            label=self._make_label(),
            created_at=datetime.now().isoformat(),
            is_active=True,
        )
        self.entries.append(entry)
        self.active_index = len(self.entries) - 1
        return entry

    def switch_session(self, index: int, bridge_manager: "DCCBridgeManager") -> Optional[SessionEntry]:
        """切换到指定会话（保存当前消息缓存）"""
        if index < 0 or index >= len(self.entries):
            return None
        if index == self.active_index:
            return self.active_entry

        # save current
        if self.active_entry:
            self.active_entry.is_active = False

        self.active_index = index
        target = self.entries[index]
        target.is_active = True

        try:
            bridge_manager.set_session_key(target.session_key)
        except Exception as e:
            logger.warning("switch_session bridge error: %s", e)

        self.save_last_session(bridge_manager)
        return target

    def delete_session(self, index: int) -> None:
        """删除指定会话"""
        if index < 0 or index >= len(self.entries):
            return
        self.entries.pop(index)
        # recalculate active_index
        if not self.entries:
            self.active_index = -1
        elif self.active_index >= len(self.entries):
            self.active_index = len(self.entries) - 1
            if self.active_entry:
                self.active_entry.is_active = True
        elif index < self.active_index:
            self.active_index -= 1

    def get_active_label(self) -> str:
        entry = self.active_entry
        return entry.label if entry else "无会话"

    # ── Agent isolation ───────────────────────────────────────────────────────

    def cache_for_agent_switch(self, agent_id: str) -> None:
        """切换 Agent 前：把当前 entries 保存到 cache"""
        import copy
        self.agent_session_cache[agent_id] = copy.deepcopy(self.entries)

    def restore_from_agent_switch(self, agent_id: str) -> bool:
        """切换 Agent 后：从 cache 恢复 entries。返回是否命中缓存"""
        cached = self.agent_session_cache.get(agent_id)
        if cached:
            self.entries = cached
            # find active
            self.active_index = next(
                (i for i, e in enumerate(self.entries) if e.is_active), 0
            )
            return True
        return False

    # ── History fetch ─────────────────────────────────────────────────────────

    def fetch_history(
        self,
        session_key: str,
        bridge_manager: "DCCBridgeManager",
    ) -> List[dict]:
        """从 Gateway 拉取历史消息列表"""
        try:
            messages = bridge_manager.fetch_history(session_key)
            return messages or []
        except Exception as e:
            logger.warning("fetch_history error: %s", e)
            return []


# ── SessionMenuWidget ─────────────────────────────────────────────────────────

class SessionMenuWidget(QWidget):
    """会话列表弹出面板

    每行: [会话标签] [X]

    Signals
    -------
    session_selected(index)  : 用户点击了某个会话
    session_deleted(index)   : 用户点击了某个会话的 X 删除按钮
    new_session_clicked()    : 点击"新对话"按钮
    """

    session_selected = Signal(int)
    session_deleted = Signal(int)
    new_session_clicked = Signal()

    def __init__(
        self,
        session_manager: SessionManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._session_manager = session_manager
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAutoFillBackground(True)
        self._build_ui()
        self._apply_styles()
        self.refresh()

    def focusOutEvent(self, event):
        """点击菜单外部时自动隐藏"""
        super().focusOutEvent(event)
        self.hide()

    def showEvent(self, event):
        """显示时自动获取焦点"""
        super().showEvent(event)
        self.setFocus()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # Header row: title + 新对话
        header = QHBoxLayout()
        title = QLabel("会话列表")
        title.setObjectName("menuTitle")
        new_btn = QPushButton("+ 新对话")
        new_btn.setFixedHeight(22)
        new_btn.setObjectName("newSessionBtn")
        new_btn.clicked.connect(self.new_session_clicked)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(new_btn)
        root.addLayout(header)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("menuSep")
        root.addWidget(sep)

        # Scroll area for session rows
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._list_container)
        root.addWidget(self._scroll)

    def _apply_styles(self) -> None:
        try:
            from artclaw_ui.theme import COLORS
            bg = COLORS.get("bg_secondary", "#4A4A4A")
            bg2 = COLORS.get("bg_primary", "#3C3C3C")
            border = COLORS.get("border", "#555555")
            accent = COLORS.get("accent", "#5285A6")
            text = COLORS.get("text", "#E0E0E0")
            text_dim = COLORS.get("text_dim", "#888888")
        except Exception:
            bg, bg2, border, accent = "#4A4A4A", "#3C3C3C", "#555555", "#5285A6"
            text, text_dim = "#E0E0E0", "#888888"

        self.setStyleSheet(f"""
            SessionMenuWidget {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 6px;
            }}
            SessionMenuWidget QLabel#menuTitle {{
                background: {bg};
                color: {text};
                font-size: 13px;
                font-weight: bold;
            }}
            SessionMenuWidget QPushButton#newSessionBtn {{
                background: {accent};
                color: white;
                border: none;
                border-radius: 3px;
                font-size: 11px;
                padding: 2px 8px;
            }}
            SessionMenuWidget QPushButton#newSessionBtn:hover {{
                background: {accent}CC;
            }}
            SessionMenuWidget QFrame#menuSep {{
                color: {border};
                max-height: 1px;
            }}
            SessionMenuWidget QScrollArea {{
                background: {bg};
                border: none;
            }}
            SessionMenuWidget QScrollArea > QWidget > QWidget {{
                background: {bg};
            }}
        """)

    def refresh(self) -> None:
        """重建会话行列表"""
        # clear existing rows (keep the trailing stretch)
        layout = self._list_layout
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        for i, entry in enumerate(self._session_manager.entries):
            row = self._make_row(i, entry)
            layout.insertWidget(layout.count() - 1, row)

    def _make_row(self, index: int, entry: SessionEntry) -> QWidget:
        row = QWidget()
        row.setObjectName("sessionRow")
        hl = QHBoxLayout(row)
        hl.setContentsMargins(4, 2, 4, 2)
        hl.setSpacing(4)

        lbl = QPushButton(entry.label)
        lbl.setFlat(True)
        lbl.setObjectName("sessionLabel" + ("Active" if entry.is_active else ""))
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lbl.setFixedHeight(24)

        # Style active vs inactive
        if entry.is_active:
            lbl.setStyleSheet(
                "QPushButton { color: #FFFFFF; background: #3A6080; "
                "border: none; font-size: 12px; text-align: left; padding: 0 6px; border-radius: 3px; }"
                "QPushButton:hover { background: #4A7090; }"
            )
        else:
            lbl.setStyleSheet(
                "QPushButton { color: #C0C0C0; background: #4A4A4A; "
                "border: none; font-size: 12px; text-align: left; padding: 0 6px; border-radius: 3px; }"
                "QPushButton:hover { background: #555555; }"
            )

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(20, 20)
        del_btn.setToolTip("删除此会话")
        del_btn.setStyleSheet(
            "QPushButton { color: #888; background: #4A4A4A; border: none; font-size: 11px; }"
            "QPushButton:hover { color: #F44336; background: #4A4A4A; }"
        )

        # Capture index by default arg
        lbl.clicked.connect(lambda _=False, idx=index: self.session_selected.emit(idx))
        del_btn.clicked.connect(lambda _=False, idx=index: self._on_delete(idx))

        hl.addWidget(lbl)
        hl.addWidget(del_btn)
        return row

    def _on_delete(self, index: int) -> None:
        self.session_deleted.emit(index)
        # Refresh display
        self.refresh()
