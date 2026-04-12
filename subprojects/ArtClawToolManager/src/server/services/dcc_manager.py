# Ref: docs/specs/architecture-design.md#SystemArchitecture
# Ref: docs/features/phase0-technical-research.md#DCCCommunication
"""
DCC connection-state manager.

Periodically pings known DCC adapter HTTP endpoints to determine which
DCC applications are online.  State changes are emitted through a
callback so the rest of the system (e.g. MessageRouter) can push
real-time ``dcc_status`` events to frontend clients.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHECK_INTERVAL_S: float = 30.0
PING_TIMEOUT_S: float = 5.0

# Default well-known DCC adapter ports
DEFAULT_DCC_PORTS: Dict[str, int] = {
    "ue57": 8080,
    "maya2024": 8081,
    "max2024": 8082,
    "blender": 8083,
    "houdini": 8084,
    "sp": 8085,
    "sd": 8086,
    "comfyui": 8087,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DCCStatus:
    """Snapshot of a single DCC connection."""

    dcc_type: str
    connected: bool = False
    host: str = "localhost"
    port: int = 0
    last_check: float = 0.0
    last_connected: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dcc_type": self.dcc_type,
            "connected": self.connected,
            "host": self.host,
            "port": self.port,
            "last_check": self.last_check,
            "last_connected": self.last_connected,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# DCCManager
# ---------------------------------------------------------------------------


class DCCManager:
    """Manages health-check polling for DCC adapter endpoints.

    Usage::

        mgr = DCCManager()
        mgr.on_status_change(my_callback)
        await mgr.start_monitoring()  # runs until stop_monitoring()
    """

    def __init__(
        self,
        dcc_ports: Optional[Dict[str, int]] = None,
        host: str = "localhost",
    ) -> None:
        ports = dcc_ports or DEFAULT_DCC_PORTS
        self._statuses: Dict[str, DCCStatus] = {
            name: DCCStatus(dcc_type=name, host=host, port=port)
            for name, port in ports.items()
        }
        self._callbacks: List[
            Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]]
        ] = []
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def on_status_change(
        self,
        handler: Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """Register an async callback ``(dcc_type, status_dict)``."""
        self._callbacks.append(handler)

    async def check_connection(self, dcc_type: str) -> bool:
        """Probe a single DCC adapter and return ``True`` if reachable."""
        status = self._statuses.get(dcc_type)
        if not status:
            return False

        prev_connected = status.connected
        now = time.time()

        try:
            import httpx  # deferred import

            url = f"http://{status.host}:{status.port}/health"
            async with httpx.AsyncClient(timeout=PING_TIMEOUT_S) as client:
                resp = await client.get(url)
                reachable = resp.status_code < 500
        except Exception as exc:
            reachable = False
            status.error = str(exc)

        status.connected = reachable
        status.last_check = now
        if reachable:
            status.last_connected = now
            status.error = None

        # Emit on change
        if reachable != prev_connected:
            logger.info(
                "DCC %s status changed: %s -> %s",
                dcc_type,
                prev_connected,
                reachable,
            )
            await self._emit(dcc_type, status.to_dict())

        return reachable

    async def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Return current cached status for every known DCC."""
        return {
            name: st.to_dict() for name, st in self._statuses.items()
        }

    async def start_monitoring(self) -> None:
        """Start the background periodic check loop."""
        if self._running:
            return
        self._running = True
        self._monitor_task = asyncio.create_task(
            self._monitor_loop(), name="dcc-monitor"
        )
        logger.info("DCC monitoring started (interval=%.0fs)", CHECK_INTERVAL_S)

    async def stop_monitoring(self) -> None:
        """Stop the background check loop."""
        self._running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("DCC monitoring stopped")

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    async def _monitor_loop(self) -> None:
        """Check all DCC endpoints periodically."""
        try:
            while self._running:
                tasks = [
                    self.check_connection(name)
                    for name in self._statuses
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
                await asyncio.sleep(CHECK_INTERVAL_S)
        except asyncio.CancelledError:
            pass

    async def _emit(self, dcc_type: str, status: Dict[str, Any]) -> None:
        for cb in self._callbacks:
            try:
                await cb(dcc_type, status)
            except Exception:
                logger.exception("DCC status-change callback error")
