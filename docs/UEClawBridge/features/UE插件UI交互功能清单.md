# UE Claw Bridge — UI 交互与展示功能清单

> **目的**: 整理 UE 插件 (UEClawBridge) 中已实现的所有 UI 交互、对话信息展示及优化项，作为下一个 DCC 软件接入开发的内容参考清单。
>
> **基于源码**: `subprojects/UEDAgentProj/Plugins/UEClawBridge/Source/`
>
> **日期**: 2026-03-23

---

## 一、插件入口与窗口管理

### 1.1 工具栏按钮
- **位置**: UE 编辑器主工具栏 `PlayToolBar` 区域 + `Window` 菜单
- **行为**: 点击打开/聚焦 Dashboard 可停靠窗口
- **实现**: `FUEClawBridgeCommands` 注册 `UI_COMMAND`，`FUEClawBridgeModule::RegisterMenus()` 扩展菜单
- **图标**: 自定义 `FUEClawBridgeStyle` 图标样式

### 1.2 可停靠窗口 (Nomad Tab)
- **Tab 名称**: `UEClawBridgeDashboard`
- **Tab 类型**: `NomadTab` (可自由停靠、拖拽到编辑器任意位置)
- **显示名**: "UE Claw Bridge"
- **Tab 内容**: 承载 `SUEAgentDashboard` 一体化面板
- **实现**: `FGlobalTabmanager::RegisterNomadTabSpawner` + `SpawnDashboardTab`

---

## 二、一体化 Dashboard 面板 (`SUEAgentDashboard`)

整个面板从上到下分为以下区域：

### 2.1 状态栏 (可折叠)
- **默认折叠**: `InitiallyCollapsed(true)`
- **折叠态显示**: 单行摘要 `● Connected | ws://localhost:8080`
- **展开后显示**:
  - 版本号 (从 Plugin Descriptor 动态读取)
  - 服务器地址 (MCP WebSocket 端口)
  - 统计信息 (活跃连接数 + 消息数)
  - 操作按钮组: **连接** / **断开** / **诊断** / **日志**
- **状态颜色**: 已连接=绿色(0.2,0.8,0.2)，未连接=灰色(0.6,0.6,0.6)
- **自动刷新**: 通过 FTSTicker 每 2 秒轮询 `_bridge_status.json` 更新连接状态

### 2.2 消息区域 (聊天历史)
- **容器**: `SScrollBox`，纵向滚动
- **消息上限**: 500 条 (`MaxMessages`)，超出自动移除最早消息
- **消息模型** (`FChatMessage`):
  - `Sender`: "user" / "assistant" / "system" / "streaming" / "thinking"
  - `Content`: 消息文本
  - `Timestamp`: 显示 HH:MM 格式
  - `bIsCode`: 是否代码块 (使用 Mono 字体)
- **消息展示**:
  - 每条消息: 发送者标签(粗体+颜色) + 时间戳(灰色小号) + 内容(可选中/复制)
  - 内容控件: `SMultiLineEditableText` (只读模式，支持右键菜单/复制)
  - 自动换行: `AutoWrapText(true)`
  - 自动滚动到底部: `ScrollToEnd()`
- **发送者颜色区分**:
  - 用户(user): 蓝色 (0.3, 0.7, 1.0)
  - AI 助手(assistant): 绿色 (0.4, 0.9, 0.4)
  - 流式消息(streaming): 较灰绿色 (0.45, 0.6, 0.45)
  - 思考过程(thinking): 淡紫色 (0.7, 0.5, 0.9)
  - 系统(system): 灰色 (0.7, 0.7, 0.7)
- **发送者标签本地化**:
  - 中文: "你" / "AI 助手" / "系统"
  - 英文: "You" / "AI Agent" / "System"

### 2.3 快捷输入分栏 (可折叠)
- **标题**: "快捷输入" / "Quick Inputs"
- **默认折叠**: `InitiallyCollapsed(true)`
- **功能**:
  - 展示用户自定义的快捷输入按钮 (WrapBox 自动换行)
  - 点击按钮 → 自动填充内容到输入框 + 聚焦输入框
  - 每个按钮附带 **编辑(e)** 和 **删除(x)** 小按钮
  - **添加按钮**: "+ 添加" / "+ Add"
- **编辑功能**:
  - 弹出模态窗口 (`SWindow`)，包含名称和内容编辑框
  - 保存/取消按钮
  - 取消时自动删除空白新增项
- **删除确认**: `FMessageDialog::Open` 弹出 Yes/No 确认
- **数据持久化**:
  - JSON 格式: `{quick_inputs: [{id, name, content}, ...]}`
  - 存储路径: `项目/Saved/UEAgent/quick_inputs.json`
  - 编码: UTF-8 without BOM
- **空状态**: 显示灰色斜体提示 "暂无快捷输入，点击「+ 添加」创建一个。"

### 2.4 输入区域
- **输入框**: `SMultiLineEditableTextBox`
  - 最小高度 52px，最大高度 120px
  - 自动换行
  - 动态占位提示文本 (根据发送模式变化)
  - 支持 `/` 前缀触发 Slash 命令菜单
- **发送按钮**: 位于输入框右侧底部对齐
- **发送模式切换**: `[☑] Enter 发送` 复选框
  - Enter 模式: Enter 发送，Shift+Enter 换行
  - Ctrl+Enter 模式: Ctrl+Enter 发送，Enter 换行
- **占位提示动态切换**:
  - Enter 模式: "向 AI 提问... (Enter 发送, Shift+Enter 换行, / 查看命令)"
  - Ctrl+Enter 模式: "向 AI 提问... (Ctrl+Enter 发送, Enter 换行, / 查看命令)"

### 2.5 底部工具栏
- **+ 新会话**: 清空聊天记录 + 重置 session key + 发送 `/new` 给 AI
- **创建 Skill**: 在输入框填充引导文本 `"Create an artclaw skill: "`，聚焦输入框让用户续写
- **语言切换按钮**: 显示 "En" 或 "中"，切换中英文界面
- **发送模式复选框**: 在最右侧

---

## 三、Slash 快捷命令系统

### 3.1 命令菜单
- **触发方式**: 输入框输入 `/` 前缀时自动弹出
- **菜单位置**: 输入框上方 (`MenuPlacement_AboveAnchor`)
- **菜单容器**: `SMenuAnchor` + `SListView`
- **最大高度**: 200px，最小宽度 300px
- **实时过滤**: 随输入文本实时匹配命令名

### 3.2 命令列表
分为 **本地命令** (白色，本地执行) 和 **AI 命令** (蓝色，转发给 AI):

| 命令 | 类型 | 描述 |
|------|------|------|
| `/connect` | 本地 | 连接 OpenClaw 网关 |
| `/disconnect` | 本地 | 断开连接 |
| `/diagnose` | 本地 | 运行连接诊断 |
| `/status` | 本地 | 显示连接状态详情 |
| `/clear` | 本地 | 清空聊天记录 (不重置 session) |
| `/cancel` | 本地 | 取消等待 AI 响应 |
| `/help` | 本地 | 显示所有可用命令 |
| `/new` | AI | 开始新会话 |
| `/compact` | AI | 压缩上下文 |
| `/review` | AI | 审查选中 Actor / 场景 |
| `/undo` | AI | 撤销上一步 AI 操作 |

### 3.3 命令执行细节
- **选中命令**: 自动填充到输入框，清空输入，关闭菜单，执行命令
- **输入框直接输入**: 也可直接输入 `/command args` 按 Enter 执行
- **`/cancel` 双端联动**: 停止 poll timer + 通知 PlatformBridge 取消 + 移除 thinking/streaming 消息 + UI 状态重置
- **`/status` 输出**: 显示 MCP 客户端状态、服务器地址、消息数、发送模式；同时触发 Python 侧 MCP+Bridge 状态检查
- **`/new` 流程**: 清空消息 → 重置 PlatformBridge session → 发送 `/new` 给 AI → 显示 AI 回复

---

## 四、AI 通信与消息展示

### 4.1 消息发送流程
1. 用户输入文本，按发送
2. 检查是否 Slash 命令（`/` 开头）→ 路由到命令处理
3. 检查是否正在等待响应 → 提示 "仍在等待..." + 建议 `/cancel`
4. 添加用户消息到聊天
5. 转义消息 (反斜杠、单引号、换行符)
6. 通过 `PlatformBridge::SendMessageAsync` 异步发送
7. 显示 "思考中..." 系统消息
8. 启动 FTSTicker 每 0.25 秒轮询响应文件

### 4.2 流式显示 (Streaming)
- **流式文件**: `_openclaw_response_stream.jsonl` (JSONL 格式)
- **事件类型**:
  - `thinking`: 思考过程，淡紫色显示
  - `delta`: 正文流式，灰绿色显示
- **实现**:
  - 记录已读行数 (`StreamLinesRead`)，每次轮询只处理新增行
  - 首次流式数据替换 "思考中..." 消息
  - 相同 sender 类型的流式数据更新同一条消息(替换内容)
  - sender 类型变化时追加新消息 (如 thinking → streaming)
- **最终回复**:
  - 检测到最终响应文件后，移除所有 thinking/streaming 消息
  - 显示最终 AI 回复 (绿色 assistant)

### 4.3 防重发与取消
- `bIsWaitingForResponse` 标记防止重复发送
- 新请求发送前自动取消旧的 poll timer
- `/cancel` 完整流程: 清标记 + 停 timer + 通知 Python `cancel_current_request()` + 清理 thinking/streaming 消息

### 4.4 错误处理
- 空回复: 显示 "AI 返回了空回复"
- `[Error]` 前缀: 作为系统消息显示
- 连接失败: 显示详细排查指引 (检查 OpenClaw 运行 / 端口 / /diagnose)

---

## 五、连接管理

### 5.1 自动连接
- 面板打开时自动调用 `ConnectOpenClawBridge()`
- 连接成功后自动发送环境上下文给 AI (`SendEnvironmentContext`)

### 5.2 连接状态轮询
- FTSTicker 每 2 秒读取 `_bridge_status.json` (Python 侧写入)
- 检测到状态变化时更新 `UUEAgentSubsystem::SetConnectionStatus`
- 触发双委托广播: 动态委托 (Blueprint/Python) + 原生委托 (C++ Slate)

### 5.3 健康检查 / 诊断
- 优先使用 `health_check.py` 完整检查
- Fallback 到 `PlatformBridge::RunDiagnostics`
- 结果通过临时文件传递，轮询读取后显示为系统消息

### 5.4 MCP Server 状态检查
- 面板构造 3 秒后延迟检查 MCP Server 端口 (8080) 是否可连
- 避免启动阶段误报 (MCP Server 通过 Slate tick 异步启动)

---

## 六、平台桥接抽象层

### 6.1 接口设计 (`IAgentPlatformBridge`)
Dashboard 通过抽象接口与 AI 平台通信，不依赖具体平台实现:

| 方法 | 用途 |
|------|------|
| `GetPlatformName()` | 平台显示名 |
| `Connect(StatusOutFile)` | 连接平台 |
| `Disconnect()` | 断开连接 |
| `CancelCurrentRequest()` | 取消当前请求 |
| `SendMessageAsync(Message, ResponseFile)` | 异步发消息 |
| `RunDiagnostics(ReportOutFile)` | 运行诊断 |
| `CollectEnvironmentContext(ContextOutFile)` | 收集环境上下文 |
| `QueryStatus()` | 查询状态 |
| `ResetSession()` | 重置会话 |

### 6.2 当前实现 (`FOpenClawPlatformBridge`)
- 通过 `IPythonScriptPlugin::ExecPythonCommand` 调用 Python
- 所有 Python 模块名/函数调用集中在此类，Dashboard 零耦合

### 6.3 文件轮询通信模式
- C++ 发起 Python 异步调用，Python 写入临时文件
- C++ 通过 FTSTicker 定时轮询文件读取结果
- 通信文件: `Saved/UEAgent/_connect_status.txt`, `_openclaw_response.txt`, `_openclaw_response_stream.jsonl`, `_bridge_status.json`, `_diagnose_result.txt`, `_env_context.txt`

---

## 七、本地化系统

### 7.1 运行时中英文切换 (`FUEAgentL10n`)
- 不依赖 UE Localization Dashboard
- 静态 Map 存储中英文文本对
- `Reg(Key, 中文, English)` 注册
- `Get(Key)` / `GetStr(Key)` 获取当前语言文本
- `ToggleLanguage()` 切换中↔英
- 默认语言: 中文

### 7.2 已注册文本分类
- 状态栏: 版本/服务器/连接状态等标签
- 按钮: 连接/断开/诊断/日志/发送/新会话/创建Skill
- 快捷输入: 标题/添加/编辑/删除/保存/取消/确认删除
- 输入框: 占位提示/发送模式标签
- 聊天消息: 发送者标签/欢迎消息/思考中/状态消息
- /status 输出: 格式化模板
- 语言切换: 切换按钮提示

### 7.3 语言切换 UI 刷新
- 按钮文本: 通过 `Text_Lambda` 动态绑定，自动刷新
- 消息列表: 调用 `RebuildMessageList()` 重建
- 快捷输入: 调用 `RebuildQuickInputPanel()` 重建
- 输入框提示: 通过 lambda 绑定自动刷新
- 静态 `.Text()` 文本: 需下次打开面板生效

---

## 八、编辑器子系统 (`UUEAgentSubsystem`)

### 8.1 全局状态管理
- EditorSubsystem 单例，管理连接状态
- 提供 `SetConnectionStatus` / `GetConnectionStatus`
- 双委托广播: `FOnAgentConnectionStatusChanged` (Blueprint) + `FOnAgentConnectionStatusChangedNative` (C++)

### 8.2 活跃面板追踪
- 追踪用户最后操作的面板: Viewport / ContentBrowser
- `USelection::SelectionChangedEvent` → 标记 Viewport
- `ContentBrowser::OnAssetSelectionChanged` → 标记 ContentBrowser
- 供 AI 判断"选中的对象"指的是哪个上下文

### 8.3 日志分类
- `LogUEAgent`: 通用 Agent 日志
- `LogUEAgent_MCP`: MCP 通信日志
- `LogUEAgent_Error`: 错误日志

---

## 九、已实施的优化项

### 9.1 面板合并优化
- **原始**: ChatPanel + Dashboard 分离为两个面板
- **优化后**: 合并为一体化 `SUEAgentDashboard`，ChatPanel 保留代码但不再作为独立入口
- **收益**: 减少 Tab 数量，集中交互入口

### 9.2 状态栏折叠
- **原始**: 状态信息始终展开占据面板空间
- **优化后**: 默认折叠，只显示一行摘要；需要时展开查看详情
- **收益**: 更多空间留给聊天区域

### 9.3 多行输入框
- **原始**: 单行 `SEditableTextBox`
- **优化后**: `SMultiLineEditableTextBox` + 可配置发送模式 (Enter / Ctrl+Enter)
- **收益**: 支持多行输入，灵活切换发送方式

### 9.4 流式显示
- **原始**: 等待完整响应才显示
- **优化后**: JSONL 流式文件轮询，实时显示 thinking + delta 内容
- **收益**: 用户即时看到 AI 思考过程和输出，减少等待焦虑

### 9.5 发送者颜色区分
- **原始**: 所有消息同色
- **优化后**: 5 种角色 5 种颜色 (user/assistant/streaming/thinking/system)
- **收益**: 视觉区分消息来源，流式内容与最终回复有色差

### 9.6 平台桥接抽象
- **原始**: Dashboard 直接拼接 Python 字符串调用
- **优化后**: `IAgentPlatformBridge` 接口 + `FOpenClawPlatformBridge` 实现
- **收益**: Dashboard 零耦合具体平台，新增平台只需实现接口

### 9.7 本地化模块
- **原始**: 硬编码中英文文本散落在各处
- **优化后**: `FUEAgentL10n` 统一注册+运行时切换，按钮通过 lambda 自动刷新
- **收益**: 一键切换语言，新增文本只需一处 Reg

### 9.8 防重发与取消机制
- **原始**: 无防重发保护，取消需手动
- **优化后**: `bIsWaitingForResponse` 防重发 + `/cancel` 双端联动 (C++ 清状态 + Python 释放资源)
- **收益**: 避免请求堆积，取消即时生效

### 9.9 连接状态自动刷新
- **原始**: 需手动 `/status` 检查
- **优化后**: 2 秒轮询 `_bridge_status.json`，断连/重连自动反映到 UI
- **收益**: 状态实时准确，无需用户主动查询

### 9.10 新对话 session 隔离
- **原始**: `/new` 通过 bridge 发送导致 Gateway 关闭 WebSocket
- **优化后**: 先 `ResetSession()` 清除 session key + 重置上下文注入标记，再正常发送
- **收益**: 新对话干净隔离，不丢连接

### 9.11 Slash 命令分色
- **原始**: 命令列表无区分
- **优化后**: 本地命令白色，AI 命令蓝色
- **收益**: 直观区分哪些命令本地执行、哪些转发给 AI

### 9.12 MCP 状态统一到 Bridge 状态文件
- **原始**: 面板构造后 3 秒硬编码延迟 + socket 单次探测 MCP 端口，与 Bridge 状态轮询割裂
- **优化后**: Python 侧将 MCP Server 状态写入 `_bridge_status.json`（新增 `mcp_ready` 字段），C++ 移除独立 socket 探测，统一由 2 秒轮询循环处理
- **收益**: 消灭硬编码延迟和单次探测，状态源统一，实时准确

### 9.13 UTF-8 安全读写
- **原始**: 使用 `FFileHelper::LoadFileToString` 可能出现中文乱码
- **优化后**: `LoadFileToArray` + `FUTF8ToTCHAR` 手动转换
- **收益**: 确保中文/emoji 内容正确显示

### 9.14 环境上下文自动注入
- **原始**: 连接后无上下文
- **优化后**: 连接成功后自动收集环境信息 (UE 版本/项目名/工具前缀等) 发送给 AI
- **收益**: AI 首轮对话即有工作环境上下文

### 9.15 快捷输入 JSON 持久化
- **原始**: 无快捷输入
- **优化后**: 项目级 JSON 配置，支持添加/编辑/删除，弹出模态窗口编辑
- **收益**: 常用操作一键填充，提升效率

---

## 十、DCC 接入开发 Checklist

以下是基于 UE 插件功能清单，下一个 DCC 软件（如 Maya/Max）接入时需要实现的对应项目:

### 必须实现 (P0)
- [ ] **插件入口注册**: 菜单项 / 工具栏按钮 / 面板
- [ ] **可停靠面板**: 对应 DCC 的窗口管理方式 (Qt 的 QDockWidget / Maya Workspaces)
- [ ] **聊天区域**: 消息历史 + 滚动 + 自动滚底
- [ ] **消息模型**: sender/content/timestamp/isCode，500 条上限
- [ ] **发送者颜色区分**: user/assistant/streaming/thinking/system 5 色
- [ ] **多行输入框**: 支持 Enter/Ctrl+Enter 发送模式切换
- [ ] **消息发送**: 通过 bridge_core.py 发送，支持文本转义
- [ ] **流式显示**: 读取 JSONL 流式文件，实时更新 thinking/delta
- [ ] **连接管理**: 连接/断开/状态显示/自动连接
- [ ] **平台桥接**: 对应 DCC 的 bridge_dcc.py (Qt signal/slot 替代文件轮询)
- [ ] **防重发与取消**: 发送锁 + 取消请求联动
- [ ] **错误处理**: 空回复/错误提示/连接失败指引

### 应该实现 (P1)
- [ ] **Slash 命令系统**: / 前缀菜单 + 本地/AI 命令区分
- [ ] **快捷输入**: 可折叠面板 + 添加/编辑/删除 + JSON 持久化
- [ ] **状态栏折叠**: 默认折叠仅显示摘要
- [ ] **诊断功能**: 健康检查 + 连接诊断
- [ ] **新会话**: 清屏 + session 重置 + AI 端重置
- [ ] **环境上下文注入**: 连接成功后自动发送 DCC 环境信息
- [ ] **本地化**: 中英文切换 (可复用 FUEAgentL10n 的文本 Map 思路)

### 可选实现 (P2)
- [ ] **Create Skill 按钮**: 引导用户创建 ArtClaw Skill
- [ ] **语言切换按钮**: UI 界面语言切换
- [ ] **活跃面板追踪**: 追踪用户当前操作的面板/视图 (DCC 特定)
- [ ] **日志分类**: 区分通信日志/错误日志
- [ ] **代码块字体**: 代码内容使用 Mono 字体

### DCC 差异注意项
- UE 用 C++ Slate 构建 UI → DCC 用 Qt (PySide2)
- UE 文件轮询通信 → DCC 用 Qt signal/slot (bridge_dcc.py)
- UE 通过 IPythonScriptPlugin 调用 Python → DCC 直接 Python 环境
- UE EditorSubsystem 单例 → DCC 对应 Qt QObject 单例
- UE FTSTicker 定时器 → Qt QTimer
- UE SWindow 模态窗口 → Qt QDialog

---

## 附录: 源码文件索引

| 文件 | 职责 |
|------|------|
| `UEClawBridge.h/cpp` | 插件模块入口，注册菜单/Tab |
| `UEClawBridgeCommands.h/cpp` | 工具栏命令注册 |
| `UEClawBridgeStyle.h/cpp` | 图标样式 |
| `UEAgentDashboard.h/cpp` | 一体化面板 (主要 UI) |
| `UEAgentChatPanel.h/cpp` | 早期独立聊天面板 (已整合到 Dashboard) |
| `UEAgentSubsystem.h/cpp` | 编辑器子系统 (状态管理+面板追踪) |
| `UEAgentLocalization.h/cpp` | 本地化模块 |
| `IAgentPlatformBridge.h` | 平台通信抽象接口 |
| `OpenClawPlatformBridge.h/cpp` | OpenClaw 平台实现 |
