# Phase 4.4: API 设计 + 数据模型 + 错误处理

> 贯穿 Phase 4 全程
> 版本: 2.0 (2026-04-14)

---

## 1. REST API

### 1.1 工具管理

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/tools` | GET | 工具列表（支持 source/search/page/limit/sort_by） |
| `/api/v1/tools/{id}` | GET | 工具详情 |
| `/api/v1/tools` | POST | 创建工具 |
| `/api/v1/tools/{id}` | PUT | 更新工具 |
| `/api/v1/tools/{id}` | DELETE | 删除工具 |
| `/api/v1/tools/{id}/run` | POST | 运行工具 |
| `/api/v1/tools/{id}/favorite` | POST | 收藏 |
| `/api/v1/tools/{id}/presets` | GET | 获取参数预设列表 |
| `/api/v1/tools/{id}/presets` | POST | 创建参数预设 |
| `/api/v1/tools/{id}/presets/{presetId}` | PUT | 更新参数预设 |
| `/api/v1/tools/{id}/presets/{presetId}` | DELETE | 删除参数预设 |
| `/api/v1/tools/{id}/open-dir` | POST | 打开工具目录 |

### 1.2 触发规则

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/tools/{id}/triggers` | GET | 触发规则列表 |
| `/api/v1/tools/{id}/triggers` | POST | 创建触发规则 |
| `/api/v1/triggers/{ruleId}` | PATCH | 更新触发规则（部分更新） |
| `/api/v1/triggers/{ruleId}` | DELETE | 删除触发规则 |
| `/api/v1/triggers/{ruleId}/enable` | POST | 启用触发规则 |
| `/api/v1/triggers/{ruleId}/disable` | POST | 禁用触发规则 |

> 注意: 列表和创建挂在 `/tools/{id}/triggers` 下；更新/删除/启禁用挂在 `/triggers/{ruleId}` 下（不需要 tool_id）。

### 1.2.1 触发规则 API 详细说明

#### GET /api/v1/tools/{id}/triggers

返回指定工具的所有触发规则（含 manifest 同步的和用户手动创建的）。

**响应**:
```json
{
  "success": true,
  "data": [
    {
      "id": "27667b16-f05e-4edf-9f2e-8696ff291570",
      "tool_id": "official/artclaw-Skill合规检查器",
      "manifest_id": "periodic",
      "name": "每2小时检查",
      "trigger_type": "schedule",
      "event_type": "",
      "event_timing": "post",
      "execution_mode": "silent",
      "is_enabled": true,
      "conditions": {},
      "schedule_config": { "mode": "interval", "interval": 7200000 },
      "dcc": "",
      "parameter_preset_id": ""
    },
    {
      "id": "db1c88e2-...",
      "tool_id": "official/artclaw-Skill合规检查器",
      "manifest_id": "on-skill-installed-change",
      "name": "已安装Skill文件变化时检查",
      "trigger_type": "watch",
      "execution_mode": "notify",
      "is_enabled": true,
      "conditions": {
        "path": [{ "pattern": "$skills_installed/**/*.{py,md,json}" }],
        "name": [{ "pattern": ".*\\.(py|md|json)$" }]
      },
      "schedule_config": {
        "watch_events": ["created", "modified", "deleted"],
        "debounce_ms": 3000
      }
    }
  ]
}
```

> **前端处理**: 后端返回 snake_case 字段，前端 `fetchTriggers()` 通过 `snakeToCamel()` 转换为 camelCase（triggerType, isEnabled 等）。

#### POST /api/v1/tools/{id}/triggers

创建新的触发规则。

**请求体**:
```json
{
  "name": "资源保存时检查",
  "trigger_type": "event",
  "dcc": "ue5",
  "event_type": "asset.save",
  "event_timing": "post",
  "execution_mode": "notify",
  "is_enabled": true,
  "conditions": {
    "path": [{ "pattern": "/Game/Characters/**" }],
    "typeFilter": { "types": ["StaticMesh"], "dcc": "ue5" }
  },
  "schedule_config": {},
  "parameter_preset_id": ""
}
```

**字段说明**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | 规则名称 |
| `trigger_type` | enum | ✅ | manual / event / schedule / watch |
| `dcc` | string | — | 仅 event 类型，指定 DCC（需与 targetDCCs 匹配） |
| `event_type` | string | — | 仅 event 类型，如 asset.save / file.export |
| `event_timing` | enum | — | pre / post（默认 post） |
| `execution_mode` | enum | ✅ | silent / notify / interactive |
| `is_enabled` | bool | — | 默认 true |
| `conditions` | object | — | 筛选条件（详见下方） |
| `schedule_config` | object | — | 定时/watch 配置 |
| `parameter_preset_id` | string | — | 关联的参数预设 ID |

**conditions 字段结构**:

```typescript
// watch 类型使用 path + name（文件级筛选）
interface WatchConditions {
  path?: Array<{ pattern: string; exclude?: boolean }>;  // $variable + glob
  name?: Array<{ pattern: string }>;                     // 文件名正则
}

// event 类型使用 path + 场景对象筛选
interface EventConditions {
  path?: Array<{ pattern: string; exclude?: boolean }>;
  fileRules?: Array<{ pattern: string }>;                // 文件路径 gitignore 风格
  sceneRules?: Array<{ pattern: string; isRegex?: boolean }>;  // 场景对象正则
  typeFilter?: { types: string[]; dcc?: string; isRegex?: boolean };
}
```

> **watch 和 event 的 conditions 格式不同**: watch 用 `path` + `name`（对应 manifest 的 filters 格式），event 用 `fileRules` + `sceneRules` + `typeFilter`（对应前端编辑器格式）。前端 `conditionsToApi()` 负责转换。

**schedule_config 字段**:

| trigger_type | schedule_config 内容 |
|---|---|
| schedule | `{ "mode": "interval", "interval": 7200000 }` 或 `{ "mode": "cron", "cron": "0 2 * * *" }` |
| watch | `{ "watch_events": ["created", "modified"], "debounce_ms": 3000 }` |
| event / manual | `{}` |

#### PATCH /api/v1/triggers/{ruleId}

部分更新触发规则。只传需要修改的字段。

**请求体示例**（切换启用状态）:
```json
{ "is_enabled": false }
```

**请求体示例**（修改筛选条件）:
```json
{
  "name": "更新后的名称",
  "conditions": { "path": [{ "pattern": "$project_root/skills/**/*.py" }] },
  "execution_mode": "silent"
}
```

#### POST /api/v1/triggers/{ruleId}/enable & /disable

快捷启用/禁用接口。无请求体。

### 1.2.2 Manifest 触发规则自动同步

manifest.json 中声明的 triggers 在服务启动时自动同步到 triggers.json：

1. `scan_tools()` 扫描所有工具 manifest
2. `TriggerService.sync_manifest_triggers(tools)` 按 `(tool_id, manifest_id)` 去重导入
3. `tool_id` 格式为 `{source}/{name}`（如 `official/artclaw-Skill合规检查器`），与 tool_service 一致

**manifest trigger 格式 → API 格式映射**:

| manifest 字段 | API 字段 |
|---|---|
| `triggers[].id` | `manifest_id`（去重键，内部 id 是 UUID） |
| `triggers[].trigger.type` | `trigger_type` |
| `triggers[].trigger.dcc/event/timing` | `dcc` / `event_type` / `event_timing` |
| `triggers[].filters` | `conditions`（直接透传） |
| `triggers[].execution.mode` | `execution_mode` |
| `triggers[].enabled` | `is_enabled` |

### 1.3 版本管理

详见 [phase4-tool-version.md](./phase4-tool-version.md)

### 1.4 批量操作

详见 [phase4-tool-list.md](./phase4-tool-list.md)

---

## 2. 数据模型

### 2.1 manifest.json（核心）

完整 Schema 详见 [trigger-mechanism.md#8](../specs/trigger-mechanism.md)

### 2.2 TypeScript 类型

```typescript
interface ToolItem {
  id: string;                    // {source}/{name} 格式
  name: string;
  description: string;
  type: 'tool';
  source: 'official' | 'marketplace' | 'user';
  targetDCCs: string[];
  status: 'not_installed' | 'installed' | 'update_available';
  runtimeStatus?: { favorited: boolean; };
  stats: { downloads: number; rating: number; useCount: number; };
  manifest: ToolManifest;
}

interface ToolManifest {
  id: string;
  name: string;
  description: string;
  version: string;
  targetDCCs: string[];
  implementation: {
    type: 'skill_wrapper' | 'script' | 'composite';
    entry?: string;
    function?: string;
    skill?: string;
    aiPrompt?: string;
  };
  inputs: ToolParameter[];
  outputs: ToolOutput[];
  triggers: ManifestTriggerRule[];
  presets: ParameterPreset[];
}

// manifest.json 中的触发规则格式
interface ManifestTriggerRule {
  id: string;                     // 必须，用于同步去重
  name: string;
  enabled: boolean;
  trigger: ManifestTrigger;
  filters?: ManifestFilters;      // watch/event 使用
  execution: { mode: 'silent' | 'notify' | 'interactive'; timeout?: number };
}

type ManifestTrigger =
  | { type: 'manual' }
  | { type: 'event'; dcc: string; event: string; timing: 'pre' | 'post' }
  | { type: 'schedule'; mode: 'interval' | 'cron' | 'once'; interval?: number; cron?: string }
  | { type: 'watch'; events: ('created' | 'modified' | 'deleted')[]; debounceMs?: number }

// ⛔ watch trigger 不含 paths 字段，路径统一走 filters.path

// manifest 的 filters 格式（统一路径声明）
interface ManifestFilters {
  path?: Array<{ pattern: string; exclude?: boolean }>;  // 支持 $variable
  name?: Array<{ pattern: string }>;
  type?: Array<{ types: string[] }>;
}

// API 返回的触发规则格式（存储在 triggers.json，snake_case）
// 前端通过 snakeToCamel() 转换
interface TriggerRuleData {
  id: string;                     // UUID（内部生成）
  tool_id: string;                // {source}/{name} 格式
  manifest_id?: string;           // 对应 manifest trigger.id
  name: string;
  trigger_type: 'manual' | 'event' | 'schedule' | 'watch';
  event_type: string;
  event_timing: 'pre' | 'post';
  execution_mode: 'silent' | 'notify' | 'interactive';
  is_enabled: boolean;
  conditions: Record<string, unknown>;
  schedule_config: Record<string, unknown>;
  dcc: string;
  parameter_preset_id: string;
}
```

### 2.3 路径变量

| 变量 | 解析值 | 说明 |
|------|--------|------|
| `$skills_installed` | `~/.openclaw/workspace/skills` | 已安装 Skill 目录 |
| `$project_root` | config.json → project_root | 项目源码根目录 |
| `$tools_dir` | `~/.artclaw/tools` | 工具存储目录 |
| `$home` | 用户主目录 | — |

### 2.4 筛选条件适用性

| 触发类型 | 筛选条件 | 前端编辑器 |
|----------|----------|------------|
| **watch** | ✅ path + name | 显示文件路径规则 |
| **event** | ✅ path + scene + type | 显示文件 + 场景对象 + 类型筛选 |
| **schedule** | ❌ | 不显示筛选区域 |
| **manual** | ❌ | 不显示筛选区域 |

---

## 3. 错误处理

### 3.1 错误码规范

使用统一前缀，与 Phase 3 (Workflow) 保持一致：

| 前缀 | 范围 | 示例 |
|------|------|------|
| `COMMON_*` | 通用错误 | `COMMON_NETWORK_ERROR`, `COMMON_TIMEOUT` |
| `TOOL_*` | 工具专属 | `TOOL_NOT_FOUND`, `TOOL_EXECUTION_FAILED` |

### 3.2 常见错误

| 错误码 | 提示信息 | 处理方式 |
|--------|----------|----------|
| `TOOL_NOT_FOUND` | 工具不存在 | 刷新列表 |
| `TOOL_DCC_NOT_CONNECTED` | DCC 未连接\n\n请启动对应 DCC 软件 | 显示连接设置 |
| `TOOL_INVALID_SELECTION` | 请先选择对象\n\n在 DCC 中选择要处理的对象 | 引导用户 |
| `TOOL_SCRIPT_ERROR` | 脚本运行出错: {detail}\n\n请检查工具脚本 | 显示错误详情 |
| `TOOL_EXECUTION_FAILED` | 运行失败: {detail}\n\n[重试] [查看日志] | 重试或查看 |
| `COMMON_NETWORK_ERROR` | 网络连接失败\n\n请检查网络连接 | 自动重试 |
| `COMMON_TIMEOUT` | 运行超时\n\n请稍后重试 | 提示重试 |

### 3.3 错误响应格式

```json
{
  "success": false,
  "error": {
    "code": "TOOL_DCC_NOT_CONNECTED",
    "message": "DCC 未连接",
    "detail": "无法连接到 Maya 2024 (ws://localhost:8081)",
    "suggestion": "请启动 Maya 2024 并确保 ArtClaw Bridge 插件已加载"
  }
}
```
