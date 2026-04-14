# Ref: docs/features/phase4-tool-api.md
"""
Pydantic schemas for Tool request / response payloads.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- enums ---

class ToolSourceEnum(str, Enum):
    OFFICIAL = "official"
    MARKETPLACE = "marketplace"
    USER = "user"


class ToolStatusEnum(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"
    DISABLED = "disabled"


class ImplementationTypeEnum(str, Enum):
    SKILL_WRAPPER = "skill_wrapper"
    SCRIPT = "script"
    COMPOSITE = "composite"


# --- request ---

class ToolCreateRequest(BaseModel):
    """Create a new tool from manifest data."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    version: str = "1.0.0"
    source: ToolSourceEnum = ToolSourceEnum.USER
    target_dccs: List[str] = Field(default_factory=list)
    implementation_type: ImplementationTypeEnum = ImplementationTypeEnum.SCRIPT
    manifest: Dict[str, Any] = Field(default_factory=dict)


class ToolUpdateRequest(BaseModel):
    """Partial update for a tool."""
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    target_dccs: Optional[List[str]] = None
    implementation_type: Optional[ImplementationTypeEnum] = None
    manifest: Optional[Dict[str, Any]] = None


class ToolBatchRequest(BaseModel):
    operation: str = Field(
        ...,
        description="enable|disable|pin|unpin|favorite|unfavorite|delete",
    )
    tool_ids: List[str]


class ToolExecuteRequest(BaseModel):
    """Execute a tool with parameters."""
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ToolPublishRequest(BaseModel):
    """Request body for publishing a tool."""
    target: str = Field(..., pattern="^(official|marketplace)$", description="Publish target")
    version: str = Field(..., description="New version string")
    description: str = Field(default="", description="Update description")


# --- response ---

class ToolResponse(BaseModel):
    """Single tool payload."""
    id: str
    name: str
    description: str = ""
    version: str = "0.0.0"
    author: str = ""
    source: ToolSourceEnum = ToolSourceEnum.USER
    target_dccs: List[str] = Field(default_factory=list)
    status: ToolStatusEnum = ToolStatusEnum.INSTALLED
    is_enabled: bool = True
    is_pinned: bool = False
    is_favorited: bool = False
    use_count: int = 0
    last_used_at: Optional[datetime] = None
    tool_path: str = ""
    manifest: Dict[str, Any] = Field(default_factory=dict)
    implementation_type: ImplementationTypeEnum = ImplementationTypeEnum.SCRIPT
    priority: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}
