# Ref: docs/specs/architecture-design.md#TechStack
"""
Application configuration via pydantic-settings.

Reads from environment variables and .env file.
All path defaults use ~/.artclaw/ as the data root.

Skill path resolution:
  skills_path follows the same priority as bridge_config.get_skills_installed_path():
    1. ARTCLAW_SKILLS_DIR env / .env override
    2. ~/.artclaw/config.json → skills.installed_path  (set by platform switch)
    3. ~/.artclaw/config.json → platform.type → _PLATFORM_DEFAULTS.skills_installed_path
    4. Hardcoded default: ~/.openclaw/skills

  This ensures Tool Manager always sees the same Skill directory as the active
  AI platform (OpenClaw / LobsterAI / Claude etc.).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings


# Platform → default skills installed path (mirrors bridge_config._PLATFORM_DEFAULTS)
_PLATFORM_SKILLS_DEFAULTS: dict = {
    "openclaw":   "~/.openclaw/skills",
    "workbuddy":  "~/.workbuddy/skills",
    "claudecode": "~/.claude/skills",
    "cursor":     "~/.cursor/skills",
    "lobster":    None,  # resolved dynamically via APPDATA
}


def _resolve_lobster_skills_path() -> str:
    appdata = os.environ.get("APPDATA", os.path.expanduser("~/AppData/Roaming"))
    return os.path.join(appdata, "LobsterAI", "SKILLs")


def _read_artclaw_config() -> dict:
    cfg_path = Path.home() / ".artclaw" / "config.json"
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _resolve_skills_path() -> str:
    """
    Resolve the active platform's Skill installed directory.

    Priority:
      1. ~/.artclaw/config.json → skills.installed_path  (explicit override)
      2. ~/.artclaw/config.json → platform.type → default for that platform
      3. ~/.openclaw/skills  (hardcoded fallback)
    """
    cfg = _read_artclaw_config()

    # 1. Explicit override in config
    explicit = cfg.get("skills", {}).get("installed_path", "")
    if explicit:
        return os.path.expanduser(explicit)

    # 2. Platform default
    platform_type = cfg.get("platform", {}).get("type", "openclaw")
    default = _PLATFORM_SKILLS_DEFAULTS.get(platform_type)
    if default is None and platform_type == "lobster":
        default = _resolve_lobster_skills_path()
    if default:
        return os.path.expanduser(default)

    # 3. Hardcoded fallback
    return str(Path.home() / ".openclaw" / "skills")


def _default_data_dir() -> str:
    return str(Path.home() / ".artclaw")


class Settings(BaseSettings):
    """Global application settings."""

    # --- App ---
    APP_NAME: str = "ArtClaw Tool Manager"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 9876

    # --- CORS ---
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:9876",
    ]

    # --- Data Paths ---
    DATA_DIR: str = _default_data_dir()
    # SKILLS_DIR can be overridden by ARTCLAW_SKILLS_DIR env var or .env file.
    # When not set, _resolve_skills_path() is called at property access time so
    # that a platform switch mid-session is reflected immediately.
    SKILLS_DIR: str = ""

    # --- OpenClaw Gateway ---
    GATEWAY_URL: str = ""
    GATEWAY_API_URL: str = "http://127.0.0.1:18789"
    GATEWAY_TOKEN: str = ""
    GATEWAY_AGENT_ID: str = "qi"

    model_config = {
        "env_prefix": "ARTCLAW_",
        "env_file": (".env", "src/server/.env"),
        "env_file_encoding": "utf-8",
    }

    # -- helpers --

    @property
    def data_path(self) -> Path:
        p = Path(os.path.expanduser(self.DATA_DIR))
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def skills_path(self) -> Path:
        # If SKILLS_DIR was explicitly set (env/env-file), use it directly.
        if self.SKILLS_DIR:
            return Path(os.path.expanduser(self.SKILLS_DIR))
        # Otherwise resolve dynamically from ~/.artclaw/config.json each time,
        # so a platform switch is picked up without restarting the server.
        return Path(_resolve_skills_path())

    @property
    def config_json_path(self) -> Path:
        return self.data_path / "config.json"


# Singleton – import this everywhere.
settings = Settings()
