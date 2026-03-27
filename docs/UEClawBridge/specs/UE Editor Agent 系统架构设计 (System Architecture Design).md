# UE Editor Agent 系统架构设计 (System Architecture Design)

## 1. 逻辑架构分层 (Layered Architecture)

本系统采用 **“多平台大脑 + 统一执行中心”** 的分布式架构，通过 **MCP 协议** 实现解耦，支持多个MCP客户端（WorkBuddy、OpenClaw等）同时接入。

### 1.1 感知与决策层 (Intelligence Layer - Multi-Platform)
*   **LLM Engines**: 支持多个AI平台（WorkBuddy、OpenClaw、Claude Desktop等）。
*   **MCP Clients**: 各平台通过MCP协议与UE插件通信，无需直接管理Skill，专注AI对话逻辑。
*   **Context Manager**: 按需拉取UE上下文（选中Actor、关卡信息等），避免Token浪费。

### 1.2 通信协议层 (Communication Layer - MCP)
*   **Transport**: 基于 **WebSocket** (支持多客户端并发连接) 或 **Stdio** (单客户端本地调用)。
*   **Protocol**: 遵循 [MCP 1.0 规范](https://modelcontextprotocol.io)，使用 JSON-RPC 2.0 进行封装。
*   **Schema Registry**: 动态管理 Python 装饰器自动生成的 API 描述文档。
*   **Notification System**: 关键事件推送（Skill重载、编辑器模式切换等），避免频繁推送造成的Token浪费。

### 1.3 核心执行层 (Execution Layer - UE Plugin - Unified Management)
*   **MCP Server**: 驻留在 UE 进程内的服务器，支持多客户端并发连接，统一分发指令。
*   **Core Tool Registry**: 注册唯一的 MCP 工具 `run_ue_python`（§1.5 定义），随插件启动加载。其余原子功能通过 Python API 访问，不再注册为 MCP 工具。
*   **Skill Hub (统一管理)**: **Skill管理中心**，统一加载/卸载/热重载所有业务 Skill（§1.5 定义），通过 `execute_skill()` Python API 提供执行入口，不再将 Skill 注册为 MCP 工具。
*   **Resource Manager**: 提供按需拉取（Pull-on-Demand）机制，AI需要时才获取UE上下文，节省Token。
*   **Native UI Bridge**: 负责唤起 Slate 或 UMG 对话框，处理 AI 操作的人机确认。
*   **Multi-Client Coordinator**: 管理多个MCP客户端连接，推送关键事件通知到所有客户端。

### 1.4 底层能力层 (Capability Layer - Engine)
*   **Python Wrapper**: 封装高频 `unreal` API，提供简化的业务接口。
*   **C++ Extension**: 针对 Python 无法触及的底层（如原生 RHI 操作、自定义 Shader 属性修改）提供扩展。
*   **Transaction Guard**: 深度钩入 UE 的 `Undo/Redo` 系统，确保 AI 每一步操作都有据可查。

---

## 2. 系统组件图 (Component Diagram)

### 多平台架构（Multi-Platform Support）

```mermaid
graph TD
    subgraph "AI Platform Layer (Multiple Clients)"
        W[WorkBuddy] --> C1[MCP Client]
        O[OpenClaw] --> C2[MCP Client]
        CD[Claude Desktop] --> C3[MCP Client]
        
        C1 --> U1[Context Manager]
        C2 --> U2[Context Manager]
        C3 --> U3[Context Manager]
    end

    subgraph "MCP Bridge (WebSocket/JSON-RPC)"
        C1 <==> S[MCP Server Gateway]
        C2 <==> S
        C3 <==> S
        
        S --> MC[Multi-Client Coordinator]
    end

    subgraph "UE Plugin (Executor Side - Unified Management)"
        MC --> F[Skill Hub (Unified)]
        MC --> R[Resource Manager]
        MC --> N[Notification System]
        
        F --> G[Python Skills]
        F --> MCP[MCP Interface Exposer]
        G --> H[C++ Core Extensions]
        G --> I[Unreal Python API]
        H --> J[Engine C++ API]
        
        R --> G1[Context Cache]
        R --> U[UE Context]
        
        N --> P[Push Notifications]
        
        G --> K[Native UI Manager]
        K --> L[UMG/Slate Dialog]
        
        I --> M[Undo/Redo System]
        J --> M
    end
    
    style F fill:#f9f,stroke:#333,stroke-width:2px
    style R fill:#bbf,stroke:#333,stroke-width:2px
    style MC fill:#bfb,stroke:#333,stroke-width:2px
```

**关键组件说明**：

- **Skill Hub (Unified)**：统一管理所有Skill，通过 `execute_skill()` Python API 提供调用入口，不再注册为 MCP 工具
- **Resource Manager**：提供按需拉取机制，避免频繁推送造成的Token浪费
- **Multi-Client Coordinator**：管理多个MCP客户端连接，推送关键事件到所有客户端
- **Context Cache**：缓存上下文数据，减少重复拉取
- **Push Notifications**：关键事件推送（Skill重载、模式切换等）

---

## 3. 关键业务流程 (Sequence Diagram)

### 以“将所有选中模型设为红色材质”为例（混合模式）：

1.  **用户**: 在WorkBuddy/OpenClaw输入“把选中的东西都变红”。
2.  **WorkBuddy/OpenClaw**:
    *   **意图分析**：识别出需要UE上下文（选中Actor和材质操作）。
    *   **按需拉取**：调用 MCP Tool `unreal://skills/list` 获取可用的材质操作Skill。
    *   **智能拉取**：仅当需要时调用 `unreal://level/selected_actors` 获取选中物体（不订阅，避免Token浪费）。
3.  **UE 插件**:
    *   **Resource Manager**：接收到拉取请求，返回当前选中Actor数据（从缓存或实时获取）。
    *   **Skill Hub (Unified)**：匹配到 `Material_Swapper` Skill，准备执行。
    *   **Native UI**：弹出确认对话框：“AI 计划修改 5 个 Actor，是否继续？”。
    *   **Core Executor**：开启 `ScopedTransaction` 包装操作。
    *   **Python Skill**：执行材质替换逻辑。
4.  **反馈**: 执行结果通过 MCP 回传，WorkBuddy/OpenClaw展示“修改完成，按 Ctrl+Z 可撤销”。

---

## 3.1 关键推送通知示例

### 场景：Skill热重载后通知所有客户端

```
1. 开发者修改Skill文件: batch_material_optimizer.py
   ↓
2. UE插件文件监控检测到变化
   ↓
3. UE插件热重载Skill (Skill Hub)
   ↓
4. Notification System推送通知给所有MCP客户端:
   {
     "method": "notifications/skills/reloaded",
     "params": {"skill_name": "batch_material_optimizer"}
   }
   ↓
5. WorkBuddy接收通知 → 更新Skill列表缓存
   ↓
6. OpenClaw接收通知 → 更新Skill列表缓存
   ↓
7. 所有客户端都能立即使用新版本的Skill
```

**推送事件类型**（关键事件，低频次）：
- `notifications/skills/reloaded` - Skill重载完成
- `notifications/editor/mode_changed` - 编辑器模式切换
- `notifications/level/loaded` - 关卡加载完成
- `notifications/transaction/committed` - 事务提交（可撤销）

---

## 4. 技术栈选择 (Tech Stack)

| 维度 | 技术选型 | 原因 |
| :--- | :--- | :--- |
| **通讯协议** | **MCP (JSON-RPC)** | 跨语言标准，生态兼容性强，支持多客户端并发 |
| **中间件** | **WebSocket (Python-SocketIO)** | 支持多客户端同时连接，实时双向通信 |
| **资源同步** | **Pull-on-Demand + Critical Push** | 避免Token浪费，关键事件实时通知 |
| **逻辑语言** | **Python 3.9+ (UE Internal)** | 迭代速度快，生态丰富，支持 inspect 自动映射 |
| **底层性能** | **C++ (Slate/RHI)** | 补齐 Python 在 UI 和底层渲染数据操作上的短板 |
| **配置管理** | **JSON / YAML** | 方便 Skill 模块的跨平台分发与人类阅读 |
| **多平台支持** | **Unified Skill Hub** | UE插件统一管理Skill，通过 `execute_skill()` Python API 提供调用入口 |

---

## 5. 多平台支持设计 (Multi-Platform Support)

### 5.1 设计原则

**统一管理，多方接入**：所有业务逻辑（Skill、资源、权限）在UE插件侧统一管理，各AI平台（WorkBuddy、OpenClaw等）通过MCP协议平等接入。

### 5.2 MCP客户端适配矩阵

| MCP客户端 | 支持版本 | 连接方式 | 特色功能 | 接入说明 |
|----------|---------|---------|---------|---------|
| **WorkBuddy** | v1.5+ | WebSocket/Stdio | 集成IDE、RAG增强 | 推荐主开发平台 |
| **OpenClaw** | v1.5+ | WebSocket/Stdio | 轻量级、跨平台 | 支持独立运行 |
| **Claude Desktop** | v0.5+ | Stdio | 官方客户端 | 基础功能可用 |
| **自定义客户端** | MCP 1.0+ | WebSocket | 企业内嵌 | 按MCP规范接入 |

### 5.3 兼容性保证

- **协议版本**：遵循MCP 1.0规范，确保跨版本兼容
- **接口统一**：所有客户端通过唯一的 MCP 工具 `run_ue_python` 与 UE 交互；Skill 通过 `run_ue_python` 调用 `skill_hub.execute_skill()` Python API 执行
- **事件通知**：关键事件推送到所有订阅的客户端，保持状态同步
- **向后兼容**：新版本的UE插件支持旧版MCP客户端（降级处理）

---

## 1.5 Core Tool 与 Skill 二层体系 (Two-Tier Capability Model)

> **v1.2 新增** — 基于阶段 0~2 实践经验，明确 Tool 和 Skill 的分层定义与增长模型。
> **v1.5 重大更新** — MCP 工具极简化：每个 DCC 只保留 1 个 MCP 工具（`run_ue_python`），Skill 不再注册为 MCP 工具，改为 Python API 调用。

### 1.5.1 定义

| 概念 | 定位 | 注册方式 | 生命周期 | 增长模型 |
|------|------|----------|----------|----------|
| **Core Tool (MCP)** | 唯一的 MCP 工具入口 | `mcp_server.register_tool()` 硬编码 | 随插件启动，不可热重载 | **极简**，仅 1 个（`run_ue_python`） |
| **Python API** | 底层原子操作（原 Core Tool 降级） | Python 函数，不注册 MCP | 随插件启动加载 | **稳定**，按需扩展 |
| **Skill** | 高层业务逻辑（应用程序级） | `execute_skill()` Python API | 热重载，保存即生效 | **持续增长**，50~500+ |

### 1.5.2 MCP 工具与 Python API 清单

v1.5 重构后，MCP Server 仅暴露 **1 个工具**：`run_ue_python`。原有的 Core Tool 功能以 Python API 形式保留，AI 通过 `run_ue_python` 执行代码来调用这些函数。

#### 唯一的 MCP 工具

| Tool | 说明 |
|------|------|
| `run_ue_python` | 万能执行器，覆盖任意 Python 代码执行。AI 通过此工具调用所有 Python API 和 Skill |

#### 原 Core Tool 迁移状态

| 类别 | 原 Tool 名 | v1.5 状态 | 说明 |
|------|-----------|-----------|------|
| **执行** | `run_ue_python` | ✅ **保留为 MCP 工具** | 唯一保留的 MCP 工具，万能执行器 |
| **感知** | `get_selected_actors` | 📦 降级为 Python API | `from ue_agent.api import get_selected_actors`，AI 通过 `run_ue_python` 调用 |
| | `get_editor_context` | 📦 降级为 Python API | `from ue_agent.api import get_editor_context`，AI 通过 `run_ue_python` 调用 |
| | `get_viewport_camera` | 📦 降级为 Python API | `from ue_agent.api import get_viewport_camera`，AI 通过 `run_ue_python` 调用 |
| | `get_dynamic_prompt` | 🔄 已内化 | 功能整合到 Prompt 生成流程中，不再作为独立接口 |
| **操作** | `focus_on_actor` | 📦 降级为 Python API | `from ue_agent.api import focus_on_actor`，AI 通过 `run_ue_python` 调用 |
| | `highlight_actors` | 📦 降级为 Python API | `from ue_agent.api import highlight_actors`，AI 通过 `run_ue_python` 调用 |
| | `set_viewport_camera` | 📦 降级为 Python API | `from ue_agent.api import set_viewport_camera`，AI 通过 `run_ue_python` 调用 |
| **安全** | `assess_risk` | 🔄 已内化 | 风险评估整合到执行管线内部，自动触发 |
| | `analyze_error` | 🔄 已内化 | 错误分析整合到执行管线的错误处理流程中 |

> **设计原则**：降级为 Python API 的函数签名和功能完全保留，只是不再占用 MCP 工具槽位。AI 通过 `run_ue_python` 编写 Python 代码即可调用，例如：
> ```python
> from ue_agent.api import get_selected_actors, highlight_actors
> actors = get_selected_actors()
> highlight_actors([a.get_name() for a in actors])
> ```

### 1.5.3 Skill 与 Core Tool 的关系

Skill 不再注册为 MCP 工具，而是作为 **Python 模块**，通过 `skill_hub.execute_skill()` API 调用。AI 使用 `run_ue_python` 作为唯一的 MCP 入口，在代码中调用 Skill 和 Python API。

```
AI (LLM) ─── run_ue_python (唯一 MCP 工具) ─── Python 代码执行
                │
                ├── skill_hub.execute_skill("optimize_lighting", params={...})
                ├── from ue_agent.api import get_selected_actors, focus_on_actor
                ├── import unreal  # 直接使用 UE Python API
                └── ...任意 Python 代码
                      │
Skill（Python 模块，可无限扩展）
  │
  ├── "一键优化关卡灯光"     → 内部调用 ue_agent.api + unreal API
  ├── "批量重命名符合项目规范" → 内部调用 get_selected_actors() + unreal API
  ├── "自动检测材质贴图分辨率" → 内部调用 highlight_actors() + unreal API
  └── "赛博朋克风灯光预设"    → 内部调用 unreal API
        │
Python API（原 Core Tool，底层原子操作）
  │
  ├── get_selected_actors() ── EditorLevelLibrary
  ├── focus_on_actor() ── EditorLevelLibrary
  ├── highlight_actors() ── EditorLevelLibrary
  └── ...
```

**关键约束**：
- Skill 和 Python API 均不注册为 MCP 工具，AI 统一通过 `run_ue_python` 访问
- `run_ue_python` 是唯一的 MCP 工具，承担"万能入口"角色
- Skill 的 Prompt 描述应引导 AI 优先使用 `execute_skill()` 调用已有 Skill，仅在无匹配时 fallback 到直接编写 Python 代码

### 1.5.4 Skill Hub 注册与执行流程

```
UE 插件启动
  │
  ├── 1. 注册唯一 MCP 工具 run_ue_python（硬编码，即时完成）
  │
  └── 2. Skill Hub 初始化
        │
        ├── 扫描 Skills/ 目录
        ├── 发现 @ue_agent.skill 装饰器
        ├── inspect 提取签名 + docstring
        ├── 注册为内部 Python API（skill_hub.register_skill()）
        │
        └── 通过 execute_skill() 对外提供调用入口
              │
              └── AI 调用示例：
                    run_ue_python(code="""
                    from ue_agent.skill_hub import execute_skill
                    result = execute_skill("batch_material_optimizer", params={...})
                    """)
```

**OpenClaw Skill（SKILL.md）按需加载**：

除了 UE 插件内置的 Python Skill，ArtClaw 还支持 OpenClaw Skill（SKILL.md 格式）。这些 Skill 以文档形式定义工作流，由 OpenClaw Agent 按需加载并翻译为 `run_ue_python` 调用序列：

```
OpenClaw Agent 接收用户请求
  │
  ├── 匹配 OpenClaw Skill（SKILL.md）
  ├── 解析 SKILL.md 中的步骤和参数
  └── 逐步生成 run_ue_python 调用
        │
        ├── run_ue_python(code="from ue_agent.api import ...")   # 步骤 1
        ├── run_ue_python(code="execute_skill('...', ...)")      # 步骤 2
        └── ...
```

### 1.5.5 OpenClaw 工具白名单策略

**v1.5 简化**：由于 MCP Server 现在仅暴露 1 个工具（`run_ue_python`），白名单膨胀问题已不复存在。

**推荐配置**：

```json
{
  "tools": {
    "allow": ["mcp_ue-editor-agent_run_ue_python"]
  }
}
```

**或使用通配符**（推荐，防止未来需要添加第二个工具时再次修改配置）：

```json
{
  "tools": {
    "allow": ["mcp_ue-editor-agent_*"]
  }
}
```

> **注**：通配符 `mcp_ue-editor-agent_*` 仍然是推荐做法。虽然当前只有 1 个工具，但未来如果需要添加必须独立暴露的工具（例如需要 C++ 底层能力且不可通过 `run_ue_python` 实现），通配符可以自动覆盖而无需修改配置。

---

## 6. OpenClaw Gateway 通信架构 (v1.3 新增, v1.4 更新)

> **重要发现**：OpenClaw Gateway 使用自定义 **WebSocket RPC 协议**，不是标准 REST HTTP API。

### 6.1 协议概述

```
┌─────────────────┐                     ┌──────────────────────────────────────┐
│ UE Dashboard    │  IAgentPlatformBridge│         Python Bridge Layer          │
│ (C++ Slate)     │  (抽象接口)          │                                      │
│                 │                      │  openclaw_bridge.py (UE 适配层 13KB) │
│ PlatformBridge  │─────────────────────►│         ↓ import                     │
│  ->Connect()    │                      │  bridge_core.py (平台无关核心 20KB)  │
│  ->SendMessage()│   File: response.txt │         ↓                            │
│       ↓         │ ◄──────────────────  │  bridge_config.py (配置加载 1KB)     │
│ FTSTicker Poll  │                      │  bridge_diagnostics.py (诊断 8KB)    │
│       ↓         │                      │                                      │
│HandlePythonResp │                      │  WebSocket RPC: connect / chat.send  │
└─────────────────┘                      └──────────────┬───────────────────────┘
                                                        │ ws://127.0.0.1:18789
                                                 ┌──────▼───────────┐
                                                 │ OpenClaw Gateway  │
                                                 │ (WebSocket RPC)   │
                                                 └──────────────────┘
```

> **v1.4 变更**：Dashboard 不再直接拼接 Python 字符串调用 `openclaw_bridge`，改为通过
> `IAgentPlatformBridge` C++ 抽象接口调用。Python 侧也从单一 46KB 文件拆分为 4 个模块。
> 详见 §6.6 和 §6.7。

### 6.2 Gateway WebSocket RPC 帧格式

| 方向 | 类型 | 格式 |
|------|------|------|
| Gateway → Client | Event | `{"event": "connect.challenge", "payload": {"nonce": "..."}}`  |
| Client → Gateway | Request | `{"type": "req", "id": "<uuid>", "method": "connect", "params": {...}}` |
| Gateway → Client | Response | `{"type": "res", "id": "<uuid>", "payload": {...}}` |
| Gateway → Client | Stream | `{"event": "chat", "payload": {"state": "delta\|final", "message": "..."}}` |

### 6.3 认证方式

Gateway 支持多种认证方式，UE Agent 使用最简单的 **Token 认证**：

```json
{
    "auth": { "token": "<gateway.auth.token from openclaw.json>" },
    "role": "operator",
    "scopes": ["operator.admin"]
}
```

### 6.4 C++ ↔ Python 数据传递

由于 UE 的 `IPythonScriptPlugin::ExecPythonCommand` 不直接返回复杂数据，采用**临时文件传递**模式：

1. Dashboard 调用 `PlatformBridge->SendMessageAsync(Message, ResponseFile)`
2. `FOpenClawPlatformBridge` 内部拼接 Python 命令，通过 `ExecPythonCommand` 执行
3. Python（`openclaw_bridge.py` → `bridge_core.py`）在后台线程完成 AI 对话
4. Python 将响应写入 `Saved/UEAgent/_openclaw_response.txt`
5. C++ 通过 `FTSTicker` 每 0.5 秒轮询文件是否存在
6. 文件出现后读取内容 → 删除文件 → `HandlePythonResponse()`

> **v1.4 变更**：步骤 1~2 原先由 Dashboard 直接拼接 Python 字符串，现在通过
> `IAgentPlatformBridge` 抽象接口隔离。Dashboard 代码中不再出现 `openclaw_bridge` 字符串。

### 6.5 前置依赖

| 依赖 | 安装方式 | 说明 |
|------|----------|------|
| `websockets` | `pip install websockets` (UE 内置 Python) | OpenClaw Gateway WS 通信 |

### 6.6 C++ 平台通信抽象层 (v1.4 新增)

> **背景**：v1.3 阶段 Dashboard 中约 200 行代码直接拼接 Python 字符串调用 `openclaw_bridge` 模块。
> 这导致 Dashboard 与 OpenClaw 平台强耦合，未来切换或新增 AI 平台需要大量改动。

#### 6.6.1 接口定义

```cpp
// IAgentPlatformBridge.h
class IAgentPlatformBridge
{
public:
    virtual ~IAgentPlatformBridge() = default;

    virtual FString GetPlatformName() const = 0;   // 平台显示名称
    virtual void Connect(const FString& StatusOutFile) = 0;
    virtual void Disconnect() = 0;
    virtual void CancelCurrentRequest() = 0;
    virtual void SendMessageAsync(const FString& Message, const FString& ResponseFile) = 0;
    virtual void RunDiagnostics(const FString& ReportOutFile) = 0;
    virtual void CollectEnvironmentContext(const FString& ContextOutFile) = 0;
    virtual void QueryStatus() = 0;
    virtual void ResetSession() = 0;
};
```

#### 6.6.2 OpenClaw 实现

```cpp
// OpenClawPlatformBridge.h / .cpp
class FOpenClawPlatformBridge : public IAgentPlatformBridge
{
public:
    virtual FString GetPlatformName() const override { return TEXT("OpenClaw"); }
    // 所有方法内部通过 ExecPythonCommand 调用 openclaw_bridge.py
    // Python 模块名和函数调用集中在此类，Dashboard 零耦合
private:
    void ExecPython(const FString& Code) const;
};
```

#### 6.6.3 Dashboard 集成

```cpp
// UEAgentDashboard.h
TSharedPtr<IAgentPlatformBridge> PlatformBridge;

// UEAgentDashboard.cpp — Construct
PlatformBridge = MakeShared<FOpenClawPlatformBridge>();

// 所有调用改为通过接口:
PlatformBridge->Connect(StatusFile);        // 替代直接拼 Python
PlatformBridge->SendMessageAsync(Msg, File); // 替代直接拼 Python
PlatformBridge->CancelCurrentRequest();      // 替代直接拼 Python
```

#### 6.6.4 扩展方式

换平台只需实现新的 `IAgentPlatformBridge` 子类，Dashboard 代码无需任何修改：

```
IAgentPlatformBridge (接口)
  ├── FOpenClawPlatformBridge   ← 当前实现 (openclaw_bridge.py)
  ├── FWorkBuddyPlatformBridge  ← 未来扩展
  └── FCustomPlatformBridge     ← 企业自定义
```

### 6.7 Python Bridge 模块拆分 (v1.4 新增)

> **背景**：v1.3 阶段 `openclaw_bridge.py` 膨胀至 46KB 单文件，混杂通信核心、配置、诊断、UE 适配逻辑。
> DCCClawBridge（Maya/Max）需要复用通信核心但不能依赖 `unreal` 模块。

#### 6.7.1 拆分后的模块结构

| 模块 | 路径 | 大小 | 职责 | 平台依赖 |
|------|------|------|------|----------|
| `bridge_config.py` | `openclaw-mcp-bridge/` | ~1KB | Gateway 配置加载（端口、Token） | 无 |
| `bridge_core.py` | `openclaw-mcp-bridge/` | ~20KB | WebSocket 连接、chat.send、流式响应、断连重连 | 无 |
| `bridge_diagnostics.py` | `openclaw-mcp-bridge/` | ~8KB | 连接诊断（9 项检测） | 无 |
| `openclaw_bridge.py` | `UEClawBridge/Content/Python/` | ~13KB | UE 适配层：unreal 模块集成、临时文件回传 | UE |
| `bridge_dcc.py` | `DCCClawBridge/core/` | ~5KB | DCC 适配层：Qt signal/slot 回传 | Qt/PySide2 |

#### 6.7.2 依赖关系

```
UE 路径:
  openclaw_bridge.py (UE 适配)
    └── import bridge_core       (平台无关)
        ├── import bridge_config (配置)
        └── import bridge_diagnostics (诊断)

DCC 路径:
  bridge_dcc.py (Maya/Max 适配)
    └── import bridge_core       (同一份，完全复用)
        ├── import bridge_config
        └── import bridge_diagnostics
```

#### 6.7.3 向后兼容

- C++ 侧零改动：`FOpenClawPlatformBridge` 仍调用 `from openclaw_bridge import ...`
- `openclaw_bridge.py` 对外暴露的函数签名不变（`connect`, `shutdown`, `send_chat_async_to_file` 等）
- 内部实现委托给 `bridge_core.py`

---

## 7. 架构演进历史

| 版本 | 日期 | 核心变更 | 原因 |
| :--- | :--- | :--- | :--- |
| v1.0 | 2026-03-15 | 初始版本 | 基础架构设计 |
| v1.1 | 2026-03-15 | 多平台支持 + 混合同步模式 | 支持WorkBuddy/OpenClaw等多客户端；优化Token使用 |
| v1.2 | 2026-03-16 | Core Tool / Skill 二层体系 + OpenClaw 白名单策略 | Phase 0~2 实践经验沉淀；解决 Skill 扩展时的注册膨胀问题 |
| v1.3 | 2026-03-16 | OpenClaw WS RPC 协议 + Python Bridge + Phase 3 子系统 | Phase 3 实现：双向通信、知识库、记忆、版本适配 |
| **v1.4** | **2026-03-18** | **C++ 平台通信抽象层 + Python Bridge 模块拆分** | **Gateway 转发流程重构 (G2)：解耦 Dashboard 与 OpenClaw、为 DCC 复用做准备** |
| **v1.5** | **2026-03-27** | **MCP 工具极简化 + Skill 体系重构** | **减少 AI 上下文占用（每个 DCC 只保留 1 个 MCP 工具），提升工具选择准确率** |

### v1.5 关键改进

1. **MCP 工具极简化 (§1.5.2)**：每个 DCC 仅保留 1 个 MCP 工具（`run_ue_python`），原有 10 个 Core Tool 中的 7 个降级为 Python API、2 个内化到执行管线。AI 上下文中的工具描述从 10+ 个缩减为 1 个，显著降低 Token 消耗和工具选择错误率。
2. **Skill 体系重构 (§1.5.3, §1.5.4)**：Skill 不再注册为 MCP 工具，改为 Python 模块通过 `skill_hub.execute_skill()` API 调用。AI 通过 `run_ue_python` 编写代码调用 Skill，消除了 MCP 工具列表膨胀问题。
3. **OpenClaw Skill 按需加载 (§1.5.4)**：新增 SKILL.md 格式的 OpenClaw Skill 支持，由 OpenClaw Agent 按需加载并翻译为 `run_ue_python` 调用序列。
4. **白名单策略简化 (§1.5.5)**：工具白名单问题不复存在（仅 1 个 MCP 工具），配置从动态维护简化为一行通配符。
5. **Python API 层保留 (§1.5.2)**：降级的原 Core Tool 功能函数完全保留（签名不变），仅从 MCP 注册中移除，确保向后兼容。

### v1.4 关键改进

1. **C++ 平台通信抽象层 (§6.6)**：新增 `IAgentPlatformBridge` 接口（8 个方法）+ `FOpenClawPlatformBridge` 实现。Dashboard 中不再出现 `openclaw_bridge` 字符串，换平台只需实现新子类。
2. **Python Bridge 模块拆分 (§6.7)**：`openclaw_bridge.py` (46KB) 拆为 `bridge_core.py` (20KB, 平台无关) + `bridge_config.py` (1KB) + `bridge_diagnostics.py` (8KB) + 瘦身后的 `openclaw_bridge.py` (13KB, UE 适配层)。
3. **DCC 复用路径打通**：`bridge_core.py` 被 DCCClawBridge 的 `bridge_dcc.py` 直接复用，UE 和 Maya/Max 共享同一套 Gateway 通信核心。
4. **架构图更新 (§6.1)**：协议概述图更新为反映抽象接口层和 Python 模块拆分后的结构。
5. **数据传递流程更新 (§6.4)**：步骤描述改为通过 `PlatformBridge->` 调用而非直接拼 Python 字符串。

### v1.3 关键改进

1. **OpenClaw Gateway 协议文档化**：记录 WS RPC 协议的帧格式、认证方式、chat.send 流程
2. **Python Bridge 架构**：C++ Slate UI → Python `openclaw_bridge.py` → OpenClaw Gateway WS 的三层桥接
3. **C++↔Python 数据传递**：临时文件 + FTSTicker 轮询模式，避免 ExecPythonCommand 返回值限制
4. **Phase 3 子系统集成**：`_init_phase3_subsystems()` 按依赖顺序初始化 4 个子系统
5. **MCP 接口扩展**：从 10 个 Core Tool 扩展到 10 + 7 = 17 个工具 + 2 个资源

### v1.2 关键改进

1. **二层体系定义**：明确 Core Tool（底层原子，10~20 个封顶）与 Skill（业务逻辑，可无限扩展）的边界
2. **Core Tool 冻结清单**：定义当前 10 个 Core Tool 及新增条件（三选二）
3. **OpenClaw 白名单策略**：明确当前手动配置 + 未来自动同步的演进路径
4. **Skill Hub 注册流程**：明确 `@ue_agent.tool` 装饰器 → inspect → MCP Schema → 通知客户端的标准链路
5. **`run_ue_python` 定位明确**：永远作为"万能后门"与 Skill 共存，Skill 优先、run_ue_python 兜底

### v1.1 关键改进

1. **多平台支持**：从单一OpenClaw扩展到支持WorkBuddy、OpenClaw、Claude Desktop等多个MCP客户端
2. **Skill统一管理**：Skill Hub从OpenClaw迁移到UE插件侧，所有客户端共享
3. **混合同步模式**：从纯推送改为"按需拉取 + 关键推送"，节省70%+ Token消耗
4. **多客户端协调器**：新增Multi-Client Coordinator组件，管理多个连接并统一推送

---


