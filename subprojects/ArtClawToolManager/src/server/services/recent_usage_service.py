# Ref: docs/features/phase2-skill-management.md#RecentUsage
"""
Recent skill usage service (no database).

Wraps :class:`ConfigManager` recent-usage helpers and enriches each entry
with skill data from the filesystem scanner.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..services.config_manager import ConfigManager
from ..services.skill_service import SkillService

logger = logging.getLogger(__name__)


class RecentUsageService:
    """Record and retrieve recently used skills."""

    def __init__(self, config: ConfigManager):
        self.config = config

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record_usage(self, skill_id: str) -> None:
        """Record that *skill_id* was just used."""
        self.config.record_skill_usage(skill_id)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the *limit* most recently used skills, enriched with scan data."""
        recent_entries: List[Dict] = self.config.get_recent_skills(limit)
        if not recent_entries:
            return []

        # Build a skill map from the scanner
        svc = SkillService(self.config)
        svc._scan_and_build()
        skill_map = {s.id: s for s in svc._cache}

        result: List[Dict[str, Any]] = []
        for entry in recent_entries:
            sid = entry.get("id", "")
            used_at = entry.get("used_at")
            skill = skill_map.get(sid)

            if skill is not None:
                item = skill.to_dict()
            else:
                item = {
                    "id": sid,
                    "name": sid,
                    "description": "",
                    "version": "0.0.0",
                    "source": "official",
                    "status": "not_installed",
                    "is_enabled": False,
                    "is_pinned": False,
                    "is_favorited": False,
                    "use_count": 0,
                    "skill_path": "",
                    "target_dccs": [],
                    "priority": 0,
                }

            item["used_at"] = used_at
            result.append(item)

        return result
