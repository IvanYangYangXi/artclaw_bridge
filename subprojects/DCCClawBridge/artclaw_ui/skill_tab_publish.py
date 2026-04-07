"""
skill_tab_publish.py - Skill 发布弹窗
========================================

选择目标层级 + DCC + 填写 changelog + Patch/Minor/Major 发布。
"""

from __future__ import annotations

import logging

from artclaw_ui.qt_compat import *  # noqa: F401,F403
HAS_QT = True

from artclaw_ui.theme import get_theme
from artclaw_ui.utils import get_artclaw_config

logger = logging.getLogger("artclaw.ui.skill_publish")

_DCC_LABELS = {
    "universal": "Universal", "unreal": "UE", "unreal_engine": "UE",
    "maya": "Maya", "max": "Max",
}


def show_publish_dialog(entry, discovered_dcc, parent=None):
    if not HAS_QT:
        return

    cfg = get_artclaw_config()
    t = get_theme(cfg.get("dcc_name", "maya"))

    dlg = QDialog(parent)
    dlg.setWindowTitle(f"发布 {entry.name}")
    dlg.resize(460, 380)

    root = QVBoxLayout(dlg)
    root.setContentsMargins(12, 12, 12, 12)
    root.setSpacing(8)

    lbl_style = f"color: {t['text']}; font-size: 12px;"
    section_style = f"color: {t['text_dim']}; font-size: 11px;"

    cur_ver = entry.version or "0.0.0"
    desc = QLabel(f"将 {entry.name} (v{cur_ver}) 发布到项目源码仓库")
    desc.setWordWrap(True)
    desc.setStyleSheet(lbl_style)
    root.addWidget(desc)

    # Layer selection
    root.addWidget(_section_label("目标层级", section_style))
    layer_row = QHBoxLayout()
    selected_layer = ["marketplace"]

    def _make_layer_btn(label, key, color):
        btn = QPushButton(label)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(28)
        _update_btn = lambda: btn.setStyleSheet(
            f"QPushButton {{ background: {color if selected_layer[0] == key else t['bg_secondary']};"
            f" color: #fff; border-radius: 3px; padding: 2px 10px; }}"
        )
        _update_btn()
        btn.clicked.connect(lambda: (_set_layer(key), _refresh_layer_btns()))
        btn._update = _update_btn
        btn._key = key
        return btn

    def _set_layer(k):
        selected_layer[0] = k

    layer_btns = []

    def _refresh_layer_btns():
        for b in layer_btns:
            b._update()

    btn_mp = _make_layer_btn("市集", "marketplace", "#4D80E6")
    btn_of = _make_layer_btn("官方", "official", "#33B34D")
    layer_btns.extend([btn_mp, btn_of])
    layer_row.addWidget(btn_mp)
    layer_row.addWidget(btn_of)
    layer_row.addStretch()
    root.addLayout(layer_row)

    # DCC selection
    root.addWidget(_section_label("目标软件目录", section_style))
    dcc_row = QHBoxLayout()
    default_dcc = entry.software
    if default_dcc == "unreal_engine":
        default_dcc = "unreal"
    if not default_dcc:
        default_dcc = "universal"
    selected_dcc = [default_dcc]

    dcc_btns = []
    dcc_options = ["universal", "unreal", "maya", "max"]
    for sw in discovered_dcc:
        norm = "unreal" if sw == "unreal_engine" else sw
        if norm not in dcc_options:
            dcc_options.append(norm)

    def _refresh_dcc_btns():
        for b in dcc_btns:
            b._update()

    for dcc_key in dcc_options:
        label = _DCC_LABELS.get(dcc_key, dcc_key)
        btn = QPushButton(label)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(28)
        k = dcc_key

        def make_update(b, k=k):
            def _u():
                b.setStyleSheet(
                    f"QPushButton {{ background: {t['accent'] if selected_dcc[0] == k else t['bg_secondary']};"
                    f" color: #fff; border-radius: 3px; padding: 2px 10px; }}"
                )
            return _u

        btn._update = make_update(btn, k)
        btn._update()
        btn.clicked.connect(lambda checked=False, k=k: (selected_dcc.__setitem__(0, k), _refresh_dcc_btns()))
        dcc_btns.append(btn)
        dcc_row.addWidget(btn)

    dcc_row.addStretch()
    root.addLayout(dcc_row)

    # Changelog
    root.addWidget(_section_label("变更说明", section_style))
    changelog_input = QLineEdit()
    changelog_input.setPlaceholderText("简短描述本次变更...")
    changelog_input.setStyleSheet(
        f"QLineEdit {{ background: {t['bg_input']}; color: {t['text']};"
        f" border: 1px solid {t['border']}; border-radius: 3px; padding: 4px 8px; }}"
    )
    root.addWidget(changelog_input)

    root.addStretch()

    # Buttons: Patch / Minor / Major / Cancel
    btn_row = QHBoxLayout()
    btn_row.addStretch()
    btn_base = (
        f"color: #fff; border-radius: 3px; padding: 4px 12px; font-weight: bold;"
    )

    def _do_publish(bump: str):
        try:
            from skill_sync import publish_skill
            cl = changelog_input.text().strip()
            publish_skill(entry.name, selected_layer[0], bump, cl, selected_dcc[0])
        except Exception as ex:
            logger.error("发布失败: %s", ex)
        dlg.accept()

    for bump, color in [("Patch", "#55A"), ("Minor", "#5A5"), ("Major", "#A55")]:
        b = QPushButton(bump)
        b.setStyleSheet(f"QPushButton {{ background: {color}; {btn_base} }}")
        b.clicked.connect(lambda checked=False, bu=bump.lower(): _do_publish(bu))
        btn_row.addWidget(b)

    cancel_btn = QPushButton("取消")
    cancel_btn.setStyleSheet(
        f"QPushButton {{ background: {t['bg_secondary']}; color: {t['text']};"
        f" border-radius: 3px; padding: 4px 12px; }}"
    )
    cancel_btn.clicked.connect(dlg.reject)
    btn_row.addWidget(cancel_btn)

    root.addLayout(btn_row)
    dlg.exec_()


def _section_label(text: str, style: str):
    if not HAS_QT:
        return None
    lbl = QLabel(text)
    lbl.setStyleSheet(style)
    return lbl
