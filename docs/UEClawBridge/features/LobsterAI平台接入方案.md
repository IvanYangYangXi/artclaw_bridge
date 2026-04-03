# LobsterAI (有道龙虾) 平台接入方案

> **版本**: v1.1  
> **日期**: 2026-04-03  
> **状态**: Phase 10.1-10.2 已完成  
> **作者**: 小优

---

## 一、背景与目标

### 1.1 背景

ArtClaw Bridge 当前以 OpenClaw 为主力平台，Claude Desktop stdio 桥接 POC 已完成。现需接入网易内部 AI Agent 平台 **LobsterAI (有道龙虾)**，作为第三个支持的平台。

### 1.2 目标

1. **复用最大化**：DCC 插件层（UE/Maya/Max）和共享核心层（core/）零改动
2. **平台切换外置**：切换脚本独立于 UE/DCC 插件，不增加插件内置复杂度（低频操作）
3. **MCP 工具复用**：LobsterAI 通过标准 MCP 协议连接 DCC 的 MCP Server，复用现有 `run_ue_python` / `run_python`
4. **渐进式**：先跑通最小链路，再补全聊天面板集成

### 1.3 前置条件（已确认）

| 项目 | 结论 | 来源 |
|------|------|------|
| **MCP 支持方式** | 内置 mcp-bridge 插件（WebSocket） | openclaw.json 分析 |
| **聊天协议** | OpenClaw Gateway RPC (端口 18790) | gateway-port.json |
| **Agent / Session 模型** | 与 OpenClaw 完全一致 | openclaw.json agents 配置 |
| **认证方式** | Gateway token (内部管理) | openclaw.json gateway.auth |
| **SDK / API 文档** | 无需，直接复用 OpenClaw 协议 | — |
| **DCC 内嵌面板** | Phase 1 不需要，LobsterAI 客户端操作 | — |
| **Skills 目录** | `%APPDATA%/LobsterAI/SKILLs/` + `skills.load.extraDirs` | openclaw.json skills 配置 |

---

## 二、架构分析：复用什么，新建什么

### 2.1 当前三层架构

```
┌─────────────────────────────────────────────────────┐
│  DCC 插件层 (UE / Maya / Max)                        │  ← 完全复用，零改动
│  MCP Server (run_ue_python / run_python)             │
│  Skill Hub / Memory / Knowledge Base                 │
└──────────────────┬──────────────────────────────────┘
                   │ 标准 MCP JSON-RPC (WebSocket)
┌──────────────────┴──────────────────────────────────┐
│  共享核心层 core/                                     │  ← 完全复用，零改动
│  bridge_core / bridge_config / memory_core           │
└──────────────────┬──────────────────────────────────┘
                   │ 平台特定协议
┌──────────────────┴──────────────────────────────────┐
│  平台 Bridge (可替换)                                 │  ← 新建 platforms/lobster/
│  openclaw/ │ claude/ │ lobster/ (新增)               │
└─────────────────────────────────────────────────────┘
```

### 2.2 复用清单

| 组件 | 复用情况 | 说明 |
|------|----------|------|
| DCC 插件 (UE/Maya/Max) | ✅ 完全复用 | MCP Server 不感知平台 |
| MCP 工具 (run_ue_python / run_python) | ✅ 完全复用 | 标准 MCP 协议 |
| Skill 体系 (skill_hub + 所有 Skills) | ✅ 完全复用 | Python API 不变 |
| 记忆系统 (memory_core) | ✅ 完全复用 | 独立于平台 |
| 知识库 (knowledge_base) | ✅ 完全复用 | 独立于平台 |
| core/bridge_config.py | ✅ 复用 + 新增配置项 | `_PLATFORM_DEFAULTS` 加 lobster 条目 |
| install.py | ✅ 复用 + 新增平台选项 | `PLATFORM_CONFIGS` 加 lobster 条目 |
| 平台切换脚本 | 🆕 新建 | `switch_platform.py`（外置） |

### 2.3 新建清单

| 组件 | 工作量预估 | 说明 |
|------|-----------|------|
| `platforms/lobster/` 目录 | — | 平台适配层 |
| LobsterAI MCP 桥接器 | 取决于 MCP 支持方式 | 见方案 A/B/C |
| LobsterAI 聊天 Bridge（可选） | ~300-500 行 | 上行链路，类似 openclaw_chat.py |
| 配置模板 | ~50 行 | lobster-config-snippet.json |
| 平台切换脚本 | ~200 行 | `scripts/switch_platform.py` |
| 文档 | — | README + 使用说明 |

---

## 三、MCP 链路方案（下行：工具调用）

根据 LobsterAI 的 MCP 支持方式，有三种方案：

### 方案 A：LobsterAI 原生支持 WebSocket MCP（最优）

**前提**：LobsterAI 能直接连接 WebSocket MCP Server（如 `ws://127.0.0.1:8080`）

```
LobsterAI 客户端/服务端
  └── MCP Client (WebSocket)
        └── 直连 DCC MCP Server (ws://127.0.0.1:8080/8081/8082)
              └── run_ue_python / run_python
```

**工作量**：几乎为零（仅需配置），只需在 LobsterAI 侧配置 MCP Server 地址。

**需要做的**：
- `platforms/lobster/config/` 提供 LobsterAI 侧的配置模板
- 测试验证

### 方案 B：LobsterAI 支持 stdio MCP（复用 Claude 方案）

**前提**：LobsterAI 支持 stdio 方式启动 MCP Server 子进程

```
LobsterAI
  └── stdio MCP Client
        └── artclaw_stdio_bridge.py (复用 Claude 的桥接器)
              └── WebSocket → DCC MCP Server (8080/8081/8082)
```

**工作量**：~2 小时
- 完全复用 `platforms/claude/artclaw_stdio_bridge.py`（或提升为通用组件）
- 只需写 LobsterAI 侧的配置模板

**改进点**：将 `artclaw_stdio_bridge.py` 从 `platforms/claude/` 提升到 `core/` 或 `tools/`，成为通用的 stdio→WebSocket 桥接器，供所有 stdio-only 平台复用。

### 方案 C：LobsterAI 有自己的 Gateway/中间层

**前提**：LobsterAI 有类似 OpenClaw Gateway 的中间层，需要通过其私有协议注册工具

```
LobsterAI Gateway / 中间层
  └── lobster_bridge 插件 (类似 mcp-bridge)
        └── 连接 DCC MCP Server
              └── 工具注册 + 调用转发
```

**工作量**：1-3 天，取决于 LobsterAI Gateway 的插件机制
- 需要写 `platforms/lobster/gateway/` 下的插件代码
- 类似 `platforms/openclaw/gateway/index.ts`

### 方案 D：LobsterAI 仅提供 REST/HTTP API（无 MCP 原生支持）

**前提**：LobsterAI 不支持 MCP，但提供 HTTP API 供工具注册和调用

```
LobsterAI HTTP API
  └── lobster_mcp_adapter.py (HTTP→MCP 适配器)
        └── 工具注册: POST /tools → 从 DCC MCP Server 获取 tools/list
        └── 工具调用: POST /tool_call → 转发到 DCC MCP Server tools/call
```

**工作量**：~1 天
- 写一个 HTTP 服务 + MCP Client 的适配器
- ~300 行 Python

### 推荐策略

**先确认 LobsterAI 的 MCP 支持方式**，然后：
- WebSocket → 方案 A（零工作量）
- stdio → 方案 B（复用已有桥接器）
- 有 Gateway → 方案 C（写插件）
- 仅 HTTP → 方案 D（写适配器）

---

## 四、聊天链路方案（上行：用户与 AI 对话）

### 4.1 场景分析

| 场景 | 说明 | 需要聊天 Bridge？ |
|------|------|-------------------|
| 用户在 LobsterAI 客户端操作 | LobsterAI 客户端直接调用 DCC 工具 | ❌ 不需要（类似 Claude Desktop） |
| 用户在 DCC 内嵌面板操作 | DCC Chat Panel → LobsterAI → AI 回复 | ✅ 需要（类似 OpenClaw） |

### 4.2 场景一：LobsterAI 客户端操作（推荐先做）

类似 Claude Desktop 模式：
- 用户在 LobsterAI 客户端打字
- LobsterAI 通过 MCP 调用 DCC 工具
- 不需要 DCC 内嵌聊天面板
- **不需要写聊天 Bridge**

```
用户 → LobsterAI 客户端 → AI → MCP 工具调用 → DCC
                                                  ↓
                                          执行结果返回
                                                  ↓
                              LobsterAI 客户端显示结果
```

### 4.3 场景二：DCC 内嵌面板操作（后续扩展）

类似 OpenClaw 模式，需要：
1. `lobster_ws.py` — 连接 LobsterAI 服务端（WebSocket 或 HTTP 长轮询）
2. `lobster_chat.py` — 聊天 API（发消息、接收流式回复、session 管理）
3. C++ 端 `FLobsterPlatformBridge` 实现 `IAgentPlatformBridge` 接口

**工作量**：~2-3 天（取决于 LobsterAI 的聊天协议复杂度）

### 4.4 推荐策略

**Phase 1**：先做"LobsterAI 客户端操作"模式（只需 MCP 链路，工作量极小）  
**Phase 2**：如有需求再做 DCC 内嵌面板模式（需要聊天 Bridge）

---

## 五、平台切换方案（外置脚本）

### 5.1 设计原则

- **切换是低频操作**，不需要内置到 UE/DCC 插件 UI
- **外置脚本** `scripts/switch_platform.py`，命令行运行
- 切换后需要**重启 DCC**（因为 bridge 模块在启动时加载）

### 5.2 切换脚本设计

```
scripts/switch_platform.py
```

**功能**：
1. 修改 `~/.artclaw/config.json` 的 platform 配置
2. 将目标平台的 bridge 文件复制到各 DCC 安装目录
3. 更新 MCP 配置（如需要）
4. 提示用户重启 DCC

**用法**：
```bash
# 查看当前平台
python scripts/switch_platform.py --status

# 切换到 LobsterAI
python scripts/switch_platform.py --to lobster

# 切回 OpenClaw
python scripts/switch_platform.py --to openclaw

# 列出可用平台
python scripts/switch_platform.py --list
```

### 5.3 切换流程

```
switch_platform.py --to lobster
  │
  ├─ 1. 读取 ~/.artclaw/config.json
  │     → 获取当前平台 (openclaw) 和各 DCC 安装路径
  │
  ├─ 2. 更新 config.json
  │     → platform.type = "lobster"
  │     → platform.gateway_url = "<lobster_gateway_url>"
  │     → skills.installed_path = "~/.openclaw/skills"  (Skills 共享，不随平台变)
  │     → mcp.config_path = "<lobster_config_path>"
  │
  ├─ 3. 复制平台 bridge 文件到 DCC 安装目录
  │     ├─ UE: Plugins/UEClawBridge/Content/Python/
  │     │     → 删除旧 openclaw_*.py → 复制 lobster_*.py
  │     ├─ Maya: Documents/maya/2023/scripts/DCCClawBridge/core/
  │     │     → 删除旧 openclaw_*.py → 复制 lobster_*.py
  │     └─ Max: 同 Maya 模式
  │
  ├─ 4. 更新 DCC 内 bridge_config.py（已是共享模块，自动读 config.json，无需改）
  │
  ├─ 5. 平台特定配置
  │     ├─ OpenClaw: 更新 ~/.openclaw/openclaw.json (MCP server 条目)
  │     └─ LobsterAI: 更新 LobsterAI 侧配置（如有）
  │
  └─ 6. 输出提示
        → "已切换到 LobsterAI 平台"
        → "请重启所有已打开的 DCC 软件（UE/Maya/Max）"
        → "如需切回: python switch_platform.py --to openclaw"
```

### 5.4 DCC 安装路径发现

切换脚本需要知道各 DCC 的安装目录，数据来源：

1. **UE 项目路径**：从 `~/.artclaw/config.json` 的历史安装记录
2. **Maya/Max 路径**：按约定目录扫描（Documents/maya/\*/scripts/DCCClawBridge/）
3. **手动指定**：`--ue-project <path>` `--maya-version 2023` 等参数

```python
def discover_dcc_installations() -> dict:
    """自动发现已安装 ArtClaw 的 DCC 目录"""
    installations = {}
    
    # Maya: 扫描 ~/Documents/maya/*/scripts/DCCClawBridge/
    maya_base = Path.home() / "Documents" / "maya"
    if maya_base.exists():
        for ver_dir in maya_base.iterdir():
            dcc_dir = ver_dir / "scripts" / "DCCClawBridge"
            if dcc_dir.exists():
                installations[f"maya-{ver_dir.name}"] = dcc_dir / "core"
    
    # UE: 从 config.json 读取上次安装的项目路径
    config = load_artclaw_config()
    ue_project = config.get("ue_project_path", "")
    if ue_project:
        ue_python = Path(ue_project) / "Plugins" / "UEClawBridge" / "Content" / "Python"
        if ue_python.exists():
            installations["ue"] = ue_python
    
    return installations
```

### 5.5 Skills 共享策略

**Skills 不随平台切换而变化**。无论用 OpenClaw 还是 LobsterAI：
- Skills 始终安装在 `~/.openclaw/skills/`（或配置的路径）
- `skill_hub.py` 从配置的 `skills.installed_path` 读取
- 切换平台时 `skills.installed_path` **保持不变**

> 如果 LobsterAI 有自己的 Skill 分发机制，可以额外配置 `lobster_skills_path`，但 ArtClaw 的 Skills 仍然走统一目录。

---

## 六、新增文件清单

### 6.1 `platforms/lobster/` 目录结构

```
platforms/lobster/
├── README.md                          # 使用说明
├── __init__.py                        # Python 包标记
├── config/
│   └── lobster-config-snippet.json    # LobsterAI 侧 MCP 配置模板
│
│  ── 以下文件根据 MCP 支持方式选择 ──
│
│  方案 A (WebSocket MCP): 无需额外文件
│
│  方案 B (stdio MCP):
│  └── (复用 core/artclaw_stdio_bridge.py)
│
│  方案 C (有 Gateway):
│  └── gateway/
│      └── lobster_bridge_plugin.py    # LobsterAI Gateway 插件
│
│  方案 D (HTTP API):
│  └── lobster_mcp_adapter.py          # HTTP→MCP 适配器
│
│  ── 如需 DCC 内嵌聊天面板 ──
│
├── lobster_ws.py                      # LobsterAI 通信核心
├── lobster_chat.py                    # 聊天 API + 流式写文件
└── lobster_diagnose.py                # 诊断工具
```

### 6.2 `scripts/switch_platform.py`

```
scripts/
└── switch_platform.py                 # 平台切换脚本（外置）
```

### 6.3 配置变更

**bridge_config.py** — `_PLATFORM_DEFAULTS` 新增：

```python
"lobster": {
    "gateway_url": "<待确认>",         # LobsterAI 服务地址
    "mcp_port": 8080,                  # DCC MCP Server 端口（不变）
    "skills_installed_path": "~/.openclaw/skills",  # Skills 共享
    "mcp_config_path": "<待确认>",     # LobsterAI 侧配置路径
    "mcp_config_key": "<待确认>",      # MCP servers 在配置中的 JSON key
},
```

**install.py** — `PLATFORM_CONFIGS` 新增：

```python
"lobster": {
    "gateway_url": "<待确认>",
    "mcp_port": 8080,
    "skills_installed_path": "~/.openclaw/skills",
    "mcp_config_path": "<待确认>",
    "mcp_config_key": "<待确认>",
    "bridge_file": "lobster_bridge.py",  # 或根据方案调整
    "has_gateway": False,                # 待确认
    "has_setup_config": False,           # 待确认
},
```

---

## 七、stdio 桥接器通用化（建议）

当前 `artclaw_stdio_bridge.py` 在 `platforms/claude/` 下，但它本质上是通用组件（任何 stdio MCP 客户端都能用）。建议提升为共享工具：

### 方案：提升到 tools/ 或 core/

```
Before:
  platforms/claude/artclaw_stdio_bridge.py

After:
  tools/artclaw_stdio_bridge.py          # 通用 stdio→WebSocket MCP 桥接器
  platforms/claude/config/               # Claude 配置模板（引用 tools/ 的桥接器）
  platforms/lobster/config/              # LobsterAI 配置模板（同上）
```

这样 Claude 和 LobsterAI（如果走 stdio）都引用同一个桥接器，只是配置不同。

---

## 八、开发路线图

### Phase 10.1：基础设施准备（~2 小时）

| 任务 | 说明 | 状态 |
|------|------|------|
| 创建 `platforms/lobster/` 目录骨架 | README + __init__.py + setup_lobster_config.py | ✅ 完成 |
| bridge_config.py 加 lobster 平台默认值 | `_PLATFORM_DEFAULTS["lobster"]` | ✅ 完成 |
| install.py 加 lobster 平台配置 | `PLATFORM_CONFIGS["lobster"]` + `--platform lobster` | ✅ 完成 |
| install.py 配置脚本动态查找 | 从硬编码 `setup_openclaw_config.py` 改为 `setup_*_config.py` glob | ✅ 完成 |

### Phase 10.2：MCP 链路打通

| 场景 | 工作量 | 状态 |
|------|--------|------|
| 方案 A: LobsterAI 内置 OpenClaw + mcp-bridge | 配置注入 | ✅ 完成 |

**结论**: LobsterAI 底层就是 OpenClaw (Gateway 端口 18790)，mcp-bridge 插件已内置且 enabled。
只需通过 `setup_lobster_config.py` 注入 servers 配置和 agent tools.allow 通配符。

### Phase 10.3：端到端验证（~2 小时）

| 任务 | 说明 | 状态 |
|------|------|------|
| LobsterAI 发现 ArtClaw MCP 工具 | tools/list 返回 run_ue_python | 待测试 |
| LobsterAI 执行 UE 操作 | 通过 run_ue_python 创建 Actor | 待测试 |
| LobsterAI 执行 Maya 操作 | 通过 run_python 操作场景 | 待测试 |
| get_context 验证 | 编辑器状态正确返回 | 待测试 |

### Phase 10.4：install.bat 集成

| 任务 | 说明 | 状态 |
|------|------|------|
| install.py --platform lobster 验证 | Skills + 配置注入一键完成 | ✅ 完成 |
| install.bat 交互式选择加 lobster | bat 脚本加平台选项 | 待做 |

### Phase 10.5：DCC 内嵌聊天面板（可选，后续）

| 任务 | 说明 | 状态 |
|------|------|------|
| lobster_ws.py | LobsterAI 通信核心 | 待做 |
| lobster_chat.py | 聊天 API 层 | 待做 |
| C++ FLobsterPlatformBridge | IAgentPlatformBridge 实现 | 待做 |
| DCC Qt 适配 | bridge_dcc.py 支持 lobster | 待做 |

---

## 九、平台切换与 DCC 的关系

### 9.1 切换对 DCC 的影响

```
切换前 (OpenClaw):
  DCC 启动 → 加载 openclaw_ws.py + openclaw_chat.py
           → 连接 OpenClaw Gateway ws://127.0.0.1:18789
           → Chat Panel 可用

切换后 (LobsterAI):
  DCC 启动 → 加载 lobster_ws.py + lobster_chat.py (如有)
           → 连接 LobsterAI 服务 (地址待确认)
           → Chat Panel 可用 (如有聊天 Bridge)
           
  或者（仅 MCP 模式）:
  DCC 启动 → MCP Server 正常启动 (ws://127.0.0.1:8080)
           → 等待 LobsterAI 客户端连接
           → Chat Panel 显示"LobsterAI 模式 - 请在 LobsterAI 客户端操作"
```

### 9.2 MCP Server 不受切换影响

DCC 内的 MCP Server（`mcp_server.py`）**始终运行**，不管当前平台是什么：
- 端口不变（UE:8080, Maya:8081, Max:8082）
- 工具不变（run_ue_python / run_python）
- 任何 MCP Client 都能连接

切换平台只影响**上行链路**（聊天面板连谁）和**配置层**（路径、认证等）。

### 9.3 无聊天 Bridge 时的 DCC UI 行为

如果 LobsterAI 平台只做 MCP 链路（不做内嵌聊天），DCC Chat Panel 应该：
- 显示当前平台信息："当前平台: LobsterAI"
- 显示 MCP Server 状态："MCP Server 运行中 (ws://127.0.0.1:8080)"
- 聊天输入框置灰，提示"请在 LobsterAI 客户端操作"
- `/status` 和 `/diagnose` 命令仍然可用

---

## 十、与现有文档的关系

| 文档 | 本方案的关系 |
|------|-------------|
| `系统架构设计.md` §1.3 平台可替换性 | LobsterAI 验证了这一设计 |
| `多平台兼容设计方案.md` Phase 9 | LobsterAI 是 Phase 10 的延续 |
| `第二平台协议调研.md` | LobsterAI 是第三平台，方法论相同 |
| `Agent切换方案调研.md` | Agent 切换是平台内切换，平台切换是跨平台切换，两者独立 |
| `openClaw集成方案.md` | LobsterAI 集成方案参照此文档结构 |

---

## 十一、风险与注意事项

1. **LobsterAI 协议未知**：最大风险。需要 Ivan 提供 API 文档或 SDK 后才能确定具体方案
2. **内部平台稳定性**：网易内部平台可能有版本迭代，需要关注 API 兼容性
3. **认证差异**：LobsterAI 的认证机制可能与 OpenClaw 差异较大，bridge_config 需要扩展认证适配
4. **聊天协议差异**：如果 LobsterAI 用 HTTP 长轮询而非 WebSocket，`lobster_ws.py` 实现方式会不同
5. **并行使用**：可能有用户同时连 OpenClaw 和 LobsterAI 的需求。当前设计是单平台切换，如需并行需要额外设计

---

## 十二、下一步行动

1. **[ ] Ivan 提供 LobsterAI 的 MCP 支持方式和 API 文档**
2. **[ ] 确定 MCP 链路方案（A/B/C/D）**
3. **[ ] 确定是否需要 DCC 内嵌聊天面板**
4. **[ ] 开始 Phase 10.1 基础设施准备**
5. **[ ] 实现 `scripts/switch_platform.py`**

---

## 变更记录

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-04-03 | v1.0 | 初始规划 |
| 2026-04-03 | v1.1 | Phase 10.1-10.2 实现完成。确认 LobsterAI = OpenClaw 封装 (Gateway 18790)，实现配置注入脚本，bridge_config/install.py 加 lobster 平台支持 |
