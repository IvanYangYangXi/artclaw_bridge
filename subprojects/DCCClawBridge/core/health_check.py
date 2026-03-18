"""
health_check.py - DCCClawBridge 环境健康检查
=============================================

从 UEClawBridge 的 health_check.py 移植，适配 DCC 环境。
检查项：Python 环境 / 依赖 / DCC 环境 / MCP Server / Gateway / 文件系统
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import socket
import sys
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger("artclaw.health")


class CheckResult:
    def __init__(self, name: str):
        self.name = name
        self.status = "pending"
        self.messages: list[str] = []
        self.is_error = False
        self.is_warning = False

    def ok(self, msg: str):
        self.status = "ok"
        self.messages.append(f"✅ {msg}")

    def fail(self, msg: str):
        self.status = "fail"
        self.is_error = True
        self.messages.append(f"❌ {msg}")

    def warn(self, msg: str):
        self.status = "warn"
        self.is_warning = True
        self.messages.append(f"⚠️  {msg}")

    def info(self, msg: str):
        self.messages.append(f"   {msg}")

    def skip(self, msg: str):
        self.status = "skip"
        self.messages.append(f"⏭️  {msg}")

    def __str__(self):
        lines = [self.name]
        for m in self.messages:
            lines.append(f"  {m}")
        return "\n".join(lines)


def _check_python():
    r = CheckResult("Python 环境")
    v = sys.version_info
    r.info(f"Python {v.major}.{v.minor}.{v.micro}")
    r.info(f"Executable: {sys.executable}")
    if v.major == 3 and v.minor >= 9:
        r.ok(f"Python {v.major}.{v.minor} (>= 3.9)")
    else:
        r.fail(f"Python {v.major}.{v.minor} < 3.9")
    return r


def _check_dependencies():
    r = CheckResult("Python 依赖")
    deps = [("websockets", "10.0"), ("PySide2", None)]
    for pkg, min_ver in deps:
        try:
            mod = importlib.import_module(pkg)
            ver = getattr(mod, "__version__", "?")
            r.info(f"{pkg} {ver}")
        except ImportError:
            if pkg == "PySide2":
                r.warn(f"{pkg} 未找到 (DCC 内置应有)")
            else:
                r.fail(f"{pkg} 未安装")
    if not r.is_error:
        r.ok("所有依赖已就绪")
    return r


def _check_mcp_server():
    r = CheckResult("MCP Server")
    try:
        from core.mcp_server import get_mcp_server
        server = get_mcp_server()
        if server and server.is_running:
            r.ok(f"运行中: {server.server_address}")
            r.info(f"已注册工具: {len(server._tools)}")
            for name in sorted(server._tools.keys()):
                r.info(f"  - {name}")
        else:
            r.warn("MCP Server 未运行")
    except Exception as e:
        r.fail(f"检查失败: {e}")
    return r


def _check_gateway():
    r = CheckResult("OpenClaw Gateway")
    try:
        from bridge_config import load_config
        config = load_config()
        gw = config.get("gateway", {})
        port = gw.get("port", 18789)

        r.info(f"目标: ws://127.0.0.1:{port}")

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        try:
            s.connect(("127.0.0.1", port))
            s.close()
            r.ok(f"端口 {port} 可达")
        except (socket.timeout, ConnectionRefusedError):
            r.warn(f"端口 {port} 不可达 (Gateway 可能未启动)")
        except Exception as e:
            r.warn(f"连接检查异常: {e}")
    except Exception as e:
        r.warn(f"配置读取失败: {e}")
    return r


def _check_bridge():
    r = CheckResult("OpenClaw Bridge")
    try:
        from core.bridge_dcc import DCCBridgeManager
        manager = DCCBridgeManager.instance()
        if manager.is_connected():
            r.ok("已连接")
        else:
            r.info("未连接 (可通过 /connect 连接)")
            r.ok("Bridge 模块正常")
    except Exception as e:
        r.fail(f"Bridge 模块异常: {e}")
    return r


def _check_mcp_bridge_config():
    r = CheckResult("mcp-bridge 插件配置")
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    if not os.path.exists(config_path):
        r.skip("openclaw.json 未找到")
        return r

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        mcp_bridge = config.get("plugins", {}).get("entries", {}).get("mcp-bridge", {})
        if not mcp_bridge.get("enabled", False):
            r.warn("mcp-bridge 插件未启用")
            return r

        servers = mcp_bridge.get("config", {}).get("servers", {})
        if not servers:
            r.warn("未配置 MCP servers")
        else:
            for name, srv in servers.items():
                url = srv.get("url", "?")
                r.info(f"Server '{name}': {url}")
            r.ok(f"{len(servers)} 个 MCP server 已配置")
    except Exception as e:
        r.fail(f"配置解析失败: {e}")
    return r


def run_health_check() -> str:
    """执行完整健康检查，返回报告文本"""
    start = time.time()

    checks = [
        _check_python,
        _check_dependencies,
        _check_mcp_server,
        _check_gateway,
        _check_bridge,
        _check_mcp_bridge_config,
    ]

    results = []
    for i, fn in enumerate(checks, 1):
        try:
            result = fn()
            result.name = f"[{i}/{len(checks)}] {result.name}"
            results.append(result)
        except Exception as e:
            r = CheckResult(f"[{i}/{len(checks)}] {fn.__name__}")
            r.fail(f"异常: {e}")
            results.append(r)

    elapsed = time.time() - start
    errors = sum(1 for r in results if r.is_error)
    warnings = sum(1 for r in results if r.is_warning)

    lines = [
        "=" * 58,
        "  ArtClaw DCC Bridge — 环境健康检查",
        f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 58,
    ]

    for r in results:
        lines.append("")
        lines.append(str(r))

    lines.append("")
    lines.append("=" * 58)
    if errors == 0 and warnings == 0:
        lines.append(f"  🎉 全部 {len(checks)} 项检查通过! ({elapsed:.1f}s)")
    elif errors == 0:
        lines.append(f"  ⚠️  通过，但有 {warnings} 个警告 ({elapsed:.1f}s)")
    else:
        lines.append(f"  ❌ {errors} 个错误, {warnings} 个警告 ({elapsed:.1f}s)")
    lines.append("=" * 58)

    return "\n".join(lines)
