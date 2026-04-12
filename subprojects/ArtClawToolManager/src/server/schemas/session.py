# Ref: docs/api/api-design.md#SessionsAPI
"""
Pydantic schemas for ChatSession / ChatMessage request & response payloads.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- enums ---

class SessionStatusEnum(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


# --- request ---

class SessionCreateRequest(BaseModel):
    title: str = "New Chat"
    dcc_software: str = "none"
    agent_platform: str = "openclaw"
    agent_id: Optional[str] = None


class SessionUpdateRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[SessionStatusEnum] = None
    dcc_software: Optional[str] = None
    agent_id: Optional[str] = None


class MessageCreateRequest(BaseModel):
    role: str = Field(..., pattern=r"^(user|assistant|system|tool)$")
    content: str = ""
    tool_calls: Optional[Any] = None
    tool_results: Optional[Any] = None
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None


# --- response ---

class SessionResponse(BaseModel):
    id: str
    title: str = "New Chat"
    status: SessionStatusEnum = SessionStatusEnum.ACTIVE
    dcc_software: str = "none"
    agent_platform: str = "openclaw"
    agent_id: Optional[str] = None
    message_count: int = 0
    context_usage: int = 0
    pinned_skills: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str = ""
    tool_calls: Optional[Any] = None
    tool_results: Optional[Any] = None
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
