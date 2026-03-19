"""
bridge_config.py - OpenClaw Bridge 配置加载
=============================================

平台无关。从 ~/.openclaw/openclaw.json 读取 Gateway 配置。
"""

import json
import os

# ---------------------------------------------------------------------------
# 协议常量
# ---------------------------------------------------------------------------

DEFAULT_GATEWAY_URL = "ws://127.0.0.1:18789"
DEFAULT_AGENT_ID = "qi"
DEFAULT_TOKEN = "ec8900cf3e3c4bbfab43c8d7d5a4638c69b854e075902325"
PROTOCOL_VERSION = 3

# Gateway 对 client.id 有严格白名单校验
CLIENT_NAME = "cli"
CLIENT_VERSION = "0.1.0"


def load_config() -> dict:
    """从 ~/.openclaw/openclaw.json 读取配置"""
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_gateway_config() -> dict:
    """获取 gateway 子配置"""
    return load_config().get("gateway", {})
