"""
Filter Presets REST API – CRUD for global filter presets.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas.common import err, ok, ok_list
from ..schemas.filter_preset import (
    FilterPresetCreateRequest,
    FilterPresetUpdateRequest,
)
from ..services.filter_preset_service import FilterPresetService

router = APIRouter()

_svc = FilterPresetService()


@router.get("")
async def list_filter_presets(
    dcc: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    """List filter presets, optionally filtered by DCC."""
    items = _svc.list_presets(dcc=dcc)
    total = len(items)
    start = (page - 1) * limit
    page_items = items[start: start + limit]
    return ok_list(page_items, page=page, limit=limit, total=total)


@router.post("")
async def create_filter_preset(body: FilterPresetCreateRequest):
    """Create a new filter preset."""
    preset = _svc.create_preset(body)
    return ok(preset)


@router.get("/{preset_id}")
async def get_filter_preset(preset_id: str):
    """Get a filter preset by ID."""
    preset = _svc.get_preset(preset_id)
    if not preset:
        raise HTTPException(
            status_code=404,
            detail=err("NOT_FOUND", "Filter preset not found"),
        )
    return ok(preset)


@router.patch("/{preset_id}")
async def update_filter_preset(preset_id: str, body: FilterPresetUpdateRequest):
    """Update a filter preset."""
    preset = _svc.update_preset(preset_id, body)
    if not preset:
        raise HTTPException(
            status_code=404,
            detail=err("NOT_FOUND", "Filter preset not found"),
        )
    return ok(preset)


@router.delete("/{preset_id}")
async def delete_filter_preset(preset_id: str):
    """Delete a filter preset."""
    success = _svc.delete_preset(preset_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=err("NOT_FOUND", "Filter preset not found"),
        )
    return ok({"message": "Filter preset deleted"})
