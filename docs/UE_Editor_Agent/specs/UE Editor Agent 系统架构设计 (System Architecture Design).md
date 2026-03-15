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
*   **Skill Hub (统一管理)**: **Skill管理中心**，统一加载/卸载/热重载所有Skill，向所有MCP客户端暴露统一接口。
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

- **Skill Hub (Unified)**：统一管理所有Skill，向所有客户端暴露统一接口
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
| **多平台支持** | **Unified Skill Hub** | UE插件统一管理Skill，所有MCP客户端共享 |

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
- **接口统一**：所有客户端使用相同的Skill接口（`unreal://skills/list`、`unreal://skills/execute`）
- **事件通知**：关键事件推送到所有订阅的客户端，保持状态同步
- **向后兼容**：新版本的UE插件支持旧版MCP客户端（降级处理）

---

## 6. 架构演进历史

| 版本 | 日期 | 核心变更 | 原因 |
| :--- | :--- | :--- | :--- |
| v1.0 | 2026-03-15 | 初始版本 | 基础架构设计 |
| **v1.1** | **2026-03-15** | **多平台支持 + 混合同步模式** | **支持WorkBuddy/OpenClaw等多客户端；优化Token使用** |

### v1.1 关键改进

1. **多平台支持**：从单一OpenClaw扩展到支持WorkBuddy、OpenClaw、Claude Desktop等多个MCP客户端
2. **Skill统一管理**：Skill Hub从OpenClaw迁移到UE插件侧，所有客户端共享
3. **混合同步模式**：从纯推送改为“按需拉取 + 关键推送”，节省70%+ Token消耗
4. **多客户端协调器**：新增Multi-Client Coordinator组件，管理多个连接并统一推送

---


