# Ref: docs/features/phase4-tool-api.md#ToolsAPI
"""
Tools REST API – list / detail / create / update / delete / toggle / batch / execute.
"""
from __future__ import annotations

import subprocess
import platform
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas.common import err, ok, ok_list
from ..schemas.tool import (
    ToolBatchRequest,
    ToolCreateRequest,
    ToolExecuteRequest,
    ToolPublishRequest,
    ToolResponse,
    ToolUpdateRequest,
)
from ..services.config_manager import ConfigManager
from ..services.tool_service import ToolService
from ..services.trigger_service import TriggerService
from ..schemas.trigger import TriggerCreateRequest
from pydantic import BaseModel, Field

router = APIRouter()

# Module-level singletons
_config = ConfigManager()
_tool_svc = ToolService(_config)
_trigger_svc = TriggerService()


# ------------------------------------------------------------------
# List
# ------------------------------------------------------------------

@router.get("")
async def list_tools(
    source: Optional[str] = Query(None, description="official|marketplace|user|all"),
    search: Optional[str] = Query(None, description="Keyword search"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
):
    """Get paginated tool list with optional filters."""
    try:
        items, total = _tool_svc.list_tools(
            source=source,
            search=search,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=err("TOOLS_UNAVAILABLE", str(exc)),
        )
    data = [t.to_dict() for t in items]
    return ok_list(data, page=page, limit=limit, total=total)


# ------------------------------------------------------------------
# Recent usage  (must be before /{tool_id:path})
# ------------------------------------------------------------------

@router.get("/recent")
async def get_recent_tools(
    limit: int = Query(10, ge=1, le=50),
):
    """Get recently used tools (by last_used timestamp)."""
    tools, _ = _tool_svc.list_tools(sort_by="last_used", sort_order="desc", limit=limit)
    return ok([t.to_dict() for t in tools])


# ------------------------------------------------------------------
# Batch  (must be registered BEFORE /{tool_id:path} routes)
# ------------------------------------------------------------------

@router.post("/batch")
async def batch_operation(body: ToolBatchRequest):
    """Execute a batch operation on multiple tools."""
    valid_ops = {"enable", "disable", "pin", "unpin", "favorite", "unfavorite", "delete"}
    if body.operation not in valid_ops:
        raise HTTPException(
            status_code=400,
            detail=err(
                "BAD_REQUEST",
                f"Invalid operation. Must be one of: {sorted(valid_ops)}",
            ),
        )
    result = _tool_svc.batch_operation(body.operation, body.tool_ids)
    return ok({
        "operation": body.operation,
        "total": len(body.tool_ids),
        **result,
    })


# ------------------------------------------------------------------
# Create
# ------------------------------------------------------------------

@router.post("")
async def create_tool(body: ToolCreateRequest):
    """Create a new tool."""
    try:
        tool = _tool_svc.create_tool(
            name=body.name,
            description=body.description,
            version=body.version,
            source=body.source.value,
            target_dccs=body.target_dccs,
            implementation_type=body.implementation_type.value,
            manifest=body.manifest,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=err("TOOL_ALREADY_EXISTS", str(exc)),
        )
    return ok(tool.to_dict())


# ------------------------------------------------------------------
# Directory Operations (must be before /{tool_id:path} routes)
# ------------------------------------------------------------------

@router.post("/{tool_id:path}/open-dir")
async def open_tool_dir(tool_id: str):
    """Open tool directory in file explorer."""
    tool = _tool_svc.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=err("TOOL_NOT_FOUND", "Tool not found"))
    # tool.tool_path 是目录路径
    dir_path = getattr(tool, 'tool_path', '') or ''
    if not dir_path or not os.path.isdir(dir_path):
        raise HTTPException(status_code=404, detail=err("DIR_NOT_FOUND", f"Directory not found: {dir_path}"))
    if platform.system() == 'Windows':
        subprocess.Popen(['explorer', dir_path])
    elif platform.system() == 'Darwin':
        subprocess.Popen(['open', dir_path])
    else:
        subprocess.Popen(['xdg-open', dir_path])
    return ok({"opened": dir_path})


@router.post("/{tool_id:path}/publish")
async def publish_tool(tool_id: str, body: ToolPublishRequest):
    """Publish user tool to official or marketplace."""
    try:
        result = _tool_svc.publish_tool(
            tool_id, body.target, body.version, body.description
        )
        return ok(result)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=err("PUBLISH_FAILED", str(e))
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=err("INTERNAL_ERROR", str(e))
        )


# ------------------------------------------------------------------
# Preset management schemas
# ------------------------------------------------------------------

class PresetCreateRequest(BaseModel):
    name: str
    description: str = ""
    is_default: bool = False
    values: dict = Field(default_factory=dict)


class PresetUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None
    values: Optional[dict] = None


# ------------------------------------------------------------------
# Preset routes (must be BEFORE /{tool_id:path} catch-all)
# ------------------------------------------------------------------

@router.get("/{tool_id:path}/presets")
async def list_presets(tool_id: str):
    """Get all presets for a tool."""
    presets = _tool_svc.list_presets(tool_id)
    if presets is None:
        raise HTTPException(status_code=404, detail=err("TOOL_NOT_FOUND", "Tool not found"))
    return ok(presets)


@router.post("/{tool_id:path}/presets")
async def create_preset(tool_id: str, body: PresetCreateRequest):
    """Create a new preset for a tool."""
    try:
        preset = _tool_svc.create_preset(
            tool_id, body.name, body.description, body.is_default, body.values
        )
        return ok(preset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=err("PRESET_ERROR", str(e)))


@router.patch("/{tool_id:path}/presets/{preset_id}")
async def update_preset(tool_id: str, preset_id: str, body: PresetUpdateRequest):
    """Update an existing preset."""
    try:
        preset = _tool_svc.update_preset(
            tool_id, preset_id,
            name=body.name,
            description=body.description,
            is_default=body.is_default,
            values=body.values,
        )
        return ok(preset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=err("PRESET_ERROR", str(e)))


@router.delete("/{tool_id:path}/presets/{preset_id}")
async def delete_preset(tool_id: str, preset_id: str):
    """Delete a preset."""
    try:
        _tool_svc.delete_preset(tool_id, preset_id)
        return ok({"deleted": True, "preset_id": preset_id})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=err("PRESET_ERROR", str(e)))


@router.post("/{tool_id:path}/presets/{preset_id}/set-default")
async def set_default_preset(tool_id: str, preset_id: str):
    """Set a preset as the default."""
    try:
        preset = _tool_svc.set_default_preset(tool_id, preset_id)
        return ok(preset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=err("PRESET_ERROR", str(e)))


# ------------------------------------------------------------------
# Trigger routes (must be BEFORE /{tool_id:path} catch-all)
# ------------------------------------------------------------------

@router.get("/{tool_id:path}/triggers")
async def list_tool_triggers(tool_id: str):
    """Get all trigger rules for a tool."""
    triggers = _trigger_svc.list_triggers(tool_id)
    data = [t.to_dict() for t in triggers]
    return ok(data)


@router.post("/{tool_id:path}/triggers")
async def create_tool_trigger(tool_id: str, body: TriggerCreateRequest):
    """Create a new trigger rule for a tool."""
    trigger = _trigger_svc.create_trigger(tool_id, body)
    return ok(trigger.to_dict())


# ------------------------------------------------------------------
# Detail
# ------------------------------------------------------------------

@router.get("/{tool_id:path}")
async def get_tool(tool_id: str):
    """Get single tool detail."""
    tool = _tool_svc.get_tool(tool_id)
    if not tool:
        raise HTTPException(
            status_code=404,
            detail=err("TOOL_NOT_FOUND", f"Tool not found: {tool_id}"),
        )
    return ok(tool.to_dict())


# ------------------------------------------------------------------
# Update
# ------------------------------------------------------------------

@router.patch("/{tool_id:path}")
async def update_tool(tool_id: str, body: ToolUpdateRequest):
    """Partial update a tool."""
    update_data = body.model_dump(exclude_unset=True)
    # Convert enum values
    if "implementation_type" in update_data and update_data["implementation_type"] is not None:
        val = update_data["implementation_type"]
        update_data["implementation_type"] = val.value if hasattr(val, "value") else val
    tool = _tool_svc.update_tool(tool_id, **update_data)
    if not tool:
        raise HTTPException(
            status_code=404,
            detail=err("TOOL_NOT_FOUND", f"Tool not found: {tool_id}"),
        )
    return ok(tool.to_dict())


# ------------------------------------------------------------------
# Delete
# ------------------------------------------------------------------

@router.delete("/{tool_id:path}")
async def delete_tool(tool_id: str):
    """Delete a tool."""
    deleted = _tool_svc.delete_tool(tool_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=err("TOOL_NOT_FOUND", f"Tool not found: {tool_id}"),
        )
    return ok({"id": tool_id, "deleted": True})


# ------------------------------------------------------------------
# Toggle operations
# ------------------------------------------------------------------

@router.post("/{tool_id:path}/enable")
async def enable_tool(tool_id: str):
    tool = _tool_svc.enable_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=err("TOOL_NOT_FOUND", "Tool not found"))
    return ok(tool.to_dict())


@router.post("/{tool_id:path}/disable")
async def disable_tool(tool_id: str):
    tool = _tool_svc.disable_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=err("TOOL_NOT_FOUND", "Tool not found"))
    return ok(tool.to_dict())


@router.post("/{tool_id:path}/pin")
async def pin_tool(tool_id: str):
    tool = _tool_svc.pin_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=err("TOOL_NOT_FOUND", "Tool not found"))
    return ok(tool.to_dict())


@router.post("/{tool_id:path}/unpin")
async def unpin_tool(tool_id: str):
    tool = _tool_svc.unpin_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=err("TOOL_NOT_FOUND", "Tool not found"))
    return ok(tool.to_dict())


@router.post("/{tool_id:path}/favorite")
async def favorite_tool(tool_id: str):
    tool = _tool_svc.favorite_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=err("TOOL_NOT_FOUND", "Tool not found"))
    return ok(tool.to_dict())


@router.post("/{tool_id:path}/unfavorite")
async def unfavorite_tool(tool_id: str):
    tool = _tool_svc.unfavorite_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=err("TOOL_NOT_FOUND", "Tool not found"))
    return ok(tool.to_dict())


# ------------------------------------------------------------------
# Execute (script tools run directly; AI-driven tools return navigate)
# ------------------------------------------------------------------

@router.post("/{tool_id:path}/execute")
async def execute_tool(tool_id: str, body: ToolExecuteRequest):
    """Execute a tool.

    - script tools with needsAI=False: actually run the Python entry point,
      return stdout/stderr and exit code.
    - skill_wrapper / composite / any needsAI=True tool: return a navigate
      instruction so the frontend opens the chat panel.
    """
    import subprocess
    import sys
    from pathlib import Path

    tool = _tool_svc.get_tool(tool_id)
    if not tool:
        raise HTTPException(
            status_code=404,
            detail=err("TOOL_NOT_FOUND", f"Tool not found: {tool_id}"),
        )

    impl_type = tool.implementation_type or "script"
    manifest = tool.manifest or {}
    impl = manifest.get("implementation", {})
    entry = impl.get("entry", "main.py")
    function = impl.get("function", "")

    # Determine if this requires AI
    # skill_wrapper and composite types need AI;
    # script tools bound to a DCC run directly via MCP (no AI needed)
    needs_ai = impl_type in ("skill_wrapper", "composite")

    if needs_ai:
        # Return navigate instruction – frontend handles the rest
        tool.use_count += 1
        return ok({
            "action": "navigate",
            "target": "/chat",
            "command": f"/run tool:{tool_id}",
            "parameters": body.parameters,
        })

    # --- Script tool ---
    target_dccs = manifest.get("targetDCCs", [])

    # "general" means platform-independent — run locally, not via DCC MCP.
    # Only route to DCC when targetDCCs contains real DCC identifiers.
    real_dcc_targets = [d for d in target_dccs if d and d != "general"]

    if real_dcc_targets:
        # DCC-bound script: execute via MCP on the connected DCC
        return await _execute_on_dcc(tool, entry, function, body.parameters or {}, real_dcc_targets)
    else:
        # Generic script: run locally via subprocess
        return await _execute_locally(tool, entry, function, body.parameters or {})


# ------------------------------------------------------------------
# Execute helpers
# ------------------------------------------------------------------

async def _execute_locally(tool, entry: str, function: str, params: dict):
    """Run a generic (non-DCC) script tool via subprocess."""
    import sys
    from pathlib import Path

    if not tool.tool_path:
        raise HTTPException(
            status_code=500,
            detail=err("TOOL_PATH_MISSING", "Tool has no tool_path configured"),
        )

    entry_path = Path(tool.tool_path) / entry
    if not entry_path.exists():
        raise HTTPException(
            status_code=500,
            detail=err("ENTRY_NOT_FOUND", f"Entry script not found: {entry_path}"),
        )

    params_repr = repr(params)

    # Resolve artclaw_sdk path so tool scripts can import it
    sdk_path = Path(__file__).resolve().parents[4] / "DCCClawBridge" / "core"
    extra_paths = [str(entry_path.parent), str(sdk_path)]

    if function:
        sys_path_insert = "; ".join(
            f"sys.path.insert(0, {repr(p)})" for p in extra_paths
        )
        code = (
            f"import sys; {sys_path_insert}; "
            f"import importlib.util; "
            f"spec = importlib.util.spec_from_file_location('_tool', {repr(str(entry_path))}); "
            f"mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); "
            f"result = mod.{function}(**{params_repr}); "
            f"import json; print(json.dumps(result) if not isinstance(result, str) else result)"
        )
        cmd = [sys.executable, "-c", code]
    else:
        cmd = [sys.executable, str(entry_path)]
        for k, v in params.items():
            cmd += [f"--{k}", str(v)]

    env = {**__import__("os").environ, "PYTHONPATH": str(sdk_path)}

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(entry_path.parent),
            env=env,
        )
        tool.use_count += 1
        return ok({
            "action": "executed",
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "success": proc.returncode == 0,
        })
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail=err("EXECUTION_TIMEOUT", "Script execution timed out (120s)"),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=err("EXECUTION_ERROR", str(exc)),
        )


async def _execute_on_dcc(tool, entry: str, function: str, params: dict, target_dccs: list):
    """Run a DCC-bound script tool via MCP WebSocket on the target DCC."""
    from pathlib import Path
    from ..services.dcc_manager import DCCManager

    # Get DCCManager instance from app state
    from ..main import dcc_manager as _dcc_manager
    if _dcc_manager is None:
        raise HTTPException(
            status_code=500,
            detail=err("DCC_MANAGER_UNAVAILABLE", "DCC manager not initialized"),
        )

    # Find a connected DCC matching targetDCCs
    dcc_type = _dcc_manager.get_connected_dcc(target_dccs)
    if not dcc_type:
        dcc_names = ", ".join(target_dccs)
        raise HTTPException(
            status_code=503,
            detail=err(
                "DCC_NOT_CONNECTED",
                f"No connected DCC found for [{dcc_names}]. Please open the target DCC application first.",
            ),
        )

    # Read the script file
    if not tool.tool_path:
        raise HTTPException(
            status_code=500,
            detail=err("TOOL_PATH_MISSING", "Tool has no tool_path configured"),
        )

    entry_path = Path(tool.tool_path) / entry
    if not entry_path.exists():
        raise HTTPException(
            status_code=500,
            detail=err("ENTRY_NOT_FOUND", f"Entry script not found: {entry_path}"),
        )

    script_source = entry_path.read_text(encoding="utf-8")

    # Build execution code: define the script, then call the function with params
    params_repr = repr(params)
    if function:
        # Wrap: exec the script source to define functions, then call the target function
        exec_code = (
            f"{script_source}\n\n"
            f"# --- ArtClaw Tool Manager: auto-call ---\n"
            f"import json as _json\n"
            f"_result = {function}(**{params_repr})\n"
            f"if _result is not None:\n"
            f"    print(_json.dumps(_result, ensure_ascii=False, default=str))\n"
        )
    else:
        # No function specified, just run the script
        exec_code = script_source

    # Execute via MCP
    result = await _dcc_manager.execute_on_dcc(dcc_type, exec_code, timeout=120.0)

    tool.use_count += 1
    return ok({
        "action": "executed",
        "exit_code": 0 if result["success"] else 1,
        "stdout": result.get("output", ""),
        "stderr": result.get("error", ""),
        "success": result["success"],
        "dcc": dcc_type,
    })
