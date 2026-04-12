# Ref: docs/features/phase4-tool-api.md#TriggerRules
"""
Trigger rule business-logic service (JSON file, no database).

Stores rules in ``~/.artclaw/triggers.json``.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from typing import Any, Dict, List, Optional

from ..core.config import settings
from ..models.data import TriggerRuleData
from ..schemas.trigger import TriggerCreateRequest, TriggerUpdateRequest


def _triggers_path():
    return settings.data_path / "triggers.json"


def _load_all() -> List[Dict[str, Any]]:
    """Load all trigger rules from JSON file."""
    path = _triggers_path()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_all(rules: List[Dict[str, Any]]) -> None:
    """Atomically save all trigger rules to JSON file."""
    path = _triggers_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(rules, f, indent=2, ensure_ascii=False)
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


_lock = threading.Lock()


class TriggerService:
    """TriggerRule CRUD operations (JSON file storage)."""

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_triggers(self, tool_id: str) -> List[TriggerRuleData]:
        with _lock:
            all_rules = _load_all()
        result = []
        for r in all_rules:
            if r.get("tool_id") == tool_id:
                result.append(self._dict_to_data(r))
        return result

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------

    def get_trigger(self, trigger_id: str) -> Optional[TriggerRuleData]:
        with _lock:
            all_rules = _load_all()
        for r in all_rules:
            if r.get("id") == trigger_id:
                return self._dict_to_data(r)
        return None

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_trigger(
        self, tool_id: str, req: TriggerCreateRequest
    ) -> TriggerRuleData:
        rule_dict = {
            "id": str(uuid.uuid4()),
            "tool_id": tool_id,
            "name": req.name,
            "trigger_type": req.trigger_type.value,
            "event_type": req.event_type,
            "event_timing": req.event_timing.value,
            "execution_mode": req.execution_mode.value,
            "conditions": req.conditions,
            "parameter_preset": req.parameter_preset,
            "is_enabled": req.is_enabled,
            "schedule_config": req.schedule_config,
            "dcc": req.dcc,
            "filter_preset_id": req.filter_preset_id,
            "parameter_preset_id": req.parameter_preset_id,
        }

        with _lock:
            all_rules = _load_all()
            all_rules.append(rule_dict)
            _save_all(all_rules)

        return self._dict_to_data(rule_dict)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_trigger(
        self, trigger_id: str, req: TriggerUpdateRequest
    ) -> Optional[TriggerRuleData]:
        with _lock:
            all_rules = _load_all()
            found = None
            for r in all_rules:
                if r.get("id") == trigger_id:
                    found = r
                    break
            if not found:
                return None

            update_data = req.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                if value is not None and hasattr(value, "value"):
                    found[key] = value.value
                else:
                    found[key] = value

            _save_all(all_rules)
            return self._dict_to_data(found)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_trigger(self, trigger_id: str) -> bool:
        with _lock:
            all_rules = _load_all()
            before = len(all_rules)
            all_rules = [r for r in all_rules if r.get("id") != trigger_id]
            if len(all_rules) == before:
                return False
            _save_all(all_rules)
        return True

    # ------------------------------------------------------------------
    # Toggle
    # ------------------------------------------------------------------

    def enable_trigger(self, trigger_id: str) -> Optional[TriggerRuleData]:
        with _lock:
            all_rules = _load_all()
            for r in all_rules:
                if r.get("id") == trigger_id:
                    r["is_enabled"] = True
                    _save_all(all_rules)
                    return self._dict_to_data(r)
        return None

    def disable_trigger(self, trigger_id: str) -> Optional[TriggerRuleData]:
        with _lock:
            all_rules = _load_all()
            for r in all_rules:
                if r.get("id") == trigger_id:
                    r["is_enabled"] = False
                    _save_all(all_rules)
                    return self._dict_to_data(r)
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dict_to_data(d: Dict[str, Any]) -> TriggerRuleData:
        return TriggerRuleData(
            id=d.get("id", ""),
            tool_id=d.get("tool_id", ""),
            name=d.get("name", ""),
            trigger_type=d.get("trigger_type", "manual"),
            event_type=d.get("event_type", ""),
            event_timing=d.get("event_timing", "post"),
            execution_mode=d.get("execution_mode", "interactive"),
            conditions=d.get("conditions", {}),
            parameter_preset=d.get("parameter_preset", {}),
            is_enabled=d.get("is_enabled", True),
            schedule_config=d.get("schedule_config", {}),
            dcc=d.get("dcc", ""),
            filter_preset_id=d.get("filter_preset_id", ""),
            parameter_preset_id=d.get("parameter_preset_id", ""),
        )
