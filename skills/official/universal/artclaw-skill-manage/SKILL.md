# ArtClaw 技能管理

创建、列出、执行、管理 ArtClaw 的 Skill 技能包，包括安装、发布和查看技能详情。

> **覆盖原 MCP 工具**: `skill_list`, `skill_manage`, `skill_generate`

## 调用方式

通过 MCP 工具 `run_ue_python`（UE）或 `run_python`（Maya/Max）执行 Python 代码操作 Skill Hub。

---

## Python API

### 初始化

```python
from skill_hub import get_skill_hub
hub = get_skill_hub()
```

### 列出所有技能

```python
hub = get_skill_hub()

# 列出全部
skills = hub.list_skills()
for s in skills:
    print(f"[{s['category']}] {s['name']} - {s['description']}")

# 按类别过滤
skills = hub.list_skills(category="material")

# 按软件过滤
skills = hub.list_skills(software="unreal_engine")
```

### 获取技能详情

```python
hub = get_skill_hub()
info = hub.get_skill_info("ue54_artclaw_material")
print(f"名称: {info['name']}")
print(f"描述: {info['description']}")
print(f"层级: {info['source_layer']}")
```

### 执行技能

```python
hub = get_skill_hub()
result = hub.execute_skill("ue54_artclaw_material", {
    "action": "create_material",
    "asset_name": "M_Test",
    "package_path": "/Game/Materials"
})
print(f"执行结果: {result}")
```

---

## Skill 包结构

每个 ArtClaw Skill 是一个目录，包含以下文件：

```
Skills/user/my_skill/
├── manifest.json    # 技能元数据（名称、描述、参数定义、依赖）
├── __init__.py      # 技能执行入口
└── SKILL.md         # 技能说明文档（可选，用于 OpenClaw 匹配）
```

### manifest.json 示例

```json
{
    "manifest_version": "1.0",
    "name": "ue54_batch_rename_actors",
    "display_name": "批量重命名 Actor",
    "description": "批量重命名场景中选中的 Actor",
    "version": "1.0.0",
    "author": "User",
    "software": "unreal_engine",
    "software_version": { "min": "5.4" },
    "category": "scene",
    "risk_level": "low",
    "entry_point": "__init__.py",
    "tools": [
        { "name": "batch_rename_actors", "description": "批量重命名 Actor" }
    ]
}
```

---

## Skill 命名规范

格式: `{dcc}{major_version}_{skill_name}`

| 部分 | 说明 | 示例 |
|------|------|------|
| `dcc` | 软件缩写: `ue` / `maya` / `max` / 空(通用) | `ue` |
| `major_version` | 大版本号（两位数字） | `54` = UE 5.4 |
| `skill_name` | 功能描述（snake_case） | `artclaw_material` |

示例: `ue54_artclaw_material`, `maya24_curve_tools`, `artclaw-memory`(通用)

---

## Skill 分层体系

| 优先级 | 目录 | 说明 |
|--------|------|------|
| 最高 | `official/` | 官方内置技能，随版本更新 |
| 高 | `marketplace/` | 市集技能，团队共享 |
| 中 | `user/` | 用户自定义技能，AI 生成的技能默认存放于此 |
| 低 | `custom/` | 临时/实验性技能 |

同名技能按优先级覆盖：`official` > `marketplace` > `user` > `custom`

### DCC 子目录

每个层级下按 DCC 分子目录：`universal/`（通用）、`unreal/`、`maya/`、`max/`

---

## 创建新 Skill 的流程

1. **自动命名** — 调用 `hub.auto_name(description)` 生成符合规范的名称
2. **AI 生成代码** — 根据用户描述，生成 `__init__.py` 和 `manifest.json`
3. **保存到用户目录** — 将文件保存到 `Skills/user/<skill_name>/`
4. **热加载** — Skill Hub 自动检测新文件并加载，无需重启
5. **生成 OpenClaw SKILL.md**（可选）— 同时在 `~/.openclaw/skills/` 下创建对应的 SKILL.md

### 自动命名 API

```python
hub = get_skill_hub()
name = hub.auto_name("batch rename actors in level")
# UE 5.4 环境 → "ue54_batch_rename_actors"

name = hub.auto_name("auto UV unwrap selected", software="maya")
# → "maya23_auto_uv_unwrap"
```

命名规则:
- 从描述提取英文关键词，去除停用词，取前 4 个词拼接 snake_case
- 自动检测当前 DCC 环境加前缀 (`ue54_` / `maya23_` / `max24_`)
- 自动去重（如已存在则加数字后缀）

### 旧名兼容

以下旧 Skill 名已自动映射到新名（deprecation 警告）：
- `artclaw_material` → `ue54_material_node_edit`
- `ue54_artclaw_material` → `ue54_material_node_edit`
- `get_material_nodes` → `ue54_get_material_nodes`
- `generate_material_documentation` → `ue54_generate_material_documentation`

---

## 使用建议

- 查看可用技能前先用 `hub.list_skills()` 列出全部
- 执行前用 `hub.get_skill_info()` 确认参数要求
- 用户自定义技能放 `user/`，避免修改 `official/`
- 创建新技能时同步生成 OpenClaw SKILL.md，保持两边一致

---

## Skill 安装/卸载/同步/发布 API (Phase 4)

通过 `skill_sync` 模块管理 Skill 的安装部署。

### 对比源码 vs 运行时

```python
from skill_sync import compare_source_vs_runtime
diff = compare_source_vs_runtime()
# diff = {
#   "available": [...],    # 源码有但未安装（可安装）
#   "installed": [...],    # 已安装
#   "updatable": [...],    # 版本不一致（可更新）
#   "orphaned": [...],     # 运行时有但源码没有
#   "project_root": "D:\\...",
#   "error": null
# }
```

### 安装

```python
from skill_sync import install_skill, install_all_available

# 安装单个
result = install_skill("ue54_batch_rename_actors")
# {"ok": True, "message": "已安装: ue54_batch_rename_actors (marketplace)"}

# 安装全部未安装的
result = install_all_available()
```

### 卸载

```python
from skill_sync import uninstall_skill
result = uninstall_skill("ue54_batch_rename_actors")
# 同时删除运行时文件和 ~/.openclaw/skills/ 的文档
```

### 更新

```python
from skill_sync import update_skill, update_all

# 更新单个（从源码覆盖）
result = update_skill("ue54_get_material_nodes")

# 更新全部版本不一致的
result = update_all()
```

### 一键同步

```python
from skill_sync import sync_all
result = sync_all()
# 安装未安装的 + 更新版本不一致的
```

### 发布（用户 Skill → 市集）

```python
from skill_sync import publish_skill
result = publish_skill(
    "ue54_my_tool",
    target_layer="marketplace",   # 或 "official"
    bump="patch",                  # patch / minor / major
    changelog="修复了多选时的bug"
)
# 搬家语义：运行时 user/ → marketplace/
# 同步到源码 skills/marketplace/unreal/
# 自动 git add + commit
```

### 依赖

- `~/.artclaw/config.json` 必须有 `project_root` 字段（install.bat 自动写入）
- 无 project_root 时安装/发布功能不可用，只能查看已安装的
