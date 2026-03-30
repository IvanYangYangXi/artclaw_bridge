"""
openclaw_chat.py - OpenClaw 聊天公开 API 层
============================================
职责: 流式写文件、cancel 管理、session 管理、C++ 调用入口。
底层连接见 openclaw_bridge.py。
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
    import unreal
except ImportError:
    unreal = None

from init_unreal import UELogger
from openclaw_bridge import OpenClawBridge

# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------

_bridge: Optional[OpenClawBridge] = None
_stream_file: Optional[str] = None
_stream_lock = threading.Lock()
_current_request_id: Optional[str] = None
_context_injected = False

# ---------------------------------------------------------------------------
# 流式写文件回调
# ---------------------------------------------------------------------------

def _make_stream_writer(stream_file: str, request_id: str):
    """返回 on_ai_message 回调，实时追加写 stream.jsonl"""
    def _on_ai_message(state: str, text: str):
        if request_id != _current_request_id:
            return
        if not stream_file or not text:
            return
        with _stream_lock:
            try:
                line = json.dumps({"type": state, "text": text}, ensure_ascii=False)
                with open(stream_file, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception as e:
                UELogger.mcp_error(f"Stream write error: {e}")
    return _on_ai_message


def _make_tool_event_writer(stream_file: str, request_id: str):
    """返回 on_tool_event 回调，写 tool_call/tool_result 到 stream.jsonl"""
    def _on_tool_event(event_type: str, data: dict):
        if request_id != _current_request_id:
            return
        if not stream_file:
            return
        with _stream_lock:
            try:
                line_obj = {"type": event_type}
                line_obj.update(data)
                if event_type == "tool_result" and isinstance(line_obj.get("content"), str):
                    if len(line_obj["content"]) > 2000:
                        line_obj["content"] = line_obj["content"][:2000] + "...[truncated]"
                line = json.dumps(line_obj, ensure_ascii=False)
                with open(stream_file, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception as e:
                UELogger.mcp_error(f"Tool event write error: {e}")
    return _on_tool_event

# ---------------------------------------------------------------------------
# 上下文注入
# ---------------------------------------------------------------------------

def _enrich_with_context(message: str) -> str:
    """首条消息注入 UE 环境上下文（项目名/引擎版本/工具约束）"""
    global _context_injected
    if _context_injected:
        return message
    _context_injected = True

    ctx_lines = ["[UE Context]"]
    try:
        import unreal as ue
        ctx_lines.append(f"Engine: Unreal Engine {ue.SystemLibrary.get_engine_version()}")
        ctx_lines.append(f"Project: {ue.SystemLibrary.get_game_name()}")
    except Exception:
        ctx_lines.append("Engine: Unreal Engine")

    ctx_lines.append("Role: UE Editor AI Assistant")
    ctx_lines.append("Constraint: Only use run_ue_python tool. Do NOT call tools for other DCCs.")

    try:
        from memory_store import get_memory_manager
        mm = get_memory_manager()
        if mm:
            briefing = mm.export_briefing()
            if briefing:
                ctx_lines.append(briefing)
    except Exception:
        pass

    ctx = "\n".join(ctx_lines)
    return f"{ctx}\n\n{message}"

# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def init_bridge() -> bool:
    """初始化 OpenClaw 桥接"""
    global _bridge
    if _bridge and _bridge.is_connected():
        return True
    _bridge = OpenClawBridge()
    return _bridge.start()


def connect(gateway_url: str = "", token: str = "") -> bool:
    return init_bridge()


def disconnect():
    shutdown()


def is_connected() -> bool:
    return _bridge is not None and _bridge.is_connected()


def send_chat(message: str) -> str:
    """同步发送消息（调试用）"""
    global _bridge
    if not _bridge:
        init_bridge()
    if not _bridge:
        return "[Error] Bridge not initialized"
    return _bridge.send_message(message)


def send_chat_async_to_file(message: str, output_file: str):
    """
    异步发送消息，完整结果写入 output_file。
    流式增量实时写入同目录的 _openclaw_response_stream.jsonl。
    """
    global _bridge, _stream_file, _current_request_id

    if not _bridge:
        init_bridge()

    # 等待连接就绪（最多 3 秒）
    if _bridge and not _bridge.is_connected():
        deadline = time.time() + 3.0
        while time.time() < deadline and not _bridge.is_connected():
            time.sleep(0.1)

    # 生成请求 ID，防止旧回调写文件
    req_id = str(uuid.uuid4())
    _current_request_id = req_id

    stream_file = os.path.join(os.path.dirname(output_file), "_openclaw_response_stream.jsonl")
    _stream_file = stream_file

    # 清空旧 stream 文件
    with _stream_lock:
        try:
            if os.path.exists(stream_file):
                os.remove(stream_file)
        except Exception:
            pass

    if _bridge:
        _bridge.on_ai_message = _make_stream_writer(stream_file, req_id)
        _bridge.on_tool_event = _make_tool_event_writer(stream_file, req_id)

    def _on_result(result: str):
        if req_id != _current_request_id:
            UELogger.info("send_chat_async_to_file: stale callback ignored")
            return
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(result)
            UELogger.info(f"OpenClaw response written to {output_file}")
        except Exception as e:
            UELogger.mcp_error(f"Failed to write response file: {e}")
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(f"[Error] Failed to write response: {e}")
            except Exception:
                pass

    if not _bridge:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("[Error] OpenClaw Bridge not initialized. Is OpenClaw running?")
        except Exception:
            pass
        return

    enriched = _enrich_with_context(message)
    _bridge.send_message_async(enriched, _on_result)


def cancel_current_request():
    """取消当前 AI 请求"""
    global _current_request_id
    _current_request_id = None
    if _bridge:
        _bridge.cancel()


def reset_session():
    """重置 session（新对话）"""
    global _context_injected
    _context_injected = False
    if _bridge:
        _bridge.reset_session()


def set_session_key(key: str):
    if _bridge:
        _bridge.set_session_key(key)


def get_session_key() -> str:
    return _bridge.get_session_key() if _bridge else ""


def _collect_and_save_context(context_file: str):
    """收集 UE 环境上下文并写入文件（保留接口兼容性，实际注入已移到 _enrich_with_context）"""
    try:
        import unreal as ue
        ctx = (
            f"[UE Context]\n"
            f"Engine: Unreal Engine {ue.SystemLibrary.get_engine_version()}\n"
            f"Project: {ue.SystemLibrary.get_game_name()}\n"
            f"Role: UE Editor AI Assistant\n"
            f"Constraint: Only use run_ue_python. Do NOT call tools for other DCCs.\n"
        )
    except Exception:
        ctx = "[UE Context]\nEngine: Unreal Engine\n"
    try:
        with open(context_file, "w", encoding="utf-8") as f:
            f.write(ctx)
    except Exception as e:
        UELogger.mcp_error(f"Failed to write context file: {e}")


def diagnose_connection(gateway_url: str = "", token: str = "") -> str:
    """诊断连接（委托到 openclaw_diagnose.py）"""
    try:
        import importlib
        import openclaw_diagnose
        importlib.reload(openclaw_diagnose)
        return openclaw_diagnose.diagnose_connection(gateway_url, token)
    except ImportError:
        return "[Error] openclaw_diagnose.py not found"


def shutdown():
    """关闭桥接"""
    global _bridge
    if _bridge:
        _bridge.stop()
        _bridge = None
