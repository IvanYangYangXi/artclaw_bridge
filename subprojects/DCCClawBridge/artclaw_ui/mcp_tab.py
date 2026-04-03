"""
mcp_tab.py - ArtClaw DCC MCP Server 管理 Tab
================================================

查看/启用/禁用/添加 MCP Server。
对应 UE 端 UEAgentMcpTab.cpp。
"""

from __future__ import annotations

import json
import logging
import os
import socket
from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:
    from PySide2.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
        QLineEdit, QScrollArea, QFrame, QCheckBox, QSizePolicy,
        QSpacerItem, QDialog, QComboBox,
    )
    from PySide2.QtCore import Qt, Signal
    HAS_QT = True
except ImportError:
    HAS_QT = False

from artclaw_ui.theme import COLORS, get_theme
from artclaw_ui.utils import get_artclaw_config, get_openclaw_config_path

logger = logging.getLogger("artclaw.ui.mcp_tab")

_DISPLAY_NAMES = {
    "ue-editor-agent": "UE Claw Bridge",
    "maya-primary": "Maya Claw Bridge",
    "max-primary": "3ds Max Claw Bridge",
}


@dataclass
class McpServerEntry:
    server_id: str = ""
    display_name: str = ""
    type: str = "websocket"     # websocket / sse / stdio
    url: str = ""
    command: str = ""
    args: List[str] = field(default_factory=list)
    enabled: bool = True
    connected: bool = False
    tool_count: int = 0


def _traverse_json_path(root: dict, dot_path: str) -> Optional[dict]:
    """按点分隔路径遍历 JSON 对象树"""
    current = root
    for part in dot_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current if isinstance(current, dict) else None


def _probe_port(port: int, timeout: float = 0.3) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except Exception:
        return False


if HAS_QT:
    class McpTab(QWidget):
        """MCP Server 管理标签页"""

        def __init__(self, parent=None):
            super().__init__(parent)
            cfg = get_artclaw_config()
            self._t = get_theme(cfg.get("dcc_name", "maya"))
            self._servers: List[McpServerEntry] = []
            self._config_key = ""
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

            # Summary row
            summary_row = QHBoxLayout()
            self._summary_label = QLabel()
            self._summary_label.setStyleSheet(f"color: {t['text']}; font-size: 12px;")
            summary_row.addWidget(self._summary_label)
            summary_row.addStretch()

            btn_add = QPushButton("添加")
            btn_add.setCursor(Qt.PointingHandCursor)
            btn_add.setStyleSheet(
                f"QPushButton {{ background: {t['accent']}; color: #fff;"
                f" border-radius: 3px; padding: 3px 10px; }}"
            )
            btn_add.clicked.connect(self._on_add)
            summary_row.addWidget(btn_add)
            root.addLayout(summary_row)

            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background: {t['border']};")
            root.addWidget(sep)

            # Server list
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
            self._rebuild_list()

        def _load_data(self):
            self._servers.clear()

            # 确定 config key
            ac_cfg = get_artclaw_config()
            config_key = "plugins.entries.mcp-bridge.config.servers"
            mcp_cfg = ac_cfg.get("mcp", {})
            raw_key = mcp_cfg.get("config_key", "")
            if raw_key:
                if raw_key == "mcp.servers":
                    config_key = "plugins.entries.mcp-bridge.config.servers"
                else:
                    config_key = raw_key
            self._config_key = config_key

            # 读取平台配置
            cfg_path = get_openclaw_config_path()
            if not cfg_path or not os.path.exists(cfg_path):
                return

            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    root = json.load(f)
            except Exception:
                return

            servers_obj = _traverse_json_path(root, config_key)
            if not servers_obj or not isinstance(servers_obj, dict):
                return

            for sid, sobj in servers_obj.items():
                if not isinstance(sobj, dict):
                    continue
                entry = McpServerEntry()
                entry.server_id = sid
                entry.display_name = _DISPLAY_NAMES.get(sid, sid)
                entry.type = sobj.get("type", "websocket")
                if entry.type == "stdio":
                    entry.command = sobj.get("command", "")
                    entry.url = entry.command
                else:
                    entry.url = sobj.get("url", "")
                entry.enabled = sobj.get("enabled", True)
                self._servers.append(entry)

            # 端口探测
            for srv in self._servers:
                if srv.type == "stdio":
                    continue
                port = self._extract_port(srv.url)
                if port:
                    srv.connected = _probe_port(port)

            # 本地 MCP tool count
            try:
                from mcp_server import get_mcp_server
                s = get_mcp_server()
                if s:
                    local_count = len(getattr(s, "_tools", []))
                    # 匹配当前 DCC 的 server
                    dcc = ac_cfg.get("dcc_name", "maya")
                    local_ids = {
                        "maya": "maya-primary",
                        "max": "max-primary",
                    }
                    local_id = local_ids.get(dcc)
                    for srv in self._servers:
                        if srv.server_id == local_id:
                            srv.tool_count = local_count
            except Exception:
                pass

        @staticmethod
        def _extract_port(url: str) -> Optional[int]:
            try:
                # ws://127.0.0.1:8081 or http://...
                last_colon = url.rfind(":")
                if last_colon < 0:
                    return None
                port_str = url[last_colon + 1:].split("/")[0]
                return int(port_str)
            except Exception:
                return None

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

            total = len(self._servers)
            conn = sum(1 for s in self._servers if s.connected)
            en = sum(1 for s in self._servers if s.enabled)
            self._summary_label.setText(f"共 {total} 个 MCP Server，{conn} 个已连接，{en} 个已启用")

            for entry in self._servers:
                row = self._make_row(entry)
                layout.addWidget(row)
            layout.addStretch()

        def _make_row(self, s: McpServerEntry) -> QWidget:
            t = self._t
            row = QWidget()
            row.setFixedHeight(52)
            h = QHBoxLayout(row)
            h.setContentsMargins(6, 4, 6, 4)
            h.setSpacing(6)

            opacity = 1.0 if s.enabled else 0.45

            # Enable checkbox
            cb = QCheckBox()
            cb.setChecked(s.enabled)
            cb.stateChanged.connect(lambda state, entry=s: self._on_enable(entry, bool(state)))
            h.addWidget(cb)

            # Connection dot
            if s.type == "stdio":
                dot_char, dot_color = "\u25CB", t["text_dim"]
            elif s.connected:
                dot_char, dot_color = "\u25CF", COLORS["status_connected"]
            else:
                dot_char, dot_color = "\u25CF", COLORS["status_error"]
            dot = QLabel(dot_char)
            dot.setFixedWidth(16)
            dot.setStyleSheet(f"color: {dot_color}; font-size: 14px;")
            h.addWidget(dot)

            # Name + URL/command
            info = QWidget()
            info_l = QVBoxLayout(info)
            info_l.setContentsMargins(0, 0, 0, 0)
            info_l.setSpacing(0)

            name_lbl = QLabel(s.display_name)
            c = t['text'] if opacity == 1.0 else t['text_dim']
            name_lbl.setStyleSheet(f"color: {c}; font-weight: bold; font-size: 12px;")
            info_l.addWidget(name_lbl)

            sub = s.url if s.type != "stdio" else f"$ {s.command}"
            sub_lbl = QLabel(f"{sub}  ({s.type})")
            sub_lbl.setStyleSheet(f"color: {t['text_dim']}; font-size: 10px;")
            info_l.addWidget(sub_lbl)
            h.addWidget(info, 1)

            # Status text
            if s.type == "stdio":
                st_text, st_color = "stdio", "#80A6CC"
            elif s.connected:
                st_text, st_color = "已连接", COLORS["status_connected"]
            else:
                st_text, st_color = "未连接", COLORS["status_error"]
            st_lbl = QLabel(st_text)
            st_lbl.setStyleSheet(f"color: {st_color}; font-size: 11px;")
            h.addWidget(st_lbl)

            # Tool count
            if s.tool_count > 0:
                tc = QLabel(f"{s.tool_count} tools")
                tc.setStyleSheet(f"color: {t['text_dim']}; font-size: 10px; padding-left: 4px;")
                h.addWidget(tc)

            return row

        # ==============================================================
        # Actions
        # ==============================================================

        def _on_enable(self, entry: McpServerEntry, enabled: bool):
            entry.enabled = enabled
            self._set_server_enabled(entry.server_id, enabled)
            self._rebuild_list()

        def _set_server_enabled(self, server_id: str, enabled: bool):
            cfg_path = get_openclaw_config_path()
            if not cfg_path or not os.path.exists(cfg_path):
                return
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    root = json.load(f)
                servers = _traverse_json_path(root, self._config_key)
                if not servers or server_id not in servers:
                    return
                if enabled:
                    servers[server_id].pop("enabled", None)
                else:
                    servers[server_id]["enabled"] = False
                with open(cfg_path, "w", encoding="utf-8") as f:
                    json.dump(root, f, indent=2, ensure_ascii=False)
            except Exception as ex:
                logger.error("设置 MCP 启用状态失败: %s", ex)

        def _on_add(self):
            dlg = _AddServerDialog(self._t, parent=self)
            if dlg.exec_() == QDialog.Accepted:
                sid, stype, url, cmd = dlg.get_values()
                if sid:
                    self._write_new_server(sid, stype, url, cmd)
                    self.refresh()

        def _write_new_server(self, sid: str, stype: str, url: str, command: str):
            cfg_path = get_openclaw_config_path()
            if not cfg_path or not os.path.exists(cfg_path):
                return
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    root = json.load(f)
                servers = _traverse_json_path(root, self._config_key)
                if servers is None:
                    return
                new = {"type": stype}
                if stype == "stdio":
                    new["command"] = command
                else:
                    new["url"] = url
                servers[sid] = new
                with open(cfg_path, "w", encoding="utf-8") as f:
                    json.dump(root, f, indent=2, ensure_ascii=False)
            except Exception as ex:
                logger.error("添加 MCP Server 失败: %s", ex)


    class _AddServerDialog(QDialog):
        """添加 MCP Server 弹窗"""

        def __init__(self, theme, parent=None):
            super().__init__(parent)
            self._t = theme
            self.setWindowTitle("添加 MCP Server")
            self.resize(460, 280)
            self._build_ui()

        def _build_ui(self):
            t = self._t
            root = QVBoxLayout(self)
            root.setContentsMargins(12, 12, 12, 12)
            root.setSpacing(8)

            input_style = (
                f"QLineEdit {{ background: {t['bg_input']}; color: {t['text']};"
                f" border: 1px solid {t['border']}; border-radius: 3px; padding: 4px 8px; }}"
            )
            lbl_style = f"color: {t['text']}; font-size: 11px;"

            desc = QLabel("添加新的 MCP Server 到平台配置")
            desc.setStyleSheet(f"color: {t['text']}; font-size: 12px;")
            root.addWidget(desc)

            # Server ID
            root.addWidget(self._lbl("Server ID", lbl_style))
            self._id_input = QLineEdit()
            self._id_input.setPlaceholderText("my-dcc-agent")
            self._id_input.setStyleSheet(input_style)
            root.addWidget(self._id_input)

            # Type
            type_row = QHBoxLayout()
            type_row.addWidget(self._lbl("类型:", lbl_style))
            self._type_combo = QComboBox()
            self._type_combo.addItems(["websocket", "stdio", "sse"])
            self._type_combo.setStyleSheet(
                f"QComboBox {{ background: {t['bg_input']}; color: {t['text']};"
                f" border: 1px solid {t['border']}; padding: 3px 6px; }}"
            )
            self._type_combo.currentTextChanged.connect(self._on_type_changed)
            type_row.addWidget(self._type_combo)
            type_row.addStretch()
            root.addLayout(type_row)

            # URL (for websocket/sse)
            root.addWidget(self._lbl("URL", lbl_style))
            self._url_input = QLineEdit()
            self._url_input.setPlaceholderText("ws://127.0.0.1:8083")
            self._url_input.setStyleSheet(input_style)
            root.addWidget(self._url_input)

            # Command (for stdio)
            self._cmd_label = self._lbl("Command", lbl_style)
            root.addWidget(self._cmd_label)
            self._cmd_input = QLineEdit()
            self._cmd_input.setPlaceholderText("npx -y @modelcontextprotocol/server-xxx")
            self._cmd_input.setStyleSheet(input_style)
            root.addWidget(self._cmd_input)
            self._cmd_label.hide()
            self._cmd_input.hide()

            root.addStretch()

            # Buttons
            btn_row = QHBoxLayout()
            btn_row.addStretch()

            confirm = QPushButton("确认")
            confirm.setStyleSheet(
                f"QPushButton {{ background: {t['accent']}; color: #fff;"
                f" border-radius: 3px; padding: 4px 14px; }}"
            )
            confirm.clicked.connect(self._on_confirm)
            btn_row.addWidget(confirm)

            cancel = QPushButton("取消")
            cancel.setStyleSheet(
                f"QPushButton {{ background: {t['bg_secondary']}; color: {t['text']};"
                f" border-radius: 3px; padding: 4px 14px; }}"
            )
            cancel.clicked.connect(self.reject)
            btn_row.addWidget(cancel)
            root.addLayout(btn_row)

        def _lbl(self, text, style):
            l = QLabel(text)
            l.setStyleSheet(style)
            return l

        def _on_type_changed(self, text):
            is_stdio = text == "stdio"
            self._url_input.setVisible(not is_stdio)
            self._cmd_label.setVisible(is_stdio)
            self._cmd_input.setVisible(is_stdio)

        def _on_confirm(self):
            sid = self._id_input.text().strip()
            if not sid:
                return
            stype = self._type_combo.currentText()
            if stype == "stdio":
                if not self._cmd_input.text().strip():
                    return
            else:
                if not self._url_input.text().strip():
                    return
            self.accept()

        def get_values(self):
            sid = self._id_input.text().strip()
            stype = self._type_combo.currentText()
            url = self._url_input.text().strip()
            cmd = self._cmd_input.text().strip()
            return sid, stype, url, cmd

else:
    class McpTab:
        pass
