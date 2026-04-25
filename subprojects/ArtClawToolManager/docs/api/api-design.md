# ArtClaw Tool Manager - API 设计文档

> 版本: 1.0
> 日期: 2026-04-10
> 位置: subprojects/ArtClawToolManager/docs/specs/api-design.md

---

## 1. 概述

本文档定义 ArtClaw Tool Manager 后端提供的 REST API 规范。

- Base URL: `http://localhost:9876/api/v1`
- 数据格式: JSON
- 编码: UTF-8

---

## 2. 通用规范

### 2.1 响应格式

```typescript
// 成功响应
{
  "success": true,
  "data": { ... },
  "meta": {          // 列表查询时包含
    "page": 1,
    "limit": 20,
    "total": 100
  }
}

// 错误响应
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Skill not found",
    "details": { ... }
  }
}
```

### 2.2 错误码

| 状态码 | 错误码 | 说明 |
|--------|--------|------|
| 400 | BAD_REQUEST | 请求参数错误 |
| 401 | UNAUTHORIZED | 未授权 |
| 404 | NOT_FOUND | 资源不存在 |
| 409 | CONFLICT | 资源冲突（如已安装） |
| 422 | VALIDATION_ERROR | 数据验证失败 |
| 500 | INTERNAL_ERROR | 服务器内部错误 |

### 2.3 分页参数

列表接口统一支持：
- `page`: 页码（从1开始）
- `limit`: 每页数量（默认20，最大100）
- `sortBy`: 排序字段
- `sortOrder`: `asc` 或 `desc`

---

## 3. Skills API

### 3.1 获取 Skill 列表

```http
GET /skills
```

**查询参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| source | string | `official` \| `marketplace` \| `user` \| `all` |
| targetDCC | string | 筛选目标 DCC |
| category | string | 功能分类 |
| search | string | 关键词搜索 |
| installed | boolean | 仅显示已安装 |

**响应：**
```json
{
  "success": true,
  "data": [
    {
      "id": "official/comfyui-txt2img",
      "name": "comfyui-txt2img",
      "type": "skill",
      "source": "official",
      "description": "ComfyUI 文生图标准流程",
      "version": "0.1.0",
      "targetDCCs": ["comfyui"],
      "status": "installed",
      "stats": {
        "downloads": 1200,
        "rating": 4.8,
        "useCount": 45
      }
    }
  ],
  "meta": {
    "page": 1,
    "limit": 20,
    "total": 50
  }
}
```

---

### 3.2 获取 Skill 详情

```http
GET /skills/{id}
```

**响应：**
```json
{
  "success": true,
  "data": {
    "id": "official/comfyui-txt2img",
    "name": "comfyui-txt2img",
    "type": "skill",
    "source": "official",
    "description": "ComfyUI 文生图标准流程",
    "detailedDescription": "...",
    "version": "0.1.0",
    "targetDCCs": ["comfyui"],
    "dependencies": {
      "nodes": ["KSampler", "CheckpointLoader"]
    },
    "status": "installed",
    "installedVersion": "0.1.0",
    "installPath": "~/.openclaw/workspace/skills/comfyui-txt2img",
    "stats": { ... },
    "data": {
      "priority": 100,
      "entryPoints": ["run_python"],
      "skillPath": "comfyui-txt2img",
      "pinned": false
    }
  }
}
```

---

### 3.3 安装 Skill

```http
POST /skills/{id}/install
```

**请求体：**
```json
{
  "version": "0.1.0",    // 可选，默认最新
  "force": false          // 可选，强制重新安装
}
```

**响应：**
```json
{
  "success": true,
  "data": {
    "installedVersion": "0.1.0",
    "installPath": "~/.openclaw/workspace/skills/comfyui-txt2img",
    "message": "安装成功"
  }
}
```

---

### 3.4 更新 Skill

```http
POST /skills/{id}/update
```

**响应：** 同安装

---

### 3.5 卸载 Skill

```http
POST /skills/{id}/uninstall
```

**响应：**
```json
{
  "success": true,
  "data": {
    "message": "卸载成功"
  }
}
```

---

### 3.6 启用/禁用 Skill

```http
POST /skills/{id}/enable
POST /skills/{id}/disable
```

---

### 3.7 钉选/取消钉选

```http
POST /skills/{id}/pin
POST /skills/{id}/unpin
```

---

## 4. Workflows API

### 4.1 获取 Workflow 列表

```http
GET /workflows
```

**查询参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| source | string | `official` \| `marketplace` \| `user` |
| targetDCC | string | 筛选目标 DCC |
| category | string | 功能分类 |
| search | string | 关键词搜索 |
| favorited | boolean | 仅显示收藏 |

**响应：**
```json
{
  "success": true,
  "data": [
    {
      "id": "marketplace/sdxl-portrait",
      "name": "SDXL 肖像摄影",
      "type": "workflow",
      "source": "marketplace",
      "description": "专业肖像摄影风格工作流",
      "previewImage": "/api/v1/workflows/marketplace/sdxl-portrait/preview",
      "targetDCCs": ["comfyui"],
      "stats": {
        "downloads": 2300,
        "rating": 4.9,
        "installStats": {
          "totalInstalls": 2300,
          "recentInstalls": 150
        }
      }
    }
  ]
}
```

---

### 4.2 获取 Workflow 详情

```http
GET /workflows/{id}
```

**响应：**
```json
{
  "success": true,
  "data": {
    "id": "marketplace/sdxl-portrait",
    "name": "SDXL 肖像摄影",
    "type": "workflow",
    "source": "marketplace",
    "description": "专业肖像摄影风格工作流",
    "detailedDescription": "...",
    "previewImage": "...",
    "targetDCCs": ["comfyui"],
    "dependencies": {
      "nodes": ["KSampler", "LoraLoader"],
      "models": ["SDXL Base"]
    },
    "stats": { ... },
    "data": {
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
      ]
    }
  }
}
```

---

### 4.3 安装/更新/卸载 Workflow

```http
POST /workflows/{id}/install
POST /workflows/{id}/update
POST /workflows/{id}/uninstall
```

---

### 4.4 收藏/取消收藏

```http
POST /workflows/{id}/favorite
POST /workflows/{id}/unfavorite
```

---

### 4.5 执行 Workflow

```http
POST /workflows/{id}/execute
```

**请求体：**
```json
{
  "parameters": {
    "prompt": "a beautiful portrait",
    "width": 1024,
    "height": 1024
  },
  "targetDCC": "comfyui",
  "options": {
    "queue": true,
    "priority": 0
  }
}
```

**响应：**
```json
{
  "success": true,
  "data": {
    "jobId": "job-123456",
    "status": "queued",
    "message": "已加入执行队列"
  }
}
```

---

### 4.6 获取执行状态

```http
GET /workflows/jobs/{jobId}
```

**响应：**
```json
{
  "success": true,
  "data": {
    "jobId": "job-123456",
    "status": "running",      // queued | running | completed | failed
    "progress": 50,           // 0-100
    "outputs": null,
    "createdAt": "2026-04-10T10:00:00Z",
    "startedAt": "2026-04-10T10:00:05Z",
    "estimatedEndAt": "2026-04-10T10:02:00Z"
  }
}
```

---

### 4.7 创建用户 Workflow

```http
POST /workflows
```

**请求体：**
```json
{
  "name": "我的文生图流程",
  "description": "自定义工作流",
  "targetDCCs": ["comfyui"],
  "templateJson": { ... },
  "parameters": [ ... ]
}
```

---

### 4.8 更新用户 Workflow

```http
PUT /workflows/{id}
```

---

### 4.9 删除用户 Workflow

```http
DELETE /workflows/{id}
```

---

## 5. Tools API

### 5.1 获取 Tool 列表

```http
GET /tools
```

**查询参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| source | string | `official` \| `marketplace` \| `user` |
| targetDCC | string | 筛选目标 DCC |
| category | string | 功能分类 |

---

### 5.2 获取 Tool 详情

```http
GET /tools/{id}
```

---

### 5.3 执行 Tool

```http
POST /tools/{id}/execute
```

**请求体：**
```json
{
  "inputs": {
    "prefix": "SM_",
    "use_numbers": true
  },
  "context": {
    "dcc": "ue5",
    "sessionId": "session-123"
  }
}
```

**响应：**
```json
{
  "success": true,
  "data": {
    "outputs": {
      "renamed_count": 5,
      "renamed_list": ["SM_Cube_01", "SM_Cube_02"]
    },
    "executionId": "exec-789",
    "duration": 1200
  }
}
```

---

### 5.4 创建用户 Tool

```http
POST /tools
```

**请求体：**
```json
{
  "name": "批量重命名",
  "description": "批量重命名选中对象",
  "category": "场景管理",
  "targetDCCs": ["ue5"],
  "implementation": {
    "type": "skill_wrapper",
    "skill": "ue5-artclaw-highlight"
  },
  "inputs": [
    {
      "id": "prefix",
      "name": "前缀",
      "type": "string",
      "default": "SM_"
    }
  ]
}
```

---

### 5.5 更新/删除用户 Tool

```http
PUT /tools/{id}
DELETE /tools/{id}
```

---

### 5.6 发布 Tool 到市集

```http
POST /tools/{id}/publish
```

**请求体：**
```json
{
  "version": "1.0.0",
  "changelog": "初始版本"
}
```

---

## 6. System API

### 6.1 获取系统状态

```http
GET /system/status
```

**响应：**
```json
{
  "success": true,
  "data": {
    "version": "1.0.0",
    "status": "running",
    "connectedDCCs": ["comfyui", "maya2024"],
    "stats": {
      "totalSkills": 50,
      "installedSkills": 20,
      "totalWorkflows": 30,
      "userTools": 5
    }
  }
}
```

---

### 6.2 获取配置

```http
GET /system/config
```

---

### 6.3 更新配置

```http
PUT /system/config
```

---

### 6.4 同步市集数据

```http
POST /system/sync
```

**响应：**
```json
{
  "success": true,
  "data": {
    "syncedAt": "2026-04-10T10:00:00Z",
    "newSkills": 2,
    "updatedSkills": 5,
    "newWorkflows": 3
  }
}
```

---

## 7. WebSocket API

用于实时推送（执行进度、状态更新等）。

### 7.1 连接

```
ws://localhost:9876/ws
```

### 7.2 消息类型

```typescript
// 客户端 → 服务器
interface SubscribeMessage {
  type: 'subscribe';
  channels: string[];    // ['jobs', 'system']
}

// 服务器 → 客户端
interface JobProgressMessage {
  type: 'job.progress';
  data: {
    jobId: string;
    progress: number;
    status: string;
  }
}

interface DCCStatusMessage {
  type: 'dcc.status';
  data: {
    dcc: string;
    status: 'connected' | 'disconnected';
  }
}
```

---

## 8. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-04-10 | 初始版本 |
