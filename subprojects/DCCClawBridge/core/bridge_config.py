"""
bridge_config.py - ArtClaw Bridge 配置加载
=============================================

平台无关。优先从 ~/.artclaw/config.json 读取平台配置，
回退到平台特定配置文件（如 ~/.openclaw/openclaw.json）。
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

# ---------------------------------------------------------------------------
# 平台默认路径映射
# ---------------------------------------------------------------------------

def _get_lobster_config_path() -> str:
    """获取 LobsterAI 的 openclaw.json 路径（惰性计算）"""
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        appdata = os.path.expanduser("~/AppData/Roaming")
    return os.path.join(appdata, "LobsterAI", "openclaw", "state", "openclaw.json")


def _get_lobster_skills_path() -> str:
    """获取 LobsterAI 的 Skills 安装目录"""
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        appdata = os.path.expanduser("~/AppData/Roaming")
    return os.path.join(appdata, "LobsterAI", "SKILLs")


_PLATFORM_DEFAULTS = {
    "openclaw": {
        "gateway_url": "ws://127.0.0.1:18789",
        "mcp_port": 8080,
        "skills_installed_path": "~/.openclaw/skills",
        "mcp_config_path": "~/.openclaw/openclaw.json",
        "mcp_config_key": "mcp.servers",
    },
    "workbuddy": {
        "gateway_url": "ws://127.0.0.1:18789",
        "mcp_port": 8080,
        "skills_installed_path": "~/.workbuddy/skills",
        "mcp_config_path": "~/.workbuddy/config.json",
        "mcp_config_key": "mcpServers",
    },
    "claude": {
        "gateway_url": "",
        "mcp_port": 8080,
        "skills_installed_path": "~/.claude/skills",
        "mcp_config_path": "~/.claude/config.json",
        "mcp_config_key": "mcpServers",
    },
    "lobster": {
        "gateway_url": "ws://127.0.0.1:18790",
        "mcp_port": 8080,
        "skills_installed_path": _get_lobster_skills_path(),
        "mcp_config_path": _get_lobster_config_path(),
        "mcp_config_key": "plugins.entries.mcp-bridge.config.servers",
    },
}


def load_artclaw_config() -> dict:
    """读取 ~/.artclaw/config.json（ArtClaw 统一配置）"""
    config_path = os.path.expanduser("~/.artclaw/config.json")
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_platform_type() -> str:
    """获取当前平台类型，默认 'openclaw'"""
    return load_artclaw_config().get("platform", {}).get("type", "openclaw")


def get_platform_defaults(platform_type: str = "") -> dict:
    """获取指定平台的默认配置"""
    pt = platform_type or get_platform_type()
    return _PLATFORM_DEFAULTS.get(pt, _PLATFORM_DEFAULTS["openclaw"])


def _resolve_platform_config_path() -> str:
    """
    解析平台特定配置文件路径。
    优先从 artclaw config.json 的 mcp.config_path 读取，
    回退到平台默认路径。
    """
    ac = load_artclaw_config()
    # 优先用 artclaw 配置中的 mcp.config_path
    mcp_cfg_path = ac.get("mcp", {}).get("config_path", "")
    if mcp_cfg_path:
        return os.path.expanduser(mcp_cfg_path)
    # 回退到平台默认
    pt = ac.get("platform", {}).get("type", "openclaw")
    defaults = get_platform_defaults(pt)
    return os.path.expanduser(defaults["mcp_config_path"])


def load_config() -> dict:
    """
    加载平台特定配置文件（如 openclaw.json）。
    路径通过 artclaw config 或平台默认值确定。
    """
    config_path = _resolve_platform_config_path()
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_gateway_config() -> dict:
    """获取 gateway 子配置（优先 artclaw config，回退平台配置文件）"""
    # 优先从 artclaw config 读取 gateway_url
    ac = load_artclaw_config()
    platform_cfg = ac.get("platform", {})
    if platform_cfg.get("gateway_url"):
        return {
            "url": platform_cfg["gateway_url"],
            "auth": load_config().get("gateway", {}).get("auth", {}),
            "port": int(platform_cfg["gateway_url"].split(":")[-1]) if ":" in platform_cfg.get("gateway_url", "") else 18789,
        }
    return load_config().get("gateway", {})


def get_skills_installed_path() -> str:
    """
    获取已安装 Skill 目录路径。
    优先从 artclaw config.json 的 skills.installed_path 读取，
    回退到平台默认值。
    """
    ac = load_artclaw_config()
    path = ac.get("skills", {}).get("installed_path", "")
    if path:
        return os.path.expanduser(path)
    defaults = get_platform_defaults()
    return os.path.expanduser(defaults["skills_installed_path"])


def get_mcp_config_info() -> dict:
    """
    获取 MCP 配置文件信息。
    返回 {"config_path": str, "config_key": str}
    """
    ac = load_artclaw_config()
    mcp = ac.get("mcp", {})
    defaults = get_platform_defaults()
    return {
        "config_path": os.path.expanduser(mcp.get("config_path", defaults["mcp_config_path"])),
        "config_key": mcp.get("config_key", defaults["mcp_config_key"]),
    }


def get_platform_config_path() -> str:
    """获取平台配置文件路径（如 ~/.openclaw/openclaw.json）"""
    return _resolve_platform_config_path()
