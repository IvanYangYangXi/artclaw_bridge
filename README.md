# ArtClaw Bridge

**让 DCC 工具通过 MCP 协议接入 AI Agent 的桥接框架**

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
| **Maya** | 🔜 计划中 | — | Python + MEL，节点编辑器集成 |
| **3ds Max** | 🔜 计划中 | — | Python / MaxScript |
| **Blender** | 💡 考虑中 | — | Python API |

> 当前已完成 Unreal Engine 端的完整实现。其他 DCC 软件的支持正在规划中，框架层面已预留扩展接口。欢迎社区贡献其他 DCC 的桥接实现！

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
└───┬────┘└───┬────┘└───┬────┘└───┬────┘
    │         │         │         │
    ▼         ▼         ▼         ▼
  UE API   Maya API  Max API    ...
```

每个 DCC 软件运行独立的 MCP Server，通过统一协议向 AI Agent 暴露编辑器能力。Skill 系统、知识库、记忆存储等核心模块跨 DCC 共享。

## 📦 项目结构

```
artclaw_bridge/
├── subprojects/                     # 各 DCC 软件的工程实现
│   ├── UEDAgentProj/                # ✅ Unreal Engine 工程
│   │   └── Plugins/UEClawBridge/    #    UE 插件（C++ + Python）
│   ├── MayaAgentProj/               # 🔜 Maya 工程（计划中）
│   └── MaxAgentProj/                # 🔜 3ds Max 工程（计划中）
├── openclaw-mcp-bridge/             # OpenClaw MCP Bridge 插件（通用）
├── cli/                             # ArtClaw CLI 工具
├── skills/                          # Skill 模板库（跨 DCC 共享）
├── team_skills/                     # 团队共享 Skill（Git 同步）
├── docs/                            # 项目文档
│   ├── specs/                       #   通用规范
│   ├── skills/                      #   Skill 开发文档
│   ├── UEClawBridge/                #   ✅ UE 插件文档
│   ├── MayaAgent/                   #   🔜 Maya 插件文档（待建）
│   └── features/                    #   OpenClaw 集成功能
└── tests/                           # 测试用例
```

## 🚀 快速开始（Unreal Engine）

> 以下安装说明针对当前已实现的 UE 端。其他 DCC 软件的安装文档将在实现后补充。

### 前置条件

- **Unreal Engine** 5.7（其他版本未验证）
- **OpenClaw** 已安装（`npm install -g openclaw`）
- **Python 依赖**：`websockets`、`pydantic`（由插件自动安装）

### 方式一：一键安装

```bash
# 克隆仓库
git clone https://github.com/IvanYangYangXi/artclaw_bridge.git

# 运行安装脚本（Windows）
cd artclaw_bridge/openclaw-mcp-bridge
setup.bat "C:\path\to\your\UE_Project"
```

安装脚本会自动：
1. 复制 UEClawBridge 插件到你的 UE 项目
2. 安装 Python 依赖
3. 配置 OpenClaw 集成

### 方式二：手动安装

#### 1. 安装 UE 插件

将 `subprojects/UEDAgentProj/Plugins/UEClawBridge` 复制到你的 UE 项目的 `Plugins/` 目录。

#### 2. 安装 Python 依赖

使用 UE 内置 Python 安装：

```bash
# Windows 示例（路径根据 UE 版本调整）
"C:\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe" -m pip install websockets pydantic
```

#### 3. 配置 OpenClaw

部署 MCP Bridge 插件：

```bash
# 复制插件文件到 OpenClaw 扩展目录
mkdir %USERPROFILE%\.openclaw\extensions\mcp-bridge
copy openclaw-mcp-bridge\mcp-bridge\* %USERPROFILE%\.openclaw\extensions\mcp-bridge\
```

在 `~/.openclaw/openclaw.json` 中添加配置：

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

#### 4. 启动

1. 打开 UE 项目，启用 **UE Claw Bridge** 插件
2. 重启编辑器
3. 打开面板：**Window 菜单 → UE Claw Bridge**
4. 重启 OpenClaw Gateway：`openclaw gateway restart`
5. 在面板中输入 `/diagnose` 验证连接

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

- 🔌 **新 DCC 桥接实现** — Maya、3ds Max、Blender 等
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
- **[贡献指南](docs/skills/CONTRIBUTING.md)** — 如何为项目贡献

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

## 👤 作者

**Ivan(杨己力)** — [@IvanYangYangXi](https://github.com/IvanYangYangXi)
