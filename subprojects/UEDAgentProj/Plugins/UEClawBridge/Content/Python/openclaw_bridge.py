"""
openclaw_bridge.py - OpenClaw Gateway WebSocket RPC 桥接 (UE 适配层)
=====================================================================

UE 特有的桥接适配：日志重定向到 UE Output Log、文件轮询回传、
环境上下文收集。核心 WebSocket 通信逻辑在 bridge_core.py（平台无关）。

向后兼容：C++ 侧所有 `from openclaw_bridge import xxx` 调用不变。
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
from typing import Callable, Optional

try:
    import unreal
except ImportError:
    unreal = None

from init_unreal import UELogger

# ---------------------------------------------------------------------------
# 导入 bridge_core / bridge_config / bridge_diagnostics
# 优先级:
#   1. 自包含部署: 安装器已将 bridge_core.py 等复制到当前 Content/Python/ 目录
#   2. 开发模式: 通过相对路径找到 openclaw-mcp-bridge/ 目录
# ---------------------------------------------------------------------------

try:
    # 自包含部署: bridge_core.py 与 openclaw_bridge.py 在同一目录
    from bridge_core import OpenClawBridge, BridgeLogger  # noqa: E402
    from bridge_config import (  # noqa: E402
        DEFAULT_GATEWAY_URL, DEFAULT_AGENT_ID, DEFAULT_TOKEN,
        PROTOCOL_VERSION, CLIENT_NAME, CLIENT_VERSION,
        load_config as _load_config,
    )
except ImportError:
    # 开发模式: 通过相对路径回溯到 openclaw-mcp-bridge/
    _bridge_pkg_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "..",
                     "openclaw-mcp-bridge")
    )
    if os.path.isdir(_bridge_pkg_dir) and _bridge_pkg_dir not in sys.path:
        sys.path.insert(0, _bridge_pkg_dir)

    from bridge_core import OpenClawBridge, BridgeLogger  # noqa: E402
    from bridge_config import (  # noqa: E402
        DEFAULT_GATEWAY_URL, DEFAULT_AGENT_ID, DEFAULT_TOKEN,
        PROTOCOL_VERSION, CLIENT_NAME, CLIENT_VERSION,
        load_config as _load_config,
    )


# ---------------------------------------------------------------------------
# UE 专用日志适配器
# ---------------------------------------------------------------------------

class _UEBridgeLogger(BridgeLogger):
    """将 bridge 日志重定向到 UE Output Log"""

    def info(self, msg: str):
        UELogger.info(msg)

    def warning(self, msg: str):
        UELogger.warning(msg)

    def error(self, msg: str):
        UELogger.mcp_error(msg)

    def debug(self, msg: str):
        UELogger.debug(msg) if hasattr(UELogger, "debug") else None


# ---------------------------------------------------------------------------
# UE 专用状态文件
# ---------------------------------------------------------------------------

def _get_bridge_status_path() -> str:
    """获取 bridge 状态文件路径 (UE Saved/UEAgent/ 目录下)"""
    try:
        import unreal as _ue
        saved_dir = _ue.Paths.project_saved_dir()
        status_dir = os.path.join(saved_dir, "UEAgent")
        os.makedirs(status_dir, exist_ok=True)
        return os.path.join(status_dir, "_bridge_status.json")
    except (ImportError, Exception):
        return ""


def _write_bridge_status(connected: bool, detail: str = ""):
    """写入 bridge 连接状态文件，供 C++ FTSTicker 轮询读取"""
    path = _get_bridge_status_path()
    if not path:
        return
    try:
        status = {
            "connected": connected,
            "timestamp": time.time(),
            "detail": detail,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(status, f)
    except Exception:
        pass


def _on_bridge_status_changed(connected: bool, detail: str):
    """桥接状态变更回调 — 写入文件供 C++ 读取"""
    _write_bridge_status(connected, detail)


# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------

_bridge: Optional[OpenClawBridge] = None
_send_chat_async_to_file_current_id: Optional[str] = None


# ---------------------------------------------------------------------------
# 游戏线程调度 (UE 专用)
# ---------------------------------------------------------------------------

_pending_callbacks = []
_callback_lock = threading.Lock()


def _schedule_on_game_thread(fn: Callable):
    """将回调排入队列，等待 Tick 时执行"""
    with _callback_lock:
        _pending_callbacks.append(fn)


def _tick_flush_callbacks(dt: float):
    """在编辑器 Tick 中执行回调"""
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

    _bridge = OpenClawBridge(
        logger=_UEBridgeLogger(),
        on_status_changed=_on_bridge_status_changed,
    )

    # 覆盖 send_message_async 使回调在游戏线程执行
    _original_send_async = _bridge.send_message_async

    def _ue_send_message_async(message: str, callback: Callable[[str], None]):
        def _ue_callback(result: str):
            if unreal:
                _schedule_on_game_thread(lambda: callback(result))
            else:
                callback(result)

        # 直接调用底层，绕过 threading（已在独立线程中）
        def _worker():
            result = _bridge.send_message(message)
            _ue_callback(result)

        threading.Thread(target=_worker, daemon=True, name="OCBridge-Chat").start()

    _bridge.send_message_async = _ue_send_message_async

    # 注册 Tick 回调
    try:
        if unreal:
            unreal.register_slate_post_tick_callback(_tick_flush_callbacks)
    except Exception:
        pass

    return _bridge.start()


def send_chat(message: str) -> str:
    """同步发送消息 (C++ 调用入口)。"""
    global _bridge
    if not _bridge:
        init_bridge()
    if not _bridge:
        return "[错误] Bridge 未初始化"
    return _bridge.send_message(message)


def send_chat_async(message: str, callback_name: str = ""):
    """异步发送消息。完成后通过 builtins 传回结果。"""
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
    同时将流式 thinking/delta 写入 stream 文件供 C++ 实时读取。
    """
    global _bridge, _send_chat_async_to_file_current_id
    if not _bridge:
        init_bridge()
    if _bridge:
        _bridge.cancel_current()

    request_id = str(uuid.uuid4())
    _send_chat_async_to_file_current_id = request_id

    stream_file = output_file.replace(".txt", "_stream.jsonl")
    try:
        if os.path.exists(stream_file):
            os.remove(stream_file)
    except Exception:
        pass

    def _write_stream_event(event_type: str, state: str, text: str):
        if _send_chat_async_to_file_current_id != request_id:
            return
        try:
            line = json.dumps({
                "type": event_type,
                "state": state,
                "text": text,
            }, ensure_ascii=False)
            with open(stream_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def _on_thinking(state: str, text: str):
        _write_stream_event("thinking", state, text)

    def _on_delta(state: str, text: str):
        _write_stream_event("delta", state, text)

    def _on_result(result: str):
        if _send_chat_async_to_file_current_id != request_id:
            UELogger.info("OpenClaw Bridge: skipping stale response write (request superseded)")
            return
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(result)
            UELogger.info(f"OpenClaw response written to {output_file}")
        except Exception as e:
            UELogger.mcp_error(f"Failed to write response file: {e}")
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(f"[错误] 写入响应文件失败: {e}")
            except Exception:
                pass

        if _bridge:
            _bridge.on_ai_thinking = None
            _bridge.on_ai_message = None

    if _bridge:
        _bridge.on_ai_thinking = _on_thinking
        _bridge.on_ai_message = _on_delta
        _bridge.send_message_async(message, _on_result)
    else:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("[错误] OpenClaw Bridge 未初始化，请确认 OpenClaw 正在运行。")
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


def cancel_current_request():
    """取消当前正在进行的 AI 请求。"""
    if _bridge:
        _bridge.cancel_current()


# ---------------------------------------------------------------------------
# 连接诊断
# ---------------------------------------------------------------------------

def diagnose_connection(gateway_url: str = "", token: str = "") -> str:
    """诊断 OpenClaw Gateway 连接"""
    from bridge_diagnostics import diagnose_connection as _diagnose
    return _diagnose(gateway_url=gateway_url, token=token, logger=_UEBridgeLogger())


# ---------------------------------------------------------------------------
# 生命周期
# ---------------------------------------------------------------------------

def shutdown():
    """关闭桥接"""
    global _bridge
    if _bridge:
        _bridge.stop()
        _bridge = None


# ---------------------------------------------------------------------------
# 环境上下文收集 (连接成功后发送给 AI) — UE 专用
# ---------------------------------------------------------------------------

def _collect_and_save_context(output_file: str):
    """
    收集当前 UE 编辑器的静态环境信息，写入文件。
    C++ 连接成功后调用，文件内容会作为消息发送给 AI。
    """
    try:
        lines = []
        lines.append("[System] ArtClaw Environment Context")
        lines.append("You are now connected to the ArtClaw UE Editor Agent plugin.")
        lines.append("The user is chatting with you from the ArtClaw Chat Panel inside Unreal Engine Editor.")
        lines.append("")

        try:
            engine_ver = str(unreal.SystemLibrary.get_engine_version())
            lines.append(f"- Engine: Unreal Engine {engine_ver}")
        except Exception:
            lines.append("- Engine: Unreal Engine 5.x")

        try:
            subsystem = unreal.get_editor_subsystem(unreal.UEAgentSubsystem)
            if subsystem:
                plugin_ver = str(subsystem.get_plugin_version())
                lines.append(f"- Plugin: ArtClaw UE Editor Agent v{plugin_ver}")
        except Exception:
            lines.append("- Plugin: ArtClaw UE Editor Agent")

        try:
            from mcp_server import get_mcp_server
            server = get_mcp_server()
            if server and server.is_running:
                lines.append(f"- MCP Server: {server.server_address} (running)")
                lines.append(f"- Registered Tools: {len(server._tools)}")
            else:
                lines.append("- MCP Server: not running")
        except Exception:
            pass

        try:
            project_dir = str(unreal.Paths.project_dir())
            lines.append(f"- Project Directory: {project_dir}")
        except Exception:
            pass

        lines.append("")
        lines.append("You can use MCP tools to query the current level, selected actors, assets, etc.")
        lines.append("When the user mentions 'selected objects', check get_editor_context first to see which panel (viewport or content_browser) the user was last interacting with, then call the appropriate selection tool.")

        context_text = "\n".join(lines)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(context_text)

    except Exception as e:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"[System] ArtClaw UE Editor Agent connected. (context collection error: {e})")
        except Exception:
            pass
