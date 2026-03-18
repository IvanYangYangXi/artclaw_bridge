# OpenClaw Gateway 转发流程 — 开发路线图

> **目标**：将 UE Chat Panel ↔ OpenClaw Gateway ↔ AI Agent ↔ MCP Server 的完整转发链路从"能用"打磨到"好用、稳定、可维护、可复用"。
>
> **前提**：当前转发流程已跑通（阶段 3.7），本路线图聚焦于**加固、优化、DCC 复用、部署体验**。

---

## 当前状态盘点

### ✅ 已完成

| 组件 | 文件 | 状态 |
|------|------|------|
| UE 内 MCP Server | `mcp_server.py` (~32KB) | 稳定运行，22 个 MCP 工具 |
| OpenClaw Gateway Bridge | `openclaw_bridge.py` (~46KB) | 基本功能完成，含断连重连/流式/cancel |
| mcp-bridge 插件 | `mcp-bridge/index.ts` (~11KB) | 稳定，自动重连+ping keepalive |
| C++ Chat Panel | `UEAgentDashboard.cpp` (~60KB) | 含 /connect /disconnect /cancel /status |
| 部署文档 | `openclaw-mcp-bridge/README.md` | 完整步骤，含配置模板 |

### 🔶 已知问题

1. **启动时序**：Gateway 先启动但 UE 没开 → mcp-bridge 工具标记为 unknown → 需重启 Gateway
2. **数据回传**：Python → 临时文件 → C++ FTSTicker 轮询，延迟 ~500ms，不够优雅
3. **会话管理**：session_key 管理简陋，/new 靠清空 key 实现
4. **openclaw_bridge.py 体积**：46KB 单文件过大，混杂通信/诊断/上下文收集
5. **C++ Dashboard 耦合**：60KB 中约 200 行直接调用 Python bridge 函数，无抽象层
6. **DCC 复用性**：openclaw_bridge.py 内含 UE 特有逻辑（unreal 模块引用），Maya/Max 无法直接用

---

## 阶段划分

### 阶段 G1：加固与稳定性 (Hardening) ✅

> **目标**：解决已知痛点，让转发链路在生产环境中可靠运行
> **实际工时**：~2 小时 | **完成日期**：2026-03-18

- [x] **G1.1 启动时序修复 — mcp-bridge 延迟发现** ✅
  - mcp-bridge 插件初始连接失败不再阻塞，后台自动重试
  - 重连后通过 `onToolsDiscovered` 回调自动注册工具
  - 工具执行时检查连接状态，离线返回友好中文错误
  - 插件版本 1.0.0 → 1.1.0

- [x] **G1.2 连接状态同步强化** ✅
  - Python bridge 连接/断连/关闭时写入 `_bridge_status.json`
  - C++ Dashboard 新增 `BridgeStatusPollHandle` 持续轮询（2s 间隔）
  - 状态变更自动更新 `UUEAgentSubsystem`（驱动图标颜色）

- [x] **G1.3 流式响应稳定性** ✅ (评估后确认现有机制已足够)
  - JSONL + 累积文本机制：中间 delta 丢失不影响最终显示
  - 不完整 JSON 行被 `FJsonSerializer::Deserialize` 静默跳过

- [x] **G1.4 错误消息本地化** ✅
  - `openclaw_bridge.py` 所有用户可见错误从英文改为中文
  - `[Error]` → `[错误]`, `[Connection lost]` → `[连接中断]` 等

---

### 阶段 G2：重构与解耦 (Refactoring)

> **目标**：拆分大文件，抽象平台无关层，为 DCCClawBridge 复用做准备
> **预估工时**：4~5 天

- [ ] **G2.1 openclaw_bridge.py 拆分**
  - **现状**：46KB 单文件，混杂多个职责
  - **目标结构**：
    ```
    openclaw-mcp-bridge/
    ├── bridge_core.py          # 核心 WebSocket RPC 通信（平台无关）
    ├── bridge_ue.py            # UE 特有适配（文件回传、unreal 日志）
    ├── bridge_config.py        # 配置加载（openclaw.json 解析）
    ├── bridge_diagnostics.py   # diagnose_connection + health 相关
    ├── context_collector.py    # _collect_and_save_context（UE 特有）
    └── __init__.py             # 向后兼容，re-export 所有公开函数
    ```
  - **原则**：`bridge_core.py` 完全不依赖 `unreal` 模块，Maya/Max 直接复用
  - **验收**：拆分后 UE 功能不变，`from openclaw_bridge import connect, send_message` 向后兼容

- [ ] **G2.2 C++ 平台通信抽象层**
  - **现状**：Dashboard 直接拼 Python 字符串调用 bridge 函数
  - **方案**：新增 `IAgentPlatformBridge` C++ 接口
    ```cpp
    class IAgentPlatformBridge {
    public:
        virtual void Connect() = 0;
        virtual void Disconnect() = 0;
        virtual void SendMessage(const FString& Message) = 0;
        virtual bool IsConnected() const = 0;
        virtual void CancelCurrentRequest() = 0;
    };
    ```
  - **实现**：`FOpenClawBridge : IAgentPlatformBridge`，封装所有 Python ExecCommand 调用
  - **改动**：新增 `OpenClawBridge.h/.cpp`，Dashboard 改为持有 `IAgentPlatformBridge*`
  - **验收**：Dashboard 代码中不再出现 `openclaw_bridge` 字符串

- [ ] **G2.3 mcp-bridge 插件增强**
  - **新增功能**：
    - 动态工具刷新（配合 G1.1）
    - 工具变更通知日志
    - 连接健康指标暴露（连接数、重连次数、延迟）
  - **改动**：`mcp-bridge/index.ts`

---

### 阶段 G3：DCC 复用适配 (DCC Portability)

> **目标**：将 bridge 通信层适配到 DCCClawBridge（Maya/Max），实现 DCC 共享同一套 Gateway 转发逻辑
> **前置依赖**：G2.1 完成（bridge_core.py 与 UE 解耦）
> **预估工时**：3~4 天

- [ ] **G3.1 bridge_dcc.py — 通用 DCC 适配器**
  - **职责**：为 PySide2/Qt 环境提供 bridge_core.py 的适配
  - **与 bridge_ue.py 的区别**：
    | | bridge_ue.py | bridge_dcc.py |
    |---|---|---|
    | 日志 | unreal.log → UE Output Log | Python logging → DCC Script Editor |
    | 数据回传 | 文件轮询（FTSTicker） | Qt signal/slot 直接通知 |
    | 线程模型 | 独立 asyncio 线程 | 独立 asyncio 线程（相同） |
    | DCC API | `import unreal` | `import maya.cmds` / `import pymxs` |
  - **改动**：新增 `bridge_dcc.py`，从 `bridge_core.py` 继承
  - **验收**：Maya 中 `from bridge_dcc import connect; connect()` 可连通 Gateway

- [ ] **G3.2 mcp-bridge 多实例配置**
  - **场景**：UE + Maya 同时连接 Gateway
  - **配置示例**：
    ```json
    {
      "servers": {
        "ue-editor": { "type": "websocket", "url": "ws://127.0.0.1:8080" },
        "maya-primary": { "type": "websocket", "url": "ws://127.0.0.1:8081" }
      }
    }
    ```
  - **工具命名空间**：`mcp_ue-editor_run_ue_python`, `mcp_maya-primary_export_fbx`
  - **改动**：mcp-bridge 已支持多 server 配置，验证实际多实例运行
  - **验收**：Gateway 同时连接 UE 和 Maya 的 MCP Server，工具互不冲突

- [ ] **G3.3 DCCClawBridge 集成测试**
  - **测试矩阵**：
    - Maya 2023 + OpenClaw Gateway → 聊天 + 工具调用
    - UE 5.5 + Maya 2023 同时在线 → 工具命名空间隔离
  - **验收**：Maya Chat Panel 输入消息 → AI 回复 → 调用 Maya 工具 → 执行成功

---

### 阶段 G4：部署与体验优化 (Deployment & DX)

> **目标**：降低部署门槛，提升开发者体验
> **预估工时**：2~3 天

- [ ] **G4.1 一键部署脚本升级**
  - **现状**：`setup.bat` 需要手动编辑 openclaw.json
  - **方案**：脚本自动检测 openclaw.json → 合并 mcp-bridge 配置 → 备份原文件
  - **新增**：`setup.sh`（macOS/Linux 支持）
  - **验收**：运行脚本后直接 `openclaw gateway restart` 即可

- [ ] **G4.2 连接诊断增强**
  - **现状**：`/diagnose` 检查 9 项，但 Gateway RPC 连接检测不够细
  - **新增检测项**：
    - Gateway RPC 协议版本匹配
    - mcp-bridge 插件加载状态
    - 工具注册数量 vs MCP Server 暴露数量
    - 端到端延迟测试（Gateway → MCP Server → 返回）
  - **改动**：`health_check.py` + `bridge_diagnostics.py`

- [ ] **G4.3 OpenClaw Agent 配置模板**
  - **提供**：针对 UE / Maya / 多 DCC 场景的完整 openclaw.json 配置模板
  - **包含**：Agent system prompt 建议、tools.allow 白名单、mcp-bridge 配置
  - **路径**：`openclaw-mcp-bridge/templates/`

---

## 时间线总览

```
         第1周              第2周              第3周              第4周
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │    G1 加固    │  │   G2 重构     │  │  G3 DCC复用   │  │  G4 部署体验  │
  │              │  │              │  │              │  │              │
  │ G1.1 时序修复 │  │ G2.1 拆分py  │  │ G3.1 DCC适配  │  │ G4.1 部署脚本 │
  │ G1.2 状态同步 │  │ G2.2 C++抽象 │  │ G3.2 多实例   │  │ G4.2 诊断增强 │
  │ G1.3 流式稳定 │  │ G2.3 插件增强 │  │ G3.3 集成测试 │  │ G4.3 配置模板 │
  │ G1.4 错误本地化│  │              │  │              │  │              │
  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

**总预估工期**：~4 周（每周 3~5 天投入）

**可并行**：
- G1 与 DCCClawBridge 阶段 1（Bootstrap）可并行
- G4 的部分工作可穿插在 G2/G3 中完成

---

## 文件改动影响矩阵

| 文件 | G1 | G2 | G3 | G4 | 说明 |
|------|:--:|:--:|:--:|:--:|------|
| `openclaw_bridge.py` | ✏️ | 🔄 拆分 | — | — | G2 后被拆为 5 个文件 |
| `mcp-bridge/index.ts` | ✏️ | ✏️ | ✅ 验证 | — | G1.1+G2.3 改动 |
| `UEAgentDashboard.cpp` | ✏️ | 🔄 重构 | — | — | G2.2 引入抽象层 |
| `UEAgentLocalization.cpp` | ✏️ | — | — | — | G1.4 新增文本对 |
| `health_check.py` | — | — | — | ✏️ | G4.2 新增检测项 |
| `bridge_core.py` | — | 🆕 | ✅ 复用 | — | G2.1 新增，G3 复用 |
| `bridge_dcc.py` | — | — | 🆕 | — | G3.1 新增 |
| `setup.bat/sh` | — | — | — | ✏️ | G4.1 升级 |

---

## 与其他路线图的关系

| 路线图 | 关系 |
|--------|------|
| UE 开发路线图 (阶段 0~4) | G 系列是对阶段 3.7 (Chat Bridge) 的深化 |
| DCCClawBridge 路线图 | G3 是 DCCClawBridge 阶段 2 (MCP通信) 的前置 |
| Skill 管理体系 | 无直接依赖，Skill 层完全平台无关 |

---

**版本**：1.0 | **创建**：2026-03-18 | **作者**：小优
