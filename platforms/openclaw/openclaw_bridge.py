"""
openclaw_bridge.py — OpenClaw Gateway WebSocket RPC 核心连接层
==============================================================
职责:
  - Gateway 握手 / 消息循环 / RPC 请求
  - chat 事件解析与分发（on_ai_message / on_tool_event 回调）

公开 API 见 openclaw_chat.py。

线程模型:
  - asyncio 事件循环运行在独立后台线程 (OpenClaw-WS)
  - 所有 asyncio 操作通过 run_coroutine_threadsafe 跨线程调度
  - _wait_for_final 使用 threading.Event（非 asyncio.Event）以保证跨线程安全
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
    import unreal  # noqa: F401
except ImportError:
    unreal = None

from init_unreal import UELogger

# ---------------------------------------------------------------------------
# 配置常量
# ---------------------------------------------------------------------------

_DEFAULT_AGENT_ID    = "qi"
_DEFAULT_TOKEN       = "ec8900cf3e3c4bbfab43c8d7d5a4638c69b854e075902325"
_PROTOCOL_VERSION    = 3
_CLIENT_NAME         = "cli"
_CLIENT_VERSION      = "0.1.0"
_CONNECT_TIMEOUT     = 10.0   # 秒：start() 等待握手的最长时间
_CHAT_TIMEOUT        = 120.0  # 秒：等待 AI 最终回复的超时
_CANCEL_POLL_INTERVAL = 0.1   # 秒：_wait_for_final 轮询间隔


def _load_gateway_config() -> dict:
    """从 ~/.artclaw/config.json 读取 gateway 配置。"""
    try:
        from bridge_config import _resolve_platform_config_path
        import os
        path = _resolve_platform_config_path()
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("gateway", {})
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# OpenClawBridge
# ---------------------------------------------------------------------------

class OpenClawBridge:
    """
    OpenClaw Gateway WebSocket RPC 客户端。

    在独立后台线程中运行 asyncio 事件循环，对外提供同步/异步发送接口。
    所有内部状态需通过锁或线程安全机制访问。
    """

    def __init__(
        self,
        gateway_url: str = "",
        agent_id:    str = "",
        token:       str = "",
    ) -> None:
        gw = _load_gateway_config()
        self.gateway_url = gateway_url or f"ws://127.0.0.1:{gw.get('port', 18789)}"
        self.agent_id    = agent_id or _DEFAULT_AGENT_ID
        self.token       = token   or gw.get("auth", {}).get("token", _DEFAULT_TOKEN)

        # asyncio 基础设施
        self._loop:   Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread]          = None
        self._ws                                          = None

        # 状态标志
        self._connected    = False
        self._stop_event   = threading.Event()
        self._cancel_event = threading.Event()

        # 当前会话
        self._session_key: Optional[str] = None

        # 待回复的 RPC Future（req_id → asyncio.Future）
        self._pending: Dict[str, asyncio.Future] = {}

        # 回调（由 openclaw_chat.py 设置）
        # on_ai_message(state: str, text: str)   — delta/final/aborted/error
        # on_tool_event(event_type: str, data: dict) — tool_call/tool_result
        self.on_ai_message: Optional[Callable[[str, str], None]] = None
        self.on_tool_event: Optional[Callable[[str, dict], None]] = None

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """启动后台连接线程，等待握手完成（最多 _CONNECT_TIMEOUT 秒）。"""
        if self._thread and self._thread.is_alive():
            return self._connected

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="OpenClaw-WS"
        )
        self._thread.start()

        deadline = time.time() + _CONNECT_TIMEOUT
        while time.time() < deadline and not self._connected:
            time.sleep(0.05)

        if self._connected:
            UELogger.info(f"OpenClaw Bridge: connected to {self.gateway_url}")
        else:
            UELogger.warning("OpenClaw Bridge: connection timeout, retrying in background")
        return self._connected

    def stop(self) -> None:
        """关闭连接并停止后台线程。"""
        self._stop_event.set()
        self._connected = False

        if self._ws and self._loop and self._loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)
            except Exception:
                pass

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        self._ws     = None
        self._loop   = None
        self._thread = None
        UELogger.info("OpenClaw Bridge: stopped")

    def cancel(self) -> None:
        """取消当前正在等待的 AI 请求。"""
        self._cancel_event.set()
        UELogger.info("OpenClaw Bridge: cancel requested")

    # ------------------------------------------------------------------
    # 连接状态
    # ------------------------------------------------------------------

    def is_connected(self) -> bool:
        return self._connected

    def reset_session(self) -> None:
        self._session_key = None

    def get_session_key(self) -> str:
        return self._session_key or ""

    def set_session_key(self, key: str) -> None:
        self._session_key = key

    # ------------------------------------------------------------------
    # 发送接口（公开，供 openclaw_chat.py 调用）
    # ------------------------------------------------------------------

    def send_message(self, message: str, timeout: float = _CHAT_TIMEOUT) -> str:
        """
        同步发送消息并等待完整回复。
        调试/测试用；正式流程请用 send_message_async。
        """
        if not self._ensure_connected():
            return "[Error] Not connected to OpenClaw Gateway. Is openclaw running?"

        future = asyncio.run_coroutine_threadsafe(
            self._async_chat_send(message), self._loop  # type: ignore[arg-type]
        )
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            return "[Error] AI response timed out."
        except Exception as exc:
            return f"[Error] {exc}"

    def send_message_async(
        self, message: str, callback: Callable[[str], None]
    ) -> None:
        """
        异步发送消息，完成后在工作线程调用 callback(result: str)。
        """
        def _worker() -> None:
            result = self.send_message(message)
            try:
                callback(result)
            except Exception as exc:
                UELogger.mcp_error(f"send_message_async callback error: {exc}")

        threading.Thread(target=_worker, daemon=True, name="OCBridge-Chat").start()

    # ------------------------------------------------------------------
    # 内部：确保连接就绪
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> bool:
        if not self._connected or not self._loop:
            self.start()
        return self._connected and self._loop is not None

    # ------------------------------------------------------------------
    # asyncio 事件循环（后台线程）
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_loop())
        except Exception as exc:
            UELogger.mcp_error(f"OpenClaw Bridge loop error: {exc}")
        finally:
            self._loop.close()
            self._loop = None

    async def _connect_loop(self) -> None:
        try:
            import websockets
        except ImportError:
            UELogger.mcp_error(
                "OpenClaw Bridge: 'websockets' not found. Run: pip install websockets"
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
                        self._connected = True
                        backoff = 1.0
                        UELogger.info("OpenClaw Bridge: handshake OK")
                        await self._message_loop(ws)
                    else:
                        UELogger.warning("OpenClaw Bridge: handshake failed")
            except Exception as exc:
                UELogger.warning(
                    f"OpenClaw Bridge: connection error ({exc}), retry in {backoff:.0f}s"
                )

            self._connected = False
            self._ws = None

            # 通知所有等待中的 RPC 请求连接已断开
            for fut in list(self._pending.values()):
                if not fut.done():
                    fut.set_exception(ConnectionError("WebSocket disconnected"))
            self._pending.clear()

            if self._stop_event.is_set():
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    # ------------------------------------------------------------------
    # 握手
    # ------------------------------------------------------------------

    async def _handshake(self, ws) -> bool:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
            msg = json.loads(raw)
            if msg.get("event") != "connect.challenge":
                UELogger.warning(f"OpenClaw Bridge: unexpected first message: {msg.get('event')}")
                return False
            nonce = msg.get("payload", {}).get("nonce", "")
            if not nonce:
                return False

            req_id = str(uuid.uuid4())
            await ws.send(json.dumps({
                "type": "req", "id": req_id, "method": "connect",
                "params": {
                    "minProtocol": _PROTOCOL_VERSION,
                    "maxProtocol": _PROTOCOL_VERSION,
                    "client": {
                        "id":          _CLIENT_NAME,
                        "displayName": "UE Claw Bridge",
                        "version":     _CLIENT_VERSION,
                        "platform":    "win32",
                        "mode":        "cli",
                    },
                    "caps": [],
                    "auth":  {"token": self.token},
                    "role":  "operator",
                    "scopes": ["operator.admin"],
                },
            }))

            deadline = time.time() + 10.0
            while time.time() < deadline:
                raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                msg = json.loads(raw)
                if msg.get("type") == "res" and msg.get("id") == req_id:
                    if msg.get("error"):
                        UELogger.mcp_error(f"OpenClaw connect error: {msg['error']}")
                        return False
                    return True
        except Exception as exc:
            UELogger.mcp_error(f"OpenClaw Bridge: handshake exception: {exc}")
        return False

    # ------------------------------------------------------------------
    # 消息循环
    # ------------------------------------------------------------------

    async def _message_loop(self, ws) -> None:
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
                    self._dispatch_rpc_response(msg)
                elif msg.get("event") == "chat":
                    self._handle_chat_event(msg.get("payload", {}))
                # tick / 其他事件静默忽略
        except Exception as exc:
            if not self._stop_event.is_set():
                UELogger.warning(f"OpenClaw Bridge: message loop error: {exc}")

    def _dispatch_rpc_response(self, msg: dict) -> None:
        req_id = msg.get("id")
        fut = self._pending.pop(req_id, None)
        if fut is None or fut.done():
            return
        if msg.get("error"):
            fut.set_exception(RuntimeError(json.dumps(msg["error"])))
        else:
            fut.set_result(msg.get("payload"))

    def _handle_chat_event(self, payload: dict) -> None:
        """
        解析 chat 事件 payload，分发 on_ai_message / on_tool_event 回调。

        Gateway chat 事件 state 字段可能的值:
          - "delta"   : 流式增量文本
          - "final"   : 最终完整回复
          - "aborted" : 被中断
          - "error"   : 出错
        """
        state       = payload.get("state", "")
        message     = payload.get("message", {})
        session_key = payload.get("sessionKey", "")

        # 过滤其他 session 的事件
        if self._session_key and session_key and session_key != self._session_key:
            return

        # 工具调用事件（嵌在 content blocks 中）
        if isinstance(message, dict):
            content = message.get("content", [])
            if isinstance(content, list) and self.on_tool_event:
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type", "")
                    if btype == "tool_use":
                        self.on_tool_event("tool_call", {
                            "tool_name": block.get("name", ""),
                            "tool_id":   block.get("id", ""),
                            "arguments": block.get("input", {}),
                        })
                    elif btype == "tool_result":
                        self.on_tool_event("tool_result", {
                            "tool_id":  block.get("tool_use_id", ""),
                            "content":  block.get("content", ""),
                            "is_error": block.get("is_error", False),
                        })

        # 文本内容
        text = _extract_text(message)

        if self.on_ai_message and (text or state in ("final", "aborted", "error")):
            # error state：构建错误文本
            if state == "error" and not text:
                err = payload.get("error", {})
                text = (
                    f"[Error] {err.get('message', 'Unknown')}"
                    if isinstance(err, dict)
                    else f"[Error] {err}"
                )
            elif state == "aborted" and not text:
                text = "[Response aborted]"
            self.on_ai_message(state, text)

        # 通知 _wait_for_final（通过写 _chat_final_event）
        if state in ("final", "aborted", "error"):
            self._notify_final(text)

    # ------------------------------------------------------------------
    # RPC 工具
    # ------------------------------------------------------------------

    async def _rpc_request(
        self, method: str, params: dict, timeout: float = _CHAT_TIMEOUT
    ) -> Any:
        if not self._ws:
            raise ConnectionError("Not connected")
        req_id = str(uuid.uuid4())
        fut = self._loop.create_future()  # type: ignore[union-attr]
        self._pending[req_id] = fut
        await self._ws.send(
            json.dumps({"type": "req", "id": req_id, "method": method, "params": params})
        )
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except (asyncio.TimeoutError, TimeoutError):
            self._pending.pop(req_id, None)
            raise
        except Exception:
            self._pending.pop(req_id, None)
            raise

    # ------------------------------------------------------------------
    # 聊天发送 + 等待回复
    # ------------------------------------------------------------------

    # 用于跨线程通知 _wait_for_final 的共享状态
    # 每次新请求开始时重置
    _chat_final_lock  = threading.Lock()
    _chat_final_event = threading.Event()
    _chat_final_text  = [""]

    def _notify_final(self, text: str) -> None:
        """在 asyncio 线程中调用，向 _wait_for_final（主线程）发送信号。"""
        with self._chat_final_lock:
            self._chat_final_text[0] = text
            self._chat_final_event.set()

    def _reset_final_state(self) -> None:
        """新请求开始前重置最终回复状态。"""
        with self._chat_final_lock:
            self._chat_final_text[0] = ""
            self._chat_final_event.clear()

    async def _async_chat_send(self, message: str) -> str:
        if not self._session_key:
            self._session_key = f"{self.agent_id}/ue-editor"

        # 重置 cancel 和 final 状态
        self._cancel_event.clear()
        self._reset_final_state()

        params = {
            "sessionKey":     self._session_key,
            "message":        message,
            "idempotencyKey": str(uuid.uuid4()),
        }
        result = await self._rpc_request("chat.send", params, timeout=_CHAT_TIMEOUT)

        if isinstance(result, dict):
            status = result.get("status", "")
            if status in ("started", "streaming", "accepted", "running"):
                run_id = result.get("runId", "")
                UELogger.info(f"OpenClaw chat.send OK (runId={run_id[:8] if run_id else 'N/A'}...)")
                return await self._wait_for_final(timeout=_CHAT_TIMEOUT)
            # 同步回复（不经过流）
            msg = result.get("message", "")
            if isinstance(msg, dict):
                return msg.get("content", "") or msg.get("text", "")
            return str(msg) if msg else json.dumps(result)
        return str(result) if result else ""

    async def _wait_for_final(self, timeout: float = _CHAT_TIMEOUT) -> str:
        """
        等待 chat final/aborted/error 事件。

        使用 threading.Event（非 asyncio.Event）以保证跨线程安全：
        _handle_chat_event 在 asyncio 协程中调用 _notify_final，
        通过 threading.Event.set() 通知本协程（在后台线程的 event loop 中运行）。

        轮询间隔 _CANCEL_POLL_INTERVAL 秒，定期检查 cancel_event。
        """
        deadline = time.monotonic() + timeout

        while True:
            # 检查取消
            if self._cancel_event.is_set():
                self._cancel_event.clear()
                UELogger.info("OpenClaw Bridge: request cancelled")
                return "[Cancelled]"

            # 非阻塞检查 final 信号（避免阻塞 asyncio loop）
            if self._chat_final_event.is_set():
                with self._chat_final_lock:
                    return self._chat_final_text[0]

            # 超时检查
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return "[Error] AI response timed out"

            # 让出 asyncio 控制权，等待下一次轮询
            await asyncio.sleep(min(_CANCEL_POLL_INTERVAL, remaining))


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _extract_text(message: Any) -> str:
    """从 OpenClaw message 结构中提取文本内容。"""
    if isinstance(message, dict):
        content = message.get("content", "")
        if isinstance(content, list):
            return "".join(
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        if isinstance(content, str):
            return content
        return message.get("text", "")
    if isinstance(message, str):
        return message
    return ""
