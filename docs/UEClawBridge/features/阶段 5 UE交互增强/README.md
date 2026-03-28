# 阶段 5: UE 交互增强 — 功能清单与开发计划

> 版本: v1.0 | 日期: 2026-03-28 | 状态: 开发中

---

## 📋 功能总览

| # | 功能 | 复杂度 | 涉及层 | 优先级 | 状态 | 依赖 |
|---|------|--------|--------|--------|------|------|
| 5.1 | 发送按钮等待态 + 不可点击 | ⭐ 简单 | C++ UI | P0 | ✅ 已完成 | 无 |
| 5.2 | 停止回答按钮 | ⭐ 简单 | C++ UI + Python | P0 | ✅ 已完成 | 5.1 |
| 5.3 | 对话框内容变化时自动滚到底部 | ⭐ 简单 | C++ UI | P0 | ✅ 已完成 | 无 |
| 5.4 | 会话名称加时间戳编号 | ⭐ 简单 | C++ UI + Python | P1 | ✅ 已完成 | 无 |
| 5.5 | 会话长度阈值展示百分比 | ⭐⭐ 中等 | C++ UI + Python + Gateway | P1 | ✅ 已完成 | 无 |
| 5.6 | 文件修改/删除/批量操作弹窗确认 | ⭐⭐ 中等 | C++ UI + Python | P1 | ✅ 已完成 | 无 |
| 5.7 | 弹窗静默模式 | ⭐⭐ 中等 | C++ UI + Python + 持久化 | P1 | ✅ 已完成 | 5.6 |
| 5.8 | 多会话管理 | ⭐⭐⭐ 复杂 | C++ UI + Python + Gateway RPC | P2 | ✅ 已完成 | 5.4 |
| 5.9 | Plan 模式 | ⭐⭐⭐⭐ 很复杂 | 全栈 (C++/Python/Gateway/OpenClaw) | P2 | ✅ 已完成 | 5.2, 5.8 |

---

## 分组策略

### 第一批: 简单独立需求 (可并行, 预计 1-2h)
- **5.1** 发送按钮等待态
- **5.2** 停止回答按钮
- **5.3** 自动滚到底部
- **5.4** 会话名称加时间戳

### 第二批: 中等需求 (可并行, 预计 2-4h)
- **5.5** 会话长度百分比
- **5.6** 文件操作弹窗确认
- **5.7** 弹窗静默模式

### 第三批: 复杂需求 (需先出规划文档)
- **5.8** 多会话管理
- **5.9** Plan 模式

---

## 第一批: 简单需求详细设计

### 5.1 发送按钮等待态 + 不可点击

**现状**: AI 执行过程中发送按钮始终可点击，`OnSendClicked()` 里用 `bIsWaitingForResponse` 判断重复发送时只弹系统消息，用户体验不好。

**方案**:
1. 给发送按钮添加 `IsEnabled` 绑定: `!bIsWaitingForResponse`
2. 按钮文本在等待时变为"等待中..."
3. `SendToOpenClaw()` 设 `bIsWaitingForResponse=true` 时按钮自动禁用
4. `HandlePythonResponse()` 设 `bIsWaitingForResponse=false` 时按钮恢复

**改动文件**: `UEAgentDashboard.cpp` (Construct 区域 + 按钮 Lambda)
**本地化**: `SendBtnWaiting` = "等待中..." / "Waiting..."

---

### 5.2 停止回答按钮

**现状**: AI 响应过程中无法主动停止，只能等 300s 超时。

**方案**:
1. 在发送按钮的位置，等待时显示"停止"按钮（替换发送按钮），停止后恢复为发送按钮
2. 点击停止 → 调用 `PlatformBridge->CancelRequest()` + 停止 PollTimer + `bIsWaitingForResponse=false`
3. Python 侧: `cancel_current_request()` 已实现，可直接调用
4. 添加 system 消息"已停止 AI 回答"

**改动文件**: `UEAgentDashboard.h/cpp`, `IAgentPlatformBridge.h`, `OpenClawPlatformBridge.h/cpp`
**本地化**: `StopBtn` = "停止" / "Stop", `StopTip` = "停止 AI 回答" / "Stop AI response", `AIStopped` = "已停止 AI 回答" / "AI response stopped"

---

### 5.3 对话框内容变化时自动滚到底部

**现状**: 新消息添加后没有自动滚动，用户需要手动滚到底部查看最新内容。

**方案**:
1. 在 `RebuildMessageList()` 末尾添加 `MessageScrollBox->ScrollToEnd()`
2. 在 `UpdateStreamingMessage()` 的 `RebuildMessageList()` 调用后也确保滚到底
3. 用 `FTimerManager` 或 `GEditor->GetTimerManager()` 延迟一帧执行滚动（确保 Layout 完成）

**改动文件**: `UEAgentDashboard.cpp`

---

### 5.4 会话名称加时间戳编号

**现状**: 每次新对话的 session key 格式为 `agent/client:timestamp`，但 UI 上显示的会话名称都一样。

**方案**:
1. 在 `OnNewChatClicked()` 时，给新会话生成可读标签，如 "对话 03-28 09:15"
2. 新增 `FString CurrentSessionLabel` 成员变量
3. 状态栏或某个区域显示当前会话名称
4. 格式: `"对话 MM-DD HH:mm"` / `"Chat MM-DD HH:mm"`

**改动文件**: `UEAgentDashboard.h/cpp`
**本地化**: `SessionLabel` = "对话" / "Chat"

---

## 第二批: 中等需求详细设计

### 5.5 会话长度阈值展示百分比

**现状**: 用户不知道当前会话消耗了多少上下文窗口。

**技术方案**:
1. OpenClaw Gateway 在 `sessions.json` 中记录 `contextTokens`，通过 chat event 的 `usage` 字段返回
2. bridge_core.py 需要解析 AI 回复中的 token usage 信息（如果 Gateway 返回的话）
3. 从 stream.jsonl 或最终响应中提取 `inputTokens` / `contextTokens`
4. C++ 侧在状态栏显示 `"上下文: 45% (36K/80K tokens)"`
5. 百分比 = contextTokens / model_context_window_size

**待确认**:
- Gateway chat event 是否在响应中包含 token usage?（需实测）
- 如果不包含，是否需要新增 RPC 方法查询 session token stats?
- model 的 context window 大小从哪里获取?

**改动文件**: `bridge_core.py`, `openclaw_bridge.py`, `UEAgentDashboard.h/cpp`
**本地化**: `ContextUsage` = "上下文" / "Context"

---

### 5.6 文件修改/删除/批量操作弹窗确认

**现状**: 阶段 2.3 已实现风险分级确认 UI（`2.3 风险分级确认UI(Risk-Aware Confirmation).md`），但当前可能未覆盖文件操作的细粒度确认。

**方案**:
1. 在 `run_ue_python` 的 Static Guard (AST 扫描) 阶段检测文件操作
2. 文件修改 (`os.rename`, `shutil.move`, 资产修改) → 中风险弹窗
3. 文件删除 (`os.remove`, `shutil.rmtree`, 资产删除) → 高风险弹窗
4. 批量操作 (循环中包含修改/删除，操作数 > 阈值) → 高风险弹窗
5. 弹窗内容: 操作类型 + 受影响文件列表 + 确认/取消

**改动文件**: Python Static Guard 相关代码, `UEAgentDashboard.cpp` (确认 UI)

---

### 5.7 弹窗静默模式

**现状**: 每次危险操作都弹窗确认，频繁操作时影响效率。

**方案**:
1. 新增全局设置 `bSilentMode`，存储在配置文件（如 `~/.artclaw/config.json`）
2. 两个入口修改:
   - 插件管理面板: 设置 Tab 增加"静默模式"开关
   - 弹窗界面: 增加"本次会话不再提示"复选框
3. 静默模式下所有中风险操作自动通过，高风险操作仍弹窗
4. "本次会话不再提示" = 进程生命周期内静默，不持久化

**改动文件**: Python 配置读写, `UEAgentDashboard.h/cpp` 或 管理面板
**依赖**: 5.6（需要先有弹窗才能加静默）

---

## 第三批: 复杂需求（需要详细规划文档）

### 5.8 多会话管理

**复杂度评估**: ⭐⭐⭐ 复杂
- 需要 UI 侧管理多个会话的切换、列表展示
- 需要 Python 侧支持多 session key 的消息路由
- 需要 Gateway 侧 session 列表查询

**核心问题**:
1. 会话列表如何获取? → Gateway `sessions.list` RPC? 还是本地维护?
2. 会话切换时消息历史如何加载? → 从 Gateway transcript? 本地缓存?
3. 是否需要侧边栏? → UI 空间有限，考虑下拉菜单或独立面板
4. 与 `/new` 的关系: `/new` 创建新会话，需要将旧会话保留在列表中

**→ 需要独立规划文档: `5.8 多会话管理.md`**

---

### 5.9 Plan 模式

**复杂度评估**: ⭐⭐⭐⭐ 很复杂

**概念**: AI 在执行任务前先生成一个步骤计划（Plan），用户可以审阅、删除未开始的步骤、批准后执行、中途停止并继续。

**核心问题**:
1. **OpenClaw 是否原生支持 Plan 模式?**
   - 查阅 OpenClaw 文档，未发现原生 plan 模式支持
   - 需要在 ArtClaw 层自行实现

2. **Plan 数据模型**:
   - Plan = 有序步骤列表，每步有状态 (pending/running/done/skipped/failed)
   - 需要 Python 侧维护 plan state
   - C++ UI 展示 plan 进度

3. **Plan 的生命周期**:
   - 生成: AI 回复包含 plan（需约定格式，如 JSON block）
   - 审阅: 用户在 UI 中查看步骤列表
   - 编辑: 删除未开始的步骤
   - 执行: 逐步执行，每步完成后更新状态
   - 暂停/继续: 停止后保留 plan 状态，可继续执行

4. **与 OpenClaw 的交互**:
   - Plan 生成: 让 AI 在 system prompt 中注入 plan 模式指令
   - Plan 执行: 每一步作为一次 chat.send? 还是连续执行?
   - 停止/继续: cancel_current() 停止当前步骤，继续时从下一步开始

5. **争议点**:
   - Plan 解析: AI 输出格式不稳定，如何可靠解析 plan?
   - 步骤粒度: 谁决定步骤拆分? AI? 用户?
   - 与多会话的关系: Plan 是否绑定到特定会话?

**→ 需要独立规划文档: `5.9 Plan模式.md`**

---

## 文件修改影响矩阵

| 文件 | 5.1 | 5.2 | 5.3 | 5.4 | 5.5 | 5.6 | 5.7 | 5.8 | 5.9 |
|------|-----|-----|-----|-----|-----|-----|-----|-----|-----|
| UEAgentDashboard.h | | ✓ | | ✓ | ✓ | | ✓ | ✓ | ✓ |
| UEAgentDashboard.cpp | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| IAgentPlatformBridge.h | | ✓ | | | | | | ✓ | |
| OpenClawPlatformBridge.h/cpp | | ✓ | | | | | | ✓ | |
| UEAgentLocalization.cpp | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| bridge_core.py | | | | | ✓ | | | ✓ | ✓ |
| openclaw_bridge.py | | | | | ✓ | ✓ | ✓ | | ✓ |
| mcp_server.py | | | | | | ✓ | ✓ | | ✓ |

---

## 变更历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03-28 | 初始版本，9 个功能点分类评估 |
| v1.1 | 2026-03-28 | 全部 9 个功能点开发完成，12 files +2411 lines |
