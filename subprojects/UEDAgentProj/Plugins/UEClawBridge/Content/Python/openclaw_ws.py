"""
openclaw_ws.py — OpenClaw Gateway WebSocket 通信层
===================================================
职责: 握手 / 发送 chat.send RPC / 接收流式回复 / 写文件输出。
每次请求在独立 asyncio.run() 中完成，不维护全局 loop。

文件输出协议 (Saved/UEAgent/):
  _openclaw_response_stream.jsonl  — 实时流式事件（每行一个 JSON）
  _openclaw_response.txt           — 最终回复（出现即代表完成）

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
import time
import uuid
from typing import Optional

from init_unreal import UELogger

# ---------------------------------------------------------------------------
# 配置常量
# ---------------------------------------------------------------------------

_PROTOCOL_VERSION  = 3
_CLIENT_NAME       = "cli"
_CLIENT_VERSION    = "0.1.0"
_CHAT_TIMEOUT      = 120.0   # 秒
_TOOL_RESULT_LIMIT = 2000    # tool_result 内容截断字符数


# ---------------------------------------------------------------------------
# 文件写入（由调用方传入 stream_lock）
# ---------------------------------------------------------------------------

def write_stream(stream_file: str, obj: dict, lock) -> None:
    """线程安全地向 stream.jsonl 追加一行。"""
    try:
        line = json.dumps(obj, ensure_ascii=False)
        with lock:
            with open(stream_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_ws] stream write: {exc}")


def write_response(response_file: str, text: str) -> None:
    """写入最终回复文件（C++ 轮询到此文件即视为完成）。"""
    try:
        with open(response_file, "w", encoding="utf-8") as f:
            f.write(text)
        UELogger.info(f"[openclaw_ws] response written ({len(text)} chars)")
    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_ws] response write: {exc}")


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
# asyncio 协程：单次完整请求
# ---------------------------------------------------------------------------

async def do_chat(
    message:       str,
    stream_file:   str,
    response_file: str,
    gateway_url:   str,
    token:         str,
    session_key:   str,
    cancel_flag,   # threading.Event
    stream_lock,   # threading.Lock
) -> None:
    """完成一次完整的 Gateway 通信：连接→握手→发消息→收回复→断开。"""
    try:
        import websockets
    except ImportError:
        _error(stream_file, response_file, "[Error] websockets not installed", stream_lock)
        return

    try:
        async with websockets.connect(
            gateway_url,
            max_size=10 * 1024 * 1024,
            ping_interval=30,
            ping_timeout=10,
            open_timeout=10,
        ) as ws:
            if not await _handshake(ws, token):
                _error(stream_file, response_file, "[Error] Gateway handshake failed", stream_lock)
                return

            req_id = str(uuid.uuid4())
            await ws.send(json.dumps({
                "type": "req", "id": req_id, "method": "chat.send",
                "params": {
                    "sessionKey":     session_key,
                    "message":        message,
                    "idempotencyKey": str(uuid.uuid4()),
                },
            }))

            ack = await _wait_for_ack(ws, req_id, timeout=15.0)
            if ack is None:
                _error(stream_file, response_file, "[Error] chat.send ACK timeout", stream_lock)
                return

            status = ack.get("status", "")
            if status not in ("started", "streaming", "accepted", "running"):
                # 同步回复（不经过流）
                msg_text = _extract_text(ack.get("message", ""))
                if msg_text:
                    write_stream(stream_file, {"type": "final", "text": msg_text}, stream_lock)
                    write_response(response_file, msg_text)
                    return
                UELogger.warning(f"[openclaw_ws] unexpected status: {status}")

            UELogger.info(f"[openclaw_ws] chat.send OK, runId={ack.get('runId', 'N/A')[:8]}...")
            await _receive_stream(ws, stream_file, response_file, cancel_flag, stream_lock,
                                  session_key=session_key)

    except Exception as exc:
        _error(stream_file, response_file, f"[Error] WebSocket: {exc}", stream_lock)
        UELogger.mcp_error(f"[openclaw_ws] do_chat exception: {exc}")


async def _handshake(ws, token: str) -> bool:
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
        msg = json.loads(raw)
        if msg.get("event") != "connect.challenge":
            return False

        req_id = str(uuid.uuid4())
        await ws.send(json.dumps({
            "type": "req", "id": req_id, "method": "connect",
            "params": {
                "minProtocol": _PROTOCOL_VERSION,
                "maxProtocol": _PROTOCOL_VERSION,
                "client": {
                    "id": _CLIENT_NAME, "displayName": "UE Claw Bridge",
                    "version": _CLIENT_VERSION, "platform": "win32", "mode": "cli",
                },
                "caps": [], "auth": {"token": token},
                "role": "operator", "scopes": ["operator.admin"],
            },
        }))

        deadline = time.time() + 10.0
        while time.time() < deadline:
            raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
            msg = json.loads(raw)
            if msg.get("type") == "res" and msg.get("id") == req_id:
                if msg.get("error"):
                    UELogger.mcp_error(f"[openclaw_ws] connect error: {msg['error']}")
                    return False
                return True
    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_ws] handshake: {exc}")
    return False


async def _wait_for_ack(ws, req_id: str, timeout: float = 15.0) -> Optional[dict]:
    """等待指定 req_id 的 RPC 响应，忽略中间的 chat/tick 事件。"""
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
                UELogger.mcp_error(f"[openclaw_ws] chat.send error: {msg['error']}")
                return None
            return msg.get("payload", {})
    return None


async def _receive_stream(ws, stream_file, response_file, cancel_flag, stream_lock,
                          session_key: str = "") -> None:
    """接收 chat 流式事件，直到 final/aborted/error。
    
    只处理与 session_key 匹配的 chat 事件，过滤其他 session 的广播消息。
    只响应 delta/final/aborted/error 四种 state，忽略其他状态（如 monitoring）。
    """
    latest_text = ""
    deadline = time.time() + _CHAT_TIMEOUT

    while time.time() < deadline:
        if cancel_flag.is_set():
            cancel_flag.clear()
            result = latest_text or "[Cancelled]"
            write_stream(stream_file, {"type": "final", "text": result}, stream_lock)
            write_response(response_file, result)
            return

        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        except Exception as exc:
            _error(stream_file, response_file, f"[Error] Connection lost: {exc}", stream_lock)
            return

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if msg.get("event") != "chat":
            continue

        payload = msg.get("payload", {})

        # --- Bug Fix: 过滤其他 session 的广播事件 ---
        # Gateway 会向所有连接推送 chat 事件，必须按 sessionKey 过滤
        event_session = payload.get("sessionKey", "")
        if session_key and event_session and event_session != session_key:
            UELogger.info(f"[openclaw_ws] skip event from other session: {event_session[:30]}")
            continue

        state   = payload.get("state", "")
        message = payload.get("message", {})
        text    = _extract_text(message)

        # --- Bug Fix: 只处理已知 state，忽略 monitoring 等非对话状态 ---
        if state not in ("delta", "final", "aborted", "error"):
            UELogger.info(f"[openclaw_ws] skip non-chat state: {state}")
            continue

        _dispatch_tool_events(message, stream_file, stream_lock)

        if state == "delta" and text:
            latest_text = text
            write_stream(stream_file, {"type": "delta", "text": text}, stream_lock)

        elif state == "final":
            final_text = text or latest_text
            write_stream(stream_file, {"type": "final", "text": final_text}, stream_lock)
            write_response(response_file, final_text)
            return

        elif state in ("aborted", "error"):
            if state == "error":
                err = payload.get("error", {})
                text = text or (f"[Error] {err.get('message', 'Unknown')}" if isinstance(err, dict) else f"[Error] {err}")
            result = text or latest_text or (f"[Response {state}]")
            write_stream(stream_file, {"type": "final" if state == "aborted" else "error", "text": result}, stream_lock)
            write_response(response_file, result)
            return

    timeout_text = (latest_text + "\n\n[Response truncated - timeout]") if latest_text else "[Error] AI response timed out"
    write_stream(stream_file, {"type": "error", "text": timeout_text}, stream_lock)
    write_response(response_file, timeout_text)


def _dispatch_tool_events(message: dict, stream_file: str, stream_lock) -> None:
    """解析 message content blocks，写入 tool_call / tool_result 事件。"""
    if not isinstance(message, dict):
        return
    content = message.get("content", [])
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type", "")
        if btype == "tool_use":
            write_stream(stream_file, {
                "type": "tool_call",
                "tool_name": block.get("name", ""),
                "tool_id":   block.get("id", ""),
                "arguments": block.get("input", {}),
            }, stream_lock)
        elif btype == "tool_result":
            content_str = block.get("content", "")
            if isinstance(content_str, str) and len(content_str) > _TOOL_RESULT_LIMIT:
                content_str = content_str[:_TOOL_RESULT_LIMIT] + "...[truncated]"
            write_stream(stream_file, {
                "type":     "tool_result",
                "tool_id":  block.get("tool_use_id", ""),
                "content":  content_str,
                "is_error": block.get("is_error", False),
            }, stream_lock)


def _error(stream_file: str, response_file: str, msg: str, stream_lock) -> None:
    write_stream(stream_file, {"type": "error", "text": msg}, stream_lock)
    write_response(response_file, msg)
