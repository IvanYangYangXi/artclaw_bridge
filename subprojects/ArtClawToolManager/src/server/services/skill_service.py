# Ref: docs/features/phase2-skill-management.md#SkillService
"""
Skill business-logic service (filesystem + config, no database).

Combines data from:
  1. ``skill_scanner`` – live filesystem scan of ~/.openclaw/workspace/skills/
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

            # Determine status: not_installed skills have no skill_path
            if s.sync_status == "not_installed" or not s.skill_path:
                status = "not_installed"
                is_enabled = False
            elif is_disabled:
                status = "disabled"
                is_enabled = False
            else:
                status = "installed"
                is_enabled = True

            sd = SkillData(
                id=skill_id,
                name=s.name,
                description=s.description,
                version=s.version,
                author=s.author,
                updated_at=s.updated_at,
                source=s.source or "official",
                target_dccs=s.target_dccs,
                status=status,
                skill_path=s.skill_path,
                source_path=s.source_path,
                sync_status=s.sync_status,
                is_enabled=is_enabled,
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
    # Install / Uninstall
    # ------------------------------------------------------------------

    def install_skill(self, skill_id: str, force: bool = False) -> Dict[str, Any]:
        """Install a skill from source directory to ~/.openclaw/workspace/skills/."""
        # Re-scan to find the skill (may be not_installed)
        items = self._scan_and_build()
        skill = None
        for s in items:
            if s.id == skill_id:
                skill = s
                break

        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")
        if skill.status == "installed" and not force:
            raise ValueError(f"Skill already installed: {skill_id}. Use force=True to reinstall.")
        if not skill.source_path:
            raise ValueError(f"No source path for skill: {skill_id}. Cannot install without source.")

        src = Path(skill.source_path)
        if not src.exists():
            raise ValueError(f"Source directory does not exist: {src}")

        from ..core.config import settings
        dst = settings.skills_path / skill_id
        if dst.exists():
            shutil.rmtree(dst)

        shutil.copytree(
            str(src), str(dst),
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

        self._cache = []  # clear cache
        return {
            "skill_id": skill_id,
            "installed_path": str(dst),
            "message": f"Skill '{skill_id}' installed successfully",
        }

    def uninstall_skill(self, skill_id: str) -> Dict[str, Any]:
        """Uninstall a skill by removing it from ~/.openclaw/workspace/skills/."""
        skill = self.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")
        if skill.status == "not_installed":
            raise ValueError(f"Skill is not installed: {skill_id}")

        skill_path = Path(skill.skill_path)
        if not skill_path.exists():
            raise ValueError(f"Skill directory does not exist: {skill_path}")

        shutil.rmtree(skill_path)
        self._cache = []  # clear cache
        return {
            "skill_id": skill_id,
            "message": f"Skill '{skill_id}' uninstalled successfully",
        }

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

    def publish_to_source(self, skill_id: str, *, version: str = None,
                          bump: str = "patch", changelog: str = "",
                          target_layer: str = "", dcc: str = "") -> Dict[str, Any]:
        """Publish skill via ``skill_sync.publish_skill`` (version bump + copy
        + SKILL.md update + git commit).

        Falls back to a simple file-copy when ``skill_sync`` is not available
        (e.g. project_root unconfigured).
        """
        skill = self.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")

        # --- Try skill_sync.publish_skill (full DCC-plugin pipeline) ---
        try:
            import sys
            # Ensure DCCClawBridge/core is importable
            _core_candidates = []
            if skill.source_path:
                # infer project_root from source_path  .../<project>/skills/<layer>/<dcc>/<name>
                _src = Path(skill.source_path)
                for parent in _src.parents:
                    candidate = parent / "subprojects" / "DCCClawBridge" / "core"
                    if candidate.is_dir():
                        _core_candidates.append(str(candidate))
                        break
            for p in _core_candidates:
                if p not in sys.path:
                    sys.path.insert(0, p)

            from skill_sync import publish_skill as _sync_publish  # type: ignore

            # Determine bump type from explicit version vs current version
            effective_bump = bump
            if version and skill.version:
                effective_bump = self._infer_bump(skill.version, version)

            # skill_sync uses the filesystem directory name, not the skill_id
            skill_dir_name = Path(skill.skill_path).name if skill.skill_path else skill_id

            result = _sync_publish(
                skill_dir_name,
                target_layer=target_layer or (skill.source_layer or "marketplace"),
                bump=effective_bump,
                changelog=changelog,
                dcc=dcc,
            )
            self._cache = []  # clear cache
            if not result.get("ok"):
                raise ValueError(result.get("message", "publish_skill failed"))
            return {
                "skill_id": skill_id,
                "version": result.get("new_version", version),
                "message": result.get("message", "Published"),
            }
        except ImportError:
            pass  # skill_sync not available, fallback below

        # --- Fallback: simple file copy (no git, no bump) ---
        if not skill.source_path:
            raise ValueError(f"No source path found for skill: {skill_id}")

        src = Path(skill.skill_path)
        dst = Path(skill.source_path)
        if not src.exists():
            raise ValueError(f"Installed directory does not exist: {src}")
        if not dst.exists():
            raise ValueError(f"Source directory does not exist: {dst}")

        if version:
            self._update_skill_version(src, version)

        copied = 0
        for item in src.rglob("*"):
            rel = item.relative_to(src)
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

        self._cache = []
        return {
            "skill_id": skill_id,
            "copied_files": copied,
            "version": version,
            "message": f"Published {copied} files (fallback mode)",
        }

    @staticmethod
    def _infer_bump(old_ver: str, new_ver: str) -> str:
        """Infer bump type from old→new version strings."""
        def _parse(v):
            try:
                return tuple(int(x) for x in v.split(".")[:3])
            except Exception:
                return (0, 0, 0)
        o = _parse(old_ver)
        n = _parse(new_ver)
        if n[0] > o[0]:
            return "major"
        if n[1] > o[1]:
            return "minor"
        return "patch"

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
            "version": version,
            "message": f"Published {copied} files from installed to source directory",
        }

    @staticmethod
    def _update_skill_version(skill_dir: Path, new_version: str) -> None:
        """Update version in SKILL.md YAML frontmatter.

        Handles two layouts:
          1. metadata.artclaw.version: X.Y.Z  (preferred)
          2. top-level version: X.Y.Z         (legacy)
        """
        import re

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return

        content = skill_md.read_text(encoding="utf-8")
        m = re.match(r"^(---\s*\n)(.*?)(\n---)", content, re.DOTALL)
        if not m:
            return

        front = m.group(2)
        updated = False

        # Try metadata.artclaw.version first
        new_front, n = re.subn(
            r"([ \t]+version\s*:\s*)([^\n]+)",
            lambda mg: mg.group(1) + new_version,
            front,
            count=1,
        )
        if n > 0:
            updated = True
            front = new_front
        else:
            # Try top-level version
            new_front, n = re.subn(
                r"^(version\s*:\s*)(.+)$",
                lambda mg: mg.group(1) + new_version,
                front,
                count=1,
                flags=re.MULTILINE,
            )
            if n > 0:
                updated = True
                front = new_front

        if updated:
            new_content = m.group(1) + front + m.group(3) + content[m.end():]
            skill_md.write_text(new_content, encoding="utf-8")
