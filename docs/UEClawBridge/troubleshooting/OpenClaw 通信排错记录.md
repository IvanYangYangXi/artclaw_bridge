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
| 11 | [connect 缺 device identity 签名导致权限不足](#issue-11-connect-缺-device-identity-签名导致权限不足) | 🔴 致命 | ✅ 已修复 | 2026-04-22 |
| 12 | [安装脚本 models 块被整体覆盖丢失 onboard 配置](#issue-12-安装脚本-models-块被整体覆盖丢失-onboard-配置) | 🟠 高 | ✅ 已修复 | 2026-04-29 |
| 13 | [subprocess 列表方式找不到 openclaw.cmd](#issue-13-subprocess-列表方式找不到-openclaw-cmd) | 🔴 致命 | ✅ 已修复 | 2026-04-29 |
| 14 | [token_mismatch：代理软件注入 X-Forwarded-For 头](#issue-14-token_mismatch代理软件注入-x-forwarded-for-头) | 🔴 致命 | ✅ 已修复 | 2026-04-29 |
| 15 | [device_token_mismatch：浏览器缓存旧 device token](#issue-15-device_token_mismatch浏览器缓存旧-device-token) | 🔴 致命 | ✅ 已修复 | 2026-04-29 |
| 16 | [device pairing required：新设备未批准无法进入 Chat](#issue-16-device-pairing-required新设备未批准无法进入-chat) | 🔴 致命 | ✅ 已修复 | 2026-04-29 |
| 17 | [Gateway 读取 LobsterAI state 目录而非 ~/.openclaw](#issue-17-gateway-读取-lobsterai-state-目录而非-openclaw) | 🟠 高 | ✅ 已修复 | 2026-04-29 |
| 18 | [Gateway 启动缓慢：~49 个 provider 插件串行 require](#issue-18-gateway-启动缓慢49-个-provider-插件串行-require) | 🟠 高 | ✅ 已缓解 | 2026-04-29 |

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

---

## Issue 11: connect 缺 device identity 签名导致权限不足

### 现象
别人电脑上安装 UE 插件后，通过 Chat Panel 与 AI 对话时连接正常但某些操作权限不足，
或新版 Gateway 要求 device 签名时直接握手失败。

### 根因
OpenClaw Gateway 协议要求所有 WS 客户端在 `connect` 握手时提供 **device identity 签名**
（Ed25519 签名 challenge nonce），否则不授予完整 operator scope。

协议要求（`docs/gateway/protocol.md`）：
```
All WS clients must include `device` identity during `connect` (operator + node).
All connections must sign the server-provided `connect.challenge` nonce.
```

**修复前的 connect params**（所有客户端）：
```json
{
  "auth": {"token": "..."},
  "role": "operator",
  "scopes": ["operator.admin"]
}
```
缺少 `device` 字段 → Gateway 不授予 operator scope → 权限不足。

**修复后的 connect params**：
```json
{
  "auth": {"token": "..."},
  "role": "operator",
  "scopes": ["operator.read", "operator.write", "operator.admin"],
  "device": {
    "id": "<deviceId>",
    "publicKey": "<base64url raw 32-byte Ed25519 public key>",
    "signature": "<base64url Ed25519 signature>",
    "signedAt": 1745305000000,
    "nonce": "<server challenge nonce>"
  }
}
```

### v3 签名 payload 格式
```
v3|{deviceId}|{clientId}|{clientMode}|{role}|{scopes}|{signedAtMs}|{token}|{nonce}|{platform}|{deviceFamily}
```
各字段用 `|` 拼接，用 Ed25519 私钥签名，结果 base64url 编码（去 padding）。

### device.json 位置
`~/.openclaw/identity/device.json`，OpenClaw 安装时自动生成：
```json
{
  "version": 1,
  "deviceId": "...",
  "publicKeyPem": "-----BEGIN PUBLIC KEY-----\n...",
  "privateKeyPem": "-----BEGIN PRIVATE KEY-----\n...",
  "createdAtMs": ...
}
```

### 影响范围
| 文件 | 用途 | 修复状态 |
|---|---|---|
| `platforms/openclaw/openclaw_ws.py` | UE 专用 WS | ✅ PR#1 修复 |
| `core/bridge_core.py` | DCC 上行聊天 (Maya/Max/Blender/Houdini/SP/SD/ComfyUI) | ✅ 已修复 |
| `ArtClawToolManager/src/server/services/gateway_client.py` | Tool Manager | ✅ 已修复 |
| `core/openclaw_diagnose.py` | 诊断工具 | 低优先级（诊断用途，token 认证够用） |

### 修复方案
提取 `core/device_auth.py` 共享模块，所有 handshake 点统一调用：
```python
from device_auth import get_device_identity, build_device_auth

identity = get_device_identity()
if identity:
    params["device"] = build_device_auth(identity, role, scopes, signed_at_ms, nonce, token)
```

### 容错设计
- `device.json` 不存在 → 跳过签名，走 token-only 认证（降级）
- `cryptography` 未安装 → import 失败被 except 捕获 → 返回 None → 跳过签名
- 签名构建异常 → except 捕获 → 日志警告 → 跳过签名
- **无签名不影响本地 loopback 连接**（Gateway 对本地连接可能放宽要求）

### 教训
- Gateway 协议升级后，所有 WS 客户端都需要同步更新握手逻辑
- 多个文件各自实现 handshake 会导致遗漏，应该抽公共模块
- 签名相关的代码应该有清晰的 fallback 路径，不能因为缺依赖就崩溃

---

## Issue 12: 安装脚本 models 块被整体覆盖丢失 onboard 配置

### 现象
重新运行安装脚本后，`openclaw.json` 中 `models` 块的其他字段（onboard 自动生成的内置模型列表、缓存设置等）全部丢失，只剩下脚本注入的 `netease-codemaker` provider。

### 根因
脚本中使用直接赋值覆盖整个 `models` 块：
```python
# 错误做法：整体替换
cfg["models"] = {
    "mode": "merge",
    "providers": { "netease-codemaker": { ... } }
}
```
`onboard` 生成的配置里 `models` 可能已有其他内容，直接赋值会全部清空。

### 修复
改为 merge 写法，只修改需要的字段：
```python
# 正确做法：只注入，不覆盖
cfg.setdefault("models", {})["mode"] = "merge"
cfg["models"].setdefault("providers", {})["netease-codemaker"] = { ... }
```

### 顺带修复
model 条目补全了参考格式要求的完整字段（`contextWindow`、`maxTokens`、`input`、`cost`、`reasoning`），避免 UI 显示异常或 token 计费逻辑报错。

### 教训
- 对 onboard 生成的配置文件只做增量注入，永远不要整体替换某个块
- 对照 `openclaw.json` 参考格式验证每个字段的完整性

---

## Issue 13: subprocess 列表方式找不到 openclaw.cmd

### 现象
安装脚本 Step 4 运行时崩溃：
```
FileNotFoundError: [WinError 2] 系统找不到指定的文件。
subprocess.run(["openclaw", "gateway", "stop"], ...)
```

### 根因
Windows 上 `openclaw` 是 npm 全局安装的 `.cmd` 脚本，不是 `.exe`。
`subprocess.run` 传入列表时，Python 直接调用 `CreateProcess` 查找可执行文件，找不到 `.cmd` 后缀的文件。

`subprocess.run` 只有在 `shell=True` 时才会通过 `cmd.exe` 解析 `.cmd` 脚本。

### 修复
所有 openclaw 相关调用统一加 `shell=True`：
```python
# 错误（Linux/Mac 可以，Windows 不行）
subprocess.run(["openclaw", "gateway", "stop"], ...)

# 正确（Windows 兼容）
subprocess.run("openclaw gateway stop", shell=True, ...)
```

### 教训
- Windows 上 npm 全局命令（`openclaw`、`node`、`npm` 等）都是 `.cmd` 脚本
- Python `subprocess` 在 Windows 上调用 `.cmd` 必须使用 `shell=True`
- `shell=True` 时参数传字符串，`shell=False` 时传列表，不能混用

---

## Issue 14: token_mismatch：代理软件注入 X-Forwarded-For 头

### 现象
Gateway 启动正常，`openclaw dashboard` 打开浏览器后连接被拒绝，日志报：
```
[ws] unauthorized reason=token_mismatch
[ws] Proxy headers detected from untrusted address.
     Connection will not be treated as local.
     fwd=4.2.2.2
```

### 根因
本机运行的 **Clash/VPN 代理软件**在劫持本地流量时，自动给请求加上了 `X-Forwarded-For: 4.2.2.2` 等转发头。

Gateway 检测到转发头来自「未受信任的地址」，不再把该连接视为本地连接，token 验证走了不同的分支（远程客户端模式），导致 token_mismatch。

### 修复
在 `openclaw.json` 的 `gateway` 块中添加 `trustedProxies`，告知 Gateway 信任本机 loopback 的代理头：
```json
"gateway": {
  "trustedProxies": ["127.0.0.1", "::1"]
}
```

脚本注入方式：
```python
cfg.setdefault("gateway", {})["trustedProxies"] = ["127.0.0.1", "::1"]
```

### 教训
- 开发环境中经常有代理/VPN 软件在运行，Gateway 的本地连接检测会被干扰
- `trustedProxies` 应作为安装脚本的默认配置注入，而不是等问题出现再排查

---

## Issue 15: device_token_mismatch：浏览器缓存旧 device token

### 现象
重新安装 OpenClaw 后，打开 `http://127.0.0.1:18789/dashboard` 连接被拒绝：
```
[ws] unauthorized reason=device_token_mismatch
(rotate/reissue device token)
```

### 根因
浏览器 LocalStorage/Cookie 中保存了**上一次安装的 device token**。
新安装的 Gateway 是全新 state，不认识旧 device token，握手时验证失败。

### 修复
**方案 A（推荐）**：使用 `openclaw dashboard` 命令打开浏览器，该命令会生成带签名 token 的 URL（`?token=xxx`），直接绕过 device token 验证。

**方案 B**：手动清除浏览器站点数据：
`F12` → `Application` → `Storage` → `Clear site data`（针对 `127.0.0.1:18789`）

脚本修复：将 Step 4 的 `os.startfile(url)` 改为 `subprocess.run("openclaw dashboard", shell=True)`，确保始终带 token 打开。

### 教训
- 裸 URL（`http://127.0.0.1:18789/`）直接打开，浏览器使用缓存的 device token，重装后必然失败
- 安装脚本必须通过 `openclaw dashboard` 打开，不能直接 `os.startfile(url)`

---

## Issue 16: device pairing required：新设备未批准无法进入 Chat

### 现象
清除浏览器缓存后重新打开 Dashboard，页面停留在连接界面，提示：
```
device pairing required (requestId: db9b1069-ad74-43eb-985b-7594824415d0)
```
无法进入 chat 界面。

### 根因
清除浏览器缓存后，浏览器作为一个**全新 device** 发起连接请求，Gateway 需要明确批准该设备才允许接入。这是 Gateway 的安全机制，防止未授权 client 接入。

### 修复
**手动修复**：在终端运行：
```
openclaw devices approve <requestId>
```

**脚本自动修复**：安装脚本 Step 4 在打开浏览器后等待 3 秒，自动查询并批准所有 pending 设备：
```python
pending = subprocess.run("openclaw devices list", shell=True, ...)
for line in pending.stdout.splitlines():
    if "pending" in line.lower():
        # 提取 requestId 并自动 approve
        subprocess.run(f"openclaw devices approve {request_id}", shell=True, ...)
```

### 教训
- 重装 / 清浏览器缓存后必然触发 device pairing，安装脚本需要自动处理
- `openclaw devices list/approve` 是安装流程的必要步骤，应纳入标准安装脚本

---

## Issue 17: Gateway 读取 LobsterAI state 目录而非 ~/.openclaw

### 现象
Gateway 日志中出现：
```
canvas host mounted at ...AppData\Roaming\LobsterAI\openclaw\state\canvas
storePath: ...AppData\Roaming\LobsterAI\openclaw\state\cron\jobs.json
```
说明 Gateway 使用的是 LobsterAI 的 state 目录，而不是脚本指定的 `~/.openclaw`。
导致 device token、auth state 与安装脚本的配置路径不一致，引发一系列认证问题。

### 根因
LobsterAI 在安装时设置了系统级环境变量 `OPENCLAW_HOME` 指向其自己的数据目录。
Python 脚本中 `os.environ["OPENCLAW_HOME"] = home` 只修改了当前进程的环境变量，
但传给子进程（`onboard`、`gateway start` 等）时若没有显式传递 `env` 参数，
子进程会继承系统环境变量，忽略脚本的修改。

同时 LobsterAI 进程（`LobsterAI.exe`）在后台运行时会启动自己的 Gateway 实例，
与脚本安装的版本共用 18789 端口，造成环境污染。

### 修复
1. **确保 LobsterAI 完全退出**（系统托盘右键退出）再运行安装脚本
2. 脚本中构建独立的 `oc_env` 字典并显式传给所有子进程：
```python
oc_env = os.environ.copy()
oc_env["OPENCLAW_HOME"] = home
oc_env["OPENCLAW_CONFIG_PATH"] = cfg_path

subprocess.run("openclaw onboard ...", shell=True, env=oc_env, ...)
subprocess.run("openclaw gateway stop", shell=True, env=oc_env, ...)
subprocess.run("openclaw gateway start", shell=True, env=oc_env, ...)
subprocess.run("openclaw dashboard", shell=True, env=oc_env, ...)
```

### 教训
- `os.environ` 修改只对当前 Python 进程有效，子进程不会自动继承
- 所有需要隔离环境的子进程调用都必须显式传 `env=oc_env`
- 安装前必须确认 LobsterAI 等可能占用相同端口/目录的程序已完全退出

---

## Issue 18: Gateway 启动缓慢：~49 个 provider 插件串行 require

### 现象
Gateway 首次冷启动耗时 **~117 秒（约 2 分钟）**，启动期间 CPU 100%。
Dashboard / Health API 在此期间不可用。

### 根因
OpenClaw v2026.4.26 打包了约 110+ 个 bundled 插件（49 个 provider 插件 + 其余 channel/utility 插件）。
在启动的 `discovery` 阶段，gateway 会遍历所有插件目录并执行 require() 加载其 provider-discovery.js，
随后执行 discovery 处理逻辑。49 个 provider 插件逐个串行加载，平均每个耗时 2-1600ms。

从 PLUGIN_LOAD_PROFILE 数据看，最慢的插件：
- `vydra`: 2161ms
- `kimi`: 89ms
- `zai`: 82ms
- `xiaomi`: 68ms
- `tencent`: 71ms + 39ms + 17ms

总 startup trace：
```
sidecars.total 108091.9ms total=117342.4ms
```

之前（未配置 plugins.deny + entries.enabled=false）的启动时间为 **~253 秒**。
配置 deny 后降至 **~117 秒**，因为插件虽无需 require() 多次（Node.js module cache），
但 discovery 阶段仍需处理每个插件的元数据。

### 修复方案（install_openclaw.py v2）
1. **plugins.deny + plugins.entries.enabled=false** — 配置级别禁用不必要的 49 个 provider 插件
   （注意：deny 列表中的插件 ID 必须与 `openclaw.plugin.json` 中的 id 字段一致，而非目录名。
   例如 `kimi-coding` 目录的实际插件 ID 是 `kimi`）
2. **`"kimi"` 替代 `"kimi-coding"`** — 修复了目录名与插件 ID 不一致导致的 config validation 失败
3. **`OPENCLAW_SKIP_CHANNELS=1` 被移除** — 该选项会跳过 channel 启动，导致 webchat 路由不可用
4. **网关配置优化**：
   - `gateway.bind = "loopback"` — 仅绑定 loopback
   - `discovery.mdns.mode = "off"` — 关闭 Bonjour 扫描
   - `discovery.wideArea.enabled = false` — 关闭 LAN 广播
   - `logging.level = "info"` — 避免 debug 日志刷屏
5. **env vars**：PLUGIN_LOAD_PROFILE, GATEWAY_STARTUP_TRACE, SKIP_GMAIL_WATCHER,
   SKIP_BROWSER_CONTROL_SERVER, DISABLE_BONJOUR, BROWSER_ENABLED=0,
   INSTALL_SCAN_MAX_DEPTH=3, INSTALL_SCAN_MAX_DIRECTORIES=200

### 已知局限
- `plugins.deny` 仅在 `config-normalization-shared` 层面阻止插件激活（状态为 "blocked-by-denylist"），
  但无法阻止 `startChannelInternal()` 中的 require() 调用（require 发生在 isEnabled() 检查之前）。
- 不删除文件的情况下，首次冷启动仍需要 ~117 秒。后续启动（Node.js module cached）时间未知。
- 如需进一步加速，可设置 `OPENCLAW_DISABLE_BUNDLED_PLUGINS=1` 环境变量（会禁用所有 bundled
  插件包括 channels，需测试 webchat 是否正常）。

### Plugins.deny 与插件 ID 映射
部分 provider 插件的目录名与 `openclaw.plugin.json#id` 不一致：
| 目录名 | 实际插件 ID |
|--------|------------|
| kimi-coding | kimi |

其余 48 个 plugin 的目录名与 ID 一致。
