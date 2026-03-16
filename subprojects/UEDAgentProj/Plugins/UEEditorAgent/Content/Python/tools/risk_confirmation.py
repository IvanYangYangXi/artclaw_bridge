"""
risk_confirmation.py - 风险分级确认 (Risk-Aware Confirmation)
===============================================================

阶段 2.3: 对高危操作强制触发确认对话框。

宪法约束:
  - 开发路线图 §2.3: C++ 实现原生 Slate 模态对话框
  - 开发路线图 §2.3: 高危操作 (delete/修改>50 Actor/保存) 强制物理确认
  - 核心机制 §4: 混合 UI 交互，关键节点协同

设计说明:
  由于 UE Python API 不直接支持模态对话框，
  本实现使用 unreal.EditorDialog 或 Python 侧的消息框作为过渡方案。
  后续可通过 C++ Slate 实现更精致的 UI。
"""

import json
import re
from typing import Optional

import unreal

from init_unreal import UELogger
from tools.static_guard import RiskLevel


# ============================================================================
# 1. 风险评估
# ============================================================================

# 高危操作关键词
_DELETE_KEYWORDS = {"delete", "destroy", "remove", "clear_level", "remove_actor"}
_SAVE_KEYWORDS = {"save_asset", "save_package", "save_map", "save_current_level"}
_BULK_THRESHOLD = 50  # 影响超过此数量的 Actor 视为高危


def assess_operation_risk(code: str, context: dict = None) -> dict:
    """
    评估代码的操作风险等级。

    宪法约束:
      - 开发路线图 §2.3: 风险等级自动计算（基于影响范围）

    Returns:
        {
            "level": "low" | "medium" | "high" | "critical",
            "reasons": [...],
            "requires_confirmation": bool,
            "affected_count_estimate": int,
        }
    """
    reasons = []
    level = "low"
    affected_estimate = 0

    code_lower = code.lower()

    # 检查删除操作
    for kw in _DELETE_KEYWORDS:
        if kw in code_lower:
            level = "high"
            reasons.append(f"Contains delete operation: '{kw}'")

    # 检查保存操作
    for kw in _SAVE_KEYWORDS:
        if kw in code_lower:
            if level != "high":
                level = "medium"
            reasons.append(f"Contains save operation: '{kw}'")

    # 检查批量操作（循环 + Actor 操作）
    if ("for " in code_lower or "while " in code_lower):
        if any(kw in code_lower for kw in ("get_all_level_actors", "get_all_actors")):
            level = "high"
            reasons.append("Bulk operation: iterating over all level actors")
            # 估算受影响数量
            try:
                actors = unreal.EditorLevelLibrary.get_all_level_actors()
                affected_estimate = len(actors)
            except Exception:
                affected_estimate = _BULK_THRESHOLD + 1

    # 检查影响范围
    if context:
        sel_count = context.get("selection_count", 0)
        if sel_count > _BULK_THRESHOLD:
            if level == "low":
                level = "medium"
            reasons.append(f"Operating on {sel_count} selected actors (>{_BULK_THRESHOLD})")
            affected_estimate = max(affected_estimate, sel_count)

    # 检查数字参数（大量生成）
    numbers = re.findall(r'\b(\d+)\b', code)
    for n in numbers:
        if int(n) > _BULK_THRESHOLD:
            if level == "low":
                level = "medium"
            reasons.append(f"Large number detected: {n} (potential bulk operation)")
            affected_estimate = max(affected_estimate, int(n))

    requires_confirmation = level in ("high", "critical")

    return {
        "level": level,
        "reasons": reasons,
        "requires_confirmation": requires_confirmation,
        "affected_count_estimate": affected_estimate,
    }


# ============================================================================
# 2. 确认对话框
# ============================================================================

def request_confirmation(risk_info: dict, code_preview: str = "") -> bool:
    """
    弹出确认对话框。

    宪法约束:
      - 开发路线图 §2.3: 强制触发物理确认
      - 核心机制 §4: 混合 UI 交互

    当前使用 unreal.EditorDialog.show_message 实现。
    """
    level = risk_info.get("level", "unknown")
    reasons = risk_info.get("reasons", [])
    affected = risk_info.get("affected_count_estimate", 0)

    # 构建消息文本
    title = f"AI Agent - {level.upper()} Risk Operation"

    reason_text = "\n".join(f"  • {r}" for r in reasons)
    code_short = code_preview[:200] + ("..." if len(code_preview) > 200 else "")

    message = (
        f"Risk Level: {level.upper()}\n"
        f"Estimated affected objects: {affected}\n\n"
        f"Reasons:\n{reason_text}\n\n"
        f"Code preview:\n{code_short}\n\n"
        f"Do you want to proceed?"
    )

    UELogger.warning(f"[Risk Confirmation] {level.upper()}: {reasons}")

    try:
        # 使用 UE 原生对话框
        result = unreal.EditorDialog.show_message(
            title,
            message,
            unreal.AppMsgType.YES_NO,
            unreal.AppReturnType.NO,  # 默认选中 NO（安全）
        )
        confirmed = (result == unreal.AppReturnType.YES)
    except Exception as e:
        UELogger.warning(f"Dialog fallback: auto-reject ({e})")
        confirmed = False

    if confirmed:
        UELogger.info(f"[Risk Confirmation] User CONFIRMED {level} operation")
    else:
        UELogger.info(f"[Risk Confirmation] User REJECTED {level} operation")

    return confirmed


# ============================================================================
# 3. MCP 注册
# ============================================================================

def register_tools(mcp_server) -> None:
    """注册风险确认工具。"""

    mcp_server.register_tool(
        name="assess_risk",
        description=(
            "Assess the risk level of Python code before execution. "
            "Returns risk level (low/medium/high/critical), reasons, and whether confirmation is required. "
            "Call this before run_ue_python for potentially dangerous operations."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to assess",
                },
            },
            "required": ["code"],
        },
        handler=_handle_assess_risk,
    )

    UELogger.info("Phase 2.3 tools registered: assess_risk")


def _handle_assess_risk(arguments: dict) -> str:
    """MCP Tool handler for risk assessment."""
    code = arguments.get("code", "")
    risk_info = assess_operation_risk(code)
    return json.dumps(risk_info)
