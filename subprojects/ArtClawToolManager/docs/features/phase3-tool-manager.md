# Phase 3: 工具管理器

> 版本: 2.0
> 日期: 2026-04-10
> 工期: 2周
> 依赖: Phase 1-2

---

## 参考文档

- **架构设计**: [architecture-design.md](../specs/architecture-design.md)
- **UI 设计**: [ui-design.md](../ui/ui-design.md)
- **API 设计**: [api-design.md](../api/api-design.md)
- **统一工具管理器设计**: [artclaw-unified-tool-manager.md](../../../../docs/features/artclaw-unified-tool-manager.md)
- **市集基础设施**: 待补充（当前为本地文件存储）

---

## 目标

实现用户工具管理和创建功能。

**交付标准**:
- 工具列表管理（官方/市集/我的）
- 工具执行
- Tool Creator Skill（Agent 协助创建）
- 发布到市集功能
- 版本管理与回滚
- 批量操作支持（多选删除/发布）

---

## 核心概念

### Tool/Skill/Workflow 关系

```
ArtClaw 工具生态 - 三层概念模型
│
├── 【Skill】AI 操作指南（官方/市集）
│   ├── 定义: 指导 AI Agent 如何完成特定任务的文档
│   ├── 示例: comfyui-txt2img、ue57-material-node-edit
│   ├── 特点: 只读、文本形式、由 ArtClaw 或社区维护
│   └── 用途: 告诉 AI "如何"操作 DCC 软件
│
├── 【Workflow】ComfyUI 工作流模板
│   ├── 定义: ComfyUI 的 JSON 格式工作流
│   ├── 示例: SDXL 肖像摄影、产品渲染流程
│   ├── 特点: 可执行、可视化节点图、可参数化
│   └── 用途: 在 ComfyUI 中执行图像生成任务
│
└── 【Tool】用户创建的可复用功能单元
    ├── 定义: 用户包装 Skill 或编写脚本创建的快捷工具
    ├── 示例: 批量重命名、一键导出 FBX
    ├── 特点: 可执行、可配置参数、个人或分享
    └── 用途: 封装常用操作为一键执行的工具
```

**三者关系**:
- **Skill** → 指导 AI 如何操作（知识层）
- **Workflow** → ComfyUI 专用工作流（执行层 - 图像生成）
- **Tool** → 用户创建的快捷操作（执行层 - 通用 DCC 操作）

**Tool 与 Skill 的关系**:
- Tool 可以包装 Skill（将 Skill 封装为带参数的工具）
- Skill 是官方/市集维护的，Tool 是用户创建的
- Skill 告诉 AI "怎么做"，Tool 是 "一键执行"

---

## Week 1: 工具管理

### Day 1-2: Tool 数据模型 + API

### 后端

**API 规范**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/tools` | GET | 列表 |
| `/api/v1/tools/{id}` | GET | 详情 |
| `/api/v1/tools/{id}/execute` | POST | 执行 |
| `/api/v1/tools` | POST | 创建 |
| `/api/v1/tools/{id}` | PUT | 更新 |
| `/api/v1/tools/{id}` | DELETE | 删除 |
| `/api/v1/tools/{id}/publish` | POST | 发布 |
| `/api/v1/tools/{id}/versions` | GET | 版本列表 |
| `/api/v1/tools/{id}/versions/{version}` | POST | 回滚到指定版本 |

**Tool 数据模型**:

```json
{
  "id": "user/batch-rename",
  "name": "批量重命名",
  "type": "tool",
  "source": "user",
  "description": "批量重命名选中对象",
  "target_dccs": ["maya2024"],
  "implementation": {
    "type": "skill_wrapper",
    "skill": "maya2024-artclaw-highlight"
  },
  "inputs": [
    {
      "id": "prefix",
      "name": "前缀",
      "type": "string",
      "default": "SM_"
    }
  ],
  "outputs": [
    {
      "id": "renamed_count",
      "name": "重命名数量",
      "type": "number"
    }
  ],
  "stats": {
    "use_count": 12,
    "last_used": "2026-04-10T10:00:00Z"
  },
  "version": {
    "current": "1.0.0",
    "history": [
      {
        "version": "1.0.0",
        "created_at": "2026-04-10T10:00:00Z",
        "changelog": "初始版本"
      }
    ]
  }
}
```

**实现类型**:

| 类型 | 说明 |
|------|------|
| skill_wrapper | 包装现有 Skill |
| script | Python/JavaScript 脚本 |
| composite | 组合多个工具 |

**验收标准**:
- [ ] 列表 API 返回正确数据
- [ ] 详情 API 包含 inputs/outputs
- [ ] 创建 API 保存到 user 目录
- [ ] 版本 API 返回历史版本列表

---

### 前端

**工具卡片统一规范**:

所有工具卡片采用统一布局:
1. 标题行: 图标 + 名称 + 状态标签
2. 分隔线
3. 描述
4. 元信息
5. 操作按钮

**状态标签**:
- `[已安装 ✓]` 绿色
- `[可安装]` 灰色
- `[有更新 ↑]` 橙色

**元信息格式**:
- 官方/市集: `来源 · 版本 · 评分 · 下载量`
- 我的: `目标 · 上次使用 · 使用次数`

**操作按钮**（统一命名）:
- 官方/市集: [安装] [文档] [详情]
- 我的: [运行] [编辑] [发布] [卸载]

**验收标准**:
- [ ] 卡片布局统一
- [ ] 状态标签正确显示
- [ ] 操作按钮根据来源变化

---

### Day 3-4: 工具执行

### 后端

**执行流程**:

1. 接收 inputs 和 context
2. 根据 implementation.type 路由
3. 调用对应 DCC Adapter
4. 返回执行结果

**执行响应**:

```json
{
  "success": true,
  "data": {
    "outputs": {
      "renamed_count": 5
    },
    "execution_id": "exec-123",
    "duration": 1200
  }
}
```

**错误响应**:

```json
{
  "success": false,
  "error": {
    "code": "TOOL_EXECUTION_FAILED",
    "message": "执行失败：DCC 未连接",
    "details": {
      "dcc": "maya2024",
      "reason": "connection_timeout"
    }
  }
}
```

**验收标准**:
- [ ] skill_wrapper 类型可执行
- [ ] 参数正确传递
- [ ] 结果正确返回
- [ ] 错误信息清晰

---

### 前端

**执行对话框**:

- 标题: 工具名称
- 参数表单（根据 inputs 生成）
- 运行按钮
- 结果展示区域

**验收标准**:
- [ ] 参数表单根据定义生成
- [ ] 执行结果显示
- [ ] 错误信息显示

---

### Day 5-7: 工具创建向导

### 设计原则

- 界面仅提供入口和说明
- 创建过程由 Agent 通过对话完成
- 不实现复杂的可视化配置

### 界面设计

**创建工具页面**:

- 标题: "创建新工具"
- 创建方式选择:
  - 📦 包装 Skill
  - 📝 编写脚本
  - 🔗 组合工具
- 创建说明:
  - 点击后唤起 Agent
  - Agent 引导完成创建
- 按钮: [🤖 开始创建 - 唤起 Agent]

---

### Tool Creator Skill 详细设计

**Skill 名称**: `artclaw-tool-creator`

**触发方式**:
- 界面点击"开始创建"
- 发送消息给 Agent

#### 1. 创建方式选择

用户在界面选择以下方式之一：

| 方式 | 说明 | 适用场景 |
|------|------|----------|
| **包装 Skill** | 将现有 Skill 包装为带参数的工具 | 常用 Skill 需要固定参数 |
| **编写脚本** | 用 Python 编写自定义逻辑 | 复杂操作或组合多个功能 |
| **组合工具** | 将多个工具串联成工作流 | 多步骤自动化流程 |

#### 2. 界面 → Agent 的消息格式

```typescript
// 界面 → Agent
interface CreateToolRequest {
  type: 'create_tool';
  creationType: 'skill_wrapper' | 'script' | 'composite';
  context?: {
    selectedSkill?: string;      // 如果用户先选了 Skill
    targetDCC?: string;          // 当前选中的 DCC
  };
}
```

**实际发送的消息示例**:

```
我想创建一个工具，使用【包装 Skill】方式
当前 DCC: Maya 2024
```

#### 3. Agent 引导对话流程（多轮交互示例）

**示例 1: 包装 Skill 方式**

```
用户: 我想创建一个工具，使用【包装 Skill】方式
      当前 DCC: Maya 2024

Agent: 好的，我来帮你创建一个包装 Skill 的工具。

       首先，请描述你想要的功能：
       例如："批量重命名选中对象，添加前缀和编号"

用户: 批量导出选中的模型为 FBX，可以设置导出路径和是否包含材质

Agent: 明白了！你想创建一个 FBX 批量导出工具。

       我建议包装【maya-export-fbx】这个 Skill，它支持：
       - 选择对象导出
       - 设置导出路径
       - 材质导出选项
       
       让我为这个工具定义参数：
       
       1. export_path (文件夹) - 导出目录
       2. include_materials (布尔值) - 是否包含材质，默认 true
       3. file_prefix (字符串) - 文件名前缀，默认 ""
       
       你觉得这些参数合适吗？需要添加或修改吗？

用户: 再加一个 file_suffix 参数吧

Agent: 好的，已添加 file_suffix 参数。
       
       现在参数列表：
       1. export_path (文件夹) - 导出目录
       2. include_materials (布尔值) - 是否包含材质，默认 true
       3. file_prefix (字符串) - 文件名前缀，默认 ""
       4. file_suffix (字符串) - 文件名后缀，默认 ""
       
       请为这个工具起个名字：

用户: FBX 批量导出器

Agent: 完美！这是生成的工具定义：

       ─────────────────────────────────────────
       名称: FBX 批量导出器
       描述: 批量导出选中的 Maya 模型为 FBX 格式
       目标 DCC: Maya 2024
       
       参数:
       - export_path: 导出目录 (文件夹)
       - include_materials: 包含材质 (布尔值, 默认: true)
       - file_prefix: 文件名前缀 (字符串, 默认: "")
       - file_suffix: 文件名后缀 (字符串, 默认: "")
       
       实现: 包装 Skill [maya-export-fbx]
       ─────────────────────────────────────────
       
       [保存到我的工具] [测试运行] [继续修改]
```

**示例 2: 编写脚本方式**

```
用户: 我想创建一个工具，使用【编写脚本】方式
      当前 DCC: Maya 2024

Agent: 好的，我来帮你创建一个基于脚本的工具。
       
       请描述你想要的功能，越详细越好：

用户: 一键清理场景中的空组和无效材质，并输出清理报告

Agent: 明白了！这是一个场景清理工具。
       
       我来为你编写脚本并定义参数：
       
       建议参数：
       1. delete_empty_groups (布尔值) - 删除空组，默认 true
       2. delete_unused_materials (布尔值) - 删除未使用的材质，默认 true
       3. show_report (布尔值) - 显示详细报告，默认 true
       
       输出：
       - deleted_groups_count (数字) - 删除的空组数量
       - deleted_materials_count (数字) - 删除的材质数量
       
       你觉得这个设计如何？

用户: 可以，再加一个 dry_run 参数，先预览不实际删除

Agent: 好主意！已添加 dry_run 参数。
       
       这是生成的工具定义：
       
       ─────────────────────────────────────────
       名称: 场景清理助手
       描述: 一键清理场景中的空组和无效材质
       目标 DCC: Maya 2024
       
       参数:
       - delete_empty_groups: 删除空组 (布尔值, 默认: true)
       - delete_unused_materials: 删除未使用材质 (布尔值, 默认: true)
       - dry_run: 预览模式 (布尔值, 默认: false)
       - show_report: 显示报告 (布尔值, 默认: true)
       
       输出:
       - deleted_groups_count: 删除的空组数量 (数字)
       - deleted_materials_count: 删除的材质数量 (数字)
       
       实现: Python 脚本
       ─────────────────────────────────────────
       
       [保存到我的工具] [测试运行] [继续修改]
```

#### 4. 工具定义生成和确认

**Agent → 界面的消息格式**:

```typescript
// Agent → 界面
interface CreateToolResponse {
  type: 'tool_definition';
  tool: {
    name: string;
    description: string;
    targetDCCs: string[];
    implementation: ToolImplementation;
    inputs: ToolParameter[];
    outputs: ToolOutput[];
  };
  actions: ['save', 'test', 'modify'];
}
```

**工具定义确认界面**:

```
┌──────────────────────────────────────────────────────────────────────┐
│  工具定义预览                                                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  名称: FBX 批量导出器                                                 │
│  描述: 批量导出选中的 Maya 模型为 FBX 格式                             │
│  目标 DCC: Maya 2024                                                  │
│                                                                      │
│  参数:                                                               │
│  ┌───────────────┬───────────┬─────────────┬──────────────────────┐  │
│  │ 参数名         │ 类型      │ 默认值       │ 描述                 │  │
│  ├───────────────┼───────────┼─────────────┼──────────────────────┤  │
│  │ export_path   │ 文件夹    │ -           │ 导出目录             │  │
│  │ include_materials │ 布尔值 │ true        │ 是否包含材质         │  │
│  │ file_prefix   │ 字符串    │ ""          │ 文件名前缀           │  │
│  │ file_suffix   │ 字符串    │ ""          │ 文件名后缀           │  │
│  └───────────────┴───────────┴─────────────┴──────────────────────┘  │
│                                                                      │
│  实现方式: 包装 Skill [maya-export-fbx]                               │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  [💾 保存到我的工具]  [▶ 测试运行]  [✏ 继续修改]                     │
└──────────────────────────────────────────────────────────────────────┘
```

#### 5. 保存和测试

**保存流程**:

```
用户点击 [💾 保存到我的工具]
    │
    ▼
界面发送保存请求到后端
    │
    ▼
后端保存到 ~/.artclaw/tools/{tool_id}/
    - tool.json (工具定义)
    - script.py (如果是 script 类型)
    - version.json (版本信息)
    │
    ▼
刷新"我的工具"列表
显示成功提示: "工具已保存到【我的工具】"
```

**测试流程**:

```
用户点击 [▶ 测试运行]
    │
    ▼
打开执行对话框，预填生成的参数
    │
    ▼
用户填写参数并运行
    │
    ▼
执行并显示结果
    │
    ▼
用户确认: [保存] [返回修改]
```

**验收标准**:
- [ ] 界面可唤起 Agent
- [ ] Agent 可引导创建（多轮对话）
- [ ] 工具定义可预览
- [ ] 创建结果保存正确
- [ ] 支持测试运行

---

## Week 2: 发布与版本管理

### Day 1-3: 发布到市集

### 后端

**发布流程**:

1. 验证工具完整性
   - 检查 tool.json 完整性
   - 检查脚本文件存在（script 类型）
   - 检查依赖 Skill 是否已安装
2. 打包工具文件
3. 上传到市集服务器
4. 返回发布结果

**API**:

```
POST /api/v1/tools/{id}/publish
{
  "version": "1.0.0",
  "changelog": "初始版本",
  "tags": ["maya", "export", "fbx"],
  "visibility": "public"  // public | unlisted
}
```

**发布失败处理**:

```json
{
  "success": false,
  "error": {
    "code": "PUBLISH_FAILED",
    "message": "发布失败",
    "details": {
      "reason": "missing_dependency",
      "missing_skills": ["maya-export-fbx"]
    }
  }
}
```

**验收标准**:
- [ ] 发布前验证完整
- [ ] 发布后可在市集查看
- [ ] 版本号正确
- [ ] 发布失败提示清晰

---

### Day 4-5: 市集审核（可选）

**审核状态**:

- pending: 待审核
- approved: 已通过
- rejected: 已拒绝

**审核失败处理**:

```json
{
  "success": false,
  "error": {
    "code": "PUBLISH_REJECTED",
    "message": "审核未通过",
    "details": {
      "reason": "包含不安全代码",
      "suggestion": "请检查脚本中的文件操作"
    }
  }
}
```

**验收标准**:
- [ ] 发布后为 pending 状态
- [ ] 审核通过后显示
- [ ] 审核失败有详细原因

---

### Day 6-7: 版本管理

沿用 Skill 管理的版本逻辑：

**版本号规范**: 语义化版本 (SemVer)
- `MAJOR.MINOR.PATCH`
- 例如: `1.0.0`, `1.1.0`, `2.0.0`

**版本列表**:

```
GET /api/v1/tools/{id}/versions

Response:
{
  "versions": [
    {
      "version": "1.1.0",
      "created_at": "2026-04-15T10:00:00Z",
      "changelog": "添加 file_suffix 参数",
      "is_current": true
    },
    {
      "version": "1.0.0",
      "created_at": "2026-04-10T10:00:00Z",
      "changelog": "初始版本",
      "is_current": false
    }
  ]
}
```

**版本回滚机制**:

```
POST /api/v1/tools/{id}/versions/{version}

功能:
1. 将指定版本恢复为当前版本
2. 保留历史版本记录
3. 生成新版本号（如从 1.1.0 回滚到 1.0.0，生成 1.1.1）

Response:
{
  "success": true,
  "data": {
    "previous_version": "1.1.0",
    "restored_version": "1.0.0",
    "new_version": "1.1.1"
  }
}
```

**版本管理界面**:

```
┌──────────────────────────────────────────────────────────────────────┐
│  版本历史 - FBX 批量导出器                                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ v1.1.0 (当前)        2026-04-15                                │ │
│  │ 添加 file_suffix 参数                                           │ │
│  │                                                          [当前] │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ v1.0.0               2026-04-10                                │ │
│  │ 初始版本                                                        │ │
│  │                                                    [回滚到此版本] │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**验收标准**:
- [ ] 版本列表可查看
- [ ] 可回滚到旧版本
- [ ] 回滚后生成新版本号
- [ ] 版本变更历史完整

---

## 错误处理

### 工具执行失败处理

| 错误类型 | 错误码 | 处理方式 |
|----------|--------|----------|
| DCC 未连接 | `DCC_NOT_CONNECTED` | 提示用户连接 DCC，提供连接指引 |
| 参数验证失败 | `INVALID_PARAMS` | 高亮错误字段，显示具体错误信息 |
| Skill 未安装 | `SKILL_NOT_FOUND` | 提示安装依赖 Skill，提供安装按钮 |
| 执行超时 | `EXECUTION_TIMEOUT` | 提示超时，建议简化操作或检查 DCC 状态 |
| 执行异常 | `EXECUTION_ERROR` | 显示详细错误堆栈，提供重试按钮 |

**错误提示示例**:

```
┌─────────────────────────────────────────────────────────┐
│  ⚠️ 执行失败                                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  错误: DCC 未连接                                        │
│  代码: DCC_NOT_CONNECTED                                │
│                                                         │
│  Maya 2024 当前未连接，请确保：                          │
│  1. Maya 已启动                                          │
│  2. ArtClaw Maya 插件已加载                              │
│  3. 端口配置正确 (默认: 8086)                            │
│                                                         │
│  [查看连接指南]  [重试]  [取消]                          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 创建失败处理

| 错误类型 | 错误码 | 处理方式 |
|----------|--------|----------|
| 名称重复 | `NAME_EXISTS` | 提示更换名称，显示已有工具列表 |
| 参数定义无效 | `INVALID_PARAMS` | 返回修改，高亮无效参数 |
| 脚本语法错误 | `SCRIPT_ERROR` | 显示语法错误位置和原因 |
| 保存失败 | `SAVE_FAILED` | 提示磁盘空间或权限问题 |

### 发布失败处理

| 错误类型 | 错误码 | 处理方式 |
|----------|--------|----------|
| 验证失败 | `VALIDATION_FAILED` | 显示具体验证错误 |
| 依赖缺失 | `MISSING_DEPENDENCY` | 列出缺失的 Skill，提供安装链接 |
| 网络错误 | `NETWORK_ERROR` | 提示检查网络，提供重试按钮 |
| 审核拒绝 | `PUBLISH_REJECTED` | 显示拒绝原因和修改建议 |

---

## 验收标准汇总

### 功能验收
- [ ] 工具列表可展示
- [ ] 工具可执行
- [ ] 工具可创建（Agent 引导）
- [ ] 工具可发布
- [ ] 卡片布局统一
- [ ] 版本管理可用
- [ ] 版本回滚可用

### 集成验收
- [ ] Tool Creator Skill 可用
- [ ] 与 Agent 集成正常
- [ ] 错误处理完善

---

## 下一步

Phase 4: Workflow 库（ComfyUI）
