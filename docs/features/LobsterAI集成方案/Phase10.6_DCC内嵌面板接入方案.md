# Phase 10.6: DCC 内嵌聊天面板接入 LobsterAI — 详细设计方案

> **版本**: v1.0  
> **日期**: 2026-04-03  
> **状态**: 规划中  
> **前置**: Phase 10.1-10.2 已完成（MCP 链路验证通过）  
> **作者**: 小优

---

## 一、目标与约束

### 1.1 目标

将 UE 和 DCC（Maya/Max）内嵌聊天面板从当前仅支持 OpenClaw 扩展为支持 LobsterAI，用户无需离开 DCC 环境即可通过 LobsterAI 进行 AI 对话。

### 1.2 架构约束

1. **DCC 插件层零改动**：UE C++ Dashboard / Maya Qt ChatPanel / Max Qt ChatPanel 不改动
2. **platforms 与 DCC 解耦**：新平台 bridge 代码放在 `platforms/{platform}/` 而非 DCC 插件内部
3. **core/ 共享层零改动**：`bridge_core.py` / `bridge_config.py` 等核心代码不为某个平台做特殊化
4. **接口契约不变**：Python 对 C++/Qt 暴露的函数签名不变，新平台通过**同名模块替换**接入
5. **未来可扩展**：方案设计必须支持第 N+1 个平台以相同方式接入

### 1.3 关键发现

| 项目 | 结论 |
|------|------|
| LobsterAI 是否为 OpenClaw 封装 | ✅ 是，Gateway 协议完全兼容 |
| Gateway RPC 协议 | 相同（connect/chat.send/chat.abort/sessions.list/agents.list） |
| 认证方式 | 相同（token + connect.challenge 握手） |
| Session key 格式 | 相同（`agent:<agentId>:<clientId>:<timestamp>`） |
| 流式事件格式 | 相同（event: "chat", state: delta/final/error/aborted） |
| Gateway 端口 | OpenClaw=18789, LobsterAI=18790（唯一差异） |

**核心结论：LobsterAI 与 OpenClaw 的 Gateway 协议完全一致，`bridge_core.py` 无需任何修改。区别仅在配置层（端口、token、配置文件路径）。**

---

## 二、现有架构验证

### 2.1 当前通信链路

```
┌── UE 端 ──────────────────────────────────────────────────────────┐
│ C++ Dashboard ←→ Python openclaw_chat.py ←→ openclaw_ws.py       │
│                  (import openclaw_chat)     (asyncio WebSocket)   │
│                  文件协议(stream.jsonl)      连接 Gateway:18789   │
└───────────────────────────────────────────────────────────────────┘

┌── DCC 端 (Maya/Max) ─────────────────────────────────────────────┐
│ Qt ChatPanel ←→ bridge_dcc.py ←→ bridge_core.py                  │
│                  (Qt signal/slot)  (asyncio WebSocket)            │
│                  DCCBridgeManager   OpenClawBridge                │
│                                     连接 Gateway:18789           │
└───────────────────────────────────────────────────────────────────┘
```

### 2.2 平台配置读取路径

**UE 端**：
- `openclaw_chat.py._get_gateway_config()` → `bridge_config._resolve_platform_config_path()` → 读 `~/.artclaw/config.json` 确定平台 → 读平台配置文件获取 port/token

**DCC 端**：
- `bridge_dcc.py` → `OpenClawBridge.__init__()` → `bridge_config.load_config()` → 同上

**结论**：两端都通过 `bridge_config.py` 间接获取 Gateway 地址和 token。切换平台 = 改 `~/.artclaw/config.json` 的 `platform.type` + 确保 `bridge_config.py` 返回正确的 port/token。

### 2.3 已完成的基础设施验证

| 组件 | 验证项 | 状态 |
|------|--------|------|
| `bridge_config.py` | `_PLATFORM_DEFAULTS["lobster"]` 存在 | ✅ |
| `bridge_config.py` | `_get_lobster_config_path()` 正确 | ✅ |
| `bridge_config.py` | `get_platform_type()` 返回 config 中的 platform.type | ✅ |
| `bridge_config.py` | `load_config()` 按平台读取正确的配置文件 | ⚠️ 需验证 |
| `bridge_core.py` | `OpenClawBridge.__init__` 通过 `load_config()` 获取 gateway port/token | ✅ |
| `bridge_core.py` | 握手协议兼容 LobsterAI | ✅（协议完全相同） |
| `openclaw_chat.py` | `_get_gateway_config()` 通过 `bridge_config` 获取配置 | ✅ |
| `openclaw_ws.py` | WebSocket 通信代码平台无关 | ✅ |

---

## 三、方案设计

### 3.1 核心思路：配置驱动，零代码分叉

由于 LobsterAI = OpenClaw 封装，Gateway 协议完全一致，**不需要写 `lobster_ws.py` / `lobster_chat.py` 等新通信模块**。只需确保配置链路正确，现有代码即可连接 LobsterAI。

```
切换到 LobsterAI 后:
  ~/.artclaw/config.json → platform.type = "lobster"
  bridge_config.py → _PLATFORM_DEFAULTS["lobster"] → gateway_url: ws://127.0.0.1:18790
  bridge_core.py / openclaw_ws.py → 连接 :18790（而非 :18789）
  其他一切不变
```

### 3.2 需要修改的代码

#### 问题 1: UE 端 `openclaw_chat.py` 硬编码了 fallback 端口

```python
# 当前代码 (openclaw_chat.py)
_GATEWAY_PORT = 18789

def _get_gateway_url() -> str:
    gw = _get_gateway_config()
    return f"ws://127.0.0.1:{gw.get('port', _GATEWAY_PORT)}"
```

当 LobsterAI 的配置文件结构与 OpenClaw 不同（没有 `gateway.port` 字段），会 fallback 到硬编码的 18789。

**修复**：让 `_get_gateway_url()` 优先从 `~/.artclaw/config.json` 的 `platform.gateway_url` 读取。

#### 问题 2: UE 端 `openclaw_chat.py` 的 `_get_gateway_config()` 直接读平台配置文件

```python
def _get_gateway_config() -> dict:
    from bridge_config import _resolve_platform_config_path
    path = _resolve_platform_config_path()
    # 读 openclaw.json 的 gateway 节
    return json.load(f).get("gateway", {})
```

LobsterAI 的 `openclaw.json` 格式可能不同（gateway 节不在同一位置），这段代码可能返回空 dict。

**修复**：增加 `platform.gateway_url` 直读路径，不依赖平台配置文件的内部结构。

#### 问题 3: DCC 端 `bridge_core.py` 的 gateway_url 构造

```python
class OpenClawBridge:
    def __init__(self, ...):
        config = load_config()  # 读平台配置文件
        gw_config = config.get("gateway", {})
        self.gateway_url = gateway_url or f"ws://127.0.0.1:{gw_config.get('port', 18789)}"
```

同样依赖平台配置文件的 `gateway.port`。LobsterAI 配置结构不同时会 fallback 到 18789。

**修复**：`OpenClawBridge.__init__` 增加从 `~/.artclaw/config.json` 的 `platform.gateway_url` 读取的逻辑。

#### 问题 4: Token 读取

UE 端和 DCC 端都从平台配置文件的 `gateway.auth.token` 读取 token。LobsterAI 的 token 位置可能不同。

**修复**：增加从 `~/.artclaw/config.json` 的 `platform.token` 读取的路径。

### 3.3 修改清单（最小化）

| 文件 | 修改内容 | 影响范围 |
|------|----------|----------|
| `core/bridge_config.py` | 新增 `get_gateway_url()` / `get_gateway_token()` 统一 API | 核心共享 |
| `core/bridge_core.py` | `__init__` 改用 `get_gateway_url()` / `get_gateway_token()` | DCC 端 |
| `platforms/openclaw/openclaw_chat.py` | `_get_gateway_url()` / `_get_token()` 改用 bridge_config API | UE 端 |
| `~/.artclaw/config.json` | 切换时写入 `platform.token` | 配置 |
| `platforms/common/switch_platform.py` | 切换脚本写入完整 platform 配置 | 工具 |

**注意：`bridge_dcc.py`、`openclaw_ws.py`、C++ Dashboard、Qt ChatPanel 均不需要修改。**

---

## 四、`bridge_config.py` 统一配置 API 设计

### 4.1 实际配置文件对比（验证数据）

| 配置项 | OpenClaw | LobsterAI |
|--------|----------|-----------|
| 配置文件 | `~/.openclaw/openclaw.json` | `%APPDATA%/LobsterAI/openclaw/state/openclaw.json` |
| gateway.port | ✅ `gateway.port: 18789` | ❌ `gateway: {"mode": "local"}` 无 port |
| gateway.auth.token | ✅ `gateway.auth.token: "ec89..."` | ❌ 无此字段 |
| 端口实际位置 | `openclaw.json` | `gateway-port.json` → `{"port": 18790}` |
| Token 实际位置 | `openclaw.json` | `gateway-token` 文件（纯文本） |

**这就是为什么必须新增统一 API —— 两个平台的配置文件结构完全不同。**

### 4.2 新增函数

```python
def get_gateway_url() -> str:
    """获取 Gateway WebSocket URL。

    优先级:
    1. ~/.artclaw/config.json → platform.gateway_url（最高优先级，平台切换脚本写入）
    2. 平台配置文件 → gateway.port（OpenClaw 格式）
    3. gateway-port.json（LobsterAI 格式）
    4. _PLATFORM_DEFAULTS 中的默认值
    """
    ac = load_artclaw_config()

    # 1. 从 artclaw config 直读
    platform_url = ac.get("platform", {}).get("gateway_url", "")
    if platform_url:
        return platform_url

    # 2. 从平台配置文件读（OpenClaw 格式）
    config = load_config()
    gw = config.get("gateway", {})
    port = gw.get("port")
    if port:
        return f"ws://127.0.0.1:{port}"

    # 3. 从 gateway-port.json 读（LobsterAI 格式）
    config_path = _resolve_platform_config_path()
    port_json = os.path.join(os.path.dirname(config_path), "gateway-port.json")
    if os.path.exists(port_json):
        try:
            with open(port_json, "r", encoding="utf-8") as f:
                port_data = json.load(f)
            port = port_data.get("port")
            if port:
                return f"ws://127.0.0.1:{port}"
        except Exception:
            pass

    # 4. 平台默认值
    defaults = get_platform_defaults()
    return defaults.get("gateway_url", DEFAULT_GATEWAY_URL)


def get_gateway_token() -> str:
    """获取 Gateway 认证 Token。

    优先级:
    1. ~/.artclaw/config.json → platform.token
    2. 平台配置文件 → gateway.auth.token（OpenClaw 格式）
    3. gateway-token 文件（LobsterAI 格式，纯文本）
    4. 硬编码默认值
    """
    ac = load_artclaw_config()

    # 1. 从 artclaw config 直读
    token = ac.get("platform", {}).get("token", "")
    if token:
        return token

    # 2. 从平台配置文件读（OpenClaw 格式）
    config = load_config()
    token = config.get("gateway", {}).get("auth", {}).get("token", "")
    if token:
        return token

    # 3. 从 gateway-token 文件读（LobsterAI 格式）
    config_path = _resolve_platform_config_path()
    token_file = os.path.join(os.path.dirname(config_path), "gateway-token")
    if os.path.exists(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                token = f.read().strip()
            if token:
                return token
        except Exception:
            pass

    return DEFAULT_TOKEN
```

### 4.2 修改影响

这两个函数封装了所有 gateway 连接信息的获取逻辑。所有消费方只需调用这两个函数，不再自己拼装。

---

## 五、各层修改详情

### 5.1 `core/bridge_config.py` — 新增 2 个函数

见第四节。现有函数 `get_gateway_config()` 保留但标记为内部使用。

### 5.2 `core/bridge_core.py` — 改用统一 API

```python
# 修改前
class OpenClawBridge:
    def __init__(self, ...):
        config = load_config()
        gw_config = config.get("gateway", {})
        self.gateway_url = gateway_url or f"ws://127.0.0.1:{gw_config.get('port', 18789)}"
        self.token = token or gw_config.get("auth", {}).get("token", DEFAULT_TOKEN)

# 修改后
class OpenClawBridge:
    def __init__(self, ...):
        from bridge_config import get_gateway_url, get_gateway_token
        self.gateway_url = gateway_url or get_gateway_url()
        self.token = token or get_gateway_token()
```

变更量：~3 行。无功能变化，仅切换配置来源。

### 5.3 `platforms/openclaw/openclaw_chat.py` — 改用统一 API

```python
# 修改前
def _get_gateway_url() -> str:
    gw = _get_gateway_config()
    return f"ws://127.0.0.1:{gw.get('port', _GATEWAY_PORT)}"

def _get_token() -> str:
    gw = _get_gateway_config()
    return gw.get("auth", {}).get("token", _DEFAULT_TOKEN)

# 修改后
def _get_gateway_url() -> str:
    from bridge_config import get_gateway_url
    return get_gateway_url()

def _get_token() -> str:
    from bridge_config import get_gateway_token
    return get_gateway_token()
```

变更量：~6 行。`_get_gateway_config()` 函数保留（其他地方可能用到 port 信息）。

### 5.4 `platforms/common/switch_platform.py` — 写入完整配置

平台切换时，将 gateway_url 和 token 写入 `~/.artclaw/config.json`：

```python
# 切换到 lobster
config["platform"] = {
    "type": "lobster",
    "gateway_url": "ws://127.0.0.1:18790",
    "mcp_port": 8080,
    "token": _read_lobster_token(),  # 从 LobsterAI 配置文件读取
}
```

### 5.5 不需要修改的文件

| 文件 | 原因 |
|------|------|
| `openclaw_ws.py` | 接收 gateway_url 参数，不自己获取配置 |
| `bridge_dcc.py` | 通过 `OpenClawBridge` 间接使用，不直接读配置 |
| C++ `OpenClawPlatformBridge.cpp` | 调用的 Python 函数签名不变 |
| C++ `IAgentPlatformBridge.h` | 接口不变 |
| Qt ChatPanel (Maya/Max) | 通过 `DCCBridgeManager` 间接使用 |
| `mcp_server.py` | MCP Server 不受平台切换影响 |

---

## 六、`lobster_chat.py` 的定位调整

### 6.1 现状

当前 `platforms/lobster/lobster_chat.py` 实现了一个独立的 `LobsterChatManager` 类，包含完整的 WebSocket 连接、握手、收发逻辑。这是一个**全新的通信实现**。

### 6.2 问题

1. **代码重复**：与 `bridge_core.py` 大量重复（握手、流式接收、session 管理），违反 DRY
2. **功能不完整**：缺少 agent 切换、会话历史、诊断、DCC 上下文注入等
3. **Qt Signal 实现有问题**：在 `__init__` 里创建 Signal 实例（应在类定义时声明）
4. **未对接 DCC UI**：ChatPanel 的回调接口与 `LobsterChatSignals` 不匹配

### 6.3 建议

**删除 `lobster_chat.py`，不再需要。**

理由：
- LobsterAI 与 OpenClaw 协议一致 → `bridge_core.py` 完全适用
- 配置差异通过 `bridge_config.py` 的 `get_gateway_url()` / `get_gateway_token()` 解决
- DCC 端 `bridge_dcc.py` + `bridge_core.py` 无需修改即可连接 LobsterAI
- UE 端 `openclaw_chat.py` + `openclaw_ws.py` 改用统一 API 即可

如果未来需要 LobsterAI 专有功能（如独特 API），再按需新建。

---

## 七、平台切换对 DCC 的完整影响

### 7.1 切换流程

```
switch_platform.py --to lobster
  │
  ├─ 1. 读取 LobsterAI token
  │     → %APPDATA%/LobsterAI/openclaw/state/openclaw.json → gateway.auth.token
  │
  ├─ 2. 更新 ~/.artclaw/config.json
  │     → platform.type = "lobster"
  │     → platform.gateway_url = "ws://127.0.0.1:18790"
  │     → platform.token = <LobsterAI token>
  │
  ├─ 3. 不需要复制/替换任何 Python 文件！
  │     （所有代码通过 bridge_config 动态读取配置）
  │
  └─ 4. 提示用户重启 DCC（bridge 在启动时加载配置）
```

### 7.2 DCC 重启后行为

```
UE/Maya/Max 启动
  → bridge_config.get_gateway_url() → 读 config.json → "ws://127.0.0.1:18790"
  → bridge_config.get_gateway_token() → 读 config.json → <LobsterAI token>
  → OpenClawBridge.start() → 连接 :18790 → 握手 → 成功
  → Chat Panel 正常使用（与 OpenClaw 完全相同的体验）
```

### 7.3 特殊情况: LobsterAI Gateway 未启动

```
bridge_config.get_gateway_url() → "ws://127.0.0.1:18790"
OpenClawBridge.start() → 连接失败
→ 自动重试（backoff 1s → 2s → 4s → ... → 30s）
→ Chat Panel 显示 "连接中断...请确认 LobsterAI 正在运行"
→ 用户启动 LobsterAI → 自动重连成功
```

---

## 八、UE 端平台抽象层评估

### 8.1 现状

UE 端有 `IAgentPlatformBridge` 接口 + `FOpenClawPlatformBridge` 实现。Dashboard 通过接口调用，不直接依赖具体平台。

### 8.2 是否需要 `FLobsterPlatformBridge`?

**不需要。**

`FOpenClawPlatformBridge` 调用的 Python 函数（`openclaw_chat.connect` / `send_chat_async_to_file` 等）在配置层已经做到平台无关。切换到 LobsterAI 后，同一套 Python 代码自动连接不同 Gateway。

如果未来需要 LobsterAI 特有的 C++ 行为（如不同的 UI 提示、不同的文件协议），再新建 `FLobsterPlatformBridge`。

### 8.3 平台名称显示

当前 `FOpenClawPlatformBridge::GetPlatformName()` 硬返回 `"OpenClaw"`。可以改为动态读取 config：

```python
# openclaw_chat.py 新增
def get_platform_name() -> str:
    from bridge_config import get_platform_type
    _name_map = {"openclaw": "OpenClaw", "lobster": "LobsterAI", "claude": "Claude"}
    return _name_map.get(get_platform_type(), "Unknown")
```

**优先级低**，不影响功能。可以后续再做。

---

## 九、开发任务拆分

### Phase 10.6.1: bridge_config.py 统一 API（30 min）

| # | 任务 | 文件 |
|---|------|------|
| 1 | 新增 `get_gateway_url()` 函数 | `core/bridge_config.py` |
| 2 | 新增 `get_gateway_token()` 函数 | `core/bridge_config.py` |
| 3 | 同步到 DCC + UE 副本 | 各 DCC 的 `core/bridge_config.py` |

### Phase 10.6.2: 消费方改用统一 API（30 min）

| # | 任务 | 文件 |
|---|------|------|
| 4 | `OpenClawBridge.__init__` 改用 `get_gateway_url()` / `get_gateway_token()` | `core/bridge_core.py` |
| 5 | `openclaw_chat._get_gateway_url()` / `_get_token()` 改用统一 API | `platforms/openclaw/openclaw_chat.py` |
| 6 | 同步到 DCC + UE 副本 | 各 DCC 的 `core/bridge_core.py` |
| 7 | 同步 `openclaw_chat.py` 到 UE Content/Python/ | UE 副本 |

### Phase 10.6.3: 平台切换脚本完善（1h）

| # | 任务 | 文件 |
|---|------|------|
| 8 | `switch_platform.py` 读取 LobsterAI token | `platforms/common/switch_platform.py` |
| 9 | 写入完整 `platform` 配置到 `config.json` | 同上 |
| 10 | 支持 `--status` / `--to lobster` / `--to openclaw` | 同上 |

### Phase 10.6.4: 端到端验证（1h）

| # | 任务 | 验证方法 |
|---|------|----------|
| 11 | OpenClaw → LobsterAI 切换 | `switch_platform.py --to lobster` |
| 12 | UE Chat Panel 连接 LobsterAI | 重启 UE，发消息，确认连 18790 |
| 13 | Maya Chat Panel 连接 LobsterAI | 重启 Maya，发消息，确认连 18790 |
| 14 | LobsterAI → OpenClaw 切回 | `switch_platform.py --to openclaw` |
| 15 | 切回后 UE/Maya 正常 | 发消息，确认连 18789 |

### Phase 10.6.5: 清理（30 min）

| # | 任务 | 文件 |
|---|------|------|
| 16 | 删除 `platforms/lobster/lobster_chat.py` | 冗余代码 |
| 17 | 更新 `LobsterAI平台接入方案.md` Phase 10.6 状态 | 文档 |
| 18 | 更新 `开发路线图.md` | 文档 |
| 19 | Git commit | — |

**总工作量预估：~3.5 小时**

---

## 十、验证矩阵

### 10.1 功能验证

| 功能 | OpenClaw | LobsterAI | 说明 |
|------|----------|-----------|------|
| UE 连接 | ✅ 已有 | ⏳ 待验证 | 切换后自动连 18790 |
| UE 发消息 | ✅ 已有 | ⏳ 待验证 | 流式回复 + stream.jsonl |
| UE 取消请求 | ✅ 已有 | ⏳ 待验证 | chat.abort RPC |
| UE Agent 切换 | ✅ 已有 | ⏳ 待验证 | agents.list → LobsterAI agents |
| UE 会话历史 | ✅ 已有 | ⏳ 待验证 | chat.history RPC |
| UE 诊断 | ✅ 已有 | ⏳ 待验证 | 端口/连接检测 |
| Maya 连接 | ✅ 已有 | ⏳ 待验证 | 同上 |
| Maya 发消息 | ✅ 已有 | ⏳ 待验证 | Qt signal 回传 |
| Maya Tool Call 显示 | ✅ 已修 | ⏳ 待验证 | MCP Server 侧推送 |
| Maya i18n | ✅ 已有 | ⏳ 待验证 | 不受平台影响 |
| 平台切换 | — | ⏳ 待验证 | switch_platform.py |
| 切回 OpenClaw | — | ⏳ 待验证 | 切回后功能正常 |

### 10.2 回归验证

切换到 LobsterAI 后，以下功能不应受影响：

| 功能 | 说明 |
|------|------|
| MCP Server | 端口不变（UE:8080, Maya:8081） |
| Skill Hub | 读取 `~/.openclaw/skills/` 或配置路径 |
| Memory System | 独立于平台 |
| Knowledge Base | 独立于平台 |
| DCC 上下文注入 | `bridge_dcc._enrich_with_briefing()` 不变 |
| Pinned Skills | 读 `~/.artclaw/config.json`，不变 |

---

## 十一、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| LobsterAI token 格式/位置不同 | 认证失败 | `get_gateway_token()` 多路径查找 |
| LobsterAI Gateway 端口变化 | 连接失败 | `gateway-port.json` 动态读取（可选） |
| 切换后忘记重启 DCC | 仍连旧 Gateway | 切换脚本明确提示 |
| 两个 Gateway 同时运行的端口冲突 | — | 不冲突（18789 vs 18790） |
| LobsterAI Agent 列表与 OpenClaw 不同 | Agent 切换 UI 显示不同 | 正常行为 |

---

## 十二、未来扩展模型

本方案建立的扩展模型：

```
新增平台 X 的步骤:
  1. bridge_config.py → _PLATFORM_DEFAULTS["x"] 添加配置
  2. install.py → PLATFORM_CONFIGS["x"] 添加安装配置
  3. switch_platform.py → 支持 --to x
  4. (可选) platforms/x/setup_x_config.py — MCP 配置注入
  5. 完成！无需新写通信代码（除非协议不兼容）
```

---

## 变更记录

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-04-03 | v1.0 | 初始设计 |
