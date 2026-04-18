#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LobsterAI MCP 配置自动化脚本
==============================

自动将 ArtClaw MCP Server 配置添加到 LobsterAI 客户端的 openclaw.json。
支持 --ue, --maya, --max 标志，与 install.py 集成。

用法:
    python setup_lobster_config.py --ue --maya --max    # 添加所有 DCC MCP Servers
    python setup_lobster_config.py --ue                 # 仅添加 UE
    python setup_lobster_config.py --remove             # 移除所有 ArtClaw 配置
    python setup_lobster_config.py --status             # 查看当前配置状态

与 install.py 集成:
    python install.py --lobster --maya --max            # 安装 DCC 插件并配置 LobsterAI MCP
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

# 项目根目录（相对于本脚本）
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent.parent

LOBSTERAI_CONFIG_PATH = Path(os.environ['APPDATA']) / 'LobsterAI' / 'openclaw' / 'state' / 'openclaw.json'

# ArtClaw MCP Server 定义
ARTCLAW_MCP_SERVERS = {
    'ue': {
        'name': 'artclaw-ue',
        'description': 'UE Editor MCP Server - ArtClaw Bridge',
        'transport': 'stdio',
        'command': 'python',
        'enabled': True,
    },
    'maya': {
        'name': 'artclaw-maya',
        'description': 'Maya MCP Server - ArtClaw Bridge',
        'transport': 'stdio',
        'command': 'python',
        'enabled': True,
    },
    'max': {
        'name': 'artclaw-max',
        'description': '3ds Max MCP Server - ArtClaw Bridge',
        'transport': 'stdio',
        'command': 'python',
        'enabled': True,
    },
    'blender': {
        'name': 'artclaw-blender',
        'description': 'Blender MCP Server - ArtClaw Bridge',
        'transport': 'stdio',
        'command': 'python',
        'enabled': True,
    },
    'houdini': {
        'name': 'artclaw-houdini',
        'description': 'Houdini MCP Server - ArtClaw Bridge',
        'transport': 'stdio',
        'command': 'python',
        'enabled': True,
    },
    'sp': {
        'name': 'artclaw-sp',
        'description': 'Substance Painter MCP Server - ArtClaw Bridge',
        'transport': 'stdio',
        'command': 'python',
        'enabled': True,
    },
    'sd': {
        'name': 'artclaw-sd',
        'description': 'Substance Designer MCP Server - ArtClaw Bridge',
        'transport': 'stdio',
        'command': 'python',
        'enabled': True,
    },
    'comfyui': {
        'name': 'artclaw-comfyui',
        'description': 'ComfyUI MCP Server - ArtClaw Bridge',
        'transport': 'stdio',
        'command': 'python',
        'enabled': True,
    },
}

# 桥接脚本路径
BRIDGE_SCRIPTS = {
    'ue': str(ROOT_DIR / 'platforms' / 'common' / 'artclaw_stdio_bridge.py'),
    'maya': str(ROOT_DIR / 'platforms' / 'common' / 'artclaw_stdio_bridge.py'),
    'max': str(ROOT_DIR / 'platforms' / 'common' / 'artclaw_stdio_bridge.py'),
    'blender': str(ROOT_DIR / 'platforms' / 'common' / 'artclaw_stdio_bridge.py'),
    'houdini': str(ROOT_DIR / 'platforms' / 'common' / 'artclaw_stdio_bridge.py'),
    'sp': str(ROOT_DIR / 'platforms' / 'common' / 'artclaw_stdio_bridge.py'),
    'sd': str(ROOT_DIR / 'platforms' / 'common' / 'artclaw_stdio_bridge.py'),
    'comfyui': str(ROOT_DIR / 'platforms' / 'common' / 'artclaw_stdio_bridge.py'),
}

# MCP 端口
MCP_PORTS = {
    'ue': 8080,
    'maya': 8081,
    'max': 8082,
    'blender': 8083,
    'houdini': 8084,
    'sp': 8085,
    'sd': 8086,
    'comfyui': 8087,
}


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

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


def load_config() -> dict:
    """加载 LobsterAI 配置文件"""
    if not LOBSTERAI_CONFIG_PATH.exists():
        raise FileNotFoundError(f"LobsterAI 配置文件不存在：{LOBSTERAI_CONFIG_PATH}")
    
    with open(LOBSTERAI_CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_config(config: dict):
    """保存 LobsterAI 配置文件（带备份）"""
    # 创建备份
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = LOBSTERAI_CONFIG_PATH.with_suffix(f'.json.backup_{timestamp}')
    
    try:
        # 备份原配置
        if LOBSTERAI_CONFIG_PATH.exists():
            import shutil
            shutil.copy2(LOBSTERAI_CONFIG_PATH, backup_path)
            cprint("OK", f"已备份原配置到：{backup_path}", "cyan")
        
        # 保存新配置
        with open(LOBSTERAI_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        cprint("OK", f"配置已保存到：{LOBSTERAI_CONFIG_PATH}", "green")
    except Exception as e:
        cprint("ERROR", f"保存配置失败：{e}", "red")
        raise


def get_mcp_servers(config: dict) -> dict:
    """获取当前 MCP Servers 配置"""
    plugins = config.get('plugins', {})
    entries = plugins.get('entries', {})
    mcp_bridge = entries.get('mcp-bridge', {})
    mcp_config = mcp_bridge.get('config', {})
    servers = mcp_config.get('servers', {})
    return servers


def check_artclaw_installed(config: dict) -> list:
    """检查已安装的 ArtClaw MCP Servers"""
    installed = []
    servers = get_mcp_servers(config)
    
    for server_name, server_config in servers.items():
        if server_name.startswith('artclaw-'):
            installed.append(server_name)
    
    return installed


def add_mcp_server(config: dict, server_type: str) -> bool:
    """添加 MCP Server 配置"""
    if server_type not in ARTCLAW_MCP_SERVERS:
        cprint("ERROR", f"未知的服务器类型：{server_type}", "red")
        return False
    
    server_config = ARTCLAW_MCP_SERVERS[server_type]
    bridge_path = BRIDGE_SCRIPTS[server_type]
    port = MCP_PORTS[server_type]
    
    # 验证桥接脚本存在
    if not Path(bridge_path).exists():
        cprint("ERROR", f"桥接脚本不存在：{bridge_path}", "red")
        return False
    
    # 构建服务器配置
    server_entry = {
        'type': 'stdio',
        'command': 'python',
        'args': [bridge_path, '--port', str(port)],
        'enabled': True,
    }
    
    # 获取或创建 servers 配置
    plugins = config.setdefault('plugins', {})
    entries = plugins.setdefault('entries', {})
    mcp_bridge = entries.setdefault('mcp-bridge', {'enabled': True, 'config': {}})
    mcp_config = mcp_bridge.setdefault('config', {})
    servers = mcp_config.setdefault('servers', {})
    
    # 检查是否已存在
    if server_config['name'] in servers:
        cprint("INFO", f"{server_config['name']} 已存在，跳过", "yellow")
        return True
    
    # 添加服务器配置
    servers[server_config['name']] = server_entry
    cprint("OK", f"已添加 {server_config['name']} (端口 {port})", "green")
    
    return True


def remove_artclaw_config(config: dict) -> bool:
    """移除所有 ArtClaw 配置"""
    plugins = config.get('plugins', {})
    entries = plugins.get('entries', {})
    mcp_bridge = entries.get('mcp-bridge', {})
    mcp_config = mcp_bridge.get('config', {})
    servers = mcp_config.get('servers', {})
    
    # 移除 artclaw-* 的服务器
    original_count = len(servers)
    keys_to_remove = [k for k in servers.keys() if k.startswith('artclaw-')]
    
    for key in keys_to_remove:
        del servers[key]
    
    removed_count = len(keys_to_remove)
    
    if removed_count > 0:
        cprint("OK", f"已移除 {removed_count} 个 ArtClaw MCP Servers", "green")
        return True
    else:
        cprint("INFO", "未找到 ArtClaw MCP Server 配置", "yellow")
        return False


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='LobsterAI MCP 配置自动化脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python setup_lobster_config.py --ue --maya --max    添加 UE+Maya+Max MCP Servers
  python setup_lobster_config.py --all                添加所有 DCC MCP Servers
  python setup_lobster_config.py --remove             移除所有 ArtClaw 配置
  python setup_lobster_config.py --status             查看当前配置状态
  python setup_lobster_config.py --ue                 仅添加 UE
        '''
    )
    
    parser.add_argument('--all', action='store_true',
                        help='添加所有 DCC MCP Servers')
    parser.add_argument('--remove', action='store_true',
                        help='移除所有 ArtClaw 配置')
    parser.add_argument('--status', action='store_true',
                        help='查看当前配置状态')
    parser.add_argument('--ue', action='store_true',
                        help='添加 UE MCP Server')
    parser.add_argument('--maya', action='store_true',
                        help='添加 Maya MCP Server')
    parser.add_argument('--max', action='store_true',
                        help='添加 3ds Max MCP Server')
    parser.add_argument('--blender', action='store_true',
                        help='添加 Blender MCP Server')
    parser.add_argument('--houdini', action='store_true',
                        help='添加 Houdini MCP Server')
    parser.add_argument('--sp', action='store_true',
                        help='添加 Substance Painter MCP Server')
    parser.add_argument('--sd', action='store_true',
                        help='添加 Substance Designer MCP Server')
    parser.add_argument('--comfyui', action='store_true',
                        help='添加 ComfyUI MCP Server')
    parser.add_argument('--force', action='store_true',
                        help='跳过确认提示')
    
    args = parser.parse_args()
    
    print()
    print("=" * 60)
    print("LobsterAI MCP 配置自动化脚本")
    print("=" * 60)
    print()
    
    # 加载配置
    try:
        config = load_config()
        cprint("OK", f"已加载 LobsterAI 配置：{LOBSTERAI_CONFIG_PATH}", "green")
    except FileNotFoundError as e:
        cprint("ERROR", str(e), "red")
        print()
        print("请确保 LobsterAI 已安装并运行过至少一次")
        sys.exit(1)
    
    # 检查当前状态
    if args.status or not (args.all or args.remove or args.ue or args.maya or args.max or 
                           args.blender or args.houdini or args.sp or args.sd or args.comfyui):
        print()
        print("当前配置状态:")
        print("-" * 40)
        
        installed = check_artclaw_installed(config)
        if installed:
            cprint("INFO", f"已安装的 ArtClaw MCP Servers ({len(installed)}):", "cyan")
            for server in installed:
                print(f"  - {server}")
        else:
            cprint("INFO", "未安装 ArtClaw MCP Servers", "yellow")
        
        print()
        return 0
    
    # 移除配置
    if args.remove:
        print()
        cprint("INFO", "移除 ArtClaw 配置...", "cyan")
        print("-" * 40)
        
        if remove_artclaw_config(config):
            save_config(config)
            print()
            cprint("OK", "配置已移除", "green")
            cprint("INFO", "请重启 LobsterAI 客户端以应用更改", "yellow")
        else:
            print()
            cprint("INFO", "无需移除", "yellow")
        
        return 0
    
    # 添加配置
    servers_to_add = []
    if args.all:
        servers_to_add = ['ue', 'maya', 'max', 'blender', 'houdini', 'sp', 'sd', 'comfyui']
    else:
        if args.ue:
            servers_to_add.append('ue')
        if args.maya:
            servers_to_add.append('maya')
        if args.max:
            servers_to_add.append('max')
        if args.blender:
            servers_to_add.append('blender')
        if args.houdini:
            servers_to_add.append('houdini')
        if args.sp:
            servers_to_add.append('sp')
        if args.sd:
            servers_to_add.append('sd')
        if args.comfyui:
            servers_to_add.append('comfyui')
    
    if not servers_to_add:
        cprint("ERROR", "未指定要添加的 MCP Server，使用 --help 查看用法", "red")
        return 1
    
    print()
    cprint("INFO", f"准备添加 {len(servers_to_add)} 个 MCP Server:", "cyan")
    for server_type in servers_to_add:
        print(f"  - {server_type} (端口 {MCP_PORTS[server_type]})")
    print()
    
    # 验证桥接脚本
    cprint("INFO", "验证桥接脚本...", "cyan")
    all_valid = True
    for server_type in servers_to_add:
        bridge_path = BRIDGE_SCRIPTS[server_type]
        if Path(bridge_path).exists():
            print(f"  [OK] {bridge_path}")
        else:
            print(f"  [ERROR] {bridge_path} (不存在)")
            all_valid = False
    
    if not all_valid:
        print()
        cprint("ERROR", "桥接脚本不存在", "red")
        print("请确保 ArtClaw Bridge 已正确安装")
        return 1
    
    print()
    
    # 添加配置
    success_count = 0
    for server_type in servers_to_add:
        if add_mcp_server(config, server_type):
            success_count += 1
    
    # 保存配置
    if success_count > 0:
        save_config(config)
        
        print()
        print("=" * 60)
        cprint("OK", f"配置完成！已添加 {success_count} 个 MCP Server", "green")
        print("=" * 60)
        print()
        cprint("INFO", "下一步:", "cyan")
        print("  1. 完全退出 LobsterAI 客户端（包括系统托盘）")
        print("  2. 重新启动 LobsterAI")
        print("  3. 在聊天中测试 MCP 工具是否可用")
        print()
    else:
        print()
        cprint("INFO", "没有新增配置（可能已全部存在）", "yellow")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
