# Ref: docs/features/phase5-dcc-integration.md
"""
Base class for all DCC Quick Panels.

Provides shared logic: recent-tools fetching, pinned-skills fetching,
tool execution, server availability check, and browser launch.
Subclasses override ``get_dcc_context`` to supply DCC-specific context.
"""
from __future__ import annotations

import urllib.parse
import webbrowser
from typing import Any, Dict, List, Optional

from .api_client import ArtClawAPIClient


class ArtClawQuickPanel:
    """DCC Quick Panel base class.

    Communicates with the ArtClaw Tool Manager web server and maintains
    a simple in-memory cache so panels can degrade gracefully when the
    server is offline.
    """

    def __init__(self, api_url: str = "http://localhost:9876") -> None:
        self.api_url: str = api_url.rstrip("/")
        self._client: ArtClawAPIClient = ArtClawAPIClient(
            f"{self.api_url}/api/v1"
        )
        self._cache: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    def get_recent_tools(self, limit: int = 5) -> List[dict]:
        """Get recently used tools via ``GET /api/v1/tools``.

        Falls back to the cached result when the server is unreachable.
        """
        result = self._client.get(
            "/tools", params={"sort": "last_used", "limit": str(limit)}
        )
        if "error" not in result:
            items = result.get("data", result.get("items", []))
            self._cache["recent_tools"] = items
            return items
        return self._cache.get("recent_tools", [])

    def get_pinned_skills(self) -> List[dict]:
        """Get pinned skills via ``GET /api/v1/skills?pinned=true``.

        Falls back to the cached result when the server is unreachable.
        """
        result = self._client.get("/skills", params={"pinned": "true"})
        if "error" not in result:
            items = result.get("data", result.get("items", []))
            self._cache["pinned_skills"] = items
            return items
        return self._cache.get("pinned_skills", [])

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def execute_tool(
        self, tool_id: str, params: Optional[Dict[str, Any]] = None
    ) -> dict:
        """Execute a tool via ``POST /api/v1/tools/{tool_id}/execute``."""
        return self._client.post(
            f"/tools/{tool_id}/execute", data=params or {}
        )

    def is_server_available(self) -> bool:
        """Return ``True`` if the ArtClaw web server is running."""
        return self._client.is_available()

    def open_web_manager(self, context: Optional[Dict[str, str]] = None) -> None:
        """Open the Web Manager in the default browser.

        If *context* is provided it is appended as query parameters to the
        ``/chat`` route so the web UI can pre-populate DCC context.
        """
        url = self.api_url
        if context:
            query = urllib.parse.urlencode(context)
            url = f"{url}/chat?{query}"
        webbrowser.open(url)

    # ------------------------------------------------------------------
    # Subclass interface
    # ------------------------------------------------------------------

    def get_dcc_context(self) -> dict:
        """Return a dict describing the current DCC environment.

        Subclasses **must** override this method.
        """
        raise NotImplementedError(
            "Subclasses must implement get_dcc_context()"
        )
