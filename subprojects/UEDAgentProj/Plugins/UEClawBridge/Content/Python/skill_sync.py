"""
skill_sync.py - Skill 安装/卸载/同步/发布 工具
===================================================

Phase 4: 对比项目源码 vs 运行时目录差异，提供安装、卸载、同步、发布操作。

依赖:
  - ~/.artclaw/config.json 中的 project_root 字段
  - skill_hub.py 中的 SkillHub 实例

宪法约束:
  - Skill与MCP管理面板设计 §3 (完整生命周期)
  - 系统架构设计 §2.3 (Python 负责业务逻辑)
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from init_unreal import UELogger


# ============================================================================
# 配置
# ============================================================================

def _get_config() -> dict:
    """读取 ~/.artclaw/config.json"""
    config_path = Path.home() / ".artclaw" / "config.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _get_project_root() -> Optional[Path]:
    """获取项目源码根目录"""
    cfg = _get_config()
    root = cfg.get("project_root")
    if root and Path(root).is_dir():
        return Path(root)
    return None


def _get_runtime_skills_dir() -> Path:
    """获取运行时 Skills 目录（统一使用平台已安装目录）"""
    return _get_openclaw_skills_dir()


def _get_openclaw_skills_dir() -> Path:
    """获取平台已安装 Skills 目录（通过 ~/.artclaw/config.json 配置驱动）"""
    cfg = _get_config()
    # 优先从 artclaw config 的 skills.installed_path 读取
    installed_path = cfg.get("skills", {}).get("installed_path", "")
    if installed_path:
        return Path(os.path.expanduser(installed_path))
    # 回退：根据 platform.type 确定默认路径
    platform_type = cfg.get("platform", {}).get("type", "openclaw")
    _defaults = {
        "openclaw": "~/.openclaw/skills",
        "workbuddy": "~/.workbuddy/skills",
        "claude": "~/.claude/skills",
    }
    return Path(os.path.expanduser(_defaults.get(platform_type, "~/.openclaw/skills")))


# ============================================================================
# 扫描
# ============================================================================

def _scan_source_skills(project_root: Path) -> Dict[str, dict]:
    """
    递归扫描项目源码 skills/ 下所有 Skill。

    支持任意 DCC 子目录（不硬编码 universal/unreal/maya/max），
    路径格式: skills/{layer}/{dcc}/{skill_name}/

    跳过 templates/ 目录（含占位符模板）。

    返回: {skill_name: {layer, dcc, path, has_code, has_skill_md, version, content_hash}}
    """
    skills = {}
    skills_dir = project_root / "skills"
    if not skills_dir.is_dir():
        return skills

    SKIP_DIRS = {"templates", "__pycache__", ".git"}

    for layer_dir in sorted(skills_dir.iterdir()):
        if not layer_dir.is_dir() or layer_dir.name in SKIP_DIRS or layer_dir.name.startswith("."):
            continue
        layer = layer_dir.name  # official, marketplace, user, ...

        for dcc_dir in sorted(layer_dir.iterdir()):
            if not dcc_dir.is_dir() or dcc_dir.name in SKIP_DIRS or dcc_dir.name.startswith("."):
                continue
            dcc = dcc_dir.name  # universal, unreal, maya, max, blender, ...

            for skill_dir in sorted(dcc_dir.iterdir()):
                if not skill_dir.is_dir() or skill_dir.name in SKIP_DIRS or skill_dir.name.startswith("."):
                    continue

                manifest_path = skill_dir / "manifest.json"
                skill_md_path = skill_dir / "SKILL.md"
                init_path = skill_dir / "__init__.py"

                # 至少有一个标识文件才视为 Skill
                if not (manifest_path.exists() or skill_md_path.exists() or init_path.exists()):
                    continue

                version = ""
                if manifest_path.exists():
                    try:
                        m = json.loads(manifest_path.read_text(encoding="utf-8"))
                        version = m.get("version", "")
                    except Exception:
                        pass

                skills[skill_dir.name] = {
                    "name": skill_dir.name,
                    "layer": layer,
                    "dcc": dcc,
                    "path": str(skill_dir),
                    "has_code": init_path.exists(),
                    "has_skill_md": skill_md_path.exists(),
                    "version": version,
                    "content_hash": _dir_content_hash(skill_dir),
                }

    return skills


def _scan_runtime_skills() -> Dict[str, dict]:
    """
    扫描运行时已安装的 Skill。
    支持两种结构:
      1. 扁平: skills_dir/skill_name/ (install.py 安装的)
      2. 分层: skills_dir/layer/skill_name/ (旧版兼容)
    返回: {skill_name: {layer, path, version}}
    """
    skills = {}
    runtime_dir = _get_runtime_skills_dir()

    if not runtime_dir.is_dir():
        return skills

    LAYER_NAMES = {"official", "marketplace", "user", "custom"}

    for entry in sorted(runtime_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue

        if entry.name in LAYER_NAMES:
            # 分层目录: 扫描其下的 Skill 包（旧版兼容）
            for skill_dir in sorted(entry.iterdir()):
                if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                    continue
                if skill_dir.name in skills:
                    continue  # 扁平优先
                _add_skill_entry(skills, skill_dir, entry.name)
        else:
            # 扁平目录: 直接是 Skill 包
            _add_skill_entry(skills, entry, "installed")

    return skills


def _add_skill_entry(skills: dict, skill_dir: Path, layer: str) -> None:
    """解析一个 Skill 目录并加入结果字典"""
    # 必须有 SKILL.md 或 manifest.json 或 __init__.py
    has_manifest = (skill_dir / "manifest.json").exists()
    has_skill_md = (skill_dir / "SKILL.md").exists()
    has_init = (skill_dir / "__init__.py").exists()
    if not (has_manifest or has_skill_md or has_init):
        return

    version = ""
    if has_manifest:
        try:
            m = json.loads((skill_dir / "manifest.json").read_text(encoding="utf-8"))
            version = m.get("version", "")
        except Exception:
            pass

    skills[skill_dir.name] = {
        "name": skill_dir.name,
        "layer": layer,
        "path": str(skill_dir),
        "version": version,
        "content_hash": _dir_content_hash(skill_dir),
    }


# ============================================================================
# 辅助：目录内容 hash（用于无版本号 Skill 的变更检测）
# ============================================================================

def _dir_content_hash(skill_dir: Path) -> str:
    """
    计算 Skill 目录的内容 hash（MD5 前 12 位）。

    只扫描关键文件（.py, .md, .json），跳过 __pycache__。
    用于对比源码和安装目录的 Skill 是否有差异（无版本号时的 fallback）。
    """
    import hashlib
    h = hashlib.md5()
    EXTENSIONS = {".py", ".md", ".json"}

    for root, dirs, files in os.walk(skill_dir):
        dirs[:] = [d for d in sorted(dirs) if d != "__pycache__"]
        for fname in sorted(files):
            if Path(fname).suffix not in EXTENSIONS:
                continue
            fpath = Path(root) / fname
            try:
                h.update(fpath.read_bytes())
            except Exception:
                pass
    return h.hexdigest()[:12]


# ============================================================================
# 差异对比
# ============================================================================

def compare_source_vs_runtime() -> dict:
    """
    对比项目源码 vs 运行时，返回差异报告。

    返回:
    {
        "available": [...],      # 源码中有但运行时没有（可安装）
        "installed": [...],      # 运行时已安装
        "updatable": [...],      # 两边都有但版本不同（可更新）
        "orphaned": [...],       # 运行时有但源码没有（可卸载）
        "project_root": "...",
        "error": null
    }
    """
    project_root = _get_project_root()
    if not project_root:
        return {
            "available": [], "installed": [], "updatable": [], "orphaned": [],
            "project_root": None,
            "error": "project_root 未配置。运行 install.bat 或在 ~/.artclaw/config.json 中设置。"
        }

    source = _scan_source_skills(project_root)
    runtime = _scan_runtime_skills()

    available = []
    updatable = []
    installed = []
    orphaned = []

    # 源码中有的
    for name, info in source.items():
        if name in runtime:
            rt = runtime[name]
            installed.append({**info, "runtime_version": rt["version"],
                              "runtime_path": rt["path"]})
            # 判断是否可更新：版本号不同 或 无版本号时 hash 不同
            src_ver = info.get("version", "")
            rt_ver = rt.get("version", "")
            if src_ver and rt_ver and src_ver != rt_ver:
                updatable.append({**info, "runtime_version": rt_ver})
            elif not (src_ver and rt_ver):
                # 无版本号的 Skill，用 content hash 对比
                src_hash = info.get("content_hash", "")
                rt_hash = rt.get("content_hash", "")
                if src_hash and rt_hash and src_hash != rt_hash:
                    updatable.append({**info, "runtime_version": rt_ver,
                                      "reason": "content_changed"})
        else:
            available.append(info)

    # 运行时有但源码没有
    for name, info in runtime.items():
        if name not in source:
            # user/custom 层的不算 orphaned
            if info["layer"] in ("user", "custom"):
                continue
            orphaned.append(info)

    return {
        "available": available,
        "installed": installed,
        "updatable": updatable,
        "orphaned": orphaned,
        "project_root": str(project_root),
        "error": None,
    }


# ============================================================================
# 安装
# ============================================================================

def install_skill(skill_name: str) -> dict:
    """
    从项目源码安装一个 Skill 到已安装目录。

    1. 整个 Skill 目录复制到平台已安装目录（代码 + SKILL.md + references 等）
    2. 通知 skill_hub 热重载

    返回: {"ok": bool, "message": str}
    """
    project_root = _get_project_root()
    if not project_root:
        return {"ok": False, "message": "project_root 未配置"}

    source = _scan_source_skills(project_root)
    if skill_name not in source:
        return {"ok": False, "message": f"源码中找不到 Skill: {skill_name}"}

    info = source[skill_name]
    src_path = Path(info["path"])
    layer = info["layer"]

    # 目标：平台已安装目录（统一目录）
    installed_dir = _get_openclaw_skills_dir() / skill_name
    installed_dir.parent.mkdir(parents=True, exist_ok=True)

    try:
        if installed_dir.exists():
            shutil.rmtree(installed_dir)
        shutil.copytree(
            src_path, installed_dir,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        UELogger.info(f"Skill installed: {skill_name} → {installed_dir}")

        # 通知 skill_hub 重新扫描
        _notify_skill_hub()

        return {"ok": True, "message": f"已安装: {skill_name} ({layer})"}
    except Exception as e:
        return {"ok": False, "message": f"安装失败: {e}"}


def install_all_available() -> dict:
    """安装所有可用但未安装的 Skill。"""
    diff = compare_source_vs_runtime()
    if diff["error"]:
        return {"ok": False, "message": diff["error"], "results": []}

    results = []
    for skill_info in diff["available"]:
        r = install_skill(skill_info["name"])
        results.append({"name": skill_info["name"], **r})

    ok_count = sum(1 for r in results if r["ok"])
    return {
        "ok": True,
        "message": f"安装完成: {ok_count}/{len(results)} 个 Skill",
        "results": results,
    }


# ============================================================================
# 卸载
# ============================================================================

def uninstall_skill(skill_name: str) -> dict:
    """
    从运行时卸载一个 Skill。

    1. 删除运行时 Skills/{layer}/{name}/
    2. 删除平台已安装 Skills 目录中的 {name}/
    3. 通知 skill_hub

    返回: {"ok": bool, "message": str}
    """
    installed_dir = _get_openclaw_skills_dir() / skill_name
    if not installed_dir.exists():
        return {"ok": False, "message": f"已安装目录中找不到: {skill_name}"}

    try:
        shutil.rmtree(installed_dir)
        UELogger.info(f"Skill uninstalled: {skill_name}")

        _notify_skill_hub()

        return {"ok": True, "message": f"已卸载: {skill_name}"}
    except Exception as e:
        return {"ok": False, "message": f"卸载失败: {e}"}


# ============================================================================
# 更新
# ============================================================================

def update_skill(skill_name: str) -> dict:
    """从源码更新运行时的 Skill（覆盖安装）。"""
    return install_skill(skill_name)  # 安装逻辑已处理覆盖


def update_all() -> dict:
    """更新所有版本不一致的 Skill。"""
    diff = compare_source_vs_runtime()
    if diff["error"]:
        return {"ok": False, "message": diff["error"], "results": []}

    results = []
    for skill_info in diff["updatable"]:
        r = update_skill(skill_info["name"])
        results.append({"name": skill_info["name"], **r})

    ok_count = sum(1 for r in results if r["ok"])
    return {
        "ok": True,
        "message": f"更新完成: {ok_count}/{len(results)} 个 Skill",
        "results": results,
    }


# ============================================================================
# 同步（安装全部可用 + 更新全部过期）
# ============================================================================

def sync_all() -> dict:
    """一键同步：安装未安装的 + 更新版本不一致的。"""
    diff = compare_source_vs_runtime()
    if diff["error"]:
        return {"ok": False, "message": diff["error"], "installed": [], "updated": []}

    installed_results = []
    for info in diff["available"]:
        r = install_skill(info["name"])
        installed_results.append({"name": info["name"], **r})

    updated_results = []
    for info in diff["updatable"]:
        r = update_skill(info["name"])
        updated_results.append({"name": info["name"], **r})

    return {
        "ok": True,
        "message": f"同步完成: 安装 {len(installed_results)} 个, 更新 {len(updated_results)} 个",
        "installed": installed_results,
        "updated": updated_results,
    }


# ============================================================================
# 发布（用户 Skill → 市集）
# ============================================================================

def publish_skill(skill_name: str, target_layer: str = "marketplace",
                  bump: str = "patch", changelog: str = "",
                  dcc: str = "") -> dict:
    """
    发布 Skill：版本号递增 + 同步到项目源码 + 更新安装目录 + git commit。

    不搬运行时目录（运行时统一扁平结构），只更新 manifest 和同步到项目源码。

    Args:
        skill_name: Skill 名称
        target_layer: "marketplace" 或 "official"
        bump: "patch" / "minor" / "major"
        changelog: 变更说明
        dcc: 目标软件目录 ("universal"/"unreal"/"maya"/"max")，空则自动推断

    返回: {"ok": bool, "message": str, "new_version": str}
    """
    project_root = _get_project_root()
    if not project_root:
        return {"ok": False, "message": "project_root 未配置", "new_version": ""}

    runtime = _scan_runtime_skills()
    if skill_name not in runtime:
        return {"ok": False, "message": f"运行时找不到: {skill_name}", "new_version": ""}

    info = runtime[skill_name]
    runtime_path = Path(info["path"])

    # DCC 目录：优先使用用户选择，否则自动推断
    target_dcc = dcc if dcc else _infer_dcc_from_name(skill_name)

    # 版本号递增
    old_version = info["version"] or "0.0.0"
    new_version = _bump_version(old_version, bump)

    try:
        # 1. 更新运行时 manifest 版本号（保留已有字段，补全缺失字段）
        manifest_path = runtime_path / "manifest.json"
        manifest = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # 如果 manifest 不完整（缺少 manifest_version 等必需字段），
        # 尝试从 SKILL.md frontmatter 补全
        if not manifest.get("manifest_version"):
            manifest = _build_manifest_from_skill_md(runtime_path, manifest)

        manifest["version"] = new_version
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8")

        # 2. 确定目标路径 & 清理项目源码中旧位置（如果换了层级或 DCC 目录）
        source_target = project_root / "skills" / target_layer / target_dcc / skill_name
        skills_root = project_root / "skills"
        for layer_name in ("official", "marketplace"):
            for dcc_name in ("universal", "unreal", "maya", "max"):
                old_path = skills_root / layer_name / dcc_name / skill_name
                if old_path.exists() and old_path != source_target:
                    shutil.rmtree(old_path)
                    UELogger.info(f"Removed old source: {layer_name}/{dcc_name}/{skill_name}")

        # 3. 同步到项目源码（目标层 + DCC 目录）
        source_target.parent.mkdir(parents=True, exist_ok=True)
        if source_target.exists():
            shutil.rmtree(source_target)
        shutil.copytree(
            runtime_path, source_target,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        UELogger.info(f"Skill published to source: {target_layer}/{target_dcc}/{skill_name} v{new_version}")

        # 4. 更新平台已安装 Skills 目录（SKILL.md + 代码）
        oc_dir = _get_openclaw_skills_dir() / skill_name
        if oc_dir != runtime_path:
            oc_dir.mkdir(parents=True, exist_ok=True)
            # 同步整个目录内容
            if oc_dir.exists():
                shutil.rmtree(oc_dir)
            shutil.copytree(
                runtime_path, oc_dir,
                ignore=shutil.ignore_patterns("__pycache__"),
            )

        # 5. git add + commit
        _git_commit(project_root, skill_name, target_layer, new_version, changelog,
                    dcc=target_dcc)

        _notify_skill_hub()

        return {
            "ok": True,
            "message": f"已发布: {skill_name} v{new_version} → {target_layer}/{target_dcc}",
            "new_version": new_version,
        }
    except Exception as e:
        return {"ok": False, "message": f"发布失败: {e}", "new_version": ""}


# ============================================================================
# 辅助函数
# ============================================================================

def _bump_version(version: str, bump: str) -> str:
    """版本号递增"""
    try:
        parts = [int(x) for x in version.split(".")]
        while len(parts) < 3:
            parts.append(0)
        major, minor, patch = parts[0], parts[1], parts[2]
    except (ValueError, IndexError):
        return "1.0.0"

    if bump == "major":
        return f"{major + 1}.0.0"
    elif bump == "minor":
        return f"{major}.{minor + 1}.0"
    else:  # patch
        return f"{major}.{minor}.{patch + 1}"


def _infer_dcc_from_name(skill_name: str) -> str:
    """从 Skill 名称推断 DCC 类型"""
    if skill_name.startswith("ue"):
        return "unreal"
    elif skill_name.startswith("maya"):
        return "maya"
    elif skill_name.startswith("max"):
        return "max"
    else:
        return "universal"


def _build_manifest_from_skill_md(skill_dir: Path, existing: dict) -> dict:
    """
    从 SKILL.md frontmatter 构建完整 manifest，保留 existing 中已有的字段。

    用于 publish_skill 场景：运行时 manifest.json 只有 version 字段，
    需要从 SKILL.md 补全其他必需字段。

    Args:
        skill_dir: Skill 目录路径
        existing: 已有的 manifest 字典（可能不完整）

    Returns:
        补全后的 manifest 字典
    """
    from skill_hub import _parse_yaml_frontmatter

    skill_md_path = skill_dir / "SKILL.md"
    if not skill_md_path.exists():
        return existing

    try:
        content = skill_md_path.read_text(encoding="utf-8")
    except Exception:
        return existing

    fm = _parse_yaml_frontmatter(content)
    if not fm:
        return existing

    skill_name = skill_dir.name
    fm_name = fm.get("name", skill_name).replace("-", "_")

    # 推断 software
    _software = fm.get("software", "")
    if not _software:
        if fm_name.startswith("ue") and len(fm_name) > 2 and fm_name[2:3].isdigit():
            _software = "unreal_engine"
        elif fm_name.startswith("maya"):
            _software = "maya"
        elif fm_name.startswith("max"):
            _software = "3ds_max"
        else:
            _software = "universal"

    # 构建完整 manifest，existing 的值优先
    full = {
        "manifest_version": "1.0",
        "name": fm_name,
        "display_name": fm.get("display_name", fm_name.replace("_", " ").title()),
        "description": fm.get("description", ""),
        "version": existing.get("version", fm.get("version", "1.0.0")),
        "author": fm.get("author", "ArtClaw"),
        "software": _software,
        "category": fm.get("category", "utils"),
        "risk_level": fm.get("risk_level", "low"),
        "entry_point": "__init__.py",
        "tools": [{"name": fm_name, "description": fm.get("description", "")}],
    }

    # existing 中已有的字段覆盖默认值
    for key, val in existing.items():
        if val and key != "version":  # version 由 bump 逻辑控制
            full[key] = val

    return full


def _git_commit(project_root: Path, skill_name: str, layer: str,
                version: str, changelog: str, dcc: str = "") -> None:
    """尝试 git add（含删除）+ commit"""
    import subprocess
    try:
        target_dcc = dcc if dcc else _infer_dcc_from_name(skill_name)
        skill_rel = f"skills/{layer}/{target_dcc}/{skill_name}"
        msg = f"skill: publish {skill_name} v{version} to {layer}/{target_dcc}"
        if changelog:
            msg += f"\n\n{changelog}"

        # git add 整个 skills/ 目录，包括旧位置的删除
        subprocess.run(["git", "add", "skills/"],
                       cwd=str(project_root), capture_output=True, timeout=10)
        subprocess.run(["git", "commit", "-m", msg],
                       cwd=str(project_root), capture_output=True, timeout=10)
        UELogger.info(f"Git commit: {msg.splitlines()[0]}")
    except Exception as e:
        UELogger.warning(f"Git commit skipped: {e}")


# ============================================================================
# 重命名
# ============================================================================

def rename_skill(old_name: str, new_name: str,
                 update_source: bool = True) -> dict:
    """
    重命名一个已安装的 Skill。

    1. 重命名安装目录 old_name/ → new_name/
    2. 更新 manifest.json 中的 name 字段
    3. 更新 SKILL.md frontmatter 中的 name 字段
    4. 可选: 同步更新项目源码中的目录名
    5. 通知 skill_hub 重新扫描

    Args:
        old_name: 当前 Skill 名称（目录名）
        new_name: 新 Skill 名称
        update_source: 是否同步更新项目源码（默认 True）

    返回: {"ok": bool, "message": str}
    """
    installed_dir = _get_openclaw_skills_dir()
    old_dir = installed_dir / old_name
    new_dir = installed_dir / new_name

    if not old_dir.exists():
        return {"ok": False, "message": f"已安装目录中找不到: {old_name}"}
    if new_dir.exists():
        return {"ok": False, "message": f"目标名称已存在: {new_name}"}

    try:
        # 1. 重命名目录
        old_dir.rename(new_dir)

        # 2. 更新 manifest.json
        manifest_path = new_dir / "manifest.json"
        if manifest_path.exists():
            try:
                m = json.loads(manifest_path.read_text(encoding="utf-8"))
                m["name"] = new_name
                # 也更新 tools 中的名称
                for tool in m.get("tools", []):
                    if tool.get("name", "").startswith(old_name):
                        tool["name"] = tool["name"].replace(old_name, new_name, 1)
                manifest_path.write_text(
                    json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

        # 3. 更新 SKILL.md frontmatter
        skill_md_path = new_dir / "SKILL.md"
        if skill_md_path.exists():
            try:
                content = skill_md_path.read_text(encoding="utf-8")
                # 替换 frontmatter 中的 name 字段
                old_kebab = old_name.replace("_", "-")
                new_kebab = new_name.replace("_", "-")
                content = content.replace(f"name: {old_name}", f"name: {new_name}")
                content = content.replace(f"name: {old_kebab}", f"name: {new_kebab}")
                skill_md_path.write_text(content, encoding="utf-8")
            except Exception:
                pass

        # 4. 同步更新源码
        if update_source:
            project_root = _get_project_root()
            if project_root:
                source = _scan_source_skills(project_root)
                if old_name in source:
                    old_src = Path(source[old_name]["path"])
                    new_src = old_src.parent / new_name
                    if old_src.exists() and not new_src.exists():
                        old_src.rename(new_src)
                        UELogger.info(f"Source renamed: {old_name} → {new_name}")

        _notify_skill_hub()

        return {"ok": True, "message": f"已重命名: {old_name} → {new_name}"}
    except Exception as e:
        return {"ok": False, "message": f"重命名失败: {e}"}


def _notify_skill_hub() -> None:
    """通知 skill_hub 重新扫描"""
    try:
        from skill_hub import get_skill_hub
        hub = get_skill_hub()
        if hub:
            hub.scan_and_register()
    except Exception:
        pass
