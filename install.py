#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtClaw Bridge — 跨平台安装器
================================

统一安装 UE / Maya / 3ds Max 插件 + OpenClaw 配置。
每个目标部署为自包含模式（bridge_core 等共享模块打包进目标目录）。

用法:
    python install.py --maya                              # 安装 Maya 插件
    python install.py --maya --maya-version 2024          # 指定 Maya 版本
    python install.py --max --max-version 2024            # 安装 Max 插件
    python install.py --ue --ue-project "C:\\path\\to\\proj"  # 安装 UE 插件
    python install.py --openclaw                          # 配置 OpenClaw
    python install.py --all --ue-project "C:\\path\\to\\proj"  # 全部安装
    python install.py --uninstall --maya                  # 卸载 Maya 插件
    python install.py --uninstall --max                   # 卸载 Max 插件
    python install.py --uninstall --ue --ue-project "C:\\path\\to\\proj"  # 卸载 UE 插件
    python install.py --force                             # 跳过覆盖确认
"""

from __future__ import annotations

import argparse
import glob
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
BRIDGE_MODULES_SRC = ROOT_DIR / "openclaw-mcp-bridge"
MCP_BRIDGE_SRC = ROOT_DIR / "openclaw-mcp-bridge" / "mcp-bridge"

# 需要打包到每个目标的共享模块
SHARED_MODULES = ["bridge_core.py", "bridge_config.py", "bridge_diagnostics.py"]

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


def copy_shared_modules(dst_dir: str):
    """将 bridge_core 等共享模块复制到目标目录"""
    os.makedirs(dst_dir, exist_ok=True)
    for mod in SHARED_MODULES:
        src = BRIDGE_MODULES_SRC / mod
        if src.exists():
            shutil.copy2(str(src), os.path.join(dst_dir, mod))
        else:
            cprint("警告", f"共享模块不存在: {src}", "yellow")


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

def install_ue(ue_project: str, force: bool):
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

def install_maya(maya_version: str, force: bool):
    """安装 Maya 插件"""
    print()
    print("  ── Maya 插件安装 ───────────────────────────────────")
    print()

    scripts_dir = os.path.join(
        os.path.expanduser("~"), "Documents", "maya", maya_version, "scripts"
    )
    dcc_dst = os.path.join(scripts_dir, "DCCClawBridge")

    cprint("信息", f"Maya 版本: {maya_version}")
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

def install_max(max_version: str, force: bool):
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

def install_openclaw():
    """配置 OpenClaw mcp-bridge 插件"""
    print()
    print("  ── OpenClaw mcp-bridge 配置 ────────────────────────")
    print()

    # 复制 mcp-bridge 插件文件
    ext_dir = os.path.join(os.path.expanduser("~"), ".openclaw", "extensions", "mcp-bridge")
    os.makedirs(ext_dir, exist_ok=True)

    for fname in ["index.ts", "openclaw.plugin.json"]:
        src = MCP_BRIDGE_SRC / fname
        if src.exists():
            shutil.copy2(str(src), os.path.join(ext_dir, fname))
    cprint("OK", f"mcp-bridge 已复制到: {ext_dir}", "green")

    # 运行配置脚本
    config_script = BRIDGE_MODULES_SRC / "setup_openclaw_config.py"
    if config_script.exists():
        cprint("配置", "运行 setup_openclaw_config.py...")
        try:
            subprocess.run(
                [sys.executable, str(config_script), "--ue", "--maya", "--max"],
                check=True, timeout=30,
            )
            cprint("OK", "OpenClaw 配置已更新", "green")
        except Exception as e:
            cprint("警告", f"配置脚本失败: {e}", "yellow")
            cprint("提示", f"请手动运行: python {config_script}", "yellow")
    else:
        cprint("警告", f"配置脚本不存在: {config_script}", "yellow")

    cprint("完成", "OpenClaw 配置成功!", "green")
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
            print(f"    ✅ {item}")
        print()

    if uninstalled:
        print("  已卸载:")
        for item in uninstalled:
            print(f"    🗑️  {item}")
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
  python install.py --openclaw                           配置 OpenClaw
  python install.py --all --ue-project "C:\\MyProject"    全部安装
  python install.py --uninstall --maya                   卸载 Maya 插件
  python install.py --uninstall --maya --max             卸载 Maya + Max
  python install.py --force --maya --max                 跳过覆盖确认
        """,
    )

    # 安装目标
    parser.add_argument("--maya", action="store_true", help="安装/卸载 Maya 插件")
    parser.add_argument("--max", action="store_true", help="安装/卸载 3ds Max 插件")
    parser.add_argument("--ue", action="store_true", help="安装/卸载 UE 插件")
    parser.add_argument("--openclaw", action="store_true", help="配置 OpenClaw mcp-bridge")
    parser.add_argument("--all", action="store_true", help="安装全部 (UE + Maya + Max + OpenClaw)")

    # 版本参数
    parser.add_argument("--maya-version", default="2023", help="Maya 版本 (默认: 2023)")
    parser.add_argument("--max-version", default="2024", help="3ds Max 版本 (默认: 2024)")
    parser.add_argument("--ue-project", default="", help="UE 项目路径 (包含 .uproject 的目录)")

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

    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    if args.uninstall:
        print("  ║       ArtClaw Bridge — 卸载器                        ║")
    else:
        print("  ║       ArtClaw Bridge — 安装器 v1.0                    ║")
    print("  ║       UE / Maya / 3ds Max                             ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    cprint("信息", f"项目目录: {ROOT_DIR}")

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
            cprint("提示", "OpenClaw 配置需手动修改平台配置文件（参考 ~/.artclaw/config.json 中的 mcp.config_path）", "yellow")
    else:
        # ─── 安装模式 ───
        if args.ue:
            if install_ue(args.ue_project, args.force):
                installed.append("UE 插件")
        if args.maya:
            if install_maya(args.maya_version, args.force):
                installed.append(f"Maya {args.maya_version} 插件")
        if args.max:
            if install_max(args.max_version, args.force):
                installed.append(f"3ds Max {args.max_version} 插件")
        if args.openclaw:
            if install_openclaw():
                installed.append("OpenClaw mcp-bridge")

    print_summary(installed, uninstalled)


if __name__ == "__main__":
    main()
