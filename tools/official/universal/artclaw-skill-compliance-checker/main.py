#!/usr/bin/env python3
"""
ArtClaw Skill Version Checker v4

多位置一致性检查：
  A. installed vs source repo（skill 版本同步）
  B. core/ 共享模块的 DCC/UE 副本同步
  C. 各 DCC 安装副本 vs DCCClawBridge 源码同步

路径来源：
  1. 优先从 manifest.json 的 triggers[].filters.path 读取（$variable 路径变量）
  2. 补充信息（core_module_copies / dcc_install_dirs）仍由 bridge_config 提供

变更检测规则（hash 优先）：
  hash 相同                            → synced
  hash 不同 + source_ver > inst_ver   → source_newer  ("更新"按钮)
  hash 不同 + inst_ver > source_ver   → installed_newer ("发布"按钮)
  hash 不同 + 版本相同/均空           → modified  (本地有改动未发布，"发布"按钮)
  两侧都有更新（mtime 双向新）        → conflict  (需手动处理)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple


# ============================================================================
# 路径变量解析
# ============================================================================

def _resolve_path_variables() -> Dict[str, str]:
    """
    解析路径变量映射表。与 manifest.json filters.path 中的 $variable 对应。
    
    变量来源优先级: bridge_config > ~/.artclaw/config.json > 默认值
    """
    cfg_path = Path.home() / ".artclaw" / "config.json"
    project_root = ""
    platform_type = "openclaw"
    skills_installed = str(Path.home() / ".openclaw" / "workspace" / "skills")

    try:
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            project_root = cfg.get("project_root", "")
            platform_type = cfg.get("platform", {}).get("type", "openclaw")
            skills_installed = cfg.get("skills", {}).get("installed_path", "") or skills_installed
    except Exception:
        pass

    # 尝试从 bridge_config 获取更精确的路径
    if project_root:
        bridge_config_paths = [
            Path(project_root) / "subprojects" / "DCCClawBridge" / "core",
            Path(project_root) / "core",
        ]
        for p in bridge_config_paths:
            if (p / "bridge_config.py").exists() and str(p) not in sys.path:
                sys.path.insert(0, str(p))
        try:
            from bridge_config import get_skills_installed_path
            skills_installed = get_skills_installed_path()
        except ImportError:
            pass

    return {
        "$skills_installed": skills_installed,
        "$project_root": project_root,
        "$tools_dir": str(Path.home() / ".artclaw" / "tools"),
        "$home": str(Path.home()),
        "_platform_type": platform_type,  # 内部使用，非路径变量
    }


def _resolve_pattern(pattern: str, variables: Dict[str, str]) -> Optional[str]:
    """
    将 $variable/... 模式解析为绝对路径。
    返回 None 如果变量不存在或值为空。
    """
    for var, value in variables.items():
        if var.startswith("_"):
            continue  # 跳过内部变量
        if pattern.startswith(var):
            if not value:
                return None
            resolved = pattern.replace(var, value, 1)
            return resolved.replace("/", os.sep)
    return pattern.replace("/", os.sep)


def _get_manifest_filter_paths() -> Tuple[List[str], List[str]]:
    """
    从自身 manifest.json 的 triggers[].filters.path 中读取路径，
    解析 $variable，返回 (installed_paths, source_paths)。
    """
    manifest_path = Path(__file__).parent / "manifest.json"
    if not manifest_path.exists():
        return [], []

    variables = _resolve_path_variables()
    installed_paths: List[str] = []
    source_paths: List[str] = []

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for trigger in manifest.get("triggers", []):
            filters = trigger.get("filters", {})
            path_filters = filters.get("path", [])
            for pf in path_filters:
                pattern = pf.get("pattern", "")
                if not pattern:
                    continue
                # 去掉 glob 后缀取基础目录
                base = pattern.split("/**")[0].split("/*")[0]
                resolved = _resolve_pattern(base, variables)
                if not resolved:
                    continue
                # 按变量分类
                if "$skills_installed" in pattern:
                    installed_paths.append(resolved)
                elif "$project_root" in pattern:
                    source_paths.append(resolved)
                else:
                    installed_paths.append(resolved)
    except Exception:
        pass

    return installed_paths, source_paths


def _get_checker_dirs() -> dict:
    """
    获取所有需要检查的目录。

    路径来源:
      1. manifest.json 的 triggers[].filters.path（$variable 解析）
      2. bridge_config.get_skill_checker_dirs()（补充 core_module_copies / dcc_install_dirs）
    """
    variables = _resolve_path_variables()
    platform_type = variables.get("_platform_type", "openclaw")
    skills_installed = variables.get("$skills_installed", "")
    project_root = variables.get("$project_root", "")

    # 从 manifest filters 读取路径（验证与变量解析一致）
    installed_from_manifest, source_from_manifest = _get_manifest_filter_paths()
    if installed_from_manifest:
        skills_installed = installed_from_manifest[0]  # 以 manifest 声明为准

    # 尝试从 bridge_config 获取补充信息（core_module_copies / dcc_install_dirs）
    dcc_install_dirs = []
    core_module_copies = []
    try:
        from bridge_config import get_skill_checker_dirs
        dirs = get_skill_checker_dirs()
        dcc_install_dirs = dirs.get("dcc_install_dirs", [])
        core_module_copies = dirs.get("core_module_copies", [])
    except ImportError:
        pass

    return {
        "platform_type": platform_type,
        "skills_installed_path": skills_installed,
        "project_root": project_root,
        "dcc_install_dirs": dcc_install_dirs,
        "core_module_copies": core_module_copies,
    }


# ============================================================================
# 版本提取
# ============================================================================

def _extract_version(skill_dir: Path) -> Optional[str]:
    """从 skill 目录提取版本（manifest.json 优先，SKILL.md metadata.artclaw.version 次之）"""
    manifest = skill_dir / "manifest.json"
    if manifest.exists():
        try:
            v = json.loads(manifest.read_text(encoding="utf-8")).get("version", "")
            if v:
                return str(v)
        except Exception:
            pass

    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        try:
            content = skill_md.read_text(encoding="utf-8")
            m_front = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
            if m_front:
                fm = m_front.group(1)
                # 1. metadata.artclaw.version（新格式）
                m = re.search(
                    r'metadata\s*:\s*\n(?:[ \t]+\S.*\n)*?'
                    r'[ \t]+artclaw\s*:\s*\n(?:[ \t]+\S.*\n)*?'
                    r'[ \t]+version\s*:\s*([^\n]+)',
                    fm, re.MULTILINE
                )
                if m:
                    v = m.group(1).strip().strip('"\'')
                    if v:
                        return v
                # 2. 顶层 version（旧格式）
                m2 = re.search(r'^version\s*:\s*(.+)$', fm, re.MULTILINE)
                if m2:
                    v = m2.group(1).strip().strip('"\'')
                    if v:
                        return v
        except Exception:
            pass
    return None


def _version_tuple(v: str) -> Tuple[int, ...]:
    if not v:
        return (0, 0, 0)
    try:
        parts = v.strip().lstrip('v').split('-')[0].split('.')
        return tuple(int(re.match(r'\d+', p).group()) for p in parts[:3])
    except Exception:
        return (0, 0, 0)


def _compare_versions(v1: str, v2: str) -> int:
    t1, t2 = _version_tuple(v1), _version_tuple(v2)
    return 1 if t1 > t2 else (-1 if t1 < t2 else 0)


# ============================================================================
# Hash 工具
# ============================================================================

def _file_hash(path: Path) -> str:
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except Exception:
        return ""


def _dir_hashes(root: Path, exclude: Optional[set] = None) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not root.exists():
        return result
    for p in sorted(root.rglob("*")):
        if p.is_dir() or p.suffix not in {".py", ".md", ".json"}:
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        if "__pycache__" in rel or rel.endswith(".pyc"):
            continue
        if exclude and rel in exclude:
            continue
        result[rel] = _file_hash(p)
    return result


# ============================================================================
# 两目录比较（hash 优先逻辑）
# ============================================================================

def _compare_dirs(
    dir_a: Path, dir_b: Path,
    ver_a: Optional[str] = None, ver_b: Optional[str] = None,
    exclude: Optional[set] = None,
) -> Tuple[str, List[str]]:
    """
    比较两个目录，返回 (status, changed_files)。

    Hash 优先规则：
      相同                          → synced
      不同 + src_ver > inst_ver    → source_newer  (显示"更新")
      不同 + inst_ver > src_ver    → installed_newer (显示"发布")
      不同 + 版本同/均空            → modified  (本地有改动未发布，显示"发布")
      两侧都有更新                  → conflict  (需手动处理)
    """
    hashes_a = _dir_hashes(dir_a, exclude)
    hashes_b = _dir_hashes(dir_b, exclude)

    if hashes_a == hashes_b:
        return "synced", []

    all_files = set(hashes_a.keys()) | set(hashes_b.keys())
    changed: List[str] = []
    a_ahead = False
    b_ahead = False

    for f in sorted(all_files):
        ha = hashes_a.get(f, "")
        hb = hashes_b.get(f, "")
        if ha == hb:
            continue
        changed.append(f)
        if not ha:
            b_ahead = True
        elif not hb:
            a_ahead = True
        else:
            try:
                mt_a = (dir_a / f).stat().st_mtime
                mt_b = (dir_b / f).stat().st_mtime
                if mt_b > mt_a:
                    b_ahead = True
                elif mt_a > mt_b:
                    a_ahead = True
                else:
                    a_ahead = b_ahead = True
            except Exception:
                a_ahead = b_ahead = True

    # Version tie-breaking
    va = ver_a or _extract_version(dir_a)
    vb = ver_b or _extract_version(dir_b)

    if a_ahead and b_ahead:
        return "conflict", changed
    if b_ahead and not a_ahead:
        return "source_newer", changed
    # a_ahead only
    if va and vb and va != vb:
        cmp = _compare_versions(va, vb)
        if cmp > 0:
            return "installed_newer", changed
        elif cmp < 0:
            return "source_newer", changed
    return "modified", changed


# ============================================================================
# 源码仓库扫描（分层目录）
# ============================================================================

def _scan_source_skills(project_root: str) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    skills_root = Path(project_root) / "skills"
    if not skills_root.exists():
        return result

    SKIP = {"templates", "__pycache__", ".git"}
    for layer_dir in sorted(skills_root.iterdir()):
        if not layer_dir.is_dir() or layer_dir.name in SKIP:
            continue
        layer = layer_dir.name
        if layer not in ("official", "marketplace", "user"):
            continue
        for dcc_dir in sorted(layer_dir.iterdir()):
            if not dcc_dir.is_dir() or dcc_dir.name in SKIP:
                continue
            for skill_dir in sorted(dcc_dir.iterdir()):
                if not skill_dir.is_dir() or skill_dir.name in SKIP:
                    continue
                if not (skill_dir / "SKILL.md").exists():
                    continue
                result[skill_dir.name] = {
                    "layer": layer, "dcc": dcc_dir.name,
                    "path": skill_dir, "version": _extract_version(skill_dir),
                }
    return result


# ============================================================================
# 检查 D：Skill 依赖完整性
# ============================================================================

def _check_skill_dependencies(installed_dir: Path, source_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    检查已安装 Skill 的依赖完整性。
    返回缺失依赖的 issue 列表。
    """
    issues: List[Dict[str, Any]] = []
    for skill_dir in sorted(installed_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        manifest_path = skill_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        dependencies = manifest.get("dependencies", [])
        if not dependencies:
            continue

        skill_name = skill_dir.name
        for dep in dependencies:
            # 去掉版本约束
            dep_name = re.split(r'[>=<]', dep)[0].strip()
            if '.' in dep_name:
                dep_name = dep_name.split('.')[-1]

            # 检查是否已安装（在 installed_dir 中）
            dep_installed = (installed_dir / dep_name).exists()
            # 检查是否在源码库中
            dep_in_source = dep_name in source_map

            if not dep_installed:
                issues.append({
                    "type": "missing_dependency",
                    "skill": skill_name,
                    "dependency": dep,
                    "dep_name": dep_name,
                    "severity": "warning" if dep_in_source else "error",
                    "detail": (
                        f"依赖 '{dep_name}' 未安装（源码库中有，可运行 artclaw skill install {dep_name}）"
                        if dep_in_source else
                        f"依赖 '{dep_name}' 未安装且在源码库中未找到"
                    ),
                })
    return issues


# ============================================================================
# 检查 A：Skill installed vs source repo
# ============================================================================

def _check_skills(installed_dir: Path, source_map: Dict[str, Any]) -> Tuple[List[Dict], int, int]:
    """
    比较已安装 Skill 与源码仓库，返回 (skills_list, updates_available, conflicts)。
    """
    skills: List[Dict] = []
    updates = 0
    conflicts = 0

    for skill_dir in sorted(installed_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_id = skill_dir.name
        inst_ver = _extract_version(skill_dir)
        info = source_map.get(skill_id)

        if info:
            src_dir: Path = info["path"]
            src_ver = info.get("version")
            status, changed = _compare_dirs(skill_dir, src_dir, inst_ver, src_ver)
        else:
            status, changed = "no_source", []

        entry = {
            "id": skill_id,
            "installed_version": inst_ver,
            "source_version": info.get("version") if info else None,
            "source_layer": info.get("layer") if info else None,
            "source_dcc": info.get("dcc") if info else None,
            "status": status,
            "changed_files": changed,
        }
        skills.append(entry)
        if status == "source_newer":
            updates += 1
        elif status == "conflict":
            conflicts += 1

    return skills, updates, conflicts


# ============================================================================
# 检查 B：核心模块副本同步
# ============================================================================

def _check_core_modules(core_copies: List[Dict]) -> List[Dict[str, Any]]:
    """
    检查 core/ 共享模块在各副本中是否同步（使用 get_skill_checker_dirs 提供的列表）。
    """
    issues: List[Dict[str, Any]] = []
    for item in core_copies:
        src = Path(item["src"])
        dst = Path(item["dst"])
        desc = item["label"]

        if not src.exists():
            issues.append({
                "type": "core_module", "desc": desc,
                "status": "src_missing", "severity": "warning",
                "detail": f"源码缺失: {src.name}",
            })
            continue
        if not dst.exists():
            issues.append({
                "type": "core_module", "desc": desc,
                "status": "dst_missing", "severity": "warning",
                "detail": "副本缺失，需重新运行 install.bat 部署",
            })
            continue

        hs = _file_hash(src)
        hd = _file_hash(dst)
        if hs != hd:
            try:
                direction = "source_newer" if src.stat().st_mtime > dst.stat().st_mtime else "dst_newer"
            except Exception:
                direction = "unknown"
            severity = "error" if direction == "dst_newer" else "warning"
            detail = ("源码已更新，副本未同步（运行 install.bat 部署）"
                      if direction == "source_newer"
                      else "副本比源码新（可能有未提交修改）")
            issues.append({
                "type": "core_module", "desc": desc,
                "status": direction, "severity": severity, "detail": detail,
            })
    return issues


# ============================================================================
# 检查 C：DCC 安装副本同步
# ============================================================================

def _check_dcc_installs(dcc_install_dirs: List[Dict]) -> List[Dict[str, Any]]:
    """
    检查各 DCC 安装副本是否与 DCCClawBridge 源码同步（使用 get_skill_checker_dirs 提供的列表）。
    """
    # DCC-specific entry files deployed by install.py from adapter directories,
    # not part of the shared DCCClawBridge source tree.
    DCC_ENTRY_FILES = {"__init__.py", "blender_manifest.toml"}

    issues: List[Dict[str, Any]] = []
    for item in dcc_install_dirs:
        label = item["label"]
        src_dir = Path(item["path"])
        install_dir = Path(item["install_path"])

        if not src_dir.exists() or not install_dir.exists():
            continue

        status, changed = _compare_dirs(install_dir, src_dir, exclude=DCC_ENTRY_FILES)
        if status == "synced":
            continue

        severity = "error" if status == "conflict" else "warning"
        detail_map = {
            "source_newer": "源码已更新，安装副本未同步（运行 install.bat 重新部署）",
            "installed_newer": "安装副本比源码新（有未提交修改）",
            "modified": "安装副本有改动未同步到源码",
            "conflict": "双侧都有修改，需要手动解决",
        }
        issues.append({
            "type": "dcc_install", "desc": f"DCCClawBridge → {label}",
            "status": status, "severity": severity,
            "detail": detail_map.get(status, status),
            "changed_files": changed[:5],
        })
    return issues


# ============================================================================
# 主入口
# ============================================================================

def check_skill_versions() -> Dict[str, Any]:
    """
    全自动检查 Skill 版本与多位置一致性。

    所有路径由 bridge_config.get_skill_checker_dirs() 自动提供，
    随平台切换自动更新。无需手动配置参数。

    Returns:
        {
          platform_type, total_checked, updates_available, conflicts,
          skills: [...],
          core_issues: [...],
          dcc_issues: [...],
          report: str,
        }
    """
    checker_dirs = _get_checker_dirs()
    platform_type = checker_dirs.get("platform_type", "openclaw")
    installed_path = checker_dirs.get("skills_installed_path", "")
    project_root = checker_dirs.get("project_root", "")

    installed_dir = Path(installed_path).expanduser() if installed_path else None

    if not installed_dir or not installed_dir.exists():
        return {
            "platform_type": platform_type,
            "total_checked": 0, "updates_available": 0, "conflicts": 0,
            "skills": [], "core_issues": [], "dcc_issues": [], "dep_issues": [],
            "report": f"Skill 目录不存在: {installed_dir}（平台: {platform_type}）",
        }

    # ── A. Skill installed vs source ──────────────────────────────────────
    source_map = _scan_source_skills(project_root) if project_root else {}
    skills, updates, conflicts = _check_skills(installed_dir, source_map)

    # ── B. Core module copies ──────────────────────────────────────────────
    core_issues = _check_core_modules(checker_dirs.get("core_module_copies", []))

    # ── C. DCC install dirs ────────────────────────────────────────────────
    dcc_issues = _check_dcc_installs(checker_dirs.get("dcc_install_dirs", []))

    # ── D. Skill dependency check ─────────────────────────────────────────
    dep_issues = _check_skill_dependencies(installed_dir, source_map)

    report = _generate_report(platform_type, skills, core_issues, dcc_issues, dep_issues)
    _update_alerts(updates, conflicts, skills, core_issues, dcc_issues, dep_issues)

    return {
        "platform_type": platform_type,
        "total_checked": len(skills),
        "updates_available": updates,
        "conflicts": conflicts,
        "skills": skills,
        "core_issues": core_issues,
        "dcc_issues": dcc_issues,
        "dep_issues": dep_issues,
        "report": report,
    }


# ============================================================================
# 报告生成
# ============================================================================

def _generate_report(
    platform_type: str,
    skills: List[Dict[str, Any]],
    core_issues: List[Dict[str, Any]],
    dcc_issues: List[Dict[str, Any]],
    dep_issues: Optional[List[Dict[str, Any]]] = None,
) -> str:
    dep_issues = dep_issues or []
    total = len(skills)
    status_labels = {
        "synced": "✅ 已同步", "source_newer": "🔄 有新版本",
        "installed_newer": "⬆️ 本地版本新", "modified": "📝 本地已修改",
        "conflict": "⚠️ 版本冲突", "no_source": "📁 无源码",
    }
    counts: Dict[str, int] = {}
    for s in skills:
        counts[s["status"]] = counts.get(s["status"], 0) + 1

    synced_n = counts.get("synced", 0) + counts.get("no_source", 0)
    problem_n = total - synced_n

    if problem_n == 0 and not core_issues and not dcc_issues and not dep_issues:
        return f"✅ 全部检查通过。共 {total} 个 Skill 已同步，平台: {platform_type}，无风险项。"

    lines: List[str] = [
        f"Skill 检查结果（平台: {platform_type}）：{total} 个，{synced_n} 个正常", ""
    ]
    for st, cnt in sorted(counts.items()):
        if st not in ("synced", "no_source") and cnt > 0:
            lines.append(f"  {status_labels.get(st, st)}: {cnt} 个")
    lines.append("")

    problematic = [s for s in skills if s["status"] not in ("synced", "no_source")]
    if problematic:
        lines.append("【Skill 需关注】")
        for s in problematic:
            lyr = f" [{s['source_layer']}/{s['source_dcc']}]" if s.get("source_layer") else ""
            lines.append(f"  • {s['id']}{lyr}: {status_labels.get(s['status'], s['status'])}")
            if s["installed_version"] or s["source_version"]:
                lines.append(f"    安装 v{s['installed_version'] or '?'}  源码 v{s['source_version'] or '?'}")
            if s["changed_files"]:
                fs = ", ".join(s["changed_files"][:3])
                if len(s["changed_files"]) > 3:
                    fs += f" 等 {len(s['changed_files'])} 个"
                lines.append(f"    变更: {fs}")
        lines.append("")

    if core_issues:
        lines.append(f"【核心模块副本不同步】（{len(core_issues)} 处）")
        for i in core_issues:
            icon = "🔴" if i["severity"] == "error" else "🟡"
            lines.append(f"  {icon} {i['desc']}: {i['detail']}")
        lines.append("")

    if dcc_issues:
        lines.append(f"【DCC 安装副本不同步】（{len(dcc_issues)} 处）")
        for i in dcc_issues:
            icon = "🔴" if i["severity"] == "error" else "🟡"
            cf = f"（{', '.join(i['changed_files'][:3])}）" if i.get("changed_files") else ""
            lines.append(f"  {icon} {i['desc']}: {i['detail']} {cf}")
        lines.append("")

    if dep_issues:
        lines.append(f"【Skill 依赖缺失】（{len(dep_issues)} 处）")
        for i in dep_issues:
            icon = "🔴" if i["severity"] == "error" else "🟡"
            lines.append(f"  {icon} {i['skill']} → 缺少依赖 {i['dependency']}: {i['detail']}")
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# Alert API
# ============================================================================

def _update_alerts(
    updates: int, conflicts: int,
    skills: List[Dict], core_issues: List[Dict], dcc_issues: List[Dict],
    dep_issues: Optional[List[Dict]] = None,
) -> None:
    try:
        import requests
    except ImportError:
        print("[WARN] requests 未安装，跳过 alert 发送")
        return

    api_url = "http://localhost:9876/api/v1/alerts"
    src_name = "skill-version-checker"

    def _post(level: str, title: str, detail: str, meta: dict) -> None:
        try:
            requests.post(api_url, json={
                "level": level, "source": src_name,
                "title": title, "detail": detail, "metadata": meta,
            }, timeout=10)
        except Exception as e:
            print(f"Alert POST 失败: {e}")

    def _resolve_all() -> None:
        try:
            resp = requests.get(f"{api_url}?resolved=false", timeout=10)
            if resp.status_code == 200:
                for a in resp.json().get("alerts", []):
                    if a.get("source") == src_name:
                        requests.patch(f"{api_url}/{a['id']}", json={"resolved": True}, timeout=10)
        except Exception:
            pass

    try:
        # Skill 冲突（最高优先级）
        if conflicts > 0:
            ids = [s["id"] for s in skills if s["status"] == "conflict"]
            _post("error", f"Skill 版本冲突 ({conflicts} 个)",
                  "以下 Skill 双侧都有修改，需手动解决：\n" + ", ".join(ids[:5]),
                  {"conflict_count": conflicts, "skills": ids})

        # 本地改动未发布
        modified = [s["id"] for s in skills if s["status"] in ("modified", "installed_newer")]
        if modified:
            _post("warning", f"Skill 有本地改动未发布 ({len(modified)} 个)",
                  "以下 Skill 安装版本与源码不一致，建议发布：\n" + ", ".join(modified[:5]),
                  {"modified_count": len(modified), "skills": modified})

        # 源码有更新
        if updates > 0:
            updatable = [s["id"] for s in skills if s["status"] == "source_newer"]
            _post("warning", f"Skill 有新版本可用 ({updates} 个)",
                  "以下 Skill 源码有更新，建议同步安装：\n" + ", ".join(updatable[:5]),
                  {"update_count": updates, "skills": updatable})

        # 核心模块副本问题（按严重度分级）
        for severity in ("error", "warning"):
            items = [i for i in core_issues if i["severity"] == severity]
            if items:
                level_label = "不一致" if severity == "error" else "需更新"
                _post(severity,
                      f"核心模块副本{level_label} ({len(items)} 处)",
                      "\n".join(f"  • {i['desc']}: {i['detail']}" for i in items[:5]),
                      {"count": len(items), "issues": [i["desc"] for i in items]})
                break  # 只发最高级

        # DCC 安装副本问题
        for severity in ("error", "warning"):
            items = [i for i in dcc_issues if i["severity"] == severity]
            if items:
                level_label = "不同步" if severity == "error" else "需更新"
                _post(severity,
                      f"DCC 安装副本{level_label} ({len(items)} 处)",
                      "\n".join(f"  • {i['desc']}: {i['detail']}" for i in items[:5]),
                      {"count": len(items), "issues": [i["desc"] for i in items]})
                break

        # Skill 依赖缺失
        _dep_issues = dep_issues or []
        for severity in ("error", "warning"):
            items = [i for i in _dep_issues if i["severity"] == severity]
            if items:
                level_label = "缺失（无源码库）" if severity == "error" else "未安装"
                _post(severity,
                      f"Skill 依赖{level_label} ({len(items)} 处)",
                      "\n".join(f"  • {i['skill']} → {i['dep_name']}: {i['detail']}" for i in items[:5]),
                      {"count": len(items), "issues": [f"{i['skill']}:{i['dep_name']}" for i in items]})
                break

        # 全部通过 → 解决之前的报警
        if not conflicts and not modified and updates == 0 and not core_issues and not dcc_issues and not _dep_issues:
            _resolve_all()

    except Exception as e:
        print(f"警告：更新报警失败: {e}")


if __name__ == "__main__":
    import io
    import sys
    # 强制 UTF-8 输出
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    result = check_skill_versions()
    print(result["report"])
