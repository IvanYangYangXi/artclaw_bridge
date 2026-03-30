"""
openclaw_chat.py — OpenClaw 聊天公开 API 层
============================================
职责: C++ 调用入口、UE 上下文注入、session 管理、文件协议。
底层 WebSocket 通信见 openclaw_ws.py。

文件协议 (Saved/UEAgent/):
  _openclaw_msg_input.txt          — C++ 写入消息内容，Python 读取
  _openclaw_response_stream.jsonl  — Python 实时写入流式事件
  _openclaw_response.txt           — Python 写入最终回复（出现即代表完成）
"""
# Ref: docs/UEClawBridge/features/对话框通信重构计划.md

from __future__ import annotations

import asyncio
import json
import os
import socket
import threading
import time
from typing import Optional

try:
    import unreal  # noqa: F401
except ImportError:
    unreal = None

from init_unreal import UELogger
import openclaw_ws

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

_DEFAULT_AGENT_ID = "qi"
_DEFAULT_TOKEN    = "ec8900cf3e3c4bbfab43c8d7d5a4638c69b854e075902325"
_GATEWAY_PORT     = 18789


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

_session_key:      Optional[str]   = None
_context_injected: bool            = False
_cancel_flag:      threading.Event = threading.Event()
_stream_lock:      threading.Lock  = threading.Lock()

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
# 后台工作线程
# ---------------------------------------------------------------------------

def _chat_worker(message: str, stream_file: str, response_file: str) -> None:
    """在独立线程中运行 asyncio.run()，完成一次完整的聊天请求。"""
    global _session_key
    if not _session_key:
        _session_key = f"{_DEFAULT_AGENT_ID}/ue-editor:{int(time.time())}"

    UELogger.info(f"[openclaw_chat] connecting to {_get_gateway_url()}, session={_session_key}")

    asyncio.run(openclaw_ws.do_chat(
        message       = message,
        stream_file   = stream_file,
        response_file = response_file,
        gateway_url   = _get_gateway_url(),
        token         = _get_token(),
        session_key   = _session_key,
        cancel_flag   = _cancel_flag,
        stream_lock   = _stream_lock,
    ))


# ---------------------------------------------------------------------------
# 公开 API（供 C++ 调用）
# ---------------------------------------------------------------------------

def connect(gateway_url: str = "", token: str = "") -> bool:
    """测试 Gateway 是否可达（socket 探测）。"""
    gw   = _get_gateway_config()
    port = gw.get("port", _GATEWAY_PORT)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    try:
        s.connect(("127.0.0.1", port))
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
    global _session_key, _context_injected
    _session_key      = None
    _context_injected = False
    UELogger.info("[openclaw_chat] session reset")


def is_connected() -> bool:
    return connect()


def send_chat_async_to_file(msg_file: str, response_file: str) -> None:
    """
    从 msg_file 读取消息，异步发送给 AI，结果写入 response_file。
    stream.jsonl 实时写入 response_file 同目录。
    """
    try:
        with open(msg_file, "r", encoding="utf-8") as f:
            message = f.read()
        try:
            os.remove(msg_file)
        except Exception:
            pass
    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_chat] read msg_file: {exc}")
        openclaw_ws.write_response(response_file, f"[Error] Failed to read message: {exc}")
        return

    message = message.strip()
    if not message:
        openclaw_ws.write_response(response_file, "[Error] Empty message")
        return

    stream_file = os.path.join(
        os.path.dirname(response_file), "_openclaw_response_stream.jsonl"
    )
    with _stream_lock:
        try:
            if os.path.exists(stream_file):
                os.remove(stream_file)
        except Exception:
            pass

    _cancel_flag.clear()
    enriched = _enrich(message)

    t = threading.Thread(
        target=_chat_worker,
        args=(enriched, stream_file, response_file),
        daemon=True,
        name="OCChat-Worker",
    )
    t.start()
    UELogger.info("[openclaw_chat] chat worker started")


def cancel_current_request() -> None:
    _cancel_flag.set()
    UELogger.info("[openclaw_chat] cancel flag set")


def reset_session() -> None:
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
    try:
        import importlib
        import openclaw_diagnose
        importlib.reload(openclaw_diagnose)
        return openclaw_diagnose.diagnose_connection(gateway_url, token)
    except ImportError:
        return "[Error] openclaw_diagnose.py not found"


def shutdown() -> None:
    disconnect()


def _collect_and_save_context(context_file: str) -> None:
    """兼容旧版 C++ 调用。"""
    try:
        with open(context_file, "w", encoding="utf-8") as f:
            f.write(_build_context_prefix())
    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_chat] context write: {exc}")
