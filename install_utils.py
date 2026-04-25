#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtClaw Bridge — 安装工具函数
==============================

供 install_dcc.py / install_platform.py / install.py 共用的常量与工具函数。

安装策略 v2.1: 精细化引用 — 不对整个源码目录做 junction，而是按子目录/文件
选择性 junction/symlink，排除 __pycache__/ Lib/ tests/ .md 等动态或非必要文件。
失败时自动 fallback 到复制。通过 --copy 强制复制模式。
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
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
    "device_auth.py",
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
# 安装模式: link (默认) vs copy
# ---------------------------------------------------------------------------

# 全局标志，由 install.py 的 --copy 参数设置
USE_COPY_MODE = False


def set_copy_mode(enabled: bool):
    """设置全局安装模式: True=复制, False=link(默认)"""
    global USE_COPY_MODE
    USE_COPY_MODE = enabled


# ---------------------------------------------------------------------------
# 文件 / 目录操作
# ---------------------------------------------------------------------------

def _is_junction_or_symlink(path: str) -> bool:
    """检查路径是否为 junction 或 symlink"""
    p = Path(path)
    if p.is_symlink():
        return True
    # Windows junction: not a symlink but is a reparse point
    if platform.system() == "Windows" and p.exists():
        try:
            import ctypes
            FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(p))
            if attrs != -1 and (attrs & FILE_ATTRIBUTE_REPARSE_POINT):
                return True
        except Exception:
            pass
    return False


def _remove_link_or_dir(path: str):
    """安全移除 junction/symlink 或普通目录"""
    if _is_junction_or_symlink(path):
        # junction/symlink: 只移除链接本身，不删除目标内容
        if platform.system() == "Windows":
            # os.rmdir 可以安全移除 junction (不删内容)
            # os.remove 可以安全移除 file symlink
            p = Path(path)
            if p.is_dir():
                os.rmdir(path)
            else:
                os.remove(path)
        else:
            os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


def _try_junction(src: str, dst: str) -> bool:
    """尝试创建 Windows junction (目录)。不需要管理员权限。"""
    if platform.system() != "Windows":
        return False
    try:
        # mklink /J 不需要管理员权限
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", dst, src],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0 and os.path.isdir(dst)
    except Exception:
        return False


def _try_symlink_dir(src: str, dst: str) -> bool:
    """尝试创建目录 symlink (需要开发者模式或管理员权限)"""
    try:
        os.symlink(src, dst, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        return False


def _try_symlink_file(src: str, dst: str) -> bool:
    """尝试创建文件 symlink"""
    try:
        os.symlink(src, dst)
        return True
    except (OSError, NotImplementedError):
        return False


def link_or_copy_dir(src: str, dst: str) -> str:
    """创建目录引用（优先 junction/symlink，fallback 复制）。

    返回: "junction" | "symlink" | "copy" 表示实际采用的方式
    """
    src = os.path.abspath(src)
    dst = os.path.abspath(dst)

    # 先清理已有目标
    if os.path.exists(dst) or _is_junction_or_symlink(dst):
        _remove_link_or_dir(dst)

    # 确保父目录存在
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    if USE_COPY_MODE:
        shutil.copytree(src, dst)
        return "copy"

    # 优先 junction (Windows, 无权限要求)
    if _try_junction(src, dst):
        return "junction"

    # 其次 symlink
    if _try_symlink_dir(src, dst):
        return "symlink"

    # fallback: 复制
    cprint("回退", f"无法创建链接，使用复制: {dst}", "yellow")
    shutil.copytree(src, dst)
    return "copy"


def link_or_copy_file(src: str, dst: str) -> str:
    """创建文件引用（优先 symlink，fallback 复制）。

    返回: "symlink" | "hardlink" | "copy" 表示实际采用的方式
    """
    src = os.path.abspath(src)
    dst = os.path.abspath(dst)

    if os.path.exists(dst) or _is_junction_or_symlink(dst):
        _remove_link_or_dir(dst)

    os.makedirs(os.path.dirname(dst), exist_ok=True)

    if USE_COPY_MODE:
        shutil.copy2(src, dst)
        return "copy"

    # 优先 symlink
    if _try_symlink_file(src, dst):
        return "symlink"

    # 其次 hardlink (同一文件系统)
    try:
        os.link(src, dst)
        return "hardlink"
    except (OSError, NotImplementedError):
        pass

    # fallback: 复制
    shutil.copy2(src, dst)
    return "copy"


def copy_dir(src: str, dst: str):
    """复制目录（镜像模式：先删后复制）— 保留向后兼容"""
    if os.path.exists(dst) or _is_junction_or_symlink(dst):
        _remove_link_or_dir(dst)
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


# ---------------------------------------------------------------------------
# 精细化安装: 按子目录/文件选择性引用
# ---------------------------------------------------------------------------

# DCCClawBridge 共享子目录 (所有 DCC 都需要)
_DCC_SHARED_DIRS = [
    "adapters",
    "artclaw_ui",
    "core",
    "skills",
]

# 各 DCC 特有的顶层文件/目录
_DCC_SPECIFIC_FILES: dict[str, list[str]] = {
    "maya":    ["maya_setup"],
    "max":     ["max_setup"],
    "blender": ["blender_addon.py", "blender_qt_bridge.py"],
    "houdini": ["houdini_shelf.py"],
    "sp":      ["sp_plugin.py"],
    "sd":      ["sd_plugin.py"],
    "comfyui": [],  # ComfyUI 用 ComfyUIClawBridge，DCCClawBridge 只做依赖库
}


def link_dcc_bridge_selective(
    dcc_type: str,
    dst: str,
    *,
    extra_files: list[str] | None = None,
) -> str:
    """按子目录/文件选择性引用 DCCClawBridge 到目标位置。

    不做整目录 junction，而是:
    1. 创建目标空目录
    2. 对共享子目录 (adapters/artclaw_ui/core/skills) 逐个 junction
    3. 对该 DCC 特有的顶层文件/目录逐个 symlink/junction
    4. 排除 __pycache__/ Lib/ tests/ .md requirements.txt 等

    Args:
        dcc_type: DCC 类型标识 ("maya"|"max"|"blender"|"houdini"|"sp"|"sd"|"comfyui")
        dst: 目标安装路径 (会被创建或清空后重建)
        extra_files: 额外需要引用的文件/目录名 (可选)

    Returns:
        "selective-link" | "selective-copy" 表示实际采用的方式
    """
    src_base = str(DCC_BRIDGE_SRC)
    dst = os.path.abspath(dst)

    # 先清理已有目标 (可能是旧的整目录 junction)
    if os.path.exists(dst) or _is_junction_or_symlink(dst):
        _remove_link_or_dir(dst)

    # 创建空的目标目录
    os.makedirs(dst, exist_ok=True)

    used_methods = set()

    # 1) 共享子目录
    for subdir in _DCC_SHARED_DIRS:
        src_path = os.path.join(src_base, subdir)
        dst_path = os.path.join(dst, subdir)
        if os.path.isdir(src_path):
            method = link_or_copy_dir(src_path, dst_path)
            used_methods.add(method)
            if method != "copy":
                cprint("链接", f"{subdir}/ ({method})", "cyan")
        else:
            cprint("警告", f"共享子目录不存在: {src_path}", "yellow")

    # 2) DCC 特有的文件/目录
    specific = list(_DCC_SPECIFIC_FILES.get(dcc_type, []))
    if extra_files:
        specific.extend(extra_files)

    for name in specific:
        src_path = os.path.join(src_base, name)
        dst_path = os.path.join(dst, name)
        if os.path.isdir(src_path):
            method = link_or_copy_dir(src_path, dst_path)
            used_methods.add(method)
            if method != "copy":
                cprint("链接", f"{name}/ ({method})", "cyan")
        elif os.path.isfile(src_path):
            method = link_or_copy_file(src_path, dst_path)
            used_methods.add(method)
            if method != "copy":
                cprint("链接", f"{name} ({method})", "cyan")
        else:
            cprint("警告", f"DCC 特有文件不存在: {src_path}", "yellow")

    # 返回主要采用的方式
    if USE_COPY_MODE or used_methods == {"copy"}:
        return "selective-copy"
    return "selective-link"


def link_ue_plugin_selective(dst: str) -> str:
    """按子目录选择性引用 UEClawBridge 到目标位置。

    排除 Binaries/ Intermediate/ Saved/ (编译/运行时产物)，
    对 Content/ Resources/ Source/ 逐个 junction，.uplugin 文件 symlink。

    Args:
        dst: 目标安装路径

    Returns:
        "selective-link" | "selective-copy"
    """
    src_base = str(UE_PLUGIN_SRC)
    dst = os.path.abspath(dst)

    if os.path.exists(dst) or _is_junction_or_symlink(dst):
        _remove_link_or_dir(dst)

    os.makedirs(dst, exist_ok=True)

    used_methods = set()

    # 需要引用的子目录
    for subdir in ["Content", "Resources", "Source"]:
        src_path = os.path.join(src_base, subdir)
        dst_path = os.path.join(dst, subdir)
        if os.path.isdir(src_path):
            method = link_or_copy_dir(src_path, dst_path)
            used_methods.add(method)
            if method != "copy":
                cprint("链接", f"{subdir}/ ({method})", "cyan")
        else:
            cprint("警告", f"UE 子目录不存在: {src_path}", "yellow")

    # .uplugin 文件
    for name in os.listdir(src_base):
        if name.endswith(".uplugin"):
            src_path = os.path.join(src_base, name)
            dst_path = os.path.join(dst, name)
            method = link_or_copy_file(src_path, dst_path)
            used_methods.add(method)
            if method != "copy":
                cprint("链接", f"{name} ({method})", "cyan")

    if USE_COPY_MODE or used_methods == {"copy"}:
        return "selective-copy"
    return "selective-link"


def link_comfyui_bridge_selective(dst: str) -> str:
    """按文件选择性引用 ComfyUIClawBridge 到目标位置。

    只引用 git tracked 文件 (__init__.py, startup.py, install.py)，
    排除 __pycache__/ 和动态生成的 .env。

    Args:
        dst: 目标安装路径

    Returns:
        "selective-link" | "selective-copy"
    """
    comfyui_src = ROOT_DIR / "subprojects" / "ComfyUIClawBridge"
    src_base = str(comfyui_src)
    dst = os.path.abspath(dst)

    if os.path.exists(dst) or _is_junction_or_symlink(dst):
        _remove_link_or_dir(dst)

    os.makedirs(dst, exist_ok=True)

    used_methods = set()
    tracked_files = ["__init__.py", "startup.py", "install.py"]

    for name in tracked_files:
        src_path = os.path.join(src_base, name)
        dst_path = os.path.join(dst, name)
        if os.path.isfile(src_path):
            method = link_or_copy_file(src_path, dst_path)
            used_methods.add(method)
            if method != "copy":
                cprint("链接", f"{name} ({method})", "cyan")
        else:
            cprint("警告", f"ComfyUI 文件不存在: {src_path}", "yellow")

    if USE_COPY_MODE or used_methods == {"copy"}:
        return "selective-copy"
    return "selective-link"


# ---------------------------------------------------------------------------
# 共享模块安装
# ---------------------------------------------------------------------------

def copy_shared_modules(dst_dir: str):
    """将 bridge_core 等共享模块链接/复制到目标目录（含 interfaces/ schemas/ 子目录）"""
    os.makedirs(dst_dir, exist_ok=True)
    for mod in SHARED_MODULES:
        src = BRIDGE_MODULES_SRC / mod
        if src.exists():
            method = link_or_copy_file(str(src), os.path.join(dst_dir, mod))
            if method != "copy":
                cprint("链接", f"{mod} ({method})", "cyan")
        else:
            cprint("警告", f"共享模块不存在: {src}", "yellow")

    # 共享子目录
    for subdir in SHARED_SUBDIRS:
        src_sub = BRIDGE_MODULES_SRC / subdir
        dst_sub = os.path.join(dst_dir, subdir)
        if src_sub.is_dir():
            method = link_or_copy_dir(str(src_sub), dst_sub)
            if method != "copy":
                cprint("链接", f"{subdir}/ ({method})", "cyan")
        # 子目录不存在是可接受的（某些构建环境可能没有）


def copy_platform_bridge(platform_type: str, dst_dir: str):
    """将平台特定 bridge 文件链接/复制到目标目录（openclaw 额外复制 chat/diagnose 模块）"""
    # 延迟导入避免循环依赖
    from install_platform import PLATFORM_CONFIGS

    pcfg = PLATFORM_CONFIGS.get(platform_type)
    if not pcfg:
        cprint("警告", f"未知平台: {platform_type}，跳过 bridge 文件复制", "yellow")
        return
    os.makedirs(dst_dir, exist_ok=True)
    platform_src = get_platform_src(platform_type)

    # 主 bridge 文件
    files_to_link = [pcfg["bridge_file"]]
    # openclaw 平台额外携带独立模块
    if platform_type == "openclaw":
        files_to_link += ["openclaw_ws.py", "openclaw_chat.py", "openclaw_diagnose.py"]

    for fname in files_to_link:
        src = platform_src / fname
        if src.exists():
            method = link_or_copy_file(str(src), os.path.join(dst_dir, fname))
            cprint("OK", f"平台 bridge: {fname} ({method})", "green")
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
        return os.path.join(os.path.expanduser("~"), ".openclaw", "workspace", "skills")

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
    return os.path.join(os.path.expanduser("~"), ".openclaw", "workspace", "skills")


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
            # Skill 安装始终用复制（不用 symlink/junction），
            # 因为版本管理需要独立副本，用户可能修改已安装 Skill。
            copy_dir(str(skill_dir), dst)
            cprint("复制", f"Skill: {skill_dir.name}", "cyan")
            skill_count += 1

    if skill_count:
        cprint("OK", f"{skill_count} 个 DCC Skills 已复制到: {skills_installed_path}", "green")
    return skill_count
