"""
Logging API - Unified logging for ArtClaw tools
==============================================

Provides standardized logging for tools:
- info(): Log informational messages
- warning(): Log warning messages
- error(): Log error messages
- debug(): Log debug messages
- set_level(): Set logging level
- configure_for_dcc(): Switch to DCC-native logging backend

Design: tool code only calls sdk.logger.info/warning/error/debug.
The backend is swapped per-DCC by configure_for_dcc(); tools never
need to import unreal / cmds / MaxPlus directly for logging.

Backend routing:
  default  -> Python standard logging -> sys.stdout
  ue       -> unreal.log / unreal.log_warning / unreal.log_error
  maya     -> maya.utils.executeDeferred + sys.stdout (future)
  max      -> MaxPlus.Core.EvalMAXScript (future)
"""
from __future__ import annotations

import logging
import sys
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Internal backends
# ---------------------------------------------------------------------------

class _StdoutBackend:
    """Default backend: Python standard logging to sys.stdout."""

    def __init__(self) -> None:
        self._logger = logging.getLogger("artclaw_sdk")
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter(
                '[%(levelname)s] %(name)s: %(message)s'
            ))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.DEBUG)

    def debug(self, msg: str) -> None:
        self._logger.debug(msg)

    def info(self, msg: str) -> None:
        self._logger.info(msg)

    def warning(self, msg: str) -> None:
        self._logger.warning(msg)

    def error(self, msg: str) -> None:
        self._logger.error(msg)

    def exception(self, msg: str) -> None:
        self._logger.exception(msg)


class _UEBackend:
    """UE backend: routes to unreal.log / unreal.log_warning / unreal.log_error.

    Using sys.stdout in UE Python causes ALL output to appear as
    LogPython: Error regardless of actual severity, which is misleading.
    This backend uses the proper unreal module functions instead.
    """

    def debug(self, msg: str) -> None:
        try:
            import unreal
            unreal.log(f"[ArtClaw][DEBUG] {msg}")
        except Exception:
            pass

    def info(self, msg: str) -> None:
        try:
            import unreal
            unreal.log(f"[ArtClaw] {msg}")
        except Exception:
            pass

    def warning(self, msg: str) -> None:
        try:
            import unreal
            unreal.log_warning(f"[ArtClaw] {msg}")
        except Exception:
            pass

    def error(self, msg: str) -> None:
        try:
            import unreal
            unreal.log_error(f"[ArtClaw] {msg}")
        except Exception:
            pass

    def exception(self, msg: str) -> None:
        import traceback
        tb = traceback.format_exc()
        self.error(f"{msg}\n{tb}")


# ---------------------------------------------------------------------------
# Active backend (default: stdout, switched by configure_for_dcc)
# ---------------------------------------------------------------------------

_backend: Any = _StdoutBackend()

# Standard Python logger kept for add_file_handler / external integrations
logger = logging.getLogger("artclaw_sdk")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())
    logger.setLevel(logging.DEBUG)


# ---------------------------------------------------------------------------
# Public API — tool code calls these, never the backend directly
# ---------------------------------------------------------------------------

def debug(message: str, *args, **kwargs) -> None:
    """Log debug message."""
    msg = message % args if args else message
    _backend.debug(msg)


def info(message: str, *args, **kwargs) -> None:
    """Log informational message."""
    msg = message % args if args else message
    _backend.info(msg)


def warning(message: str, *args, **kwargs) -> None:
    """Log warning message."""
    msg = message % args if args else message
    _backend.warning(msg)


def error(message: str, *args, **kwargs) -> None:
    """Log error message."""
    msg = message % args if args else message
    _backend.error(msg)


def exception(message: str, *args, **kwargs) -> None:
    """Log exception with traceback."""
    msg = message % args if args else message
    _backend.exception(msg)


def set_level(level: str) -> None:
    """Set logging level (only affects stdout backend)."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)


def configure_for_dcc(dcc_name: str) -> None:
    """Switch logging backend to match the current DCC environment.

    Call this once at module init time in the DCC-specific bridge layer.
    Tool code does not need to call this directly.

    Args:
        dcc_name: 'ue' | 'maya' | 'max' | 'standalone'
    """
    global _backend
    dcc_name = dcc_name.lower()

    if dcc_name in ("ue", "ue5", "unreal"):
        _backend = _UEBackend()
    else:
        # maya, max, standalone, etc.: fall back to stdout
        _backend = _StdoutBackend()


def add_file_handler(file_path: str, level: str = "INFO") -> None:
    """Add file handler for persistent log output (all DCC environments)."""
    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))
    file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.addHandler(file_handler)


def remove_handlers() -> None:
    """Remove all existing handlers from the standard logger."""
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)


def get_tool_logger(tool_name: str) -> "ToolLogger":
    """Get a tool-specific logger with automatic name prefix."""
    return ToolLogger(tool_name)


class ToolLogger:
    """Tool-specific logger — wraps the global backend with a name prefix."""

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        self._prefix = f"[{tool_name}]"

    def debug(self, message: str, *args, **kwargs):
        debug(f"{self._prefix} {message}", *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        info(f"{self._prefix} {message}", *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        warning(f"{self._prefix} {message}", *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        error(f"{self._prefix} {message}", *args, **kwargs)

    def exception(self, message: str, *args, **kwargs):
        exception(f"{self._prefix} {message}", *args, **kwargs)


# ---------------------------------------------------------------------------
# Misc utilities (keep for backward compat)
# ---------------------------------------------------------------------------

def log_function_call(func_name: str, args: tuple = (), kwargs: dict = None) -> None:
    """Log function call with arguments (debug level)."""
    kwargs = kwargs or {}
    parts = [str(a) for a in args] + [f"{k}={v}" for k, v in kwargs.items()]
    debug(f"Calling {func_name}({', '.join(parts)})")


def log_execution_time(func):
    """Decorator to log function execution time."""
    import time
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            debug(f"{func.__name__} completed in {time.time()-start:.3f}s")
            return result
        except Exception as e:
            error(f"{func.__name__} failed after {time.time()-start:.3f}s: {e}")
            raise

    return wrapper