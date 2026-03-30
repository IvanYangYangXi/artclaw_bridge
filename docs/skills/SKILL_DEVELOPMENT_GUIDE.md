# ArtClaw Skill 开发规范

> **版本**: v0.3  
> **日期**: 2026-03-30  
> **状态**: 正式  
> **适用范围**: 所有 ArtClaw Skill 开发者

---

## 1. 概述

Skill 是 ArtClaw 中可被 AI Agent 调用的最小功能单元。每个 Skill 通过 `@ue_tool` 装饰器声明为 MCP Tool，安装到统一的外部目录（`~/.openclaw/skills/`）后由 Skill Hub 自动发现、注册、热重载。

**安装目录变更**：Skills 现已统一安装到外部目录（`~/.openclaw/skills/` 或按平台配置），不再存储在 UE 插件内部的 `Content/Python/Skills/`。`skill_hub.py` 通过 `~/.artclaw/config.json` 的 `skills.installed_path` 读取安装路径。

本文档定义 Skill 开发的强制规范与推荐实践。

---

## 2. 文件结构

### 2.1 Skill 包目录（推荐）

每个 Skill 是一个独立目录，安装到统一的外部目录：

```
~/.openclaw/skills/my_skill/          # 统一安装目录（扁平结构）
├── SKILL.md                          # AI 文档 + OpenClaw/ClawHub 分发
├── manifest.json                     # MCP 注册元数据
├── __init__.py                       # Python 入口（@ue_tool 装饰器）
├── references/                       # 可选，参考文档
└── scripts/                          # 可选，辅助脚本
```

**SKILL.md** — OpenClaw 兼容格式，YAML frontmatter (`name` + `description`) + Markdown body。
用于 AI 理解技能用途、ClawHub 分发、以及作为 manifest.json 的 fallback。

**manifest.json** — ArtClaw 运行时元数据，Skill Hub 用它注册 MCP 工具、版本匹配、冲突检测。

> **最小要求**: `manifest.json` 或 `SKILL.md` 至少有一个。推荐两个都有。
> 详见 [MANIFEST_SPEC.md](MANIFEST_SPEC.md)。

### 2.2 旧版单文件 Skill（向后兼容）

```
Skills/
├── scene_ops.py        # 场景操作 Skill
├── asset_ops.py        # 资产操作 Skill
├── material_ops.py     # 材质操作 Skill
├── level_ops.py        # 关卡操作 Skill
├── example_skills.py   # 示例 Skill
└── ...
```

### 2.2 文件命名

- 使用 **蛇形命名** (snake_case)
- 按功能分类归组，一个文件包含同类别的多个 Skill
- 文件名应反映 Skill 类别：`{category}_ops.py`

---

## 3. Skill 声明规范

### 3.1 装饰器用法

```python
from skill_hub import tool as ue_tool

@ue_tool(
    name="skill_name",              # 必填：全局唯一标识，snake_case
    description="English desc...",   # 必填：AI 可见的英文描述
    category="scene",                # 必填：标准分类
    risk_level="low",                # 必填：low / medium / high / critical
)
def skill_name(arguments: dict) -> str:
    """中文文档说明"""
    ...
```

### 3.2 name 命名规范

| 规则 | 示例 | 反例 |
|------|------|------|
| 全小写 snake_case | `get_selected_actors` | `GetSelectedActors` |
| 动词开头 | `spawn_actor`, `delete_actor` | `actor_spawn` |
| 不超过 40 字符 | `create_material_instance` | `create_a_new_material_instance_from_parent` |
| 不含模块前缀 | `get_materials` | `material_get_materials` |

### 3.3 description 规范

- **必须使用英文**（AI 消费，中文可能导致 token 浪费）
- 第一句话概括功能，后续补充关键行为
- 说明返回值包含什么
- 适当说明使用场景

```python
# ✅ 好的描述
description="Spawn a new actor in the current level by class name. "
            "Supports setting initial location, rotation, and display label. "
            "Returns the spawned actor's name, class, and transform."

# ❌ 差的描述
description="spawn actor"
```

### 3.4 category 标准枚举

| Category | 说明 | 示例 Skill |
|----------|------|-----------|
| `scene` | 场景/Actor 操作 | spawn_actor, delete_actor |
| `asset` | 资产管理 | load_asset, rename_asset |
| `material` | 材质操作 | get_materials, set_material |
| `level` | 关卡操作 | save_level, open_level |
| `lighting` | 灯光设置 | create_light, set_light_params |
| `render` | 渲染相关 | set_render_settings |
| `blueprint` | 蓝图操作 | compile_blueprint |
| `animation` | 动画相关 | play_animation |
| `utils` | 工具类 | batch_rename, find_actors |

### 3.5 risk_level 分级

| 级别 | 说明 | 示例 |
|------|------|------|
| `low` | 只读操作，无副作用 | get_materials, get_level_actors |
| `medium` | 可撤销的写操作 | spawn_actor, set_material |
| `high` | 难以撤销的操作 | delete_actor, rename_asset |
| `critical` | 不可逆或影响面大 | delete_all_actors, save_all |

---

## 4. 函数签名规范

### 4.1 统一签名

**所有 Skill 函数必须使用以下签名：**

```python
def skill_name(arguments: dict) -> str:
```

- **参数**: 始终为 `arguments: dict`，从中提取具体参数
- **返回值**: 始终为 `str`（JSON 格式字符串）

### 4.2 参数提取

```python
def my_skill(arguments: dict) -> str:
    # 必填参数
    actor_name = arguments.get("actor_name", "")
    if not actor_name:
        return json.dumps({"success": False, "error": "actor_name is required"})
    
    # 可选参数（带默认值）
    limit = arguments.get("limit", 20)
    include_transform = arguments.get("include_transform", True)
```

### 4.3 参数命名规范

| 规则 | 示例 | 反例 |
|------|------|------|
| snake_case | `actor_name` | `actorName`, `ActorName` |
| 具体明确 | `material_path` | `path`, `mat` |
| 布尔用 is/has/include | `include_transform` | `transform` |
| 列表用复数 | `actor_names` | `actor_name_list` |
| 路径类参数带 _path 后缀 | `asset_path`, `level_path` | `asset`, `level` |

### 4.4 常用参数类型

| 参数 | 类型 | JSON Schema |
|------|------|-------------|
| 名称/路径 | `string` | `{"type": "string"}` |
| 数量/索引 | `integer` | `{"type": "integer"}` |
| 开关 | `boolean` | `{"type": "boolean"}` |
| 坐标 | `object` | `{"type": "object", "properties": {"x": ..., "y": ..., "z": ...}}` |
| 名称列表 | `array` | `{"type": "array", "items": {"type": "string"}}` |

---

## 5. 返回值标准格式

### 5.1 成功响应

```python
return json.dumps({
    "success": True,
    # ... 业务数据
})
```

### 5.2 失败响应

```python
return json.dumps({
    "success": False,
    "error": "Human-readable error message in English"
})
```

### 5.3 标准字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `success` | bool | ✅ | 操作是否成功 |
| `error` | string | 失败时必需 | 英文错误描述 |
| `count` | int | 列表结果推荐 | 结果数量 |
| `actors` | array | Actor 相关 | Actor 列表 |
| `actor` | object | 单 Actor 结果 | Actor 信息 |

### 5.4 Actor 数据标准格式

```python
{
    "name": "StaticMeshActor_0",      # get_name()
    "label": "MyMesh",                # get_actor_label()
    "class": "StaticMeshActor",       # get_class().get_name()
    "location": {"x": 0, "y": 0, "z": 0},
    "rotation": {"pitch": 0, "yaw": 0, "roll": 0},
    "scale": {"x": 1, "y": 1, "z": 1},
    "tags": ["tag1"],
    "visible": True,
}
```

### 5.5 数据量控制

- Actor 列表默认限制 **100** 条，通过 `limit` 参数控制
- 超出限制时返回 `truncated: true` 和 `total` 字段
- 坐标值 `round()` 到 2 位小数
- 字符串长度超过 500 字符时截断

---

## 6. 错误处理模式

### 6.1 三层错误处理

```python
@ue_tool(name="my_skill", description="...", category="scene", risk_level="low")
def my_skill(arguments: dict) -> str:
    """我的 Skill"""
    # 第 1 层：环境检查
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})
    
    # 第 2 层：参数校验
    actor_name = arguments.get("actor_name", "")
    if not actor_name:
        return json.dumps({"success": False, "error": "actor_name is required"})
    
    # 第 3 层：业务逻辑 try-except
    try:
        # ... UE API 调用
        return json.dumps({"success": True, ...})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
```

### 6.2 常见错误消息模板

```python
# 参数缺失
"actor_name is required"

# 对象未找到
f"Actor not found: {actor_name}"
f"Asset not found: {asset_path}"

# 类型错误
f"Invalid actor class: {class_name}"

# 操作失败
f"Failed to spawn actor: {str(e)}"
f"Failed to save level: {str(e)}"
```

### 6.3 禁止事项

- ❌ 不要抛出未捕获的异常（会导致 MCP 返回 isError=true）
- ❌ 不要返回非 JSON 字符串
- ❌ 不要在错误消息中包含完整 traceback（太长，浪费 token）
- ❌ 不要返回 None

---

## 7. 事务保护

### 7.1 写操作必须使用事务

```python
try:
    with unreal.ScopedEditorTransaction("Spawn Actor via AI"):
        actor = unreal.EditorLevelLibrary.spawn_actor_from_object(...)
    return json.dumps({"success": True, ...})
except Exception as e:
    return json.dumps({"success": False, "error": str(e)})
```

### 7.2 事务命名规范

格式：`"{Action} via AI"` 或 `"AI: {Action}"`

```python
"Spawn Actor via AI"
"Delete Actor via AI"
"Set Material via AI"
"AI: Rename Asset"
```

---

## 8. UE 外部测试支持

### 8.1 unreal 模块保护

每个 Skill 文件头部必须包含：

```python
try:
    import unreal
except ImportError:
    unreal = None  # 允许在 UE 外部测试
```

### 8.2 函数内检查

```python
if unreal is None:
    return json.dumps({"success": False, "error": "Not running in Unreal Engine"})
```

---

## 9. 完整 Skill 模板

```python
"""
{category}_ops.py - {Category} 操作 Skill
============================================

Skill Hub 自动发现并注册。保存后热重载生效。
"""

from skill_hub import tool as ue_tool
import json

try:
    import unreal
except ImportError:
    unreal = None


# ============================================================================
# 辅助函数
# ============================================================================

def _find_actor_by_name(actor_name: str):
    """按名称查找 Actor（匹配 name 或 label）"""
    actors = unreal.EditorLevelLibrary.get_all_level_actors()
    for actor in actors:
        if (str(actor.get_name()) == actor_name or 
            str(actor.get_actor_label()) == actor_name):
            return actor
    return None


def _prune_actor(actor) -> dict:
    """将 Actor 转为精简字典"""
    data = {
        "name": str(actor.get_name()),
        "label": str(actor.get_actor_label()),
        "class": str(actor.get_class().get_name()),
    }
    try:
        loc = actor.get_actor_location()
        rot = actor.get_actor_rotation()
        scale = actor.get_actor_scale3d()
        data["location"] = {"x": round(loc.x, 2), "y": round(loc.y, 2), "z": round(loc.z, 2)}
        data["rotation"] = {"pitch": round(rot.pitch, 2), "yaw": round(rot.yaw, 2), "roll": round(rot.roll, 2)}
        data["scale"] = {"x": round(scale.x, 2), "y": round(scale.y, 2), "z": round(scale.z, 2)}
    except Exception:
        pass
    return data


# ============================================================================
# Skills
# ============================================================================

@ue_tool(
    name="example_skill",
    description="One-line English description of what this skill does. "
                "Additional details about parameters and return values.",
    category="scene",
    risk_level="low",
)
def example_skill(arguments: dict) -> str:
    """中文功能说明"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    # 参数提取与校验
    actor_name = arguments.get("actor_name", "")
    if not actor_name:
        return json.dumps({"success": False, "error": "actor_name is required"})

    try:
        # 业务逻辑
        actor = _find_actor_by_name(actor_name)
        if actor is None:
            return json.dumps({"success": False, "error": f"Actor not found: {actor_name}"})

        return json.dumps({
            "success": True,
            "actor": _prune_actor(actor),
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
```

---

## 10. 代码风格

### 10.1 文件头部

```python
"""
module_name.py - 模块说明
==========================

功能描述。Skill Hub 自动发现并注册。保存后热重载生效。
"""

from skill_hub import tool as ue_tool
import json

try:
    import unreal
except ImportError:
    unreal = None
```

### 10.2 分节注释

```python
# ============================================================================
# 辅助函数
# ============================================================================

# ============================================================================
# Scene Skills
# ============================================================================
```

### 10.3 文档字符串

- 装饰器 `description` 用**英文**（给 AI 看）
- 函数 docstring 用**中文**（给开发者看）

---

## 11. 审查清单

提交 Skill 前，确保满足以下条件：

- [ ] 使用 `@ue_tool` 装饰器声明
- [ ] name 为 snake_case，全局唯一
- [ ] description 为英文，清晰描述功能
- [ ] category 和 risk_level 正确设置
- [ ] 函数签名为 `(arguments: dict) -> str`
- [ ] 返回值为标准 JSON 格式，包含 `success` 字段
- [ ] 必填参数有校验和错误提示
- [ ] 写操作包裹在 `ScopedEditorTransaction` 中
- [ ] `unreal is None` 有保护处理
- [ ] 无未捕获异常
- [ ] 列表结果有数量限制
- [ ] 坐标值已 round 到 2 位小数
- [ ] 可通过 `artclaw skill test` 本地验证
