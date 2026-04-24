# Ref: docs/specs/architecture-design.md#SystemArchitecture
# Ref: docs/features/phase0-technical-research.md#DCCCommunication
"""
DCC connection-state manager.

Periodically pings known DCC adapter HTTP endpoints to determine which
DCC applications are online.  State changes are emitted through a
callback so the rest of the system (e.g. MessageRouter) can push
real-time ``dcc_status`` events to frontend clients.

Also provides ``execute_on_dcc()`` to run Python code on a connected DCC
via its MCP WebSocket server (JSON-RPC 2.0 ``tools/call`` → ``run_python``).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
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

# MCP tool name varies by DCC type
DCC_TOOL_NAMES: Dict[str, str] = {
    "ue57": "run_ue_python",
    # All others use run_python (default)
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

    # ------------------------------------------------------------------
    # Code execution via MCP WebSocket
    # ------------------------------------------------------------------

    # Map manifest targetDCCs values → dcc_type keys in _statuses
    _TARGET_DCC_MAP: Dict[str, str] = {
        "ue57": "ue57",
        "maya": "maya2024",
        "max": "max2024",
        "blender": "blender",
        "houdini": "houdini",
        "substance-painter": "sp",
        "substance-designer": "sd",
        "comfyui": "comfyui",
    }

    def resolve_dcc_type(self, target_dcc: str) -> Optional[str]:
        """Resolve a manifest targetDCCs value to an internal dcc_type key."""
        return self._TARGET_DCC_MAP.get(target_dcc, None)

    def get_connected_dcc(self, target_dccs: List[str]) -> Optional[str]:
        """Find the first connected DCC from a list of target DCC identifiers.

        Returns the internal dcc_type key, or None if none are connected.
        """
        for td in target_dccs:
            dcc_type = self.resolve_dcc_type(td)
            if dcc_type and self._statuses.get(dcc_type, DCCStatus(dcc_type="")).connected:
                return dcc_type
        return None

    async def execute_on_dcc(
        self,
        dcc_type: str,
        code: str,
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """Execute Python code on a DCC via MCP WebSocket ``tools/call`` → ``run_python``.

        Args:
            dcc_type: Internal key (e.g. "blender", "maya2024").
            code: Python source code to execute.
            timeout: Seconds to wait for a response.

        Returns:
            Dict with "success", "output", "error" keys.
        """
        status = self._statuses.get(dcc_type)
        if not status or not status.connected:
            return {"success": False, "output": "", "error": f"DCC '{dcc_type}' is not connected"}

        ws_url = f"ws://{status.host}:{status.port}/ws"
        request_id = str(uuid.uuid4())

        # JSON-RPC 2.0: initialize → tools/call → close
        try:
            import websockets  # type: ignore
        except ImportError:
            return {"success": False, "output": "", "error": "websockets package not installed"}

        try:
            async with websockets.connect(ws_url, open_timeout=5, close_timeout=3) as ws:
                # 1. Initialize handshake
                init_msg = json.dumps({
                    "jsonrpc": "2.0",
                    "id": f"init-{request_id}",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "ArtClawToolManager", "version": "1.0.0"},
                    },
                })
                await ws.send(init_msg)
                # Read init response (ignore content)
                await asyncio.wait_for(ws.recv(), timeout=5.0)

                # 2. Send initialized notification
                await ws.send(json.dumps({
                    "jsonrpc": "2.0",
                    "method": "initialized",
                    "params": {},
                }))

                # 3. Call the DCC's MCP tool
                tool_name = DCC_TOOL_NAMES.get(dcc_type, "run_python")
                call_msg = json.dumps({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": {"code": code},
                    },
                })
                await ws.send(call_msg)

                # 4. Wait for the matching response
                deadline = time.time() + timeout
                while time.time() < deadline:
                    remaining = deadline - time.time()
                    raw = await asyncio.wait_for(ws.recv(), timeout=max(remaining, 0.1))
                    resp = json.loads(raw)
                    if resp.get("id") == request_id:
                        # Parse MCP result
                        if "error" in resp:
                            err = resp["error"]
                            return {
                                "success": False,
                                "output": "",
                                "error": err.get("message", str(err)),
                            }
                        result = resp.get("result", {})
                        is_error = result.get("isError", False)
                        content_parts = result.get("content", [])
                        text_parts = [
                            c.get("text", "") for c in content_parts if c.get("type") == "text"
                        ]
                        output = "\n".join(text_parts)
                        return {
                            "success": not is_error,
                            "output": output,
                            "error": output if is_error else "",
                        }
                    # else: notification or other message, keep reading

                return {"success": False, "output": "", "error": f"Timeout waiting for DCC response ({timeout}s)"}

        except asyncio.TimeoutError:
            return {"success": False, "output": "", "error": f"Connection/response timeout ({timeout}s)"}
        except Exception as exc:
            return {"success": False, "output": "", "error": f"DCC execution error: {exc}"}
