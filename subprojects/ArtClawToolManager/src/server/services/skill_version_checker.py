# Ref: docs/features/phase2-skill-management.md#VersionCheck
"""
Skill version checker.

Compares the version found in SKILL.md (filesystem scan) with the
installed version recorded in ``~/.artclaw/config.json``.  A mismatch
indicates that an update is available.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

from ..services.config_manager import ConfigManager


# Minimal semver regex: major.minor.patch with optional pre-release
_SEMVER_RE = re.compile(
    r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.]+))?$"
)


def _parse_version(v: str) -> Tuple[int, int, int, str]:
    """Parse a version string into a comparable tuple.

    Returns ``(major, minor, patch, pre_release)``.
    Non-parseable strings fall back to ``(0, 0, 0, "")``.
    """
    m = _SEMVER_RE.match(v.strip())
    if not m:
        return (0, 0, 0, "")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4) or "")


class SkillVersionChecker:
    """Compare scanned skill versions with installed versions."""

    def __init__(self, config: ConfigManager):
        self.config = config

    def get_installed_version(self, skill_id: str) -> Optional[str]:
        """Return the installed version string from config, or None."""
        installed = self.config.load().get("skills", {}).get("installed", {})
        entry = installed.get(skill_id)
        if entry is None:
            return None
        return entry.get("version", "0.0.0")

    def check_update_available(self, skill_id: str, current_version: str) -> bool:
        """Check whether *current_version* (from filesystem) differs from the
        installed version stored in config.

        Returns ``True`` when an update is available (i.e. the scanned version
        is newer or simply different from the recorded version).
        Returns ``False`` if the skill is not tracked in config or versions
        match.
        """
        installed_version = self.get_installed_version(skill_id)
        if installed_version is None:
            return False
        return current_version.strip() != installed_version.strip()

    def is_newer(self, current: str, installed: str) -> bool:
        """Return True if *current* is strictly newer than *installed*."""
        c = _parse_version(current)
        i = _parse_version(installed)
        return c[:3] > i[:3]

    def record_installed_version(self, skill_id: str, version: str) -> None:
        """Persist the installed version into config."""
        with self.config._lock:
            cfg = self.config._ensure_structure(self.config._read())
            cfg["skills"]["installed"].setdefault(skill_id, {})
            cfg["skills"]["installed"][skill_id]["version"] = version
            self.config._write(cfg)
