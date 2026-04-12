"""
Logging API - Unified logging for ArtClaw tools
==============================================

Provides standardized logging for tools:
- info(): Log informational messages
- warning(): Log warning messages  
- error(): Log error messages
- debug(): Log debug messages
- set_level(): Set logging level
"""
from __future__ import annotations

import logging
import sys
from typing import Any, Optional

# Create logger for ArtClaw tools
logger = logging.getLogger("artclaw_sdk")

# Default configuration
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def info(message: str, *args, **kwargs) -> None:
    """Log informational message.
    
    Args:
        message: Log message
        *args: Positional arguments for string formatting
        **kwargs: Keyword arguments for logging
    """
    logger.info(message, *args, **kwargs)


def warning(message: str, *args, **kwargs) -> None:
    """Log warning message.
    
    Args:
        message: Log message  
        *args: Positional arguments for string formatting
        **kwargs: Keyword arguments for logging
    """
    logger.warning(message, *args, **kwargs)


def error(message: str, *args, **kwargs) -> None:
    """Log error message.
    
    Args:
        message: Log message
        *args: Positional arguments for string formatting  
        **kwargs: Keyword arguments for logging
    """
    logger.error(message, *args, **kwargs)


def debug(message: str, *args, **kwargs) -> None:
    """Log debug message.
    
    Args:
        message: Log message
        *args: Positional arguments for string formatting
        **kwargs: Keyword arguments for logging
    """
    logger.debug(message, *args, **kwargs)


def exception(message: str, *args, **kwargs) -> None:
    """Log exception with traceback.
    
    Args:
        message: Log message
        *args: Positional arguments for string formatting
        **kwargs: Keyword arguments for logging
    """
    logger.exception(message, *args, **kwargs)


def set_level(level: str) -> None:
    """Set logging level.
    
    Args:
        level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR')
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)


def add_file_handler(file_path: str, level: str = "INFO") -> None:
    """Add file handler for logging to file.
    
    Args:
        file_path: Path to log file
        level: Logging level for file handler
    """
    file_handler = logging.FileHandler(file_path)
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    file_handler.setLevel(numeric_level)
    
    logger.addHandler(file_handler)


def remove_handlers() -> None:
    """Remove all existing handlers."""
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)


def configure_for_dcc(dcc_name: str) -> None:
    """Configure logging for specific DCC environment.
    
    Args:
        dcc_name: Name of DCC ('maya', 'max', 'ue', etc.)
    """
    # Update logger name to include DCC
    global logger
    logger = logging.getLogger(f"artclaw_sdk.{dcc_name}")
    
    # DCC-specific configuration
    if dcc_name == "maya":
        # Maya has its own console output handling
        pass
    elif dcc_name == "max":
        # 3ds Max listener configuration
        pass
    elif dcc_name == "ue":
        # UE Output Log configuration  
        pass


class ToolLogger:
    """Tool-specific logger with automatic prefixing."""
    
    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        self.prefix = f"[{tool_name}]"
        
    def info(self, message: str, *args, **kwargs):
        """Log info with tool prefix."""
        info(f"{self.prefix} {message}", *args, **kwargs)
        
    def warning(self, message: str, *args, **kwargs):
        """Log warning with tool prefix.""" 
        warning(f"{self.prefix} {message}", *args, **kwargs)
        
    def error(self, message: str, *args, **kwargs):
        """Log error with tool prefix."""
        error(f"{self.prefix} {message}", *args, **kwargs)
        
    def debug(self, message: str, *args, **kwargs):
        """Log debug with tool prefix."""
        debug(f"{self.prefix} {message}", *args, **kwargs)
        
    def exception(self, message: str, *args, **kwargs):
        """Log exception with tool prefix."""
        exception(f"{self.prefix} {message}", *args, **kwargs)


def get_tool_logger(tool_name: str) -> ToolLogger:
    """Get a tool-specific logger.
    
    Args:
        tool_name: Name of the tool
        
    Returns:
        ToolLogger instance
    """
    return ToolLogger(tool_name)


def log_function_call(func_name: str, args: tuple = (), kwargs: dict = None) -> None:
    """Log function call with arguments.
    
    Args:
        func_name: Name of function being called
        args: Positional arguments
        kwargs: Keyword arguments
    """
    kwargs = kwargs or {}
    
    args_str = ", ".join(str(arg) for arg in args)
    kwargs_str = ", ".join(f"{k}={v}" for k, v in kwargs.items())
    
    all_args = []
    if args_str:
        all_args.append(args_str)
    if kwargs_str:
        all_args.append(kwargs_str)
        
    args_display = "(" + ", ".join(all_args) + ")"
    debug(f"Calling {func_name}{args_display}")


def log_execution_time(func):
    """Decorator to log function execution time."""
    import time
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            debug(f"{func.__name__} completed in {execution_time:.3f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            error(f"{func.__name__} failed after {execution_time:.3f}s: {e}")
            raise
    
    return wrapper