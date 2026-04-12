# Ref: docs/features/phase5-dcc-integration.md
"""
TriggerEngine — rule-based trigger engine for DCC events and schedules.

Lifecycle:
    engine = TriggerEngine()
    await engine.start()      # loads rules from JSON, starts scheduler
    ...
    result = await engine.handle_dcc_event("asset.save", {...})
    ...
    await engine.stop()

Rules are loaded from ``~/.artclaw/triggers.json`` (no database).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional

from .filter_evaluator import FilterEvaluator
from .schedule_manager import ScheduleManager

logger = logging.getLogger(__name__)


def _load_triggers_json() -> List[Dict[str, Any]]:
    """Load enabled trigger rules from ~/.artclaw/triggers.json."""
    from ...core.config import settings
    path = settings.data_path / "triggers.json"
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return [r for r in data if r.get("is_enabled", True)]
    except (json.JSONDecodeError, OSError):
        return []


class TriggerEngine:
    """Rule-based trigger engine for DCC events and schedules."""

    def __init__(self) -> None:
        self._filter = FilterEvaluator()
        self._scheduler = ScheduleManager()
        self._running = False
        self._rules_cache: Dict[str, Dict[str, Any]] = {}  # rule_id → rule dict

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Load all enabled rules from JSON and start scheduled jobs."""
        self._running = True
        rules = self._load_enabled_rules()
        for rule in rules:
            await self._register_rule(rule)
        await self._scheduler.start()
        logger.info("TriggerEngine started with %d rules", len(rules))

    async def stop(self) -> None:
        """Stop scheduler and clear caches."""
        self._running = False
        await self._scheduler.stop()
        self._rules_cache.clear()
        logger.info("TriggerEngine stopped")

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    async def handle_dcc_event(
        self, event_type: str, event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate all event rules against an incoming DCC event."""
        if not self._running:
            return self._empty_result()

        matched: List[str] = []
        executed: List[str] = []
        blocked = False
        block_reason = None

        sorted_rules = sorted(
            self._rules_cache.values(),
            key=lambda r: r.get("priority", 0),
            reverse=True,
        )

        for rule in sorted_rules:
            if rule.get("trigger_type") != "event":
                continue
            if not self._event_matches(rule, event_type, event_data):
                continue

            conditions = rule.get("conditions")
            if self._filter.evaluate(conditions, event_data):
                rule_id = rule["id"]
                matched.append(rule_id)
                try:
                    exec_result = await self._execute_rule(rule, event_data)
                    executed.append(rule_id)

                    if (event_data.get("timing") == "pre" and
                        exec_result and not exec_result.get("success", True)):
                        blocked = True
                        block_reason = exec_result.get("error", "Blocked by trigger rule")
                        break

                except Exception:
                    logger.exception("Failed to execute rule %s", rule_id)

        result = {
            "triggered": len(executed) > 0,
            "rules_matched": len(matched),
            "rules_executed": len(executed),
            "details": [
                {"rule_id": rid, "executed": rid in executed}
                for rid in matched
            ],
        }

        if event_data.get("timing") == "pre":
            result["blocked"] = blocked
            if block_reason:
                result["block_reason"] = block_reason

        return result

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    async def reload_rules(self) -> None:
        """Reload all rules from JSON file."""
        await self._scheduler.stop()
        self._rules_cache.clear()
        rules = self._load_enabled_rules()
        for rule in rules:
            await self._register_rule(rule)
        await self._scheduler.start()
        logger.info("TriggerEngine reloaded %d rules", len(rules))

    def get_stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "total_rules": len(self._rules_cache),
            "scheduled_jobs": self._scheduler.job_count,
            "event_rules": sum(
                1
                for r in self._rules_cache.values()
                if r.get("trigger_type") == "event"
            ),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        return {
            "triggered": False,
            "rules_matched": 0,
            "rules_executed": 0,
            "details": [],
        }

    @staticmethod
    def _event_matches(
        rule: Dict[str, Any], event_type: str, event_data: Dict[str, Any]
    ) -> bool:
        rule_evt = rule.get("event_type")
        if rule_evt and rule_evt != event_type:
            return False
        rule_dcc = rule.get("dcc_type")
        if rule_dcc and rule_dcc != event_data.get("dcc_type"):
            return False
        rule_timing = rule.get("event_timing")
        if rule_timing and rule_timing != event_data.get("timing", "post"):
            return False
        return True

    def _load_enabled_rules(self) -> List[Dict[str, Any]]:
        """Load enabled rules from triggers.json and normalize to internal format."""
        raw_rules = _load_triggers_json()
        rules: List[Dict[str, Any]] = []
        for row in raw_rules:
            rules.append({
                "id": row.get("id", ""),
                "name": row.get("name", ""),
                "tool_id": row.get("tool_id", ""),
                "trigger_type": row.get("trigger_type", "manual"),
                "event_type": row.get("event_type", ""),
                "event_timing": row.get("event_timing", "post"),
                "dcc_type": row.get("dcc_type"),
                "schedule_config": row.get("schedule_config", {}),
                "conditions": row.get("conditions", {}),
                "param_presets": row.get("parameter_preset", {}),
                "exec_mode": row.get("execution_mode", "notify"),
                "priority": row.get("priority", 0),
            })
        return rules

    async def _register_rule(self, rule: Dict[str, Any]) -> None:
        rule_id = rule["id"]
        self._rules_cache[rule_id] = rule

        if rule["trigger_type"] == "schedule" and rule.get("schedule_config"):
            config = rule["schedule_config"]
            if isinstance(config, str):
                try:
                    config = json.loads(config)
                except (json.JSONDecodeError, TypeError):
                    return
            self._scheduler.add_job(rule_id, config, self._on_schedule_trigger)

    async def _on_schedule_trigger(self, rule_id: str) -> None:
        rule = self._rules_cache.get(rule_id)
        if not rule:
            return
        logger.info("Schedule triggered rule: %s (%s)", rule.get("name"), rule_id)
        await self._execute_rule(rule, {"trigger": "schedule"})

    async def _execute_rule(
        self, rule: Dict[str, Any], event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the tool associated with a trigger rule."""
        tool_id = rule.get("tool_id")
        exec_mode = rule.get("exec_mode", "silent")
        params = rule.get("param_presets") or {}

        if isinstance(params, str):
            try:
                params = json.loads(params)
            except (json.JSONDecodeError, TypeError):
                params = {}

        logger.info("Executing rule '%s': tool=%s, mode=%s", rule.get("name"), tool_id, exec_mode)

        # Load tool manifest from filesystem
        from ..tool_service import ToolService
        from ..config_manager import ConfigManager
        config = ConfigManager()
        tool_svc = ToolService(config)
        tool_svc._scan_and_build()
        tool = tool_svc.get_tool(tool_id)

        if not tool:
            logger.error("Tool not found: %s", tool_id)
            return {"success": False, "error": "TOOL_NOT_FOUND"}

        manifest = tool.manifest or {}
        impl = manifest.get("implementation", {})
        impl_type = impl.get("type", "script")

        result = {
            "success": True,
            "tool_id": tool_id,
            "execution_mode": exec_mode,
            "implementation_type": impl_type,
        }

        if exec_mode == "interactive":
            result["action"] = "navigate"
            result["target"] = "/chat"
            result["command"] = f"/run tool:{tool_id}"
            result["parameters"] = params

        elif exec_mode in ("silent", "notify"):
            if impl_type == "script":
                entry = impl.get("entry", "main.py")
                function = impl.get("function", "main")
                tool_path = tool.tool_path or ""
                code = self._build_execution_code(tool_path, entry, function, params)
                result["code"] = code
                result["requires_dcc"] = True

            elif impl_type == "skill_wrapper":
                skill_id = impl.get("skill")
                fixed_params = impl.get("fixedParams", {})
                merged_params = {**fixed_params, **params}
                result["skill"] = skill_id
                result["parameters"] = merged_params
                result["requires_dcc"] = True

            elif impl_type == "composite":
                steps = impl.get("steps", [])
                result["steps"] = steps
                result["requires_dcc"] = True

        if exec_mode == "notify":
            result["notify"] = True
            result["notification"] = {
                "title": f"工具执行: {tool.name}",
                "message": f"触发规则 '{rule.get('name')}' 已执行",
                "tool_id": tool_id,
            }

        return result

    def _build_execution_code(self, tool_path: str, entry: str, function: str, params: dict) -> str:
        import os
        script_path = os.path.join(tool_path, entry).replace("\\", "/")

        param_parts = []
        for k, v in params.items():
            if isinstance(v, str):
                param_parts.append(f'{k}="{v}"')
            else:
                param_parts.append(f'{k}={v}')
        params_str = ", ".join(param_parts)

        code = f'''import sys, os
tool_dir = r"{tool_path}"
if tool_dir not in sys.path:
    sys.path.insert(0, tool_dir)

import importlib
mod = importlib.import_module("{entry.replace('.py', '')}")
result = mod.{function}({params_str})
print(result)
'''
        return code
