#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtClaw Bridge — 跨平台安装器
================================

统一安装 UE / Maya / 3ds Max 插件 + 平台配置。
每个目标部署为自包含模式（bridge_core 等共享模块打包进目标目录）。
支持多平台: openclaw (默认) / workbuddy / claude

用法:
    python install.py --maya                              # 安装 Maya 插件
    python install.py --maya --maya-version 2024          # 指定 Maya 版本
    python install.py --max --max-version 2024            # 安装 Max 插件
    python install.py --ue --ue-project "C:\\path\\to\\proj"  # 安装 UE 插件
    python install.py --openclaw                          # 配置平台
    python install.py --all --ue-project "C:\\path\\to\\proj"  # 全部安装
    python install.py --uninstall --maya                  # 卸载 Maya 插件
    python install.py --uninstall --max                   # 卸载 Max 插件
    python install.py --uninstall --ue --ue-project "C:\\path\\to\\proj"  # 卸载 UE 插件
    python install.py --platform workbuddy --maya         # 安装 Maya 并配置 WorkBuddy 平台
    python install.py --force                             # 跳过覆盖确认
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent
DCC_BRIDGE_SRC = ROOT_DIR / "subprojects" / "DCCClawBridge"
UE_PLUGIN_SRC = ROOT_DIR / "subprojects" / "UEDAgentProj" / "Plugins" / "UEClawBridge"
BRIDGE_MODULES_SRC = ROOT_DIR / "core"
PLATFORMS_DIR = ROOT_DIR / "platforms"
SKILLS_SRC = ROOT_DIR / "skills"


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


# 需要打包到每个目标的共享模块
SHARED_MODULES = ["bridge_core.py", "bridge_config.py", "bridge_diagnostics.py"]

# 支持的平台及其默认配置（与 bridge_config.py 的 _PLATFORM_DEFAULTS 保持一致）
PLATFORM_CONFIGS = {
    "openclaw": {
        "gateway_url": "ws://127.0.0.1:18789",
        "mcp_port": 8080,
        "skills_installed_path": "~/.openclaw/skills",
        "mcp_config_path": "~/.openclaw/openclaw.json",
        "mcp_config_key": "mcp.servers",
        "bridge_file": "openclaw_bridge.py",
        "has_gateway": True,
        "has_setup_config": True,
    },
    "workbuddy": {
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
        "gateway_url": "ws://127.0.0.1:18790",
        "mcp_port": 8080,
        "skills_installed_path": _get_lobster_skills_path(),
        "mcp_config_path": _get_lobster_config_path(),
        "mcp_config_key": "plugins.entries.mcp-bridge.config.servers",
        "bridge_file": "",  # LobsterAI 客户端操作，无需 DCC 内嵌 bridge
        "has_gateway": False,  # Gateway 内置于 LobsterAI
        "has_setup_config": True,
    },
}

# userSetup / startup 注入标记
INJECT_START = "# ===== ArtClaw Bridge START ====="
INJECT_END = "# ===== ArtClaw Bridge END ====="


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def cprint(tag: str, msg: str, color: str = ""):
    """带标签的彩色输出"""
    colors = {"green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m",
              "cyan": "\033[96m", "reset": "\033[0m"}
    c = colors.get(color, "")
    r = colors["reset"] if c else ""
    print(f"  {c}[{tag}]{r} {msg}")


def confirm_overwrite(path: str, force: bool) -> bool:
    """确认是否覆盖已有目标"""
    if not os.path.exists(path):
        return True
    if force:
        cprint("覆盖", f"目标已存在，强制覆盖: {path}", "yellow")
        return True
    ans = input(f"  [提示] 目标已存在: {path}\n         是否覆盖？(Y/n): ").strip().lower()
    return ans in ("", "y", "yes")


def copy_dir(src: str, dst: str):
    """复制目录（镜像模式：先删后复制）"""
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def get_platform_src(platform_type: str) -> Path:
    """获取平台源码目录"""
    return PLATFORMS_DIR / platform_type


def get_gateway_src(platform_type: str) -> Path:
    """获取平台 Gateway 插件源码目录"""
    return get_platform_src(platform_type) / "gateway"


def copy_shared_modules(dst_dir: str):
    """将 bridge_core 等共享模块复制到目标目录"""
    os.makedirs(dst_dir, exist_ok=True)
    for mod in SHARED_MODULES:
        src = BRIDGE_MODULES_SRC / mod
        if src.exists():
            shutil.copy2(str(src), os.path.join(dst_dir, mod))
        else:
            cprint("警告", f"共享模块不存在: {src}", "yellow")


def copy_platform_bridge(platform_type: str, dst_dir: str):
    """将平台特定 bridge 文件复制到目标目录（openclaw 额外复制 chat/diagnose 模块）"""
    pcfg = PLATFORM_CONFIGS.get(platform_type)
    if not pcfg:
        cprint("警告", f"未知平台: {platform_type}，跳过 bridge 文件复制", "yellow")
        return
    os.makedirs(dst_dir, exist_ok=True)
    platform_src = get_platform_src(platform_type)

    # 主 bridge 文件
    files_to_copy = [pcfg["bridge_file"]]
    # openclaw 平台额外携带独立模块
    if platform_type == "openclaw":
        files_to_copy += ["openclaw_chat.py", "openclaw_diagnose.py"]

    for fname in files_to_copy:
        src = platform_src / fname
        if src.exists():
            shutil.copy2(str(src), os.path.join(dst_dir, fname))
            cprint("OK", f"平台 bridge 已复制: {fname}", "green")
        else:
            cprint("警告", f"平台 bridge 文件不存在: {src}", "yellow")


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

    # 更新 project_root
    existing["project_root"] = str(ROOT_DIR)

    # 更新平台配置
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

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    cprint("OK", f"~/.artclaw/config.json 已更新 (platform={platform_type})", "green")


def read_file(path: str) -> str:
    """读取文件内容，不存在返回空串"""
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_file(path: str, content: str):
    """写入文件（UTF-8）"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# startup 文件注入 / 移除（幂等）
# ---------------------------------------------------------------------------

def _get_artclaw_startup_block(source_file: str) -> str:
    """读取源 startup 文件并包裹在标记块中"""
    content = read_file(source_file)
    if not content:
        return ""
    # 去掉源文件中的模块级文档字符串 header（保留功能代码）
    return f"""{INJECT_START}
{content}
{INJECT_END}
"""


def _has_artclaw_block(content: str) -> bool:
    """检查内容中是否已包含 ArtClaw 注入块"""
    return INJECT_START in content


def _has_artclaw_code(content: str) -> bool:
    """检查是否包含 ArtClaw 相关代码（宽松匹配）"""
    lower = content.lower()
    return "artclaw" in lower or "dccclawbridge" in lower


def _remove_artclaw_block(content: str) -> str:
    """从文件内容中移除 ArtClaw 注入块"""
    pattern = re.compile(
        re.escape(INJECT_START) + r".*?" + re.escape(INJECT_END),
        re.DOTALL,
    )
    result = pattern.sub("", content)
    # 清理多余空行
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip() + "\n" if result.strip() else ""


def inject_startup(target_file: str, source_file: str, label: str) -> str:
    """
    将 ArtClaw 启动代码注入到目标 startup 文件。
    幂等：已有标记块则更新，已有非标记 ArtClaw 代码则跳过，否则追加。
    
    返回状态: "created" | "updated" | "skipped" | "appended"
    """
    block = _get_artclaw_startup_block(source_file)
    if not block:
        cprint("警告", f"启动文件源不存在: {source_file}", "yellow")
        return "skipped"

    existing = read_file(target_file)

    if not existing:
        # 目标不存在 → 创建新文件
        write_file(target_file, block)
        cprint("创建", f"{label} → {target_file}", "green")
        return "created"

    if _has_artclaw_block(existing):
        # 已有标记块 → 替换更新
        updated = _remove_artclaw_block(existing)
        if updated:
            updated = updated.rstrip("\n") + "\n\n" + block
        else:
            updated = block
        write_file(target_file, updated)
        cprint("更新", f"{label} 已更新 (替换旧标记块)", "green")
        return "updated"

    if _has_artclaw_code(existing):
        # 有 ArtClaw 代码但没有标记 → 跳过，避免重复
        cprint("跳过", f"{label} 已包含 ArtClaw 代码 (非标记块)，请手动检查", "yellow")
        return "skipped"

    # 追加
    content = existing.rstrip("\n") + "\n\n" + block
    write_file(target_file, content)
    cprint("追加", f"{label} 已追加到: {target_file}", "green")
    return "appended"


def remove_startup_injection(target_file: str, label: str) -> bool:
    """从目标文件中移除 ArtClaw 注入块。返回是否有变更。"""
    if not os.path.isfile(target_file):
        cprint("跳过", f"{label} 文件不存在: {target_file}", "yellow")
        return False

    content = read_file(target_file)
    if not _has_artclaw_block(content):
        cprint("跳过", f"{label} 中未找到 ArtClaw 标记块", "yellow")
        return False

    cleaned = _remove_artclaw_block(content)
    if cleaned.strip():
        write_file(target_file, cleaned)
        cprint("清理", f"已从 {label} 中移除 ArtClaw 代码块", "green")
    else:
        # 文件只剩空白 → 删除整个文件
        os.remove(target_file)
        cprint("删除", f"{label} 已删除 (文件仅含 ArtClaw 代码)", "green")
    return True


# ---------------------------------------------------------------------------
# 安装: UE
# ---------------------------------------------------------------------------

def install_ue(ue_project: str, force: bool, platform_type: str = "openclaw"):
    """安装 UE 插件到指定项目"""
    print()
    print("  ── Unreal Engine 插件安装 ──────────────────────────")
    print()

    if not ue_project:
        cprint("错误", "请通过 --ue-project 指定 UE 项目路径", "red")
        return False

    ue_project = os.path.abspath(ue_project)
    uproject_files = glob.glob(os.path.join(ue_project, "*.uproject"))
    if not uproject_files:
        cprint("错误", f"未找到 .uproject 文件: {ue_project}", "red")
        return False

    cprint("OK", f"UE 项目: {uproject_files[0]}", "green")
    cprint("信息", f"平台: {platform_type}")

    if not UE_PLUGIN_SRC.exists():
        cprint("错误", f"UE 插件源码不存在: {UE_PLUGIN_SRC}", "red")
        return False

    plugin_dst = os.path.join(ue_project, "Plugins", "UEClawBridge")
    if not confirm_overwrite(plugin_dst, force):
        cprint("跳过", "UE 插件安装", "yellow")
        return True

    # 复制插件
    cprint("复制", "UEClawBridge 插件...")
    copy_dir(str(UE_PLUGIN_SRC), plugin_dst)
    cprint("OK", f"插件已安装到: {plugin_dst}", "green")

    # 复制共享模块
    cprint("复制", "bridge_core 共享模块...")
    python_dst = os.path.join(plugin_dst, "Content", "Python")
    copy_shared_modules(python_dst)
    cprint("OK", f"共享模块已打包到: {python_dst}", "green")

    # 复制平台 bridge
    cprint("复制", f"平台 bridge ({platform_type})...")
    copy_platform_bridge(platform_type, python_dst)

    # 尝试安装 Python 依赖
    _install_ue_python_deps()

    cprint("完成", "UE 插件安装成功!", "green")
    return True


def uninstall_ue(ue_project: str):
    """卸载 UE 插件"""
    print()
    print("  ── Unreal Engine 插件卸载 ──────────────────────────")
    print()

    if not ue_project:
        cprint("错误", "请通过 --ue-project 指定 UE 项目路径", "red")
        return False

    plugin_dst = os.path.join(os.path.abspath(ue_project), "Plugins", "UEClawBridge")
    if os.path.isdir(plugin_dst):
        shutil.rmtree(plugin_dst)
        cprint("删除", f"已删除: {plugin_dst}", "green")
    else:
        cprint("跳过", f"UE 插件不存在: {plugin_dst}", "yellow")

    return True


def _install_ue_python_deps():
    """尝试查找 UE Python 并安装依赖"""
    ue_python = _find_ue_python()
    if not ue_python:
        cprint("提示", "未找到 UE Python，请手动安装: pip install websockets pydantic", "yellow")
        return
    try:
        subprocess.run(
            [ue_python, "-m", "pip", "install", "websockets", "pydantic"],
            capture_output=True, timeout=120,
        )
        cprint("OK", "Python 依赖已安装", "green")
    except Exception as e:
        cprint("警告", f"依赖安装失败: {e}", "yellow")


def _find_ue_python() -> str | None:
    """查找 UE 内置 Python"""
    if platform.system() != "Windows":
        return None
    for ver in ["5.7", "5.6", "5.5", "5.4", "5.3"]:
        for base in ["C:\\Epic Games", "C:\\Program Files\\Epic Games"]:
            p = os.path.join(base, f"UE_{ver}", "Engine", "Binaries",
                             "ThirdParty", "Python3", "Win64", "python.exe")
            if os.path.isfile(p):
                cprint("OK", f"找到 UE {ver} Python: {p}", "cyan")
                return p
    return None


# ---------------------------------------------------------------------------
# 安装: Maya
# ---------------------------------------------------------------------------

def install_maya(maya_version: str, force: bool, platform_type: str = "openclaw"):
    """安装 Maya 插件"""
    print()
    print("  ── Maya 插件安装 ───────────────────────────────────")
    print()

    scripts_dir = os.path.join(
        os.path.expanduser("~"), "Documents", "maya", maya_version, "scripts"
    )
    dcc_dst = os.path.join(scripts_dir, "DCCClawBridge")

    cprint("信息", f"Maya 版本: {maya_version}")
    cprint("信息", f"平台: {platform_type}")
    cprint("信息", f"目标目录: {dcc_dst}")

    if not confirm_overwrite(dcc_dst, force):
        cprint("跳过", "Maya 插件安装", "yellow")
        return True

    # 创建 scripts 目录
    os.makedirs(scripts_dir, exist_ok=True)

    # 复制 DCCClawBridge
    cprint("复制", "DCCClawBridge...")
    copy_dir(str(DCC_BRIDGE_SRC), dcc_dst)
    cprint("OK", f"DCCClawBridge 已安装到: {dcc_dst}", "green")

    # 复制共享模块到 core/
    cprint("复制", "bridge_core 共享模块到 core/...")
    copy_shared_modules(os.path.join(dcc_dst, "core"))
    cprint("OK", "共享模块已打包 (自包含部署)", "green")

    # 复制平台 bridge 到 core/
    cprint("复制", f"平台 bridge ({platform_type}) 到 core/...")
    copy_platform_bridge(platform_type, os.path.join(dcc_dst, "core"))

    # 注入 userSetup.py（幂等追加）
    user_setup_src = str(DCC_BRIDGE_SRC / "maya_setup" / "userSetup.py")
    user_setup_dst = os.path.join(scripts_dir, "userSetup.py")
    inject_startup(user_setup_dst, user_setup_src, "userSetup.py")

    cprint("完成", "Maya 插件安装成功!", "green")
    return True


def uninstall_maya(maya_version: str):
    """卸载 Maya 插件"""
    print()
    print("  ── Maya 插件卸载 ───────────────────────────────────")
    print()

    scripts_dir = os.path.join(
        os.path.expanduser("~"), "Documents", "maya", maya_version, "scripts"
    )
    dcc_dst = os.path.join(scripts_dir, "DCCClawBridge")

    # 删除 DCCClawBridge 目录
    if os.path.isdir(dcc_dst):
        shutil.rmtree(dcc_dst)
        cprint("删除", f"已删除: {dcc_dst}", "green")
    else:
        cprint("跳过", f"DCCClawBridge 不存在: {dcc_dst}", "yellow")

    # 从 userSetup.py 移除 ArtClaw 块
    user_setup = os.path.join(scripts_dir, "userSetup.py")
    remove_startup_injection(user_setup, "userSetup.py")

    cprint("完成", "Maya 插件卸载完成", "green")
    return True


# ---------------------------------------------------------------------------
# 安装: 3ds Max
# ---------------------------------------------------------------------------

def install_max(max_version: str, force: bool, platform_type: str = "openclaw"):
    """安装 3ds Max 插件"""
    print()
    print("  ── 3ds Max 插件安装 ────────────────────────────────")
    print()

    if platform.system() != "Windows":
        cprint("错误", "3ds Max 仅支持 Windows", "red")
        return False

    scripts_dir = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Autodesk", "3dsMax", max_version, "ENU", "scripts"
    )
    startup_dir = os.path.join(scripts_dir, "startup")
    dcc_dst = os.path.join(scripts_dir, "DCCClawBridge")

    cprint("信息", f"3ds Max 版本: {max_version}")
    cprint("信息", f"平台: {platform_type}")
    cprint("信息", f"目标目录: {dcc_dst}")

    if not confirm_overwrite(dcc_dst, force):
        cprint("跳过", "Max 插件安装", "yellow")
        return True

    # 创建目录
    os.makedirs(scripts_dir, exist_ok=True)
    os.makedirs(startup_dir, exist_ok=True)

    # 复制 DCCClawBridge
    cprint("复制", "DCCClawBridge...")
    copy_dir(str(DCC_BRIDGE_SRC), dcc_dst)
    cprint("OK", f"DCCClawBridge 已安装到: {dcc_dst}", "green")

    # 复制共享模块到 core/
    cprint("复制", "bridge_core 共享模块到 core/...")
    copy_shared_modules(os.path.join(dcc_dst, "core"))
    cprint("OK", "共享模块已打包 (自包含部署)", "green")

    # 复制平台 bridge 到 core/
    cprint("复制", f"平台 bridge ({platform_type}) 到 core/...")
    copy_platform_bridge(platform_type, os.path.join(dcc_dst, "core"))

    # 注入 startup.py（幂等追加）
    startup_src = str(DCC_BRIDGE_SRC / "max_setup" / "startup.py")
    startup_dst = os.path.join(startup_dir, "artclaw_startup.py")
    inject_startup(startup_dst, startup_src, "artclaw_startup.py")

    cprint("完成", "3ds Max 插件安装成功!", "green")
    return True


def uninstall_max(max_version: str):
    """卸载 3ds Max 插件"""
    print()
    print("  ── 3ds Max 插件卸载 ────────────────────────────────")
    print()

    scripts_dir = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Autodesk", "3dsMax", max_version, "ENU", "scripts"
    )
    startup_dir = os.path.join(scripts_dir, "startup")
    dcc_dst = os.path.join(scripts_dir, "DCCClawBridge")

    # 删除 DCCClawBridge 目录
    if os.path.isdir(dcc_dst):
        shutil.rmtree(dcc_dst)
        cprint("删除", f"已删除: {dcc_dst}", "green")
    else:
        cprint("跳过", f"DCCClawBridge 不存在: {dcc_dst}", "yellow")

    # 从 startup 移除 ArtClaw 块
    startup_file = os.path.join(startup_dir, "artclaw_startup.py")
    remove_startup_injection(startup_file, "artclaw_startup.py")

    cprint("完成", "3ds Max 插件卸载完成", "green")
    return True


# ---------------------------------------------------------------------------
# 安装: OpenClaw 配置
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

    # 安装 Skills（从 skills/official/ + marketplace/ 复制整个 Skill 目录）
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
                # 必须有 SKILL.md 或 manifest.json
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

    # 运行平台特定配置脚本（如 setup_openclaw_config.py / setup_lobster_config.py）
    if pcfg.get("has_setup_config"):
        # 动态查找平台目录下的 setup_*_config.py
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


# ---------------------------------------------------------------------------
# 总结
# ---------------------------------------------------------------------------

def print_summary(installed: list[str], uninstalled: list[str]):
    """打印安装总结"""
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    if uninstalled:
        print("  ║              卸载完成!                                ║")
    else:
        print("  ║              安装完成!                                ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()

    if installed:
        print("  已安装:")
        for item in installed:
            print(f"    [OK] {item}")
        print()

    if uninstalled:
        print("  已卸载:")
        for item in uninstalled:
            print(f"    [DEL] {item}")
        print()
        cprint("提示", "OpenClaw 配置中的 server 条目需手动移除 (可能有其他 DCC 在用)", "yellow")
        print()

    if not uninstalled:
        print("  后续步骤:")
        print()
        if "UE" in " ".join(installed):
            print("    UE:")
            print("      1. 打开 UE 项目，启用 \"UE Claw Bridge\" 插件")
            print("      2. 重启编辑器")
            print("      3. Window 菜单 → UE Claw Bridge")
            print("      4. 输入 /diagnose 验证连接")
            print()
        if "Maya" in " ".join(installed):
            print("    Maya:")
            print("      1. 启动 Maya → ArtClaw 菜单自动出现")
            print("      2. ArtClaw → 打开 Chat Panel")
            print("      3. 点击 连接 或输入 /connect")
            print()
        if "Max" in " ".join(installed):
            print("    3ds Max:")
            print("      1. 启动 Max → ArtClaw 自动加载")
            print("      2. 菜单栏 → ArtClaw → Chat Panel")
            print("      3. 点击 连接 或输入 /connect")
            print()
        if "OpenClaw" in " ".join(installed):
            print("    OpenClaw:")
            print("      1. 重启 Gateway: openclaw gateway restart")
            print("      2. 确认 mcp-bridge 已加载")
            print()


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ArtClaw Bridge 安装器 — UE / Maya / 3ds Max 一键部署",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python install.py --maya                               安装 Maya 插件 (默认版本 2023)
  python install.py --maya --maya-version 2024           安装到 Maya 2024
  python install.py --max --max-version 2024             安装 Max 插件
  python install.py --ue --ue-project "C:\\MyProject"     安装 UE 插件
  python install.py --openclaw                           配置平台 (默认 openclaw)
  python install.py --all --ue-project "C:\\MyProject"    全部安装
  python install.py --uninstall --maya                   卸载 Maya 插件
  python install.py --uninstall --maya --max             卸载 Maya + Max
  python install.py --force --maya --max                 跳过覆盖确认
  python install.py --platform workbuddy --maya          安装 Maya 并配置 WorkBuddy 平台
        """,
    )

    # 安装目标
    parser.add_argument("--maya", action="store_true", help="安装/卸载 Maya 插件")
    parser.add_argument("--max", action="store_true", help="安装/卸载 3ds Max 插件")
    parser.add_argument("--ue", action="store_true", help="安装/卸载 UE 插件")
    parser.add_argument("--openclaw", action="store_true", help="配置平台 (Gateway + Skills + config)")
    parser.add_argument("--all", action="store_true", help="安装全部 (UE + Maya + Max + 平台配置)")

    # 版本参数
    parser.add_argument("--maya-version", default="2023", help="Maya 版本 (默认: 2023)")
    parser.add_argument("--max-version", default="2024", help="3ds Max 版本 (默认: 2024)")
    parser.add_argument("--ue-project", default="", help="UE 项目路径 (包含 .uproject 的目录)")

    # 平台选择
    parser.add_argument(
        "--platform", default="openclaw",
        choices=list(PLATFORM_CONFIGS.keys()),
        help="目标平台 (默认: openclaw)，决定部署哪个平台的 bridge 和配置",
    )

    # 选项
    parser.add_argument("--force", action="store_true", help="跳过覆盖确认")
    parser.add_argument("--uninstall", action="store_true", help="卸载模式")

    args = parser.parse_args()

    # 无参数时显示帮助
    if not (args.maya or args.max or args.ue or args.openclaw or args.all):
        parser.print_help()
        return

    # --all 展开
    if args.all:
        args.maya = True
        args.max = True
        args.ue = True
        args.openclaw = True

    pt = args.platform

    # 验证平台目录存在（非卸载模式）
    if not args.uninstall:
        platform_dir = get_platform_src(pt)
        if not platform_dir.exists():
            cprint("警告", f"平台目录不存在: {platform_dir}（可能尚未开发）", "yellow")
            cprint("提示", "将继续安装 DCC 插件 + 共享核心，但跳过平台 bridge 文件", "yellow")

    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    if args.uninstall:
        print("  ║       ArtClaw Bridge — 卸载器                        ║")
    else:
        print("  ║       ArtClaw Bridge — 安装器 v1.2                    ║")
    print("  ║       UE / Maya / 3ds Max                             ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    cprint("信息", f"项目目录: {ROOT_DIR}")
    if not args.uninstall:
        cprint("信息", f"目标平台: {pt}")

    installed = []
    uninstalled = []

    if args.uninstall:
        # ─── 卸载模式 ───
        if args.ue:
            if uninstall_ue(args.ue_project):
                uninstalled.append("UE 插件")
        if args.maya:
            if uninstall_maya(args.maya_version):
                uninstalled.append(f"Maya {args.maya_version} 插件")
        if args.max:
            if uninstall_max(args.max_version):
                uninstalled.append(f"3ds Max {args.max_version} 插件")
        if args.openclaw:
            cprint("提示", "平台配置需手动修改（参考 ~/.artclaw/config.json）", "yellow")
    else:
        # ─── 安装模式 ───
        if args.ue:
            if install_ue(args.ue_project, args.force, pt):
                installed.append("UE 插件")
        if args.maya:
            if install_maya(args.maya_version, args.force, pt):
                installed.append(f"Maya {args.maya_version} 插件")
        if args.max:
            if install_max(args.max_version, args.force, pt):
                installed.append(f"3ds Max {args.max_version} 插件")
        if args.openclaw:
            if install_openclaw(pt):
                installed.append(f"平台配置 ({pt})")

    print_summary(installed, uninstalled)

    # 安装模式结束后自动运行同步校验
    if not args.uninstall and installed:
        print()
        cprint("信息", "运行共享模块同步校验...", "cyan")
        try:
            import verify_sync
            rc = verify_sync.main.__wrapped__() if hasattr(verify_sync.main, '__wrapped__') else _run_verify_sync()
        except Exception:
            _run_verify_sync()


def _run_verify_sync():
    """通过子进程运行 verify_sync.py"""
    import subprocess
    verify_script = ROOT_DIR / "verify_sync.py"
    if verify_script.exists():
        result = subprocess.run(
            [sys.executable, str(verify_script)],
            cwd=str(ROOT_DIR),
        )
        return result.returncode
    else:
        cprint("警告", "verify_sync.py 不存在，跳过同步校验", "yellow")
        return 0


if __name__ == "__main__":
    main()
