# ArtClaw 技能管理

创建、列出、执行、安装、卸载、同步、发布 ArtClaw 的 Skill 技能包。

> **覆盖原 MCP 工具**: `skill_list`, `skill_manage`, `skill_generate`

## 何时使用本 Skill

| 场景 | 使用本 Skill | 不使用本 Skill |
|------|:---:|:---:|
| Skill 安装/卸载/更新/同步 | ✅ | |
| Skill 发布到市集 | ✅ | |
| Skill 重命名/改目录 | ✅ | |
| 列出/查看/执行 Skill | ✅ | |
| 创建新 Skill（AI 生成代码） | ✅ | |
| 发布到 ClawHub（外部市集） | | ❌ 用 clawhub CLI |
| OpenClaw CLI 的 `skills list` | | ❌ 那是 OpenClaw 自己的命令 |

**关键区别**: ArtClaw 的 Skill 管理操作**全部通过 Python API** 在 DCC 内执行（`run_ue_python` 或 `run_python`），不要用 shell 命令或 OpenClaw CLI。

## 调用方式

通过 MCP 工具 `run_ue_python`（UE）或 `run_python`（Maya/Max）执行 Python 代码。

---

## 常用操作速查

### 列出所有 Skill

```python
from skill_hub import get_skill_hub
hub = get_skill_hub()
skills = hub.list_skills()
for s in skills:
    print(f"[{s['category']}] {s['name']} v{s.get('version','?')} - {s['description']}")
```

### 安装/更新/同步（最常用）

```python
from skill_sync import sync_all, install_skill, update_skill, uninstall_skill

# 一键同步：安装未安装的 + 更新版本不一致的
result = sync_all()

# 安装单个
result = install_skill("ue54_batch_rename_actors")

# 更新单个
result = update_skill("ue54_get_material_nodes")

# 卸载
result = uninstall_skill("ue54_batch_rename_actors")
```

### 发布（user → marketplace/official）

```python
from skill_sync import publish_skill
result = publish_skill(
    "ue54_my_tool",
    target_layer="marketplace",   # 或 "official"
    bump="patch",                  # patch / minor / major
    changelog="修复了多选时的bug"
)
# 搬家语义: 运行时 user/ → marketplace/
# 自动同步到源码 + git add + commit
```

### 对比源码 vs 运行时

```python
from skill_sync import compare_source_vs_runtime
diff = compare_source_vs_runtime()
# diff.keys(): available, installed, updatable, orphaned, project_root, error
```

---

## Skill 重命名流程

当需要重命名一个已安装的 Skill 时，按以下步骤操作：

### 步骤 1: 修改运行时目录和文件

```python
import os, json, shutil

old_name = "artclaw_material"
new_name = "ue54_material_node_edit"

# 找到运行时目录（通常在 Skills/official/ 或 Skills/marketplace/ 下）
from skill_hub import get_skill_hub
hub = get_skill_hub()
info = hub.get_skill_info(old_name)
old_dir = info['source_dir']

# 重命名目录
new_dir = os.path.join(os.path.dirname(old_dir), new_name)
os.rename(old_dir, new_dir)

# 更新 manifest.json
manifest_path = os.path.join(new_dir, "manifest.json")
with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)
manifest['name'] = new_name
manifest['display_name'] = "新的显示名称"
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

# 更新 SKILL.md 的 frontmatter name
skill_md = os.path.join(new_dir, "SKILL.md")
if os.path.exists(skill_md):
    with open(skill_md, 'r', encoding='utf-8') as f:
        content = f.read()
    content = content.replace(f"name: {old_name}", f"name: {new_name}")
    with open(skill_md, 'w', encoding='utf-8') as f:
        f.write(content)

result = f"重命名完成: {old_name} → {new_name}"
```

### 步骤 2: 同步到 OpenClaw Skills 目录

```python
import os, shutil

new_name = "ue54_material_node_edit"
old_oc_name = "artclaw-material"  # OpenClaw 目录名用连字符
new_oc_name = "ue54-material-node-edit"

oc_skills = os.path.expanduser("~/.openclaw/skills")

# 删除旧的 OpenClaw Skill 目录
old_oc_dir = os.path.join(oc_skills, old_oc_name)
if os.path.exists(old_oc_dir):
    shutil.rmtree(old_oc_dir)

# 创建新的（如果有 SKILL.md 需要复制到 OpenClaw）
new_oc_dir = os.path.join(oc_skills, new_oc_name)
os.makedirs(new_oc_dir, exist_ok=True)
# 将运行时的 SKILL.md 复制过去
shutil.copy2(
    os.path.join(new_dir, "SKILL.md"),
    os.path.join(new_oc_dir, "SKILL.md")
)

result = f"OpenClaw Skills 同步完成: {old_oc_name} → {new_oc_name}"
```

### 步骤 3: 同步到源码仓库（如果有 project_root）

```python
from skill_sync import publish_skill
# 如果是从 user 层发布到 marketplace
result = publish_skill(new_name, target_layer="marketplace", bump="minor",
                       changelog=f"重命名: {old_name} → {new_name}")
```

### 步骤 4: 刷新 Skill Hub

```python
from skill_hub import get_skill_hub
hub = get_skill_hub()
hub.scan_and_register()  # 重新扫描注册
result = f"Skill Hub 已刷新，当前 {len(hub.list_skills())} 个 Skill"
```

---

## Python API 详细参考

### skill_hub — 技能查看/执行

```python
from skill_hub import get_skill_hub
hub = get_skill_hub()

# 列出全部
skills = hub.list_skills()
# 按类别过滤
skills = hub.list_skills(category="material")
# 按软件过滤
skills = hub.list_skills(software="unreal_engine")

# 获取详情
info = hub.get_skill_info("ue54_material_node_edit")
# info: {name, description, version, source_layer, source_dir, tools, ...}

# 执行
result = hub.execute_skill("ue54_material_node_edit", {
    "action": "create_material",
    "asset_name": "M_Test",
    "package_path": "/Game/Materials"
})

# 自动命名
name = hub.auto_name("batch rename actors in level")
# UE 5.4 环境 → "ue54_batch_rename_actors"

# 刷新
hub.scan_and_register()
```

### skill_sync — 安装/卸载/同步/发布

```python
from skill_sync import (
    compare_source_vs_runtime,
    install_skill, install_all_available,
    uninstall_skill,
    update_skill, update_all,
    sync_all,
    publish_skill,
)

# 对比
diff = compare_source_vs_runtime()

# 安装
install_skill("ue54_batch_rename_actors")
install_all_available()

# 卸载（同时删除运行时文件 + ~/.openclaw/skills/ 的文档）
uninstall_skill("ue54_batch_rename_actors")

# 更新
update_skill("ue54_get_material_nodes")
update_all()

# 同步 = 安装 + 更新
sync_all()

# 发布（user → marketplace，搬家语义 + git commit）
publish_skill("ue54_my_tool", target_layer="marketplace",
              bump="patch", changelog="修复bug")
```

**依赖**: `~/.artclaw/config.json` 必须有 `project_root` 字段（install.bat 自动写入）。

---

## Skill 包结构

```
Skills/user/my_skill/
├── manifest.json    # 技能元数据（名称、描述、版本、依赖）
├── __init__.py      # 技能执行入口
└── SKILL.md         # 技能说明文档（可选，用于 OpenClaw 匹配）
```

## Skill 命名规范

格式: `{dcc}{major_version}_{skill_name}`

| 部分 | 说明 | 示例 |
|------|------|------|
| `dcc` | 软件缩写: `ue`/`maya`/`max`/空(通用) | `ue` |
| `major_version` | 大版本号（两位） | `54` = UE 5.4 |
| `skill_name` | 功能描述（snake_case） | `material_node_edit` |

示例: `ue54_material_node_edit`, `maya24_curve_tools`, `artclaw-memory`(通用)

## Skill 分层体系

| 优先级 | 目录 | 说明 |
|--------|------|------|
| 最高 | `official/` | 官方内置，随版本更新 |
| 高 | `marketplace/` | 市集，团队共享 |
| 中 | `user/` | 用户自定义，AI 生成默认存放 |
| 低 | `custom/` | 临时/实验性 |

同名按优先级覆盖。每层下按 DCC 分子目录：`universal/`、`unreal/`、`maya/`、`max/`

## 创建新 Skill 流程

1. `hub.auto_name(description)` 生成名称
2. AI 生成 `__init__.py` + `manifest.json`
3. 保存到 `Skills/user/<skill_name>/`
4. Skill Hub 自动热加载
5. 可选：在 `~/.openclaw/skills/` 创建 SKILL.md

## 旧名兼容映射

- `artclaw_material` → `ue54_material_node_edit`
- `ue54_artclaw_material` → `ue54_material_node_edit`
- `get_material_nodes` → `ue54_get_material_nodes`
- `generate_material_documentation` → `ue54_generate_material_documentation`
