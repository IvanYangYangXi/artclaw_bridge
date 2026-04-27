#!/usr/bin/env python3
"""
ArtClaw Tool Compliance Checker v3.0

扫描工具目录，对照 docs/specs/tool-manifest-spec.md 进行合规检查（29 条规则）。

路径来源：
  优先从自身 manifest.json 的 defaultFilters.path 读取（$variable 路径变量）
  手动运行 / watch 触发 / 定时触发 共用同一套路径。
"""
# ── SDK 头 ──
import os, json
import artclaw_sdk as sdk

def _load_manifest() -> dict:
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)
# ── SDK 头结束 ──

import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set


# ============================================================================
# 路径变量解析（与 trigger-mechanism.md 规范对齐）
# ============================================================================

def _resolve_path_variables() -> Dict[str, str]:
    """
    解析路径变量映射表。与 manifest.json filters.path 中的 $variable 对应。
    """
    cfg_path = Path.home() / ".artclaw" / "config.json"
    project_root = ""

    try:
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            project_root = cfg.get("project_root", "")
    except Exception:
        pass

    return {
        "$skills_installed": str(Path.home() / ".openclaw" / "workspace" / "skills"),
        "$project_root": project_root,
        "$tools_dir": str(Path.home() / ".artclaw" / "tools"),
        "$home": str(Path.home()),
    }


def _resolve_pattern(pattern: str, variables: Dict[str, str]) -> Optional[str]:
    """将 $variable/... 模式解析为绝对路径。变量值为空则返回 None。"""
    for var, value in variables.items():
        if pattern.startswith(var):
            if not value:
                return None
            resolved = pattern.replace(var, value, 1)
            return resolved.replace("/", os.sep)
    return pattern.replace("/", os.sep)


def _get_scan_dirs_from_manifest() -> List[str]:
    """
    从自身 manifest.json 读取扫描路径。
    
    读取来源: defaultFilters.path（工具级默认筛选条件）。
    这是脚本运行时的唯一路径来源，不从 triggers[].filters 读取
    （triggers 的 filters 由触发引擎处理，脚本不关心）。
    
    解析 $variable，返回去重后的目录列表。
    """
    manifest_path = Path(__file__).parent / "manifest.json"
    if not manifest_path.exists():
        return []

    variables = _resolve_path_variables()
    dirs: List[str] = []

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        
        default_filters = manifest.get("defaultFilters", {})
        for pf in default_filters.get("path", []):
            pattern = pf.get("pattern", "")
            if not pattern:
                continue
            base = pattern.split("/**")[0].split("/*")[0]
            resolved = _resolve_pattern(base, variables)
            if resolved and resolved not in dirs:
                dirs.append(resolved)
    except Exception:
        pass

    return dirs


def _get_source_tool_names(project_root: str) -> set:
    """从 project_root/tools/ 扫描源码工具名集合，返回 {layer/tool_name} 集合。
    支持 flat 和 nested 两种布局。"""
    if not project_root:
        raise RuntimeError(
            "project_root 未配置。请在 ~/.artclaw/config.json 中指定。"
        )
    source_tools_root = Path(project_root) / "tools"
    if not source_tools_root.exists():
        raise RuntimeError(
            f"project_root/tools 目录不存在: {source_tools_root}\n"
            "请确认 ArtClaw 已正确安装，project_root 配置正确。"
        )
    names = set()
    for layer_dir in source_tools_root.iterdir():
        if not layer_dir.is_dir():
            continue
        for child in layer_dir.iterdir():
            if not child.is_dir():
                continue
            if (child / "manifest.json").exists():
                # Flat: layer/tool-name
                names.add(f"{layer_dir.name}/{child.name}")
            else:
                # Nested: layer/dcc/tool-name
                for tool_dir in child.iterdir():
                    if tool_dir.is_dir() and (tool_dir / "manifest.json").exists():
                        names.add(f"{layer_dir.name}/{tool_dir.name}")
    return names


def check_compliance(**kwargs) -> Dict[str, Any]:
    """
    检查工具合规性。
    
    路径来源优先级：
      1. 调用参数 tools_dir（非空时使用）
      2. 自身 manifest.json 的 triggers[].filters.path（$variable 解析）
      3. 默认值 ~/.artclaw/tools
    
    Args:
        tools_dir: 工具目录路径（为空时从 manifest filters 读取）
        fix_simple: 是否自动修复简单问题（如空版本号）
        source_only: 只检查在项目源码目录里有源码的工具（默认True）
        
    Returns:
        检查结果字典: {total_checked, issues_found, issues: [...], report}
    """
    manifest = _load_manifest()
    parsed = sdk.params.parse_params(manifest.get("inputs", []), kwargs)
    
    tools_dir = parsed.get("tools_dir", "")
    fix_simple = parsed.get("fix_simple", False)
    source_only = parsed.get("source_only", False)  # 默认 False，与 manifest inputs default 一致
    # 路径解析：manifest filters 优先
    if tools_dir:
        scan_dirs = [str(Path(tools_dir).expanduser())]
    else:
        scan_dirs = _get_scan_dirs_from_manifest()
        if not scan_dirs:
            scan_dirs = [str(Path.home() / ".artclaw" / "tools")]

    # 验证至少有一个有效目录
    valid_dirs = [d for d in scan_dirs if Path(d).exists()]
    if not valid_dirs:
        return sdk.result.fail("NO_VALID_DIRS", f"工具目录不存在: {', '.join(scan_dirs)}", data={
            "total_checked": 0,
            "issues_found": 0,
            "issues": [],
            "report": f"工具目录不存在: {', '.join(scan_dirs)}",
            "success": False
        })
    
    # 获取源码工具名集合
    variables = _resolve_path_variables()
    project_root = variables.get("$project_root", "")
    
    if source_only:
        try:
            source_names = _get_source_tool_names(project_root)
        except RuntimeError as e:
            return sdk.result.fail("GET_SOURCE_ERROR", str(e), data={
                "total_checked": 0,
                "issues_found": 1,
                "issues": [{"tool_id": "system", "severity": "error", "message": str(e)}],
                "report": f"❌ 无法获取源码工具列表：{e}\n\n请检查 ArtClaw 安装配置。",
                "success": False
            })
    else:
        source_names = None  # 检查全部

    issues = []
    total_checked = 0
    
    # 扫描所有目录
    for tools_path in valid_dirs:
        tools_path = Path(tools_path)
        
        # 扫描 {layer}/{dcc_or_tool}/{tool-name?}/
        # 支持两种布局:
        #   Flat:   {layer}/{tool-name}/manifest.json
        #   Nested: {layer}/{dcc}/{tool-name}/manifest.json
        for layer_dir in tools_path.iterdir():
            if not layer_dir.is_dir():
                continue
                
            for child in layer_dir.iterdir():
                if not child.is_dir():
                    continue
                
                if (child / "manifest.json").exists():
                    # Flat layout: child is tool dir
                    tool_id = f"{layer_dir.name}/{child.name}"
                    if source_names is not None and tool_id not in source_names:
                        continue
                    total_checked += 1
                    tool_issues = _check_tool_compliance(child, tool_id, fix_simple)
                    issues.extend(tool_issues)
                else:
                    # Nested layout: child is dcc dir
                    for tool_dir in child.iterdir():
                        if not tool_dir.is_dir():
                            continue
                        if not (tool_dir / "manifest.json").exists():
                            continue
                        tool_id = f"{layer_dir.name}/{tool_dir.name}"
                        if source_names is not None and tool_id not in source_names:
                            continue
                        total_checked += 1
                        tool_issues = _check_tool_compliance(tool_dir, tool_id, fix_simple)
                        issues.extend(tool_issues)
    
    # 生成报告
    report = _generate_report(total_checked, issues)
    
    # 调用报警 API
    _update_alerts(issues)
    
    result_data = {
        "total_checked": total_checked,
        "issues_found": len(issues),
        "issues": issues,
        "report": report,
        "success": len(issues) == 0
    }
    
    if len(issues) == 0:
        return sdk.result.success(data=result_data, message=report)
    else:
        return sdk.result.fail("COMPLIANCE_ISSUES", report, data=result_data)


def _check_tool_compliance(tool_dir: Path, tool_id: str, fix_simple: bool) -> List[Dict[str, str]]:
    """
    检查单个工具的合规性。
    规则定义见 docs/specs/tool-manifest-spec.md（共 29 条规则）。
    """
    issues = []
    manifest_path = tool_dir / "manifest.json"

    # ── Rule 1: manifest.json 必须存在 ──────────────────────────────────────
    if not manifest_path.exists():
        issues.append({"tool_id": tool_id, "severity": "error",
                        "message": "缺少 manifest.json 文件"})
        return issues

    # ── Rule 2: 必须是合法 JSON ──────────────────────────────────────────────
    raw_text = manifest_path.read_text(encoding="utf-8")
    try:
        manifest = json.loads(raw_text)
    except json.JSONDecodeError as e:
        issues.append({"tool_id": tool_id, "severity": "error",
                        "message": f"manifest.json JSON 格式错误: {e}"})
        return issues

    # ── Rule 3: 不得有顶层重复键（嵌套字段重名是合法的）────────────────────
    # 用 object_pairs_hook 检测顶层 object 的重复键（第一个调用对应顶层）
    _dup_record: list = []
    _call_count: list = [0]
    def _top_dup_hook(pairs):
        _call_count[0] += 1
        if _call_count[0] == 1:  # 只检查顶层 object
            seen: dict = {}
            dups: list = []
            for k, v in pairs:
                if k in seen:
                    dups.append(k)
                seen[k] = v
            _dup_record.extend(dups)
            return seen
        # 其他层级正常构建
        seen2: dict = {}
        for k, v in pairs:
            seen2[k] = v
        return seen2
    try:
        json.loads(raw_text, object_pairs_hook=_top_dup_hook)
    except Exception:
        pass
    if _dup_record:
        issues.append({"tool_id": tool_id, "severity": "error",
                        "message": f"manifest.json 存在顶层重复键: {', '.join(_dup_record)}（后者覆盖前者，前者静默丢失）"})

    # ── Rule 4: name 必填非空 ────────────────────────────────────────────────
    if not manifest.get("name"):
        issues.append({"tool_id": tool_id, "severity": "error",
                        "message": "缺少必填字段: name"})

    # ── Rule 5: implementation 必填非空对象 ──────────────────────────────────
    impl = manifest.get("implementation", None)
    if not impl or not isinstance(impl, dict):
        issues.append({"tool_id": tool_id, "severity": "error",
                        "message": "缺少必填字段: implementation（必须为对象）"})
        impl = {}
    else:
        # ── Rule 6: implementation.type 有效值 ──────────────────────────────
        valid_impl_types = {"script", "skill_wrapper", "composite"}
        impl_type = impl.get("type", "")
        if not impl_type:
            issues.append({"tool_id": tool_id, "severity": "error",
                            "message": "implementation 缺少 type 字段"})
        elif impl_type not in valid_impl_types:
            issues.append({"tool_id": tool_id, "severity": "error",
                            "message": f"implementation.type 无效: {impl_type!r}，有效值: {sorted(valid_impl_types)}"})

        # ── Rule 7: type=script 时 entry 必填且文件存在 ──────────────────────
        if impl_type == "script":
            entry = impl.get("entry", "")
            if not entry:
                issues.append({"tool_id": tool_id, "severity": "error",
                                "message": "implementation.type=script 时必须填写 entry（入口文件名）"})
            elif not (tool_dir / entry).exists():
                issues.append({"tool_id": tool_id, "severity": "error",
                                "message": f"入口文件不存在: {entry}"})
            if not impl.get("function"):
                issues.append({"tool_id": tool_id, "severity": "warning",
                                "message": "implementation.function 未填写，AI 执行时无法定位入口函数"})

        # ── Rule 8: type=skill_wrapper 时 skill 必填 ─────────────────────────
        if impl_type == "skill_wrapper" and not impl.get("skill"):
            issues.append({"tool_id": tool_id, "severity": "error",
                            "message": "implementation.type=skill_wrapper 时必须填写 skill（被包装的 Skill ID）"})

    # ── Rule 9: description 必填非空 ─────────────────────────────────────────
    if not manifest.get("description"):
        issues.append({"tool_id": tool_id, "severity": "warning",
                        "message": "缺少 description 字段"})

    # ── Rule 10: version 必填且符合 semver ──────────────────────────────────
    version = manifest.get("version", "")
    if not version:
        if fix_simple:
            manifest["version"] = "0.0.0"
            _save_manifest(manifest_path, manifest)
            issues.append({"tool_id": tool_id, "severity": "info",
                            "message": "已自动修复：设置默认版本 0.0.0"})
        else:
            issues.append({"tool_id": tool_id, "severity": "warning",
                            "message": "缺少 version 字段"})
    elif not _is_valid_semver(str(version)):
        if fix_simple:
            fixed = _fix_version_format(str(version))
            if fixed != str(version):
                manifest["version"] = fixed
                _save_manifest(manifest_path, manifest)
                issues.append({"tool_id": tool_id, "severity": "info",
                                "message": f"已自动修复版本格式: {version} → {fixed}"})
        else:
            issues.append({"tool_id": tool_id, "severity": "warning",
                            "message": f"version 格式不符合 semver (MAJOR.MINOR.PATCH): {version!r}"})

    # ── Rule 11: author 必填非空 ─────────────────────────────────────────────
    author = manifest.get("author", None)
    if author is None or str(author).strip() == "":
        issues.append({"tool_id": tool_id, "severity": "warning",
                        "message": "缺少 author 字段（建议填写作者名，官方工具用 ArtClaw）"})

    # ── Rule 12: source 必填且与文件夹层级一致 ───────────────────────────────
    valid_sources = {"official", "marketplace", "user"}
    manifest_source = manifest.get("source", "")
    if not manifest_source:
        issues.append({"tool_id": tool_id, "severity": "warning",
                        "message": "缺少 source 字段（有效值: official/marketplace/user）"})
    elif manifest_source not in valid_sources:
        issues.append({"tool_id": tool_id, "severity": "warning",
                        "message": f"source 无效值: {manifest_source!r}，有效值: {sorted(valid_sources)}"})
    else:
        folder_layer = tool_id.split("/")[0] if "/" in tool_id else ""
        if folder_layer and manifest_source != folder_layer:
            issues.append({"tool_id": tool_id, "severity": "warning",
                            "message": f"source 字段 {manifest_source!r} 与文件夹层级 {folder_layer!r} 不一致"})

    # ── Rule 13: id 必填且格式正确 ──────────────────────────────────────────
    manifest_id = manifest.get("id", "")
    if not manifest_id:
        issues.append({"tool_id": tool_id, "severity": "warning",
                        "message": "缺少 id 字段，格式应为 {source}/{name}"})
    else:
        parts = manifest_id.split("/")
        if len(parts) < 2:
            issues.append({"tool_id": tool_id, "severity": "warning",
                            "message": f"id 格式错误: {manifest_id!r}，应为 {{source}}/{{name}}"})
        elif parts[0] not in valid_sources:
            issues.append({"tool_id": tool_id, "severity": "warning",
                            "message": f"id 前缀 {parts[0]!r} 不是有效 source 值（official/marketplace/user）"})

    # ── Rule 14: targetDCCs 必填且元素合法 ──────────────────────────────────
    valid_dccs = {"ue5", "maya2024", "max2024", "blender", "comfyui", "sp", "sd", "houdini", "general"}
    target_dccs = manifest.get("targetDCCs", None)
    if target_dccs is None:
        issues.append({"tool_id": tool_id, "severity": "warning",
                        "message": "缺少 targetDCCs 字段（通用工具用 [] 或 [\"general\"]）"})
        target_dccs = []
    elif not isinstance(target_dccs, list):
        issues.append({"tool_id": tool_id, "severity": "error",
                        "message": f"targetDCCs 必须是数组，当前类型: {type(target_dccs).__name__}"})
        target_dccs = []
    else:
        for dcc in target_dccs:
            if dcc not in valid_dccs:
                issues.append({"tool_id": tool_id, "severity": "warning",
                                "message": f"targetDCCs 包含未知 DCC: {dcc!r}，有效值: {sorted(valid_dccs)}"})

    # ── Rule 15–17: inputs 参数校验 ─────────────────────────────────────────
    valid_param_types = {"string", "number", "boolean", "select", "image", "object", "array"}
    inputs = manifest.get("inputs", [])
    if not isinstance(inputs, list):
        issues.append({"tool_id": tool_id, "severity": "error",
                        "message": "inputs 必须是数组"})
    else:
        for i, inp in enumerate(inputs):
            if not isinstance(inp, dict):
                issues.append({"tool_id": tool_id, "severity": "warning",
                                "message": f"inputs[{i}] 不是对象"})
                continue
            for field in ("id", "name", "type"):
                if not inp.get(field):
                    issues.append({"tool_id": tool_id, "severity": "warning",
                                    "message": f"inputs[{i}] 缺少必填字段: {field}"})
            p_type = inp.get("type", "")
            if p_type and p_type not in valid_param_types:
                issues.append({"tool_id": tool_id, "severity": "warning",
                                "message": f"inputs[{i}].type 无效值: {p_type!r}，有效值: {sorted(valid_param_types)}"})
            if p_type == "select" and not inp.get("options"):
                issues.append({"tool_id": tool_id, "severity": "warning",
                                "message": f"inputs[{i}] type=select 但缺少 options 数组"})

    # ── Rule 18: outputs 参数校验 ────────────────────────────────────────────
    outputs = manifest.get("outputs", [])
    if not isinstance(outputs, list):
        issues.append({"tool_id": tool_id, "severity": "error",
                        "message": "outputs 必须是数组"})
    else:
        for i, out in enumerate(outputs):
            if not isinstance(out, dict):
                issues.append({"tool_id": tool_id, "severity": "warning",
                                "message": f"outputs[{i}] 不是对象"})
                continue
            for field in ("id", "name", "type"):
                if not out.get(field):
                    issues.append({"tool_id": tool_id, "severity": "warning",
                                    "message": f"outputs[{i}] 缺少字段: {field}"})
            p_type = out.get("type", "")
            if p_type and p_type not in valid_param_types:
                issues.append({"tool_id": tool_id, "severity": "warning",
                                "message": f"outputs[{i}].type 无效值: {p_type!r}"})

    # ── Rule 19–28: triggers 触发规则校验 ────────────────────────────────────
    triggers = manifest.get("triggers", [])
    is_general = not target_dccs or set(target_dccs) <= {"general"}
    if isinstance(triggers, list):
        trigger_ids: set = set()
        for ti, tr in enumerate(triggers):
            if not isinstance(tr, dict):
                issues.append({"tool_id": tool_id, "severity": "warning",
                                "message": f"triggers[{ti}] 不是对象"})
                continue

            t_block = tr.get("trigger", {}) or {}
            t_type = t_block.get("type", "")
            filters_block = tr.get("filters", {}) or {}
            exec_block = tr.get("execution", {}) or {}

            # Rule 19: 每条 trigger 必须有 id
            t_id = tr.get("id", "")
            if not t_id:
                issues.append({"tool_id": tool_id, "severity": "error",
                                "message": f"triggers[{ti}] 缺少 id（manifest 同步到 triggers.json 时需要）"})
                t_id = f"[{ti}]"
            elif t_id in trigger_ids:
                # Rule 20
                issues.append({"tool_id": tool_id, "severity": "error",
                                "message": f"triggers[{ti}] id 重复: {t_id!r}"})
            else:
                trigger_ids.add(t_id)

            # Rule 21: trigger.type 有效值
            valid_trigger_types = {"watch", "event", "schedule"}
            if not t_type:
                issues.append({"tool_id": tool_id, "severity": "error",
                                "message": f"triggers[{ti}] ({t_id}): trigger.type 缺失"})
            elif t_type not in valid_trigger_types:
                issues.append({"tool_id": tool_id, "severity": "error",
                                "message": f"triggers[{ti}] ({t_id}): trigger.type 无效: {t_type!r}，有效值: {sorted(valid_trigger_types)}"})

            # Rule 22: execution.mode 必填
            if not exec_block.get("mode"):
                issues.append({"tool_id": tool_id, "severity": "error",
                                "message": f"triggers[{ti}] ({t_id}): execution 缺少 mode（silent/notify/interactive）"})

            # watch 专属规则
            if t_type == "watch":
                # Rule 23: 禁止 trigger.paths（废弃）
                if "paths" in t_block:
                    issues.append({"tool_id": tool_id, "severity": "error",
                                    "message": f"triggers[{ti}] ({t_id}): 使用了废弃字段 trigger.paths，请改用 filters.path + $variable"})
                # Rule 24/25: 必须有监听路径来源
                use_default = tr.get("useDefaultFilters", False)
                has_default_filters = bool(manifest.get("defaultFilters", {}).get("path"))
                filter_paths = filters_block.get("path", []) if isinstance(filters_block, dict) else []
                if use_default:
                    if not has_default_filters:
                        issues.append({"tool_id": tool_id, "severity": "error",
                                        "message": f"triggers[{ti}] ({t_id}): useDefaultFilters=true 但工具缺少 defaultFilters.path"})
                elif not filter_paths:
                    issues.append({"tool_id": tool_id, "severity": "error",
                                    "message": f"triggers[{ti}] ({t_id}): watch trigger 无 filters.path 且未设 useDefaultFilters=true，无法确定监听范围"})

            # event 专属规则
            if t_type == "event":
                event_val = t_block.get("event", "")
                event_dcc = t_block.get("dcc", "")

                # Rule 25.5: trigger.event 不得为空
                if not event_val:
                    issues.append({"tool_id": tool_id, "severity": "error",
                                    "message": f"triggers[{ti}] ({t_id}): trigger.event 缺失（必须为完整事件名，如 asset.save.pre）"})
                # Rule 25.6: trigger.event 不应含已废弃的 timing 字段
                elif t_block.get("timing"):
                    issues.append({"tool_id": tool_id, "severity": "error",
                                    "message": (f"triggers[{ti}] ({t_id}): 使用了废弃字段 trigger.timing，"
                                                 f"请将 timing 合并到 event 字段，如 \"{event_val}.{t_block['timing']}\"")})
                # Rule 25.7: trigger.event 格式检查（应包含 timing 后缀 .pre 或 .post）
                elif "." in event_val:
                    parts = event_val.split(".")
                    if parts[-1] not in ("pre", "post", "startup", "complete", "queue"):
                        issues.append({"tool_id": tool_id, "severity": "warning",
                                        "message": (f"triggers[{ti}] ({t_id}): trigger.event {event_val!r} "
                                                     f"末段不是合法 timing（pre/post），"
                                                     f"建议使用 {event_val!r}.pre 或 {event_val!r}.post")})

                if event_dcc:
                    # Rule 26
                    if is_general:
                        issues.append({"tool_id": tool_id, "severity": "error",
                                        "message": f"triggers[{ti}] ({t_id}): 通用工具不能使用 event trigger（绑定 DCC {event_dcc!r}）"})
                    # Rule 27
                    elif event_dcc not in target_dccs:
                        issues.append({"tool_id": tool_id, "severity": "warning",
                                        "message": f"triggers[{ti}] ({t_id}): event trigger dcc {event_dcc!r} 不在 targetDCCs {target_dccs} 中"})

            # Rule 28: filters.path 禁止花括号扩展
            for blk_name, blk in [("filters", filters_block),
                                    ("defaultFilters", manifest.get("defaultFilters", {}))]:
                if not isinstance(blk, dict):
                    continue
                for pi, path_entry in enumerate(blk.get("path", [])):
                    pat = path_entry.get("pattern", "") if isinstance(path_entry, dict) else str(path_entry)
                    if re.search(r'\{[^}]+,[^}]+\}', pat):
                        issues.append({"tool_id": tool_id, "severity": "error",
                                        "message": (f"triggers[{ti}] ({t_id}) {blk_name}.path[{pi}]: "
                                                     f"花括号扩展 {pat!r} fnmatch 不支持，watch 将静默失效，"
                                                     f"请拆为多条独立 pattern")})

    # ── Rule 29: createdAt / updatedAt 时间戳格式 ────────────────────────────
    ts_pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
    for ts_field in ("createdAt", "updatedAt"):
        val = manifest.get(ts_field, "")
        if val and not ts_pattern.match(str(val)):
            issues.append({"tool_id": tool_id, "severity": "warning",
                            "message": f"{ts_field} 格式不正确: {val!r}，应为 YYYY-MM-DD HH:MM:SS"})

    # ── Rule 30-36: artclaw_sdk 合规检查（AST 静态分析）────────────────────
    entry_file = impl.get("entry", "main.py") if impl else "main.py"
    entry_path_file = tool_dir / entry_file
    if entry_path_file.exists() and impl.get("type") == "script":
        try:
            script_source = entry_path_file.read_text(encoding="utf-8")
            import ast
            tree = ast.parse(script_source)

            # ── 判断触发类型（影响后续多条规则）─────────────────────────────
            has_event_trigger = any(
                isinstance(tr, dict) and (tr.get("trigger", {}) or {}).get("type") == "event"
                for tr in triggers
            ) if isinstance(triggers, list) else False

            # Rule 30: main.py 必须 import artclaw_sdk ──────────────────────
            has_sdk_import = False
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "artclaw_sdk" in alias.name:
                            has_sdk_import = True
                elif isinstance(node, ast.ImportFrom):
                    if node.module and "artclaw_sdk" in node.module:
                        has_sdk_import = True
            if not has_sdk_import:
                issues.append({"tool_id": tool_id, "severity": "error",
                              "message": "main.py 未 import artclaw_sdk（所有工具必须使用 SDK）"})

            func_name = impl.get("function", "") if impl else ""

            # Rule 31: selection 工具入口函数应调用 parse_params ─────────────
            # event trigger 工具使用 sdk.event.parse()，不需要 parse_params
            if func_name and has_sdk_import and not has_event_trigger:
                has_parse_params = any(
                    isinstance(node, ast.Attribute) and node.attr == "parse_params"
                    for node in ast.walk(tree)
                )
                if not has_parse_params:
                    issues.append({"tool_id": tool_id, "severity": "warning",
                                  "message": "入口函数未调用 sdk.params.parse_params（建议使用 SDK 参数解析）"})

            # Rule 33: 不应包含与 SDK 功能重复的 DCC 原生选中查询调用 ─────────
            # 规范：sdk.context.get_selected_assets/objects 已覆盖这些调用
            # event trigger 工具由 Rule 35 单独处理，此处跳过
            if has_sdk_import and not has_event_trigger:
                # 检测 attribute chain，避免误报同名方法
                sdk_overlap_attrs = {
                    "get_selected_assets",        # UE: EditorUtilityLibrary
                    "get_selected_asset_data",    # UE: EditorUtilityLibrary
                    "get_selected_level_actors",  # UE: EditorLevelLibrary
                    "selected_objects",           # Blender: bpy.context
                }
                for node in ast.walk(tree):
                    if isinstance(node, ast.Attribute) and node.attr in sdk_overlap_attrs:
                        # 排除 sdk.context.xxx 自身的调用（value 是 sdk 相关的 attribute）
                        if not (isinstance(node.value, ast.Attribute) and
                                node.value.attr in ("context", "artclaw_sdk")):
                            issues.append({"tool_id": tool_id, "severity": "warning",
                                          "message": (f"脚本直接调用 .{node.attr}()，"
                                                       f"建议改用 sdk.context.get_selected_assets() 或 get_selected_objects()")})
                            break

            # Rule 34: 入口函数返回值应通过 sdk.result.success/fail ───────────
            if func_name:
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name == func_name:
                        has_success_return = False
                        for child in ast.walk(node):
                            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                                if child.func.attr in ("success", "fail", "allow", "reject"):
                                    has_success_return = True
                                    break
                            if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
                                for key in child.value.keys:
                                    if isinstance(key, ast.Constant) and key.value == "success":
                                        has_success_return = True
                                        break
                        if not has_success_return:
                            issues.append({"tool_id": tool_id, "severity": "warning",
                                          "message": "入口函数返回值建议使用 sdk.result.success/fail/allow/reject"})
                        break

            # Rule 35: 事件触发工具禁止在模块顶层 import DCC 原生模块 ─────────
            # event_data 上下文由运行时引擎填入，工具脚本通过 sdk.event.parse() 读取。
            # 注意：函数体内的 `import unreal` 是允许的（lazy import 常见用法），
            # 只有模块级 import 才违规。
            if has_event_trigger:
                _BANNED_DCC_IMPORTS = {
                    "unreal", "maya", "maya.cmds", "maya.mel", "pymxs",
                    "bpy", "hou", "sd", "substance_painter",
                }
                banned_found = []
                # 只检查模块顶层的 import 语句（body 直接子节点）
                for node in tree.body:
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            top_mod = alias.name.split(".")[0]
                            if alias.name in _BANNED_DCC_IMPORTS or top_mod in _BANNED_DCC_IMPORTS:
                                banned_found.append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            top_mod = node.module.split(".")[0]
                            if node.module in _BANNED_DCC_IMPORTS or top_mod in _BANNED_DCC_IMPORTS:
                                banned_found.append(node.module)
                if banned_found:
                    issues.append({"tool_id": tool_id, "severity": "warning",
                                  "message": (
                                      f"事件触发工具在模块顶层 import 了 DCC 模块: {', '.join(sorted(set(banned_found)))}。"
                                      f"上下文由运行时引擎填入 event_data，建议通过 sdk.event.parse() 读取，"
                                      f"DCC 原生模块改为在函数体内 lazy import。"
                                  )})

            # Rule 36: 配置分层——脚本必须从 manifest 读取配置 ─────────────────
            # 正向验证：检查脚本是否实际调用了 manifest 的 defaultFilters / inputs 读取。
            # 若脚本声明了 inputs 但从不从 manifest 里读，说明配置可能被硬编码在脚本里。
            manifest_inputs = manifest.get("inputs", [])
            manifest_has_default_filters = bool(
                manifest.get("defaultFilters", {}).get("path") or
                manifest.get("defaultFilters", {}).get("typeFilter")
            )
            if manifest_inputs or manifest_has_default_filters:
                # 检查脚本是否有 manifest 读取调用（_load_manifest 或等价写法）
                reads_manifest = False
                for node in ast.walk(tree):
                    # 函数调用名含 load_manifest / read_manifest
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and "manifest" in node.func.id.lower():
                            reads_manifest = True
                            break
                        if isinstance(node.func, ast.Attribute) and "manifest" in node.func.attr.lower():
                            reads_manifest = True
                            break
                    # 字符串常量含 "manifest.json"（直接 open 读取）
                    if isinstance(node, ast.Constant) and isinstance(node.value, str) and "manifest.json" in node.value:
                        reads_manifest = True
                        break
                if not reads_manifest:
                    issues.append({"tool_id": tool_id, "severity": "warning",
                                  "message": (
                                      "manifest 定义了 inputs/defaultFilters 但脚本未读取 manifest.json。"
                                      "路径范围、类型列表、可配置参数等应从 manifest 读取，不应在脚本中硬编码。"
                                  )})

        except SyntaxError:
            pass

    # Rule 32: DCC 工具应有 defaultFilters.typeFilter
    real_dccs = [d for d in target_dccs if d and d != "general"]
    if real_dccs:
        type_filter = manifest.get("defaultFilters", {}).get("typeFilter", None)
        if type_filter is None:
            issues.append({"tool_id": tool_id, "severity": "warning",
                          "message": "DCC 工具建议设置 defaultFilters.typeFilter（声明对象类型筛选条件）"})

    return issues


def _is_valid_semver(version: str) -> bool:
    """检查版本号是否符合 semver 格式"""
    pattern = r'^\d+\.\d+\.\d+(?:-[\w\.-]+)?(?:\+[\w\.-]+)?$'
    return bool(re.match(pattern, version))


def _fix_version_format(version: str) -> str:
    """尝试修复版本格式"""
    # 移除前后空格
    version = version.strip()
    
    # 如果是纯数字，补充为 x.0.0
    if version.isdigit():
        return f"{version}.0.0"
    
    # 如果是 x.y 格式，补充为 x.y.0
    if re.match(r'^\d+\.\d+$', version):
        return f"{version}.0"
    
    # 移除前缀 v
    if version.startswith('v'):
        version = version[1:]
        if _is_valid_semver(version):
            return version
    
    # 无法修复，返回原值
    return version


def _save_manifest(manifest_path: Path, manifest: Dict[str, Any]) -> None:
    """保存 manifest.json 文件"""
    try:
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"警告：无法保存 {manifest_path}: {e}")


def _generate_report(total_checked: int, issues: List[Dict[str, str]]) -> str:
    """生成检查报告"""
    if not issues:
        return f"✅ 检查完成，共 {total_checked} 个工具，全部合规。"
    
    # 按严重级别分组
    errors = [i for i in issues if i['severity'] == 'error']
    warnings = [i for i in issues if i['severity'] == 'warning']
    infos = [i for i in issues if i['severity'] == 'info']
    
    report_lines = [
        f"检查完成，共 {total_checked} 个工具，发现 {len(issues)} 个问题：",
        ""
    ]
    
    if errors:
        report_lines.append(f"🚨 严重错误 ({len(errors)} 个):")
        for issue in errors:
            report_lines.append(f"  - {issue['tool_id']}: {issue['message']}")
        report_lines.append("")
    
    if warnings:
        report_lines.append(f"⚠️  警告 ({len(warnings)} 个):")
        for issue in warnings:
            report_lines.append(f"  - {issue['tool_id']}: {issue['message']}")
        report_lines.append("")
    
    if infos:
        report_lines.append(f"ℹ️  信息 ({len(infos)} 个):")
        for issue in infos:
            report_lines.append(f"  - {issue['tool_id']}: {issue['message']}")
        report_lines.append("")
    
    return "\n".join(report_lines)


def _update_alerts(issues: List[Dict[str, str]]) -> None:
    """更新报警状态。requests 为软依赖，Tool Manager 未运行时静默跳过。"""
    try:
        import requests
    except ImportError:
        return

    api_url = "http://localhost:9876/api/v1/alerts"
    source = "tool-compliance-checker"

    # 统计问题
    errors = [i for i in issues if i['severity'] == 'error']
    warnings = [i for i in issues if i['severity'] == 'warning']

    try:
        if errors or warnings:
            # 有问题，创建报警
            if errors:
                title = f"工具配置错误 ({len(errors)} 个)"
                detail = "\n".join(f"• {e['tool_id']}: {e['message']}" for e in errors[:5])
                if len(errors) > 5:
                    detail += f"\n... 还有 {len(errors) - 5} 个错误"
                level = "error"
            else:
                title = f"工具配置警告 ({len(warnings)} 个)"
                detail = "\n".join(f"• {w['tool_id']}: {w['message']}" for w in warnings[:5])
                if len(warnings) > 5:
                    detail += f"\n... 还有 {len(warnings) - 5} 个警告"
                level = "warning"
            
            alert_data = {
                "level": level,
                "source": source,
                "title": title,
                "detail": detail,
                "metadata": {
                    "error_count": len(errors),
                    "warning_count": len(warnings),
                    "total_issues": len(issues)
                }
            }
            
            response = requests.post(api_url, json=alert_data, timeout=10)
            response.raise_for_status()
        else:
            # 无问题，解决之前的报警
            # 获取现有报警
            response = requests.get(f"{api_url}?resolved=false", timeout=10)
            if response.status_code == 200:
                alerts_data = response.json()
                alerts = alerts_data.get('alerts', [])
                
                # 找到来源为 tool-compliance-checker 的报警
                for alert in alerts:
                    if alert.get('source') == source:
                        alert_id = alert['id']
                        update_data = {"resolved": True}
                        requests.patch(f"{api_url}/{alert_id}", json=update_data, timeout=10)
    
    except Exception as e:
        print(f"警告：更新报警失败: {e}")


# 测试入口点
if __name__ == "__main__":
    # 可以进行简单测试
    result = check_compliance()
    print(f"检查结果: {result}")