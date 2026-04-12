# Phase 3: Workflow 库详细开发文档

> **项目**: ArtClaw Tool Manager  
> **阶段**: Phase 3 - Workflow 库（ComfyUI）  
> **版本**: 1.0  
> **日期**: 2026-04-10  
> **工期**: 1周（5个工作日）

---

## 目录

1. [概述](#1-概述)
2. [开发任务分解（到天）](#2-开发任务分解到天)
3. [AI 协助执行流程设计](#3-ai-协助执行流程设计)
4. [右侧面板参数表单交互逻辑](#4-右侧面板参数表单交互逻辑)
5. [ComfyUI 集成细节](#5-comfyui-集成细节)
6. [进度更新机制](#6-进度更新机制)
7. [错误处理方案](#7-错误处理方案)
8. [代码示例](#8-代码示例)
9. [API 接口定义](#9-api-接口定义)
10. [数据模型](#10-数据模型)

---

## 1. 概述

### 1.1 目标

Phase 3 实现 **ComfyUI Workflow 库** 的完整功能，核心亮点是 **AI 协助执行流程**：

- Workflow 浏览、安装、收藏管理
- **点击运行 → 跳转对话面板 → AI 协助填参 → 运行**
- 右侧面板动态参数表单
- ComfyUI HTTP API / WebSocket 集成
- 实时进度推送与运行结果展示

### 1.2 核心设计原则

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI 协助执行模式                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  传统模式: 用户手动填写所有参数 → 容易出错、体验差                │
│                                                                  │
│  AI 协助模式:                                                    │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐       │
│  │ 用户意图 │ → │ AI 理解 │ → │ 自动填参 │ → │ 用户确认 │       │
│  │ "生成肖像"│    │ 解析需求 │    │ 智能推荐 │    │ 一键运行 │       │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘       │
│                                                                  │
│  优势: 减少用户操作、降低学习成本、提高成功率                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 与整体架构的关系

```
ArtClaw Tool Manager
│
├── Phase 1: 基础框架 + 对话面板 ✅
├── Phase 2: Skill 管理 ✅
├── Phase 3: Workflow 库（本阶段）← 依赖 Phase 1 的对话面板
├── Phase 4: 工具管理器
└── Phase 5: DCC 集成
```

---

## 2. 开发任务分解（到天）

### Day 1: Workflow 数据层与基础接口

| 任务 | 描述 | 验收标准 |
|------|------|----------|
| 2.1.1 | 设计 Workflow 数据模型 | `Workflow`, `WorkflowParameter` 接口定义完成 |
| 2.1.2 | 实现 Workflow Store 服务 | CRUD 操作可用，支持本地文件读写 |
| 2.1.3 | 实现 Workflow API 路由 | `/api/workflows/*` 基础接口可用 |
| 2.1.4 | 集成 ComfyUI Client | HTTP API 封装完成，可查询模型列表 |

**交付物**:
- `src/server/models/workflow.py`
- `src/server/services/workflow_store.py`
- `src/server/api/workflows.py`
- `src/server/services/comfyui_client.py`

### Day 2: Workflow 管理界面

| 任务 | 描述 | 验收标准 |
|------|------|----------|
| 2.2.1 | Workflow 列表页面 | 网格/列表视图切换，预览图展示 |
| 2.2.2 | 标签切换（全部/官方/市集/我的） | 可切换不同来源的 Workflow |
| 2.2.3 | Workflow 卡片组件 | 显示预览图、名称、评分、操作按钮 |
| 2.2.4 | 搜索和筛选功能 | 支持关键词搜索、分类筛选 |

**交付物**:
- `src/web/pages/Workflows/WorkflowList.tsx`
- `src/web/components/WorkflowCard.tsx`
- `src/web/stores/workflowStore.ts`

### Day 3: AI 协助执行流程（核心）

| 任务 | 描述 | 验收标准 |
|------|------|----------|
| 2.3.1 | 运行按钮跳转逻辑 | 点击 [运行] 跳转对话面板，自动发送消息 |
| 2.3.2 | AI 意图识别 | AI 识别 `/run workflow:{id}` 命令 |
| 2.3.3 | 右侧面板参数表单框架 | 动态表单渲染基础架构 |
| 2.3.4 | 参数表单组件（基础类型） | string/number/boolean/enum 输入组件 |

**交付物**:
- `src/web/components/ParameterForm/`
- `src/web/stores/executionStore.ts`
- 消息解析逻辑更新

### Day 4: ComfyUI 集成与执行

| 任务 | 描述 | 验收标准 |
|------|------|----------|
| 2.4.1 | ComfyUI HTTP API 提交 | 可提交 workflow JSON 到 ComfyUI |
| 2.4.2 | WebSocket 连接管理 | 建立 WebSocket 连接，监听事件 |
| 2.4.3 | 进度更新解析 | 解析 ComfyUI 进度事件 |
| 2.4.4 | 运行结果处理 | 获取输出图片路径，生成预览 |

**交付物**:
- `src/server/services/comfyui_websocket.py`
- `src/server/services/workflow_executor.py`
- `src/web/components/ExecutionProgress.tsx`

### Day 5: 完善与测试

| 任务 | 描述 | 验收标准 |
|------|------|----------|
| 2.5.1 | 图片上传组件 | 支持选择/拖拽上传参考图 |
| 2.5.2 | 错误处理完善 | 各类错误场景处理 |
| 2.5.3 | 执行历史记录 | 保存执行记录，可查看历史 |
| 2.5.4 | 端到端测试 | 完整流程测试通过 |

**交付物**:
- `src/web/components/ImageUploader.tsx`
- `src/server/services/execution_history.py`
- 测试报告

---

## 3. AI 协助执行流程设计

### 3.1 整体流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AI 协助执行流程                                      │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐
  │  Workflow    │
  │   库页面     │
  └──────┬───────┘
         │ 1. 点击 [运行]
         ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                         阶段一: 跳转与初始化                              │
  │                                                                          │
  │  2. 自动跳转对话面板                                                       │
  │  3. 自动发送消息: "/run workflow:official/sdxl-portrait"                  │
  │  4. 或显示为: "我想运行 Workflow 'SDXL 肖像摄影'，请帮我填写参数"          │
  │                                                                          │
  └─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                         阶段二: AI 解析与响应                             │
  │                                                                          │
  │  5. AI 解析意图: 执行 Workflow 请求                                        │
  │  6. AI 读取 Workflow 定义，获取参数列表                                     │
  │  7. AI 回复用户，询问参数或提供建议                                        │
  │                                                                          │
  │     AI: "好的，我来帮你运行 SDXL 肖像摄影。请填写以下参数："               │
  │         "1. 提示词：你想生成什么样的肖像？"                                 │
  │         "2. 宽度/高度：默认 1024x1024"                                     │
  │                                                                          │
  └─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                         阶段三: 右侧面板参数表单                           │
  │                                                                          │
  │  8. 右侧面板显示动态参数表单                                                │
  │  ┌─────────────────────────────────────┐                                  │
  │  │ 运行: SDXL 肖像摄影                  │                                  │
  │  │ ─────────────────────────────────── │                                  │
  │  │                                     │                                  │
  │  │ 提示词 *                            │                                  │
  │  │ ┌─────────────────────────────────┐ │                                  │
  │  │ │ a beautiful portrait...         │ │  ← 用户可手动修改                 │
  │  │ └─────────────────────────────────┘ │                                  │
  │  │                                     │                                  │
  │  │ 宽度              [====●========] 1024                               │
  │  │ 高度              [====●========] 1024                               │
  │  │ 高清修复          ☑ 已启用                                           │
  │  │                                     │                                  │
  │  │ [运行] [取消]                       │                                  │
  │  │                                     │                                  │
  │  │ 💡 你可以说"帮我填写参数"让 AI 协助  │                                  │
  │  └─────────────────────────────────────┘                                  │
  │                                                                          │
  └─────────────────────────────────────────────────────────────────────────┘
         │
         │ 用户操作分支
         ├─── 手动填写参数 ──→ 点击 [运行]
         │
         └─── 请求 AI 协助 ──→ 对话交互
                    │
                    ▼
         ┌────────────────────┐
         │ 用户: "帮我填写参数" │
         │ 或: "生成商务风格女性肖像" │
         └────────┬───────────┘
                  │
                  ▼
         ┌─────────────────────────────────────────────────────────────────┐
         │ AI: "明白了，我来帮你填写参数："                                   │
         │     "• 提示词: 'business style female portrait, professional...'" │
         │     "• 宽度: 1024, 高度: 1024"                                     │
         │     "• 高清修复: 已开启"                                           │
         │                                                                   │
         │     "请确认右侧面板的参数，然后点击 [运行]"                         │
         └─────────────────────────────────────────────────────────────────┘
                  │
                  ▼
         ┌─────────────────────────────────────────────────────────────────┐
         │                    阶段四: 执行与进度                              │
         │                                                                   │
         │  9. 用户点击 [运行] 或说"开始运行"                                 │
         │ 10. 前端收集参数，发送到后端                                         │
         │ 11. 后端构建完整 workflow JSON                                      │
         │ 12. 提交到 ComfyUI HTTP API                                         │
         │ 13. WebSocket 监听进度                                              │
         │                                                                   │
         └─────────────────────────────────────────────────────────────────┘
                  │
                  ▼
         ┌─────────────────────────────────────────────────────────────────┐
         │                    阶段五: 结果展示                                │
         │                                                                   │
         │  14. 运行进度在消息流中显示（实时更新）                              │
         │  15. 运行完成，显示结果图片                                         │
         │  16. AI 总结运行结果                                                │
         │                                                                   │
         │  ┌─────────────────────────────────────────────────────────────┐  │
         │  │ 🤖 AI                                            10:25      │  │
         │  │                                                             │  │
         │  │ 开始运行 SDXL 肖像摄影 Workflow...                           │  │
         │  │                                                             │  │
         │  │ ┌─────────────────────────────────────────────────────────┐ │  │
         │  │ │ [████████████████████░░░░░░░░░░] 65%                   │ │  │
         │  │ │ 状态: 采样中 (step 13/20)                               │ │  │
         │  │ │ 预计剩余: 15秒                                          │ │  │
         │  │ └─────────────────────────────────────────────────────────┘ │  │
         │  │                                                             │  │
         │  │ [IMAGE: output_0001.png]                                    │  │
         │  │                                                             │  │
         │  │ 运行完成！生成了 1 张图片。                                   │  │
         │  │                                                             │  │
         │  │ [保存] [分享] [再生成一张]                                   │  │
         │  └─────────────────────────────────────────────────────────────┘  │
         │                                                                   │
         └─────────────────────────────────────────────────────────────────┘
```

### 3.2 状态机设计

```typescript
// 执行状态机
enum ExecutionState {
  IDLE = 'idle',           // 空闲状态
  PREPARING = 'preparing', // 准备中（AI 协助填参）
  READY = 'ready',         // 参数已确认，等待执行
  SUBMITTING = 'submitting', // 提交到 ComfyUI
  QUEUED = 'queued',       // 已在 ComfyUI 队列中
  RUNNING = 'running',     // 正在执行
  COMPLETED = 'completed', // 执行完成
  FAILED = 'failed',       // 执行失败
  CANCELLED = 'cancelled', // 用户取消
}

interface ExecutionContext {
  state: ExecutionState;
  workflowId: string;
  workflowName: string;
  parameters: Record<string, any>;  // 当前参数值
  executionId?: string;              // ComfyUI prompt_id
  progress?: ExecutionProgress;
  result?: ExecutionResult;
  error?: ExecutionError;
}
```

### 3.3 消息协议

```typescript
// 前端 → 后端: 开始执行
interface StartExecutionRequest {
  workflowId: string;
  parameters: Record<string, any>;
  options?: {
    priority?: number;
    callbackUrl?: string;
  };
}

// 后端 → 前端: 执行状态更新
interface ExecutionStatusMessage {
  type: 'execution_status';
  executionId: string;
  state: ExecutionState;
  progress?: {
    percent: number;
    currentStep: number;
    totalSteps: number;
    currentNode?: string;
    eta?: number;  // 预计剩余时间（秒）
  };
  result?: {
    images: string[];  // 输出图片路径列表
    metadata?: any;
  };
  error?: {
    code: string;
    message: string;
    details?: any;
  };
  timestamp: number;
}
```

---

## 4. 右侧面板参数表单交互逻辑

### 4.1 表单动态生成流程

```
┌─────────────────────────────────────────────────────────────────┐
│                  参数表单动态生成流程                            │
└─────────────────────────────────────────────────────────────────┘

Workflow 定义
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 解析参数列表                                                     │
│                                                                 │
│ parameters: [                                                   │
│   { id: 'prompt', type: 'string', required: true, ... },       │
│   { id: 'width', type: 'number', min: 512, max: 2048, ... },   │
│   { id: 'enable_hires', type: 'boolean', default: false },     │
│   { id: 'sampler', type: 'enum', options: ['euler', 'dpm'] },  │
│   { id: 'reference_image', type: 'image' },                    │
│ ]                                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 按参数类型映射到组件                                              │
│                                                                 │
│ 参数类型 ────────▶ 组件                                          │
│ ─────────────────────────────────────────────────────────────── │
│ string          ──▶ TextInput (多行文本)                        │
│ number          ──▶ NumberInput / Slider                        │
│ boolean         ──▶ Checkbox / Toggle                           │
│ enum            ──▶ Select / RadioGroup                         │
│ image           ──▶ ImageUploader                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 生成表单布局                                                     │
│                                                                 │
│ 分组策略:                                                        │
│ - 按参数分组（如"基础参数"、"高级参数"）                         │
│ - 必填参数优先显示                                               │
│ - 相关参数相邻排列                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 渲染到右侧面板                                                   │
│                                                                 │
│ 表单状态管理:                                                    │
│ - 使用 React Hook Form 或 Zustand                               │
│ - 实时验证（required, min, max, pattern）                        │
│ - 参数联动（如 enable_hires 控制 hires_steps 显示）               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 参数组件详细设计

#### 4.2.1 StringInput（文本输入）

```typescript
interface StringParameter {
  id: string;
  name: string;
  type: 'string';
  required: boolean;
  default?: string;
  multiline?: boolean;      // 是否多行（提示词用）
  maxLength?: number;
  placeholder?: string;
  description?: string;
}

// 组件特性
// - 多行模式：自适应高度，最大 200px
// - 支持提示词高亮（括号权重显示）
// - 支持常用提示词快捷插入
```

#### 4.2.2 NumberInput（数值输入）

```typescript
interface NumberParameter {
  id: string;
  name: string;
  type: 'number';
  required: boolean;
  default?: number;
  min?: number;
  max?: number;
  step?: number;
  slider?: boolean;         // 是否显示滑块
  display?: 'number' | 'slider' | 'both';
}

// 组件特性
// - 数字输入框 + 滑块双模式
// - 滑块实时预览数值
// - 支持步进按钮（+/-）
```

#### 4.2.3 BooleanInput（布尔输入）

```typescript
interface BooleanParameter {
  id: string;
  name: string;
  type: 'boolean';
  required: boolean;
  default?: boolean;
}

// 组件特性
// - Toggle Switch 样式
// - 可控制其他参数的显示/隐藏（条件渲染）
```

#### 4.2.4 EnumInput（枚举输入）

```typescript
interface EnumParameter {
  id: string;
  name: string;
  type: 'enum';
  required: boolean;
  options: string[];
  default?: string;
  display?: 'select' | 'radio' | 'button-group';
}

// 组件特性
// - 选项少（<5）用 Radio/Button Group
// - 选项多用 Select Dropdown
// - 支持搜索过滤
```

#### 4.2.5 ImageInput（图片输入）

```typescript
interface ImageParameter {
  id: string;
  name: string;
  type: 'image';
  required: boolean;
  accept?: string[];        // 允许的文件类型
  maxSize?: number;         // 最大文件大小（MB）
}

// 组件特性
// - 支持点击选择文件
// - 支持拖拽上传
// - 图片预览
// - 支持从 URL 加载
```

### 4.3 表单交互状态

```typescript
// 表单状态
interface FormState {
  values: Record<string, any>;        // 当前值
  errors: Record<string, string>;     // 验证错误
  touched: Record<string, boolean>;   // 是否已交互
  isValid: boolean;                   // 整体是否有效
  isDirty: boolean;                   // 是否有修改
}

// 表单操作
interface FormActions {
  setValue: (id: string, value: any) => void;
  setValues: (values: Record<string, any>) => void;
  validate: () => boolean;
  reset: () => void;
  submit: () => void;
}

// 与 AI 协作的表单操作
interface AIAssistedForm extends FormState, FormActions {
  // AI 填充参数
  applyAIValues: (values: Record<string, any>) => void;
  // 获取当前参数（用于 AI 分析）
  getValuesForAI: () => string;
  // 高亮需要用户确认的参数
  highlightUncertainParams: (paramIds: string[]) => void;
}
```

### 4.4 参数联动逻辑

```typescript
// 示例：高清修复参数联动
const conditionalFields: ConditionalField[] = [
  {
    when: { field: 'enable_hires', equals: true },
    show: ['hires_steps', 'hires_denoising', 'hires_upscaler'],
  },
  {
    when: { field: 'sampler', equals: 'dpmpp_2m' },
    set: { field: 'scheduler', value: 'karras' },
  },
];

// 实现方式
// 1. 监听表单值变化
// 2. 检查条件规则
// 3. 更新字段显示状态或值
```

---

## 5. ComfyUI 集成细节

### 5.1 架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ComfyUI 集成架构                                     │
└─────────────────────────────────────────────────────────────────────────────┘

  ArtClaw Tool Manager                    ComfyUI Server
  ┌─────────────────────┐                 ┌─────────────────────┐
  │   Web Frontend      │                 │   ComfyUI Web UI    │
  │  (React + WS Client)│◄───────────────►│   (localhost:8188)  │
  └──────────┬──────────┘    HTTP/WS      └─────────────────────┘
             │
             ▼
  ┌─────────────────────┐
  │   FastAPI Backend   │
  │  ┌───────────────┐  │
  │  │ Workflow API  │  │
  │  │  - list       │  │
  │  │  - execute    │  │
  │  │  - status     │  │
  │  └───────┬───────┘  │
  │          │          │
  │  ┌───────▼───────┐  │
  │  │ ComfyUIClient │  │◄───────────────►  ComfyUI HTTP API
  │  │  - submit()   │  │      (localhost:8188)
  │  │  - queue()    │  │
  │  │  - history()  │  │
  │  └───────┬───────┘  │
  │          │          │
  │  ┌───────▼────────┐ │
  │  │ ComfyUIWebSocket│ │◄───────────────►  ComfyUI WS
  │  │  - connect()   │ │      (localhost:8188/ws)
  │  │  - onProgress()│ │
  │  │  - onComplete()│ │
  │  └────────────────┘ │
  └─────────────────────┘
```

### 5.2 HTTP API 封装

```python
# src/server/services/comfyui_client.py

import aiohttp
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class ComfyUIConfig:
    host: str = "127.0.0.1"
    port: int = 8188
    
    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.port}/ws"

class ComfyUIClient:
    """ComfyUI HTTP API 客户端"""
    
    def __init__(self, config: ComfyUIConfig = None):
        self.config = config or ComfyUIConfig()
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    # ─── 系统信息 ───
    
    async def get_system_info(self) -> Dict[str, Any]:
        """获取 ComfyUI 系统信息"""
        async with self.session.get(f"{self.config.base_url}/system_stats") as resp:
            return await resp.json()
    
    async def get_object_info(self, node_type: str = None) -> Dict[str, Any]:
        """获取节点类型信息"""
        url = f"{self.config.base_url}/object_info"
        if node_type:
            url += f"/{node_type}"
        async with self.session.get(url) as resp:
            return await resp.json()
    
    # ─── 模型管理 ───
    
    async def get_model_list(self, folder: str) -> List[str]:
        """获取模型列表
        folder: checkpoints, loras, vae, controlnet, etc.
        """
        async with self.session.get(
            f"{self.config.base_url}/models/{folder}"
        ) as resp:
            return await resp.json()
    
    async def get_checkpoints(self) -> List[str]:
        return await self.get_model_list("checkpoints")
    
    async def get_loras(self) -> List[str]:
        return await self.get_model_list("loras")
    
    # ─── 队列管理 ───
    
    async def get_queue(self) -> Dict[str, Any]:
        """获取当前队列状态"""
        async with self.session.get(f"{self.config.base_url}/queue") as resp:
            return await resp.json()
    
    async def clear_queue(self) -> bool:
        """清空队列"""
        async with self.session.post(f"{self.config.base_url}/queue") as resp:
            return resp.status == 200
    
    async def cancel_current(self) -> bool:
        """取消当前任务"""
        async with self.session.post(
            f"{self.config.base_url}/interrupt"
        ) as resp:
            return resp.status == 200
    
    # ─── Workflow 执行 ───
    
    async def submit_workflow(
        self, 
        workflow: Dict[str, Any],
        extra_data: Dict[str, Any] = None
    ) -> str:
        """提交 workflow 执行
        
        Returns:
            prompt_id: 任务ID，用于追踪进度
        """
        data = {
            "prompt": workflow,
        }
        if extra_data:
            data["extra_data"] = extra_data
            
        async with self.session.post(
            f"{self.config.base_url}/prompt",
            json=data
        ) as resp:
            result = await resp.json()
            if "prompt_id" in result:
                return result["prompt_id"]
            raise ComfyUIError(result.get("error", "Unknown error"))
    
    # ─── 结果获取 ───
    
    async def get_history(self, prompt_id: str = None) -> Dict[str, Any]:
        """获取执行历史"""
        url = f"{self.config.base_url}/history"
        if prompt_id:
            url += f"/{prompt_id}"
        async with self.session.get(url) as resp:
            return await resp.json()
    
    async def get_image(
        self, 
        filename: str, 
        subfolder: str = "", 
        folder_type: str = "output"
    ) -> bytes:
        """获取生成的图片"""
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type,
        }
        async with self.session.get(
            f"{self.config.base_url}/view",
            params=params
        ) as resp:
            return await resp.read()
    
    # ─── 文件上传 ───
    
    async def upload_image(
        self,
        image_data: bytes,
        filename: str,
        folder: str = "input"
    ) -> Dict[str, str]:
        """上传图片"""
        data = aiohttp.FormData()
        data.add_field("image", image_data, filename=filename)
        data.add_field("type", folder)
        
        async with self.session.post(
            f"{self.config.base_url}/upload/image",
            data=data
        ) as resp:
            return await resp.json()


class ComfyUIError(Exception):
    """ComfyUI API 错误"""
    pass
```

### 5.3 WebSocket 实时进度

```python
# src/server/services/comfyui_websocket.py

import asyncio
import json
import websockets
from typing import Callable, Optional
from dataclasses import dataclass
from enum import Enum

class ComfyUIMessageType(Enum):
    STATUS = "status"
    PROGRESS = "progress"
    EXECUTING = "executing"
    EXECUTION_CACHED = "execution_cached"
    EXECUTION_ERROR = "execution_error"
    EXECUTION_INTERRUPTED = "execution_interrupted"
    COMPLETED = "completed"

@dataclass
class ComfyUIProgress:
    value: int          # 当前进度值
    max: int            # 最大值
    percent: float      # 百分比

@dataclass
class ComfyUIMessage:
    type: ComfyUIMessageType
    data: dict
    prompt_id: Optional[str] = None

class ComfyUIWebSocket:
    """ComfyUI WebSocket 客户端"""
    
    def __init__(self, ws_url: str = "ws://127.0.0.1:8188/ws"):
        self.ws_url = ws_url
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._callbacks: Dict[str, List[Callable]] = {
            "progress": [],
            "executing": [],
            "completed": [],
            "error": [],
            "status": [],
        }
        self._client_id: Optional[str] = None
    
    def on(self, event: str, callback: Callable):
        """注册事件回调"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
        return self
    
    def off(self, event: str, callback: Callable):
        """移除事件回调"""
        if event in self._callbacks and callback in self._callbacks[event]:
            self._callbacks[event].remove(callback)
        return self
    
    def _emit(self, event: str, data: any):
        """触发事件"""
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                print(f"Error in {event} callback: {e}")
    
    async def connect(self, client_id: str = None):
        """连接 WebSocket"""
        self._client_id = client_id or self._generate_client_id()
        url = f"{self.ws_url}?clientId={self._client_id}"
        
        self.ws = await websockets.connect(url)
        self._running = True
        
        # 启动消息接收循环
        asyncio.create_task(self._receive_loop())
        
        return self
    
    async def disconnect(self):
        """断开连接"""
        self._running = False
        if self.ws:
            await self.ws.close()
            self.ws = None
    
    async def _receive_loop(self):
        """消息接收循环"""
        while self._running and self.ws:
            try:
                message = await self.ws.recv()
                await self._handle_message(message)
            except websockets.exceptions.ConnectionClosed:
                self._emit("error", {"type": "connection_closed"})
                break
            except Exception as e:
                self._emit("error", {"type": "receive_error", "error": str(e)})
    
    async def _handle_message(self, message: str):
        """处理收到的消息"""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return
        
        msg_type = data.get("type")
        
        if msg_type == "status":
            # 队列状态更新
            status_data = data.get("data", {})
            self._emit("status", status_data)
            
        elif msg_type == "progress":
            # 进度更新
            progress_data = data.get("data", {})
            progress = ComfyUIProgress(
                value=progress_data.get("value", 0),
                max=progress_data.get("max", 1),
                percent=progress_data.get("value", 0) / max(progress_data.get("max", 1), 1) * 100
            )
            self._emit("progress", {
                "progress": progress,
                "prompt_id": data.get("prompt_id"),
                "node_id": progress_data.get("node"),
            })
            
        elif msg_type == "executing":
            # 节点开始执行
            exec_data = data.get("data", {})
            self._emit("executing", {
                "node_id": exec_data.get("node"),
                "prompt_id": exec_data.get("prompt_id"),
            })
            
        elif msg_type == "execution_cached":
            # 节点使用缓存
            cached_data = data.get("data", {})
            self._emit("executing", {
                "node_id": cached_data.get("node"),
                "prompt_id": cached_data.get("prompt_id"),
                "cached": True,
            })
            
        elif msg_type == "execution_error":
            # 执行错误
            error_data = data.get("data", {})
            self._emit("error", {
                "prompt_id": error_data.get("prompt_id"),
                "node_id": error_data.get("node"),
                "error": error_data.get("error"),
            })
            
        elif msg_type == "execution_interrupted":
            # 执行被中断
            self._emit("error", {
                "type": "interrupted",
                "prompt_id": data.get("prompt_id"),
            })
    
    def _generate_client_id(self) -> str:
        """生成客户端 ID"""
        import uuid
        return str(uuid.uuid4())


# 使用示例
async def example_usage():
    ws = ComfyUIWebSocket()
    
    # 注册回调
    ws.on("progress", lambda data: print(f"Progress: {data['progress'].percent:.1f}%"))
    ws.on("executing", lambda data: print(f"Executing node: {data['node_id']}"))
    ws.on("completed", lambda data: print(f"Completed: {data['prompt_id']}"))
    ws.on("error", lambda data: print(f"Error: {data}"))
    
    # 连接
    await ws.connect()
    
    # 保持运行
    await asyncio.sleep(60)
    
    # 断开
    await ws.disconnect()
```

### 5.4 Workflow 执行器

```python
# src/server/services/workflow_executor.py

import asyncio
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto

from .comfyui_client import ComfyUIClient, ComfyUIConfig
from .comfyui_websocket import ComfyUIWebSocket

class ExecutionStatus(Enum):
    PENDING = auto()
    QUEUED = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()

@dataclass
class ExecutionTask:
    id: str
    workflow_id: str
    workflow_name: str
    parameters: Dict[str, Any]
    status: ExecutionStatus = ExecutionStatus.PENDING
    prompt_id: Optional[str] = None
    progress: float = 0.0
    current_node: Optional[str] = None
    output_images: list = field(default_factory=list)
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class WorkflowExecutor:
    """Workflow 执行管理器"""
    
    def __init__(self, comfyui_config: ComfyUIConfig = None):
        self.config = comfyui_config or ComfyUIConfig()
        self.client = ComfyUIClient(self.config)
        self.websocket: Optional[ComfyUIWebSocket] = None
        self._tasks: Dict[str, ExecutionTask] = {}
        self._callbacks: Dict[str, List[Callable]] = {
            "status_changed": [],
            "progress": [],
            "completed": [],
            "error": [],
        }
        self._ws_connected = False
    
    async def initialize(self):
        """初始化（连接 WebSocket）"""
        self.websocket = ComfyUIWebSocket(self.config.ws_url)
        
        # 注册 WebSocket 回调
        self.websocket.on("progress", self._on_progress)
        self.websocket.on("executing", self._on_executing)
        self.websocket.on("error", self._on_error)
        self.websocket.on("status", self._on_status)
        
        await self.websocket.connect()
        self._ws_connected = True
    
    async def shutdown(self):
        """关闭"""
        if self.websocket:
            await self.websocket.disconnect()
            self._ws_connected = False
    
    async def execute(
        self,
        workflow_id: str,
        workflow_name: str,
        workflow_json: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> ExecutionTask:
        """执行 Workflow"""
        import uuid
        
        # 创建任务
        task = ExecutionTask(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            parameters=parameters,
        )
        self._tasks[task.id] = task
        
        try:
            async with self.client:
                # 1. 应用参数到 workflow
                modified_workflow = self._apply_parameters(
                    workflow_json, 
                    parameters
                )
                
                # 2. 提交到 ComfyUI
                task.status = ExecutionStatus.QUEUED
                self._emit("status_changed", task)
                
                prompt_id = await self.client.submit_workflow(
                    modified_workflow,
                    extra_data={"task_id": task.id}
                )
                task.prompt_id = prompt_id
                task.status = ExecutionStatus.RUNNING
                task.started_at = datetime.now()
                self._emit("status_changed", task)
                
                # 3. 等待完成（通过 WebSocket 更新进度）
                await self._wait_for_completion(task)
                
        except Exception as e:
            task.status = ExecutionStatus.FAILED
            task.error_message = str(e)
            self._emit("error", task)
        
        return task
    
    def _apply_parameters(
        self, 
        workflow: Dict[str, Any], 
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """将用户参数应用到 workflow"""
        import copy
        result = copy.deepcopy(workflow)
        
        # 遍历 workflow 节点，替换参数
        for node_id, node in result.items():
            if not isinstance(node, dict):
                continue
                
            inputs = node.get("inputs", {})
            for param_name, param_value in parameters.items():
                # 根据参数映射规则替换
                if param_name in inputs:
                    inputs[param_name] = param_value
        
        return result
    
    async def _wait_for_completion(self, task: ExecutionTask, timeout: float = 600):
        """等待任务完成"""
        start_time = datetime.now()
        
        while task.status == ExecutionStatus.RUNNING:
            # 检查超时
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout:
                task.status = ExecutionStatus.FAILED
                task.error_message = "Execution timeout"
                break
            
            # 轮询检查状态（WebSocket 备用）
            if not self._ws_connected:
                await self._poll_status(task)
            
            await asyncio.sleep(0.5)
        
        task.completed_at = datetime.now()
        
        if task.status == ExecutionStatus.COMPLETED:
            self._emit("completed", task)
        
        return task
    
    async def _poll_status(self, task: ExecutionTask):
        """轮询检查状态（WebSocket 不可用时）"""
        try:
            history = await self.client.get_history(task.prompt_id)
            if task.prompt_id in history:
                outputs = history[task.prompt_id].get("outputs", {})
                # 提取输出图片
                for node_id, node_outputs in outputs.items():
                    if "images" in node_outputs:
                        task.output_images.extend(node_outputs["images"])
                
                task.status = ExecutionStatus.COMPLETED
                task.progress = 100.0
        except Exception:
            pass
    
    # ─── WebSocket 回调 ───
    
    def _on_progress(self, data: Dict):
        """进度更新"""
        prompt_id = data.get("prompt_id")
        task = self._find_task_by_prompt_id(prompt_id)
        
        if task:
            progress = data.get("progress")
            task.progress = progress.percent if progress else 0
            self._emit("progress", task)
    
    def _on_executing(self, data: Dict):
        """节点执行"""
        prompt_id = data.get("prompt_id")
        task = self._find_task_by_prompt_id(prompt_id)
        
        if task:
            task.current_node = data.get("node_id")
            # 如果节点为 null，表示执行完成
            if data.get("node_id") is None:
                task.status = ExecutionStatus.COMPLETED
                task.progress = 100.0
    
    def _on_error(self, data: Dict):
        """执行错误"""
        prompt_id = data.get("prompt_id")
        task = self._find_task_by_prompt_id(prompt_id)
        
        if task:
            task.status = ExecutionStatus.FAILED
            task.error_message = data.get("error", "Unknown error")
            self._emit("error", task)
    
    def _on_status(self, data: Dict):
        """状态更新"""
        # 可以在这里处理队列状态变化
        pass
    
    def _find_task_by_prompt_id(self, prompt_id: str) -> Optional[ExecutionTask]:
        """根据 prompt_id 查找任务"""
        for task in self._tasks.values():
            if task.prompt_id == prompt_id:
                return task
        return None
    
    # ─── 事件系统 ───
    
    def on(self, event: str, callback: Callable):
        """注册事件回调"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _emit(self, event: str, data: Any):
        """触发事件"""
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                print(f"Error in {event} callback: {e}")
    
    # ─── 任务管理 ───
    
    def get_task(self, task_id: str) -> Optional[ExecutionTask]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[ExecutionTask]:
        """获取所有任务"""
        return list(self._tasks.values())
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False
        
        if task.status in [ExecutionStatus.PENDING, ExecutionStatus.QUEUED]:
            task.status = ExecutionStatus.CANCELLED
            return True
        
        if task.status == ExecutionStatus.RUNNING and task.prompt_id:
            # 调用 ComfyUI 取消 API
            async with self.client:
                await self.client.cancel_current()
                task.status = ExecutionStatus.CANCELLED
                return True
        
        return False
```

---

## 6. 进度更新机制

### 6.1 进度推送架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     进度推送架构                                 │
└─────────────────────────────────────────────────────────────────┘

ComfyUI Server
    │
    │ WebSocket 事件
    ▼
┌─────────────────┐
│ ComfyUIWebSocket│
│  (后端服务)      │
└────────┬────────┘
         │ 解析事件
         ▼
┌─────────────────┐
│ WorkflowExecutor│
│  (任务管理)      │
└────────┬────────┘
         │ 更新任务状态
         ▼
┌─────────────────┐     ┌─────────────────┐
│  WebSocket      │────►│   Web Frontend  │
│  Server (FastAPI)│     │  (React Hook)   │
└─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │  ExecutionStore │
                        │   (Zustand)     │
                        └─────────────────┘
```

### 6.2 进度消息格式

```typescript
// 后端 → 前端 WebSocket 消息
interface ProgressMessage {
  type: 'execution_progress' | 'execution_status' | 'execution_complete' | 'execution_error';
  taskId: string;
  timestamp: number;
  
  // execution_progress
  progress?: {
    percent: number;
    currentStep: number;
    totalSteps: number;
    currentNode?: string;
    nodeName?: string;
    eta?: number;
  };
  
  // execution_complete
  result?: {
    images: Array<{
      filename: string;
      subfolder: string;
      url: string;
    }>;
    metadata?: any;
  };
  
  // execution_error
  error?: {
    code: string;
    message: string;
    nodeId?: string;
    details?: any;
  };
}
```

### 6.3 前端进度展示组件

```tsx
// src/web/components/ExecutionProgress.tsx

import React from 'react';
import { useExecutionStore } from '../stores/executionStore';

export const ExecutionProgress: React.FC<{ taskId: string }> = ({ taskId }) => {
  const task = useExecutionStore(state => state.getTask(taskId));
  
  if (!task) return null;
  
  const { status, progress, currentNode, workflowName } = task;
  
  // 根据状态显示不同 UI
  switch (status) {
    case 'queued':
      return (
        <div className="execution-progress queued">
          <div className="status-icon">⏳</div>
          <div className="status-text">排队中...</div>
        </div>
      );
      
    case 'running':
      return (
        <div className="execution-progress running">
          <div className="progress-header">
            <span className="workflow-name">{workflowName}</span>
            <span className="progress-percent">{progress.percent.toFixed(0)}%</span>
          </div>
          
          <div className="progress-bar">
            <div 
              className="progress-fill"
              style={{ width: `${progress.percent}%` }}
            />
          </div>
          
          <div className="progress-details">
            <span className="step-info">
              步骤 {progress.currentStep}/{progress.totalSteps}
            </span>
            {currentNode && (
              <span className="node-info">
                正在执行: {currentNode}
              </span>
            )}
            {progress.eta && (
              <span className="eta">
                预计剩余: {formatDuration(progress.eta)}
              </span>
            )}
          </div>
          
          <button 
            className="cancel-btn"
            onClick={() => useExecutionStore.getState().cancelTask(taskId)}
          >
            取消
          </button>
        </div>
      );
      
    case 'completed':
      return (
        <div className="execution-progress completed">
          <div className="status-icon">✅</div>
          <div className="status-text">运行完成</div>
          {task.result?.images && (
            <div className="result-images">
              {task.result.images.map((img, idx) => (
                <img 
                  key={idx}
                  src={img.url}
                  alt={`Result ${idx + 1}`}
                  className="result-image"
                />
              ))}
            </div>
          )}
        </div>
      );
      
    case 'failed':
      return (
        <div className="execution-progress failed">
          <div className="status-icon">❌</div>
          <div className="status-text">运行失败</div>
          {task.error && (
            <div className="error-message">
              {task.error.message}
            </div>
          )}
          <button 
            className="retry-btn"
            onClick={() => useExecutionStore.getState().retryTask(taskId)}
          >
            重试
          </button>
        </div>
      );
      
    default:
      return null;
  }
};

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.ceil(seconds)}秒`;
  if (seconds < 3600) return `${Math.ceil(seconds / 60)}分钟`;
  return `${Math.floor(seconds / 3600)}小时${Math.ceil((seconds % 3600) / 60)}分钟`;
}
```

### 6.4 降级机制

```python
# 当 WebSocket 不可用时，使用轮询作为降级方案

class PollingFallback:
    """轮询降级方案"""
    
    def __init__(self, client: ComfyUIClient, interval: float = 2.0):
        self.client = client
        self.interval = interval
        self._running = False
    
    async def start_polling(self, prompt_id: str, callback: Callable):
        """开始轮询"""
        self._running = True
        
        while self._running:
            try:
                # 获取历史记录
                history = await self.client.get_history(prompt_id)
                
                if prompt_id in history:
                    # 执行完成
                    result = history[prompt_id]
                    callback({
                        "type": "completed",
                        "outputs": result.get("outputs", {})
                    })
                    break
                
                # 获取队列状态
                queue = await self.client.get_queue()
                running = queue.get("queue_running", [])
                pending = queue.get("queue_pending", [])
                
                # 检查任务是否在队列中
                is_queued = any(
                    item[1] == prompt_id 
                    for item in running + pending
                )
                
                if not is_queued and prompt_id not in history:
                    # 任务可能已丢失
                    callback({
                        "type": "error",
                        "error": "Task not found"
                    })
                    break
                
            except Exception as e:
                callback({
                    "type": "error",
                    "error": str(e)
                })
            
            await asyncio.sleep(self.interval)
    
    def stop(self):
        """停止轮询"""
        self._running = False
```

---

## 7. 错误处理方案

### 7.1 错误分类

```typescript
// 错误类型枚举（统一错误码前缀）
enum ErrorType {
  // 通用错误 (COMMON_*)
  COMMON_NETWORK_ERROR = 'COMMON_NETWORK_ERROR',
  COMMON_CONNECTION_LOST = 'COMMON_CONNECTION_LOST',
  COMMON_TIMEOUT = 'COMMON_TIMEOUT',
  COMMON_INTERNAL_ERROR = 'COMMON_INTERNAL_ERROR',
  
  // 参数错误 (COMMON_*)
  COMMON_INVALID_PARAMETER = 'COMMON_INVALID_PARAMETER',
  COMMON_MISSING_REQUIRED_PARAMETER = 'COMMON_MISSING_REQUIRED_PARAMETER',
  COMMON_PARAMETER_VALIDATION_FAILED = 'COMMON_PARAMETER_VALIDATION_FAILED',
  
  // Workflow 错误 (WORKFLOW_*)
  WORKFLOW_NOT_FOUND = 'WORKFLOW_NOT_FOUND',
  WORKFLOW_INVALID = 'WORKFLOW_INVALID',
  WORKFLOW_NODE_EXECUTION_FAILED = 'WORKFLOW_NODE_EXECUTION_FAILED',
  WORKFLOW_OUT_OF_MEMORY = 'WORKFLOW_OUT_OF_MEMORY',
  WORKFLOW_MODEL_NOT_FOUND = 'WORKFLOW_MODEL_NOT_FOUND',
  
  // 系统错误 (COMMON_*)
  COMMON_COMFYUI_NOT_RUNNING = 'COMMON_COMFYUI_NOT_RUNNING',
  COMMON_QUEUE_FULL = 'COMMON_QUEUE_FULL',
}

// 错误信息
// 用户提示格式: "{简要描述}\n\n{建议操作}"
interface AppError {
  type: ErrorType;
  code: string;
  message: string;
  userMessage: string;      // 格式: "{简要描述}\n\n{建议操作}"
  details?: any;
  recoverable: boolean;     // 是否可恢复
  suggestedActions?: string[];  // 建议操作
}
```

### 7.2 错误处理流程

```
┌─────────────────────────────────────────────────────────────────┐
│                     错误处理流程                                 │
└─────────────────────────────────────────────────────────────────┘

检测到错误
    │
    ▼
┌─────────────────┐
│  分类错误类型    │
│  - 连接错误？    │
│  - 参数错误？    │
│  - 执行错误？    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 根据类型处理                                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 连接错误:                                                        │
│   - 显示重连按钮                                                │
│   - 自动重试（最多3次）                                          │
│   - 提示检查 ComfyUI 是否运行                                    │
│                                                                 │
│ 参数错误:                                                        │
│   - 高亮错误字段                                                │
│   - 显示验证错误信息                                             │
│   - 允许用户修正后重试                                           │
│                                                                 │
│ 执行错误:                                                        │
│   - 显示详细错误信息                                             │
│   - 提供解决方案（如缺少模型时提示安装）                          │
│   - 提供重试/取消选项                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  记录错误日志    │
└─────────────────┘
```

### 7.3 具体错误处理

#### 7.3.1 ComfyUI 未运行

```tsx
// 前端处理
const handleComfyUINotRunning = () => {
  return (
    <div className="error-panel">
      <div className="error-icon">🔌</div>
      <h3>无法连接到 ComfyUI</h3>
      <p>请确保 ComfyUI 已启动并运行在 ws://localhost:8188</p>
      <div className="error-actions">
        <button onClick={retryConnection}>重试连接</button>
        <button onClick={openSettings}>打开设置</button>
      </div>
      <div className="error-help">
        <p>如何启动 ComfyUI：</p>
        <code>python main.py --listen --port 8188</code>
      </div>
    </div>
  );
};
```

#### 7.3.2 缺少模型

```tsx
// 前端处理
const handleModelNotFound = (error: AppError) => {
  const missingModel = error.details?.model_name;
  
  return (
    <div className="error-panel">
      <div className="error-icon">📦</div>
      <h3>缺少模型文件</h3>
      <p>Workflow 需要以下模型，但未找到：</p>
      <code>{missingModel}</code>
      <div className="error-actions">
        <button onClick={() => openModelDownloadPage(missingModel)}>
          下载模型
        </button>
        <button onClick={selectAlternativeModel}>
          选择替代模型
        </button>
      </div>
    </div>
  );
};
```

#### 7.3.3 参数验证失败

```tsx
// 表单验证错误显示
const ParameterField: React.FC<{
  param: WorkflowParameter;
  value: any;
  error?: string;
  onChange: (value: any) => void;
}> = ({ param, value, error, onChange }) => {
  return (
    <div className={`param-field ${error ? 'has-error' : ''}`}>
      <label>
        {param.name}
        {param.required && <span className="required">*</span>}
      </label>
      
      {/* 根据类型渲染输入组件 */}
      <ParamInput 
        type={param.type}
        value={value}
        onChange={onChange}
        {...param}
      />
      
      {/* 错误提示 */}
      {error && (
        <div className="error-message">
          <span className="error-icon">⚠️</span>
          {error}
        </div>
      )}
      
      {/* 参数说明 */}
      {param.description && !error && (
        <div className="param-description">
          {param.description}
        </div>
      )}
    </div>
  );
};
```

### 7.4 后端错误处理

```python
# src/server/api/errors.py

from fastapi import HTTPException
from enum import Enum

class ErrorCode(Enum):
    # 通用错误 (COMMON_*)
    COMMON_NETWORK_ERROR = "COMMON_NETWORK_ERROR"
    COMMON_TIMEOUT = "COMMON_TIMEOUT"
    COMMON_INVALID_PARAMETERS = "COMMON_INVALID_PARAMETERS"
    COMMON_MISSING_REQUIRED_PARAMETER = "COMMON_MISSING_REQUIRED_PARAMETER"
    COMMON_COMFYUI_NOT_CONNECTED = "COMMON_COMFYUI_NOT_CONNECTED"
    COMMON_INTERNAL_ERROR = "COMMON_INTERNAL_ERROR"
    
    # Workflow 错误 (WORKFLOW_*)
    WORKFLOW_NOT_FOUND = "WORKFLOW_NOT_FOUND"
    WORKFLOW_COMFYUI_ERROR = "WORKFLOW_COMFYUI_ERROR"
    WORKFLOW_EXECUTION_FAILED = "WORKFLOW_EXECUTION_FAILED"

# 用户提示格式: "{简要描述}\n\n{建议操作}"
ERROR_MESSAGES = {
    ErrorCode.WORKFLOW_NOT_FOUND: {
        "status_code": 404,
        "message": "Workflow not found",
        "user_message": "找不到指定的 Workflow\n\n请检查 Workflow ID 是否正确，或返回列表重新选择",
    },
    ErrorCode.COMMON_INVALID_PARAMETERS: {
        "status_code": 400,
        "message": "Invalid parameters",
        "user_message": "参数格式不正确\n\n请检查参数类型和取值范围后重试",
    },
    ErrorCode.COMMON_MISSING_REQUIRED_PARAMETER: {
        "status_code": 400,
        "message": "Missing required parameter",
        "user_message": "缺少必填参数\n\n请填写所有标记为 * 的必填项",
    },
    ErrorCode.COMMON_COMFYUI_NOT_CONNECTED: {
        "status_code": 503,
        "message": "ComfyUI not connected",
        "user_message": "无法连接到 ComfyUI\n\n请检查 ComfyUI 是否已启动，或在设置中检查连接地址",
    },
    ErrorCode.WORKFLOW_COMFYUI_ERROR: {
        "status_code": 502,
        "message": "ComfyUI error",
        "user_message": "ComfyUI 运行出错\n\n请查看 ComfyUI 控制台获取详细错误信息",
    },
    ErrorCode.WORKFLOW_EXECUTION_FAILED: {
        "status_code": 500,
        "message": "Execution failed",
        "user_message": "运行失败\n\n请查看详细错误信息，或尝试重新运行",
    },
}

def raise_app_error(code: ErrorCode, details: dict = None):
    """抛出应用错误"""
    error_info = ERROR_MESSAGES[code]
    raise HTTPException(
        status_code=error_info["status_code"],
        detail={
            "code": code.value,
            "message": error_info["message"],
            "user_message": error_info["user_message"],
            "details": details,
        }
    )

# 使用示例
@app.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    workflow = workflow_store.get(workflow_id)
    if not workflow:
        raise_app_error(ErrorCode.WORKFLOW_NOT_FOUND, {"workflow_id": workflow_id})
    return workflow
```

---

## 8. 代码示例

### 8.1 Workflow 定义示例

```json
{
  "id": "official/sdxl-portrait",
  "name": "SDXL 肖像摄影",
  "description": "基于 SDXL 的高质量肖像摄影工作流",
  "detailed_description": "本工作流专为肖像摄影设计，支持多种风格和光照效果...",
  "type": "workflow",
  "source": "official",
  "targetDCCs": ["comfyui"],
  "status": "installed",
  "previewImage": "/workflows/official/sdxl-portrait/preview.png",
  "stats": {
    "downloads": 2300,
    "rating": 4.9,
    "useCount": 150
  },
  "data": {
    "version": "1.0.0",
    "parameters": [
      {
        "id": "prompt",
        "name": "提示词",
        "type": "string",
        "required": true,
        "multiline": true,
        "default": "professional portrait photo, 8k, highly detailed",
        "description": "描述你想要生成的肖像内容"
      },
      {
        "id": "negative_prompt",
        "name": "负面提示词",
        "type": "string",
        "required": false,
        "multiline": true,
        "default": "ugly, blurry, low quality",
        "description": "描述你不希望出现的内容"
      },
      {
        "id": "width",
        "name": "宽度",
        "type": "number",
        "required": true,
        "default": 1024,
        "min": 512,
        "max": 2048,
        "step": 64,
        "slider": true
      },
      {
        "id": "height",
        "name": "高度",
        "type": "number",
        "required": true,
        "default": 1024,
        "min": 512,
        "max": 2048,
        "step": 64,
        "slider": true
      },
      {
        "id": "checkpoint",
        "name": "大模型",
        "type": "enum",
        "required": true,
        "options_source": "comfyui.checkpoints",
        "default": "sd_xl_base_1.0.safetensors"
      },
      {
        "id": "sampler",
        "name": "采样器",
        "type": "enum",
        "required": true,
        "options": ["euler", "euler_ancestral", "dpmpp_2m", "dpmpp_sde"],
        "default": "dpmpp_2m"
      },
      {
        "id": "steps",
        "name": "采样步数",
        "type": "number",
        "required": true,
        "default": 30,
        "min": 1,
        "max": 100,
        "step": 1,
        "slider": true
      },
      {
        "id": "cfg",
        "name": "CFG Scale",
        "type": "number",
        "required": true,
        "default": 7.0,
        "min": 1.0,
        "max": 30.0,
        "step": 0.5,
        "slider": true
      },
      {
        "id": "enable_hires",
        "name": "启用高清修复",
        "type": "boolean",
        "required": false,
        "default": false
      },
      {
        "id": "hires_denoise",
        "name": "高清修复重绘幅度",
        "type": "number",
        "required": false,
        "default": 0.5,
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
        "slider": true,
        "show_when": { "enable_hires": true }
      }
    ],
    "workflow_json": {
      "1": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
          "ckpt_name": "${checkpoint}"
        }
      },
      "2": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "text": "${prompt}",
          "clip": ["1", 1]
        }
      },
      "3": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "text": "${negative_prompt}",
          "clip": ["1", 1]
        }
      },
      "4": {
        "class_type": "EmptyLatentImage",
        "inputs": {
          "width": "${width}",
          "height": "${height}",
          "batch_size": 1
        }
      },
      "5": {
        "class_type": "KSampler",
        "inputs": {
          "model": ["1", 0],
          "seed": "${seed}",
          "steps": "${steps}",
          "cfg": "${cfg}",
          "sampler_name": "${sampler}",
          "scheduler": "normal",
          "positive": ["2", 0],
          "negative": ["3", 0],
          "latent_image": ["4", 0]
        }
      },
      "6": {
        "class_type": "VAEDecode",
        "inputs": {
          "samples": ["5", 0],
          "vae": ["1", 2]
        }
      },
      "7": {
        "class_type": "SaveImage",
        "inputs": {
          "images": ["6", 0],
          "filename_prefix": "artclaw"
        }
      }
    }
  }
}
```

### 8.2 前端执行流程代码

```tsx
// src/web/hooks/useWorkflowExecution.ts

import { useState, useCallback } from 'react';
import { useExecutionStore } from '../stores/executionStore';
import { useChatStore } from '../stores/chatStore';
import { workflowApi } from '../api/workflow';

export const useWorkflowExecution = () => {
  const [isLoading, setIsLoading] = useState(false);
  const { addTask, updateTask } = useExecutionStore();
  const { sendMessage, addSystemMessage } = useChatStore();
  
  // 启动 Workflow 执行流程
  const startExecution = useCallback(async (workflow: Workflow) => {
    setIsLoading(true);
    
    try {
      // 1. 跳转到对话面板（如果不在）
      // 由路由处理
      
      // 2. 发送自动消息给 AI
      const message = `/run workflow:${workflow.id}`;
      await sendMessage(message);
      
      // 3. 等待 AI 响应，显示参数表单
      // 这部分由 AI 响应处理
      
    } catch (error) {
      addSystemMessage({
        type: 'error',
        content: `启动 Workflow 失败: ${error.message}`
      });
    } finally {
      setIsLoading(false);
    }
  }, [sendMessage, addSystemMessage]);
  
  // 提交执行（用户确认参数后）
  const submitExecution = useCallback(async (
    workflow: Workflow,
    parameters: Record<string, any>
  ) => {
    // 创建执行任务
    const task = await workflowApi.execute(workflow.id, parameters);
    
    // 添加到执行存储
    addTask({
      id: task.id,
      workflowId: workflow.id,
      workflowName: workflow.name,
      parameters,
      status: 'queued',
      progress: 0,
    });
    
    // 在消息流中显示进度卡片
    addSystemMessage({
      type: 'execution',
      content: '',
      metadata: {
        taskId: task.id,
        workflowName: workflow.name,
      }
    });
    
    return task;
  }, [addTask, addSystemMessage]);
  
  return {
    isLoading,
    startExecution,
    submitExecution,
  };
};
```

### 8.3 参数表单组件

```tsx
// src/web/components/ParameterForm/ParameterForm.tsx

import React from 'react';
import { WorkflowParameter } from '../../types/workflow';
import { StringInput } from './inputs/StringInput';
import { NumberInput } from './inputs/NumberInput';
import { BooleanInput } from './inputs/BooleanInput';
import { EnumInput } from './inputs/EnumInput';
import { ImageInput } from './inputs/ImageInput';

interface ParameterFormProps {
  workflowName: string;
  parameters: WorkflowParameter[];
  values: Record<string, any>;
  errors: Record<string, string>;
  onChange: (id: string, value: any) => void;
  onSubmit: () => void;
  onCancel: () => void;
}

export const ParameterForm: React.FC<ParameterFormProps> = ({
  workflowName,
  parameters,
  values,
  errors,
  onChange,
  onSubmit,
  onCancel,
}) => {
  // 根据条件过滤显示的参数
  const visibleParams = parameters.filter(param => {
    if (!param.show_when) return true;
    
    // 检查条件
    return Object.entries(param.show_when).every(([key, expectedValue]) => {
      return values[key] === expectedValue;
    });
  });
  
  // 分组：必填和非必填
  const requiredParams = visibleParams.filter(p => p.required);
  const optionalParams = visibleParams.filter(p => !p.required);
  
  const renderInput = (param: WorkflowParameter) => {
    const commonProps = {
      key: param.id,
      param,
      value: values[param.id],
      error: errors[param.id],
      onChange: (value: any) => onChange(param.id, value),
    };
    
    switch (param.type) {
      case 'string':
        return <StringInput {...commonProps} />;
      case 'number':
        return <NumberInput {...commonProps} />;
      case 'boolean':
        return <BooleanInput {...commonProps} />;
      case 'enum':
        return <EnumInput {...commonProps} />;
      case 'image':
        return <ImageInput {...commonProps} />;
      default:
        return null;
    }
  };
  
  return (
    <div className="parameter-form">
      <div className="form-header">
        <h3>运行: {workflowName}</h3>
      </div>
      
      <div className="form-body">
        {requiredParams.length > 0 && (
          <div className="param-group">
            <h4>必填参数</h4>
            {requiredParams.map(renderInput)}
          </div>
        )}
        
        {optionalParams.length > 0 && (
          <div className="param-group">
            <h4>可选参数</h4>
            {optionalParams.map(renderInput)}
          </div>
        )}
      </div>
      
      <div className="form-footer">
        <button className="btn-secondary" onClick={onCancel}>
          取消
        </button>
        <button className="btn-primary" onClick={onSubmit}>
          运行
        </button>
      </div>
      
      <div className="form-hint">
        💡 你可以说"帮我填写参数"让 AI 协助
      </div>
    </div>
  );
};
```

---

## 9. API 接口定义

### 9.1 Workflow 管理 API

```yaml
# Workflow 管理接口

# 获取 Workflow 列表
GET /api/workflows
Query:
  - source: string (optional) - 来源筛选: official, marketplace, user
  - tag: string (optional) - 标签筛选
  - search: string (optional) - 关键词搜索
  - page: number (optional) - 页码，默认 1
  - pageSize: number (optional) - 每页数量，默认 20
Response:
  200:
    data:
      items: Workflow[]
      total: number
      page: number
      pageSize: number

# 获取单个 Workflow
GET /api/workflows/{workflow_id}
Response:
  200:
    data: Workflow
  404:
    error: WORKFLOW_NOT_FOUND

# 安装 Workflow
POST /api/workflows/{workflow_id}/install
Body:
  source: string - 来源: official, marketplace
Response:
  200:
    data: { installed: true }
  400:
    error: ALREADY_INSTALLED
  404:
    error: WORKFLOW_NOT_FOUND

# 卸载 Workflow
POST /api/workflows/{workflow_id}/uninstall
Response:
  200:
    data: { uninstalled: true }

# 收藏/取消收藏 Workflow
POST /api/workflows/{workflow_id}/favorite
Body:
  favorite: boolean
Response:
  200:
    data: { favorited: boolean }

# 获取 Workflow 参数定义
GET /api/workflows/{workflow_id}/parameters
Response:
  200:
    data:
      parameters: WorkflowParameter[]
```

### 9.2 Workflow 执行 API

```yaml
# Workflow 执行接口

# 执行 Workflow
POST /api/workflows/{workflow_id}/execute
Body:
  parameters: object - 参数值
  options:
    priority: number (optional) - 优先级
    clientId: string (optional) - 客户端ID，用于接收 WebSocket 通知
Response:
  200:
    data:
      taskId: string
      promptId: string
      status: string
      estimatedTime: number
  400:
    error: INVALID_PARAMETERS
  503:
    error: COMFYUI_NOT_CONNECTED

# 获取执行状态
GET /api/workflows/execute/{task_id}
Response:
  200:
    data:
      taskId: string
      status: string
      progress:
        percent: number
        currentStep: number
        totalSteps: number
        currentNode: string
        eta: number
      result:
        images: string[]
      error:
        code: string
        message: string

# 取消执行
POST /api/workflows/execute/{task_id}/cancel
Response:
  200:
    data: { cancelled: true }
  400:
    error: CANNOT_CANCEL

# 获取执行历史
GET /api/workflows/execute/history
Query:
  - workflowId: string (optional)
  - limit: number (optional)
Response:
  200:
    data:
      items: ExecutionTask[]
      total: number
```

### 9.3 WebSocket 事件

```yaml
# WebSocket 连接
WS /ws

# 客户端发送
## 订阅执行状态
{
  "type": "subscribe",
  "taskId": "task-id"
}

## 取消订阅
{
  "type": "unsubscribe",
  "taskId": "task-id"
}

# 服务端推送
## 进度更新
{
  "type": "execution_progress",
  "taskId": "task-id",
  "data": {
    "percent": 65.0,
    "currentStep": 13,
    "totalSteps": 20,
    "currentNode": "KSampler",
    "eta": 15
  },
  "timestamp": 1712750400000
}

## 状态变更
{
  "type": "execution_status",
  "taskId": "task-id",
  "data": {
    "status": "running",
    "promptId": "prompt-id"
  },
  "timestamp": 1712750400000
}

## 执行完成
{
  "type": "execution_complete",
  "taskId": "task-id",
  "data": {
    "images": [
      {
        "filename": "artclaw_0001.png",
        "subfolder": "",
        "url": "/api/images/artclaw_0001.png"
      }
    ]
  },
  "timestamp": 1712750500000
}

## 执行错误
{
  "type": "execution_error",
  "taskId": "task-id",
  "data": {
    "code": "WORKFLOW_NODE_EXECUTION_FAILED",
    "message": "KSampler execution failed: out of memory",
    "nodeId": "5"
  },
  "timestamp": 1712750450000
}
```

---

## 10. 数据模型

### 10.1 TypeScript 类型定义

```typescript
// src/web/types/workflow.ts

// Workflow 类型
export type WorkflowSource = 'official' | 'marketplace' | 'user';
export type WorkflowStatus = 'not_installed' | 'installed' | 'update_available';

export interface Workflow {
  id: string;
  name: string;
  description: string;
  detailedDescription?: string;
  type: 'workflow';
  source: WorkflowSource;
  targetDCCs: string[];
  status: WorkflowStatus;
  previewImage?: string;
  stats: {
    downloads: number;
    rating: number;
    useCount: number;
  };
  runtimeStatus?: {
    favorited: boolean;
    lastUsed?: string;
  };
  data: WorkflowData;
}

export interface WorkflowData {
  version: string;
  parameters: WorkflowParameter[];
  workflowJson?: object;
}

// 参数类型
export type ParameterType = 'string' | 'number' | 'boolean' | 'enum' | 'image';

export interface BaseParameter {
  id: string;
  name: string;
  type: ParameterType;
  required: boolean;
  default?: any;
  description?: string;
  show_when?: Record<string, any>;
}

export interface StringParameter extends BaseParameter {
  type: 'string';
  multiline?: boolean;
  maxLength?: number;
  placeholder?: string;
}

export interface NumberParameter extends BaseParameter {
  type: 'number';
  min?: number;
  max?: number;
  step?: number;
  slider?: boolean;
}

export interface BooleanParameter extends BaseParameter {
  type: 'boolean';
}

export interface EnumParameter extends BaseParameter {
  type: 'enum';
  options: string[];
  options_source?: string;  // 动态选项来源，如 "comfyui.checkpoints"
}

export interface ImageParameter extends BaseParameter {
  type: 'image';
  accept?: string[];
  maxSize?: number;
}

export type WorkflowParameter = 
  | StringParameter 
  | NumberParameter 
  | BooleanParameter 
  | EnumParameter 
  | ImageParameter;

// 执行任务类型
export type ExecutionState = 
  | 'idle'
  | 'preparing'
  | 'ready'
  | 'submitting'
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface ExecutionProgress {
  percent: number;
  currentStep: number;
  totalSteps: number;
  currentNode?: string;
  eta?: number;
}

export interface ExecutionResult {
  images: Array<{
    filename: string;
    subfolder: string;
    url: string;
  }>;
  metadata?: any;
}

export interface ExecutionError {
  code: string;
  message: string;
  nodeId?: string;
  details?: any;
}

export interface ExecutionTask {
  id: string;
  workflowId: string;
  workflowName: string;
  parameters: Record<string, any>;
  state: ExecutionState;
  promptId?: string;
  progress?: ExecutionProgress;
  result?: ExecutionResult;
  error?: ExecutionError;
  createdAt: number;
  startedAt?: number;
  completedAt?: number;
}
```

### 10.2 Python 数据模型

```python
# src/server/models/workflow.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime

class WorkflowSource(str, Enum):
    OFFICIAL = "official"
    MARKETPLACE = "marketplace"
    USER = "user"

class WorkflowStatus(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"

class ParameterType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"
    IMAGE = "image"

class WorkflowStats(BaseModel):
    downloads: int = 0
    rating: float = 0.0
    use_count: int = 0

class WorkflowRuntimeStatus(BaseModel):
    favorited: bool = False
    last_used: Optional[datetime] = None

class BaseParameter(BaseModel):
    id: str
    name: str
    type: ParameterType
    required: bool
    default: Optional[Any] = None
    description: Optional[str] = None
    show_when: Optional[Dict[str, Any]] = None

class StringParameter(BaseParameter):
    type: ParameterType = ParameterType.STRING
    multiline: bool = False
    max_length: Optional[int] = None
    placeholder: Optional[str] = None

class NumberParameter(BaseParameter):
    type: ParameterType = ParameterType.NUMBER
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    slider: bool = False

class BooleanParameter(BaseParameter):
    type: ParameterType = ParameterType.BOOLEAN

class EnumParameter(BaseParameter):
    type: ParameterType = ParameterType.ENUM
    options: List[str]
    options_source: Optional[str] = None

class ImageParameter(BaseParameter):
    type: ParameterType = ParameterType.IMAGE
    accept: Optional[List[str]] = None
    max_size: Optional[int] = None  # MB

WorkflowParameter = Union[
    StringParameter,
    NumberParameter,
    BooleanParameter,
    EnumParameter,
    ImageParameter,
]

class WorkflowData(BaseModel):
    version: str
    parameters: List[Dict[str, Any]]  # 序列化为 dict 存储
    workflow_json: Optional[Dict[str, Any]] = None

class Workflow(BaseModel):
    id: str
    name: str
    description: str
    detailed_description: Optional[str] = None
    type: str = "workflow"
    source: WorkflowSource
    target_dccs: List[str]
    status: WorkflowStatus
    preview_image: Optional[str] = None
    stats: WorkflowStats = Field(default_factory=WorkflowStats)
    runtime_status: Optional[WorkflowRuntimeStatus] = None
    data: WorkflowData
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# 执行任务模型
class ExecutionState(str, Enum):
    IDLE = "idle"
    PREPARING = "preparing"
    READY = "ready"
    SUBMITTING = "submitting"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ExecutionProgress(BaseModel):
    percent: float
    current_step: int
    total_steps: int
    current_node: Optional[str] = None
    eta: Optional[float] = None

class ExecutionResult(BaseModel):
    images: List[Dict[str, str]]
    metadata: Optional[Any] = None

class ExecutionError(BaseModel):
    code: str
    message: str
    node_id: Optional[str] = None
    details: Optional[Any] = None

class ExecutionTask(BaseModel):
    id: str
    workflow_id: str
    workflow_name: str
    parameters: Dict[str, Any]
    state: ExecutionState
    prompt_id: Optional[str] = None
    progress: Optional[ExecutionProgress] = None
    result: Optional[ExecutionResult] = None
    error: Optional[ExecutionError] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

---

## 附录

### A. 文件结构

```
src/
├── server/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── workflows.py          # Workflow API 路由
│   │   └── execution.py          # 执行 API 路由
│   ├── models/
│   │   ├── __init__.py
│   │   └── workflow.py           # 数据模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── workflow_store.py     # Workflow 存储服务
│   │   ├── workflow_executor.py  # 执行管理器
│   │   ├── comfyui_client.py     # ComfyUI HTTP 客户端
│   │   └── comfyui_websocket.py  # ComfyUI WebSocket 客户端
│   └── websocket/
│       └── manager.py            # WebSocket 连接管理
│
└── web/
    ├── api/
    │   └── workflow.ts           # 前端 API 客户端
    ├── components/
    │   ├── ParameterForm/
    │   │   ├── index.tsx
    │   │   ├── ParameterForm.tsx
    │   │   └── inputs/
    │   │       ├── StringInput.tsx
    │   │       ├── NumberInput.tsx
    │   │       ├── BooleanInput.tsx
    │   │       ├── EnumInput.tsx
    │   │       └── ImageInput.tsx
    │   ├── ExecutionProgress.tsx
    │   └── WorkflowCard.tsx
    ├── pages/
    │   └── Workflows/
    │       ├── index.tsx
    │       ├── WorkflowList.tsx
    │       └── WorkflowDetail.tsx
    ├── stores/
    │   ├── workflowStore.ts
    │   └── executionStore.ts
    └── types/
        └── workflow.ts
```

### B. 依赖清单

```toml
# 后端依赖 (pyproject.toml)
[tool.poetry.dependencies]
python = "^3.10"
fastapi = "^0.110.0"
uvicorn = {extras = ["standard"], version = "^0.27.0"}
websockets = "^12.0"
aiohttp = "^3.9.0"
pydantic = "^2.6.0"
python-multipart = "^0.0.9"

# 前端依赖 (package.json)
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "zustand": "^4.5.0",
    "react-hook-form": "^7.51.0",
    "zod": "^3.22.0",
    "@hookform/resolvers": "^3.3.0",
    "axios": "^1.6.0",
    "react-query": "^3.39.0"
  }
}
```

---

> **文档结束**
> 
> 本文档为 Phase 3 开发提供详细指导，实际开发中可根据实际情况调整。
