# Ref: docs/api/api-design.md#SkillsAPI
"""
Skills REST API – list / detail / enable / disable / pin / favorite / batch.

The skill list is populated by scanning ``~/.openclaw/skills/`` on demand.
User preferences (pinned, disabled, favorites) are stored in
``~/.artclaw/config.json`` via ConfigManager.
"""
from __future__ import annotations

import subprocess
import platform
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas.common import err, ok, ok_list
from ..schemas.skill import SkillBatchRequest
from ..services.config_manager import ConfigManager
from ..services.recent_usage_service import RecentUsageService
from ..services.skill_service import SkillService

router = APIRouter()

# Module-level singletons
_config = ConfigManager()
_svc = SkillService(_config)


# ------------------------------------------------------------------
# List
# ------------------------------------------------------------------

@router.get("")
async def list_skills(
    source: Optional[str] = Query(None, description="official|marketplace|user|all"),
    status: Optional[str] = Query(None, description="installed|not_installed|disabled|all"),
    search: Optional[str] = Query(None, description="Keyword search"),
    target_dcc: Optional[str] = Query(None, alias="targetDCC", description="Filter by DCC type"),
    installed: Optional[bool] = Query(None),
    pinned: Optional[bool] = Query(None),
    favorited: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    sort_by: str = Query("name"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
):
    """Get paginated skill list with optional filters."""
    items, total = _svc.list_skills(
        source=source,
        status=status,
        search=search,
        target_dcc=target_dcc,
        installed=installed,
        pinned=pinned,
        favorited=favorited,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    data = [s.to_dict() for s in items]
    return ok_list(data, page=page, limit=limit, total=total)


# ------------------------------------------------------------------
# Batch  (must be registered BEFORE /{skill_id:path} routes)
# ------------------------------------------------------------------

@router.post("/batch")
async def batch_operation(body: SkillBatchRequest):
    """Execute a batch operation on multiple skills."""
    valid_ops = {"enable", "disable", "pin", "unpin", "favorite", "unfavorite"}
    if body.operation not in valid_ops:
        raise HTTPException(
            status_code=400,
            detail=err(
                "BAD_REQUEST",
                f"Invalid operation. Must be one of: {sorted(valid_ops)}",
            ),
        )
    result = _svc.batch_operation(body.operation, body.skill_ids)
    return ok({
        "operation": body.operation,
        "total": len(body.skill_ids),
        **result,
    })


# ------------------------------------------------------------------
# Recent usage
# ------------------------------------------------------------------

@router.get("/recent")
async def get_recent_skills(
    limit: int = Query(10, ge=1, le=50),
):
    """Get recently used skills."""
    svc = RecentUsageService(_config)
    items = svc.get_recent(limit)
    return ok(items)


# ------------------------------------------------------------------
# Directory Operations (must be before /{skill_id:path} routes)
# ------------------------------------------------------------------

@router.post("/{skill_id:path}/open-dir")
async def open_skill_dir(skill_id: str):
    """Open skill directory in file explorer."""
    skill = _svc.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=err("NOT_FOUND", "Skill not found"))
    # skill.skill_path 是目录路径
    dir_path = getattr(skill, 'skill_path', '') or ''
    if not dir_path or not os.path.isdir(dir_path):
        raise HTTPException(status_code=404, detail=err("DIR_NOT_FOUND", f"Directory not found: {dir_path}"))
    if platform.system() == 'Windows':
        subprocess.Popen(['explorer', dir_path])
    elif platform.system() == 'Darwin':
        subprocess.Popen(['open', dir_path])
    else:
        subprocess.Popen(['xdg-open', dir_path])
    return ok({"opened": dir_path})


@router.post("/{skill_id:path}/open-source-dir")
async def open_skill_source_dir(skill_id: str):
    """Open skill source directory in file explorer."""
    skill = _svc.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=err("NOT_FOUND", "Skill not found"))
    # Use pre-computed source_path from scanner
    source_path = getattr(skill, 'source_path', '') or ''
    if not source_path or not os.path.isdir(source_path):
        raise HTTPException(
            status_code=404,
            detail=err(
                "SOURCE_NOT_FOUND",
                f"Source directory not found for skill '{skill_id}'. "
                "Ensure project_root is configured and the skill exists in skills/{{layer}}/{{dcc}}/{{skill_dir}}/",
            ),
        )
    if platform.system() == 'Windows':
        subprocess.Popen(['explorer', source_path])
    elif platform.system() == 'Darwin':
        subprocess.Popen(['open', source_path])
    else:
        subprocess.Popen(['xdg-open', source_path])
    return ok({"opened": source_path})


@router.post("/{skill_id:path}/publish")
async def publish_skill(skill_id: str):
    """Publish user skill to project directory."""
    skill = _svc.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=err("SKILL_NOT_FOUND", "Skill not found"))
    # 暂时返回说明
    return ok({"message": "Publish functionality coming soon", "skill_id": skill_id})


@router.post("/{skill_id:path}/sync-from-source")
async def sync_from_source(skill_id: str):
    """Sync skill from source directory to installed directory."""
    try:
        result = _svc.sync_from_source(skill_id)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=err("SYNC_FAILED", str(e)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=err("INTERNAL_ERROR", str(e)))


@router.post("/{skill_id:path}/publish-to-source")
async def publish_to_source(skill_id: str):
    """Publish skill from installed directory to source directory."""
    try:
        result = _svc.publish_to_source(skill_id)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=err("PUBLISH_FAILED", str(e)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=err("INTERNAL_ERROR", str(e)))


# ------------------------------------------------------------------
# Detail
# ------------------------------------------------------------------

@router.get("/{skill_id:path}")
async def get_skill(skill_id: str):
    """Get single skill detail."""
    skill = _svc.get_skill(skill_id)
    if not skill:
        raise HTTPException(
            status_code=404,
            detail=err("NOT_FOUND", f"Skill not found: {skill_id}"),
        )
    return ok(skill.to_dict())


# ------------------------------------------------------------------
# Toggle operations (each returns the updated skill)
# ------------------------------------------------------------------

@router.post("/{skill_id:path}/enable")
async def enable_skill(skill_id: str):
    """Enable a disabled skill."""
    skill = _svc.enable_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=err("NOT_FOUND", "Skill not found"))
    return ok(skill.to_dict())


@router.post("/{skill_id:path}/disable")
async def disable_skill(skill_id: str):
    """Disable an installed skill."""
    skill = _svc.disable_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=err("NOT_FOUND", "Skill not found"))
    return ok(skill.to_dict())


@router.post("/{skill_id:path}/pin")
async def pin_skill(skill_id: str):
    """Pin a skill (show at top of list)."""
    skill = _svc.pin_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=err("NOT_FOUND", "Skill not found"))
    return ok(skill.to_dict())


@router.post("/{skill_id:path}/unpin")
async def unpin_skill(skill_id: str):
    """Unpin a skill."""
    skill = _svc.unpin_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=err("NOT_FOUND", "Skill not found"))
    return ok(skill.to_dict())


@router.post("/{skill_id:path}/favorite")
async def favorite_skill(skill_id: str):
    """Add skill to favorites."""
    skill = _svc.favorite_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=err("NOT_FOUND", "Skill not found"))
    return ok(skill.to_dict())


@router.post("/{skill_id:path}/unfavorite")
async def unfavorite_skill(skill_id: str):
    """Remove skill from favorites."""
    skill = _svc.unfavorite_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=err("NOT_FOUND", "Skill not found"))
    return ok(skill.to_dict())
