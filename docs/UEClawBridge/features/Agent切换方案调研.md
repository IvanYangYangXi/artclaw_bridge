# Agent 切换 + 会话管理优化方案

> 版本: v2.0 | 日期: 2026-03-31 | 作者: 小优
> 基于 Clawket 调研 + 现有架构分析

## 1. 现有问题

### 1.1 会话管理问题："新会话"实际上替换了旧会话

**根因分析**：

当前 `OnNewChatClicked` 的流程：
```
1. 保存当前 session 条目（SessionEntries[i].SessionKey = currentKey）
2. Messages.Empty() — 清屏
3. PlatformBridge->ResetSession() — 清空 Python 端的 _session_key
4. 创建新 SessionEntry（此时 SessionKey 为空）
5. SendToOpenClaw("/new") — 发送 /new 给 AI
```

**问题出在步骤 3-5**：
- `reset_session()` 将 `_session_key` 设为 `None`
- 下次 `_chat_worker` 时重新生成 `_session_key = f"{_DEFAULT_AGENT_ID}/ue-editor:{int(time.time())}"`
- 但新生成的 key **没有写回** SessionEntry — 新 SessionEntry 的 `SessionKey` 一直是空字符串
- 切换到旧 session 时，`LoadSessionHistory` 尝试读取本地 JSON 历史文件 —— 但我们从来没写过这个文件
- 效果：**所有 session 条目都是空壳，切换后看不到历史**

还有一个更深层问题：
- Gateway 端的 session 通过 `sessionKey` 区分，`reset_session()` 清掉 key 后确实能开新 session
- 但**旧 session 的消息在 Gateway 端依然存在**，只是 C++ 端没有能力从 Gateway 拉历史
- `LoadSessionHistory` 尝试读本地 JSON 文件，而不是 Gateway RPC `chat.history`

### 1.2 Agent 切换：无入口

- Agent ID 硬编码在 `_DEFAULT_AGENT_ID = "qi"`
- 没有 UI 入口选择其他 Agent
- 切换 Agent 需要手动改 config 文件

## 2. 设计目标

1. **会话管理修复**：新会话真正创建独立 session，可切换回旧会话并看到历史
2. **Agent 切换**：设置面板中选择 Agent，重启对话生效
3. **通用性**：方案不耦合 OpenClaw，未来接其他平台也能用
4. **方案 A+C 融合**：配置持久化（C）+ Gateway 动态查询（A）

## 3. 架构设计

### 3.1 分层职责

```
┌────────────────────────────────────────────────────────────────────┐
│  C++ 通用层（IAgentPlatformBridge + Dashboard）                      │
│                                                                    │
│  职责:                                                             │
│  - 会话列表 UI（SessionEntries 增强为 gateway session 缓存）       │
│  - Agent 选择 UI（设置面板 Agent 下拉/列表）                        │
│  - 消息历史缓存（本地 + Gateway 按需拉取）                          │
│                                                                    │
│  不关心: 具体 Gateway 协议、WebSocket 细节、Agent 发现机制          │
├────────────────────────────────────────────────────────────────────┤
│  IAgentPlatformBridge 接口扩展                                      │
│                                                                    │
│  + ListAgents(ResultFile)       // 获取可用 Agent 列表              │
│  + SetAgentId(AgentId)          // 切换当前 Agent                   │
│  + GetAgentId() → FString       // 获取当前 Agent ID                │
│  + FetchSessionHistory(Key,File) // 从远端拉取会话历史             │
│  + ListSessions(ResultFile)     // 列出当前 Agent 的所有 session    │
├────────────────────────────────────────────────────────────────────┤
│  FOpenClawPlatformBridge 实现（platforms/openclaw/）                 │
│                                                                    │
│  通过 Python ExecCommand 调用 openclaw_chat.py:                     │
│  - list_agents() → agents.list RPC                                 │
│  - set_agent_id(id) → 更新全局 + 写 config                         │
│  - fetch_history(key) → chat.history RPC                           │
│  - list_sessions() → sessions.list RPC                             │
├────────────────────────────────────────────────────────────────────┤
│  未来其他平台（FXxxPlatformBridge）                                  │
│                                                                    │
│  实现同一套接口，Agent 列表/会话管理通过各自平台 API                │
└────────────────────────────────────────────────────────────────────┘
```

### 3.2 核心思路

**Agent 切换 = 配置 + 动态查询（A+C 融合）：**
- **C 的部分**：选中的 Agent 持久化到 `~/.artclaw/config.json`，下次启动自动恢复
- **A 的部分**：Agent 列表从 Gateway 动态查询（`agents.list` RPC），不硬编码

**通用性保证：**
- 所有 Agent/Session 操作通过 `IAgentPlatformBridge` 抽象接口
- OpenClaw 实现在 `FOpenClawPlatformBridge` + `platforms/openclaw/` Python 层
- 其他平台只需实现同一个 C++ 接口 + 各自的通信层
- C++ Dashboard 代码不包含任何 OpenClaw 特定逻辑

## 4. 会话管理优化

### 4.1 新的会话模型

```
┌─ SessionEntries（C++ 本地） ─────────────────────────────┐
│                                                           │
│  [0] "会话 03-31 16:00"  key=qi/ue-editor:1711864800    │ ← 有 key，可恢复
│  [1] "会话 03-31 17:00"  key=qi/ue-editor:1711868400    │ ← 有 key，可恢复
│  [2] "会话 03-31 17:30"  key=(pending)                   │ ← 新建还没发消息
│                                                           │
└───────────────────────────────────────────────────────────┘
```

**关键改动：**

1. **首次发消息后回写 SessionKey**：`_chat_worker` 生成 session key 后，通过 stream.jsonl 写一个 `session_key` 事件回传给 C++，C++ 更新 `SessionEntries[active].SessionKey`

2. **会话历史从 Gateway 拉取**：切换 session 时调用 `FetchSessionHistory(key, file)` → Python 端 `chat.history` RPC → 写入 JSON 文件 → C++ 读取并显示

3. **本地消息缓存**：当前 session 的 Messages 数组在 `OnSessionSelected` 时保存到 `SessionEntries[i].CachedMessages`，切换回来时直接加载（省去 Gateway 查询延迟）

### 4.2 新建会话流程（修复后）

```
OnNewChatClicked:
  1. 保存当前 session → SessionEntries[old].SessionKey + CachedMessages
  2. Messages.Empty() + 清屏
  3. PlatformBridge->ResetSession()  // Python 端清 _session_key
  4. 创建新 SessionEntry（key=空，等首次发消息后回填）
  5. AddMessage("system", "新会话已开始")
  // 注意：不再发 /new 给 AI（不需要 AI 响应，只需要 Python 端 reset session key）
```

**为什么不发 /new？**
- 之前发 `/new` 是为了让 AI 知道这是新对话，但 Gateway 通过 session key 隔离对话
- `reset_session()` 清空 key → 下次发消息时生成新 key → 新 session 自动创建
- 省掉一次不必要的 AI 请求

### 4.3 切换会话流程

```
OnSessionSelected(index):
  1. 保存当前 session:
     - SessionEntries[old].CachedMessages = Messages  // 本地缓存
     - SessionEntries[old].SessionKey = PlatformBridge->GetSessionKey()
  2. 切换到新 session:
     - ActiveSessionIndex = index
     - key = SessionEntries[index].SessionKey
  3. 恢复消息:
     IF SessionEntries[index].CachedMessages 非空:
       Messages = CachedMessages  // 本地缓存命中
     ELIF key 非空:
       PlatformBridge->FetchSessionHistory(key, file)  // 从 Gateway 拉
       // 轮询文件 → 解析 → 填充 Messages
     ELSE:
       Messages.Empty()  // 新空 session
  4. PlatformBridge->SetSessionKey(key)  // 切换 Python 端的活跃 key
  5. 关闭菜单 + RebuildMessageList
```

### 4.4 Session Key 回传机制

Python 端生成 session key 后，通过 stream.jsonl 写入一个元数据事件：

```python
# openclaw_ws.py - do_chat() 中，发送 chat.send 后
effective_session_key = ack.get("sessionKey") or session_key
# 写入 stream 文件，让 C++ 端获取实际 key
write_stream(stream_file, {
    "type": "session_key",
    "key": effective_session_key,
}, stream_lock)
```

C++ 端在流式轮询中捕获：
```cpp
else if (EventType == TEXT("session_key"))
{
    FString Key = JsonObj->GetStringField(TEXT("key"));
    if (!Key.IsEmpty() && SessionEntries.IsValidIndex(ActiveSessionIndex))
    {
        SessionEntries[ActiveSessionIndex].SessionKey = Key;
    }
}
```

## 5. Agent 切换设计

### 5.1 UI 位置：设置面板

Agent 切换放在设置面板中（而非工具栏），原因：
- 切换 Agent 是低频操作（比切换会话还低频）
- 工具栏空间有限，Agent 信息可以放在标题/状态栏显示
- 设置面板有足够空间展示 Agent 列表 + 详情

```
┌─ 设置面板 ─────────────────────────────┐
│                                         │
│  语言: [中文 ▼]                         │
│  ─────────────────────                  │
│  发送模式: [✓] Enter 发送               │
│  ─────────────────────                  │
│  当前 Agent:                            │
│  ┌─────────────────────────────────┐    │
│  │ 🐱 柒 (qi)              [当前]  │    │
│  │ 🔧 小优 (xiaoyou)              │    │
│  │ 🎨 小树 (xiaoshu)              │    │
│  │                                 │    │
│  │ [刷新列表]                      │    │
│  └─────────────────────────────────┘    │
│  ─────────────────────                  │
│  静默模式: ...                          │
│  Plan 模式: ...                         │
│  Skills 管理: ...                       │
│  ─────────────────────                  │
│                         [关闭]          │
└─────────────────────────────────────────┘
```

### 5.2 工具栏显示当前 Agent

在工具栏的 session 标签旁边显示当前 Agent：

```
[🐱 柒] [会话 03-31 16:00 ▼] [+ 新会话] [管理] ...
```

- 点击 Agent 标签打开设置面板（定位到 Agent 部分）
- 或者只是静态显示，切换需要进设置

### 5.3 切换 Agent 流程

```
用户在设置面板选择新 Agent:
  1. PlatformBridge->SetAgentId("xiaoyou")
     → Python: set_agent_id("xiaoyou")
     → 写入 ~/.artclaw/config.json: {"last_agent_id": "xiaoyou"}
     → 清空 _session_key + _context_injected
  2. C++ 端:
     → SessionEntries.Empty()  // 清空所有旧 session
     → Messages.Empty() + RebuildMessageList()
     → InitFirstSession()  // 创建新 Agent 的第一个 session
     → 更新工具栏 Agent 标签
     → AddMessage("system", "已切换到 Agent: 小优 (xiaoyou)")
  3. 下次发消息时:
     → _session_key = "xiaoyou/ue-editor:{timestamp}"
     → 自动连接到 xiaoyou 的 session
```

### 5.4 Agent 列表获取

**两级来源（A+C 融合）：**

1. **配置文件（C）**：`~/.artclaw/config.json` 的 `agents` 字段
   - 启动时立即可用，无需网络
   - 手动添加/编辑也行

2. **Gateway 查询（A）**：`agents.list` RPC
   - 设置面板"刷新列表"按钮触发
   - 结果回写到 config.json 缓存

```json
// ~/.artclaw/config.json
{
  "platform": "openclaw",
  "last_agent_id": "qi",
  "agents_cache": [
    {"id": "qi", "name": "柒", "emoji": "🐱"},
    {"id": "xiaoyou", "name": "小优", "emoji": "🔧"}
  ],
  "agents_cache_updated": "2026-03-31T17:00:00Z",
  "gateway": { ... }
}
```

**启动流程：**
```
1. 读 config.json → last_agent_id + agents_cache
2. 如果有 agents_cache → 立即填充 Agent 列表
3. 如果缓存过期（>1天）或为空 → 后台触发 Gateway 查询刷新
4. 用户也可以手动刷新
```

### 5.5 IAgentPlatformBridge 接口扩展

```cpp
// IAgentPlatformBridge.h 新增

/** 获取当前 Agent ID */
virtual FString GetAgentId() const = 0;

/** 设置当前 Agent ID（切换 Agent）。实现应同时 reset session。 */
virtual void SetAgentId(const FString& AgentId) = 0;

/**
 * 异步获取可用 Agent 列表。
 * 结果以 JSON 写入 ResultFile: {"agents": [{"id":"...", "name":"...", "emoji":"..."}]}
 * @param ResultFile 结果写入路径
 */
virtual void ListAgents(const FString& ResultFile) = 0;

/**
 * 异步获取指定 session 的聊天历史。
 * 结果以 JSON 写入 HistoryFile: {"messages": [{"role":"user/assistant", "content":"..."}]}
 * @param SessionKey 目标 session key
 * @param HistoryFile 历史写入路径
 */
virtual void FetchSessionHistory(const FString& SessionKey, const FString& HistoryFile) = 0;

/**
 * 异步获取当前 Agent 的所有 session 列表。
 * 结果以 JSON 写入 ResultFile: {"sessions": [{"key":"...", "label":"...", "updatedAt":...}]}
 * @param ResultFile 结果写入路径
 */
virtual void ListSessions(const FString& ResultFile) = 0;
```

**通用性保证**：这些方法不含任何 OpenClaw 特有概念，其他平台同样有 Agent + Session 的概念。

### 5.6 Python API（platforms/openclaw/）

```python
# openclaw_chat.py 新增

_agent_id: str = _DEFAULT_AGENT_ID

def list_agents(result_file: str) -> None:
    """异步查询 Agent 列表，写入 result_file。"""
    def _worker():
        result = asyncio.run(openclaw_ws.do_list_agents(
            gateway_url=_get_gateway_url(),
            token=_get_token(),
        ))
        with open(result_file, "w", encoding="utf-8") as f:
            f.write(result)
        # 同时更新 config.json 缓存
        _update_agents_cache(json.loads(result))
    threading.Thread(target=_worker, daemon=True).start()


def set_agent_id(agent_id: str) -> str:
    """切换 Agent，reset session，写入 config。"""
    global _agent_id, _session_key, _context_injected
    _agent_id = agent_id
    _session_key = None
    _context_injected = False
    # 持久化
    _save_last_agent_id(agent_id)
    return json.dumps({"ok": True, "agentId": agent_id})


def get_agent_id() -> str:
    return _agent_id


def get_cached_agents() -> str:
    """从 config.json 读取缓存的 Agent 列表（无需网络）。"""
    try:
        config = _load_artclaw_config()
        agents = config.get("agents_cache", [])
        return json.dumps({"agents": agents}, ensure_ascii=False)
    except:
        return json.dumps({"agents": []})


def fetch_history(session_key: str, result_file: str) -> None:
    """异步从 Gateway 拉取会话历史，写入 result_file。"""
    def _worker():
        result = asyncio.run(openclaw_ws.do_fetch_history(
            session_key=session_key,
            gateway_url=_get_gateway_url(),
            token=_get_token(),
        ))
        with open(result_file, "w", encoding="utf-8") as f:
            f.write(result)
    threading.Thread(target=_worker, daemon=True).start()


def list_sessions(result_file: str) -> None:
    """异步从 Gateway 拉取当前 Agent 的 session 列表。"""
    def _worker():
        result = asyncio.run(openclaw_ws.do_list_sessions(
            gateway_url=_get_gateway_url(),
            token=_get_token(),
        ))
        with open(result_file, "w", encoding="utf-8") as f:
            f.write(result)
    threading.Thread(target=_worker, daemon=True).start()
```

```python
# openclaw_ws.py 新增

async def do_list_agents(gateway_url: str, token: str) -> str:
    """一次性连接 → agents.list RPC → 返回 JSON。"""
    # ... (同方案 A，略)

async def do_fetch_history(session_key: str, gateway_url: str, token: str) -> str:
    """一次性连接 → chat.history RPC → 返回 JSON。"""
    async with websockets.connect(gateway_url, open_timeout=5) as ws:
        if not await _handshake(ws, token, session_key=session_key):
            return json.dumps({"error": "handshake failed", "messages": []})
        req_id = str(uuid.uuid4())
        await ws.send(json.dumps({
            "type": "req", "id": req_id,
            "method": "chat.history",
            "params": {"sessionKey": session_key, "limit": 50},
        }))
        ack = await _wait_for_ack(ws, req_id, timeout=10.0)
        if not ack:
            return json.dumps({"error": "timeout", "messages": []})
        return json.dumps({
            "messages": ack.get("messages", []),
        }, ensure_ascii=False)

async def do_list_sessions(gateway_url: str, token: str) -> str:
    """一次性连接 → sessions.list RPC → 返回 JSON。"""
    # 类似 do_list_agents 模式
```

## 6. DCC 端复用

### 6.1 Maya/Max 的 bridge_dcc.py

DCC 端使用 `bridge_core.py`（持久连接），对应的改动：

```python
# bridge_core.py 新增方法
class OpenClawBridge:
    def list_agents(self) -> list:
        """通过已有连接发送 agents.list RPC。"""
        result = self._send_rpc("agents.list", {})
        return result.get("agents", []) if result else []

    def set_agent(self, agent_id: str):
        """切换 Agent，重置 session。"""
        self._agent_id = agent_id
        self._session_key = None
        self._context_injected = False

    def fetch_history(self, session_key: str) -> list:
        """通过已有连接发送 chat.history RPC。"""
        result = self._send_rpc("chat.history", {"sessionKey": session_key, "limit": 50})
        return result.get("messages", []) if result else []
```

### 6.2 Qt UI 适配

DCC 端的 Qt UI (`artclaw_ui/`) 需要对应改动：
- 设置面板加 Agent 选择（同 UE 的设置面板设计）
- 会话管理用同一套 session 切换逻辑
- 通过 `bridge_dcc.py` 的 Qt signal 回调

## 7. 通用性评估：其他 Agent 管理平台

### 7.1 接入新平台只需

1. **实现 `IAgentPlatformBridge` 接口** — C++ 侧新建 `FXxxPlatformBridge`
2. **实现对应的 Python 通信层** — `platforms/xxx/` 目录
3. **确保同样的 API 语义**：
   - `ListAgents` → 返回平台上的 Agent 列表
   - `SetAgentId` → 切换活跃 Agent
   - `FetchSessionHistory` → 拉取历史消息
   - `ListSessions` → 列出 session

### 7.2 不同平台的差异点

| 特性 | OpenClaw | 其他平台 (示例) |
|------|----------|----------------|
| Agent 列表 | `agents.list` RPC | 平台 REST API |
| Session 概念 | session key 隔离 | 可能有不同的 conversation ID |
| 历史拉取 | `chat.history` RPC | 平台 API |
| 配置存储 | `~/.artclaw/config.json` | 同一个配置文件 |

**关键**：`IAgentPlatformBridge` 抽象层屏蔽了这些差异，C++ Dashboard 完全不需要改。

## 8. 实施计划

### Phase 1：会话管理修复（~2 小时）

**Python 层：**
- [ ] `openclaw_ws.py`: `do_chat` 中写 `session_key` 事件到 stream.jsonl
- [ ] `openclaw_ws.py`: 新增 `do_fetch_history()`
- [ ] `openclaw_chat.py`: 新增 `fetch_history()` 异步包装
- [ ] `openclaw_chat.py`: `_chat_worker` 中 session key 用 `_agent_id` 而非 `_DEFAULT_AGENT_ID`

**C++ 层：**
- [ ] 流式轮询中捕获 `session_key` 事件 → 写入 `SessionEntries`
- [ ] `OnNewChatClicked`: 不发 `/new`，只 reset
- [ ] `OnSessionSelected`: 优先用 CachedMessages，fallback 到 Gateway history
- [ ] `SessionEntries` 增加 `CachedMessages` 字段
- [ ] `IAgentPlatformBridge` 增加 `FetchSessionHistory` 方法
- [ ] `FOpenClawPlatformBridge` 实现 `FetchSessionHistory`

### Phase 2：Agent 切换（~2 小时）

**Python 层：**
- [ ] `openclaw_ws.py`: 新增 `do_list_agents()`
- [ ] `openclaw_chat.py`: 新增 `_agent_id` 全局变量 + `list_agents()` / `set_agent_id()` / `get_agent_id()` / `get_cached_agents()`
- [ ] 启动时从 config.json 恢复 `last_agent_id`
- [ ] agents_cache 读写

**C++ 层：**
- [ ] `IAgentPlatformBridge` 增加 `ListAgents` / `SetAgentId` / `GetAgentId` 方法
- [ ] `FOpenClawPlatformBridge` 实现这 3 个方法
- [ ] 设置面板新增 Agent 列表区域 + 刷新按钮
- [ ] 工具栏显示当前 Agent emoji+名称
- [ ] 切换 Agent 后清空 session + 重置 UI

### Phase 3：DCC 端适配（~1 小时）
- [ ] `bridge_core.py` 新增 `list_agents()` / `set_agent()` / `fetch_history()`
- [ ] Qt 设置面板 Agent 选择
- [ ] Maya 端测试

### Phase 4：Gateway Session 列表（~1 小时，可选）
- [ ] Python: `do_list_sessions()` RPC
- [ ] C++: 会话菜单从 Gateway 拉取真实 session 列表（替代本地 SessionEntries）
- [ ] 支持看到其他客户端（Clawket、WebChat）创建的 session

## 9. 风险与注意事项

1. **Gateway 版本兼容**：`agents.list` / `chat.history` / `sessions.list` RPC 在较新版本 Gateway 才有。需要 try-catch + fallback（只显示默认 Agent）

2. **session key 格式**：当前用 `qi/ue-editor:xxx`，Gateway 可能做 namespace 包装。`chat.history` 查询时需要用 ACK 返回的 effective key

3. **消息格式差异**：Gateway 返回的历史消息格式（`{role, content}`）可能与我们本地 `FChatMessage`（`{Sender, Content}`）不同，需要映射层

4. **CachedMessages 内存**：大量消息会占内存。建议限制每个 session 缓存最近 100 条

5. **并发安全**：Python 端的 `_agent_id` / `_session_key` 是全局变量，多线程访问需要注意。当前只有一个 chat worker 线程，暂时安全

## 10. 结论

**方案 A+C 融合是最合适的路线：**
- **C 的持久化**保证启动即可用（不等网络）
- **A 的动态查询**保证列表实时准确
- **IAgentPlatformBridge 抽象接口**保证其他平台可以无缝接入
- **会话管理修复**是前置条件，解决了当前最大的体验问题

总工作量约 **6 小时**，分 4 个 Phase 可以增量交付。
