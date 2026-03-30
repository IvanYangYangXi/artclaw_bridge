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
_stream_file: Optional[str] = None          # 当前流式输出文件路径
_stream_lock = threading.Lock()
_current_request_id: Optional[str] = None  # 用于防止旧回调写文件
_context_injected = False                   # 本 session 是否已注入 DCC 上下文

# ---------------------------------------------------------------------------
# 流式写文件
# ---------------------------------------------------------------------------

def _make_stream_writer(stream_file: str, request_id: str):
    """返回 on_ai_message 回调，负责实时写 stream.jsonl"""
    def _on_ai_message(state: str, text: str):
        global _current_request_id
        # 忽略过期请求的回调
        if request_id != _current_request_id:
            return
        if not stream_file or not text:
            return

        with _stream_lock:
            try:
                event_type = "delta" if state == "delta" else state
                line = json.dumps({"type": event_type, "text": text}, ensure_ascii=False)
                with open(stream_file, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception as e:
                UELogger.mcp_error(f"Stream write error: {e}")

    return _on_ai_message


def _make_tool_event_writer(stream_file: str, request_id: str):
    """返回 on_tool_event 回调，负责实时写 tool_call/tool_result 到 stream.jsonl"""
    def _on_tool_event(event_type: str, data: dict):
        global _current_request_id
        if request_id != _current_request_id:
            return
        if not stream_file:
            return
        with _stream_lock:
            try:
                line_obj = {"type": event_type}
                line_obj.update(data)
                # tool_result content 截断到 2000 字符
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
    ctx_lines.append("Constraint: Only use run_ue_python tool. Do NOT call tools for other DCCs (Maya, Max, etc.).")

    # 追加 memory briefing（如果有）
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
# 公开 API（供 C++ 通过 ExecPythonCommand 调用）
# ---------------------------------------------------------------------------

def init_bridge() -> bool:
    """初始化 OpenClaw 桥接。C++ 启动时调用。"""
    global _bridge
    if _bridge and _bridge.is_connected():
        return True
    _bridge = OpenClawBridge()
    return _bridge.start()


def connect(gateway_url: str = "", token: str = "") -> bool:
    """连接 Gateway（Connect 按钮调用）"""
    return init_bridge()


def disconnect():
    """断开连接"""
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
    流式增量实时写入 output_file 同目录的 _openclaw_response_stream.jsonl。

    C++ 侧：轮询 output_file 获取完整回复，轮询 stream.jsonl 获取流式内容。
    """
    global _bridge, _stream_file, _current_request_id

    if not _bridge:
        init_bridge()

    # 等待连接就绪（最多 3 秒，应对重连后立即发消息的情况）
    if _bridge and not _bridge.is_connected():
        deadline = time.time() + 3.0
        while time.time() < deadline and not _bridge.is_connected():
            time.sleep(0.1)

    # 生成请求 ID，防止旧回调写文件
    import uuid
    req_id = str(uuid.uuid4())
    _current_request_id = req_id

    # stream.jsonl 路径与 output_file 同目录
    stream_file = os.path.join(os.path.dirname(output_file), "_openclaw_response_stream.jsonl")
    _stream_file = stream_file

    # 清空旧的 stream 文件（新请求开始）
    with _stream_lock:
        try:
            if os.path.exists(stream_file):
                os.remove(stream_file)
        except Exception:
            pass

    # 注册流式回调
    if _bridge:
        _bridge.on_ai_message = _make_stream_writer(stream_file, req_id)
        _bridge.on_tool_event = _make_tool_event_writer(stream_file, req_id)

    def _on_result(result: str):
        # 写完整结果文件（C++ 检测到此文件才算完成）
        if req_id != _current_request_id:
            UELogger.verbose("send_chat_async_to_file: stale callback, skipping write")
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
    """取消当前 AI 请求（停止按钮调用）"""
    global _current_request_id
    _current_request_id = None  # 让旧回调忽略结果
    if _bridge:
        _bridge.cancel()


def reset_session():
    """重置 session（新对话按钮调用）"""
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
    """收集 UE 环境上下文并写入文件（ConnectOpenClawBridge 调用）"""
    try:
        import unreal as ue
        project_name = ue.SystemLibrary.get_game_name()
        engine_version = ue.SystemLibrary.get_engine_version()
        ctx_text = (
            f"[DCC Context - 重要]\n"
            f"当前软件: Unreal Engine {engine_version}\n"
            f"项目名称: {project_name}\n"
            f"角色定位: 你是一个 UE 编辑器内的 AI 助手。\n"
            f"工具约束: 禁止调用非 UE 编辑器工具（Maya/Max 等）。\n"
            f"唯一可用工具: run_ue_python\n"
        )
    except Exception:
        ctx_text = (
            "[DCC Context - 重要]\n"
            "当前软件: Unreal Engine\n"
            "工具约束: 禁止调用非 UE 编辑器工具。\n"
            "唯一可用工具: run_ue_python\n"
        )
    try:
        with open(context_file, "w", encoding="utf-8") as f:
            f.write(ctx_text)
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
