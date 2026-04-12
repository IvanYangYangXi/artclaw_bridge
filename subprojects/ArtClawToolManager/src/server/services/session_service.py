# Ref: docs/features/phase1-foundation.md#SessionAPI
"""
Session business-logic service (in-memory, no database).

Sessions are ephemeral — lost on restart.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..models.data import SessionData
from ..schemas.session import (
    MessageCreateRequest,
    SessionCreateRequest,
    SessionUpdateRequest,
)

# Module-level in-memory stores
_sessions: Dict[str, SessionData] = {}
_messages: Dict[str, List[Dict[str, Any]]] = {}  # session_id → messages

# Pre-populate with a default session
_DEFAULT_ID = "default"
_sessions[_DEFAULT_ID] = SessionData(
    id=_DEFAULT_ID,
    title="新对话",
    dcc_software="none",
    agent_platform="openclaw",
    status="active",
)
_messages[_DEFAULT_ID] = []


class SessionService:
    """Chat session & message CRUD (in-memory)."""

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def list_sessions(
        self,
        *,
        status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[SessionData], int]:
        items = list(_sessions.values())

        if status:
            items = [s for s in items if s.status == status]
        else:
            items = [s for s in items if s.status != "deleted"]

        if search:
            low = search.lower()
            items = [s for s in items if low in s.title.lower()]

        # Sort by id (most recent first would need timestamps; just reverse order)
        items.reverse()

        total = len(items)
        start = (page - 1) * limit
        page_items = items[start : start + limit]
        return page_items, total

    def create_session(self, data: SessionCreateRequest) -> SessionData:
        sid = str(uuid.uuid4())
        session = SessionData(
            id=sid,
            title=data.title,
            dcc_software=data.dcc_software,
            agent_platform=data.agent_platform,
            agent_id=data.agent_id or "",
        )
        _sessions[sid] = session
        _messages[sid] = []
        return session

    def get_session(self, session_id: str) -> Optional[SessionData]:
        return _sessions.get(session_id)

    def update_session(
        self, session_id: str, data: SessionUpdateRequest
    ) -> Optional[SessionData]:
        session = _sessions.get(session_id)
        if not session:
            return None
        update = data.model_dump(exclude_unset=True)
        for field_name, value in update.items():
            if hasattr(session, field_name):
                if hasattr(value, "value"):
                    value = value.value
                setattr(session, field_name, value)
        return session

    def delete_session(self, session_id: str) -> bool:
        session = _sessions.get(session_id)
        if not session:
            return False
        session.status = "deleted"
        return True

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def get_messages(
        self,
        session_id: str,
        *,
        before_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        msgs = _messages.get(session_id, [])
        if before_id:
            idx = None
            for i, m in enumerate(msgs):
                if m.get("id") == before_id:
                    idx = i
                    break
            if idx is not None:
                msgs = msgs[:idx]
        return msgs[-limit:]

    def create_message(
        self, session_id: str, data: MessageCreateRequest
    ) -> Optional[Dict[str, Any]]:
        session = _sessions.get(session_id)
        if not session:
            return None

        msg = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "role": data.role,
            "content": data.content,
            "tool_calls": data.tool_calls,
            "tool_results": data.tool_results,
            "tokens_used": data.tokens_used,
            "latency_ms": data.latency_ms,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _messages.setdefault(session_id, []).append(msg)
        session.message_count = (session.message_count or 0) + 1
        return msg
