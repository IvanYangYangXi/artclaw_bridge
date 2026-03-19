# ArtClaw Bridge

**让 UE引擎、Maya、3ds Max 等 DCC 工具通过 MCP 协议接入 AI Agent 的桥接框架**

ArtClaw Bridge 为 Unreal Engine、Maya、3ds Max 等数字内容创作（DCC）软件提供统一的 AI 桥接层。通过 [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) 协议，AI Agent 可以直接理解和操作编辑器环境。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Status](https://img.shields.io/badge/status-beta-orange.svg)

---

## ✨ 特性

- **统一 MCP 协议** — 各 DCC 软件通过标准 MCP 协议与 AI Agent 通信，一套框架多端接入
- **Skill 热加载系统** — 分层管理（官方/团队/用户/临时），运行时动态加载，跨 DCC 复用
- **AI 生成 Skill** — 用自然语言描述需求，AI 自动生成可执行的编辑器 Skill
- **本地 RAG 知识库** — 索引 API 文档和项目文档，语义检索辅助 AI 决策
- **安全守卫** — 事务保护、风险评估、主线程调度
- **OpenClaw 集成** — 通过 MCP Bridge 插件无缝接入 [OpenClaw](https://github.com/openclaw/openclaw) Agent 框架

## 🎯 支持的 DCC 软件

| 软件 | 状态 | 插件 | 说明 |
|------|------|------|------|
| **Unreal Engine 5.7** | ✅ 已实现 | UEClawBridge | C++ + Python，编辑器内 AI 对话面板 |
| **Maya 2022+** | ✅ 已实现 | DCCClawBridge | Python + PySide2，ArtClaw Chat Panel |
| **3ds Max 2024+** | ✅ 已实现 | DCCClawBridge | Python + PySide2，ArtClaw Chat Panel |
| **Blender** | 💡 考虑中 | — | Python API |

> UE、Maya、3ds Max 三端均已实现完整的 MCP Server + AI 对话面板。Blender 支持正在规划中，框架层面已预留扩展接口。欢迎社区贡献！

## 🏗️ 架构

```
┌─────────────────────┐
│   AI Agent (LLM)    │
│   via OpenClaw       │
└────────┬────────────┘
         │ WebSocket (MCP)
┌────────▼────────────┐
│  MCP Bridge Plugin   │  ← OpenClaw 插件，桥接各 DCC 的 MCP Server
└────────┬────────────┘
         │ WebSocket JSON-RPC
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

每个 DCC 软件运行独立的 MCP Server，通过统一协议向 AI Agent 暴露编辑器能力。Skill 系统、知识库、记忆存储等核心模块跨 DCC 共享。

## 📦 项目结构

```
artclaw_bridge/
├── install.bat                      # 📦 一键安装器 (Windows 交互菜单)
├── install.py                       # 📦 跨平台安装器 (CLI, 支持卸载)
├── subprojects/                     # 各 DCC 软件的工程实现
│   ├── UEDAgentProj/                # ✅ Unreal Engine 工程
│   │   └── Plugins/UEClawBridge/    #    UE 插件（C++ + Python）
│   └── DCCClawBridge/               # ✅ Maya / 3ds Max 共享插件
│       ├── artclaw_ui/              #    通用 Qt 聊天面板
│       ├── adapters/                #    DCC 适配层 (Maya / Max)
│       ├── core/                    #    共享核心 (bridge, MCP, skill...)
│       ├── maya_setup/              #    Maya 部署文件
│       ├── max_setup/               #    Max 部署文件
│       └── skills/                  #    DCC Skill 模板
├── openclaw-mcp-bridge/             # OpenClaw MCP Bridge 插件 + 共享模块
│   ├── bridge_core.py               #    通信核心 (UE/DCC 共用)
│   ├── bridge_config.py             #    配置管理
│   ├── bridge_diagnostics.py        #    诊断工具
│   ├── mcp-bridge/                  #    OpenClaw 插件文件
│   ├── setup.bat                    #    UE 快速安装脚本
│   └── setup_openclaw_config.py     #    OpenClaw 配置生成
├── cli/                             # ArtClaw CLI 工具
├── skills/                          # Skill 模板库（跨 DCC 共享）
├── team_skills/                     # 团队共享 Skill（Git 同步）
├── docs/                            # 项目文档
└── tests/                           # 测试用例
```

## 🚀 安装

### 前置条件

- **Python** 3.9+（用于运行安装脚本）
- **OpenClaw** 已安装（`npm install -g openclaw`）
- 目标 DCC 软件已安装：
  - UE: Unreal Engine 5.3+（推荐 5.7）
  - Maya: 2022+（内置 Python 3.9+、PySide2）
  - Max: 2024+（内置 Python 3.9+、PySide2）

### 方式一：一键安装（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/IvanYangYangXi/artclaw_bridge.git
cd artclaw_bridge

# 2a. Windows 交互菜单 — 双击或命令行运行:
install.bat

# 2b. 或使用 Python CLI (跨平台):
python install.py --help                                     # 查看所有选项
python install.py --maya                                     # 安装 Maya 插件 (默认版本 2023)
python install.py --maya --maya-version 2024                 # 指定 Maya 2024
python install.py --max --max-version 2024                   # 安装 Max 插件
python install.py --ue --ue-project "C:\path\to\project"     # 安装 UE 插件
python install.py --openclaw                                 # 配置 OpenClaw
python install.py --all --ue-project "C:\path\to\project"    # 全部安装
```

安装脚本会自动：
1. 复制插件文件到目标 DCC 的标准目录
2. 打包 `bridge_core` 共享模块（自包含部署，无需源码目录）
3. **安全处理 startup 文件**（追加模式，不覆盖用户已有内容）
4. 配置 OpenClaw mcp-bridge 集成
5. 重复运行安全（幂等）

### 方式二：手动安装

<details>
<summary>手动安装步骤（点击展开）</summary>

#### UE 插件

```bash
# 1. 复制插件
# 将 subprojects/UEDAgentProj/Plugins/UEClawBridge 复制到 <UE项目>/Plugins/
xcopy /E /I subprojects\UEDAgentProj\Plugins\UEClawBridge "<UE项目路径>\Plugins\UEClawBridge"

# 2. 复制共享模块到插件的 Python 目录
copy openclaw-mcp-bridge\bridge_core.py "<UE项目路径>\Plugins\UEClawBridge\Content\Python\"
copy openclaw-mcp-bridge\bridge_config.py "<UE项目路径>\Plugins\UEClawBridge\Content\Python\"
copy openclaw-mcp-bridge\bridge_diagnostics.py "<UE项目路径>\Plugins\UEClawBridge\Content\Python\"

# 3. 安装 Python 依赖 (使用 UE 内置 Python)
"C:\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe" -m pip install websockets pydantic
```

#### Maya 插件

```bash
# 将 <Maya版本> 替换为实际版本号，如 2023、2024

# 1. 复制 DCCClawBridge 目录
xcopy /E /I subprojects\DCCClawBridge "%USERPROFILE%\Documents\maya\<Maya版本>\scripts\DCCClawBridge"

# 2. 复制共享模块到 core/ (自包含部署)
copy openclaw-mcp-bridge\bridge_core.py "%USERPROFILE%\Documents\maya\<Maya版本>\scripts\DCCClawBridge\core\"
copy openclaw-mcp-bridge\bridge_config.py "%USERPROFILE%\Documents\maya\<Maya版本>\scripts\DCCClawBridge\core\"
copy openclaw-mcp-bridge\bridge_diagnostics.py "%USERPROFILE%\Documents\maya\<Maya版本>\scripts\DCCClawBridge\core\"

# 3. 复制 userSetup.py (如果已有该文件，请追加而非覆盖!)
# 方式 A: 无已有 userSetup.py — 直接复制:
copy subprojects\DCCClawBridge\maya_setup\userSetup.py "%USERPROFILE%\Documents\maya\<Maya版本>\scripts\"

# 方式 B: 已有 userSetup.py — 将以下内容追加到文件末尾:
#   打开 subprojects/DCCClawBridge/maya_setup/userSetup.py
#   将其全部内容用以下注释包裹后追加:
#     # ===== ArtClaw Bridge START =====
#     (userSetup.py 内容)
#     # ===== ArtClaw Bridge END =====
```

#### 3ds Max 插件

```bash
# 将 <Max版本> 替换为实际版本号，如 2024、2025

# 1. 复制 DCCClawBridge 目录
xcopy /E /I subprojects\DCCClawBridge "%LOCALAPPDATA%\Autodesk\3dsMax\<Max版本>\ENU\scripts\DCCClawBridge"

# 2. 复制共享模块到 core/ (自包含部署)
copy openclaw-mcp-bridge\bridge_core.py "%LOCALAPPDATA%\Autodesk\3dsMax\<Max版本>\ENU\scripts\DCCClawBridge\core\"
copy openclaw-mcp-bridge\bridge_config.py "%LOCALAPPDATA%\Autodesk\3dsMax\<Max版本>\ENU\scripts\DCCClawBridge\core\"
copy openclaw-mcp-bridge\bridge_diagnostics.py "%LOCALAPPDATA%\Autodesk\3dsMax\<Max版本>\ENU\scripts\DCCClawBridge\core\"

# 3. 复制 startup 脚本
copy subprojects\DCCClawBridge\max_setup\startup.py "%LOCALAPPDATA%\Autodesk\3dsMax\<Max版本>\ENU\scripts\startup\artclaw_startup.py"
```

#### OpenClaw 配置

```bash
# 1. 复制 mcp-bridge 插件
mkdir %USERPROFILE%\.openclaw\extensions\mcp-bridge
copy openclaw-mcp-bridge\mcp-bridge\* %USERPROFILE%\.openclaw\extensions\mcp-bridge\

# 2. 运行配置脚本 (自动合并到 openclaw.json)
python openclaw-mcp-bridge\setup_openclaw_config.py --ue --maya --max

# 3. 重启 Gateway
openclaw gateway restart
```

</details>

### 安装后验证

| DCC | 验证步骤 |
|-----|---------|
| **UE** | 打开项目 → 启用 "UE Claw Bridge" 插件 → 重启 → Window → UE Claw Bridge → 输入 `/diagnose` |
| **Maya** | 启动 Maya → 菜单栏出现 **ArtClaw** → 打开 Chat Panel → 输入 `/connect` |
| **3ds Max** | 启动 Max → ArtClaw 自动加载 → 菜单栏 ArtClaw → Chat Panel → 输入 `/connect` |
| **OpenClaw** | 运行 `openclaw gateway restart` → 确认日志中 `mcp-bridge` 已加载 |

### 卸载

```bash
# 使用安装脚本卸载 (推荐):
python install.py --uninstall --maya                           # 卸载 Maya 插件
python install.py --uninstall --maya --maya-version 2024       # 指定版本
python install.py --uninstall --max                            # 卸载 Max 插件
python install.py --uninstall --ue --ue-project "C:\project"   # 卸载 UE 插件

# 或使用 install.bat 交互菜单 (选项 6/7/8)
```

卸载脚本会：
- 删除 DCCClawBridge / UEClawBridge 目录
- 从 `userSetup.py` / `startup.py` 中**仅移除 ArtClaw 代码块**（不删除用户自己的内容）
- OpenClaw 配置需手动修改（避免误删其他 server 配置）

## 🛠️ Skill 系统

ArtClaw 使用分层 Skill 管理系统，Skill 可跨 DCC 软件复用：

| 层级 | 目录 | 优先级 | 说明 |
|------|------|--------|------|
| 官方 | `Skills/00_official/` | 最高 | 内置 Skill |
| 团队 | `Skills/01_team/` | 高 | 团队共享，Git 同步 |
| 用户 | `Skills/02_user/` | 中 | 个人自定义 |
| 临时 | `Skills/99_custom/` | 低 | AI 临时生成 |

### 创建 Skill

在编辑器中直接用自然语言描述：

> "帮我创建一个 skill，批量重命名场景中选中的 Actor，加上指定前缀"

AI 会自动生成 `manifest.json` + `__init__.py` + `SKILL.md`，确认后即可使用。

或使用 CLI：

```bash
python artclaw.py skill list            # 列出所有 Skill
python artclaw.py skill test scene_ops   # 测试指定 Skill
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！特别欢迎以下方向的贡献：

- 🔌 **新 DCC 桥接实现** — Blender、Houdini 等
- 🛠️ **新 Skill** — 适用于各 DCC 的实用 Skill
- 📖 **文档改进** — 使用教程、最佳实践

### 贡献流程

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feat/my-feature`
3. 提交更改：`git commit -m "feat: add my feature"`
4. 推送并创建 PR

详见 [贡献指南](docs/skills/CONTRIBUTING.md)。

## 📖 文档

详细文档位于 `docs/` 目录：

- **[系统架构设计](docs/specs/系统架构设计.md)** — 整体架构与设计原则
- **[Skill 开发指南](docs/skills/SKILL_DEVELOPMENT_GUIDE.md)** — 编写自定义 Skill
- **[Skill 规范](docs/skills/MANIFEST_SPEC.md)** — manifest.json 格式规范
- **[MCP Bridge 部署](openclaw-mcp-bridge/README.md)** — OpenClaw 集成详细说明
- **[DCCClawBridge](subprojects/DCCClawBridge/README.md)** — Maya / 3ds Max 插件详细说明
- **[贡献指南](docs/skills/CONTRIBUTING.md)** — 如何为项目贡献

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

## 👤 作者

**Ivan(杨己力)** — [@IvanYangYangXi](https://github.com/IvanYangYangXi)
