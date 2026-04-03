# LobsterAI (有道龙虾) 平台适配

ArtClaw Bridge 的 LobsterAI 平台适配。LobsterAI 底层基于 OpenClaw，
通过内置的 mcp-bridge 插件连接 DCC MCP Server。

## 架构

```
LobsterAI 客户端
  └── 内置 OpenClaw Gateway (端口 18790)
        └── mcp-bridge 插件 (内置)
              └── WebSocket → DCC MCP Server (8080/8081/8082)
                    └── run_ue_python / run_python
```

## 与 OpenClaw 的区别

| 特性 | OpenClaw | LobsterAI |
|------|----------|-----------|
| 配置根目录 | `~/.openclaw/` | `%APPDATA%/LobsterAI/openclaw/` |
| 配置文件 | `~/.openclaw/openclaw.json` | `%APPDATA%/LobsterAI/openclaw/state/openclaw.json` |
| Gateway 端口 | 18789 | 18790 |
| Skills 目录 | `~/.openclaw/skills/` | `%APPDATA%/LobsterAI/SKILLs/` |
| mcp-bridge | 需手动部署插件 | 已内置 |
| 聊天面板 | DCC 内嵌 | LobsterAI 客户端窗口 |
| 默认模型 | 可配置 | qwen3.5-plus-YoudaoInner |

## 安装

```bash
# 安装 Maya 插件 + LobsterAI 平台配置
python install.py --maya --openclaw --platform lobster

# 安装 UE 插件 + LobsterAI 平台配置
python install.py --ue --ue-project "C:\path\to\proj" --openclaw --platform lobster

# 全部安装
python install.py --all --ue-project "C:\path\to\proj" --platform lobster
```

## 配置注入

`setup_lobster_config.py` 会自动向 LobsterAI 的 openclaw.json 注入：
1. mcp-bridge servers 配置（UE/Maya/Max 的 WebSocket 地址）
2. Agent tools.allow 通配符（确保 AI 能调用 MCP 工具）

## MCP 端口复用

LobsterAI 和 OpenClaw 连接同一组 DCC MCP Server 端口（8080/8081/8082）。
WebSocket 是多连接兼容的，JSON-RPC 请求-响应通过 id 匹配，两个 Gateway
同时连接同一个 MCP Server 不会冲突。

## Skills 独立安装

LobsterAI 的 Skills 安装到 `%APPDATA%/LobsterAI/SKILLs/`，不与 OpenClaw
的 `~/.openclaw/skills/` 共享。LobsterAI 通过 `skills.load.extraDirs` 配置
扫描该目录。

## 文件说明

| 文件 | 说明 |
|------|------|
| `setup_lobster_config.py` | 自动配置 LobsterAI 的 openclaw.json |
| `README.md` | 本文档 |
