# OpenClaw 通信排错记录

> 记录 UE Editor Agent ↔ OpenClaw Gateway 通信过程中遇到的已知问题，
> 及其根因分析与修复方案。供后续开发和团队其他成员参考。

---

## 问题索引

| # | 问题 | 严重性 | 状态 | 发现日期 |
|---|------|--------|------|----------|
| 1 | [HTTP 404 on Gateway](#issue-1-http-404-on-gateway) | 🔴 致命 | ✅ 已修复 | 2026-03-16 |
| 2 | [client.id 白名单校验失败](#issue-2-clientid-白名单校验失败) | 🔴 致命 | ✅ 已修复 | 2026-03-16 |
| 3 | [握手失败后重试刷屏](#issue-3-握手失败后重试刷屏) | 🟡 中等 | ✅ 已修复 | 2026-03-16 |
| 4 | [chat.send 返回 started 被当作最终结果](#issue-4-chatsend-返回-started-被当作最终结果) | 🔴 致命 | ✅ 已修复 | 2026-03-16 |
| 5 | [message.content 格式解析错误](#issue-5-messagecontent-格式解析错误) | 🔴 致命 | ✅ 已修复 | 2026-03-16 |
| 6 | [MCP Server 端口占用 (热重载)](#issue-6-mcp-server-端口占用-热重载) | 🟡 中等 | ✅ 已修复 | 2026-03-16 |
| 7 | [connect() 参数签名不匹配](#issue-7-connect-参数签名不匹配) | 🔴 致命 | ✅ 已修复 | 2026-03-16 |
| 8 | [SimpleButton 样式不存在](#issue-8-simplebutton-样式不存在) | 🔴 致命 | ✅ 已修复 | 2026-03-16 |
| 9 | [Gateway 重启后 Chat Panel 卡死](#issue-9-gateway-重启后-chat-panel-卡死) | 🔴 致命 | ✅ 已修复 | 2026-03-17 |
| 10 | [Create Skill 按钮乱码](#issue-10-create-skill-按钮乱码) | 🟡 中等 | ✅ 已修复 | 2026-03-17 |

---

## Issue 1: HTTP 404 on Gateway

### 现象
UE Chat Panel 发送消息后，返回：
```
OpenClaw returned HTTP 404 Not Found
```

### 根因
OpenClaw Gateway (默认端口 18789) **不提供 REST HTTP API**。其 Web 端点仅服务 SPA 前端页面。
所有业务通信必须通过 **WebSocket RPC 协议** 进行。

用 HTTP POST/GET 去请求 Gateway 等于访问了一个不存在的 REST 端点。

### 修复
放弃 HTTP 方案，改用 **Python Bridge** (`openclaw_bridge.py`) 实现完整的 WebSocket RPC 协议：
```
C++ ExecPythonCommand → Python asyncio/websockets → Gateway WS :18789
```

### 教训
- Gateway 虽然监听 HTTP 端口，但它是 **WebSocket Upgrade** 端点，不是 REST API
- 不要假设"端口能 ping 通 = 支持 REST"

---

## Issue 2: client.id 白名单校验失败

### 现象
WebSocket 连接成功，但握手阶段 `connect` 请求被拒绝：
```json
{
  "code": "INVALID_REQUEST",
  "message": "invalid connect params: at /client/id: must be equal to constant; at /client/id: must match a schema in anyOf"
}
```
错误每秒刷一次，持续不断。

### 根因
OpenClaw Gateway 对 connect 参数中的 `client.id` 字段实施 **JSON Schema 枚举白名单校验**。
只有预定义的客户端标识才被接受。

**白名单** (`GATEWAY_CLIENT_IDS`，定义在 `message-channel-*.js`)：
```javascript
const GATEWAY_CLIENT_IDS = {
  WEBCHAT_UI: "webchat-ui",
  CONTROL_UI: "openclaw-control-ui",
  WEBCHAT:    "webchat",
  CLI:        "cli",                  // ← 我们选择这个
  GATEWAY_CLIENT: "gateway-client",
  MACOS_APP:  "openclaw-macos",
  IOS_APP:    "openclaw-ios",
  ANDROID_APP: "openclaw-android",
  NODE_HOST:  "node-host",
  TEST:       "test",
  FINGERPRINT: "fingerprint",
  PROBE:      "openclaw-probe"
};
```

`mode` 字段也有白名单 (`GATEWAY_CLIENT_MODES`)：
```javascript
const GATEWAY_CLIENT_MODES = {
  WEBCHAT: "webchat",
  CLI:     "cli",
  UI:      "ui",
  BACKEND: "backend",
  NODE:    "node",
  PROBE:   "probe",
  TEST:    "test"
};
```

我们之前使用的 `"ue-editor-agent"` 不在白名单中，被 JSON Schema 校验直接拒绝。

### 修复
将 `_CLIENT_NAME` 从 `"ue-editor-agent"` 改为 `"cli"`，`mode` 从 `"backend"` 改为 `"cli"`：
```python
# 修复前 (错误)
_CLIENT_NAME = "ue-editor-agent"
"mode": "backend"

# 修复后 (正确)
_CLIENT_NAME = "cli"
"mode": "cli"
```

### 教训
- OpenClaw Gateway 的 RPC 协议是**闭源的内部协议**，没有公开文档
- 必须从 npm 安装包的编译产物 (`dist/*.js`) 中逆向分析协议细节
- **关键文件**：`node_modules/openclaw/dist/message-channel-*.js` 包含所有协议常量定义
- 任何新的 client 接入都必须使用白名单中的 ID，不能自定义

### 如何验证
运行 `openclaw_bridge.diagnose_connection()` 会自动检查 client.id 是否合法。

---

## Issue 3: 握手失败后重试刷屏

### 现象
Issue 2 的连锁反应。握手失败后，bridge 以每秒 1 次的频率疯狂重试，
导致 UE Output Log 被刷爆（几分钟内产生数百条错误日志）。

### 根因
`_connect_loop()` 中的退避 (backoff) 逻辑有 bug：
```python
# 问题代码
async with websockets.connect(...) as ws:
    self._ws = ws
    backoff = 1.0  # ← TCP 连接成功就重置！

    if await self._handshake(ws):
        ...
    else:
        # 握手失败，但 backoff 已经被重置为 1.0
```

因为 Gateway 在 localhost，TCP 连接几乎瞬间成功，
所以每次进入 `websockets.connect` 后 backoff 就被重置为 1.0。
握手失败后 `sleep(backoff)` 只等 1 秒，然后 `backoff *= 2` 变成 2，
但下一轮 TCP 又瞬间成功，又被重置回 1.0。如此循环。

### 修复
将 `backoff = 1.0` 移到**握手成功之后**：
```python
# 修复后
async with websockets.connect(...) as ws:
    self._ws = ws
    # 不在这里重置 backoff

    if await self._handshake(ws):
        self._connected = True
        backoff = 1.0  # ← 只在握手成功后才重置
```

修复后退避序列：1s → 2s → 4s → 8s → 16s → 30s（上限）

### 教训
- localhost 场景下 TCP 连接延迟几乎为零，不能把 "TCP 连接成功" 等同于 "连接可用"
- 退避重置应该绑定到**完整连接建立**（包括握手），而不是 TCP 连接

---

## Issue 4: chat.send 返回 started 被当作最终结果

### 现象
UE Chat Panel 发送消息后，显示：
```json
{"runId": "76e3c064-d6b9-41cc-a25b-121ec6ba7a38", "status": "started"}
```
而不是 AI 的实际回复。OpenClaw 侧则正常收到消息并开始处理。

### 根因
OpenClaw Gateway 的 `chat.send` RPC 是**异步流式**的，响应分为多个阶段：

```
Bridge → Gateway:  {type: "req", method: "chat.send", ...}
Gateway → Bridge:  {type: "res", payload: {status: "started", runId: "..."}}  ← 第1个res
Gateway → Bridge:  {type: "event", event: "chat", payload: {state: "delta", ...}}  ← 流式N次
Gateway → Bridge:  {type: "event", event: "chat", payload: {state: "final", ...}}  ← 结束
```

我们的 `_async_chat_send` 在处理第 1 个 `res` 时，只检查了 `status in ("streaming", "accepted")`，
漏掉了 `"started"` 这个状态。导致代码走了 fallback 路径，把整个 JSON 当成最终结果返回。

### 修复
```python
# 修复前 (漏掉 "started")
if status in ("streaming", "accepted"):
    return await self._wait_for_final(timeout=120.0)

# 修复后 (完整的中间状态列表)
if status in ("started", "streaming", "accepted", "running"):
    return await self._wait_for_final(timeout=120.0)
```

### 教训
- Gateway 的 `chat.send` 使用的是 `expectFinal` 模式（源码中明确标注）
- 第一个 `res` 帧只是确认"已接受"，真正的 AI 回复通过后续 `event` 帧到达
- 需要覆盖所有可能的中间状态值，不能只靠猜测

---

## Issue 5: message.content 格式解析错误

### 现象
即使等到了 final 事件，提取到的文本也可能为空字符串。

### 根因
OpenClaw 使用**标准 MCP 消息格式**，`message.content` 是一个**数组**而不是字符串：

```json
{
  "message": {
    "role": "assistant",
    "content": [
      {"type": "text", "text": "这是 AI 的回复内容..."}
    ]
  }
}
```

我们之前的代码假设 `content` 是字符串：
```python
# 错误: 假设 content 是 string
text = message.get("content", "")
```

实际上 `message.get("content", "")` 返回的是一个 list，被当成了非空值但无法直接作为文本使用。

另外，**delta 事件中的 `text` 是累积全文**，而不是增量片段。
即第 N 次 delta 的 `text` 包含了前 N-1 次的所有文本 + 新增文本。
我们之前用 `collected_text.append(text)` 会导致文本重复拼接。

### 修复
```python
# 修复后: 正确解析 content 数组
if isinstance(content, list):
    text_parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(block.get("text", ""))
    text = "".join(text_parts)

# 修复后: delta 用覆盖而非追加
if state == "delta":
    latest_text[0] = text  # 覆盖，因为是累积全文
```

### 教训
- OpenClaw 的消息格式遵循 Anthropic MCP 规范：`content` 是 `ContentBlock[]` 数组
- 不要假设 API 返回简单字符串，要从源码确认实际数据结构
- 流式 delta 的实现方式因 API 而异：有的是增量，有的是累积全文（OpenClaw 是后者）

---

## 排查清单 (Quick Checklist)

遇到 OpenClaw 通信问题时，按此顺序检查：

1. **OpenClaw 是否在运行？**
   ```bash
   openclaw status
   ```

2. **Gateway 端口是否可达？**
   ```bash
   curl -s http://127.0.0.1:18789  # 应返回 HTML (SPA 页面)
   ```

3. **Auth Token 是否正确？**
   - 查看 `~/.openclaw/openclaw.json` 中的 `gateway.auth.token`
   - 对比 `openclaw_bridge.py` 中的 `_DEFAULT_TOKEN`

4. **client.id 是否在白名单中？**
   - 允许值见 Issue 2 的白名单表
   - 运行 `diagnose_connection()` 自动检查

5. **websockets 包是否安装？**
   ```bash
   # UE 5.7 内置 Python
   "C:\Epic Games\UE_5.7\Engine\Binaries\ThirdParty\Python3\Win64\python.exe" -m pip list | findstr websockets
   ```

6. **查看完整日志**
   - UE Output Log 搜索 `LogUEAgent_MCP`
   - 特别关注 `connect error` 和 `handshake failed`

---

## Issue 9: Gateway 重启后 Chat Panel 卡死

### 现象
用户在 UE Chat Panel 中让 AI Agent 重启 OpenClaw Gateway，面板永久显示 "Waiting for AI response..."，无法继续输入。需要关闭并重开 UE 编辑器才能恢复。

### 根因
**Python 端**：`_connect_loop()` 断连清理时只清理了 `_pending` futures，但没有通知正在 `_wait_for_final()` 中等待的 `asyncio.Event`。`_wait_for_final` 通过临时替换 `on_ai_message` 回调来监听 `final` 事件，但断连路径不触发该回调，导致 `final_event.wait()` 挂起直到 300 秒超时。

**C++ 端**：`bIsWaitingForResponse = true` 后没有任何手动取消手段。用户发送的所有消息都被拦截，只显示 "Waiting for AI response..."。

### 修复

**Python (`openclaw_bridge.py`)**：
`_connect_loop` 断连后主动通知等待方：
```python
# 断连时通知 on_ai_message 回调
if was_connected and self.on_ai_message:
    self.on_ai_message(
        "error",
        "[Connection lost] OpenClaw Gateway disconnected (may be restarting). "
        "Click 'Connect' or /connect to reconnect."
    )
```
这会触发 `_wait_for_final` 中 `_capture` 回调 → 设置 `final_event` → 立即解除阻塞。

**C++ (`UEAgentDashboard.cpp`)**：
新增 `/cancel` 本地命令，可随时手动解除等待状态：
- 清理 `bIsWaitingForResponse`
- 移除 "Thinking..." / 流式消息
- 提示用户可继续输入

### 教训
- WebSocket 断连是异步事件，所有等待链路都必须有断连感知机制
- 长时间等待的 UI 状态必须提供手动取消出口
- 不能假设请求一定会有响应（网络随时可能中断）

---

## Issue 10: Create Skill 按钮乱码

### 现象
Dashboard 底部的 "Create Skill" 按钮显示为乱码字符。

### 根因
源码中使用 UTF-8 字节序列嵌入 emoji：
```cpp
.Text(LOCTEXT("CreateSkillBtn", "\xF0\x9F\x94\xA7 Create Skill"))
```
`\xF0\x9F\x94\xA7` 是 🔧 的 UTF-8 编码（4 字节），但 Windows 上 `TEXT()` / `LOCTEXT()` 宏编译为 `wchar_t`（UTF-16）。编译器将每个 `\xNN` 字节直接扩展为独立的 `wchar_t`，产生 4 个无效的 UTF-16 码元，显示为乱码。

### 修复
移除 emoji 前缀，使用纯文本：
```cpp
.Text(LOCTEXT("CreateSkillBtn", "Create Skill"))
```

### 教训
- UE C++ 中 `TEXT()` / `LOCTEXT()` 不能嵌入 UTF-8 字节转义序列
- 如需 emoji，要用 Unicode 转义 `\u` 或 UTF-16 代理对
- 最简单的方案：按钮文字用纯文本，emoji 留给运行时的 Python/JS 层
