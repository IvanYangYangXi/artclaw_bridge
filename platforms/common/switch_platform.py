#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArtClaw Bridge 平台切换脚本
============================

在不同 AI平台之间切换（OpenClaw、LobsterAI 等）。

用法:
    python switch_platform.py --status              # 查看当前平台
    python switch_platform.py --to lobster          # 切换到 LobsterAI
    python switch_platform.py --to openclaw         # 切换到 OpenClaw
    python switch_platform.py --list                # 列出可用平台
    python switch_platform.py --ue-project <path>   # 指定 UE 项目路径

支持的平台:
  - openclaw: OpenClaw 社区版
  - lobster: LobsterAI（有道龙虾）
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

ARTCLAW_CONFIG_PATH = Path.home() / '.artclaw' / 'config.json'

PLATFORMS = {
    'openclaw': {
        'display_name': 'OpenClaw',
        'gateway_url': 'http://127.0.0.1:18789',
        'mcp_config_path': Path(os.environ['APPDATA']) / 'OpenClaw' / 'openclaw' / 'state' / 'openclaw.json',
        'bridge_prefix': 'openclaw',
    },
    'lobster': {
        'display_name': 'LobsterAI',
        'gateway_url': 'http://127.0.0.1:18790',
        'mcp_config_path': Path(os.environ['APPDATA']) / 'LobsterAI' / 'openclaw' / 'state' / 'openclaw.json',
        'bridge_prefix': 'lobster',
    },
}

# DCC 安装路径模式
DCC_PATHS = {
    'ue': [
        # 从 config.json 读取
    ],
    'maya': [
        Path.home() / 'Documents' / 'maya' / '*' / 'scripts' / 'DCCClawBridge' / 'core',
    ],
    'max': [
        Path.home() / 'Documents' / '3ds Max' / '*' / 'scripts' / 'DCCClawBridge' / 'core',
    ],
}


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def load_artclaw_config() -> dict:
    """加载 ArtClaw 配置文件"""
    if not ARTCLAW_CONFIG_PATH.exists():
        return {
            'platform': {
                'type': 'openclaw',
                'gateway_url': 'http://127.0.0.1:18789',
            },
            'ue_project_path': '',
            'skills_installed_path': str(Path.home() / '.openclaw' / 'skills'),
        }
    
    with open(ARTCLAW_CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_artclaw_config(config: dict):
    """保存 ArtClaw 配置文件"""
    ARTCLAW_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # 备份
    if ARTCLAW_CONFIG_PATH.exists():
        backup_path = ARTCLAW_CONFIG_PATH.with_suffix('.json.backup')
        shutil.copy2(ARTCLAW_CONFIG_PATH, backup_path)
        print(f"✓ 已备份原配置到：{backup_path}")
    
    with open(ARTCLAW_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"✓ 配置已保存到：{ARTCLAW_CONFIG_PATH}")


def discover_dcc_installations() -> dict:
    """自动发现已安装 ArtClaw 的 DCC 目录"""
    installations = {}
    
    # Maya: 扫描 ~/Documents/maya/*/scripts/DCCClawBridge/
    maya_base = Path.home() / "Documents" / "maya"
    if maya_base.exists():
        for ver_dir in maya_base.iterdir():
            if not ver_dir.is_dir():
                continue
            dcc_dir = ver_dir / "scripts" / "DCCClawBridge" / "core"
            if dcc_dir.exists():
                installations[f"maya-{ver_dir.name}"] = dcc_dir
    
    # Max: 扫描 ~/Documents/3ds Max/*/scripts/DCCClawBridge/
    max_base = Path.home() / "Documents" / "3ds Max"
    if max_base.exists():
        for ver_dir in max_base.iterdir():
            if not ver_dir.is_dir():
                continue
            dcc_dir = ver_dir / "scripts" / "DCCClawBridge" / "core"
            if dcc_dir.exists():
                installations[f"max-{ver_dir.name}"] = dcc_dir
    
    # UE: 从 config.json 读取
    config = load_artclaw_config()
    ue_project = config.get('ue_project_path', '')
    if ue_project:
        ue_python = Path(ue_project) / "Plugins" / "UEClawBridge" / "Content" / "Python"
        if ue_python.exists():
            installations["ue"] = ue_python
    
    return installations


def get_current_platform() -> str:
    """获取当前平台"""
    config = load_artclaw_config()
    return config.get('platform', {}).get('type', 'openclaw')


def switch_platform(target_platform: str, ue_project: str = None) -> bool:
    """切换到目标平台"""
    if target_platform not in PLATFORMS:
        print(f"✗ 不支持的平台：{target_platform}")
        print(f"可用平台：{', '.join(PLATFORMS.keys())}")
        return False
    
    platform_info = PLATFORMS[target_platform]
    
    print()
    print("=" * 60)
    print(f"切换到 {platform_info['display_name']}")
    print("=" * 60)
    print()
    
    # 1. 加载并更新 ArtClaw 配置
    config = load_artclaw_config()
    
    old_platform = config.get('platform', {}).get('type', 'openclaw')
    if old_platform == target_platform:
        print(f"ℹ 当前已经是 {platform_info['display_name']}")
        return True
    
    print(f"当前平台：{old_platform}")
    print(f"目标平台：{target_platform}")
    print()
    
    # 更新配置
    config.setdefault('platform', {})
    config['platform']['type'] = target_platform
    config['platform']['gateway_url'] = platform_info['gateway_url']
    
    if ue_project:
        config['ue_project_path'] = ue_project
        print(f"✓ UE 项目路径：{ue_project}")
    
    # Skills 路径保持不变（共享）
    if 'skills_installed_path' not in config:
        config['skills_installed_path'] = str(Path.home() / '.openclaw' / 'skills')
    
    # 2. 保存配置
    save_artclaw_config(config)
    print()
    
    # 3. 发现 DCC 安装
    print("发现 DCC 安装...")
    installations = discover_dcc_installations()
    
    if not installations:
        print("ℹ 未发现 DCC 安装")
        print("   请确保已运行过 install.py 安装 ArtClaw Bridge")
    else:
        print(f"✓ 发现 {len(installations)} 个 DCC 安装:")
        for name, path in installations.items():
            print(f"  - {name}: {path}")
    print()
    
    # 4. 复制平台 bridge 文件
    # 注意：当前实现中，bridge 文件是共享的（bridge_dcc.py）
    # 平台切换主要通过配置实现，不需要复制文件
    
    print("ℹ 平台切换说明:")
    print("   ArtClaw Bridge 使用共享 bridge 模块（bridge_dcc.py）")
    print("   平台切换通过配置实现，不需要复制文件")
    print()
    
    # 5. 平台特定配置
    if target_platform == 'lobster':
        print("LobsterAI平台特定配置:")
        print("  1. 配置 LobsterAI MCP Server")
        print("     运行：python platforms/lobster/setup_lobster_mcp.py")
        print("  2. 或在 LobsterAI 客户端界面配置:")
        print("     设置 → MCP 服务 → 添加 MCP 服务")
        print()
    
    # 6. 输出提示
    print("=" * 60)
    print("✓ 切换完成")
    print("=" * 60)
    print()
    print("下一步:")
    print("  1. 重启所有已打开的 DCC 软件（UE/Maya/Max）")
    print("  2. 重启目标平台客户端（OpenClaw/LobsterAI）")
    print("  3. 验证配置:")
    print(f"     运行：python {sys.argv[0]} --status")
    print()
    
    return True


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='ArtClaw Bridge 平台切换脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python switch_platform.py --status              查看当前平台
  python switch_platform.py --to lobster          切换到 LobsterAI
  python switch_platform.py --to openclaw         切换到 OpenClaw
  python switch_platform.py --list                列出可用平台
  python switch_platform.py --ue-project <path>   指定 UE 项目路径
        '''
    )
    
    parser.add_argument('--status', action='store_true',
                        help='查看当前平台')
    parser.add_argument('--to', metavar='PLATFORM',
                        help='切换到目标平台')
    parser.add_argument('--list', action='store_true',
                        help='列出可用平台')
    parser.add_argument('--ue-project', metavar='PATH',
                        help='指定 UE 项目路径')
    
    args = parser.parse_args()
    
    # 列出平台
    if args.list:
        print("可用平台:")
        for key, info in PLATFORMS.items():
            current = " (当前)" if key == get_current_platform() else ""
            print(f"  - {key}: {info['display_name']}{current}")
        print()
        return 0
    
    # 查看状态
    if args.status or not args.to:
        config = load_artclaw_config()
        current_platform = config.get('platform', {}).get('type', 'openclaw')
        platform_info = PLATFORMS.get(current_platform, {})
        
        print()
        print("=" * 60)
        print("ArtClaw Bridge 平台状态")
        print("=" * 60)
        print()
        print(f"当前平台：{platform_info.get('display_name', current_platform)}")
        print(f"Gateway URL: {config.get('platform', {}).get('gateway_url', 'N/A')}")
        print(f"UE 项目路径：{config.get('ue_project_path', '未设置')}")
        print(f"Skills 路径：{config.get('skills_installed_path', '未设置')}")
        print()
        
        # 发现 DCC 安装
        installations = discover_dcc_installations()
        if installations:
            print(f"发现的 DCC 安装 ({len(installations)}):")
            for name, path in installations.items():
                print(f"  - {name}: {path}")
        else:
            print("未发现 DCC 安装")
            print("  运行 install.py 安装 ArtClaw Bridge")
        print()
        
        return 0
    
    # 切换平台
    if args.to:
        success = switch_platform(args.to, args.ue_project)
        return 0 if success else 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
