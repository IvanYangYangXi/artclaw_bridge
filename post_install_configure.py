#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtClaw Bridge — 安装后配置脚本
=================================

在 install.py 完成 DCC 插件安装后运行，自动配置平台的 MCP Servers。

用法:
    python post_install_configure.py --platform lobster --ue --maya
    python post_install_configure.py --platform openclaw --all
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
PLATFORMS_DIR = SCRIPT_DIR / "platforms"


def cprint(title: str, message: str, color: str = 'white'):
    """彩色打印"""
    colors = {
        'green': '\033[92m',
        'yellow': '\033[93m',
        'red': '\033[91m',
        'cyan': '\033[96m',
        'white': '\033[0m',
    }
    reset = '\033[0m'
    color_code = colors.get(color, '')
    print(f"{color_code}[{title}] {message}{reset}")


def run_platform_config(platform: str, installed_dccs: list[str]):
    """运行平台特定的配置脚本"""
    platform_dir = PLATFORMS_DIR / platform
    
    if not platform_dir.exists():
        cprint("WARNING", f"平台目录不存在：{platform_dir}", "yellow")
        return False
    
    # 查找 setup_*_config.py 脚本
    config_script = None
    for f in platform_dir.glob("setup_*_config.py"):
        config_script = f
        break
    
    if not config_script:
        cprint("WARNING", f"平台 {platform} 没有配置脚本", "yellow")
        return False
    
    # 构建命令行参数
    cmd_args = [sys.executable, str(config_script)]
    for dcc in installed_dccs:
        dcc = dcc.strip().lower()
        if dcc in ["ue", "maya", "max", "blender", "houdini", "sp", "sd", "comfyui"]:
            cmd_args.append(f"--{dcc}")
    
    if len(cmd_args) == 2:
        cmd_args.extend(["--ue", "--maya", "--max"])
    
    cprint("INFO", f"运行配置脚本：{config_script.name}", "cyan")
    cprint("INFO", f"参数：{' '.join(cmd_args[1:])}", "cyan")
    
    try:
        result = subprocess.run(cmd_args, check=True, timeout=60, capture_output=False)
        cprint("OK", "平台配置完成", "green")
        return True
    except subprocess.TimeoutExpired:
        cprint("WARNING", "配置脚本超时 (60 秒)", "yellow")
        return False
    except subprocess.CalledProcessError as e:
        cprint("ERROR", f"配置脚本失败：{e}", "red")
        return False
    except Exception as e:
        cprint("ERROR", f"配置脚本异常：{e}", "red")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='ArtClaw Bridge 安装后配置脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python post_install_configure.py --platform lobster --ue --maya
  python post_install_configure.py --platform openclaw --all
  python post_install_configure.py --platform claude --maya --max
        '''
    )
    
    parser.add_argument('--platform', required=True,
                        choices=['openclaw', 'lobster', 'claude', 'workbuddy', 'blender', 'houdini', 'sp', 'sd', 'comfyui'],
                        help='目标平台')
    parser.add_argument('--ue', action='store_true', help='配置 UE MCP Server')
    parser.add_argument('--maya', action='store_true', help='配置 Maya MCP Server')
    parser.add_argument('--max', action='store_true', help='配置 3ds Max MCP Server')
    parser.add_argument('--blender', action='store_true', help='配置 Blender MCP Server')
    parser.add_argument('--houdini', action='store_true', help='配置 Houdini MCP Server')
    parser.add_argument('--sp', action='store_true', help='配置 Substance Painter MCP Server')
    parser.add_argument('--sd', action='store_true', help='配置 Substance Designer MCP Server')
    parser.add_argument('--comfyui', action='store_true', help='配置 ComfyUI MCP Server')
    parser.add_argument('--all', action='store_true', help='配置所有 DCC MCP Servers')
    
    args = parser.parse_args()
    
    # 收集已安装的 DCC
    installed_dccs = []
    if args.all:
        installed_dccs = ['ue', 'maya', 'max', 'blender', 'houdini', 'sp', 'sd', 'comfyui']
    else:
        if args.ue:
            installed_dccs.append('ue')
        if args.maya:
            installed_dccs.append('maya')
        if args.max:
            installed_dccs.append('max')
        if args.blender:
            installed_dccs.append('blender')
        if args.houdini:
            installed_dccs.append('houdini')
        if args.sp:
            installed_dccs.append('sp')
        if args.sd:
            installed_dccs.append('sd')
        if args.comfyui:
            installed_dccs.append('comfyui')
    
    if not installed_dccs:
        cprint("ERROR", "未指定要配置的 DCC，使用 --help 查看用法", "red")
        return 1
    
    # 运行平台配置
    success = run_platform_config(args.platform, installed_dccs)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
