# Ref: docs/features/phase1-foundation.md#WebSocket
# Ref: docs/api/api-design.md#WebSocketAPI
"""
WebSocket connection manager for frontend clients.

Manages per-session connection sets (one session can have multiple browser
tabs open), heartbeat detection, and session-level / broadcast messaging.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HEARTBEAT_INTERVAL_S: float = 30.0
HEARTBEAT_TIMEOUT_S: float = 10.0


# ---------------------------------------------------------------------------
# ConnectionManager
# ---------------------------------------------------------------------------


class ConnectionManager:
    """Manage frontend WebSocket connections grouped by session_id.

    One session may have multiple WebSocket connections (multiple browser
    tabs).  Messages sent to a session are fanned out to all its active
    connections.
    """

    def __init__(self) -> None:
        # session_id -> set of WebSocket
        self._connections: Dict[str, Set[WebSocket]] = {}
        # ws -> session_id  (reverse lookup for fast disconnect)
        self._ws_session: Dict[WebSocket, str] = {}
        # ws -> heartbeat asyncio.Task
        self._heartbeat_tasks: Dict[WebSocket, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # connect / disconnect
    # ------------------------------------------------------------------

    async def connect(self, ws: WebSocket, session_id: str) -> None:
        """Accept *ws* and register it under *session_id*."""
        await ws.accept()

        async with self._lock:
            if session_id not in self._connections:
                self._connections[session_id] = set()
            self._connections[session_id].add(ws)
            self._ws_session[ws] = session_id

        logger.info(
            "WS connected  session=%s  total_for_session=%d",
            session_id,
            len(self._connections.get(session_id, set())),
        )

    async def disconnect(self, ws: WebSocket, session_id: str) -> None:
        """Remove *ws* from *session_id* and cancel its heartbeat task."""
        # Cancel heartbeat first
        task = self._heartbeat_tasks.pop(ws, None)
        if task and not task.done():
            task.cancel()

        async with self._lock:
            conns = self._connections.get(session_id)
            if conns:
                conns.discard(ws)
                if not conns:
                    del self._connections[session_id]
            self._ws_session.pop(ws, None)

        logger.info("WS disconnected  session=%s", session_id)

    # ------------------------------------------------------------------
    # messaging
    # ------------------------------------------------------------------

    async def send_to_session(
        self, session_id: str, message: Dict[str, Any]
    ) -> None:
        """Send *message* (JSON-serialisable dict) to every connection
        in *session_id*.  Silently drops connections that have gone away."""
        conns = self._connections.get(session_id)
        if not conns:
            return

        dead: List[WebSocket] = []
        payload = json.dumps(message, ensure_ascii=False)

        for ws in list(conns):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        # Clean up dead connections outside iteration
        for ws in dead:
            await self.disconnect(ws, session_id)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Send *message* to **all** connected sessions."""
        for sid in list(self._connections.keys()):
            await self.send_to_session(sid, message)

    # ------------------------------------------------------------------
    # heartbeat
    # ------------------------------------------------------------------

    async def start_heartbeat(self, ws: WebSocket, session_id: str) -> None:
        """Launch a background heartbeat task for *ws*.

        The task periodically sends ``{"type":"ping","ts":…}`` and expects
        the client to respond within *HEARTBEAT_TIMEOUT_S*.  If the client
        is unresponsive the connection is forcibly closed.
        """
        task = asyncio.create_task(
            self._heartbeat_loop(ws, session_id),
            name=f"heartbeat-{session_id}-{id(ws)}",
        )
        self._heartbeat_tasks[ws] = task

    async def _heartbeat_loop(
        self, ws: WebSocket, session_id: str
    ) -> None:
        """Internal heartbeat sender – runs until cancelled or ws dies."""
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL_S)
                try:
                    await ws.send_json(
                        {"type": "ping", "ts": time.time()}
                    )
                except Exception:
                    break
        except asyncio.CancelledError:
            pass
        finally:
            # Ensure cleanup
            await self.disconnect(ws, session_id)

    # ------------------------------------------------------------------
    # statistics
    # ------------------------------------------------------------------

    def get_connection_count(self) -> int:
        """Total number of active WebSocket connections."""
        return sum(len(s) for s in self._connections.values())

    def get_session_ids(self) -> List[str]:
        """List of session IDs that have at least one active connection."""
        return list(self._connections.keys())

    def get_session_connection_count(self, session_id: str) -> int:
        """Number of active connections for a specific session."""
        return len(self._connections.get(session_id, set()))
