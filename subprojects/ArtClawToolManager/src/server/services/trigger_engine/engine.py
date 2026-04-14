# Ref: docs/specs/trigger-mechanism.md
"""
TriggerEngine — rule-based trigger engine for DCC events and schedules.

Supported trigger types:
    - event:    DCC event (asset.save, level.load, …)
    - schedule: interval / once timer
    - watch:    file-system change via WatchManager (watchdog)

Lifecycle:
    engine = TriggerEngine()
    await engine.start()
    result = await engine.handle_dcc_event("asset.save", {...})
    await engine.stop()

Rules are loaded from ``~/.artclaw/triggers.json`` (no database).
"""
from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from typing import Any, Callable, Coroutine, Dict, List, Optional

from .filter_evaluator import FilterEvaluator
from .schedule_manager import ScheduleManager
from .watch_manager import WatchManager

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
    """Rule-based trigger engine for DCC events, schedules, and file watches."""

    def __init__(self) -> None:
        self._filter = FilterEvaluator()
        self._scheduler = ScheduleManager()
        self._watcher: Optional[WatchManager] = None
        self._running = False
        self._rules_cache: Dict[str, Dict[str, Any]] = {}   # rule_id → rule dict
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Load all enabled rules from JSON and start scheduler + watcher."""
        self._running = True
        self._loop = asyncio.get_event_loop()

        # Start file watcher (watchdog runs in a background thread)
        self._watcher = WatchManager(self._loop, self._on_watch_trigger)
        self._watcher.start()

        rules = self._load_enabled_rules()
        for rule in rules:
            await self._register_rule(rule)

        await self._scheduler.start()
        logger.info(
            "TriggerEngine started — %d rules (schedule: %d, watch: %d, event: %d)",
            len(rules),
            self._scheduler.job_count,
            self._watcher.rule_count if self._watcher else 0,
            sum(1 for r in self._rules_cache.values() if r.get("trigger_type") == "event"),
        )

    async def stop(self) -> None:
        """Stop scheduler, watcher, and clear caches."""
        self._running = False
        await self._scheduler.stop()
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
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
        """Reload all rules from JSON file (hot-reload)."""
        await self._scheduler.stop()
        if self._watcher:
            self._watcher.stop()
            self._watcher = WatchManager(self._loop, self._on_watch_trigger)
            self._watcher.start()

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
            "watch_rules": self._watcher.rule_count if self._watcher else 0,
            "event_rules": sum(
                1 for r in self._rules_cache.values()
                if r.get("trigger_type") == "event"
            ),
        }

    # ------------------------------------------------------------------
    # Internal callbacks
    # ------------------------------------------------------------------

    async def _on_schedule_trigger(self, rule_id: str) -> None:
        rule = self._rules_cache.get(rule_id)
        if not rule:
            return
        logger.info("Schedule triggered rule: %s (%s)", rule.get("name"), rule_id)
        await self._execute_rule(rule, {"trigger": "schedule"})

    async def _on_watch_trigger(self, rule_id: str, file_path: str) -> None:
        rule = self._rules_cache.get(rule_id)
        if not rule:
            return
        logger.info(
            "Watch triggered rule: %s (%s) — file: %s",
            rule.get("name"), rule_id, file_path,
        )
        await self._execute_rule(rule, {"trigger": "watch", "file_path": file_path})

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
        """Load enabled rules from triggers.json and normalise to internal format."""
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

        ttype = rule["trigger_type"]

        if ttype == "schedule" and rule.get("schedule_config"):
            config = rule["schedule_config"]
            if isinstance(config, str):
                try:
                    config = json.loads(config)
                except (json.JSONDecodeError, TypeError):
                    return
            # Normalise schedule_config to ScheduleManager format:
            #   manifest uses: {"mode": "interval", "interval": <ms>}
            #                  {"mode": "once",     "run_at": <unix_ts>}
            #   ScheduleManager expects: {"type": "interval", "seconds": <s>}
            #                            {"type": "once",     "run_at": <unix_ts>}
            stype = config.get("type") or config.get("mode", "interval")
            normalised: Dict[str, Any] = {"type": stype}
            if stype == "interval":
                # Accept seconds (new) or interval_ms (legacy manifest)
                if "seconds" in config:
                    normalised["seconds"] = float(config["seconds"])
                elif "interval" in config:
                    normalised["seconds"] = float(config["interval"]) / 1000.0
                else:
                    normalised["seconds"] = 3600.0  # 1h fallback
            elif stype == "once":
                normalised["run_at"] = config.get("run_at")
            self._scheduler.add_job(rule_id, normalised, self._on_schedule_trigger)

        elif ttype == "watch" and self._watcher:
            self._watcher.register_rule(rule)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def _execute_rule(
        self, rule: Dict[str, Any], event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the tool associated with a trigger rule.

        For general (non-DCC) script tools: run via subprocess.
        For DCC tools: send to dcc_manager (if available).
        For interactive mode: emit a navigation event over WebSocket.
        Handles 'notify' mode by creating an alert.
        """
        tool_id = rule.get("tool_id")
        exec_mode = rule.get("exec_mode", "notify")
        params = rule.get("param_presets") or {}

        if isinstance(params, str):
            try:
                params = json.loads(params)
            except (json.JSONDecodeError, TypeError):
                params = {}

        logger.info(
            "Executing rule '%s': tool=%s mode=%s",
            rule.get("name"), tool_id, exec_mode,
        )

        # ----- Load tool manifest -----
        try:
            from ..tool_service import ToolService
            from ..config_manager import ConfigManager
            config = ConfigManager()
            tool_svc = ToolService(config)
            tool_svc._scan_and_build()
            tool = tool_svc.get_tool(tool_id)
        except Exception as e:
            logger.error("Failed to load tool '%s': %s", tool_id, e)
            return {"success": False, "error": "TOOL_LOAD_FAILED", "detail": str(e)}

        if not tool:
            logger.error("Tool not found: %s", tool_id)
            return {"success": False, "error": "TOOL_NOT_FOUND"}

        manifest = tool.manifest or {}
        impl = manifest.get("implementation", {})
        impl_type = impl.get("type", "script")
        target_dccs = [d for d in (manifest.get("targetDCCs") or []) if d and d != "general"]

        # ----- Interactive mode → emit navigation event to frontend -----
        if exec_mode == "interactive":
            command = f"/run tool:{tool_id}"
            await self._emit_navigate(command, tool_id, params)
            return {
                "success": True,
                "tool_id": tool_id,
                "execution_mode": "interactive",
                "action": "navigate",
                "target": "/chat",
                "command": command,
            }

        # ----- Silent / notify mode → actually execute -----
        exec_output = ""
        success = True
        error_msg = ""

        try:
            if target_dccs:
                # DCC tool — route through DCCManager
                exec_output, success, error_msg = await self._run_on_dcc(
                    tool, impl, target_dccs, params, event_data
                )
            else:
                # General (local) script tool
                exec_output, success, error_msg = await self._run_local_script(
                    tool, impl, params, event_data
                )
        except Exception as exc:
            success = False
            error_msg = str(exc)
            logger.exception("Execution error for rule '%s'", rule.get("name"))

        result = {
            "success": success,
            "tool_id": tool_id,
            "execution_mode": exec_mode,
            "implementation_type": impl_type,
            "output": exec_output,
        }
        if not success:
            result["error"] = error_msg

        # ----- Notify mode → create alert -----
        if exec_mode == "notify":
            await self._create_alert(rule, tool.name, success, exec_output, error_msg)

        return result

    # ------------------------------------------------------------------
    # Execution helpers
    # ------------------------------------------------------------------

    async def _run_local_script(
        self,
        tool: Any,
        impl: Dict[str, Any],
        params: Dict[str, Any],
        event_data: Dict[str, Any],
    ) -> tuple[str, bool, str]:
        """Run a general (non-DCC) script tool in a subprocess.

        Uses asyncio.to_thread + subprocess.run (blocking) to avoid the
        Windows SelectorEventLoop limitation with create_subprocess_exec.
        """
        import os
        import subprocess as _subprocess
        entry = impl.get("entry", "main.py")
        function = impl.get("function", "main")
        tool_path = tool.tool_path or ""
        script_path = os.path.join(tool_path, entry)

        if not os.path.isfile(script_path):
            return "", False, f"Script not found: {script_path}"

        # Build a small driver snippet so we can pass params cleanly via JSON.
        # Tools may have any signature; we try (params, event_data) first, then
        # fall back to calling the entry function with no arguments.
        driver_code = (
            "import sys, os, json\n"
            f"tool_dir = {repr(tool_path)}\n"
            "if tool_dir not in sys.path:\n"
            "    sys.path.insert(0, tool_dir)\n"
            "import importlib, inspect\n"
            f"mod = importlib.import_module({repr(entry.replace('.py', ''))})\n"
            f"fn = getattr(mod, {repr(function)})\n"
            f"params = json.loads({repr(json.dumps(params))})\n"
            f"event_data = json.loads({repr(json.dumps(event_data))})\n"
            "sig = inspect.signature(fn)\n"
            "_param_names = list(sig.parameters.keys())\n"
            "if 'params' in _param_names and 'event_data' in _param_names:\n"
            "    result = fn(params=params, event_data=event_data)\n"
            "elif 'params' in _param_names:\n"
            "    result = fn(params=params)\n"
            "elif _param_names:\n"
            "    result = fn(**{k: v for k, v in {**params, 'event_data': event_data}.items() if k in _param_names})\n"
            "else:\n"
            "    result = fn()\n"
            "print(result)\n"
        )

        def _run_sync() -> tuple[str, bool, str]:
            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                proc = _subprocess.run(
                    [sys.executable, "-c", driver_code],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                )
                out = proc.stdout.strip()
                err = proc.stderr.strip()
                if err:
                    logger.warning("Tool stderr [%s]:\n%s", tool.name, err)
                if proc.returncode != 0:
                    return out, False, err or f"Exit code {proc.returncode}"
                return out, True, ""
            except _subprocess.TimeoutExpired:
                return "", False, "Execution timed out (120 s)"

        return await asyncio.to_thread(_run_sync)

    async def _run_on_dcc(
        self,
        tool: Any,
        impl: Dict[str, Any],
        target_dccs: List[str],
        params: Dict[str, Any],
        event_data: Dict[str, Any],
    ) -> tuple[str, bool, str]:
        """Send execution to a DCC via DCCManager.

        Tries each target DCC in order; uses the first connected one.
        """
        # Access dcc_manager from FastAPI app.state (injected at startup)
        try:
            from ...main import dcc_manager  # type: ignore
        except ImportError:
            return "", False, "DCCManager not available"

        import os
        entry = impl.get("entry", "main.py")
        function = impl.get("function", "main")
        tool_path = tool.tool_path or ""

        code = (
            "import sys, os, json\n"
            f"tool_dir = {repr(tool_path)}\n"
            "if tool_dir not in sys.path:\n"
            "    sys.path.insert(0, tool_dir)\n"
            "import importlib\n"
            f"mod = importlib.import_module({repr(entry.replace('.py', ''))})\n"
            f"params = json.loads({repr(json.dumps(params))})\n"
            f"event_data = json.loads({repr(json.dumps(event_data))})\n"
            f"result = mod.{function}(params=params, event_data=event_data)\n"
            "print(result)\n"
        )

        for dcc_name in target_dccs:
            try:
                result = await dcc_manager.execute_on_dcc(dcc_name, code)
                output = result.get("output", "") if isinstance(result, dict) else str(result)
                return output, True, ""
            except Exception as e:
                logger.warning("DCC '%s' execution failed: %s", dcc_name, e)
                continue

        return "", False, f"No connected DCC available in {target_dccs}"

    async def _create_alert(
        self,
        rule: Dict[str, Any],
        tool_name: str,
        success: bool,
        output: str,
        error_msg: str,
    ) -> None:
        """Create an alert entry for notify-mode executions.

        Note: Alert.level only supports 'warning' | 'error'.
        Successful notify-mode executions create a 'warning' (informational) alert;
        failures create an 'error' alert.
        """
        try:
            from ..alert_service import AlertService
            from ...schemas.alert import AlertCreateRequest
            svc = AlertService()
            level = "warning" if success else "error"
            trigger_name = rule.get("name", rule.get("id", "unknown"))
            title = (
                f"触发执行完成: {tool_name} ({trigger_name})"
                if success
                else f"触发执行失败: {tool_name} ({trigger_name})"
            )
            detail = (output[:1900] if output else "执行完成，无输出") if success else (error_msg or "Unknown error")
            req = AlertCreateRequest(
                source=f"trigger/{rule.get('tool_id', '')}",
                level=level,
                title=title,
                detail=detail,
                metadata={
                    "rule_id": rule.get("id"),
                    "trigger_type": rule.get("trigger_type"),
                    "tool_id": rule.get("tool_id"),
                },
            )
            svc.create_alert(req)
        except Exception as e:
            logger.warning("Failed to create trigger alert: %s", e)

    async def _emit_navigate(
        self, command: str, tool_id: str, params: Dict[str, Any]
    ) -> None:
        """Broadcast a navigate event to connected WebSocket clients."""
        try:
            from ...main import ws_manager  # type: ignore
            await ws_manager.broadcast({
                "type": "navigate",
                "target": "/chat",
                "command": command,
                "tool_id": tool_id,
                "parameters": params,
            })
        except Exception as e:
            logger.debug("Failed to emit navigate event: %s", e)

    def _build_execution_code(self, tool_path: str, entry: str, function: str, params: dict) -> str:
        """Legacy helper retained for compatibility."""
        import os
        script_path = os.path.join(tool_path, entry).replace("\\", "/")
        param_parts = []
        for k, v in params.items():
            if isinstance(v, str):
                param_parts.append(f'{k}="{v}"')
            else:
                param_parts.append(f'{k}={v}')
        params_str = ", ".join(param_parts)
        return (
            f'import sys, os\n'
            f'tool_dir = r"{tool_path}"\n'
            'if tool_dir not in sys.path:\n'
            '    sys.path.insert(0, tool_dir)\n'
            'import importlib\n'
            f'mod = importlib.import_module("{entry.replace(".py", "")}")\n'
            f'result = mod.{function}({params_str})\n'
            'print(result)\n'
        )

