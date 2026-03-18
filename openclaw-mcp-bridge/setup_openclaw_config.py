"""
setup_openclaw_config.py - 自动配置 OpenClaw mcp-bridge
=========================================================

自动将 mcp-bridge 插件配置合并到 ~/.openclaw/openclaw.json。
安全操作：合并前自动备份原文件。

用法:
    python setup_openclaw_config.py                    # UE 单实例
    python setup_openclaw_config.py --maya              # 添加 Maya
    python setup_openclaw_config.py --ue --maya         # UE + Maya
    python setup_openclaw_config.py --ue-port 8080      # 自定义端口
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time


OPENCLAW_CONFIG = os.path.expanduser("~/.openclaw/openclaw.json")


def load_config() -> dict:
    if not os.path.exists(OPENCLAW_CONFIG):
        return {}
    with open(OPENCLAW_CONFIG, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict):
    os.makedirs(os.path.dirname(OPENCLAW_CONFIG), exist_ok=True)
    with open(OPENCLAW_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def backup_config():
    if os.path.exists(OPENCLAW_CONFIG):
        ts = time.strftime("%Y%m%d_%H%M%S")
        backup = f"{OPENCLAW_CONFIG}.backup_{ts}"
        shutil.copy2(OPENCLAW_CONFIG, backup)
        print(f"  备份: {backup}")
        return backup
    return None


def ensure_mcp_bridge(config: dict, servers: dict) -> bool:
    """确保 mcp-bridge 插件配置存在且包含指定的 servers"""
    changed = False

    # 确保 plugins 结构
    if "plugins" not in config:
        config["plugins"] = {}
        changed = True

    plugins = config["plugins"]

    # 确保 allow 列表包含 mcp-bridge
    if "allow" not in plugins:
        plugins["allow"] = []
    if "mcp-bridge" not in plugins["allow"]:
        plugins["allow"].append("mcp-bridge")
        changed = True

    # 确保 entries
    if "entries" not in plugins:
        plugins["entries"] = {}

    entries = plugins["entries"]

    if "mcp-bridge" not in entries:
        entries["mcp-bridge"] = {
            "enabled": True,
            "config": {"servers": {}},
        }
        changed = True

    bridge = entries["mcp-bridge"]
    if "config" not in bridge:
        bridge["config"] = {"servers": {}}
        changed = True

    existing_servers = bridge["config"].get("servers", {})

    # 合并新 servers（不覆盖已有配置）
    for name, server_def in servers.items():
        if name not in existing_servers:
            existing_servers[name] = server_def
            changed = True
            print(f"  添加 server: {name} → {server_def['url']}")
        else:
            print(f"  跳过 server: {name} (已存在)")

    bridge["config"]["servers"] = existing_servers
    return changed


def main():
    parser = argparse.ArgumentParser(
        description="配置 OpenClaw mcp-bridge 插件"
    )
    parser.add_argument("--ue", action="store_true", default=True,
                        help="添加 UE Editor MCP Server (默认)")
    parser.add_argument("--maya", action="store_true",
                        help="添加 Maya MCP Server")
    parser.add_argument("--max", action="store_true",
                        help="添加 3ds Max MCP Server")
    parser.add_argument("--ue-port", type=int, default=8080,
                        help="UE MCP Server 端口 (默认 8080)")
    parser.add_argument("--maya-port", type=int, default=8081,
                        help="Maya MCP Server 端口 (默认 8081)")
    parser.add_argument("--max-port", type=int, default=8082,
                        help="3ds Max MCP Server 端口 (默认 8082)")
    parser.add_argument("--dry-run", action="store_true",
                        help="只显示将要做的修改，不实际写入")

    args = parser.parse_args()

    print("=" * 50)
    print("  OpenClaw mcp-bridge 配置工具")
    print("=" * 50)

    # 构建 servers
    servers = {}
    if args.ue:
        servers["ue-editor"] = {
            "type": "websocket",
            "url": f"ws://127.0.0.1:{args.ue_port}",
        }
    if args.maya:
        servers["maya-primary"] = {
            "type": "websocket",
            "url": f"ws://127.0.0.1:{args.maya_port}",
        }
    if args.max:
        servers["max-primary"] = {
            "type": "websocket",
            "url": f"ws://127.0.0.1:{args.max_port}",
        }

    if not servers:
        print("  没有指定任何 server，使用默认 UE 配置")
        servers["ue-editor"] = {
            "type": "websocket",
            "url": "ws://127.0.0.1:8080",
        }

    config = load_config()

    if args.dry_run:
        print("\n  [DRY RUN] 将要添加的 servers:")
        for name, s in servers.items():
            print(f"    {name}: {s['url']}")
        print("\n  实际运行时去掉 --dry-run 参数")
        return

    # 备份
    backup = backup_config()

    # 合并
    changed = ensure_mcp_bridge(config, servers)

    if changed:
        save_config(config)
        print(f"\n  ✅ 配置已更新: {OPENCLAW_CONFIG}")
        print("  请运行 'openclaw gateway restart' 使配置生效")
    else:
        print("\n  ℹ️  配置无需修改（已是最新）")


if __name__ == "__main__":
    main()
