"""
init_unreal.py - UE Editor Agent Python 初始化入口
==================================================

阶段 0.4: 日志与调试重定向 (Logging System)
阶段 0.5: 依赖隔离与自动安装 (Dependency Management)

宪法约束:
  - 将 Python stdout/stderr 重定向至 UE Output Log，添加 LogUEAgent 前缀
    (开发路线图 §0.5 / 系统架构设计 §2.3)
  - 插件私有库路径加入 sys.path，不污染引擎环境
    (开发路线图 §0.4 / 项目概要 §五)
  - C++ 负责生命周期/UI/主线程调度，Python 负责 MCP 通信和 Skill 逻辑
    (系统架构设计 §2.3)

本文件在 UE 编辑器加载插件时由 PythonScriptPlugin 自动执行。
"""

import sys
import os
import traceback
import functools
import logging
import asyncio
from datetime import datetime

import unreal


# ============================================================================
# 0. 路径常量
# ============================================================================

# 插件 Content/Python 目录（本文件所在目录）
_PLUGIN_PYTHON_DIR = os.path.dirname(os.path.abspath(__file__))

# 启动时清理 __pycache__，确保源码修改后不会加载过期的 .pyc
_pycache_dir = os.path.join(_PLUGIN_PYTHON_DIR, "__pycache__")
if os.path.isdir(_pycache_dir):
    import shutil
    try:
        shutil.rmtree(_pycache_dir)
    except Exception:
        pass

# 插件私有第三方库目录
_PLUGIN_LIB_DIR = os.path.join(_PLUGIN_PYTHON_DIR, "Lib")


# ============================================================================
# 1. 日志系统 (阶段 0.4)
# ============================================================================

class _UELogLevel:
    """UE 日志级别常量，对应 ELogVerbosity"""
    DEBUG = "Verbose"
    INFO = "Log"
    WARNING = "Warning"
    ERROR = "Error"


class UELogger:
    """
    UE Editor Agent 统一日志接口。

    将 Python 日志按分类输出到 UE Output Log：
      - LogUEAgent       : 通用 Agent 日志
      - LogUEAgent_MCP   : MCP 协议通信日志
      - LogUEAgent_Error : 错误与异常日志

    四级日志映射：
      DEBUG   -> UE Verbose  (灰色)
      INFO    -> UE Log      (白色)
      WARNING -> UE Warning  (黄色)
      ERROR   -> UE Error    (红色)

    宪法约束:
      - 开发路线图 §0.5: 重定向 Python stdout/stderr 至 UE Output Log
      - 概要设计 §1.1: 统一管理中心
    """

    # 分类前缀
    CATEGORY_GENERAL = "LogUEAgent"
    CATEGORY_MCP = "LogUEAgent_MCP"
    CATEGORY_ERROR = "LogUEAgent_Error"

    @staticmethod
    def _log(category: str, level: str, message: str):
        """
        底层日志输出，统一格式：[CATEGORY] [LEVEL] message

        使用 unreal.log / unreal.log_warning / unreal.log_error
        将消息路由到 UE Output Log。
        """
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted = f"[{category}] [{level}] {timestamp} | {message}"

        if level == _UELogLevel.ERROR:
            unreal.log_error(formatted)
        elif level == _UELogLevel.WARNING:
            unreal.log_warning(formatted)
        else:
            unreal.log(formatted)

    # --- 通用 Agent 日志 ---

    @staticmethod
    def debug(message: str):
        """DEBUG 级别 (Verbose) - 详细调试信息"""
        UELogger._log(UELogger.CATEGORY_GENERAL, _UELogLevel.DEBUG, message)

    @staticmethod
    def info(message: str):
        """INFO 级别 (Log) - 常规信息"""
        UELogger._log(UELogger.CATEGORY_GENERAL, _UELogLevel.INFO, message)

    @staticmethod
    def warning(message: str):
        """WARNING 级别 - 警告信息"""
        UELogger._log(UELogger.CATEGORY_GENERAL, _UELogLevel.WARNING, message)

    @staticmethod
    def error(message: str):
        """ERROR 级别 - 错误信息"""
        UELogger._log(UELogger.CATEGORY_ERROR, _UELogLevel.ERROR, message)

    # --- MCP 通信日志 ---

    @staticmethod
    def mcp(message: str, level: str = _UELogLevel.INFO):
        """MCP 通信专用日志，默认 INFO 级别"""
        UELogger._log(UELogger.CATEGORY_MCP, level, message)

    @staticmethod
    def mcp_error(message: str):
        """MCP 通信错误日志"""
        UELogger._log(UELogger.CATEGORY_MCP, _UELogLevel.ERROR, message)
        UELogger._log(UELogger.CATEGORY_ERROR, _UELogLevel.ERROR, f"[MCP] {message}")

    # --- 异常日志 ---

    @staticmethod
    def exception(message: str = ""):
        """
        记录当前异常的完整堆栈，以红色高亮显示。

        包含文件名、行号、函数名。
        """
        exc_info = traceback.format_exc()
        prefix = f"{message} | " if message else ""
        UELogger._log(
            UELogger.CATEGORY_ERROR,
            _UELogLevel.ERROR,
            f"{prefix}Exception:\n{exc_info}"
        )


class _UEOutputStream:
    """
    将 Python stdout / stderr 重定向到 UE Output Log。

    宪法约束:
      - 开发路线图 §0.5: 重定向 Python stdout/stderr 至 UE Output Log
      - 所有 print() 输出实时显示在 Output Log 中

    设计说明:
      - stdout  -> LogUEAgent       [INFO]
      - stderr  -> LogUEAgent_Error [ERROR]
      - 使用行缓冲：积累到完整一行后再输出，避免堆栈信息被拆成多条日志
      - 多行文本（如 traceback）合并为一条日志输出，避免刷屏
    """

    def __init__(self, level: str = _UELogLevel.INFO, category: str = None, original_stream=None):
        self._level = level
        # stderr 使用 ERROR 分类，stdout 使用 GENERAL 分类
        self._category = category or UELogger.CATEGORY_GENERAL
        self._original = original_stream
        self._buffer = ""

    def write(self, text: str):
        if not text:
            return

        # 同时写入原始流（保留 IDE 调试能力）
        if self._original:
            try:
                self._original.write(text)
            except Exception:
                pass

        # 累积到缓冲区，等 flush 或完整行时再输出
        self._buffer += text

    def flush(self):
        # 刷新时把缓冲区内容一次性输出（保持多行完整性）
        if self._buffer.strip():
            UELogger._log(self._category, self._level, self._buffer.rstrip("\n"))
            self._buffer = ""
        if self._original:
            try:
                self._original.flush()
            except Exception:
                pass

    def isatty(self):
        return False


def _install_stream_redirectors():
    """
    安装 stdout/stderr 重定向器。

    - stdout -> LogUEAgent       [INFO]
    - stderr -> LogUEAgent_Error [ERROR]
    """
    # 保存原始流引用
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    sys.stdout = _UEOutputStream(
        level=_UELogLevel.INFO,
        category=UELogger.CATEGORY_GENERAL,
        original_stream=original_stdout,
    )
    sys.stderr = _UEOutputStream(
        level=_UELogLevel.ERROR,
        category=UELogger.CATEGORY_ERROR,
        original_stream=original_stderr,
    )


def _install_exception_hook():
    """
    安装全局未捕获异常处理器。

    确保 Python 未捕获的异常也能记录到 UE Output Log。
    """
    _original_excepthook = sys.excepthook

    def _ue_excepthook(exc_type, exc_value, exc_tb):
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        UELogger._log(
            UELogger.CATEGORY_ERROR,
            _UELogLevel.ERROR,
            f"Uncaught Exception:\n{tb_str}"
        )
        # 仍然调用原始 hook
        if _original_excepthook and _original_excepthook is not _ue_excepthook:
            _original_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = _ue_excepthook


# --- MCP 调用日志装饰器 ---

def log_mcp_call(func):
    """
    MCP 调用装饰器：自动记录请求/响应到 LogUEAgent_MCP 分类。

    支持同步函数和异步协程函数。

    用法::

        @log_mcp_call
        def handle_tool_call(method, params):
            ...

        @log_mcp_call
        async def async_handle_tool_call(method, params):
            ...

    宪法约束:
      - 概要设计 §2.2: MCP Tool 封装
      - 核心机制 §1: 自动能力发现
    """
    # 判断是否是协程函数
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            func_name = func.__name__
            # 检测 ping 消息：检查字符串参数中是否包含 "ping" method
            is_ping = False
            for arg in args:
                if isinstance(arg, str) and '"method":"ping"' in arg.replace(' ', ''):
                    is_ping = True
                    break
            # ping 消息静默跳过，不输出任何日志
            if is_ping:
                return await func(*args, **kwargs)
            UELogger.mcp(f">>> {func_name} called | args={args}, kwargs={kwargs}")
            try:
                result = await func(*args, **kwargs)
                UELogger.mcp(f"<<< {func_name} returned | result={result}")
                return result
            except Exception as e:
                UELogger.mcp_error(f"!!! {func_name} raised {type(e).__name__}: {e}")
                raise
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            func_name = func.__name__
            UELogger.mcp(f">>> {func_name} called | args={args}, kwargs={kwargs}")
            try:
                result = func(*args, **kwargs)
                UELogger.mcp(f"<<< {func_name} returned | result={result}")
                return result
            except Exception as e:
                UELogger.mcp_error(f"!!! {func_name} raised {type(e).__name__}: {e}")
                raise
        return sync_wrapper


# ============================================================================
# 2. 依赖隔离与自动安装 (阶段 0.5)
# ============================================================================

# 必需依赖：安装失败则阻止插件功能
_REQUIRED_PACKAGES = [
    ("websockets", "websockets>=12.0"),
    ("pydantic", "pydantic>=2.0"),
]

# 可选依赖：安装失败不影响核心功能
_OPTIONAL_PACKAGES = [
    ("yaml", "PyYAML>=6.0"),
]


def _ensure_lib_dir():
    """确保插件私有 Lib 目录存在。"""
    if not os.path.exists(_PLUGIN_LIB_DIR):
        os.makedirs(_PLUGIN_LIB_DIR, exist_ok=True)
        UELogger.info(f"Created Lib directory: {_PLUGIN_LIB_DIR}")


def _add_lib_to_path():
    """
    将插件私有 Lib 目录加入 sys.path（优先级高于引擎目录）。

    宪法约束:
      - 开发路线图 §0.5: 将插件私有库路径加入 sys.path
      - 项目概要 §五: 每个插件独立虚拟环境，互不干扰
    """
    if _PLUGIN_LIB_DIR not in sys.path:
        sys.path.insert(0, _PLUGIN_LIB_DIR)
        UELogger.debug(f"Added to sys.path: {_PLUGIN_LIB_DIR}")


def _check_package_available(import_name: str) -> bool:
    """检查指定包是否可导入。"""
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False


def _find_ue_python_executable() -> str:
    """
    查找 UE 内置 Python 解释器路径。

    注意：在 UE 内嵌 Python 中，sys.executable 指向 UnrealEditor.exe，
    不能直接用于 subprocess。必须找到真正的 python.exe。

    UE5 的 Python 解释器位于引擎的 Binaries/ThirdParty/Python3 目录下。
    """
    # 方法 1: 通过 unreal 模块获取引擎路径，查找 ThirdParty Python
    try:
        engine_dir = unreal.Paths.engine_dir()
        possible_paths = [
            os.path.join(engine_dir, "Binaries", "ThirdParty", "Python3", "Win64", "python.exe"),
            os.path.join(engine_dir, "Binaries", "ThirdParty", "Python3", "Win64", "python3.exe"),
            os.path.join(engine_dir, "Binaries", "ThirdParty", "Python3", "Win64", "python311.exe"),
        ]
        for p in possible_paths:
            if os.path.exists(p):
                UELogger.debug(f"Found UE Python: {p}")
                return p
    except Exception:
        pass

    # 方法 2: 通过 sys.executable 的目录推算（仅当它确实是 python.exe 时）
    if sys.executable and os.path.exists(sys.executable):
        exe_name = os.path.basename(sys.executable).lower()
        # 只有当 sys.executable 确实是 python 时才使用
        # 排除 UnrealEditor.exe / UnrealEditor-Cmd.exe 等
        if "python" in exe_name and "unreal" not in exe_name:
            UELogger.debug(f"Using sys.executable: {sys.executable}")
            return sys.executable

    # 方法 3: 在 PATH 中搜索 python（最后的回退手段）
    import shutil
    python_in_path = shutil.which("python3") or shutil.which("python")
    if python_in_path:
        UELogger.debug(f"Found Python in PATH: {python_in_path}")
        return python_in_path

    return ""


def _pip_install(package_spec: str, target_dir: str) -> bool:
    """
    使用 pip install --target 安装包到指定目录。

    重要：使用 subprocess.Popen + 轮询方式避免阻塞 UE 主线程过久。
    如果发现无法找到有效的 Python 解释器，会跳过安装并提示手动操作。

    宪法约束:
      - 开发路线图 §0.4: pip install --target 定向安装，不污染引擎环境
      - 项目概要 §五: 依赖隔离
    """
    import subprocess

    python_exe = _find_ue_python_executable()
    if not python_exe:
        UELogger.error(
            f"Cannot find UE Python executable for pip install. "
            f"Please manually install: pip install --target \"{target_dir}\" {package_spec}"
        )
        return False

    # 安全检查：确保不是 UnrealEditor.exe
    exe_basename = os.path.basename(python_exe).lower()
    if "unreal" in exe_basename or "editor" in exe_basename:
        UELogger.error(
            f"Detected UnrealEditor as python executable ({python_exe}), aborting pip install. "
            f"Please manually install: pip install --target \"{target_dir}\" {package_spec}"
        )
        return False

    cmd = [
        python_exe, "-m", "pip", "install",
        "--target", target_dir,
        "--no-user",
        "--disable-pip-version-check",
        "--no-warn-script-location",
        package_spec
    ]

    UELogger.info(f"Installing: {package_spec} -> {target_dir}")
    UELogger.debug(f"Command: {' '.join(cmd)}")

    try:
        # 使用 Popen 启动子进程，避免阻塞主线程
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags,
        )

        # 等待完成（带超时），使用 communicate 避免死锁
        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=120)
            stdout_str = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr_str = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            UELogger.error(f"pip install timed out for {package_spec} (120s)")
            return False

        if proc.returncode == 0:
            UELogger.info(f"Successfully installed: {package_spec}")
            return True
        else:
            UELogger.error(f"pip install failed for {package_spec} (code={proc.returncode}):")
            if stdout_str.strip():
                UELogger.error(f"  stdout: {stdout_str.strip()}")
            if stderr_str.strip():
                UELogger.error(f"  stderr: {stderr_str.strip()}")
            return False

    except FileNotFoundError:
        UELogger.error(f"Python executable not found: {python_exe}")
        return False
    except Exception:
        UELogger.exception(f"pip install unexpected error for {package_spec}")
        return False


def _check_offline_bundle() -> bool:
    """
    检查并安装离线依赖包。

    离线 bundle 位于 Content/Python/Lib_bundle/ 目录。
    """
    bundle_dir = os.path.join(_PLUGIN_PYTHON_DIR, "Lib_bundle")
    if not os.path.isdir(bundle_dir):
        return False

    # 检查是否有 .whl 或 .tar.gz 文件
    wheel_files = [
        f for f in os.listdir(bundle_dir)
        if f.endswith((".whl", ".tar.gz", ".zip"))
    ]

    if not wheel_files:
        return False

    UELogger.info(f"Found offline bundle with {len(wheel_files)} packages")

    import subprocess
    python_exe = _find_ue_python_executable()
    if not python_exe:
        return False

    # 安全检查：确保不是 UnrealEditor.exe
    exe_basename = os.path.basename(python_exe).lower()
    if "unreal" in exe_basename or "editor" in exe_basename:
        UELogger.warning("Cannot use UnrealEditor as pip executable for offline bundle")
        return False

    cmd = [
        python_exe, "-m", "pip", "install",
        "--target", _PLUGIN_LIB_DIR,
        "--no-index",
        "--find-links", bundle_dir,
        "--no-user",
        "--disable-pip-version-check",
    ]
    # 安装 bundle 目录下所有包
    cmd.extend([os.path.join(bundle_dir, f) for f in wheel_files])

    try:
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags,
        )
        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=120)
            stderr_str = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            UELogger.warning("Offline bundle install timed out")
            return False

        if proc.returncode == 0:
            UELogger.info("Offline bundle installed successfully")
            return True
        else:
            UELogger.warning(f"Offline bundle install failed: {stderr_str}")
            return False
    except Exception:
        UELogger.exception("Offline bundle install error")
        return False


def _check_dependencies_fast() -> bool:
    """
    快速检测依赖是否已安装（不安装，仅检测）。

    Returns:
        True 如果所有必需包都已可用
    """
    _ensure_lib_dir()
    _add_lib_to_path()

    for import_name, _ in _REQUIRED_PACKAGES:
        if not _check_package_available(import_name):
            return False
    return True


def _install_dependencies():
    """
    主依赖安装流程。

    流程：
    1. 确保 Lib 目录存在
    2. 将 Lib 加入 sys.path
    3. 检测每个依赖是否可用
    4. 缺失时：先尝试离线 bundle，再尝试在线 pip install
    5. 必需包全部就绪后返回 True

    宪法约束:
      - 开发路线图 §0.4: 启动时检测 site-packages
      - 项目概要 §五: dependency_manager 统一管理
    """
    _ensure_lib_dir()
    _add_lib_to_path()

    missing_required = []
    missing_optional = []

    # 检测缺失的包
    for import_name, _ in _REQUIRED_PACKAGES:
        if not _check_package_available(import_name):
            missing_required.append((import_name, _))

    for import_name, _ in _OPTIONAL_PACKAGES:
        if not _check_package_available(import_name):
            missing_optional.append((import_name, _))

    all_missing = missing_required + missing_optional

    if not all_missing:
        UELogger.info("All dependencies are already installed")
        return True

    UELogger.info(f"Missing packages: {[m[0] for m in all_missing]}")

    # 尝试离线安装
    offline_success = False
    if missing_required or missing_optional:
        offline_success = _check_offline_bundle()
        if offline_success:
            # 重新加载 Lib 目录以识别新安装的包
            if _PLUGIN_LIB_DIR in sys.path:
                sys.path.remove(_PLUGIN_LIB_DIR)
            sys.path.insert(0, _PLUGIN_LIB_DIR)

    # 在线安装缺失的必需包
    required_ok = True
    for import_name, package_spec in missing_required:
        if not _check_package_available(import_name):
            success = _pip_install(package_spec, _PLUGIN_LIB_DIR)
            if not success:
                required_ok = False
                UELogger.error(
                    f"CRITICAL: Required package '{import_name}' installation failed! "
                    f"Manual install: pip install --target \"{_PLUGIN_LIB_DIR}\" {package_spec}"
                )

    # 在线安装缺失的可选包
    for import_name, package_spec in missing_optional:
        if not _check_package_available(import_name):
            success = _pip_install(package_spec, _PLUGIN_LIB_DIR)
            if not success:
                UELogger.warning(
                    f"Optional package '{import_name}' installation failed (non-critical)"
                )

    # 最终验证
    if required_ok:
        # 重新验证所有必需包
        all_verified = True
        for import_name, _ in _REQUIRED_PACKAGES:
            if _check_package_available(import_name):
                UELogger.info(f"  Verified: {import_name}")
            else:
                UELogger.error(f"  MISSING: {import_name}")
                all_verified = False

        if all_verified:
            UELogger.info("All dependencies installed successfully")
            return True

    UELogger.error(
        "Some required dependencies are missing. "
        "Plugin functionality may be limited. "
        "Please check the Output Log for details."
    )
    return False


# ============================================================================
# 3. Subsystem 桥接 (阶段 0.2 延续)
# ============================================================================

def sync_connection_state(is_online: bool):
    """
    同步连接状态到 C++ 子系统。

    宪法约束:
      - 系统架构设计 §1.3: 核心执行层统一管理
      - 开发路线图 §0.2: UUEAgentSubsystem 作为状态真值来源
    """
    subsystem = unreal.get_editor_subsystem(unreal.UEAgentSubsystem)
    if subsystem:
        subsystem.set_connection_status(is_online)
        UELogger.info(f"Agent connection status synced: {is_online}")
    else:
        UELogger.warning("UEAgentSubsystem not available, cannot sync connection state")


# ============================================================================
# 4. 初始化入口
# ============================================================================

def _is_mcp_server_alive(host: str = "127.0.0.1", port: int = 8080, timeout: float = 1.0) -> bool:
    """检测 MCP Server 是否正在监听"""
    import socket
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False



def _start_mcp_gateway():
    """
    启动 MCP WebSocket 通信网关 (阶段 1.1)。

    流程:
      1. 检测 MCP Server 是否已在运行 (端口 8080)
      2. 如果已在运行 → 跳过，避免重复启动
      3. 如果未运行 → 先尝试关闭残留实例，再启动新实例
      4. 端口就绪验证通过 deferred tick 异步完成，不阻塞主线程

    宪法约束:
      - 开发路线图 §1.1: WebSocket 服务器在插件启动时自动启动
      - 系统架构设计 §1.2: WebSocket 传输层
    """
    import builtins as _bi
    host, port = "127.0.0.1", 8080

    # 步骤 0: 防止并发/重复启动（用 builtins 跨 exec 持久化）
    if getattr(_bi, '_UE_MCP_GATEWAY_STARTING', False):
        UELogger.info("MCP Gateway startup already in progress, skipping duplicate call")
        return

    # 步骤 1: 检测是否已在运行
    if _is_mcp_server_alive(host, port):
        UELogger.info(f"MCP Server already running on {host}:{port}")
        return

    _bi._UE_MCP_GATEWAY_STARTING = True

    # 步骤 2: 清理可能残留的旧实例（非阻塞：不 sleep）
    UELogger.info(f"MCP Server not detected on {host}:{port}, starting...")
    try:
        from mcp_server import stop_mcp_server, _mcp_server
        if _mcp_server is not None:
            UELogger.info("Cleaning up stale MCP Server instance...")
            stop_mcp_server()
    except (ImportError, Exception) as e:
        UELogger.info(f"No stale instance to clean: {e}")

    # 步骤 3: 启动新实例（start_mcp_server 内部通过 slate tick 驱动 asyncio，不阻塞）
    try:
        from mcp_server import start_mcp_server
        success = start_mcp_server(host="localhost", port=port)
        if not success:
            UELogger.warning("MCP Gateway start_mcp_server returned False")
            _bi._UE_MCP_GATEWAY_STARTING = False
            return
    except ImportError as e:
        UELogger.warning(f"MCP Server module not available: {e}")
        _bi._UE_MCP_GATEWAY_STARTING = False
        return
    except Exception:
        UELogger.exception("MCP Gateway startup error")
        _bi._UE_MCP_GATEWAY_STARTING = False
        return

    # 步骤 4: 异步验证端口就绪（通过 tick 回调，不用 time.sleep）
    _verify_counter = [0]
    _max_checks = 600  # 600 次 tick，覆盖启动期间低帧率场景（约 10 秒超时）

    def _verify_tick(delta_time):
        _verify_counter[0] += 1
        if _is_mcp_server_alive(host, port):
            UELogger.info(f"MCP Gateway verified on {host}:{port} (after {_verify_counter[0]} ticks)")
            unreal.unregister_slate_post_tick_callback(_verify_handle)
            return
        # 也检查递增端口
        for alt_port in range(port + 1, port + 5):
            if _is_mcp_server_alive(host, alt_port):
                UELogger.info(f"MCP Gateway verified on {host}:{alt_port} (after {_verify_counter[0]} ticks)")
                unreal.unregister_slate_post_tick_callback(_verify_handle)
                return
        if _verify_counter[0] >= _max_checks:
            UELogger.warning(
                f"MCP Gateway startup may have failed — "
                f"port {port} not responding after {_max_checks} ticks. "
                f"Use /diagnose to troubleshoot."
            )
            unreal.unregister_slate_post_tick_callback(_verify_handle)

    _verify_handle = unreal.register_slate_post_tick_callback(_verify_tick)


def _register_shutdown_hook():
    """
    注册编辑器关闭时的清理回调。

    确保 MCP 服务器在编辑器关闭时正确释放端口。
    """
    import atexit

    def _on_shutdown():
        UELogger.info("Editor shutting down, stopping MCP Gateway...")
        try:
            from mcp_server import stop_mcp_server
            stop_mcp_server()
        except Exception:
            pass

    atexit.register(_on_shutdown)


def _deferred_startup():
    """
    延迟启动：在后台线程中执行耗时的依赖安装和 MCP 网关启动。

    通过 unreal.register_slate_post_tick_callback 在下一帧触发，
    避免阻塞编辑器启动。
    """
    import threading

    def _bg_work():
        try:
            # 步骤 1: 安装缺失依赖（可能触发 pip install）
            deps_ok = _install_dependencies()

            if not deps_ok:
                UELogger.warning("Deferred startup: dependencies incomplete, MCP Gateway skipped")
                return

            # 步骤 2: 启动 MCP 网关（这里面有端口探测 + asyncio 初始化）
            # 注意：_start_mcp_gateway 内部的 start_mcp_server 会注册
            # slate_post_tick_callback，必须在主线程执行。
            # 所以我们用 _schedule_on_game_thread 把它排回主线程。
            _schedule_mcp_start_on_game_thread()

        except Exception:
            UELogger.exception("Deferred startup error")

    thread = threading.Thread(target=_bg_work, daemon=True, name="UEAgent-DeferredInit")
    thread.start()
    UELogger.info("Deferred startup dispatched to background thread")


def _schedule_mcp_start_on_game_thread():
    """
    将 MCP 网关启动排回主线程执行。

    MCP Server 的 asyncio bridge 需要注册 slate_post_tick_callback，
    这个 API 必须在主线程调用。
    """
    _pending_init_callbacks = []
    _init_lock = __import__('threading').Lock()

    def _do_start():
        try:
            _start_mcp_gateway()
            _register_shutdown_hook()
            UELogger.info("MCP Gateway started (from game thread)")
        except Exception:
            UELogger.exception("MCP Gateway start failed (from game thread)")

    def _tick_init(delta_time):
        # 只执行一次，然后注销自己
        try:
            _do_start()
        finally:
            unreal.unregister_slate_post_tick_callback(_tick_handle)

    _tick_handle = unreal.register_slate_post_tick_callback(_tick_init)


def _initialize():
    """
    插件 Python 层初始化入口。

    执行顺序：
    1. 安装日志重定向 (0.4) — 同步，极快
    2. 安装异常处理器 (0.4) — 同步，极快
    3. 快速检测依赖 — 同步，仅 import 检查
    4a. 依赖已就绪 → 延迟到首个 Slate tick 启动 MCP 网关
    4b. 依赖缺失 → 延迟到后台线程安装，安装完成后回主线程启动 MCP

    注意：本函数可能在 Engine Init 阶段被调用（Slate 尚未 tick），
    因此 MCP 启动必须通过 slate_post_tick_callback 延迟执行。
    """
    # --- 阶段 0.4: 日志系统（极快） ---
    _install_stream_redirectors()
    _install_exception_hook()
    UELogger.info("=" * 60)
    UELogger.info("UE Claw Bridge - Python Layer Initializing")
    UELogger.info("=" * 60)

    # --- 阶段 0.3.5: 共享模块完整性检查 ---
    try:
        # integrity_check.py 本身也是共享模块，先尝试导入
        try:
            from integrity_check import check_and_repair
        except ImportError:
            # integrity_check.py 也缺失 → 尝试从开发路径导入
            _bridge_dir = os.path.normpath(
                os.path.join(_PLUGIN_PYTHON_DIR, "..", "..", "..", "..", "..", "..",
                             "core")
            )
            if os.path.isdir(_bridge_dir) and _bridge_dir not in sys.path:
                sys.path.insert(0, _bridge_dir)
            from integrity_check import check_and_repair

        integrity = check_and_repair(_PLUGIN_PYTHON_DIR, auto_repair=True)
        if integrity.repaired:
            UELogger.info(f"共享模块自动修复: {', '.join(integrity.repaired)}")
        if not integrity.ok:
            UELogger.error(f"共享模块缺失且无法修复: {', '.join(integrity.failed)}")
            UELogger.error("请使用 setup.bat 重新安装插件，或查看 _integrity_issues.md")
    except Exception as e:
        UELogger.warning(f"完整性检查跳过: {e}")

    # --- 快速依赖检测（仅 import 检查，不安装） ---
    deps_ready = _check_dependencies_fast()

    # 初始化连接状态（默认离线）
    sync_connection_state(False)

    if deps_ready:
        # 依赖已就绪 → 延迟到首个 Slate tick 再启动 MCP
        # 不在这里直接调用 _start_mcp_gateway()，因为 Engine Init 阶段
        # Slate 还没 tick，asyncio bridge 无法运转
        UELogger.info("All dependencies ready, deferring MCP Gateway to first Slate tick...")
        UELogger.info("-" * 40)

        def _deferred_mcp_tick(delta_time):
            """首个 Slate tick 回调：启动 MCP 网关"""
            try:
                _start_mcp_gateway()
                _register_shutdown_hook()
                UELogger.info("Python layer initialization complete")
            except Exception:
                UELogger.exception("Deferred MCP Gateway start failed")
            finally:
                unreal.unregister_slate_post_tick_callback(_deferred_mcp_handle)

        _deferred_mcp_handle = unreal.register_slate_post_tick_callback(_deferred_mcp_tick)
    else:
        # 依赖缺失 → 后台安装，不阻塞编辑器
        UELogger.info("Missing dependencies detected, deferring install to background...")
        UELogger.info("-" * 40)
        UELogger.info("Python layer initialized (MCP Gateway pending dependency install)")
        _deferred_startup()


# ============================================================================
# 5. 初始化守卫 — 防止重复执行
# ============================================================================
# UE PythonScriptPlugin 可能多次 exec 本文件（Engine Init 阶段 + 延迟加载阶段），
# C++ 端的 ConnectOpenClawBridge 也会 import 并调用 _start_mcp_gateway。
#
# 关键：UE 的 exec() 不走 sys.modules 缓存，所以模块级变量每次都被重置。
# 必须用 builtins 或全局字典来跨 exec 持久化标志。

import builtins as _builtins

if not getattr(_builtins, '_UE_AGENT_INITIALIZED', False):
    _builtins._UE_AGENT_INITIALIZED = True
    _initialize()
else:
    UELogger.info("Python layer already initialized, skipping duplicate _initialize()")
