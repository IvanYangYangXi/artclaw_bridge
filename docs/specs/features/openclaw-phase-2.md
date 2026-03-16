# OpenClaw Phase 2 — 感知增强与原生交互闭环

> **路线图对应**：阶段 2：感知增强与原生交互
> **集成方案对应**：§8 Phase 2

---

## 阶段目标

让 OpenClaw 从"能执行"升级为"有上下文、可确认、有结果反馈"的闭环协作状态。

---

## Feature 清单与实现状态

### `feature/openclaw-in-editor-chat-entry` ✅ 已完成

**需求**：预留 UE 内 OpenClaw 对话入口，明确嵌入式或外部唤起方案。

**实现**：采用**嵌入式方案** — Dashboard 窗口整合 Chat Panel。

| 模块 | 文件 | 说明 |
|------|------|------|
| 合并面板 | `UEAgentDashboard.h/cpp` | 一体化：可折叠状态栏 + 消息历史 + 多行输入 |
| "/" 快捷命令 | `UEAgentDashboard.cpp::InitSlashCommands()` | 输入 `/` 弹出命令菜单（SMenuAnchor + SListView） |
| 模块注册 | `UEEditorAgent.cpp` | 单一 Nomad Tab，工具栏按钮直接打开 |

**Chat Panel 布局**：
```
┌─────────────────────────────────┐
│ ▶ Agent Status  ● Connected     │  ← 可折叠 SExpandableArea
├─────────────────────────────────┤
│ AI Agent  14:21                 │
│   Hello! I'm the UE Agent...   │
│ You  14:22                      │  ← SScrollBox 消息区
│   /select                       │
├─────────────────────────────────┤
│ ┌──────────────────────┐ [Send] │
│ │ Ask AI anything...   │ [Clear]│  ← SMultiLineEditableTextBox
│ └──────────────────────┘        │
│  ┌─────────────────────────┐    │
│  │ /select  Show selected  │    │  ← "/" Slash 命令弹出菜单
│  │ /create  Create actor   │    │
│  └─────────────────────────┘    │
└─────────────────────────────────┘
```

**预设 Slash 命令**：`/select`, `/create`, `/delete`, `/material`, `/camera`, `/level`, `/assets`, `/run`, `/status`, `/clear`, `/help`

**验收**：
- [x] UE 内可看到对话面板
- [x] 面板可停靠/浮动
- [x] 输入 "/" 弹出快捷命令提示
- [x] 多行输入支持
- [ ] 与 OpenClaw Agent 的双向消息转发（阶段 3 实现）

---

### `feature/openclaw-resource-context-sync` ✅ 已完成

**需求**：将 UE 编辑器状态映射为 MCP Resource URI，OpenClaw 可按需读取。

**实现文件**：`Content/Python/tools/context_provider.py`

**已注册的 MCP Resources**：

| URI | 说明 | 返回示例 |
|-----|------|----------|
| `unreal://level/selection` | 当前选中的 Actor 列表 | `[{name, class, location, rotation}]` |
| `unreal://level/actors` | 关卡中所有 Actor（精简版） | `[{name, class, tags}]` |
| `unreal://viewport/camera` | 视口相机位置/朝向 | `{location, rotation, fov}` |
| `unreal://editor/mode` | 当前编辑器模式 | `{mode: "LevelEditor"}` |
| `unreal://level/info` | 关卡基础信息 | `{name, actor_count, world_type}` |

**MCP 协议交互**：
```
OpenClaw → resources/list → 获取 URI 清单
OpenClaw → resources/read {uri: "unreal://level/selection"} → 获取 JSON 数据
```

**数据精简策略**（对应路线图 §2.6）：
- Actor 只返回 `name`, `class`, `transform`, `tags`（不返回原始 UObject 属性）
- 列表默认限制 200 条
- 支持懒加载（按需采样）

**验收**：
- [x] `resources/list` 返回所有 URI
- [x] `resources/read` 返回结构化 JSON
- [x] 数据体积可控，不超过 Token 限制
- [x] 选中物体变更后读取结果实时更新

---

### `feature/openclaw-risk-confirmation` ✅ 已完成

**需求**：高危指令触发 UE 原生确认框，确认结果反馈给 OpenClaw。

**实现文件**：`Content/Python/tools/risk_confirmation.py`

**风险分级规则**：

| 级别 | 触发条件 | 动作 |
|------|----------|------|
| LOW | 读取操作、信息查询 | 直接执行 |
| MEDIUM | 修改单个 Actor 属性 | 直接执行（记录日志） |
| HIGH | 包含 `delete`/`destroy`/`remove` 关键字 | 弹出确认框 |
| HIGH | 修改超过 10 个 Actor | 弹出确认框 |
| CRITICAL | `save_asset` / `save_package` / 磁盘写操作 | 弹出确认框 + 详细说明 |

**确认框实现**：
```python
# 使用 unreal.EditorDialog 原生模态对话框
result = unreal.EditorDialog.show_message(
    title="AI Agent - High Risk Operation",
    message=f"The AI wants to execute:\n{code_summary}\n\nProceed?",
    message_type=unreal.AppMsgType.YES_NO
)
```

**OpenClaw 侧体验**：
- AI 生成删除代码 → `run_ue_python` 检测到高风险
- UE 弹出确认框 → 用户选择 Yes/No
- 结果返回给 OpenClaw：`"User confirmed"` 或 `"User cancelled the operation"`

**验收**：
- [x] `delete` 相关代码触发确认框
- [x] 用户拒绝后代码不执行
- [x] 确认结果回传给 OpenClaw Agent

---

### `feature/openclaw-viewport-feedback` ✅ 已完成

**需求**：执行后自动高亮受影响 Actor，支持自动聚焦目标区域。

**实现文件**：`Content/Python/tools/context_provider.py`

| Tool | 说明 | 状态 |
|------|------|------|
| `focus_on_actor` | 选中 Actor + 计算 bounds 自动调整相机距离 | ✅ |
| `highlight_actors` | 批量选中 + 自动聚焦到群体中心 | ✅ |
| `set_viewport_camera` | 手动设置视口相机位置/旋转 | ✅ |
| `get_viewport_camera` | 获取当前视口相机位置 | ✅ |

**`focus_on_actor` 实现**：
- 按 name 或 label 搜索 Actor
- 使用 `get_actor_bounds()` 计算 bounding box
- 相机放在 Actor 前方，距离 = max(extent) × 2.5
- 自动选中 Actor（视口高亮）

**`highlight_actors` 实现**：
- 批量搜索并选中多个 Actor
- 单个 Actor → 标准偏移聚焦
- 多个 Actor → 计算群体中心点，扩大视距

**验收**：
- [x] AI 修改材质后视口自动聚焦该物体
- [x] 批量操作后受影响的 Actor 被选中/高亮
- [x] 相机距离根据物体大小自适应

---

### `feature/openclaw-editor-mode-filter` ✅ 已完成

**需求**：根据当前编辑器模式调整上下文提示。

**实现文件**：`Content/Python/tools/context_provider.py`

**MCP Tool**：
```json
{
  "name": "get_dynamic_prompt",
  "description": "Get a dynamic system prompt based on the current editor mode and context",
  "inputSchema": {
    "properties": {
      "task_intent": {"type": "string", "description": "Brief description of what the user wants to do"}
    }
  }
}
```

**动态 Prompt 包含**：
- 引擎版本、关卡名称、Actor 数量
- 编辑器模式 + 模式特定 API 推荐
- 当前选中 Actor 摘要（最多 5 个）
- 任务感知提示（根据 intent 关键词注入材质/灯光/删除/布局等专项指导）
- 快捷变量和安全规则提醒

**任务感知示例**：
- intent 包含 "材质" → 提示使用 `MaterialEditingLibrary`
- intent 包含 "灯光" → 提示 PointLight / SpotLight / DirectionalLight
- intent 包含 "删除" → 提示高风险操作会弹确认框

**验收**：
- [x] `unreal://editor/mode` 可读取
- [x] `get_dynamic_prompt` Tool 返回完整动态 Prompt
- [x] Prompt 包含模式特定 API 推荐
- [x] 支持任务意图感知注入

---

### `feature/openclaw-error-self-healing-loop` ✅ 已完成

**需求**：将 Traceback 自动回传为后续上下文，支持失败后修复重试。

**实现文件**：`Content/Python/tools/self_healing.py`

**MCP Tool**：
```json
{
  "name": "analyze_error",
  "description": "Analyze a Python traceback and suggest fixes",
  "inputSchema": {
    "type": "object",
    "properties": {
      "traceback": {"type": "string"},
      "original_code": {"type": "string"},
      "intent": {"type": "string"}
    },
    "required": ["traceback"]
  }
}
```

**自修复链路**：
```
OpenClaw → run_ue_python(code) → 执行失败，返回 Traceback
OpenClaw Agent → 分析 Traceback → 调用 analyze_error 获取修复建议
OpenClaw Agent → 生成修复后的代码 → 再次调用 run_ue_python
```

**分析能力**：
- 识别常见错误模式（AttributeError → API 名称建议）
- 提供 UE Python API 相关的修复提示
- 返回结构化修复建议（问题原因 + 建议方案 + 修复代码模板）

**验收**：
- [x] 执行失败时 Traceback 完整回传
- [x] `analyze_error` 返回结构化修复建议
- [x] OpenClaw Agent 可据此重试

---

## 阶段验收总结

| 验收项 | 状态 |
|--------|------|
| OpenClaw 能主动读取 UE 上下文 | ✅ 5 个 Resource URI |
| 高危操作有确认链路 | ✅ EditorDialog 确认框 |
| 执行结果可在视口中直接感知 | ✅ focus + highlight |
| 编辑器内有对话入口 | ✅ Dashboard 整合 Chat |
| 错误可自修复重试 | ✅ analyze_error Tool |

---

## 当前完成度

| Feature | 状态 |
|---------|------|
| `openclaw-in-editor-chat-entry` | ✅ 已完成 |
| `openclaw-resource-context-sync` | ✅ 已完成 |
| `openclaw-risk-confirmation` | ✅ 已完成 |
| `openclaw-viewport-feedback` | ✅ 已完成 |
| `openclaw-editor-mode-filter` | ✅ 已完成 |
| `openclaw-error-self-healing-loop` | ✅ 已完成 |

**Phase 2 完成度：6/6 features (100%) ✅**

---

## OpenClaw 部署状态

| 项目 | 路径 | 状态 |
|------|------|------|
| Bridge 插件 | `~/.openclaw/extensions/mcp-bridge/` | ✅ 已部署 |
| 插件清单 | `openclaw.plugin.json` | ✅ |
| 插件代码 | `index.ts` | ✅ |
| openclaw.json | `plugins.entries.mcp-bridge` | ✅ 已配置 |
| 服务器名 | `ue-editor-agent` | ✅ ws://127.0.0.1:8080 |

---

## 下一步 (Phase 3)

1. **Chat Panel ↔ OpenClaw 双向消息** — C++ → Python → WebSocket → OpenClaw 的消息转发
2. **Skill 热加载器** — 监控 Skills 目录变更
3. **RAG 知识库** — UE API 文档向量索引
