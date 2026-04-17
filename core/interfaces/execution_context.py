"""
ExecutionContext — 代码执行上下文数据类

定义 DCC 插件中代码执行的输入/输出契约，
确保所有 DCC 的代码执行结果格式一致。

参考规范：docs/specs/sdk-dcc-interface-spec.md § D6
"""

from dataclasses import dataclass, field
from typing import Optional, Any, Dict


@dataclass
class ExecutionResult:
    """
    代码执行结果。

    对应 BaseDCCAdapter.execute_code() 的返回值契约。
    """
    success: bool
    """执行是否成功"""

    result: Optional[Any] = None
    """执行结果值（仅 success=True 时有意义）"""

    error: Optional[str] = None
    """错误信息（仅 success=False 时有意义）"""

    output: str = ""
    """标准输出 / 打印内容"""

    execution_time_ms: Optional[float] = None
    """执行耗时（毫秒），可选"""

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典，用于 JSON 返回给 AI。"""
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "output": self.output,
        }

    @classmethod
    def ok(cls, result: Any = None, output: str = "") -> "ExecutionResult":
        """创建成功结果的工厂方法。"""
        return cls(success=True, result=result, output=output)

    @classmethod
    def fail(cls, error: str, output: str = "") -> "ExecutionResult":
        """创建失败结果的工厂方法。"""
        return cls(success=False, error=error, output=output)


@dataclass
class ExecutionContext:
    """
    代码执行上下文。

    传递给 DCC 代码执行环境的上下文信息，
    包含持久化命名空间和执行选项。
    """
    namespace: Dict[str, Any] = field(default_factory=dict)
    """Python 执行命名空间（持久化跨调用）"""

    timeout_seconds: Optional[float] = None
    """执行超时（秒），None 表示不超时"""

    capture_output: bool = True
    """是否捕获 stdout/stderr"""

    main_thread_required: bool = False
    """是否必须在主线程执行（Maya/Max 等 DCC 要求）"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """附加元数据（调用来源、技能名称等）"""
