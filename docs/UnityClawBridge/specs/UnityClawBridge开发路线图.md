# UnityClawBridge 开发路线图

**版本**：1.1.0 | **创建**：2026-04-19 | **更新**：2026-04-19 | **状态**：M1 开发完成

---

## 一、总体原则

### 1.1 ArtClaw SDK/API 统一性约束

UnityClawBridge 必须对齐 ArtClaw 四层 SDK 体系（[SDK 大纲](../../specs/sdk-api-standardization-overview.md)）：

| 层 | 接口 | Unity 落地要求 |
|----|------|---------------|
| **D** DCC 插件接口层 | `BaseDCCAdapter` 13 个抽象方法 | `UnityAdapter` 实现全部方法（M1） |
| **P** 平台适配器层 | `PlatformAdapter` 11 个方法 | Python 端复用，无需新增 |
| **S** Skill SDK 层 | `@artclaw_tool` + manifest.json | Skill 遵循 SKILL.md + manifest.json 规范 |
| **C** 共享核心层 | MemoryManagerV2、skill_sync、VersionManager | Python 端直接 `import`，零修改 |

**不引入任何非标准接口**。新增 C# 能力通过 Skill 扩展，新增 Python 能力通过 core/ 模块。

### 1.2 Chat 功能策略

| 平台 | Chat 集成 | 优先级 |
|------|----------|--------|
| **WorkBuddy** | ❌ 不支持 Gateway 接入，Dashboard Chat 无法对接 | — |
| **OpenClaw** | ✅ 支持 Gateway WebSocket 接入 | **最后开发**（M6） |
| MCP-only (Claude/Cursor) | ✅ 仅工具调用，无 Chat | M4 自动获得 |

**结论**：Dashboard 的 Chat 面板仅对接 OpenClaw Gateway，放在 M6。M1-M5 的 Dashboard 只做状态展示 + 工具调用日志。

### 1.3 UI 技术选型

| 维度 | UE | Unity |
|------|-----|-------|
| UI 框架 | Slate (C++) | **UI Toolkit**（C# UXML/USS）|
| 设计理由 | UE 原生 | Unity 2022+ 官方推荐，响应式、可样式化 |
| IMGUI | 不用 | 仅用于临时调试面板 |
| 数据绑定 | 手动 Tick 轮询 | **UI Toolkit 数据绑定 API** |
| 深色/浅色主题 | 不支持 | ✅ USS 变量跟随编辑器主题 |

---

## 二、里程碑规划

```
M0 骨架 ✅ ─→ M1 基础链路 ✅ ─→ M2 执行引擎 ─→ M3 Skill ─→ M4 平台集成 ─→ M5 Dashboard ─→ M6 Chat
  (已完成)      (2026-04-19)    (1个月)      (2个月)     (3个月)      (1个月)      (1个月)
```

---

## M0 · 项目骨架 ✅

| 交付物 | 状态 |
|--------|------|
| 目录结构 / package.json (v0.2.0) | ✅ |
| C# Bootstrap + CommandServer (v0.2, batch_execute) | ✅ |
| Python bootstrap.py + unity_adapter.py | ✅ |
| Dashboard 基础版 (IMGUI, 状态+启动/停止) | ✅ |
| 设计文档 + 参考项目分析 | ✅ |
| Skill 包 (6 个 SKILL.md) | ✅ |
| Universal Skills 安装到 WorkBuddy | ✅ |

---

## M1 · 基础链路打通 ✅（2026-04-19 完成）

**目标**：AI 通过 `run_unity_python` 执行 C# 代码，Dashboard 显示实时状态和执行日志。

### M1.1 CommandServer Roslyn 执行引擎 ✅

| 任务 | 说明 |
|------|------|
| 集成 `Microsoft.CodeAnalysis.CSharp.Scripting` | C# 代码在编辑器主线程编译执行 |
| 持久命名空间 | 跨调用保持变量（`ScriptOptions.Default.AddReferences`） |
| Undo 支持 | 每次执行前 `Undo.RecordObject`，可 Ctrl+Z |
| 错误信息格式化 | 编译错误 + 运行异常 → 结构化 JSON 返回 |
| 上下文注入 | `Selection`、`ActiveScene`、`AssetDatabase` 等快捷变量 |
| validate_script | Roslyn 语法预验证（执行前检查），参考 CoplayDev |

**Roslyn 依赖**：
```json
// package.json
"dependencies": {
  "com.unity.nuget.newtonsoft-json": "3.2.1",
  "com.microsoft.codeanalysis.csharp.scripting": "4.11.0"
}
```

### M1.2 Python 端完善 ✅

| 任务 | 说明 |
|------|------|
| bootstrap.py 集成共享 mcp_server.py | 从 `core/` 导入，复用 ArtClaw 标准 MCP 实现 |
| unity_adapter.py 完善 `execute_code()` | 返回 C# 执行结果（结构化 JSON）|
| 自动检测 Python 路径 | 已实现（`FindPythonExecutable`），增强错误提示 |

### M1.3 Dashboard 完善 ✅

| 任务 | 说明 |
|------|------|
| 实时连接状态 | Python PID、MCP 端口、CommandServer 端口、Unity 版本 |
| 执行日志面板 | 最近 50 条 AI 执行日志（滚动列表）|
| 错误高亮 | 执行失败红色标记 + 可点击跳转 |

**验收**：
```
AI → run_unity_python("GameObject.Find('Main Camera')") → 返回正确的 GameObject 信息 ✅
AI → Debug.Log("Hello from AI") → Unity Console 显示日志 ✅
Dashboard → 显示连接状态 ✅ + 执行日志 ✅
```

---

## M2 · 执行引擎完善（目标 1 个月）

**目标**：完整的 C# 执行能力 + 安全隔离。

| 任务 | 说明 |
|------|------|
| Roslyn 脚本引擎完整集成 | 支持所有 Unity API（UnityEngine + UnityEditor）|
| 持久命名空间 + 跨调用变量 | `var obj = new GameObject("test"); obj.name` 分两步执行 |
| 超时保护 | 执行超 30 秒自动中断 |
| 安全沙箱 | 禁止 `System.Diagnostics.Process`、`System.IO.File.Delete` 等危险操作 |
| 输出捕获 | `Debug.Log` + `Console.WriteLine` → 结构化 output 字段 |

---

## M3 · P0 核心 Skill 开发（目标 2 个月）

**目标**：42 个 P0 Skill，覆盖 Unity 日常编辑操作。

### 已完成（M0 输出）

| Skill | 覆盖操作 |
|-------|---------|
| `artclaw-unity-context` | 入口路由、环境检查 |
| `unity-scene-ops` | 8 种场景操作 |
| `unity-gameobject-ops` | 10 种 GameObject 操作 |
| `unity-component-ops` | 8 种组件操作 |
| `unity-asset-ops` | 8 种资产操作 |
| `unity-editor-control` | 8 种编辑器控制 |

### M3 新增 Skill

| Skill | 覆盖操作 | 数量 |
|-------|---------|------|
| `unity-material-ops` | 材质创建/属性/Shader/URP/HDRP | 6 |
| `unity-physics-ops` | 物理设置/Layer碰撞/关节/Raycast | 4 |
| `unity-animation-ops` | Animator/AnimationClip/BlendTree | 4 |
| `unity-scripting-ops` | MonoBehaviour创建/模板/编辑/Roslyn验证 | 4 |
| `unity-build-ops` | 构建/平台切换/PlayerSettings | 3 |
| `unity-package-ops` | UPM包安装/卸载/搜索 | 2 |

### Skill 规范约束

所有 Skill 必须符合 ArtClaw Skill SDK 规范：
- SKILL.md YAML frontmatter（name/description/metadata.artclaw.*）
- manifest.json（version/software/category/risk_level）
- C# 代码模板包含 `Undo.RegisterCreatedObjectUndo`
- 使用 `SerializedObject` 修改组件属性
- 描述英文（供 AI 读取），用户 UI 文本中文

---

## M4 · 平台集成（目标 3 个月）

**目标**：接入 ArtClaw SDK 标准化接口，与 OpenClaw/WorkBuddy 联调。

### D 层：DCC 接口对齐

| 任务 | SDK 接口 | 说明 |
|------|---------|------|
| `UnityAdapter` 完整实现 | `BaseDCCAdapter` 13 方法 | 继承 `subprojects/DCCClawBridge/adapters/base_adapter.py` |
| MCP Server 初始化 | D2 标准 | 复用 `core/mcp_server.py` |
| Tool 注册 | `@artclaw_tool` 装饰器 | S 层标准 |
| 工具返回值契约 | D5 | `{success, result, error, output}` |

### C 层：共享核心集成

| 任务 | SDK 接口 | 说明 |
|------|---------|------|
| 记忆系统 | `MemoryManagerV2` | Python 端 `from core.memory_core import MemoryManagerV2` |
| 版本管理 | `VersionManager` | `from core.version_manager import VersionManager` |
| Skill 同步 | `skill_sync.sync_all()` | 自动同步源码 → 运行时 |
| 安装脚本 | `install.py` | 一键安装 UnityClawBridge + 共享 core |

### P 层：平台适配

| 任务 | 说明 |
|------|------|
| OpenClaw 适配器 | Python 端复用 `platforms/openclaw/openclaw_adapter.py` |
| MCP-only 适配 | Claude Desktop / Cursor 通过 MCP 协议自动获得工具调用能力 |

### 事件集成

| 任务 | SDK 接口 | 说明 |
|------|---------|------|
| `DCCEventManager` Unity 适配 | `subprojects/DCCClawBridge/core/dcc_event_manager.py` | 新增 Unity 事件处理器（file.save/scene.new/asset.import 等）|
| Tool Manager 触发器 | `/api/v1/dcc-events` | 文件保存、资产导入等事件转发到 Tool Manager |

---

## M5 · Dashboard 完善（目标 1 个月）

**目标**：功能完整的 Unity Editor Dashboard，对标 UE Dashboard。

### 5.1 UI Toolkit 迁移

| 任务 | 说明 |
|------|------|
| 从 IMGUI 迁移到 UI Toolkit | UXML + USS，响应式布局 |
| 状态栏 | 连接状态、Unity 版本、Python PID、MCP 端口、CommandServer 端口 |
| 执行日志面板 | 滚动列表、过滤（成功/失败/全部）、可点击复制 |
| Skill 管理面板 | 列出已安装 Skill、启用/禁用开关、版本信息 |
| 快捷操作 | 常用 AI 操作按钮（场景信息、选中对象、资产搜索） |

### 5.2 设置面板

| 任务 | 说明 |
|------|------|
| 自动启动开关 | EditorPrefs 持久化（已有） |
| 端口配置 | MCP/CommandServer 端口自定义 |
| Python 路径 | 手动指定 Python 可执行文件路径 |
| 日志级别 | Python 端日志级别调节 |
| 打开日志文件夹 | 一键打开 `~/.artclaw/logs/` |

### 5.3 安全面板

| 任务 | 说明 |
|------|------|
| 风险确认弹窗 | 中/高风险操作弹出确认对话框 |
| 静默模式开关 | 中风险/高风险静默执行（参考 UE Dashboard） |
| 操作历史 | 最近 100 条 AI 操作记录 |

### 5.4 工具管理器集成

| 任务 | 说明 |
|------|------|
| Tool Manager 链接 | 一键打开 ArtClaw Tool Manager Web UI |
| 触发规则查看 | 显示当前 DCC 注册的事件触发规则 |

---

## M6 · Chat 面板（目标 1 个月，最低优先级）

**目标**：Dashboard 内嵌 Chat 面板，仅对接 OpenClaw Gateway。

### 前提条件

- OpenClaw Gateway 可达
- `core/bridge_core.py` 的 `OpenClawBridge` 类已集成

### 6.1 Chat 面板功能

| 任务 | 说明 | 对标 UE |
|------|------|--------|
| 聊天消息列表 | 滚动列表，支持代码块渲染 | `FChatMessage` + `MessageScrollBox` |
| 多行输入框 | 支持 Enter 发送 / Ctrl+Enter 换行 | `InputTextBox` |
| 流式显示 | AI 回复实时流式更新 | `UpdateStreamingMessage` |
| 工具调用展示 | 折叠式工具调用/结果展示 | `AddToolCallMessage` |
| 多会话管理 | 会话列表、切换、删除 | `SessionEntries` + `OnSessionSelected` |
| 快捷输入 | 预设常用提示词 | `QuickInputs` |
| 附件支持 | 粘贴剪贴板图片/文件 | `TryPasteFromClipboard` |
| Agent 切换 | 切换不同 AI Agent | `OnAgentSelected` |
| 平台切换 | OpenClaw / 其他平台 | `OnPlatformSelected` |
| Plan 模式 | 解析 AI 返回的 Plan JSON，展示步骤卡片 | `TryParsePlan` + `ExecuteNextPlanStep` |

### 6.2 OpenClaw Gateway 通信

| 任务 | 说明 |
|------|------|
| WebSocket 连接管理 | 复用 `core/bridge_core.py` 的 `OpenClawBridge` |
| 流事件解析 | `ProcessStreamEventLine` 处理 stream.jsonl |
| 会话持久化 | 本地保存/恢复会话状态 |
| 环境上下文注入 | 连接成功后发送 Unity 环境信息 |

### 6.3 Chat 不可用时的降级

当连接的 AI 平台不支持 Chat（如 WorkBuddy MCP-only）时：
- Chat 面板显示提示："当前平台不支持 Chat，请使用 WorkBuddy 对话窗口"
- 隐藏输入框，只保留日志查看功能

---

## 三、Dashboard 功能模块对比

| 功能模块 | UE Dashboard | Unity Dashboard |
|----------|-------------|-----------------|
| 状态栏 | ✅ Slate | M1 IMGUI → M5 UI Toolkit |
| 执行日志 | ✅ Console 输出 | M1 |
| 聊天面板 | ✅ OpenClaw Bridge | **M6**（最低优先级）|
| 多会话 | ✅ | M6 |
| 流式显示 | ✅ | M6 |
| 工具调用展示 | ✅ 折叠式 | M6 |
| 快捷输入 | ✅ | M6 |
| 附件 | ✅ 剪贴板图片/文件 | M6 |
| Agent 切换 | ✅ | M6 |
| 平台切换 | ✅ | M6 |
| Plan 模式 | ✅ | M6 |
| Skill 管理 | ✅ 启用/禁用 | M5 |
| 设置面板 | ✅ | M5 |
| 安全确认弹窗 | ✅ | M5 |
| 静默模式 | ✅ | M5 |
| 工具管理器 | ✅ | M5 |
| 中英文切换 | ✅ | M5+ |
| 深色/浅色主题 | ❌ | M5 ✅ USS 变量 |

---

## 四、SDK 统一性检查清单

每次提交前自检：

### D 层

- [ ] `UnityAdapter` 继承 `BaseDCCAdapter`
- [ ] 实现 13 个抽象方法（含 `execute_code`）
- [ ] `on_startup()` 注册菜单、`on_shutdown()` 清理资源
- [ ] `execute_on_main_thread()` 通过 `EditorApplication.update` 调度

### S 层

- [ ] 所有 Skill 有 `SKILL.md`（YAML frontmatter）
- [ ] 所有 Skill 有 `manifest.json`（符合 JSON Schema）
- [ ] Skill 命名 `{dcc}{ver}-{name}` 或 `artclaw-*`（通用）
- [ ] 新 Skill 通过 `skill_sync.install_skill()` 安装

### C 层

- [ ] Python 端 `from core.memory_core import MemoryManagerV2`（不自行实现）
- [ ] Python 端 `from core.skill_sync import sync_all`（不自行实现）
- [ ] 共享 core/ 通过 `install.py` 部署，不手动复制

### P 层

- [ ] Python 端复用 `platforms/openclaw/openclaw_adapter.py`
- [ ] Dashboard Chat 复用 `core/bridge_core.py` 的 `OpenClawBridge`
- [ ] 不自行实现 WebSocket 客户端

---

## 五、风险

| 风险 | 级别 | 应对 |
|------|------|------|
| Roslyn 编译延迟 | 中 | 持久命名空间减少重复编译；复杂操作走 Skill 模板 |
| UI Toolkit 学习曲线 | 低 | 先 IMGUI 验证功能，后迁移 UI Toolkit |
| Unity 域重载断连 | 低 | CommandServer 端口保持，Python 进程不中断 |
| Chat 仅支持 OpenClaw | 设计选择 | MCP-only 平台通过外部客户端使用，Dashboard 降级显示 |
| Python 外置进程管理 | 中 | Bootstrap 监控进程退出、自动重启、日志输出 |
