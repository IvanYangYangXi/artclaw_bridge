<!-- Ref: docs/specs/sdk-skill-spec.md -->
# Skill SDK 标准化规范

> 定义 Skill 开发的标准接口、规范和工具链。
> 索引文档：[SDK/API 标准化总览](./sdk-api-standardization-overview.md)

## 概述

Skill 是 ArtClaw 中 AI 可调用的功能单元。每个 Skill 包含元数据定义（manifest.json / SKILL.md）
和 Python 实现（`__init__.py`），通过 `@artclaw_tool` 装饰器注册为 MCP 工具。

### 相关已有文档

| 文档 | 位置 | 内容 |
|------|------|------|
| Manifest 规范 | `docs/skills/MANIFEST_SPEC.md` | manifest.json 字段定义 |
| Skill 开发指南 | `docs/skills/SKILL_DEVELOPMENT_GUIDE.md` | 开发最佳实践 |
| 贡献指南 | `docs/skills/CONTRIBUTING.md` | PR 提交规范 |
| Skill 管理系统 | `docs/specs/skill-management-system.md` | 加载/分层/热重载 |

## S1 — manifest.json JSON Schema

### 当前状态

字段定义在 `docs/skills/MANIFEST_SPEC.md` 中有文档描述，
但缺少机器可读的 JSON Schema 文件。

### 标准化方案

生成 `skills/manifest.schema.json`，CLI 的 `artclaw skill test` 命令用它做校验。

### 必需字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `manifest_version` | string | 固定 `"1.0"` | `"1.0"` |
| `name` | string | snake_case, ≤64 字符 | `"ue57_get_material_nodes"` |
| `display_name` | string | 显示名（支持中文） | `"获取材质节点"` |
| `description` | string | 一行描述（英文，AI 可见） | `"Get all expression nodes..."` |
| `version` | string | 语义版本 MAJOR.MINOR.PATCH | `"1.0.0"` |
| `author` | string | 作者名 | `"Ivan(杨己力)"` |
| `software` | string | 目标平台枚举 | `"unreal_engine"` |
| `category` | string | 分类枚举 | `"material"` |
| `risk_level` | string | 风险等级 | `"low"` |
| `entry_point` | string | 入口文件名 | `"__init__.py"` |
| `tools` | array | 工具列表 (≥1) | 见下方 |

### 可选字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `license` | string | `"MIT"` | 许可证 |
| `software_version` | object | `null` | `{min, max}` 版本范围 |
| `dependencies` | array | `[]` | 依赖的其他 Skill |
| `tags` | array | `[]` | 搜索标签 |
| `icon` | string | `null` | 图标文件路径 |
| `config` | object | `null` | 自定义配置 |

### software 枚举

`universal`, `unreal_engine`, `maya`, `3ds_max`, `blender`,
`houdini`, `substance_painter`, `substance_designer`, `comfyui`

### category 枚举

`scene`, `asset`, `material`, `lighting`, `render`, `blueprint`,
`animation`, `ui`, `utils`, `integration`, `workflow`

### risk_level 枚举

| 等级 | 说明 | 示例 |
|------|------|------|
| `low` | 只读，无副作用 | 查询操作 |
| `medium` | 可撤销的修改 | 属性编辑 |
| `high` | 难以撤销 | 文件删除 |
| `critical` | 不可逆或大范围影响 | 批量删除 |

## S2 — Skill 入口函数签名

### 统一装饰器：`@artclaw_tool`

```python
from skill_hub import tool as artclaw_tool  # 向后兼容 ue_tool

@artclaw_tool(
    name="tool_name",           # 必需，snake_case，全局唯一
    description="...",           # 必需，英文，AI 可见
    category="scene",            # 必需，标准分类
    risk_level="low",            # 必需，风险评估
)
def tool_name(arguments: dict) -> str:
    """中文文档字符串"""
    ...
```

### 签名约束（不可违反）

1. 参数：固定为 `arguments: dict`
2. 返回值：固定为 `str`（JSON 格式）
3. 装饰器 `@artclaw_tool` 必须存在
4. 函数名 = 装饰器中的 `name`

### 向后兼容与迁移策略

`@ue_tool` **永久保留**，作为 `@artclaw_tool` 的别名，无需迁移已有代码：

```python
# skill_hub.py 中
ue_tool = artclaw_tool  # 别名，永久保留，向后兼容
```

**迁移策略说明：**

| 场景 | 建议 |
|------|------|
| 已有 Skill 使用 `@ue_tool` | **保持不变**，无需修改，运行时等价 |
| 新编写的 Skill | 推荐使用 `@artclaw_tool`（更清晰的命名） |
| 强制迁移 | **不要求**，不会有弃用警告或兼容性破坏 |

> ⚠️ `@ue_tool` 不会被废弃（deprecated）。保留它是有意为之的设计，
> 避免大量已有 Skill 代码因重命名而产生维护负担。

## S3 — Skill 返回值 Schema

### 标准返回格式

```python
# 成功
{"success": True, "data": {...}, "count": 5}

# 失败
{"success": False, "error": "Human-readable English error message"}
```

### 必需字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | bool | 必须存在 |
| `error` | string | `success=False` 时必须存在 |

### 可选字段（约定）

| 字段 | 类型 | 说明 |
|------|------|------|
| `data` | any | 业务数据 |
| `count` | int | 列表结果数量 |
| `truncated` | bool | 结果是否被截断 |

### 辅助函数（建议提供）

```python
def success_result(**kwargs) -> str:
    return json.dumps({"success": True, **kwargs})

def error_result(msg: str) -> str:
    return json.dumps({"success": False, "error": msg})
```

## S4 — 错误处理三层契约

每个 Skill 函数必须包含三层错误处理：

```python
@artclaw_tool(name="example", ...)
def example(arguments: dict) -> str:
    # 第一层：环境检查
    if unreal is None:
        return error_result("Not running in Unreal Engine")

    # 第二层：参数校验
    name = arguments.get("name", "")
    if not name:
        return error_result("name is required")

    # 第三层：业务逻辑异常捕获
    try:
        # DCC API 调用...
        return success_result(data=result)
    except Exception as e:
        return error_result(str(e))
```

### 禁止行为

- ❌ 不捕获异常（导致 MCP isError=true）
- ❌ 返回非 JSON 字符串
- ❌ 返回 None
- ❌ 使用 `print()` 输出（应使用 `unreal.log` 等）
- ❌ 错误信息使用中文（浪费 token）

## S6 — Skill 依赖解析

### 当前状态

manifest.json 有 `dependencies` 字段，但未实现版本范围匹配。

### 待实现

- 版本范围匹配：`skill_name>=1.0.0`
- 缺失依赖检测与提示
- 安装时自动检查依赖

## S7 — Skill Enable/Disable 持久化

### 当前状态

CLI 命令 `artclaw skill enable/disable` 存在但状态未写入配置。

### 待实现

持久化到 `~/.artclaw/config.json` 的 `disabled_skills` 数组。

## S8 — Skill 模板

### 作用

`artclaw skill create --template <name>` 使用模板生成新 Skill 的骨架代码。

### 模板对比

| 维度 | basic | advanced |
|------|-------|----------|
| 定位 | 最小起步骨架 | 生产级框架 |
| 代码行数 | 53 行 | 204 行 |
| 工具数 | 1 | 2 |
| 撤销支持 | ❌ | ✅ ScopedEditorTransaction |
| 批量处理 | ❌ | ✅ batch_items + dry_run |
| 配置对象 | ❌ | ✅ config |
| 依赖声明 | ❌ | ✅ dependencies |

两个模板不建议合并为一个，53 行和 204 行的复杂度跨度合理区分了
新手起步和生产级场景。

> 原 `material_doc` 模板为真实实现（非模板），已删除。

### 与 OpenClaw 规范的关系

**完全兼容**。SKILL.md 的 frontmatter 格式即 OpenClaw 规范：

```yaml
---
name: my-skill
description: >
  Skill 描述，AI 用于匹配意图
---
```

模板的价值是帮助开发者快速生成符合 OpenClaw 规范的骨架，
不是独立的规范体系。已有模板无需修改。

## Skill 生命周期总览

```
开发者编写 Skill → artclaw skill create (从模板生成)
    ↓
manifest.json + SKILL.md + __init__.py (源码)
    ↓
artclaw skill install → ~/.openclaw/skills/ (安装到运行时)
    ↓
SkillRuntime.scan_and_register() → 发现并注册
    ↓
@artclaw_tool 装饰器 → MCP 工具注册
    ↓
AI Agent 调用 → execute_skill(name, arguments) → 返回 JSON
```
