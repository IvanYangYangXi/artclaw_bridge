# ArtClaw Bridge

**让 DCC 工具通过 MCP 协议接入 AI Agent 的桥接框架**

ArtClaw Bridge 为 Unreal Engine、Maya、3ds Max 等数字内容创作（DCC）软件提供统一的 AI 桥接层。通过 [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) 协议，AI Agent 可以直接理解和操作编辑器环境。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![UE](https://img.shields.io/badge/Unreal%20Engine-5.7-black.svg)
![Status](https://img.shields.io/badge/status-beta-orange.svg)

---

## ✨ 特性

- **UE 编辑器内 AI 对话面板** — 直接在 Unreal Editor 中与 AI 交互，操作场景、材质、资产
- **MCP 协议标准通信** — 基于 WebSocket 的 JSON-RPC 2.0，符合 MCP 规范
- **Skill 热加载系统** — 分层管理（官方/团队/用户/临时），运行时动态加载
- **本地 RAG 知识库** — 索引 UE API 文档和项目文档，语义检索辅助 AI 决策
- **AI 生成 Skill** — 用自然语言描述需求，AI 自动生成可执行的编辑器 Skill
- **安全守卫** — 事务保护（Undo Guard）、风险评估、主线程调度
- **OpenClaw 集成** — 通过 MCP Bridge 插件无缝接入 [OpenClaw](https://github.com/openclaw/openclaw) Agent 框架

## 🏗️ 架构

```
┌─────────────────────┐
│   AI Agent (LLM)    │
│   via OpenClaw       │
└────────┬────────────┘
         │ WebSocket (MCP)
┌────────▼────────────┐
│  MCP Bridge Plugin   │  ← OpenClaw 插件，桥接 MCP 工具
└────────┬────────────┘
         │ WebSocket JSON-RPC
┌────────▼────────────┐
│  MCP Server (Python) │  ← 运行在 UE 内置 Python 中
│  ┌────────────────┐  │
│  │ Skills Engine   │  │  ← 热加载 Skill 模块
│  │ Knowledge Base  │  │  ← 本地 RAG 检索
│  │ Memory Store    │  │  ← 项目记忆存储
│  └────────────────┘  │
└────────┬────────────┘
         │ UE Python API
┌────────▼────────────┐
│  Unreal Engine       │
│  Editor Subsystem    │  ← C++ 插件：UI / 生命周期 / 主线程调度
└─────────────────────┘
```

## 📦 项目结构

```
artclaw_bridge/
├── subprojects/UEDAgentProj/        # UE 工程
│   └── Plugins/UEClawBridge/        # UE 插件（C++ + Python）
│       ├── Source/                   # C++ 源码（UI、子系统、本地化）
│       └── Content/Python/           # Python（MCP Server、Skills、工具链）
├── openclaw-mcp-bridge/             # OpenClaw MCP Bridge 插件
├── cli/                             # ArtClaw CLI 工具
├── skills/                          # Skill 模板库
├── team_skills/                     # 团队共享 Skill（Git 同步）
├── docs/                            # 项目文档
└── tests/                           # 测试用例
```

## 🚀 快速开始

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
"C:\Epic Games\UE_5.5\Engine\Binaries\ThirdParty\Python3\Win64\python.exe" -m pip install websockets pydantic
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

ArtClaw 使用分层 Skill 管理系统：

| 层级 | 目录 | 优先级 | 说明 |
|------|------|--------|------|
| 官方 | `Skills/00_official/` | 最高 | 内置 Skill |
| 团队 | `Skills/01_team/` | 高 | 团队共享，Git 同步 |
| 用户 | `Skills/02_user/` | 中 | 个人自定义 |
| 临时 | `Skills/99_custom/` | 低 | AI 临时生成 |

### 创建 Skill

在 UE 编辑器中直接用自然语言描述：

> "帮我创建一个 skill，批量重命名场景中选中的 Actor，加上指定前缀"

AI 会自动生成 `manifest.json` + `__init__.py` + `SKILL.md`，确认后即可使用。

或使用 CLI：

```bash
python artclaw.py skill list          # 列出所有 Skill
python artclaw.py skill test scene_ops  # 测试指定 Skill
```

## 📖 文档

详细文档位于 `docs/` 目录：

- **[系统架构设计](docs/specs/系统架构设计.md)** — 整体架构与设计原则
- **[Skill 开发指南](docs/skills/SKILL_DEVELOPMENT_GUIDE.md)** — 编写自定义 Skill
- **[Skill 规范](docs/skills/MANIFEST_SPEC.md)** — manifest.json 格式规范
- **[MCP Bridge 部署](openclaw-mcp-bridge/README.md)** — OpenClaw 集成详细说明
- **[贡献指南](docs/skills/CONTRIBUTING.md)** — 如何为项目贡献

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feat/my-feature`
3. 提交更改：`git commit -m "feat: add my feature"`
4. 推送并创建 PR

详见 [贡献指南](docs/skills/CONTRIBUTING.md)。

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

## 👤 作者

**Ivan(杨己力)** — [@IvanYangYangXi](https://github.com/IvanYangYangXi)
