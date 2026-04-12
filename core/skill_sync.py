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

import logging

logger = logging.getLogger("artclaw.skill_sync")


# ============================================================================
# 轻量 SKILL.md Frontmatter 解析
# ============================================================================

def _parse_frontmatter_light(skill_md_path: Path) -> dict:
    """
    轻量解析 SKILL.md YAML frontmatter，只提取顶层和 metadata.artclaw.* key-value。

    支持多行 description (> 和 |)，正确处理嵌套 metadata.artclaw 块。
    不依赖 skill_hub 或 PyYAML，零外部依赖。

    返回: {"name": ..., "description": ..., "version": ..., "author": ..., ...}
    （author/version/software/category/risk_level/display_name 会合并 metadata.artclaw.* 的值）
    """
    try:
        raw = skill_md_path.read_text(encoding="utf-8")[:4096]
    except Exception:
        return {}

    if not raw.startswith("---"):
        return {}

    end = raw.find("---", 3)
    if end < 0:
        return {}

    fm_block = raw[3:end]
    result = {}
    ac_meta = {}
    in_metadata = False
    in_artclaw = False
    in_multiline = False
    multiline_key = ""
    multiline_val = ""
    multiline_target = None  # result 或 ac_meta

    for line in fm_block.split("\n"):
        stripped = line.strip()

        # 处理多行值（description: > 的后续行）
        if in_multiline:
            if not stripped:
                # 空行在多行中可能是段落分隔，跳过
                continue
            indent = len(line) - len(line.lstrip())
            if indent >= 2:
                # 缩进行：多行值的续行
                multiline_val += " " + stripped
                continue
            else:
                # 缩进回退：多行结束
                target = multiline_target or result
                target[multiline_key] = multiline_val.strip()
                in_multiline = False
                # 继续解析当前行

        # 跳过空行和注释
        if not stripped or stripped.startswith("#"):
            continue

        # 检测缩进层级
        indent = len(line) - len(line.lstrip())

        if indent == 0:
            in_metadata = False
            in_artclaw = False

        if ":" not in stripped:
            continue

        key, _, val = stripped.partition(":")
        key = key.strip()
        val = val.strip()

        if indent == 0:
            if key == "metadata":
                in_metadata = True
                continue
            if val == ">" or val == "|":
                # 多行值
                in_multiline = True
                multiline_key = key
                multiline_val = ""
                multiline_target = result
                continue
            result[key] = val.strip('"').strip("'")
        elif in_metadata and not in_artclaw:
            if key == "artclaw":
                in_artclaw = True
                continue
        elif in_artclaw:
            if val == ">" or val == "|":
                in_multiline = True
                multiline_key = key
                multiline_val = ""
                multiline_target = ac_meta
                continue
            ac_meta[key] = val.strip('"').strip("'")

    if in_multiline:
        target = multiline_target or result
        target[multiline_key] = multiline_val.strip()

    # 合并: metadata.artclaw.* 的值覆盖顶层 fallback
    for k in ("author", "version", "software", "category", "risk_level", "display_name"):
        if k in ac_meta and ac_meta[k]:
            result[k] = ac_meta[k]

    return result


# ============================================================================
# 版本比较
# ============================================================================

def _version_gt(a: str, b: str) -> bool:
    """a 是否严格大于 b？用 tuple 数值比较。"""
    def _parse(v):
        try:
            return tuple(int(x) for x in v.split("."))
        except (ValueError, AttributeError):
            return (0, 0, 0)
    return _parse(a) > _parse(b)


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
                author = ""
                if manifest_path.exists():
                    try:
                        m = json.loads(manifest_path.read_text(encoding="utf-8"))
                        version = m.get("version", "")
                        author = m.get("author", "")
                    except Exception:
                        pass

                # manifest.json 没有 version/author 时，从 SKILL.md frontmatter 补充
                if skill_md_path.exists() and (not version or not author):
                    fm = _parse_frontmatter_light(skill_md_path)
                    if not version:
                        version = fm.get("version", "")
                    if not author:
                        author = fm.get("author", "")

                skills[skill_dir.name] = {
                    "name": skill_dir.name,
                    "layer": layer,
                    "dcc": dcc,
                    "path": str(skill_dir),
                    "has_code": init_path.exists(),
                    "has_skill_md": skill_md_path.exists(),
                    "version": version,
                    "author": author,
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
    author = ""
    if has_manifest:
        try:
            m = json.loads((skill_dir / "manifest.json").read_text(encoding="utf-8"))
            version = m.get("version", "")
            author = m.get("author", "")
        except Exception:
            pass

    # manifest.json 没有 version/author 时，从 SKILL.md frontmatter 补充
    if has_skill_md and (not version or not author):
        fm = _parse_frontmatter_light(skill_dir / "SKILL.md")
        if not version:
            version = fm.get("version", "")
        if not author:
            author = fm.get("author", "")

    skills[skill_dir.name] = {
        "name": skill_dir.name,
        "layer": layer,
        "path": str(skill_dir),
        "version": version,
        "author": author,
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
        "updatable": [...],      # 源码比运行时新（可更新）
        "modified": [...],       # 运行时比源码新（有未发布修改，可发布）
        "orphaned": [...],       # 运行时有但源码没有（可卸载）
        "project_root": "...",
        "error": null
    }
    """
    project_root = _get_project_root()
    if not project_root:
        return {
            "available": [], "installed": [], "updatable": [],
            "modified": [], "orphaned": [],
            "project_root": None,
            "error": "project_root 未配置。运行 install.bat 或在 ~/.artclaw/config.json 中设置。"
        }

    source = _scan_source_skills(project_root)
    runtime = _scan_runtime_skills()

    available = []
    updatable = []
    modified = []
    installed = []
    orphaned = []

    # 源码中有的
    for name, info in source.items():
        if name in runtime:
            rt = runtime[name]
            installed.append({**info, "runtime_version": rt["version"],
                              "runtime_path": rt["path"]})

            src_ver = info.get("version", "")
            rt_ver = rt.get("version", "")
            src_hash = info.get("content_hash", "")
            rt_hash = rt.get("content_hash", "")

            if src_hash == rt_hash:
                # 内容完全一致，无需更新也无需发布
                continue

            # hash 不同，判断方向
            if src_ver and rt_ver:
                # 有版本号: 按版本判断方向
                if _version_gt(src_ver, rt_ver):
                    # 源码版本更高 → 可更新
                    updatable.append({**info, "runtime_version": rt_ver})
                elif _version_gt(rt_ver, src_ver):
                    # 运行时版本更高 → 有未发布修改
                    modified.append({**info, "runtime_version": rt_ver,
                                     "reason": "version_ahead"})
                else:
                    # 版本相同但 hash 不同 → 运行时有未发布修改
                    modified.append({**info, "runtime_version": rt_ver,
                                     "reason": "content_changed"})
            else:
                # 无版本号: hash 不同 → 假定运行时有修改（用户更可能编辑运行时）
                modified.append({**info, "runtime_version": rt_ver,
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
        "modified": modified,
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
        logger.info(f"Skill installed: {skill_name} → {installed_dir}")

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
        logger.info(f"Skill uninstalled: {skill_name}")

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
    """一键同步：安装未安装的 + 更新版本不一致的。不包含 modified (有未发布修改的不会被覆盖)。"""
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

        # 1b. 同步更新 SKILL.md frontmatter 中的 version 和 updated_at 字段
        _update_skill_md_version(runtime_path / "SKILL.md", new_version)
        _update_skill_md_updated_at(runtime_path / "SKILL.md")

        # 2. 确定目标路径 & 清理项目源码中旧位置（如果换了层级或 DCC 目录）
        source_target = project_root / "skills" / target_layer / target_dcc / skill_name
        skills_root = project_root / "skills"
        for layer_name in ("official", "marketplace"):
            # 动态扫描所有 DCC 子目录，不硬编码
            layer_dir = skills_root / layer_name
            if not layer_dir.is_dir():
                continue
            for dcc_dir in layer_dir.iterdir():
                if not dcc_dir.is_dir():
                    continue
                old_path = dcc_dir / skill_name
                if old_path.exists() and old_path != source_target:
                    shutil.rmtree(old_path)
                    logger.info(f"Removed old source: {layer_name}/{dcc_dir.name}/{skill_name}")

        # 3. 同步到项目源码（目标层 + DCC 目录）
        source_target.parent.mkdir(parents=True, exist_ok=True)
        if source_target.exists():
            shutil.rmtree(source_target)
        shutil.copytree(
            runtime_path, source_target,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        logger.info(f"Skill published to source: {target_layer}/{target_dcc}/{skill_name} v{new_version}")

        # 4. 更新平台已安装 Skills 目录（确保 hash 一致）
        #    发布后源码和运行时都来自同一份数据(runtime_path → source → oc_dir)
        #    但 manifest.json 已在 runtime_path 更新过 version，需要同步到 oc_dir
        oc_dir = _get_openclaw_skills_dir() / skill_name
        if oc_dir != runtime_path:
            oc_dir.mkdir(parents=True, exist_ok=True)
            if oc_dir.exists():
                shutil.rmtree(oc_dir)
            shutil.copytree(
                runtime_path, oc_dir,
                ignore=shutil.ignore_patterns("__pycache__"),
            )

        # 5. 回写源码的 manifest.json（确保源码和运行时版本一致）
        source_manifest = source_target / "manifest.json"
        if source_manifest.exists() or manifest_path.exists():
            try:
                source_manifest.write_text(
                    manifest_path.read_text(encoding="utf-8"),
                    encoding="utf-8")
            except Exception:
                pass

        # 6. git add + commit
        _git_commit(project_root, skill_name, target_layer, new_version, changelog,
                    dcc=target_dcc)

        _notify_skill_hub(force=True)

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


def _update_skill_md_version(skill_md_path: Path, new_version: str) -> bool:
    """
    更新 SKILL.md frontmatter 中的 version 字段。

    支持两种格式:
    1. metadata.artclaw.version: X.Y.Z (OpenClaw 兼容格式)
    2. 顶层 version: X.Y.Z (旧格式 fallback)

    如果 frontmatter 中不存在 version 字段，在 metadata.artclaw 块中插入。
    如果没有 frontmatter，不修改文件。

    返回: True 如果成功更新
    """
    if not skill_md_path.exists():
        return False

    try:
        raw = skill_md_path.read_text(encoding="utf-8")
    except Exception:
        return False

    if not raw.startswith("---"):
        return False

    end = raw.find("---", 3)
    if end < 0:
        return False

    fm_block = raw[3:end]
    body = raw[end:]  # includes closing "---" and everything after

    lines = fm_block.split("\n")
    new_lines = []
    version_updated = False
    in_metadata = False
    in_artclaw = False
    artclaw_indent = ""

    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        # 追踪 metadata / artclaw 块层级
        if indent == 0 and stripped and not stripped.startswith("#"):
            in_metadata = stripped == "metadata:"
            in_artclaw = False
        elif in_metadata and indent >= 2 and stripped == "artclaw:":
            in_artclaw = True
            artclaw_indent = " " * (indent + 2)

        # 替换 version 字段
        if stripped.startswith("version:"):
            if in_artclaw and indent >= 4:
                # metadata.artclaw.version
                new_lines.append(f"{line[:indent]}version: {new_version}")
                version_updated = True
                continue
            elif indent == 0 and not in_metadata:
                # 顶层 version（旧格式）
                new_lines.append(f"version: {new_version}")
                version_updated = True
                continue

        new_lines.append(line)

    # 如果没找到 version 字段，尝试插入到 metadata.artclaw 块
    if not version_updated:
        inserted = False
        final_lines = []
        for i, line in enumerate(new_lines):
            final_lines.append(line)
            stripped = line.strip()
            # 找到 artclaw: 行后，在下一行插入 version
            if stripped == "artclaw:" and not inserted:
                # 计算缩进
                ac_indent = len(line) - len(line.lstrip()) + 2
                final_lines.append(f"{' ' * ac_indent}version: {new_version}")
                inserted = True
                version_updated = True
        if inserted:
            new_lines = final_lines

    if not version_updated:
        return False

    try:
        result = "---" + "\n".join(new_lines) + body
        skill_md_path.write_text(result, encoding="utf-8")
        logger.info(f"Updated SKILL.md version to {new_version}: {skill_md_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to update SKILL.md version: {e}")
        return False


def _update_skill_md_updated_at(skill_md_path: Path) -> bool:
    """
    更新 SKILL.md frontmatter 中的 updated_at 字段为当前时间。

    支持两种格式:
    1. metadata.artclaw.updated_at: "2026-04-12 01:52:00" (优先)
    2. 顶层 updated_at: "2026-04-12 01:52:00" (fallback)

    如果 frontmatter 中不存在 updated_at 字段，在 metadata.artclaw 块中插入。
    如果没有 frontmatter，不修改文件。

    返回: True 如果成功更新
    """
    if not skill_md_path.exists():
        return False

    try:
        raw = skill_md_path.read_text(encoding="utf-8")
    except Exception:
        return False

    if not raw.startswith("---"):
        return False

    end = raw.find("---", 3)
    if end < 0:
        return False

    fm_block = raw[3:end]
    body = raw[end:]  # includes closing "---" and everything after

    # Generate current timestamp
    import datetime
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = fm_block.split("\n")
    new_lines = []
    updated_at_updated = False
    in_metadata = False
    in_artclaw = False
    artclaw_indent = ""

    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        # 追踪 metadata / artclaw 块层级
        if indent == 0 and stripped and not stripped.startswith("#"):
            in_metadata = stripped == "metadata:"
            in_artclaw = False
        elif in_metadata and indent >= 2 and stripped == "artclaw:":
            in_artclaw = True
            artclaw_indent = " " * (indent + 2)

        # 替换 updated_at 字段
        if stripped.startswith("updated_at:"):
            if in_artclaw and indent >= 4:
                # metadata.artclaw.updated_at
                new_lines.append(f"{line[:indent]}updated_at: {current_time}")
                updated_at_updated = True
                continue
            elif indent == 0 and not in_metadata:
                # 顶层 updated_at（旧格式）
                new_lines.append(f"updated_at: {current_time}")
                updated_at_updated = True
                continue

        new_lines.append(line)

    # 如果没找到 updated_at 字段，尝试插入到 metadata.artclaw 块
    if not updated_at_updated:
        inserted = False
        final_lines = []
        for i, line in enumerate(new_lines):
            final_lines.append(line)
            stripped = line.strip()
            # 找到 artclaw: 行后，在下一行插入 updated_at
            if stripped == "artclaw:" and not inserted:
                # 计算缩进
                ac_indent = len(line) - len(line.lstrip()) + 2
                final_lines.append(f"{' ' * ac_indent}updated_at: {current_time}")
                inserted = True
                updated_at_updated = True
        if inserted:
            new_lines = final_lines

    if not updated_at_updated:
        return False

    try:
        result = "---" + "\n".join(new_lines) + body
        skill_md_path.write_text(result, encoding="utf-8")
        logger.info(f"Updated SKILL.md updated_at to {current_time}: {skill_md_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to update SKILL.md updated_at: {e}")
        return False


def _infer_dcc_from_name(skill_name: str) -> str:
    """从 Skill 名称推断 DCC 类型"""
    if skill_name.startswith("ue"):
        return "unreal"
    elif skill_name.startswith("maya"):
        return "maya"
    elif skill_name.startswith("max"):
        return "max"
    elif skill_name.startswith("sd-") or skill_name.startswith("sd_"):
        return "substance_designer"
    elif skill_name.startswith("sp-") or skill_name.startswith("sp_"):
        return "substance_painter"
    elif skill_name.startswith("blender"):
        return "blender"
    elif skill_name.startswith("houdini"):
        return "houdini"
    else:
        return "universal"


def _build_manifest_from_skill_md(skill_dir: Path, existing: dict) -> dict:
    """
    从 SKILL.md frontmatter 构建完整 manifest，保留 existing 中已有的字段。

    用于 publish_skill 场景：运行时 manifest.json 只有 version 字段，
    需要从 SKILL.md 补全其他必需字段。

    字段读取优先级（新格式 > 旧格式 > 默认值）:
      - 新格式: metadata.artclaw.{field}
      - 旧格式: 顶层 {field}（向后兼容）

    使用本模块的 _parse_frontmatter_light() 解析 frontmatter，
    不依赖 skill_hub（DCC 环境中不存在 skill_hub）。

    Args:
        skill_dir: Skill 目录路径
        existing: 已有的 manifest 字典（可能不完整）

    Returns:
        补全后的 manifest 字典
    """
    skill_md_path = skill_dir / "SKILL.md"
    if not skill_md_path.exists():
        return existing

    fm = _parse_frontmatter_light(skill_md_path)
    if not fm:
        return existing

    skill_name = skill_dir.name
    fm_name = fm.get("name", skill_name).replace("-", "_")

    def _ac(field, default=""):
        """优先 metadata.artclaw.{field} (已由 _parse_frontmatter_light 合并)，
        fallback 顶层 fm.{field}。"""
        val = fm.get(field, "")
        if val:
            return val
        return default

    # 推断 software
    _software = _ac("software", "")
    if not _software:
        if fm_name.startswith("ue") and len(fm_name) > 2 and fm_name[2:3].isdigit():
            _software = "unreal_engine"
        elif fm_name.startswith("maya"):
            _software = "maya"
        elif fm_name.startswith("max"):
            _software = "3ds_max"
        elif fm_name.startswith("sd_") or fm_name.startswith("sd-"):
            _software = "substance_designer"
        elif fm_name.startswith("sp_") or fm_name.startswith("sp-"):
            _software = "substance_painter"
        elif fm_name.startswith("blender"):
            _software = "blender"
        elif fm_name.startswith("houdini"):
            _software = "houdini"
        else:
            _software = "universal"

    # 构建完整 manifest，existing 的值优先
    full = {
        "manifest_version": "1.0",
        "name": fm_name,
        "display_name": _ac("display_name", fm_name.replace("_", " ").title()),
        "description": fm.get("description", ""),
        "version": existing.get("version", _ac("version", "1.0.0")),
        "author": _ac("author", "ArtClaw"),
        "software": _software,
        "category": _ac("category", "utils"),
        "risk_level": _ac("risk_level", "low"),
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
        logger.info(f"Git commit: {msg.splitlines()[0]}")
    except Exception as e:
        logger.warning(f"Git commit skipped: {e}")


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
                        logger.info(f"Source renamed: {old_name} → {new_name}")

        _notify_skill_hub()

        return {"ok": True, "message": f"已重命名: {old_name} → {new_name}"}
    except Exception as e:
        return {"ok": False, "message": f"重命名失败: {e}"}


def _notify_skill_hub(force: bool = False) -> None:
    """通知 skill_hub/skill_runtime 重新扫描。force=True 时强制重扫（发布后需要刷新缓存的 version）。"""
    try:
        from skill_hub import get_skill_hub
        hub = get_skill_hub()
        if hub:
            hub.scan_and_register()
            return
    except ImportError:
        pass
    except Exception:
        pass

    # DCC 环境: 尝试 skill_runtime
    try:
        from core.skill_runtime import get_skill_runtime
        rt = get_skill_runtime()
        if rt:
            rt.scan_and_register()
    except ImportError:
        pass
    except Exception:
        pass
