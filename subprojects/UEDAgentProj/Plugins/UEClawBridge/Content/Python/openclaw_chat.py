"""
openclaw_chat.py — OpenClaw 聊天公开 API 层
============================================
职责: C++ 调用入口、UE 上下文注入、session 管理、文件协议。
底层 WebSocket 通信见 openclaw_ws.py。

文件协议 (Saved/ClawBridge/):
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

from claw_bridge_logger import UELogger

import openclaw_ws

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

_DEFAULT_AGENT_ID = "qi"
_DEFAULT_TOKEN    = "ec8900cf3e3c4bbfab43c8d7d5a4638c69b854e075902325"
_GATEWAY_PORT     = 18789


def _load_artclaw_config() -> dict:
    """读取 ~/.artclaw/config.json（Agent 切换 + 缓存用）。"""
    try:
        config_path = os.path.join(os.path.expanduser("~"), ".artclaw", "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_artclaw_config(config: dict) -> None:
    """原子写入 ~/.artclaw/config.json。"""
    try:
        config_dir = os.path.join(os.path.expanduser("~"), ".artclaw")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "config.json")
        import tempfile
        fd, tmp = tempfile.mkstemp(dir=config_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            os.replace(tmp, config_path)
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise
    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_chat] save artclaw config: {exc}")


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
    try:
        from bridge_config import get_gateway_url
        return get_gateway_url()
    except ImportError:
        gw = _get_gateway_config()
        return f"ws://127.0.0.1:{gw.get('port', _GATEWAY_PORT)}"


def _get_token() -> str:
    try:
        from bridge_config import get_gateway_token
        return get_gateway_token()
    except ImportError:
        gw = _get_gateway_config()
        return gw.get("auth", {}).get("token", _DEFAULT_TOKEN)


# ---------------------------------------------------------------------------
# 全局状态（最小化）
# ---------------------------------------------------------------------------

_agent_id:         str             = _DEFAULT_AGENT_ID
_session_key:      Optional[str]   = None
_context_injected: bool            = False
_cancel_flag:      threading.Event = threading.Event()
_stream_lock:      threading.Lock  = threading.Lock()

# 启动时从 config 恢复 last_agent_id
try:
    _agent_id = _load_artclaw_config().get("last_agent_id", _DEFAULT_AGENT_ID) or _DEFAULT_AGENT_ID
except Exception:
    pass

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
    lines.append(
        "工具使用规则:\n"
        "- UE 场景/资产的查询与操作使用 run_ue_python\n"
        "- 涉及其他 DCC 软件（Maya/Max 等）时，使用对应软件的 run_python\n"
        "- 本地文件读写、以及其他不依赖 UE 环境的任务，直接使用自身能力处理"
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


def _build_pinned_hint() -> str:
    """读取 pinned_skills，生成一句自然语言提示告诉 AI 优先使用这些 Skill。"""
    try:
        config_path = os.path.join(os.path.expanduser("~"), ".artclaw", "config.json")
        if not os.path.exists(config_path):
            return ""
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        pinned = cfg.get("pinned_skills", [])
        if not pinned:
            return ""
        names = ", ".join(pinned[:5])
        return (
            f"[Pinned Skills] 用户钉选了以下技能: {names}。"
            f"当用户请求涉及这些技能的功能时，请优先加载并按照对应 Skill 的操作指南执行。"
        )
    except Exception:
        return ""


def _enrich(message: str) -> str:
    """为用户消息注入上下文。

    - DCC Context + Memory Briefing: 仅首条消息注入（不变化的静态信息）
    - Pinned Skills 提示: 每条消息都注入（用户可能中途钉/取消钉）
    """
    global _context_injected
    parts = []

    if not _context_injected:
        _context_injected = True
        parts.append(_build_context_prefix())

    # Pinned hint 每条消息都实时读取（轻量，一句话）
    pinned_hint = _build_pinned_hint()
    if pinned_hint:
        parts.append(pinned_hint)

    if parts:
        return "\n\n".join(parts) + "\n\n" + message
    return message


# ---------------------------------------------------------------------------
# 后台工作线程
# ---------------------------------------------------------------------------

def _chat_worker(message: str, stream_file: str, response_file: str) -> None:
    """在独立线程中运行 asyncio.run()，完成一次完整的聊天请求。"""
    global _session_key
    if not _session_key:
        # 使用 Gateway 规范的 session key 格式: agent:<agentId>:<rest>
        # Gateway 通过 agent: 前缀识别目标 Agent，不用 bindings
        _session_key = f"agent:{_agent_id}:ue-editor:{int(time.time())}"

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

    # Chat 完成后，异步查询 session token 用量并写入独立文件
    # C++ BridgeStatusPoll 周期性读取此文件更新上下文百分比
    _query_session_usage()


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
    """取消当前请求：设置本地 flag + 发送 Gateway chat.abort RPC。

    本地 flag 让 _receive_stream 停止监听并写 [Cancelled]。
    chat.abort RPC 让 Gateway 终止 agent 运行，避免继续消耗资源。
    _receive_stream 内部也会发 abort（通过已有 ws 连接），这里作为安全网
    处理 stream 尚未开始或已退出的情况。
    """
    _cancel_flag.set()
    UELogger.info("[openclaw_chat] cancel flag set")

    # 安全网: 通过独立连接发送 chat.abort
    if _session_key:
        def _abort_bg():
            try:
                asyncio.run(openclaw_ws.do_abort(
                    session_key=_session_key,
                    gateway_url=_get_gateway_url(),
                    token=_get_token(),
                ))
            except Exception as exc:
                UELogger.warning(f"[openclaw_chat] abort bg failed: {exc}")
        t = threading.Thread(target=_abort_bg, daemon=True, name="OCChat-Abort")
        t.start()


def _query_session_usage() -> None:
    """查询当前 session 的 token 用量，写入 _session_usage.json。

    C++ BridgeStatusPoll 读取此文件更新上下文百分比。
    使用 sessions.list Gateway RPC 获取 contextTokens/totalTokens。
    """
    if not _session_key:
        return
    try:
        result_str = asyncio.run(openclaw_ws.do_session_info(
            session_key=_session_key,
            gateway_url=_get_gateway_url(),
            token=_get_token(),
        ))
        # 写入独立文件（C++ 轮询读取）
        import tempfile
        try:
            import unreal
            status_dir = os.path.join(unreal.Paths.project_saved_dir(), "ClawBridge")
        except Exception:
            status_dir = os.path.join(os.path.expanduser("~"), ".artclaw")
        os.makedirs(status_dir, exist_ok=True)

        usage_path = os.path.join(status_dir, "_session_usage.json")
        fd, tmp = tempfile.mkstemp(dir=status_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(result_str)
            os.replace(tmp, usage_path)
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise
        UELogger.info(f"[openclaw_chat] usage written: {result_str[:100]}")
    except Exception as exc:
        UELogger.warning(f"[openclaw_chat] usage query failed: {exc}")


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


# ---------------------------------------------------------------------------
# Agent 切换 + 会话管理 API
# ---------------------------------------------------------------------------

def get_agent_id() -> str:
    """获取当前 Agent ID。"""
    return _agent_id


def set_agent_id(agent_id: str) -> str:
    """切换 Agent，reset session，写入 config。返回 JSON 确认。"""
    global _agent_id, _session_key, _context_injected
    _agent_id = agent_id
    _session_key = None
    _context_injected = False
    # 持久化
    try:
        config = _load_artclaw_config()
        config["last_agent_id"] = agent_id
        _save_artclaw_config(config)
    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_chat] save last_agent_id: {exc}")
    UELogger.info(f"[openclaw_chat] agent switched to: {agent_id}")
    return json.dumps({"ok": True, "agentId": agent_id})


def get_cached_agents() -> str:
    """从 config.json 读取缓存的 Agent 列表（无需网络）。"""
    try:
        config = _load_artclaw_config()
        agents = config.get("agents_cache", [])
        return json.dumps({"agents": agents}, ensure_ascii=False)
    except Exception:
        return json.dumps({"agents": []})


def list_agents(result_file: str) -> None:
    """异步查询 Agent 列表，写入 result_file。同时更新 config.json 缓存。"""
    def _worker():
        try:
            result = asyncio.run(openclaw_ws.do_list_agents(
                gateway_url=_get_gateway_url(),
                token=_get_token(),
            ))
            with open(result_file, "w", encoding="utf-8") as f:
                f.write(result)
            # 更新缓存
            try:
                data = json.loads(result)
                agents = data.get("agents", [])
                if agents:
                    config = _load_artclaw_config()
                    config["agents_cache"] = agents
                    config["agents_cache_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    _save_artclaw_config(config)
            except Exception:
                pass
        except Exception as exc:
            UELogger.mcp_error(f"[openclaw_chat] list_agents: {exc}")
            try:
                with open(result_file, "w", encoding="utf-8") as f:
                    f.write(json.dumps({"agents": [], "error": str(exc)}))
            except Exception:
                pass
    threading.Thread(target=_worker, daemon=True, name="OCListAgents").start()


def fetch_history(session_key: str, result_file: str) -> None:
    """异步从 Gateway 拉取会话历史，写入 result_file。"""
    def _worker():
        try:
            result = asyncio.run(openclaw_ws.do_fetch_history(
                session_key=session_key,
                gateway_url=_get_gateway_url(),
                token=_get_token(),
            ))
            with open(result_file, "w", encoding="utf-8") as f:
                f.write(result)
        except Exception as exc:
            UELogger.mcp_error(f"[openclaw_chat] fetch_history: {exc}")
            try:
                with open(result_file, "w", encoding="utf-8") as f:
                    f.write(json.dumps({"messages": [], "error": str(exc)}))
            except Exception:
                pass
    threading.Thread(target=_worker, daemon=True, name="OCFetchHistory").start()


def _collect_and_save_context(context_file: str) -> None:
    """兼容旧版 C++ 调用。"""
    try:
        with open(context_file, "w", encoding="utf-8") as f:
            f.write(_build_context_prefix())
    except Exception as exc:
        UELogger.mcp_error(f"[openclaw_chat] context write: {exc}")
