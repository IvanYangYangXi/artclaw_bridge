"""
adapter_factory.py — 平台适配器工厂
=====================================
根据平台类型字符串创建对应的 PlatformAdapter 实例。

用法示例::

    from platforms.common.adapter_factory import create_adapter

    # OpenClaw（读取默认配置）
    adapter = create_adapter("openclaw")

    # OpenClaw（显式传参）
    adapter = create_adapter(
        "openclaw",
        gateway_url="ws://127.0.0.1:18789",
        token="your-token",
        agent_id="qi",
    )

    # Claude Desktop MCP 桥接
    adapter = create_adapter("claude", mcp_port=8081)

已支持平台：
  - "openclaw"  — OpenClaw Gateway（WebSocket 直连，OpenClawAdapter）
  - "claude"    — Claude Desktop（stdio→MCP 桥接，ClaudeAdapter，POC）
  - "lobster"   — LobsterAI（基于 OpenClaw 协议，LobsterAdapter）

添加新平台：在 create_adapter() 中添加对应分支，并在 list_platforms() 中
注册平台元信息即可。
"""

from __future__ import annotations

from typing import Any


def create_adapter(platform_type: str, **kwargs: Any):
    """
    根据平台类型创建适配器实例。

    :param platform_type: 平台标识符（大小写不敏感）。
                          支持："openclaw"、"claude"
    :param kwargs:        传递给适配器构造函数的关键字参数。

                          openclaw 可用参数：
                            gateway_url (str)    — Gateway WebSocket URL
                            token (str)          — 认证令牌
                            agent_id (str)       — Agent ID
                            client_id (str)      — 客户端标识
                            logger               — BridgeLogger 兼容实例
                            on_status_changed    — Callable[[bool, str], None]

                          claude 可用参数：
                            mcp_host (str)           — MCP 服务器主机，默认 127.0.0.1
                            mcp_port (int)           — MCP 服务器端口，默认 8080
                            stdio_bridge_path (str)  — artclaw_stdio_bridge.py 路径

    :return: PlatformAdapter 实例
    :raises ValueError: 未知的平台类型
    """
    _type = platform_type.strip().lower()

    if _type == "openclaw":
        from platforms.openclaw.openclaw_adapter import OpenClawAdapter
        return OpenClawAdapter(**kwargs)

    elif _type == "claude":
        from platforms.claude.claude_adapter import ClaudeAdapter
        return ClaudeAdapter(**kwargs)

    elif _type == "lobster":
        from platforms.lobster.lobster_adapter import LobsterAdapter
        return LobsterAdapter(**kwargs)

    else:
        supported = ", ".join(f'"{p}"' for p in list_platforms().keys())
        raise ValueError(
            f"未知的平台类型: {platform_type!r}。\n"
            f"支持的平台: {supported}"
        )


def list_platforms() -> dict[str, dict]:
    """
    返回所有已注册平台的元信息字典。

    :return: {platform_type: {"display_name": str, "status": str, "description": str}}
    """
    return {
        "openclaw": {
            "display_name": "OpenClaw",
            "status": "stable",
            "description": "OpenClaw Gateway（WebSocket 直连），支持完整聊天和工具调用",
            "adapter_class": "platforms.openclaw.openclaw_adapter.OpenClawAdapter",
        },
        "claude": {
            "display_name": "Claude Desktop",
            "status": "poc",
            "description": "Claude Desktop stdio→MCP 桥接，仅工具调用（消息发送 TODO）",
            "adapter_class": "platforms.claude.claude_adapter.ClaudeAdapter",
        },
        "lobster": {
            "display_name": "LobsterAI",
            "status": "stable",
            "description": "LobsterAI 平台（OpenClaw 协议兼容，委托 OpenClawAdapter），支持 MCP Server 注册",
            "adapter_class": "platforms.lobster.lobster_adapter.LobsterAdapter",
        },
    }


def get_platform_info(platform_type: str) -> dict | None:
    """
    获取指定平台的元信息。

    :param platform_type: 平台标识符
    :return: 元信息字典，未找到时返回 None
    """
    return list_platforms().get(platform_type.strip().lower())
