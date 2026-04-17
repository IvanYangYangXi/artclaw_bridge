#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtClaw Bridge — 安装工具函数
==============================

供 install_dcc.py / install_platform.py / install.py 共用的常量与工具函数。
"""

from __future__ import annotations

import os
import re
import shutil
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

# 需要打包到每个目标的共享模块（与 install.bat 保持一致）
SHARED_MODULES = [
    "bridge_core.py",
    "bridge_config.py",
    "bridge_diagnostics.py",
    "memory_core.py",
    "integrity_check.py",
    "health_check.py",
    "skill_sync.py",
    "retry_tracker.py",
    "skill_decorator.py",
    "version_manager.py",
]

# 共享子目录（interfaces/, schemas/ 等）
SHARED_SUBDIRS = [
    "interfaces",
    "schemas",
]

# userSetup / startup 注入标记
INJECT_START = "# ===== ArtClaw Bridge START ====="
INJECT_END = "# ===== ArtClaw Bridge END ====="


# ---------------------------------------------------------------------------
# 路径工具
# ---------------------------------------------------------------------------

def get_platform_src(platform_type: str) -> Path:
    """获取平台源码目录"""
    return PLATFORMS_DIR / platform_type


def get_gateway_src(platform_type: str) -> Path:
    """获取平台 Gateway 插件源码目录"""
    return get_platform_src(platform_type) / "gateway"


# ---------------------------------------------------------------------------
# 输出 / 交互
# ---------------------------------------------------------------------------

def cprint(tag: str, msg: str, color: str = ""):
    """带标签的彩色输出"""
    colors = {
        "green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m",
        "cyan": "\033[96m", "reset": "\033[0m",
    }
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


# ---------------------------------------------------------------------------
# 文件 / 目录操作
# ---------------------------------------------------------------------------

def copy_dir(src: str, dst: str):
    """复制目录（镜像模式：先删后复制）"""
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


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


def copy_shared_modules(dst_dir: str):
    """将 bridge_core 等共享模块复制到目标目录（含 interfaces/ schemas/ 子目录）"""
    os.makedirs(dst_dir, exist_ok=True)
    for mod in SHARED_MODULES:
        src = BRIDGE_MODULES_SRC / mod
        if src.exists():
            shutil.copy2(str(src), os.path.join(dst_dir, mod))
        else:
            cprint("警告", f"共享模块不存在: {src}", "yellow")

    # 共享子目录
    for subdir in SHARED_SUBDIRS:
        src_sub = BRIDGE_MODULES_SRC / subdir
        dst_sub = os.path.join(dst_dir, subdir)
        if src_sub.is_dir():
            copy_dir(str(src_sub), dst_sub)
        # 子目录不存在是可接受的（某些构建环境可能没有）


def copy_platform_bridge(platform_type: str, dst_dir: str):
    """将平台特定 bridge 文件复制到目标目录（openclaw 额外复制 chat/diagnose 模块）"""
    # 延迟导入避免循环依赖
    from install_platform import PLATFORM_CONFIGS

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


# ---------------------------------------------------------------------------
# startup 文件注入 / 移除（幂等）
# ---------------------------------------------------------------------------

def _get_artclaw_startup_block(source_file: str) -> str:
    """读取源 startup 文件并包裹在标记块中"""
    content = read_file(source_file)
    if not content:
        return ""
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
        write_file(target_file, block)
        cprint("创建", f"{label} → {target_file}", "green")
        return "created"

    if _has_artclaw_block(existing):
        updated = _remove_artclaw_block(existing)
        if updated:
            updated = updated.rstrip("\n") + "\n\n" + block
        else:
            updated = block
        write_file(target_file, updated)
        cprint("更新", f"{label} 已更新 (替换旧标记块)", "green")
        return "updated"

    if _has_artclaw_code(existing):
        cprint("跳过", f"{label} 已包含 ArtClaw 代码 (非标记块)，请手动检查", "yellow")
        return "skipped"

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
        os.remove(target_file)
        cprint("删除", f"{label} 已删除 (文件仅含 ArtClaw 代码)", "green")
    return True


# ---------------------------------------------------------------------------
# DCC Skills 安装
# ---------------------------------------------------------------------------

def _get_skills_installed_path(platform_type: str = "openclaw") -> str:
    """获取 Skills 安装目标路径"""
    import json

    # 优先从 ~/.artclaw/config.json 读取
    config_path = os.path.join(os.path.expanduser("~"), ".artclaw", "config.json")
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            custom_path = config.get("skills", {}).get("installed_path")
            if custom_path:
                return os.path.expanduser(custom_path)
        except Exception:
            pass

    # 平台默认路径
    if platform_type == "openclaw":
        return os.path.join(os.path.expanduser("~"), ".openclaw", "skills")

    # 延迟导入避免循环依赖
    try:
        from install_platform import PLATFORM_CONFIGS
        pcfg = PLATFORM_CONFIGS.get(platform_type, {})
        skills_path = pcfg.get("skills_path")
        if skills_path:
            return os.path.expanduser(skills_path)
    except Exception:
        pass

    # 最终 fallback
    return os.path.join(os.path.expanduser("~"), ".openclaw", "skills")


def install_dcc_skills(dcc_categories: list, platform_type: str = "openclaw") -> int:
    """
    安装指定 DCC 类别的官方 Skills。

    Args:
        dcc_categories: 技能类别列表，如 ["blender", "universal"]
        platform_type: 平台类型，影响安装路径

    Returns:
        安装的 Skill 数量
    """
    skills_installed_path = _get_skills_installed_path(platform_type)
    os.makedirs(skills_installed_path, exist_ok=True)

    skill_count = 0
    for category in dcc_categories:
        category_dir = SKILLS_SRC / "official" / category
        if not category_dir.exists():
            continue
        for skill_dir in category_dir.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            if not (skill_dir / "SKILL.md").exists():
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
        cprint("OK", f"{skill_count} 个 DCC Skills 已安装到: {skills_installed_path}", "green")
    return skill_count
