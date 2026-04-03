"""
setup_lobster_config.py - 自动配置 LobsterAI mcp-bridge
=========================================================

将 mcp-bridge 插件的 servers 配置和 agent tools.allow 注入到
LobsterAI 的 openclaw.json 中。安全操作：合并前自动备份原文件。

LobsterAI 底层基于 OpenClaw，配置文件位于:
  %APPDATA%/LobsterAI/openclaw/state/openclaw.json

用法:
    python setup_lobster_config.py                    # UE 单实例
    python setup_lobster_config.py --maya              # 添加 Maya
    python setup_lobster_config.py --ue --maya --max   # 全部 DCC
    python setup_lobster_config.py --ue-port 8080      # 自定义端口
    python setup_lobster_config.py --dry-run            # 预览不写入
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time


def get_lobster_config_path() -> str:
    """获取 LobsterAI 的 openclaw.json 路径"""
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        appdata = os.path.expanduser("~/AppData/Roaming")
    return os.path.join(appdata, "LobsterAI", "openclaw", "state", "openclaw.json")


LOBSTER_CONFIG = get_lobster_config_path()


def load_config() -> dict:
    """加载 LobsterAI 配置文件"""
    if not os.path.exists(LOBSTER_CONFIG):
        return {}
    with open(LOBSTER_CONFIG, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict):
    """保存配置文件"""
    os.makedirs(os.path.dirname(LOBSTER_CONFIG), exist_ok=True)
    with open(LOBSTER_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def backup_config() -> str | None:
    """备份当前配置文件"""
    if os.path.exists(LOBSTER_CONFIG):
        ts = time.strftime("%Y%m%d_%H%M%S")
        backup = f"{LOBSTER_CONFIG}.backup_{ts}"
        shutil.copy2(LOBSTER_CONFIG, backup)
        print(f"  备份: {backup}")
        return backup
    return None


def ensure_mcp_bridge(config: dict, servers: dict) -> bool:
    """确保 mcp-bridge 插件配置包含指定的 servers"""
    changed = False

    # LobsterAI 的 plugins 结构已存在，确保 entries 有 mcp-bridge
    plugins = config.setdefault("plugins", {})
    entries = plugins.setdefault("entries", {})

    bridge = entries.setdefault("mcp-bridge", {"enabled": True})

    # 确保 enabled
    if not bridge.get("enabled"):
        bridge["enabled"] = True
        changed = True

    # 确保 config.servers 结构
    bridge_config = bridge.setdefault("config", {})
    existing_servers = bridge_config.setdefault("servers", {})

    # 合并新 servers（不覆盖已有配置）
    for name, server_def in servers.items():
        if name not in existing_servers:
            existing_servers[name] = server_def
            changed = True
            print(f"  添加 server: {name} -> {server_def['url']}")
        else:
            # 检查 URL 是否一致
            if existing_servers[name].get("url") != server_def["url"]:
                existing_servers[name] = server_def
                changed = True
                print(f"  更新 server: {name} -> {server_def['url']}")
            else:
                print(f"  跳过 server: {name} (已存在且一致)")

    return changed


def ensure_agent_tools(config: dict, server_names: list[str]) -> bool:
    """确保 agent 的 tools.allow 包含 MCP 工具通配符"""
    changed = False
    agents_list = config.get("agents", {}).get("list", [])

    for agent in agents_list:
        tools = agent.setdefault("tools", {})
        allow = tools.setdefault("allow", [])

        for server_name in server_names:
            wildcard = f"mcp_{server_name}_*"
            if wildcard not in allow:
                allow.append(wildcard)
                changed = True
                print(f"  agent '{agent.get('id', '?')}': 添加 {wildcard}")

    return changed


def main():
    parser = argparse.ArgumentParser(
        description="配置 LobsterAI mcp-bridge 插件（DCC MCP Server 接入）"
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
    print("  LobsterAI mcp-bridge 配置工具")
    print("=" * 50)
    print(f"  配置文件: {LOBSTER_CONFIG}")

    if not os.path.exists(LOBSTER_CONFIG):
        print()
        print("  [错误] LobsterAI 配置文件不存在!")
        print("  请先安装并启动一次 LobsterAI 客户端。")
        sys.exit(1)

    # 构建 servers
    servers = {}
    if args.ue:
        servers["ue-editor-agent"] = {
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
        servers["ue-editor-agent"] = {
            "type": "websocket",
            "url": "ws://127.0.0.1:8080",
        }

    if args.dry_run:
        print("\n  [DRY RUN] 将要添加的 servers:")
        for name, s in servers.items():
            print(f"    {name}: {s['url']}")
        print("\n  将要添加的 tools.allow 通配符:")
        for name in servers:
            print(f"    mcp_{name}_*")
        print("\n  实际运行时去掉 --dry-run 参数")
        return

    config = load_config()

    # 备份
    backup_config()

    # 合并 servers
    changed = ensure_mcp_bridge(config, servers)

    # 注入 agent tools.allow 通配符
    changed |= ensure_agent_tools(config, list(servers.keys()))

    if changed:
        save_config(config)
        print(f"\n  配置已更新: {LOBSTER_CONFIG}")
        print("  请重启 LobsterAI 客户端使配置生效")
    else:
        print("\n  配置无需修改（已是最新）")


if __name__ == "__main__":
    main()
