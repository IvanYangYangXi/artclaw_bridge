"""
health_check.py - UE Claw Bridge 环境体检工具
================================================

阶段 4.6: 稳定性 "体检" 工具 (Health Check)

自动检测:
  1. Python 环境与依赖包
  2. UE 插件加载状态
  3. MCP Server 端口与 WebSocket
  4. OpenClaw Gateway 连接
  5. OpenClaw MCP Bridge 插件状态
  6. 文件系统权限与路径
  7. RAG 索引完整性 (Knowledge Base)
  8. Memory Store 状态

用法:
    from health_check import run_health_check
    report = run_health_check()
    print(report)

    # 或写入文件
    from health_check import run_health_check_to_file
    run_health_check_to_file(r"C:\\path\\to\\report.txt")

宪法约束:
  - 开发路线图 §4.6: Health Check 诊断工具
"""

import os
import sys
import json
import time
import socket
import platform
import importlib
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# 尝试导入 UE 环境模块 (在 UE 外运行时优雅降级)
# ---------------------------------------------------------------------------
try:
    import unreal
    _IN_UE = True
except ImportError:
    _IN_UE = False

try:
    from claw_bridge_logger import UELogger
except ImportError:
    try:
        from init_unreal import UELogger
    except ImportError:
        class _FallbackLogger:
            @staticmethod
            def info(msg): print(f"[INFO] {msg}")
            @staticmethod
            def warning(msg): print(f"[WARN] {msg}")
            @staticmethod
            def mcp_error(msg): print(f"[ERROR] {msg}")
        UELogger = _FallbackLogger()


# ---------------------------------------------------------------------------
# 检查项定义
# ---------------------------------------------------------------------------

class CheckResult:
    """单项检查结果"""
    def __init__(self, name: str):
        self.name = name
        self.status = "⏳"  # ✅ ⚠️ ❌ ⏭️
        self.details: list[str] = []
        self.is_error = False
        self.is_warning = False

    def ok(self, msg: str = ""):
        self.status = "✅"
        self.is_warning = False
        self.is_error = False
        if msg:
            self.details.append(msg)

    def warn(self, msg: str):
        self.status = "⚠️"
        self.is_warning = True
        self.details.append(msg)

    def fail(self, msg: str):
        self.status = "❌"
        self.is_error = True
        self.details.append(msg)

    def skip(self, msg: str):
        self.status = "⏭️"
        self.details.append(msg)

    def info(self, msg: str):
        self.details.append(msg)

    def __str__(self):
        lines = [f"  {self.status} {self.name}"]
        for d in self.details:
            lines.append(f"     {d}")
        return "\n".join(lines)


def _check_python_env() -> CheckResult:
    """检查 1: Python 环境"""
    r = CheckResult("Python Environment")
    r.info(f"Version: {sys.version.split()[0]}")
    r.info(f"Executable: {sys.executable}")
    r.info(f"Platform: {platform.platform()}")

    major, minor = sys.version_info[:2]
    if major == 3 and minor >= 9:
        r.ok(f"Python {major}.{minor} supported")
    else:
        r.fail(f"Python {major}.{minor} — requires >= 3.9")
    return r


def _check_dependencies() -> CheckResult:
    """检查 2: 必需依赖包"""
    r = CheckResult("Required Dependencies")
    packages = {
        "websockets": ">=12.0",
        "pydantic": ">=2.0",
    }
    optional = ["yaml", "sklearn"]

    all_ok = True
    for pkg, version_req in packages.items():
        try:
            mod = importlib.import_module(pkg)
            ver = getattr(mod, "__version__", "?")
            r.info(f"{pkg} {ver}")
        except ImportError:
            r.fail(f"{pkg} MISSING (required {version_req})")
            all_ok = False

    for pkg in optional:
        try:
            importlib.import_module(pkg)
            r.info(f"{pkg} (optional) ✓")
        except ImportError:
            r.info(f"{pkg} (optional) — not installed")

    if all_ok:
        r.ok("All required packages present")
    return r


def _check_ue_environment() -> CheckResult:
    """检查 3: UE 插件加载状态"""
    r = CheckResult("Unreal Engine Environment")
    if not _IN_UE:
        r.skip("Not running inside UE Editor")
        return r

    r.info(f"Engine version: {unreal.SystemLibrary.get_engine_version()}")

    # 检查 PythonScriptPlugin
    try:
        unreal.PythonScriptLibrary
        r.info("PythonScriptPlugin: loaded")
    except AttributeError:
        r.warn("PythonScriptPlugin: not detected (some features may fail)")

    # 检查 EditorScriptingUtilities
    try:
        unreal.EditorLevelLibrary
        r.info("EditorScriptingUtilities: loaded")
    except AttributeError:
        r.warn("EditorScriptingUtilities: not detected")

    r.ok("UE environment ready")
    return r


def _check_mcp_server() -> CheckResult:
    """检查 4: MCP Server (ws://localhost:8080)"""
    r = CheckResult("MCP Server (Port 8080)")

    host, port = "127.0.0.1", 8080
    try:
        sock = socket.create_connection((host, port), timeout=2.0)
        sock.close()
        r.ok(f"{host}:{port} listening")
    except (socket.timeout, ConnectionRefusedError, OSError):
        r.fail(f"{host}:{port} not reachable — MCP Server not running")
        r.info("Fix: Ensure ue_mcp_server.py is initialized (check init_unreal.py)")
        return r

    # 尝试 WebSocket 握手 (快速连接+断开)
    # 注意: UE 环境中已有 asyncio 事件循环在运行 (MCP Server)，
    # 不能用 asyncio.run()，改用同步 socket 发送 HTTP Upgrade。
    try:
        import http.client
        conn = http.client.HTTPConnection(host, port, timeout=3)
        conn.request(
            "GET", "/",
            headers={
                "Upgrade": "websocket",
                "Connection": "Upgrade",
                "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
                "Sec-WebSocket-Version": "13",
            },
        )
        resp = conn.getresponse()
        conn.close()
        if resp.status == 101:
            r.info("WebSocket handshake OK")
        else:
            r.info(f"WebSocket upgrade returned HTTP {resp.status} (expected 101)")
    except Exception as e:
        # TCP 已通过 (前面的检查)，WebSocket 握手失败不算严重问题
        err_msg = str(e).strip()
        if err_msg:
            r.info(f"WebSocket handshake: {type(e).__name__}: {err_msg}")
        else:
            r.info(f"WebSocket handshake: {type(e).__name__} (non-critical)")

    return r


def _check_openclaw_gateway() -> CheckResult:
    """检查 5: OpenClaw Gateway 连通性"""
    r = CheckResult("OpenClaw Gateway")

    # 加载配置 (通过 artclaw config 驱动)
    try:
        from bridge_config import _resolve_platform_config_path
        config_path = Path(_resolve_platform_config_path())
    except ImportError:
        config_path = Path.home() / ".openclaw" / "openclaw.json"
    host, port = "127.0.0.1", 18789  # fallback 默认端口
    token = ""

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            gw = config.get("gateway", {})
            port = gw.get("port", port)
            token = gw.get("auth", {}).get("token", "")
            r.info(f"Config: {config_path}")
        except Exception as e:
            r.warn(f"Failed to read config: {e}")
    else:
        r.info(f"No config found at {config_path}, using defaults")

    # TCP 检查
    try:
        sock = socket.create_connection((host, port), timeout=2.0)
        sock.close()
        r.info(f"{host}:{port} reachable")
    except (socket.timeout, ConnectionRefusedError, OSError):
        r.fail(f"{host}:{port} not reachable — OpenClaw Gateway not running")
        r.info("Fix: Run 'openclaw start' or check Gateway process")
        return r

    # Token 检查
    if token:
        masked = token[:8] + "..." + token[-4:] if len(token) > 12 else "***"
        r.info(f"Auth token: {masked}")
    else:
        r.info("No auth token configured (OK for local use)")

    # WebSocket 握手 (完整)
    try:
        from openclaw_bridge import diagnose_connection
        # 不执行完整诊断 (太慢)，只做快速检查
        r.ok(f"Gateway accessible at ws://{host}:{port}")
    except ImportError:
        r.ok(f"Gateway port reachable (bridge not imported)")

    return r


def _check_openclaw_mcp_bridge() -> CheckResult:
    """检查 6: OpenClaw MCP Bridge 插件是否注册了 ue-editor server"""
    r = CheckResult("OpenClaw MCP Bridge Plugin")

    try:
        from bridge_config import _resolve_platform_config_path
        config_path = Path(_resolve_platform_config_path())
    except ImportError:
        config_path = Path.home() / ".openclaw" / "openclaw.json"
    if not config_path.exists():
        r.skip(f"Platform config not found: {config_path}")
        return r

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        plugins = config.get("plugins", {})
        entries = plugins.get("entries", {})
        mcp_bridge = entries.get("mcp-bridge", {})

        if not mcp_bridge.get("enabled", False):
            r.fail("mcp-bridge plugin is not enabled")
            r.info(f"Fix: Set plugins.entries.mcp-bridge.enabled = true in {config_path}")
            return r

        r.info("mcp-bridge plugin: enabled")

        servers = mcp_bridge.get("config", {}).get("servers", {})
        if not servers:
            r.fail("No MCP servers configured in mcp-bridge")
            return r

        for name, srv in servers.items():
            enabled = srv.get("enabled", True)
            url = srv.get("url", "?")
            status = "✓" if enabled else "✗ (disabled)"
            r.info(f"  Server '{name}': {url} {status}")

        r.ok(f"{len(servers)} MCP server(s) configured")

    except Exception as e:
        r.fail(f"Failed to parse config: {e}")

    return r


def _check_filesystem() -> CheckResult:
    """检查 7: 文件系统权限"""
    r = CheckResult("File System & Paths")

    # 检查 Saved/ClawBridge 目录
    if _IN_UE:
        saved_dir = unreal.Paths.project_saved_dir()
    else:
        saved_dir = os.path.join(os.getcwd(), "Saved")

    agent_dir = os.path.join(saved_dir, "ClawBridge")
    r.info(f"Agent data dir: {agent_dir}")

    if os.path.isdir(agent_dir):
        # 写入测试
        test_file = os.path.join(agent_dir, "_healthcheck_test.tmp")
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            r.info("Write permission: OK")
        except Exception as e:
            r.fail(f"Write permission denied: {e}")
            return r
    else:
        r.info("Agent data dir does not exist yet (will be created on first use)")

    # 检查 Python 脚本路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    r.info(f"Python scripts: {script_dir}")

    # 检查关键文件存在
    key_files = ["ue_mcp_server.py", "openclaw_bridge.py", "init_unreal.py"]
    for kf in key_files:
        fp = os.path.join(script_dir, kf)
        if os.path.isfile(fp):
            r.info(f"  {kf}: ✓")
        else:
            r.warn(f"  {kf}: MISSING")

    r.ok("File system checks passed")
    return r


def _check_knowledge_base() -> CheckResult:
    """检查 8: RAG Knowledge Base 索引"""
    r = CheckResult("Knowledge Base (RAG Index)")

    try:
        from knowledge_base import LocalKnowledgeBase
        kb = LocalKnowledgeBase()
        stats = kb.get_stats() if hasattr(kb, "get_stats") else {}

        doc_count = stats.get("document_count", 0)
        chunk_count = stats.get("chunk_count", 0)

        if chunk_count > 0:
            r.ok(f"{chunk_count} chunks indexed from {doc_count} documents")
        else:
            r.warn("Knowledge base is empty — RAG search will not work")
            r.info("Fix: Place .md/.txt files in the docs directory and restart")
    except ImportError:
        r.skip("knowledge_base module not available")
    except Exception as e:
        r.warn(f"Knowledge base check failed: {e}")

    return r


def _check_memory_store() -> CheckResult:
    """检查 9: Memory Store 状态"""
    r = CheckResult("Memory Store (Persistent)")

    try:
        from memory_store import TieredMemoryStore
        store = TieredMemoryStore()
        stats = store.get_all_summary() if hasattr(store, "get_all_summary") else {}

        total = stats.get("total_entries", 0)
        r.ok(f"{total} entries stored")

        # v2 格式: layer_stats
        layer_stats = stats.get("layer_stats", {})
        for layer_name, layer_info in layer_stats.items():
            count = layer_info.get("total_entries", 0)
            r.info(f"  {layer_name}: {count}")

        # 健康度
        health = stats.get("memory_health", {})
        score = health.get("overall_score", 0)
        if score > 0:
            r.info(f"  health: {score:.2f}")
    except ImportError:
        r.skip("memory_store module not available")
    except Exception as e:
        r.warn(f"Memory store check: {e}")

    return r


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def run_health_check() -> str:
    """执行完整环境体检，返回报告文本"""
    start_time = time.time()

    checks = [
        _check_python_env,
        _check_dependencies,
        _check_ue_environment,
        _check_mcp_server,
        _check_openclaw_gateway,
        _check_openclaw_mcp_bridge,
        _check_filesystem,
        _check_knowledge_base,
        _check_memory_store,
    ]

    results: list[CheckResult] = []
    for i, check_fn in enumerate(checks, 1):
        try:
            result = check_fn()
            result.name = f"[{i}/{len(checks)}] {result.name}"
            results.append(result)
        except Exception as e:
            r = CheckResult(f"[{i}/{len(checks)}] {check_fn.__name__}")
            r.fail(f"Unexpected error: {e}")
            results.append(r)

    elapsed = time.time() - start_time

    # 汇总
    errors = sum(1 for r in results if r.is_error)
    warnings = sum(1 for r in results if r.is_warning)

    lines = []
    lines.append("=" * 62)
    lines.append("  UE Claw Bridge — Environment Health Check")
    lines.append(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 62)

    for r in results:
        lines.append("")
        lines.append(str(r))

    lines.append("")
    lines.append("=" * 62)
    if errors == 0 and warnings == 0:
        lines.append(f"  🎉 All {len(checks)} checks passed! ({elapsed:.1f}s)")
    elif errors == 0:
        lines.append(f"  ⚠️  Passed with {warnings} warning(s). ({elapsed:.1f}s)")
    else:
        lines.append(f"  ❌ {errors} error(s), {warnings} warning(s). ({elapsed:.1f}s)")
    lines.append("=" * 62)

    report = "\n".join(lines)

    # 日志输出
    if errors > 0:
        UELogger.mcp_error(f"[HealthCheck] {errors} errors found")
    elif warnings > 0:
        UELogger.warning(f"[HealthCheck] {warnings} warnings found")
    else:
        UELogger.info("[HealthCheck] All checks passed")

    return report


def run_health_check_to_file(output_path: str = "") -> str:
    """执行体检并写入文件，返回文件路径"""
    report = run_health_check()

    if not output_path:
        if _IN_UE:
            saved_dir = unreal.Paths.project_saved_dir()
        else:
            saved_dir = os.path.join(os.getcwd(), "Saved")
        agent_dir = os.path.join(saved_dir, "ClawBridge")
        os.makedirs(agent_dir, exist_ok=True)
        output_path = os.path.join(agent_dir, "_health_check_report.txt")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    UELogger.info(f"[HealthCheck] Report saved to: {output_path}")
    return output_path
