"""
bridge_config.py - ArtClaw Bridge 配置加载
=============================================

平台无关。优先从 ~/.artclaw/config.json 读取平台配置，
回退到平台特定配置文件（如 ~/.openclaw/openclaw.json）。
"""

import json
import os
import socket
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# 协议常量
# ---------------------------------------------------------------------------

DEFAULT_GATEWAY_URL = "ws://127.0.0.1:18789"
# Agent ID / Token 不硬编码 — 每台机器的 OpenClaw 配置不同
# 运行时通过 get_default_agent_id() / get_gateway_token() 动态读取
DEFAULT_AGENT_ID = ""
DEFAULT_TOKEN = ""
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
        "display_name": "OpenClaw",
        "gateway_url": "ws://127.0.0.1:18789",
        "mcp_port": 8080,
        "visible": True,
        "skills_installed_path": "~/.openclaw/workspace/skills",
        "mcp_config_path": "~/.openclaw/openclaw.json",
        "mcp_config_key": "mcp.servers",
    },
    "workbuddy": {
        "display_name": "WorkBuddy",
        "gateway_url": "",
        "mcp_port": 8080,
        "visible": False,
        "skills_installed_path": "~/.workbuddy/skills",
        "mcp_config_path": "~/.workbuddy/config.json",
        "mcp_config_key": "mcpServers",
    },
    "claudecode": {
        "display_name": "Claude Code",
        "gateway_url": "",
        "mcp_port": 8080,
        "visible": False,
        "skills_installed_path": "~/.claude/skills",
        "mcp_config_path": "~/.claude.json",
        "mcp_config_key": "mcpServers",
    },
    "cursor": {
        "display_name": "Cursor",
        "gateway_url": "",
        "mcp_port": 8080,
        "visible": False,
        "skills_installed_path": "~/.cursor/skills",
        "mcp_config_path": "~/.cursor/mcp.json",
        "mcp_config_key": "mcpServers",
    },
    "lobster": {
        "display_name": "LobsterAI",
        "gateway_url": "ws://127.0.0.1:18794",
        "mcp_port": 8080,
        "visible": True,
        "skills_installed_path": _get_lobster_skills_path(),
        "mcp_config_path": _get_lobster_config_path(),
        "mcp_config_key": "plugins.entries.mcp-bridge.config.servers",
    },
}


def _get_artclaw_config_path() -> str:
    """返回 ~/.artclaw/config.json 路径（全平台统一）。"""
    return os.path.expanduser("~/.artclaw/config.json")


def load_artclaw_config() -> dict:
    """读取 ~/.artclaw/config.json（ArtClaw 统一配置）"""
    config_path = _get_artclaw_config_path()
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


# ---------------------------------------------------------------------------
# Skill 检查目录 API（平台侧统一查询接口）
# ---------------------------------------------------------------------------

def get_skill_checker_dirs() -> dict:
    """
    返回当前平台下 Skill 检查所需的全部目录信息。

    此函数是平台侧插件向检查工具（skill-version-checker、Tool Manager）
    提供目录信息的统一 API。所有需要检查的路径由平台插件的
    _PLATFORM_DEFAULTS 和用户配置决定，检查工具不得硬编码任何路径。

    返回结构::

        {
            "platform_type": "openclaw",          # 当前平台
            "skills_installed_path": "/abs/path", # 已安装 Skill 目录
            "project_root": "/abs/path",          # 项目源码根目录（可能为 ""）
            "dcc_install_dirs": [                 # 各 DCC 安装副本目录
                {
                    "label": "Maya 2024",
                    "dcc": "maya",
                    "path": "/abs/path/to/DCCClawBridge",
                    "install_path": "/abs/path/to/maya/scripts/DCCClawBridge",
                },
                ...
            ],
            "core_module_copies": [               # 核心模块的各副本位置
                {
                    "label": "DCC core",
                    "src": "/abs/path/core/skill_sync.py",
                    "dst": "/abs/path/DCCClawBridge/core/skill_sync.py",
                },
                ...
            ],
        }

    Notes:
        - 所有路径均为绝对路径（已展开 ~）。
        - 若路径不存在，照常返回（调用方自行判断）。
        - DCC 安装目录通过自动检测得到，未安装的 DCC 不会出现在列表中。
    """
    ac = load_artclaw_config()
    platform_type = ac.get("platform", {}).get("type", "openclaw")
    project_root = ac.get("project_root", "")
    skills_installed = get_skills_installed_path()

    result = {
        "platform_type": platform_type,
        "skills_installed_path": skills_installed,
        "project_root": project_root,
        "dcc_install_dirs": [],
        "core_module_copies": [],
    }

    if not project_root:
        return result

    pr = Path(project_root)
    dcc_src = pr / "subprojects" / "DCCClawBridge"
    ue_py = pr / "subprojects" / "UEDAgentProj" / "Plugins" / "UEClawBridge" / "Content" / "Python"

    # ── Core module copies ──────────────────────────────────────────────
    CORE_MODULES = ["skill_sync.py", "bridge_core.py", "bridge_config.py", "memory_core.py", "tool_manager_launcher.py", "device_auth.py"]
    for mod in CORE_MODULES:
        src = pr / "core" / mod
        result["core_module_copies"].append({
            "label": f"core → DCC  {mod}", "src": str(src),
            "dst": str(dcc_src / "core" / mod),
        })
        result["core_module_copies"].append({
            "label": f"core → UE   {mod}", "src": str(src),
            "dst": str(ue_py / mod),
        })

    # ── DCC install dirs（自动检测） ──────────────────────────────────────
    import os as _os

    # Maya
    maya_base = Path(_os.path.expanduser("~/Documents/maya"))
    if maya_base.exists():
        ver_dirs = sorted(
            [d for d in maya_base.iterdir() if d.is_dir() and d.name.isdigit()],
            key=lambda d: d.name, reverse=True,
        )
        for vd in ver_dirs[:2]:  # 检查最近两个版本
            scripts = vd / "scripts" / "DCCClawBridge"
            if scripts.exists():
                result["dcc_install_dirs"].append({
                    "label": f"Maya {vd.name}",
                    "dcc": "maya",
                    "path": str(dcc_src),
                    "install_path": str(scripts),
                })
            for locale_d in sorted(vd.iterdir()):
                if locale_d.is_dir() and "_" in locale_d.name and locale_d.name[0].islower():
                    lscripts = locale_d / "scripts" / "DCCClawBridge"
                    if lscripts.exists():
                        result["dcc_install_dirs"].append({
                            "label": f"Maya {vd.name}/{locale_d.name}",
                            "dcc": "maya",
                            "path": str(dcc_src),
                            "install_path": str(lscripts),
                        })

    # 3ds Max
    max_base = Path(_os.path.expanduser("~/AppData/Roaming/Autodesk"))
    if max_base.exists():
        for entry in sorted(max_base.iterdir(), reverse=True):
            if entry.is_dir() and entry.name.startswith("3dsMax"):
                scripts = entry / "scripts" / "DCCClawBridge"
                if scripts.exists():
                    result["dcc_install_dirs"].append({
                        "label": f"3ds Max {entry.name}",
                        "dcc": "max",
                        "path": str(dcc_src),
                        "install_path": str(scripts),
                    })
                    break

    # Blender
    bl_base = Path(_os.path.expanduser("~/AppData/Roaming/Blender Foundation/Blender"))
    if not bl_base.exists():
        bl_base = Path(_os.path.expanduser("~/.config/blender"))
    if bl_base.exists():
        for vd in sorted(bl_base.iterdir(), reverse=True):
            addon = vd / "scripts" / "addons" / "artclaw_bridge"
            if addon.exists():
                result["dcc_install_dirs"].append({
                    "label": f"Blender {vd.name}",
                    "dcc": "blender",
                    "path": str(dcc_src),
                    "install_path": str(addon),
                })
                break

    # Houdini
    docs = Path(_os.path.expanduser("~/Documents"))
    if docs.exists():
        for entry in sorted(docs.iterdir(), reverse=True):
            if entry.is_dir() and entry.name.startswith("houdini"):
                dcc_dir = entry / "scripts" / "python" / "DCCClawBridge"
                if dcc_dir.exists():
                    result["dcc_install_dirs"].append({
                        "label": f"Houdini {entry.name}",
                        "dcc": "houdini",
                        "path": str(dcc_src),
                        "install_path": str(dcc_dir),
                    })
                    break

    # Substance Painter
    sp_dir = Path(_os.path.expanduser(
        "~/Documents/Adobe/Adobe Substance 3D Painter/python/plugins/artclaw_bridge"))
    if sp_dir.exists():
        result["dcc_install_dirs"].append({
            "label": "Substance Painter",
            "dcc": "sp",
            "path": str(dcc_src),
            "install_path": str(sp_dir),
        })

    # Substance Designer
    sd_dir = Path(_os.path.expanduser(
        "~/Documents/Adobe/Adobe Substance 3D Designer/python/sduserplugins/artclaw_bridge"))
    if sd_dir.exists():
        result["dcc_install_dirs"].append({
            "label": "Substance Designer",
            "dcc": "sd",
            "path": str(dcc_src),
            "install_path": str(sd_dir),
        })

    # ComfyUI
    comfyui_dirs = [
        Path(_os.path.expanduser("~/ComfyUI/custom_nodes/artclaw_bridge")),
        Path(_os.path.expanduser("~/Desktop/ComfyUI/custom_nodes/artclaw_bridge")),
    ]
    # 也从 artclaw config 读取 ComfyUI 路径
    comfyui_custom_path = ac.get("comfyui", {}).get("custom_nodes_path", "")
    if comfyui_custom_path:
        comfyui_dirs.insert(0, Path(_os.path.expanduser(comfyui_custom_path)) / "artclaw_bridge")
    for cu_dir in comfyui_dirs:
        if cu_dir.exists():
            result["dcc_install_dirs"].append({
                "label": "ComfyUI",
                "dcc": "comfyui",
                "path": str(dcc_src),
                "install_path": str(cu_dir),
            })
            break

    return result


def get_gateway_url() -> str:
    """获取 Gateway WebSocket URL。

    优先级:
    1. ~/.artclaw/config.json → platform.gateway_url
    2. 平台配置文件 → gateway.port（OpenClaw 格式）
    3. gateway-port.json（LobsterAI 等平台格式）
    4. 动态端口检测（detect_gateway_port；检测成功则自动保存到配置）
    5. _PLATFORM_DEFAULTS 中的默认值
    """
    ac = load_artclaw_config()

    # 1. artclaw config 直读
    platform_url = ac.get("platform", {}).get("gateway_url", "")
    if platform_url:
        return platform_url

    # 2. 平台配置文件 → gateway.port（OpenClaw 格式）
    config = load_config()
    port = config.get("gateway", {}).get("port")
    if port:
        return f"ws://127.0.0.1:{port}"

    # 3. gateway-port.json（同目录下的端口文件）
    config_path = _resolve_platform_config_path()
    port_json = os.path.join(os.path.dirname(config_path), "gateway-port.json")
    if os.path.exists(port_json):
        try:
            with open(port_json, "r", encoding="utf-8") as f:
                port_data = json.load(f)
            port = port_data.get("port")
            if port:
                return f"ws://127.0.0.1:{port}"
        except Exception:
            pass

    # 4. 动态端口检测（检测成功自动保存，下次启动直接用）
    current_pt = ac.get("platform", {}).get("type", "openclaw")
    detected_port = detect_gateway_port(current_pt)
    if detected_port is not None:
        url = f"ws://127.0.0.1:{detected_port}"
        update_platform_gateway_url(current_pt, url)
        return url

    # 5. 平台默认值
    defaults = get_platform_defaults()
    return defaults.get("gateway_url", DEFAULT_GATEWAY_URL)


def get_gateway_token() -> str:
    """获取 Gateway 认证 Token。

    优先级:
    1. ~/.artclaw/config.json → platform.token
    2. 平台配置文件 → gateway.auth.token（OpenClaw 格式）
    3. gateway-token 文件（同目录下的纯文本 token）
    4. 硬编码默认值
    """
    ac = load_artclaw_config()

    # 1. artclaw config 直读
    token = ac.get("platform", {}).get("token", "")
    if token:
        return token

    # 2. 平台配置文件 → gateway.auth.token
    config = load_config()
    token = config.get("gateway", {}).get("auth", {}).get("token", "")
    if token:
        return token

    # 3. gateway-token 文件（LobsterAI 等平台格式）
    config_path = _resolve_platform_config_path()
    token_file = os.path.join(os.path.dirname(config_path), "gateway-token")
    if os.path.exists(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                token = f.read().strip()
            if token:
                return token
        except Exception:
            pass

    return DEFAULT_TOKEN


def get_default_agent_id() -> str:
    """获取默认 Agent ID。

    优先级:
    1. ~/.artclaw/config.json → last_agent_id（上次使用的 Agent）
    2. 平台配置文件 → agents.list[0].id（第一个注册的 Agent）
    3. 空串（由 Gateway 使用默认 Agent 路由）
    """
    ac = load_artclaw_config()

    # 1. artclaw config 直读（DCC 切换 Agent 时会保存到这里）
    last = ac.get("last_agent_id", "")
    if last:
        return last

    # 2. 平台配置文件 → agents.list 第一个
    config = load_config()
    agents_list = config.get("agents", {}).get("list", [])
    if agents_list:
        first_id = agents_list[0].get("id", "")
        if first_id:
            return first_id

    return DEFAULT_AGENT_ID


# ---------------------------------------------------------------------------
# 平台注册与切换 API（UI ComboBox 数据源 + 热切换）
# ---------------------------------------------------------------------------

def check_platform_configured(platform_type: str) -> bool:
    """检查指定平台是否已配置（配置文件/工具是否存在）。

    仅做本地文件/工具检测，不做网络探测。
    """
    import shutil

    if platform_type == "openclaw":
        return os.path.exists(os.path.expanduser("~/.openclaw/openclaw.json"))
    elif platform_type == "lobster":
        return os.path.exists(_get_lobster_config_path())
    elif platform_type == "claudecode":
        return (
            shutil.which("claude") is not None
            or os.path.exists(os.path.expanduser("~/.claude.json"))
            or os.path.isdir(os.path.expanduser("~/.claude"))
        )
    elif platform_type == "cursor":
        return (
            os.path.exists(os.path.expanduser("~/.cursor/mcp.json"))
            or os.path.isdir(os.path.expanduser("~/.cursor"))
        )
    elif platform_type == "workbuddy":
        return os.path.exists(os.path.expanduser("~/.workbuddy/config.json"))
    return False


def get_available_platforms() -> list:
    """返回已注册的可用平台列表（UI ComboBox 数据源）。

    数据来源优先级:
    1. config.json → platforms_registry（install 脚本或用户手动注册）
    2. _PLATFORM_DEFAULTS keys（fallback）

    返回 [{"type": "openclaw", "display_name": "OpenClaw", "gateway_url": "ws://...", "configured": True/False}, ...]
    """
    ac = load_artclaw_config()
    registry = ac.get("platforms_registry", [])
    if registry:
        result = []
        for entry in registry:
            p_type = entry.get("type", "")
            defaults = _PLATFORM_DEFAULTS.get(p_type, {})
            if not defaults.get("visible", True):
                continue
            entry["configured"] = check_platform_configured(p_type)
            result.append(entry)
        return result

    # fallback: 从默认配置生成（包含所有 visible=True 的平台）
    result = []
    for k, v in _PLATFORM_DEFAULTS.items():
        if not v.get("visible", True):
            continue
        result.append({
            "type": k,
            "display_name": v.get("display_name", k.title()),
            "gateway_url": v.get("gateway_url", ""),
            "configured": check_platform_configured(k),
        })
    return result


def switch_platform(platform_type: str) -> bool:
    """切换到指定平台，更新 config.json。

    自动解析目标平台的 gateway_url 和 token:
    - 优先从 platforms_registry 读取（含用户填写的 token 等）
    - 回退到 _PLATFORM_DEFAULTS
    - 自动探测 gateway-port.json / gateway-token 文件

    调用方负责断开旧连接 + 重新连接。
    返回 True 表示配置已更新。
    """
    ac = load_artclaw_config()

    # 从注册表获取目标平台信息
    registry = {p["type"]: p for p in ac.get("platforms_registry", [])}
    target = registry.get(platform_type, {})
    defaults = get_platform_defaults(platform_type)

    # 解析 gateway_url
    gateway_url = target.get("gateway_url") or defaults.get("gateway_url", "")

    # 如果没有显式 URL，尝试从目标平台的 gateway-port.json 读取
    if not gateway_url:
        target_config_path = os.path.expanduser(defaults.get("mcp_config_path", ""))
        if target_config_path:
            port_json = os.path.join(os.path.dirname(target_config_path), "gateway-port.json")
            if os.path.exists(port_json):
                try:
                    with open(port_json, "r", encoding="utf-8") as f:
                        port = json.load(f).get("port")
                    if port:
                        gateway_url = f"ws://127.0.0.1:{port}"
                except Exception:
                    pass

    # 解析 token
    token = target.get("token", "")
    if not token:
        # 尝试从目标平台配置文件读取
        target_config_path = os.path.expanduser(defaults.get("mcp_config_path", ""))
        if target_config_path and os.path.exists(target_config_path):
            try:
                with open(target_config_path, "r", encoding="utf-8") as f:
                    target_cfg = json.load(f)
                token = target_cfg.get("gateway", {}).get("auth", {}).get("token", "")
            except Exception:
                pass
        # fallback: gateway-token 文件
        if not token and target_config_path:
            token_file = os.path.join(os.path.dirname(target_config_path), "gateway-token")
            if os.path.exists(token_file):
                try:
                    with open(token_file, "r", encoding="utf-8") as f:
                        token = f.read().strip()
                except Exception:
                    pass

    # 更新 config
    ac["platform"] = {
        "type": platform_type,
        "gateway_url": gateway_url,
        "token": token,
        "mcp_port": defaults.get("mcp_port", 8080),
    }

    # 同步更新 mcp/skills 路径
    ac.setdefault("mcp", {})["config_path"] = defaults.get("mcp_config_path", "")
    ac.setdefault("mcp", {})["config_key"] = defaults.get("mcp_config_key", "")
    ac.setdefault("skills", {})["installed_path"] = defaults.get("skills_installed_path", "")

    _save_artclaw_config(ac)
    return True


def _save_artclaw_config(config: dict) -> None:
    """原子写入 ~/.artclaw/config.json。"""
    import tempfile
    config_dir = os.path.join(os.path.expanduser("~"), ".artclaw")
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, "config.json")
    try:
        fd, tmp = tempfile.mkstemp(dir=config_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            os.replace(tmp, config_path)
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 动态网关端口检测
# ---------------------------------------------------------------------------

def _is_port_listening(host: str, port: int, timeout: float = 0.5) -> bool:
    """检查指定 host:port 是否正在监听（TCP 连接探测）。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def _try_read_gateway_port_json(config_dir: str) -> int | None:
    """
    从给定目录读取 gateway-port.json，返回端口号或 None。

    支持两种文件名: gateway-port.json（新）和 gateway_port.json（旧）。
    """
    for fname in ("gateway-port.json", "gateway_port.json"):
        port_json = os.path.join(config_dir, fname)
        if os.path.isfile(port_json):
            try:
                with open(port_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                port = data.get("port")
                if port and isinstance(port, int):
                    return port
            except Exception:
                continue
    return None


def _find_process_listening_port(process_name: str, host: str = "127.0.0.1",
                                  port_range: tuple = (18780, 18810)) -> int | None:
    """
    通过扫描已知端口范围来检测进程是否在监听。

    这是后备方案：当无法读取配置文件时，通过主动端口探测定位网关。
    不需要读取 /proc 或调用 ps（避免跨平台兼容问题）。
    """
    for port in range(port_range[0], port_range[1] + 1):
        if _is_port_listening(host, port):
            return port
    return None


def detect_gateway_port(platform_type: str) -> int | None:
    """
    动态检测实际运行的网关端口。

    检测策略（按优先级）:

    1. **gateway-port.json**：
       - LobsterAI: %APPDATA%/LobsterAI/openclaw/state/gateway-port.json
       - OpenClaw: ~/.openclaw/state/gateway-port.json
       文件内容如 {"port": 18794}

    2. **配置文件 gateway.port**：
       从平台配置文件的 gateway.port 字段读取（OpenClaw 格式）

    3. **端口扫描**：
       在已知端口范围内（18780-18810）探测 127.0.0.1 上的 TCP 监听端口

    Args:
        platform_type: 平台类型字符串（'openclaw', 'lobster', 等）

    Returns:
        检测到的端口号，或 None（如果未找到）
    """
    defaults = get_platform_defaults(platform_type)
    mcp_config_path = defaults.get("mcp_config_path", "")

    # ── Strategy 1: gateway-port.json ──────────────────────────────
    if mcp_config_path:
        expanded = os.path.expanduser(mcp_config_path)
        config_dir = os.path.dirname(expanded)
        if config_dir:
            port = _try_read_gateway_port_json(config_dir)
            if port is not None and _is_port_listening("127.0.0.1", port):
                return port

    # ── Strategy 2: 配置文件 gateway.port ──────────────────────────
    if mcp_config_path:
        expanded = os.path.expanduser(mcp_config_path)
        if os.path.isfile(expanded):
            try:
                with open(expanded, "r", encoding="utf-8") as f:
                    platform_cfg = json.load(f)
                port = platform_cfg.get("gateway", {}).get("port")
                if port and isinstance(port, int) and port > 0:
                    if _is_port_listening("127.0.0.1", port):
                        return port
            except Exception:
                pass

    # ── Strategy 3: openclaw gateway status (命令行探测) ───────────
    # 仅对 openclaw 平台尝试
    if platform_type == "openclaw":
        try:
            result = subprocess.run(
                ["openclaw", "gateway", "status"],
                capture_output=True, text=True, timeout=5,
                cwd=os.path.expanduser("~"),
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if ":" in line and "127.0.0.1" in line:
                        # 解析类似 "url: ws://127.0.0.1:18789" 的行
                        parts = line.split(":")
                        if parts:
                            last_part = parts[-1].strip()
                            try:
                                port = int(last_part)
                                if _is_port_listening("127.0.0.1", port):
                                    return port
                            except ValueError:
                                pass
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

    # ── Strategy 4: 端口范围扫描 ──────────────────────────────────
    port = _find_process_listening_port(
        "LobsterAI" if platform_type == "lobster" else platform_type,
        host="127.0.0.1",
        port_range=(18780, 18810),
    )
    if port is not None:
        return port

    # ── Final: 端口范围扩展扫描 ────────────────────────────────────
    # 如果常见范围没找到，尝试直接探测默认端口
    default_url = defaults.get("gateway_url", "")
    if default_url and ":" in default_url:
        try:
            default_port = int(default_url.rsplit(":", 1)[-1])
            if _is_port_listening("127.0.0.1", default_port):
                return default_port
        except (ValueError, IndexError):
            pass

    return None


# ---------------------------------------------------------------------------
# 配置更新 API
# ---------------------------------------------------------------------------

def update_platform_gateway_url(platform_type: str, new_url: str) -> bool:
    """
    将新的网关 URL 保存到 ~/.artclaw/config.json。

    更新位置:
    - config['platform']['gateway_url']
    - config['platforms_registry'] 中匹配 platform_type 的条目

    Args:
        platform_type: 平台类型字符串
        new_url: 新的 WebSocket URL（如 "ws://127.0.0.1:18794"）

    Returns:
        True 表示保存成功
    """
    try:
        ac = load_artclaw_config()

        # 更新 platform 节
        ac.setdefault("platform", {})[("gateway_url")] = new_url
        ac["platform"]["type"] = ac["platform"].get("type", platform_type)

        # 同步更新 platforms_registry
        registry = ac.get("platforms_registry", [])
        found = False
        for entry in registry:
            if entry.get("type") == platform_type:
                entry["gateway_url"] = new_url
                found = True
                break
        if not found:
            defaults = get_platform_defaults(platform_type)
            registry.append({
                "type": platform_type,
                "display_name": defaults.get("display_name", platform_type.title()),
                "gateway_url": new_url,
            })
            ac["platforms_registry"] = registry

        _save_artclaw_config(ac)
        return True
    except Exception:
        return False


def update_platform_mcp_port(platform_type: str, new_port: int) -> bool:
    """
    将新的 MCP 端口保存到 ~/.artclaw/config.json。

    更新位置: config['platform']['mcp_port']

    Args:
        platform_type: 平台类型字符串
        new_port: 新的 MCP 端口号

    Returns:
        True 表示保存成功
    """
    try:
        ac = load_artclaw_config()
        ac.setdefault("platform", {})[("mcp_port")] = new_port
        ac["platform"]["type"] = ac["platform"].get("type", platform_type)
        _save_artclaw_config(ac)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Tool Manager UI 数据源
# ---------------------------------------------------------------------------

def get_all_platforms_config() -> list[dict]:
    """
    返回所有平台的当前配置（供 Tool Manager UI 使用）。

    对每个已注册/已知的平台，返回:
    - type: 平台类型标识
    - display_name: 显示名称
    - gateway_url: 当前配置的网关 URL
    - detected_port: 动态检测到的端口（可能为 null）
    - configured: 平台是否已安装/配置
    - mcp_port: MCP 服务端口

    Returns:
        [{type, display_name, gateway_url, detected_port, configured, mcp_port}, ...]
    """
    ac = load_artclaw_config()
    registry = ac.get("platforms_registry", [])
    result = []

    if registry:
        for entry in registry:
            p_type = entry.get("type", "")
            defaults = _PLATFORM_DEFAULTS.get(p_type, {})
            if not defaults.get("visible", True):
                continue

            detected = detect_gateway_port(p_type)
            result.append({
                "type": p_type,
                "display_name": entry.get("display_name", defaults.get("display_name", p_type.title())),
                "gateway_url": entry.get("gateway_url", defaults.get("gateway_url", "")),
                "detected_port": detected,
                "configured": check_platform_configured(p_type),
                "mcp_port": entry.get("mcp_port", defaults.get("mcp_port", 8080)),
            })
    else:
        # Fallback: 从 _PLATFORM_DEFAULTS 生成
        current_type = ac.get("platform", {}).get("type", "openclaw")
        for k, v in _PLATFORM_DEFAULTS.items():
            if not v.get("visible", True):
                continue
            detected = detect_gateway_port(k)
            gateway_url = v.get("gateway_url", "")
            # 如果当前平台就是它，从 artclaw config 读取覆盖
            if k == current_type:
                platform_cfg = ac.get("platform", {})
                gateway_url = platform_cfg.get("gateway_url", gateway_url)

            result.append({
                "type": k,
                "display_name": v.get("display_name", k.title()),
                "gateway_url": gateway_url,
                "detected_port": detected,
                "configured": check_platform_configured(k),
                "mcp_port": v.get("mcp_port", 8080),
            })

    return result


def detect_and_save_gateway_port(platform_type: str) -> str:
    """
    自动检测网关端口并保存到配置。

    这是 UI "Auto Detect" 按钮对应的后端函数。
    检测到端口后自动写入 ~/.artclaw/config.json，下次启动即可直接使用。

    Args:
        platform_type: 平台类型字符串

    Returns:
        格式化的网关 URL（如 "ws://127.0.0.1:18794"），或空字符串（检测失败）
    """
    port = detect_gateway_port(platform_type)
    if port is None:
        defaults = get_platform_defaults(platform_type)
        return defaults.get("gateway_url", "")

    url = f"ws://127.0.0.1:{port}"
    update_platform_gateway_url(platform_type, url)
    return url
