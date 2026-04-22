"""
adapter_factory.py — 平台适配器工厂
=====================================
根据平台类型字符串创建对应的 PlatformAdapter 实例。

用法示例::

    from platforms.common.adapter_factory import create_adapter

    # OpenClaw（读取默认配置）
    adapter = create_adapter("openclaw")

    # OpenClaw（显式传参，通常不需要——自动从配置文件解析）
    adapter = create_adapter(
        "openclaw",
        gateway_url="ws://127.0.0.1:18789",
        token="your-token",
        agent_id="your-agent",
    )

    # Claude Code（stdio MCP 桥接）
    adapter = create_adapter("claudecode")

已支持平台：
  - "openclaw"    — OpenClaw Gateway（WebSocket 直连，OpenClawAdapter）
  - "lobster"     — LobsterAI（基于 OpenClaw 协议，LobsterAdapter）
  - "claudecode"  — Claude Code（stdio→MCP 桥接，ClaudeCodeAdapter，POC）
  - "cursor"      — Cursor IDE（stdio→MCP 桥接，CursorAdapter，POC）
  - "workbuddy"   — WorkBuddy（stdio→MCP 桥接，WorkBuddyAdapter，POC）

添加新平台：在 create_adapter() 中添加对应分支，并在 list_platforms() 中
注册平台元信息即可。
"""

from __future__ import annotations

from typing import Any


def create_adapter(platform_type: str, **kwargs: Any):
    """
    根据平台类型创建适配器实例。

    :param platform_type: 平台标识符（大小写不敏感）。
                          支持："openclaw"、"lobster"、"claudecode"、"cursor"、"workbuddy"
    :param kwargs:        传递给适配器构造函数的关键字参数。

                          openclaw 可用参数：
                            gateway_url (str)    — Gateway WebSocket URL
                            token (str)          — 认证令牌
                            agent_id (str)       — Agent ID
                            client_id (str)      — 客户端标识
                            logger               — BridgeLogger 兼容实例
                            on_status_changed    — Callable[[bool, str], None]

    :return: PlatformAdapter 实例
    :raises ValueError: 未知的平台类型
    """
    _type = platform_type.strip().lower()

    if _type == "openclaw":
        from platforms.openclaw.openclaw_adapter import OpenClawAdapter
        return OpenClawAdapter(**kwargs)

    elif _type == "lobster":
        from platforms.lobster.lobster_adapter import LobsterAdapter
        return LobsterAdapter(**kwargs)

    elif _type == "claudecode":
        from platforms.claudecode.claudecode_adapter import ClaudeCodeAdapter
        return ClaudeCodeAdapter(**kwargs)

    elif _type == "cursor":
        from platforms.cursor.cursor_adapter import CursorAdapter
        return CursorAdapter(**kwargs)

    elif _type == "workbuddy":
        from platforms.workbuddy.workbuddy_adapter import WorkBuddyAdapter
        return WorkBuddyAdapter(**kwargs)

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
        "lobster": {
            "display_name": "LobsterAI",
            "status": "stable",
            "description": "LobsterAI 平台（OpenClaw 协议兼容，委托 OpenClawAdapter），支持 MCP Server 注册",
            "adapter_class": "platforms.lobster.lobster_adapter.LobsterAdapter",
        },
        "claudecode": {
            "display_name": "Claude Code",
            "status": "poc",
            "description": "Claude Code CLI stdio→MCP 桥接，仅工具调用（MCP-only）",
            "adapter_class": "platforms.claudecode.claudecode_adapter.ClaudeCodeAdapter",
        },
        "cursor": {
            "display_name": "Cursor",
            "status": "poc",
            "description": "Cursor IDE stdio→MCP 桥接，仅工具调用（MCP-only）",
            "adapter_class": "platforms.cursor.cursor_adapter.CursorAdapter",
        },
        "workbuddy": {
            "display_name": "WorkBuddy",
            "status": "poc",
            "description": "WorkBuddy 平台 stdio→MCP 桥接，仅工具调用（MCP-only）",
            "adapter_class": "platforms.workbuddy.workbuddy_adapter.WorkBuddyAdapter",
        },
    }


def get_platform_info(platform_type: str) -> dict | None:
    """
    获取指定平台的元信息。

    :param platform_type: 平台标识符
    :return: 元信息字典，未找到时返回 None
    """
    return list_platforms().get(platform_type.strip().lower())
