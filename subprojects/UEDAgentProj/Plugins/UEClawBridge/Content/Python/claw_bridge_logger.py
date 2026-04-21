"""
claw_bridge_logger.py - UE ClawBridge Logger
============================================

从 init_unreal.py 提取的 UELogger 类和 log_mcp_call 装饰器，
消除与项目其他工具的命名冲突。

本模块专为 UEClawBridge 插件提供统一日志接口。
"""

import sys
import functools
import asyncio
from datetime import datetime
import traceback

import unreal


# ============================================================================
# 日志级别常量
# ============================================================================

class _UELogLevel:
    """UE 日志级别常量，对应 ELogVerbosity"""
    DEBUG = "Verbose"
    INFO = "Log"
    WARNING = "Warning"
    ERROR = "Error"


# ============================================================================
# UE Logger 类
# ============================================================================

class UELogger:
    """
    UE ClawBridge 统一日志接口。

    将 Python 日志按分类输出到 UE Output Log：
      - LogUEAgent       : 通用 Agent 日志
      - LogUEAgent_MCP   : MCP 协议通信日志
      - LogUEAgent_Error : 错误与异常日志

    四级日志映射：
      DEBUG   -> UE Verbose  (灰色)
      INFO    -> UE Log      (白色)
      WARNING -> UE Warning  (黄色)
      ERROR   -> UE Error    (红色)
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


# ============================================================================
# MCP 调用装饰器
# ============================================================================

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