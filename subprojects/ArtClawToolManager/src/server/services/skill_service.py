# Ref: docs/features/phase2-skill-management.md#SkillService
"""
Skill business-logic service (filesystem + config, no database).

Combines data from:
  1. ``skill_scanner`` – live filesystem scan of ~/.openclaw/skills/
  2. ``config_manager`` – user preferences (pinned/disabled/favorites)

The authoritative source of "which skills exist" is the filesystem scan.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..models.data import SkillData
from ..services.config_manager import ConfigManager
from ..services.skill_scanner import scan_skills


class SkillService:
    """Skill list + toggle operations (no DB)."""

    def __init__(self, config: ConfigManager):
        self.config = config
        self._cache: List[SkillData] = []

    # ------------------------------------------------------------------
    # Scan & build
    # ------------------------------------------------------------------

    def _scan_and_build(self) -> List[SkillData]:
        """Scan skills directory and merge with user prefs from config."""
        scanned = scan_skills()
        disabled_set = set(self.config.get_disabled_skills())
        pinned_set = set(self.config.get_pinned_skills())
        fav_set = set(self.config.get_favorite_skills())

        result: List[SkillData] = []
        for s in scanned:
            skill_id = s.name
            is_disabled = skill_id in disabled_set
            sd = SkillData(
                id=skill_id,
                name=s.name,
                description=s.description,
                version=s.version,
                author=s.author,
                updated_at=s.updated_at,
                source=s.source or "official",
                target_dccs=s.target_dccs,
                status="disabled" if is_disabled else "installed",
                skill_path=s.skill_path,
                source_path=s.source_path,
                sync_status=s.sync_status,
                is_enabled=not is_disabled,
                is_pinned=skill_id in pinned_set,
                is_favorited=skill_id in fav_set,
            )
            result.append(sd)

        self._cache = result
        return result

    # ------------------------------------------------------------------
    # List / Detail
    # ------------------------------------------------------------------

    def list_skills(
        self,
        *,
        source: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        target_dcc: Optional[str] = None,
        installed: Optional[bool] = None,
        pinned: Optional[bool] = None,
        favorited: Optional[bool] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> Tuple[List[SkillData], int]:
        """Filtered + paginated skill list (re-scans filesystem each call)."""
        items = self._scan_and_build()

        # --- filters ---
        if source and source != "all":
            items = [s for s in items if s.source == source]
        if status and status != "all":
            items = [s for s in items if s.status == status]
        if installed is True:
            items = [s for s in items if s.status == "installed"]
        if target_dcc:
            items = [s for s in items if target_dcc in s.target_dccs]
        if pinned is not None:
            items = [s for s in items if s.is_pinned == pinned]
        if favorited is not None:
            items = [s for s in items if s.is_favorited == favorited]
        if search:
            low = search.lower()
            items = [
                s for s in items
                if low in s.name.lower() or low in s.description.lower()
            ]

        # --- sort ---
        reverse = sort_order == "desc"

        def sort_key(s: SkillData):
            primary = not s.is_pinned  # pinned first (False < True)
            secondary = getattr(s, sort_by, s.name)
            if isinstance(secondary, str):
                secondary = secondary.lower()
            return (primary, secondary)

        items.sort(key=sort_key, reverse=reverse)

        # If reverse is True, pinned-first is also reversed.
        # We need pinned always first, so re-sort only if desc.
        if reverse:
            items.sort(key=lambda s: not s.is_pinned)

        total = len(items)
        start = (page - 1) * limit
        page_items = items[start : start + limit]
        return page_items, total

    def get_skill(self, skill_id: str) -> Optional[SkillData]:
        """Find a skill by id from the cache (or re-scan)."""
        if not self._cache:
            self._scan_and_build()
        for s in self._cache:
            if s.id == skill_id:
                return s
        return None

    # ------------------------------------------------------------------
    # Toggle operations
    # ------------------------------------------------------------------

    def enable_skill(self, skill_id: str) -> Optional[SkillData]:
        skill = self.get_skill(skill_id)
        if not skill:
            return None
        skill.is_enabled = True
        skill.status = "installed"
        self.config.set_disabled(skill_id, False)
        return skill

    def disable_skill(self, skill_id: str) -> Optional[SkillData]:
        skill = self.get_skill(skill_id)
        if not skill:
            return None
        skill.is_enabled = False
        skill.status = "disabled"
        self.config.set_disabled(skill_id, True)
        return skill

    def pin_skill(self, skill_id: str) -> Optional[SkillData]:
        skill = self.get_skill(skill_id)
        if not skill:
            return None
        skill.is_pinned = True
        self.config.set_pinned(skill_id, True)
        return skill

    def unpin_skill(self, skill_id: str) -> Optional[SkillData]:
        skill = self.get_skill(skill_id)
        if not skill:
            return None
        skill.is_pinned = False
        self.config.set_pinned(skill_id, False)
        return skill

    def favorite_skill(self, skill_id: str) -> Optional[SkillData]:
        skill = self.get_skill(skill_id)
        if not skill:
            return None
        skill.is_favorited = True
        self.config.set_favorite(skill_id, True)
        return skill

    def unfavorite_skill(self, skill_id: str) -> Optional[SkillData]:
        skill = self.get_skill(skill_id)
        if not skill:
            return None
        skill.is_favorited = False
        self.config.set_favorite(skill_id, False)
        return skill

    # ------------------------------------------------------------------
    # Batch
    # ------------------------------------------------------------------

    def batch_operation(
        self, operation: str, skill_ids: List[str]
    ) -> Dict[str, Any]:
        op_map = {
            "enable": self.enable_skill,
            "disable": self.disable_skill,
            "pin": self.pin_skill,
            "unpin": self.unpin_skill,
            "favorite": self.favorite_skill,
            "unfavorite": self.unfavorite_skill,
        }
        fn = op_map.get(operation)
        if fn is None:
            return {
                "succeeded": 0,
                "failed": len(skill_ids),
                "errors": [
                    {"skill_id": sid, "error": f"Unknown operation: {operation}"}
                    for sid in skill_ids
                ],
            }

        succeeded = 0
        failed = 0
        errors: List[Dict[str, str]] = []
        for sid in skill_ids:
            try:
                result = fn(sid)
                if result is None:
                    raise ValueError(f"Skill not found: {sid}")
                succeeded += 1
            except Exception as exc:
                failed += 1
                errors.append({"skill_id": sid, "error": str(exc)})

        return {"succeeded": succeeded, "failed": failed, "errors": errors}

    # ------------------------------------------------------------------
    # Sync operations
    # ------------------------------------------------------------------

    def sync_from_source(self, skill_id: str) -> Dict[str, Any]:
        """Copy all files from source directory to installed directory (skip __pycache__)."""
        skill = self.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")
        if not skill.source_path:
            raise ValueError(f"No source path found for skill: {skill_id}")

        src = Path(skill.source_path)
        dst = Path(skill.skill_path)
        if not src.exists():
            raise ValueError(f"Source directory does not exist: {src}")
        if not dst.exists():
            raise ValueError(f"Installed directory does not exist: {dst}")

        copied = 0
        for item in src.rglob("*"):
            rel = item.relative_to(src)
            # Skip __pycache__ and other unwanted files
            skip = False
            for part_name in rel.parts:
                if part_name in ("__pycache__", ".git") or part_name.endswith(".pyc"):
                    skip = True
                    break
            if skip:
                continue

            target = dst / rel
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
                copied += 1

        # Remove files in dst that don't exist in src (cleanup)
        for item in list(dst.rglob("*")):
            if item.is_dir():
                continue
            rel = item.relative_to(dst)
            skip = False
            for part_name in rel.parts:
                if part_name in ("__pycache__", ".git") or part_name.endswith(".pyc"):
                    skip = True
                    break
            if skip:
                continue
            if not (src / rel).exists():
                item.unlink(missing_ok=True)

        # Clear cache so next list_skills re-scans
        self._cache = []

        return {
            "skill_id": skill_id,
            "copied_files": copied,
            "message": f"Synced {copied} files from source to installed directory",
        }

    def publish_to_source(self, skill_id: str) -> Dict[str, Any]:
        """Copy all files from installed directory to source directory (skip __pycache__)."""
        skill = self.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")
        if not skill.source_path:
            raise ValueError(f"No source path found for skill: {skill_id}")

        src = Path(skill.skill_path)
        dst = Path(skill.source_path)
        if not src.exists():
            raise ValueError(f"Installed directory does not exist: {src}")
        if not dst.exists():
            raise ValueError(f"Source directory does not exist: {dst}")

        copied = 0
        for item in src.rglob("*"):
            rel = item.relative_to(src)
            # Skip __pycache__ and other unwanted files
            skip = False
            for part_name in rel.parts:
                if part_name in ("__pycache__", ".git") or part_name.endswith(".pyc"):
                    skip = True
                    break
            if skip:
                continue

            target = dst / rel
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
                copied += 1

        # Remove files in dst that don't exist in src (cleanup)
        for item in list(dst.rglob("*")):
            if item.is_dir():
                continue
            rel = item.relative_to(dst)
            skip = False
            for part_name in rel.parts:
                if part_name in ("__pycache__", ".git") or part_name.endswith(".pyc"):
                    skip = True
                    break
            if skip:
                continue
            if not (src / rel).exists():
                item.unlink(missing_ok=True)

        # Clear cache so next list_skills re-scans
        self._cache = []

        return {
            "skill_id": skill_id,
            "copied_files": copied,
            "message": f"Published {copied} files from installed to source directory",
        }
