# OpenClaw MCP Bridge 插件 — 完整部署文档

## 概述

OpenClaw 不像 Claude Desktop / Cursor 那样在配置文件中直接支持 `mcpServers` 字段。
本方案通过编写一个 **OpenClaw 插件 (Plugin)**，在 Gateway 启动时通过 WebSocket 连接到外部 MCP Server，
自动发现并注册其提供的工具 (tools)，使 Agent 能原生调用这些工具。

### 架构示意

```
┌─────────────┐    WebSocket     ┌──────────────────┐
│  OpenClaw   │ ◄──────────────► │  MCP Server      │
│  Gateway    │   JSON-RPC 2.0   │  (ws://...:8080) │
│             │                  │                  │
│ ┌─────────┐ │                  │  tools/list      │
│ │mcp-     │ │  ── initialize → │  tools/call      │
│ │bridge   │ │  ← tools/list ── │                  │
│ │plugin   │ │  ── tools/call → │                  │
│ └─────────┘ │  ← result ────── │                  │
│             │                  │                  │
│ ┌─────────┐ │                  └──────────────────┘
│ │ Agent   │ │
│ │ (LLM)   │ │  调用 mcp_my-mcp-server_xxx
│ └─────────┘ │
└─────────────┘
```

---

## 前提条件

- **OpenClaw** 已安装并能正常运行 (`openclaw --version`)
- **Node.js** 18+ (OpenClaw 运行环境)
- 一个运行在 `ws://127.0.0.1:8080` 的 MCP Server (如果还没有，见文末「附录：示例 MCP Server」)

---

## 步骤 1：创建插件目录

在 OpenClaw 全局扩展目录下创建插件文件夹：

```bash
mkdir -p ~/.openclaw/extensions/mcp-bridge
```

Windows:
```cmd
mkdir "%USERPROFILE%\.openclaw\extensions\mcp-bridge"
```

---

## 步骤 2：创建插件清单文件

将 `mcp-bridge/openclaw.plugin.json` 复制到插件目录：

```bash
cp mcp-bridge/openclaw.plugin.json ~/.openclaw/extensions/mcp-bridge/
```

文件内容（`openclaw.plugin.json`）：

```json
{
  "id": "mcp-bridge",
  "name": "MCP Bridge",
  "description": "Bridge external MCP servers (WebSocket/stdio) into OpenClaw agent tools",
  "version": "1.0.0",
  "configSchema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "servers": {
        "type": "object",
        "description": "MCP server definitions keyed by server name",
        "additionalProperties": {
          "type": "object",
          "properties": {
            "type": {
              "type": "string",
              "enum": ["websocket", "stdio"],
              "description": "Transport type"
            },
            "url": {
              "type": "string",
              "description": "WebSocket URL (for type=websocket)"
            },
            "command": {
              "type": "string",
              "description": "Command to run (for type=stdio)"
            },
            "args": {
              "type": "array",
              "items": { "type": "string" },
              "description": "Command arguments (for type=stdio)"
            },
            "enabled": {
              "type": "boolean",
              "default": true,
              "description": "Whether this server is enabled"
            }
          },
          "required": ["type"]
        }
      }
    }
  },
  "uiHints": {
    "servers": {
      "label": "MCP Servers",
      "placeholder": "Add MCP server configurations"
    }
  }
}
```

**说明：**
- `id`: 插件唯一标识，后续在 `openclaw.json` 中引用
- `configSchema`: 定义插件接受的配置结构（JSON Schema），支持配置验证
- 支持 `websocket` 和 `stdio` 两种传输类型（当前实现了 websocket）

---

## 步骤 3：创建插件主代码

将 `mcp-bridge/index.ts` 复制到插件目录：

```bash
cp mcp-bridge/index.ts ~/.openclaw/extensions/mcp-bridge/
```

**插件核心逻辑说明：**

| 模块 | 功能 |
|------|------|
| `McpWebSocketClient` | WebSocket MCP 客户端，实现 MCP 协议的连接、握手、工具发现和调用 |
| `createJsonRpcRequest` | 构建 JSON-RPC 2.0 请求消息 |
| `parseJsonRpcResponse` | 解析 JSON-RPC 2.0 响应 |
| 插件入口 `export default` | 读取配置 → 连接 MCP Server → 注册工具到 OpenClaw Agent |

**MCP 协议握手流程：**

1. 客户端发送 `initialize` 请求 (protocolVersion: `2024-11-05`)
2. 服务端返回 `serverInfo` + `capabilities`
3. 客户端发送 `notifications/initialized` 通知
4. 客户端调用 `tools/list` 发现可用工具
5. Agent 调用时通过 `tools/call` 转发到 MCP Server

**断线重连：**
- 最多重试 5 次
- 重连间隔递增 (3s → 6s → 9s → 12s → 15s)

---

## 步骤 4：配置 `openclaw.json`

编辑 `~/.openclaw/openclaw.json`，在 `plugins` 部分添加以下配置：

```jsonc
{
  // ... 其他配置 ...

  "plugins": {
    "allow": ["mcp-bridge"],     // ← 将插件加入信任列表
    "entries": {
      // ... 其他插件 ...

      "mcp-bridge": {            // ← 启用插件并配置 MCP 服务器
        "enabled": true,
        "config": {
          "servers": {
            "my-mcp-server": {   // ← 服务器名称（可自定义）
              "type": "websocket",
              "url": "ws://127.0.0.1:8080"
            }
          }
        }
      }
    }
  }
}
```

### 配置项说明

| 路径 | 类型 | 说明 |
|------|------|------|
| `plugins.allow` | `string[]` | 受信任的插件 ID 列表，防止安全警告 |
| `plugins.entries.mcp-bridge.enabled` | `boolean` | 是否启用此插件 |
| `plugins.entries.mcp-bridge.config.servers` | `object` | MCP 服务器定义，key 为服务器名称 |
| `servers.<name>.type` | `"websocket"` | 传输协议类型 |
| `servers.<name>.url` | `string` | WebSocket 地址 |
| `servers.<name>.enabled` | `boolean` | 是否启用此服务器（默认 `true`） |

### 多服务器配置示例

```json
{
  "config": {
    "servers": {
      "renderdoc": {
        "type": "websocket",
        "url": "ws://127.0.0.1:8080"
      },
      "database-tools": {
        "type": "websocket",
        "url": "ws://127.0.0.1:9090"
      },
      "disabled-server": {
        "type": "websocket",
        "url": "ws://127.0.0.1:7070",
        "enabled": false
      }
    }
  }
}
```

---

## 步骤 5：验证配置

```bash
# 验证配置文件语法
openclaw config validate

# 查看插件是否被识别
openclaw plugins list
```

期望输出包含：
```
│ MCP Bridge   │ mcp-bridge │ loaded │ global:mcp-bridge/index.ts │ 1.0.0 │
```

---

## 步骤 6：启动/重启 Gateway

```bash
# 重启 Gateway 使配置生效
openclaw gateway --force
```

如果 MCP Server 已在运行，Gateway 日志中会看到：
```
[mcp-bridge] Connected to MCP server "my-mcp-server" at ws://127.0.0.1:8080
[mcp-bridge] Initialized "my-mcp-server": <server-name> v<version>
[mcp-bridge] Discovered N tools from "my-mcp-server"
[mcp-bridge] Registered tool: mcp_my-mcp-server_tool1
[mcp-bridge] Registered tool: mcp_my-mcp-server_tool2
[mcp-bridge] Total tools registered: N
```

---

## 工具命名规则

MCP Server 中的工具在注册到 OpenClaw 后，命名格式为：

```
mcp_<服务器名称>_<原始工具名>
```

例如 MCP Server 名为 `my-mcp-server`，提供工具 `get_weather`，则在 OpenClaw 中名为：

```
mcp_my-mcp-server_get_weather
```

Agent 在对话中可直接调用这些工具。

---

## 为特定 Agent 启用 MCP 工具

如果你的 Agent 使用了 `tools.allow` 白名单，需要将 MCP 工具加入：

```jsonc
{
  "agents": {
    "list": [
      {
        "id": "my-agent",
        "tools": {
          "allow": [
            // ... 其他工具 ...
            "mcp-bridge"                       // 方式1：启用该插件的所有工具
            // "mcp_my-mcp-server_get_weather" // 方式2：指定具体工具名
          ]
        }
      }
    ]
  }
}
```

---

## 故障排查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| `Unrecognized key: "mcpServers"` | OpenClaw 不支持顶层 mcpServers 字段 | 使用本插件方案，配置在 `plugins.entries` 下 |
| `Config path not found` | 配置路径错误 | 检查 JSON 结构和缩进 |
| `WebSocket error ... [object ErrorEvent]` | MCP Server 未启动或地址错误 | 确认 MCP Server 已运行并监听正确端口 |
| `No tools registered` | MCP Server 未返回工具列表 | 检查 MCP Server 的 `capabilities.tools` 是否为 `true` |
| `Max reconnect attempts reached` | 网络不可达 | 检查防火墙、端口占用 |
| 插件未显示 `loaded` | 插件文件路径或 manifest 有误 | 运行 `openclaw plugins doctor` 诊断 |

---

## 文件清单

本目录包含以下文件：

```
openclaw-mcp-bridge/
├── README.md                          # 本文档
├── mcp-bridge/
│   ├── openclaw.plugin.json           # 插件清单 (manifest)
│   └── index.ts                       # 插件主代码
└── openclaw-config-snippet.json       # openclaw.json 配置片段示例
```

部署目标路径：

```
~/.openclaw/extensions/mcp-bridge/
├── openclaw.plugin.json
└── index.ts
```

---

## 附录：示例 MCP Server (用于测试)

如果你还没有 MCP Server，可以用以下 Node.js 代码快速搭建一个测试用的 WebSocket MCP Server：

```javascript
// test-mcp-server.js
// 运行: node test-mcp-server.js

const { WebSocketServer } = require("ws");

const wss = new WebSocketServer({ port: 8080 });
console.log("MCP Server listening on ws://127.0.0.1:8080");

wss.on("connection", (ws) => {
  console.log("Client connected");

  ws.on("message", (data) => {
    const msg = JSON.parse(data.toString());
    console.log("Received:", msg.method || msg);

    // Handle JSON-RPC requests
    if (msg.method === "initialize") {
      ws.send(JSON.stringify({
        jsonrpc: "2.0",
        id: msg.id,
        result: {
          protocolVersion: "2024-11-05",
          capabilities: { tools: {} },
          serverInfo: { name: "test-server", version: "1.0.0" },
        },
      }));
    } else if (msg.method === "tools/list") {
      ws.send(JSON.stringify({
        jsonrpc: "2.0",
        id: msg.id,
        result: {
          tools: [
            {
              name: "hello",
              description: "Say hello to someone",
              inputSchema: {
                type: "object",
                properties: {
                  name: { type: "string", description: "Name to greet" },
                },
                required: ["name"],
              },
            },
            {
              name: "add",
              description: "Add two numbers",
              inputSchema: {
                type: "object",
                properties: {
                  a: { type: "number" },
                  b: { type: "number" },
                },
                required: ["a", "b"],
              },
            },
          ],
        },
      }));
    } else if (msg.method === "tools/call") {
      const { name, arguments: args } = msg.params;
      let resultText = "";
      if (name === "hello") {
        resultText = `Hello, ${args.name}! 👋`;
      } else if (name === "add") {
        resultText = `${args.a} + ${args.b} = ${args.a + args.b}`;
      } else {
        resultText = `Unknown tool: ${name}`;
      }
      ws.send(JSON.stringify({
        jsonrpc: "2.0",
        id: msg.id,
        result: {
          content: [{ type: "text", text: resultText }],
        },
      }));
    }
    // Ignore notifications (no id)
  });

  ws.on("close", () => console.log("Client disconnected"));
});
```

先安装 ws 依赖并启动：
```bash
npm install ws
node test-mcp-server.js
```

然后重启 OpenClaw Gateway，即可在 Agent 中使用 `mcp_my-mcp-server_hello` 和 `mcp_my-mcp-server_add` 两个工具。