# ArtClaw 统一工具管理器设计

> 整合 Workflow 模板库、Skill 管理、MCP 工具管理、用户工具管理的统一入口
> 版本: 1.0
> 日期: 2026-04-10

---

## 1. 核心概念定义

### 1.1 工具分类体系

```
ArtClaw 工具生态
│
├── 系统层（框架内置）
│   ├── MCP 工具（run_python / run_ue_python）
│   └── 核心服务（bridge_core, mcp_server）
│
├── 官方层（ArtClaw 维护）
│   ├── Official Skills（comfyui-txt2img, maya-operation-rules...）
│   ├── Official Workflows（官方 workflow 模板）
│   └── Official Tools（安装器、修复器等基础设施）
│
├── 市集层（社区/团队）
│   ├── Marketplace Skills（civitai, video...）
│   ├── Marketplace Workflows（社区分享模板）
│   └── Marketplace Tools（第三方工具）
│
└── 用户层（个人创建）
    ├── User Skills（个人开发的 skill）
    ├── User Workflows（个人 workflow 库）
    └── User Tools（通过 Tool Builder 创建的工具）
```

### 1.2 什么是"用户工具"（User Tool）

**定义**: 用户通过可视化界面或代码创建的可复用功能单元，可以：
- 封装一系列操作（如"一键设置渲染参数"）
- 调用 DCC API、Skill API、或其他工具
- 有输入参数和输出结果
- 可以在不同 DCC 间共享（如果兼容）

**示例用户工具**:
```yaml
# 用户创建的"批量重命名"工具
name: 批量重命名Actor
icon: 🔤
category: UE/场景管理
target_dcc: [ue57]  # 可在哪些 DCC 运行
inputs:
  - name: prefix
    type: string
    default: "SM_"
  - name: selected_only
    type: bool
    default: true

# 工具实现（可以是多种方式）
implementation:
  type: skill_wrapper  # 包装现有 skill
  skill: ue57-artclaw-highlight
  code: |
    from ue57_artclaw_highlight import batch_rename
    batch_rename(prefix=inputs.prefix, selected_only=inputs.selected_only)
```

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        统一工具管理器 (Unified Tool Manager)                  │
│                              入口: 网页 / VS Code 插件 / DCC 内嵌面板          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│   Skill 管理   │           │  Workflow 库  │           │  工具管理器   │
│   (Skill Hub)  │           │  (Template   │           │  (Tool       │
│                │           │   Library)   │           │   Manager)   │
├───────────────┤           ├───────────────┤           ├───────────────┤
│ • 浏览/搜索   │           │ • 发现模板   │           │ • 官方工具   │
│ • 安装/更新   │           │ • 执行/编辑  │           │ • 市集工具   │
│ • 启用/禁用   │           │ • 收藏/管理  │           │ • 我的工具   │
│ • 发布分享   │           │ • 发布分享   │           │ • 创建工具   │
└───────┬───────┘           └───────┬───────┘           └───────┬───────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    ▼
                    ┌───────────────────────────────┐
                    │      工具运行时 (Tool Runtime)  │
                    │  • 环境检测（当前 DCC）         │
                    │  • 依赖解析（需要什么环境）      │
                    │  • 执行调度（本地/远程/容器）    │
                    │  • 结果返回                    │
                    └───────────────────────────────┘
```

### 2.2 技术选型：网页 vs 桌面 vs DCC 内嵌

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **Web 网页** ✅ 推荐 | 跨平台、易更新、可远程访问、UI 灵活 | 需要单独窗口 | 主管理界面 |
| **VS Code 插件** | 开发者友好、与代码编辑整合 | 非开发者不友好 | 开发者可选 |
| **DCC 内嵌面板** | 与 DCC 工作流无缝整合 | 每个 DCC 单独实现、维护成本高 | DCC 内快捷操作 |
| **桌面应用** | 独立性强 | 需要单独安装、跨平台问题 | 不推荐 |

**推荐架构**: **Web 为主 + DCC 内嵌快捷入口**

```
用户操作路径:

1. 主管理: 浏览器打开 https://tools.artclaw.local (或 localhost)
   → 完整的 Skill/Workflow/Tool 管理
   
2. DCC 快捷: 在 UE/Maya/ComfyUI 中点击"工具管理器"按钮
   → 打开简化版面板（或唤起浏览器）
   → 显示当前 DCC 相关的工具和 workflow
```

---

## 3. 详细设计

### 3.1 统一数据模型

所有可管理项（Skill、Workflow、Tool）共享统一的数据模型：

```typescript
// 统一工具项接口
interface ToolItem {
  // 基础信息
  id: string;                    // 唯一标识: "official/comfyui-txt2img"
  name: string;                  // 显示名称
  description: string;           // 描述
  icon: string;                  // 图标 URL 或 emoji
  
  // 分类信息
  type: 'skill' | 'workflow' | 'tool';  // 类型
  category: string;              // 功能分类: "生成/编辑/管理..."
  tags: string[];                // 标签: ["sdxl", "portrait", "official"]
  
  // 来源与层级
  source: 'official' | 'marketplace' | 'user' | 'team';
  author: string;                // 作者
  version: string;               // 版本
  
  // 目标环境
  targetDCCs: string[];          // ["ue57", "maya2024", "comfyui"]
  targetPlatforms: string[];     // ["windows", "macos", "linux"]
  
  // 依赖关系
  dependencies: {
    skills?: string[];           // 依赖的其他 skill
    nodes?: string[];            // ComfyUI 节点依赖
    models?: string[];           // 模型依赖
    tools?: string[];            // 依赖的其他工具
  };
  
  // 状态
  status: 'not_installed' | 'installed' | 'update_available' | 'disabled';
  installPath?: string;          // 本地安装路径
  
  // 统计
  stats: {
    downloads: number;             // 下载/安装次数
    rating: number;               // 评分 0-5
    ratingCount: number;          // 评分人数
    lastUsed?: Date;              // 最后使用时间
    useCount: number;             // 使用次数
    
    // 安装统计（Skill/Workflow 专用）
    installStats?: {
      totalInstalls: number;      // 总安装次数
      recentInstalls: number;     // 近30天安装
      lastInstalledAt?: Date;     // 最后安装时间
    };
  };
  
  // 元数据
  createdAt: Date;
  updatedAt: Date;
  
  // 类型特定数据
  data: SkillData | WorkflowData | ToolData;
}

// Skill 特有数据
interface SkillData {
  priority: number;              // 匹配优先级
  entryPoints: string[];         // 入口点: ["run_python", "API"]
  apiReference: string;          // API 文档
}

// Workflow 特有数据
interface WorkflowData {
  previewImage: string;          // 预览图
  parameters: Parameter[];       // 可调参数
  templateJson: object;          // 模板 JSON
  
  // 详细描述（支持 Markdown）
  description: string;           // 简短描述（列表展示）
  detailedDescription?: string;   // 详细描述（展开/详情页）
  
  // 安装统计
  installStats: {
    totalInstalls: number;       // 总安装次数
    recentInstalls: number;      // 近30天安装
    lastInstalledAt?: Date;      // 最后安装时间
  };
}

// Tool 特有数据
interface ToolData {
  implementation: {
    type: 'skill_wrapper' | 'script' | 'workflow' | 'composite';
    code?: string;               // 代码/配置
    entryPoint?: string;         // 入口函数
  };
  inputs: Parameter[];           // 输入参数
  outputs: Parameter[];          // 输出参数
}
```

### 3.2 网页界面设计

#### 整体布局

```
┌──────────────────────────────────────────────────────────────────────┐
│  🔧 ArtClaw Tool Manager                    [搜索...] [👤 User] [⚙️]  │
├──────────┬───────────────────────────────────────────────────────────┤
│          │                                                           │
│  📦 总览  │   欢迎回来，Ivan                                          │
│  ────────│   最近使用: comfyui-txt2img, maya-batch-export...          │
│          │   快捷操作: [文生图] [批量导出] [安装节点]                 │
│  🎯 Skills│                                                           │
│  ────────│   ┌─────────────────────────────────────────────────────┐ │
│  📋 Work- │   │  推荐工具                                            │ │
│     flows │   │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │ │
│  ────────│   │  │ 🎨 SDXL  │ │ 🎬 Video │ │ 🎭 3D    │            │ │
│          │   │  │ 文生图   │ │ 生成     │ │ 生成     │            │ │
│  🔧 Tools │   │  └──────────┘ └──────────┘ └──────────┘            │ │
│  ────────│   └─────────────────────────────────────────────────────┘ │
│          │                                                           │
│  📊 统计  │                                                           │
│  ────────│                                                           │
│          │                                                           │
│  ⚙️ 设置  │                                                           │
│          │                                                           │
└──────────┴───────────────────────────────────────────────────────────┘
```

#### Skills 管理页

```
┌──────────────────────────────────────────────────────────────────────┐
│  Skills                                                              │
│  ─────────────────────────────────────────────────────────────────── │
│                                                                      │
│  [全部 ▼] [官方 ▼] [ComfyUI ▼] [已安装 ▼]        [🔍 搜索...]        │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  comfyui-txt2img                                    [已安装 ✓] │  │
│  │  ───────────────────────────────────────────────────────────  │  │
│  │  🎨 ComfyUI 文生图标准流程                                     │  │
│  │  官方 · ComfyUI · v0.1.0 · ⭐ 4.8 · 📥 1.2k                   │  │
│  │  [使用] [文档] [更新] [禁用]                                   │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  comfyui-video-generation                           [可安装]   │  │
│  │  ───────────────────────────────────────────────────────────  │  │
│  │  🎬 视频生成工作流                                             │  │
│  │  市集 · ComfyUI · v1.0.0 · ⭐ 4.5 · 📥 856                    │  │
│  │  [安装] [预览] [详情]                                          │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

#### Workflow 库页

```
┌──────────────────────────────────────────────────────────────────────┐
│  Workflow 模板库                                                      │
│  ─────────────────────────────────────────────────────────────────── │
│                                                                      │
│  [官方] [市集] [我的]                                                │
│                                                                      │
│  分类: [全部 ▼] [文生图 ▼] [写实 ▼] [动漫 ▼]        [🔍 搜索...]      │
│                                                                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                 │
│  │ [预览图]     │ │ [预览图]     │ │ [预览图]     │                 │
│  │              │ │              │ │              │                 │
│  │ SDXL 标准版  │ │ 动漫风格     │ │ 肖像摄影     │                 │
│  │ ⭐ 4.9  📥2.3k│ │ ⭐ 4.7  📥856 │ │ ⭐ 4.8  📥1.1k│                 │
│  │              │ │              │ │              │                 │
│  │ 基于SDXL的   │ │ 适合二次元   │ │ 专业肖像     │                 │
│  │ 高质量文生图 │ │ 风格的文生图 │ │ 摄影风格     │                 │
│  │ 工作流，支持 │ │ 工作流，内置 │ │ 工作流，内置 │                 │
│  │ 高清修复...  │ │ 多种风格...  │ │ 美颜和...    │                 │
│  │              │ │              │ │              │                 │
│  │ [使用] [⭐]  │ │ [使用] [⭐]  │ │ [使用] [⭐]  │                 │
│  └──────────────┘ └──────────────┘ └──────────────┘                 │
│                                                                      │
│  ─── 我的 Workflow ───                                               │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  📝 产品渲染流程                                                  │
│  │     专为电商产品渲染优化的 ComfyUI 工作流                         │
│  │     上次使用: 2小时前  使用次数: 47                               │
│  │     [使用] [编辑] [发布] [删除]                                   │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

#### 工具管理器页

```
┌──────────────────────────────────────────────────────────────────────┐
│  工具管理器                                                           │
│  ─────────────────────────────────────────────────────────────────── │
│                                                                      │
│  [官方工具] [市集工具] [我的工具] [创建工具]                          │
│                                                                      │
│  ─── 官方工具 ───                                                    │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  🔧 节点安装器                                      [已安装 ✓]  │  │
│  │  ───────────────────────────────────────────────────────────  │  │
│  │  自动检测并安装缺失的 ComfyUI 自定义节点                         │  │
│  │  官方 · v1.2.0 · ⭐ 4.9 · 📥 5.2k                              │  │
│  │  [打开] [文档] [禁用]                                           │  │
│  └────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  🔧 Workflow 修复器                                 [可安装]   │  │
│  │  ───────────────────────────────────────────────────────────  │  │
│  │  诊断并修复损坏的 workflow                                       │  │
│  │  官方 · v0.8.0 · ⭐ 4.6 · 📥 3.1k                              │  │
│  │  [安装] [预览] [详情]                                           │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ─── 我的工具 ───                                                    │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  ⚡ 批量导出 FBX                                                │  │
│  │  ───────────────────────────────────────────────────────────  │  │
│  │  一键导出选中模型为 FBX                                          │  │
│  │  目标: Maya 2024 · 上次使用: 2天前 · 使用次数: 12               │  │
│  │  [运行] [编辑] [发布] [删除]                                    │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  [+ 创建新工具]                                                      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**面板统一规范**：
- 所有工具卡片采用统一布局：标题行（名称+状态）→ 分隔线 → 描述 → 元信息 → 操作按钮
- 状态标签统一：`[已安装 ✓]` `[可安装]` `[有更新 ↑]` `[已禁用]`
- 元信息格式统一：`来源 · 版本 · 评分 · 下载量`（官方/市集）或 `目标 · 上次使用 · 使用次数`（我的）
- 操作按钮统一：官方/市集工具 `[安装/打开] [文档/预览] [禁用/详情]`；我的工具 `[运行] [编辑] [发布] [删除]`

#### 工具创建向导（简化版）

工具创建过程由 Agent 协助完成，界面仅提供入口和简单说明。

```
┌──────────────────────────────────────────────────────────────────────┐
│  创建新工具                                                           │
│  ─────────────────────────────────────────────────────────────────── │
│                                                                      │
│  选择创建方式：                                                       │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐           │
│  │  📦 包装 Skill │  │  📝 编写脚本   │  │  🔗 组合工具   │           │
│  │                │  │                │  │                │           │
│  │ 将现有 Skill   │  │ 用 Python 编写 │  │ 将多个工具     │           │
│  │ 包装为可复用   │  │ 自定义工具逻辑 │  │ 组合成工作流   │           │
│  │ 工具           │  │                │  │                │           │
│  └────────────────┘  └────────────────┘  └────────────────┘           │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  💡 创建说明                                                          │
│                                                                      │
│  点击上方选项后，AI Agent 将引导你完成工具创建：                        │
│                                                                      │
│  1. 描述你想要的功能（如"批量导出选中的模型为FBX"）                    │
│  2. Agent 会自动选择合适的 Skill 或编写代码                           │
│  3. 定义参数和界面（名称、类型、默认值）                              │
│  4. 测试并保存到你的工具库                                           │
│                                                                      │
│  你也可以直接告诉 Agent：                                              │
│  "创建一个工具，用 comfyui-txt2img 生成图片后自动高清修复"              │
│                                                                      │
│  [🤖 开始创建 - 唤起 Agent]                                          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**实现方式**：
- 工具创建向导本身是一个 Skill：`artclaw-tool-creator`
- 界面点击"开始创建"后，发送消息给 Agent 触发 Skill
- Agent 通过对话交互完成工具定义、代码生成、测试验证
- 最终结果保存到用户工具库

### 3.3 DCC 内嵌快捷面板

在 DCC 中提供简化版入口：

```
┌────────────────────────────────────┐
│  🔧 ArtClaw 工具                    │
├────────────────────────────────────┤
│                                    │
│  最近使用                          │
│  ┌────────┐ ┌────────┐            │
│  │ 🎨     │ │ 📦     │            │
│  │ 文生图 │ │ 导出   │            │
│  └────────┘ └────────┘            │
│                                    │
│  常用工具                          │
│  ├─ 🔧 节点安装器                  │
│  ├─ 🔧 Workflow 修复器             │
│  ├─ ⚡ 批量重命名                  │
│  └─ ...                            │
│                                    │
│  [打开完整管理器 →]                │
│                                    │
└────────────────────────────────────┘
```

---

## 4. 技术实现

### 4.1 架构组件

```
artclaw-tool-manager/                    # 独立项目
├── web/                                 # Web 前端 (React/Vue)
│   ├── src/
│   │   ├── components/                  # UI 组件
│   │   ├── pages/                       # 页面
│   │   │   ├── SkillsPage.tsx
│   │   │   ├── WorkflowsPage.tsx
│   │   │   ├── ToolsPage.tsx
│   │   │   └── ToolBuilderPage.tsx
│   │   ├── stores/                      # 状态管理
│   │   │   ├── skillStore.ts
│   │   │   ├── workflowStore.ts
│   │   │   └── toolStore.ts
│   │   └── api/                         # API 客户端
│   │       └── artclawApi.ts
│   └── package.json
│
├── server/                              # 后端服务 (Python/FastAPI)
│   ├── app/
│   │   ├── api/                         # REST API
│   │   │   ├── skills.py
│   │   │   ├── workflows.py
│   │   │   └── tools.py
│   │   ├── services/                    # 业务逻辑
│   │   │   ├── skill_service.py
│   │   │   ├── workflow_service.py
│   │   │   └── tool_runtime.py          # 工具执行引擎
│   │   └── models/                      # 数据模型
│   │       └── schemas.py
│   └── requirements.txt
│
├── dcc-panels/                          # DCC 内嵌面板
│   ├── ue/
│   │   └── ArtClawToolPanel.cpp         # UE Slate 面板
│   ├── maya/
│   │   └── artclaw_tool_panel.py        # Maya Qt 面板
│   └── comfyui/
│       └── tool_manager_button.js       # ComfyUI 按钮扩展
│
└── shared/                              # 共享代码
    └── types/                           # TypeScript/Python 共享类型
```

### 4.2 与现有系统的集成

```
┌─────────────────────────────────────────────────────────────────┐
│                    ArtClaw Tool Manager                         │
│                         (Web 界面)                               │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/WebSocket
┌────────────────────────────▼────────────────────────────────────┐
│              Tool Manager Server (Python)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Skill API   │  │ Workflow API│  │ Tool Runtime API        │  │
│  │             │  │             │  │                         │  │
│  │ • 扫描目录  │  │ • CRUD 模板 │  │ • 环境检测              │  │
│  │ • 安装/更新 │  │ • 执行 workflow│ │ • 依赖解析              │  │
│  │ • 发布分享  │  │ • 版本管理  │  │ • 调度执行              │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────────┘  │
└─────────┼────────────────┼────────────────────┼─────────────────┘
          │                │                    │
          ▼                ▼                    ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────────────────┐
│ ~/.openclaw/    │ │ Workflow     │ │ DCC Adapters             │
│   skills/       │ │   Store      │ │                          │
│                 │ │              │ │ • UE Adapter (ws:8080)   │
│ • official/     │ │ • official/  │ │ • Maya Adapter (ws:8081) │
│ • marketplace/  │ │ • marketplace│ │ • ComfyUI (ws:8087)      │
│ • user/         │ │ • user/      │ │ • ...                    │
└─────────────────┘ └──────────────┘ └──────────────────────────┘
```

### 4.3 工具运行时（Tool Runtime）

**核心职责**: 管理工具的执行环境

```python
class ToolRuntime:
    """工具执行运行时"""
    
    def execute(self, tool: ToolItem, inputs: dict, context: ExecutionContext):
        """执行工具"""
        
        # 1. 环境检测
        target_dcc = tool.targetDCCs[0]  # 主要目标 DCC
        available_dccs = self.detect_available_dccs()
        
        if target_dcc not in available_dccs:
            return {
                "success": False,
                "error": f"需要 {target_dcc}，但未检测到运行中的实例",
                "suggestion": f"请启动 {target_dcc} 后重试"
            }
        
        # 2. 依赖检查
        deps_check = self.check_dependencies(tool, target_dcc)
        if not deps_check["ok"]:
            return {
                "success": False,
                "error": "缺少依赖",
                "missing_deps": deps_check["missing"]
            }
        
        # 3. 路由到对应 DCC 执行
        adapter = self.get_adapter(target_dcc)
        
        if tool.data.implementation.type == "skill_wrapper":
            result = adapter.execute_skill_wrapper(tool, inputs)
        elif tool.data.implementation.type == "script":
            result = adapter.execute_script(tool, inputs)
        elif tool.data.implementation.type == "workflow":
            result = adapter.execute_workflow(tool, inputs)
        
        return result
    
    def detect_available_dccs(self) -> list:
        """检测当前可用的 DCC 实例"""
        dccs = []
        # 检查各 DCC 的 MCP Server 是否可连接
        for dcc in ["ue57", "maya2024", "comfyui", "sd"]:
            if self.ping_dcc(dcc):
                dccs.append(dcc)
        return dccs
```

---

## 5. 用户工具的创建方式

### 5.1 方式1: 包装现有 Skill（最简单）

适合: 将常用的 Skill 调用封装为带参数的工具

### 5.2 方式2: 可视化 Workflow 编排

适合: 组合多个工具形成工作流

```
┌──────────────────────────────────────────────────────────────────────┐
│  可视化工具编排器                                                     │
│                                                                      │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐                   │
│  │ 选择模型 │ ───→ │ 文生图   │ ───→ │ 高清修复 │                   │
│  │          │      │          │      │          │                   │
│  └──────────┘      └──────────┘      └──────────┘                   │
│       │                 │                 │                         │
│       ▼                 ▼                 ▼                         │
│   [下拉选择]        [提示词输入]       [放大倍数]                     │
│                                                                      │
│  [+ 添加节点]  [保存为工具]                                          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.3 方式3: 代码编写

适合: 复杂逻辑、需要条件判断

支持语言:
- Python (用于 DCC 操作)
- JavaScript (用于 Web/数据处理)

---

## 6. 部署与访问

### 6.1 本地部署（开发/个人使用）

```bash
# 启动 Tool Manager Server
python -m artclaw_tool_manager.server

# 默认访问
open http://localhost:9876
```

### 6.2 集成到 OpenClaw Gateway

```
OpenClaw Gateway
├── mcp-bridge/          # 现有
├── openclaw-bridge/     # 现有
└── tool-manager/        # 新增
    ├── web/             # 静态文件
    └── server/          # API 服务
```

访问: `http://gateway-host:18789/tools`

### 6.3 DCC 快捷入口

| DCC | 入口方式 |
|-----|----------|
| UE | 菜单栏: Tools → ArtClaw Tool Manager |
| Maya | 菜单: ArtClaw → Tool Manager |
| ComfyUI | 侧边栏按钮 |
| SD | 菜单栏按钮 |

---

## 7. 实施建议

### Phase 1: 基础框架（2周）
- [ ] Tool Manager Server 基础架构
- [ ] Web 前端框架
- [ ] 与现有 Skill 系统的集成

### Phase 2: Skill 管理（1周）
- [ ] Skill 浏览/安装/更新 UI
- [ ] 与现有 skill_hub 的对接

### Phase 3: Workflow 库（1周）
- [ ] Workflow 模板管理
- [ ] 执行和版本控制

### Phase 4: 工具管理器（2周）
- [ ] 官方工具集成
- [ ] 用户工具列表管理
- [ ] 工具运行时
- [ ] `artclaw-tool-creator` Skill（工具创建助手）

### Phase 5: DCC 集成（1周）
- [ ] UE 面板
- [ ] Maya 面板
- [ ] ComfyUI 按钮

---

## 8. 关键决策

1. **Web 为主**: 跨平台、易维护、功能完整
2. **统一数据模型**: Skill/Workflow/Tool 统一管理
3. **分层架构**: Official/Marketplace/User 清晰分层
4. **运行时环境检测**: 自动识别可用 DCC，智能调度
5. **工具创建助手**: 通过 Skill 形式让 Agent 协助用户创建工具，而非复杂的可视化向导

---

*文档结束*
