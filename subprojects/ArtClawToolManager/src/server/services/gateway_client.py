# Ref: docs/features/phase1-foundation.md#GatewayClient
"""
OpenClaw Gateway client – WebSocket full-duplex mode.

All communication (chat.send, chat.abort) goes through a single
WebSocket connection per chat request, matching the UE/DCC plugin
architecture (openclaw_ws.py).

Flow per chat message:
  1. Open WS → handshake → chat.send RPC
  2. Receive stream (chat events: delta / final / aborted / error)
  3. On cancel: send chat.abort on the SAME WS → Agent stops

Configuration:
    ARTCLAW_GATEWAY_API_URL  – base URL, e.g. http://127.0.0.1:18789
    ARTCLAW_GATEWAY_TOKEN    – bearer token
    ARTCLAW_GATEWAY_AGENT_ID – target agent id (default: qi)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Callable, Coroutine, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_PROTOCOL_VERSION = 3
_CHAT_TIMEOUT = 300.0   # absolute max per request
_IDLE_TIMEOUT = 120.0   # no activity timeout


class GatewayClient:
    """Gateway client using WebSocket full-duplex (mirrors UE/DCC openclaw_ws.py)."""

    def __init__(
        self,
        gateway_url: str = "",
        token: str = "",
        agent_id: str = "qi",
    ) -> None:
        self._base_url = gateway_url.rstrip("/")
        self._token = token
        self._agent_id = agent_id
        self._connected = False
        self._handlers: List[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = []
        self._http: Optional[httpx.AsyncClient] = None

        # Active chat tasks keyed by session_id
        self._active_tasks: Dict[str, asyncio.Task] = {}
        # session_id → cancel asyncio.Event (signals _receive_stream to abort)
        self._cancel_flags: Dict[str, asyncio.Event] = {}
        # session_id → effective Gateway session key
        self._session_keys: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @property
    def _ws_url(self) -> str:
        return self._base_url.replace("https://", "wss://").replace("http://", "ws://")

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

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        if not self._base_url:
            logger.info("Gateway URL not configured – skipping")
            return False
        try:
            self._http = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
            resp = await self._http.get(
                f"{self._base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._token}"} if self._token else {},
            )
            if resp.status_code in (200, 400, 401, 405):
                self._connected = True
                logger.info("Gateway reachable at %s", self._base_url)
                return True
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

    async def start(self) -> None:
        if not self._base_url:
            return
        await self.connect()

    # ------------------------------------------------------------------
    # chat  (WS full-duplex, mirrors UE openclaw_ws.do_chat)
    # ------------------------------------------------------------------

    async def send_chat_message(
        self,
        session_id: str,
        content: str,
        agent_id: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Send a chat message via WS chat.send. Cancellable via send_cancel()."""
        # Cancel any previous request
        old = self._active_tasks.pop(session_id, None)
        if old and not old.done():
            old.cancel()

        cancel_flag = asyncio.Event()
        self._cancel_flags[session_id] = cancel_flag

        task = asyncio.create_task(
            self._ws_chat(session_id, content, agent_id, cancel_flag),
            name=f"ws-chat-{session_id}",
        )
        self._active_tasks[session_id] = task
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            self._active_tasks.pop(session_id, None)
            self._cancel_flags.pop(session_id, None)

    async def _ws_chat(
        self,
        session_id: str,
        content: str,
        agent_id: Optional[str],
        cancel_flag: asyncio.Event,
    ) -> None:
        """Full WS lifecycle: connect → handshake → chat.send → receive stream."""
        if not self._connected:
            await self._emit(session_id, "error", "GATEWAY_DISCONNECTED", "Gateway 未连接")
            return

        target_agent = agent_id or self._agent_id
        # Use OpenClaw's agent-scoped session key format: agent:<agentId>:<subKey>
        # This routes the message to the correct agent in multi-agent Gateway setups
        session_key = f"agent:{target_agent}:artclaw-{session_id}"

        try:
            import websockets
        except ImportError:
            await self._emit(session_id, "error", "MISSING_DEP", "websockets not installed")
            return

        try:
            async with websockets.connect(
                self._ws_url,
                max_size=10 * 1024 * 1024,
                ping_interval=30,
                ping_timeout=10,
                open_timeout=10,
            ) as ws:
                # --- Handshake ---
                if not await self._handshake(ws, session_key, target_agent):
                    await self._emit(session_id, "error", "HANDSHAKE_FAILED", "Gateway 握手失败")
                    return

                # --- chat.send ---
                req_id = str(uuid.uuid4())
                await ws.send(json.dumps({
                    "type": "req",
                    "id": req_id,
                    "method": "chat.send",
                    "params": {
                        "sessionKey": session_key,
                        "message": content,
                        "idempotencyKey": str(uuid.uuid4()),
                    },
                }))

                ack = await self._wait_for_ack(ws, req_id, timeout=15.0)
                if ack is None:
                    await self._emit(session_id, "error", "ACK_TIMEOUT", "chat.send ACK 超时")
                    return

                status = ack.get("status", "")
                logger.info(f"[GW-WS] chat.send ACK: status={status}, keys={list(ack.keys())}")

                # Sync response (no streaming)
                if status not in ("started", "streaming", "accepted", "running"):
                    msg_text = self._extract_text(ack.get("message", ""))
                    if msg_text:
                        for h in self._handlers:
                            await h({"session_id": session_id, "type": "message", "role": "assistant", "content": msg_text})
                    return

                # Save effective session key from ACK
                effective_key = ack.get("sessionKey") or session_key
                self._session_keys[session_id] = effective_key
                run_id = ack.get("runId", "")
                logger.info(f"[GW-WS] effective_key={effective_key}, runId={run_id[:12] if run_id else 'N/A'}")

                # --- Receive stream ---
                await self._receive_stream(ws, session_id, cancel_flag, effective_key, run_id)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("WS chat failed for session %s", session_id)
            await self._emit(session_id, "error", "WS_ERROR", f"WebSocket 错误: {exc}")

    async def _handshake(self, ws: Any, session_key: str, agent_id: Optional[str] = None) -> bool:
        """Connect + authenticate with Gateway (with device identity signing)."""
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
            msg = json.loads(raw)
            if msg.get("event") != "connect.challenge":
                return False

            nonce = msg.get("payload", {}).get("nonce", "")

            # Build a display name consistent with frontend session labels
            suffix = session_key.split(":", 2)[-1][:20] if session_key else ""
            display_name = f"ArtClaw TM · {suffix}"

            scopes = ["operator.read", "operator.write", "operator.admin"]
            signed_at_ms = int(time.time() * 1000)

            params: Dict[str, Any] = {
                "minProtocol": _PROTOCOL_VERSION,
                "maxProtocol": _PROTOCOL_VERSION,
                "client": {
                    "id": "cli",
                    "displayName": display_name,
                    "version": "0.1.0",
                    "platform": "win32",
                    "mode": "cli",
                },
                "caps": [],
                "auth": {"token": self._token},
                "role": "operator",
                "scopes": scopes,
            }

            # Device identity 签名（可选，缺失时 fallback 到 token-only）
            try:
                import sys, os as _os
                _core_dir = _os.path.normpath(_os.path.join(
                    _os.path.dirname(__file__), "..", "..", "..", "..", "..", "core"))
                if _os.path.isdir(_core_dir) and _core_dir not in sys.path:
                    sys.path.append(_core_dir)
                from device_auth import get_device_identity, build_device_auth
                identity = get_device_identity()
                if identity:
                    params["device"] = build_device_auth(
                        identity, "operator", scopes, signed_at_ms, nonce,
                        auth_token=self._token,
                    )
            except Exception:
                pass  # 静默降级

            req_id = str(uuid.uuid4())
            await ws.send(json.dumps({
                "type": "req",
                "id": req_id,
                "method": "connect",
                "params": params,
            }))

            deadline = time.time() + 10.0
            while time.time() < deadline:
                raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                ack = json.loads(raw)
                if ack.get("type") == "res" and ack.get("id") == req_id:
                    if ack.get("error"):
                        logger.warning("Handshake error: %s", ack["error"])
                        return False
                    return True
        except Exception as exc:
            logger.warning("Handshake exception: %s", exc)
        return False

    async def _wait_for_ack(self, ws: Any, req_id: str, timeout: float = 15.0) -> Optional[dict]:
        """Wait for RPC response, ignoring intermediate chat/tick events."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=min(deadline - time.time(), 5.0))
            except asyncio.TimeoutError:
                break
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "res" and msg.get("id") == req_id:
                if msg.get("error"):
                    logger.error("RPC error: %s", msg["error"])
                    return None
                return msg.get("payload", {})
        return None

    async def _receive_stream(
        self,
        ws: Any,
        session_id: str,
        cancel_flag: asyncio.Event,
        session_key: str,
        run_id: str,
    ) -> None:
        """Receive chat events until final/aborted/error. On cancel, send abort on same WS."""
        latest_text = ""
        abs_deadline = time.time() + _CHAT_TIMEOUT
        idle_deadline = time.time() + _IDLE_TIMEOUT

        while True:
            now = time.time()
            if now >= abs_deadline or now >= idle_deadline:
                break

            # Check cancel flag
            if cancel_flag.is_set():
                cancel_flag.clear()
                logger.info(f"[GW-WS] Cancel flag set, sending chat.abort on same WS, key={session_key}")
                await self._send_abort_on_ws(ws, session_key)
                # Notify frontend
                for h in self._handlers:
                    await h({"session_id": session_id, "type": "typing", "is_typing": False, "source": "assistant"})
                return

            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("event") != "chat":
                continue

            payload = msg.get("payload", {})

            # Filter by runId or sessionKey
            event_run_id = payload.get("runId", "")
            event_session = payload.get("sessionKey", "")

            if run_id and event_run_id:
                if event_run_id != run_id:
                    continue
            elif session_key and event_session:
                if not (event_session == session_key
                        or session_key in event_session
                        or event_session in session_key):
                    continue

            state = payload.get("state", "")
            message = payload.get("message", {})
            text = self._extract_text(message)

            if state not in ("delta", "final", "aborted", "error"):
                continue

            # Reset idle timeout
            idle_deadline = time.time() + _IDLE_TIMEOUT

            if state == "delta" and text:
                # Gateway sends cumulative text, extract incremental
                incremental = text[len(latest_text):] if text.startswith(latest_text) else text
                latest_text = text
                if incremental:
                    for h in self._handlers:
                        await h({"session_id": session_id, "type": "message_chunk", "content": incremental})

            elif state == "final":
                final_text = text or latest_text
                if final_text:
                    for h in self._handlers:
                        await h({"session_id": session_id, "type": "message", "role": "assistant", "content": final_text})
                return

            elif state in ("aborted", "error"):
                result = text or latest_text or f"[{state}]"
                for h in self._handlers:
                    await h({"session_id": session_id, "type": "message", "role": "assistant", "content": result})
                return

        # Timeout
        if latest_text:
            for h in self._handlers:
                await h({"session_id": session_id, "type": "message", "role": "assistant", "content": latest_text})

    async def _send_abort_on_ws(self, ws: Any, session_key: str) -> None:
        """Send chat.abort on the SAME WebSocket connection (best-effort)."""
        try:
            req_id = str(uuid.uuid4())
            await ws.send(json.dumps({
                "type": "req",
                "id": req_id,
                "method": "chat.abort",
                "params": {"sessionKey": session_key},
            }))
            logger.info(f"[GW-WS] chat.abort sent for {session_key[:50]}")
            # Wait briefly for ACK
            try:
                deadline = time.time() + 3.0
                while time.time() < deadline:
                    raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
                    ack = json.loads(raw)
                    if ack.get("type") == "res" and ack.get("id") == req_id:
                        logger.info(f"[GW-WS] chat.abort ACK: {json.dumps(ack)}")
                        return
            except asyncio.TimeoutError:
                logger.info("[GW-WS] chat.abort ACK timeout")
        except Exception as exc:
            logger.info(f"[GW-WS] chat.abort failed: {exc}")

    # ------------------------------------------------------------------
    # cancel
    # ------------------------------------------------------------------

    async def send_cancel(self, session_id: str) -> None:
        """Signal the active chat task to send abort on its WS connection."""
        flag = self._cancel_flags.get(session_id)
        if flag:
            logger.info(f"[GW-WS] Setting cancel flag for session {session_id}")
            flag.set()
        else:
            logger.info(f"[GW-WS] No cancel flag for session {session_id} (no active chat)")

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text(message: Any) -> str:
        """Extract text from a Gateway message object."""
        if isinstance(message, str):
            return message
        if isinstance(message, dict):
            content = message.get("content", [])
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        parts.append(block)
                return "".join(parts)
        return ""

    async def _emit(self, session_id: str, msg_type: str, code: str, message: str) -> None:
        for h in self._handlers:
            await h({"session_id": session_id, "type": msg_type, "code": code, "message": message})

    async def get_agents(self) -> List[Dict[str, Any]]:
        return []
