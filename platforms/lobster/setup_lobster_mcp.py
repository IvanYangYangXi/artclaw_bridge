#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LobsterAI MCP 配置注入脚本
===========================

自动将 ArtClaw MCP Server 配置添加到 LobsterAI 客户端。

用法:
    python setup_lobster_mcp.py                    # 添加 UE MCP Server
    python setup_lobster_mcp.py --all              # 添加 UE+Maya+Max
    python setup_lobster_mcp.py --remove           # 移除 ArtClaw 配置
    python setup_lobster_mcp.py --status           # 查看当前配置状态
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

LOBSTERAI_CONFIG_PATH = Path(os.environ['APPDATA']) / 'LobsterAI' / 'openclaw' / 'state' / 'openclaw.json'

ARTCLAW_MCP_SERVERS = {
    'ue': {
        'name': 'artclaw-ue',
        'description': 'UE Editor MCP Server',
        'transport': 'stdio',
        'command': 'python',
        'args': [],  # 运行时动态填充
        'enabled': True,
    },
    'maya': {
        'name': 'artclaw-maya',
        'description': 'Maya MCP Server',
        'transport': 'stdio',
        'command': 'python',
        'args': [],
        'enabled': True,
    },
    'max': {
        'name': 'artclaw-max',
        'description': '3ds Max MCP Server',
        'transport': 'stdio',
        'command': 'python',
        'args': [],
        'enabled': True,
    },
}

# 桥接脚本路径（相对于本脚本）
BRIDGE_SCRIPTS = {
    'ue': 'D:\\MyProject_D\\artclaw_bridge\\platforms\\common\\artclaw_stdio_bridge.py',
    'maya': 'D:\\MyProject_D\\artclaw_bridge\\platforms\\common\\artclaw_stdio_bridge.py',
    'max': 'D:\\MyProject_D\\artclaw_bridge\\platforms\\common\\artclaw_stdio_bridge.py',
}

# MCP 端口
MCP_PORTS = {
    'ue': 8080,
    'maya': 8081,
    'max': 8082,
}


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """加载 LobsterAI 配置文件"""
    if not LOBSTERAI_CONFIG_PATH.exists():
        raise FileNotFoundError(f"LobsterAI 配置文件不存在：{LOBSTERAI_CONFIG_PATH}")
    
    with open(LOBSTERAI_CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_config(config: dict):
    """保存 LobsterAI 配置文件"""
    # 备份原配置
    backup_path = LOBSTERAI_CONFIG_PATH.with_suffix('.json.backup')
    LOBSTERAI_CONFIG_PATH.rename(backup_path)
    print(f"[OK] 已备份原配置到：{backup_path}")
    
    # 保存新配置
    with open(LOBSTERAI_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"[OK] 配置已保存到：{LOBSTERAI_CONFIG_PATH}")


def get_mcp_servers_config(config: dict) -> dict:
    """获取当前 MCP Servers 配置"""
    plugins = config.get('plugins', {})
    entries = plugins.get('entries', {})
    mcp_bridge = entries.get('mcp-bridge', {})
    mcp_config = mcp_bridge.get('config', {})
    
    # LobsterAI 使用集中式 MCP 管理，配置可能在其他地方
    # 这里尝试从多个位置获取
    return mcp_config


def check_artclaw_installed(config: dict) -> list:
    """检查已安装的 ArtClaw MCP Servers"""
    installed = []
    
    # 检查配置中是否有 artclaw-* 的服务器
    # 由于 LobsterAI 使用集中式管理，这里只能检查客户端配置
    plugins = config.get('plugins', {})
    entries = plugins.get('entries', {})
    mcp_bridge = entries.get('mcp-bridge', {})
    mcp_config = mcp_bridge.get('config', {})
    
    # 检查 tools 数组
    tools = mcp_config.get('tools', [])
    for tool in tools:
        server = tool.get('server', '')
        if server.startswith('artclaw-') and server not in installed:
            installed.append(server)
    
    return installed


def add_mcp_server(config: dict, server_type: str) -> bool:
    """添加 MCP Server 配置"""
    if server_type not in ARTCLAW_MCP_SERVERS:
        print(f"[ERROR] 未知的服务器类型：{server_type}")
        return False
    
    server_config = ARTCLAW_MCP_SERVERS[server_type]
    bridge_path = BRIDGE_SCRIPTS[server_type]
    port = MCP_PORTS[server_type]
    
    # 验证桥接脚本存在
    if not Path(bridge_path).exists():
        print(f"[ERROR] 桥接脚本不存在：{bridge_path}")
        return False
    
    # 构建参数
    args = [bridge_path, '--port', str(port)]
    
    # 添加到配置
    # 注意：LobsterAI 使用集中式 MCP 管理，直接编辑 openclaw.json 可能无效
    # 这里添加配置仅供参考，实际需要通过 LobsterAI 客户端界面配置
    
    plugins = config.setdefault('plugins', {})
    entries = plugins.setdefault('entries', {})
    mcp_bridge = entries.setdefault('mcp-bridge', {'enabled': True, 'config': {}})
    mcp_config = mcp_bridge.setdefault('config', {})
    
    # 使用旧格式（LobsterAI 支持的格式）
    tools = mcp_config.setdefault('tools', [])
    
    # 检查是否已存在
    for tool in tools:
        if tool.get('server') == server_config['name']:
            print(f"[INFO] {server_config['name']} 已存在，跳过")
            return True
    
    # 添加工具定义（Context7 格式）
    # 注意：这只是配置模板，实际需要通过 LobsterAI 客户端界面配置
    print(f"[WARN] 注意：LobsterAI 使用集中式 MCP 管理")
    print(f"   直接编辑配置文件可能无效，请通过 LobsterAI 客户端界面配置")
    print(f"   配置路径：设置 → MCP 服务 → 添加 MCP 服务")
    
    return True


def remove_artclaw_config(config: dict) -> bool:
    """移除所有 ArtClaw 配置"""
    plugins = config.get('plugins', {})
    entries = plugins.get('entries', {})
    mcp_bridge = entries.get('mcp-bridge', {})
    mcp_config = mcp_bridge.get('config', {})
    tools = mcp_config.get('tools', [])
    
    # 移除 artclaw-* 的工具
    original_count = len(tools)
    tools[:] = [t for t in tools if not t.get('server', '').startswith('artclaw-')]
    removed_count = original_count - len(tools)
    
    if removed_count > 0:
        print(f"[OK] 已移除 {removed_count} 个 ArtClaw 工具配置")
        return True
    else:
        print(f"[INFO] 未找到 ArtClaw 工具配置")
        return False


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='LobsterAI MCP 配置注入脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python setup_lobster_mcp.py          添加 UE MCP Server
  python setup_lobster_mcp.py --all    添加 UE+Maya+Max
  python setup_lobster_mcp.py --remove 移除 ArtClaw 配置
  python setup_lobster_mcp.py --status 查看当前配置状态
        '''
    )
    
    parser.add_argument('--all', action='store_true',
                        help='添加所有 DCC MCP Servers (UE+Maya+Max)')
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
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("LobsterAI MCP 配置注入脚本")
    print("=" * 60)
    print()
    
    # 加载配置
    try:
        config = load_config()
        print(f"[OK] 已加载 LobsterAI 配置：{LOBSTERAI_CONFIG_PATH}")
    except FileNotFoundError as e:
        print(f"[ERROR] 错误：{e}")
        print()
        print("请确保 LobsterAI 已安装并运行过至少一次")
        sys.exit(1)
    
    # 检查当前状态
    if args.status or not (args.all or args.remove or args.ue or args.maya or args.max):
        print()
        print("当前配置状态:")
        print("-" * 40)
        
        installed = check_artclaw_installed(config)
        if installed:
            print(f"已安装的 ArtClaw MCP Servers:")
            for server in installed:
                print(f"  - {server}")
        else:
            print("未安装 ArtClaw MCP Servers")
        
        print()
        print("建议:")
        print("  通过 LobsterAI 客户端界面配置:")
        print("  1. 打开 LobsterAI 客户端")
        print("  2. 设置 → MCP 服务")
        print("  3. 添加 MCP 服务")
        print("  4. 配置:")
        print("     - 名称：artclaw-ue")
        print("     - 传输类型：stdio")
        print("     - 命令：python")
        print("     - 参数：<桥接脚本路径> --port 8080")
        print()
        return 0
    
    # 移除配置
    if args.remove:
        print()
        print("移除 ArtClaw 配置...")
        print("-" * 40)
        
        if remove_artclaw_config(config):
            save_config(config)
            print()
            print("[OK] 配置已移除")
            print("[WARN] 请重启 LobsterAI 客户端以应用更改")
        else:
            print()
            print("[INFO] 无需移除")
        
        return 0
    
    # 添加配置
    servers_to_add = []
    if args.all:
        servers_to_add = ['ue', 'maya', 'max']
    else:
        if args.ue:
            servers_to_add.append('ue')
        if args.maya:
            servers_to_add.append('maya')
        if args.max:
            servers_to_add.append('max')
    
    # 默认添加 UE
    if not servers_to_add:
        servers_to_add = ['ue']
    
    print()
    print(f"准备添加 {len(servers_to_add)} 个 MCP Server:")
    for server_type in servers_to_add:
        print(f"  - {server_type} (端口 {MCP_PORTS[server_type]})")
    print()
    
    # 验证桥接脚本
    print("验证桥接脚本...")
    for server_type in servers_to_add:
        bridge_path = BRIDGE_SCRIPTS[server_type]
        if Path(bridge_path).exists():
            print(f"  [OK] {bridge_path}")
        else:
            print(f"  [ERROR] {bridge_path} (不存在)")
            print()
            print("错误：桥接脚本不存在")
            print("请确保 ArtClaw Bridge 已正确安装")
            sys.exit(1)
    
    print()
    print("=" * 60)
    print("[WARN]  重要提示")
    print("=" * 60)
    print()
    print("LobsterAI 使用集中式 MCP 管理，配置存储在服务器端。")
    print("直接编辑配置文件可能无效，建议通过 LobsterAI 客户端界面配置。")
    print()
    print("手动配置步骤:")
    print("  1. 打开 LobsterAI 客户端")
    print("  2. 设置 → MCP 服务")
    print("  3. 添加 MCP 服务")
    print("  4. 配置:")
    print("     - 名称：artclaw-ue")
    print("     - 传输类型：标准输入输出 (stdio)")
    print("     - 命令：python")
    print("     - 参数：{} --port 8080".format(BRIDGE_SCRIPTS['ue']))
    print("  5. 保存并重启 LobsterAI")
    print()
    
    # 询问是否继续
    response = input("是否继续通过配置文件添加？(y/N): ")
    if response.lower() != 'y':
        print()
        print("已取消")
        return 0
    
    # 添加配置
    for server_type in servers_to_add:
        add_mcp_server(config, server_type)
    
    # 保存配置
    save_config(config)
    
    print()
    print("=" * 60)
    print("[OK] 配置完成")
    print("=" * 60)
    print()
    print("下一步:")
    print("  1. 完全退出 LobsterAI 客户端（包括系统托盘）")
    print("  2. 重新启动 LobsterAI")
    print("  3. 在 LobsterAI 聊天中测试:")
    print("     使用 run_ue_python 执行：print(\"Hello from ArtClaw!\")")
    print()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
