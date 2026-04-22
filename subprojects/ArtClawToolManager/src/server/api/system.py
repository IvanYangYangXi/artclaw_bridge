# Ref: docs/api/api-design.md#SystemAPI
"""System status and configuration endpoints."""

from __future__ import annotations

import json
import os
import platform
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from ..core.config import settings
from ..schemas.common import ok
from ..services.config_manager import ConfigManager
from ..services.skill_service import SkillService

router = APIRouter()

# DCC display metadata (id → name, icon)
_DCC_META = {
    "ue57":     ("UE5",     "🎮"),
    "maya2024": ("Maya",    "🗿"),
    "max2024":  ("3ds Max", "📐"),
    "blender":  ("Blender", "🧊"),
    "houdini":  ("Houdini", "🌊"),
    "sp":       ("SP",      "🖌️"),
    "sd":       ("SD",      "🎯"),
    "comfyui":  ("ComfyUI", "🎨"),
}

# Module-level singletons
_config = ConfigManager()
_skill_svc = SkillService(_config)


@router.get("/status")
async def get_system_status():
    """Return high-level system state."""
    # Count skills from filesystem scan
    items, _ = _skill_svc.list_skills(limit=9999)
    total = len(items)
    installed = sum(1 for s in items if s.status == "installed")
    disabled = sum(1 for s in items if s.status == "disabled")

    return ok({
        "version": settings.APP_VERSION,
        "status": "running",
        "uptime": None,  # placeholder
        "platform": platform.system(),
        "python": platform.python_version(),
        "data_dir": str(settings.data_path),
        "skills_dir": str(settings.skills_path),
        "stats": {
            "totalSkills": total,
            "installedSkills": installed,
            "disabledSkills": disabled,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@router.get("/config")
async def get_system_config():
    """Return current application configuration (safe subset)."""
    return ok({
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "data_dir": str(settings.data_path),
        "skills_dir": str(settings.skills_path),
        "gateway_url": settings.GATEWAY_URL,
        "cors_origins": settings.CORS_ORIGINS,
    })


@router.get("/dcc-status")
async def get_dcc_status(request: Request):
    """Get all DCC connection statuses."""
    dcc_manager = request.app.state.dcc_manager
    statuses = await dcc_manager.get_all_status()
    return ok(statuses)


@router.post("/dcc-status/refresh")
async def refresh_dcc_status(request: Request):
    """Force refresh all DCC connection statuses."""
    dcc_manager = request.app.state.dcc_manager
    for dcc_type in list((await dcc_manager.get_all_status()).keys()):
        await dcc_manager.check_connection(dcc_type)
    statuses = await dcc_manager.get_all_status()
    return ok(statuses)


# ------------------------------------------------------------------
# DCC Options (with MCP connection status)
# ------------------------------------------------------------------

@router.get("/dcc-options")
async def get_dcc_options(request: Request):
    """Return DCC list with connection status from DCC manager."""
    from ..services.dcc_manager import DEFAULT_DCC_PORTS

    dcc_manager = request.app.state.dcc_manager
    statuses = await dcc_manager.get_all_status()

    ordered = ["comfyui", "ue57", "maya2024", "max2024", "blender", "houdini", "sp", "sd"]
    result = []
    for dcc_id in ordered:
        name, icon = _DCC_META.get(dcc_id, (dcc_id, "🔧"))
        port = DEFAULT_DCC_PORTS.get(dcc_id, 0)
        connected = statuses.get(dcc_id, {}).get("connected", False)
        result.append({
            "id": dcc_id,
            "name": name,
            "icon": icon,
            "port": port,
            "connected": connected,
        })
    return ok(result)


# ------------------------------------------------------------------
# Agents per platform
# ------------------------------------------------------------------

def _read_json(path: str) -> dict:
    p = os.path.expanduser(path)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _check_platform_configured(platform_type: str) -> bool:
    """Check if a platform's config file or tool exists (no network probes)."""
    import shutil

    if platform_type == "openclaw":
        return os.path.exists(os.path.expanduser("~/.openclaw/openclaw.json"))
    elif platform_type == "lobster":
        appdata = os.environ.get("APPDATA", os.path.expanduser("~/AppData/Roaming"))
        return os.path.exists(os.path.join(appdata, "LobsterAI", "openclaw", "state", "openclaw.json"))
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


@router.get("/agents")
async def get_agents():
    """Return agent lists per platform by reading ~/.artclaw/config.json registry."""
    # Read platform registry from artclaw config
    artclaw_cfg = _read_json("~/.artclaw/config.json")
    registry = artclaw_cfg.get("platforms_registry", [])

    # Fallback: if registry is empty, build from known platforms
    if not registry:
        # Read actual port from openclaw.json if available
        oc_cfg = _read_json("~/.openclaw/openclaw.json")
        oc_port = oc_cfg.get("gateway", {}).get("port", 18789)
        registry = [
            {"type": "openclaw", "display_name": "OpenClaw", "gateway_url": f"ws://127.0.0.1:{oc_port}"},
            {"type": "lobster", "display_name": "LobsterAI", "gateway_url": "ws://127.0.0.1:18790"},
        ]

    platforms = []
    for plat in registry:
        p_type = plat.get("type", "")
        p_name = plat.get("display_name", p_type.title())
        agents = _get_agents_for_platform(p_type)
        configured = _check_platform_configured(p_type)
        platforms.append({"id": p_type, "name": p_name, "agents": agents, "configured": configured})

    return ok({"platforms": platforms})


def _get_agents_for_platform(platform_type: str) -> list:
    """Get agent list for a given platform type."""
    # Platform-specific config file paths
    _CONFIG_PATHS = {
        "openclaw": "~/.openclaw/openclaw.json",
        "lobster": None,  # resolved dynamically
        "workbuddy": "~/.workbuddy/config.json",
    }

    # MCP-only platforms (no agent management, return static entry)
    _MCP_ONLY = {"claudecode", "cursor"}

    if platform_type in _MCP_ONLY:
        display_names = {"claudecode": "Claude Code", "cursor": "Cursor"}
        name = display_names.get(platform_type, platform_type.title())
        return [{"id": platform_type, "name": name}]

    # LobsterAI special path
    if platform_type == "lobster":
        appdata = os.environ.get("APPDATA", os.path.expanduser("~/AppData/Roaming"))
        config_path = os.path.join(appdata, "LobsterAI", "openclaw", "state", "openclaw.json")
    else:
        config_path = _CONFIG_PATHS.get(platform_type, "")

    if not config_path:
        return [{"id": "default", "name": "Default Agent"}]

    cfg = _read_json(config_path)
    agents_raw = cfg.get("agents", {}).get("list", [])
    agents = []
    for a in agents_raw:
        aid = a.get("id", "")
        if aid:
            agents.append({"id": aid, "name": a.get("name", aid)})

    if not agents:
        agents = [{"id": "default", "name": "Default Agent"}]

    return agents
