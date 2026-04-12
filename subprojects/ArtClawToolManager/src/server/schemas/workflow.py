# Ref: docs/api/api-design.md#WorkflowsAPI
"""
Pydantic schemas for Workflow request / response payloads.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- enums ---

class WorkflowSourceEnum(str, Enum):
    OFFICIAL = "official"
    MARKETPLACE = "marketplace"
    USER = "user"


class WorkflowStatusEnum(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"


# --- parameter schema ---

class WorkflowParameterSchema(BaseModel):
    """Describes a single user-tunable parameter exposed by a workflow."""
    id: str
    name: str
    type: str = "string"  # string | number | boolean | enum | image
    required: bool = False
    default: Optional[Any] = None
    description: str = ""
    options: List[str] = Field(default_factory=list)
    min_value: Optional[float] = None
    max_value: Optional[float] = None


# --- request ---

class WorkflowExecuteRequest(BaseModel):
    """Parameters submitted when executing a workflow."""
    parameters: Dict[str, Any] = Field(default_factory=dict)


class WorkflowBatchRequest(BaseModel):
    """Batch operation request for multiple workflows."""
    operation: str = Field(
        ...,
        description="favorite|unfavorite|delete",
    )
    workflow_ids: List[str] = Field(..., description="List of workflow IDs to operate on")


# --- response ---

class WorkflowResponse(BaseModel):
    """Full workflow payload (includes workflow_json)."""
    id: str
    name: str
    description: str = ""
    version: str = "0.0.0"
    source: WorkflowSourceEnum = WorkflowSourceEnum.OFFICIAL
    target_dcc: str = "comfyui"
    status: WorkflowStatusEnum = WorkflowStatusEnum.INSTALLED
    is_favorited: bool = False
    preview_image_path: str = ""
    workflow_json: Dict[str, Any] = Field(default_factory=dict)
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    use_count: int = 0
    last_used_at: Optional[datetime] = None
    workflow_path: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkflowListResponse(BaseModel):
    """Lightweight workflow payload for list views (no workflow_json)."""
    id: str
    name: str
    description: str = ""
    version: str = "0.0.0"
    source: WorkflowSourceEnum = WorkflowSourceEnum.OFFICIAL
    target_dcc: str = "comfyui"
    status: WorkflowStatusEnum = WorkflowStatusEnum.INSTALLED
    is_favorited: bool = False
    preview_image_path: str = ""
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    use_count: int = 0
    last_used_at: Optional[datetime] = None
    workflow_path: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkflowExecuteResponse(BaseModel):
    """Result of a workflow execution request."""
    workflow_id: str
    status: str = "queued"
    message: str = ""
    result: Optional[Dict[str, Any]] = None


class WorkflowPublishRequest(BaseModel):
    """Request body for publishing a workflow."""
    target: str = Field(..., pattern="^(official|marketplace)$", description="Publish target")
    version: str = Field(..., description="New version string")
    description: str = Field(default="", description="Update description")
