#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtClaw Bridge — 平台配置安装
==============================

管理平台配置（PLATFORM_CONFIGS）、Skills 安装、config.json 写入。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from install_utils import (
    ROOT_DIR,
    SKILLS_SRC,
    cprint,
    get_gateway_src,
    get_platform_src,
)

# ---------------------------------------------------------------------------
# 支持的平台及其默认配置
# ---------------------------------------------------------------------------


def _get_lobster_skills_path() -> str:
    """获取 LobsterAI 的 Skills 安装目录"""
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        appdata = os.path.expanduser("~/AppData/Roaming")
    return os.path.join(appdata, "LobsterAI", "SKILLs")


def _get_lobster_config_path() -> str:
    """获取 LobsterAI 的 openclaw.json 路径"""
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        appdata = os.path.expanduser("~/AppData/Roaming")
    return os.path.join(appdata, "LobsterAI", "openclaw", "state", "openclaw.json")


PLATFORM_CONFIGS = {
    "openclaw": {
        "display_name": "OpenClaw",
        "gateway_url": "ws://127.0.0.1:18789",
        "mcp_port": 8080,
        "skills_installed_path": "~/.openclaw/skills",
        "mcp_config_path": "~/.openclaw/openclaw.json",
        "mcp_config_key": "mcp.servers",
        "bridge_file": "openclaw_ws.py",
        "has_gateway": True,
        "has_setup_config": True,
    },
    "workbuddy": {
        "display_name": "WorkBuddy",
        "gateway_url": "ws://127.0.0.1:18789",
        "mcp_port": 8080,
        "skills_installed_path": "~/.workbuddy/skills",
        "mcp_config_path": "~/.workbuddy/config.json",
        "mcp_config_key": "mcpServers",
        "bridge_file": "workbuddy_bridge.py",
        "has_gateway": False,
        "has_setup_config": False,
    },
    "claude": {
        "display_name": "Claude Desktop",
        "gateway_url": "",
        "mcp_port": 8080,
        "skills_installed_path": "~/.claude/skills",
        "mcp_config_path": "~/.claude/config.json",
        "mcp_config_key": "mcpServers",
        "bridge_file": "claude_bridge.py",
        "has_gateway": False,
        "has_setup_config": False,
    },
    "lobster": {
        "display_name": "LobsterAI",
        "gateway_url": "ws://127.0.0.1:18790",
        "mcp_port": 8080,
        "skills_installed_path": _get_lobster_skills_path(),
        "mcp_config_path": _get_lobster_config_path(),
        "mcp_config_key": "plugins.entries.mcp-bridge.config.servers",
        "bridge_file": "",
        "has_gateway": False,
        "has_setup_config": True,
    },
}


# ---------------------------------------------------------------------------
# 配置写入
# ---------------------------------------------------------------------------

def write_artclaw_config(platform_type: str):
    """
    写入 ~/.artclaw/config.json 的平台配置。
    保留已有字段（如 project_root、ue_agent_id），更新 platform/skills/mcp 节。
    """
    pcfg = PLATFORM_CONFIGS.get(platform_type)
    if not pcfg:
        cprint("警告", f"未知平台: {platform_type}，跳过配置写入", "yellow")
        return

    config_path = os.path.expanduser("~/.artclaw/config.json")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    # 读取现有配置
    existing = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass

    existing["project_root"] = str(ROOT_DIR)
    existing["platform"] = {
        "type": platform_type,
        "gateway_url": pcfg["gateway_url"],
        "mcp_port": pcfg["mcp_port"],
    }
    existing["skills"] = {
        "installed_path": pcfg["skills_installed_path"],
        "disabled": existing.get("skills", {}).get("disabled", []),
        "pinned": existing.get("skills", {}).get("pinned", []),
    }
    existing["mcp"] = {
        "config_path": pcfg["mcp_config_path"],
        "config_key": pcfg["mcp_config_key"],
    }

    # 写入 platforms_registry
    registry = []
    for ptype, pconf in PLATFORM_CONFIGS.items():
        gw = pconf.get("gateway_url", "")
        if gw:
            registry.append({
                "type": ptype,
                "display_name": pconf.get("display_name", ptype.title()),
                "gateway_url": gw,
            })
    if registry:
        existing["platforms_registry"] = registry

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    cprint("OK", f"~/.artclaw/config.json 已更新 (platform={platform_type})", "green")


# ---------------------------------------------------------------------------
# 平台安装
# ---------------------------------------------------------------------------

def install_openclaw(platform_type: str = "openclaw"):
    """配置 OpenClaw mcp-bridge 插件"""
    print()
    print("  ── OpenClaw mcp-bridge 配置 ────────────────────────")
    print()

    platform_src = get_platform_src(platform_type)
    gateway_src = get_gateway_src(platform_type)
    pcfg = PLATFORM_CONFIGS.get(platform_type, {})

    # 复制 Gateway 插件文件（仅支持 Gateway 的平台）
    if pcfg.get("has_gateway") and gateway_src.exists():
        ext_dir = os.path.join(os.path.expanduser("~"), ".openclaw", "extensions", "mcp-bridge")
        os.makedirs(ext_dir, exist_ok=True)

        for fname in ["index.ts", "openclaw.plugin.json"]:
            src = gateway_src / fname
            if src.exists():
                shutil.copy2(str(src), os.path.join(ext_dir, fname))
        cprint("OK", f"mcp-bridge 已复制到: {ext_dir}", "green")
    else:
        cprint("跳过", f"平台 {platform_type} 无 Gateway 插件", "yellow")

    # 安装 Skills
    skills_installed_path = os.path.expanduser(
        pcfg.get("skills_installed_path", "~/.openclaw/skills")
    )
    os.makedirs(skills_installed_path, exist_ok=True)

    skill_count = 0
    for layer in ("official", "marketplace"):
        layer_dir = SKILLS_SRC / layer
        if not layer_dir.exists():
            continue
        for category_dir in layer_dir.iterdir():
            if not category_dir.is_dir():
                continue
            for skill_dir in category_dir.iterdir():
                if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                    continue
                if not (skill_dir / "SKILL.md").exists() and not (skill_dir / "manifest.json").exists():
                    continue
                dst = os.path.join(skills_installed_path, skill_dir.name)
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(
                    str(skill_dir), dst,
                    ignore=shutil.ignore_patterns("__pycache__"),
                )
                skill_count += 1
    if skill_count:
        cprint("OK", f"{skill_count} 个 Skills 已安装到: {skills_installed_path}", "green")
    else:
        cprint("跳过", "未找到可安装的 Skills", "yellow")

    # 写入 ~/.artclaw/config.json
    write_artclaw_config(platform_type)

    # 运行平台特定配置脚本
    if pcfg.get("has_setup_config"):
        config_script = None
        for f in platform_src.glob("setup_*_config.py"):
            config_script = f
            break
        if config_script and config_script.exists():
            cprint("配置", f"运行 {config_script.name}...")
            try:
                subprocess.run(
                    [sys.executable, str(config_script), "--ue", "--maya", "--max"],
                    check=True, timeout=30,
                )
                cprint("OK", "平台配置已更新", "green")
            except Exception as e:
                cprint("警告", f"配置脚本失败: {e}", "yellow")
                cprint("提示", f"请手动运行: python {config_script}", "yellow")
        else:
            cprint("警告", f"平台 {platform_type} 的配置脚本不存在", "yellow")
    else:
        cprint("跳过", f"平台 {platform_type} 无配置脚本", "yellow")

    cprint("完成", f"平台配置成功 (platform={platform_type})!", "green")
    return True
