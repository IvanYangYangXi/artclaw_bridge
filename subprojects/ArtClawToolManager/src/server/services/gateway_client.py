# Ref: docs/features/phase1-foundation.md#GatewayClient
# Ref: docs/features/parameter-panel-interaction.md
"""
OpenClaw Gateway HTTP client.

Uses the OpenAI-compatible /v1/chat/completions endpoint for chat.
Supports both streaming (SSE) and non-streaming modes.

Configuration:
    ARTCLAW_GATEWAY_API_URL  – e.g. http://127.0.0.1:18789
    ARTCLAW_GATEWAY_TOKEN    – bearer token for auth
    ARTCLAW_GATEWAY_AGENT_ID – target agent id (default: qi)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GatewayClient (HTTP-based)
# ---------------------------------------------------------------------------


class GatewayClient:
    """Async HTTP client for OpenClaw Gateway chat completions.

    Usage::

        gw = GatewayClient("http://127.0.0.1:18789", token="xxx")
        gw.on_message(my_handler)
        await gw.start()   # just marks ready, no persistent connection
    """

    def __init__(
        self,
        gateway_url: str = "",
        token: str = "",
        agent_id: str = "qi",
    ) -> None:
        # Normalise: strip trailing /v1/... from URL if user passed full path
        self._base_url = gateway_url.rstrip("/")
        self._token = token
        self._agent_id = agent_id
        self._connected = False
        self._handlers: List[
            Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]
        ] = []
        self._http: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def url(self) -> str:
        return self._base_url

    def on_message(
        self,
        handler: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        self._handlers.append(handler)

    async def connect(self) -> bool:
        """Probe the gateway to check reachability."""
        if not self._base_url:
            logger.info("Gateway URL not configured – skipping")
            return False

        try:
            self._http = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
            # Quick health probe
            resp = await self._http.get(
                f"{self._base_url}/v1/chat/completions",
                headers=self._auth_headers(),
            )
            # 405 Method Not Allowed = endpoint exists but GET not supported (expected)
            # 200/400/401 also acceptable probes
            if resp.status_code in (200, 400, 401, 405):
                self._connected = True
                logger.info("Gateway reachable at %s", self._base_url)
                return True
            else:
                logger.warning("Gateway probe unexpected status: %s", resp.status_code)
                self._connected = False
                return False
        except Exception as exc:
            logger.warning("Gateway probe failed: %s", exc)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        self._connected = False
        if self._http:
            await self._http.aclose()
            self._http = None
        logger.info("Gateway client closed")

    async def start(self) -> None:
        if not self._base_url:
            logger.info("Gateway URL not configured – skipping connection")
            return
        await self.connect()

    # ------------------------------------------------------------------
    # send helpers
    # ------------------------------------------------------------------

    async def send_chat_message(
        self,
        session_id: str,
        content: str,
        agent_id: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Send a chat message via /v1/chat/completions (streaming SSE)."""
        if not self._http or not self._connected:
            logger.warning("Cannot send – Gateway not connected")
            # Notify handlers of error
            for h in self._handlers:
                await h({
                    "session_id": session_id,
                    "type": "error",
                    "code": "GATEWAY_DISCONNECTED",
                    "message": "Gateway 未连接",
                })
            return

        target_agent = agent_id or self._agent_id
        headers = {
            **self._auth_headers(),
            "Content-Type": "application/json",
            "x-openclaw-agent-id": target_agent,
        }
        body = {
            "model": "openclaw",
            "stream": True,
            "user": session_id,  # derive stable session from session_id
            "messages": [{"role": "user", "content": content}],
        }

        try:
            # Streaming SSE
            async with self._http.stream(
                "POST",
                f"{self._base_url}/v1/chat/completions",
                headers=headers,
                json=body,
            ) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    error_text = error_body.decode("utf-8", errors="replace")
                    logger.error("Gateway HTTP %s: %s", resp.status_code, error_text[:500])
                    for h in self._handlers:
                        await h({
                            "session_id": session_id,
                            "type": "error",
                            "code": f"HTTP_{resp.status_code}",
                            "message": f"Gateway 返回错误 {resp.status_code}",
                        })
                    return

                collected_content = ""
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    delta_content = delta.get("content", "")
                    if delta_content:
                        collected_content += delta_content
                        # Send streaming chunk to handlers
                        for h in self._handlers:
                            await h({
                                "session_id": session_id,
                                "type": "message_chunk",
                                "content": delta_content,
                            })

                # Send final complete message
                if collected_content:
                    for h in self._handlers:
                        await h({
                            "session_id": session_id,
                            "type": "message",
                            "role": "assistant",
                            "content": collected_content,
                        })

        except httpx.ReadTimeout:
            logger.error("Gateway request timed out for session %s", session_id)
            for h in self._handlers:
                await h({
                    "session_id": session_id,
                    "type": "error",
                    "code": "TIMEOUT",
                    "message": "Gateway 请求超时",
                })
        except Exception as exc:
            logger.exception("Gateway request failed for session %s", session_id)
            for h in self._handlers:
                await h({
                    "session_id": session_id,
                    "type": "error",
                    "code": "REQUEST_FAILED",
                    "message": f"Gateway 请求失败: {exc}",
                })

    async def send_cancel(self, session_id: str) -> None:
        """Cancel is not directly supported via HTTP completions.
        The stream will be closed by the caller."""
        logger.info("Cancel requested for session %s (HTTP mode – closing stream)", session_id)

    async def get_agents(self) -> List[Dict[str, Any]]:
        """Not available via HTTP completions endpoint."""
        return []

    # ------------------------------------------------------------------
    # private
    # ------------------------------------------------------------------

    def _auth_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers
