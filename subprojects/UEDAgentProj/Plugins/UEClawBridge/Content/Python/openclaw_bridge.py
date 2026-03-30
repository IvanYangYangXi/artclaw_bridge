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


def _write_bridge_status(connected: bool, detail: str = "", mcp_ready: bool = None):
    """写入 bridge 连接状态文件，供 C++ FTSTicker 轮询读取。

    mcp_ready: True/False 表示 MCP Server 状态；None 表示保留上次值。
    """
    path = _get_bridge_status_path()
    if not path:
        return
    try:
        # 读取现有状态以保留 mcp_ready（当本次不显式设置时）
        prev_mcp_ready = False
        if mcp_ready is None:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    prev = json.load(f)
                    prev_mcp_ready = prev.get("mcp_ready", False)
            except Exception:
                pass

        status = {
            "connected": connected,
            "mcp_ready": mcp_ready if mcp_ready is not None else prev_mcp_ready,
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


def write_mcp_ready(ready: bool):
    """供 MCP Server 调用：更新 mcp_ready 状态到 bridge 状态文件。

    通过 _write_bridge_status 统一写入，避免文件竞态和字段缺失。
    """
    path = _get_bridge_status_path()
    if not path:
        return
    try:
        # 读取现有状态，保留 connected / detail 等字段
        prev_connected = False
        prev_detail = ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                prev = json.load(f)
                prev_connected = prev.get("connected", False)
                prev_detail = prev.get("detail", "")
        except Exception:
            pass
        _write_bridge_status(prev_connected, prev_detail, mcp_ready=ready)
    except Exception:
        pass


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
_tick_handle = None  # Slate tick callback handle，防止重复注册和 GC


def _schedule_on_game_thread(fn: Callable):
    """将回调排入队列，等待 Tick 时执行"""
    with _callback_lock:
        _pending_callbacks.append(fn)
    # 确保 tick 回调已注册（自愈：如果注册丢失会重新注册）
    _ensure_tick_registered()


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


def _ensure_tick_registered():
    """确保 Slate tick 回调已注册且仅注册一次。"""
    global _tick_handle
    if _tick_handle is not None:
        return  # 已注册
    try:
        if unreal:
            _tick_handle = unreal.register_slate_post_tick_callback(_tick_flush_callbacks)
    except Exception:
        pass


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

    # 注册 Tick 回调（幂等，仅首次生效）
    _ensure_tick_registered()

    return _bridge.start()



# ---------------------------------------------------------------------------
# 记忆摘要注入
# ---------------------------------------------------------------------------

_context_injected = False  # DCC 上下文是否已注入（每个 session 只注入首条）

def _get_pinned_skill_contents() -> str:
    """读取 ~/.artclaw/config.json 中钉选 Skill 的 SKILL.md 内容，拼接注入 AI 上下文。

    最多注入 5 个 Skill（config 层已限制），每个 SKILL.md 截断到 2000 字符。
    """
    config_path = os.path.expanduser("~/.artclaw/config.json")
    if not os.path.exists(config_path):
        return ""

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return ""

    pinned = cfg.get("pinned_skills", [])
    if not pinned:
        return ""

    # 查找 Skill 目录：优先从 skill_hub 获取，fallback 到 Skills/ 目录扫描
    skill_dirs = {}
    try:
        from skill_hub import get_skill_hub
        hub = get_skill_hub()
        if hub:
            for name, info in hub._registered_skills.items():
                manifest = info.get("manifest")
                if manifest and hasattr(manifest, "source_dir"):
                    skill_dirs[name] = manifest.source_dir
    except Exception:
        pass

    parts = []
    for skill_name in pinned[:5]:
        source_dir = skill_dirs.get(skill_name, "")
        if not source_dir:
            continue
        skill_md = os.path.join(str(source_dir), "SKILL.md")
        if not os.path.exists(skill_md):
            continue
        try:
            with open(skill_md, "r", encoding="utf-8") as f:
                content = f.read(2000)
            parts.append(f"[Pinned Skill: {skill_name}]\n{content}")
        except Exception:
            continue

    if not parts:
        return ""

    return "[Pinned Skills Context]\n" + "\n\n".join(parts)


def _enrich_with_briefing(message: str) -> str:
    """在用户消息前附加 DCC 上下文 + 记忆摘要 (Memory Briefing)

    DCC 上下文仅在 session 首条消息注入。
    记忆摘要每条消息都注入（如有内容）。
    """
    global _context_injected
    prefix_parts = []

    # UE 环境上下文 + 跨软件提示（只在首条注入）
    if not _context_injected:
        prefix_parts.append(
            "[DCC Context - 重要]\n"
            "当前对话环境: Unreal Engine 编辑器\n"
            "必须使用的工具前缀: mcp_ue-editor-agent_\n\n"
            "约束规则:\n"
            "1. 所有操作默认使用 mcp_ue-editor-agent_ 前缀的工具\n"
            "2. 获取编辑器上下文请用 mcp_ue-editor-agent_run_ue_python 的 get_context=true\n"
            "3. 仅在当前软件内操作时，不要调用其他软件的工具\n"
            "4. 当任务涉及其他软件时（如从 Maya 导出模型到 UE、查看 Max 场景等），"
            "应主动使用对应软件的工具完成跨软件协作\n"
            "5. 其他软件工具前缀: mcp_maya-primary_（Maya）、mcp_max-primary_（Max）"
        )
        _context_injected = True

    # 记忆摘要
    try:
        from memory_store import get_memory_store
        store = get_memory_store()
        if store:
            briefing = store.manager.export_briefing(max_tokens=1500)
            if briefing and "记忆库为空" not in briefing:
                prefix_parts.append(briefing)
    except Exception:
        pass

    # 钉选 Skill 注入：读取 pinned_skills 的 SKILL.md 内容
    try:
        pinned_skills = _get_pinned_skill_contents()
        if pinned_skills:
            prefix_parts.append(pinned_skills)
    except Exception:
        pass

    if prefix_parts:
        prefix = "\n\n".join(prefix_parts)
        return f"{prefix}\n\n[User Message]\n{message}"
    return message


def set_session_key(session_key: str):
    """设置当前会话的 session key（用于会话切换）"""
    global _bridge
    if _bridge:
        _bridge.set_session_key(session_key)


def get_session_key() -> str:
    """获取当前 session key"""
    global _bridge
    if _bridge:
        return _bridge.get_session_key()
    return ""


def load_session_history(session_key: str) -> str:
    """从 Gateway transcript 加载会话历史，返回 JSON 格式的消息列表。

    session_key 是 bridge 格式 (如 "xiaoyou/ue-editor:1711612345000")。
    sessions.json 中的 key 是 Gateway 格式 (如 "agent:xiaoyou:ue-editor:1711612345000")。
    需要将 bridge key 转换为 Gateway key 进行查找。
    """
    import os
    import json as _json

    # 获取 agent_id（从 bridge 或默认）
    agent_id = "xiaoyou"
    if _bridge:
        agent_id = _bridge.agent_id

    # 构建 sessions.json 路径（通过平台配置驱动）
    try:
        from bridge_config import load_artclaw_config, get_platform_type
        _ac = load_artclaw_config()
        _pt = _ac.get("platform", {}).get("type", "openclaw")
        # 不同平台的 agent 数据目录
        _platform_agent_dirs = {
            "openclaw": os.path.expanduser(f"~/.openclaw/agents/{agent_id}"),
            "workbuddy": os.path.expanduser(f"~/.workbuddy/agents/{agent_id}"),
            "claude": os.path.expanduser(f"~/.claude/agents/{agent_id}"),
        }
        _agent_dir = _platform_agent_dirs.get(_pt, _platform_agent_dirs["openclaw"])
    except ImportError:
        _agent_dir = os.path.expanduser(f"~/.openclaw/agents/{agent_id}")
    sessions_file = os.path.join(_agent_dir, "sessions", "sessions.json")
    if not os.path.exists(sessions_file):
        return "[]"

    try:
        with open(sessions_file, "r", encoding="utf-8") as f:
            sessions = _json.load(f)
    except Exception:
        return "[]"

    # bridge key 格式: "xiaoyou/ue-editor:1711612345000"
    # Gateway key 格式: "agent:xiaoyou:ue-editor:1711612345000"
    # 转换: 将 "/" 替换为 ":"，前加 "agent:"
    gateway_key = "agent:" + session_key.replace("/", ":")

    entry = sessions.get(gateway_key)

    # Fallback: 如果精确匹配不到，遍历查找包含 session_key 后缀的条目
    if not entry:
        # 提取时间戳后缀用于模糊匹配
        for k, v in sessions.items():
            # 检查 key 是否以 session_key 的特征部分结尾
            if session_key in k or k.endswith(session_key.split(":")[-1]):
                entry = v
                break

    if not entry:
        return "[]"

    # 找到 transcript 文件路径
    session_file = entry.get("sessionFile", "")
    if not session_file:
        session_id = entry.get("sessionId", "")
        if not session_id:
            return "[]"
        sessions_dir = os.path.dirname(sessions_file)
        session_file = os.path.join(sessions_dir, f"{session_id}.jsonl")

    if not os.path.exists(session_file):
        return "[]"

    # 解析 JSONL transcript
    messages = []
    try:
        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = _json.loads(line)
                    if obj.get("type") != "message":
                        continue
                    msg = obj.get("message", {})
                    role = msg.get("role", "")
                    if role not in ("user", "assistant"):
                        continue  # 跳过 toolResult 等

                    content = msg.get("content", "")
                    text = ""
                    if isinstance(content, list):
                        text_parts = []
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                        text = "".join(text_parts)
                    elif isinstance(content, str):
                        text = content

                    if text:
                        messages.append({
                            "sender": role,
                            "content": text,
                            "timestamp": obj.get("timestamp", ""),
                        })
                except _json.JSONDecodeError:
                    continue
    except Exception:
        return "[]"

    return _json.dumps(messages, ensure_ascii=False)


def send_chat(message: str) -> str:
    """同步发送消息 (C++ 调用入口)。"""
    global _bridge
    if not _bridge:
        init_bridge()
    if not _bridge:
        return "[错误] Bridge 未初始化"
    enriched = _enrich_with_briefing(message)
    return _bridge.send_message(enriched)


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

    def _on_tool_call(tool_name: str, tool_id: str, arguments: dict):
        if _send_chat_async_to_file_current_id != request_id:
            return
        try:
            line = json.dumps({
                "type": "tool_call",
                "tool_name": tool_name,
                "tool_id": tool_id,
                "arguments": arguments,
            }, ensure_ascii=False)
            with open(stream_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def _on_tool_result(tool_name: str, tool_id: str, content: str, is_error: bool):
        if _send_chat_async_to_file_current_id != request_id:
            return
        try:
            # 截断过长的结果内容
            truncated = content[:2000] if len(content) > 2000 else content
            line = json.dumps({
                "type": "tool_result",
                "tool_name": tool_name,
                "tool_id": tool_id,
                "content": truncated,
                "is_error": is_error,
            }, ensure_ascii=False)
            with open(stream_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def _on_usage_update(usage: dict):
        """将 usage 写入 stream file 供 C++ 轮询"""
        if _send_chat_async_to_file_current_id != request_id:
            return
        try:
            line = json.dumps({
                "type": "usage",
                "usage": usage,
            }, ensure_ascii=False)
            with open(stream_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def _on_result(result: str):
        """最终结果回调 — 直接写文件（不走游戏线程调度，避免 tick 丢失导致卡死）"""
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
            _bridge.on_tool_call = None
            _bridge.on_tool_result = None
            _bridge.on_usage_update = None

    if _bridge:
        _bridge.on_ai_thinking = _on_thinking
        _bridge.on_ai_message = _on_delta
        _bridge.on_tool_call = _on_tool_call
        _bridge.on_tool_result = _on_tool_result
        _bridge.on_usage_update = _on_usage_update
        enriched = _enrich_with_briefing(message)

        # 直接用 worker 线程调用 send_message，绕过 monkey-patched send_message_async
        # _on_result 只写文件，不需要在游戏线程执行
        def _worker():
            try:
                result = _bridge.send_message(enriched)
                _on_result(result)
            except Exception as e:
                _on_result(f"[错误] {e}")

        threading.Thread(target=_worker, daemon=True, name="OCBridge-Chat").start()
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


def get_usage_info() -> str:
    """返回 JSON 格式的 token usage 信息，供 C++ 解析"""
    global _bridge
    if not _bridge:
        return "{}"
    usage = _bridge.get_last_usage()
    if not usage:
        return "{}"
    return json.dumps(usage, ensure_ascii=False)


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
