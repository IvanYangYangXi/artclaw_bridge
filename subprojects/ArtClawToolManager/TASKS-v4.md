# Tool Manager v4.0 开发任务清单

> 基于 2026-04-11 Ivan 反馈，更新文档后需要同步到代码

## 已完成的文档更新

- architecture-design.md v4.0
- ui-design.md v4.0
- phase4-tool-list.md (移除 tool 禁用)
- phase4-tool-api.md (移除 tool 禁用, 新增 preset API)

## 代码修改任务

### Task 1: TypeScript 类型更新 (`src/web/src/types/index.ts`)

1. `SkillTab` 类型: `'mine'` → `'platform'`
2. `ToolItem`: 移除 `disabled` 相关（`ToolStatus` 在 Tool 上下文中不包含 `'disabled'`）
3. `ToolItem` / `WorkflowItem`: 新增 `paths?: { installed: string; source?: string }` 字段
4. `ToolItemExtended`: 新增 `presets?: ParameterPreset[]`
5. 确保 `ParameterPreset` 包含 `isDefault?: boolean`, `createdAt`, `updatedAt`

### Task 2: Skills 页面更新 (`src/web/src/pages/Skills/index.tsx`)

1. 标签: `'我的'` → `'平台'` (中文), `'Mine'` → `'Platform'` (英文)
2. 新增收藏筛选按钮 (⭐ toggle)
3. Skill 卡片新增 📂 目录下拉菜单（打开安装目录/源码目录）

### Task 3: SkillCard 更新 (`src/web/src/components/Skills/SkillCard.tsx`)

1. 新增 📂 目录按钮（下拉: 打开安装目录 / 打开源码目录）
2. 确认安装/卸载/更新/启用/禁用按钮完整

### Task 4: Tools 页面更新 (`src/web/src/pages/Tools/index.tsx`)

1. 新增 DCC 软件筛选下拉
2. 新增收藏筛选按钮 (⭐ toggle)
3. 移除禁用相关功能

### Task 5: ToolCard 更新 (`src/web/src/components/Tools/ToolCard.tsx`)

1. 移除禁用按钮
2. 新增 DCC 标签显示
3. 新增参数预设标签展示 (`[默认] [角色] [道具] [+]`)
4. 新增 📂 目录按钮
5. "运行"按钮: 跳转后预填消息

### Task 6: Workflows 页面更新 (`src/web/src/pages/Workflows/index.tsx`)

1. 新增收藏筛选按钮 (⭐ toggle)

### Task 7: WorkflowCard 更新 (`src/web/src/components/Workflows/WorkflowCard.tsx`)

1. 新增 📂 目录按钮
2. 新增发布按钮（用户 Workflow）

### Task 8: Chat 页面 — 钉选 Skill 展示区

1. 在 QuickInput 上方新增 PinnedSkills 组件
2. 显示已钉选的 Skill 标签
3. 点击标签填充输入框
4. 点击 ✕ 取消钉选
5. 无钉选时隐藏

### Task 9: Chat 页面 — 运行跳转引导

1. 从 Workflow/Tool 页面跳转时，输入框预填消息（不自动发送）
2. 消息区显示系统引导卡片

### Task 10: 后端 — Tool API 更新 (`src/server/api/tools.py`)

1. 移除 enable/disable 端点
2. 新增 presets CRUD 端点
3. 新增 open-dir 端点
4. tool_scanner/tool_service: 适配单副本存储模型（用户→`~/.artclaw/tools/user/`, 官方→`{project_root}/tools/`）

### Task 11: 后端 — Skill API 更新 (`src/server/api/skills.py`)

1. 新增 open-dir 端点（安装目录/源码目录）

### Task 12: 后端 — Workflow API 更新 (`src/server/api/workflows.py`)

1. 新增 open-dir 端点
2. 新增 publish 端点（用户→项目目录）
3. workflow_scanner: 适配单副本存储模型（用户→`~/.artclaw/workflows/`, 官方→`{project_root}/workflows/`）

### Task 13: Store 更新

1. `skillsStore.ts`: 新增 `favoritesOnly` filter
2. `toolsStore.ts`: 新增 `dccFilter`, `favoritesOnly` filter; 移除 disabled 相关逻辑
3. `workflowsStore.ts`: 新增 `favoritesOnly` filter
4. `chatStore.ts`: 新增 `pinnedSkills` 状态、`prefillMessage` 状态
5. `appStore.ts`: 确认 `executionContext` 支持 tool 类型

## 优先级

1. Task 1 (类型) → Task 2-7 (页面) → Task 8-9 (Chat) → Task 10-12 (后端) → Task 13 (Store)
2. Store 更新穿插在各 Task 中按需完成

## 参考文档

- `docs/specs/architecture-design.md` v4.0
- `docs/ui/ui-design.md` v4.0
