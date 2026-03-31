"""
openclaw_ws.py — OpenClaw Gateway WebSocket 通信层
===================================================
职责: 握手 / 发送 chat.send RPC / 接收流式回复 / 写文件输出。
每次请求在独立 asyncio.run() 中完成，不维护全局 loop。

文件输出协议 (Saved/UEAgent/):
  _openclaw_response_stream.jsonl  — 实时流式事件（每行一个 JSON）
  _openclaw_response.txt           — 最终回复（出现即代表完成）

stream.jsonl 事件格式:
  {"type": "delta",       "text": "..."}           ← 增量文本（仅新增 token，非累积）
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


def write_bridge_status(status_dir: str, connected: bool, mcp_ready: bool = False,
                        mcp_clients: int = 0, detail: str = "") -> None:
    """写入 _bridge_status.json，供 C++ BridgeStatusPoll 读取连接状态。"""
    try:
        import tempfile
        path = os.path.join(status_dir, "_bridge_status.json")
        data = {
            "timestamp": time.time(),
            "connected": connected,
            "mcp_ready": mcp_ready,
            "mcp_clients": mcp_clients,
            "detail": detail,
        }
        payload = json.dumps(data, ensure_ascii=False)
        # 原子写：先写临时文件再 rename，避免 C++ 读到半写文件
        fd, tmp = tempfile.mkstemp(dir=status_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise
    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_ws] write_bridge_status: {exc}")


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
            if not await _handshake(ws, token, session_key=session_key):
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

            # Gateway 可能对 sessionKey 做 namespace 包装，优先用 ACK 返回的 sessionKey；
            # 同时记录 runId 作为备用过滤维度。
            effective_session_key = ack.get("sessionKey") or session_key
            active_run_id = ack.get("runId", "")
            UELogger.info(f"[openclaw_ws] chat.send OK, "
                          f"runId={active_run_id[:8] if active_run_id else 'N/A'}..., "
                          f"effectiveSession={effective_session_key[:50] if effective_session_key else 'N/A'}")
            await _receive_stream(ws, stream_file, response_file, cancel_flag, stream_lock,
                                  session_key=effective_session_key,
                                  run_id=active_run_id)

    except Exception as exc:
        _error(stream_file, response_file, f"[Error] WebSocket: {exc}", stream_lock)
        UELogger.mcp_error(f"[openclaw_ws] do_chat exception: {exc}")


async def _handshake(ws, token: str, session_key: str = "") -> bool:
    """握手并认证。displayName 带上 session key 后缀，方便在网页端区分会话。"""
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
        msg = json.loads(raw)
        if msg.get("event") != "connect.challenge":
            return False

        # displayName: "UE Claw Bridge · ue-editor:17334..."（取 session key 末尾 16 字符）
        suffix = session_key[-16:] if session_key else ""
        display_name = f"UE Claw Bridge · {suffix}" if suffix else "UE Claw Bridge"

        req_id = str(uuid.uuid4())
        await ws.send(json.dumps({
            "type": "req", "id": req_id, "method": "connect",
            "params": {
                "minProtocol": _PROTOCOL_VERSION,
                "maxProtocol": _PROTOCOL_VERSION,
                "client": {
                    "id": _CLIENT_NAME, "displayName": display_name,
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
                          session_key: str = "", run_id: str = "") -> None:
    """接收 chat 流式事件，直到 final/aborted/error。

    过滤策略（双重保险）:
    1. sessionKey 匹配：事件 sessionKey 包含本地 key，或等于 ACK 返回的 effective key
    2. runId 匹配：如果 ACK 返回了 runId，只接受同 runId 的事件（更精确）
    只响应 delta/final/aborted/error 四种 state，忽略其他状态（如 monitoring）。
    """
    latest_text = ""
    seen_tool_ids: set = set()  # 追踪已写过系统消息的 tool id，避免重复
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

        # --- 过滤其他 session / run 的广播事件 ---
        # 优先用 runId 过滤（最精确）；fallback 到 sessionKey 包含匹配。
        # Gateway 可能对 sessionKey 做 namespace 包装（如 "agent:qi:qi/ue-editor:xxx"），
        # 所以不用精确匹配，而是检查本地 key 是否包含在事件 key 中（或反之）。
        event_run_id = payload.get("runId", "")
        event_session = payload.get("sessionKey", "")

        if run_id and event_run_id:
            # runId 过滤：精确匹配
            if event_run_id != run_id:
                UELogger.info(f"[openclaw_ws] skip event runId={event_run_id[:12]} (want {run_id[:12]})")
                continue
        elif session_key and event_session:
            # sessionKey 过滤：包含匹配（兼容 Gateway namespace 包装）
            match = (
                event_session == session_key
                or session_key in event_session
                or event_session in session_key
            )
            if not match:
                UELogger.info(f"[openclaw_ws] skip event from other session: {event_session[:60]}")
                continue

        state   = payload.get("state", "")
        message = payload.get("message", {})
        text    = _extract_text(message)

        # --- 只处理已知 state，忽略 monitoring 等非对话状态 ---
        if state not in ("delta", "final", "aborted", "error"):
            UELogger.info(f"[openclaw_ws] skip non-chat state: {state}")
            continue

        _dispatch_tool_events(message, stream_file, stream_lock, seen_tool_ids)

        if state == "delta" and text:
            # Gateway 推送的 delta text 是累积全文，需要提取增量部分写入 stream
            # C++ 端使用 += 追加，所以必须只写新增 token
            incremental = text[len(latest_text):] if text.startswith(latest_text) else text
            latest_text = text
            if incremental:
                write_stream(stream_file, {"type": "delta", "text": incremental}, stream_lock)

        elif state == "final":
            final_text = text or latest_text
            # 提取 usage 信息（Gateway 在 final 事件中携带 token 统计）
            _dispatch_usage(payload, message, stream_file, stream_lock)
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


def _dispatch_usage(payload: dict, message: dict, stream_file: str, stream_lock) -> None:
    """从 final 事件中提取 token usage 并写入 stream.jsonl。

    Gateway 的 usage 位置不确定（payload.usage / message.usage / payload.message.usage），
    逐层查找，取第一个有效的。
    """
    usage = None
    for source in (payload, message):
        if isinstance(source, dict) and isinstance(source.get("usage"), dict):
            usage = source["usage"]
            break
    if not usage:
        return

    # 统一字段名: Gateway 可能用 camelCase 或 snake_case
    total = (
        usage.get("totalTokens")
        or usage.get("total_tokens")
        or 0
    )
    if not total:
        # 尝试 input + output 合计
        inp = usage.get("inputTokens") or usage.get("input_tokens") or 0
        out = usage.get("outputTokens") or usage.get("output_tokens") or 0
        total = inp + out

    if total > 0:
        write_stream(stream_file, {
            "type": "usage",
            "usage": {
                "totalTokens": total,
                "inputTokens": usage.get("inputTokens") or usage.get("input_tokens") or 0,
                "outputTokens": usage.get("outputTokens") or usage.get("output_tokens") or 0,
            },
        }, stream_lock)


def _dispatch_tool_events(message: dict, stream_file: str, stream_lock,
                          seen_tool_ids: set | None = None) -> None:
    """解析 message content blocks，写入 tool 事件 + 系统消息文本。

    双轨输出:
    1. tool_call / tool_result 事件 — 供 C++ 特殊消息类型解析（保留兼容）
    2. tool_use 文本（delta 类型）— 作为可靠 fallback，直接显示在消息流中

    Gateway 推送的 block 字段为驼峰格式（OpenClaw 协议）：
      toolCall:   type="toolCall",  id, name, arguments (dict/str)
      toolResult: type="toolResult", toolCallId, toolName, content, isError
    """
    if seen_tool_ids is None:
        seen_tool_ids = set()
    if not isinstance(message, dict):
        return
    content = message.get("content", [])
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type", "")

        if btype == "toolCall":
            tool_id = block.get("id", "")
            tool_name = block.get("name", "")
            tool_args = block.get("arguments", {})
            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except (json.JSONDecodeError, ValueError):
                    tool_args = {"raw": tool_args}

            # 写原有 tool_call 事件（C++ 兼容）
            write_stream(stream_file, {
                "type":      "tool_call",
                "tool_name": tool_name,
                "tool_id":   tool_id,
                "arguments": tool_args,
            }, stream_lock)

            # 写系统消息文本（可靠 fallback），只写一次
            text_key = f"call:{tool_id}"
            if text_key not in seen_tool_ids:
                seen_tool_ids.add(text_key)
                # 格式化参数摘要（截断，避免刷屏）
                args_summary = ""
                if tool_args:
                    args_str = json.dumps(tool_args, ensure_ascii=False)
                    if len(args_str) > 200:
                        args_str = args_str[:200] + "..."
                    args_summary = f"\n  Args: {args_str}"
                write_stream(stream_file, {
                    "type": "tool_use_text",
                    "text": f"\n[Tool] {tool_name}{args_summary}\n",
                }, stream_lock)

        elif btype == "toolResult":
            tool_id = block.get("toolCallId", "")
            tool_name = block.get("toolName", "")
            is_error = block.get("isError", False)
            result_content = block.get("content", "")
            if isinstance(result_content, list):
                result_content = "\n".join(
                    item.get("text", "")
                    for item in result_content
                    if isinstance(item, dict)
                )
            elif not isinstance(result_content, str):
                result_content = str(result_content)
            if len(result_content) > _TOOL_RESULT_LIMIT:
                result_content = result_content[:_TOOL_RESULT_LIMIT] + "...[truncated]"

            # 写原有 tool_result 事件（C++ 兼容）
            write_stream(stream_file, {
                "type":      "tool_result",
                "tool_name": tool_name,
                "tool_id":   tool_id,
                "content":   result_content,
                "is_error":  is_error,
            }, stream_lock)

            # 写系统消息文本（可靠 fallback），只写一次
            text_key = f"result:{tool_id}"
            if text_key not in seen_tool_ids:
                seen_tool_ids.add(text_key)
                status = "[Error]" if is_error else "[Done]"
                # 结果摘要截断
                result_preview = result_content[:150]
                if len(result_content) > 150:
                    result_preview += "..."
                write_stream(stream_file, {
                    "type": "tool_use_text",
                    "text": f"[Tool] {tool_name} {status}\n",
                }, stream_lock)


def _error(stream_file: str, response_file: str, msg: str, stream_lock) -> None:
    write_stream(stream_file, {"type": "error", "text": msg}, stream_lock)
    write_response(response_file, msg)
