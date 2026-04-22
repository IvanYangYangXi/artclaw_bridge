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


def _resolve_gateway_agent_id() -> str:
    """Resolve default Agent ID from platform config.

    Priority:
      1. ~/.artclaw/config.json → last_agent_id
      2. Platform config → agents.list[0].id
      3. Empty string (Gateway routes to default agent)
    """
    cfg = _read_artclaw_config()
    last = cfg.get("last_agent_id", "")
    if last:
        return last

    # Read platform config (e.g. openclaw.json)
    platform_type = cfg.get("platform", {}).get("type", "openclaw")
    config_paths = {
        "openclaw": Path.home() / ".openclaw" / "openclaw.json",
    }
    config_path = config_paths.get(platform_type)
    if config_path and config_path.exists():
        try:
            pcfg = json.loads(config_path.read_text(encoding="utf-8"))
            agents_list = pcfg.get("agents", {}).get("list", [])
            if agents_list:
                first_id = agents_list[0].get("id", "")
                if first_id:
                    return first_id
        except Exception:
            pass

    return ""


def _resolve_gateway_api_url() -> str:
    """Resolve Gateway HTTP API URL from platform config.

    Priority:
      1. ~/.artclaw/config.json → platform.gateway_url (convert ws→http)
      2. Platform config → gateway.port
      3. Default: http://127.0.0.1:18789
    """
    cfg = _read_artclaw_config()

    # 1. artclaw config
    platform_url = cfg.get("platform", {}).get("gateway_url", "")
    if platform_url:
        # ws://host:port → http://host:port
        return platform_url.replace("ws://", "http://").replace("wss://", "https://")

    # 2. Platform config → gateway.port
    platform_type = cfg.get("platform", {}).get("type", "openclaw")
    _config_paths = {
        "openclaw": Path.home() / ".openclaw" / "openclaw.json",
    }
    config_path = _config_paths.get(platform_type)
    if config_path and config_path.exists():
        try:
            pcfg = json.loads(config_path.read_text(encoding="utf-8"))
            port = pcfg.get("gateway", {}).get("port")
            if port:
                return f"http://127.0.0.1:{port}"
        except Exception:
            pass

    # 3. Platform defaults
    _port_defaults = {"openclaw": 18789, "lobster": 18790}
    port = _port_defaults.get(platform_type, 18789)
    return f"http://127.0.0.1:{port}"


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
    GATEWAY_API_URL: str = ""  # 空=动态解析（resolved_api_url 属性）
    GATEWAY_TOKEN: str = ""
    GATEWAY_AGENT_ID: str = ""

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

    @property
    def resolved_agent_id(self) -> str:
        """GATEWAY_AGENT_ID with dynamic fallback from platform config."""
        if self.GATEWAY_AGENT_ID:
            return self.GATEWAY_AGENT_ID
        return _resolve_gateway_agent_id()

    @property
    def resolved_token(self) -> str:
        """GATEWAY_TOKEN with dynamic fallback from platform config."""
        if self.GATEWAY_TOKEN:
            return self.GATEWAY_TOKEN
        # Try reading from openclaw.json → gateway.auth.token
        try:
            oc_path = Path.home() / ".openclaw" / "openclaw.json"
            if oc_path.exists():
                cfg = json.loads(oc_path.read_text(encoding="utf-8"))
                token = cfg.get("gateway", {}).get("auth", {}).get("token", "")
                if token:
                    return token
        except Exception:
            pass
        return ""

    @property
    def resolved_api_url(self) -> str:
        """GATEWAY_API_URL with dynamic fallback from platform config."""
        if self.GATEWAY_API_URL:
            return self.GATEWAY_API_URL
        return _resolve_gateway_api_url()


# Singleton – import this everywhere.
settings = Settings()
