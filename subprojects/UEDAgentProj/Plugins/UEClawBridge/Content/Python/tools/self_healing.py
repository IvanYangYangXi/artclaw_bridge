"""
self_healing.py - 错误感知与自修复循环
========================================

阶段 2.7: 将执行报错自动回传给 AI，引导其自动修复。

宪法约束:
  - 开发路线图 §2.7: 将 run_ue_python 的 Traceback 自动作为上下文回传
  - 开发路线图 §2.7: Prompt 引导 AI 分析原因并重新执行修复代码
"""

import json
from typing import Optional, Dict, List
from dataclasses import dataclass, field

from init_unreal import UELogger


# ============================================================================
# 1. 错误分类
# ============================================================================

# 常见错误类型 → 修复提示模板
ERROR_PATTERNS = {
    "AttributeError": {
        "category": "api_mismatch",
        "hint": "The attribute or method does not exist on this object. Check the UE Python API docs for the correct method name. Use dir(obj) to list available attributes.",
    },
    "NameError": {
        "category": "undefined_variable",
        "hint": "A variable or name is not defined. Make sure you import required modules and define variables before use. Available context: S (selected actors), W (world), L (unreal module).",
    },
    "TypeError": {
        "category": "wrong_arguments",
        "hint": "Wrong argument types or count. Check the function signature and ensure arguments match the expected types.",
    },
    "ImportError": {
        "category": "missing_module",
        "hint": "Module not found. In UE Python, use 'import unreal' for editor APIs. Third-party modules may not be available.",
    },
    "ModuleNotFoundError": {
        "category": "missing_module",
        "hint": "Module not found. Only modules available in UE's Python environment can be imported.",
    },
    "RuntimeError": {
        "category": "runtime_error",
        "hint": "A runtime error occurred. This may be due to invalid editor state or attempting an operation at the wrong time.",
    },
    "ValueError": {
        "category": "invalid_value",
        "hint": "Invalid value provided. Check that parameters are within valid ranges.",
    },
    "IndexError": {
        "category": "out_of_bounds",
        "hint": "Index out of range. Check the length of lists/arrays before accessing elements. The selection (S) might be empty.",
    },
    "KeyError": {
        "category": "missing_key",
        "hint": "Key not found in dictionary. Check available keys before access.",
    },
    "ZeroDivisionError": {
        "category": "math_error",
        "hint": "Division by zero. Add a check for zero before dividing.",
    },
}


@dataclass
class ErrorAnalysis:
    """错误分析结果"""
    error_type: str
    error_message: str
    category: str
    hint: str
    traceback: str
    line_number: Optional[int] = None
    suggestion: str = ""

    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type,
            "error_message": self.error_message,
            "category": self.category,
            "hint": self.hint,
            "line_number": self.line_number,
            "suggestion": self.suggestion,
        }


# ============================================================================
# 2. 错误分析器
# ============================================================================

def analyze_error(error_msg: str, original_code: str = "") -> ErrorAnalysis:
    """
    分析执行错误，提取类型、行号、修复提示。

    宪法约束:
      - 开发路线图 §2.7: 自动分析错误类型
    """
    # 提取错误类型
    error_type = "Unknown"
    error_text = ""
    line_number = None

    lines = error_msg.strip().split("\n")

    # 最后一行通常是 "ErrorType: message"
    if lines:
        last_line = lines[-1].strip()
        if ":" in last_line:
            error_type = last_line.split(":")[0].strip()
            error_text = last_line[len(error_type) + 1:].strip()

    # 提取行号
    for line in lines:
        if "line " in line.lower():
            try:
                parts = line.split("line ")
                if len(parts) >= 2:
                    num_str = parts[-1].split(",")[0].split()[0]
                    line_number = int(num_str)
            except (ValueError, IndexError):
                pass

    # 匹配错误模式
    pattern = ERROR_PATTERNS.get(error_type, {
        "category": "unknown",
        "hint": "An unexpected error occurred. Review the traceback for details.",
    })

    # 构建修复建议
    suggestion = _build_suggestion(error_type, error_text, original_code, line_number)

    return ErrorAnalysis(
        error_type=error_type,
        error_message=error_text,
        category=pattern["category"],
        hint=pattern["hint"],
        traceback=error_msg,
        line_number=line_number,
        suggestion=suggestion,
    )


def _build_suggestion(error_type: str, error_text: str, code: str, line_num: Optional[int]) -> str:
    """根据错误类型构建具体修复建议。"""
    suggestions = []

    if error_type == "AttributeError":
        # 尝试提取对象类型和缺失属性
        if "has no attribute" in error_text:
            suggestions.append("Use dir(object) to check available attributes.")
            if "unreal" in error_text.lower():
                suggestions.append("Check UE Python API for the correct method name. API names may differ between UE versions.")

    elif error_type == "NameError":
        if "is not defined" in error_text:
            name = error_text.split("'")[1] if "'" in error_text else ""
            if name:
                suggestions.append(f"Variable '{name}' is not defined. Did you forget to import it or assign it?")
                if name in ("S", "W", "L", "ELL", "EAL"):
                    suggestions.append(f"'{name}' should be auto-injected. Make sure inject_context=True.")

    elif error_type == "IndexError":
        suggestions.append("Check len(S) before accessing S[0]. The selection might be empty.")

    elif error_type == "TypeError":
        if "argument" in error_text.lower():
            suggestions.append("Check the function signature for correct argument types and count.")

    return " ".join(suggestions) if suggestions else ""


# ============================================================================
# 3. 自修复上下文构建
# ============================================================================

def build_retry_context(exec_result: dict, original_code: str, max_retries: int = 3) -> Optional[dict]:
    """
    从失败的执行结果构建重试上下文。

    宪法约束:
      - 开发路线图 §2.7: 引导 AI 根据错误日志分析原因，生成修复代码

    Returns:
        dict with retry prompt context, or None if no retry should be attempted.
    """
    if exec_result.get("success", True):
        return None  # 成功则无需重试

    error_msg = exec_result.get("error", "")
    if not error_msg:
        return None

    exec_id = exec_result.get("exec_id", 0)

    # 分析错误
    analysis = analyze_error(error_msg, original_code)

    UELogger.info(
        f"[Self-Heal #{exec_id}] Error: {analysis.error_type} -> {analysis.category}"
    )

    retry_context = {
        "retry_requested": True,
        "original_code": original_code,
        "error_analysis": analysis.to_dict(),
        "instruction": (
            f"The previous code failed with {analysis.error_type}: {analysis.error_message}. "
            f"{analysis.hint} "
            f"{analysis.suggestion} "
            f"Please fix the code and try again. "
            f"Remember: S=selected actors, W=editor world, L=unreal module."
        ),
    }

    return retry_context


# ============================================================================
# 4. MCP 注册
# ============================================================================

def register_tools(mcp_server) -> None:
    """错误分析已内化到 run_ue_python 流程中，不再单独暴露为 MCP Tool。
    
    analyze_error() 仍可被其他模块调用。
    """
    # analyze_error 已内化：run_ue_python 失败时自动附带错误分析
    UELogger.info("Phase 2.7: error analysis available (internalized, no MCP tool)")


def _handle_analyze_error(arguments: dict) -> str:
    """MCP Tool handler for error analysis."""
    error_msg = arguments.get("error_message", "")
    original_code = arguments.get("original_code", "")

    analysis = analyze_error(error_msg, original_code)

    return json.dumps({
        "analysis": analysis.to_dict(),
        "instruction": (
            f"Error: {analysis.error_type}: {analysis.error_message}. "
            f"Category: {analysis.category}. "
            f"Hint: {analysis.hint} "
            f"Suggestion: {analysis.suggestion}"
        ),
    })
