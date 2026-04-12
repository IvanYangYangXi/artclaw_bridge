# Ref: docs/features/phase5-dcc-integration.md
"""
Lightweight API client for ArtClaw Tool Manager.

Uses only stdlib (urllib.request + json) — no external dependencies required.
Designed to run inside DCC environments (UE, Maya, Blender, ComfyUI).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional


class ArtClawAPIClient:
    """HTTP client for communicating with the ArtClaw Tool Manager web server.

    All methods are synchronous and safe to call from DCC main threads.
    On failure, ``get`` / ``post`` return ``{"error": "<message>"}`` instead
    of raising, so callers can degrade gracefully (offline mode).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:9876/api/v1",
        timeout: int = 10,
    ) -> None:
        # Strip trailing slash for consistent path joining
        self.base_url: str = base_url.rstrip("/")
        self.timeout: int = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, path: str, params: Optional[Dict[str, str]] = None) -> dict:
        """Send a GET request and return the parsed JSON response.

        Parameters
        ----------
        path:
            API path relative to *base_url*, e.g. ``"/tools"``.
        params:
            Optional query-string parameters.

        Returns
        -------
        dict
            Parsed JSON on success, or ``{"error": "..."}`` on failure.
        """
        url = self._build_url(path, params)
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        return self._execute(req)

    def post(self, path: str, data: Optional[Dict[str, Any]] = None) -> dict:
        """Send a POST request with a JSON body and return the parsed response.

        Parameters
        ----------
        path:
            API path relative to *base_url*.
        data:
            JSON-serialisable payload (sent as ``application/json``).

        Returns
        -------
        dict
            Parsed JSON on success, or ``{"error": "..."}`` on failure.
        """
        url = self._build_url(path)
        body = json.dumps(data or {}).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        return self._execute(req)

    def is_available(self) -> bool:
        """Return ``True`` if the server responds to the health endpoint."""
        try:
            result = self.get("/health")
            return "error" not in result
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_url(
        self, path: str, params: Optional[Dict[str, str]] = None
    ) -> str:
        """Combine *base_url*, *path*, and optional query params into a URL."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        return url

    def _execute(self, req: urllib.request.Request) -> dict:
        """Execute *req* and return parsed JSON, or an error dict."""
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                if not raw.strip():
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            return {"error": f"HTTP {exc.code}: {body or exc.reason}"}
        except urllib.error.URLError as exc:
            return {"error": f"URL error: {exc.reason}"}
        except json.JSONDecodeError as exc:
            return {"error": f"JSON decode error: {exc}"}
        except Exception as exc:
            return {"error": str(exc)}
