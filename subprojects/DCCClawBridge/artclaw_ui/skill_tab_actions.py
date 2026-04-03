"""
skill_tab_actions.py - Skill Tab 操作方法
============================================

启用/禁用/钉选/安装/卸载/更新/同步/发布/详情。
从 skill_tab.py 拆分，保持文件在 500 行以内。
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger("artclaw.ui.skill_actions")


def exec_config_action(action: str, skill_name: str):
    """执行 Skill 配置操作 (enable/disable/pin/unpin)"""
    try:
        cfg_path = os.path.expanduser("~/.artclaw/config.json")
        cfg = {}
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        disabled = set(cfg.get("disabled_skills", []))
        pinned = list(cfg.get("pinned_skills", []))

        if action == "enable":
            disabled.discard(skill_name)
            try:
                from skill_hub import get_skill_hub
                hub = get_skill_hub()
                if hub:
                    hub.enable_skill(skill_name)
            except Exception:
                pass
        elif action == "disable":
            disabled.add(skill_name)
            if skill_name in pinned:
                pinned.remove(skill_name)
            try:
                from skill_hub import get_skill_hub
                hub = get_skill_hub()
                if hub:
                    hub.disable_skill(skill_name)
            except Exception:
                pass
        elif action == "pin":
            if skill_name not in pinned and len(pinned) < 5:
                pinned.append(skill_name)
            disabled.discard(skill_name)
        elif action == "unpin":
            if skill_name in pinned:
                pinned.remove(skill_name)

        cfg["disabled_skills"] = sorted(disabled)
        cfg["pinned_skills"] = pinned
        os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as ex:
        logger.error("Skill 配置操作失败: %s", ex)


def do_install(skill_name: str):
    try:
        from skill_sync import install_skill
        install_skill(skill_name)
    except Exception as ex:
        logger.error("安装失败: %s", ex)


def do_uninstall(skill_name: str):
    try:
        from skill_sync import uninstall_skill
        uninstall_skill(skill_name)
    except Exception as ex:
        logger.error("卸载失败: %s", ex)


def do_update(skill_name: str):
    try:
        from skill_sync import update_skill
        update_skill(skill_name)
    except Exception as ex:
        logger.error("更新失败: %s", ex)


def do_sync_all():
    try:
        from skill_sync import sync_all
        sync_all()
    except Exception as ex:
        logger.error("同步失败: %s", ex)
