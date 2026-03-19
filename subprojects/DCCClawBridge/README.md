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

| DCC | 最低版本 | Python | 默认端口 | Adapter |
|-----|---------|--------|---------|---------|
| Maya | 2022 | 3.9+ | 8081 | maya_adapter.py |
| 3ds Max | 2024 | 3.9+ | 8082 | max_adapter.py |

## 安装

### 方式 1: 一键安装（推荐）

从项目根目录运行安装脚本：

```bash
# Windows 交互菜单
cd artclaw_bridge
install.bat

# 或 Python CLI
python install.py --maya                        # 安装 Maya (默认版本 2023)
python install.py --maya --maya-version 2024    # 安装到 Maya 2024
python install.py --max --max-version 2024      # 安装 Max
python install.py --maya --max --openclaw        # Maya + Max + OpenClaw
```

安装脚本会自动：
1. 复制 `DCCClawBridge/` 到 DCC 的标准 scripts 目录
2. 将 `bridge_core.py` 等共享模块打包到 `core/`（自包含，无需源码目录）
3. **安全处理 startup 文件**：
   - 如果用户已有 `userSetup.py` → **追加**模式，不覆盖原有内容
   - 使用 `# ===== ArtClaw Bridge START/END =====` 标记包裹
   - 重复运行安全（幂等），不会产生重复代码
4. 配置 OpenClaw mcp-bridge

### 方式 2: 手动安装

<details>
<summary>Maya 手动安装（点击展开）</summary>

```bash
# 将 <版本> 替换为实际 Maya 版本号 (如 2023)
set MAYA_SCRIPTS=%USERPROFILE%\Documents\maya\<版本>\scripts

# 1. 复制 DCCClawBridge
xcopy /E /I subprojects\DCCClawBridge "%MAYA_SCRIPTS%\DCCClawBridge"

# 2. 复制共享模块到 core/ (自包含)
copy openclaw-mcp-bridge\bridge_core.py "%MAYA_SCRIPTS%\DCCClawBridge\core\"
copy openclaw-mcp-bridge\bridge_config.py "%MAYA_SCRIPTS%\DCCClawBridge\core\"
copy openclaw-mcp-bridge\bridge_diagnostics.py "%MAYA_SCRIPTS%\DCCClawBridge\core\"

# 3. 处理 userSetup.py
# 如果没有已有的 userSetup.py:
copy subprojects\DCCClawBridge\maya_setup\userSetup.py "%MAYA_SCRIPTS%\"

# 如果已有 userSetup.py: 将以下内容追加到文件末尾
# (不要覆盖! 打开 maya_setup/userSetup.py，复制全部内容，
#  用 "# ===== ArtClaw Bridge START/END =====" 注释包裹后追加)
```

</details>

<details>
<summary>3ds Max 手动安装（点击展开）</summary>

```bash
# 将 <版本> 替换为实际 Max 版本号 (如 2024)
set MAX_SCRIPTS=%LOCALAPPDATA%\Autodesk\3dsMax\<版本>\ENU\scripts

# 1. 复制 DCCClawBridge
xcopy /E /I subprojects\DCCClawBridge "%MAX_SCRIPTS%\DCCClawBridge"

# 2. 复制共享模块到 core/ (自包含)
copy openclaw-mcp-bridge\bridge_core.py "%MAX_SCRIPTS%\DCCClawBridge\core\"
copy openclaw-mcp-bridge\bridge_config.py "%MAX_SCRIPTS%\DCCClawBridge\core\"
copy openclaw-mcp-bridge\bridge_diagnostics.py "%MAX_SCRIPTS%\DCCClawBridge\core\"

# 3. 复制 startup 脚本
copy subprojects\DCCClawBridge\max_setup\startup.py "%MAX_SCRIPTS%\startup\artclaw_startup.py"
```

</details>

### 方式 3: 开发模式

适用于从源码开发/调试的场景：

```bash
# 设置环境变量指向项目根目录
set ARTCLAW_BRIDGE_PATH=D:\MyProject_D\artclaw_bridge

# 仅复制 startup 脚本 (不复制 DCCClawBridge 目录)
# Maya:
copy subprojects\DCCClawBridge\maya_setup\userSetup.py %USERPROFILE%\Documents\maya\2023\scripts\

# Max:
copy subprojects\DCCClawBridge\max_setup\startup.py %LOCALAPPDATA%\Autodesk\3dsMax\2024\ENU\scripts\startup\artclaw_startup.py
```

开发模式下，`userSetup.py` / `startup.py` 会通过 `ARTCLAW_BRIDGE_PATH` 环境变量定位源码目录。

## 使用

1. 启动 DCC 软件 → ArtClaw 菜单自动出现
2. 点击 **ArtClaw → 打开 Chat Panel**
3. 点击 **连接** 或输入 `/connect`
4. 开始对话

### 常用命令

| 命令 | 说明 |
|------|------|
| `/connect` | 连接 OpenClaw Gateway |
| `/disconnect` | 断开连接 |
| `/diagnose` | 运行连接诊断 |
| `/reset` | 重置会话 |

## 卸载

### 一键卸载

```bash
# 从项目根目录运行:
python install.py --uninstall --maya                    # 卸载 Maya 插件
python install.py --uninstall --maya --maya-version 2024  # 指定版本
python install.py --uninstall --max                     # 卸载 Max 插件
python install.py --uninstall --max --max-version 2025  # 指定版本

# 或使用 install.bat 交互菜单 (选项 6/7)
```

卸载脚本会：
- 删除 DCC scripts 目录下的 `DCCClawBridge/` 目录
- 从 `userSetup.py` / `startup.py` 中**仅移除 ArtClaw 代码块**（不删除用户自己的内容）

### 手动卸载

```bash
# Maya:
rmdir /S /Q "%USERPROFILE%\Documents\maya\<版本>\scripts\DCCClawBridge"
# 编辑 userSetup.py，删除 "ArtClaw Bridge START" 到 "ArtClaw Bridge END" 之间的内容

# Max:
rmdir /S /Q "%LOCALAPPDATA%\Autodesk\3dsMax\<版本>\ENU\scripts\DCCClawBridge"
del "%LOCALAPPDATA%\Autodesk\3dsMax\<版本>\ENU\scripts\startup\artclaw_startup.py"
```

> **注意**: OpenClaw 配置 (`~/.openclaw/openclaw.json`) 需手动编辑，移除 `maya-editor` / `max-editor` 相关 server 条目。

## 依赖

- `websockets` — 首次启动自动安装到 `Lib/` 目录
- `PySide2` — Maya / 3ds Max 内置
- `bridge_core.py` 等共享模块 — 安装脚本自动打包到 `core/` (或通过 `ARTCLAW_BRIDGE_PATH` 开发模式引用)
