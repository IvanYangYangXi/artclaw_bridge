"""
save_intercept.py — DCC 事件拦截本地检查器
==========================================

在 UE Python 环境中直接运行，不依赖 Tool Manager HTTP 服务。
读取 ~/.artclaw/triggers.json 匹配各种 pre 类型事件规则，
执行对应工具脚本，返回 allow/reject 结果。

支持的事件类型：
- asset.save.pre: 资产保存前检查
- asset.delete.pre: 资产删除前检查  
- asset.import.pre: 资产导入前检查

C++ 调用方式:
    from save_intercept import check_pre_save, check_pre_delete, check_pre_import
    
    # 保存检查
    result = check_pre_save(asset_path, asset_name, file_name)
    
    # 删除检查
    result = check_pre_delete(asset_paths)
    
    # 导入检查
    result = check_pre_import(source_file, factory_class)
    
    # 所有返回格式: {"blocked": bool, "reason": str}
"""
from __future__ import annotations

import importlib
import inspect
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 自动切换到 UE 日志后端（在 UE Python 环境中 sys.stdout 会被路由成 Error 级别）
try:
    from artclaw_sdk import logger as _sdk_logger
    _sdk_logger.configure_for_dcc("ue")
except Exception:
    pass

import logging as _logging
logger = _logging.getLogger("dcc_event_intercept")


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
    """读取 ~/.artclaw/triggers.json"""
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


def _resolve_tool_path(tool_id: str, config: Dict[str, Any]) -> Optional[str]:
    """根据 tool_id 找到工具目录路径。
    
    tool_id 格式: "{source}/{tool_name}" e.g. "marketplace/SM 命名检查"
    工具目录: {project_root}/tools/{source}/{dcc}/{tool_name}/
    
    匹配策略:
    1. 直接匹配目录名
    2. 遍历目录读 manifest.json 的 id 或 name 字段匹配
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
    
    # 搜索所有 DCC 子目录
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


def _ensure_sdk_path(config: Dict[str, Any]) -> None:
    """确保 artclaw_sdk 在 sys.path 中。"""
    project_root = config.get("project_root", "")
    if not project_root:
        return
    sdk_dir = os.path.join(project_root, "subprojects", "DCCClawBridge", "core")
    if os.path.isdir(os.path.join(sdk_dir, "artclaw_sdk")) and sdk_dir not in sys.path:
        sys.path.insert(0, sdk_dir)


def _match_filters(conditions: Dict[str, Any], asset_path: str, asset_name: str, asset_class: str = "") -> bool:
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



def _get_asset_class(asset_path: str) -> str:
    """查询资产类型。使用 AssetRegistry 获取 asset_class。"""
    try:
        import unreal
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        asset_data = registry.get_asset_by_object_path(asset_path)
        if asset_data.is_valid():
            return str(asset_data.asset_class_path.asset_name)
    except Exception:
        pass
    return ""


def _match_event(trigger: Dict[str, Any], event_base: str, timing: str) -> bool:
    """判断一条 trigger 规则是否匹配指定的事件类型和时序。

    event_type 字段存储完整值，timing 已编码在其中：
      e.g. "asset.save.pre"、"asset.save.post"、"file.save.pre"

    匹配规则：event_type 必须完全等于 "{event_base}.{timing}"
    """
    return trigger.get("event_type", "") == f"{event_base}.{timing}"


def _check_pre_event(event_base: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """通用 pre 事件检查。

    Args:
        event_base: 事件基础名，如 "asset.save"
        event_data: 事件上下文数据

    Returns:
        {"blocked": bool, "reason": str, "execution_mode": str}
    """
    result = {"blocked": False, "reason": ""}

    try:
        config = _load_config()
        _ensure_sdk_path(config)
        triggers = _load_triggers()

        matched_rules = []
        for t in triggers:
            if not t.get("is_enabled", True) or t.get("trigger_type") != "event":
                continue
            if _match_event(t, event_base, "pre"):
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

            # 加载 manifest
            manifest_path = os.path.join(tool_path, "manifest.json")
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception:
                continue

            # 筛选条件检查
            use_default = rule.get("use_default_filters", False)
            if use_default:
                conditions = manifest.get("defaultFilters", {})
            else:
                conditions = rule.get("conditions", {})
            if not _match_filters(conditions, asset_path, asset_name, asset_class):
                continue

            # 执行工具
            tool_result = _execute_tool_generic(tool_path, manifest, event_data)

            # 检查 reject
            action = tool_result.get("action", "allow")
            if action == "reject":
                exec_mode = rule.get("execution_mode", "notify")
                result["blocked"] = True
                result["reason"] = tool_result.get("reason", "Blocked by trigger rule")
                result["execution_mode"] = exec_mode
                break  # 第一个 reject 即拦截

    except Exception as e:
        logger.error("event_intercept error: %s", e)
        # 出错时放行，不阻塞用户工作

    return result


def _execute_tool_generic(tool_path: str, manifest: Dict[str, Any], event_data: Dict[str, Any]) -> Dict[str, Any]:
    """通用工具执行函数，支持任意事件数据。"""
    impl = manifest.get("implementation", {})
    entry = impl.get("entry", "main.py")
    function = impl.get("function", "main")
    
    # 将工具目录加入 sys.path
    if tool_path not in sys.path:
        sys.path.insert(0, tool_path)
    
    try:
        module_name = entry.replace(".py", "")
        # 如果已经导入过，重新加载以获取最新代码
        if module_name in sys.modules:
            mod = importlib.reload(sys.modules[module_name])
        else:
            mod = importlib.import_module(module_name)
        
        fn = getattr(mod, function)
        
        # 调用函数（兼容不同签名）
        sig = inspect.signature(fn)
        param_names = list(sig.parameters.keys())
        
        if "params" in param_names and "event_data" in param_names:
            result = fn(params={}, event_data=event_data)
        elif "event_data" in param_names:
            result = fn(event_data=event_data)
        elif param_names:
            # **kwargs 支持
            result = fn(**event_data.get("data", {}), event_data=event_data)
        else:
            result = fn()
        
        return result if isinstance(result, dict) else {}
        
    except Exception as e:
        err_msg = f"[ArtClaw] Tool execution error [{os.path.basename(tool_path)}]: {e}"
        logger.warning(err_msg)
        try:
            import unreal
            unreal.log_warning(err_msg)
        except Exception:
            pass
        return {"action": "error", "reason": str(e)}
    finally:
        # 清理 sys.path
        if tool_path in sys.path:
            sys.path.remove(tool_path)


def check_pre_save(asset_path: str, asset_name: str, file_name: str = "") -> Dict[str, Any]:
    """保存前检查入口。
    
    读取 triggers.json，匹配 asset.save pre 规则，执行工具脚本。
    
    Returns:
        {"blocked": bool, "reason": str}
    """
    # 补全资产路径: Package path → Asset path (PackageName.AssetName)
    full_asset_path = asset_path
    if "." not in asset_path.rsplit("/", 1)[-1]:
        full_asset_path = f"{asset_path}.{asset_name}"
    
    # 查询资产类型
    asset_class = _get_asset_class(full_asset_path)
    
    # 构建事件数据
    event_data = {
        "dcc_type": "ue5",
        "event_type": "asset.save",
        "timing": "pre",
        "data": {
            "asset_path": full_asset_path,
            "asset_name": asset_name,
            "asset_class": asset_class,
            "file_name": file_name,
            "package_path": asset_path,
        },
    }
    
    return _check_pre_event("asset.save", event_data)


def check_pre_delete(asset_paths: List[str]) -> Dict[str, Any]:
    """删除前检查入口。
    
    Args:
        asset_paths: 批量删除的资产路径列表
        
    Returns:
        {"blocked": bool, "reason": str}
    """
    if not asset_paths:
        return {"blocked": False, "reason": ""}
    
    # 获取第一个资产的基本信息用于事件数据
    first_path = asset_paths[0]
    asset_name = first_path.rsplit("/", 1)[-1].split(".")[0] if "." in first_path else first_path.rsplit("/", 1)[-1]
    
    # 查询第一个资产的类型
    asset_class = _get_asset_class(first_path)
    
    # 构建事件数据
    event_data = {
        "dcc_type": "ue5", 
        "event_type": "asset.delete",
        "timing": "pre",
        "data": {
            "asset_paths": asset_paths,
            "asset_path": first_path,
            "asset_name": asset_name,
            "asset_class": asset_class,
        },
    }
    
    return _check_pre_event("asset.delete", event_data)


# ------------------------------------------------------------------
# Post 事件处理（不拦截，执行工具 + 通知）
# ------------------------------------------------------------------

def handle_post_save(asset_path: str, asset_name: str) -> Dict[str, Any]:
    """保存后执行检查工具。
    
    匹配 asset.save post 规则，执行工具并返回结果。
    不拦截，仅用于检查 + 通知。
    
    Returns:
        {"executed": int, "issues": list}
    """
    full_asset_path = asset_path
    if "." not in asset_path.rsplit("/", 1)[-1]:
        full_asset_path = f"{asset_path}.{asset_name}"
    
    asset_class = _get_asset_class(full_asset_path)
    
    event_data = {
        "dcc_type": "ue5",
        "event_type": "asset.save",
        "timing": "post",
        "data": {
            "asset_path": full_asset_path,
            "asset_name": asset_name,
            "asset_class": asset_class,
            "package_path": asset_path,
        },
    }
    
    return _handle_post_event("asset.save", event_data)   # matches event_type "asset.save.post"


def handle_post_delete(asset_path: str, asset_name: str) -> Dict[str, Any]:
    """删除后执行检查工具。"""
    event_data = {
        "dcc_type": "ue5",
        "event_type": "asset.delete",
        "timing": "post",
        "data": {
            "asset_path": asset_path,
            "asset_name": asset_name,
        },
    }
    return _handle_post_event("asset.delete", event_data)   # matches event_type "asset.delete.post"


def handle_actor_placed(actor_path: str, actor_name: str, actor_class: str) -> Dict[str, Any]:
    """Actor 放置到场景后执行检查工具。

    匹配 asset.place.post 规则，执行工具并返回结果。
    actor_path 是 Actor 在关卡中的路径，需要额外获取其源资产路径。
    """
    # C++ 侧已直接传入源资产路径（如 /Game/Foo/Bar），无需 Python 二次查询
    event_data = {
        "dcc_type": "ue5",
        "event_type": "asset.place",
        "timing": "post",
        "data": {
            "asset_path": actor_path,    # 源资产路径（C++ 已从 StaticMeshComponent 提取）
            "asset_name": actor_name,
            "asset_class": actor_class,
        },
    }
    return _handle_post_event("asset.place", event_data)   # matches event_type "asset.place.post"


def handle_post_import(asset_path: str, asset_class: str) -> Dict[str, Any]:
    """导入后执行检查工具。"""
    asset_name = asset_path.rsplit("/", 1)[-1].split(".")[0] if asset_path else ""
    event_data = {
        "dcc_type": "ue5",
        "event_type": "asset.import",
        "timing": "post",
        "data": {
            "asset_path": asset_path,
            "asset_name": asset_name,
            "asset_class": asset_class,
        },
    }
    return _handle_post_event("asset.import", event_data)   # matches event_type "asset.import.post"


# 用于 C++ 读取 post 事件通知结果的临时文件路径
_PENDING_NOTIFY_PATH = str(Path.home() / ".artclaw" / "_pending_notify.json")


def _notify_ue(reason: str, exec_mode: str, asset_path: str = "") -> None:
    """根据 execution_mode 向 UE 发送通知。

    通知策略：
    - silent : unreal.log_warning + 写 pending 文件（C++ FlushPendingNotify 弹气泡）
               后者仅对 save 事件生效；对 place 等事件，气泡通过 Python 直接调用
    - notify : unreal.EditorDialog 阻塞对话框（Python 直接弹）
               失败时回退写 pending 文件由 C++ 弹对话框
    """
    try:
        import unreal
        label = asset_path.rsplit("/", 1)[-1] if asset_path else "Asset"
        unreal.log_warning(f"[ArtClaw] {label}: {reason}")

        mode = exec_mode.lower() if exec_mode else "silent"

        if mode == "notify":
            # 直接弹阻塞对话框
            try:
                unreal.EditorDialog.show_message(
                    unreal.Text("ArtClaw"),
                    unreal.Text(reason),
                    unreal.AppMsgType.OK,
                )
                # 写 handled，防止 C++ FlushPendingNotify 重复弹
                _write_pending({"mode": "handled", "message": reason, "asset_path": asset_path})
                return
            except Exception:
                pass  # 回退：让 C++ 弹对话框

        # silent 或 notify 回退：写 pending 文件
        # - save 事件：C++ HandlePackageSaved 调 FlushPendingNotify 消费
        # - place / 其他事件：同时用 Python 直接弹气泡（不依赖 C++ 轮询）
        _write_pending({"mode": mode, "message": reason, "asset_path": asset_path})
        _show_slate_notification(label, reason)

    except Exception:
        pass


def _write_pending(payload: dict) -> None:
    """写 pending 通知文件，供 C++ FlushPendingNotify 消费（save 事件路径）。"""
    try:
        with open(_PENDING_NOTIFY_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception as ex:
        logger.warning("_write_pending failed: %s", ex)


def _show_slate_notification(title: str, message: str) -> None:
    """占位：气泡由 C++ FlushPendingNotify 在 Python 执行完后读取 pending 文件显示。
    
    对于 place/import 等非 save 事件，C++ 在调用 Python 后会显式调 FlushPendingNotify。
    此函数保留接口以备将来扩展。
    """
    pass


def _handle_post_event(event_base: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """通用 post 事件处理。匹配规则并执行工具，不拦截。"""
    result = {"executed": 0, "issues": []}
    
    try:
        config = _load_config()
        _ensure_sdk_path(config)
        triggers = _load_triggers()
        
        matched_rules = [
            t for t in triggers
            if t.get("is_enabled", True)
            and t.get("trigger_type") == "event"
            and _match_event(t, event_base, "post")
        ]
        
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

            # 筛选条件检查
            use_default = rule.get("use_default_filters", False)
            if use_default:
                conditions = manifest.get("defaultFilters", {})
            else:
                conditions = rule.get("conditions", {})
            if not _match_filters(conditions, asset_path, asset_name, asset_class):
                continue

            tool_result = _execute_tool_generic(tool_path, manifest, event_data)
            result["executed"] += 1
            
            action = tool_result.get("action", "allow")
            reason = tool_result.get("reason", "")
            
            if action == "reject":
                # 工具明确拒绝（有问题）：按 execution_mode 通知用户
                issue_reason = reason or "Issue found"
                result["issues"].append({"tool": tool_id, "reason": issue_reason})
                _notify_ue(issue_reason, exec_mode, asset_path)
            
            elif action == "error":
                # 工具执行出错：始终气泡提示（不用 notify 弹窗打断工作流）
                _notify_ue(f"工具执行错误: {reason}", "silent", asset_path)
    
    except Exception as e:
        logger.error("post event error: %s", e)
    
    return result

