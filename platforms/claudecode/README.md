# Claude Code 平台适配

ArtClaw Bridge 的 Claude Code 平台适配。通过 stdio→WebSocket 桥接器，让 Claude Code 能调用 DCC (UE/Maya/Max/Blender/Houdini/SP/SD/ComfyUI) 的 MCP 工具。

## ⚠️ 接入模式限制

Claude Code 是 **MCP-only** 模式，仅支持工具调用，**不支持 DCC 内嵌聊天面板**。

| 能力 | Claude Code | OpenClaw / LobsterAI |
|------|-------------|---------------------|
| 工具调用（run_python 等） | ✅ 通过 MCP stdio bridge | ✅ 通过 WebSocket MCP |
| DCC 内嵌聊天面板 | ❌ 不支持 | ✅ 支持 |
| AI 多轮对话操作 DCC | ❌ 仅在终端内对话 | ✅ DCC 内直接对话 |
| Skill 上下文注入 | ❌ 无（Claude Code 不读 SKILL.md） | ✅ OpenClaw 自动加载 |
| Agent 切换 | ❌ 固定用 Claude 模型 | ✅ 可选多个 Agent |
| 消息历史/会话管理 | ❌ Claude Code 自行管理 | ✅ Gateway 统一管理 |
| 停止/取消请求 | ❌ 不可从 DCC 侧控制 | ✅ DCC 面板可停止 |

### 适用场景

- 已在终端使用 Claude Code，顺手调用 DCC 执行脚本
- 不需要 DCC 内嵌 AI 聊天面板
- 仅需简单的工具调用（如批量处理资产、查询场景信息）

### 推荐

如需完整的 AI + DCC 交互体验（内嵌聊天面板、Skill 自动加载、多轮对话操作 DCC），建议使用带 Gateway 的平台：**OpenClaw** 或 **LobsterAI**。

## 架构

```
Claude Code CLI (stdio MCP Client)
  └── artclaw_stdio_bridge.py (stdio→WebSocket bridge)
        └── DCC MCP Server (port 8080-8087)
```

Claude Code 使用自己的 Claude 模型，MCP 仅提供工具调用能力。
DCC 端的 AI 聊天面板无法与 Claude Code 的 AI 通信。

## 快速配置

### 方式一：使用 `claude mcp add` CLI（推荐）

```bash
claude mcp add artclaw-ue -- python /path/to/artclaw_stdio_bridge.py --port 8080
claude mcp add artclaw-maya -- python /path/to/artclaw_stdio_bridge.py --port 8081
claude mcp add artclaw-max -- python /path/to/artclaw_stdio_bridge.py --port 8082
claude mcp add artclaw-blender -- python /path/to/artclaw_stdio_bridge.py --port 8083
claude mcp add artclaw-houdini -- python /path/to/artclaw_stdio_bridge.py --port 8084
claude mcp add artclaw-sp -- python /path/to/artclaw_stdio_bridge.py --port 8085
claude mcp add artclaw-sd -- python /path/to/artclaw_stdio_bridge.py --port 8086
claude mcp add artclaw-comfyui -- python /path/to/artclaw_stdio_bridge.py --port 8087
```

### 方式二：使用自动配置脚本

```bash
python platforms/claudecode/setup_claudecode_config.py
```

### 方式三：手动编辑配置文件

编辑 `~/.claude.json`（全局）或 `.mcp.json`（项目级），参考 `config/claude-code-config-snippet.json`。

## 与 Claude Desktop 的区别

| 特性 | Claude Desktop | Claude Code |
|------|----------------|-------------|
| 运行环境 | 桌面应用 | 终端 CLI |
| 配置路径 | `%APPDATA%\Claude\claude_desktop_config.json` | `~/.claude.json` 或 `.mcp.json` |
| 配置方式 | 手动编辑 JSON | `claude mcp add` CLI 或编辑 JSON |
| 项目级配置 | 不支持 | 支持（`.mcp.json`） |

两者均为 MCP-only 模式，局限性相同（见上表）。

## DCC 端口映射

| DCC 软件 | 端口 | MCP Server 名称 |
|----------|------|-----------------|
| Unreal Engine | 8080 | artclaw-ue |
| Maya | 8081 | artclaw-maya |
| 3ds Max | 8082 | artclaw-max |
| Blender | 8083 | artclaw-blender |
| Houdini | 8084 | artclaw-houdini |
| Substance Painter | 8085 | artclaw-sp |
| Substance Designer | 8086 | artclaw-sd |
| ComfyUI | 8087 | artclaw-comfyui |

## 文件说明

| 文件 | 说明 |
|------|------|
| `claudecode_adapter.py` | Claude Code 平台适配器 |
| `config/claude-code-config-snippet.json` | MCP 配置模板 |
| `setup_claudecode_config.py` | 自动配置脚本 |
