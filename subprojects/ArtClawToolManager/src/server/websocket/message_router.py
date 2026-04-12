# Ref: docs/features/phase1-foundation.md#WebSocket
# Ref: docs/api/api-design.md#WebSocketAPI
"""
Message router – orchestrates message flow between:

    Frontend (WebSocket) ↔ Gateway (OpenClaw) ↔ DCC Adapters

Handles:
* Client chat messages (including slash-command interception)
* Gateway response messages (streaming chunks, tool calls, etc.)
* DCC status-change notifications
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Slash commands processed locally (not forwarded to AI)
_LOCAL_COMMANDS = {"/connect", "/disconnect", "/status", "/clear", "/cancel"}


class MessageRouter:
    """Central coordinator between WS manager, Gateway client, and DCC
    manager."""

    def __init__(
        self,
        ws_manager,      # websocket.manager.ConnectionManager
        gateway_client,  # services.gateway_client.GatewayClient
        dcc_manager,     # services.dcc_manager.DCCManager
    ) -> None:
        self._ws = ws_manager
        self._gw = gateway_client
        self._dcc = dcc_manager

        # Wire up callbacks so components can push messages through us
        self._gw.on_message(self.handle_gateway_message)
        self._dcc.on_status_change(self.handle_dcc_status_change)

    # ------------------------------------------------------------------
    # client → router
    # ------------------------------------------------------------------

    async def handle_client_message(
        self, session_id: str, message: Dict[str, Any]
    ) -> None:
        """Entry point for every message arriving from the frontend WS."""
        msg_type = message.get("type")

        if msg_type == "cancel":
            await self._handle_cancel(session_id)
            return

        if msg_type != "chat":
            return  # only chat & cancel flow through here

        content: str = (message.get("content") or "").strip()
        if not content:
            return

        # --- slash-command interception ---
        if content.startswith("/"):
            parts = content.split(maxsplit=1)
            cmd = parts[0].lower()
            if cmd in _LOCAL_COMMANDS:
                result = await self.handle_slash_command(session_id, content)
                if result:
                    await self._ws.send_to_session(session_id, result)
                return

        # --- normal chat: forward to gateway ---
        if not self._gw.connected:
            # If gateway URL is not configured, show a helpful message
            if not self._gw.url:
                await self._ws.send_to_session(
                    session_id,
                    _system_message(
                        "💡 Gateway 未配置。Tool Manager 当前仅提供 Skill/Workflow/Tool 管理功能。\n"
                        "如需 AI 对话，请在 Settings → Connection 中配置 Gateway URL，"
                        "或通过 DCC 内的 ArtClaw 面板直接与 AI 对话。"
                    ),
                )
            else:
                await self._ws.send_to_session(
                    session_id,
                    {
                        "type": "error",
                        "code": "GATEWAY_DISCONNECTED",
                        "message": "Gateway 未连接，请先执行 /connect",
                    },
                )
            # Stop typing indicator
            await self._ws.send_to_session(
                session_id,
                {"type": "typing", "is_typing": False, "source": "assistant"},
            )
            return

        # Notify UI that AI is "typing"
        await self._ws.send_to_session(
            session_id,
            {"type": "typing", "is_typing": True, "source": "assistant"},
        )

        await self._gw.send_chat_message(
            session_id=session_id,
            content=content,
            agent_id=message.get("agent_id"),
            attachments=message.get("attachments"),
        )

    # ------------------------------------------------------------------
    # gateway → router
    # ------------------------------------------------------------------

    async def handle_gateway_message(self, data: Dict[str, Any]) -> None:
        """Invoked by GatewayClient whenever the gateway sends a message."""
        session_id = data.get("session_id")
        if not session_id:
            logger.warning("Gateway message without session_id: %s", data)
            return

        msg_type = data.get("type", "message")

        # Map gateway payload to the WS protocol expected by the frontend
        if msg_type in (
            "message",
            "message_chunk",
            "typing",
            "context_usage",
            "tool_call",
            "tool_result",
            "error",
        ):
            await self._ws.send_to_session(session_id, data)
        else:
            # Forward anything else unchanged
            await self._ws.send_to_session(session_id, data)

    # ------------------------------------------------------------------
    # DCC → router
    # ------------------------------------------------------------------

    async def handle_dcc_status_change(
        self, dcc_type: str, status: Dict[str, Any]
    ) -> None:
        """Broadcast DCC connection state changes to all WS sessions."""
        await self._ws.broadcast(
            {
                "type": "dcc_status",
                "dcc_type": dcc_type,
                **status,
            }
        )

    # ------------------------------------------------------------------
    # slash commands
    # ------------------------------------------------------------------

    async def handle_slash_command(
        self, session_id: str, command: str
    ) -> Optional[Dict[str, Any]]:
        """Process a local slash command and return a response message."""
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()

        if cmd == "/connect":
            success = await self._gw.connect()
            status = "connected" if success else "failed"
            return _system_message(
                f"Gateway 连接{'成功' if success else '失败'} ({status})"
            )

        if cmd == "/disconnect":
            await self._gw.disconnect()
            return _system_message("已断开 Gateway 连接")

        if cmd == "/status":
            return await self._build_status_response()

        if cmd == "/clear":
            return {
                "type": "clear",
                "session_id": session_id,
                "message": "会话已清空",
            }

        if cmd == "/cancel":
            await self._handle_cancel(session_id)
            return _system_message("已发送取消请求")

        return None

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    async def _handle_cancel(self, session_id: str) -> None:
        """Send cancel to gateway and stop typing indicator."""
        if self._gw.connected:
            await self._gw.send_cancel(session_id)

        await self._ws.send_to_session(
            session_id,
            {"type": "typing", "is_typing": False, "source": "assistant"},
        )

    async def _build_status_response(self) -> Dict[str, Any]:
        """Gather system status for the ``/status`` command."""
        dcc_status = await self._dcc.get_all_status()
        dcc_list = [
            {"dcc": k, "connected": v.get("connected", False)}
            for k, v in dcc_status.items()
        ]

        return {
            "type": "message",
            "id": str(uuid.uuid4()),
            "role": "system",
            "content": _format_status_text(
                gateway_connected=self._gw.connected,
                dcc_list=dcc_list,
                ws_count=self._ws.get_connection_count(),
                ws_sessions=self._ws.get_session_ids(),
            ),
            "ts": time.time(),
        }


# ---------------------------------------------------------------------------
# formatting utilities
# ---------------------------------------------------------------------------


def _system_message(text: str) -> Dict[str, Any]:
    return {
        "type": "message",
        "id": str(uuid.uuid4()),
        "role": "system",
        "content": text,
        "ts": time.time(),
    }


def _format_status_text(
    *,
    gateway_connected: bool,
    dcc_list: List[Dict[str, Any]],
    ws_count: int,
    ws_sessions: List[str],
) -> str:
    gw_icon = "🟢" if gateway_connected else "🔴"
    lines = [
        "📊 **系统状态**",
        f"  Gateway: {gw_icon} {'已连接' if gateway_connected else '未连接'}",
        f"  WebSocket 连接数: {ws_count}",
        f"  活跃会话: {len(ws_sessions)}",
        "",
        "**DCC 连接状态:**",
    ]
    for d in dcc_list:
        icon = "🟢" if d["connected"] else "⚪"
        lines.append(f"  {icon} {d['dcc']}")

    return "\n".join(lines)
