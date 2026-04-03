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

    # 触发重新扫描
    try:
        from skill_hub import get_skill_hub
        hub = get_skill_hub()
        if hub:
            hub.scan_and_register(metadata_only=True)
    except Exception:
        hub = None

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

    # 1) skill_hub manifests
    if hub:
        try:
            for m in hub._all_manifests:
                name = m.name
                if name in seen:
                    continue
                seen.add(name)
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
            seen.add(name)
            desc = _read_skill_desc(sm)
            src_info = source_map.get(name, {})
            layer = src_info.get("layer", "platform")
            sw = src_info.get("dcc", "universal")
            result.append({
                "name": name, "display_name": name,
                "description": desc, "version": "",
                "layer": layer, "software": sw,
                "category": "general", "risk_level": "low", "author": "",
                "has_code": False, "has_skill_md": True,
                "install_status": "installed",
                "installed_dir": sd,
                "source_dir": src_info.get("path", ""),
                "enabled": name not in disabled,
                "pinned": name in pinned,
            })

    # 3) 未安装 + 可更新
    try:
        from skill_sync import compare_source_vs_runtime
        diff = compare_source_vs_runtime()
        if not diff.get("error"):
            for info in diff.get("available", []):
                n = info["name"]
                if n in seen:
                    continue
                seen.add(n)
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
            for s in result:
                if s["name"] in updatable:
                    s["updatable"] = True
                    for u in diff.get("updatable", []):
                        if u["name"] == s["name"]:
                            s["source_version"] = u.get("version", "")
                            break
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


def _read_skill_desc(skill_md_path: str) -> str:
    """从 SKILL.md 读取第一行有效描述"""
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
