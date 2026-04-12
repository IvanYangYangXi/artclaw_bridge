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


@router.get("/agents")
async def get_agents():
    """Return agent lists per platform by reading real config files."""
    platforms = []

    # OpenClaw agents
    oc_cfg = _read_json("~/.openclaw/openclaw.json")
    oc_agents_raw = oc_cfg.get("agents", {}).get("list", [])
    oc_agents = []
    for a in oc_agents_raw:
        aid = a.get("id", "")
        if aid:
            oc_agents.append({"id": aid, "name": a.get("name", aid)})
    if not oc_agents:
        oc_agents = [{"id": "default", "name": "Default Agent"}]
    platforms.append({"id": "openclaw", "name": "OpenClaw", "agents": oc_agents})

    # LobsterAI agents
    appdata = os.environ.get("APPDATA", os.path.expanduser("~/AppData/Roaming"))
    lobster_path = os.path.join(appdata, "LobsterAI", "openclaw", "state", "openclaw.json")
    lb_cfg = _read_json(lobster_path)
    lb_agents_raw = lb_cfg.get("agents", {}).get("list", [])
    lb_agents = []
    for a in lb_agents_raw:
        aid = a.get("id", "")
        if aid:
            lb_agents.append({"id": aid, "name": a.get("name", aid)})
    if not lb_agents:
        lb_agents = [{"id": "default", "name": "Default Agent"}]
    platforms.append({"id": "lobsterai", "name": "LobsterAI", "agents": lb_agents})

    # Claude agents (static)
    platforms.append({"id": "claude", "name": "Claude", "agents": [{"id": "claude", "name": "Claude"}]})

    return ok({"platforms": platforms})
