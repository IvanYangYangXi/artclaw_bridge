"""
StreamEvent — 流式 AI 响应事件

定义从 AI 平台接收到的流式事件格式，
确保所有平台的事件结构一致，便于 DCC 插件统一处理。

参考规范：docs/specs/sdk-platform-adapter-spec.md § P4
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, Dict


class StreamEventType(str, Enum):
    """流式事件类型枚举。"""

    TEXT_CHUNK = "text_chunk"
    """AI 正在生成回复文本（增量片段）"""

    THINKING = "thinking"
    """AI 正在思考（内部推理，可能不展示给用户）"""

    TOOL_CALL = "tool_call"
    """AI 调用工具"""

    TOOL_RESULT = "tool_result"
    """工具执行结果"""

    STATUS_CHANGE = "status_change"
    """连接/会话状态变化"""

    USAGE_UPDATE = "usage_update"
    """Token 使用量更新"""

    COMPLETE = "complete"
    """本次请求完成（complete 之后不再有事件）"""

    ERROR = "error"
    """发生错误"""


@dataclass
class StreamEvent:
    """
    流式 AI 响应事件。

    对应 PlatformAdapter 注册的流式回调函数的参数格式：
    - on_ai_message(session_key: str, text: str) → TEXT_CHUNK 事件
    - on_ai_thinking(session_key: str, thinking: str) → THINKING 事件
    - on_usage_update(usage: dict) → USAGE_UPDATE 事件
    """
    event_type: StreamEventType
    """事件类型"""

    session_key: str = ""
    """关联的会话 key"""

    content: str = ""
    """文本内容（TEXT_CHUNK / THINKING / ERROR 类型使用）"""

    data: Optional[Dict[str, Any]] = None
    """结构化数据（TOOL_CALL / USAGE_UPDATE 等类型使用）"""

    timestamp: Optional[float] = None
    """事件时间戳（Unix 时间戳）"""

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "event_type": self.event_type.value,
            "session_key": self.session_key,
            "content": self.content,
            "data": self.data,
            "timestamp": self.timestamp,
        }
