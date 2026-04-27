"""
dcc_event_intercept_shared.py — 触发器执行层公共函数
=====================================================

从 UE dcc_event_intercept.py 提取的 DCC 无关公共逻辑。
所有 DCC（Blender / Maya / Max / UE 等）的 intercept 脚本均应 import 本模块，
只实现 DCC 特有的入口函数和通知函数。

用法：
    from dcc_event_intercept_shared import (
        _load_config, _load_triggers, _resolve_tool_path, _ensure_sdk_path,
        _match_filters, _match_event,
        _check_pre_event, _handle_post_event, _execute_tool_generic,
        _dedup_event,
    )
"""
from __future__ import annotations

import importlib
import inspect
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("artclaw.dcc_event_intercept")

# ── 去重保护：防止同一事件在极短时间内重复触发 ──────────────────────────────────
_recent_events: Dict[str, float] = {}
_DEDUP_WINDOW_SEC = 0.5   # 500ms 内同 key 只处理一次


def _dedup_event(key: str) -> bool:
    """返回 True 表示重复（应跳过），False 表示首次（应处理）。"""
    now = time.monotonic()
    if key in _recent_events and (now - _recent_events[key]) < _DEDUP_WINDOW_SEC:
        logger.debug("Dedup skipped: %s", key)
        return True
    _recent_events[key] = now
    return False


# ── 配置 / 触发器加载 ────────────────────────────────────────────────────────

def _load_config() -> Dict[str, Any]:
    """读取 ~/.artclaw/config.json"""
    cfg_path = Path.home() / ".artclaw" / "config.json"
    if not cfg_path.exists():
        return {}
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _load_triggers() -> List[Dict[str, Any]]:
    """读取 ~/.artclaw/triggers.json（由 Tool Manager 启动时同步写入）。"""
    triggers_path = Path.home() / ".artclaw" / "triggers.json"
    if not triggers_path.exists():
        return []
    try:
        with open(triggers_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return data
    except Exception:
        return []


def _ensure_sdk_path(config: Dict[str, Any]) -> None:
    """将 {project_root}/subprojects/DCCClawBridge/core 加入 sys.path。"""
    project_root = config.get("project_root", "")
    if not project_root:
        return
    sdk_dir = os.path.join(project_root, "subprojects", "DCCClawBridge", "core")
    if os.path.isdir(os.path.join(sdk_dir, "artclaw_sdk")) and sdk_dir not in sys.path:
        sys.path.insert(0, sdk_dir)


# ── 工具路径解析 ─────────────────────────────────────────────────────────────

def _resolve_tool_path(tool_id: str, config: Dict[str, Any]) -> Optional[str]:
    """根据 tool_id 找到工具目录路径。

    tool_id 格式: "{source}/{tool_name}"  e.g. "marketplace/SM 命名检查"
    工具目录搜索：{project_root}/tools/{source}/**/{tool_name}/

    匹配策略：
    1. 目录名直接匹配（含/不含空格差异兼容）
    2. 遍历 manifest.json 的 id 或 name 字段匹配
    """
    project_root = config.get("project_root", "")
    if not project_root:
        return None

    parts = tool_id.split("/", 1)
    if len(parts) != 2:
        return None
    source, tool_name = parts

    tools_base = os.path.join(project_root, "tools", source)
    if not os.path.isdir(tools_base):
        return None

    # 搜索所有 DCC 子目录（如 blender / ue / maya 等）
    for dcc_dir in os.listdir(tools_base):
        dcc_path = os.path.join(tools_base, dcc_dir)
        if not os.path.isdir(dcc_path):
            continue

        for item_dir in os.listdir(dcc_path):
            candidate = os.path.join(dcc_path, item_dir)
            manifest_file = os.path.join(candidate, "manifest.json")
            if not os.path.isfile(manifest_file):
                continue

            # 策略 1: 目录名直接匹配（含/不含空格）
            if item_dir == tool_name or item_dir.replace(" ", "") == tool_name.replace(" ", ""):
                return candidate

            # 策略 2: manifest 的 id 或 name 匹配
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                m_id = manifest.get("id", "")
                m_name = manifest.get("name", "")
                if m_id == tool_id or m_name == tool_name:
                    return candidate
            except Exception:
                continue

    return None


# ── 条件匹配 ─────────────────────────────────────────────────────────────────

def _match_filters(
    conditions: Dict[str, Any],
    asset_path: str,
    asset_name: str,
    asset_class: str = "",
) -> bool:
    """条件匹配：path glob + typeFilter.types。空条件 = 全部匹配。"""
    if not conditions:
        return True

    import fnmatch

    # path 条件匹配（任意一条命中即通过）
    path_conditions = conditions.get("path", [])
    if path_conditions:
        matched = False
        for pc in path_conditions:
            pattern = pc.get("pattern", "")
            if not pattern:
                continue
            # 支持路径前缀匹配（去掉尾部 /**/* 后做 startswith）
            base = pattern.rstrip("/*")
            if asset_path.startswith(base) or fnmatch.fnmatch(asset_path, pattern):
                matched = True
                break
        if not matched:
            return False

    # typeFilter 匹配（asset_class 在列表中即通过）
    type_filter = conditions.get("typeFilter", {})
    allowed_types = type_filter.get("types", []) if type_filter else []
    if allowed_types and asset_class:
        if asset_class not in allowed_types:
            return False

    return True


# ── 事件类型匹配 ─────────────────────────────────────────────────────────────

def _match_event(trigger: Dict[str, Any], event_base: str, timing: str) -> bool:
    """判断 trigger 规则是否匹配指定的事件类型和时序。

    event_type 字段格式："{base}.{timing}"，如 "asset.save.pre"。
    精确等于匹配，无兼容逻辑。
    """
    return trigger.get("event_type", "") == f"{event_base}.{timing}"


# ── 通用工具执行 ─────────────────────────────────────────────────────────────

def _execute_tool_generic(
    tool_path: str,
    manifest: Dict[str, Any],
    event_data: Dict[str, Any],
) -> Dict[str, Any]:
    """通用工具执行函数，支持任意事件数据。

    动态 import + importlib.reload（热更新支持）。
    函数签名自适应：
      1. params + event_data → fn(params={}, event_data=event_data)
      2. 只有 event_data    → fn(event_data=event_data)
      3. 其他参数 / **kwargs → fn(**event_data.get("data", {}), event_data=event_data)
      4. 无参数              → fn()

    Returns:
        {"action": "allow" | "reject" | "error", "reason": str}
    """
    impl = manifest.get("implementation", {})
    entry = impl.get("entry", "main.py")
    function = impl.get("function", "main")

    if tool_path not in sys.path:
        sys.path.insert(0, tool_path)

    try:
        module_name = entry.replace(".py", "")
        if module_name in sys.modules:
            mod = importlib.reload(sys.modules[module_name])
        else:
            mod = importlib.import_module(module_name)

        fn = getattr(mod, function)

        sig = inspect.signature(fn)
        param_names = list(sig.parameters.keys())

        if "params" in param_names and "event_data" in param_names:
            result = fn(params={}, event_data=event_data)
        elif "event_data" in param_names:
            result = fn(event_data=event_data)
        elif param_names:
            result = fn(**event_data.get("data", {}), event_data=event_data)
        else:
            result = fn()

        return result if isinstance(result, dict) else {}

    except Exception as e:
        err_msg = f"[ArtClaw] Tool execution error [{os.path.basename(tool_path)}]: {e}"
        logger.warning(err_msg)
        return {"action": "error", "reason": str(e)}
    finally:
        if tool_path in sys.path:
            sys.path.remove(tool_path)


# ── Pre 事件检查 ─────────────────────────────────────────────────────────────

def _check_pre_event(event_base: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """通用 pre 事件检查。

    Args:
        event_base: 事件基础名，如 "asset.save" / "file.save"
        event_data: 事件上下文数据

    Returns:
        {"blocked": bool, "reason": str, "execution_mode": str}

    注意：
        pre 事件中第一个 reject 即拦截，后续规则不再执行。
        但 Blender 的 save_pre 不支持真正拦截，只能通知（上层函数处理）。
    """
    result: Dict[str, Any] = {"blocked": False, "reason": "", "execution_mode": "notify"}

    try:
        config = _load_config()
        _ensure_sdk_path(config)
        triggers = _load_triggers()

        event_dcc = event_data.get("dcc_type", "")
        seen_tool_ids: set = set()
        matched_rules = []
        for t in triggers:
            if not t.get("is_enabled", True) or t.get("trigger_type") != "event":
                continue
            if not _match_event(t, event_base, "pre"):
                continue
            # dcc 过滤：只执行匹配当前 DCC 的规则
            rule_dcc = t.get("dcc", "")
            if rule_dcc and event_dcc and rule_dcc != event_dcc:
                continue
            tid = t.get("tool_id", "")
            if tid in seen_tool_ids:
                logger.debug("Skipping duplicate tool_id rule: %s", tid)
                continue
            seen_tool_ids.add(tid)
            matched_rules.append(t)

        if not matched_rules:
            return result

        asset_path = event_data.get("data", {}).get("asset_path", "")
        asset_name = event_data.get("data", {}).get("asset_name", "")
        asset_class = event_data.get("data", {}).get("asset_class", "")

        for rule in matched_rules:
            tool_id = rule.get("tool_id", "")
            tool_path = _resolve_tool_path(tool_id, config)
            if not tool_path:
                logger.warning("Tool not found: %s", tool_id)
                continue

            manifest_path = os.path.join(tool_path, "manifest.json")
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception:
                continue

            use_default = rule.get("use_default_filters", False)
            conditions = manifest.get("defaultFilters", {}) if use_default else rule.get("conditions", {})
            if not _match_filters(conditions, asset_path, asset_name, asset_class):
                continue

            tool_result = _execute_tool_generic(tool_path, manifest, event_data)

            action = tool_result.get("action", "allow")
            if action == "reject":
                exec_mode = rule.get("execution_mode", "notify")
                result["blocked"] = True
                result["reason"] = tool_result.get("reason", "Blocked by trigger rule")
                result["execution_mode"] = exec_mode
                break  # 第一个 reject 即拦截

    except Exception as e:
        logger.error("_check_pre_event error: %s", e)

    return result


# ── Post 事件处理 ────────────────────────────────────────────────────────────

def _handle_post_event(event_base: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """通用 post 事件处理。匹配规则并执行工具，不拦截。

    Returns:
        {"executed": int, "issues": [{"tool": str, "reason": str}, ...]}
    """
    result: Dict[str, Any] = {"executed": 0, "issues": []}

    try:
        config = _load_config()
        _ensure_sdk_path(config)
        triggers = _load_triggers()

        event_dcc = event_data.get("dcc_type", "")
        seen_tool_ids: set = set()
        matched_rules = []
        for t in triggers:
            if not t.get("is_enabled", True) or t.get("trigger_type") != "event":
                continue
            if not _match_event(t, event_base, "post"):
                continue
            # dcc 过滤：只执行匹配当前 DCC 的规则
            rule_dcc = t.get("dcc", "")
            if rule_dcc and event_dcc and rule_dcc != event_dcc:
                continue
            tid = t.get("tool_id", "")
            if tid in seen_tool_ids:
                continue
            seen_tool_ids.add(tid)
            matched_rules.append(t)

        if not matched_rules:
            return result

        asset_path = event_data.get("data", {}).get("asset_path", "")
        asset_name = event_data.get("data", {}).get("asset_name", "")
        asset_class = event_data.get("data", {}).get("asset_class", "")

        for rule in matched_rules:
            tool_id = rule.get("tool_id", "")
            exec_mode = rule.get("execution_mode", "silent")
            tool_path = _resolve_tool_path(tool_id, config)
            if not tool_path:
                continue

            manifest_path = os.path.join(tool_path, "manifest.json")
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception:
                continue

            use_default = rule.get("use_default_filters", False)
            conditions = manifest.get("defaultFilters", {}) if use_default else rule.get("conditions", {})
            if not _match_filters(conditions, asset_path, asset_name, asset_class):
                continue

            tool_result = _execute_tool_generic(tool_path, manifest, event_data)
            result["executed"] += 1

            action = tool_result.get("action", "allow")
            reason = tool_result.get("reason", "")

            if action in ("reject", "error"):
                issue_reason = reason or ("Issue found" if action == "reject" else "Tool execution error")
                result["issues"].append({"tool": tool_id, "reason": issue_reason})
                # 通知由各 DCC 的 intercept 层在调用方处理，此处只收集

    except Exception as e:
        logger.error("_handle_post_event error: %s", e)

    return result
