# ArtClaw Tool Manager - 架构设计文档

> 版本: 4.0
> 更新日期: 2026-04-11
> 说明: 移除 UI 部分，专注于架构和数据模型

---

## 1. 核心概念

### 1.1 概念定义

```
ArtClaw 工具生态 - 三层概念模型
│
├── 【Skill】AI 操作指南
│   ├── 定义: 指导 AI Agent 如何完成特定任务的文档
│   ├── 示例: comfyui-txt2img、ue5-material-node-edit
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
用户点击 Workflow [运行] → 跳转对话面板 → 输入框预填消息 → AI 协助填参 → 执行
         ↓
用户点击 Tool [运行] → 跳转对话面板 → 输入框预填消息 → AI 协助填参 → 执行
         ↓
事件/定时/监听触发 → 触发规则引擎 → 条件筛选 → 加载预设 → 自动执行
```

### 1.3 工具触发机制

工具不仅支持手动运行，还支持事件驱动、定时调度、文件监听等自动触发方式。

**触发方式**:
| 类型 | 说明 | 示例 |
|------|------|------|
| manual | 手动点击运行 | 用户在管理器中点击[运行] |
| event | DCC 事件触发 | UE 保存资源时、Maya 导出 FBX 时 |
| schedule | 定时/周期触发 | 每30分钟、每天凌晨2点 |
| watch | 文件/目录监听 | 目录下有新文件时自动运行 |

**触发规则 = 触发方式 + 条件筛选 + 参数预设**

- **条件筛选**: 目录路径、命名正则、资源类型、选中对象、属性条件、标签
- **参数预设**: 工具参数的默认值组合，不同场景快速切换
- **执行模式**: silent（静默）/ notify（通知）/ interactive（AI协助）
- **事件时机**: pre（事件前，可拦截）/ post（事件后）

详见: [trigger-mechanism.md](./trigger-mechanism.md)

### 1.2 工具分类体系

```
ArtClaw 工具生态 - 三层来源
│
├── 官方层（ArtClaw 维护）
│   ├── Official Skills          → ~/.openclaw/workspace/skills/
│   ├── Official Workflows       → {project_root}/workflows/
│   └── Official Tools           → {project_root}/tools/
│
├── 市集层（社区）
│   ├── Marketplace Skills       → ~/.openclaw/workspace/skills/
│   ├── Marketplace Workflows    → {project_root}/workflows/
│   └── Marketplace Tools        → {project_root}/tools/
│
└── 用户层（个人创建）
    ├── User Workflows (ComfyUI) → ~/.artclaw/workflows/      （发布后移到项目目录）
    └── User Tools               → ~/.artclaw/tools/user/      （发布后移到项目目录）
```

**单副本原则**: Workflow/Tool 只保留一份文件。用户创建的放 `~/.artclaw/`，
发布后移动到 `{project_root}/`（通过 Git 团队同步），原位置删除。

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
│  │  ┌──────────────────────────────────────────────────┐     │   │
│  │  │ 📌 钉选 Skill 标签: [comfyui-txt2img] [ue5-op] │     │   │
│  │  └──────────────────────────────────────────────────┘     │   │
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
│   skills/       │ │ workflows/(用户)│ │                 │
│                 │ │ tools/user/(用户)│ │ • UE (ws:8080)  │
│ config.json     │ │                 │ │ • Maya(ws:8081) │
│  - pinned  ────────→ 对话面板标签   │ │ • ComfyUI       │
│  - disabled     │ │ config.json     │ │   (ws:8087)     │
│  - favorites    │ │  - favorites    │ │ • ...           │
└─────────────────┘ └────────┬────────┘ └─────────────────┘
                             │
                    ┌────────▼────────┐
                    │ {project_root}/ │  ← Git 同步
                    │ workflows/(官方) │
                    │ tools/(官方)     │
                    └─────────────────┘
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
| 3 | 输入框预填消息 | 格式: `/run workflow:{id}` 或 `/run tool:{id}`，显示为可读文本 |
| 4 | 消息区显示引导卡片 | 系统消息提示"即将运行 XXX，点击发送或修改参数" |
| 5 | 用户发送 | 点击发送按钮或按 Enter |
| 6 | AI 解析意图 | 识别为执行 Workflow/Tool 请求 |
| 7 | 右侧面板显示参数表单 | 根据 Workflow/Tool 定义动态生成 |
| 8 | 用户与 AI 协作填参 | 可手动填写，也可让 AI 根据对话上下文填写 |
| 9 | 用户确认执行 | 点击 [执行] 或告诉 AI "开始执行" |
| 10 | 发送执行命令到 DCC | 通过 MCP 调用对应 DCC 的 run_python/run_ue_python |
| 11 | 显示执行进度 | 在消息流中显示进度卡片 |
| 12 | 显示执行结果 | 成功/失败都在消息流中显示 |

**注意**: 步骤 3-4 是关键的引导体验——用户跳转后不是空白页面，而是看到预填的命令和引导提示。

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

### 2.3 AI 执行消息格式

前端发送给 AI Agent 的消息会自动附带工具的定位信息，确保 AI 能精确找到并执行工具脚本：

```
请执行Tool "批量重命名"

工具目录: C:\Users\xxx\.artclaw\tools\user\batch-rename
入口脚本: main.py
实现方式: script
关联 Skill: blender-operation-rules     ← 仅 skill_wrapper 类型
AI 执行指引: 读取入口脚本并执行...       ← 来自 manifest.implementation.aiPrompt

参数:
{ "prefix": "SM_", "start_number": 1 }

参数定义:
[ { "id": "prefix", "name": "前缀", "type": "string", "required": true } ]
```

**消息中包含的关键字段**:

| 字段 | 来源 | 用途 |
|------|------|------|
| 工具目录 `toolPath` | 后端扫描的磁盘路径 | AI 定位脚本文件 |
| 入口脚本 `entryScript` | manifest.implementation.entry | AI 知道执行哪个文件 |
| 实现方式 `implementationType` | manifest.implementation.type | AI 选择执行策略 |
| 关联 Skill `skillRef` | manifest.implementation.skill | skill_wrapper 引用的 Skill |
| AI 执行指引 `aiPrompt` | manifest.implementation.aiPrompt | 自定义的 AI 执行指令 |

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
  targetDCCs: string[];          // ["ue5", "comfyui", "maya2024"]
  
  // 状态（Skill/Workflow 有 disabled 状态，Tool 没有）
  status: 'not_installed' | 'installed' | 'update_available' | 'disabled';
  // 注: Tool 不支持 disabled 状态，因为工具是用户主动运行的
  
  // 操作状态（运行时状态）
  runtimeStatus?: {
    enabled: boolean;            // 是否启用（仅 Skill/Workflow）
    pinned: boolean;             // 是否钉选（仅 Skill）
    favorited: boolean;          // 是否收藏
  };
  
  // 本地路径信息
  paths: {
    installed: string;           // 安装目录 (如 ~/.openclaw/workspace/skills/xxx 或 ~/.artclaw/tools/user/xxx)
    source?: string;             // 源码目录 (如 artclaw_bridge/skills/xxx, 仅有源码时存在)
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
  presets: ParameterPreset[];    // 参数预设列表（多配置管理）
  lastUsed?: string;             // ISO 时间
  useCount: number;
}

// 参数预设（一个工具可有多个预设）
interface ParameterPreset {
  id: string;                    // 预设 ID
  name: string;                  // 预设名称（如 "角色命名规范"、"道具命名规范"）
  description?: string;          // 预设描述
  isDefault?: boolean;           // 是否为默认预设
  params: Record<string, any>;   // 参数键值对
  createdAt: string;             // 创建时间
  updatedAt: string;             // 更新时间
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
Skill/Workflow 状态流转（含禁用）:

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

Tool 状态流转（无禁用）:

                    ┌─────────────┐
         ┌─────────►│  未安装     │◄────────┐
         │          │ not_installed│         │
         │          └──────┬──────┘         │
      删除│                 │ 创建/安装       │更新失败
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
                    └─────────────┘

注意:
- Tool 不支持禁用（用户主动运行的工具不需要禁用）
- Tool 支持删除而非卸载（用户创建的工具直接删除）
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

| 页面 | 功能 | 标签 | 筛选器 |
|------|------|------|--------|
| **对话** | AI 对话面板（核心功能，Workflow/Tool 执行入口） | 单页面 | — |
| Skills | Skill 浏览/安装/管理 | 全部/官方/市集/平台 | DCC软件筛选 + 收藏筛选 |
| Workflow 库 | ComfyUI Workflow 管理（运行按钮跳转对话面板） | 全部/官方/市集/我的 | 收藏筛选 |
| 工具管理器 | 工具管理和创建（运行按钮跳转对话面板） | 全部/官方/市集/我的/创建 | DCC软件筛选 + 收藏筛选 |
| 设置 | 系统配置 | 通用/高级 | — |

**导航结构**:
```
🔧 ArtClaw Tool Manager
│
├── 💬 对话 (核心入口 - Workflow/Tool 执行)
│   └── 钉选 Skill 标签展示区（快捷输入上方）
├── 📦 Skills
│   ├── 全部
│   ├── 官方
│   ├── 市集
│   ├── 平台（按 DCC 软件分类: UE/Maya/Max/Blender/ComfyUI/SD/SP）
│   └── [筛选器: DCC软件▼] [⭐仅收藏]
├── 📋 Workflow 库 (ComfyUI)
│   ├── 全部
│   ├── 官方
│   ├── 市集
│   ├── 我的
│   └── [⭐仅收藏]
├── 🔧 工具管理器
│   ├── 全部
│   ├── 官方工具
│   ├── 市集工具
│   ├── 我的工具
│   ├── 创建工具
│   └── [筛选器: DCC软件▼] [⭐仅收藏]
└── ⚙️ 设置
```

**标签说明**:
- Skills "平台" 标签: 对应 UE 侧 `get_skills_by_category()`/`list_skills(software=xxx)` 的按 DCC 筛选逻辑
- Skills 不设"我的"标签（Skill 无用户自创概念，用户通过 Tool Creator 创建的是 Tool 不是 Skill）
- 收藏筛选: 所有页面（Skills/Workflow/Tools）统一支持收藏筛选按钮
- DCC 软件筛选: Skills 和 Tools 支持按目标 DCC 筛选（数据来自 `targetDCCs` 字段）

**Skill 操作按钮**（与 UE 侧 skill_mcp_tools.py 一致）:

| 操作 | UE 侧对应 API | 说明 |
|------|---------------|------|
| 安装 | `install_skill()` | 从源码安装到已安装目录 |
| 卸载 | `uninstall_skill()` | 从已安装目录移除 |
| 更新 | `update_skill()` | 从源码更新到已安装目录 |
| 启用/禁用 | `enable_skill()` / `disable_skill()` | 控制 Skill 是否加载 |
| 钉选 | config.json `pinned_skills` | 钉选后在对话面板显示标签 |
| 收藏 | config.json `skills.favorites` | 收藏后可通过收藏筛选快速找到 |
| 打开安装目录 | — | 在文件管理器中打开 `~/.openclaw/workspace/skills/{name}/` |
| 打开源码目录 | — | 在文件管理器中打开源码仓库中的 Skill 目录（如有） |
| 文档 | — | 打开 SKILL.md 查看 |

**Workflow 操作按钮**:

| 操作 | 说明 |
|------|------|
| 运行 | 跳转对话面板执行 |
| 收藏 | config.json `workflows.favorites` |
| 打开目录 | 打开 Workflow 所在目录（用户: `~/.artclaw/workflows/`，官方: `{project_root}/workflows/`） |
| 发布 | 用户 Workflow 移动到项目目录（Git 同步） |

**Tool 操作按钮**（无禁用功能）:

| 操作 | 说明 |
|------|------|
| 运行 | 跳转对话面板执行 |
| 编辑 | 跳转对话面板发送 `/edit tool:{id}` |
| 收藏 | config.json `tools.favorites` |
| 打开目录 | 打开 Tool 所在目录（用户: `~/.artclaw/tools/user/`，官方: `{project_root}/tools/`） |
| 预设管理 | 管理参数预设（CRUD，详见下文） |
| 发布 | 用户 Tool 移动到项目目录（Git 同步） |
| 删除 | 确认后删除工具目录 |

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

### 6.3 存储模型（单副本原则）

**核心规则**: Workflow 和 Tool 只保留一份文件，不同步维护多个副本。

**存储位置**:

| 来源 | 存储位置 | 说明 |
|------|----------|------|
| 用户创建的 | `~/.artclaw/workflows/` 或 `~/.artclaw/tools/user/` | 个人本地，不进 Git |
| 官方/市集 | `{project_root}/workflows/` 或 `{project_root}/tools/` | 项目目录，Git 同步 |

**发布流程（用户 → 官方/市集）**:
```
~/.artclaw/workflows/{name}/     ──发布──>  {project_root}/workflows/{name}/
~/.artclaw/tools/user/{name}/    ──发布──>  {project_root}/tools/{name}/
```
发布 = 把用户目录下的文件**移动**到项目目录，然后通过 Git 同步给团队。
用户目录下的原文件删除（只保留一份）。

**安装流程（官方/市集 → 本地运行）**:
官方和市集的 Workflow/Tool 直接从项目目录读取，不复制到 `~/.artclaw/`。
本地 `~/.artclaw/` 仅存放用户自己创建的、尚未发布的内容。

**完整目录结构**:
```
~/.artclaw/                      # 用户本地（不进 Git）
    workflows/                   # 用户自建 Workflow
        {workflow-name}/
            workflow.json
            preview.png
    tools/
        user/                    # 用户自建 Tool
            {tool-name}/
                manifest.json
                main.py
    config.json                  # 全局配置（pinned/disabled/favorites）
    filter-presets/              # 全局筛选预设

{project_root}/                  # 项目目录（Git 同步）
    workflows/                   # 官方/市集 Workflow
        {workflow-name}/
            workflow.json
            preview.png
    tools/                       # 官方/市集 Tool
        {tool-name}/
            manifest.json
            main.py

~/.openclaw/workspace/skills/              # Skill（与 OpenClaw 共享，Skill 有自己的同步机制）
```

**与 Skill 的区别**:
- Skill 使用 `install_skill()`/`publish_skill()` 机制，源码和安装分离
- Workflow/Tool 采用单副本，发布时直接移动文件

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

### v4.0 (2026-04-11)
- **存储模型改为单副本**: Workflow/Tool 只保留一份，发布=移动到项目目录（Git 同步）
- Workflow/Tool 执行流程改为"预填消息+引导卡片"，解决跳转后空白问题
- Skill 标签从"全部/官方/市集/我的"改为"全部/官方/市集/平台"
- 新增所有页面的收藏筛选按钮
- 新增 Skill 打开安装目录/源码目录功能
- 新增 Workflow/Tool 打开目录功能
- 明确 Skill 操作与 UE 侧 skill_hub/skill_mcp_tools 一致
- Tool 移除禁用功能（用户主动运行不需要禁用）
- Tool 状态流转独立定义（无 disabled 状态）
- Tool 新增 DCC 软件筛选器
- ToolData 新增 presets 字段（参数预设列表）
- ToolItem 新增 paths 字段（安装/源码目录路径）
- 明确存储路径: Skills→~/.openclaw/workspace/skills/, Workflows→~/.artclaw/workflows/, Tools→~/.artclaw/tools/
- 对话面板新增钉选 Skill 标签展示区

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
