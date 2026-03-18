# UE Editor Agent 插件系统概要设计

## 1. 项目概述 (Project Overview)
本方案旨在开发一个虚幻引擎（Unreal Engine）深度集成的智能体插件。通过 **MCP (Model Context Protocol)** 协议支持 **多平台AI客户端**（WorkBuddy、OpenClaw、Claude Desktop等）接入大语言模型（LLM），实现引擎数据与 AI 能力的标准化互联。该 Agent 不仅能通过自然语言执行场景操作，还能利用统一管理的 **Skill 系统** 不断进化，并依托 **UE 原生 UI** 提供专业级开发体验。

**核心设计理念**：**统一管理，多方接入** - 所有业务逻辑（Skill、资源、权限）在UE插件侧统一管理，各AI平台通过MCP协议平等接入。

### 1.1 核心目标
- **多平台支持**：支持 **WorkBuddy**、**OpenClaw**、**Claude Desktop** 等多个MCP客户端同时接入，各平台共享统一的Skill系统和执行环境。
- **UE → LLM**：用户在 UE 编辑器中通过自然语言输入，调用任意MCP客户端的大模型能力，帮助解决 UE 开发中的问题。
- **LLM → UE**：用户在任意MCP客户端中输入指令，通过插件调用 UE 的功能，实现自动化任务。
- **深层感知与标准化交互**：基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io)，将 UE 场景层级、资产库定义为 **Resources**，将编辑器操作封装为 **Tools**，实现跨平台的上下文共享。
- **统一Skill管理**：所有Skill在UE插件侧统一管理，支持运行时热加载，向所有MCP客户端暴露统一接口（`unreal://skills/list`、`unreal://skills/execute`）。
- **混合同步模式**：采用**按需拉取（Pull-on-Demand）+ 关键推送（Critical Push）**，避免Token浪费，关键事件实时通知。
- **混合界面交互**：集成 **UE 原生 Slate/UMG 对话框**，在涉及高风险操作（如批量删除、参数大幅调整）时进行二次确认。
- **底层控制与性能**：通过 C++ 接口扩展底层数据访问（如原始贴图数据、渲染通道），并深度集成 UE 的 **Undo/Redo 撤销系统**。
- **模块化分发**：提供标准化的配置和Skill包格式（`.clawpkg`），支持通过远程市场一键安装和团队Git协作。

### 1.2 整体架构图（多平台支持）
```text
[用户输入] ──> [多平台AI客户端] <── [MCP协议 (标准化接口)]
                     │
                     ▼ (JSON-RPC 指令流)
┌──────────────────────────────────────────────────────────────────┐
│                    MCP Server (UE插件)                           │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │          统一管理中心 (Unified Management Hub)              │ │
│  │                                                            │ │
│  │  - Skill Hub: 统一管理所有Skill (热加载/版本控制)          │ │
│  │  - Resource Manager: 按需拉取 + 关键推送                   │ │
│  │  - Multi-Client Coordinator: 多客户端连接管理              │ │
│  │  - Notification System: 关键事件推送                       │ │
│  └──────────────────────┬─────────────────────────────────────┘ │
│                         │                                          │
│  ┌──────────────────────▼─────────────────────────────────────┐ │
│  │              MCP接口层 (Standardized APIs)                  │ │
│  │                                                            │ │
│  │  - tools/unreal://skills/list (Skill列表)                  │ │
│  │  - tools/unreal://skills/execute (Skill执行)               │ │
│  │  - resources/unreal://level/selected_actors (资源)          │ │
│  │  - notifications/skills/reloaded (事件通知)                │ │
│  └──────────────┬──────────────────┬──────────────────────────┘ │
│                 │                  │                              │
└─────────────────┼──────────────────┼──────────────────────────────┘
                  │                  │
        ┌─────────▼─────────┐  ┌────▼──────────┐  ┌──────────────┐
        │   WorkBuddy       │  │   OpenClaw    │  │ 其他MCP客户端 │
        │   (推荐)          │  │   (轻量级)    │  │              │
        └───────────────────┘  └───────────────┘  └──────────────┘
                             ▲  ▲
                             │  │
              ┌──────────────┴──┴──────────────┐
              │    UE编辑器原生交互层            │
              │    (Slate/UMG对话框)            │
              └──────────────┬─────────────────┘
                             │
              ┌──────────────▼─────────────────┐
              │  Python执行层 + C++扩展层       │
              │  (Unreal API + Undo系统)        │
              └────────────────────────────────┘
```

**核心设计原则**：
- **统一管理**：所有业务逻辑（Skill、资源、权限）在UE插件侧统一管理
- **多方接入**：各AI平台（WorkBuddy、OpenClaw等）通过MCP协议平等接入
- **按需交互**：AI需要时才拉取UE上下文，避免Token浪费
- **关键推送**：仅推送高频次、高价值事件（Skill重载、模式切换等）

## 2. 关键演进特性 (Key Evolved Features)

### 2.1 多平台支持 (Multi-Platform Support)
- **统一管理架构**：UE插件作为统一的Skill管理中心，向所有MCP客户端（WorkBuddy、OpenClaw、Claude Desktop等）暴露标准接口，避免重复管理。
- **混合同步模式**：采用**按需拉取（Pull-on-Demand）+ 关键推送（Critical Push）**，AI需要时才获取UE上下文，避免Token浪费；关键事件（Skill重载、模式切换）实时推送到所有客户端。
- **跨平台兼容**：遵循MCP 1.0协议，确保不同AI平台能够平等接入，共享同一套Skill系统和执行环境。

### 2.2 MCP 协议集成
- **Resource 映射**：将 `Content Browser` 中的资产路径映射为 MCP 资源，支持按需拉取，避免频繁推送造成的性能开销。
- **Tool 封装**：将 `SpawnActor`、`SetMaterial` 等操作封装为标准 MCP 工具，支持参数自动发现与校验。
- **事件通知**：关键事件推送机制，Skill重载后自动通知所有连接的MCP客户端，保持状态同步。

### 2.3 动态 Skill 模块规范（统一管理）
- **统一管理中心**：所有Skill在UE插件侧统一管理，通过MCP接口向所有客户端暴露：
  - `tools/unreal://skills/list` - 查询可用Skill列表
  - `tools/unreal://skills/execute` - 执行指定Skill
  - `notifications/skills/reloaded` - Skill重载事件通知
- **包结构**：
  - `scripts/`: 核心逻辑（.py 或 .cpp 源码）。
  - `ui/`: 关联的 UMG 界面资产。
  - `config.json`: 定义技能触发词、参数 Schema 及权限等级。
- **分发方式**：支持通过远程市场或Git仓库分发，安装到UE插件后，所有MCP客户端立即可用，无需重复安装。

### 2.4 安全与版本控制
- **操作溯源**：所有 AI 生成的操作均关联至 UE Transaction 栈，支持 `Ctrl+Z` 恢复。
- **权限审计**：在UE插件侧统一实施权限控制，所有MCP客户端共享同一套安全策略。
- **版本兼容**：支持UE 5.3/5.4/5.5+版本，通过接口适配层保证不同版本的API兼容性。

---

## 3. 多平台适配优势

| 对比维度 | 单平台方案 (OpenClaw Only) | 多平台方案 (Multi-Platform) |
|---------|--------------------------|--------------------------|
| **平台支持** | 仅支持OpenClaw | 支持WorkBuddy、OpenClaw、Claude Desktop等 |
| **Skill管理** | OpenClaw侧管理 | UE插件侧统一管理 |
| **Token效率** | 频繁推送，消耗高 | 按需拉取+关键推送，节省70%+ |
| **维护成本** | 多平台重复实现 | 统一维护，成本降低50% |
| **用户体验** | 平台间不一致 | 所有平台体验一致 |
| **生态扩展** | 有限 | 任意MCP客户端可接入 |

---

**提示**：本设计基于 **UE 5.5+** 的 Python 脚本环境，支持 **MCP 1.0+** 协议，兼容 **WorkBuddy v1.5+**、**OpenClaw v1.5+**、**Claude Desktop v0.5+** 等多种AI客户端平台。
