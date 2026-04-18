#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup_cursor_config.py — Cursor MCP 自动配置
==============================================

自动为 Cursor 配置 ArtClaw MCP Server。
写入 ~/.cursor/mcp.json（全局）或 {project}/.cursor/mcp.json（项目级）。

用法：
    python setup_cursor_config.py [--ue] [--maya] [--max] [--blender]
                                   [--houdini] [--sp] [--sd] [--comfyui]
                                   [--all] [--global] [--project]

默认：--ue --maya --max（仅配置最常用的 DCC），写入全局配置
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# ArtClaw Bridge 项目根目录
BRIDGE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# stdio 桥接脚本路径
STDIO_BRIDGE = os.path.join(BRIDGE_ROOT, "platforms", "common", "artclaw_stdio_bridge.py")

# DCC 名称 → 端口映射
DCC_SERVERS = {
    "ue":       ("artclaw-ue",       8080),
    "maya":     ("artclaw-maya",     8081),
    "max":      ("artclaw-max",      8082),
    "blender":  ("artclaw-blender",  8083),
    "houdini":  ("artclaw-houdini",  8084),
    "sp":       ("artclaw-sp",       8085),
    "sd":       ("artclaw-sd",       8086),
    "comfyui":  ("artclaw-comfyui",  8087),
}


def _write_cursor_config(servers: dict, config_path: str) -> bool:
    """写入 Cursor MCP 配置文件。"""
    # 读取现有配置
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass

    # 确保 mcpServers 键存在
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    # 添加/更新服务器配置
    for server_name, port in servers.items():
        config["mcpServers"][server_name] = {
            "command": "python",
            "args": [STDIO_BRIDGE.replace("\\", "/"), "--port", str(port)],
            "env": {},
        }

    # 写入配置文件
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    return True


def main():
    parser = argparse.ArgumentParser(description="Cursor MCP 自动配置")
    parser.add_argument("--ue", action="store_true", help="配置 UE MCP Server")
    parser.add_argument("--maya", action="store_true", help="配置 Maya MCP Server")
    parser.add_argument("--max", action="store_true", help="配置 3ds Max MCP Server")
    parser.add_argument("--blender", action="store_true", help="配置 Blender MCP Server")
    parser.add_argument("--houdini", action="store_true", help="配置 Houdini MCP Server")
    parser.add_argument("--sp", action="store_true", help="配置 Substance Painter MCP Server")
    parser.add_argument("--sd", action="store_true", help="配置 Substance Designer MCP Server")
    parser.add_argument("--comfyui", action="store_true", help="配置 ComfyUI MCP Server")
    parser.add_argument("--all", action="store_true", help="配置所有 DCC MCP Server")
    parser.add_argument("--global", dest="use_global", action="store_true",
                        help="写入全局配置 (~/.cursor/mcp.json)，默认行为")
    parser.add_argument("--project", action="store_true",
                        help="写入项目级配置 ({project}/.cursor/mcp.json)")
    args = parser.parse_args()

    # 确定要配置的 DCC
    if args.all:
        selected_dcc = list(DCC_SERVERS.keys())
    else:
        selected_dcc = []
        for dcc in DCC_SERVERS:
            if getattr(args, dcc, False):
                selected_dcc.append(dcc)
        if not selected_dcc:
            # 默认：ue + maya + max
            selected_dcc = ["ue", "maya", "max"]

    print("=" * 60)
    print("  Cursor MCP 自动配置")
    print("=" * 60)
    print(f"\n  Bridge 根目录: {BRIDGE_ROOT}")
    print(f"  stdio 桥接脚本: {STDIO_BRIDGE}")
    print(f"  要配置的 DCC: {', '.join(selected_dcc)}")

    # 检查 stdio 桥接脚本
    if not os.path.exists(STDIO_BRIDGE):
        print(f"\n  ❌ 错误: artclaw_stdio_bridge.py 不存在: {STDIO_BRIDGE}")
        sys.exit(1)

    # 确定配置文件路径
    if args.project:
        config_path = os.path.join(os.getcwd(), ".cursor", "mcp.json")
        label = "项目级"
    else:
        config_path = os.path.join(os.path.expanduser("~"), ".cursor", "mcp.json")
        label = "全局"

    print(f"  配置级别: {label}")
    print(f"  配置路径: {config_path}")
    print()

    # 构建服务器配置
    servers = {}
    for dcc in selected_dcc:
        server_name, port = DCC_SERVERS[dcc]
        servers[server_name] = port

    # 写入配置
    if _write_cursor_config(servers, config_path):
        print(f"  ✅ {label}配置已写入: {config_path}")
        for server_name, port in servers.items():
            print(f"     {server_name} → 端口 {port}")
    else:
        print(f"  ❌ 写入配置文件失败")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  配置完成！请重启 Cursor 以加载新的 MCP Server。")
    print("=" * 60)


if __name__ == "__main__":
    main()
