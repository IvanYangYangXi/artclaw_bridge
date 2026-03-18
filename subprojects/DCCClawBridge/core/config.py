"""
config.py - DCCClawBridge 配置管理
===================================

管理端口、路径、偏好等配置。
"""

from __future__ import annotations

import json
import os
from typing import Optional

# 默认 MCP Server 端口（UE 用 8080，Maya 从 8081 开始）
DEFAULT_MCP_PORT = 8081

# 默认数据目录（在 DCC 用户目录下）
DEFAULT_DATA_DIR_NAME = "ArtClaw"


def get_data_dir(dcc_name: str = "maya", dcc_version: str = "") -> str:
    """
    获取 ArtClaw 数据目录。

    Maya: ~/Documents/maya/2023/ArtClaw/
    Max:  ~/Documents/3dsMax/2024/ArtClaw/
    """
    home = os.path.expanduser("~")

    if dcc_name == "maya" and dcc_version:
        base = os.path.join(home, "Documents", "maya", dcc_version)
    elif dcc_name == "max" and dcc_version:
        base = os.path.join(home, "Documents", "3dsMax", dcc_version)
    else:
        base = os.path.join(home, ".artclaw")

    data_dir = os.path.join(base, DEFAULT_DATA_DIR_NAME)
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_config_path(dcc_name: str = "maya", dcc_version: str = "") -> str:
    """获取配置文件路径"""
    return os.path.join(get_data_dir(dcc_name, dcc_version), "config.json")


def load_config(dcc_name: str = "maya", dcc_version: str = "") -> dict:
    """加载配置"""
    path = get_config_path(dcc_name, dcc_version)
    if not os.path.exists(path):
        return _default_config()
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
        # 合并默认值
        defaults = _default_config()
        for key, val in defaults.items():
            if key not in config:
                config[key] = val
        return config
    except Exception:
        return _default_config()


def save_config(config: dict, dcc_name: str = "maya", dcc_version: str = ""):
    """保存配置"""
    path = get_config_path(dcc_name, dcc_version)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def _default_config() -> dict:
    return {
        "mcp_port": DEFAULT_MCP_PORT,
        "auto_connect": True,
        "language": "zh",
        "theme": "auto",  # "auto" | "dark" | "light"
        "font_size": 12,
    }
