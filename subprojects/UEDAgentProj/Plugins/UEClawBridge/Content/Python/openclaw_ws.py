"""
openclaw_ws.py — OpenClaw Gateway WebSocket 通信层
===================================================
职责: 握手 / 发送 chat.send RPC / 接收流式回复 / 写文件输出。
每次请求在独立 asyncio.run() 中完成，不维护全局 loop。

文件输出协议 (Saved/ClawBridge/):
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

try:
    from claw_bridge_logger import UELogger
except ImportError:
    from init_unreal import UELogger

# ---------------------------------------------------------------------------
# 配置常量
# ---------------------------------------------------------------------------

_PROTOCOL_VERSION  = 3
_CLIENT_NAME       = "cli"
_CLIENT_VERSION    = "0.1.0"
_CHAT_TIMEOUT      = 1800.0  # 绝对超时 30 分钟
_IDLE_TIMEOUT      = 300.0   # 无活动超时 5 分钟: 收到事件后重置
_TOOL_RESULT_LIMIT = 2000    # tool_result 内容截断字符数


def _truncate_for_debug(obj, max_str_len=200):
    """递归截断 JSON 对象中的长字符串，用于 debug dump。"""
    if isinstance(obj, str):
        return obj[:max_str_len] + "..." if len(obj) > max_str_len else obj
    if isinstance(obj, dict):
        return {k: _truncate_for_debug(v, max_str_len) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_truncate_for_debug(item, max_str_len) for item in obj[:20]]  # 最多 20 项
    return obj


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
        os.makedirs(status_dir, exist_ok=True)
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
                UELogger.info(f"[openclaw_ws] sync response: status={status!r}, "
                              f"text_len={len(msg_text)}, keys={list(ack.keys())}")
                if msg_text:
                    write_stream(stream_file, {"type": "final", "text": msg_text}, stream_lock)
                    write_response(response_file, msg_text)
                    return
                UELogger.warning(f"[openclaw_ws] unexpected status: {status}")

            # Gateway 可能对 sessionKey 做 namespace 包装，优先用 ACK 返回的 sessionKey；
            # 同时记录 runId 作为备用过滤维度。
            effective_session_key = ack.get("sessionKey") or session_key
            active_run_id = ack.get("runId", "")
            UELogger.info(f"[openclaw_ws] chat.send OK, status={status!r}, "
                          f"runId={active_run_id[:8] if active_run_id else 'N/A'}..., "
                          f"effectiveSession={effective_session_key[:50] if effective_session_key else 'N/A'}")

            # 回传 session key 给 C++，让 SessionEntry 记录真实 key
            write_stream(stream_file, {
                "type": "session_key",
                "key": effective_session_key,
            }, stream_lock)

            await _receive_stream(ws, stream_file, response_file, cancel_flag, stream_lock,
                                  session_key=effective_session_key,
                                  run_id=active_run_id)

    except Exception as exc:
        _error(stream_file, response_file, f"[Error] WebSocket: {exc}", stream_lock)
        UELogger.mcp_error(f"[openclaw_ws] do_chat exception: {exc}")


def _load_device_identity():
    """加载 OpenClaw device identity 用于签名握手。
    
    返回 (device_id, public_key_raw_b64url, private_key_pem) 或 None。
    """
    import base64
    identity_path = os.path.join(os.path.expanduser("~"), ".openclaw", "identity", "device.json")
    if not os.path.isfile(identity_path):
        return None
    try:
        with open(identity_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        device_id = data.get("deviceId", "")
        pub_pem = data.get("publicKeyPem", "")
        priv_pem = data.get("privateKeyPem", "")
        if not (device_id and pub_pem and priv_pem):
            return None
        # 从 PEM 提取 raw 32-byte public key 并转 base64url
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        pub_key = load_pem_public_key(pub_pem.encode())
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        spki_der = pub_key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        # Ed25519 SPKI DER = 12-byte prefix + 32-byte raw key
        raw_pub = spki_der[12:]
        pub_b64url = base64.urlsafe_b64encode(raw_pub).rstrip(b"=").decode()
        return (device_id, pub_b64url, priv_pem)
    except Exception as exc:
        UELogger.warning(f"[openclaw_ws] load device identity: {exc}")
        return None


def _sign_device_payload(private_key_pem: str, payload: str) -> str:
    """用 Ed25519 私钥签名 payload，返回 base64url 编码的签名。"""
    import base64
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    priv_key = load_pem_private_key(private_key_pem.encode(), password=None)
    signature = priv_key.sign(payload.encode())
    return base64.urlsafe_b64encode(signature).rstrip(b"=").decode()


def _build_device_auth(identity, role, scopes, signed_at_ms, nonce, auth_token=""):
    """构建 v3 格式的 device auth 参数。"""
    device_id, pub_b64url, priv_pem = identity
    # v3 payload: "v3|deviceId|clientId|clientMode|role|scopes|signedAtMs|token|nonce|platform|deviceFamily"
    # token = auth.token (gateway token), 用于签名校验
    scopes_str = ",".join(scopes)  # 不排序，保持和 connect params 一致
    payload = "|".join([
        "v3",
        device_id,
        _CLIENT_NAME,       # clientId
        "cli",               # clientMode
        role,
        scopes_str,
        str(signed_at_ms),
        auth_token,          # gateway auth token
        nonce,
        "win32",             # platform
        "",                  # deviceFamily
    ])
    signature = _sign_device_payload(priv_pem, payload)
    return {
        "id": device_id,
        "publicKey": pub_b64url,
        "signature": signature,
        "signedAt": signed_at_ms,
        "nonce": nonce,
    }


# 缓存 device identity，只加载一次
_cached_device_identity = None
_device_identity_loaded = False


def _get_device_identity():
    global _cached_device_identity, _device_identity_loaded
    if not _device_identity_loaded:
        _cached_device_identity = _load_device_identity()
        _device_identity_loaded = True
        if _cached_device_identity:
            UELogger.info("[openclaw_ws] device identity loaded OK")
        else:
            UELogger.warning("[openclaw_ws] no device identity found, scopes will be limited")
    return _cached_device_identity


async def _handshake(ws, token: str, session_key: str = "") -> bool:
    """握手并认证。使用 device identity 签名以获得 operator scopes。"""
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
        msg = json.loads(raw)
        if msg.get("event") != "connect.challenge":
            return False

        nonce = msg.get("payload", {}).get("nonce", "")

        # displayName: "UE Claw Bridge · ue-editor:17334..."
        suffix = session_key[-16:] if session_key else ""
        display_name = f"UE Claw Bridge · {suffix}" if suffix else "UE Claw Bridge"

        scopes = ["operator.read", "operator.write", "operator.admin"]
        signed_at_ms = int(time.time() * 1000)

        # 构建 device auth（如果有 identity）
        identity = _get_device_identity()
        device_param = None
        if identity:
            try:
                device_param = _build_device_auth(identity, "operator", scopes, signed_at_ms, nonce, auth_token=token)
            except Exception as exc:
                UELogger.warning(f"[openclaw_ws] device auth build failed: {exc}")

        params = {
            "minProtocol": _PROTOCOL_VERSION,
            "maxProtocol": _PROTOCOL_VERSION,
            "client": {
                "id": _CLIENT_NAME, "displayName": display_name,
                "version": _CLIENT_VERSION, "platform": "win32", "mode": "cli",
            },
            "caps": [], "auth": {"token": token},
            "role": "operator", "scopes": scopes,
        }
        if device_param:
            params["device"] = device_param

        req_id = str(uuid.uuid4())
        await ws.send(json.dumps({
            "type": "req", "id": req_id, "method": "connect",
            "params": params,
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


async def _send_abort(ws, session_key: str) -> None:
    """通过已有 ws 连接发送 chat.abort RPC（best-effort，不等响应）。"""
    try:
        req_id = str(uuid.uuid4())
        await ws.send(json.dumps({
            "type": "req", "id": req_id,
            "method": "chat.abort",
            "params": {"sessionKey": session_key},
        }))
        UELogger.info(f"[openclaw_ws] chat.abort sent for session={session_key[:50]}")
    except Exception as exc:
        UELogger.warning(f"[openclaw_ws] chat.abort failed: {exc}")


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
    abs_deadline = time.time() + _CHAT_TIMEOUT    # 绝对上限
    idle_deadline = time.time() + _IDLE_TIMEOUT    # 无活动超时（收到事件后重置）

    while True:
        now = time.time()
        if now >= abs_deadline:
            break
        if now >= idle_deadline:
            break
        if cancel_flag.is_set():
            cancel_flag.clear()
            # 发送 chat.abort RPC 让 Gateway 终止 agent 运行
            await _send_abort(ws, session_key)
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
        # Gateway 可能对 sessionKey 做 namespace 包装（如 "agent:<agentId>:<clientId>:xxx"），
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

        # DEBUG: 记录所有 chat 事件的 state + content block 类型
        content_blocks = message.get("content", []) if isinstance(message, dict) else []
        block_types = [b.get("type", "?") for b in content_blocks if isinstance(b, dict)]
        UELogger.info(f"[openclaw_ws] chat event: state={state}, text_len={len(text)}, "
                      f"blocks={block_types}, payload_keys={list(payload.keys())}")

        # --- 只处理已知 state，忽略 monitoring 等非对话状态 ---
        if state not in ("delta", "final", "aborted", "error"):
            UELogger.info(f"[openclaw_ws] skip non-chat state: {state}")
            continue

        # 收到有效事件 → 重置无活动超时
        idle_deadline = time.time() + _IDLE_TIMEOUT

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
            # DEBUG: 转储完整 final payload 到日志文件，帮助定位 usage 字段位置
            try:
                _debug_dir = os.path.dirname(stream_file)
                _debug_path = os.path.join(_debug_dir, "_debug_final_payload.json")
                with open(_debug_path, "w", encoding="utf-8") as _df:
                    # 写原始 payload（截断文本内容避免文件过大）
                    _debug_payload = {}
                    for k, v in payload.items():
                        if k == "message":
                            # 截断 message content 文本，但保留结构
                            _debug_payload[k] = _truncate_for_debug(v)
                        else:
                            _debug_payload[k] = v
                    json.dump(_debug_payload, _df, ensure_ascii=False, indent=2, default=str)
                UELogger.info(f"[openclaw_ws] final payload dumped to {_debug_path}")
            except Exception as _de:
                UELogger.info(f"[openclaw_ws] debug dump failed: {_de}")
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

    # 超时处理: 区分绝对超时和无活动超时
    if time.time() >= abs_deadline:
        timeout_text = (latest_text + "\n\n[Response truncated - absolute timeout 30min]") if latest_text else "[Error] AI response timed out (30min)"
    else:
        timeout_text = (latest_text + "\n\n[Response truncated - idle timeout 5min]") if latest_text else "[Error] AI response timed out (no activity for 5min)"
    write_stream(stream_file, {"type": "error", "text": timeout_text}, stream_lock)
    write_response(response_file, timeout_text)


def _dispatch_usage(payload: dict, message: dict, stream_file: str, stream_lock) -> None:
    """从 final 事件中提取 token usage 并写入 stream.jsonl。

    Gateway 的 usage 位置不确定，按优先级逐层查找:
    1. payload.usage
    2. message.usage
    3. payload.result.usage
    4. payload.meta.usage
    """
    usage = None
    # 多层查找 usage 对象
    candidates = [payload, message]
    for key in ("result", "meta"):
        sub = payload.get(key)
        if isinstance(sub, dict):
            candidates.append(sub)

    for source in candidates:
        if isinstance(source, dict) and isinstance(source.get("usage"), dict):
            usage = source["usage"]
            break

    if not usage:
        # 调试: 记录 payload 顶层 key 帮助定位 usage 位置
        UELogger.info(f"[openclaw_ws] final event no usage found, payload keys: {list(payload.keys())}")
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


def _format_tool_call_summary(tool_name: str, tool_args: dict) -> str:
    """格式化 tool_call 的单行摘要文本。

    根据工具类型提取关键参数，控制在一行内。
    例如:
      [Tool] read - file_path: src/main.py
      [Tool] exec - command: ls -la
      [Tool] web_search - query: "python async"
      [Tool] edit - path: src/main.py
      [Tool] run_ue_python
    """
    if not tool_args:
        return f"[Tool] {tool_name}"

    # 提取最有意义的参数（按工具类型）
    key_param = ""
    # 常见的关键参数名（优先级从高到低）
    _KEY_PARAMS = [
        "query", "command", "code", "message", "text", "url",
        "file_path", "path", "action",
    ]
    for k in _KEY_PARAMS:
        v = tool_args.get(k)
        if v and isinstance(v, str):
            v = v.strip().replace("\n", " ")
            if len(v) > 60:
                v = v[:57] + "..."
            key_param = f"{k}: {v}"
            break

    if not key_param:
        # fallback: 取第一个字符串参数
        for k, v in tool_args.items():
            if isinstance(v, str) and v.strip():
                v = v.strip().replace("\n", " ")
                if len(v) > 60:
                    v = v[:57] + "..."
                key_param = f"{k}: {v}"
                break

    if key_param:
        return f"[Tool] {tool_name} - {key_param}"
    return f"[Tool] {tool_name}"


def _format_tool_result_preview(result_content: str) -> str:
    """从 tool_result 内容中提取简短预览（单行，最多 80 字符）。"""
    if not result_content:
        return ""

    # 取第一个非空行
    for line in result_content.split("\n"):
        line = line.strip()
        if line:
            if len(line) > 80:
                return line[:77] + "..."
            return line
    return ""


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
                # 提取关键参数作为单行摘要
                call_summary = _format_tool_call_summary(tool_name, tool_args)
                write_stream(stream_file, {
                    "type": "tool_use_text",
                    "text": call_summary,
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
                # 结果摘要: 取第一个有意义的行，截断到 80 字符
                result_preview = _format_tool_result_preview(result_content)
                result_line = f"  {tool_name} {status}"
                if result_preview:
                    result_line += f" - {result_preview}"
                write_stream(stream_file, {
                    "type": "tool_use_text",
                    "text": result_line,
                }, stream_lock)


def _error(stream_file: str, response_file: str, msg: str, stream_lock) -> None:
    write_stream(stream_file, {"type": "error", "text": msg}, stream_lock)
    write_response(response_file, msg)


# ---------------------------------------------------------------------------
# 一次性 RPC 辅助: Agent 列表 / 会话历史 / 中止请求
# ---------------------------------------------------------------------------


async def do_abort(session_key: str, gateway_url: str, token: str) -> bool:
    """一次性连接 → chat.abort RPC → 终止指定 session 的所有运行中请求。"""
    try:
        import websockets
    except ImportError:
        UELogger.mcp_error("[openclaw_ws] do_abort: websockets not installed")
        return False

    try:
        async with websockets.connect(gateway_url, open_timeout=5) as ws:
            if not await _handshake(ws, token, session_key=session_key):
                UELogger.mcp_error("[openclaw_ws] do_abort: handshake failed")
                return False

            req_id = str(uuid.uuid4())
            await ws.send(json.dumps({
                "type": "req", "id": req_id,
                "method": "chat.abort",
                "params": {"sessionKey": session_key},
            }))
            ack = await _wait_for_ack(ws, req_id, timeout=10.0)
            if ack is not None:
                UELogger.info(f"[openclaw_ws] do_abort OK: {ack}")
                return True
            UELogger.warning("[openclaw_ws] do_abort: ACK timeout")
            return False

    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_ws] do_abort: {exc}")
        return False

async def do_list_agents(gateway_url: str, token: str) -> str:
    """一次性连接 → agents.list RPC → 返回 JSON。"""
    try:
        import websockets
    except ImportError:
        return json.dumps({"agents": [], "error": "websockets not installed"})

    try:
        async with websockets.connect(gateway_url, open_timeout=5) as ws:
            if not await _handshake(ws, token):
                return json.dumps({"agents": [], "error": "handshake failed"})

            req_id = str(uuid.uuid4())
            await ws.send(json.dumps({
                "type": "req", "id": req_id,
                "method": "agents.list",
                "params": {},
            }))
            ack = await _wait_for_ack(ws, req_id, timeout=10.0)
            if not ack:
                return json.dumps({"agents": [], "error": "timeout"})

            # Gateway 返回格式: {"agents": [{"id":"...", "name":"...", "emoji":"...", ...}]}
            agents = ack.get("agents", [])
            result = []
            for a in agents:
                if isinstance(a, dict):
                    result.append({
                        "id": a.get("id", ""),
                        "name": a.get("name", a.get("id", "")),
                        "emoji": a.get("emoji", ""),
                    })
            return json.dumps({"agents": result}, ensure_ascii=False)

    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_ws] do_list_agents: {exc}")
        return json.dumps({"agents": [], "error": str(exc)})


async def do_fetch_history(session_key: str, gateway_url: str, token: str) -> str:
    """一次性连接 → chat.history RPC → 返回 JSON。"""
    try:
        import websockets
    except ImportError:
        return json.dumps({"messages": [], "error": "websockets not installed"})

    try:
        async with websockets.connect(gateway_url, open_timeout=5) as ws:
            if not await _handshake(ws, token, session_key=session_key):
                return json.dumps({"messages": [], "error": "handshake failed"})

            req_id = str(uuid.uuid4())
            await ws.send(json.dumps({
                "type": "req", "id": req_id,
                "method": "chat.history",
                "params": {"sessionKey": session_key, "limit": 50},
            }))
            ack = await _wait_for_ack(ws, req_id, timeout=10.0)
            if not ack:
                return json.dumps({"messages": [], "error": "timeout"})

            # 将 Gateway 消息格式转换为我们的格式
            raw_messages = ack.get("messages", [])
            messages = []
            for m in raw_messages:
                if not isinstance(m, dict):
                    continue
                role = m.get("role", "")
                content = _extract_text(m)
                if not content:
                    continue
                # 映射 role → sender
                sender = "assistant"
                if role in ("user", "human"):
                    sender = "user"
                elif role == "system":
                    sender = "system"
                messages.append({
                    "sender": sender,
                    "content": content,
                    "isCode": False,
                })
            return json.dumps({"messages": messages}, ensure_ascii=False)

    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_ws] do_fetch_history: {exc}")
        return json.dumps({"messages": [], "error": str(exc)})


async def do_session_info(session_key: str, gateway_url: str, token: str) -> str:
    """一次性连接 → sessions.list RPC → 提取当前 session 的 token 用量信息。

    返回 JSON: {"contextTokens": N, "totalTokens": N, "model": "..."}
    """
    try:
        import websockets
    except ImportError:
        return json.dumps({"error": "websockets not installed"})

    try:
        async with websockets.connect(gateway_url, open_timeout=5) as ws:
            if not await _handshake(ws, token, session_key=session_key):
                return json.dumps({"error": "handshake failed"})

            req_id = str(uuid.uuid4())
            await ws.send(json.dumps({
                "type": "req", "id": req_id,
                "method": "sessions.list",
                "params": {},
            }))
            ack = await _wait_for_ack(ws, req_id, timeout=10.0)
            if not ack:
                return json.dumps({"error": "timeout"})

            # sessions.list 返回 sessions 数组，找到匹配的 session
            sessions = ack.get("sessions", [])
            for s in sessions:
                if not isinstance(s, dict):
                    continue
                s_key = s.get("key", "")
                # 包含匹配（session_key 可能被 Gateway namespace 包装）
                if s_key == session_key or session_key in s_key or s_key in session_key:
                    result = {
                        "contextTokens": s.get("contextTokens", 0),
                        "totalTokens": s.get("totalTokens", 0),
                        "model": s.get("model", ""),
                    }
                    UELogger.info(f"[openclaw_ws] session_info: {result}")
                    return json.dumps(result, ensure_ascii=False)

            UELogger.info(f"[openclaw_ws] session_info: key not found in {len(sessions)} sessions")
            return json.dumps({"error": "session not found", "sessionCount": len(sessions)})

    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_ws] do_session_info: {exc}")
        return json.dumps({"error": str(exc)})
