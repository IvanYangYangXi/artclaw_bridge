#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup_claudecode_config.py — Claude Code MCP 自动配置
======================================================

自动为 Claude Code 配置 ArtClaw MCP Server。

优先使用 `claude mcp add` CLI 命令（如果可用），
否则回退到直接写入 ~/.claude.json 配置文件。

用法：
    python setup_claudecode_config.py [--ue] [--maya] [--max] [--blender]
                                       [--houdini] [--sp] [--sd] [--comfyui]
                                       [--all] [--global] [--project]

默认：--ue --maya --max（仅配置最常用的 DCC）
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
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


def _has_claude_cli() -> bool:
    """检查 claude CLI 是否可用。"""
    return shutil.which("claude") is not None


def _add_via_cli(server_name: str, port: int) -> bool:
    """使用 `claude mcp add` CLI 命令添加 MCP Server。"""
    try:
        cmd = [
            "claude", "mcp", "add", server_name,
            "--transport", "stdio",
            "--",
            "python", STDIO_BRIDGE, "--port", str(port),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            print(f"  ✅ {server_name} (端口 {port}) — 已通过 claude CLI 添加")
            return True
        else:
            print(f"  ⚠️  {server_name} — claude CLI 返回错误: {result.stderr.strip()}")
            return False
    except FileNotFoundError:
        print(f"  ⚠️  {server_name} — claude CLI 不可用")
        return False
    except subprocess.TimeoutExpired:
        print(f"  ⚠️  {server_name} — claude CLI 超时")
        return False
    except Exception as e:
        print(f"  ⚠️  {server_name} — 异常: {e}")
        return False


def _add_via_config_file(servers: dict, config_path: str) -> bool:
    """直接写入 JSON 配置文件。"""
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
    parser = argparse.ArgumentParser(description="Claude Code MCP 自动配置")
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
                        help="写入全局配置 (~/.claude.json)，默认行为")
    parser.add_argument("--project", action="store_true",
                        help="写入项目级配置 (.mcp.json)")
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
    print("  Claude Code MCP 自动配置")
    print("=" * 60)
    print(f"\n  Bridge 根目录: {BRIDGE_ROOT}")
    print(f"  stdio 桥接脚本: {STDIO_BRIDGE}")
    print(f"  要配置的 DCC: {', '.join(selected_dcc)}")

    # 检查 stdio 桥接脚本
    if not os.path.exists(STDIO_BRIDGE):
        print(f"\n  ❌ 错误: artclaw_stdio_bridge.py 不存在: {STDIO_BRIDGE}")
        sys.exit(1)

    # 尝试使用 claude CLI
    use_cli = _has_claude_cli()
    if use_cli:
        print(f"\n  ✅ 检测到 claude CLI，使用 `claude mcp add` 命令")
    else:
        print(f"\n  ℹ️  未检测到 claude CLI，将直接写入配置文件")

    print()

    if use_cli and not args.project:
        # 使用 claude CLI 逐个添加
        success_count = 0
        for dcc in selected_dcc:
            server_name, port = DCC_SERVERS[dcc]
            if _add_via_cli(server_name, port):
                success_count += 1
        print(f"\n  完成: {success_count}/{len(selected_dcc)} 个 MCP Server 已配置")
    else:
        # 直接写入配置文件
        if args.project:
            config_path = os.path.join(os.getcwd(), ".mcp.json")
            label = "项目级"
        else:
            config_path = os.path.join(os.path.expanduser("~"), ".claude.json")
            label = "全局"

        servers = {}
        for dcc in selected_dcc:
            server_name, port = DCC_SERVERS[dcc]
            servers[server_name] = port

        if _add_via_config_file(servers, config_path):
            print(f"  ✅ {label}配置已写入: {config_path}")
            for server_name, port in servers.items():
                print(f"     {server_name} → 端口 {port}")
        else:
            print(f"  ❌ 写入配置文件失败")
            sys.exit(1)

    print("\n" + "=" * 60)
    print("  配置完成！请确认 DCC 端 MCP Server 已启动。")
    print("=" * 60)


if __name__ == "__main__":
    main()
