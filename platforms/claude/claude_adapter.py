"""
claude_adapter.py — Claude Desktop 平台适配器（POC 桩）
=======================================================
实现 PlatformAdapter 接口的最小可编译桩，标注需要实现的 TODO。

Claude Desktop 通过 stdio→WebSocket 桥接器（artclaw_stdio_bridge.py）与
DCC MCP Server 通信，不走 OpenClaw Gateway，因此「聊天」能力在 Claude
Desktop 端，本端只负责桥接 MCP 工具调用。

当前状态：POC — 仅连接/诊断有部分实现，消息发送返回 NotImplementedError。

参考规范：docs/specs/sdk-platform-adapter-spec.md
"""

from __future__ import annotations

import json
import sys
import os
import socket
from typing import Callable, Optional

# 确保 core/ 可导入
_CORE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "core")
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from interfaces.platform_adapter import PlatformAdapter  # noqa: E402


class ClaudeAdapter(PlatformAdapter):
    """
    Claude Desktop 平台适配器（POC 桩）。

    Claude Desktop 架构：
        Claude Desktop (stdio MCP Client)
          └── artclaw_stdio_bridge.py (stdio 进程)
                └── WebSocket → DCC MCP Server (8080/8081/8082)

    与 OpenClaw 的区别：
    - 传输层：stdio（桥接），而非 WebSocket 直连
    - 聊天面板：Claude Desktop 窗口，非 DCC 内嵌
    - 消息发送：不适用（Claude Desktop 负责聊天）
    - 用途：仅工具调用的 MCP 服务端桥接

    TODO 标注说明哪些方法需要进一步实现。
    """

    # Claude Desktop MCP 桥接默认端口
    _DEFAULT_MCP_WS_PORTS = [8080, 8081, 8082]

    def __init__(
        self,
        mcp_host: str = "127.0.0.1",
        mcp_port: int = 8080,
        stdio_bridge_path: str = "",
    ):
        """
        初始化 Claude 适配器。

        :param mcp_host:          MCP WebSocket 服务器主机，默认 127.0.0.1
        :param mcp_port:          MCP WebSocket 服务器端口，默认 8080
        :param stdio_bridge_path: artclaw_stdio_bridge.py 脚本路径（供启动进程用）
        """
        self._mcp_host = mcp_host
        self._mcp_port = mcp_port
        self._stdio_bridge_path = stdio_bridge_path
        self._session_key: str = ""

        # TODO(Phase N): 持久 MCP WebSocket 连接管理
        self._connected = False

    # ──────────────────────────────────────────
    # P2: 连接管理
    # ──────────────────────────────────────────

    def connect(self, gateway_url: str = "", token: str = "", **kwargs) -> bool:
        """
        检测本地 MCP WebSocket 服务器是否可达。

        Claude Desktop 模式下，"连接" 实际指 stdio 桥接进程是否已启动
        并监听 MCP 端口。此处做 TCP socket 探测。

        TODO: 若需启动 stdio 桥接进程，在此处 Popen artclaw_stdio_bridge.py。
        """
        host = self._mcp_host
        port = self._mcp_port

        # 尝试从 gateway_url 解析（兼容 PlatformAdapter 接口）
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
        """
        标记断开状态。

        TODO: 若在 connect() 中启动了 stdio 桥接进程，在此处终止进程。
        """
        self._connected = False
        self._session_key = ""

    def is_connected(self) -> bool:
        """
        检测本地 MCP 服务是否可达。

        每次调用都做轻量 TCP 探测（Claude Desktop 模式下连接生命周期由外部管理）。
        """
        return self.connect()

    # ──────────────────────────────────────────
    # P3: 消息发送（不适用）
    # ──────────────────────────────────────────

    def send_message(self, message: str, timeout: float = 1800.0) -> str:
        """
        Claude Desktop 模式下，消息发送不由本端负责。

        Claude Desktop 窗口直接接收用户消息并通过 stdio 调用 MCP 工具。
        本适配器不需要/不支持消息发送。

        TODO: 若将来支持 API 模式（Claude API Key），在此实现 HTTP 调用。

        :raises NotImplementedError: Claude Desktop 模式下不支持消息发送
        """
        raise NotImplementedError(
            "ClaudeAdapter 不支持 send_message()。\n"
            "Claude Desktop 模式下，消息发送由 Claude Desktop 客户端负责。\n"
            "若需要通过 API 发送消息，请实现 Claude API Key 模式（TODO）。"
        )

    def send_message_async(self, message: str, callback: Callable[[str], None]) -> None:
        """
        不支持异步消息发送。

        TODO: 同 send_message()，API Key 模式下可实现。

        :raises NotImplementedError: Claude Desktop 模式下不支持消息发送
        """
        raise NotImplementedError(
            "ClaudeAdapter 不支持 send_message_async()。原因同 send_message()。"
        )

    def cancel_current_request(self) -> None:
        """
        取消当前请求（无操作，Claude Desktop 自行管理）。

        TODO: API Key 模式下，此处可发送取消信号。
        """
        pass  # Claude Desktop 模式无需取消，noop

    # ──────────────────────────────────────────
    # P5: 会话管理
    # ──────────────────────────────────────────

    def reset_session(self) -> None:
        """
        重置会话。

        Claude Desktop 模式下，会话由 Claude Desktop 管理，此处仅重置本地标记。
        TODO: 若启动了 stdio 桥接进程，发送重置信号或重启进程。
        """
        self._session_key = ""

    def set_session_key(self, session_key: str) -> None:
        """
        设置会话标识（本地记录，暂不传递给 Claude Desktop）。

        TODO: API Key 模式下，将 session_key 对应到对话线程 ID。
        """
        self._session_key = session_key

    def get_session_key(self) -> str:
        """获取当前会话标识。"""
        return self._session_key

    # ──────────────────────────────────────────
    # P6: Agent 管理（不适用）
    # ──────────────────────────────────────────

    def get_agent_id(self) -> str:
        """
        Claude Desktop 无多 Agent 概念，返回固定标识。

        TODO: 若将来接入 Claude Projects，在此返回 Project ID。
        """
        return "claude"

    def list_agents(self) -> list:
        """
        Claude Desktop 无多 Agent 概念，返回空列表。

        TODO: 接入 Claude Projects API 后实现。
        """
        return []

    def set_agent(self, agent_id: str) -> None:
        """
        Claude Desktop 不支持多 Agent 切换。

        TODO: 接入 Claude Projects API 后实现。
        """
        pass  # noop

    # ──────────────────────────────────────────
    # P7: 诊断
    # ──────────────────────────────────────────

    def diagnose_connection(self, gateway_url: str = "") -> str:
        """
        诊断 Claude Desktop MCP 桥接连接状态。

        检查本地 MCP WebSocket 服务器端口可达性，并输出 stdio 桥接建议。
        """
        lines = ["=" * 60, "  Claude Desktop MCP 桥接诊断", "=" * 60]

        # 检测 MCP 端口
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

        # 检测 stdio 桥接脚本
        lines.append("\n[2/3] stdio 桥接脚本...")
        bridge_path = self._stdio_bridge_path or self._find_stdio_bridge()
        if bridge_path and os.path.exists(bridge_path):
            lines.append(f"  ✅ 脚本存在: {bridge_path}")
        else:
            lines.append("  ⚠️  artclaw_stdio_bridge.py 未找到")
            lines.append("     修复: 确认 platforms/common/artclaw_stdio_bridge.py 路径")

        # Claude Desktop 配置提示
        lines.append("\n[3/3] Claude Desktop 配置...")
        config_path = self._find_claude_config()
        if config_path and os.path.exists(config_path):
            lines.append(f"  ✅ Claude Desktop 配置文件存在: {config_path}")
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if "mcpServers" in cfg:
                    servers = list(cfg["mcpServers"].keys())
                    lines.append(f"  ✅ 已配置 MCP Server: {', '.join(servers)}")
                else:
                    lines.append("  ⚠️  配置文件中未找到 mcpServers 键")
                    lines.append("     修复: 参考 platforms/claude/config/claude-config-snippet.json")
            except Exception as e:
                lines.append(f"  ⚠️  配置文件解析失败: {e}")
        else:
            lines.append("  ℹ️  Claude Desktop 配置文件未找到（可能未安装）")
            lines.append("     路径: %APPDATA%\\Claude\\claude_desktop_config.json (Windows)")

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
        return "claude"

    @property
    def display_name(self) -> str:
        return "Claude Desktop"

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

    def _find_claude_config(self) -> str:
        """查找 Claude Desktop 配置文件路径。"""
        # Windows
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            win_path = os.path.join(appdata, "Claude", "claude_desktop_config.json")
            if os.path.exists(win_path):
                return win_path

        # macOS
        home = os.path.expanduser("~")
        mac_path = os.path.join(
            home, "Library", "Application Support", "Claude", "claude_desktop_config.json"
        )
        if os.path.exists(mac_path):
            return mac_path

        return ""

    def __repr__(self) -> str:
        return (
            f"<ClaudeAdapter platform={self.platform_type!r} "
            f"mcp={self._mcp_host}:{self._mcp_port}>"
        )
