"""
bridge_core.py - OpenClaw Gateway WebSocket RPC 核心
=====================================================

平台无关的 WebSocket RPC 客户端。不依赖任何 DCC 模块（unreal/maya/max）。
DCC 特有逻辑（日志、状态文件、线程调度）通过回调/钩子注入。

使用方式:
    from bridge_core import OpenClawBridge
    bridge = OpenClawBridge(logger=my_logger, on_status_changed=my_callback)
    bridge.start()
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from typing import Any, Callable, Dict, Optional

from bridge_config import (
    DEFAULT_GATEWAY_URL,
    DEFAULT_AGENT_ID,
    DEFAULT_TOKEN,
    PROTOCOL_VERSION,
    CLIENT_NAME,
    CLIENT_VERSION,
    load_config,
)


class BridgeLogger:
    """默认日志接口 — 子类或替换实例以对接 DCC 日志系统"""

    def info(self, msg: str):
        print(f"[OpenClaw] {msg}")

    def warning(self, msg: str):
        print(f"[OpenClaw WARN] {msg}")

    def error(self, msg: str):
        print(f"[OpenClaw ERROR] {msg}")

    def debug(self, msg: str):
        pass  # 默认静默


class OpenClawBridge:
    """
    OpenClaw Gateway WebSocket RPC 客户端。

    在独立线程中运行 asyncio 事件循环，提供同步的 send_message() 接口。

    平台无关 — DCC 特有行为通过以下钩子注入:
      - logger: BridgeLogger 实例（日志输出）
      - on_status_changed: Callable[[bool, str], None]（连接状态变更通知）
    """

    def __init__(
        self,
        gateway_url: str = "",
        agent_id: str = "",
        token: str = "",
        client_id: str = "",
        logger: Optional[BridgeLogger] = None,
        on_status_changed: Optional[Callable[[bool, str], None]] = None,
    ):
        config = load_config()
        gw_config = config.get("gateway", {})

        self.gateway_url = gateway_url or f"ws://127.0.0.1:{gw_config.get('port', 18789)}"
        self.agent_id = agent_id or DEFAULT_AGENT_ID
        self.token = token or gw_config.get("auth", {}).get("token", DEFAULT_TOKEN)
        self.client_id = client_id or "ue-editor"  # 默认 UE，DCC 覆盖

        self._log = logger or BridgeLogger()
        self._on_status_changed = on_status_changed

        self._ws = None
        self._connected = False
        self._pending: Dict[str, asyncio.Future] = {}
        self._event_handlers: Dict[str, Callable] = {}
        self._session_key: Optional[str] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 回调: 收到 AI 流式消息时
        self.on_ai_message: Optional[Callable[[str, str], None]] = None
        # 回调: 收到 AI thinking 内容时
        self.on_ai_thinking: Optional[Callable[[str, str], None]] = None
        # 当前活跃的 chat runId
        self._active_run_id: Optional[str] = None
        # 取消信号
        self._cancel_event: Optional[asyncio.Event] = None

    # ------------------------------------------------------------------
    # 公开 API (同步)
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """启动后台连接线程"""
        if self._thread and self._thread.is_alive():
            return True

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="OpenClaw-WS"
        )
        self._thread.start()

        # 等待连接就绪 (最多 10 秒)
        deadline = time.time() + 10.0
        while time.time() < deadline and not self._connected:
            time.sleep(0.1)

        if self._connected:
            self._log.info(f"OpenClaw Bridge: connected to {self.gateway_url}")
        else:
            self._log.warning(
                "OpenClaw Bridge: connection timeout, will retry in background"
            )

        return self._connected

    def stop(self):
        """停止连接"""
        self._stop_event.set()
        self._set_connected(False, "shutdown")

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
        self._log.info("OpenClaw Bridge: stopped")

    def is_connected(self) -> bool:
        return self._connected

    def send_message(self, message: str, timeout: float = 1800.0) -> str:
        """发送消息给 AI 并等待完整回复 (同步阻塞)。"""
        if not self._connected or not self._loop:
            self.start()
            if not self._connected:
                return "[错误] 未连接到 OpenClaw Gateway，请确认 OpenClaw 正在运行。"

        future = asyncio.run_coroutine_threadsafe(
            self._async_chat_send(message), self._loop
        )

        try:
            return future.result(timeout=timeout)
        except asyncio.TimeoutError:
            return "[错误] AI 响应超时。"
        except Exception as e:
            return f"[错误] {str(e)}"

    def send_message_async(self, message: str, callback: Callable[[str], None]):
        """异步发送消息，完成后调用 callback。"""

        def _worker():
            result = self.send_message(message)
            callback(result)

        threading.Thread(
            target=_worker, daemon=True, name="OCBridge-Chat"
        ).start()

    def cancel_current(self):
        """取消当前正在进行的 AI 请求。"""
        if self._cancel_event and self._loop:
            self._loop.call_soon_threadsafe(self._cancel_event.set)
            self._log.info("OpenClaw Bridge: cancel requested")
        self._active_run_id = None

    def reset_session(self):
        """重置会话: 清空 session key，下次发消息时自动创建新 session。"""
        self._session_key = None
        self._log.info("OpenClaw Bridge: session reset")

    async def _async_reset_session(self, session_key: str):
        """向 Gateway 发送 /new 重置指定 session（不走流式回调）。"""
        if not self._ws:
            return

        params = {
            "sessionKey": session_key,
            "message": "/new",
            "idempotencyKey": str(uuid.uuid4()),
        }

        try:
            await self._rpc_request("chat.send", params, timeout=10.0)
        except Exception as e:
            self._log.debug(f"reset_session RPC: {e}")

    # ------------------------------------------------------------------
    # 内部: 状态管理
    # ------------------------------------------------------------------

    def _set_connected(self, connected: bool, detail: str = ""):
        """更新连接状态并通知外部"""
        changed = self._connected != connected
        self._connected = connected
        if changed and self._on_status_changed:
            try:
                self._on_status_changed(connected, detail)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 内部: asyncio 事件循环
    # ------------------------------------------------------------------

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_loop())
        except Exception as e:
            self._log.error(f"OpenClaw Bridge loop error: {e}")
        finally:
            self._loop.close()
            self._loop = None

    async def _connect_loop(self):
        try:
            import websockets
        except ImportError:
            self._log.error(
                "OpenClaw Bridge: 'websockets' package not found. "
                "Install: pip install websockets"
            )
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
                        self._set_connected(True, "connected")
                        backoff = 1.0
                        self._log.info("OpenClaw Bridge: handshake OK")
                        await self._message_loop(ws)
                    else:
                        self._log.warning("OpenClaw Bridge: handshake failed")

            except Exception as e:
                self._log.warning(
                    f"OpenClaw Bridge: connection error ({e}), retry in {backoff:.0f}s"
                )

            was_connected = self._connected
            self._set_connected(False, "disconnected" if was_connected else "")

            for fid, fut in list(self._pending.items()):
                if not fut.done():
                    fut.set_exception(ConnectionError("WebSocket disconnected"))
            self._pending.clear()

            if was_connected and self.on_ai_message:
                try:
                    self.on_ai_message(
                        "error",
                        "[连接中断] OpenClaw Gateway 已断开（可能正在重启）。"
                        "请点击 Connect 按钮或输入 /connect 重新连接。",
                    )
                except Exception:
                    pass

            if self._stop_event.is_set():
                break

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    # ------------------------------------------------------------------
    # displayName 映射
    # ------------------------------------------------------------------

    # client_id → 显示名称
    _DISPLAY_NAME_MAP = {
        "ue-editor": "UE Claw Bridge",
        "maya-editor": "Maya Claw Bridge",
        "max-editor": "Max Claw Bridge",
    }

    def _get_display_name(self) -> str:
        """根据 client_id 返回对应的 displayName"""
        return self._DISPLAY_NAME_MAP.get(
            self.client_id,
            f"{self.client_id.replace('-', ' ').title()} Bridge"
        )

    # ------------------------------------------------------------------
    # 内部: OpenClaw RPC 协议
    # ------------------------------------------------------------------

    async def _handshake(self, ws) -> bool:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
            msg = json.loads(raw)

            if msg.get("event") != "connect.challenge":
                self._log.warning(
                    f"OpenClaw Bridge: expected challenge, got: {msg.get('event')}"
                )
                return False

            nonce = msg.get("payload", {}).get("nonce", "")
            if not nonce:
                self._log.warning("OpenClaw Bridge: challenge has no nonce")
                return False

            # 根据 client_id 动态生成 displayName
            display_name = self._get_display_name()

            connect_params = {
                "minProtocol": PROTOCOL_VERSION,
                "maxProtocol": PROTOCOL_VERSION,
                "client": {
                    "id": CLIENT_NAME,
                    "displayName": display_name,
                    "version": CLIENT_VERSION,
                    "platform": "win32",
                    "mode": "cli",
                },
                "caps": [],
                "auth": {"token": self.token},
                "role": "operator",
                "scopes": ["operator.admin"],
            }

            connect_id = str(uuid.uuid4())
            connect_frame = {
                "type": "req",
                "id": connect_id,
                "method": "connect",
                "params": connect_params,
            }

            await ws.send(json.dumps(connect_frame))

            deadline = time.time() + 10.0
            while time.time() < deadline:
                raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                msg = json.loads(raw)

                if msg.get("type") == "res" and msg.get("id") == connect_id:
                    if msg.get("error"):
                        self._log.error(
                            f"OpenClaw connect error: {msg['error']}"
                        )
                        return False
                    return True

            self._log.warning("OpenClaw Bridge: connect response timeout")
            return False

        except Exception as e:
            self._log.error(f"OpenClaw Bridge: handshake error: {e}")
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
                                fut.set_exception(
                                    RuntimeError(json.dumps(msg["error"]))
                                )
                            else:
                                fut.set_result(msg.get("payload"))

                elif msg_type == "event" or msg.get("event"):
                    event_name = msg.get("event", "")
                    payload = msg.get("payload", {})

                    if event_name == "chat":
                        self._handle_chat_event(payload)
                    elif event_name == "agent":
                        self._handle_agent_event(payload)
                    elif event_name in ("tick", "health"):
                        pass
                    else:
                        self._log.debug(
                            f"OpenClaw Bridge: unhandled event '{event_name}'"
                        )

        except Exception as e:
            if not self._stop_event.is_set():
                self._log.warning(f"OpenClaw Bridge: message loop error: {e}")

    def _handle_chat_event(self, payload: dict):
        state = payload.get("state", "")
        message = payload.get("message", {})
        run_id = payload.get("runId", "")

        if self._active_run_id and run_id and run_id != self._active_run_id:
            return

        text = ""
        thinking_text = ""
        if isinstance(message, dict):
            content = message.get("content", "")
            if isinstance(content, list):
                text_parts = []
                thinking_parts = []
                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get("type", "")
                        if block_type == "text":
                            text_parts.append(block.get("text", ""))
                        elif block_type == "thinking":
                            thinking_parts.append(
                                block.get("thinking", "") or block.get("text", "")
                            )
                text = "".join(text_parts)
                thinking_text = "".join(thinking_parts)
            elif isinstance(content, str):
                text = content
            else:
                text = message.get("text", "")
        elif isinstance(message, str):
            text = message

        if self.on_ai_thinking and thinking_text:
            self.on_ai_thinking(state, thinking_text)

        if self.on_ai_message and text:
            self.on_ai_message(state, text)

        if state in ("final", "aborted", "error"):
            if state == "aborted":
                text = text or "[响应已中止]"
            elif state == "error":
                error_msg = payload.get("error", {})
                if isinstance(error_msg, dict):
                    text = text or f"[错误] {error_msg.get('message', '未知错误')}"
                else:
                    text = text or f"[错误] {error_msg}"

            for fid, fut in list(self._pending.items()):
                if hasattr(fut, "_chat_session_key") and not fut.done():
                    fut.set_result(text)

    def _handle_agent_event(self, payload: dict):
        stream = payload.get("stream", "")
        data = payload.get("data", {})
        run_id = payload.get("runId", "")

        if self._active_run_id and run_id and run_id != self._active_run_id:
            return

        if not isinstance(data, dict):
            return

        text = data.get("text", "")

        if stream == "assistant" and text:
            if self.on_ai_message:
                self.on_ai_message("delta", text)
        elif stream == "thinking":
            thinking_text = data.get("thinking", "") or data.get("text", "")
            if self.on_ai_thinking and thinking_text:
                self.on_ai_thinking("delta", thinking_text)
        elif stream == "lifecycle":
            phase = data.get("phase", "")
            if phase in ("end", "error"):
                state = "error" if phase == "error" else "final"
                if self.on_ai_message:
                    self.on_ai_message(state, text or "")

    async def _rpc_request(
        self, method: str, params: dict, timeout: float = 120.0
    ) -> Any:
        if not self._ws:
            raise ConnectionError("Not connected")

        req_id = str(uuid.uuid4())
        frame = {
            "type": "req",
            "id": req_id,
            "method": method,
            "params": params,
        }

        fut = self._loop.create_future()
        self._pending[req_id] = fut

        await self._ws.send(json.dumps(frame))

        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise
        except Exception:
            self._pending.pop(req_id, None)
            raise

    async def _async_chat_send(self, message: str) -> str:
        self._cancel_event = asyncio.Event()

        if not self._session_key:
            # 用时间戳后缀确保每次新对话是不同的 session
            ts = int(time.time() * 1000)
            self._session_key = f"{self.agent_id}/{self.client_id}:{ts}"

        params = {
            "sessionKey": self._session_key,
            "message": message,
            "idempotencyKey": str(uuid.uuid4()),
        }

        try:
            result = await self._rpc_request("chat.send", params, timeout=300.0)

            if result is None:
                return ""

            if isinstance(result, dict):
                status = result.get("status", "")

                if status in ("started", "streaming", "accepted", "running"):
                    run_id = result.get("runId", "")
                    self._active_run_id = run_id
                    self._log.info(
                        f"OpenClaw chat started (runId={run_id[:8]}...), "
                        f"waiting for AI response..."
                    )
                    return await self._wait_for_final(timeout=1800.0)

                msg = result.get("message", "")
                if isinstance(msg, dict):
                    return msg.get("content", "") or msg.get("text", "")
                return str(msg) if msg else json.dumps(result)

            return str(result)

        except Exception as e:
            error_str = str(e)
            self._log.error(f"OpenClaw chat.send error: {error_str}")
            return f"[错误] {error_str}"

    async def _wait_for_final(self, timeout: float = 1800.0) -> str:
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
            cancel_evt = self._cancel_event

            async def _wait_final():
                await final_event.wait()

            async def _wait_cancel():
                if cancel_evt:
                    await cancel_evt.wait()
                else:
                    await asyncio.Event().wait()

            done, pending = await asyncio.wait(
                [
                    asyncio.ensure_future(_wait_final()),
                    asyncio.ensure_future(_wait_cancel()),
                ],
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

            if cancel_evt and cancel_evt.is_set():
                self._log.info("OpenClaw Bridge: request cancelled by user")
                if latest_text[0]:
                    return latest_text[0] + "\n\n[已取消]"
                return "[已取消] AI 请求已被用户取消"

            if final_event.is_set():
                return final_text[0]

            if latest_text[0]:
                return latest_text[0] + "\n\n[响应超时]"
            return "[错误] AI 响应超时"
        except asyncio.TimeoutError:
            if latest_text[0]:
                return latest_text[0] + "\n\n[响应超时]"
            return "[错误] AI 响应超时"
        finally:
            self.on_ai_message = original_handler
            self._active_run_id = None
