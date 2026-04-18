"""
cursor_adapter.py — Cursor 平台适配器（MCP-only）
===================================================
实现 PlatformAdapter 接口。

Cursor 是 AI 驱动的代码编辑器（IDE），通过 stdio→WebSocket 桥接器
（artclaw_stdio_bridge.py）与 DCC MCP Server 通信。
聊天在 Cursor 编辑器中进行，本端仅负责 MCP 工具调用桥接。

配置文件位置：
  - 全局：~/.cursor/mcp.json
  - 项目级：{project}/.cursor/mcp.json

参考规范：docs/specs/sdk-platform-adapter-spec.md
"""

from __future__ import annotations

import json
import os
import socket
import sys
from typing import Callable, Optional

# 确保 core/ 可导入
_CORE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from interfaces.platform_adapter import PlatformAdapter  # noqa: E402


class CursorAdapter(PlatformAdapter):
    """
    Cursor 平台适配器（MCP-only）。

    Cursor 架构：
        Cursor IDE (stdio MCP Client)
          └── artclaw_stdio_bridge.py (stdio 进程)
                └── WebSocket → DCC MCP Server (8080-8087)

    Cursor 支持全局和项目级 MCP 配置：
    - 全局：~/.cursor/mcp.json
    - 项目级：{project}/.cursor/mcp.json
    """

    # MCP 桥接默认端口（所有 DCC）
    _DEFAULT_MCP_WS_PORTS = [8080, 8081, 8082, 8083, 8084, 8085, 8086, 8087]

    def __init__(
        self,
        mcp_host: str = "127.0.0.1",
        mcp_port: int = 8080,
        stdio_bridge_path: str = "",
    ):
        """
        初始化 Cursor 适配器。

        :param mcp_host:          MCP WebSocket 服务器主机，默认 127.0.0.1
        :param mcp_port:          MCP WebSocket 服务器端口，默认 8080
        :param stdio_bridge_path: artclaw_stdio_bridge.py 脚本路径
        """
        self._mcp_host = mcp_host
        self._mcp_port = mcp_port
        self._stdio_bridge_path = stdio_bridge_path
        self._session_key: str = ""
        self._connected = False

    # ──────────────────────────────────────────
    # P2: 连接管理
    # ──────────────────────────────────────────

    def connect(self, gateway_url: str = "", token: str = "", **kwargs) -> bool:
        """
        检测本地 MCP WebSocket 服务器是否可达。

        Cursor 模式下，"连接" 指 DCC MCP 端口是否已监听。
        此处做 TCP socket 探测。
        """
        host = self._mcp_host
        port = self._mcp_port

        if gateway_url:
            try:
                import urllib.parse
                parsed = urllib.parse.urlparse(gateway_url)
                host = parsed.hostname or host
                port = parsed.port or port
            except Exception:
                pass

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        try:
            s.connect((host, port))
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False
        finally:
            try:
                s.close()
            except Exception:
                pass

    def disconnect(self) -> None:
        """标记断开状态。"""
        self._connected = False
        self._session_key = ""

    def is_connected(self) -> bool:
        """检测本地 MCP 服务是否可达（TCP 探测）。"""
        return self.connect()

    # ──────────────────────────────────────────
    # P3: 消息发送（不适用）
    # ──────────────────────────────────────────

    def send_message(self, message: str, timeout: float = 1800.0) -> str:
        """
        Cursor 模式下不支持消息发送。

        聊天在 Cursor 编辑器中进行，本适配器仅负责 MCP 工具桥接。

        :raises NotImplementedError: Cursor 模式下不支持消息发送
        """
        raise NotImplementedError(
            "CursorAdapter 不支持 send_message()。\n"
            "Cursor 模式下，消息发送由 Cursor 编辑器负责。"
        )

    def send_message_async(self, message: str, callback: Callable[[str], None]) -> None:
        """
        不支持异步消息发送。

        :raises NotImplementedError: Cursor 模式下不支持消息发送
        """
        raise NotImplementedError(
            "CursorAdapter 不支持 send_message_async()。原因同 send_message()。"
        )

    def cancel_current_request(self) -> None:
        """取消当前请求（无操作）。"""
        pass

    # ──────────────────────────────────────────
    # P5: 会话管理
    # ──────────────────────────────────────────

    def reset_session(self) -> None:
        """重置会话（仅重置本地标记）。"""
        self._session_key = ""

    def set_session_key(self, session_key: str) -> None:
        """设置会话标识。"""
        self._session_key = session_key

    def get_session_key(self) -> str:
        """获取当前会话标识。"""
        return self._session_key

    # ──────────────────────────────────────────
    # P6: Agent 管理（不适用）
    # ──────────────────────────────────────────

    def get_agent_id(self) -> str:
        """Cursor 无多 Agent 概念，返回固定标识。"""
        return "cursor"

    def list_agents(self) -> list:
        """Cursor 无多 Agent 概念，返回空列表。"""
        return []

    def set_agent(self, agent_id: str) -> None:
        """Cursor 不支持多 Agent 切换。"""
        pass

    # ──────────────────────────────────────────
    # P7: 诊断
    # ──────────────────────────────────────────

    def diagnose_connection(self, gateway_url: str = "") -> str:
        """
        诊断 Cursor MCP 桥接连接状态。

        检查：MCP 端口可达性、stdio 桥接脚本、Cursor 配置文件。
        """
        lines = ["=" * 60, "  Cursor MCP 桥接诊断", "=" * 60]

        # [1/3] 检测 MCP 端口
        ports_to_check = [self._mcp_port] + [
            p for p in self._DEFAULT_MCP_WS_PORTS if p != self._mcp_port
        ]
        active_ports = []

        lines.append("\n[1/3] MCP WebSocket 端口扫描 (127.0.0.1)...")
        for port in ports_to_check:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            try:
                s.connect(("127.0.0.1", port))
                lines.append(f"  ✅ 端口 {port} 可达 (MCP 服务已启动)")
                active_ports.append(port)
            except Exception:
                lines.append(f"  ⚠️  端口 {port} 不可达")
            finally:
                try:
                    s.close()
                except Exception:
                    pass

        # [2/3] 检测 stdio 桥接脚本
        lines.append("\n[2/3] stdio 桥接脚本...")
        bridge_path = self._stdio_bridge_path or self._find_stdio_bridge()
        if bridge_path and os.path.exists(bridge_path):
            lines.append(f"  ✅ 脚本存在: {bridge_path}")
        else:
            lines.append("  ⚠️  artclaw_stdio_bridge.py 未找到")
            lines.append("     修复: 确认 platforms/common/artclaw_stdio_bridge.py 路径")

        # [3/3] Cursor 配置
        lines.append("\n[3/3] Cursor MCP 配置...")
        config_paths = self._find_cursor_configs()
        if config_paths:
            for label, path in config_paths:
                lines.append(f"  ✅ {label}: {path}")
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    servers = cfg.get("mcpServers", {})
                    if servers:
                        artclaw_servers = [k for k in servers if k.startswith("artclaw-")]
                        if artclaw_servers:
                            lines.append(f"     已配置 ArtClaw MCP Server: {', '.join(artclaw_servers)}")
                        else:
                            lines.append("     ⚠️  未找到 artclaw-* MCP Server 配置")
                    else:
                        lines.append("     ⚠️  配置文件中未找到 mcpServers 键")
                except Exception as e:
                    lines.append(f"     ⚠️  配置文件解析失败: {e}")
        else:
            lines.append("  ℹ️  Cursor MCP 配置文件未找到")
            lines.append("     全局配置: ~/.cursor/mcp.json")
            lines.append("     项目配置: {project}/.cursor/mcp.json")

        # 汇总
        lines.append("\n" + "=" * 60)
        if active_ports:
            lines.append(f"  ✅ MCP 服务运行中 (端口: {', '.join(str(p) for p in active_ports)})")
        else:
            lines.append("  ⚠️  未检测到活跃的 MCP 服务。请确认 DCC 端 MCP Server 已启动。")
        lines.append("=" * 60)

        return "\n".join(lines)

    # ──────────────────────────────────────────
    # 平台元信息
    # ──────────────────────────────────────────

    @property
    def platform_type(self) -> str:
        return "cursor"

    @property
    def display_name(self) -> str:
        return "Cursor"

    # ──────────────────────────────────────────
    # 内部工具
    # ──────────────────────────────────────────

    def _find_stdio_bridge(self) -> str:
        """搜索 artclaw_stdio_bridge.py 的常见位置。"""
        candidates = [
            os.path.join(os.path.dirname(__file__), "..", "common", "artclaw_stdio_bridge.py"),
            os.path.join(os.path.dirname(__file__), "..", "..", "platforms", "common", "artclaw_stdio_bridge.py"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return os.path.abspath(c)
        return ""

    def _find_cursor_configs(self) -> list:
        """
        查找 Cursor MCP 配置文件。
        返回 [(label, path), ...] 列表。
        """
        found = []
        home = os.path.expanduser("~")

        # 全局配置：~/.cursor/mcp.json
        global_config = os.path.join(home, ".cursor", "mcp.json")
        if os.path.exists(global_config):
            found.append(("全局配置 (~/.cursor/mcp.json)", global_config))

        # 项目级配置：{cwd}/.cursor/mcp.json
        cwd_config = os.path.join(os.getcwd(), ".cursor", "mcp.json")
        if os.path.exists(cwd_config):
            found.append(("项目配置 (.cursor/mcp.json)", cwd_config))

        return found

    def __repr__(self) -> str:
        return (
            f"<CursorAdapter platform={self.platform_type!r} "
            f"mcp={self._mcp_host}:{self._mcp_port}>"
        )
