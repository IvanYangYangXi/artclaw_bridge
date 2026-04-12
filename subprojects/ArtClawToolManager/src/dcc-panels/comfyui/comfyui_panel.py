# Ref: docs/features/phase5-dcc-integration.md
"""
ComfyUI Extension Panel for ArtClaw Tool Manager.

Provides a lightweight integration layer that can be mounted as a
ComfyUI server extension, exposing REST routes alongside the standard
ComfyUI API.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ..common.panel_base import ArtClawQuickPanel


class ComfyUIQuickPanel(ArtClawQuickPanel):
    """Quick Panel tailored for ComfyUI.

    Unlike the Qt-based DCC panels this class exposes a set of HTTP route
    definitions (via ``get_api_routes``) that a ComfyUI server extension
    can register directly.
    """

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    def get_dcc_context(self) -> Dict[str, Any]:
        """Return ComfyUI context.

        ComfyUI has no persistent selection concept, so the returned
        context is intentionally minimal.
        """
        return {
            "dcc": "comfyui",
            "selected": [],
            "workflow": None,
        }

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def open_web_manager(self, context: Optional[Dict[str, str]] = None) -> None:
        """Open the web manager with ComfyUI context."""
        ctx = context or self.get_dcc_context()
        url_params: Dict[str, str] = {
            "dcc": "comfyui",
        }
        workflow = ctx.get("workflow")
        if workflow:
            url_params["workflow"] = str(workflow)
        super().open_web_manager(url_params)

    # ------------------------------------------------------------------
    # Event reporting
    # ------------------------------------------------------------------

    def report_event(
        self,
        event_type: str,
        timing: str = "post",
        data: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Report a DCC event to the trigger engine."""
        event_data: Dict[str, Any] = {
            "dcc_type": "comfyui",
            "event_type": event_type,
            "timing": timing,
            "data": data or {},
        }
        return self._client.post("/dcc-events", data=event_data)

    # ------------------------------------------------------------------
    # ComfyUI extension routes
    # ------------------------------------------------------------------

    def get_api_routes(self) -> Dict[str, Dict[str, Any]]:
        """Return route definitions for ComfyUI server extension registration.

        Each key is a URL path; the value contains the HTTP method and a
        handler callable.  A ComfyUI extension can iterate over these and
        register them with ``aiohttp`` or a similar framework.

        Returns
        -------
        dict
            Mapping of ``path -> {"method": str, "handler": Callable}``.
        """
        return {
            "/artclaw/recent": {
                "method": "GET",
                "handler": self._handle_recent,
            },
            "/artclaw/pinned": {
                "method": "GET",
                "handler": self._handle_pinned,
            },
            "/artclaw/execute": {
                "method": "POST",
                "handler": self._handle_execute,
            },
            "/artclaw/open": {
                "method": "GET",
                "handler": self._handle_open,
            },
        }

    # ------------------------------------------------------------------
    # Route handlers
    # ------------------------------------------------------------------

    def _handle_recent(self, **kwargs: Any) -> list:
        """Handler: return recently used tools."""
        return self.get_recent_tools(5)

    def _handle_pinned(self, **kwargs: Any) -> list:
        """Handler: return pinned skills."""
        return self.get_pinned_skills()

    def _handle_execute(
        self,
        tool_id: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> dict:
        """Handler: execute a tool by *tool_id*."""
        if not tool_id:
            return {"error": "tool_id required"}
        return self.execute_tool(tool_id, params)

    def _handle_open(self, **kwargs: Any) -> Dict[str, str]:
        """Handler: open the web manager in the default browser."""
        self.open_web_manager()
        return {"status": "opened"}
