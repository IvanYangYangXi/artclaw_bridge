#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtClaw Bridge — DCC 安装/卸载 (Blender / Houdini / Substance Painter / Substance Designer)
============================================================================================

新增 DCC 的安装与卸载逻辑。
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess

from install_utils import (
    DCC_BRIDGE_SRC,
    confirm_overwrite,
    copy_dir,
    copy_platform_bridge,
    copy_shared_modules,
    cprint,
    install_dcc_skills,
    ROOT_DIR,
)

# ===========================================================================
# Blender
# ===========================================================================


def install_blender(blender_version: str, force: bool, platform_type: str = "openclaw"):
    """安装 Blender 插件"""
    print()
    print("  ── Blender 插件安装 ────────────────────────────────")
    print()

    # Windows: %APPDATA%\Blender Foundation\Blender\{version}\scripts\addons\
    appdata = os.environ.get("APPDATA", os.path.expanduser("~/AppData/Roaming"))
    addons_dir = os.path.join(
        appdata, "Blender Foundation", "Blender", blender_version, "scripts", "addons"
    )
    dcc_dst = os.path.join(addons_dir, "artclaw_bridge")

    cprint("信息", f"Blender 版本: {blender_version}")
    cprint("信息", f"平台: {platform_type}")
    cprint("信息", f"目标目录: {dcc_dst}")

    if not confirm_overwrite(dcc_dst, force):
        cprint("跳过", "Blender 插件安装", "yellow")
        return True

    os.makedirs(addons_dir, exist_ok=True)

    # 复制 DCCClawBridge 到 addons 目录
    cprint("复制", "DCCClawBridge → artclaw_bridge...")
    copy_dir(str(DCC_BRIDGE_SRC), dcc_dst)
    cprint("OK", f"DCCClawBridge 已安装到: {dcc_dst}", "green")

    # 创建 __init__.py（Blender addon 包入口，必须存在）
    # bl_info 必须作为字面量定义（Blender AST 扫描，不执行 import）
    init_path = os.path.join(dcc_dst, "__init__.py")
    with open(init_path, "w", encoding="utf-8") as f:
        f.write(
            "# ArtClaw Bridge - Blender Addon\n\n"
            "bl_info = {\n"
            '    "name": "ArtClaw Bridge",\n'
            '    "author": "ArtClaw Team",\n'
            '    "version": (1, 0, 0),\n'
            '    "blender": (3, 0, 0),\n'
            '    "location": "View3D > Sidebar > ArtClaw",\n'
            '    "description": "AI Agent bridge for Blender via ArtClaw",\n'
            '    "category": "Interface",\n'
            "}\n\n\n"
            "def _ensure_path():\n"
            "    import os, sys\n"
            "    addon_dir = os.path.dirname(os.path.abspath(__file__))\n"
            "    if addon_dir not in sys.path:\n"
            "        sys.path.insert(0, addon_dir)\n\n\n"
            "def register():\n"
            "    _ensure_path()\n"
            "    from .blender_addon import register as _register\n"
            "    _register()\n\n\n"
            "def unregister():\n"
            "    from .blender_addon import unregister as _unregister\n"
            "    _unregister()\n"
        )
    cprint("OK", "已创建 __init__.py (Blender addon 入口)", "green")

    # 复制共享模块到 core/
    cprint("复制", "bridge_core 共享模块到 core/...")
    copy_shared_modules(os.path.join(dcc_dst, "core"))
    cprint("OK", "共享模块已打包 (自包含部署)", "green")

    # 复制平台 bridge 到 core/
    cprint("复制", f"平台 bridge ({platform_type}) 到 core/...")
    copy_platform_bridge(platform_type, os.path.join(dcc_dst, "core"))

    # 尝试安装 PySide6 到 Blender Python
    _install_blender_python_deps(blender_version)

    # 安装 DCC Skills
    install_dcc_skills(["blender", "universal"], platform_type)

    cprint("完成", "Blender 插件安装成功!", "green")
    print()
    cprint("后续步骤", "在 Blender 中: Edit → Preferences → Add-ons → 搜索 'ArtClaw' → 启用", "cyan")
    return True


def uninstall_blender(blender_version: str):
    """卸载 Blender 插件"""
    print()
    print("  ── Blender 插件卸载 ────────────────────────────────")
    print()

    appdata = os.environ.get("APPDATA", os.path.expanduser("~/AppData/Roaming"))
    dcc_dst = os.path.join(
        appdata, "Blender Foundation", "Blender", blender_version,
        "scripts", "addons", "artclaw_bridge"
    )

    if os.path.isdir(dcc_dst):
        shutil.rmtree(dcc_dst)
        cprint("删除", f"已删除: {dcc_dst}", "green")
    else:
        cprint("跳过", f"artclaw_bridge 不存在: {dcc_dst}", "yellow")

    cprint("完成", "Blender 插件卸载完成", "green")
    return True


def _install_blender_python_deps(blender_version: str):
    """尝试查找 Blender Python 并安装所有依赖"""
    blender_python = _find_blender_python(blender_version)
    if not blender_python:
        cprint("提示", "未找到 Blender Python，请手动安装依赖", "yellow")
        cprint("提示", "需要: pip install PySide6 websockets pydantic", "yellow")
        return
    deps = ["PySide6", "websockets", "pydantic"]
    try:
        subprocess.run(
            [blender_python, "-m", "pip", "install"] + deps,
            capture_output=True, timeout=180,
        )
        cprint("OK", f"Python 依赖已安装到 Blender Python ({', '.join(deps)})", "green")
    except Exception as e:
        cprint("警告", f"依赖安装失败: {e}", "yellow")
        cprint("提示", f"请手动运行: \"{blender_python}\" -m pip install {' '.join(deps)}", "yellow")


def _find_blender_python(blender_version: str) -> str | None:
    """查找 Blender 内置 Python"""
    if platform.system() != "Windows":
        return None
    for base in [
        "C:\\Program Files\\Blender Foundation",
        "C:\\Program Files (x86)\\Blender Foundation",
    ]:
        p = os.path.join(
            base, f"Blender {blender_version}", blender_version,
            "python", "bin", "python.exe"
        )
        if os.path.isfile(p):
            cprint("OK", f"找到 Blender {blender_version} Python: {p}", "cyan")
            return p
    return None


# ===========================================================================
# Houdini
# ===========================================================================


def install_houdini(houdini_version: str, force: bool, platform_type: str = "openclaw"):
    """安装 Houdini 插件"""
    print()
    print("  ── Houdini 插件安装 ────────────────────────────────")
    print()

    # Windows: %USERPROFILE%\Documents\houdini{version}\scripts\python\
    docs_dir = os.path.join(
        os.path.expanduser("~"), "Documents", f"houdini{houdini_version}"
    )
    scripts_python_dir = os.path.join(docs_dir, "scripts", "python")
    dcc_dst = os.path.join(scripts_python_dir, "DCCClawBridge")

    cprint("信息", f"Houdini 版本: {houdini_version}")
    cprint("信息", f"平台: {platform_type}")
    cprint("信息", f"目标目录: {dcc_dst}")

    if not confirm_overwrite(dcc_dst, force):
        cprint("跳过", "Houdini 插件安装", "yellow")
        return True

    os.makedirs(scripts_python_dir, exist_ok=True)

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

    # 复制 shelf tool 启动脚本
    shelf_src = DCC_BRIDGE_SRC / "houdini_shelf.py"
    if shelf_src.exists():
        shelf_dst = os.path.join(scripts_python_dir, "houdini_shelf.py")
        shutil.copy2(str(shelf_src), shelf_dst)
        cprint("OK", f"Shelf 脚本已复制: {shelf_dst}", "green")
    else:
        cprint("警告", f"Shelf 脚本源不存在: {shelf_src}", "yellow")

    # 尝试安装 Python 依赖到 Houdini Python
    _install_houdini_python_deps(houdini_version)

    # 安装 DCC Skills
    install_dcc_skills(["houdini", "universal"], platform_type)

    cprint("完成", "Houdini 插件安装成功!", "green")
    print()
    cprint("后续步骤", "创建 Shelf Tool → Script:", "cyan")
    cprint("", "  import houdini_shelf; houdini_shelf.toggle_artclaw()", "cyan")
    return True


def uninstall_houdini(houdini_version: str):
    """卸载 Houdini 插件"""
    print()
    print("  ── Houdini 插件卸载 ────────────────────────────────")
    print()

    docs_dir = os.path.join(
        os.path.expanduser("~"), "Documents", f"houdini{houdini_version}"
    )
    scripts_python_dir = os.path.join(docs_dir, "scripts", "python")
    dcc_dst = os.path.join(scripts_python_dir, "DCCClawBridge")

    if os.path.isdir(dcc_dst):
        shutil.rmtree(dcc_dst)
        cprint("删除", f"已删除: {dcc_dst}", "green")
    else:
        cprint("跳过", f"DCCClawBridge 不存在: {dcc_dst}", "yellow")

    # 移除 shelf 脚本
    shelf_file = os.path.join(scripts_python_dir, "houdini_shelf.py")
    if os.path.isfile(shelf_file):
        os.remove(shelf_file)
        cprint("删除", f"已删除: {shelf_file}", "green")

    cprint("完成", "Houdini 插件卸载完成", "green")
    return True


def _install_houdini_python_deps(houdini_version: str):
    """尝试查找 Houdini Python (hython) 并安装所有依赖"""
    hython = _find_houdini_python(houdini_version)
    if not hython:
        cprint("提示", "未找到 Houdini Python，请手动安装依赖", "yellow")
        cprint("提示", "需要: hython -m pip install websockets pydantic", "yellow")
        return
    deps = ["websockets", "pydantic"]
    try:
        subprocess.run(
            [hython, "-m", "pip", "install"] + deps,
            capture_output=True, timeout=180,
        )
        cprint("OK", f"Python 依赖已安装到 Houdini Python ({', '.join(deps)})", "green")
    except Exception as e:
        cprint("警告", f"依赖安装失败: {e}", "yellow")
        cprint("提示", f"请手动运行: \"{hython}\" -m pip install {' '.join(deps)}", "yellow")


def _find_houdini_python(houdini_version: str) -> str | None:
    """查找 Houdini 内置 Python (hython)"""
    if platform.system() != "Windows":
        return None

    # houdini_version 格式为 "20.5" 等
    base_dir = "C:\\Program Files\\Side Effects Software"
    if not os.path.isdir(base_dir):
        return None

    # 搜索匹配 "Houdini {version}*" 的目录
    import glob as _glob
    pattern = os.path.join(base_dir, f"Houdini {houdini_version}*")
    matches = sorted(_glob.glob(pattern), reverse=True)

    for hou_dir in matches:
        hython_path = os.path.join(hou_dir, "bin", "hython.exe")
        if os.path.isfile(hython_path):
            cprint("OK", f"找到 Houdini {houdini_version} Python: {hython_path}", "cyan")
            return hython_path

    return None


# ===========================================================================
# Substance Painter
# ===========================================================================


def install_substance_painter(force: bool, platform_type: str = "openclaw"):
    """安装 Substance Painter 插件"""
    print()
    print("  ── Substance Painter 插件安装 ──────────────────────")
    print()

    # 安装目标: %USERPROFILE%\Documents\Adobe\Adobe Substance 3D Painter\python\plugins\
    plugins_dir = os.path.join(
        os.path.expanduser("~"), "Documents", "Adobe",
        "Adobe Substance 3D Painter", "python", "plugins"
    )
    dcc_dst = os.path.join(plugins_dir, "artclaw_bridge")

    cprint("信息", f"平台: {platform_type}")
    cprint("信息", f"目标目录: {dcc_dst}")

    if not confirm_overwrite(dcc_dst, force):
        cprint("跳过", "Substance Painter 插件安装", "yellow")
        return True

    os.makedirs(plugins_dir, exist_ok=True)

    # 复制 DCCClawBridge
    cprint("复制", "DCCClawBridge → artclaw_bridge...")
    copy_dir(str(DCC_BRIDGE_SRC), dcc_dst)
    cprint("OK", f"DCCClawBridge 已安装到: {dcc_dst}", "green")

    # 复制共享模块到 core/
    cprint("复制", "bridge_core 共享模块到 core/...")
    copy_shared_modules(os.path.join(dcc_dst, "core"))
    cprint("OK", "共享模块已打包 (自包含部署)", "green")

    # 复制平台 bridge 到 core/
    cprint("复制", f"平台 bridge ({platform_type}) 到 core/...")
    copy_platform_bridge(platform_type, os.path.join(dcc_dst, "core"))

    # 创建 __init__.py（SP 包 plugin 入口 — SP 通过此文件发现插件）
    # 注意：SP 启动时自动扫描 plugins/ 并执行 __init__.py，
    # 因此不能在模块顶层 import 任何依赖，只在函数调用时延迟 import。
    init_path = os.path.join(dcc_dst, "__init__.py")
    with open(init_path, "w", encoding="utf-8") as f:
        f.write(
            '"""ArtClaw Bridge - Substance Painter Plugin"""\n\n\n'
            "def _ensure_path():\n"
            "    import os, sys\n"
            "    pkg_dir = os.path.dirname(os.path.abspath(__file__))\n"
            "    if pkg_dir not in sys.path:\n"
            "        sys.path.insert(0, pkg_dir)\n\n\n"
            "def start_plugin():\n"
            "    _ensure_path()\n"
            "    from sp_plugin import start_plugin as _start\n"
            "    _start()\n\n\n"
            "def close_plugin():\n"
            "    try:\n"
            "        from sp_plugin import close_plugin as _close\n"
            "        _close()\n"
            "    except Exception:\n"
            "        pass\n"
        )
    cprint("OK", "已创建 __init__.py (SP plugin 包入口, 延迟加载)", "green")

    # 尝试安装 Python 依赖到 SP Python
    _install_substance_python_deps("Painter")

    # 安装 DCC Skills
    install_dcc_skills(["substance_painter", "universal"], platform_type)

    cprint("完成", "Substance Painter 插件安装成功!", "green")
    print()
    cprint("后续步骤", "启动 Substance Painter → Python → 勾选 artclaw_bridge", "cyan")
    return True


def uninstall_substance_painter():
    """卸载 Substance Painter 插件"""
    print()
    print("  ── Substance Painter 插件卸载 ──────────────────────")
    print()

    plugins_dir = os.path.join(
        os.path.expanduser("~"), "Documents", "Adobe",
        "Adobe Substance 3D Painter", "python", "plugins"
    )
    dcc_dst = os.path.join(plugins_dir, "artclaw_bridge")

    if os.path.isdir(dcc_dst):
        shutil.rmtree(dcc_dst)
        cprint("删除", f"已删除: {dcc_dst}", "green")
    else:
        cprint("跳过", f"artclaw_bridge 不存在: {dcc_dst}", "yellow")

    cprint("完成", "Substance Painter 插件卸载完成", "green")
    return True


# ===========================================================================
# Substance Designer
# ===========================================================================


def install_substance_designer(force: bool, platform_type: str = "openclaw"):
    """安装 Substance Designer 插件"""
    print()
    print("  ── Substance Designer 插件安装 ─────────────────────")
    print()

    # 安装目标: %USERPROFILE%\Documents\Adobe\Adobe Substance 3D Designer\python\sduserplugins\
    plugins_dir = os.path.join(
        os.path.expanduser("~"), "Documents", "Adobe",
        "Adobe Substance 3D Designer", "python", "sduserplugins"
    )
    dcc_dst = os.path.join(plugins_dir, "artclaw_bridge")

    cprint("信息", f"平台: {platform_type}")
    cprint("信息", f"目标目录: {dcc_dst}")

    if not confirm_overwrite(dcc_dst, force):
        cprint("跳过", "Substance Designer 插件安装", "yellow")
        return True

    os.makedirs(plugins_dir, exist_ok=True)

    # 复制 DCCClawBridge
    cprint("复制", "DCCClawBridge → artclaw_bridge...")
    copy_dir(str(DCC_BRIDGE_SRC), dcc_dst)
    cprint("OK", f"DCCClawBridge 已安装到: {dcc_dst}", "green")

    # 复制共享模块到 core/
    cprint("复制", "bridge_core 共享模块到 core/...")
    copy_shared_modules(os.path.join(dcc_dst, "core"))
    cprint("OK", "共享模块已打包 (自包含部署)", "green")

    # 复制平台 bridge 到 core/
    cprint("复制", f"平台 bridge ({platform_type}) 到 core/...")
    copy_platform_bridge(platform_type, os.path.join(dcc_dst, "core"))

    # 创建 __init__.py（SD 包 plugin 入口 — SD 通过此文件发现插件）
    # 同 SP：不在模块顶层 import，延迟到函数调用时加载。
    init_path = os.path.join(dcc_dst, "__init__.py")
    with open(init_path, "w", encoding="utf-8") as f:
        f.write(
            '"""ArtClaw Bridge - Substance Designer Plugin"""\n\n\n'
            "def _ensure_path():\n"
            "    import os, sys\n"
            "    pkg_dir = os.path.dirname(os.path.abspath(__file__))\n"
            "    if pkg_dir not in sys.path:\n"
            "        sys.path.insert(0, pkg_dir)\n\n\n"
            "def initializeSDPlugin():\n"
            "    _ensure_path()\n"
            "    from sd_plugin import initializeSDPlugin as _init\n"
            "    _init()\n\n\n"
            "def uninitializeSDPlugin():\n"
            "    try:\n"
            "        from sd_plugin import uninitializeSDPlugin as _uninit\n"
            "        _uninit()\n"
            "    except Exception:\n"
            "        pass\n"
        )
    cprint("OK", "已创建 __init__.py (SD plugin 包入口, 延迟加载)", "green")

    # 尝试安装 Python 依赖到 SD Python
    _install_substance_python_deps("Designer")

    # 安装 DCC Skills
    install_dcc_skills(["substance_designer", "universal"], platform_type)

    cprint("完成", "Substance Designer 插件安装成功!", "green")
    print()
    cprint("后续步骤", "启动 Substance Designer → plugin 自动加载", "cyan")
    return True


def uninstall_substance_designer():
    """卸载 Substance Designer 插件"""
    print()
    print("  ── Substance Designer 插件卸载 ─────────────────────")
    print()

    plugins_dir = os.path.join(
        os.path.expanduser("~"), "Documents", "Adobe",
        "Adobe Substance 3D Designer", "python", "sduserplugins"
    )
    dcc_dst = os.path.join(plugins_dir, "artclaw_bridge")

    if os.path.isdir(dcc_dst):
        shutil.rmtree(dcc_dst)
        cprint("删除", f"已删除: {dcc_dst}", "green")
    else:
        cprint("跳过", f"artclaw_bridge 不存在: {dcc_dst}", "yellow")

    cprint("完成", "Substance Designer 插件卸载完成", "green")
    return True


# ===========================================================================
# ComfyUI
# ===========================================================================

COMFYUI_BRIDGE_SRC = ROOT_DIR / "subprojects" / "ComfyUIClawBridge"


def _detect_comfyui_path() -> str | None:
    """自动检测 ComfyUI 安装目录。

    搜索优先级:
    1. ~/Documents/ComfyUI (ComfyUI Desktop 默认数据目录)
    2. %LOCALAPPDATA%/Programs/ComfyUI/resources/ComfyUI (Desktop app 内置)
    3. 常见安装路径: D:/ComfyUI, C:/ComfyUI
    """
    candidates = [
        os.path.expanduser("~/Documents/ComfyUI"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "ComfyUI", "resources", "ComfyUI"),
        "D:/ComfyUI",
        "C:/ComfyUI",
    ]
    if platform.system() != "Windows":
        candidates.extend([
            os.path.expanduser("~/ComfyUI"),
            "/opt/ComfyUI",
        ])
    for path in candidates:
        if path and os.path.isdir(os.path.join(path, "custom_nodes")):
            return path
    return None


def install_comfyui(comfyui_path: str, force: bool, platform_type: str = "openclaw"):
    """安装 ComfyUI 自定义节点

    将 ComfyUIClawBridge 部署到 ComfyUI 的 custom_nodes/artclaw_bridge/ 目录。
    同时复制 DCCClawBridge（adapters + core）作为依赖。

    Args:
        comfyui_path: ComfyUI 安装目录（包含 main.py 的目录），空则自动检测
        force: 跳过覆盖确认
        platform_type: 目标平台
    """
    print()
    print("  ── ComfyUI 插件安装 ─────────────────────────────")
    print()

    if not comfyui_path:
        detected = _detect_comfyui_path()
        if detected:
            comfyui_path = detected
            cprint("检测", f"自动发现 ComfyUI: {comfyui_path}", "cyan")
        else:
            cprint("错误", "--comfyui-path 未指定且未能自动检测到 ComfyUI 安装目录", "red")
            cprint("提示", "请手动指定: --comfyui-path <ComfyUI目录>", "yellow")
            return False

    # 验证 ComfyUI 目录
    comfyui_dir = os.path.abspath(comfyui_path)
    custom_nodes_dir = os.path.join(comfyui_dir, "custom_nodes")
    if not os.path.isdir(custom_nodes_dir):
        # 尝试向上一级找
        if os.path.isdir(os.path.join(comfyui_dir, "main.py")):
            pass  # comfyui_dir is correct
        elif os.path.isdir(os.path.join(os.path.dirname(comfyui_dir), "custom_nodes")):
            comfyui_dir = os.path.dirname(comfyui_dir)
            custom_nodes_dir = os.path.join(comfyui_dir, "custom_nodes")
        else:
            cprint("错误", f"未找到 custom_nodes 目录: {custom_nodes_dir}", "red")
            cprint("提示", "请确认 ComfyUI 安装目录正确（包含 main.py 和 custom_nodes/）", "yellow")
            return False

    dcc_dst = os.path.join(custom_nodes_dir, "artclaw_bridge")

    cprint("信息", f"平台: {platform_type}")
    cprint("信息", f"ComfyUI 目录: {comfyui_dir}")
    cprint("信息", f"目标目录: {dcc_dst}")

    if not confirm_overwrite(dcc_dst, force):
        cprint("跳过", "ComfyUI 插件安装", "yellow")
        return True

    os.makedirs(custom_nodes_dir, exist_ok=True)

    # 复制 ComfyUIClawBridge 为 artclaw_bridge
    cprint("复制", "ComfyUIClawBridge → artclaw_bridge...")
    if not COMFYUI_BRIDGE_SRC.is_dir():
        cprint("错误", f"ComfyUIClawBridge 源码不存在: {COMFYUI_BRIDGE_SRC}", "red")
        return False
    copy_dir(str(COMFYUI_BRIDGE_SRC), dcc_dst)
    cprint("OK", f"ComfyUIClawBridge 已安装到: {dcc_dst}", "green")

    # 复制 DCCClawBridge 到 artclaw_bridge 旁边的 DCCClawBridge/ 目录
    # startup.py 通过 ../DCCClawBridge 找到依赖
    dcc_bridge_dst = os.path.join(custom_nodes_dir, "artclaw_bridge_dcc")
    cprint("复制", "DCCClawBridge → artclaw_bridge_dcc/ (依赖库)...")
    copy_dir(str(DCC_BRIDGE_SRC), dcc_bridge_dst)
    cprint("OK", f"DCCClawBridge 已安装到: {dcc_bridge_dst}", "green")

    # 复制共享模块到 dcc 的 core/
    cprint("复制", "bridge_core 共享模块到 core/...")
    copy_shared_modules(os.path.join(dcc_bridge_dst, "core"))
    cprint("OK", "共享模块已打包 (自包含部署)", "green")

    # 创建 artclaw_bridge_dcc 的 __init__.py（ComfyUI 需要这个文件来识别包）
    init_path = os.path.join(dcc_bridge_dst, "__init__.py")
    with open(init_path, "w", encoding="utf-8") as f:
        f.write('"""ArtClaw Bridge - DCC 依赖库"""\n')
    cprint("OK", "已创建 artclaw_bridge_dcc/__init__.py", "green")

    # 复制平台 bridge 到 core/
    cprint("复制", f"平台 bridge ({platform_type}) 到 core/...")
    copy_platform_bridge(platform_type, os.path.join(dcc_bridge_dst, "core"))

    # 更新 startup.py 中的路径（指向实际 DCCClawBridge 位置）
    # 写入环境变量配置文件
    env_file = os.path.join(dcc_dst, ".env")
    with open(env_file, "w", encoding="utf-8") as f:
        f.write(f"# ArtClaw Bridge 自动生成\n")
        f.write(f"ARTCLAW_DCC_BRIDGE_PATH={dcc_bridge_dst}\n")
    cprint("OK", f"已创建 .env 配置: {env_file}", "green")

    # 安装 Python 依赖到 ComfyUI 环境
    _install_comfyui_python_deps(comfyui_dir)

    # 安装推荐的 ComfyUI 节点包
    _install_comfyui_custom_nodes(comfyui_dir)

    # 安装 DCC Skills
    install_dcc_skills(["comfyui", "universal"], platform_type)

    cprint("完成", "ComfyUI 插件安装成功!", "green")
    print()
    cprint("后续步骤", "1. 启动 ComfyUI → ArtClaw Bridge 自动加载", "cyan")
    cprint("后续步骤", "2. 日志中应出现: ArtClaw: MCP Server started on port 8087", "cyan")
    cprint("后续步骤", "3. 配置 OpenClaw: python setup_openclaw_config.py --comfyui", "cyan")
    cprint("后续步骤", "4. 重启 ComfyUI Desktop 加载新安装的节点包", "cyan")
    print()
    cprint("注意", "如果 MCP Server 启动失败，请检查 websockets 和 pydantic 是否已安装", "yellow")
    return True


def uninstall_comfyui(comfyui_path: str):
    """卸载 ComfyUI 自定义节点"""
    print()
    print("  ── ComfyUI 插件卸载 ─────────────────────────────")
    print()

    if not comfyui_path:
        cprint("错误", "--comfyui-path 未指定", "red")
        return False

    comfyui_dir = os.path.abspath(comfyui_path)
    custom_nodes_dir = os.path.join(comfyui_dir, "custom_nodes")

    for dirname in ["artclaw_bridge", "artclaw_bridge_dcc"]:
        dst = os.path.join(custom_nodes_dir, dirname)
        if os.path.isdir(dst):
            shutil.rmtree(dst)
            cprint("删除", f"已删除: {dst}", "green")
        else:
            cprint("跳过", f"{dirname} 不存在: {dst}", "yellow")

    cprint("完成", "ComfyUI 插件卸载完成", "green")
    return True


# ===========================================================================
# Substance 共用: Python 依赖安装
# ===========================================================================


def _install_comfyui_custom_nodes(comfyui_dir: str):
    """
    安装推荐的 ComfyUI 自定义节点包。

    这些节点包提供额外的图像处理功能，用于 PBR 贴图生成等。
    """
    custom_nodes_dir = os.path.join(comfyui_dir, "custom_nodes")
    os.makedirs(custom_nodes_dir, exist_ok=True)

    # 推荐的节点包列表
    repos = [
        {
            "name": "ComfyUI-Manager",
            "url": "https://github.com/ltdrdata/ComfyUI-Manager.git",
            "desc": "节点管理器",
            "required": True,
        },
        {
            "name": "comfyui_controlnet_aux",
            "url": "https://github.com/Fannovel16/comfyui_controlnet_aux.git",
            "desc": "ControlNet 辅助节点",
            "required": False,
        },
        {
            "name": "cg-image-picker",
            "url": "https://github.com/chrisgoringe/cg-image-picker.git",
            "desc": "图像选择和处理",
            "required": False,
        },
    ]

    print()
    cprint("安装", "ComfyUI 自定义节点包...")
    print()

    python = _find_comfyui_python(comfyui_dir)

    for repo in repos:
        repo_path = os.path.join(custom_nodes_dir, repo["name"])
        print(f"  [{repo['name']}]")
        print(f"    描述: {repo['desc']}")

        if os.path.exists(repo_path):
            print(f"    状态: 已存在")
        else:
            print(f"    安装: {repo['url']}")
            try:
                result = subprocess.run(
                    ["git", "clone", repo["url"]],
                    cwd=custom_nodes_dir,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode == 0:
                    print(f"    状态: [OK] 安装成功")
                else:
                    print(f"    状态: [X] 安装失败")
                    if repo["required"]:
                        cprint("警告", f"{repo['name']} 安装失败，但它是可选组件", "yellow")
                    continue
            except Exception as e:
                print(f"    状态: [X] 错误: {e}")
                continue

        # 安装节点包的依赖
        req_file = os.path.join(repo_path, "requirements.txt")
        if os.path.exists(req_file) and python:
            print(f"    依赖: 安装中...")
            try:
                result = subprocess.run(
                    [python, "-m", "pip", "install", "-r", req_file],
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                if result.returncode == 0:
                    print(f"    依赖: OK 安装成功")
                else:
                    print(f"    依赖: [!] 可能有问题")
            except Exception as e:
                print(f"    依赖: [!] 错误: {e}")

    print()
    cprint("OK", "节点包安装完成", "green")


def _install_comfyui_python_deps(comfyui_dir: str):
    """
    尝试查找 ComfyUI 的 Python 并安装依赖。

    ComfyUI Desktop 使用独立的虚拟环境 (.venv)。
    依赖: websockets, pydantic
    """
    python = _find_comfyui_python(comfyui_dir)
    if not python:
        cprint("提示", "未找到 ComfyUI Python，请手动安装依赖", "yellow")
        cprint("提示", "需要: pip install websockets pydantic", "yellow")
        return

    deps = ["websockets", "pydantic"]
    cprint("安装", f"正在安装 Python 依赖到 ComfyUI: {', '.join(deps)}...")
    try:
        result = subprocess.run(
            [python, "-m", "pip", "install"] + deps,
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode == 0:
            cprint("OK", f"Python 依赖已安装到 ComfyUI Python ({', '.join(deps)})", "green")
        else:
            error = result.stderr.strip() or result.stdout.strip()
            cprint("警告", f"依赖安装失败: {error}", "yellow")
            cprint("提示", f'请手动运行: "{python}" -m pip install {" ".join(deps)}', "yellow")
    except Exception as e:
        cprint("警告", f"依赖安装失败: {e}", "yellow")
        cprint("提示", f'请手动运行: "{python}" -m pip install {" ".join(deps)}', "yellow")


def _find_comfyui_python(comfyui_dir: str) -> str | None:
    """
    查找 ComfyUI 使用的 Python 解释器。

    优先级:
    1. ComfyUI Desktop: .venv/Scripts/python.exe (虚拟环境)
    2. 系统 Python (comfyui_dir 下的 python.exe)
    3. 环境变量中的 python
    """
    # 1. ComfyUI Desktop 虚拟环境
    venv_python = os.path.join(comfyui_dir, ".venv", "Scripts", "python.exe")
    if os.path.isfile(venv_python):
        cprint("OK", f"找到 ComfyUI Desktop Python: {venv_python}", "cyan")
        return venv_python

    # 2. 直接放在 comfyui_dir 下的 python
    direct_python = os.path.join(comfyui_dir, "python.exe")
    if os.path.isfile(direct_python):
        cprint("OK", f"找到 ComfyUI Python: {direct_python}", "cyan")
        return direct_python

    # 3. 尝试系统 Python
    try:
        result = subprocess.run(
            ["python", "-c", "import sys; print(sys.executable)"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            system_python = result.stdout.strip()
            cprint("提示", f"使用系统 Python: {system_python}", "yellow")
            return system_python
    except Exception:
        pass

    return None


def _install_substance_python_deps(product: str):
    """
    尝试查找 Substance Painter/Designer Python 并安装依赖。

    Args:
        product: "Painter" 或 "Designer"
    """
    python = _find_substance_python(product)
    if not python:
        cprint("提示", f"未找到 Substance 3D {product} Python，请手动安装依赖", "yellow")
        cprint("提示", "需要: pip install websockets pydantic", "yellow")
        return
    deps = ["websockets", "pydantic"]
    try:
        result = subprocess.run(
            [python, "-m", "pip", "install"] + deps,
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode == 0:
            cprint("OK", f"Python 依赖已安装到 Substance {product} Python ({', '.join(deps)})", "green")
        else:
            error = result.stderr.strip() or result.stdout.strip()
            cprint("警告", f"依赖安装失败: {error}", "yellow")
            cprint("提示", f'请手动运行: "{python}" -m pip install {" ".join(deps)}', "yellow")
    except Exception as e:
        cprint("警告", f"依赖安装失败: {e}", "yellow")
        cprint("提示", f'请手动运行: "{python}" -m pip install {" ".join(deps)}', "yellow")


def _find_substance_python(product: str) -> str | None:
    """
    查找 Substance Painter/Designer 内置 Python。

    SP: C:\\Program Files\\Adobe\\Adobe Substance 3D Painter\\resources\\pythonsdk\\python.exe
    SD: C:\\Program Files\\Adobe\\Adobe Substance 3D Designer\\plugins\\pythonsdk\\python.exe
    """
    if platform.system() != "Windows":
        return None

    # SP 和 SD 的 pythonsdk 位置不同
    sdk_subdirs = {
        "Painter": ["resources", "pythonsdk"],
        "Designer": ["plugins", "pythonsdk"],
    }
    subdir_parts = sdk_subdirs.get(product, ["pythonsdk"])

    for base in [
        "C:\\Program Files\\Adobe",
        "C:\\Program Files (x86)\\Adobe",
    ]:
        app_dir = os.path.join(base, f"Adobe Substance 3D {product}")
        if not os.path.isdir(app_dir):
            continue
        p = os.path.join(app_dir, *subdir_parts, "python.exe")
        if os.path.isfile(p):
            cprint("OK", f"找到 Substance {product} Python: {p}", "cyan")
            return p

    return None
