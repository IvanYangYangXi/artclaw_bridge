#!/usr/bin/env python3
"""
ArtClaw Tool Compliance Checker v3.0

扫描工具目录，对照 docs/specs/tool-manifest-spec.md 进行合规检查（29 条规则）。

路径来源：
  优先从自身 manifest.json 的 defaultFilters.path 读取（$variable 路径变量）
  手动运行 / watch 触发 / 定时触发 共用同一套路径。
"""
import json
import re
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
import requests


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
        "$skills_installed": str(Path.home() / ".openclaw" / "skills"),
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


def check_compliance(tools_dir: str = "", fix_simple: bool = False, source_only: bool = True) -> Dict[str, Any]:
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
        return {
            "total_checked": 0,
            "issues_found": 0,
            "issues": [],
            "report": f"工具目录不存在: {', '.join(scan_dirs)}"
        }
    
    # 获取源码工具名集合
    variables = _resolve_path_variables()
    project_root = variables.get("$project_root", "")
    
    if source_only:
        try:
            source_names = _get_source_tool_names(project_root)
        except RuntimeError as e:
            return {
                "total_checked": 0,
                "issues_found": 1,
                "issues": [{"tool_id": "system", "severity": "error", "message": str(e)}],
                "report": f"❌ 无法获取源码工具列表：{e}\n\n请检查 ArtClaw 安装配置。"
            }
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
    
    return {
        "total_checked": total_checked,
        "issues_found": len(issues),
        "issues": issues,
        "report": report
    }


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
                event_dcc = t_block.get("dcc", "")
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
    """更新报警状态"""
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