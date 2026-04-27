"""
tool_event_writer.py - 通用 Tool 事件写入器
=============================================

所有 DCC (UE/Maya/Max/Blender/Houdini/SP/SD/ComfyUI) 通用。
MCP Server 在执行 tool call 前后调用本模块，将结构化事件写入 stream file。
前端（C++ / Qt / Web）轮询或订阅该文件即可显示 tool call 卡片。

事件类型:
  - tool_call:    工具调用开始 (tool_name, tool_id, arguments)
  - tool_result:  工具调用完成 (tool_name, tool_id, content, is_error)
  - tool_use_text: 轻量文本摘要 (fallback 用)

使用方式:
  1. DCC 启动时调用 set_stream_file_provider(fn) 注入路径获取逻辑
  2. MCP Server 在 tool 执行前后调用 write_tool_event("start"/"done"/"error", ...)
"""

import json
import logging
import threading
import uuid
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("artclaw.tool_event")

# --------------------------------------------------------------------------
# 配置
# --------------------------------------------------------------------------

_stream_lock = threading.Lock()
_active_tool_ids: Dict[str, str] = {}  # tool_name → tool_id 配对缓存

# DCC 注入的回调: () -> str，返回当前活跃 stream file 路径（空串 = 不写）
_stream_file_provider: Optional[Callable[[], str]] = None


def set_stream_file_provider(provider: Callable[[], str]) -> None:
    """注入 stream file 路径提供函数。各 DCC 在启动时调用一次。"""
    global _stream_file_provider
    _stream_file_provider = provider


def _get_stream_file() -> str:
    if _stream_file_provider:
        try:
            return _stream_file_provider() or ""
        except Exception:
            return ""
    return ""


# --------------------------------------------------------------------------
# 工具名简化
# --------------------------------------------------------------------------

def _shorten_tool_name(tool_name: str) -> str:
    """mcp_ue-editor-agent_run_ue_python → run_ue_python"""
    if "_" not in tool_name:
        return tool_name
    parts = tool_name.split("_")
    prefix_end = 0
    for i, p in enumerate(parts):
        if p in ("mcp",):
            prefix_end = i + 1
            continue
        if "-" in p:
            prefix_end = i + 1
            continue
        break
    return "_".join(parts[prefix_end:]) if prefix_end < len(parts) else tool_name


# --------------------------------------------------------------------------
# 参数摘要
# --------------------------------------------------------------------------

_PREVIEW_KEYS = ("code", "query", "command", "path", "file_path", "action", "message")


def _arg_preview(arguments: Optional[Dict]) -> str:
    if not arguments or not isinstance(arguments, dict):
        return ""
    for k in _PREVIEW_KEYS:
        v = arguments.get(k)
        if v and isinstance(v, str):
            v = v.strip().replace("\n", " ")
            if len(v) > 50:
                v = v[:47] + "..."
            return f" ({k}: {v})"
    return ""


# --------------------------------------------------------------------------
# 核心写入
# --------------------------------------------------------------------------

# 结果截断阈值
_RESULT_MAX_CHARS = 2000


def write_tool_event(
    event_type: str,
    tool_name: str,
    *,
    arguments: Optional[Dict] = None,
    result: Any = None,
) -> None:
    """将 tool 事件写入 stream file。

    Args:
        event_type: "start" | "done" | "error"
        tool_name:  MCP tool 全名
        arguments:  tool 入参 (start 时传)
        result:     tool 返回值或错误信息 (done/error 时传)
    """
    stream_file = _get_stream_file()
    if not stream_file:
        return

    short = _shorten_tool_name(tool_name)
    events = []

    try:
        if event_type == "start":
            tool_id = f"mcp_{uuid.uuid4().hex[:12]}"
            _active_tool_ids[tool_name] = tool_id

            events.append({
                "type": "tool_call",
                "tool_name": short,
                "tool_id": tool_id,
                "arguments": arguments if isinstance(arguments, dict) else {},
            })
            events.append({
                "type": "tool_use_text",
                "text": f"\u2699 {short}{_arg_preview(arguments)}",
            })

        elif event_type == "done":
            tool_id = _active_tool_ids.pop(tool_name, "mcp_unknown")
            content = str(result).strip() if result is not None else ""
            if len(content) > _RESULT_MAX_CHARS:
                content = content[:_RESULT_MAX_CHARS] + "...[truncated]"

            events.append({
                "type": "tool_result",
                "tool_name": short,
                "tool_id": tool_id,
                "content": content,
                "is_error": False,
            })
            preview = content.replace("\n", " ")[:80]
            events.append({
                "type": "tool_use_text",
                "text": f"\u2705 {short} \u2192 {preview}" if preview else f"\u2705 {short}",
            })

        elif event_type == "error":
            tool_id = _active_tool_ids.pop(tool_name, "mcp_unknown")
            err = str(result)[:200] if result else "unknown"

            events.append({
                "type": "tool_result",
                "tool_name": short,
                "tool_id": tool_id,
                "content": err,
                "is_error": True,
            })
            events.append({
                "type": "tool_use_text",
                "text": f"\u274C {short}: {err[:80]}",
            })

        else:
            return

        with _stream_lock:
            with open(stream_file, "a", encoding="utf-8") as f:
                for ev in events:
                    f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    except Exception as e:
        logger.error(f"write_tool_event: {e}")
