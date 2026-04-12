# Ref: docs/api/api-design.md#SessionsAPI
"""
Sessions REST API – CRUD for chat sessions and messages (in-memory).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas.common import err, ok, ok_list
from ..schemas.session import (
    MessageCreateRequest,
    SessionCreateRequest,
    SessionUpdateRequest,
)
from ..services.session_service import SessionService

router = APIRouter()

# Module-level singleton
_svc = SessionService()


# ------------------------------------------------------------------
# Session CRUD
# ------------------------------------------------------------------

@router.get("")
async def list_sessions(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """List chat sessions (paginated)."""
    items, total = _svc.list_sessions(
        status=status, search=search, page=page, limit=limit,
    )
    data = [s.to_dict() for s in items]
    return ok_list(data, page=page, limit=limit, total=total)


@router.post("")
async def create_session(body: SessionCreateRequest):
    """Create a new chat session."""
    session = _svc.create_session(body)
    return ok(session.to_dict())


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get session detail."""
    session = _svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=err("NOT_FOUND", "Session not found"))
    return ok(session.to_dict())


@router.patch("/{session_id}")
async def update_session(session_id: str, body: SessionUpdateRequest):
    """Update session metadata."""
    session = _svc.update_session(session_id, body)
    if not session:
        raise HTTPException(status_code=404, detail=err("NOT_FOUND", "Session not found"))
    return ok(session.to_dict())


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Soft-delete a session."""
    success = _svc.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail=err("NOT_FOUND", "Session not found"))
    return ok({"message": "Session deleted"})


# ------------------------------------------------------------------
# Messages
# ------------------------------------------------------------------

@router.get("/{session_id}/messages")
async def get_messages(
    session_id: str,
    before_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Get message history for a session."""
    messages = _svc.get_messages(
        session_id, before_id=before_id, limit=limit,
    )
    return ok(messages)


@router.post("/{session_id}/messages")
async def create_message(session_id: str, body: MessageCreateRequest):
    """Store a message in a session."""
    msg = _svc.create_message(session_id, body)
    if not msg:
        raise HTTPException(status_code=404, detail=err("NOT_FOUND", "Session not found"))
    return ok(msg)
