# 右侧面板参数表单交互 - 开发文档

> 版本: 1.0
> 日期: 2026-04-11
> 优先级: P0（Phase 1 核心功能）

---

## 1. 概述

### 1.1 目标

实现右侧面板（RightPanel）的参数表单交互功能，使 Workflow/Tool 的运行流程完整闭环：

```
点击[运行] → 跳转对话面板 → 预填消息 → 用户发送 → 右侧面板显示参数表单 → 填参 → 执行 → 结果显示
```

### 1.2 当前状态

| 组件 | 状态 | 说明 |
|------|------|------|
| ParameterPanel | ✅ 已实现 | 表单渲染、字段类型（string/number/boolean/enum/image）完整 |
| RightPanel | ✅ 已实现 | 支持 executionContext 驱动切换（参数面板 vs 最近使用） |
| ChatStore.prefill | ✅ 已实现 | 预填消息 + 引导卡片 |
| WorkflowCard.handleRun | ✅ 已实现 | 跳转 + setPrefill |
| 执行上下文传递 | ❌ 缺失 | prefill 后无法触发右侧面板显示参数表单 |
| AI 协助填参 | ❌ 缺失 | AI 回复无法更新右侧面板的字段值 |
| 执行提交 | ❌ 缺失 | 点击[执行]后的实际调用逻辑 |
| 进度 + 结果 | ❌ 缺失 | 执行后在消息流中显示进度和结果 |

### 1.3 不依赖 Gateway

当前 Gateway 连接尚未打通，参数表单交互应在**纯前端**可用：
- 参数表单由前端根据 Workflow/Tool 定义直接渲染
- 执行提交暂时走 mock / 本地回显
- Gateway 对接后续独立迭代

---

## 2. 数据流设计

### 2.1 完整流程

```
WorkflowCard / ToolCard
  │  点击[运行]
  ▼
chatStore.setExecutionContext(ctx)  ← 传递完整的执行上下文
navigate('/')
  │
  ▼
ChatPage + RightPanel
  ├── 右侧面板检测到 executionContext → 直接切换到 ParameterPanel
  │     ├── 渲染表单字段（自动填充默认值）
  │     ├── 用户手动编辑 → paramValues 更新
  │     ├── 点击[执行] → chatStore.executeWorkflowOrTool()
  │     └── 点击[取消] → chatStore.clearExecutionContext()
  │
  └── 对话输入框保持正常状态
        └── 用户可通过对话请求 AI 协助（"帮我把步数改成 30"）
            → AI 回复中更新参数（未来功能）
```

**关键设计决策**：
- **不使用 prefill/引导卡片**：运行跳转后右侧面板直接显示参数表单，不需要用户先"发送"消息
- **对话与参数表单独立**：左侧对话区正常使用，右侧参数面板独立操作
- **AI 协助是增强而非必须**：用户可以纯手动填参+执行，不依赖 AI

### 2.2 ChatStore 新增字段

```typescript
interface ChatState {
  // ... 现有字段 ...

  // 执行上下文（驱动右侧面板显示参数表单）
  executionContext: ExecutionContext | null

  // Actions
  setExecutionContext: (ctx: ExecutionContext) => void
  clearExecutionContext: () => void
  updateParamValues: (values: Record<string, unknown>) => void
  executeWorkflowOrTool: () => void
}
```

### 2.3 ExecutionContext 扩展

```typescript
// types/index.ts 中已有 ExecutionContext，需扩展：
interface ExecutionContext {
  type: 'workflow' | 'tool'        // 新增：区分类型
  id: string                       // workflow/tool id
  name: string                     // 显示名称
  parameters: WorkflowParameter[]  // 参数定义
  values: Record<string, unknown>  // 当前参数值（含默认值）
  presetId?: string                // 使用的预设 id（可选）
}
```

---

## 3. 实现任务

### 3.1 ChatStore 扩展

**文件**: `src/web/src/stores/chatStore.ts`

新增：
- `executionContext` 状态字段
- `setExecutionContext(ctx)` — 设置执行上下文，驱动右侧面板
- `clearExecutionContext()` — 清除执行上下文，右侧面板回到最近使用
- `updateParamValues(values)` — 更新参数值（AI 填参时调用）
- `executeWorkflowOrTool()` — 提交执行（读取 executionContext + 当前 values）

### 3.2 WorkflowCard / ToolCard 改造

**变更**: 点击[运行]时，除了 setPrefill，还要 setExecutionContext。

**WorkflowCard**:
```typescript
const handleRun = () => {
  const { setPrefill, setExecutionContext } = useChatStore.getState()
  setPrefill(
    `我想运行 Workflow "${workflow.name}"，请帮我填写参数`,
    `即将运行 Workflow "${workflow.name}"，点击发送开始`,
  )
  // 需要获取 workflow 的参数定义
  // 如果 workflow 已有 parameters（从 API 加载），直接使用
  // 否则设置空参数列表
  setExecutionContext({
    type: 'workflow',
    id: workflow.id,
    name: workflow.name,
    parameters: workflow.parameters ?? [],
    values: buildDefaultValues(workflow.parameters ?? []),
  })
  navigate('/')
}
```

**ToolCard**: 类似逻辑，从 tool.manifest?.inputs 构建。

### 3.3 ChatPage 传递 executionContext

**文件**: `src/web/src/pages/Chat/index.tsx`

ChatPage 需要读取 `executionContext` 并传给 Layout 的 RightPanel：

```typescript
const executionContext = useChatStore((s) => s.executionContext)
// 传递给父 Layout 或直接渲染 RightPanel
```

### 3.4 RightPanel 响应 executionContext

**文件**: `src/web/src/components/Layout/RightPanel.tsx`

当前 RightPanel 已支持 `executionContext` prop，需要：
- 从 chatStore 读取 executionContext（而不是从 props）
- paramValues 状态改为从 executionContext.values 初始化
- onSubmit 调用 chatStore.executeWorkflowOrTool()
- onReset 重置为 executionContext.values 的默认值

### 3.5 Layout 整合

**文件**: `src/web/src/components/Layout/Layout.tsx`

确保 RightPanel 在对话页面可见，且能响应 chatStore 中的 executionContext。

### 3.6 执行与结果（Mock）

执行提交后：
1. 在消息流中添加系统消息："⚙️ 开始执行 {name}..."
2. 模拟进度（1-2 秒延迟）
3. 添加结果消息："✅ 执行完成！" 或 "❌ 执行失败: {error}"
4. 清除 executionContext（右侧面板回到最近使用）

Gateway 连接后替换为真实调用。

---

## 4. Mock 数据

Workflow 和 Tool 的 mock 数据需要包含参数定义，以便测试参数表单。

### 4.1 Workflow Mock 参数

```typescript
// workflowsStore.ts 的 mock 数据中补充 parameters
{
  id: 'official/sdxl-portrait',
  name: 'SDXL 肖像摄影',
  parameters: [
    { id: 'prompt', name: '提示词', type: 'string', required: true, multiline: true, placeholder: '描述你想生成的肖像...' },
    { id: 'negative', name: '反向提示词', type: 'string', required: false, multiline: true, default: 'blurry, low quality' },
    { id: 'width', name: '宽度', type: 'number', required: false, default: 1024, min: 512, max: 2048, step: 64 },
    { id: 'height', name: '高度', type: 'number', required: false, default: 1024, min: 512, max: 2048, step: 64 },
    { id: 'steps', name: '采样步数', type: 'number', required: false, default: 20, min: 1, max: 50 },
    { id: 'sampler', name: '采样器', type: 'enum', required: false, default: 'euler_ancestral', options: ['euler', 'euler_ancestral', 'dpmpp_2m', 'dpmpp_sde'] },
    { id: 'hires_fix', name: '高清修复', type: 'boolean', required: false, default: false },
    { id: 'reference_image', name: '参考图', type: 'image', required: false },
  ],
}
```

### 4.2 Tool Mock 参数

```typescript
{
  id: 'user/batch-rename',
  name: '批量重命名',
  manifest: {
    inputs: [
      { id: 'prefix', name: '前缀', type: 'string', required: true, default: 'SM_' },
      { id: 'use_numbering', name: '使用编号', type: 'boolean', required: false, default: true },
      { id: 'start_number', name: '起始编号', type: 'number', required: false, default: 1, min: 0, max: 9999 },
    ],
  },
}
```

---

## 5. 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `stores/chatStore.ts` | 修改 | 新增 executionContext 相关状态和 actions |
| `types/index.ts` | 修改 | ExecutionContext 扩展 type 字段 |
| `components/Layout/RightPanel.tsx` | 修改 | 从 chatStore 读取 executionContext |
| `components/Layout/Layout.tsx` | 修改 | 移除 RightPanel 的 executionContext prop 透传 |
| `components/Workflows/WorkflowCard.tsx` | 修改 | handleRun 补充 setExecutionContext |
| `components/Tools/ToolCard.tsx` | 修改 | handleRun 补充 setExecutionContext |
| `stores/workflowsStore.ts` | 修改 | mock 数据补充 parameters |
| `stores/toolsStore.ts` | 修改 | mock 数据补充 manifest.inputs |
| `components/Chat/ParameterPanel.tsx` | 修改 | onSubmit/onCancel 对接 chatStore |
| `pages/Chat/index.tsx` | 修改 | 执行结果消息显示 |

---

## 6. Agent 交互协议

### 6.1 执行时发给 Agent 的消息

点击[执行]后，前端构造结构化消息通过 WebSocket → 后端 → Gateway 发给 Agent：

```
请执行Workflow "SDXL 肖像摄影"

参数:
```json
{"prompt": "a cat", "steps": 20, "hires_fix": false}
```

参数定义:
```json
[{"id":"prompt","name":"提示词","type":"string","required":true}, ...]
```
```

Agent 收到后就知道要运行哪个 Workflow/Tool 及用户填的参数。

### 6.2 对话时自动附带参数上下文

当右侧面板有 executionContext 时，用户在对话框发的每条消息都会自动附带：
- 当前正在配置的 Workflow/Tool 名称
- 参数定义（schema）
- 当前参数值

这样 Agent 能理解上下文，比如用户说"把步数改成 30"，Agent 知道是指 `steps` 参数。

### 6.3 Agent 回填参数（参数指令标记）

Agent 回复中如果包含以下格式的标记，前端会自动解析并更新右侧面板的参数值：

```
<!--artclaw:params {"steps": 30, "prompt": "a beautiful cat"}-->
```

**流程**：
1. 用户说"帮我填写参数，我想生成一只猫"
2. Agent 回复："好的，我帮你设置好了参数：提示词设为猫的描述，步数 25 步。\n\n<!--artclaw:params {\"prompt\": \"a beautiful cat, high quality\", \"steps\": 25}-->"
3. 前端解析到标记 → 调用 updateParamValues → 右侧面板参数自动更新
4. 用户确认后点[执行]

### 6.4 Gateway 未连接时的 fallback

- 点[执行] → 前端 mock 回显（1 秒延迟，模拟结果）
- 对话发送 → 本地 echo 回显

---

## 7. 验收标准

1. **参数表单显示**: 点击 Workflow/Tool 的[运行] → 跳转对话面板 → 右侧面板显示参数表单
2. **字段渲染正确**: string(单行/多行)、number(数字框+滑块)、boolean(开关)、enum(下拉)、image(上传区) 均正常渲染
3. **默认值填充**: 表单字段自动填充默认值
4. **手动编辑**: 用户可以修改任意字段值
5. **执行提交**: 点击[执行] → 消息流显示执行消息 → 右侧面板回到最近使用
6. **取消/重置**: 点击[取消]回到最近使用，点击[重置]恢复默认值
7. **引导卡片**: 跳转后消息区显示引导卡片，输入框预填消息
