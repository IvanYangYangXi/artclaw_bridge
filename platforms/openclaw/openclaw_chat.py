"""
openclaw_chat.py — OpenClaw Gateway 通信模块（单文件重构版）
============================================================
职责:
  - 与 OpenClaw Gateway 建立 WebSocket 连接
  - 发送用户消息，接收 AI 流式回复
  - 将流式事件实时写入 stream.jsonl，最终回复写入 response.txt
  - 提供 C++ 调用的公开 API

设计原则:
  - 每次请求在独立后台线程里调用 asyncio.run()，不共享全局 loop
  - C++ 与 Python 之间只通过文件通信，不通过字符串拼接传参
  - 单一文件，不依赖 openclaw_bridge.py

文件协议 (Saved/UEAgent/):
  _openclaw_msg_input.txt          — C++ 写入消息内容，Python 读取
  _openclaw_response_stream.jsonl  — Python 实时写入流式事件
  _openclaw_response.txt           — Python 写入最终回复（出现即代表完成）

stream.jsonl 事件格式:
  {"type": "delta",       "text": "..."}
  {"type": "tool_call",   "tool_name": "...", "tool_id": "...", "arguments": {}}
  {"type": "tool_result", "tool_id": "...", "content": "...", "is_error": false}
  {"type": "final",       "text": "..."}
  {"type": "error",       "text": "[Error] ..."}
"""
# Ref: docs/UEClawBridge/features/对话框通信重构计划.md

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import uuid
from typing import Optional

try:
    import unreal  # noqa: F401
except ImportError:
    unreal = None

from init_unreal import UELogger

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

_DEFAULT_AGENT_ID   = "qi"
_DEFAULT_TOKEN      = "ec8900cf3e3c4bbfab43c8d7d5a4638c69b854e075902325"
_PROTOCOL_VERSION   = 3
_CLIENT_NAME        = "cli"
_CLIENT_VERSION     = "0.1.0"
_GATEWAY_PORT       = 18789
_CHAT_TIMEOUT       = 120.0   # 秒
_TOOL_RESULT_LIMIT  = 2000    # tool_result 内容截断字符数


def _get_gateway_config() -> dict:
    try:
        from bridge_config import _resolve_platform_config_path
        path = _resolve_platform_config_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get("gateway", {})
    except Exception:
        pass
    return {}


def _get_gateway_url() -> str:
    gw = _get_gateway_config()
    return f"ws://127.0.0.1:{gw.get('port', _GATEWAY_PORT)}"


def _get_token() -> str:
    gw = _get_gateway_config()
    return gw.get("auth", {}).get("token", _DEFAULT_TOKEN)


# ---------------------------------------------------------------------------
# 全局状态（最小化）
# ---------------------------------------------------------------------------

_session_key:         Optional[str]   = None
_context_injected:    bool            = False
_cancel_flag:         threading.Event = threading.Event()
_stream_lock:         threading.Lock  = threading.Lock()

# ---------------------------------------------------------------------------
# 文件写入工具
# ---------------------------------------------------------------------------

def _write_stream(stream_file: str, obj: dict) -> None:
    """线程安全地向 stream.jsonl 追加一行。"""
    try:
        line = json.dumps(obj, ensure_ascii=False)
        with _stream_lock:
            with open(stream_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_chat] stream write error: {exc}")


def _write_response(response_file: str, text: str) -> None:
    """写入最终回复文件（C++ 轮询到此文件即视为完成）。"""
    try:
        with open(response_file, "w", encoding="utf-8") as f:
            f.write(text)
        UELogger.info(f"[openclaw_chat] response written ({len(text)} chars)")
    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_chat] response write error: {exc}")


# ---------------------------------------------------------------------------
# UE 上下文注入
# ---------------------------------------------------------------------------

def _build_context_prefix() -> str:
    lines = ["[UE Context - 重要]"]
    try:
        import unreal as ue
        lines.append(f"Engine: Unreal Engine {ue.SystemLibrary.get_engine_version()}")
        lines.append(f"Project: {ue.SystemLibrary.get_game_name()}")
    except Exception:
        lines.append("Engine: Unreal Engine")
    lines.append("Role: UE Editor AI Assistant")
    lines.append("Constraint: 禁止调用任何其他 DCC 工具（Maya/Max 等）。只允许使用 run_ue_python 工具。")
    try:
        from memory_store import get_memory_manager
        mm = get_memory_manager()
        if mm:
            briefing = mm.export_briefing()
            if briefing:
                lines.append(briefing)
    except Exception:
        pass
    return "\n".join(lines)


def _enrich(message: str) -> str:
    global _context_injected
    if _context_injected:
        return message
    _context_injected = True
    return _build_context_prefix() + "\n\n" + message


# ---------------------------------------------------------------------------
# 文本提取工具
# ---------------------------------------------------------------------------

def _extract_text(message) -> str:
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


# ---------------------------------------------------------------------------
# 单次请求的 asyncio 协程（在独立线程里用 asyncio.run() 调用）
# ---------------------------------------------------------------------------

async def _do_chat(
    message:       str,
    stream_file:   str,
    response_file: str,
    gateway_url:   str,
    token:         str,
    agent_id:      str,
    session_key:   str,
) -> None:
    """
    完成一次完整的 Gateway 通信：连接 → 握手 → 发消息 → 收回复 → 断开。
    结果通过文件输出，不返回值。
    """
    try:
        import websockets
    except ImportError:
        _write_stream(stream_file, {"type": "error", "text": "[Error] websockets not installed"})
        _write_response(response_file, "[Error] websockets not installed")
        return

    try:
        async with websockets.connect(
            gateway_url,
            max_size=10 * 1024 * 1024,
            ping_interval=30,
            ping_timeout=10,
            open_timeout=10,
        ) as ws:
            # --- 握手 ---
            if not await _handshake(ws, token):
                _write_stream(stream_file, {"type": "error", "text": "[Error] Gateway handshake failed"})
                _write_response(response_file, "[Error] Gateway handshake failed")
                return

            # --- 发送消息 ---
            req_id = str(uuid.uuid4())
            await ws.send(json.dumps({
                "type": "req", "id": req_id, "method": "chat.send",
                "params": {
                    "sessionKey":     session_key,
                    "message":        message,
                    "idempotencyKey": str(uuid.uuid4()),
                },
            }))

            # --- 等待 chat.send 的 ACK ---
            ack = await _wait_for_ack(ws, req_id, timeout=15.0)
            if ack is None:
                _write_stream(stream_file, {"type": "error", "text": "[Error] chat.send ACK timeout"})
                _write_response(response_file, "[Error] chat.send ACK timeout")
                return

            status = ack.get("status", "")
            if status not in ("started", "streaming", "accepted", "running"):
                # 可能是同步回复（不经过流）
                msg_text = _extract_text(ack.get("message", ""))
                if msg_text:
                    _write_stream(stream_file, {"type": "final", "text": msg_text})
                    _write_response(response_file, msg_text)
                    return
                UELogger.warning(f"[openclaw_chat] unexpected chat.send status: {status}")

            run_id = ack.get("runId", "N/A")
            UELogger.info(f"[openclaw_chat] chat.send OK, runId={run_id[:8]}...")

            # --- 接收流式回复 ---
            await _receive_stream(ws, stream_file, response_file)

    except Exception as exc:
        err_msg = f"[Error] WebSocket error: {exc}"
        UELogger.mcp_error(f"[openclaw_chat] _do_chat exception: {exc}")
        _write_stream(stream_file, {"type": "error", "text": err_msg})
        _write_response(response_file, err_msg)


async def _handshake(ws, token: str) -> bool:
    """执行 OpenClaw Gateway 握手协议。"""
    try:
        # 等待 connect.challenge
        raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
        msg = json.loads(raw)
        if msg.get("event") != "connect.challenge":
            UELogger.warning(f"[openclaw_chat] expected connect.challenge, got: {msg.get('event')}")
            return False

        # 发送 connect 请求
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
                "caps":   [],
                "auth":   {"token": token},
                "role":   "operator",
                "scopes": ["operator.admin"],
            },
        }))

        # 等待 connect 响应
        deadline = time.time() + 10.0
        while time.time() < deadline:
            raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
            msg = json.loads(raw)
            if msg.get("type") == "res" and msg.get("id") == req_id:
                if msg.get("error"):
                    UELogger.mcp_error(f"[openclaw_chat] connect error: {msg['error']}")
                    return False
                return True
    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_chat] handshake exception: {exc}")
    return False


async def _wait_for_ack(ws, req_id: str, timeout: float = 15.0):
    """等待指定 req_id 的 RPC 响应，忽略中间的 chat/tick 事件。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = deadline - time.time()
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 5.0))
        except asyncio.TimeoutError:
            break
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if msg.get("type") == "res" and msg.get("id") == req_id:
            if msg.get("error"):
                UELogger.mcp_error(f"[openclaw_chat] chat.send error: {msg['error']}")
                return None
            return msg.get("payload", {})
        # 忽略 tick / 其他事件，继续等
    return None


async def _receive_stream(ws, stream_file: str, response_file: str) -> None:
    """接收 chat 流式事件，直到 final/aborted/error，写入文件。"""
    latest_text = ""
    deadline = time.time() + _CHAT_TIMEOUT

    while time.time() < deadline:
        # 检查取消
        if _cancel_flag.is_set():
            _cancel_flag.clear()
            UELogger.info("[openclaw_chat] request cancelled")
            _write_stream(stream_file, {"type": "final", "text": latest_text or "[Cancelled]"})
            _write_response(response_file, latest_text or "[Cancelled]")
            return

        remaining = deadline - time.time()
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=min(0.5, remaining))
        except asyncio.TimeoutError:
            continue
        except Exception as exc:
            err = f"[Error] Connection lost: {exc}"
            _write_stream(stream_file, {"type": "error", "text": err})
            _write_response(response_file, err)
            return

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue

        # 忽略非 chat 事件
        if msg.get("event") != "chat":
            continue

        payload = msg.get("payload", {})
        state   = payload.get("state", "")
        message = payload.get("message", {})
        text    = _extract_text(message)

        # 工具调用事件
        if isinstance(message, dict):
            content = message.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type", "")
                    if btype == "tool_use":
                        _write_stream(stream_file, {
                            "type":      "tool_call",
                            "tool_name": block.get("name", ""),
                            "tool_id":   block.get("id", ""),
                            "arguments": block.get("input", {}),
                        })
                    elif btype == "tool_result":
                        content_str = block.get("content", "")
                        if isinstance(content_str, str) and len(content_str) > _TOOL_RESULT_LIMIT:
                            content_str = content_str[:_TOOL_RESULT_LIMIT] + "...[truncated]"
                        _write_stream(stream_file, {
                            "type":     "tool_result",
                            "tool_id":  block.get("tool_use_id", ""),
                            "content":  content_str,
                            "is_error": block.get("is_error", False),
                        })

        # 文本增量
        if state == "delta" and text:
            latest_text = text
            _write_stream(stream_file, {"type": "delta", "text": text})

        # 最终状态
        elif state == "final":
            final_text = text or latest_text
            _write_stream(stream_file, {"type": "final", "text": final_text})
            _write_response(response_file, final_text)
            return

        elif state == "aborted":
            result = text or latest_text or "[Response aborted]"
            _write_stream(stream_file, {"type": "final", "text": result})
            _write_response(response_file, result)
            return

        elif state == "error":
            err_info = payload.get("error", {})
            err_text = text or (
                f"[Error] {err_info.get('message', 'Unknown')}"
                if isinstance(err_info, dict) else f"[Error] {err_info}"
            )
            _write_stream(stream_file, {"type": "error", "text": err_text})
            _write_response(response_file, err_text)
            return

    # 超时
    timeout_text = (latest_text + "\n\n[Response truncated - timeout]") if latest_text else "[Error] AI response timed out"
    _write_stream(stream_file, {"type": "error", "text": timeout_text})
    _write_response(response_file, timeout_text)


# ---------------------------------------------------------------------------
# 后台工作线程
# ---------------------------------------------------------------------------

def _chat_worker(
    message:       str,
    stream_file:   str,
    response_file: str,
) -> None:
    """在独立线程中运行 asyncio.run()，完成一次完整的聊天请求。"""
    global _session_key
    if not _session_key:
        _session_key = f"{_DEFAULT_AGENT_ID}/ue-editor:{int(time.time())}"

    gateway_url = _get_gateway_url()
    token       = _get_token()

    UELogger.info(f"[openclaw_chat] connecting to {gateway_url}, session={_session_key}")

    asyncio.run(_do_chat(
        message       = message,
        stream_file   = stream_file,
        response_file = response_file,
        gateway_url   = gateway_url,
        token         = token,
        agent_id      = _DEFAULT_AGENT_ID,
        session_key   = _session_key,
    ))


# ---------------------------------------------------------------------------
# 公开 API（供 C++ 调用）
# ---------------------------------------------------------------------------

def connect(gateway_url: str = "", token: str = "") -> bool:
    """
    测试连接是否可达（快速握手检测）。
    C++ 的 Connect 按钮调用此函数，结果写入 StatusFile。
    实际通信在 send_chat_async_to_file 时建立，不需要持久连接。
    """
    import socket
    gw = _get_gateway_config()
    port = gw.get("port", _GATEWAY_PORT)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
        UELogger.info(f"[openclaw_chat] Gateway reachable on port {port}")
        return True
    except Exception as exc:
        UELogger.warning(f"[openclaw_chat] Gateway not reachable: {exc}")
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def disconnect() -> None:
    """断开（本实现无持久连接，仅重置 session）。"""
    global _session_key, _context_injected
    _session_key      = None
    _context_injected = False
    UELogger.info("[openclaw_chat] session reset")


def is_connected() -> bool:
    return connect()


def send_chat_async_to_file(msg_file: str, response_file: str) -> None:
    """
    从 msg_file 读取消息内容，异步发送给 AI，结果写入 response_file。
    stream.jsonl 实时写入 response_file 同目录。

    调用方（C++）应:
      1. 将消息内容写入 msg_file（UTF-8）
      2. 调用此函数
      3. 轮询 response_file 是否出现（同时读 stream.jsonl 获取流式更新）
    """
    # 读取消息
    try:
        with open(msg_file, "r", encoding="utf-8") as f:
            message = f.read()
        try:
            os.remove(msg_file)
        except Exception:
            pass
    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_chat] failed to read msg_file: {exc}")
        _write_response(response_file, f"[Error] Failed to read message file: {exc}")
        return

    message = message.strip()
    if not message:
        _write_response(response_file, "[Error] Empty message")
        return

    # 清空旧 stream 文件
    stream_file = os.path.join(os.path.dirname(response_file), "_openclaw_response_stream.jsonl")
    with _stream_lock:
        try:
            if os.path.exists(stream_file):
                os.remove(stream_file)
        except Exception:
            pass

    # 注入上下文
    enriched = _enrich(message)

    # 重置取消标志
    _cancel_flag.clear()

    # 启动后台线程
    t = threading.Thread(
        target=_chat_worker,
        args=(enriched, stream_file, response_file),
        daemon=True,
        name="OCChat-Worker",
    )
    t.start()
    UELogger.info(f"[openclaw_chat] chat worker started for response_file={os.path.basename(response_file)}")


def cancel_current_request() -> None:
    """取消当前正在进行的请求。"""
    _cancel_flag.set()
    UELogger.info("[openclaw_chat] cancel flag set")


def reset_session() -> None:
    """重置会话（新对话）。"""
    global _session_key, _context_injected
    _session_key      = None
    _context_injected = False
    UELogger.info("[openclaw_chat] session reset for new chat")


def set_session_key(key: str) -> None:
    global _session_key
    _session_key = key


def get_session_key() -> str:
    return _session_key or ""


def diagnose_connection(gateway_url: str = "", token: str = "") -> str:
    """诊断连接（委托到 openclaw_diagnose.py）。"""
    try:
        import importlib
        import openclaw_diagnose
        importlib.reload(openclaw_diagnose)
        return openclaw_diagnose.diagnose_connection(gateway_url, token)
    except ImportError:
        return "[Error] openclaw_diagnose.py not found"


def shutdown() -> None:
    """关闭（重置会话状态）。"""
    disconnect()


# ---------------------------------------------------------------------------
# 兼容旧接口
# ---------------------------------------------------------------------------

def _collect_and_save_context(context_file: str) -> None:
    try:
        with open(context_file, "w", encoding="utf-8") as f:
            f.write(_build_context_prefix())
    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_chat] context file write error: {exc}")
