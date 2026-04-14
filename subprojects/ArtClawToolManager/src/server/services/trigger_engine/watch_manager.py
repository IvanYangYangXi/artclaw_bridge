# Ref: docs/specs/trigger-mechanism.md
"""
WatchManager — file-system watcher for watch-type trigger rules.

Uses ``watchdog`` to monitor directories derived from
``conditions.path`` patterns (supports $variable expansion).

Lifecycle:
    mgr = WatchManager(callback)
    mgr.start()
    mgr.register_rule(rule)   # can be called after start()
    mgr.unregister_rule(rule_id)
    mgr.stop()

The *callback* is a coroutine ``async def on_change(rule_id, path) -> None``
that will be scheduled into the engine's event loop via
``asyncio.run_coroutine_threadsafe``.
"""
from __future__ import annotations

import asyncio
import fnmatch
import logging
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path variable resolution
# ---------------------------------------------------------------------------

def _resolve_path_variables(pattern: str) -> Optional[str]:
    """Expand $variable tokens in a path pattern to absolute paths.

    Supported variables (matches trigger-mechanism.md §3.1.1):
        $skills_installed  → resolved via config.settings.skills_path (platform-aware)
        $project_root      → settings.PROJECT_ROOT or auto-detected from bridge_config.py location
        $tools_dir         → settings.data_path / "tools"  (i.e. ~/.artclaw/tools, respects DATA_DIR override)
        $home              → Path.home()
    """
    from ...core.config import settings  # local import avoids circular deps
    import os

    variables: Dict[str, str] = {
        "$home": str(Path.home()),
        "$tools_dir": str(settings.data_path / "tools"),
        "$skills_installed": str(settings.skills_path),
    }

    # Try to get project_root from settings env var, then auto-detect
    project_root = os.environ.get("ARTCLAW_PROJECT_ROOT")
    if not project_root:
        try:
            # Walk up from this file to find artclaw_bridge root (contains core/bridge_config.py)
            for parent in Path(__file__).resolve().parents:
                if (parent / "core" / "bridge_config.py").exists():
                    project_root = str(parent)
                    break
        except Exception:
            pass
    if project_root:
        variables["$project_root"] = str(project_root)

    for var, replacement in variables.items():
        if var in pattern:
            pattern = pattern.replace(var, replacement)

    if "$" in pattern:
        logger.debug("Unresolved path variable in pattern: %s", pattern)
        return None  # unresolvable variable → skip

    return pattern


def _normalise_patterns(raw: Any) -> List[str]:
    """Normalise a conditions dimension value to a flat list of pattern strings.

    Supports three formats:
        "pattern_string"
        ["pattern_string", ...]
        [{"pattern": "pattern_string"}, ...]
    """
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw]
    result: List[str] = []
    for item in raw:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            p = item.get("pattern") or item.get("value") or ""
            if p:
                result.append(str(p))
    return result


def _extract_watch_dirs(conditions: Dict[str, Any]) -> List[str]:
    """Extract concrete watch directories from a rule's conditions.path list.

    Each entry may be a glob like ``$skills_installed/**/*.md``.
    We watch the longest non-glob prefix as a directory.
    """
    patterns = _normalise_patterns(conditions.get("path", []))

    dirs: List[str] = []
    for pattern in patterns:
        resolved = _resolve_path_variables(pattern)
        if not resolved:
            continue
        # Find the non-glob prefix by splitting on path separators
        norm = resolved.replace("\\", "/")
        segments = norm.split("/")
        non_glob_segs = []
        for seg in segments:
            if any(c in seg for c in ("*", "?", "[")):
                break
            non_glob_segs.append(seg)
        if not non_glob_segs:
            continue
        watch_dir = "/".join(non_glob_segs)
        # On Windows, a drive-only prefix like "C:" needs a trailing slash
        if len(watch_dir) == 2 and watch_dir[1] == ":":
            watch_dir += "/"
        watch_dir = str(Path(watch_dir))
        if os.path.isdir(watch_dir):
            dirs.append(watch_dir)
        else:
            logger.debug("Watch dir does not exist (skipping): %s", watch_dir)
    return dirs


def _pattern_matches_path(conditions: Dict[str, Any], file_path: str) -> bool:
    """Check if *file_path* matches the conditions.path and conditions.name patterns."""
    path_patterns = _normalise_patterns(conditions.get("path", []))
    name_patterns = _normalise_patterns(conditions.get("name", []))

    # Normalize to forward slashes for matching
    norm_path = file_path.replace("\\", "/")
    basename = os.path.basename(file_path)

    # Check path patterns (glob, OR within dimension)
    if path_patterns:
        path_ok = False
        for raw_pattern in path_patterns:
            resolved = _resolve_path_variables(raw_pattern)
            if not resolved:
                continue
            resolved = resolved.replace("\\", "/")
            if fnmatch.fnmatch(norm_path, resolved):
                path_ok = True
                break
        if not path_ok:
            return False

    # Check name patterns (regex, OR within dimension)
    if name_patterns:
        name_ok = False
        for pattern in name_patterns:
            try:
                if re.search(pattern, basename):
                    name_ok = True
                    break
            except re.error:
                if pattern == basename:
                    name_ok = True
                    break
        if not name_ok:
            return False

    return True


# ---------------------------------------------------------------------------
# Watchdog event handler
# ---------------------------------------------------------------------------

class _RuleEventHandler(FileSystemEventHandler):
    """Watchdog handler that fans out file events to matching rules."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        callback: Callable[[str, str], Coroutine[Any, Any, None]],
    ) -> None:
        super().__init__()
        self._loop = loop
        self._callback = callback
        # rule_id → (rule dict, debounce_ms)
        self._rules: Dict[str, Dict[str, Any]] = {}
        # rule_id → last_triggered_ts
        self._debounce: Dict[str, float] = {}

    def add_rule(self, rule: Dict[str, Any]) -> None:
        self._rules[rule["id"]] = rule

    def remove_rule(self, rule_id: str) -> None:
        self._rules.pop(rule_id, None)
        self._debounce.pop(rule_id, None)

    def _handle(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        file_path = event.src_path

        for rule_id, rule in list(self._rules.items()):
            conditions = rule.get("conditions") or {}
            watch_events = rule.get("schedule_config", {}).get("watch_events", [])
            debounce_ms = rule.get("schedule_config", {}).get("debounce_ms", 1000)

            # Check event type filter (created / modified / deleted / moved)
            if watch_events:
                ev_type = event.event_type  # "created", "modified", "deleted", "moved"
                if ev_type not in watch_events:
                    continue

            # Check path/name conditions
            if not _pattern_matches_path(conditions, file_path):
                continue

            # Debounce
            now = time.monotonic()
            last = self._debounce.get(rule_id, 0.0)
            if (now - last) * 1000 < debounce_ms:
                continue
            self._debounce[rule_id] = now

            # Fire callback in the asyncio event loop
            asyncio.run_coroutine_threadsafe(
                self._callback(rule_id, file_path), self._loop
            )

    def on_created(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_deleted(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        self._handle(event)


# ---------------------------------------------------------------------------
# WatchManager
# ---------------------------------------------------------------------------

class WatchManager:
    """Manage file-system watches for watch-type trigger rules."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        callback: Callable[[str, str], Coroutine[Any, Any, None]],
    ) -> None:
        self._loop = loop
        self._callback = callback
        self._observer: Optional[Observer] = None
        self._handler = _RuleEventHandler(loop, callback)
        # watch_dir → watchdog Watch handle
        self._watches: Dict[str, Any] = {}
        # rule_id → set of watch_dirs
        self._rule_dirs: Dict[str, Set[str]] = defaultdict(set)
        # rule_id → rule dict (for re-registration)
        self._rules: Dict[str, Dict[str, Any]] = {}

    def start(self) -> None:
        self._observer = Observer()
        self._observer.start()
        logger.info("WatchManager started")

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        self._watches.clear()
        self._rule_dirs.clear()
        self._rules.clear()
        logger.info("WatchManager stopped")

    def register_rule(self, rule: Dict[str, Any]) -> None:
        """Register a watch rule; sets up watchdog watches for its directories."""
        if not self._observer:
            return
        rule_id = rule["id"]
        conditions = rule.get("conditions") or {}
        dirs = _extract_watch_dirs(conditions)

        if not dirs:
            logger.warning(
                "Watch rule '%s' has no resolvable watch directories — rule inactive",
                rule.get("name", rule_id),
            )
            return

        self._rules[rule_id] = rule
        self._handler.add_rule(rule)

        for watch_dir in dirs:
            if watch_dir not in self._watches:
                watch_handle = self._observer.schedule(
                    self._handler, watch_dir, recursive=True
                )
                self._watches[watch_dir] = watch_handle
                logger.info("WatchManager: watching %s", watch_dir)
            self._rule_dirs[rule_id].add(watch_dir)

        logger.info(
            "Registered watch rule '%s' (%s) → %d dirs",
            rule.get("name", rule_id), rule_id, len(dirs),
        )

    def unregister_rule(self, rule_id: str) -> None:
        """Unregister a watch rule; removes unneeded directory watches."""
        if rule_id not in self._rules:
            return
        self._handler.remove_rule(rule_id)
        self._rule_dirs.pop(rule_id, None)
        self._rules.pop(rule_id, None)

        # Unschedule dirs no longer referenced by any rule
        if self._observer:
            all_watched_dirs: Set[str] = set()
            for dirs in self._rule_dirs.values():
                all_watched_dirs |= dirs
            for watch_dir, handle in list(self._watches.items()):
                if watch_dir not in all_watched_dirs:
                    try:
                        self._observer.unschedule(handle)
                    except Exception:
                        pass
                    del self._watches[watch_dir]

    @property
    def rule_count(self) -> int:
        return len(self._rules)
