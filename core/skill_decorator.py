"""
skill_decorator.py — 平台无关的 @artclaw_tool 装饰器
======================================================

在 core/ 中提供与平台无关的 @artclaw_tool 装饰器定义。

设计原则：
- 新代码（新 Skill）推荐使用 @artclaw_tool（更清晰的命名）
- 旧代码的 @ue_tool 保持不变，无需迁移（@ue_tool 永久保留为别名）
- 若 UE 侧 skill_hub 可导入，则直接复用其 `tool` 实现（零重复）
- 若 skill_hub 不可用（纯 CLI/测试环境），使用此处的独立实现

导入方式（推荐顺序）：
    # 方式 1: 在 UE 运行时（skill_hub 可用）
    from skill_hub import tool as artclaw_tool

    # 方式 2: 在纯 Python 环境（如 CLI 测试）
    from core.skill_decorator import artclaw_tool

    # 方式 3: 自动选择（skill_decorator 内部已处理）
    from skill_decorator import artclaw_tool

参考规范：docs/specs/sdk-skill-spec.md §4（@artclaw_tool 统一装饰器）
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# 尝试复用 UE 侧 skill_hub.tool（零重复原则）
# ---------------------------------------------------------------------------

def _try_import_skill_hub_tool():
    """尝试从 UE 侧 skill_hub 导入 tool 函数。"""
    try:
        from skill_hub import tool  # noqa: F401
        return tool
    except ImportError:
        return None


_skill_hub_tool = _try_import_skill_hub_tool()


# ---------------------------------------------------------------------------
# 独立实现（skill_hub 不可用时的 fallback）
# ---------------------------------------------------------------------------

# 全局注册表：记录通过 @artclaw_tool 声明的工具（独立实现维护此表）
_ARTCLAW_TOOL_REGISTRY: Dict[str, dict] = {}


def _generate_schema_from_hints(func: Callable) -> dict:
    """从函数签名的 type hints 生成 JSON Schema（与 UE 侧实现对齐）。"""
    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        return {"type": "object", "properties": {}}

    properties: dict = {}
    required: list = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls", "arguments"):
            continue

        prop: dict = {}
        annotation = param.annotation

        if annotation is str:
            prop["type"] = "string"
        elif annotation is int:
            prop["type"] = "integer"
        elif annotation is float:
            prop["type"] = "number"
        elif annotation is bool:
            prop["type"] = "boolean"
        elif annotation is list or annotation is List:
            prop["type"] = "array"
        elif annotation is dict or annotation is Dict:
            prop["type"] = "object"
        else:
            prop["type"] = "string"  # fallback

        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        else:
            prop["default"] = param.default

        properties[param_name] = prop

    schema: dict = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _artclaw_tool_standalone(
    name: Optional[str] = None,
    description: str = "",
    category: str = "general",
    risk_level: str = "low",
) -> Callable:
    """
    独立版 @artclaw_tool 装饰器实现（不依赖 UE 运行时）。

    与 UE 侧 skill_hub.tool 签名及行为完全一致：
    - 注册到 _ARTCLAW_TOOL_REGISTRY
    - 在函数上设置 _ue_agent_tool / _ue_agent_tool_name 属性（向后兼容）
    - name 默认使用函数名
    - description 默认从 docstring 首行提取

    Args:
        name:        Tool 名称。默认使用函数名。
        description: Tool 描述，AI 可见。默认从 docstring 提取。
        category:    分类标签（general, material, lighting, layout, asset, …）
        risk_level:  风险级别（low, medium, high, critical）
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        tool_desc = description or (inspect.getdoc(func) or "").split("\n")[0]
        input_schema = _generate_schema_from_hints(func)

        _ARTCLAW_TOOL_REGISTRY[tool_name] = {
            "name": tool_name,
            "description": tool_desc,
            "category": category,
            "risk_level": risk_level,
            "input_schema": input_schema,
            "handler": func,
            "module": func.__module__,
            "source_file": (
                inspect.getfile(func) if hasattr(func, "__code__") else None
            ),
        }

        # 与 UE 侧 skill_hub.tool 相同的元数据标记（向后兼容）
        func._ue_agent_tool = True
        func._ue_agent_tool_name = tool_name

        return func

    return decorator


# ---------------------------------------------------------------------------
# 导出：优先使用 skill_hub.tool，否则使用独立实现
# ---------------------------------------------------------------------------

if _skill_hub_tool is not None:
    #: 来自 UE 侧 skill_hub（功能完整，含 MCP 注册）
    artclaw_tool = _skill_hub_tool
else:
    #: 独立实现（纯 Python/CLI 环境，功能最小化）
    artclaw_tool = _artclaw_tool_standalone  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 公共工具函数
# ---------------------------------------------------------------------------

def get_registered_tools() -> Dict[str, dict]:
    """
    获取通过独立实现注册的所有工具。

    注意：若使用了 UE 侧 skill_hub.tool，工具注册在 skill_hub._DECORATED_SKILLS 中，
    此函数仅返回通过独立实现注册的工具（CLI/测试环境）。

    :return: {tool_name: tool_info_dict}
    """
    return dict(_ARTCLAW_TOOL_REGISTRY)


def is_artclaw_tool(func: Callable) -> bool:
    """
    判断函数是否已被 @artclaw_tool（或 @ue_tool）装饰。

    :return: True 表示已装饰
    """
    return bool(getattr(func, "_ue_agent_tool", False))


def get_tool_name(func: Callable) -> Optional[str]:
    """
    获取被 @artclaw_tool 装饰的函数的工具名称。

    :return: 工具名称字符串，未装饰时返回 None
    """
    return getattr(func, "_ue_agent_tool_name", None)
