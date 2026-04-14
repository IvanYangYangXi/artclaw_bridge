#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtClaw Bridge — DCC 安装/卸载 (UE / Maya / 3ds Max)
=====================================================

已有 DCC 的安装与卸载逻辑（从原 install.py 搬迁，逻辑不变）。
"""

from __future__ import annotations

import glob
import os
import platform
import shutil
import subprocess

from install_utils import (
    DCC_BRIDGE_SRC,
    UE_PLUGIN_SRC,
    confirm_overwrite,
    copy_dir,
    copy_platform_bridge,
    copy_shared_modules,
    cprint,
    inject_startup,
    install_dcc_skills,
    remove_startup_injection,
)

# ===========================================================================
# UE
# ===========================================================================


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

    # 安装 DCC Skills
    install_dcc_skills(["unreal", "universal"], platform_type)

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


# ===========================================================================
# Maya
# ===========================================================================


def install_maya(maya_version: str, force: bool, platform_type: str = "openclaw"):
    """安装 Maya 插件（自动包含 zh_CN 等 locale 副本）"""
    print()
    print("  ── Maya 插件安装 ───────────────────────────────────")
    print()

    maya_base = os.path.join(
        os.path.expanduser("~"), "Documents", "maya", maya_version
    )
    scripts_dir = os.path.join(maya_base, "scripts")
    dcc_dst = os.path.join(scripts_dir, "DCCClawBridge")

    cprint("信息", f"Maya 版本: {maya_version}")
    cprint("信息", f"平台: {platform_type}")
    cprint("信息", f"目标目录: {dcc_dst}")

    if not confirm_overwrite(dcc_dst, force):
        cprint("跳过", "Maya 插件安装", "yellow")
        return True

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

    # 自动同步 locale 副本（zh_CN 等中文版 Maya）
    _sync_maya_locales(maya_base, scripts_dir)

    # 安装 DCC Skills
    install_dcc_skills(["maya", "universal"], platform_type)

    cprint("完成", "Maya 插件安装成功!", "green")
    return True


def _sync_maya_locales(maya_base: str, scripts_dir: str):
    """将 scripts/ 下的 DCCClawBridge + userSetup.py 同步到所有 locale 子目录。

    Maya 中文版在 <version>/zh_CN/scripts/ 下查找脚本，
    日文版在 ja_JP/scripts/，需要全部同步。
    """
    for entry in os.scandir(maya_base):
        if not entry.is_dir():
            continue
        locale_scripts = os.path.join(entry.path, "scripts")
        # 只处理含 scripts/ 子目录的 locale 文件夹（如 zh_CN/scripts/）
        if not os.path.isdir(locale_scripts):
            continue
        # 跳过非 locale 目录（locale 通常是 xx_XX 格式）
        name = entry.name
        if len(name) < 2 or name == "scripts":
            continue

        cprint("同步", f"Maya locale: {name}")

        # 同步 DCCClawBridge
        src_dcc = os.path.join(scripts_dir, "DCCClawBridge")
        dst_dcc = os.path.join(locale_scripts, "DCCClawBridge")
        if os.path.isdir(src_dcc):
            copy_dir(src_dcc, dst_dcc)
            cprint("OK", f"DCCClawBridge → {name}/scripts/DCCClawBridge", "green")

        # 同步 userSetup.py
        src_setup = os.path.join(scripts_dir, "userSetup.py")
        dst_setup = os.path.join(locale_scripts, "userSetup.py")
        if os.path.isfile(src_setup):
            shutil.copy2(src_setup, dst_setup)
            cprint("OK", f"userSetup.py → {name}/scripts/userSetup.py", "green")


def uninstall_maya(maya_version: str):
    """卸载 Maya 插件"""
    print()
    print("  ── Maya 插件卸载 ───────────────────────────────────")
    print()

    scripts_dir = os.path.join(
        os.path.expanduser("~"), "Documents", "maya", maya_version, "scripts"
    )
    dcc_dst = os.path.join(scripts_dir, "DCCClawBridge")

    if os.path.isdir(dcc_dst):
        shutil.rmtree(dcc_dst)
        cprint("删除", f"已删除: {dcc_dst}", "green")
    else:
        cprint("跳过", f"DCCClawBridge 不存在: {dcc_dst}", "yellow")

    user_setup = os.path.join(scripts_dir, "userSetup.py")
    remove_startup_injection(user_setup, "userSetup.py")

    cprint("完成", "Maya 插件卸载完成", "green")
    return True


# ===========================================================================
# 3ds Max
# ===========================================================================


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

    # 安装 DCC Skills
    install_dcc_skills(["max", "universal"], platform_type)

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

    if os.path.isdir(dcc_dst):
        shutil.rmtree(dcc_dst)
        cprint("删除", f"已删除: {dcc_dst}", "green")
    else:
        cprint("跳过", f"DCCClawBridge 不存在: {dcc_dst}", "yellow")

    startup_file = os.path.join(startup_dir, "artclaw_startup.py")
    remove_startup_injection(startup_file, "artclaw_startup.py")

    cprint("完成", "3ds Max 插件卸载完成", "green")
    return True
