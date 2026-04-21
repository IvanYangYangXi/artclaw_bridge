"""
PlatformAdapter — Agent 平台适配器抽象基类

所有 AI 平台（OpenClaw、Claude、LobsterAI 等）的适配器均应继承此基类，
以确保跨平台接口一致性，支持平台热切换。

参考规范：docs/specs/sdk-platform-adapter-spec.md
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable, Any


class PlatformAdapter(ABC):
    """
    Agent 平台适配器抽象基类。

    实现此接口以支持新的 AI 平台接入。
    接口分为以下职责组：
    - P2: 连接管理
    - P3: 消息发送与流式处理
    - P5: 会话管理
    - P6: Agent 管理（可选）
    - P7: 诊断与健康检查
    """

    # ──────────────────────────────────────────
    # P2: 连接管理
    # ──────────────────────────────────────────

    @abstractmethod
    def connect(self, gateway_url: str, token: str, **kwargs) -> bool:
        """
        建立与 AI 平台的连接。

        :param gateway_url: 网关 URL（WebSocket 或其他协议）
        :param token: 认证令牌
        :param kwargs: 平台特定的连接参数（client_id、agent_id 等）
        :return: True 表示连接成功，False 表示失败
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """断开与 AI 平台的连接，释放相关资源。"""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """
        检查当前连接状态。

        :return: True 表示已连接，False 表示未连接
        """
        ...

    # ──────────────────────────────────────────
    # P3: 消息发送与流式处理
    # ──────────────────────────────────────────

    @abstractmethod
    def send_message(self, message: str, timeout: float = 1800.0) -> str:
        """
        同步发送消息并等待完整回复。

        :param message: 用户消息文本
        :param timeout: 等待超时秒数（默认 30 分钟）
        :return: AI 回复文本
        :raises TimeoutError: 超过 timeout 未收到完整回复
        :raises ConnectionError: 发送时连接断开
        """
        ...

    @abstractmethod
    def send_message_async(self, message: str, callback: Callable[[str], None]) -> None:
        """
        异步发送消息，通过回调接收回复。

        :param message: 用户消息文本
        :param callback: 回调函数，接收完整回复文本
        """
        ...

    @abstractmethod
    def cancel_current_request(self) -> None:
        """取消当前正在进行的消息请求。"""
        ...

    # ──────────────────────────────────────────
    # P5: 会话管理
    # ──────────────────────────────────────────

    @abstractmethod
    def reset_session(self) -> None:
        """
        重置当前会话，开始全新对话。
        清除会话上下文、历史记录等状态。
        """
        ...

    @abstractmethod
    def set_session_key(self, session_key: str) -> None:
        """
        设置会话标识符，用于恢复已有对话。

        :param session_key: 会话唯一标识
        """
        ...

    @abstractmethod
    def get_session_key(self) -> str:
        """
        获取当前会话标识符。

        :return: 当前会话 key，若无会话返回空字符串
        """
        ...

    # ──────────────────────────────────────────
    # P6: Agent 管理（可选，提供默认空实现）
    # ──────────────────────────────────────────

    def get_agent_id(self) -> str:
        """
        获取当前使用的 Agent ID。

        :return: Agent ID 字符串；不支持多 Agent 的平台返回空字符串
        """
        return ""

    def list_agents(self) -> list:
        """
        列出平台上所有可用的 Agent。

        :return: Agent 信息字典列表，格式：[{"id": str, "name": str, ...}]
                 不支持多 Agent 的平台返回空列表
        """
        return []

    def set_agent(self, agent_id: str) -> None:
        """
        切换到指定 Agent。

        :param agent_id: 目标 Agent 的 ID
        :raises ValueError: agent_id 无效或平台不支持多 Agent
        """
        pass

    def fetch_history(self, session_key: str, limit: int = 50) -> list:
        """
        获取指定会话的历史记录。

        :param session_key: 会话标识符
        :param limit: 最多返回的消息数量
        :return: 消息字典列表，格式：[{"role": str, "content": str, "timestamp": float}]
                 不支持历史查询的平台返回空列表
        """
        return []

    # ──────────────────────────────────────────
    # P7: 诊断与健康检查
    # ──────────────────────────────────────────

    @abstractmethod
    def diagnose_connection(self, gateway_url: str) -> str:
        """
        诊断到指定网关 URL 的连接状况。

        :param gateway_url: 目标网关 URL
        :return: 人类可读的诊断报告文本
        """
        ...

    # ──────────────────────────────────────────
    # 平台元信息
    # ──────────────────────────────────────────

    @property
    @abstractmethod
    def platform_type(self) -> str:
        """
        平台类型标识符。

        :return: 平台类型字符串，如 "openclaw"、"claude"、"lobster"
        """
        ...

    @property
    def display_name(self) -> str:
        """
        平台显示名称（用于 UI）。

        :return: 人类可读的平台名称，默认使用 platform_type
        """
        return self.platform_type
