# Ref: docs/features/phase4-tool-api.md
"""
Pydantic schemas for TriggerRule request / response payloads.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- enums ---

class TriggerTypeEnum(str, Enum):
    MANUAL = "manual"
    EVENT = "event"
    SCHEDULE = "schedule"
    WATCH = "watch"


class EventTimingEnum(str, Enum):
    PRE = "pre"
    POST = "post"


class ExecutionModeEnum(str, Enum):
    SILENT = "silent"
    NOTIFY = "notify"
    INTERACTIVE = "interactive"


# --- request ---

class TriggerCreateRequest(BaseModel):
    """Create a new trigger rule."""
    name: str = Field(..., min_length=1, max_length=255)
    trigger_type: TriggerTypeEnum = TriggerTypeEnum.MANUAL
    event_type: str = ""
    execution_mode: ExecutionModeEnum = ExecutionModeEnum.NOTIFY
    conditions: Dict[str, Any] = Field(default_factory=dict)
    use_default_filters: bool = False
    parameter_preset: Dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True
    schedule_config: Dict[str, Any] = Field(default_factory=dict)
    dcc: str = ""
    filter_preset_id: str = ""
    parameter_preset_id: str = ""


class TriggerUpdateRequest(BaseModel):
    """Partial update for a trigger rule."""
    name: Optional[str] = None
    trigger_type: Optional[TriggerTypeEnum] = None
    event_type: Optional[str] = None
    execution_mode: Optional[ExecutionModeEnum] = None
    conditions: Optional[Dict[str, Any]] = None
    parameter_preset: Optional[Dict[str, Any]] = None
    is_enabled: Optional[bool] = None
    schedule_config: Optional[Dict[str, Any]] = None
    dcc: Optional[str] = None
    filter_preset_id: Optional[str] = None
    parameter_preset_id: Optional[str] = None


# --- response ---

class TriggerRuleResponse(BaseModel):
    """Single trigger rule payload."""
    id: str
    tool_id: str
    name: str
    trigger_type: TriggerTypeEnum = TriggerTypeEnum.MANUAL
    event_type: str = ""
    execution_mode: ExecutionModeEnum = ExecutionModeEnum.NOTIFY
    conditions: Dict[str, Any] = Field(default_factory=dict)
    parameter_preset: Dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True
    schedule_config: Dict[str, Any] = Field(default_factory=dict)
    dcc: str = ""
    filter_preset_id: str = ""
    parameter_preset_id: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
