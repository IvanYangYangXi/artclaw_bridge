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
    _is_junction_or_symlink,
    _remove_link_or_dir,
    confirm_overwrite,
    copy_dir,
    copy_platform_bridge,
    copy_shared_modules,
    cprint,
    inject_startup,
    install_dcc_skills,
    link_or_copy_dir,
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

    # 链接/复制插件
    cprint("部署", "UEClawBridge 插件...")
    method = link_or_copy_dir(str(UE_PLUGIN_SRC), plugin_dst)
    cprint("OK", f"插件已安装到: {plugin_dst} ({method})", "green")

    # 共享模块 & 平台 bridge: 仅复制模式需要打包（link 模式下源码树已自包含）
    python_dst = os.path.join(plugin_dst, "Content", "Python")
    if method == "copy":
        cprint("复制", "bridge_core 共享模块...")
        copy_shared_modules(python_dst)
        cprint("OK", f"共享模块已打包到: {python_dst}", "green")

        cprint("复制", f"平台 bridge ({platform_type})...")
        copy_platform_bridge(platform_type, python_dst)
    else:
        cprint("跳过", "共享模块打包 (link 模式，源码树已自包含)", "cyan")

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
    if os.path.isdir(plugin_dst) or _is_junction_or_symlink(plugin_dst):
        link_type = "链接" if _is_junction_or_symlink(plugin_dst) else "目录"
        _remove_link_or_dir(plugin_dst)
        cprint("删除", f"已删除 ({link_type}): {plugin_dst}", "green")
    else:
        cprint("跳过", f"UE 插件不存在: {plugin_dst}", "yellow")

    return True


_UE_REQUIRED_PACKAGES = ["websockets", "pydantic"]


def _install_ue_python_deps():
    """查找 UE Python 并安装/验证依赖（websockets, pydantic）"""
    ue_python = _find_ue_python()
    if not ue_python:
        cprint("提示", f"未找到 UE Python，请手动安装: pip install {' '.join(_UE_REQUIRED_PACKAGES)}", "yellow")
        return

    # 逐个检查，只安装缺失的
    missing = []
    for pkg in _UE_REQUIRED_PACKAGES:
        try:
            r = subprocess.run(
                [ue_python, "-c", f"import {pkg}"],
                capture_output=True, timeout=10,
            )
            if r.returncode == 0:
                cprint("OK", f"{pkg} 已安装", "green")
            else:
                missing.append(pkg)
        except Exception:
            missing.append(pkg)

    if not missing:
        cprint("OK", "所有 Python 依赖已就绪", "green")
        return

    cprint("安装", f"缺失依赖: {', '.join(missing)}")

    # 先确保 pip 可用
    try:
        r = subprocess.run(
            [ue_python, "-m", "pip", "--version"],
            capture_output=True, timeout=10,
        )
        if r.returncode != 0:
            # 尝试 ensurepip
            cprint("安装", "pip 不可用，尝试 ensurepip...")
            subprocess.run(
                [ue_python, "-m", "ensurepip", "--default-pip"],
                capture_output=True, timeout=60,
            )
    except Exception:
        pass

    try:
        r = subprocess.run(
            [ue_python, "-m", "pip", "install", "--quiet"] + missing,
            capture_output=True, timeout=120, text=True,
        )
        if r.returncode == 0:
            cprint("OK", f"依赖已安装: {', '.join(missing)}", "green")
        else:
            cprint("警告", f"pip install 失败 (exit {r.returncode}): {r.stderr[:200]}", "yellow")
            cprint("提示", f"请手动运行: \"{ue_python}\" -m pip install {' '.join(missing)}", "yellow")
    except Exception as e:
        cprint("警告", f"依赖安装异常: {e}", "yellow")
        cprint("提示", f"请手动运行: \"{ue_python}\" -m pip install {' '.join(missing)}", "yellow")


def _find_ue_python() -> str | None:
    """查找 UE 内置 Python（注册表 > 常见路径 > 环境变量）"""
    if platform.system() != "Windows":
        return None

    # 1) 注册表查找 (最可靠)
    try:
        import winreg
        for ver in ["5.7", "5.6", "5.5", "5.4"]:
            for root_key in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                try:
                    key = winreg.OpenKey(root_key, rf"SOFTWARE\EpicGames\Unreal Engine\{ver}")
                    install_dir, _ = winreg.QueryValueEx(key, "InstalledDirectory")
                    winreg.CloseKey(key)
                    p = os.path.join(install_dir, "Engine", "Binaries",
                                     "ThirdParty", "Python3", "Win64", "python.exe")
                    if os.path.isfile(p):
                        cprint("OK", f"找到 UE {ver} Python (注册表): {p}", "cyan")
                        return p
                except (OSError, FileNotFoundError):
                    pass
    except ImportError:
        pass

    # 2) 常见安装路径扫描
    search_bases = [
        "C:\\Epic Games",
        "C:\\Program Files\\Epic Games",
        "D:\\Epic Games",
        "E:\\Epic Games",
        "D:\\Program Files\\Epic Games",
    ]
    for ver in ["5.7", "5.6", "5.5", "5.4", "5.3"]:
        for base in search_bases:
            p = os.path.join(base, f"UE_{ver}", "Engine", "Binaries",
                             "ThirdParty", "Python3", "Win64", "python.exe")
            if os.path.isfile(p):
                cprint("OK", f"找到 UE {ver} Python: {p}", "cyan")
                return p

    # 3) 环境变量 UE_ROOT
    ue_root = os.environ.get("UE_ROOT", "")
    if ue_root:
        p = os.path.join(ue_root, "Engine", "Binaries",
                         "ThirdParty", "Python3", "Win64", "python.exe")
        if os.path.isfile(p):
            cprint("OK", f"找到 UE Python (UE_ROOT): {p}", "cyan")
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

    # 部署 DCCClawBridge
    cprint("部署", "DCCClawBridge...")
    method = link_or_copy_dir(str(DCC_BRIDGE_SRC), dcc_dst)
    cprint("OK", f"DCCClawBridge 已安装到: {dcc_dst} ({method})", "green")

    # 共享模块 & 平台 bridge: 仅复制模式需要打包
    if method == "copy":
        cprint("复制", "bridge_core 共享模块到 core/...")
        copy_shared_modules(os.path.join(dcc_dst, "core"))
        cprint("OK", "共享模块已打包 (自包含部署)", "green")

        cprint("复制", f"平台 bridge ({platform_type}) 到 core/...")
        copy_platform_bridge(platform_type, os.path.join(dcc_dst, "core"))
    else:
        cprint("跳过", "共享模块打包 (link 模式，源码树已自包含)", "cyan")

    # 注入 userSetup.py（幂等追加）
    user_setup_src = str(DCC_BRIDGE_SRC / "maya_setup" / "userSetup.py")
    user_setup_dst = os.path.join(scripts_dir, "userSetup.py")
    inject_startup(user_setup_dst, user_setup_src, "userSetup.py")

    # 自动同步 locale 副本（zh_CN 等中文版 Maya）
    _sync_maya_locales(maya_base, scripts_dir, method)

    # 安装 DCC Skills
    install_dcc_skills(["maya", "universal"], platform_type)

    cprint("完成", "Maya 插件安装成功!", "green")
    return True


def _sync_maya_locales(maya_base: str, scripts_dir: str, primary_method: str = "copy"):
    """将 scripts/ 下的 DCCClawBridge + userSetup.py 同步到所有 locale 子目录。

    Maya 中文版在 <version>/zh_CN/scripts/ 下查找脚本，
    日文版在 ja_JP/scripts/，需要全部同步。

    link 模式下用 junction 指向主安装目录的 DCCClawBridge。
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
        if os.path.isdir(src_dcc) or _is_junction_or_symlink(src_dcc):
            method = link_or_copy_dir(src_dcc, dst_dcc)
            cprint("OK", f"DCCClawBridge → {name}/scripts/DCCClawBridge ({method})", "green")

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

    if os.path.isdir(dcc_dst) or _is_junction_or_symlink(dcc_dst):
        _remove_link_or_dir(dcc_dst)
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


def _find_max_scripts_dirs(max_version: str) -> list[str]:
    """查找 3ds Max 所有可能的 scripts 目录。

    Max 的用户配置目录有两种格式：
    - 旧版: %LOCALAPPDATA%/Autodesk/3dsMax/{version}/ENU/scripts/
    - 新版: %LOCALAPPDATA%/Autodesk/3dsMax/{version} - 64bit/{locale}/scripts/
      其中 {locale} 可以是 ENU(英文), CHS(中文), JPN(日文) 等

    返回所有存在的 scripts 目录路径列表（不含 startup/ 子目录）。
    第一个元素始终是主安装目录（用于 force 确认提示）。
    """
    local_app = os.environ.get("LOCALAPPDATA", "")
    max_base = os.path.join(local_app, "Autodesk", "3dsMax")
    dirs: list[str] = []

    # 格式 1: {version}/ENU/scripts/
    enu_dir = os.path.join(max_base, max_version, "ENU", "scripts")
    dirs.append(enu_dir)  # 主安装目录始终在第一位

    # 格式 2: {version} - 64bit/{locale}/scripts/
    bit64_dir = os.path.join(max_base, f"{max_version} - 64bit")
    if os.path.isdir(bit64_dir):
        for entry in os.scandir(bit64_dir):
            if not entry.is_dir():
                continue
            locale_scripts = os.path.join(entry.path, "scripts")
            # 如果该 locale 目录下有配置文件(3dsMax.ini)，说明是活跃的
            has_ini = os.path.exists(os.path.join(entry.path, "3dsMax.ini"))
            has_scripts = os.path.isdir(locale_scripts)
            if has_ini or has_scripts:
                if locale_scripts not in dirs:
                    dirs.append(locale_scripts)

    return dirs


def install_max(max_version: str, force: bool, platform_type: str = "openclaw"):
    """安装 3ds Max 插件（自动同步到所有 locale 目录）"""
    print()
    print("  ── 3ds Max 插件安装 ────────────────────────────────")
    print()

    if platform.system() != "Windows":
        cprint("错误", "3ds Max 仅支持 Windows", "red")
        return False

    all_scripts_dirs = _find_max_scripts_dirs(max_version)
    # 主安装目录
    scripts_dir = all_scripts_dirs[0]
    startup_dir = os.path.join(scripts_dir, "startup")
    dcc_dst = os.path.join(scripts_dir, "DCCClawBridge")

    cprint("信息", f"3ds Max 版本: {max_version}")
    cprint("信息", f"平台: {platform_type}")
    cprint("信息", f"主目录: {dcc_dst}")
    if len(all_scripts_dirs) > 1:
        cprint("信息", f"检测到 {len(all_scripts_dirs) - 1} 个额外 locale 目录，将自动同步")

    if not confirm_overwrite(dcc_dst, force):
        cprint("跳过", "Max 插件安装", "yellow")
        return True

    os.makedirs(scripts_dir, exist_ok=True)
    os.makedirs(startup_dir, exist_ok=True)

    # 部署 DCCClawBridge
    cprint("部署", "DCCClawBridge...")
    method = link_or_copy_dir(str(DCC_BRIDGE_SRC), dcc_dst)
    cprint("OK", f"DCCClawBridge 已安装到: {dcc_dst} ({method})", "green")

    # 共享模块 & 平台 bridge: 仅复制模式需要打包
    if method == "copy":
        cprint("复制", "bridge_core 共享模块到 core/...")
        copy_shared_modules(os.path.join(dcc_dst, "core"))
        cprint("OK", "共享模块已打包 (自包含部署)", "green")

        cprint("复制", f"平台 bridge ({platform_type}) 到 core/...")
        copy_platform_bridge(platform_type, os.path.join(dcc_dst, "core"))
    else:
        cprint("跳过", "共享模块打包 (link 模式，源码树已自包含)", "cyan")

    # 注入 startup.py（Python 启动脚本）
    startup_src = str(DCC_BRIDGE_SRC / "max_setup" / "startup.py")
    startup_dst = os.path.join(startup_dir, "artclaw_startup.py")
    inject_startup(startup_dst, startup_src, "artclaw_startup.py")

    # 部署 MaxScript 启动脚本（Max 只自动执行 .ms 文件）
    ms_src = DCC_BRIDGE_SRC / "max_setup" / "artclaw_startup.ms"
    ms_dst = os.path.join(startup_dir, "artclaw_startup.ms")
    if ms_src.exists():
        shutil.copy2(str(ms_src), ms_dst)
        cprint("OK", "MaxScript 启动脚本已安装: artclaw_startup.ms", "green")
    else:
        cprint("警告", f"MaxScript 启动脚本不存在: {ms_src}", "yellow")

    # 同步到所有 locale 目录（CHS/JPN 等）
    _sync_max_locales(all_scripts_dirs, scripts_dir)

    # 安装 DCC Skills
    install_dcc_skills(["max", "universal"], platform_type)

    cprint("完成", "3ds Max 插件安装成功!", "green")
    return True


def _sync_max_locales(all_scripts_dirs: list[str], primary_dir: str):
    """将主安装目录的 DCCClawBridge + artclaw_startup.py 同步到所有 locale 目录。

    3ds Max 中文版在 {version} - 64bit/CHS/scripts/ 下查找启动脚本，
    英文版在 ENU/scripts/，需要全部同步。

    link 模式下用 junction 指向主安装目录的 DCCClawBridge。
    """
    for scripts_dir in all_scripts_dirs:
        if scripts_dir == primary_dir:
            continue

        locale_name = os.path.basename(os.path.dirname(scripts_dir))
        cprint("同步", f"Max locale: {locale_name}")

        os.makedirs(scripts_dir, exist_ok=True)
        startup_dir = os.path.join(scripts_dir, "startup")
        os.makedirs(startup_dir, exist_ok=True)

        # 同步 DCCClawBridge
        src_dcc = os.path.join(primary_dir, "DCCClawBridge")
        dst_dcc = os.path.join(scripts_dir, "DCCClawBridge")
        if os.path.isdir(src_dcc) or _is_junction_or_symlink(src_dcc):
            method = link_or_copy_dir(src_dcc, dst_dcc)
            cprint("OK", f"DCCClawBridge → {locale_name}/scripts/DCCClawBridge ({method})", "green")

        # 同步 artclaw_startup.py
        src_startup = os.path.join(primary_dir, "startup", "artclaw_startup.py")
        dst_startup = os.path.join(startup_dir, "artclaw_startup.py")
        if os.path.isfile(src_startup):
            shutil.copy2(src_startup, dst_startup)
            cprint("OK", f"artclaw_startup.py → {locale_name}/scripts/startup/", "green")

        # 同步 artclaw_startup.ms（MaxScript 启动脚本）
        src_ms = os.path.join(primary_dir, "startup", "artclaw_startup.ms")
        dst_ms = os.path.join(startup_dir, "artclaw_startup.ms")
        if os.path.isfile(src_ms):
            shutil.copy2(src_ms, dst_ms)
            cprint("OK", f"artclaw_startup.ms → {locale_name}/scripts/startup/", "green")


def uninstall_max(max_version: str):
    """卸载 3ds Max 插件（清理所有 locale 目录）"""
    print()
    print("  ── 3ds Max 插件卸载 ────────────────────────────────")
    print()

    all_scripts_dirs = _find_max_scripts_dirs(max_version)

    for scripts_dir in all_scripts_dirs:
        dcc_dst = os.path.join(scripts_dir, "DCCClawBridge")
        startup_file = os.path.join(scripts_dir, "startup", "artclaw_startup.py")
        ms_file = os.path.join(scripts_dir, "startup", "artclaw_startup.ms")

        if os.path.isdir(dcc_dst) or _is_junction_or_symlink(dcc_dst):
            _remove_link_or_dir(dcc_dst)
            cprint("删除", f"已删除: {dcc_dst}", "green")

        if os.path.isfile(startup_file):
            remove_startup_injection(startup_file, "artclaw_startup.py")
            cprint("删除", f"已清理: {startup_file}", "green")

        if os.path.isfile(ms_file):
            os.remove(ms_file)
            cprint("删除", f"已删除: {ms_file}", "green")

    cprint("完成", "3ds Max 插件卸载完成", "green")
    return True
