"""
skill_tab.py - ArtClaw DCC Skill 管理 Tab
============================================

查看/启用/禁用/钉选/安装/卸载/同步/发布 Skill。
对应 UE 端 UEAgentSkillTab.cpp + Data_impl + Actions_impl。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

try:
    from artclaw_ui.qt_compat import (
        QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
        QLineEdit, QScrollArea, QFrame, QCheckBox, QSizePolicy,
        QSpacerItem, QDialog, QTextEdit, QApplication,
    )
    from artclaw_ui.qt_compat import Qt, Signal
    from artclaw_ui.qt_compat import QFont
    HAS_QT = True
except ImportError:
    HAS_QT = False

from artclaw_ui.theme import COLORS, get_theme
from artclaw_ui.utils import get_artclaw_config, save_artclaw_config
from artclaw_ui.skill_tab_data import query_all_skills
from artclaw_ui.skill_tab_actions import exec_config_action, do_install, do_uninstall, do_update, do_sync_all

logger = logging.getLogger("artclaw.ui.skill_tab")

# -- 层级 / 安装状态颜色映射 --
_LAYER_COLORS = {
    "official": COLORS["layer_official"],
    "marketplace": COLORS["layer_marketplace"],
    "user": COLORS["layer_user"],
    "custom": COLORS["layer_custom"],
    "platform": COLORS["layer_platform"],
}
_LAYER_NAMES = {
    "official": "官方", "marketplace": "市集",
    "user": "用户", "platform": "平台",
}
_DCC_NAMES = {
    "unreal_engine": "UE", "unreal": "UE", "maya": "Maya",
    "max": "Max", "universal": "通用",
}


@dataclass
class SkillEntry:
    name: str = ""
    display_name: str = ""
    description: str = ""
    version: str = ""
    layer: str = "custom"
    software: str = "universal"
    category: str = "general"
    risk_level: str = "low"
    author: str = ""
    enabled: bool = True
    pinned: bool = False
    has_code: bool = False
    has_skill_md: bool = False
    install_status: str = "installed"  # installed / not_installed
    source_dir: str = ""
    installed_dir: str = ""
    source_version: str = ""
    updatable: bool = False
    modified: bool = False  # 运行时有未发布修改


if HAS_QT:
    class SkillTab(QWidget):
        """Skill 管理标签页"""

        def __init__(self, parent=None):
            super().__init__(parent)
            cfg = get_artclaw_config()
            self._t = get_theme(cfg.get("dcc_name", "maya"))
            self._all_skills: List[SkillEntry] = []
            self._filtered: List[SkillEntry] = []
            self._layer_filter = "all"
            self._dcc_filter = "all"
            self._install_filter = "all"
            self._search_kw = ""
            self._discovered_layers: List[str] = []
            self._discovered_dcc: List[str] = []
            self._build_ui()
            self.refresh()

        # ==============================================================
        # UI
        # ==============================================================

        def _build_ui(self):
            t = self._t
            root = QVBoxLayout(self)
            root.setContentsMargins(4, 4, 4, 4)
            root.setSpacing(4)

            # Row 1: layer filters
            self._layer_row = QHBoxLayout()
            self._layer_row.setSpacing(2)
            lbl = QLabel("层级:")
            lbl.setStyleSheet(f"color: {t['text_dim']}; font-size: 11px;")
            self._layer_row.addWidget(lbl)
            self._layer_row.addStretch()
            root.addLayout(self._layer_row)

            # Row 2: dcc filters
            self._dcc_row = QHBoxLayout()
            self._dcc_row.setSpacing(2)
            lbl2 = QLabel("软件:")
            lbl2.setStyleSheet(f"color: {t['text_dim']}; font-size: 11px;")
            self._dcc_row.addWidget(lbl2)
            self._dcc_row.addStretch()
            root.addLayout(self._dcc_row)

            # Row 3: search + count + sync
            row3 = QHBoxLayout()
            self._search_input = QLineEdit()
            self._search_input.setPlaceholderText("搜索 Skill...")
            self._search_input.setStyleSheet(
                f"QLineEdit {{ background: {t['bg_input']}; color: {t['text']};"
                f" border: 1px solid {t['border']}; border-radius: 3px; padding: 3px 6px; }}"
            )
            self._search_input.textChanged.connect(self._on_search)
            row3.addWidget(self._search_input, 1)

            self._count_label = QLabel("0/0")
            self._count_label.setStyleSheet(f"color: {t['text_dim']}; font-size: 11px; padding: 0 6px;")
            row3.addWidget(self._count_label)

            self._btn_sync = QPushButton("全量更新 (0)")
            self._btn_sync.setStyleSheet(
                f"QPushButton {{ background: {t['accent']}; color: #fff;"
                f" border-radius: 3px; padding: 3px 8px; }}"
            )
            self._btn_sync.clicked.connect(self._on_sync_all)
            row3.addWidget(self._btn_sync)
            root.addLayout(row3)

            # Separator
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background: {t['border']};")
            root.addWidget(sep)

            # Skill list scroll area
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {t['bg_primary']}; }}")
            self._list_container = QWidget()
            self._list_layout = QVBoxLayout(self._list_container)
            self._list_layout.setContentsMargins(0, 0, 0, 0)
            self._list_layout.setSpacing(2)
            self._list_layout.addStretch()
            scroll.setWidget(self._list_container)
            root.addWidget(scroll, 1)

        # ==============================================================
        # Data
        # ==============================================================

        def refresh(self):
            self._load_data()
            self._rebuild_filter_buttons()
            self._apply_filters()
            self._rebuild_list()

        def _load_data(self):
            self._all_skills.clear()
            try:
                skills_data = query_all_skills()
                for s in skills_data:
                    e = SkillEntry(**{k: v for k, v in s.items()
                                     if k in SkillEntry.__dataclass_fields__})
                    self._all_skills.append(e)
            except Exception as ex:
                logger.error("加载 Skill 数据失败: %s", ex)

            layers, dccs = set(), set()
            for s in self._all_skills:
                if s.layer:
                    layers.add(s.layer)
                if s.software:
                    dccs.add(s.software)
            self._discovered_layers = sorted(layers)
            self._discovered_dcc = sorted(dccs)

        # ==============================================================
        # Filters
        # ==============================================================

        def _rebuild_filter_buttons(self):
            t = self._t
            # Clear existing buttons (keep the label at index 0)
            for layout in (self._layer_row, self._dcc_row):
                while layout.count() > 1:
                    item = layout.takeAt(1)
                    if item.widget():
                        item.widget().deleteLater()

            # Layer buttons
            all_layers = [("全部", "all")] + [(
                _LAYER_NAMES.get(l, l), l) for l in self._discovered_layers]
            for label, key in all_layers:
                btn = self._make_filter_btn(label, key, "layer")
                self._layer_row.insertWidget(self._layer_row.count(), btn)

            # Not-installed toggle
            sep_lbl = QLabel("|")
            sep_lbl.setStyleSheet(f"color: {t['border']}; padding: 0 4px;")
            self._layer_row.insertWidget(self._layer_row.count(), sep_lbl)
            inst_btn = self._make_filter_btn("已安装", "installed", "install")
            self._layer_row.insertWidget(self._layer_row.count(), inst_btn)
            ni_btn = self._make_filter_btn("未安装", "not_installed", "install")
            self._layer_row.insertWidget(self._layer_row.count(), ni_btn)

            # DCC buttons
            all_dcc = [("全部", "all")]
            dcc_seen = set()
            for sw in self._discovered_dcc:
                norm = "unreal" if sw == "unreal_engine" else sw
                if norm in dcc_seen: continue
                dcc_seen.add(norm)
                all_dcc.append((_DCC_NAMES.get(norm, norm), norm))
            for label, key in all_dcc:
                btn = self._make_filter_btn(label, key, "dcc")
                self._dcc_row.insertWidget(self._dcc_row.count(), btn)

        def _make_filter_btn(self, label: str, key: str, kind: str) -> QPushButton:
            t = self._t
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setCursor(Qt.PointingHandCursor)

            is_active = False
            if kind == "layer":
                is_active = self._layer_filter == key
            elif kind == "dcc":
                is_active = self._dcc_filter == key
            elif kind == "install":
                is_active = self._install_filter == key

            color = t['accent'] if is_active else t['bg_secondary']
            btn.setStyleSheet(
                f"QPushButton {{ background: {color}; color: {t['text']};"
                f" border-radius: 3px; padding: 1px 6px; font-size: 11px; }}"
            )
            btn.clicked.connect(lambda checked=False, k=key, ki=kind: self._on_filter(k, ki))
            return btn

        def _on_filter(self, key: str, kind: str):
            if kind == "layer":
                self._layer_filter = key
            elif kind == "dcc":
                self._dcc_filter = key
            elif kind == "install":
                self._install_filter = key if self._install_filter != key else "all"
            self._rebuild_filter_buttons()
            self._apply_filters()
            self._rebuild_list()

        def _on_search(self, text: str):
            self._search_kw = text.strip().lower()
            self._apply_filters()
            self._rebuild_list()

        def _apply_filters(self):
            self._filtered.clear()
            for s in self._all_skills:
                if self._layer_filter != "all" and s.layer != self._layer_filter:
                    continue
                if self._install_filter == "not_installed" and s.install_status != "not_installed":
                    continue
                if self._install_filter == "installed" and s.install_status == "not_installed":
                    continue
                if self._dcc_filter != "all":
                    norm = "unreal" if s.software == "unreal_engine" else s.software
                    if norm != self._dcc_filter:
                        continue
                if self._search_kw:
                    kw = self._search_kw
                    if not (kw in s.name.lower() or kw in s.display_name.lower()
                            or kw in s.description.lower()):
                        continue
                self._filtered.append(s)

            updatable = sum(1 for s in self._all_skills if s.updatable)
            not_inst = sum(1 for s in self._all_skills if s.install_status == "not_installed")
            self._count_label.setText(f"显示 {len(self._filtered)}/{len(self._all_skills)}")
            self._btn_sync.setText(f"全量更新 ({updatable})")
            self._btn_sync.setEnabled(updatable > 0)
            self._btn_sync.setToolTip(
                f"更新 {updatable} 个 + 未安装 {not_inst} 个" if not_inst
                else f"更新 {updatable} 个"
            )

        # ==============================================================
        # List rendering
        # ==============================================================

        def _rebuild_list(self):
            layout = self._list_layout
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()

            for entry in self._filtered:
                row = self._make_skill_row(entry)
                layout.addWidget(row)
            layout.addStretch()

        def _make_skill_row(self, s: SkillEntry) -> QWidget:
            t = self._t
            row = QWidget()
            row.setMinimumHeight(48)
            row.setMaximumHeight(56)
            row.setStyleSheet(
                f"QWidget {{ background: {t['bg_secondary']}; border-radius: 4px; }}"
            )
            h = QHBoxLayout(row)
            h.setContentsMargins(6, 4, 6, 4)
            h.setSpacing(4)

            is_inst = s.install_status != "not_installed"
            dim = "" if (is_inst and s.enabled) else "opacity: 0.5;"

            # Pin star
            star = QPushButton("\u2605" if s.pinned else "\u2606")
            star.setFixedSize(28, 28)
            star.setCursor(Qt.PointingHandCursor)
            if s.pinned:
                star_style = (
                    "QPushButton { background: #3D3520; color: #F2BF0F;"
                    " border: 1px solid #F2BF0F; border-radius: 4px;"
                    " font-size: 15px; padding: 0; min-height: 0; min-width: 0; }"
                    "QPushButton:hover { background: #4D4530; }"
                )
            else:
                star_style = (
                    f"QPushButton {{ background: transparent; color: {t['text_muted']};"
                    f" border: 1px solid {t['border']}; border-radius: 4px;"
                    f" font-size: 15px; padding: 0; min-height: 0; min-width: 0; }}"
                    f"QPushButton:hover {{ color: #F2BF0F; border-color: #F2BF0F; }}"
                )
            star.setStyleSheet(star_style)
            star.setToolTip("取消钉选" if s.pinned else "钉选此技能")
            star.setEnabled(is_inst)
            star.clicked.connect(lambda checked=False, entry=s: self._on_pin(entry))
            h.addWidget(star)

            # Enable checkbox
            cb = QCheckBox()
            cb.setChecked(s.enabled)
            cb.setEnabled(is_inst)
            cb.stateChanged.connect(lambda state, entry=s: self._on_enable(entry, state))
            h.addWidget(cb)

            # Name + meta + description block (stretches to fill)
            name_w = QWidget()
            name_w.setStyleSheet("background: transparent;")
            name_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            name_l = QVBoxLayout(name_w)
            name_l.setContentsMargins(0, 0, 0, 0)
            name_l.setSpacing(1)

            # Row 1: name + layer badge + version + author
            top_row = QHBoxLayout()
            top_row.setSpacing(4)
            disp_text = s.display_name or s.name
            disp = QLabel(disp_text)
            disp.setStyleSheet(
                f"background: transparent; color: {t['text']};"
                f" font-weight: bold; font-size: 11px; {dim}"
            )
            top_row.addWidget(disp)

            # Layer badge (compact)
            lc = _LAYER_COLORS.get(s.layer, COLORS["layer_platform"])
            layer_lbl = QLabel(_LAYER_NAMES.get(s.layer, s.layer))
            layer_lbl.setStyleSheet(
                f"background: {lc}33; color: {lc}; font-size: 9px;"
                f" padding: 0px 3px; border-radius: 2px;"
            )
            top_row.addWidget(layer_lbl)

            if s.version:
                ver = QLabel(f"v{s.version}")
                ver.setStyleSheet(f"background: transparent; color: {t['text_dim']}; font-size: 9px;")
                top_row.addWidget(ver)
            if s.author:
                author_lbl = QLabel(s.author)
                author_lbl.setStyleSheet(
                    f"background: transparent; color: {t['text_dim']}; font-size: 9px;"
                )
                top_row.addWidget(author_lbl)
            top_row.addStretch()
            name_l.addLayout(top_row)

            # Row 2: description (single line, elided)
            desc_text = (s.description or s.name)[:60]
            desc = QLabel(desc_text)
            desc.setStyleSheet(
                f"background: transparent; color: {t['text_dim']}; font-size: 9px;"
            )
            desc.setWordWrap(False)
            name_l.addWidget(desc)
            h.addWidget(name_w, 1)

            # Action buttons (fixed-width, never pushed off)
            btn_area = QWidget()
            btn_area.setStyleSheet("background: transparent;")
            btn_area.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            btn_h = QHBoxLayout(btn_area)
            btn_h.setContentsMargins(0, 0, 0, 0)
            btn_h.setSpacing(3)

            btn_style = (
                f"QPushButton {{ background: {t['btn_secondary_bg']}; color: {t['text']};"
                f" border: 1px solid {t['border']}; border-radius: 3px;"
                f" padding: 1px 6px; font-size: 10px; }}"
                f"QPushButton:hover {{ background: {t['btn_secondary_hover']}; }}"
            )
            accent_btn_style = (
                f"QPushButton {{ background: {t['accent']}; color: #fff;"
                f" border: none; border-radius: 3px; padding: 1px 6px; font-size: 10px; }}"
                f"QPushButton:hover {{ background: {t['accent_hover']}; }}"
            )
            publish_style = (
                f"QPushButton {{ background: #4D80E6; color: #fff;"
                f" border: none; border-radius: 3px; padding: 1px 6px; font-size: 10px; }}"
                f"QPushButton:hover {{ background: #5A8DF0; }}"
            )

            if not is_inst:
                b = QPushButton("安装")
                b.setStyleSheet(accent_btn_style)
                b.clicked.connect(lambda checked=False, e=s: self._on_install(e))
                btn_h.addWidget(b)
            if s.updatable:
                b = QPushButton("更新")
                b.setStyleSheet(accent_btn_style)
                b.clicked.connect(lambda checked=False, e=s: self._on_update(e))
                btn_h.addWidget(b)
            if is_inst and s.layer in ("user", "custom", "marketplace"):
                b = QPushButton("卸载")
                b.setStyleSheet(btn_style)
                b.clicked.connect(lambda checked=False, e=s: self._on_uninstall(e))
                btn_h.addWidget(b)
            if is_inst and s.modified:
                b = QPushButton("发布")
                b.setStyleSheet(publish_style)
                b.clicked.connect(lambda checked=False, e=s: self._on_publish(e))
                btn_h.addWidget(b)

            det = QPushButton("···")
            det.setFixedSize(32, 28)
            det.setStyleSheet(
                f"QPushButton {{ background: {t['btn_secondary_bg']}; color: {t['text_dim']};"
                f" border: 1px solid {t['border']}; border-radius: 4px;"
                f" font-size: 14px; font-weight: bold;"
                f" padding: 0; min-height: 0; min-width: 0; }}"
                f"QPushButton:hover {{ color: {t['text']}; background: {t['btn_secondary_hover']}; }}"
            )
            det.setToolTip("详情")
            det.clicked.connect(lambda checked=False, e=s: self._on_detail(e))
            btn_h.addWidget(det)

            h.addWidget(btn_area)

            return row

        # ==============================================================
        # Actions
        # ==============================================================

        def _on_enable(self, entry: SkillEntry, state: int):
            entry.enabled = bool(state)
            action = "enable" if entry.enabled else "disable"
            exec_config_action(action, entry.name)

        def _on_pin(self, entry: SkillEntry):
            entry.pinned = not entry.pinned
            action = "pin" if entry.pinned else "unpin"
            exec_config_action(action, entry.name)
            self._rebuild_list()

        def _on_install(self, entry: SkillEntry):
            do_install(entry.name)
            self.refresh()

        def _on_uninstall(self, entry: SkillEntry):
            do_uninstall(entry.name)
            self.refresh()

        def _on_update(self, entry: SkillEntry):
            do_update(entry.name)
            self.refresh()

        def _on_sync_all(self):
            do_sync_all()
            self.refresh()

        def _on_publish(self, entry: SkillEntry):
            from artclaw_ui.skill_tab_publish import show_publish_dialog
            show_publish_dialog(entry, self._discovered_dcc, parent=self)
            self.refresh()

        def _on_detail(self, entry: SkillEntry):
            from artclaw_ui.skill_tab_detail import show_detail_dialog
            show_detail_dialog(entry, parent=self)
else:
    class SkillTab:
        pass
