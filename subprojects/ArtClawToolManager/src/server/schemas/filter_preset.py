"""Pydantic schemas for FilterPreset request/response payloads."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FileFilterRuleSchema(BaseModel):
    pattern: str
    is_regex: bool = False


class SceneFilterRuleSchema(BaseModel):
    pattern: str
    is_regex: bool = True


class TypeFilterSchema(BaseModel):
    types: List[str] = Field(default_factory=list)
    dcc: Optional[str] = None


class FilterConfigSchema(BaseModel):
    file_rules: List[FileFilterRuleSchema] = Field(default_factory=list)
    scene_rules: List[SceneFilterRuleSchema] = Field(default_factory=list)
    type_filter: Optional[TypeFilterSchema] = None
    selection_only: bool = False


class FilterPresetCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    dcc: List[str] = Field(default_factory=list)
    filter: FilterConfigSchema = Field(default_factory=FilterConfigSchema)


class FilterPresetUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    dcc: Optional[List[str]] = None
    filter: Optional[FilterConfigSchema] = None


class FilterPresetResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    dcc: List[str] = Field(default_factory=list)
    filter: FilterConfigSchema = Field(default_factory=FilterConfigSchema)
    source: str = "user"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
