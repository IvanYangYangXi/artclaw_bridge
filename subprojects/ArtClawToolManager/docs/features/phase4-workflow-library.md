# Phase 4: Workflow 库

> 版本: 2.0
> 日期: 2026-04-10
> 工期: 1周
> 依赖: Phase 1-2

---

## 目标

实现 ComfyUI Workflow 模板管理和执行功能。

**交付标准**:
- Workflow 浏览/安装/收藏
- 预览图展示
- 参数编辑界面
- 执行接口（提交到 ComfyUI）

---

## Workflow 定位

### 与 Skill/Tool 的关系

```
ArtClaw 工具生态 - 三层概念模型
│
├── 【Skill】AI 操作指南
│   ├── 定义: 指导 AI Agent 如何完成特定任务的文档
│   ├── 示例: comfyui-txt2img、ue57-material-node-edit
│   └── 用途: 告诉 AI "如何"操作 DCC 软件
│
├── 【Workflow】ComfyUI 工作流模板 ← 本 Phase 专注
│   ├── 定义: ComfyUI 的 JSON 格式工作流
│   ├── 示例: SDXL 肖像摄影、产品渲染流程
│   ├── 特点: 可执行、可视化节点图、可参数化
│   └── 用途: 在 ComfyUI 中执行图像生成任务
│
└── 【Tool】用户创建的可复用功能单元
    ├── 定义: 用户包装 Skill 或编写脚本创建的快捷工具
    └── 用途: 封装常用操作为一键执行的工具
```

**关键区分**:
- **Workflow 是 ComfyUI 专属功能** - 仅针对 ComfyUI 平台
- Workflow 直接提交给 ComfyUI 执行，不经过 AI Agent 处理
- Skill 指导 AI 如何操作，Workflow 是预定义的节点图配置
- Tool 是通用 DCC 操作封装，Workflow 专用于图像生成

**执行路径对比**:
```
Skill 路径:
用户输入 → AI 读取 Skill → 生成操作指令 → DCC 执行

Workflow 路径:
用户点击 Workflow → 参数编辑 → 提交 ComfyUI HTTP API → ComfyUI 执行
```

---

## Workflow 存储

```
~/.artclaw/workflows/
├── official/
│   └── workflow-name/
│       ├── manifest.json
│       ├── workflow.json
│       └── preview.png
├── marketplace/
└── user/
```

---

## Day 1-2: Workflow API

### 后端

**API 规范**:

| 端点 | 方法 | 功能 | 参数 |
|------|------|------|------|
| `/api/v1/workflows` | GET | 列表 | source, search, page, limit |
| `/api/v1/workflows/{id}` | GET | 详情 | - |
| `/api/v1/workflows/{id}/install` | POST | 安装 | - |
| `/api/v1/workflows/{id}/uninstall` | POST | 卸载 | - |
| `/api/v1/workflows/{id}/favorite` | POST | 收藏/取消收藏 | - |
| `/api/v1/workflows/{id}/execute` | POST | 执行 | parameters |
| `/api/v1/workflows/jobs/{id}` | GET | 任务状态 | - |

**Workflow 数据模型**:

```json
{
  "id": "official/sdxl-portrait",
  "name": "SDXL 肖像摄影",
  "type": "workflow",
  "source": "official",
  "description": "专业肖像摄影风格",
  "detailedDescription": "基于SDXL的高质量文生图工作流，支持高清修复...",
  "previewImage": "/api/v1/workflows/official/sdxl-portrait/preview",
  "targetDccs": ["comfyui"],
  "status": "not_installed",
  "runtimeStatus": {
    "favorited": false
  },
  "parameters": [
    {
      "id": "prompt",
      "name": "提示词",
      "type": "string",
      "required": true
    },
    {
      "id": "width",
      "name": "宽度",
      "type": "number",
      "default": 1024,
      "min": 512,
      "max": 2048
    }
  ],
  "stats": {
    "downloads": 2300,
    "rating": 4.9,
    "installStats": {
      "totalInstalls": 2300,
      "recentInstalls": 150
    }
  }
}
```

**执行流程**:

1. 接收执行请求和参数
2. 验证参数完整性（必填项、类型、范围）
3. 替换 workflow.json 中的参数占位符
4. 提交到 ComfyUI HTTP API (`/prompt`)
5. 返回 job_id 给客户端
6. 客户端轮询任务状态（或 WebSocket 推送）

**验收标准**:
- [ ] 列表 API 返回正确数据
- [ ] 详情 API 包含完整参数定义
- [ ] 执行 API 返回 job_id
- [ ] 任务状态 API 返回进度
- [ ] 收藏/取消收藏 API 正常工作

---

### 前端

**API 客户端**:

新增 workflowsApi，接口与 skillsApi 类似。

**验收标准**:
- [ ] API 客户端可调用
- [ ] 类型定义完整

---

## Day 3-4: Workflow 卡片和列表

### 页面布局

**Workflow 库页面**:

- 标题: "Workflow 模板库"
- 标签: 官方 | 市集 | 我的
- 卡片网格: 3 列布局

**卡片内容**:

- 预览图（顶部，16:9 比例）
- 收藏按钮（预览图右上角）
- 名称
- 评分 + 安装次数
- 详细描述（3-4行）
- 操作按钮: [运行] [⭐ 收藏]

**操作按钮统一命名**:

| 功能 | 按钮文字 | 说明 |
|------|----------|------|
| 执行 | **运行** | 打开参数编辑对话框 |
| 安装 | **安装** | 未安装状态显示 |
| 更新 | **更新** | 有更新状态显示 |
| 卸载 | **卸载** | 已安装状态，在详情页或菜单中 |
| 收藏 | **收藏** | 添加到收藏列表 |
| 取消收藏 | **取消收藏** | 从收藏列表移除 |
| 查看详情 | **详情** | 打开详情页 |

**验收标准**:
- [ ] 预览图正常加载
- [ ] 预览图加载前显示占位
- [ ] 收藏按钮状态正确
- [ ] 详细描述多行截断
- [ ] 操作按钮命名统一为"运行"

---

## Day 5: 参数编辑界面

### 参数类型支持

| 类型 | 控件 | 配置项 |
|------|------|--------|
| string | 输入框/文本域 | - |
| number | 滑块 + 数字输入 | min, max, step |
| enum | 下拉选择 | options |
| boolean | 复选框 | - |

### 执行对话框

**对话框内容**:
- 标题: "运行: {workflow_name}"
- 参数表单
- 进度区域（执行中显示）
- 按钮: [取消] [开始运行]

**参数表单布局**:

- 每个参数一行
- 标签: 参数名 + 必填标识
- 控件根据类型变化
- 描述文字（小字，灰色）

**完整执行流程**:

```
用户操作流程:

1. 浏览 Workflow 库
   ↓
2. 点击 Workflow 卡片上的 [运行] 按钮
   ↓
3. 弹出参数编辑对话框
   - 显示所有可配置参数
   - 默认值自动填充
   - 必填项验证提示
   ↓
4. 用户编辑参数
   - 修改提示词、调整滑块等
   - 实时验证输入有效性
   ↓
5. 点击 [开始运行]
   - 前端验证参数完整性
   - 提交到后端 /execute API
   - 后端转发给 ComfyUI
   ↓
6. 显示执行进度
   - 进度条实时更新
   - 状态文字显示
   - 预计剩余时间
   ↓
7. 执行完成
   - 成功: 显示输出图片，提供下载/查看
   - 失败: 显示错误信息
   ↓
8. 用户操作
   - 保存结果、重新运行、关闭对话框
```

**验收标准**:
- [ ] 所有参数类型可编辑
- [ ] 默认值正确填充
- [ ] 必填验证有效
- [ ] 滑块和数字输入联动
- [ ] 点击"运行"打开参数对话框

---

## Day 6-7: 执行和进度

### ComfyUI 集成

**HTTP API 提交**:

```python
# 提交 Workflow 到 ComfyUI
POST http://localhost:8188/prompt
Content-Type: application/json

{
  "prompt": { /* workflow JSON with parameters */ },
  "client_id": "artclaw-client-id"
}

# 响应
{
  "prompt_id": "uuid-string",
  "number": 123,
  "node_errors": {}
}
```

**任务状态更新机制（详细设计）**:

**方案选择**: WebSocket 实时推送（推荐）+ 轮询降级

```
┌─────────────────────────────────────────────────────────────────┐
│                    进度更新架构                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐      WebSocket       ┌─────────────────────┐  │
│  │   ComfyUI    │ ◄──────────────────► │  Tool Manager       │  │
│  │  (ws:8188)   │   实时推送进度        │  Server             │  │
│  └──────────────┘                      └──────────┬──────────┘  │
│         ▲                                         │             │
│         │                                         │ WebSocket   │
│         │ 轮询降级（WebSocket失败时）              │ 广播        │
│         │                                         ▼             │
│  ┌──────┴──────┐                      ┌─────────────────────┐  │
│  │  HTTP API   │ ◄──────────────────► │   Web Frontend      │  │
│  │  (/history) │   轮询获取状态        │   (React)           │  │
│  └─────────────┘                      └─────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**WebSocket 连接流程**:

1. **建立连接**:
   ```javascript
   // 前端连接到 Tool Manager WebSocket
   const ws = new WebSocket('ws://localhost:9876/ws');
   
   // 订阅任务频道
   ws.send(JSON.stringify({
     type: 'subscribe',
     channels: ['jobs', 'comfyui']
   }));
   ```

2. **提交任务**:
   ```python
   # 后端提交到 ComfyUI 时建立 ComfyUI WebSocket
   POST http://localhost:8188/prompt
   
   # 同时建立 ComfyUI WebSocket 监听
   ws_comfyui = websocket.connect('ws://localhost:8188/ws?clientId=artclaw-client-id')
   ```

3. **消息转发**:
   ```python
   # 后端转发 ComfyUI 消息到前端
   async def forward_comfyui_messages():
       async for message in ws_comfyui:
           # 解析 ComfyUI 消息
           data = json.loads(message)
           
           # 转换为统一格式
           if data['type'] == 'progress':
               progress = data['data']['value'] / data['data']['max'] * 100
               await broadcast_to_clients({
                   'type': 'job.progress',
                   'jobId': job_id,
                   'progress': progress,
                   'status': 'running',
                   'step': f"{data['data']['value']}/{data['data']['max']}"
               })
           elif data['type'] == 'executing':
               await broadcast_to_clients({
                   'type': 'job.status',
                   'jobId': job_id,
                   'status': 'executing',
                   'node': data['data']['node']
               })
           elif data['type'] == 'executed':
               await broadcast_to_clients({
                   'type': 'job.completed',
                   'jobId': job_id,
                   'outputs': data['data']['output']
               })
   ```

**消息类型定义**:

```typescript
// ComfyUI → Tool Manager (原始消息)
interface ComfyUIMessage {
  type: 'status' | 'progress' | 'executing' | 'executed' | 'execution_error';
  data: any;
}

// Tool Manager → Frontend (统一格式)
interface JobProgressMessage {
  type: 'job.progress';
  jobId: string;
  progress: number;        // 0-100
  status: 'queued' | 'running' | 'completed' | 'failed';
  step?: string;           // 如 "13/20"
  node?: string;           // 当前执行节点
  eta?: number;            // 预计剩余秒数
}

interface JobCompletedMessage {
  type: 'job.completed';
  jobId: string;
  outputs: {
    images?: Array<{filename: string, subfolder: string, type: string}>;
    text?: string[];
  };
}

interface JobFailedMessage {
  type: 'job.failed';
  jobId: string;
  error: string;
  node_errors?: Record<string, any>;
}
```

**轮询降级机制**:

当 WebSocket 连接失败时，自动降级为轮询:

```typescript
class JobProgressTracker {
  private ws: WebSocket | null = null;
  private pollInterval: number | null = null;
  
  async connect(jobId: string) {
    try {
      // 尝试 WebSocket
      this.ws = new WebSocket('ws://localhost:9876/ws');
      this.ws.onmessage = (e) => this.handleMessage(JSON.parse(e.data));
    } catch (err) {
      console.warn('WebSocket failed, falling back to polling');
      // 降级为轮询
      this.startPolling(jobId);
    }
  }
  
  startPolling(jobId: string) {
    this.pollInterval = window.setInterval(async () => {
      const res = await fetch(`/api/v1/workflows/jobs/${jobId}`);
      const data = await res.json();
      this.handleMessage(data);
      
      // 完成后停止轮询
      if (data.data.status === 'completed' || data.data.status === 'failed') {
        this.stopPolling();
      }
    }, 1000); // 1秒轮询间隔
  }
  
  stopPolling() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }
}
```

**API 端点**:

| 端点 | 方法 | 功能 | 说明 |
|------|------|------|------|
| `/api/v1/workflows/jobs/{id}` | GET | 获取任务状态 | 轮询使用 |
| `/ws` | WebSocket | 实时推送 | 推荐方式 |

**任务状态响应**:

```json
{
  "success": true,
  "data": {
    "jobId": "job-123",
    "status": "running",
    "progress": 65,
    "step": "13/20",
    "node": "KSampler_1",
    "outputs": null,
    "createdAt": "2026-04-10T10:00:00Z",
    "startedAt": "2026-04-10T10:00:05Z",
    "estimatedEndAt": "2026-04-10T10:02:00Z"
  }
}
```

### 进度显示

**执行状态**:
```
┌─────────────────────────────────────────────────────────┐
│ 运行中: SDXL 肖像摄影                            [✕]    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [████████████████████░░░░░░░░░░] 65%                   │
│                                                         │
│  状态: 采样中 (step 13/20)                              │
│  预计剩余: 15秒                                         │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  [取消运行]                                             │
└─────────────────────────────────────────────────────────┘
```

- 进度条: 0-100%
- 状态文字: 排队中 | 执行中 | 完成 | 失败
- 百分比数字
- 预计剩余时间

### 结果处理

- 成功: 显示输出图片/文件，提供下载
- 失败: 显示错误信息

**取消机制**:

```python
# 取消正在执行的任务
POST http://localhost:8188/interrupt

# 或清除队列
POST http://localhost:8188/queue
Content-Type: application/json

{"clear": true}
```

**注意**: 取消操作仅停止后续执行，已生成的中间结果可能保留。

**验收标准**:
- [ ] 执行可提交到 ComfyUI
- [ ] 进度实时更新（WebSocket 优先，轮询降级）
- [ ] WebSocket 连接自动建立和重连
- [ ] 消息格式统一，前端易于处理
- [ ] 成功显示结果
- [ ] 失败显示错误
- [ ] 取消可中断执行

---

## 错误处理

### ComfyUI 未连接处理

**场景**: 用户点击"运行"时 ComfyUI 未启动或未连接

**处理方式**:
1. 前端检测 ComfyUI 连接状态
2. 未连接时显示错误提示:
   ```
   ┌─────────────────────────────────────────┐
   │ 无法连接到 ComfyUI                      │
   ├─────────────────────────────────────────┤
   │                                         │
   │ 请确保 ComfyUI 已启动并运行在           │
   │ ws://localhost:8188                     │
   │                                         │
   │ [打开设置] [重试] [取消]                │
   │                                         │
   └─────────────────────────────────────────┘
   ```
3. 提供快捷入口打开设置页面配置 ComfyUI 地址

### 执行失败处理

**场景**: Workflow 提交后执行失败

**处理方式**:
1. 通过轮询/WebSocket 获取错误信息
2. 在对话框中显示错误详情:
   ```
   ┌─────────────────────────────────────────┐
   │ 执行失败                                │
   ├─────────────────────────────────────────┤
   │                                         │
   │ 错误: 节点 "KSampler" 执行失败          │
   │ 原因: 模型文件未找到: model.safetensors │
   │                                         │
   │ [查看详情] [重新运行] [关闭]            │
   │                                         │
   └─────────────────────────────────────────┘
   ```
3. 记录错误日志，便于排查

### 参数验证失败处理

**场景**: 用户提交的参数不符合要求

**处理方式**:
1. **前端验证**（即时反馈）:
   - 必填项为空时阻止提交，显示红色提示
   - 数值超出范围时显示警告
   - 字符串格式错误时提示

2. **后端验证**（二次确认）:
   ```json
   {
     "error": "VALIDATION_ERROR",
     "message": "参数验证失败",
     "details": [
       {"field": "prompt", "error": "不能为空"},
       {"field": "width", "error": "必须在 512-2048 之间"}
     ]
   }
   ```

3. 对话框中高亮显示错误字段

### 错误码规范

```typescript
enum WorkflowErrorCode {
  // 连接错误
  COMFYUI_NOT_CONNECTED = 'COMFYUI_NOT_CONNECTED',
  COMFYUI_CONNECTION_TIMEOUT = 'COMFYUI_CONNECTION_TIMEOUT',
  
  // 执行错误
  WORKFLOW_NOT_FOUND = 'WORKFLOW_NOT_FOUND',
  WORKFLOW_EXECUTION_FAILED = 'WORKFLOW_EXECUTION_FAILED',
  WORKFLOW_VALIDATION_ERROR = 'WORKFLOW_VALIDATION_ERROR',
  
  // 参数错误
  MISSING_REQUIRED_PARAMETER = 'MISSING_REQUIRED_PARAMETER',
  INVALID_PARAMETER_TYPE = 'INVALID_PARAMETER_TYPE',
  PARAMETER_OUT_OF_RANGE = 'PARAMETER_OUT_OF_RANGE',
  
  // 其他
  WORKFLOW_CANCELLED = 'WORKFLOW_CANCELLED',
  UNKNOWN_ERROR = 'UNKNOWN_ERROR'
}
```

---

## 验收标准汇总

### 功能验收
- [ ] Workflow 列表可展示
- [ ] 预览图正常加载
- [ ] 参数表单可编辑
- [ ] 执行可提交到 ComfyUI
- [ ] 进度可实时更新
- [ ] 收藏功能正常
- [ ] 安装/更新/卸载功能正常

### 集成验收
- [ ] Workflow 存储格式正确
- [ ] ComfyUI HTTP API 调用正常
- [ ] WebSocket 或轮询进度更新正常
- [ ] 最近使用记录正确

### 错误处理验收
- [ ] ComfyUI 未连接时友好提示
- [ ] 执行失败时显示错误详情
- [ ] 参数验证失败时高亮错误字段
- [ ] 取消操作可正常中断

---

## 下一步

Phase 5: DCC 内嵌面板
