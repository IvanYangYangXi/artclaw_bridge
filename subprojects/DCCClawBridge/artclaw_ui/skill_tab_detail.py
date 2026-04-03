"""
skill_tab_detail.py - Skill 详情弹窗
=======================================

显示 Skill 完整元数据 + 打开目录按钮。
"""

from __future__ import annotations

import os
import logging
import subprocess

try:
    from PySide2.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
        QTextEdit, QSpacerItem, QSizePolicy,
    )
    from PySide2.QtCore import Qt
    HAS_QT = True
except ImportError:
    HAS_QT = False

from artclaw_ui.theme import get_theme
from artclaw_ui.utils import get_artclaw_config

logger = logging.getLogger("artclaw.ui.skill_detail")


def show_detail_dialog(entry, parent=None):
    if not HAS_QT:
        return

    cfg = get_artclaw_config()
    t = get_theme(cfg.get("dcc_name", "maya"))

    install_str = "已安装" if entry.install_status != "not_installed" else "未安装"
    version_str = entry.version or "-"
    if entry.updatable and entry.source_version and entry.source_version != entry.version:
        version_str += f"  (源码: {entry.source_version})"

    detail = (
        f"{entry.display_name}\n"
        f"{entry.name} v{version_str}\n\n"
        f"{entry.description}\n\n"
        f"作者: {entry.author or '-'}\n"
        f"层级: {entry.layer}\n"
        f"软件: {entry.software}\n"
        f"分类: {entry.category}\n"
        f"风险: {entry.risk_level}\n"
        f"安装状态: {install_str}\n"
        f"含代码: {'是' if entry.has_code else '否'}\n"
        f"含 SKILL.md: {'是' if entry.has_skill_md else '否'}\n"
        f"安装路径: {entry.installed_dir or '-'}\n"
        f"源码路径: {entry.source_dir or '-'}"
    )

    dlg = QDialog(parent)
    dlg.setWindowTitle(entry.display_name)
    dlg.resize(480, 420)

    root = QVBoxLayout(dlg)
    root.setContentsMargins(12, 12, 12, 12)
    root.setSpacing(8)

    text = QTextEdit()
    text.setReadOnly(True)
    text.setPlainText(detail)
    text.setStyleSheet(
        f"QTextEdit {{ background: {t['bg_secondary']}; color: {t['text']};"
        f" border: 1px solid {t['border']}; border-radius: 4px; padding: 8px;"
        f" font-size: 12px; }}"
    )
    root.addWidget(text, 1)

    btn_row = QHBoxLayout()
    btn_style = (
        f"QPushButton {{ background: {t['accent']}; color: #fff;"
        f" border-radius: 4px; padding: 4px 12px; }}"
        f"QPushButton:hover {{ background: {t['accent_hover']}; }}"
    )

    btn_installed = QPushButton("打开安装目录")
    btn_installed.setStyleSheet(btn_style)
    btn_installed.setEnabled(bool(entry.installed_dir and os.path.isdir(entry.installed_dir)))
    btn_installed.clicked.connect(
        lambda: _open_dir(entry.installed_dir))
    btn_row.addWidget(btn_installed, 1)

    btn_source = QPushButton("打开源码目录")
    btn_source.setStyleSheet(btn_style)
    btn_source.setEnabled(bool(entry.source_dir and os.path.isdir(entry.source_dir)))
    btn_source.clicked.connect(
        lambda: _open_dir(entry.source_dir))
    btn_row.addWidget(btn_source, 1)

    root.addLayout(btn_row)
    dlg.exec_()


def _open_dir(path: str):
    if not path or not os.path.isdir(path):
        return
    try:
        if os.name == "nt":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as ex:
        logger.error("打开目录失败: %s", ex)
