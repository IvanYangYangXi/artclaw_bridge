"""
openclaw_adapter.py — OpenClaw 平台适配器
==========================================
实现 PlatformAdapter 抽象接口，通过委托模式包装
openclaw_chat.py 和 bridge_core.py 中的现有实现。

不修改任何已有文件；所有行为均通过委托调用现有函数实现。

参考规范：docs/specs/sdk-platform-adapter-spec.md
"""

from __future__ import annotations

import json
import sys
import os
from typing import Callable, Optional

# 确保 core/ 可导入
_CORE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from interfaces.platform_adapter import PlatformAdapter  # noqa: E402


class OpenClawAdapter(PlatformAdapter):
    """
    OpenClaw 平台适配器。

    将 PlatformAdapter 接口委托给以下现有实现：
    - `bridge_core.OpenClawBridge`（连接/消息/会话，WebSocket 持久连接）
    - `openclaw_chat` 模块（文件协议、Agent 管理、诊断）

    根据使用场景自动选择实现层：
    - 若仅需「轻量探测」（connect/is_connected/diagnose），使用 openclaw_chat 中的
      socket 探测函数，不维护 WebSocket 持久连接。
    - 若需要完整聊天（send_message），使用 OpenClawBridge。

    回调均通过构造函数参数注入，不修改已有代码。
    """

    def __init__(
        self,
        gateway_url: str = "",
        token: str = "",
        agent_id: str = "",
        client_id: str = "",
        logger=None,
        on_status_changed: Optional[Callable[[bool, str], None]] = None,
    ):
        """
        初始化 OpenClaw 适配器。

        :param gateway_url: Gateway WebSocket URL，默认从 bridge_config 读取
        :param token:       认证令牌，默认从 bridge_config 读取
        :param agent_id:    Agent ID，默认从 ~/.artclaw/config.json 读取
        :param client_id:   客户端标识（如 "ue-editor"），默认 "ue-editor"
        :param logger:      BridgeLogger 兼容实例；为 None 时使用默认 BridgeLogger
        :param on_status_changed: Callable[[bool, str], None]，连接状态变更回调
        """
        self._gateway_url = gateway_url
        self._token = token
        self._agent_id = agent_id
        self._client_id = client_id
        self._logger = logger
        self._on_status_changed = on_status_changed

        # 延迟初始化：首次 send_message / connect(full=True) 时才创建
        self._bridge: Optional[object] = None  # OpenClawBridge 实例

    # ──────────────────────────────────────────
    # P2: 连接管理
    # ──────────────────────────────────────────

    def connect(self, gateway_url: str = "", token: str = "", **kwargs) -> bool:
        """
        测试 Gateway 可达性（socket 探测，不建立持久 WebSocket）。

        若 kwargs 中包含 `full=True`，则改用 OpenClawBridge.start() 建立
        持久连接（会话聊天前需调用一次）。
        """
        if gateway_url:
            self._gateway_url = gateway_url
        if token:
            self._token = token

        if kwargs.get("full", False):
            # 完整 WebSocket 连接（用于聊天会话）
            bridge = self._get_bridge()
            return bridge.start()

        # 轻量 TCP 探测（用于状态检测）
        try:
            import openclaw_chat
            return openclaw_chat.connect(self._gateway_url, self._token)
        except ImportError:
            # fallback：直接 socket 探测
            import socket
            import urllib.parse
            url = self._gateway_url or self._resolve_gateway_url()
            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 18789
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            try:
                s.connect((host, port))
                return True
            except Exception:
                return False
            finally:
                try:
                    s.close()
                except Exception:
                    pass

    def disconnect(self) -> None:
        """断开连接并重置会话状态。"""
        if self._bridge is not None:
            try:
                self._bridge.stop()
            except Exception:
                pass
            self._bridge = None

        # 同步重置 openclaw_chat 模块全局状态（若已导入）
        try:
            import openclaw_chat
            openclaw_chat.disconnect()
        except ImportError:
            pass

    def is_connected(self) -> bool:
        """检查当前连接状态（socket 探测）。"""
        # 若有持久连接，优先查询其状态
        if self._bridge is not None:
            try:
                return self._bridge.is_connected()
            except Exception:
                pass

        # 否则做轻量 TCP 探测
        return self.connect()

    # ──────────────────────────────────────────
    # P3: 消息发送
    # ──────────────────────────────────────────

    def send_message(self, message: str, timeout: float = 1800.0) -> str:
        """
        同步发送消息，等待完整 AI 回复。

        委托给 OpenClawBridge.send_message()（持久 WebSocket 模式）。
        """
        bridge = self._get_bridge()
        return bridge.send_message(message, timeout=timeout)

    def send_message_async(self, message: str, callback: Callable[[str], None]) -> None:
        """
        异步发送消息，回复时调用 callback。

        委托给 OpenClawBridge.send_message_async()。
        """
        bridge = self._get_bridge()
        bridge.send_message_async(message, callback)

    def cancel_current_request(self) -> None:
        """取消当前请求。"""
        if self._bridge is not None:
            try:
                self._bridge.cancel_current()
                return
            except Exception:
                pass

        # fallback：通过 openclaw_chat 模块取消
        try:
            import openclaw_chat
            openclaw_chat.cancel_current_request()
        except ImportError:
            pass

    # ──────────────────────────────────────────
    # P5: 会话管理
    # ──────────────────────────────────────────

    def reset_session(self) -> None:
        """重置会话，清除 session key。"""
        if self._bridge is not None:
            try:
                self._bridge.reset_session()
            except Exception:
                pass

        try:
            import openclaw_chat
            openclaw_chat.reset_session()
        except ImportError:
            pass

    def set_session_key(self, session_key: str) -> None:
        """设置 session key（用于恢复已有对话）。"""
        if self._bridge is not None:
            try:
                self._bridge.set_session_key(session_key)
            except Exception:
                pass

        try:
            import openclaw_chat
            openclaw_chat.set_session_key(session_key)
        except ImportError:
            pass

    def get_session_key(self) -> str:
        """获取当前 session key。"""
        if self._bridge is not None:
            try:
                return self._bridge.get_session_key()
            except Exception:
                pass

        try:
            import openclaw_chat
            return openclaw_chat.get_session_key()
        except ImportError:
            return ""

    # ──────────────────────────────────────────
    # P6: Agent 管理
    # ──────────────────────────────────────────

    def get_agent_id(self) -> str:
        """获取当前 Agent ID。"""
        if self._bridge is not None:
            try:
                return self._bridge.get_agent_id()
            except Exception:
                pass

        try:
            import openclaw_chat
            return openclaw_chat.get_agent_id()
        except ImportError:
            return self._agent_id or ""

    def list_agents(self) -> list:
        """
        列出可用 Agent（同步，需已建立持久连接）。

        :return: [{"id": str, "name": str, "emoji": str}, ...]
        """
        bridge = self._get_bridge()
        return bridge.list_agents()

    def set_agent(self, agent_id: str) -> None:
        """切换 Agent，重置 session。"""
        self._agent_id = agent_id

        if self._bridge is not None:
            try:
                self._bridge.set_agent(agent_id)
            except Exception:
                pass

        try:
            import openclaw_chat
            openclaw_chat.set_agent_id(agent_id)
        except ImportError:
            pass

    def fetch_history(self, session_key: str, limit: int = 50) -> list:
        """
        从 Gateway 拉取会话历史（委托给 OpenClawBridge）。

        :return: [{"sender": "user"|"assistant"|"system", "content": str}, ...]
        """
        bridge = self._get_bridge()
        try:
            return bridge.fetch_history(session_key, limit=limit)
        except Exception:
            return []

    # ──────────────────────────────────────────
    # P7: 诊断
    # ──────────────────────────────────────────

    def diagnose_connection(self, gateway_url: str = "") -> str:
        """
        运行完整的连接诊断报告。

        委托给 openclaw_chat.diagnose_connection()（调用 openclaw_diagnose 模块）。
        """
        url = gateway_url or self._gateway_url or self._resolve_gateway_url()
        token = self._token or self._resolve_token()

        try:
            import openclaw_chat
            return openclaw_chat.diagnose_connection(url, token)
        except ImportError:
            pass

        # 最后尝试直接调用 openclaw_diagnose
        try:
            import importlib
            import openclaw_diagnose
            importlib.reload(openclaw_diagnose)
            return openclaw_diagnose.diagnose_connection(url, token)
        except ImportError:
            return (
                f"[Error] 诊断模块不可用。\n"
                f"目标 URL: {url}\n"
                f"提示: openclaw_diagnose.py 未找到"
            )

    # ──────────────────────────────────────────
    # 平台元信息
    # ──────────────────────────────────────────

    @property
    def platform_type(self) -> str:
        return "openclaw"

    @property
    def display_name(self) -> str:
        return "OpenClaw"

    # ──────────────────────────────────────────
    # 内部工具
    # ──────────────────────────────────────────

    def _get_bridge(self):
        """
        懒加载 OpenClawBridge 实例（单例）。

        首次调用时导入 bridge_core 并创建实例。
        """
        if self._bridge is None:
            # bridge_core.py 位于 core/ 目录，已加入 sys.path
            from bridge_core import OpenClawBridge, BridgeLogger  # noqa: E402

            logger_instance = self._logger
            if logger_instance is None:
                logger_instance = BridgeLogger()

            self._bridge = OpenClawBridge(
                gateway_url=self._gateway_url or "",
                agent_id=self._agent_id or "",
                token=self._token or "",
                client_id=self._client_id or "ue-editor",
                logger=logger_instance,
                on_status_changed=self._on_status_changed,
            )
        return self._bridge

    def _resolve_gateway_url(self) -> str:
        """从 bridge_config 读取 Gateway URL（容错）。"""
        try:
            from bridge_config import get_gateway_url
            return get_gateway_url()
        except Exception:
            return "ws://127.0.0.1:18789"

    def _resolve_token(self) -> str:
        """从 bridge_config 读取认证 Token（容错）。"""
        try:
            from bridge_config import get_gateway_token
            return get_gateway_token()
        except Exception:
            return ""

    def __repr__(self) -> str:
        connected = self._bridge.is_connected() if self._bridge else False
        return (
            f"<OpenClawAdapter platform={self.platform_type!r} "
            f"connected={connected} "
            f"gateway={self._gateway_url or '(from config)'}>"
        )
