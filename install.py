#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtClaw Bridge — 跨平台安装器
================================

统一安装 UE / Maya / 3ds Max / Blender / Houdini / Substance Painter / Substance Designer
插件 + 平台配置。每个目标部署为自包含模式（bridge_core 等共享模块打包进目标目录）。
支持多平台: openclaw (默认) / workbuddy / claude / lobster

用法:
    python install.py --maya                              # 安装 Maya 插件
    python install.py --maya --maya-version 2024          # 指定 Maya 版本
    python install.py --max --max-version 2024            # 安装 Max 插件
    python install.py --ue --ue-project "C:\\path\\to\\proj"  # 安装 UE 插件
    python install.py --blender                           # 安装 Blender 插件 (默认 4.2)
    python install.py --blender --blender-version 4.3     # 指定 Blender 版本
    python install.py --houdini                           # 安装 Houdini 插件 (默认 20.5)
    python install.py --sp                                # 安装 Substance Painter 插件
    python install.py --sd                                # 安装 Substance Designer 插件
    python install.py --openclaw                          # 配置平台
    python install.py --all --ue-project "C:\\path\\to\\proj"  # 全部安装
    python install.py --uninstall --maya                  # 卸载 Maya 插件
    python install.py --platform workbuddy --maya         # 安装 Maya 并配置 WorkBuddy 平台
    python install.py --force                             # 跳过覆盖确认
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from install_utils import ROOT_DIR, cprint, get_platform_src
from install_platform import PLATFORM_CONFIGS, install_openclaw
from install_dcc import (
    install_ue, uninstall_ue,
    install_maya, uninstall_maya,
    install_max, uninstall_max,
)
from install_dcc_ext import (
    install_blender, uninstall_blender,
    install_houdini, uninstall_houdini,
    install_substance_painter, uninstall_substance_painter,
    install_substance_designer, uninstall_substance_designer,
    install_comfyui, uninstall_comfyui,
)


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
        _print_post_steps(installed)


def _print_post_steps(installed: list[str]):
    """打印后续步骤"""
    joined = " ".join(installed)
    print("  后续步骤:")
    print()
    if "UE" in joined:
        print("    UE:")
        print("      1. 打开 UE 项目，启用 \"UE Claw Bridge\" 插件")
        print("      2. 重启编辑器")
        print("      3. Window 菜单 → UE Claw Bridge")
        print("      4. 输入 /diagnose 验证连接")
        print()
    if "Maya" in joined:
        print("    Maya:")
        print("      1. 启动 Maya → ArtClaw 菜单自动出现")
        print("      2. ArtClaw → 打开 Chat Panel")
        print("      3. 点击 连接 或输入 /connect")
        print()
    if "Max" in joined:
        print("    3ds Max:")
        print("      1. 启动 Max → ArtClaw 自动加载")
        print("      2. 菜单栏 → ArtClaw → Chat Panel")
        print("      3. 点击 连接 或输入 /connect")
        print()
    if "Blender" in joined:
        print("    Blender:")
        print("      1. Edit → Preferences → Add-ons → 搜索 'ArtClaw'")
        print("      2. 勾选启用 ArtClaw Bridge 插件")
        print("      3. 重启 Blender")
        print()
    if "Houdini" in joined:
        print("    Houdini:")
        print("      1. 创建 Shelf Tool")
        print("      2. Script: import houdini_shelf; houdini_shelf.toggle_artclaw()")
        print()
    if "Substance Painter" in joined:
        print("    Substance Painter:")
        print("      1. 启动 SP → Python → 勾选 artclaw_bridge")
        print()
    if "Substance Designer" in joined:
        print("    Substance Designer:")
        print("      1. 启动 SD → plugin 自动加载")
        print()
    if "ComfyUI" in joined:
        print("    ComfyUI:")
        print("      1. 启动 ComfyUI → ArtClaw Bridge 自动加载")
        print("      2. 日志中应出现 MCP Server started on port 8087")
        print("      3. 配置 OpenClaw 连接: --comfyui")
        print()
    if "OpenClaw" in joined:
        print("    OpenClaw:")
        print("      1. 重启 Gateway: openclaw gateway restart")
        print("      2. 确认 mcp-bridge 已加载")
        print()


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ArtClaw Bridge 安装器 — UE / Maya / Max / Blender / Houdini / SP / SD 一键部署",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python install.py --maya                               安装 Maya 插件 (默认版本 2023)
  python install.py --maya --maya-version 2024           安装到 Maya 2024
  python install.py --max --max-version 2024             安装 Max 插件
  python install.py --ue --ue-project "C:\\MyProject"     安装 UE 插件
  python install.py --blender                            安装 Blender 插件 (默认 4.2)
  python install.py --houdini --houdini-version 20.0     安装 Houdini 插件
  python install.py --sp                                 安装 Substance Painter 插件
  python install.py --sd                                 安装 Substance Designer 插件
  python install.py --comfyui --comfyui-path "C:\\ComfyUI" 安装 ComfyUI 插件
  python install.py --openclaw                           配置平台 (默认 openclaw)
  python install.py --all --ue-project "C:\\MyProject"    全部安装
  python install.py --uninstall --maya                   卸载 Maya 插件
  python install.py --uninstall --blender                卸载 Blender 插件
  python install.py --force --maya --max                 跳过覆盖确认
  python install.py --platform workbuddy --maya          安装 Maya 并配置 WorkBuddy 平台
  python install.py --platform lobster --maya            安装 Maya 并配置 LobsterAI 平台
        """,
    )

    # 安装目标
    parser.add_argument("--maya", action="store_true", help="安装/卸载 Maya 插件")
    parser.add_argument("--max", action="store_true", help="安装/卸载 3ds Max 插件")
    parser.add_argument("--ue", action="store_true", help="安装/卸载 UE 插件")
    parser.add_argument("--blender", action="store_true", help="安装/卸载 Blender 插件")
    parser.add_argument("--houdini", action="store_true", help="安装/卸载 Houdini 插件")
    parser.add_argument("--sp", action="store_true", help="安装/卸载 Substance Painter 插件")
    parser.add_argument("--sd", action="store_true", help="安装/卸载 Substance Designer 插件")
    parser.add_argument("--comfyui", action="store_true", help="安装/卸载 ComfyUI 插件")
    parser.add_argument("--openclaw", action="store_true", help="配置平台 (Gateway + Skills + config)")
    parser.add_argument("--all", action="store_true", help="安装全部 (7 个 DCC + 平台配置)")

    # 版本参数
    parser.add_argument("--maya-version", default="2023", help="Maya 版本 (默认: 2023)")
    parser.add_argument("--max-version", default="2024", help="3ds Max 版本 (默认: 2024)")
    parser.add_argument("--ue-project", default="", help="UE 项目路径 (包含 .uproject 的目录)")
    parser.add_argument("--blender-version", default="4.2", help="Blender 版本 (默认: 4.2)")
    parser.add_argument("--houdini-version", default="20.5", help="Houdini 版本 (默认: 20.5)")
    parser.add_argument("--comfyui-path", default="", help="ComfyUI 安装目录 (包含 main.py 的目录)")

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
    any_target = (
        args.maya or args.max or args.ue or args.blender
        or args.houdini or args.sp or args.sd or args.comfyui
        or args.openclaw or args.all
    )
    if not any_target:
        parser.print_help()
        return

    # --all 展开: 所有 7 个 DCC + 平台配置
    if args.all:
        args.maya = args.max = args.ue = True
        args.blender = args.houdini = args.sp = args.sd = args.comfyui = True
        args.openclaw = True

    pt = args.platform

    # 验证平台目录存在（非卸载模式）
    if not args.uninstall:
        platform_dir = get_platform_src(pt)
        if not platform_dir.exists():
            cprint("警告", f"平台目录不存在: {platform_dir}（可能尚未开发）", "yellow")
            cprint("提示", "将继续安装 DCC 插件 + 共享核心，但跳过平台 bridge 文件", "yellow")

    # 打印 banner
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    if args.uninstall:
        print("  ║       ArtClaw Bridge — 卸载器                        ║")
    else:
        print("  ║       ArtClaw Bridge — 安装器 v2.0                    ║")
    print("  ║       UE / Maya / Max / Blender / Houdini / SP / SD   ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print()
    cprint("信息", f"项目目录: {ROOT_DIR}")
    if not args.uninstall:
        cprint("信息", f"目标平台: {pt}")

    installed = []
    uninstalled = []

    if args.uninstall:
        _run_uninstalls(args, installed, uninstalled)
    else:
        _run_installs(args, pt, installed, uninstalled)

    print_summary(installed, uninstalled)

    # 安装模式结束后自动运行同步校验
    if not args.uninstall and installed:
        print()
        cprint("信息", "运行共享模块同步校验...", "cyan")
        _run_verify_sync()


def _run_installs(args, pt: str, installed: list[str], uninstalled: list[str]):
    """执行所有安装任务"""
    if args.ue and install_ue(args.ue_project, args.force, pt):
        installed.append("UE 插件")
    if args.maya and install_maya(args.maya_version, args.force, pt):
        installed.append(f"Maya {args.maya_version} 插件")
    if args.max and install_max(args.max_version, args.force, pt):
        installed.append(f"3ds Max {args.max_version} 插件")
    if args.blender and install_blender(args.blender_version, args.force, pt):
        installed.append(f"Blender {args.blender_version} 插件")
    if args.houdini and install_houdini(args.houdini_version, args.force, pt):
        installed.append(f"Houdini {args.houdini_version} 插件")
    if args.sp and install_substance_painter(args.force, pt):
        installed.append("Substance Painter 插件")
    if args.sd and install_substance_designer(args.force, pt):
        installed.append("Substance Designer 插件")
    if args.comfyui and install_comfyui(args.comfyui_path, args.force, pt):
        installed.append("ComfyUI 插件")
    if args.openclaw and install_openclaw(pt):
        installed.append(f"平台配置 ({pt})")


def _run_uninstalls(args, installed: list[str], uninstalled: list[str]):
    """执行所有卸载任务"""
    if args.ue and uninstall_ue(args.ue_project):
        uninstalled.append("UE 插件")
    if args.maya and uninstall_maya(args.maya_version):
        uninstalled.append(f"Maya {args.maya_version} 插件")
    if args.max and uninstall_max(args.max_version):
        uninstalled.append(f"3ds Max {args.max_version} 插件")
    if args.blender and uninstall_blender(args.blender_version):
        uninstalled.append(f"Blender {args.blender_version} 插件")
    if args.houdini and uninstall_houdini(args.houdini_version):
        uninstalled.append(f"Houdini {args.houdini_version} 插件")
    if args.sp and uninstall_substance_painter():
        uninstalled.append("Substance Painter 插件")
    if args.sd and uninstall_substance_designer():
        uninstalled.append("Substance Designer 插件")
    if args.comfyui and uninstall_comfyui(args.comfyui_path):
        uninstalled.append("ComfyUI 插件")
    if args.openclaw:
        cprint("提示", "平台配置需手动修改（参考 ~/.artclaw/config.json）", "yellow")


def _run_verify_sync():
    """通过子进程运行 verify_sync.py"""
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
