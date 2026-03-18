# DCCClawBridge

Maya / 3ds Max 共享的 AI Agent 桥接插件，通过统一的 Qt 界面和薄适配层接入 ArtClaw MCP 体系。

## 架构

```
DCCClawBridge/
├── artclaw_ui/              # 通用 Qt 界面（Chat Panel + 主题）
│   ├── chat_panel.py        # 主聊天面板 (流式显示 + /命令 + 快捷输入)
│   └── theme.py             # DCC 配色方案
├── adapters/                # DCC 薄适配层
│   ├── base_adapter.py      # 抽象接口
│   ├── maya_adapter.py      # Maya 实现
│   └── max_adapter.py       # 3ds Max 实现
├── core/                    # 共享核心
│   ├── bridge_dcc.py        # OpenClaw 通信（Qt signal/slot）
│   ├── mcp_server.py        # MCP WebSocket 服务器
│   ├── skill_runtime.py     # Skill 加载/管理
│   ├── knowledge_base.py    # 知识库
│   ├── memory_store.py      # 分层记忆
│   ├── health_check.py      # 环境健康检查
│   ├── config.py            # 配置管理
│   └── dependency_manager.py # 依赖自动安装
├── maya_setup/              # Maya 部署
│   └── userSetup.py
├── max_setup/               # Max 部署
│   └── startup.py
├── skills/                  # DCC 特有 Skill
│   ├── maya/
│   ├── max/
│   └── common/
└── tests/
```

## 支持平台

| DCC | 最低版本 | Python | 端口 | Adapter |
|-----|---------|--------|------|---------|
| Maya | 2022 | 3.9+ | 8081 | maya_adapter.py |
| 3ds Max | 2024 | 3.9+ | 8082 | max_adapter.py |

## 快速开始 (Maya)

### 方式 1: 开发模式

设置环境变量，将 `userSetup.py` 复制到 Maya scripts 目录：

```bash
set ARTCLAW_BRIDGE_PATH=D:\MyProject_D\artclaw_bridge
copy maya_setup\userSetup.py %USERPROFILE%\Documents\maya\2023\scripts\
```

### 方式 2: 直接部署

将整个 `DCCClawBridge/` 目录复制到 Maya scripts 目录：

```bash
xcopy /E DCCClawBridge %USERPROFILE%\Documents\maya\2023\scripts\DCCClawBridge\
copy maya_setup\userSetup.py %USERPROFILE%\Documents\maya\2023\scripts\
```

### 使用

1. 启动 Maya → ArtClaw 菜单自动出现
2. 点击 **ArtClaw → 打开 Chat Panel**
3. 点击 **连接** 或输入 `/connect`
4. 开始对话

## 依赖

- `websockets` — 首次启动自动安装到 `Lib/` 目录
- `PySide2` — Maya 内置
