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
skills = hub.list_skills(category="modeling")

# 按软件过滤
skills = hub.list_skills(software="maya")
```

### 获取技能详情

```python
hub = get_skill_hub()
info = hub.get_skill_info("auto_uv_unwrap")
print(f"名称: {info['name']}")
print(f"描述: {info['description']}")
print(f"参数: {info['params']}")
print(f"层级: {info['layer']}")
```

### 执行技能

```python
hub = get_skill_hub()
result = hub.execute_skill("auto_uv_unwrap", {
    "target": "selected",
    "method": "smart_project",
    "margin": 0.02
})
print(f"执行结果: {result}")
```

---

## Skill 包结构

每个 ArtClaw Skill 是一个目录，包含以下文件：

```
Skills/02_user/my_skill/
├── manifest.json    # 技能元数据（名称、描述、参数定义、依赖）
├── __init__.py      # 技能执行入口
└── SKILL.md         # 技能说明文档（可选，用于 OpenClaw 匹配）
```

### manifest.json 示例

```json
{
    "name": "auto_uv_unwrap",
    "version": "1.0.0",
    "description": "自动 UV 展开工具",
    "software": ["maya", "max"],
    "category": "modeling",
    "params": {
        "target": {"type": "string", "default": "selected"},
        "method": {"type": "string", "enum": ["smart_project", "planar", "cylindrical"]},
        "margin": {"type": "float", "default": 0.02}
    }
}
```

---

## Skill 分层体系

| 优先级 | 目录 | 说明 |
|--------|------|------|
| 最高 | `00_official/` | 官方内置技能，随版本更新 |
| 高 | `01_team/` | 团队共享技能，通过团队仓库同步 |
| 中 | `02_user/` | 用户自定义技能，AI 生成的技能默认存放于此 |
| 低 | `99_custom/` | 临时/实验性技能 |

同名技能按优先级覆盖：`00_official` > `01_team` > `02_user` > `99_custom`

---

## 创建新 Skill 的流程

1. **AI 生成代码** — 根据用户描述，生成 `__init__.py` 和 `manifest.json`
2. **保存到用户目录** — 将文件保存到 `Skills/02_user/<skill_name>/`
3. **热加载** — Skill Hub 自动检测新文件并加载，无需重启
4. **生成 OpenClaw SKILL.md**（可选）— 同时在 OpenClaw 的 skills 目录下创建对应的 SKILL.md，便于 OpenClaw 侧的技能匹配

### 快速创建示例

```python
hub = get_skill_hub()

# AI 生成的技能代码
skill_code = '''
def execute(params):
    import maya.cmds as cmds
    selected = cmds.ls(selection=True)
    for obj in selected:
        cmds.polyAutoProjection(obj, lm=0, pb=0, ibd=1, cm=0, l=2, sc=1, o=1, p=6, ps=0.2)
    return {"processed": len(selected)}
'''

# 保存并注册（实际操作中通过文件系统写入 Skills/02_user/ 目录）
```

---

## 使用建议

- 查看可用技能前先用 `hub.list_skills()` 列出全部
- 执行前用 `hub.get_skill_info()` 确认参数要求
- 用户自定义技能放 `02_user/`，避免修改 `00_official/`
- 创建新技能时同步生成 OpenClaw SKILL.md，保持两边一致
