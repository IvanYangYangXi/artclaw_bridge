# ArtClaw Tool Manager - 数据模型规范

> 版本: 1.0
> 日期: 2026-04-10
> 位置: docs/specs/tool-manager-data-models.md

---

## 1. 概述

本文档定义 ArtClaw Tool Manager 使用的所有数据模型，包括存储格式、字段定义和关系。

---

## 2. 核心模型

### 2.1 ToolItem（统一工具项）

所有可管理项（Skill、Workflow、Tool）的基础接口。

```typescript
interface ToolItem {
  // 基础信息
  id: string;                    // 唯一标识，格式: "{source}/{name}"
  name: string;                  // 显示名称
  description: string;           // 简短描述（列表展示）
  icon: string;                  // 图标 URL 或 emoji
  
  // 分类
  type: 'skill' | 'workflow' | 'tool';
  category: string;              // 功能分类
  tags: string[];                // 标签
  
  // 来源
  source: 'official' | 'marketplace' | 'user';
  author: string;                // 作者名
  authorId?: string;             // 作者ID（市集/用户）
  version: string;               // 语义化版本
  
  // 目标环境
  targetDCCs: string[];          // ["ue57", "maya2024", "comfyui"]
  targetPlatforms: string[];     // ["windows", "macos", "linux"]
  
  // 依赖
  dependencies: {
    skills?: string[];           // 依赖的 skill IDs
    nodes?: string[];            // ComfyUI 节点依赖
    models?: string[];           // 模型依赖
    tools?: string[];            // 依赖的工具 IDs
    minVersions?: Record<string, string>;  // 最低版本要求
  };
  
  // 状态（本地）
  status: 'not_installed' | 'installed' | 'update_available' | 'disabled';
  installPath?: string;          // 本地安装路径
  installedVersion?: string;     // 已安装版本
  
  // 统计
  stats: {
    downloads: number;           // 总下载/安装次数
    rating: number;              // 评分 0-5
    ratingCount: number;         // 评分人数
    lastUsed?: string;           // ISO 8601 时间
    useCount: number;            // 使用次数
    installStats?: {             // Skill/Workflow 专用
      totalInstalls: number;
      recentInstalls: number;    // 近30天
      lastInstalledAt?: string;  // ISO 8601 时间
    };
  };
  
  // 元数据
  createdAt: string;             // ISO 8601 时间
  updatedAt: string;             // ISO 8601 时间
  publishedAt?: string;          // 发布时间（市集）
  
  // 类型特定数据
  data: SkillData | WorkflowData | ToolData;
}
```

---

### 2.2 SkillData

```typescript
interface SkillData {
  // Skill 元信息
  priority: number;              // 匹配优先级 0-100
  entryPoints: string[];         // 入口点: ["run_python", "API"]
  apiReference?: string;         // API 文档链接
  
  // Skill 内容
  skillPath: string;             // Skill 文件路径（相对 skills/）
  readmeContent?: string;        // README.md 内容（缓存）
  
  // 上下文注入
  pinned: boolean;               // 是否钉选
  contextLength: number;         // 上下文长度限制
}
```

---

### 2.3 WorkflowData

```typescript
interface WorkflowData {
  // 预览
  previewImage: string;          // 预览图 URL/路径
  thumbnail?: string;            // 缩略图（小尺寸）
  
  // 描述
  description: string;           // 简短描述（1-2行）
  detailedDescription?: string;  // 详细描述（支持 Markdown）
  
  // 参数
  parameters: WorkflowParameter[];
  
  // 工作流内容
  templateJson: object;          // 工作流 JSON
  apiJson?: object;              // API 格式 JSON（ComfyUI）
  
  // 统计
  installStats: {
    totalInstalls: number;
    recentInstalls: number;
    lastInstalledAt?: string;
  };
}

interface WorkflowParameter {
  id: string;
  name: string;                  // 显示名称
  type: 'string' | 'number' | 'boolean' | 'enum' | 'image' | 'path';
  description?: string;
  default?: any;
  required: boolean;
  
  // 类型特定
  enumOptions?: string[];        // enum 类型选项
  min?: number;                  // number 类型最小值
  max?: number;                  // number 类型最大值
  step?: number;                 // number 类型步长
  accept?: string;               // image/path 类型接受格式
}
```

---

### 2.4 ToolData

```typescript
interface ToolData {
  // 实现方式
  implementation: {
    type: 'skill_wrapper' | 'script' | 'workflow' | 'composite';
    
    // skill_wrapper: 包装现有 Skill
    skill?: string;              // Skill ID
    
    // script: 自定义脚本
    code?: string;               // Python/JavaScript 代码
    language?: 'python' | 'javascript';
    
    // workflow: 工作流工具
    workflow?: string;           // Workflow ID
    
    // composite: 组合多个工具
    steps?: ToolStep[];
  };
  
  // 接口定义
  inputs: ToolParameter[];
  outputs: ToolParameter[];
  
  // 运行时
  timeout?: number;              // 超时时间（秒）
  retryPolicy?: {
    maxRetries: number;
    retryDelay: number;
  };
}

interface ToolParameter {
  id: string;
  name: string;
  type: 'string' | 'number' | 'boolean' | 'enum' | 'array' | 'object';
  description?: string;
  default?: any;
  required: boolean;
}

interface ToolStep {
  id: string;
  tool: string;                  // 工具 ID
  inputs: Record<string, any>;   // 输入映射
  outputs: Record<string, string>; // 输出映射到上下文
  condition?: string;            // 执行条件（可选）
}
```

---

## 3. 存储模型

### 3.1 本地存储结构

```
~/.artclaw/tool-manager/
├── config.json                  # 用户配置
├── cache/
│   ├── skills.json              # Skill 列表缓存
│   ├── workflows.json           # Workflow 列表缓存
│   └── marketplace/             # 市集数据缓存
│       ├── skills.json
│       └── workflows.json
├── user-tools/
│   └── {tool-id}.json           # 用户工具定义
└── stats.json                   # 使用统计
```

### 3.2 配置文件

```typescript
// config.json
interface ToolManagerConfig {
  // 通用
  version: string;               // 配置版本
  lastSyncAt?: string;           // 上次同步时间
  
  // 显示
  theme: 'light' | 'dark' | 'system';
  language: string;              // "zh-CN", "en-US"
  
  // 行为
  autoUpdate: boolean;           // 自动检查更新
  updateChannel: 'stable' | 'beta';
  
  // 路径
  customWorkflowPath?: string;   // 自定义 Workflow 存储路径
  
  // 收藏
  favorites: {
    skills: string[];            // Skill IDs
    workflows: string[];         // Workflow IDs
    tools: string[];             // Tool IDs
  };
  
  // 最近使用
  recent: {
    skills: RecentItem[];
    workflows: RecentItem[];
    tools: RecentItem[];
  };
}

interface RecentItem {
  id: string;
  usedAt: string;
  useCount: number;
}
```

---

## 4. API 请求/响应模型

### 4.1 列表查询

```typescript
// GET /api/v1/{type}?source=&category=&search=&page=&limit=
// type: skills | workflows | tools

interface ListRequest {
  source?: 'official' | 'marketplace' | 'user' | 'all';
  category?: string;
  targetDCC?: string;
  search?: string;
  page?: number;
  limit?: number;
  sortBy?: 'name' | 'rating' | 'downloads' | 'updated';
  sortOrder?: 'asc' | 'desc';
}

interface ListResponse {
  items: ToolItem[];
  total: number;
  page: number;
  limit: number;
  hasMore: boolean;
}
```

### 4.2 安装/更新

```typescript
// POST /api/v1/{type}/{id}/install
// POST /api/v1/{type}/{id}/update
// POST /api/v1/{type}/{id}/uninstall

interface InstallRequest {
  version?: string;              // 指定版本，默认最新
  force?: boolean;               // 强制重新安装
}

interface InstallResponse {
  success: boolean;
  message?: string;
  installedVersion: string;
  installPath: string;
}
```

### 4.3 工具执行

```typescript
// POST /api/v1/tools/{id}/execute

interface ExecuteRequest {
  inputs: Record<string, any>;
  context?: {
    dcc?: string;                // 目标 DCC
    sessionId?: string;          // 会话 ID
  };
}

interface ExecuteResponse {
  success: boolean;
  outputs?: Record<string, any>;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
  executionId: string;
  duration: number;              // 执行耗时（毫秒）
}
```

### 4.4 Workflow 执行

```typescript
// POST /api/v1/workflows/{id}/execute

interface WorkflowExecuteRequest {
  parameters: Record<string, any>;
  targetDCC: string;
  options?: {
    queue?: boolean;             // 是否加入队列
    priority?: number;           // 优先级
  };
}

interface WorkflowExecuteResponse {
  success: boolean;
  jobId?: string;                // 异步任务 ID
  outputs?: {
    images?: string[];           // 输出图片路径
    files?: string[];            // 其他输出文件
  };
  error?: {
    code: string;
    message: string;
  };
}
```

---

## 5. 市集数据模型

### 5.1 发布包

```typescript
interface MarketplacePackage {
  id: string;
  type: 'skill' | 'workflow' | 'tool';
  name: string;
  version: string;
  author: {
    name: string;
    id: string;
    avatar?: string;
  };
  
  // 内容
  manifest: ToolItem;            // 完整工具定义
  files: PackageFile[];          // 文件列表
  
  // 统计
  stats: {
    downloads: number;
    rating: number;
    ratingCount: number;
  };
  
  // 元数据
  createdAt: string;
  updatedAt: string;
  publishedAt: string;
  changelog?: string;            // 更新日志
}

interface PackageFile {
  path: string;                  // 文件路径（包内）
  size: number;                  // 文件大小
  hash: string;                  // SHA256 校验
}
```

### 5.2 评分/评论

```typescript
interface Review {
  id: string;
  packageId: string;
  author: {
    name: string;
    id: string;
  };
  rating: number;                // 1-5
  comment?: string;
  createdAt: string;
  updatedAt?: string;
}
```

---

## 6. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-04-10 | 初始版本 |
