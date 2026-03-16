# OpenClaw Phase 0 — 接入预设与工程初始化

> **路线图对应**：阶段 0：环境预设与工程初始化
> **集成方案对应**：§8 Phase 0

---

## 阶段目标

让 OpenClaw 能识别 UE Agent、完成最小连接、具备连接可见性和基础日志能力。

---

## Feature 清单与实现状态

### `feature/openclaw-config-bootstrap` ✅ 已完成

**需求**：提供 OpenClaw 接入示例配置，区分 stdio / WebSocket 两种最小配置。

**实现**：

| 产物 | 路径 | 说明 |
|------|------|------|
| Bridge 插件清单 | `openclaw-mcp-bridge/mcp-bridge/openclaw.plugin.json` | 定义 configSchema，支持 websocket / stdio |
| Bridge 主代码 | `openclaw-mcp-bridge/mcp-bridge/index.ts` | WebSocket 客户端，自动发现 tools 并注册到 OpenClaw |
| 配置片段 | `openclaw-mcp-bridge/openclaw-config-snippet.json` | 可直接合并到 `~/.openclaw/openclaw.json` |
| 部署文档 | `openclaw-mcp-bridge/README.md` | 完整 6 步部署流程 |

**当前默认配置（WebSocket）**：
```json
{
  "plugins": {
    "allow": ["mcp-bridge"],
    "entries": {
      "mcp-bridge": {
        "enabled": true,
        "config": {
          "servers": {
            "ue-editor-agent": {
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

**验收**：
- [x] 配置文件能通过 `openclaw config validate`
- [x] 支持 WebSocket 传输（默认）
- [x] 配置路径明确指向 `openclaw-mcp-bridge`
- [ ] stdio 传输待阶段 3+ 实现

---

### `feature/openclaw-connection-status` ✅ 已完成

**需求**：OpenClaw 连接状态接入 UUEAgentSubsystem，工具栏图标联动。

**实现**：

| 模块 | 文件 | 说明 |
|------|------|------|
| C++ Subsystem | `UEAgentSubsystem.h/cpp` | `SetConnectionStatus(bool)` / `GetConnectionStatus()` / `OnConnectionStatusChangedNative` 委托 |
| Python 同步 | `init_unreal.py::sync_connection_state()` | WebSocket 客户端连接/断开时调用 |
| MCP Server | `mcp_server.py::_connection_handler()` | 有客户端连接时 `sync_connection_state(True)`，全部断开时 `sync_connection_state(False)` |
| Dashboard UI | `UEAgentDashboard.cpp` | 可折叠状态栏实时显示 `● Connected` / `○ Disconnected` + 服务器地址 |

**验收**：
- [x] 有 OpenClaw Bridge 连接时 Dashboard 显示 Connected
- [x] 断开后自动切换为 Disconnected
- [x] 日志输出连接/断开事件

---

### `feature/openclaw-dependency-bootstrap` ✅ 已完成

**需求**：明确 OpenClaw 接入依赖，补充桥接层依赖安装指引。

**实现**：

| 依赖类型 | 具体内容 | 管理方式 |
|----------|----------|----------|
| UE 插件 Python 依赖 | `websockets>=12.0`, `pydantic>=2.0` | `dependency_manager.py` 自动 `pip install --target` 到 `Content/Python/Lib/` |
| OpenClaw Bridge 依赖 | Node.js 18+, `ws` npm 包 | 通过 OpenClaw 运行时自动管理 |
| 路径隔离 | 插件私有 `sys.path` 优先 | `init_unreal.py` 启动时注入 |

**验收**：
- [x] UE 插件首次启动自动安装 Python 依赖
- [x] 不污染引擎自带 Python 环境
- [x] `import websockets` 在 UE Python 环境中可用

---

### `feature/openclaw-log-observability` ✅ 已完成

**需求**：打通 OpenClaw 请求到 UE Output Log 的链路，记录请求 ID / 时间 / 结果。

**实现**：

| 模块 | 文件 | 说明 |
|------|------|------|
| 日志系统 | `init_unreal.py::UELogger` | 带颜色前缀的 `LogUEAgent` 分类，支持 `.info()` / `.mcp()` / `.mcp_error()` |
| MCP 调用日志 | `init_unreal.py::log_mcp_call` | 装饰器，自动记录每次 JSON-RPC 请求的方法名、参数摘要、耗时 |
| 异常钩子 | `init_unreal.py::_setup_exception_hooks()` | 全局异常自动写入 UE Output Log |

**日志格式示例**：
```
[UEAgent][MCP] Client connected: 127.0.0.1:54321 (total: 1)
[UEAgent][MCP] Initialize request from OpenClaw (protocol: 2024-11-05)
[UEAgent][MCP] tools/list -> 4 tools
[UEAgent][MCP] tools/call -> run_ue_python({code: "import unreal..."})
[UEAgent][MCP] Tool execution completed in 0.023s
```

**验收**：
- [x] OpenClaw 每次请求都能在 UE Output Log 中追踪
- [x] 包含方法名、时间戳
- [x] 错误信息可读

---

## 阶段验收总结

| 验收项 | 状态 |
|--------|------|
| OpenClaw 可发现 UE Agent | ✅ 通过 mcp-bridge 插件连接 |
| `tools/list` 可返回基础能力 | ✅ 返回 `run_ue_python` 等工具 |
| UE 插件 UI 能反映连接状态 | ✅ Dashboard 实时显示 |
| 日志可追踪一次完整连接过程 | ✅ UELogger + log_mcp_call |
