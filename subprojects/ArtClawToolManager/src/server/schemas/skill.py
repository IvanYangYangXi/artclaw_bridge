# Ref: docs/api/api-design.md#SkillsAPI
"""
Pydantic schemas for Skill request / response payloads.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- enums ---

class SkillSourceEnum(str, Enum):
    OFFICIAL = "official"
    MARKETPLACE = "marketplace"
    USER = "user"


class SkillStatusEnum(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"
    DISABLED = "disabled"


# --- request ---

class SkillInstallRequest(BaseModel):
    version: Optional[str] = None
    force: bool = False


class SkillUpdateRequest(BaseModel):
    """Partial update for toggle operations."""
    is_enabled: Optional[bool] = None
    is_pinned: Optional[bool] = None
    is_favorited: Optional[bool] = None


class SkillPublishRequest(BaseModel):
    version: Optional[str] = None
    bump: str = "patch"
    target: str = "marketplace"   # "official" | "marketplace"
    dcc: str = ""                  # target DCC directory (e.g. "universal", "unreal")
    description: str = ""


class SkillBatchRequest(BaseModel):
    operation: str = Field(
        ...,
        description="install|uninstall|enable|disable|pin|unpin|favorite|unfavorite",
    )
    skill_ids: List[str]
    operation: str = Field(
        ...,
        description="install|uninstall|enable|disable|pin|unpin|favorite|unfavorite",
    )
    skill_ids: List[str]


# --- response ---

class SkillResponse(BaseModel):
    """Single skill payload."""
    id: str
    name: str
    description: str = ""
    version: str = "0.0.0"
    source: SkillSourceEnum = SkillSourceEnum.OFFICIAL
    target_dccs: List[str] = Field(default_factory=list)
    status: SkillStatusEnum = SkillStatusEnum.INSTALLED
    is_enabled: bool = True
    is_pinned: bool = False
    is_favorited: bool = False
    use_count: int = 0
    last_used_at: Optional[datetime] = None
    skill_path: str = ""
    priority: int = 0
    dependencies: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SkillDetailResponse(SkillResponse):
    """Extended detail (same fields for now, extensible later)."""
    pass


class BatchResultResponse(BaseModel):
    operation: str
    total: int
    succeeded: int
    failed: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)
