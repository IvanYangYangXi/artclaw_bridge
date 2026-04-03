# LobsterAI (有道龙虾) 平台接入方案

> **版本**: v1.2  
> **日期**: 2026-04-03  
> **状态**: Phase 10.1-10.2 已完成验证  
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
| **MCP 支持方式** | LobsterAI 内置 mcp-bridge 插件（WebSocket） | 实际验证 |
| **LobsterAI 架构** | LobsterAI = OpenClaw 封装版本 | Gateway 端口 18790 验证 |
| **聊天协议** | OpenClaw Gateway RPC (端口动态，当前 18790) | gateway-port.json |
| **Agent / Session 模型** | 与 OpenClaw 完全一致 | openclaw.json agents 配置 |
| **认证方式** | Gateway token (内部管理) | openclaw.json gateway.auth |
| **SDK / API 文档** | 无需，直接复用 OpenClaw 协议 | — |
| **Skills 目录** | `%APPDATA%/LobsterAI/SKILLs/` + `skills.load.extraDirs` | openclaw.json skills 配置 |
| **DCC 内嵌面板** | UE/Maya/Max 已有内嵌聊天面板，LobsterAI 侧未集成 | 现状 |
| **MCP 配置管理** | LobsterAI 使用集中式 MCP 管理（服务器端口动态，如 12982） | 实际验证 |

---

## 二、架构分析：复用什么，新建什么

### 2.1 当前三层架构

```
┌─────────────────────────────────────────────────────┐
│  DCC 插件层 (UE / Maya / Max)                        │  ← 完全复用，零改动
│  MCP Server (run_ue_python / run_python)             │
│  Skill Hub / Memory / Knowledge Base                 │
│  DCC 内嵌聊天面板 (已有)                              │
└──────────────────┬──────────────────────────────────┘
                   │ 标准 MCP JSON-RPC (WebSocket)
┌──────────────────┴──────────────────────────────────┐
│  共享核心层 core/                                     │  ← 完全复用，零改动
│  bridge_core / bridge_config / memory_core           │
└──────────────────┬──────────────────────────────────┘
                   │ LobsterAI = OpenClaw 协议
┌──────────────────┴──────────────────────────────────┐
│  LobsterAI平台 (OpenClaw 封装)                        │  ← 配置注入即可
│  Gateway (端口 18790) + mcp-bridge 插件               │
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
| DCC 内嵌聊天面板 | ✅ 已有 | UE/Maya/Max 已有内嵌面板 |
| core/bridge_config.py | ✅ 复用 + 新增配置项 | `_PLATFORM_DEFAULTS` 加 lobster 条目 |
| install.py | ✅ 复用 + 新增平台选项 | `PLATFORM_CONFIGS` 加 lobster 条目 |
| 平台切换脚本 | 🆕 新建 | `switch_platform.py`（外置） |

### 2.3 新建清单

| 组件 | 工作量预估 | 说明 |
|------|-----------|------|
| `platforms/lobster/` 目录 | — | 平台适配层 |
| 配置注入脚本 | ~100 行 | `setup_lobster_mcp.py` |
| 配置模板 | ~50 行 | lobster-config-snippet.json |
| 平台切换脚本 | ~200 行 | `platforms/common/switch_platform.py` |
| 文档 | — | 本方案 + 使用说明 |

---

## 三、MCP 链路方案（下行：工具调用）

### 3.1 实际验证结果

**LobsterAI 架构确认**：
- LobsterAI 底层就是 OpenClaw 的封装版本
- Gateway 端口：18790（动态，记录在 `gateway-port.json`）
- 内置 mcp-bridge 插件，支持 WebSocket MCP Server
- MCP 配置管理：集中式（服务器端口动态，如 12982）

**配置方式**：
LobsterAI 使用**集中式 MCP 管理**：
1. 用户在 LobsterAI 客户端界面添加 MCP Server 配置
2. 配置存储在 LobsterAI 服务器（端口动态，如 12982）
3. mcp-bridge 插件从服务器拉取配置
4. mcp-bridge 连接 WebSocket MCP Server（如 `ws://127.0.0.1:8080`）

**验证结果**：
```
✅ UE MCP Server 运行在 ws://127.0.0.1:8080
✅ 提供 run_ue_python 工具
✅ 直接 WebSocket 调用成功
✅ 执行 Python 代码成功（包括 unreal 模块）
✅ 获取关卡信息成功
```

### 3.2 配置注入方案

由于 LobsterAI 使用集中式 MCP 管理，**不能直接编辑 `openclaw.json`**（会被服务器配置覆盖）。

**正确做法**：
1. 用户通过 LobsterAI 客户端界面添加 MCP Server
2. 或使用配置注入脚本自动添加

**配置注入脚本** (`setup_lobster_mcp.py`)：
```python
# 通过 LobsterAI API 或配置数据库添加 MCP Server 配置
# 而不是直接编辑 openclaw.json
```

### 3.3 实际配置步骤（用户侧）

1. 打开 LobsterAI 客户端
2. 进入 **设置 → MCP Servers**
3. 点击 **添加 MCP Server**
4. 填写：
   - 名称：`artclaw-ue`
   - 类型：`WebSocket`
   - URL：`ws://127.0.0.1:8080`
   - 状态：✅ 启用
5. 保存
6. 完全退出 LobsterAI（包括系统托盘）
7. 重新启动 LobsterAI
8. 测试：`使用 run_ue_python 执行：print("Hello from ArtClaw!")`

### 3.4 方案对比

| 方案 | 工作量 | 状态 | 说明 |
|------|--------|------|------|
| 方案 A: LobsterAI 客户端界面配置 | 零代码 | ✅ 已验证 | 用户手动配置 |
| 方案 B: 配置注入脚本 | ~100 行 | ⏳ 待做 | 自动化配置 |
| 方案 C: 直接编辑 openclaw.json | ❌ 不可行 | 配置会被服务器覆盖 |

---

## 四、聊天链路方案（上行：用户与 AI 对话）

### 4.1 现状

**DCC 端**：
- ✅ UE 已有内嵌聊天面板（UEClawBridge 插件）
- ✅ Maya 已有内嵌聊天面板
- ✅ Max 已有内嵌聊天面板
- 面板功能：聊天输入、AI 回复显示、工具调用结果展示

**LobsterAI 端**：
- ✅ LobsterAI 客户端支持聊天
- ⚠️ DCC 内嵌面板未连接 LobsterAI

### 4.2 当前可用模式

**模式一：LobsterAI 客户端操作**（已可用）
```
用户 → LobsterAI 客户端 → AI → MCP 工具调用 → DCC
                                              ↓
                                      执行结果返回
                                              ↓
                          LobsterAI 客户端显示结果
```

**特点**：
- ✅ 无需额外开发
- ✅ MCP 工具调用正常
- ⚠️ 用户需要离开 DCC 环境，在 LobsterAI 客户端操作

**模式二：DCC 内嵌面板操作**（待开发）
```
用户 → DCC 内嵌面板 → bridge_chat.py → LobsterAI Gateway
                                            ↓
                                      AI 流式回复
                                            ↓
                          DCC 面板显示回复 + 工具调用结果
```

**特点**：
- ✅ 用户无需离开 DCC 环境
- ⚠️ 需要开发 LobsterAI 聊天 Bridge
- ⚠️ 需要 LobsterAI Gateway API 支持

### 4.3 推荐策略

**Phase 1（当前）**：使用 LobsterAI 客户端操作模式
- 零开发工作量
- MCP 工具调用已验证通过
- 适合开发和测试

**Phase 2（后续）**：开发 DCC 内嵌面板集成
- 需要 LobsterAI 提供 Gateway API 文档
- 开发 `lobster_chat.py` 桥接层
- 实现 DCC 面板 → LobsterAI 的完整链路

---

## 五、平台切换方案（外置脚本）

### 5.1 设计原则

- **切换是低频操作**，不需要内置到 UE/DCC 插件 UI
- **外置脚本** `platforms/common/switch_platform.py`，命令行运行
- 切换后需要**重启 DCC**（因为 bridge 模块在启动时加载）

### 5.2 切换脚本设计

```
platforms/common/switch_platform.py
```

**功能**：
1. 修改 `~/.artclaw/config.json` 的 platform 配置
2. 将目标平台的 bridge 文件复制到各 DCC 安装目录
3. 更新 MCP 配置（如需要）
4. 提示用户重启 DCC

**用法**：
```bash
# 查看当前平台
python platforms/common/switch_platform.py --status

# 切换到 LobsterAI
python platforms/common/switch_platform.py --to lobster

# 切回 OpenClaw
python platforms/common/switch_platform.py --to openclaw

# 列出可用平台
python platforms/common/switch_platform.py --list
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
  │     → platform.gateway_url = "http://127.0.0.1:18790"
  │     → skills.installed_path = "~/.openclaw/skills"  (Skills 共享，不随平台变)
  │     → mcp.config_path = "%APPDATA%/LobsterAI/openclaw/state/openclaw.json"
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
  │     └─ LobsterAI: 提示用户通过客户端界面配置 MCP Server
  │
  └─ 6. 输出提示
        → "已切换到 LobsterAI平台"
        → "请重启所有已打开的 DCC 软件（UE/Maya/Max）"
        → "在 LobsterAI 客户端 设置 → MCP Servers 中添加 artclaw-ue"
        → "如需切回：python switch_platform.py --to openclaw"
```

### 5.4 DCC 安装路径发现

切换脚本需要知道各 DCC 的安装目录，数据来源：

1. **UE 项目路径**：从 `~/.artclaw/config.json` 的历史安装记录
2. **Maya/Max 路径**：按约定目录扫描（Documents/maya/\*/scripts/DCCClawBridge/）
3. **手动指定**：`--ue-project <path>` `--maya-version 2023` 等参数

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
├── setup_lobster_config.py            # 配置注入脚本
├── config/
│   └── lobster-config-snippet.json    # LobsterAI 侧 MCP 配置模板
└── switch_platform.py                 # 平台切换脚本（也可放在 scripts/）
```

### 6.2 配置变更

**bridge_config.py** — `_PLATFORM_DEFAULTS` 新增：

```python
"lobster": {
    "gateway_url": "http://127.0.0.1:18790",  # LobsterAI Gateway 端口
    "mcp_port": 8080,                         # DCC MCP Server 端口（不变）
    "skills_installed_path": "~/.openclaw/skills",  # Skills 共享
    "mcp_config_path": "%APPDATA%/LobsterAI/openclaw/state/openclaw.json",
    "mcp_config_key": "plugins.entries.mcp-bridge.config",
    "has_client_ui": True,                  # LobsterAI 有独立客户端
    "mcp_config_via_ui": True,              # MCP 配置需通过客户端界面
},
```

**install.py** — `PLATFORM_CONFIGS` 新增：

```python
"lobster": {
    "gateway_url": "http://127.0.0.1:18790",
    "mcp_port": 8080,
    "skills_installed_path": "~/.openclaw/skills",
    "mcp_config_path": "%APPDATA%/LobsterAI/openclaw/state/openclaw.json",
    "mcp_config_key": "plugins.entries.mcp-bridge.config",
    "bridge_file": "lobster_bridge.py",
    "has_gateway": False,                   # LobsterAI 管理自己的 Gateway
    "has_setup_config": True,               # 需要配置注入脚本
    "setup_script": "setup_lobster_config.py",
},
```

---

## 七、开发路线图

### Phase 10.1：基础设施准备（✅ 已完成）

| 任务 | 说明 | 状态 |
|------|------|------|
| 创建 `platforms/lobster/` 目录骨架 | README + __init__.py + setup_lobster_config.py | ✅ 完成 |
| bridge_config.py 加 lobster 平台默认值 | `_PLATFORM_DEFAULTS["lobster"]` | ✅ 完成 |
| install.py 加 lobster 平台配置 | `PLATFORM_CONFIGS["lobster"]` + `--platform lobster` | ✅ 完成 |
| install.py 配置脚本动态查找 | 从硬编码 `setup_openclaw_config.py` 改为 `setup_*_config.py` glob | ✅ 完成 |
| 确认 LobsterAI = OpenClaw 封装 | Gateway 端口 18790，mcp-bridge 插件内置 | ✅ 完成 |

### Phase 10.2：MCP 链路打通（✅ 已验证）

| 任务 | 说明 | 状态 |
|------|------|------|
| UE MCP Server 运行 | `ws://127.0.0.1:8080` | ✅ 验证 |
| 直接 WebSocket 调用 | 通过 MCP 协议调用 `run_ue_python` | ✅ 验证 |
| Python 代码执行 | 包括 `unreal` 模块 | ✅ 验证 |
| 关卡信息查询 | `unreal.EditorLevelLibrary.get_editor_world()` | ✅ 验证 |
| LobsterAI 客户端配置 | 通过界面添加 MCP Server | ✅ 可用 |

### Phase 10.3：配置自动化（⏳ 待做）

| 任务 | 说明 | 状态 |
|------|------|------|
| 配置注入脚本 | 自动添加 MCP Server 配置到 LobsterAI | ⏳ 待做 |
| 测试配置同步 | 验证配置从服务器同步到 mcp-bridge | ⏳ 待做 |

### Phase 10.4：端到端验证（⏳ 待做）

| 任务 | 说明 | 状态 |
|------|------|------|
| LobsterAI 发现 ArtClaw MCP 工具 | tools/list 返回 run_ue_python | ⏳ 待测试 |
| LobsterAI 执行 UE 操作 | 通过 run_ue_python 创建 Actor | ⏳ 待测试 |
| LobsterAI 执行 Maya 操作 | 通过 run_python 操作场景 | ⏳ 待测试 |
| get_context 验证 | 编辑器状态正确返回 | ⏳ 待测试 |

### Phase 10.5：install.bat 集成（⏳ 待做）

| 任务 | 说明 | 状态 |
|------|------|------|
| install.py --platform lobster 验证 | Skills + 配置注入一键完成 | ⏳ 待做 |
| install.bat 交互式选择加 lobster | bat 脚本加平台选项 | ⏳ 待做 |

### Phase 10.6：DCC 内嵌聊天面板集成（⏳ 后续）

DCC和UE内嵌聊天面板已存在且功能完整，LobsterAI需要参考openClaw的接口适配DCC和UE的标准，并接通通信

---

## 八、平台切换与 DCC 的关系

### 8.1 切换对 DCC 的影响

```
切换前 (OpenClaw):
  DCC 启动 → 加载 openclaw_ws.py + openclaw_chat.py
           → 连接 OpenClaw Gateway ws://127.0.0.1:18789
           → Chat Panel 可用

切换后 (LobsterAI):
  DCC 启动 → 加载 lobster_ws.py + lobster_chat.py (如有)
           → 连接 LobsterAI Gateway ws://127.0.0.1:18790
           → Chat Panel 可用 (如有聊天 Bridge)
           
  或者（仅 MCP 模式，当前）:
  DCC 启动 → MCP Server 正常启动 (ws://127.0.0.1:8080)
           → 等待 LobsterAI 客户端连接
           → Chat Panel 显示"LobsterAI 模式 - 请在 LobsterAI 客户端操作"
```

### 8.2 MCP Server 不受切换影响

DCC 内的 MCP Server（`mcp_server.py`）**始终运行**，不管当前平台是什么：
- 端口不变（UE:8080, Maya:8081, Max:8082）
- 工具不变（run_ue_python / run_python）
- 任何 MCP Client 都能连接

切换平台只影响**上行链路**（聊天面板连谁）和**配置层**（路径、认证等）。

### 8.3 无聊天 Bridge 时的 DCC UI 行为

如果 LobsterAI平台只做 MCP 链路（不做内嵌聊天），DCC Chat Panel 应该：
- 显示当前平台信息："当前平台：LobsterAI"
- 显示 MCP Server 状态："MCP Server 运行中 (ws://127.0.0.1:8080)"
- 聊天输入框置灰，提示"请在 LobsterAI 客户端操作"
- `/status` 和 `/diagnose` 命令仍然可用

---

## 九、实际验证记录

### 9.1 环境信息

- **LobsterAI 版本**: OpenClaw 2026.3.2 (d7f7232)
- **Gateway 端口**: 18790
- **MCP 管理服务器端口**: 12982（动态）
- **UE MCP Server 端口**: 8080
- **测试时间**: 2026-04-03 15:30

### 9.2 验证步骤

**1. 确认 UE MCP Server 运行**
```powershell
netstat -ano | FindStr ":8080"
# 输出：TCP 127.0.0.1:8080 LISTENING
```

**2. 直接 WebSocket 调用测试**
```powershell
$ws = New-Object System.Net.WebSockets.ClientWebSocket
$ws.ConnectAsync("ws://127.0.0.1:8080", $null).Wait()
# 发送 initialize + tools/list
# 结果：返回 run_ue_python 工具
```

**3. 执行 Python 代码测试**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "run_ue_python",
    "arguments": {
      "code": "print(\"Hello from ArtClaw!\")"
    }
  }
}
```

**结果**：
```json
{
  "success": true,
  "exec_id": 6,
  "output": "Hello from ArtClaw!\n",
  "error": null,
  "execution_time": 0.0001
}
```

**4. 获取关卡信息测试**
```python
import unreal
world = unreal.EditorLevelLibrary.get_editor_world()
level_asset = world.get_outer()
print(f"Current level: {level_asset.get_path_name()}")
```

**结果**：
```
Current level: /Game/Maps/图生场景测试
```

### 9.3 验证结论

✅ **MCP 链路完全正常**
- UE MCP Server 运行正常
- WebSocket 连接稳定
- `run_ue_python` 工具可调用
- Python 代码执行成功
- `unreal` 模块访问正常

⚠️ **LobsterAI 工具集成受限**
- LobsterAI 配置 schema 不允许 `servers{}` 格式
- MCP 配置存储在 LobsterAI 服务器（端口 12982）
- 需要通过 LobsterAI 客户端界面配置
- mcp-bridge 插件从服务器拉取配置，不直接读取 openclaw.json

---

## 十、与现有文档的关系

| 文档 | 本方案的关系 |
|------|-------------|
| `系统架构设计.md` §1.3 平台可替换性 | LobsterAI 验证了这一设计 |
| `多平台兼容设计方案.md` Phase 9 | LobsterAI 是 Phase 10 的延续 |
| `第二平台协议调研.md` | LobsterAI 是第三平台，方法论相同 |
| `Agent 切换方案调研.md` | Agent 切换是平台内切换，平台切换是跨平台切换，两者独立 |
| `openClaw集成方案.md` | LobsterAI 集成方案参照此文档结构 |
| `UEClawBridge/specs/开发路线图.md` | Phase 10 对应 LobsterAI 集成 |

---

## 十一、风险与注意事项

1. **LobsterAI 配置同步机制**：MCP 配置存储在服务器端，客户端配置可能被覆盖
2. **配置 schema 限制**：LobsterAI 不允许 `servers{}` 格式，只能通过客户端界面配置
3. **内部平台稳定性**：网易内部平台可能有版本迭代，需要关注 API 兼容性
4. **并行使用**：可能有用户同时连 OpenClaw 和 LobsterAI 的需求。当前设计是单平台切换，如需并行需要额外设计
5. **DCC 内嵌面板未集成**：当前只能在 LobsterAI 客户端操作，DCC 内嵌面板未连接 LobsterAI

---

## 十二、下一步行动

### 立即可用

1. ✅ **使用 LobsterAI 客户端操作模式**
   - 在 LobsterAI 客户端 设置 → MCP Servers 中添加 `artclaw-ue`
   - URL: `ws://127.0.0.1:8080`
   - 测试：`使用 run_ue_python 执行：print("Hello from ArtClaw!")`

### 短期（Phase 10.3-10.5）

2. ⏳ **实现配置注入脚本**
   - 自动添加 MCP Server 配置到 LobsterAI 服务器
   - 或提供一键配置工具

3. ⏳ **实现平台切换脚本**
   - `platforms/common/switch_platform.py`
   - 支持 OpenClaw ↔ LobsterAI 切换

4. ⏳ **端到端验证**
   - LobsterAI 聊天中直接使用 `run_ue_python`
   - 测试完整工具链

### 中期（Phase 10.6+）

5. ⏳ **DCC 内嵌聊天面板集成**
   - 开发 `lobster_chat.py` 桥接层
   - 连接 DCC 内嵌面板到 LobsterAI
   - 用户无需离开 DCC 环境

6. ⏳ **Skills 共享优化**
   - 确保 Skills 在 OpenClaw 和 LobsterAI 间共享
   - 避免重复安装

---

## 变更记录

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-04-03 | v1.0 | 初始规划 |
| 2026-04-03 | v1.1 | Phase 10.1-10.2 实现完成。确认 LobsterAI = OpenClaw 封装 (Gateway 18790)，实现配置注入脚本，bridge_config/install.py 加 lobster 平台支持 |
| 2026-04-03 | v1.2 | 根据实际验证结果更新：MCP 链路已验证通过，DCC 内嵌面板已有但未集成，LobsterAI 配置需通过客户端界面，补充下一步工作规划 |

---

## 附录 A：快速参考

### LobsterAI MCP 配置步骤

1. 打开 LobsterAI 客户端
2. 设置 → MCP Servers
3. 添加 MCP Server
   - 名称：`artclaw-ue`
   - 类型：`WebSocket`
   - URL：`ws://127.0.0.1:8080`
   - 状态：✅ 启用
4. 保存
5. 完全退出 LobsterAI（包括系统托盘）
6. 重启 LobsterAI
7. 测试：`使用 run_ue_python 执行：print("Hello from ArtClaw!")`

### 直接 WebSocket 测试（PowerShell）

```powershell
$ws = New-Object System.Net.WebSockets.ClientWebSocket
$ws.ConnectAsync("ws://127.0.0.1:8080", $null).Wait()

# Initialize
$init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
$bytes = [System.Text.Encoding]::UTF8.GetBytes($init)
$ws.SendAsync($bytes, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $null).Wait()

# List tools
$tools = '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
$bytes = [System.Text.Encoding]::UTF8.GetBytes($tools)
$ws.SendAsync($bytes, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $null).Wait()

# Call tool
$call = '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"run_ue_python","arguments":{"code":"print(\"Hello\")"}}}'
$bytes = [System.Text.Encoding]::UTF8.GetBytes($call)
$ws.SendAsync($bytes, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $null).Wait()
```

### 端口汇总

| 组件 | 端口 | 说明 |
|------|------|------|
| LobsterAI Gateway | 18790 | 动态，记录在 gateway-port.json |
| LobsterAI MCP 管理 | 12982 | 动态，存储 MCP 配置 |
| UE MCP Server | 8080 | WebSocket |
| Maya MCP Server | 8081 | WebSocket（规划） |
| Max MCP Server | 8082 | WebSocket（规划） |
