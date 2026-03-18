# ArtClaw Skill 系统

ArtClaw 的 Skill 系统让 AI Agent 能够在 DCC 软件（Unreal Engine、Maya、3ds Max 等）中执行具体操作。每个 Skill 是一个独立的功能包，通过 MCP 协议暴露为可调用的工具。

## 什么是 Skill？

Skill 是 ArtClaw 的核心功能单元。每个 Skill：

- 📦 是一个独立的 Python 包（目录 + `__init__.py` + `manifest.json` + `SKILL.md`）
- 🔧 通过 `@ue_tool` 装饰器暴露一个或多个工具
- 🤖 由 AI Agent 通过自然语言理解后自动调用
- 🔄 支持热加载：保存即生效，无需重启 DCC
- 🌐 兼容 OpenClaw/ClawHub 分发（通过 SKILL.md）

## 目录结构

```
artclaw/
├── skills/                           # Skill 开发资源
│   ├── templates/                    # 开发模板
│   │   ├── basic/                    # 基础模板
│   │   ├── advanced/                 # 高级模板（多工具、撤销支持）
│   │   └── material_doc/            # 参考实现：材质文档生成
│   └── categories.py                 # 标准分类枚举
│
├── subprojects/UEDAgentProj/.../Skills/   # UE 插件运行时 Skill 目录
│   ├── 00_official/                  # 官方 Skill（最高优先级）
│   │   ├── artclaw_material/        # 材质节点图写操作
│   │   ├── get_material_nodes/      # 材质节点图查询
│   │   └── generate_material_documentation/  # 材质文档生成
│   ├── 01_team/                      # 团队共享 Skill
│   ├── 02_user/                      # 用户个人 Skill
│   ├── 99_custom/                    # 临时实验 Skill
│   └── *.py                          # 旧版单文件 Skill（向后兼容）
│
├── team_skills/                      # 团队共享 Skill（Git 管理）
│
└── ~/.artclaw/skills/                # 用户个人 Skill
```

### 加载优先级

| 优先级 | 层级 | 来源 | 说明 |
|--------|------|------|------|
| 0 (最高) | `00_official/` | UE 插件内 | ArtClaw 官方维护 |
| 1 | `01_team/` | UE 插件内 / team_skills/ | 团队共享定制 |
| 2 | `02_user/` | UE 插件内 / ~/.artclaw/skills/ | 个人私有 |
| 99 | `99_custom/` | UE 插件内 | 临时实验 |

同名 Skill 高优先级覆盖低优先级。

## Skill 包结构（双文件策略）

每个 Skill 推荐同时包含 `SKILL.md` 和 `manifest.json`：

```
my_skill/
├── SKILL.md            # AI 文档 + OpenClaw/ClawHub 分发（推荐）
├── manifest.json       # MCP 注册元数据（推荐）
├── __init__.py         # 入口代码（必需）
├── references/         # 参考文档（可选）
└── scripts/            # 辅助脚本（可选）
```

**加载优先级**: `manifest.json` > `SKILL.md` fallback

- 如果 `manifest.json` 存在 → Skill Hub 直接注册 MCP 工具
- 如果只有 `SKILL.md` → Skill Hub 从 frontmatter 提取元数据 + AST 扫描 `@ue_tool` 自动构建
- 如果两个都有 → `manifest.json` 用于 MCP 注册，`SKILL.md` 用于 AI 理解和分发

> 详见 [MANIFEST_SPEC.md](MANIFEST_SPEC.md)

## 快速开始

### 1. 从模板创建

```bash
# 基础 Skill
artclaw skill create my_tool --template basic --category material --software unreal_engine

# 高级 Skill（多工具、批量操作、撤销支持）
artclaw skill create my_tool --template advanced --category asset
```

### 2. 手动创建

**SKILL.md**:

```yaml
---
name: my-skill
description: >
  One-line description of what this skill does and when to use it.
---

# My Skill

详细说明...
```

**manifest.json**:

```json
{
  "manifest_version": "1.0",
  "name": "my_skill",
  "display_name": "我的技能",
  "description": "一句话描述",
  "version": "1.0.0",
  "author": "Your Name",
  "license": "MIT",
  "software": "unreal_engine",
  "software_version": { "min": "5.3", "max": "5.5" },
  "category": "material",
  "risk_level": "low",
  "dependencies": [],
  "tags": ["material"],
  "entry_point": "__init__.py",
  "tools": [
    {
      "name": "my_tool",
      "description": "工具描述"
    }
  ]
}
```

**\_\_init\_\_.py**:

```python
from skill_hub import tool as ue_tool
import json

try:
    import unreal
except ImportError:
    unreal = None

@ue_tool(
    name="my_tool",
    description="工具描述",
    category="material",
    risk_level="low",
)
def my_tool(arguments: dict) -> str:
    if unreal is None:
        return json.dumps({"success": False, "error": "Not in UE"})

    # 你的逻辑
    return json.dumps({"success": True, "data": {}}, default=str)
```

### 3. 自然语言创建

```bash
artclaw skill generate "读取母材质的材质蓝图，创建材质使用文档" \
  --category material --software unreal_engine
```

## 标准分类

| 分类 | 说明 |
|------|------|
| `scene` | 场景操作（Actor、Level、Transform） |
| `asset` | 资产管理（导入、导出、迁移） |
| `material` | 材质编辑 |
| `lighting` | 灯光设置 |
| `render` | 渲染设置 |
| `blueprint` | 蓝图操作 |
| `animation` | 动画相关 |
| `ui` | UI/UMG 操作 |
| `utils` | 工具类 |
| `integration` | 第三方集成 |
| `workflow` | 工作流自动化 |

## 风险级别

| 级别 | 说明 | 示例 |
|------|------|------|
| `low` | 只读操作 | 查询资产信息、生成文档 |
| `medium` | 可撤销的修改 | 重命名 Actor、修改材质参数 |
| `high` | 不可撤销的修改 | 删除资产、修改文件 |
| `critical` | 影响项目全局 | 修改项目设置、构建配置 |

## 开发资源

- [manifest.json 规范](MANIFEST_SPEC.md) — 完整字段说明 + 双文件策略
- [贡献指南](CONTRIBUTING.md) — 如何提交 Skill
- [Skill 开发指南](SKILL_DEVELOPMENT_GUIDE.md) — 详细开发教程

## 示例 Skill

UE 插件 `Skills/00_official/` 中的三个官方 Skill 是最佳参考：

| Skill | 功能 | 特点 |
|-------|------|------|
| `artclaw_material` | 材质节点图写操作 | 多工具、references 目录、完整 SKILL.md |
| `get_material_nodes` | 材质节点图查询 | 单工具、BFS 遍历、安全限制 |
| `generate_material_documentation` | 材质文档生成 | 只读操作、文件输出 |

模板目录 `skills/templates/` 中有 basic/advanced/material_doc 三种脚手架。
