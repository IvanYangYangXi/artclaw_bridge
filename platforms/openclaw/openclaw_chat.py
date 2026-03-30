"""
openclaw_chat.py — OpenClaw 聊天公开 API 层
============================================
职责:
  - 流式写文件（stream.jsonl，供 C++ 轮询）
  - cancel / session 管理
  - C++ 调用入口（send_chat_async_to_file 等）

底层连接见 openclaw_bridge.py。

消息传递规范:
  C++ → Python 发送消息时，消息内容通过临时 JSON 文件传递，
  不通过 Python 字符串拼接，以避免引号/特殊字符问题。
"""
# Ref: docs/UEClawBridge/specs/架构设计.md

from __future__ import annotations

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
from openclaw_bridge import OpenClawBridge

# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------

_bridge:              Optional[OpenClawBridge] = None
_stream_lock          = threading.Lock()
_current_request_id:  Optional[str]            = None
_context_injected     = False

# ---------------------------------------------------------------------------
# 流式写文件
# ---------------------------------------------------------------------------

def _write_stream_line(stream_file: str, obj: dict) -> None:
    """线程安全地向 stream.jsonl 追加一行 JSON。"""
    try:
        line = json.dumps(obj, ensure_ascii=False)
        with _stream_lock:
            with open(stream_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception as exc:
        UELogger.mcp_error(f"Stream write error: {exc}")


def _make_ai_message_handler(stream_file: str, request_id: str):
    """
    返回 on_ai_message 回调。
    实时将 delta/final/aborted/error 事件追加写入 stream.jsonl。
    通过 request_id 防止旧回调写入新请求的文件。
    """
    def _handler(state: str, text: str) -> None:
        if request_id != _current_request_id:
            return
        if not text and state not in ("final", "aborted", "error"):
            return
        _write_stream_line(stream_file, {"type": state, "text": text or ""})

    return _handler


def _make_tool_event_handler(stream_file: str, request_id: str):
    """
    返回 on_tool_event 回调。
    将 tool_call / tool_result 事件追加写入 stream.jsonl。
    tool_result 内容截断到 2000 字符，避免 C++ 侧解析超长字符串。
    """
    def _handler(event_type: str, data: dict) -> None:
        if request_id != _current_request_id:
            return
        obj = {"type": event_type}
        obj.update(data)
        if event_type == "tool_result":
            content = obj.get("content", "")
            if isinstance(content, str) and len(content) > 2000:
                obj["content"] = content[:2000] + "...[truncated]"
        _write_stream_line(stream_file, obj)

    return _handler


# ---------------------------------------------------------------------------
# 上下文注入
# ---------------------------------------------------------------------------

def _build_ue_context() -> str:
    """构建 UE 环境上下文字符串（仅首次调用时注入）。"""
    lines = ["[UE Context - 重要]"]
    try:
        import unreal as ue
        lines.append(f"Engine: Unreal Engine {ue.SystemLibrary.get_engine_version()}")
        lines.append(f"Project: {ue.SystemLibrary.get_game_name()}")
    except Exception:
        lines.append("Engine: Unreal Engine")
    lines.append("Role: UE Editor AI Assistant")
    lines.append(
        "Constraint: 禁止调用任何其他 DCC 工具（Maya/Max 等）。"
        "只允许使用 run_ue_python 工具。"
    )
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


def _enrich_with_context(message: str) -> str:
    """首条消息前注入 UE 环境上下文。"""
    global _context_injected
    if _context_injected:
        return message
    _context_injected = True
    ctx = _build_ue_context()
    return f"{ctx}\n\n{message}"


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def init_bridge() -> bool:
    """初始化 OpenClaw 桥接（幂等）。"""
    global _bridge
    if _bridge and _bridge.is_connected():
        return True
    _bridge = OpenClawBridge()
    return _bridge.start()


def connect(gateway_url: str = "", token: str = "") -> bool:
    """连接到 OpenClaw Gateway。"""
    return init_bridge()


def disconnect() -> None:
    """断开连接。"""
    shutdown()


def is_connected() -> bool:
    """返回当前是否已连接。"""
    return _bridge is not None and _bridge.is_connected()


def send_chat(message: str) -> str:
    """同步发送消息（调试用）。"""
    global _bridge
    if not _bridge:
        init_bridge()
    if not _bridge:
        return "[Error] Bridge not initialized"
    return _bridge.send_message(message)


def send_chat_async_to_file(message_or_file: str, output_file: str) -> None:
    """
    异步发送消息，完整结果写入 output_file。
    流式增量实时写入同目录的 _openclaw_response_stream.jsonl。

    参数:
        message_or_file: 消息文本，或以 @file: 开头的临时文件路径（推荐）。
                         C++ 侧应通过 send_chat_from_file 使用文件方式。
        output_file:     AI 完整回复写入路径。
    """
    global _bridge, _current_request_id

    # 从临时文件读取消息（安全，避免字符串拼接问题）
    if message_or_file.startswith("@file:"):
        msg_file = message_or_file[6:]
        try:
            with open(msg_file, "r", encoding="utf-8") as f:
                message = f.read()
            try:
                os.remove(msg_file)
            except Exception:
                pass
        except Exception as exc:
            UELogger.mcp_error(f"Failed to read message file: {exc}")
            _write_error_file(output_file, f"Failed to read message file: {exc}")
            return
    else:
        message = message_or_file

    if not message.strip():
        _write_error_file(output_file, "Empty message")
        return

    # 确保 bridge 已初始化
    if not _bridge:
        init_bridge()
    if not _bridge:
        _write_error_file(output_file, "OpenClaw Bridge not initialized. Is OpenClaw running?")
        return

    # 等待连接就绪（最多 3 秒）
    if not _bridge.is_connected():
        deadline = time.time() + 3.0
        while time.time() < deadline and not _bridge.is_connected():
            time.sleep(0.1)
    if not _bridge.is_connected():
        _write_error_file(output_file, "Not connected to OpenClaw Gateway. Is openclaw running?")
        return

    # 生成请求 ID，防止旧回调写文件
    req_id          = str(uuid.uuid4())
    _current_request_id = req_id

    stream_file = os.path.join(
        os.path.dirname(output_file), "_openclaw_response_stream.jsonl"
    )

    # 清空旧 stream 文件
    with _stream_lock:
        try:
            if os.path.exists(stream_file):
                os.remove(stream_file)
        except Exception:
            pass

    # 注册回调
    _bridge.on_ai_message = _make_ai_message_handler(stream_file, req_id)
    _bridge.on_tool_event = _make_tool_event_handler(stream_file, req_id)

    def _on_result(result: str) -> None:
        if req_id != _current_request_id:
            UELogger.info("send_chat_async_to_file: stale callback ignored")
            return
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(result)
            UELogger.info(f"OpenClaw response written ({len(result)} chars)")
        except Exception as exc:
            UELogger.mcp_error(f"Failed to write response file: {exc}")
            _write_error_file(output_file, f"Failed to write response: {exc}")

    enriched = _enrich_with_context(message)
    _bridge.send_message_async(enriched, _on_result)


def cancel_current_request() -> None:
    """取消当前 AI 请求。"""
    global _current_request_id
    _current_request_id = None
    if _bridge:
        _bridge.cancel()


def reset_session() -> None:
    """重置 session（新对话）。"""
    global _context_injected
    _context_injected = False
    if _bridge:
        _bridge.reset_session()


def set_session_key(key: str) -> None:
    if _bridge:
        _bridge.set_session_key(key)


def get_session_key() -> str:
    return _bridge.get_session_key() if _bridge else ""


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
    """关闭桥接。"""
    global _bridge
    if _bridge:
        _bridge.stop()
        _bridge = None


# ---------------------------------------------------------------------------
# 保留旧接口（兼容性）
# ---------------------------------------------------------------------------

def _collect_and_save_context(context_file: str) -> None:
    """兼容旧版 C++ 调用（实际上下文注入已移到 _enrich_with_context）。"""
    try:
        ctx = _build_ue_context()
        with open(context_file, "w", encoding="utf-8") as f:
            f.write(ctx)
    except Exception as exc:
        UELogger.mcp_error(f"Failed to write context file: {exc}")


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _write_error_file(output_file: str, message: str) -> None:
    """写入错误信息到 output_file，让 C++ 轮询到结果而不是一直等待。"""
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"[Error] {message}")
    except Exception:
        pass
