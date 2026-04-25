# Ref: docs/api/api-design.md#WorkflowsAPI
"""
Workflows REST API – list / detail / favorite / parameters / execute.

Workflow templates are discovered by scanning ``~/.artclaw/workflows/``
and ``~/.openclaw/workspace/skills/`` for directories containing ``workflow.json``.
"""
from __future__ import annotations

import subprocess
import platform
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas.common import err, ok, ok_list
from ..schemas.workflow import (
    WorkflowBatchRequest,
    WorkflowExecuteRequest,
    WorkflowPublishRequest,
)
from ..services.config_manager import ConfigManager
from ..services.workflow_service import WorkflowService

router = APIRouter()

# Module-level singletons
_config = ConfigManager()
_svc = WorkflowService(_config)


# ------------------------------------------------------------------
# List
# ------------------------------------------------------------------

@router.get("")
async def list_workflows(
    source: Optional[str] = Query(None, description="official|marketplace|user|all"),
    target_dcc: Optional[str] = Query(None, description="comfyui|blender|all"),
    search: Optional[str] = Query(None, description="Keyword search"),
    favorited: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
):
    """Get paginated workflow list with optional filters."""
    items, total = _svc.list_workflows(
        source=source,
        target_dcc=target_dcc,
        search=search,
        favorited=favorited,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    data = [w.to_dict() for w in items]
    return ok_list(data, page=page, limit=limit, total=total)


# ------------------------------------------------------------------
# Recent usage  (must be before /{workflow_id:path})
# ------------------------------------------------------------------

@router.get("/recent")
async def get_recent_workflows(
    limit: int = Query(10, ge=1, le=50),
):
    """Get recently used workflows (by last_used timestamp)."""
    workflows, _ = _svc.list_workflows(sort_by="last_used", sort_order="desc", limit=limit)
    return ok([w.to_dict() for w in workflows])


# ------------------------------------------------------------------
# Batch  (must be registered BEFORE /{workflow_id} routes)
# ------------------------------------------------------------------

@router.post("/batch")
async def batch_workflow_operation(body: WorkflowBatchRequest):
    """Execute a batch operation on multiple workflows."""
    valid_ops = {"favorite", "unfavorite", "delete"}
    if body.operation not in valid_ops:
        raise HTTPException(
            status_code=400,
            detail=err(
                "BAD_REQUEST",
                f"Invalid operation. Must be one of: {sorted(valid_ops)}",
            ),
        )
    result = _svc.batch_operation(body.operation, body.workflow_ids)
    return ok({
        "operation": body.operation,
        "total": len(body.workflow_ids),
        **result,
    })


# ------------------------------------------------------------------
# Directory Operations (must be before /{workflow_id} routes)
# ------------------------------------------------------------------

@router.post("/{workflow_id:path}/open-dir")
async def open_workflow_dir(workflow_id: str):
    """Open workflow directory in file explorer."""
    wf = _svc.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=err("NOT_FOUND", "Workflow not found"))
    # workflow.workflow_path 是目录路径
    dir_path = getattr(wf, 'workflow_path', '') or ''
    if not dir_path or not os.path.isdir(dir_path):
        raise HTTPException(status_code=404, detail=err("DIR_NOT_FOUND", f"Directory not found: {dir_path}"))
    if platform.system() == 'Windows':
        subprocess.Popen(['explorer', dir_path])
    elif platform.system() == 'Darwin':
        subprocess.Popen(['open', dir_path])
    else:
        subprocess.Popen(['xdg-open', dir_path])
    return ok({"opened": dir_path})


# ------------------------------------------------------------------
# Detail
# ------------------------------------------------------------------

@router.post("/{workflow_id:path}/publish")
async def publish_workflow(workflow_id: str, body: WorkflowPublishRequest):
    """Publish user workflow to official or marketplace."""
    try:
        result = _svc.publish_workflow(
            workflow_id, body.target, body.version, body.description
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


@router.get("/{workflow_id:path}")
async def get_workflow(workflow_id: str):
    """Get single workflow detail (includes workflow_json)."""
    wf = _svc.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(
            status_code=404,
            detail=err("NOT_FOUND", f"Workflow not found: {workflow_id}"),
        )
    return ok(wf.to_dict())


# ------------------------------------------------------------------
# Favorite / Unfavorite
# ------------------------------------------------------------------

@router.post("/{workflow_id:path}/favorite")
async def favorite_workflow(workflow_id: str):
    """Add workflow to favorites."""
    wf = _svc.favorite(workflow_id)
    if not wf:
        raise HTTPException(
            status_code=404,
            detail=err("NOT_FOUND", "Workflow not found"),
        )
    return ok(wf.to_dict())


@router.post("/{workflow_id:path}/unfavorite")
async def unfavorite_workflow(workflow_id: str):
    """Remove workflow from favorites."""
    wf = _svc.unfavorite(workflow_id)
    if not wf:
        raise HTTPException(
            status_code=404,
            detail=err("NOT_FOUND", "Workflow not found"),
        )
    return ok(wf.to_dict())


# ------------------------------------------------------------------
# Parameters
# ------------------------------------------------------------------

@router.get("/{workflow_id:path}/parameters")
async def get_workflow_parameters(workflow_id: str):
    """Get the exposed parameters for a workflow."""
    params = _svc.get_workflow_parameters(workflow_id)
    if params is None:
        raise HTTPException(
            status_code=404,
            detail=err("NOT_FOUND", "Workflow not found"),
        )
    return ok(params)


# ------------------------------------------------------------------
# Execute
# ------------------------------------------------------------------

@router.post("/{workflow_id:path}/execute")
async def execute_workflow(workflow_id: str, body: WorkflowExecuteRequest):
    """Execute a workflow with the given parameters."""
    result = _svc.execute_workflow(workflow_id, body.parameters)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=err("NOT_FOUND", "Workflow not found"),
        )
    return ok(result)
