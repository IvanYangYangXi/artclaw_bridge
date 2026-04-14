# Ref: docs/features/official-system-tools.md#DataModels
"""Alert data models and schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AlertBase(BaseModel):
    """Base alert model."""
    level: str = Field(..., pattern="^(warning|error)$")  # 严重级别
    source: str = Field(..., min_length=1)  # 来源工具 ID  
    title: str = Field(..., min_length=1, max_length=200)  # 简短标题
    detail: str = Field(..., max_length=2000)  # 详细描述
    metadata: Optional[Dict[str, Any]] = None  # 扩展数据


class AlertCreateRequest(AlertBase):
    """Request model for creating an alert."""
    pass


class AlertUpdateRequest(BaseModel):
    """Request model for updating an alert."""
    resolved: bool = False
    resolvedAt: Optional[str] = None  # ISO datetime string


class Alert(AlertBase):
    """Complete alert model with ID and timestamps."""
    id: str = Field(..., min_length=1)  # 唯一 ID
    createdAt: str = Field(...)  # 创建时间 (ISO)
    resolvedAt: Optional[str] = None  # 解决时间 (ISO)
    updatedAt: Optional[str] = None  # 最后更新时间 (ISO, 去重更新时写入)
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AlertResponse(Alert):
    """Response model for alert API."""
    pass


class AlertListResponse(BaseModel):
    """Response model for alert list API."""
    alerts: list[Alert]
    total: int
    unresolved: int