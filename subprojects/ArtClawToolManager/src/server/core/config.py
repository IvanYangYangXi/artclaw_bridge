# Ref: docs/specs/architecture-design.md#TechStack
"""
Application configuration via pydantic-settings.

Reads from environment variables and .env file.
All path defaults use ~/.artclaw/ as the data root.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings


def _default_data_dir() -> str:
    """Return ~/.artclaw as the default data directory."""
    return str(Path.home() / ".artclaw")


def _default_skills_dir() -> str:
    """Return ~/.openclaw/skills as the default skills directory."""
    return str(Path.home() / ".openclaw" / "skills")


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
    SKILLS_DIR: str = _default_skills_dir()

    # --- OpenClaw Gateway ---
    GATEWAY_URL: str = ""          # Kept for backward compat
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
        return Path(os.path.expanduser(self.SKILLS_DIR))

    @property
    def config_json_path(self) -> Path:
        return self.data_path / "config.json"


# Singleton – import this everywhere.
settings = Settings()
