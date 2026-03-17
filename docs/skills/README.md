# ArtClaw Skill 系统

ArtClaw 的 Skill 系统让 AI Agent 能够在 DCC 软件（Unreal Engine、Maya、3ds Max 等）中执行具体操作。每个 Skill 是一个独立的功能包，通过 MCP 协议暴露为可调用的工具。

## 什么是 Skill？

Skill 是 ArtClaw 的核心功能单元。每个 Skill：

- 📦 是一个独立的 Python 包（目录 + `__init__.py` + `manifest.json`）
- 🔧 通过 `@ue_tool` 装饰器暴露一个或多个工具
- 🤖 由 AI Agent 通过自然语言理解后自动调用
- 🔄 支持热加载：保存即生效，无需重启 DCC

## 目录结构

```
artclaw/
├── skills/                           # 官方 Skill 库（Git 管理）
│   ├── universal/                    # 跨平台通用 Skill
│   │   ├── utils/
│   │   └── common/
│   ├── unreal_engine/                # UE 专用 Skill
│   │   ├── core/                     # P0 核心 Skill
│   │   └── extended/                 # P1 扩展 Skill
│   ├── maya/                         # Maya 专用 Skill
│   ├── 3ds_max/                      # 3ds Max 专用 Skill
│   ├── templates/                    # 开发模板
│   │   ├── basic/                    # 基础模板
│   │   ├── advanced/                 # 高级模板（多工具、撤销支持）
│   │   └── material_doc/             # 参考实现：材质文档生成
│   └── categories.py                 # 标准分类枚举
│
├── team_skills/                      # 团队共享 Skill
│
└── ~/.artclaw/skills/                # 用户个人 Skill
```

### 加载优先级

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 0 (最高) | `skills/` | ArtClaw 官方维护 |
| 1 | `team_skills/` | 团队共享定制 |
| 2 | `~/.artclaw/skills/` | 个人私有 |
| 99 | 运行时动态 | 临时实验 |

同名 Skill 高优先级覆盖低优先级。

## Skill 包结构

每个 Skill 是一个目录，最小包含两个文件：

```
my_skill/
├── manifest.json       # 元数据（必需）
├── __init__.py         # 入口代码（必需）
├── README.md           # 使用说明（推荐）
├── icon.png            # 图标（可选）
├── tests/              # 测试用例（推荐）
├── examples/           # 使用示例（可选）
└── resources/          # 附加资源（可选）
```

## 快速开始

### 1. 从模板创建

```bash
# 基础 Skill
artclaw skill create my_tool --template basic --category material --software unreal_engine

# 高级 Skill（多工具、批量操作、撤销支持）
artclaw skill create my_tool --template advanced --category asset
```

### 2. 手动创建

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

- [manifest.json 规范](MANIFEST_SPEC.md) — 完整字段说明
- [贡献指南](CONTRIBUTING.md) — 如何提交 Skill
- [Skill 开发指南](SKILL_DEVELOPMENT_GUIDE.md) — 详细开发教程

## 示例 Skill

参考 `skills/unreal_engine/material/generate_material_documentation/`，这是一个完整的生产级 Skill，展示了所有最佳实践。

模板目录 `skills/templates/material_doc/` 中也有该 Skill 的参考副本。
