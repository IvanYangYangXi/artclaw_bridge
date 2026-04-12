"""
Filter preset business-logic service (JSON file storage).

Stores presets in:
- {project_root}/presets/filters/{id}.json (official/marketplace)
- ~/.artclaw/presets/filters/{id}.json (user)
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.config import settings
from ..schemas.filter_preset import (
    FilterPresetCreateRequest,
    FilterPresetUpdateRequest,
)


def _user_presets_dir() -> Path:
    p = settings.data_path / "presets" / "filters"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _project_presets_dir() -> Optional[Path]:
    """Try to read project_root from config.json."""
    config_path = settings.config_json_path
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            root = cfg.get("project_root")
            if root:
                p = Path(root) / "presets" / "filters"
                if p.is_dir():
                    return p
        except (json.JSONDecodeError, OSError):
            pass
    return None


_lock = threading.Lock()


class FilterPresetService:
    """FilterPreset CRUD (JSON file per preset)."""

    def list_presets(self, dcc: Optional[str] = None) -> List[Dict[str, Any]]:
        presets: List[Dict[str, Any]] = []

        # Load from project dir (official/marketplace)
        project_dir = _project_presets_dir()
        if project_dir:
            presets.extend(self._load_dir(project_dir, source="official"))

        # Load from user dir
        user_dir = _user_presets_dir()
        presets.extend(self._load_dir(user_dir, source="user"))

        # Filter by DCC if specified
        if dcc:
            presets = [
                p for p in presets
                if not p.get("dcc") or dcc in p.get("dcc", [])
            ]

        return presets

    def get_preset(self, preset_id: str) -> Optional[Dict[str, Any]]:
        # Search user dir first, then project dir
        user_path = _user_presets_dir() / f"{preset_id}.json"
        if user_path.exists():
            return self._load_file(user_path, source="user")

        project_dir = _project_presets_dir()
        if project_dir:
            proj_path = project_dir / f"{preset_id}.json"
            if proj_path.exists():
                return self._load_file(proj_path, source="official")

        return None

    def create_preset(self, req: FilterPresetCreateRequest) -> Dict[str, Any]:
        preset_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "id": preset_id,
            "name": req.name,
            "description": req.description,
            "dcc": req.dcc,
            "filter": req.filter.model_dump(),
            "source": "user",
            "created_at": now,
            "updated_at": now,
        }
        with _lock:
            path = _user_presets_dir() / f"{preset_id}.json"
            self._save_file(path, data)
        return data

    def update_preset(
        self, preset_id: str, req: FilterPresetUpdateRequest
    ) -> Optional[Dict[str, Any]]:
        user_path = _user_presets_dir() / f"{preset_id}.json"
        if not user_path.exists():
            return None

        with _lock:
            data = self._load_file(user_path, source="user")
            if not data:
                return None

            update = req.model_dump(exclude_unset=True)
            if "filter" in update and update["filter"] is not None:
                update["filter"] = req.filter.model_dump() if req.filter else data.get("filter", {})
            for key, value in update.items():
                if value is not None:
                    data[key] = value
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save_file(user_path, data)
        return data

    def delete_preset(self, preset_id: str) -> bool:
        user_path = _user_presets_dir() / f"{preset_id}.json"
        if not user_path.exists():
            return False
        with _lock:
            user_path.unlink()
        return True

    # -- helpers --

    @staticmethod
    def _load_dir(directory: Path, source: str) -> List[Dict[str, Any]]:
        results = []
        if not directory.is_dir():
            return results
        for fp in directory.glob("*.json"):
            data = FilterPresetService._load_file(fp, source)
            if data:
                results.append(data)
        return results

    @staticmethod
    def _load_file(fp: Path, source: str) -> Optional[Dict[str, Any]]:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("source", source)
            data.setdefault("id", fp.stem)
            return data
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def _save_file(fp: Path, data: Dict[str, Any]) -> None:
        fp.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(fp.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, str(fp))
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
