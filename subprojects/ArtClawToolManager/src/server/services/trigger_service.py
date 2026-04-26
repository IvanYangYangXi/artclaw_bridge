# Ref: docs/features/phase4-tool-api.md#TriggerRules
"""
Trigger rule business-logic service (JSON file, no database).

Stores rules in ``~/.artclaw/triggers.json``.

On startup, manifest triggers are synced into triggers.json
(keyed by manifest_id + tool_id to avoid duplicates).
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import uuid
from typing import Any, Dict, List, Optional

from ..core.config import settings
from ..models.data import TriggerRuleData
from ..schemas.trigger import TriggerCreateRequest, TriggerUpdateRequest

logger = logging.getLogger(__name__)


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
        new_id = str(uuid.uuid4())
        rule_dict = {
            "id": new_id,
            "manifest_id": new_id,          # 新建规则同时作为 manifest_id，用于写回 manifest
            "tool_id": tool_id,
            "name": req.name,
            "trigger_type": req.trigger_type.value,
            "event_type": req.event_type,
            "execution_mode": req.execution_mode.value,
            "conditions": req.conditions,
            "use_default_filters": req.use_default_filters if hasattr(req, "use_default_filters") else False,
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

        # 同步写回 manifest.json（追加新条目）
        self._append_rule_to_manifest(rule_dict)

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

            # Also update the source manifest.json so sync doesn't overwrite
            self._sync_rule_to_manifest(found)

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
            execution_mode=d.get("execution_mode", "interactive"),
            conditions=d.get("conditions", {}),
            parameter_preset=d.get("parameter_preset", {}),
            is_enabled=d.get("is_enabled", True),
            use_default_filters=d.get("use_default_filters", False),
            schedule_config=d.get("schedule_config", {}),
            dcc=d.get("dcc", ""),
            filter_preset_id=d.get("filter_preset_id", ""),
            parameter_preset_id=d.get("parameter_preset_id", ""),
        )

    # ------------------------------------------------------------------
    # Manifest trigger sync
    # ------------------------------------------------------------------

    def sync_manifest_triggers(self, tools: List[Any]) -> int:
        """Sync manifest triggers into triggers.json (full reconciliation).

        For each tool with ``triggers`` in its manifest.json:
        - Insert new triggers (by manifest_id + tool_id)
        - Update existing triggers if manifest content changed
        - Remove triggers whose manifest_id no longer exists in manifest

        Args:
            tools: list of ScannedTool (or any object with .manifest dict
                   and a tool id derivable from manifest["id"]).

        Returns:
            Number of changes (inserts + updates + deletes).
        """
        changes = 0

        with _lock:
            all_rules = _load_all()

            # Build index: (tool_id, manifest_id) → rule index in all_rules
            existing_index: Dict[tuple, int] = {}
            for idx, r in enumerate(all_rules):
                mid = r.get("manifest_id", "")
                tid = r.get("tool_id", "")
                if mid and tid:
                    existing_index[(tid, mid)] = idx

            # Collect all valid (tool_id, manifest_id) from current manifests
            current_manifest_keys: set = set()

            for tool in tools:
                manifest = getattr(tool, "manifest", None) or {}
                tool_source = getattr(tool, "source", "") or manifest.get("source", "user")
                tool_name = manifest.get("name", "")
                if not tool_name:
                    continue

                tool_id = f"{tool_source}/{tool_name}"
                manifest_triggers = manifest.get("triggers", [])
                if not isinstance(manifest_triggers, list):
                    continue

                for mt in manifest_triggers:
                    manifest_id = mt.get("id", "")
                    if not manifest_id:
                        continue
                    key = (tool_id, manifest_id)
                    current_manifest_keys.add(key)

                    if key in existing_index:
                        # Trigger already exists in triggers.json — do NOT overwrite
                        # user modifications with stale manifest content.
                        # The user's edits are the source of truth; _sync_rule_to_manifest
                        # writes them back to manifest.json after every update_trigger call.
                        pass
                    else:
                        # Insert new trigger from manifest (first time only)
                        rule = self._manifest_trigger_to_rule(tool_id, mt)
                        all_rules.append(rule)
                        changes += 1

            # Remove triggers whose manifest_id no longer exists in any manifest
            # (only for tools that have manifests — don't touch user-created triggers without manifest_id)
            tool_ids_with_manifests = {k[0] for k in current_manifest_keys}

            # Also build set of all currently scanned tool_ids (for orphan detection)
            # When a tool is renamed, its old tool_id won't appear in any manifest scan.
            # If triggers.json has a manifest_id-bound rule pointing to an unknown tool_id,
            # it's an orphan left over from a rename — safe to remove.
            all_known_tool_ids = {k[0] for k in current_manifest_keys}

            cleaned = []
            for r in all_rules:
                mid = r.get("manifest_id", "")
                tid = r.get("tool_id", "")
                if mid and tid:
                    if tid in tool_ids_with_manifests:
                        # Known tool with manifests: keep only if manifest_id still exists
                        if (tid, mid) in current_manifest_keys:
                            cleaned.append(r)
                        else:
                            changes += 1  # manifest trigger removed from manifest → delete
                    elif tid not in all_known_tool_ids:
                        # Orphan: tool_id not found in any current manifest scan
                        # (likely caused by a tool rename). Safe to remove.
                        logger.info(
                            "Removing orphan trigger rule (tool renamed or deleted): "
                            "tool_id=%r manifest_id=%r name=%r",
                            tid, mid, r.get("name", "")
                        )
                        changes += 1
                    else:
                        # Known tool but without manifest triggers — keep user-created rule
                        cleaned.append(r)
                else:
                    # User-created trigger (no manifest_id) — always keep
                    cleaned.append(r)
            all_rules = cleaned

            if changes > 0:
                _save_all(all_rules)

        if changes > 0:
            logger.info("Synced manifest triggers: %d changes", changes)
        return changes

    @staticmethod
    def _manifest_trigger_to_rule(
        tool_id: str, mt: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert a manifest trigger to the internal triggers.json format.

        Manifest format:
          { id, name, enabled, trigger: {type, ...}, filters: {...}, execution: {mode, ...} }

        Internal format:
          { id, tool_id, manifest_id, name, trigger_type, event_type,
            execution_mode, is_enabled, conditions, schedule_config, dcc, ... }
        """
        trigger_block = mt.get("trigger", {})
        trigger_type = trigger_block.get("type", "manual")
        execution_block = mt.get("execution", {})
        filters_block = mt.get("filters", {})

        # Map trigger type specifics
        event_type = ""
        dcc = ""
        schedule_config: Dict[str, Any] = {}

        if trigger_type == "event":
            # event field is the full value including timing suffix, e.g. "asset.save.pre"
            event_type = trigger_block.get("event", "")
            dcc = trigger_block.get("dcc", "")
        elif trigger_type == "schedule":
            schedule_config = {
                k: v for k, v in trigger_block.items() if k != "type"
            }
        elif trigger_type == "watch":
            # watch specifics go into schedule_config as storage
            schedule_config = {
                "watch_events": trigger_block.get("events", []),
                "debounce_ms": trigger_block.get("debounceMs", 1000),
            }

        # Map filters to conditions
        conditions: Dict[str, Any] = {}
        if filters_block:
            conditions = filters_block  # pass through as-is

        return {
            "id": str(uuid.uuid4()),
            "manifest_id": mt.get("id", ""),  # for dedup
            "tool_id": tool_id,
            "name": mt.get("name", ""),
            "trigger_type": trigger_type,
            "event_type": event_type,   # full value, e.g. "asset.save.pre"
            "execution_mode": execution_block.get("mode", "notify"),
            "is_enabled": mt.get("enabled", True),
            "use_default_filters": mt.get("useDefaultFilters", False),
            "conditions": conditions,
            "parameter_preset": {},
            "schedule_config": schedule_config,
            "dcc": dcc,
            "filter_preset_id": "",
            "parameter_preset_id": mt.get("presetId", ""),
        }

    def _append_rule_to_manifest(self, rule: Dict[str, Any]) -> None:
        """将新建的触发规则追加到工具的 manifest.json triggers 数组中。"""
        tool_id = rule.get("tool_id", "")
        if not tool_id:
            return

        from .tool_scanner import scan_tools
        tool_path = None
        for scanned in scan_tools():
            sid = f"{scanned.source}/{scanned.name}"
            if sid == tool_id:
                tool_path = scanned.tool_path
                break
        if not tool_path:
            return

        manifest_path = os.path.join(tool_path, "manifest.json")
        if not os.path.exists(manifest_path):
            return

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            triggers = manifest.setdefault("triggers", [])
            if not isinstance(triggers, list):
                manifest["triggers"] = []
                triggers = manifest["triggers"]

            # 构建 manifest 格式的 trigger 条目
            manifest_entry = {
                "id": rule["manifest_id"],
                "name": rule.get("name", ""),
                "enabled": rule.get("is_enabled", True),
                "trigger": {
                    "type": rule.get("trigger_type", "event"),
                    "event": rule.get("event_type", ""),
                    "dcc": rule.get("dcc", ""),
                },
                "execution": {
                    "mode": rule.get("execution_mode", "notify"),
                },
                "useDefaultFilters": rule.get("use_default_filters", False),
            }
            if rule.get("conditions"):
                manifest_entry["filters"] = rule["conditions"]

            triggers.append(manifest_entry)

            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.warning("Failed to append rule to manifest: %s", e)

    def _sync_rule_to_manifest(self, rule: Dict[str, Any]) -> None:
        """Write trigger rule changes back to the source manifest.json.

        This ensures sync_manifest_triggers won't overwrite user edits.
        Uses tool_scanner directly to avoid triggering a full scan+sync cycle.
        """
        manifest_id = rule.get("manifest_id", "")
        tool_id = rule.get("tool_id", "")
        if not manifest_id or not tool_id:
            return

        # Resolve manifest path from the scanner (no full scan, just path lookup)
        from .tool_scanner import scan_tools
        tool_path = None
        for scanned in scan_tools():
            sid = f"{scanned.source}/{scanned.name}"
            if sid == tool_id:
                tool_path = scanned.tool_path
                break
        if not tool_path:
            return

        manifest_path = os.path.join(tool_path, "manifest.json")
        if not os.path.exists(manifest_path):
            return

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            triggers = manifest.get("triggers", [])
            if not isinstance(triggers, list):
                return

            for mt in triggers:
                if mt.get("id") == manifest_id:
                    # Update manifest trigger fields from rule
                    mt["name"] = rule.get("name", mt.get("name", ""))
                    mt["enabled"] = rule.get("is_enabled", True)

                    trigger_block = mt.setdefault("trigger", {})
                    trigger_block["type"] = rule.get("trigger_type", "event")
                    if rule.get("trigger_type") == "event":
                        trigger_block["event"] = rule.get("event_type", "")   # full value
                        trigger_block["dcc"] = rule.get("dcc", "")

                    exec_block = mt.setdefault("execution", {})
                    exec_block["mode"] = rule.get("execution_mode", "notify")

                    if rule.get("use_default_filters") is not None:
                        mt["useDefaultFilters"] = rule.get("use_default_filters")
                    if rule.get("conditions"):
                        mt["filters"] = rule["conditions"]
                    break

            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.warning("Failed to sync rule to manifest: %s", e)
