# ArtClaw Bridge

**让 UE引擎、Maya、3ds Max 等 DCC 工具通过 MCP 协议接入 AI Agent 的桥接框架**

ArtClaw Bridge 为 Unreal Engine、Maya、3ds Max 等数字内容创作（DCC）软件提供统一的 AI 桥接层。通过 [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) 协议，AI Agent 可以直接理解和操作编辑器环境。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Status](https://img.shields.io/badge/status-beta-orange.svg)

---

## 展示

**UE 连接 OpenClaw 效果**

![UEClawBridge](docs/示例/UE连接openClaw效果.png)

**打通不同软件间的上下流交接**

![UEClawBridge](docs/示例/打通不同软件间的上下流交接.png)

---

## 项目愿景

在一个框架下做软件和 Agent 桥接，把 AI 能力接入到整个游戏开发的美术流，赋予 Agent 操作软件和解决上下游对接问题的能力。

桥接的好处是**未来可以接各种软件和各种 Agent 平台**，形成通用的软件-Agent 交互层。

---

## ✨ 核心特性

### 🔗 统一 MCP 协议
各 DCC 软件通过标准 MCP 协议与 AI Agent 通信。每个 DCC 只暴露一个 MCP 工具（`run_ue_python` / `run_python`），AI 通过执行 Python 代码完成所有操作，极简且强大。

### 💬 编辑器内 AI 对话面板
在 UE / Maya / Max 编辑器内直接与 AI 对话，无需切换窗口。支持：
- **流式输出** — AI 回复实时显示，支持 Markdown 渲染
- **Tool 调用可视化** — 折叠卡片显示工具名、参数、执行结果
- **附件发送** — 支持拖入图片或文件，AI 自动读取分析
- **上下文长度显示** — 实时显示 token 使用百分比
- **停止按钮** — 随时中断 AI 执行（发送 `chat.abort` 终止 Agent 运行）

### 🛠️ Skill 管理系统
分层管理的 Skill 热加载系统，跨 DCC 共享：
- **四层优先级** — 官方 > 市集 > 用户 > 临时，高层覆盖低层同名 Skill
- **编辑器内管理面板** — 双端（UE + DCC）统一 UI，支持筛选/搜索/启用/禁用/钉选
- **完整生命周期** — 安装、卸载、更新、发布（版本递增 + git commit），一键全量同步
- **AI 生成 Skill** — 自然语言描述需求，AI 自动生成可执行的 Skill（manifest + 代码 + 文档）
- **修改检测** — 自动识别运行时有未发布变更的 Skill，智能区分"更新"与"发布"方向
- **Pinned Skills 上下文注入** — 钉选的 Skill 文档自动注入 AI 首条消息上下文

### 🌐 多 Agent 平台支持
配置驱动的平台抽象层，新平台注册到配置文件即自动出现在 UI：
- **OpenClaw** — 主力平台，通过 mcp-bridge 插件集成
- **LobsterAI（有道龙虾）** — OpenClaw 二次封装，Gateway 端口 18790
- **Claude Desktop** — stdio→WebSocket 桥接 POC
- **编辑器内热切换** — Settings 面板一键切换平台，自动断连/重连/刷新 Agent 列表

### 🔄 多会话与 Agent 管理
- **多 Agent 切换** — 设置面板选择 Agent，工具栏显示当前 Agent 信息
- **会话列表管理** — 新建/切换/删除对话，各 Agent 独立会话缓存
- **会话持久化** — UE 重启后自动恢复上次会话，DCC 实时保存会话状态

### 🧠 记忆管理系统 v2
三层渐进式记忆模型，AI 记住用户偏好和操作历史：
- **短期记忆**（4h / 200 条）→ **中期**（7d / 500 条）→ **长期**（永久 / 1000 条）
- 语义标签分类（事实/偏好/规范/操作/崩溃/模式）
- 自动晋升、合并去重、定时维护
- 操作历史追踪与查询

### 📚 本地知识库（RAG）
索引 API 文档和项目文档，语义检索辅助 AI 决策。

### 🛡️ 安全与稳定
- 事务保护、风险评估、主线程调度
- 共享模块同步校验（`verify_sync.py` 对比 MD5，防止多副本漂移）
- 长任务超时保护 + 活跃事件重置

## ⚠️ 验证状态

| 组件 | 验证状态 | 说明 |
|------|----------|------|
| **OpenClaw** | ✅ 已验证 | 主力开发平台，所有功能均在此验证 |
| **LobsterAI** | ✅ 已验证 | 基础连接与对话功能已验证 |
| **Unreal Engine 5.7** | ✅ 已验证 | C++ + Python，完整功能验证 |
| **Maya 2023** | ✅ 已验证 | Python 3.9.7 + PySide2，完整功能验证 |
| **3ds Max** | ⚠️ 未验证 | 代码已实现，与 Maya 共享 DCC 插件，未进行实际测试 |
| **Claude Desktop** | ⚠️ POC | stdio→WebSocket 桥接概念验证，未深度集成 |
| **其他 Maya / UE 版本** | ⚠️ 未验证 | 理论兼容 Maya 2022+ / UE 5.3+，但未实际测试 |
| **本地知识库** | ⚠️ 未验证 | 功能已实现，未进行完整功能验证 |

> 目前所有开发和测试均基于 **OpenClaw + UE 5.7 + Maya 2023** 环境。其他组合理论兼容但未实际验证，欢迎社区反馈。

## 🎯 支持的 DCC 软件

| 软件 | 状态 | 插件 | MCP 端口 | 说明 |
|------|------|------|----------|------|
| **Unreal Engine 5.7** | ✅ 已实现 | UEClawBridge | 8080 | C++ + Python，Slate UI 对话面板 |
| **Maya 2023** | ✅ 已实现 | DCCClawBridge | 8081 | Python + PySide2，Qt 对话面板 |
| **3ds Max 2024+** | ✅ 已实现（未测试） | DCCClawBridge | 8082 | Python + PySide2，与 Maya 共享插件 |
| **Blender** | 💡 规划中 | — | — | 框架已预留扩展接口 |

## 🏗️ 架构

```
┌─────────────────────┐
│   AI Agent (LLM)    │
│ OpenClaw / LobsterAI│
└────────┬────────────┘
         │ WebSocket (上行:聊天 RPC / 下行:MCP 工具调用)
┌────────▼────────────┐
│   Agent Gateway      │  ← OpenClaw / LobsterAI Gateway
│   + MCP Bridge       │     统一管理 Agent、Session、MCP Server
└────────┬────────────┘
         │ WebSocket JSON-RPC (MCP)
    ┌────┴────┬──────────┬──────────┐
    ▼         ▼          ▼          ▼
┌────────┐┌────────┐┌────────┐┌────────┐
│ UE     ││ Maya   ││ 3dsMax ││ ...    │
│ MCP    ││ MCP    ││ MCP    ││ MCP    │
│ Server ││ Server ││ Server ││ Server │
│ :8080  ││ :8081  ││ :8082  ││        │
└───┬────┘└───┬────┘└───┬────┘└───┬────┘
    │         │         │         │
    ▼         ▼         ▼         ▼
  UE API   Maya API  Max API    ...
```

**通信双链路**：
- **上行（聊天）**：编辑器面板 → Gateway WebSocket RPC → AI Agent
- **下行（工具调用）**：AI Agent → Gateway → MCP Bridge → DCC MCP Server → DCC API

每个 DCC 软件运行独立的 MCP Server，通过统一协议向 AI Agent 暴露编辑器能力。Skill 系统、知识库、记忆存储等核心模块跨 DCC 共享。

## 📦 项目结构

```
artclaw_bridge/
├── core/                            # 🔧 共享核心模块（唯一源码，安装时复制到各 DCC）
│   ├── bridge_core.py               #    WebSocket RPC 通信核心
│   ├── bridge_config.py             #    配置加载与多平台默认值
│   ├── bridge_dcc.py                #    DCC 端 Bridge 管理器（Qt signal/slot）
│   ├── memory_core.py               #    记忆管理系统 v2 核心
│   ├── mcp_server.py                #    MCP Server（DCC 端，含 tool 事件回调）
│   ├── skill_sync.py                #    Skill 安装/卸载/同步/发布
│   └── ...                          #    诊断、健康检查、完整性检查等
├── platforms/                       # 🌐 平台 Bridge（可替换）
│   ├── openclaw/                    #    OpenClaw 适配（ws 连接 + 聊天 API + 诊断）
│   ├── lobster/                     #    LobsterAI 配置注入
│   └── claude/                      #    Claude Desktop stdio→WS 桥接 POC
├── subprojects/                     # 💻 DCC 插件子项目
│   ├── UEDAgentProj/                #    Unreal Engine 工程
│   │   └── Plugins/UEClawBridge/    #       UE 插件（C++ Slate UI + Python 业务逻辑）
│   └── DCCClawBridge/               #    Maya / 3ds Max 共享插件
│       ├── artclaw_ui/              #       通用 Qt 聊天面板 + Skill 管理面板
│       ├── adapters/                #       DCC 适配层（Maya / Max 各 ~200 行）
│       ├── core/                    #       核心模块副本（安装时从 core/ 同步）
│       ├── maya_setup/              #       Maya 部署文件
│       └── max_setup/               #       Max 部署文件
├── skills/                          # 🛠️ Skill 源码仓库
│   ├── official/                    #    官方 Skill（universal / unreal / maya / max）
│   ├── marketplace/                 #    市集 Skill
│   └── templates/                   #    Skill 模板（basic / advanced / material_doc）
├── cli/                             # ⌨️ ArtClaw CLI 工具
├── docs/                            # 📚 项目文档（规范 / 功能设计 / 排错记录）
├── install.bat                      # 📦 一键安装器（Windows 交互菜单，支持平台选择）
├── install.py                       # 📦 跨平台安装器（CLI，--platform openclaw/lobster）
└── verify_sync.py                   # 🔍 共享模块同步校验（MD5 对比，--fix 自动修复）
```

## 🚀 安装

### 前置条件

- **Python** 3.9+
- **Agent 平台**（任选其一）：
  - [OpenClaw](https://github.com/openclaw/openclaw)（`npm install -g openclaw`）
  - [LobsterAI](https://lobsterai.com/)（有道龙虾）
- 目标 DCC 软件：
  - UE 5.7（推荐，理论兼容 5.3+）
  - Maya 2023（推荐，理论兼容 2022+）
  - 3ds Max 2024+（未测试）

### 方式一：一键安装（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/IvanYangYangXi/artclaw_bridge.git
cd artclaw_bridge

# 2a. Windows 交互菜单 — 双击或命令行运行:
install.bat

# 2b. 或使用 Python CLI:
python install.py --help                                     # 查看所有选项
python install.py --maya                                     # 安装 Maya 插件（默认 2023）
python install.py --maya --maya-version 2024                 # 指定 Maya 版本
python install.py --max --max-version 2024                   # 安装 Max 插件
python install.py --ue --ue-project "C:\path\to\project"     # 安装 UE 插件
python install.py --openclaw                                 # 配置 OpenClaw
python install.py --openclaw --platform lobster              # 配置 LobsterAI
python install.py --all --ue-project "C:\path\to\project"    # 全部安装
```

安装脚本会自动：
1. 复制插件文件到目标 DCC 的标准目录
2. 部署 `core/` 共享模块（自包含，无需源码目录）
3. 安装官方 Skills 到平台目录（`~/.openclaw/skills/` 或 LobsterAI 对应目录）
4. **安全处理 startup 文件**（追加模式，不覆盖用户已有内容）
5. 配置 Agent 平台 mcp-bridge 集成
6. 写入 `~/.artclaw/config.json` 项目配置
7. 重复运行安全（幂等）

### 方式二：手动安装

<details>
<summary>手动安装步骤（点击展开）</summary>

#### UE 插件

```bash
# 1. 复制插件
xcopy /E /I subprojects\UEDAgentProj\Plugins\UEClawBridge "<UE项目路径>\Plugins\UEClawBridge"

# 2. 复制共享核心模块到插件的 Python 目录
for %f in (bridge_core bridge_config bridge_diagnostics health_check integrity_check memory_core skill_sync) do (
    copy core\%f.py "<UE项目路径>\Plugins\UEClawBridge\Content\Python\"
)

# 3. 复制平台 Bridge 模块（以 OpenClaw 为例）
for %f in (openclaw_ws openclaw_chat openclaw_diagnose) do (
    copy platforms\openclaw\%f.py "<UE项目路径>\Plugins\UEClawBridge\Content\Python\"
)

# 4. 安装 Python 依赖（使用 UE 内置 Python）
"<UE引擎路径>\Engine\Binaries\ThirdParty\Python3\Win64\python.exe" -m pip install websockets pydantic
```

#### Maya 插件

```bash
# 1. 复制 DCCClawBridge 目录
xcopy /E /I subprojects\DCCClawBridge "%USERPROFILE%\Documents\maya\2023\scripts\DCCClawBridge"

# 2. 复制共享模块到 core/
for %f in (bridge_core bridge_config bridge_diagnostics memory_core mcp_server skill_sync) do (
    copy core\%f.py "%USERPROFILE%\Documents\maya\2023\scripts\DCCClawBridge\core\"
)

# 3. 复制 userSetup.py（如果已有该文件，请追加而非覆盖）
copy subprojects\DCCClawBridge\maya_setup\userSetup.py "%USERPROFILE%\Documents\maya\2023\scripts\"

# 注意：Maya 中文版需要同时安装到 zh_CN/scripts/ 目录
```

#### Agent 平台配置

```bash
# OpenClaw
python platforms\openclaw\setup_openclaw_config.py --ue --maya --max
openclaw gateway restart

# LobsterAI
python platforms\lobster\setup_lobster_config.py
# 重启 LobsterAI
```

</details>

### 安装后验证

| DCC | 验证步骤 |
|-----|---------|
| **UE** | 打开项目 → 启用 "UE Claw Bridge" 插件 → 重启 → Window → UE Claw Bridge → 连接 |
| **Maya** | 启动 Maya → 菜单栏出现 **ArtClaw** → 打开 Chat Panel → 连接 |
| **3ds Max** | 启动 Max → ArtClaw 自动加载 → 菜单栏 ArtClaw → Chat Panel → 连接 |

### 卸载

```bash
python install.py --uninstall --maya                           # 卸载 Maya 插件
python install.py --uninstall --ue --ue-project "C:\project"   # 卸载 UE 插件
```

卸载脚本会删除插件目录，从 startup 文件中**仅移除 ArtClaw 代码块**（不影响用户已有内容）。

## 🛠️ Skill 系统

### 目录结构

```
项目源码（开发时）:                        已安装（运行时）:
skills/                                   ~/.openclaw/skills/
├── official/                             ├── ue57-camera-transform/
│   ├── universal/                        ├── ue57-artclaw-context/
│   │   ├── artclaw-memory/               ├── artclaw-memory/
│   │   └── scene-vision-analyzer/        ├── scene-vision-analyzer/
│   ├── unreal/                           ├── maya-operation-rules/
│   │   ├── ue57-camera-transform/        └── ...
│   │   └── ue57-operation-rules/
│   ├── maya/
│   │   └── maya-operation-rules/
│   └── max/
│       └── max-operation-rules/
├── marketplace/
│   └── universal/
│       └── ...
└── templates/
```

**工作流**：编辑已安装目录 → `发布`（已安装→源码 + 版本递增 + git commit）→ `更新`（源码→已安装）

### 创建 Skill

在编辑器中直接用自然语言描述：

> "帮我创建一个 skill，批量重命名场景中选中的 Actor，加上指定前缀"

AI 会自动生成 `SKILL.md` + `manifest.json` + `__init__.py`，确认后即可使用。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！特别欢迎以下方向的贡献：

- 🔌 **新 DCC 桥接实现** — Blender、Houdini 等
- 🛠️ **新 Skill** — 适用于各 DCC 的实用 Skill
- 🧪 **测试反馈** — 在未验证的 DCC 版本上测试并反馈
- 📖 **文档改进** — 使用教程、最佳实践

### 贡献流程

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feat/my-feature`
3. 提交更改：`git commit -m "feat: add my feature"`
4. 推送并创建 PR

详见 [贡献指南](docs/skills/CONTRIBUTING.md)。

## 📖 文档

- **[系统架构设计](docs/specs/系统架构设计.md)** — 整体架构与设计原则
- **[Skill 开发指南](docs/skills/SKILL_DEVELOPMENT_GUIDE.md)** — 编写自定义 Skill
- **[Skill 规范](docs/skills/MANIFEST_SPEC.md)** — manifest.json 格式规范
- **[代码规范](docs/specs/代码规范.md)** — 项目编码约定
- **[多平台兼容设计](docs/UEClawBridge/features/多平台兼容设计方案.md)** — 平台抽象层设计
- **[DCCClawBridge](subprojects/DCCClawBridge/README.md)** — Maya / 3ds Max 插件详细说明
- **[贡献指南](docs/skills/CONTRIBUTING.md)** — 如何为项目贡献

---

## 🧾 一些想法说明（不一定正确，欢迎指正）

### 为什么不直接做 Agent 接入大模型？

Agent 平台是个大工程。现在很多公司都在做自己的 Agent 管理平台，龙虾也属于 Agent 管理平台。

这部分是个大工程，本项目只做了**当前需要的工程问题方案**，专注于软件桥接这个细分领域。

### 有 MCP 和 Skill 就可以接入大模型了，为什么要做这个桥接工程？

目的是优化使用者体验。就像 VSCode 有很多 Agent 插件，让用户能在原本软件的窗口里使用，能大大提高使用的意愿和效率，并且可以根据需求做定制开发。

### 生产落地的思考

一些简单任务，比如按明确规则批量生成一些对象，通过 MCP 接入后直接就能干活了。对于性能优化等分析工作、脚本开发等可以通过代码执行的任务也完全能直接胜任。但是这些应用场景大多是 TA 和程序的工作，完全无法帮到美术同学。现在的好处是，美术可以直接让 AI 帮做一些简单脚本能实现的功能，而不需要学习编程。

大模型直接执行的过程是个黑盒，完全不知道内部是怎么工作的，AI 的执行结果完全无法预测，就像最早期的 AI 生图——AI 能画图，但无法在项目落地。后来出了很多工程化的工具，让 AI 的执行过程更加可控，才能真正提升生产效率。

所以我们接下来需要做的是把过程拆解，让 AI 的产出变得可控。这个过程还是需要依靠传统的工程化思维。Claude Code 的代码也验证了这个方向是对的——他们没有很多黑科技，而是通过工程化让大模型以正确可控的方式去执行。

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

## 👤 作者

**Ivan(杨己力)** — [@IvanYangYangXi](https://github.com/IvanYangYangXi)
