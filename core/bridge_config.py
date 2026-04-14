"""
bridge_config.py - ArtClaw Bridge 配置加载
=============================================

平台无关。优先从 ~/.artclaw/config.json 读取平台配置，
回退到平台特定配置文件（如 ~/.openclaw/openclaw.json）。
"""

import json
import os
from pathlib import Path

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
    CORE_MODULES = ["skill_sync.py", "bridge_core.py", "bridge_config.py", "memory_core.py"]
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
    4. _PLATFORM_DEFAULTS 中的默认值
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

    # 4. 平台默认值
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


# ---------------------------------------------------------------------------
# 平台注册与切换 API（UI ComboBox 数据源 + 热切换）
# ---------------------------------------------------------------------------

def get_available_platforms() -> list:
    """返回已注册的可用平台列表（UI ComboBox 数据源）。

    数据来源优先级:
    1. config.json → platforms_registry（install 脚本或用户手动注册）
    2. _PLATFORM_DEFAULTS keys（fallback）

    返回 [{"type": "openclaw", "display_name": "OpenClaw", "gateway_url": "ws://..."}, ...]
    """
    ac = load_artclaw_config()
    registry = ac.get("platforms_registry", [])
    if registry:
        return registry

    # fallback: 从默认配置生成（排除无 gateway 的平台如 claude）
    result = []
    for k, v in _PLATFORM_DEFAULTS.items():
        gw = v.get("gateway_url", "")
        if gw:
            result.append({
                "type": k,
                "display_name": k.title(),
                "gateway_url": gw,
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
