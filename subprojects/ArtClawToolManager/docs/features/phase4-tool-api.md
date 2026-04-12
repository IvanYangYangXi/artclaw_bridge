# Phase 4.4: API 设计 + 数据模型 + 错误处理

> 贯穿 Phase 4 全程

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
| `/api/v1/tools/{id}/triggers/{ruleId}` | PUT | 更新触发规则 |
| `/api/v1/tools/{id}/triggers/{ruleId}` | DELETE | 删除触发规则 |

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
  id: string;
  name: string;
  description: string;
  type: 'tool';
  source: 'official' | 'marketplace' | 'user';
  targetDCCs: string[];
  status: 'not_installed' | 'installed' | 'update_available';  // Tool 无 disabled 状态
  runtimeStatus?: { favorited: boolean; };  // Tool 无 enabled/pinned
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
  triggers: TriggerRule[];
  presets: ParameterPreset[];
}
```

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
