"""
lobster_adapter.py — LobsterAI 平台适配器
==========================================
实现 PlatformAdapter 抽象接口。

LobsterAI 基于 OpenClaw 协议（相同的 WebSocket Gateway），
所有核心通信逻辑通过**组合模式**委托给 OpenClawAdapter，
避免重复代码，保持向后兼容。

额外功能：
  configure_mcp_servers(platforms) — 注册 DCC MCP Servers
      调用 platforms/lobster/setup_lobster_mcp.py 中的实现。
"""

from __future__ import annotations

import os
import sys
from typing import Callable, Optional

# 确保 core/ 可导入
_CORE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from interfaces.platform_adapter import PlatformAdapter  # noqa: E402
from platforms.openclaw.openclaw_adapter import OpenClawAdapter  # noqa: E402


class LobsterAdapter(PlatformAdapter):
    """
    LobsterAI 平台适配器。

    LobsterAI 使用与 OpenClaw 相同的 WebSocket Gateway 协议，
    因此将所有消息/会话/Agent 操作委托给内部的 OpenClawAdapter 实例
    （lazy-created，首次使用时初始化）。

    额外提供 configure_mcp_servers() 方法，用于注册 DCC MCP Servers。
    """

    def __init__(
        self,
        gateway_url: str = "",
        token: str = "",
        agent_id: str = "",
        client_id: str = "lobster-editor",
        logger=None,
        on_status_changed: Optional[Callable[[bool, str], None]] = None,
    ):
        """
        初始化 LobsterAI 适配器。

        :param gateway_url: Gateway WebSocket URL，默认从 bridge_config 读取
        :param token:       认证令牌，默认从 bridge_config 读取
        :param agent_id:    Agent ID
        :param client_id:   客户端标识，默认 "lobster-editor"
        :param logger:      BridgeLogger 兼容实例
        :param on_status_changed: Callable[[bool, str], None]，连接状态变更回调
        """
        self._gateway_url = gateway_url
        self._token = token
        self._agent_id = agent_id
        self._client_id = client_id
        self._logger = logger
        self._on_status_changed = on_status_changed

        # 延迟初始化：首次调用委托方法时才创建 OpenClawAdapter
        self._delegate: Optional[OpenClawAdapter] = None

    # ──────────────────────────────────────────
    # 内部：获取委托实例（lazy-create）
    # ──────────────────────────────────────────

    def _get_delegate(self) -> OpenClawAdapter:
        """懒加载 OpenClawAdapter 委托实例（单例）。"""
        if self._delegate is None:
            self._delegate = OpenClawAdapter(
                gateway_url=self._gateway_url,
                token=self._token,
                agent_id=self._agent_id,
                client_id=self._client_id,
                logger=self._logger,
                on_status_changed=self._on_status_changed,
            )
        return self._delegate

    # ──────────────────────────────────────────
    # P2: 连接管理
    # ──────────────────────────────────────────

    def connect(self, gateway_url: str = "", token: str = "", **kwargs) -> bool:
        """建立连接（委托给 OpenClawAdapter）。"""
        if gateway_url:
            self._gateway_url = gateway_url
            if self._delegate is not None:
                self._delegate._gateway_url = gateway_url
        if token:
            self._token = token
            if self._delegate is not None:
                self._delegate._token = token
        return self._get_delegate().connect(gateway_url, token, **kwargs)

    def disconnect(self) -> None:
        """断开连接（委托给 OpenClawAdapter）。"""
        self._get_delegate().disconnect()

    def is_connected(self) -> bool:
        """检查连接状态（委托给 OpenClawAdapter）。"""
        return self._get_delegate().is_connected()

    # ──────────────────────────────────────────
    # P3: 消息发送
    # ──────────────────────────────────────────

    def send_message(self, message: str, timeout: float = 1800.0) -> str:
        """同步发送消息（委托给 OpenClawAdapter）。"""
        return self._get_delegate().send_message(message, timeout=timeout)

    def send_message_async(self, message: str, callback: Callable[[str], None]) -> None:
        """异步发送消息（委托给 OpenClawAdapter）。"""
        self._get_delegate().send_message_async(message, callback)

    def cancel_current_request(self) -> None:
        """取消当前请求（委托给 OpenClawAdapter）。"""
        self._get_delegate().cancel_current_request()

    # ──────────────────────────────────────────
    # P5: 会话管理
    # ──────────────────────────────────────────

    def reset_session(self) -> None:
        """重置会话（委托给 OpenClawAdapter）。"""
        self._get_delegate().reset_session()

    def set_session_key(self, session_key: str) -> None:
        """设置 session key（委托给 OpenClawAdapter）。"""
        self._get_delegate().set_session_key(session_key)

    def get_session_key(self) -> str:
        """获取当前 session key（委托给 OpenClawAdapter）。"""
        return self._get_delegate().get_session_key()

    # ──────────────────────────────────────────
    # P6: Agent 管理（覆盖基类默认实现，委托）
    # ──────────────────────────────────────────

    def get_agent_id(self) -> str:
        """获取当前 Agent ID（委托给 OpenClawAdapter）。"""
        return self._get_delegate().get_agent_id()

    def list_agents(self) -> list:
        """列出可用 Agent（委托给 OpenClawAdapter）。"""
        return self._get_delegate().list_agents()

    def set_agent(self, agent_id: str) -> None:
        """切换 Agent（委托给 OpenClawAdapter）。"""
        self._agent_id = agent_id
        self._get_delegate().set_agent(agent_id)

    def fetch_history(self, session_key: str, limit: int = 50) -> list:
        """拉取会话历史（委托给 OpenClawAdapter）。"""
        return self._get_delegate().fetch_history(session_key, limit=limit)

    # ──────────────────────────────────────────
    # P7: 诊断
    # ──────────────────────────────────────────

    def diagnose_connection(self, gateway_url: str = "") -> str:
        """运行连接诊断（委托给 OpenClawAdapter）。"""
        return self._get_delegate().diagnose_connection(gateway_url)

    # ──────────────────────────────────────────
    # 平台元信息
    # ──────────────────────────────────────────

    @property
    def platform_type(self) -> str:
        return "lobster"

    @property
    def display_name(self) -> str:
        return "LobsterAI"

    # ──────────────────────────────────────────
    # LobsterAI 专有：MCP Server 注册
    # ──────────────────────────────────────────

    def configure_mcp_servers(self, platforms: list[str] | None = None) -> bool:
        """
        向 LobsterAI 注册 DCC MCP Servers。

        调用 setup_lobster_mcp.py 中的 add_mcp_server() 逻辑。

        :param platforms: 要注册的平台列表，可选值 "ue"、"maya"、"max"。
                          默认为 ["ue"]（仅注册 UE MCP Server）。
        :return: True 表示全部处理成功，False 表示至少一个失败。

        :raises FileNotFoundError: LobsterAI 配置文件不存在
                                   （即 LobsterAI 未安装或从未启动过）
        """
        # 按需导入，避免在 APPDATA 不存在时模块级报错
        from platforms.lobster.setup_lobster_mcp import (  # noqa: E402
            add_mcp_server,
            load_config,
            save_config,
        )

        if platforms is None:
            platforms = ["ue"]

        config = load_config()
        success = True
        for platform in platforms:
            result = add_mcp_server(config, platform)
            if not result:
                success = False
        if success:
            save_config(config)
        return success

    def __repr__(self) -> str:
        connected = self._delegate.is_connected() if self._delegate else False
        return (
            f"<LobsterAdapter platform={self.platform_type!r} "
            f"connected={connected} "
            f"gateway={self._gateway_url or '(from config)'}>"
        )
