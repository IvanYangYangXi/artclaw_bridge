# Phase 3: Workflow 库

> 版本: 2.0
> 日期: 2026-04-10
> 工期: 1周
> 依赖: Phase 1-2

---

## 目标

实现 Workflow 模板管理和执行功能。

**交付标准**:
- Workflow 浏览/安装/收藏
- 预览图展示
- 参数编辑界面
- 执行接口（提交到 DCC）

---

## 与现有系统的集成

### Workflow 存储

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

### ComfyUI 集成

- Workflow JSON 格式兼容 ComfyUI
- 通过 HTTP API 提交执行
- 支持队列和进度查询

---

## Day 1-2: Workflow API

### 后端

**API 规范**:

| 端点 | 方法 | 功能 | 参数 |
|------|------|------|------|
| `/api/v1/workflows` | GET | 列表 | source, search, page, limit |
| `/api/v1/workflows/{id}` | GET | 详情 | - |
| `/api/v1/workflows/{id}/install` | POST | 安装 | - |
| `/api/v1/workflows/{id}/execute` | POST | 执行 | parameters, target_dcc |
| `/api/v1/workflows/jobs/{id}` | GET | 任务状态 | - |

**Workflow 数据模型**:

```json
{
  "id": "official/sdxl-portrait",
  "name": "SDXL 肖像摄影",
  "type": "workflow",
  "source": "official",
  "description": "专业肖像摄影风格",
  "detailed_description": "基于SDXL的高质量文生图工作流，支持高清修复...",
  "preview_image": "/api/v1/workflows/official/sdxl-portrait/preview",
  "target_dccs": ["comfyui"],
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
    "install_stats": {
      "total_installs": 2300,
      "recent_installs": 150
    }
  }
}
```

**执行流程**:

1. 接收参数
2. 替换 workflow.json 中的参数占位符
3. 提交到 ComfyUI
4. 返回 job_id
5. 客户端轮询任务状态

**验收标准**:
- [ ] 列表 API 返回正确数据
- [ ] 详情 API 包含完整参数定义
- [ ] 执行 API 返回 job_id
- [ ] 任务状态 API 返回进度

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
- 操作按钮: [使用] [收藏]

**验收标准**:
- [ ] 预览图正常加载
- [ ] 预览图加载前显示占位
- [ ] 收藏按钮状态正确
- [ ] 详细描述多行截断

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
- 标题: "执行: {workflow_name}"
- 参数表单
- 进度条（执行中显示）
- 按钮: [取消] [开始执行]

**参数表单布局**:

- 每个参数一行
- 标签: 参数名 + 必填标识
- 控件根据类型变化
- 描述文字（小字，灰色）

**验收标准**:
- [ ] 所有参数类型可编辑
- [ ] 默认值正确填充
- [ ] 必填验证有效
- [ ] 滑块和数字输入联动

---

## Day 6-7: 执行和进度

### 执行流程

1. 用户点击"使用"打开对话框
2. 填写参数，点击"开始执行"
3. 显示进度条和状态文字
4. 轮询任务状态（每秒）
5. 完成后显示结果或错误

### 进度显示

- 进度条: 0-100%
- 状态文字: 排队中 | 执行中 | 完成 | 失败
- 百分比数字

### 结果处理

- 成功: 显示输出图片/文件，提供下载
- 失败: 显示错误信息

**验收标准**:
- [ ] 执行可提交到 ComfyUI
- [ ] 进度实时更新
- [ ] 成功显示结果
- [ ] 失败显示错误
- [ ] 取消可关闭对话框

---

## 验收标准汇总

### 功能验收
- [ ] Workflow 列表可展示
- [ ] 预览图正常加载
- [ ] 参数表单可编辑
- [ ] 执行可提交到 ComfyUI
- [ ] 进度可实时更新
- [ ] 收藏功能正常

### 集成验收
- [ ] Workflow 存储格式正确
- [ ] ComfyUI 执行正常
- [ ] 最近使用记录正确

---

## 下一步

Phase 4: 工具管理器
