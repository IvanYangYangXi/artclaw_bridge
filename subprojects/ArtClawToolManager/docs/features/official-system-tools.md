# ArtClaw Tool Manager - 官方系统工具设计

> 版本: 1.0  
> 日期: 2026-04-12  
> 说明: 状态栏报警机制、工具合规性检查器、Skill 版本同步检查器的整体设计

## 1. 概述

### 1.1 背景

ArtClaw Tool Manager 需要内置"官方系统工具"来维护工具生态的健康：

- **工具合规性检查器**: 监控 ~/.artclaw/tools/ 目录，检查工具的 manifest.json 格式和配置是否合规
- **Skill 版本同步检查器**: 检查已安装 skill 是否有更新或冲突
- **状态栏报警机制**: 在前端 StatusBar 显示系统报警，引导用户修复问题

### 1.2 核心原则

- **官方工具**: 通过现有工具框架开发，遵循统一的 manifest.json 规范
- **自动触发**: 文件监听 + 定时检查 + 事件驱动，无需用户干预
- **报警驱动**: 问题出现时在 StatusBar 常驻报警，问题解决后自动消失
- **硬编码规则**: 检查规则固化在工具代码中，保证一致性

## 2. 数据模型

### 2.1 Alert 数据模型

```typescript
interface Alert {
  id: string;                    // 唯一 ID
  level: 'warning' | 'error';    // 严重级别
  source: string;                // 来源工具 ID
  title: string;                 // 简短标题
  detail: string;                // 详细描述
  createdAt: string;             // 创建时间 (ISO)
  resolvedAt: string | null;     // 解决时间 (ISO)
  metadata?: Record<string, any>; // 扩展数据
}

interface AlertCreateRequest {
  level: 'warning' | 'error';
  source: string;
  title: string;
  detail: string;
  metadata?: Record<string, any>;
}

interface AlertUpdateRequest {
  resolved: boolean;
  resolvedAt?: string;
}
```

### 2.2 Compliance Check Result

```typescript
interface ComplianceResult {
  toolPath: string;              // 工具目录路径
  toolId: string;                // 工具 ID
  isValid: boolean;              // 是否合规
  errors: string[];              // 错误列表
  warnings: string[];            // 警告列表
}
```

### 2.3 Skill Version Info

```typescript
interface SkillVersionInfo {
  skillId: string;               // Skill ID
  installedVersion: string;      // 已安装版本
  sourceVersion: string;         // 源码版本
  status: 'up_to_date' | 'update_available' | 'source_newer' | 'conflict';
  lastChecked: string;           // 最后检查时间
}
```

## 3. 后端 API 设计

### 3.1 Alerts API

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/v1/alerts` | 获取活跃报警列表 |
| GET | `/api/v1/alerts?resolved=true` | 获取全部报警（含已解决） |
| POST | `/api/v1/alerts` | 创建报警 |
| PATCH | `/api/v1/alerts/{id}` | 更新报警状态 |
| DELETE | `/api/v1/alerts/{id}` | 删除报警 |

**示例请求/响应**:

```json
# POST /api/v1/alerts
{
  "level": "error",
  "source": "tool-compliance-checker",
  "title": "工具配置错误",
  "detail": "工具 user/batch-rename 的 manifest.json 缺少必填字段 name",
  "metadata": {
    "toolId": "user/batch-rename",
    "missingFields": ["name"]
  }
}

# Response
{
  "id": "alert-001",
  "level": "error",
  "source": "tool-compliance-checker",
  "title": "工具配置错误",
  "detail": "工具 user/batch-rename 的 manifest.json 缺少必填字段 name",
  "createdAt": "2026-04-12T02:30:00Z",
  "resolvedAt": null,
  "metadata": {
    "toolId": "user/batch-rename",
    "missingFields": ["name"]
  }
}
```

### 3.2 System Tools API

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/v1/system/tools/compliance-check` | 手动触发工具合规检查 |
| POST | `/api/v1/system/tools/skill-version-check` | 手动触发 Skill 版本检查 |
| GET | `/api/v1/system/tools/compliance-check/results` | 获取最近的合规检查结果 |
| GET | `/api/v1/system/tools/skill-version-check/results` | 获取最近的版本检查结果 |

## 4. 官方系统工具规格

### 4.1 工具合规性检查器

**名称**: `system/tool-compliance-checker`  
**类型**: 官方系统工具  
**触发方式**:
- `watch`: 监听 `~/.artclaw/tools/` 目录变化 (新增/修改)
- `schedule`: 每 30 分钟全量扫描一次

**检查项（硬编码规则）**:

1. **manifest.json 存在性**: 工具目录下必须有 manifest.json
2. **JSON 格式**: manifest.json 必须是有效的 JSON
3. **必填字段检查**:
   - `id`: 工具唯一标识
   - `name`: 工具名称
   - `version`: 语义化版本 (semver)
   - `implementation.type`: script | skill_wrapper | ai_generated
   - `implementation.entry`: 入口文件路径
4. **入口文件存在性**: implementation.entry 指向的文件必须存在
5. **inputs 参数格式**: 每个参数必须有 id, name, type 字段
6. **targetDCCs 有效性**: 只能包含已知的 DCC 类型
7. **version 格式**: 符合 semver 规范 (x.y.z)

**输出行为**:
- 发现问题 → 调用 `POST /api/v1/alerts` 创建报警
- 问题修复 → 调用 `PATCH /api/v1/alerts/{id}` 标记 resolved
- 报警类型: `error` (阻止工具运行), `warning` (建议修复)

**manifest.json 示例**:

```json
{
  "id": "system/tool-compliance-checker",
  "name": "工具合规性检查器",
  "description": "检查工具 manifest.json 的格式和配置合规性",
  "version": "1.0.0",
  "targetDCCs": ["*"],
  "type": "official",
  
  "implementation": {
    "type": "script",
    "entry": "main.py",
    "function": "check_compliance"
  },
  
  "inputs": [],
  
  "triggers": [
    {
      "id": "watch-tools-dir",
      "name": "监听工具目录变化",
      "enabled": true,
      "trigger": {
        "type": "watch",
        "paths": ["~/.artclaw/tools/**"],
        "events": ["created", "modified"],
        "debounceMs": 2000
      },
      "execution": {
        "mode": "silent",
        "timeout": 30
      }
    },
    {
      "id": "scheduled-scan",
      "name": "定时全量扫描",
      "enabled": true,
      "trigger": {
        "type": "schedule",
        "mode": "interval",
        "interval": 1800000
      },
      "execution": {
        "mode": "silent",
        "timeout": 60
      }
    }
  ]
}
```

### 4.2 Skill 版本同步检查器

**名称**: `system/skill-version-checker`  
**类型**: 官方系统工具  
**触发方式**:
- `event`: DCC 连接时 (editor.startup)
- `schedule`: 每 2 小时检查一次

**检查项**:

1. **已安装 Skill 列表**: 扫描 ~/.artclaw/skills/
2. **源码版本对比**: 
   - Git diff 检查源码是否有更新
   - 版本号对比 (SKILL.md 中的版本信息)
3. **状态分类**:
   - `up_to_date`: 已是最新版本
   - `update_available`: 有新版本可用
   - `source_newer`: 源码比安装版新 (开发场景)
   - `conflict`: 版本冲突 (需要手动解决)

**输出行为**:
- 发现需要更新 → 创建 warning 级别报警
- 发现冲突 → 创建 error 级别报警
- 报警消息示例: "3 个 Skill 有新版本可用", "2 个 Skill 源码与安装版本不一致"

**manifest.json 示例**:

```json
{
  "id": "system/skill-version-checker",
  "name": "Skill 版本同步检查器",
  "description": "检查已安装 Skill 是否有更新或版本冲突",
  "version": "1.0.0",
  "targetDCCs": ["*"],
  "type": "official",
  
  "implementation": {
    "type": "script",
    "entry": "main.py",
    "function": "check_skill_versions"
  },
  
  "inputs": [],
  
  "triggers": [
    {
      "id": "on-dcc-startup",
      "name": "DCC 启动时检查",
      "enabled": true,
      "trigger": {
        "type": "event",
        "dcc": "*",
        "event": "editor.startup",
        "timing": "post"
      },
      "execution": {
        "mode": "silent",
        "timeout": 30
      }
    },
    {
      "id": "scheduled-check",
      "name": "定时检查",
      "enabled": true,
      "trigger": {
        "type": "schedule",
        "mode": "interval",
        "interval": 7200000
      },
      "execution": {
        "mode": "silent",
        "timeout": 60
      }
    }
  ]
}
```

## 5. 前端交互设计

### 5.1 StatusBar 报警指示器

**位置**: StatusBar 左侧，连接状态之后

**视觉设计**:
```
[●已连接] [⚠️ 2] [Maya ●] [DeepSeek] / [Claude] ...
           ↑
        报警指示器
```

**交互行为**:
- **无报警**: 不显示指示器
- **有报警**: 显示图标 + 数量 badge (如: ⚠️ 3, 🚨 1)
- **点击**: 弹出报警列表弹窗
- **样式**:
  - warning: 黄色 ⚠️ 图标
  - error: 红色 🚨 图标
  - 数量 badge: 小圆圈，显示活跃报警总数

### 5.2 报警列表弹窗

**布局**:
```
┌─── 系统报警 ─────────────────────────┐
│ 🚨 工具配置错误                      × │
│   工具 user/batch-rename 缺少字段 nam │
│   [查看详情] [忽略]                    │
│                                      │
│ ⚠️ Skill 版本更新                     │
│   3 个 Skill 有新版本可用             │
│   [查看详情] [立即更新]                │
│                                      │
│ [显示已解决] [清空全部]                │
└─────────────────────────────────────┘
```

**功能**:
- **查看详情**: 跳转到对应工具/Skill 管理页面
- **忽略**: 标记报警为已解决 (PATCH /api/v1/alerts/{id})
- **立即更新**: 触发相关操作 (如批量更新 Skill)
- **显示已解决**: 切换显示历史报警
- **清空全部**: 批量删除已解决的报警

### 5.3 报警状态轮询

**机制**: 
- StatusBar 组件每 30 秒轮询 `GET /api/v1/alerts`
- WebSocket 推送实时报警更新 (可选，优化用户体验)

**状态管理**:
```typescript
// store/alertStore.ts
interface AlertStore {
  alerts: Alert[];
  isLoading: boolean;
  lastUpdate: string;
  
  fetchAlerts: () => Promise<void>;
  createAlert: (alert: AlertCreateRequest) => Promise<void>;
  resolveAlert: (id: string) => Promise<void>;
  deleteAlert: (id: string) => Promise<void>;
}
```

## 6. 存储方案

### 6.1 Alert 存储

**文件位置**: `~/.artclaw/alerts/alerts.json`  
**备份机制**: 每日自动备份到 `alerts-YYYY-MM-DD.json`

**JSON 结构**:
```json
{
  "version": "1.0",
  "alerts": [
    {
      "id": "alert-001",
      "level": "error",
      "source": "tool-compliance-checker",
      "title": "工具配置错误",
      "detail": "工具 user/batch-rename 的 manifest.json 缺少必填字段 name",
      "createdAt": "2026-04-12T02:30:00Z",
      "resolvedAt": null,
      "metadata": {
        "toolId": "user/batch-rename",
        "missingFields": ["name"]
      }
    }
  ],
  "lastCleanup": "2026-04-12T00:00:00Z"
}
```

### 6.2 官方工具存储

**位置**: `~/.artclaw/tools/system/`  
**结构**:
```
~/.artclaw/tools/system/
├── tool-compliance-checker/
│   ├── manifest.json
│   ├── main.py
│   └── lib/
│       └── compliance_rules.py
└── skill-version-checker/
    ├── manifest.json
    ├── main.py
    └── lib/
        └── version_utils.py
```

### 6.3 检查结果缓存

**位置**: `~/.artclaw/cache/system-tools/`  
**内容**:
- `compliance-check-results.json`: 最近的合规检查结果
- `skill-version-results.json`: 最近的版本检查结果
- 自动清理: 保留最近 30 天的记录

## 7. 部署与安装

### 7.1 官方工具自动部署

ArtClaw Tool Manager 首次启动时：

1. 检查 `~/.artclaw/tools/system/` 是否存在
2. 不存在则从项目内置目录复制官方工具
3. 注册官方工具的触发规则到 trigger engine
4. 启动后台监听和定时任务

### 7.2 依赖要求

**Python 库**:
- `watchdog`: 文件系统监听
- `gitpython`: Git 操作 (Skill 版本检查)
- `semver`: 语义化版本解析
- `jsonschema`: manifest.json 格式验证

**系统要求**:
- ~/.artclaw/ 目录可读写
- 对工具目录的文件监听权限

## 8. 错误处理与容错

### 8.1 工具执行失败

- **超时处理**: 工具执行超过设定时间自动终止
- **异常捕获**: Python 异常不影响主流程，记录到日志
- **重试机制**: 网络/IO 错误自动重试 (最多 3 次)

### 8.2 存储异常

- **JSON 损坏**: 自动恢复到最近备份
- **磁盘空间不足**: 清理旧记录，保留关键报警
- **权限问题**: 降级到只读模式，仅显示报警不创建

### 8.3 报警降级

当报警数量过多时 (>100 条)：
1. 只显示 error 级别报警
2. 同类 warning 合并为一条
3. 自动清理 7 天前的已解决报警

## 9. 扩展性设计

### 9.1 自定义检查器

用户可以创建自己的"检查器工具"：
- 实现相同的 manifest.json 规范
- 调用 `/api/v1/alerts` API 创建报警
- 通过触发机制自动执行

### 9.2 报警插件化

报警系统支持扩展：
- **通知渠道**: 邮件、钉钉、Slack 等
- **报警规则**: 自定义严重级别、分组规则
- **动作绑定**: 报警触发时自动执行脚本

### 9.3 Dashboard 集成

未来可扩展系统健康 Dashboard：
- 工具运行统计
- 报警趋势图表
- 系统性能监控

## 10. 安全考虑

### 10.1 文件系统安全

- 限制工具只能读写 ~/.artclaw/ 目录
- 禁止执行外部系统命令 (除 Git 操作)
- 日志脱敏，不记录敏感路径信息

### 10.2 API 安全

- 报警 API 需要身份验证 (Token/Session)
- 限制报警创建频率 (防止恶意刷屏)
- 输入验证和 XSS 防护

## 11. 测试策略

### 11.1 单元测试

- 合规检查规则测试 (各种错误场景)
- Alert 模型 CRUD 操作
- 文件监听触发逻辑

### 11.2 集成测试

- 完整工具检查流程 (创建工具 → 检查 → 报警)
- StatusBar 报警显示和交互
- 系统工具自动部署

### 11.3 性能测试

- 大量工具目录扫描 (1000+ 工具)
- 高频文件变更监听
- 报警系统负载测试

---

**总行数**: 389 行 (符合 400 行以内要求)