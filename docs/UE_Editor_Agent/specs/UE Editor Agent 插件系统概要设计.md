# UE Editor Agent 插件系统概要设计

## 1. 项目概述 (Project Overview)
本方案旨在开发一个虚幻引擎（Unreal Engine）深度集成的智能体插件。通过 **OpenClaw** 接入大语言模型（LLM），结合 **MCP (Model Context Protocol)** 实现引擎数据与 AI 能力的标准化互联。该 Agent 不仅能通过自然语言执行场景操作，还能利用动态 **Skill 系统** 不断进化，并依托 **UE 原生 UI** 提供专业级开发体验。

### 1.1 核心目标
- **UE → LLM**：用户在 UE 编辑器中通过自然语言输入，调用 WorkBuddy/OpenClaw 的大模型能力，帮助解决 UE 开发中的问题
- **LLM → UE**：用户在 WorkBuddy/OpenClaw 中输入指令，通过插件调用 UE 的功能，实现自动化任务
- **深层感知与标准化交互**：基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io)，将 UE 场景层级、资产库定义为 **Resources**，将编辑器操作封装为 **Tools**，实现跨平台的上下文共享。
- **动态 Skill 进化**：支持运行时热加载由 Python 或 C++ 编写的技能包。开发者可通过 [ClawHub](https://github.com/VoltAgent/awesome-openclaw-skills) 等平台一键发布与分享自定义工作流。
- **混合界面交互**：集成 **UE 原生 Slate/UMG 对话框**，在涉及高风险操作（如批量删除、参数大幅调整）时进行二次确认。
- **底层控制与性能**：通过 C++ 接口扩展底层数据访问（如原始贴图数据、渲染通道），并深度集成 UE 的 **Undo/Redo 撤销系统**。
- **模块化分发**：提供标准化的 `openclaw.plugin.json` 配置，确保 OpenClaw 端与 UE 插件端能同步部署与版本管理。

### 1.2 整体架构图
```text
[用户输入] ──> [OpenClaw (大脑)] <── [MCP Host (项目上下文: 资源/规范/日志)]
                     │
                     ▼ (JSON-RPC 指令流)
[UE 插件执行端 (Client/Server 架构)] ──────────────────────┐
    │                                                   │
    ├─> [Native UI Manager] (Slate/UMG 交互对话框)        │
    │                                                   │
    ├─> [Dynamic Skill Hub] (热加载 Python/C++ 技能包) <──┘ (分享 & 发布)
    │
    └─> [Core Executor]
            ├─ Python 脚本层 (逻辑转换 & 快速迭代)
            └─ C++ 扩展层 (底层数据操作 & Undo 栈集成)
```

## 2. 关键演进特性 (Key Evolved Features)

### 2.1 MCP 协议集成
- **Resource 映射**：将 `Content Browser` 中的资产路径映射为 MCP 资源，允许 AI 实时检索资产元数据。
- **Tool 封装**：将 `SpawnActor`、`SetMaterial` 等操作封装为标准 MCP 工具，支持参数自动发现与校验。

### 2.2 动态 Skill 模块规范
- **包结构**：
  - `scripts/`: 核心逻辑（.py 或 .cpp 源码）。
  - `ui/`: 关联的 UMG 界面资产。
  - `config.json`: 定义技能触发词、参数 Schema 及权限等级。
- **分发方式**：支持通过 [ClawHub CLI](https://docs.openclaw.ai/tools/plugin) 进行 `clawhub install <skill-id>` 一键安装到 UE 项目路径。

### 2.3 安全与版本控制
- **操作溯源**：所有 AI 生成的操作均关联至 UE Transaction 栈，支持 `Ctrl+Z` 恢复。
- **权限审计**：利用 OpenClaw 的 Sandbox 机制限制 AI 对本地文件系统的非授权访问。

---
**提示**：本设计基于 **UE 5.5+** 的 Python 脚本环境及 **OpenClaw v1.5+** 架构。
