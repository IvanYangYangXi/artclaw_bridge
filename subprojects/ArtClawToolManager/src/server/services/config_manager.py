# Ref: docs/features/phase2-skill-management.md#ConfigManager
"""
Configuration manager for ``~/.artclaw/config.json``.

Provides thread-safe read/write with file-lock and atomic writes.
The JSON structure stores pinned / disabled / favorites / installed skills
and recent usage records.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.config import settings

# Default config skeleton
_DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "1.0",
    "skills": {
        "pinned": [],
        "disabled": [],
        "favorites": [],
        "installed": {},
    },
    "recent": {
        "skills": [],
    },
}

_MAX_RECENT = 50


class ConfigManager:
    """Thread-safe JSON config reader/writer."""

    def __init__(self, path: Optional[Path] = None):
        self._path = path or settings.config_json_path
        self._lock = threading.Lock()

    # ---- low-level ----

    def _read(self) -> Dict[str, Any]:
        if not self._path.exists():
            return json.loads(json.dumps(_DEFAULT_CONFIG))
        with open(self._path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: Dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: write to temp, then rename.
        fd, tmp = tempfile.mkstemp(
            dir=str(self._path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # On Windows, target must not exist for os.replace to succeed.
            os.replace(tmp, str(self._path))
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    # ---- public helpers ----

    def load(self) -> Dict[str, Any]:
        with self._lock:
            return self._read()

    def save(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self._write(data)

    def _ensure_structure(self, cfg: Dict) -> Dict:
        """Fill missing keys with defaults."""
        for k, v in _DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        for k, v in _DEFAULT_CONFIG["skills"].items():
            cfg["skills"].setdefault(k, v if not isinstance(v, dict) else {})
        cfg["recent"].setdefault("skills", [])
        return cfg

    # ---- skill pinned ----

    def get_pinned_skills(self) -> List[str]:
        return self.load().get("skills", {}).get("pinned", [])

    def set_pinned(self, skill_id: str, pinned: bool) -> None:
        with self._lock:
            cfg = self._ensure_structure(self._read())
            lst: List[str] = cfg["skills"]["pinned"]
            if pinned and skill_id not in lst:
                lst.append(skill_id)
            elif not pinned and skill_id in lst:
                lst.remove(skill_id)
            self._write(cfg)

    # ---- skill disabled ----

    def get_disabled_skills(self) -> List[str]:
        return self.load().get("skills", {}).get("disabled", [])

    def set_disabled(self, skill_id: str, disabled: bool) -> None:
        with self._lock:
            cfg = self._ensure_structure(self._read())
            lst: List[str] = cfg["skills"]["disabled"]
            if disabled and skill_id not in lst:
                lst.append(skill_id)
            elif not disabled and skill_id in lst:
                lst.remove(skill_id)
            self._write(cfg)

    # ---- skill favorites ----

    def get_favorite_skills(self) -> List[str]:
        return self.load().get("skills", {}).get("favorites", [])

    def set_favorite(self, skill_id: str, favorited: bool) -> None:
        with self._lock:
            cfg = self._ensure_structure(self._read())
            lst: List[str] = cfg["skills"]["favorites"]
            if favorited and skill_id not in lst:
                lst.append(skill_id)
            elif not favorited and skill_id in lst:
                lst.remove(skill_id)
            self._write(cfg)

    # ---- recent usage ----

    def record_skill_usage(self, skill_id: str) -> None:
        from datetime import datetime, timezone

        with self._lock:
            cfg = self._ensure_structure(self._read())
            recent: List[Dict] = cfg["recent"]["skills"]
            recent = [r for r in recent if r.get("id") != skill_id]
            recent.insert(0, {
                "id": skill_id,
                "used_at": datetime.now(timezone.utc).isoformat(),
            })
            cfg["recent"]["skills"] = recent[:_MAX_RECENT]
            self._write(cfg)

    def get_recent_skills(self, limit: int = 10) -> List[Dict]:
        recent = self.load().get("recent", {}).get("skills", [])
        return recent[:limit]
