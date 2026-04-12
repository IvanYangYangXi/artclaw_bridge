# Ref: docs/features/phase4-tool-api.md#TriggerAPI
"""
Trigger Rules REST API – update / delete / enable / disable.

List and create are handled by tools.py (registered before the
/{tool_id:path} catch-all).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas.common import err, ok
from ..schemas.trigger import TriggerUpdateRequest
from ..services.trigger_service import TriggerService

router = APIRouter()

# Module-level singleton
_svc = TriggerService()


# ------------------------------------------------------------------
# Update trigger
# ------------------------------------------------------------------

@router.patch("/triggers/{trigger_id}")
async def update_trigger(trigger_id: str, body: TriggerUpdateRequest):
    """Update a trigger rule."""
    trigger = _svc.update_trigger(trigger_id, body)
    if not trigger:
        raise HTTPException(
            status_code=404,
            detail=err("TRIGGER_NOT_FOUND", f"Trigger not found: {trigger_id}"),
        )
    return ok(trigger.to_dict())


# ------------------------------------------------------------------
# Delete trigger
# ------------------------------------------------------------------

@router.delete("/triggers/{trigger_id}")
async def delete_trigger(trigger_id: str):
    """Delete a trigger rule."""
    deleted = _svc.delete_trigger(trigger_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=err("TRIGGER_NOT_FOUND", f"Trigger not found: {trigger_id}"),
        )
    return ok({"id": trigger_id, "deleted": True})


# ------------------------------------------------------------------
# Enable / Disable trigger
# ------------------------------------------------------------------

@router.post("/triggers/{trigger_id}/enable")
async def enable_trigger(trigger_id: str):
    """Enable a trigger rule."""
    trigger = _svc.enable_trigger(trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=404,
            detail=err("TRIGGER_NOT_FOUND", "Trigger not found"),
        )
    return ok(trigger.to_dict())


@router.post("/triggers/{trigger_id}/disable")
async def disable_trigger(trigger_id: str):
    """Disable a trigger rule."""
    trigger = _svc.disable_trigger(trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=404,
            detail=err("TRIGGER_NOT_FOUND", "Trigger not found"),
        )
    return ok(trigger.to_dict())
