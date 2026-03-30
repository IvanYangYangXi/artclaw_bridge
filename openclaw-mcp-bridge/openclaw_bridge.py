"""
openclaw_bridge.py - OpenClaw Gateway WebSocket RPC 桥接
=========================================================

实现 UE Chat Panel → OpenClaw Gateway 的双向通信。

OpenClaw Gateway 使用自定义 WebSocket RPC 协议:
  1. 连接 ws://127.0.0.1:{port}
  2. 收到 event: connect.challenge + nonce
  3. 发送 req: connect (携带 auth token)
  4. 收到 helloOk 响应 (连接建立)
  5. 发送 req: chat.send (sessionKey + message)
  6. 收到流式 delta / final 事件

本模块为 C++ Dashboard 提供同步调用接口，内部使用 asyncio + websockets。
"""

from __future__ import annotations

import asyncio
import json
import os
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
# 配置
# ---------------------------------------------------------------------------

_DEFAULT_GATEWAY_URL = "ws://127.0.0.1:18789"
_DEFAULT_AGENT_ID = "qi"
_DEFAULT_TOKEN = "ec8900cf3e3c4bbfab43c8d7d5a4638c69b854e075902325"
_PROTOCOL_VERSION = 3
# Gateway 对 client.id 有严格白名单校验 (GATEWAY_CLIENT_IDS)
# 允许的值: "cli", "gateway-client", "webchat-ui", "webchat",
#           "node-host", "test", "openclaw-probe" 等
# 我们用 "cli" + mode "cli" 来模拟 CLI 客户端
_CLIENT_NAME = "cli"
_CLIENT_VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------

_bridge: Optional["OpenClawBridge"] = None


def _load_config() -> dict:
    """尝试从平台配置文件读取 gateway 配置"""
    from bridge_config import _resolve_platform_config_path
    config_path = _resolve_platform_config_path()
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class OpenClawBridge:
    """
    OpenClaw Gateway WebSocket RPC 客户端。

    在独立线程中运行 asyncio 事件循环，提供同步的 send_message() 接口。
    """

    def __init__(self, gateway_url: str = "", agent_id: str = "", token: str = ""):
        config = _load_config()
        gw_config = config.get("gateway", {})

        self.gateway_url = gateway_url or f"ws://127.0.0.1:{gw_config.get('port', 18789)}"
        self.agent_id = agent_id or _DEFAULT_AGENT_ID
        self.token = token or gw_config.get("auth", {}).get("token", _DEFAULT_TOKEN)

        self._ws = None
        self._connected = False
        self._pending: Dict[str, asyncio.Future] = {}
        self._event_handlers: Dict[str, Callable] = {}
        self._session_key: Optional[str] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 回调: 收到 AI 流式消息时
        self.on_ai_message: Optional[Callable[[str, str], None]] = None  # (state, text)

    # ------------------------------------------------------------------
    # 公开 API (同步, 供 C++ 调用)
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """启动后台连接线程"""
        if self._thread and self._thread.is_alive():
            return True

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="OpenClaw-WS")
        self._thread.start()

        # 等待连接就绪 (最多 10 秒)
        deadline = time.time() + 10.0
        while time.time() < deadline and not self._connected:
            time.sleep(0.1)

        if self._connected:
            UELogger.info(f"OpenClaw Bridge: connected to {self.gateway_url}")
        else:
            UELogger.warning("OpenClaw Bridge: connection timeout, will retry in background")

        return self._connected

    def stop(self):
        """停止连接"""
        self._stop_event.set()
        self._connected = False

        # 关闭 WebSocket 连接（触发 _message_loop 退出）
        if self._ws:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._ws.close(), self._loop
                )
            except Exception:
                pass

        # 停止 event loop
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        # 等待线程退出
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        self._ws = None
        self._loop = None
        self._thread = None
        UELogger.info("OpenClaw Bridge: stopped")

    def is_connected(self) -> bool:
        return self._connected

    def send_message(self, message: str, timeout: float = 120.0) -> str:
        """
        发送消息给 AI 并等待完整回复 (同步阻塞)。

        Args:
            message: 用户消息
            timeout: 超时秒数

        Returns:
            AI 的完整回复文本，出错时返回 "[Error] ..." 格式
        """
        if not self._connected or not self._loop:
            # 尝试重连
            self.start()
            if not self._connected:
                return "[Error] Not connected to OpenClaw Gateway. Check if openclaw is running."

        future = asyncio.run_coroutine_threadsafe(
            self._async_chat_send(message), self._loop
        )

        try:
            result = future.result(timeout=timeout)
            return result
        except asyncio.TimeoutError:
            return "[Error] AI response timed out."
        except Exception as e:
            return f"[Error] {str(e)}"

    def send_message_async(self, message: str, callback: Callable[[str], None]):
        """
        异步发送消息，完成后调用 callback (在游戏线程)。

        供 C++ 用: callback 会在主线程被调用。
        """
        def _worker():
            result = self.send_message(message)
            # 回到游戏线程
            if unreal:
                # 使用 Slate 应用下一帧调用
                _schedule_on_game_thread(lambda: callback(result))
            else:
                callback(result)

        threading.Thread(target=_worker, daemon=True, name="OCBridge-Chat").start()

    # ------------------------------------------------------------------
    # 内部: asyncio 事件循环
    # ------------------------------------------------------------------

    def _run_loop(self):
        """后台线程运行 asyncio 事件循环"""
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
        """持续尝试连接 Gateway"""
        try:
            import websockets
        except ImportError:
            UELogger.mcp_error(
                "OpenClaw Bridge: 'websockets' package not found. "
                "Install: pip install websockets"
            )
            return

        backoff = 1.0
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(
                    self.gateway_url,
                    max_size=10 * 1024 * 1024,  # 10MB
                    ping_interval=30,
                    ping_timeout=10,
                ) as ws:
                    self._ws = ws

                    # 握手
                    if await self._handshake(ws):
                        self._connected = True
                        backoff = 1.0  # 只在握手成功后才重置退避
                        UELogger.info("OpenClaw Bridge: handshake OK")
                        await self._message_loop(ws)
                    else:
                        UELogger.warning("OpenClaw Bridge: handshake failed")

            except Exception as e:
                UELogger.warning(f"OpenClaw Bridge: connection error ({e}), retry in {backoff:.0f}s")

            self._connected = False
            self._ws = None

            # 清理 pending futures
            for fid, fut in list(self._pending.items()):
                if not fut.done():
                    fut.set_exception(ConnectionError("WebSocket disconnected"))
            self._pending.clear()

            if self._stop_event.is_set():
                break

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    # ------------------------------------------------------------------
    # 内部: OpenClaw RPC 协议
    # ------------------------------------------------------------------

    async def _handshake(self, ws) -> bool:
        """
        OpenClaw Gateway 握手流程:
          1. 收到 connect.challenge event (含 nonce)
          2. 发送 connect request (含 auth token)
          3. 收到 connect response (helloOk)
        """
        try:
            # 1. 等待 challenge
            raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
            msg = json.loads(raw)

            if msg.get("event") != "connect.challenge":
                UELogger.warning(f"OpenClaw Bridge: expected challenge, got: {msg.get('event')}")
                return False

            nonce = msg.get("payload", {}).get("nonce", "")
            if not nonce:
                UELogger.warning("OpenClaw Bridge: challenge has no nonce")
                return False

            # 2. 发送 connect
            connect_params = {
                "minProtocol": _PROTOCOL_VERSION,
                "maxProtocol": _PROTOCOL_VERSION,
                "client": {
                    "id": _CLIENT_NAME,
                    "displayName": "UE Claw Bridge",
                    "version": _CLIENT_VERSION,
                    "platform": "win32",
                    "mode": "cli",
                },
                "caps": [],
                "auth": {
                    "token": self.token,
                },
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

            # 3. 等待 helloOk 响应
            deadline = time.time() + 10.0
            while time.time() < deadline:
                raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                msg = json.loads(raw)

                # 响应帧
                if msg.get("type") == "res" and msg.get("id") == connect_id:
                    if msg.get("error"):
                        UELogger.mcp_error(f"OpenClaw connect error: {msg['error']}")
                        return False
                    # 成功!
                    return True

                # 可能收到其他事件 (如 tick)
                # 继续等待

            UELogger.warning("OpenClaw Bridge: connect response timeout")
            return False

        except Exception as e:
            UELogger.mcp_error(f"OpenClaw Bridge: handshake error: {e}")
            return False

    async def _message_loop(self, ws):
        """持续接收并分发消息"""
        try:
            async for raw in ws:
                if self._stop_event.is_set():
                    break

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")

                # 响应帧 → 匹配 pending
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

                # 事件帧
                elif msg.get("event"):
                    event_name = msg["event"]
                    payload = msg.get("payload", {})

                    # chat 流式事件
                    if event_name == "chat":
                        self._handle_chat_event(payload)

                    # tick 保活
                    elif event_name == "tick":
                        pass  # 心跳，忽略

        except Exception as e:
            if not self._stop_event.is_set():
                UELogger.warning(f"OpenClaw Bridge: message loop error: {e}")

    def _handle_chat_event(self, payload: dict):
        """处理 chat 流式事件 (delta / final / aborted / error)"""
        state = payload.get("state", "")
        message = payload.get("message", {})
        session_key = payload.get("sessionKey", "")
        run_id = payload.get("runId", "")

        # 解析 message 结构 —— OpenClaw 的 message 格式为:
        # {content: [{type: "text", text: "..."}, ...], role: "assistant"}
        text = ""
        if isinstance(message, dict):
            content = message.get("content", "")
            if isinstance(content, list):
                # 标准格式: content 是数组
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                text = "".join(text_parts)
            elif isinstance(content, str):
                # 简化格式: content 是字符串
                text = content
            else:
                text = message.get("text", "")
        elif isinstance(message, str):
            text = message

        if self.on_ai_message and text:
            self.on_ai_message(state, text)

        # 处理终止状态
        if state in ("final", "aborted", "error"):
            if state == "aborted":
                text = text or "[Response aborted]"
            elif state == "error":
                error_msg = payload.get("error", {})
                if isinstance(error_msg, dict):
                    text = text or f"[Error] {error_msg.get('message', 'Unknown error')}"
                else:
                    text = text or f"[Error] {error_msg}"

            for fid, fut in list(self._pending.items()):
                if hasattr(fut, '_chat_session_key') and not fut.done():
                    fut.set_result(text)

    async def _rpc_request(self, method: str, params: dict,
                           timeout: float = 120.0) -> Any:
        """发送 RPC 请求并等待响应"""
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
        """
        发送 chat.send RPC 并等待 final 响应。

        chat.send 需要 sessionKey。
        对于 UE Editor 通道，使用 agent/ue-editor 格式。
        """
        if not self._session_key:
            # 构建 session key: {agentId}/ue-editor
            self._session_key = f"{self.agent_id}/ue-editor"

        params = {
            "sessionKey": self._session_key,
            "message": message,
            "idempotencyKey": str(uuid.uuid4()),
        }

        try:
            result = await self._rpc_request("chat.send", params, timeout=120.0)

            # chat.send 可能返回直接结果或通过事件流
            if result is None:
                return ""

            if isinstance(result, dict):
                status = result.get("status", "")

                # Gateway 对 chat.send 的响应流程:
                # 1. 立即返回 res {status: "started", runId: "..."}
                #    或 {status: "accepted"}
                # 2. 通过 event 帧发送 delta (流式文本片段)
                # 3. 最后发送 event {state: "final", message: "完整回复"}
                #
                # 所以 "started"/"accepted"/"streaming" 都不是最终结果,
                # 需要等待 final 事件
                if status in ("started", "streaming", "accepted", "running"):
                    run_id = result.get("runId", "")
                    UELogger.info(
                        f"OpenClaw chat started (runId={run_id[:8]}...), "
                        f"waiting for AI response..."
                    )
                    return await self._wait_for_final(timeout=120.0)

                # 同步返回 (某些场景下 Gateway 直接在 res 帧返回完整结果)
                msg = result.get("message", "")
                if isinstance(msg, dict):
                    return msg.get("content", "") or msg.get("text", "")
                return str(msg) if msg else json.dumps(result)

            return str(result)

        except Exception as e:
            error_str = str(e)
            UELogger.mcp_error(f"OpenClaw chat.send error: {error_str}")
            return f"[Error] {error_str}"

    async def _wait_for_final(self, timeout: float = 120.0) -> str:
        """等待 chat final 事件"""
        # 注意: OpenClaw 的 delta 事件中 message.content[0].text 是
        # **到目前为止的累积全文**，而不是增量片段。
        # 所以我们用 latest_text 保留最新一次的完整文本即可。
        latest_text = [""]

        final_event = asyncio.Event()
        final_text = [""]

        original_handler = self.on_ai_message

        def _capture(state: str, text: str):
            if state == "delta":
                # delta 的 text 是累积全文，直接覆盖
                latest_text[0] = text
            elif state in ("final", "aborted", "error"):
                if text:
                    final_text[0] = text
                else:
                    # final 事件有时不带 text，用最后一次 delta 的累积文本
                    final_text[0] = latest_text[0]
                final_event.set()

            # 也调用原始 handler
            if original_handler:
                original_handler(state, text)

        self.on_ai_message = _capture

        try:
            await asyncio.wait_for(final_event.wait(), timeout=timeout)
            return final_text[0]
        except asyncio.TimeoutError:
            if latest_text[0]:
                return latest_text[0] + "\n\n[Response truncated - timeout]"
            return "[Error] AI response timed out"
        finally:
            self.on_ai_message = original_handler


# ---------------------------------------------------------------------------
# 游戏线程调度
# ---------------------------------------------------------------------------

_pending_callbacks = []
_callback_lock = threading.Lock()


def _schedule_on_game_thread(fn: Callable):
    """将回调排入队列，等待 Tick 时执行"""
    with _callback_lock:
        _pending_callbacks.append(fn)


def _tick_flush_callbacks(dt: float):
    """在编辑器 Tick 中执行回调 (注册到 unreal.register_slate_post_tick_callback)"""
    with _callback_lock:
        callbacks = list(_pending_callbacks)
        _pending_callbacks.clear()

    for fn in callbacks:
        try:
            fn()
        except Exception as e:
            UELogger.mcp_error(f"OpenClaw callback error: {e}")


# ---------------------------------------------------------------------------
# 公开接口 (供 C++ 通过 ExecutePythonCommand 调用)
# ---------------------------------------------------------------------------

def init_bridge() -> bool:
    """初始化 OpenClaw 桥接。C++ 启动时调用。"""
    global _bridge
    if _bridge and _bridge.is_connected():
        return True

    _bridge = OpenClawBridge()

    # 注册 Tick 回调
    try:
        if unreal:
            unreal.register_slate_post_tick_callback(_tick_flush_callbacks)
    except Exception:
        pass

    return _bridge.start()


def send_chat(message: str) -> str:
    """
    同步发送消息 (C++ 调用入口)。

    C++ 侧:
        FString Result = UPythonBridge::ExecutePythonCommand(
            "from openclaw_bridge import send_chat; result = send_chat('hello')"
        );
    """
    global _bridge
    if not _bridge:
        init_bridge()
    if not _bridge:
        return "[Error] Bridge not initialized"

    return _bridge.send_message(message)


def send_chat_async(message: str, callback_name: str = ""):
    """
    异步发送消息。完成后通过 builtins 传回结果。

    Args:
        message: 用户消息
        callback_name: Python 回调函数全名 (如 'my_module.on_result')
    """
    global _bridge
    if not _bridge:
        init_bridge()

    def _on_result(result: str):
        import builtins
        builtins._openclaw_last_response = result
        builtins._openclaw_response_ready = True

    if _bridge:
        _bridge.send_message_async(message, _on_result)


def send_chat_async_to_file(message: str, output_file: str):
    """
    异步发送消息，完成后将结果写入文件。

    C++ 侧轮询该文件是否存在来获取响应。
    这是最可靠的跨语言通信方式。

    Args:
        message: 用户消息
        output_file: 响应写入的文件路径
    """
    global _bridge
    if not _bridge:
        init_bridge()

    def _on_result(result: str):
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(result)
            UELogger.info(f"OpenClaw response written to {output_file}")
        except Exception as e:
            UELogger.mcp_error(f"Failed to write response file: {e}")
            # 写入错误信息
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(f"[Error] Failed to write response: {e}")
            except Exception:
                pass

    if _bridge:
        _bridge.send_message_async(message, _on_result)
    else:
        # 直接写错误
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("[Error] OpenClaw Bridge not initialized. Is OpenClaw running?")
        except Exception:
            pass


def get_last_response() -> str:
    """C++ 轮询读取最新回复"""
    import builtins
    if getattr(builtins, '_openclaw_response_ready', False):
        builtins._openclaw_response_ready = False
        return getattr(builtins, '_openclaw_last_response', '')
    return ''


def connect(gateway_url: str = "", token: str = "") -> bool:
    """连接到 OpenClaw Gateway (connect 按钮调用)"""
    return init_bridge()


def disconnect():
    """断开 OpenClaw Gateway 连接"""
    shutdown()


def is_connected() -> bool:
    """检查连接状态"""
    return _bridge is not None and _bridge.is_connected()


# ---------------------------------------------------------------------------
# 连接诊断 (diagnose_connection)
# ---------------------------------------------------------------------------

# Gateway 允许的 client.id 白名单 (来自 openclaw/dist/message-channel-*.js)
_VALID_CLIENT_IDS = {
    "webchat-ui", "openclaw-control-ui", "webchat", "cli",
    "gateway-client", "openclaw-macos", "openclaw-ios",
    "openclaw-android", "node-host", "test", "fingerprint",
    "openclaw-probe",
}
_VALID_CLIENT_MODES = {
    "webchat", "cli", "ui", "backend", "node", "probe", "test",
}


def diagnose_connection(gateway_url: str = "", token: str = "") -> str:
    """
    诊断 OpenClaw Gateway 连接，逐项检查所有已知问题。

    在 UE Python Console 或 C++ ExecPythonCommand 中调用:
        from openclaw_bridge import diagnose_connection
        print(diagnose_connection())

    Returns:
        多行诊断报告文本
    """
    import socket
    import urllib.parse

    config = _load_config()
    gw_config = config.get("gateway", {})
    url = gateway_url or f"ws://127.0.0.1:{gw_config.get('port', 18789)}"
    tok = token or gw_config.get("auth", {}).get("token", _DEFAULT_TOKEN)

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("  OpenClaw Gateway 连接诊断")
    lines.append("=" * 60)
    errors = 0
    warnings = 0

    # ── 检查 1: websockets 包 ──
    lines.append("\n[1/6] websockets 包...")
    try:
        import websockets
        lines.append(f"  ✅ websockets {websockets.__version__} 已安装")
    except ImportError:
        lines.append("  ❌ websockets 未安装!")
        lines.append("     修复: pip install websockets")
        errors += 1

    # ── 检查 2: Gateway URL 格式 ──
    lines.append("\n[2/6] Gateway URL...")
    lines.append(f"  目标: {url}")
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 18789
    if parsed.scheme not in ("ws", "wss"):
        lines.append(f"  ❌ URL scheme 应为 ws:// 或 wss://，当前: {parsed.scheme}://")
        errors += 1
    else:
        lines.append(f"  ✅ scheme={parsed.scheme}, host={host}, port={port}")

    # ── 检查 3: TCP 端口可达 ──
    lines.append("\n[3/6] TCP 端口可达性...")
    try:
        sock = socket.create_connection((host, port), timeout=3.0)
        sock.close()
        lines.append(f"  ✅ {host}:{port} 可达")
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        lines.append(f"  ❌ {host}:{port} 不可达: {e}")
        lines.append("     可能原因: OpenClaw 未启动，或端口被占用")
        lines.append("     修复: 运行 openclaw start")
        errors += 1

    # ── 检查 4: Auth Token ──
    lines.append("\n[4/6] Auth Token...")
    if tok:
        masked = tok[:8] + "..." + tok[-4:] if len(tok) > 12 else "***"
        lines.append(f"  ✅ Token 已配置: {masked}")
        # 检查 token 来源
        file_token = gw_config.get("auth", {}).get("token", "")
        if file_token and tok == file_token:
            from bridge_config import get_platform_config_path
            lines.append(f"  ℹ️  来源: {get_platform_config_path()}")
        elif tok == _DEFAULT_TOKEN:
            lines.append("  ⚠️  来源: 硬编码默认值 (建议从平台配置文件读取)")
            warnings += 1
    else:
        lines.append("  ❌ Token 为空!")
        from bridge_config import get_platform_config_path
        lines.append(f"     修复: 检查 {get_platform_config_path()} 中的 gateway.auth.token")
        errors += 1

    # ── 检查 5: Client ID 白名单 ──
    lines.append("\n[5/6] Client ID 白名单校验...")
    lines.append(f"  client.id = \"{_CLIENT_NAME}\"")
    lines.append(f"  client.mode = \"cli\"")
    if _CLIENT_NAME in _VALID_CLIENT_IDS:
        lines.append(f"  ✅ client.id 在白名单中")
    else:
        lines.append(f"  ❌ client.id \"{_CLIENT_NAME}\" 不在白名单中!")
        lines.append(f"     允许值: {', '.join(sorted(_VALID_CLIENT_IDS))}")
        lines.append(f"     这会导致: INVALID_REQUEST 'must be equal to constant'")
        errors += 1

    # ── 检查 6: WebSocket 握手测试 ──
    lines.append("\n[6/6] WebSocket 握手测试...")
    if errors > 0:
        lines.append("  ⏭️  跳过 (前置检查有错误)")
    else:
        try:
            import asyncio
            result = asyncio.run(_diagnose_handshake(url, tok))
            for line in result:
                lines.append(f"  {line}")
        except Exception as e:
            lines.append(f"  ❌ 握手测试异常: {e}")
            errors += 1

    # ── 汇总 ──
    lines.append("\n" + "=" * 60)
    if errors == 0 and warnings == 0:
        lines.append("  🎉 所有检查通过! Gateway 连接应该正常工作。")
    elif errors == 0:
        lines.append(f"  ⚠️  通过，但有 {warnings} 个警告。")
    else:
        lines.append(f"  ❌ 发现 {errors} 个错误，{warnings} 个警告。请按上述提示修复。")
    lines.append("=" * 60)

    report = "\n".join(lines)

    # 同时输出到 UE 日志
    for line in lines:
        stripped = line.strip()
        if stripped:
            if "❌" in stripped:
                UELogger.mcp_error(f"[Diagnose] {stripped}")
            elif "⚠️" in stripped:
                UELogger.warning(f"[Diagnose] {stripped}")
            elif "✅" in stripped or "🎉" in stripped:
                UELogger.info(f"[Diagnose] {stripped}")

    return report


async def _diagnose_handshake(url: str, token: str) -> list[str]:
    """执行实际的 WebSocket 连接 + 握手测试 (独立 asyncio 运行)"""
    import websockets
    results: list[str] = []
    try:
        async with websockets.connect(url, open_timeout=5.0) as ws:
            results.append("✅ WebSocket 连接成功")

            # 等待 challenge
            raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            msg = json.loads(raw)
            if msg.get("event") == "connect.challenge":
                nonce = msg.get("payload", {}).get("nonce", "")
                results.append(f"✅ 收到 challenge (nonce={nonce[:8]}...)")
            else:
                results.append(f"⚠️  期望 connect.challenge，收到: {msg.get('event', msg.get('type', '?'))}")
                return results

            # 发送 connect
            connect_frame = {
                "type": "req",
                "id": str(uuid.uuid4()),
                "method": "connect",
                "params": {
                    "minProtocol": _PROTOCOL_VERSION,
                    "maxProtocol": _PROTOCOL_VERSION,
                    "client": {
                        "id": _CLIENT_NAME,
                        "displayName": "UE Agent Diagnose",
                        "version": _CLIENT_VERSION,
                        "platform": "win32",
                        "mode": "cli",
                    },
                    "caps": [],
                    "auth": {"token": token},
                    "role": "operator",
                    "scopes": ["operator.admin"],
                },
            }
            await ws.send(json.dumps(connect_frame))

            # 等待响应
            deadline = time.time() + 5.0
            while time.time() < deadline:
                raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                msg = json.loads(raw)
                if msg.get("type") == "res" and msg.get("id") == connect_frame["id"]:
                    if msg.get("error"):
                        err = msg["error"]
                        results.append(f"❌ 握手被拒绝: {err.get('code', '?')}: {err.get('message', '?')}")
                        # 诊断具体原因
                        err_msg = err.get("message", "")
                        if "client/id" in err_msg:
                            results.append(f"   原因: client.id \"{_CLIENT_NAME}\" 不被接受")
                            results.append(f"   修复: 检查 _CLIENT_NAME 是否在白名单中")
                        elif "auth" in err_msg.lower() or "token" in err_msg.lower():
                            results.append(f"   原因: Token 无效或过期")
                            results.append(f"   修复: 更新 token 配置")
                    else:
                        results.append("✅ 握手成功! (helloOk)")
                    return results

            results.append("⚠️  等待 connect 响应超时 (5s)")

    except asyncio.TimeoutError:
        results.append("❌ 超时: Gateway 没有响应")
    except ConnectionRefusedError:
        results.append("❌ 连接被拒绝: Gateway 可能未启动")
    except Exception as e:
        results.append(f"❌ 异常: {type(e).__name__}: {e}")

    return results


def shutdown():
    """关闭桥接"""
    global _bridge
    if _bridge:
        _bridge.stop()
        _bridge = None
