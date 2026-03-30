"""
openclaw_bridge.py - OpenClaw Gateway WebSocket RPC 核心连接层
==============================================================
职责: Gateway 握手、消息循环、RPC 请求、chat 事件分发。
公开 API 见 openclaw_chat.py。
"""
# Ref: docs/UEClawBridge/specs/架构设计.md

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from typing import Any, Callable, Dict, Optional

try:
    import unreal
except ImportError:
    unreal = None

from init_unreal import UELogger

# ---------------------------------------------------------------------------
# 配置常量
# ---------------------------------------------------------------------------

_DEFAULT_AGENT_ID = "qi"
_DEFAULT_TOKEN = "ec8900cf3e3c4bbfab43c8d7d5a4638c69b854e075902325"
_PROTOCOL_VERSION = 3
_CLIENT_NAME = "cli"
_CLIENT_VERSION = "0.1.0"


def _load_gateway_config() -> dict:
    """从平台配置文件读取 gateway 配置"""
    from bridge_config import _resolve_platform_config_path
    import os
    config_path = _resolve_platform_config_path()
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f).get("gateway", {})
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# OpenClawBridge — WebSocket 连接与 RPC
# ---------------------------------------------------------------------------

class OpenClawBridge:
    """
    OpenClaw Gateway WebSocket RPC 客户端。
    在后台线程运行 asyncio 事件循环，提供同步发送接口。
    """

    def __init__(self, gateway_url: str = "", agent_id: str = "", token: str = ""):
        gw = _load_gateway_config()
        self.gateway_url = gateway_url or f"ws://127.0.0.1:{gw.get('port', 18789)}"
        self.agent_id = agent_id or _DEFAULT_AGENT_ID
        self.token = token or gw.get("auth", {}).get("token", _DEFAULT_TOKEN)

        self._ws = None
        self._connected = False
        self._pending: Dict[str, asyncio.Future] = {}
        self._session_key: Optional[str] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._cancel_event = threading.Event()

        # on_ai_message(state, text) — delta/final/aborted/error
        self.on_ai_message: Optional[Callable[[str, str], None]] = None
        # on_tool_event(event_type, data) — tool_call/tool_result
        self.on_tool_event: Optional[Callable[[str, dict], None]] = None

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="OpenClaw-WS")
        self._thread.start()

        deadline = time.time() + 10.0
        while time.time() < deadline and not self._connected:
            time.sleep(0.1)

        if self._connected:
            UELogger.info(f"OpenClaw Bridge: connected to {self.gateway_url}")
        else:
            UELogger.warning("OpenClaw Bridge: connection timeout, will retry in background")
        return self._connected

    def stop(self):
        self._stop_event.set()
        self._connected = False
        if self._ws:
            try:
                asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)
            except Exception:
                pass
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._ws = None
        self._loop = None
        self._thread = None
        UELogger.info("OpenClaw Bridge: stopped")

    def cancel(self):
        """取消当前正在等待的 AI 请求"""
        self._cancel_event.set()
        UELogger.info("OpenClaw Bridge: cancel requested")

    def is_connected(self) -> bool:
        return self._connected

    def reset_session(self):
        self._session_key = None

    def get_session_key(self) -> str:
        return self._session_key or ""

    def set_session_key(self, key: str):
        self._session_key = key

    # ------------------------------------------------------------------
    # 发送接口
    # ------------------------------------------------------------------

    def send_message(self, message: str, timeout: float = 120.0) -> str:
        """同步发送消息并等待完整回复"""
        if not self._connected or not self._loop:
            self.start()
            if not self._connected:
                return "[Error] Not connected to OpenClaw Gateway. Check if openclaw is running."

        future = asyncio.run_coroutine_threadsafe(
            self._async_chat_send(message), self._loop
        )
        try:
            return future.result(timeout=timeout)
        except asyncio.TimeoutError:
            return "[Error] AI response timed out."
        except Exception as e:
            return f"[Error] {str(e)}"

    def send_message_async(self, message: str, callback: Callable[[str], None]):
        """异步发送消息，完成后调用 callback（在工作线程）"""
        def _worker():
            result = self.send_message(message)
            try:
                callback(result)
            except Exception as e:
                UELogger.mcp_error(f"send_message_async callback error: {e}")

        threading.Thread(target=_worker, daemon=True, name="OCBridge-Chat").start()

    # ------------------------------------------------------------------
    # asyncio 内部
    # ------------------------------------------------------------------

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_loop())
        except Exception as e:
            UELogger.mcp_error(f"OpenClaw Bridge loop error: {e}")
        finally:
            self._loop.close()
            self._loop = None

    async def _connect_loop(self):
        try:
            import websockets
        except ImportError:
            UELogger.mcp_error("OpenClaw Bridge: 'websockets' package not found. pip install websockets")
            return

        backoff = 1.0
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(
                    self.gateway_url,
                    max_size=10 * 1024 * 1024,
                    ping_interval=30,
                    ping_timeout=10,
                ) as ws:
                    self._ws = ws
                    if await self._handshake(ws):
                        self._connected = True
                        backoff = 1.0
                        UELogger.info("OpenClaw Bridge: handshake OK")
                        await self._message_loop(ws)
                    else:
                        UELogger.warning("OpenClaw Bridge: handshake failed")
            except Exception as e:
                UELogger.warning(f"OpenClaw Bridge: connection error ({e}), retry in {backoff:.0f}s")

            self._connected = False
            self._ws = None

            for fut in list(self._pending.values()):
                if not fut.done():
                    fut.set_exception(ConnectionError("WebSocket disconnected"))
            self._pending.clear()

            if self._stop_event.is_set():
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    async def _handshake(self, ws) -> bool:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
            msg = json.loads(raw)
            if msg.get("event") != "connect.challenge":
                return False
            nonce = msg.get("payload", {}).get("nonce", "")
            if not nonce:
                return False

            connect_id = str(uuid.uuid4())
            await ws.send(json.dumps({
                "type": "req", "id": connect_id, "method": "connect",
                "params": {
                    "minProtocol": _PROTOCOL_VERSION,
                    "maxProtocol": _PROTOCOL_VERSION,
                    "client": {
                        "id": _CLIENT_NAME,
                        "displayName": "UE Claw Bridge",
                        "version": _CLIENT_VERSION,
                        "platform": "win32",
                        "mode": "cli",
                    },
                    "caps": [], "auth": {"token": self.token},
                    "role": "operator", "scopes": ["operator.admin"],
                },
            }))

            deadline = time.time() + 10.0
            while time.time() < deadline:
                raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                msg = json.loads(raw)
                if msg.get("type") == "res" and msg.get("id") == connect_id:
                    if msg.get("error"):
                        UELogger.mcp_error(f"OpenClaw connect error: {msg['error']}")
                        return False
                    return True
        except Exception as e:
            UELogger.mcp_error(f"OpenClaw Bridge: handshake error: {e}")
        return False

    async def _message_loop(self, ws):
        try:
            async for raw in ws:
                if self._stop_event.is_set():
                    break
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")
                if msg_type == "res":
                    req_id = msg.get("id")
                    if req_id in self._pending:
                        fut = self._pending.pop(req_id)
                        if not fut.done():
                            if msg.get("error"):
                                fut.set_exception(RuntimeError(json.dumps(msg["error"])))
                            else:
                                fut.set_result(msg.get("payload"))
                elif msg.get("event"):
                    event_name = msg["event"]
                    if event_name == "chat":
                        self._handle_chat_event(msg.get("payload", {}))
                    elif event_name == "tick":
                        pass
                    else:
                        pass  # unhandled event (e.g. cron, tick variants) — ignore silently
        except Exception as e:
            if not self._stop_event.is_set():
                UELogger.warning(f"OpenClaw Bridge: message loop error: {e}")

    def _handle_chat_event(self, payload: dict):
        """解析 chat 事件，提取文本并回调 on_ai_message"""
        state = payload.get("state", "")
        message = payload.get("message", {})
        session_key = payload.get("sessionKey", "")

        # 过滤其他 session 的事件
        if self._session_key and session_key and session_key != self._session_key:
            return

        # 提取工具调用事件（嵌入在 content blocks 中）
        if isinstance(message, dict):
            content = message.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type", "")
                    if btype == "tool_use" and self.on_tool_event:
                        self.on_tool_event("tool_call", {
                            "tool_name": block.get("name", ""),
                            "tool_id": block.get("id", ""),
                            "arguments": block.get("input", {}),
                        })
                    elif btype == "tool_result" and self.on_tool_event:
                        self.on_tool_event("tool_result", {
                            "tool_id": block.get("tool_use_id", ""),
                            "content": block.get("content", ""),
                            "is_error": block.get("is_error", False),
                        })

        # 提取文本
        text = _extract_text(message)

        if self.on_ai_message and text:
            self.on_ai_message(state, text)

        if state in ("final", "aborted", "error"):
            if state == "aborted":
                text = text or "[Response aborted]"
            elif state == "error":
                err = payload.get("error", {})
                text = text or (f"[Error] {err.get('message', 'Unknown')}" if isinstance(err, dict) else f"[Error] {err}")
            for fut in list(self._pending.values()):
                if hasattr(fut, '_is_chat_wait') and not fut.done():
                    fut.set_result(text)

    async def _rpc_request(self, method: str, params: dict, timeout: float = 120.0) -> Any:
        if not self._ws:
            raise ConnectionError("Not connected")
        req_id = str(uuid.uuid4())
        fut = self._loop.create_future()
        self._pending[req_id] = fut
        await self._ws.send(json.dumps({"type": "req", "id": req_id, "method": method, "params": params}))
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise
        except Exception:
            self._pending.pop(req_id, None)
            raise

    async def _async_chat_send(self, message: str) -> str:
        if not self._session_key:
            self._session_key = f"{self.agent_id}/ue-editor"

        params = {
            "sessionKey": self._session_key,
            "message": message,
            "idempotencyKey": str(uuid.uuid4()),
        }
        result = await self._rpc_request("chat.send", params, timeout=120.0)

        if isinstance(result, dict):
            status = result.get("status", "")
            if status in ("started", "streaming", "accepted", "running"):
                run_id = result.get("runId", "")
                UELogger.info(f"OpenClaw chat fire-and-forget started (runId={run_id[:8]}...)")
                self._cancel_event.clear()
                return await self._wait_for_final(timeout=120.0)
            msg = result.get("message", "")
            if isinstance(msg, dict):
                return msg.get("content", "") or msg.get("text", "")
            return str(msg) if msg else json.dumps(result)
        return str(result) if result else ""

    async def _wait_for_final(self, timeout: float = 120.0) -> str:
        """等待 chat final 事件，期间支持 cancel"""
        latest_text = [""]
        final_event = asyncio.Event()
        final_text = [""]
        original_handler = self.on_ai_message

        def _capture(state: str, text: str):
            if state == "delta":
                latest_text[0] = text
            elif state in ("final", "aborted", "error"):
                final_text[0] = text if text else latest_text[0]
                final_event.set()
            if original_handler:
                original_handler(state, text)

        self.on_ai_message = _capture

        try:
            deadline = asyncio.get_event_loop().time() + timeout
            while not final_event.is_set():
                # 检查 cancel
                if self._cancel_event.is_set():
                    self._cancel_event.clear()
                    return latest_text[0] or "[Cancelled]"
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    await asyncio.wait_for(final_event.wait(), timeout=min(0.2, remaining))
                except asyncio.TimeoutError:
                    pass
            if final_event.is_set():
                return final_text[0]
            return (latest_text[0] + "\n\n[Response truncated - timeout]") if latest_text[0] else "[Error] AI response timed out"
        finally:
            self.on_ai_message = original_handler


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _extract_text(message) -> str:
    """从 OpenClaw message 结构中提取文本"""
    if isinstance(message, dict):
        content = message.get("content", "")
        if isinstance(content, list):
            return "".join(
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        if isinstance(content, str):
            return content
        return message.get("text", "")
    if isinstance(message, str):
        return message
    return ""
