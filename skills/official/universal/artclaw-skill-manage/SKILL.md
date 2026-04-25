---
name: artclaw-skill-manage
description: >
  Manage ArtClaw skills: list, execute, install, uninstall, update, publish, rename,
  and create new skills. Use when AI needs to: (1) install/uninstall/update skills,
  (2) publish user skills to source repository, (3) list available skills and their info,
  (4) create new skills with AI-generated code, (5) rename or reorganize skills.
  All operations via Python API in DCC (run_ue_python or run_python).
  NOT for: OpenClaw CLI skill commands, ClawHub marketplace publishing.
---

# ArtClaw 技能管理

管理 ArtClaw 的 Skill 技能包：列出、执行、安装、卸载、更新、发布、重命名、创建。

## 版本与更新模型

Skill 存在于两个位置，数据流是单向的：

```
源码 skills/{layer}/{dcc}/{name}/     ──更新──>  已安装 ~/.openclaw/workspace/skills/{name}/
  (Git 仓库，分发给其他用户)            <──发布──    (本地运行时，AI 实际使用)
```

- **编辑**：修改已安装目录中的文件（SKILL.md / `__init__.py` / references）
- **发布**：`publish_skill()` — 已安装目录 → 源码仓库，自动 bump 版本 + git commit
- **更新**：`update_skill()` / `sync_all()` — 源码仓库 → 已安装目录（覆盖安装）
- **变更检测**：有版本号用版本对比，无版本号用文件内容 hash 对比

## 调用方式

通过 MCP 工具 `run_ue_python`（UE）或 `run_python`（Maya/Max）执行 Python 代码。

---

## 常用操作

### 列出 Skill

```python
from skill_hub import get_skill_hub
hub = get_skill_hub()
for s in hub.list_skills():
    print(f"[{s['category']}] {s['name']} v{s.get('version','?')} - {s['description']}")
```

### 安装 / 更新 / 全量更新

```python
from skill_sync import install_skill, update_skill, sync_all

install_skill("ue57_batch_rename_actors")   # 从源码安装单个
update_skill("ue57_get_material_nodes")     # 从源码更新单个
sync_all()                                   # 安装未安装的 + 更新版本不一致的
```

### 卸载

```python
from skill_sync import uninstall_skill
uninstall_skill("ue57_batch_rename_actors")
```

### 发布（已安装 → 源码仓库）

```python
from skill_sync import publish_skill
result = publish_skill(
    "ue57_my_tool",
    target_layer="marketplace",   # 或 "official"
    bump="patch",                  # patch / minor / major
    changelog="修复了多选时的bug",
    dcc="unreal",                  # universal / unreal / maya / max
)
```

### 对比源码 vs 已安装

```python
from skill_sync import compare_source_vs_runtime
diff = compare_source_vs_runtime()
# diff: {available, installed, updatable, orphaned, project_root, error}
```

### 重命名

```python
from skill_sync import rename_skill
result = rename_skill("old_skill_name", "new_skill_name")
# 自动更新: 安装目录 + manifest.json + SKILL.md frontmatter + 源码目录
```

---

## 创建新 Skill

### 步骤

1. `hub.auto_name(description)` 生成名称
2. AI 生成 `__init__.py` + `manifest.json`
3. **必须**生成 `SKILL.md`（含 YAML frontmatter，见下方模板）
4. 保存到已安装目录 `~/.openclaw/workspace/skills/<skill_name>/`
5. `publish_skill()` 发布到源码仓库

### SKILL.md 模板（OpenClaw 兼容格式）

```markdown
---
name: my-skill-name
description: >
  英文描述。必须包含 "Use when AI needs to:" + 编号列表。
  末尾加 "NOT for:" 说明不适用场景。
license: MIT
metadata:
  artclaw:
    display_name: "中文显示名"
    author: ArtClaw
    software: unreal_engine
    category: material
    risk_level: low
    version: 1.0.0
    tags: ["material", "node"]
---

# Skill 标题

## 调用方式

通过 `run_ue_python` 或 `run_python` 执行。

## 操作示例

（代码示例）
```

### Frontmatter 字段规范

**OpenClaw 允许的顶层字段**（必须遵守，否则无法发布到 ClawHub）：

| 字段 | 必需 | 说明 |
|------|------|------|
| `name` | ✅ | kebab-case，如 `ue57-material-node-edit` |
| `description` | ✅ | 英文，含触发条件和排除场景 |
| `license` | 可选 | 默认 MIT |
| `allowed-tools` | 可选 | 声明需要的 OpenClaw 工具，如 `["message"]` |
| `metadata` | 可选 | 嵌套对象，含 `openclaw` 和 `artclaw` 子块 |

**ArtClaw 专属字段**（放在 `metadata.artclaw.*` 下）：

| 字段 | 说明 |
|------|------|
| `display_name` | 中文显示名 |
| `author` | 作者 |
| `software` | `unreal_engine` / `maya` / `3ds_max` / `universal` |
| `category` | `scene` / `asset` / `material` / `lighting` / `render` / `utils` / ... |
| `risk_level` | `low` / `medium` / `high` / `critical` |
| `version` | semver，如 `1.0.0` |
| `tags` | 标签数组 |

> **向后兼容**: 旧格式（字段在顶层）仍可被 skill_hub 解析，但新 Skill 必须使用新格式。

## Skill 命名规范

格式: `{dcc}{major_version}-{skill-name}`（kebab-case，OpenClaw 标准）

示例: `ue57-material-node-edit`, `maya24-curve-tools`, `artclaw-memory`（通用）

> skill_hub 内部自动将 kebab-case 转为 snake_case（`replace("-", "_")`），MCP 工具注册和 Python 模块名使用 snake_case。

## Skill 分层

| 优先级 | 层级 | 说明 |
|--------|------|------|
| 最高 | `official` | 官方内置 |
| 高 | `marketplace` | 市集/团队共享 |
| 中 | `user` | 用户自定义 |
| 低 | `custom` | 临时实验 |

每层下按 DCC 分子目录：`universal/`、`unreal/`、`maya/`、`max/`（可扩展）
