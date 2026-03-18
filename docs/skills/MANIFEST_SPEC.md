# manifest.json 规范

**版本**: 1.1  
**状态**: 正式

每个 ArtClaw Skill **推荐同时包含** `SKILL.md` 和 `manifest.json` 两个文件：

| 文件 | 用途 | 必需 |
|------|------|------|
| `manifest.json` | MCP 工具注册、版本匹配、冲突检测 | 推荐（可由 SKILL.md 自动推断） |
| `SKILL.md` | AI 可读文档 + OpenClaw/ClawHub 分发 | 推荐（向后兼容可省略） |

### 双文件策略

```
my_skill/
├── SKILL.md           ← AI 文档 + ClawHub 分发（OpenClaw 格式）
├── manifest.json      ← MCP 注册元数据（ArtClaw 格式）
├── __init__.py        ← Python 入口
└── references/        ← 可选，参考文档
```

**加载优先级**: `manifest.json` > `SKILL.md` fallback

- 如果 `manifest.json` 存在 → Skill Hub 直接使用它注册 MCP 工具
- 如果只有 `SKILL.md` → Skill Hub 从 frontmatter 提取元数据 + AST 扫描 `@ue_tool` 装饰器自动构建 manifest
- 如果两个都存在 → `manifest.json` 用于 MCP 注册，`SKILL.md` 用于 AI 理解和分发

### SKILL.md 格式（OpenClaw 兼容）

```yaml
---
name: my-skill                    # kebab-case (OpenClaw 惯例)
description: >
  One-line description of what this skill does and when to use it.
  Include triggers and contexts for AI to understand.
---
```

frontmatter 仅需 `name` + `description`。body 部分为 Markdown 格式的使用文档。

## 完整字段定义

### 必需字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `manifest_version` | string | Manifest 规范版本，当前固定为 `"1.0"` | `"1.0"` |
| `name` | string | Skill 唯一标识符。snake_case，动词开头，≤64 字符 | `"generate_material_documentation"` |
| `display_name` | string | 显示名称（支持中文） | `"生成材质使用文档"` |
| `description` | string | 一句话描述 Skill 功能 | `"Read a master material's blueprint..."` |
| `version` | string | 语义化版本号 (semver) | `"1.0.0"` |
| `author` | string | 作者名称 | `"ArtClaw"` |
| `software` | string | 适用 DCC 软件。枚举值见下方 | `"unreal_engine"` |
| `category` | string | 标准分类。枚举值见下方 | `"material"` |
| `risk_level` | string | 风险级别。枚举值见下方 | `"low"` |
| `entry_point` | string | 入口文件名 | `"__init__.py"` |
| `tools` | array | 暴露的工具列表（至少一个） | 见下方 |

### 可选字段

| 字段 | 类型 | 默认值 | 说明 | 示例 |
|------|------|--------|------|------|
| `license` | string | `"MIT"` | 许可证 | `"MIT"` |
| `software_version` | object | `null` | 适用的软件版本范围 | `{"min": "5.3", "max": "5.5"}` |
| `dependencies` | array | `[]` | 依赖的其他 Skill | `["artclaw.universal.utils>=1.0.0"]` |
| `tags` | array | `[]` | 搜索标签 | `["material", "documentation"]` |
| `icon` | string | `null` | 图标文件路径（相对于 Skill 目录） | `"icon.png"` |
| `config` | object | `null` | Skill 自定义配置 | `{"max_batch_size": 100}` |

## 枚举值

### software

| 值 | 说明 |
|----|------|
| `"universal"` | 跨平台通用 |
| `"unreal_engine"` | Unreal Engine |
| `"maya"` | Autodesk Maya |
| `"3ds_max"` | Autodesk 3ds Max |

### category

| 值 | 显示名 | 说明 |
|----|--------|------|
| `"scene"` | 场景操作 | Actor、Level、Transform |
| `"asset"` | 资产管理 | 导入、导出、迁移 |
| `"material"` | 材质编辑 | 材质参数、材质图表 |
| `"lighting"` | 灯光设置 | 光源、光照构建 |
| `"render"` | 渲染设置 | 渲染参数、后处理 |
| `"blueprint"` | 蓝图操作 | 蓝图编辑、节点 |
| `"animation"` | 动画相关 | 动画序列、蒙太奇 |
| `"ui"` | UI/UMG | Widget、UI 布局 |
| `"utils"` | 工具类 | 通用辅助工具 |
| `"integration"` | 第三方集成 | 外部服务对接 |
| `"workflow"` | 工作流自动化 | 批处理、流水线 |

完整定义参见 `skills/categories.py`。

### risk_level

| 值 | 说明 | 适用场景 |
|----|------|----------|
| `"low"` | 只读操作，无副作用 | 查询、文档生成、信息展示 |
| `"medium"` | 可撤销的修改操作 | 重命名、属性修改（需 `ScopedEditorTransaction`） |
| `"high"` | 不可撤销的修改 | 删除资产、文件操作 |
| `"critical"` | 影响项目全局的操作 | 项目设置、构建配置 |

## tools 数组

每个元素描述一个暴露的工具：

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | 工具名称，与代码中 `@ue_tool(name=...)` 一致 |
| `description` | string | ✅ | 工具描述，AI Agent 依据此理解工具用途 |

## software_version 对象

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `min` | string | ❌ | 最低支持版本（包含） |
| `max` | string | ❌ | 最高支持版本（包含） |

省略 `min` 表示无下限，省略 `max` 表示无上限。

## 完整示例

### 基础示例

```json
{
  "manifest_version": "1.0",
  "name": "list_scene_actors",
  "display_name": "列出场景 Actor",
  "description": "List all actors in the current level with optional type filtering",
  "version": "1.0.0",
  "author": "ArtClaw",
  "license": "MIT",
  "software": "unreal_engine",
  "software_version": {
    "min": "5.3",
    "max": "5.5"
  },
  "category": "scene",
  "risk_level": "low",
  "dependencies": [],
  "tags": ["scene", "actor", "query"],
  "entry_point": "__init__.py",
  "tools": [
    {
      "name": "list_scene_actors",
      "description": "List all actors in the current level, optionally filtered by class"
    }
  ]
}
```

### 高级示例（多工具）

```json
{
  "manifest_version": "1.0",
  "name": "batch_material_editor",
  "display_name": "批量材质编辑器",
  "description": "Batch edit material parameters across multiple material instances",
  "version": "2.1.0",
  "author": "ArtClaw",
  "license": "MIT",
  "software": "unreal_engine",
  "software_version": {
    "min": "5.1",
    "max": "5.5"
  },
  "category": "material",
  "risk_level": "medium",
  "dependencies": [
    "artclaw.universal.utils>=1.0.0"
  ],
  "tags": ["material", "batch", "parameters", "editor"],
  "entry_point": "__init__.py",
  "icon": "icon.png",
  "tools": [
    {
      "name": "batch_set_scalar_parameter",
      "description": "Set a scalar parameter value across multiple material instances"
    },
    {
      "name": "batch_set_texture_parameter",
      "description": "Set a texture parameter across multiple material instances"
    },
    {
      "name": "preview_batch_changes",
      "description": "Preview what would change without applying (dry-run mode)"
    }
  ],
  "config": {
    "max_batch_size": 200,
    "timeout_seconds": 120,
    "enable_undo": true
  }
}
```

## 验证规则

1. `manifest_version` 必须为 `"1.0"`
2. `name` 必须匹配正则 `^[a-z][a-z0-9_]{0,63}$`
3. `version` 必须符合 semver（`MAJOR.MINOR.PATCH`）
4. `software` 必须是已定义的枚举值
5. `category` 必须是已定义的枚举值
6. `risk_level` 必须是已定义的枚举值
7. `tools` 数组至少包含一个元素
8. 每个 `tools[].name` 必须在 `__init__.py` 中有对应的 `@ue_tool` 装饰器

## 与 skill_hub 的关系

`manifest.json` 在以下时机被读取：

1. **加载时**: skill_hub 扫描 Skill 目录，读取 manifest 判断是否加载
2. **注册时**: 根据 `tools` 数组注册到 MCP 工具列表
3. **版本匹配时**: 根据 `software_version` 判断是否适用于当前 DCC 版本
4. **冲突检测时**: 根据 `name` 检测同名 Skill 覆盖关系
