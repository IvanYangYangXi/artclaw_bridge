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

from claw_bridge_logger import UELogger
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
    请求确认。

    1. 先检查静默模式（读 ~/.artclaw/config.json）— 如果已静默则直接通过
    2. 否则弹 UE 原生对话框（同步，不阻塞 Slate tick）

    注意: 不能用文件轮询等待 C++ 响应，因为 MCP handler 运行在 Slate tick
    驱动的 asyncio 中，time.sleep 会阻塞主线程导致死锁。

    宪法约束:
      - 开发路线图 §2.3: 强制触发物理确认
      - 核心机制 §4: 混合 UI 交互
    """
    import os

    level = risk_info.get("level", "unknown")
    reasons = risk_info.get("reasons", [])
    affected = risk_info.get("affected_count_estimate", 0)

    UELogger.warning(f"[Risk Confirmation] {level.upper()}: {reasons}")

    # --- 静默模式检查: 读 config.json ---
    try:
        config_path = os.path.join(os.path.expanduser("~"), ".artclaw", "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            silent_medium = cfg.get("silent_mode_medium", False)
            silent_high = cfg.get("silent_mode_high", False)

            if level == "medium" and silent_medium:
                UELogger.info(f"[Risk Confirmation] Auto-approved (silent mode medium)")
                return True
            if level == "high" and silent_high:
                UELogger.info(f"[Risk Confirmation] Auto-approved (silent mode high)")
                return True
            if level == "critical" and silent_high:
                # critical 也受 high 静默控制
                UELogger.info(f"[Risk Confirmation] Auto-approved (silent mode high covers critical)")
                return True
    except Exception as e:
        UELogger.warning(f"[Risk Confirmation] Config read error: {e}")

    # --- 非静默: 弹 UE 原生对话框 (同步，不阻塞 Slate tick) ---
    reason_text = "\n".join(f"  - {r}" for r in reasons)
    code_short = code_preview[:300] + ("..." if len(code_preview) > 300 else "")

    message = (
        f"Risk: {level.upper()}\n"
        f"Affected: ~{affected} objects\n\n"
        f"Reasons:\n{reason_text}\n\n"
        f"Code:\n{code_short}\n\n"
        f"Proceed?"
    )

    try:
        result = unreal.EditorDialog.show_message(
            f"AI Agent - {level.upper()} Risk",
            message,
            unreal.AppMsgType.YES_NO,
            unreal.AppReturnType.NO,
        )
        confirmed = (result == unreal.AppReturnType.YES)
    except Exception as e:
        UELogger.warning(f"[Risk Confirmation] Dialog error, auto-reject: {e}")
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
    """风险评估已内化到 run_ue_python 流程中，不再单独暴露为 MCP Tool。
    
    assess_operation_risk() 和 request_confirmation() 仍可被其他模块调用。
    """
    # assess_risk 已内化：AI 不需要单独调用，run_ue_python 内部自动评估
    UELogger.info("Phase 2.3: risk assessment available (internalized, no MCP tool)")


def _handle_assess_risk(arguments: dict) -> str:
    """MCP Tool handler for risk assessment."""
    code = arguments.get("code", "")
    risk_info = assess_operation_risk(code)
    return json.dumps(risk_info)
