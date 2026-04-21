"""
ArtClaw Bridge - 核心接口层

本模块提供 SDK/API 标准化所需的抽象基类、数据类和协议定义。
所有平台适配器和 DCC 插件实现均应遵循此处定义的接口契约。
"""

from .platform_adapter import PlatformAdapter
from .execution_context import ExecutionContext, ExecutionResult
from .stream_event import StreamEvent, StreamEventType

__all__ = [
    "PlatformAdapter",
    "ExecutionContext",
    "ExecutionResult",
    "StreamEvent",
    "StreamEventType",
]
