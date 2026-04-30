# Ref: docs/api/api-design.md#SystemAPI
"""System status and configuration endpoints."""

from __future__ import annotations

import json
import logging
import os
import platform
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Request

from ..core.config import settings
from ..schemas.common import ok
from ..services.config_manager import ConfigManager
from ..services.skill_service import SkillService

router = APIRouter()

# DCC display metadata (id → name, icon)
_DCC_META = {
    "ue5":      ("UE5",     "🎮"),
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

    ordered = ["comfyui", "ue5", "maya2024", "max2024", "blender", "houdini", "sp", "sd"]
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


# ------------------------------------------------------------------
# DCC Object Types (live query via MCP)
# ------------------------------------------------------------------

# Python snippets executed on each DCC to enumerate object/asset types.
# Each must print a JSON list of {"type": str, "label": str} dicts.
_DCC_TYPE_QUERY_CODE: dict[str, str] = {
    "ue5": r"""
import unreal, json
class_set = set()
try:
    assets = unreal.EditorAssetLibrary.list_assets('/Game/', recursive=True, include_folder=False)
    for path in assets:
        ad = unreal.EditorAssetLibrary.find_asset_data(path)
        try:
            cls = str(ad.asset_class_path.asset_name)
        except Exception:
            cls = str(getattr(ad, 'asset_class', ''))
        if cls:
            class_set.add(cls)
except Exception:
    pass
for name in ['StaticMesh', 'SkeletalMesh', 'Material', 'MaterialInstance',
             'MaterialInstanceConstant', 'Texture2D', 'TextureCube',
             'Blueprint', 'World', 'Level', 'LevelSequence',
             'AnimSequence', 'AnimBlueprint', 'AnimMontage',
             'SoundWave', 'SoundCue', 'NiagaraSystem', 'NiagaraEmitter',
             'ParticleSystem', 'PhysicsAsset', 'DataTable', 'CurveFloat',
             'WidgetBlueprint', 'MediaSource', 'ObjectRedirector']:
    class_set.add(name)
result = sorted([{"type": t, "label": t} for t in class_set], key=lambda x: x["type"])
print(json.dumps(result, ensure_ascii=False))
""",
    "maya2024": r"""
import maya.cmds as cmds, json
types = sorted(cmds.allNodeTypes())
result = [{"type": t, "label": t} for t in types]
print(json.dumps(result, ensure_ascii=False))
""",
    "max2024": r"""
import json
from pymxs import runtime as rt
classes = set()
for sc in rt.superClasses:
    for c in rt.showClass("*", asArray=True, superClass=sc):
        classes.add(str(c))
result = sorted([{"type": t, "label": t} for t in classes], key=lambda x: x["type"])
print(json.dumps(result, ensure_ascii=False))
""",
    "blender": r"""
import bpy, json
types = sorted(set(o.type for o in bpy.data.objects))
result = [{"type": t, "label": t} for t in types]
print(json.dumps(result, ensure_ascii=False))
""",
    "comfyui": r"""
import json
try:
    import nodes as _n
    mapping = getattr(_n, 'NODE_CLASS_MAPPINGS', {})
    types = sorted(mapping.keys())
except Exception:
    types = []
result = [{"type": t, "label": t} for t in types]
print(json.dumps(result, ensure_ascii=False))
""",
    "sp": r"""
import substance_painter as sp, json
types = ["TextureSet", "FillLayer", "PaintLayer", "GroupLayer", "MaskLayer", "FilterLayer", "GeneratorLayer"]
result = [{"type": t, "label": t} for t in types]
print(json.dumps(result, ensure_ascii=False))
""",
    "sd": r"""
import sd, json
types = ["SDSBSCompGraph", "SDSBSFunctionGraph", "SDNode", "SDResource", "SDPackage", "SDProperty", "SDConnection"]
result = [{"type": t, "label": t} for t in types]
print(json.dumps(result, ensure_ascii=False))
""",
}


@router.get("/dcc-types/{dcc_type}")
async def get_dcc_object_types(dcc_type: str, request: Request):
    """Query a connected DCC for available object/asset types via MCP.

    Falls back to static presets if the DCC is not connected or the query fails.
    """
    dcc_manager = request.app.state.dcc_manager

    # Static fallback from dccTypes.ts presets (kept in sync here)
    _STATIC_PRESETS: dict[str, list[str]] = {
        "ue5": ["AActor", "UObject", "UStaticMesh", "USkeletalMesh", "UMaterial",
                "UMaterialInstance", "UTexture2D", "UBlueprint", "UWorld",
                "UStaticMeshComponent"],
        "maya2024": ["mesh", "nurbsSurface", "nurbsCurve", "joint", "camera",
                     "light", "transform", "locator"],
        "max2024": ["Editable_Mesh", "Editable_Poly", "Bone", "Camera", "Light",
                    "Spline", "Helper"],
        "blender": ["MESH", "ARMATURE", "CURVE", "SURFACE", "CAMERA", "LIGHT",
                    "EMPTY", "FONT", "GPENCIL"],
        "comfyui": ["CheckpointLoaderSimple", "KSampler", "VAEDecode",
                    "CLIPTextEncode", "SaveImage", "LoadImage", "ControlNetApply"],
        "sp": ["TextureSet", "FillLayer", "PaintLayer", "GroupLayer", "MaskLayer"],
        "sd": ["SDSBSCompGraph", "SDNode", "SDResource", "SDPackage"],
    }

    # Try live query first
    code = _DCC_TYPE_QUERY_CODE.get(dcc_type)
    if code:
        statuses = await dcc_manager.get_all_status()
        dcc_status = statuses.get(dcc_type, {})
        if dcc_status.get("connected"):
            try:
                result = await dcc_manager.execute_on_dcc(dcc_type, code, timeout=15.0)
                if result.get("success") and result.get("output"):
                    import json as _json
                    output = result["output"].strip()

                    # Some DCC MCP servers (e.g. UE) wrap the result in a JSON envelope:
                    #   {"success": true, "output": "<actual print output>", ...}
                    # Unwrap if needed.
                    try:
                        envelope = _json.loads(output)
                        if isinstance(envelope, dict) and "output" in envelope:
                            if not envelope.get("success", True):
                                # Inner execution failed
                                raise ValueError(envelope.get("error", "inner exec failed"))
                            output = envelope["output"].strip()
                    except (ValueError, _json.JSONDecodeError):
                        pass  # Not an envelope, use output as-is

                    # Extract JSON array from output (find last JSON array line)
                    for line in reversed(output.splitlines()):
                        line = line.strip()
                        if line.startswith("["):
                            types = _json.loads(line)
                            return ok({"dcc": dcc_type, "source": "live", "types": types})
            except Exception as exc:
                logger.warning("Live DCC type query failed for %s: %s", dcc_type, exc)

    # Fallback to static presets
    preset = _STATIC_PRESETS.get(dcc_type, [])
    types = [{"type": t, "label": t} for t in preset]
    return ok({"dcc": dcc_type, "source": "preset", "types": types})


# ------------------------------------------------------------------
# Platform Gateway CRUD
# ------------------------------------------------------------------

_PLATFORM_DISPLAY_NAMES = {
    "openclaw": "OpenClaw",
    "lobster": "LobsterAI",
    "claudecode": "Claude Code",
    "cursor": "Cursor",
    "workbuddy": "WorkBuddy",
}

_PLATFORM_DEFAULT_URLS: dict[str, str] = {
    "openclaw": "ws://127.0.0.1:18789",
    "lobster": "ws://127.0.0.1:18794",
    "claudecode": "",
    "cursor": "",
    "workbuddy": "ws://127.0.0.1:18795",
}


def _artclaw_config_path() -> str:
    return os.path.expanduser("~/.artclaw/config.json")


def _load_artclaw_cfg() -> dict:
    p = _artclaw_config_path()
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_artclaw_cfg(cfg: dict) -> None:
    import tempfile
    p = _artclaw_config_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


@router.get("/platforms")
async def get_platforms():
    """Return platform list with current gateway_url from ~/.artclaw/config.json."""
    cfg = _load_artclaw_cfg()
    registry = cfg.get("platforms_registry", [])

    # 如果 registry 为空，用当前 platform + defaults 构造
    if not registry:
        current = cfg.get("platform", {})
        p_type = current.get("type", "openclaw")
        registry = [
            {"type": p_type, "gateway_url": current.get("gateway_url", _PLATFORM_DEFAULT_URLS.get(p_type, ""))},
        ]
        for k, url in _PLATFORM_DEFAULT_URLS.items():
            if k != p_type:
                registry.append({"type": k, "gateway_url": url})

    result = []
    # 当前 platform.gateway_url 覆盖 registry（以实际生效配置为准）
    current_platform = cfg.get("platform", {})
    current_type = current_platform.get("type", "")
    current_url = current_platform.get("gateway_url", "")

    for entry in registry:
        p_type = entry.get("type", "")
        url = entry.get("gateway_url", _PLATFORM_DEFAULT_URLS.get(p_type, ""))
        if p_type == current_type and current_url:
            url = current_url  # 以 config.json platform.gateway_url 为准
        result.append({
            "type": p_type,
            "name": _PLATFORM_DISPLAY_NAMES.get(p_type, p_type.title()),
            "gateway_url": url,
            "configured": _check_platform_configured(p_type),
            "is_current": p_type == current_type,
        })

    return ok(result)


@router.post("/platforms/gateway")
async def update_platform_gateway(body: dict):
    """Save gateway_url for a platform to ~/.artclaw/config.json."""
    platform_type = body.get("platform", "")
    new_url = body.get("url", "").strip()

    if not platform_type or not new_url:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="platform and url are required")

    cfg = _load_artclaw_cfg()

    # 更新 platforms_registry 中对应条目
    registry = cfg.setdefault("platforms_registry", [])
    found = False
    for entry in registry:
        if entry.get("type") == platform_type:
            entry["gateway_url"] = new_url
            found = True
            break
    if not found:
        registry.append({"type": platform_type, "gateway_url": new_url,
                         "display_name": _PLATFORM_DISPLAY_NAMES.get(platform_type, platform_type.title())})

    # 如果修改的是当前平台，同步更新 platform.gateway_url
    current = cfg.setdefault("platform", {})
    if current.get("type", "openclaw") == platform_type:
        current["gateway_url"] = new_url

    _save_artclaw_cfg(cfg)
    logger.info("Platform gateway updated: %s -> %s", platform_type, new_url)
    return ok({"platform": platform_type, "url": new_url})


@router.post("/platforms/detect")
async def detect_platform_port(body: dict):
    """Auto-detect gateway URL for a platform by reading its config files."""
    platform_type = body.get("platform", "openclaw")

    detected_url = ""

    if platform_type == "openclaw":
        # 读 ~/.openclaw/openclaw.json gateway.port
        oc_cfg = _read_json("~/.openclaw/openclaw.json")
        port = oc_cfg.get("gateway", {}).get("port", 0)
        if port:
            detected_url = f"ws://127.0.0.1:{port}"
        # 再尝试 gateway-port.json
        if not detected_url:
            port_json = os.path.expanduser("~/.openclaw/gateway-port.json")
            if os.path.exists(port_json):
                try:
                    with open(port_json, "r", encoding="utf-8") as f:
                        p = json.load(f).get("port", 0)
                    if p:
                        detected_url = f"ws://127.0.0.1:{p}"
                except Exception:
                    pass

    elif platform_type == "lobster":
        appdata = os.environ.get("APPDATA", os.path.expanduser("~/AppData/Roaming"))
        lb_cfg_path = os.path.join(appdata, "LobsterAI", "openclaw", "state", "openclaw.json")
        lb_cfg = _read_json(lb_cfg_path) if os.path.exists(lb_cfg_path) else {}
        port = lb_cfg.get("gateway", {}).get("port", 0)
        if port:
            detected_url = f"ws://127.0.0.1:{port}"

    # fallback to default
    if not detected_url:
        detected_url = _PLATFORM_DEFAULT_URLS.get(platform_type, "ws://127.0.0.1:18789")

    return ok({"platform": platform_type, "url": detected_url})


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
