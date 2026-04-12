# Ref: docs/api/api-design.md#WebSocketAPI
# Ref: docs/features/phase1-foundation.md#WebSocket
"""
FastAPI WebSocket endpoint for real-time chat.

URL: ``ws://localhost:9876/ws/chat/{session_id}``

Client → Server message types:
    chat, ping, typing, cancel

Server → Client message types:
    pong, message_received, message, message_chunk, typing,
    context_usage, tool_call, tool_result, error, dcc_status,
    job_progress
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

# These will be injected at startup (see main.py lifespan)
_ws_manager = None   # websocket.manager.ConnectionManager
_msg_router = None   # websocket.message_router.MessageRouter


def init_chat_ws(ws_manager, msg_router) -> None:
    """Called once from lifespan to wire up shared instances."""
    global _ws_manager, _msg_router
    _ws_manager = ws_manager
    _msg_router = msg_router


# ---------------------------------------------------------------------------
# endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str) -> None:
    """Main chat WebSocket endpoint.

    The connection lifecycle:
    1. Accept & register in ConnectionManager
    2. Start heartbeat background task
    3. Enter receive loop – dispatch each message by ``type``
    4. On disconnect clean up resources
    """
    if _ws_manager is None or _msg_router is None:
        await websocket.close(code=1013, reason="Server not ready")
        return

    await _ws_manager.connect(websocket, session_id)
    await _ws_manager.start_heartbeat(websocket, session_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message: Dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                await _send_error(websocket, "INVALID_JSON", "Malformed JSON")
                continue

            msg_type = message.get("type")
            await _dispatch(websocket, session_id, msg_type, message)

    except WebSocketDisconnect:
        logger.info("Client disconnected  session=%s", session_id)
    except Exception as exc:
        logger.exception(
            "Unexpected error in WS loop  session=%s", session_id
        )
        try:
            await _send_error(websocket, "INTERNAL_ERROR", str(exc))
        except Exception:
            pass
    finally:
        await _ws_manager.disconnect(websocket, session_id)


# ---------------------------------------------------------------------------
# dispatch helpers
# ---------------------------------------------------------------------------

async def _dispatch(
    ws: WebSocket,
    session_id: str,
    msg_type: str | None,
    message: Dict[str, Any],
) -> None:
    """Route incoming client message to the appropriate handler."""
    if msg_type == "ping":
        await ws.send_json({"type": "pong", "ts": time.time()})

    elif msg_type == "chat":
        await _handle_chat(ws, session_id, message)

    elif msg_type == "typing":
        # Broadcast typing state to other connections of the same session
        await _ws_manager.send_to_session(
            session_id,
            {
                "type": "typing",
                "is_typing": message.get("is_typing", False),
                "source": "user",
            },
        )

    elif msg_type == "cancel":
        await _handle_cancel(session_id)

    else:
        await _send_error(
            ws, "UNKNOWN_TYPE", f"Unknown message type: {msg_type}"
        )


async def _handle_chat(
    ws: WebSocket, session_id: str, message: Dict[str, Any]
) -> None:
    """Process an incoming chat message from the client."""
    content = (message.get("content") or "").strip()
    if not content:
        await _send_error(ws, "EMPTY_CONTENT", "Message content is empty")
        return

    # ACK receipt immediately
    await ws.send_json(
        {
            "type": "message_received",
            "session_id": session_id,
            "ts": time.time(),
        }
    )

    # Delegate to the message router (which handles slash commands,
    # Gateway forwarding, etc.)
    await _msg_router.handle_client_message(session_id, message)


async def _handle_cancel(session_id: str) -> None:
    """Forward a cancel request through the message router."""
    await _msg_router.handle_client_message(
        session_id, {"type": "cancel"}
    )


async def _send_error(ws: WebSocket, code: str, message: str) -> None:
    """Send a typed error frame to a single client WebSocket."""
    try:
        await ws.send_json(
            {"type": "error", "code": code, "message": message}
        )
    except Exception:
        pass
