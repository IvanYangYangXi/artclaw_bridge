# ArtClaw Tool Manager - 架构设计文档

> 版本: 3.0
> 更新日期: 2026-04-10
> 说明: 移除 UI 部分，专注于架构和数据模型

---

## 1. 核心概念

### 1.1 概念定义

```
ArtClaw 工具生态 - 三层概念模型
│
├── 【Skill】AI 操作指南
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
- Skill → 指导 AI 如何操作（知识层）
- Workflow → ComfyUI 专用工作流（执行层 - 图像生成）
- Tool → 用户创建的快捷操作（执行层 - 通用 DCC 操作）

**执行路径**:
```
用户输入 → AI 读取 Skill → 生成操作指令 → DCC 执行
         ↓
用户点击 Workflow → 跳转对话面板 → AI 协助填写参数 → 执行
         ↓
用户点击 Tool → 跳转对话面板 → AI 协助填写参数 → 执行
```

### 1.2 工具分类体系

```
ArtClaw 工具生态 - 三层来源
│
├── 官方层（ArtClaw 维护）
│   ├── Official Skills
│   ├── Official Workflows (ComfyUI)
│   └── Official Tools
│
├── 市集层（社区）
│   ├── Marketplace Skills
│   ├── Marketplace Workflows (ComfyUI)
│   └── Marketplace Tools
│
└── 用户层（个人创建）
    ├── User Workflows (ComfyUI)
    └── User Tools
```

---

## 2. 整体架构

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                    ArtClaw Tool Manager                          │
│                   (Web 前端 + FastAPI 后端)                       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     对话面板 (核心)                        │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │   │
│  │  │  消息流区域  │  │ 右侧面板    │  │ 底部工具栏       │   │   │
│  │  │             │  │ • 参数表单  │  │ • 输入框        │   │   │
│  │  │ • 用户消息  │  │ • 最近使用  │  │ • 快捷按钮      │   │   │
│  │  │ • AI 回复   │  │             │  │                 │   │   │
│  │  │ • 工具调用  │  │             │  │                 │   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────┐  ┌──────────┐  │  ┌──────────┐  ┌──────────┐     │
│  │ Skills   │  │ Workflow │  │  │  Tools   │  │ Settings │     │
│  │ 管理界面  │  │ 管理界面  │──┘  │ 管理界面  │  │ 设置界面  │     │
│  └──────────┘  └──────────┘     └──────────┘  └──────────┘     │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   OpenClaw Gateway  │
                    │   (WebSocket/HTTP)  │
                    └─────────┬──────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ ~/.openclaw/    │ │ ~/.artclaw/     │ │   DCC Adapters  │
│   skills/       │ │   workflows/    │ │                 │
│                 │ │   tools/        │ │ • UE (ws:8080)  │
│ config.json     │ │                 │ │ • Maya(ws:8081) │
│  - pinned       │ │ config.json     │ │ • ComfyUI       │
│  - disabled     │ │  - favorites    │ │   (ws:8087)     │
│  - favorites    │ │  - recent       │ │ • ...           │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### 2.2 Workflow/Tool 执行流程（核心逻辑）

**新执行模式**：所有 Workflow 和 Tool 的执行都通过对话面板，由 AI 协助完成

```
┌─────────────────────────────────────────────────────────────────┐
│                    Workflow/Tool 执行流程                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 用户在 Workflow/Tool 页面点击 [运行]                          │
│     │                                                            │
│     ▼                                                            │
│  2. 系统自动跳转回【对话面板】                                     │
│     │                                                            │
│     ▼                                                            │
│  3. 自动发送消息给 AI：                                           │
│     "我想运行 Workflow 'SDXL 肖像摄影'，请帮我填写参数"            │
│     │                                                            │
│     ▼                                                            │
│  4. AI 回复，在【右侧面板】显示参数表单                             │
│     │                                                            │
│     ├── 用户手动填写参数 ──→ 点击 [执行]                          │
│     │                                                            │
│     └── 用户说"帮我填" ──→ AI 根据上下文自动填写 ──→ [执行]        │
│                                                                  │
│  5. 执行结果在消息流中显示                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**执行流程详细说明**:

| 步骤 | 动作 | 说明 |
|------|------|------|
| 1 | 用户点击 [运行] | 在 Workflow/Tool 管理页面 |
| 2 | 跳转对话面板 | 保持当前会话或新建会话 |
| 3 | 自动发送消息 | 格式: `/run workflow:{id}` 或 `/run tool:{id}` |
| 4 | AI 解析意图 | 识别为执行 Workflow/Tool 请求 |
| 5 | 右侧面板显示参数表单 | 根据 Workflow/Tool 定义动态生成 |
| 6 | 用户与 AI 协作填参 | 可手动填写，也可让 AI 根据对话上下文填写 |
| 7 | 用户确认执行 | 点击 [执行] 或告诉 AI "开始执行" |
| 8 | 发送执行命令到 DCC | 通过 MCP 调用对应 DCC 的 run_python/run_ue_python |
| 9 | 显示执行进度 | 在消息流中显示进度卡片 |
| 10 | 显示执行结果 | 成功/失败都在消息流中显示 |

**参数表单交互模式**:

```
右侧面板显示:
┌─────────────────────────────────────┐
│ 运行: SDXL 肖像摄影                  │
│ ─────────────────────────────────── │
│                                     │
│ 提示词 *                            │
│ ┌─────────────────────────────────┐ │
│ │ a beautiful portrait...         │ │  ← 用户可手动修改
│ └─────────────────────────────────┘ │
│                                     │
│ 宽度                                │
│ [====●========] 1024               │
│                                     │
│ [执行] [取消]                       │
│                                     │
│ 💡 你可以说"帮我填写参数"让 AI 协助   │
└─────────────────────────────────────┘
```

**AI 协助填参对话示例**:

```
用户: 我想运行 SDXL 肖像摄影

AI: 好的，我来帮你运行 SDXL 肖像摄影 Workflow。
    请填写以下参数（已在右侧面板显示）：
    
    1. 提示词：你想生成什么样的肖像？
    2. 宽度/高度：默认 1024x1024
    3. 是否启用高清修复？

用户: 生成一个商务风格的女性肖像，高清修复开启

AI: 明白了，我来帮你填写参数：
    • 提示词: "business style female portrait, professional..."
    • 宽度: 1024, 高度: 1024
    • 高清修复: 已开启
    
    请确认右侧面板的参数，然后点击 [执行] 或告诉我"开始执行"。

用户: 开始执行

AI: [开始执行 Workflow...]
    [显示进度...]
    [显示结果图片]
```

---

## 3. 数据模型

### 3.1 统一工具项接口

```typescript
interface ToolItem {
  id: string;                    // 唯一标识，格式: {source}/{name}
  name: string;                  // 显示名称
  description: string;           // 简短描述
  type: 'skill' | 'workflow' | 'tool';
  source: 'official' | 'marketplace' | 'user';
  targetDCCs: string[];          // ["ue57", "comfyui", "maya2024"]
  
  // 状态统一使用以下枚举
  status: 'not_installed' | 'installed' | 'update_available' | 'disabled';
  
  // 操作状态（运行时状态）
  runtimeStatus?: {
    enabled: boolean;            // 是否启用
    pinned: boolean;             // 是否钉选
    favorited: boolean;          // 是否收藏
  };
  
  stats: {
    downloads: number;
    rating: number;
    useCount: number;
    installStats?: {             // Skill/Workflow 专用
      totalInstalls: number;
      recentInstalls: number;
    };
  };
  
  data: SkillData | WorkflowData | ToolData;
}
```

### 3.2 类型特定数据

```typescript
// Skill 数据
interface SkillData {
  version: string;
  priority: number;              // 排序优先级
  entryPoints: string[];         // ["run_python", "run_ue_python"]
  skillPath: string;             // 本地路径
  dependencies?: string[];       // 依赖的其他 Skill
}

// Workflow 数据（ComfyUI 专用）
interface WorkflowData {
  previewImage: string;          // 预览图 URL
  parameters: WorkflowParameter[];  // 可配置参数
  description: string;           // 简短描述
  detailedDescription?: string;  // 详细描述
  workflowJson?: object;         // ComfyUI JSON
}

interface WorkflowParameter {
  id: string;
  name: string;
  type: 'string' | 'number' | 'boolean' | 'enum' | 'image';
  required: boolean;
  default?: any;
  min?: number;                  // number 类型
  max?: number;
  step?: number;
  options?: string[];            // enum 类型
  description?: string;          // 参数说明
}

// Tool 数据
interface ToolData {
  implementation: {
    type: 'skill_wrapper' | 'script' | 'composite';
    skill?: string;              // skill_wrapper 时指定
    code?: string;               // script 时指定
    tools?: string[];            // composite 时指定
  };
  inputs: ToolParameter[];
  outputs: ToolOutput[];
  lastUsed?: string;             // ISO 时间
  useCount: number;
}

interface ToolParameter {
  id: string;
  name: string;
  type: 'string' | 'number' | 'boolean' | 'enum' | 'file' | 'folder';
  required: boolean;
  default?: any;
  description?: string;
}

interface ToolOutput {
  id: string;
  name: string;
  type: 'string' | 'number' | 'boolean' | 'image' | 'file';
}
```

### 3.3 状态流转定义

```
Skill/Workflow/Tool 统一状态流转:

                    ┌─────────────┐
         ┌─────────►│  未安装     │◄────────┐
         │          │ not_installed│         │
         │          └──────┬──────┘         │
      卸载│                 │ 安装            │更新失败
         │                 ▼                │
         │          ┌─────────────┐         │
         └──────────┤   已安装    │─────────┘
                    │  installed  │
                    └──────┬──────┘
                           │ 检测到新版本
                           ▼
                    ┌─────────────┐
                    │  有更新     │
                    │update_available│
                    └──────┬──────┘
                           │ 更新
                           ▼
                    ┌─────────────┐
         ┌─────────►│   已禁用    │◄────────┐
         │          │  disabled   │         │
         │          └─────────────┘         │
      启用│                                   │禁用
         └───────────────────────────────────┘

注意:
- 禁用是独立状态，与安装状态正交
- 已禁用的工具仍可卸载
- 更新时保留禁用状态
```

---

## 4. 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | React + TypeScript + Tailwind | Web 界面 |
| 状态管理 | Zustand | 全局状态 |
| 后端 | FastAPI | REST API + WebSocket |
| 存储 | JSON 文件 + SQLite | 配置和缓存 |
| 通信 | HTTP/WebSocket | 与 DCC Adapters 通信 |
| 对话 | 集成 OpenClaw Gateway | 复用现有对话能力 |

---

## 5. 页面结构

| 页面 | 功能 | 标签 |
|------|------|------|
| **对话** | AI 对话面板（核心功能，Workflow/Tool 执行入口） | 单页面 |
| Skills | Skill 浏览/安装/管理 | 全部/官方/市集/我的 |
| Workflow 库 | ComfyUI Workflow 管理（运行按钮跳转对话面板） | 全部/官方/市集/我的 |
| 工具管理器 | 工具管理和创建（运行按钮跳转对话面板） | 全部/官方/市集/我的/创建 |
| 设置 | 系统配置 | 通用/高级 |

**导航结构**:
```
🔧 ArtClaw Tool Manager
│
├── 💬 对话 (核心入口 - Workflow/Tool 执行)
├── 📦 Skills
│   ├── 全部
│   ├── 官方
│   ├── 市集
│   └── 我的
├── 📋 Workflow 库 (ComfyUI)
│   ├── 全部
│   ├── 官方
│   ├── 市集
│   └── 我的
├── 🔧 工具管理器
│   ├── 全部
│   ├── 官方工具
│   ├── 市集工具
│   ├── 我的工具
│   └── 创建工具
└── ⚙️ 设置
```

---

## 6. 版本管理

**版本管理范围**: Skill、Workflow、Tool 统一使用相同的版本管理逻辑

### 6.1 版本号规范

- 采用语义化版本 (Semantic Versioning): `MAJOR.MINOR.PATCH`
- 示例: `1.2.3`
  - MAJOR: 不兼容的 API 变更
  - MINOR: 向后兼容的功能添加
  - PATCH: 向后兼容的问题修复

### 6.2 版本管理功能

| 功能 | 说明 |
|------|------|
| 版本检测 | 自动检测是否有新版本可用 |
| 版本历史 | 查看所有历史版本列表 |
| 版本回滚 | 回滚到指定历史版本 |
| 版本对比 | 对比不同版本的差异 |

### 6.3 版本存储

```
~/.artclaw/
├── skills/
│   └── {source}/
│       └── {skill-name}/
│           ├── v1.0.0/          # 版本目录
│           ├── v1.1.0/
│           └── current -> v1.1.0  # 符号链接指向当前版本
├── workflows/
│   └── {source}/
│       └── {workflow-name}/
│           ├── v1.0.0/
│           ├── v1.2.0/
│           └── current -> v1.2.0
└── tools/
    └── {source}/
        └── {tool-name}/
            ├── v1.0.0/
            └── current -> v1.0.0
```

---

## 7. 项目结构

```
ArtClawToolManager/
├── docs/
│   ├── specs/
│   │   ├── architecture-design.md   # 本文件
│   │   ├── ui-design.md             # UI 详细设计
│   │   ├── api-design.md            # API 规范
│   │   └── data-models.md           # 数据模型详细定义
│   └── features/                    # Phase 详细文档
│       ├── phase0-technical-research.md
│       ├── phase1-foundation.md
│       ├── phase2-skill-management.md
│       ├── phase3-workflow-library.md
│       ├── phase4-tool-manager.md
│       └── phase5-dcc-integration.md
├── src/
│   ├── web/                         # React 前端
│   │   ├── components/              # 通用组件
│   │   ├── pages/                   # 页面
│   │   │   ├── Chat/                # 对话面板（核心）
│   │   │   ├── Skills/
│   │   │   ├── Workflows/
│   │   │   ├── Tools/
│   │   │   └── Settings/
│   │   ├── stores/                  # Zustand 状态
│   │   └── api/                     # API 客户端
│   ├── server/                      # FastAPI 后端
│   │   ├── api/                     # API 路由
│   │   ├── services/                # 业务逻辑
│   │   ├── models/                  # 数据模型
│   │   └── websocket/               # WebSocket 处理
│   └── dcc-panels/                  # DCC 内嵌面板
│       ├── ue/
│       ├── maya/
│       └── comfyui/
└── README.md
```

---

## 8. 实施阶段

| 阶段 | 内容 | 工期 | 优先级 |
|------|------|------|--------|
| Phase 0 | 技术预研（DCC通信方案验证） | 3-5天 | P0 |
| Phase 1 | 基础框架（Server + Web）+ 对话面板 | 3周 | P0 |
| Phase 2 | Skill 管理完整功能 | 1周 | P0 |
| Phase 3 | Workflow 库（含AI协助执行流程） | 1周 | P1 |
| Phase 4 | 工具管理器 + Tool Creator | 2周 | P0 |
| Phase 5 | DCC 内嵌面板 | 2-3周 | P1 |

**调整说明**:
- Phase 1 增加对话面板（大需求）
- Phase 3 Workflow 执行流程改为 AI 协助模式
- Phase 4 工具执行同样采用 AI 协助模式
- Phase 5 工期增加（3个DCC面板）

---

## 9. 参考文档

- **UI 设计**: [ui-design.md](./ui-design.md)
- **API 设计**: [api-design.md](./api-design.md)
- **OpenClaw Gateway**: [gateway-forwarding-roadmap.md](../../../../docs/features/gateway-forwarding-roadmap.md)
- **ComfyUI MCP 集成**: [comfyui-mcp-integration.md](../../../../docs/features/comfyui-mcp-integration.md)

---

## 10. 更新记录

### v3.0 (2026-04-10)
- 移除 UI 部分，专注于架构和数据模型
- 重新定义 Workflow/Tool 执行流程（AI 协助模式）
- 明确版本管理范围（Skill/Workflow/Tool 统一）
- 调整 Phase 顺序（Workflow 前置）

### v2.0 (2026-04-10)
- 明确 Skill/Workflow/Tool 概念定义和关系
- 添加对话面板架构设计
- 细化状态流转图
- 细化工具创建流程

### v1.0 (2026-04-10)
- 初始版本
