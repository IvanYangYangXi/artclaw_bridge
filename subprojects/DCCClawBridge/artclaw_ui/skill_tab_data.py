"""
skill_tab_data.py - Skill Tab 数据查询
=========================================

从 skill_hub + 安装目录 + 源码目录 + skill_sync 收集 Skill 信息。
从 skill_tab.py 拆分，保持文件在 500 行以内。
"""

from __future__ import annotations

import json
import logging
import os
from typing import List

from artclaw_ui.utils import get_artclaw_config

logger = logging.getLogger("artclaw.ui.skill_data")


def query_all_skills() -> List[dict]:
    """执行 Python 查询获取 Skill 列表，返回 dict 列表"""
    result = []

    # 触发重新扫描: 尝试 skill_hub (UE) → skill_runtime (DCC) → None
    hub = None
    try:
        from skill_hub import get_skill_hub
        hub = get_skill_hub()
        if hub:
            hub.scan_and_register(metadata_only=True)
    except ImportError:
        try:
            from core.skill_runtime import get_skill_runtime
            hub = get_skill_runtime()
        except ImportError:
            pass
    except Exception:
        pass

    # 加载配置
    ac_cfg = get_artclaw_config()
    installed_path = ac_cfg.get("skills", {}).get("installed_path", "")
    if not installed_path:
        pt = ac_cfg.get("platform", {}).get("type", "openclaw")
        defaults = {"openclaw": "~/.openclaw/skills",
                    "workbuddy": "~/.workbuddy/skills"}
        installed_path = defaults.get(pt, "~/.openclaw/skills")
    oc_dir = os.path.expanduser(installed_path)

    # 项目源码扫描
    project_root = ac_cfg.get("project_root", "")
    source_map = _scan_source_skills(project_root)

    # 配置中的 pinned/disabled
    config_path = os.path.expanduser("~/.artclaw/config.json")
    pinned, disabled = [], []
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            pinned = cfg.get("pinned_skills", [])
            disabled = cfg.get("disabled_skills", [])
        except Exception:
            pass

    seen = set()

    def _mark_seen(n: str):
        """标记名称及其 kebab/snake 变体为已见，防止重复"""
        seen.add(n)
        seen.add(n.replace("-", "_"))
        seen.add(n.replace("_", "-"))

    # 1) skill_hub / skill_runtime manifests
    if hub:
        try:
            # skill_hub (UE) uses _all_manifests; skill_runtime (DCC) uses _skills dict
            manifests = getattr(hub, '_all_manifests', None)
            if manifests is None:
                # skill_runtime: _skills is a dict of SkillManifest
                manifests = list(getattr(hub, '_skills', {}).values())
            for m in manifests:
                name = m.name
                if name in seen:
                    continue
                _mark_seen(name)
                src_info = source_map.get(name, {})
                layer = src_info.get("layer", getattr(m, "source_layer", "custom"))
                sw = src_info.get("dcc", "") or getattr(m, "software", "universal")
                src_dir = str(getattr(m, "source_dir", "") or "")
                result.append({
                    "name": name,
                    "display_name": getattr(m, "display_name", name),
                    "description": getattr(m, "description", ""),
                    "version": getattr(m, "version", ""),
                    "layer": layer, "software": sw,
                    "category": getattr(m, "category", "general"),
                    "risk_level": getattr(m, "risk_level", "low"),
                    "author": getattr(m, "author", ""),
                    "has_code": os.path.exists(os.path.join(src_dir, "__init__.py")) if src_dir else False,
                    "has_skill_md": os.path.exists(os.path.join(src_dir, "SKILL.md")) if src_dir else False,
                    "install_status": "installed",
                    "installed_dir": src_dir,
                    "source_dir": src_info.get("path", ""),
                    "enabled": name not in disabled,
                    "pinned": name in pinned,
                })
        except Exception as ex:
            logger.error("读取 skill_hub manifests 失败: %s", ex)

    # 2) 平台已安装 Skills 目录
    if os.path.isdir(oc_dir):
        for name in sorted(os.listdir(oc_dir)):
            if name in seen:
                continue
            sd = os.path.join(oc_dir, name)
            sm = os.path.join(sd, "SKILL.md")
            if not os.path.isdir(sd) or not os.path.isfile(sm):
                continue
            _mark_seen(name)
            desc, author, version = _read_skill_metadata(sd)
            src_info = source_map.get(name, {})
            layer = src_info.get("layer", "platform")
            sw = src_info.get("dcc", "universal")
            result.append({
                "name": name, "display_name": name,
                "description": desc, "version": version,
                "layer": layer, "software": sw,
                "category": "general", "risk_level": "low", "author": author,
                "has_code": False, "has_skill_md": True,
                "install_status": "installed",
                "installed_dir": sd,
                "source_dir": src_info.get("path", ""),
                "enabled": name not in disabled,
                "pinned": name in pinned,
            })

    # 3) 未安装 + 可更新 + 有修改
    try:
        from skill_sync import compare_source_vs_runtime
        diff = compare_source_vs_runtime()
        if not diff.get("error"):
            for info in diff.get("available", []):
                n = info["name"]
                if n in seen:
                    continue
                _mark_seen(n)
                result.append({
                    "name": n, "display_name": n,
                    "description": "", "version": info.get("version", ""),
                    "layer": info.get("layer", "marketplace"),
                    "software": info.get("dcc", "universal"),
                    "install_status": "not_installed",
                    "source_dir": info.get("path", ""),
                    "enabled": True, "pinned": False,
                })
            updatable = {i["name"] for i in diff.get("updatable", [])}
            modified = {i["name"] for i in diff.get("modified", [])}
            orphaned = {i["name"] for i in diff.get("orphaned", [])}
            for s in result:
                if s["name"] in updatable:
                    s["updatable"] = True
                    for u in diff.get("updatable", []):
                        if u["name"] == s["name"]:
                            s["source_version"] = u.get("version", "")
                            break
                if s["name"] in modified:
                    s["modified"] = True
                if s["name"] in orphaned:
                    s["orphaned"] = True
    except Exception:
        pass

    return result


def _scan_source_skills(project_root: str) -> dict:
    """扫描项目源码目录，返回 {skill_name: {layer, path, dcc}}"""
    source_map = {}
    if not project_root or not os.path.isdir(project_root):
        return source_map
    skills_root = os.path.join(project_root, "skills")
    if not os.path.isdir(skills_root):
        return source_map
    skip = {"templates", "__pycache__", ".git"}
    for layer_name in os.listdir(skills_root):
        lp = os.path.join(skills_root, layer_name)
        if not os.path.isdir(lp) or layer_name in skip:
            continue
        for dcc_name in os.listdir(lp):
            dp = os.path.join(lp, dcc_name)
            if not os.path.isdir(dp) or dcc_name in skip:
                continue
            for sn in os.listdir(dp):
                sp = os.path.join(dp, sn)
                if os.path.isdir(sp) and sn not in skip:
                    source_map[sn] = {"layer": layer_name, "path": sp, "dcc": dcc_name}
    return source_map


def _read_skill_metadata(skill_dir: str) -> tuple:
    """从 Skill 目录读取 description, author, version。
    优先从 manifest.json，不足时从 SKILL.md frontmatter 补充。
    支持多行 description (> 和 |) 和嵌套 metadata.artclaw.* 字段。
    返回: (description, author, version)
    """
    desc = ""
    author = ""
    version = ""

    # 1) 从 manifest.json 读取
    manifest_path = os.path.join(skill_dir, "manifest.json")
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                m = json.load(f)
            desc = m.get("description", "")[:120]
            author = m.get("author", "")
            version = m.get("version", "")
        except Exception:
            pass

    # 2) 从 SKILL.md frontmatter 补充（使用 skill_sync 的轻量解析器）
    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    if os.path.isfile(skill_md_path) and (not desc or not author or not version):
        try:
            from pathlib import Path
            from skill_sync import _parse_frontmatter_light
            fm = _parse_frontmatter_light(Path(skill_md_path))
            if fm:
                if not author and fm.get("author"):
                    author = fm["author"]
                if not version and fm.get("version"):
                    version = fm["version"]
                if not desc and fm.get("description"):
                    desc = fm["description"][:120]
        except ImportError:
            # skill_sync 不可用时回退到简单解析
            try:
                with open(skill_md_path, "r", encoding="utf-8") as f:
                    raw = f.read(4096)
            except Exception:
                raw = ""

            if raw.startswith("---"):
                end = raw.find("---", 3)
                if end > 0:
                    fm_block = raw[3:end]
                    in_artclaw = False
                    in_multiline = False
                    multiline_key = ""
                    multiline_val = ""
                    fm_desc = ""
                    fm_author = ""
                    fm_version = ""
                    for line in fm_block.split("\n"):
                        stripped = line.strip()
                        indent = len(line) - len(line.lstrip())

                        # 处理多行值续行
                        if in_multiline:
                            if not stripped:
                                continue
                            if indent >= 2:
                                multiline_val += " " + stripped
                                continue
                            else:
                                if multiline_key == "description":
                                    fm_desc = multiline_val.strip()[:120]
                                in_multiline = False

                        if indent == 0:
                            in_artclaw = False
                        if stripped.startswith("description:"):
                            val = stripped[12:].strip()
                            if val == ">" or val == "|":
                                in_multiline = True
                                multiline_key = "description"
                                multiline_val = ""
                            elif val and not fm_desc:
                                fm_desc = val[:120]
                        elif stripped.startswith("author:"):
                            fm_author = stripped[7:].strip()
                        elif stripped.startswith("version:"):
                            fm_version = stripped[8:].strip()
                        elif stripped == "artclaw:":
                            in_artclaw = True

                    if in_multiline and multiline_key == "description":
                        fm_desc = multiline_val.strip()[:120]

                    if not author and fm_author:
                        author = fm_author
                    if not version and fm_version:
                        version = fm_version
                    if not desc and fm_desc:
                        desc = fm_desc

        # 如果还没有 desc，取 SKILL.md 正文第一行
        if not desc:
            try:
                with open(skill_md_path, "r", encoding="utf-8") as f:
                    raw = f.read(2048)
                for line in raw.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("---"):
                        # 跳过 frontmatter 内容
                        if raw.startswith("---"):
                            end = raw.find("---", 3)
                            if end > 0 and raw.find(line) < end + 3:
                                continue
                        desc = line[:120]
                        break
            except Exception:
                pass

    return desc, author, version


def _read_skill_desc(skill_md_path: str) -> str:
    """从 SKILL.md 读取第一行有效描述（保留向后兼容）"""
    try:
        with open(skill_md_path, "r", encoding="utf-8") as f:
            raw = f.read(2048)
        for line in raw.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("---"):
                return line[:120]
    except Exception:
        pass
    return ""
