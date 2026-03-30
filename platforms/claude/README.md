# Claude Desktop 平台适配

ArtClaw Bridge 的 Claude Desktop 平台适配。通过 stdio→WebSocket 桥接器，让 Claude Desktop 能调用 DCC (UE/Maya/Max) 的 MCP 工具。

## 架构

```
Claude Desktop (stdio MCP Client)
  └── artclaw_stdio_bridge.py (stdio 进程)
        └── WebSocket → DCC MCP Server (8080/8081/8082)
```

## 配置

1. 运行 `install.bat` 或 `install.py --platform claude --openclaw`
2. 编辑 Claude Desktop 配置文件：
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
3. 参考 `config/claude-config-snippet.json`，将路径替换为实际路径

## 与 OpenClaw 的区别

| 特性 | OpenClaw | Claude Desktop |
|------|----------|----------------|
| 传输 | WebSocket (直连) | stdio (桥接) |
| 聊天面板 | DCC 内嵌 | Claude Desktop 窗口 |
| 工具调用 | mcp-bridge 插件转发 | stdio 桥接器转发 |
| 双向通信 | 聊天+工具 | 仅工具 |

## 限制

- Claude Desktop 不支持 DCC 内嵌聊天面板
- 用户在 Claude Desktop 窗口操作，DCC 内无对话界面
- 适合 "Claude Desktop 控制 DCC" 的单向模式

## 文件说明

| 文件 | 说明 |
|------|------|
| `artclaw_stdio_bridge.py` | stdio→WebSocket MCP 桥接器 |
| `config/claude-config-snippet.json` | Claude Desktop 配置模板 |
