"""Plain data models (no ORM). Replace SQLAlchemy models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SkillData:
    id: str
    name: str
    description: str = ""
    version: str = "0.0.0"
    author: str = ""
    updated_at: str = ""
    source: str = "official"  # official/marketplace/user
    target_dccs: List[str] = field(default_factory=list)
    status: str = "installed"  # installed/not_installed/disabled/update_available
    skill_path: str = ""
    source_path: str = ""  # path to source directory in project repo
    sync_status: str = "no_source"  # synced/source_newer/installed_newer/conflict/no_source
    is_enabled: bool = True
    is_pinned: bool = False
    is_favorited: bool = False
    use_count: int = 0
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "updated_at": self.updated_at,
            "source": self.source,
            "target_dccs": self.target_dccs,
            "status": self.status,
            "skill_path": self.skill_path,
            "source_path": self.source_path,
            "sync_status": self.sync_status,
            "is_enabled": self.is_enabled,
            "is_pinned": self.is_pinned,
            "is_favorited": self.is_favorited,
            "use_count": self.use_count,
            "priority": self.priority,
        }


@dataclass
class ToolData:
    id: str
    name: str
    description: str = ""
    version: str = "0.0.0"
    source: str = "user"
    target_dccs: List[str] = field(default_factory=list)
    status: str = "installed"
    tool_path: str = ""
    implementation_type: str = "script"
    manifest: Dict[str, Any] = field(default_factory=dict)
    is_enabled: bool = True
    is_pinned: bool = False
    is_favorited: bool = False
    use_count: int = 0
    author: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return vars(self).copy()


@dataclass
class WorkflowData:
    id: str
    name: str
    description: str = ""
    version: str = "0.0.0"
    source: str = "official"
    target_dcc: str = "comfyui"
    status: str = "installed"
    is_favorited: bool = False
    preview_image_path: str = ""
    workflow_json: Dict[str, Any] = field(default_factory=dict)
    parameters: List[Dict] = field(default_factory=list)
    workflow_path: str = ""
    use_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return vars(self).copy()


@dataclass
class SessionData:
    id: str
    title: str = "新对话"
    dcc_software: str = ""
    agent_platform: str = ""
    agent_id: str = ""
    message_count: int = 0
    status: str = "active"

    def to_dict(self) -> Dict[str, Any]:
        return vars(self).copy()


@dataclass
class TriggerRuleData:
    id: str
    tool_id: str
    name: str = ""
    trigger_type: str = "manual"
    event_type: str = ""
    event_timing: str = "post"
    execution_mode: str = "interactive"
    conditions: Dict[str, Any] = field(default_factory=dict)
    parameter_preset: Dict[str, Any] = field(default_factory=dict)
    is_enabled: bool = True
    use_default_filters: bool = False
    schedule_config: Dict[str, Any] = field(default_factory=dict)
    dcc: str = ""  # DCC this rule applies to
    filter_preset_id: str = ""  # reference to global filter preset
    parameter_preset_id: str = ""  # reference to tool parameter preset

    def to_dict(self) -> Dict[str, Any]:
        return vars(self).copy()
