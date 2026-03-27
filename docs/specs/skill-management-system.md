# ArtClaw Skill 管理体系设计文档

**版本**: v2.1  
**日期**: 2026-03-27  
**状态**: 已完成  
**文档路径**: `docs/specs/skill-management-system.md`

> **v2.1 变更说明 (2026-03-27)**:
> - MCP 工具精简重构：每个 DCC 仅保留 1 个 MCP 工具（`run_ue_python` / `run_python`），原有工具全部降级为 Python API
> - Skill 不再注册为 MCP 工具，通过 `execute_skill()` Python API 提供执行入口
> - 新增 5 个 OpenClaw Skill（SKILL.md 触发文档），指导 AI 通过 `run_python` 调用 Python API
> - ArtClaw 从"Skill 运行时"转型为"Skill 市集"
> - §8 对话式 Skill 创建流程更新
> - §9 MCP 接口扩展整节重写
> - §10 开发工作清单同步更新

---

## 1. 设计目标

建立一套**分层、可扩展、支持用户自定义**的 Skill 管理体系：

1. **官方 Skill 库**: ArtClaw 维护的跨 DCC 标准 Skill
2. **团队 Skill 库**: 项目组共享的定制 Skill
3. **用户 Skill 库**: 个人开发的私有 Skill
4. **Skill 市场** (远期): 社区分享与发现

---

## 2. 核心特性

### 2.1 分层加载机制
- 按优先级分层加载: `官方 > 团队 > 用户 > 临时`
- 同名 Skill 高优先级覆盖低优先级
- 支持版本匹配: 优先使用与 DCC 软件版本匹配的 Skill

### 2.2 多 DCC 支持
- Skill 区分适用软件: `universal` / `unreal_engine` / `maya` / `3ds_max` 等
- 同 Skill 可有多平台实现
- 运行时根据当前 DCC 自动选择合适实现

### 2.3 自然语言创建
- 用户通过自然语言描述需求
- AI 自动生成 Skill 代码、manifest、文档
- 自动分类、归档、安装到对应 Agent 平台

### 2.4 热加载与实时生效
- 保存即生效，无需重启 DCC
- 文件监控自动检测变更
- 内部 API 注册表自动更新，无需 MCP 工具列表刷新

### 2.5 C++ 接口开发规范
- **原则**: Skill 优先使用 Python/蓝图实现
- **约束**: 如果功能必须通过 C++ 开放接口支持，**禁止直接修改 C++ 代码**
- **流程**:
  1. Skill 开发时识别 C++ 依赖需求
  2. 记录到 `docs/c++_requirements.md`
  3. **通过 UE 弹窗提示用户确认**（非 AI 对话提示）
  4. **用户确认后**，方可修改 C++ 代码
- **弹窗实现**: 使用 `FMessageDialog::Open` 或 `SWindow` 创建原生 UE 弹窗
- **弹窗内容示例**:
  ```
  ┌─────────────────────────────────────────┐
  │  ArtClaw Skill 需要 C++ 支持            │
  ├─────────────────────────────────────────┤
  │                                         │
  │  Skill "generate_material_documentation"│
  │  需要以下 C++ 接口：                    │
  │                                         │
  │  • GetMaterialGraphNodes()              │
  │    位置: Source/ArtClaw/Private/        │
  │            MaterialUtils.cpp            │
  │                                         │
  │  [确认添加]    [跳过此功能]    [详情]   │
  │                                         │
  └─────────────────────────────────────────┘
  ```
- **用户选择**:
  - **确认添加**: 修改 C++，完成完整功能
  - **跳过此功能**: Skill 以纯 Python 可用功能运行
  - **详情**: 展示详细技术说明
- **目的**: 让用户控制 C++ 代码修改节奏，避免自动修改引发不可预期问题

---

## 3. 目录结构

### 3.1 项目级 Skill 库

```
artclaw/                              # 项目根目录
├── skills/                           # 🆕 官方 Skill 库（Git 管理）
│   ├── __init__.py
│   ├── universal/                    # 跨平台通用 Skill
│   │   ├── utils/
│   │   └── common/
│   ├── unreal_engine/                # UE 专用 Skill
│   │   ├── core/                     # P0 核心 Skill
│   │   │   ├── scene/
│   │   │   ├── asset/
│   │   │   ├── material/
│   │   │   └── lighting/
│   │   └── extended/                 # P1 扩展 Skill
│   ├── maya/                         # Maya 专用 Skill
│   ├── 3ds_max/                      # 3ds Max 专用 Skill
│   └── templates/                    # Skill 开发模板
│       ├── basic/                    # 基础模板
│       ├── advanced/                 # 高级模板
│       └── material_doc/             # 样板: 材质文档生成
│
├── team_skills/                      # 🆕 团队 Skill 库（项目 Git 内）
│   └── [团队自定义 Skill]
│
└── docs/
    └── skills/                       # Skill 开发文档
        ├── README.md
        ├── CONTRIBUTING.md
        ├── MANIFEST_SPEC.md          # manifest.json 规范
        └── templates/                # 文档模板
```

### 3.2 运行时加载目录（UE 插件内）

```
UEClawBridge/
└── Content/
    └── Python/
        ├── skill_hub.py              # Skill 管理中心
        ├── Skills/                   # 运行时加载目录（合并视图）
        │   ├── 00_official/          # 软链接/拷贝: 官方库
        │   ├── 01_team/              # 软链接/拷贝: 团队库
        │   ├── 02_user/              # 软链接/拷贝: 用户库
        │   └── 99_custom/            # 临时/实验 Skill
        └── ...
```

### 3.3 用户库位置

```
~/.artclaw/                           # 用户配置目录
├── skills/                           # 用户个人 Skill 库
│   └── [用户自定义 Skill]
├── config.yaml                       # 用户配置
└── logs/                             # 日志
```

---

## 4. Skill 包结构

### 4.1 标准 Skill 包

```
my_skill/                             # Skill 包目录（蛇形命名）
├── SKILL.md                          # AI 文档 + OpenClaw/ClawHub 分发（推荐）
├── manifest.json                     # MCP 注册元数据（推荐）
├── __init__.py                       # Skill 入口（必需）
├── references/                       # 参考文档（可选）
└── scripts/                          # 辅助脚本（可选）
```

> **双文件策略**: `SKILL.md` 和 `manifest.json` 至少有一个。推荐两个都有。
> - `manifest.json` → Skill Hub 直接注册 MCP 工具
> - `SKILL.md` → AI 理解 + ClawHub 分发；无 manifest 时作为 fallback 自动构建
> 详见 [MANIFEST_SPEC.md](../skills/MANIFEST_SPEC.md)
    ├── prompts/
    └── templates/
```

### 4.2 manifest.json 规范

```json
{
  "manifest_version": "1.0",
  "name": "my_skill",
  "display_name": "我的技能",
  "description": "一句话描述这个 Skill 的作用",
  "version": "1.0.0",
  "author": "Ivan(杨己力)",
  "license": "MIT",
  
  "software": "unreal_engine",        // universal | unreal_engine | maya | 3ds_max
  "software_version": {
    "min": "5.3",
    "max": "5.5"
  },
  
  "category": "material",             // 标准分类枚举
  "risk_level": "low",                // low | medium | high | critical
  
  "dependencies": [                   // 依赖其他 Skill
    "artclaw.universal.utils>=1.0.0"
  ],
  
  "tags": ["lighting", "batch", "utility"],
  "entry_point": "__init__.py",
  
  "tools": [                          // 暴露的 Tool 列表
    {
      "name": "batch_rename",
      "description": "批量重命名 Actor"
    }
  ]
}
```

### 4.3 标准 Category 枚举

```python
# P0 核心分类
SCENE = "scene"                       # 场景操作（Actor、Level、Transform）
ASSET = "asset"                       # 资产管理（导入、导出、迁移）
MATERIAL = "material"                 # 材质编辑
LIGHTING = "lighting"                 # 灯光设置
RENDER = "render"                     # 渲染设置
BLUEPRINT = "blueprint"               # 蓝图操作
ANIMATION = "animation"               # 动画相关
UI = "ui"                             # UI/UMG 操作

# P1 扩展分类
UTILS = "utils"                       # 工具类
INTEGRATION = "integration"           # 第三方集成
WORKFLOW = "workflow"                 # 工作流自动化
```

---

## 5. Skill 加载优先级

### 5.1 加载顺序（数字越小优先级越高）

| 优先级 | 目录 | 来源 | 用途 |
|--------|------|------|------|
| 00 | `00_official/` | `artclaw/skills/` | ArtClaw 官方维护 |
| 01 | `01_team/` | `artclaw/team_skills/` | 团队共享 |
| 02 | `02_user/` | `~/.artclaw/skills/` | 个人私有 |
| 99 | `99_custom/` | 运行时动态 | 临时实验 |

### 5.2 版本匹配策略

```python
# 加载时优先选择版本匹配的 Skill
for skill_candidate in all_sources:
    if skill_candidate.software != current_software:
        continue
    if not version_match(skill_candidate.version, current_software_version):
        continue
    # 选择版本最接近的
    return best_match
```

---

## 6. CLI 工具设计

参考 OpenClaw `skill-creator` 规范，设计 ArtClaw CLI：

### 6.1 命令列表

```bash
# Skill 创建
artclaw skill create <name> [options]
  --category <cat>          # 分类
  --software <sw>           # 适用软件 (unreal_engine/maya/3ds_max/universal)
  --template <tpl>          # 模板 (basic/advanced/material_doc)
  --description <desc>      # 描述（支持自然语言）

# Skill 测试
artclaw skill test <name> [options]
  --software <sw>           # 指定测试环境
  --dry-run                 # 仅验证不执行

# Skill 打包
artclaw skill package <name> [options]
  --output <dir>            # 输出目录
  --format <fmt>            # 格式 (zip/skill)

# Skill 发布
artclaw skill publish <name> [options]
  --target <target>         # 发布目标 (user/team/official)
  --message <msg>           # 版本说明

# Skill 安装
artclaw skill install <source> [options]
  --source-type <type>      # 来源类型 (git/local/registry)
  --software <sw>           # 指定软件版本

# Skill 管理
artclaw skill list [options]
  --category <cat>          # 按分类筛选
  --software <sw>           # 按软件筛选
  --source <src>            # 按来源筛选

artclaw skill info <name>           # 查看详情
artclaw skill enable <name>         # 启用
artclaw skill disable <name>        # 禁用
artclaw skill uninstall <name>      # 卸载
artclaw skill update <name>         # 更新

# 自然语言创建（核心特性）
artclaw skill generate "读取母材质的材质蓝图，创建材质使用文档"
  --category material
  --software unreal_engine
```

### 6.2 自然语言创建流程

```
用户输入自然语言描述
        ↓
CLI 解析意图，提取关键信息
        ↓
调用 AI 生成:
  - SKILL.md
  - manifest.json
  - __init__.py (Skill 代码)
        ↓
验证生成的 Skill 结构
        ↓
自动分类 → 选择目标目录
        ↓
安装到对应 Agent 平台
        ↓
返回安装结果和用法说明
```

---

## 7. 样板 Skill: 材质文档生成

### 7.1 功能描述

**名称**: `generate_material_documentation`  
**描述**: 读取母材质的材质蓝图，创建材质使用文档  
**分类**: `material`  
**适用软件**: `unreal_engine`  
**风险级别**: `low`

### 7.2 输入输出

```python
# 输入
{
    "material_path": "/Game/Materials/M_Master",  # 母材质路径
    "output_format": "markdown",                   # 输出格式
    "include_parameters": true,                    # 是否包含参数说明
    "include_graph": true                          # 是否包含节点图
}

# 输出
{
    "documentation": "# M_Master 材质文档\n...",
    "output_path": "Saved/MaterialDocs/M_Master.md",
    "parameter_count": 12,
    "texture_count": 4
}
```

### 7.3 实现要点

1. 使用 `unreal.EditorAssetLibrary` 读取材质
2. 解析材质参数（Scalar、Vector、Texture、Switch 等）
3. 遍历材质图表，提取关键节点
4. 生成 Markdown 格式文档
5. 保存到项目 `Saved/MaterialDocs/` 目录

---

## 8. UE 编辑器内集成

### 8.1 对话式 Skill 创建（核心交互 — v2）

> **v2 更新 (2026-03-17)**: 移除 C++ 模态对话框，改为 AI 对话式创建。
> 详见 `docs/UEClawBridge/features/阶段 3 智能增强/3.7 Skill创建交互优化方案.md`

**设计原则**: 创建 Skill 应该是一次自然对话，而不是填表单。用户只需说一句话，AI 自动推断所有能推断的字段，需要确认的通过聊天追问。

**流程**:
```
用户: "帮我创建一个 artclaw 技能，批量重命名场景中的 Actor 并加前缀"
        ↓
[所有消息统一发给 AI，不再 C++ 侧拦截]
        ↓
AI 自动收集上下文:
  • 调用 get_editor_context() → UE 版本
  • 推断 category / risk_level / name / display_name
        ↓
AI 展示确认摘要:
  "📦 名称: batch_rename_actors_prefix
   📂 分类: scene
   🎯 软件: unreal_engine (UE 5.5)
   ⚠️ 风险: medium
   确认创建？"
        ↓
用户确认 → AI 通过 run_ue_python 调用 skill_hub.create_skill(...)
        ↓
自动安装 + 热加载（注册为内部 Python API，不再注册 MCP）
        ↓
同时生成 OpenClaw SKILL.md → 保存到 ~/.openclaw/skills/
```

**AI 自动获取/推断的字段**:
- `software` — 环境检测（UE 内 = unreal_engine）
- `software_version` — 从 `get_editor_context()` 获取 UE 版本
- `name` — AI 从描述推断 snake_case 名称
- `display_name` — AI 生成人类可读名称
- `category` — AI 语义分析分类
- `risk_level` — AI 根据读/写/删除判断

**需要追问的场景**（通过聊天，非弹窗）:
- 描述模糊无法确定功能
- 涉及多个 DCC 软件
- 可能需要 C++ 接口
- 目标层级不确定

### 8.2 备用入口：Create Skill 按钮

保留按钮，但行为改为在聊天输入框填充引导文本（Skill 创建全程由 AI 对话驱动，不涉及 MCP 工具注册）:

```
[用户点击 Create Skill]
  → 输入框自动填充: "Create an artclaw skill: "
  → 用户继续输入描述
  → 发送给 AI，走对话式流程（通过 run_ue_python 调用 Python API）
```

如 AI 未连接，提示用户先执行 `/connect`。

---

## 9. MCP 接口扩展

### 9.1 MCP 工具与 Python API（v2.1 重构）

> **v2.1 重构 (2026-03-27)**: MCP 工具从 22 个精简为 **1 个**。
> 每个 DCC 仅保留 1 个 MCP 工具作为唯一执行入口，所有其他功能降级为 Python API。
> AI 通过 OpenClaw Skill（SKILL.md 触发文档）获取调用指引，经由 `run_python` 调用 Python API。

#### 9.1.1 唯一 MCP 工具

| DCC 侧 | MCP 工具名 | 说明 |
|---------|-----------|------|
| UE 编辑器 | `run_ue_python` | UE 侧唯一 MCP 工具，万能 Python 执行器 |
| DCC 软件（Maya 等） | `run_python` | DCC 侧唯一 MCP 工具，万能 Python 执行器 |

#### 9.1.2 Python API（原 MCP 工具降级）

原有 MCP 工具功能完整保留，降级为 Python API，AI 通过 `run_ue_python` / `run_python` 调用。

**Core API**:

| 原 MCP 工具 | Python API 调用方式 | 说明 |
|-------------|---------------------|------|
| `get_editor_context()` | `from artclaw.api import context; context.get_editor_context()` | 编辑器上下文 |
| `highlight_actors(names)` | `from artclaw.api import scene; scene.highlight_actors(names)` | 高亮 Actor |

**Scene Ops API**:

| 原 MCP 工具 | Python API 调用方式 | 说明 |
|-------------|---------------------|------|
| `get_selected_actors()` | `from artclaw.api import scene; scene.get_selected_actors()` | 选中 Actor 列表 |
| `get_all_level_actors(filter)` | `scene.get_all_level_actors(class_filter=filter)` | 全部 Actor |
| `get_actor_details(name)` | `scene.get_actor_details(actor_name=name)` | Actor 详情 |
| `focus_on_actor(name)` | `scene.focus_on_actor(actor_name=name)` | 视口聚焦 |
| `select_actors(names)` | `scene.select_actors(actor_names=names)` | 选择 Actor |

**Asset Ops API**:

| 原 MCP 工具 | Python API 调用方式 | 说明 |
|-------------|---------------------|------|
| `load_asset(path)` | `from artclaw.api import asset; asset.load_asset(asset_path=path)` | 加载资产信息 |
| `get_asset_path(query)` | `asset.get_asset_path(query=query)` | 搜索资产路径 |
| `list_assets_in_directory(dir)` | `asset.list_assets_in_directory(directory=dir)` | 列出目录资产 |
| `rename_asset(path, name)` | `asset.rename_asset(asset_path=path, new_name=name)` | 重命名资产 |

**Material Ops API**:

| 原 MCP 工具 | Python API 调用方式 | 说明 |
|-------------|---------------------|------|
| `get_actor_materials(name)` | `from artclaw.api import material; material.get_actor_materials(actor_name=name)` | Actor 材质列表 |
| `get_material_parameters(path)` | `material.get_material_parameters(material_path=path)` | 材质参数 |

**Level Ops API**:

| 原 MCP 工具 | Python API 调用方式 | 说明 |
|-------------|---------------------|------|
| `get_current_level()` | `from artclaw.api import level; level.get_current_level()` | 当前关卡信息 |
| `get_level_actors()` | `level.get_level_actors()` | 关卡 Actor 分类汇总 |
| `get_viewport_info()` | `level.get_viewport_info()` | 视口相机信息 |

**Memory API**:

| 原 MCP 工具 | Python API 调用方式 | 说明 |
|-------------|---------------------|------|
| `memory(action, ...)` | `from artclaw.api import memory; memory.memory(action=action, layer=layer, key=key, value=value, query=query)` | 统一记忆操作 |

**Knowledge API**:

| 原 MCP 工具 | Python API 调用方式 | 说明 |
|-------------|---------------------|------|
| `knowledge_search(query, top_k)` | `from artclaw.api import knowledge; knowledge.search(query=query, top_k=top_k)` | 知识库搜索 |

**Skill Management API**:

| 原 MCP 工具 | Python API 调用方式 | 说明 |
|-------------|---------------------|------|
| `skill_list(...)` | `from artclaw import skill_hub; skill_hub.list_skills(category=..., software=..., layer=..., keyword=...)` | 列出 Skill |
| `skill_manage(action, ...)` | `skill_hub.manage_skill(action=action, name=name, ...)` | 统一管理操作 |
| `skill_generate(desc, ...)` | `skill_hub.generate_skill(description=desc, category=..., software=...)` | 自然语言生成 |

**Skill 执行（统一入口）**:

```python
# AI 通过 run_ue_python / run_python 调用：
from artclaw import skill_hub
result = skill_hub.execute_skill("skill_name", {"param1": "value1", "param2": "value2"})
```

#### 9.1.3 OpenClaw Skill（SKILL.md 触发文档）

以下 5 个 OpenClaw Skill 保存在 `~/.openclaw/skills/`，作为按需加载的触发文档。当 AI 识别到相关意图时自动加载对应 SKILL.md，获取调用指引后通过 `run_ue_python` / `run_python` 执行 Python API。

| OpenClaw Skill | 路径 | 说明 | 对应 Python API |
|----------------|------|------|----------------|
| `artclaw-context` | `~/.openclaw/skills/artclaw-context/SKILL.md` | 编辑器上下文获取与场景信息查询 | `artclaw.api.context.*` / `artclaw.api.scene.*` / `artclaw.api.level.*` |
| `artclaw-memory` | `~/.openclaw/skills/artclaw-memory/SKILL.md` | 项目记忆读写（对话上下文、偏好设置等） | `artclaw.api.memory.*` |
| `artclaw-knowledge` | `~/.openclaw/skills/artclaw-knowledge/SKILL.md` | 知识库搜索与索引 | `artclaw.api.knowledge.*` |
| `artclaw-skill-manage` | `~/.openclaw/skills/artclaw-skill-manage/SKILL.md` | Skill 列表查看、创建、管理 | `artclaw.skill_hub.*` |
| `artclaw-highlight` | `~/.openclaw/skills/artclaw-highlight/SKILL.md` | Actor 高亮与视觉反馈 | `artclaw.api.scene.highlight_actors()` |

**工作流示意**:
```
用户意图（如 "查看场景中所有灯光"）
        ↓
OpenClaw 按需加载 artclaw-context SKILL.md
        ↓
AI 获得调用指引 → 生成 Python 代码
        ↓
AI 通过 run_ue_python 执行:
  from artclaw.api import scene
  actors = scene.get_all_level_actors(class_filter="Light")
        ↓
返回结果给用户
```

#### 9.1.4 已内化（不再暴露为工具或 API）

- `assess_risk` → 内化到 `run_ue_python` 流程
- `analyze_error` → 内化到 `run_ue_python` 流程
- `get_dynamic_prompt` → 内化到 system prompt

#### 9.1.5 已由 run_ue_python 替代（代码保留供内部调用）

- `spawn_actor`, `delete_actors`, `set_actor_transform`, `rename_actor`, `duplicate_actors`
- `set_actor_material`, `create_material_instance`, `does_asset_exist`
- `save_current_level`, `save_all_dirty_packages`, `open_level`, `set_viewport_camera`
- `knowledge_index`, `knowledge_stats`

### 9.2 新增 Resources

```python
unreal://skills/official                              # 官方库列表
unreal://skills/team                                  # 团队库列表
unreal://skills/user                                  # 用户库列表
unreal://skills/disabled                              # 已禁用列表
unreal://skills/categories                            # 分类列表
unreal://skills/templates                             # 可用模板

# 带过滤的列表
unreal://skills/by_category/{category}
unreal://skills/by_software/{software}
unreal://skills/by_version/{version}
```

### 9.3 新增 Notifications

```python
notifications/skills/created                          # Skill 创建
notifications/skills/updated                          # Skill 更新
notifications/skills/deleted                          # Skill 删除
notifications/skills/enabled                          # Skill 启用
notifications/skills/disabled                         # Skill 禁用
notifications/skills/reloaded                         # Skill 热重载
notifications/skills/dependencies_resolved            # 依赖解析完成
```

---

## 10. 开发工作清单

> **状态**: 全部阶段已完成 (2026-03-17)

### 阶段 A: 基础设施 (P0) ✅

| # | 任务 | 说明 | 状态 |
|---|------|------|------|
| A1 | 创建 `artclaw/skills/` 目录结构 | 按 software/category 分层 | ✅ |
| A2 | 设计 `manifest.json` Schema | 含 software/version 字段 | ✅ |
| A3 | 创建 Skill 模板 | `templates/basic/` `templates/advanced/` `templates/material_doc/` | ✅ |
| A4 | 编写开发文档 | `docs/skills/README.md` `MANIFEST_SPEC.md` `CONTRIBUTING.md` `SKILL_DEVELOPMENT_GUIDE.md` | ✅ |
| A5 | 定义标准 category 枚举 | `skills/categories.py` | ✅ |
| A6 | 创建样板 Skill | `generate_material_documentation` | ✅ |

### 阶段 B: Skill Hub 增强 (P0) ✅

| # | 任务 | 说明 | 状态 |
|---|------|------|------|
| B1 | 实现分层加载机制 | `skill_loader.py` | ✅ |
| B2 | 实现 manifest 解析 | `skill_manifest.py` JSON Schema 验证 | ✅ |
| B3 | 实现软件版本匹配 | `skill_version.py` | ✅ |
| B4 | 实现 Skill 冲突检测 | `skill_conflict.py` | ✅ |
| B5 | MCP Tools | `skill_mcp_tools.py` (精简为 0 个 MCP 工具，全部降级为 Python API，通过 execute_skill() 调用) | ✅ |
| B6 | MCP Resources | `skill_mcp_resources.py` (8 个 resources) | ✅ |

### 阶段 C: CLI 工具 (P0) ✅

| # | 任务 | 说明 | 状态 |
|---|------|------|------|
| C1 | `artclaw skill create` | 创建脚手架 | ✅ |
| C2 | `artclaw skill generate` | 自然语言生成（降级模式，AI 后端待接入） | ✅ |
| C3 | `artclaw skill test` | 本地测试 | ✅ |
| C4 | `artclaw skill package` | 打包发布 | ✅ |
| C5 | `artclaw skill publish` | 发布到团队库 | ✅ |
| C6 | `artclaw skill install/list/info/enable/disable/uninstall/update/check-deps` | 管理命令 | ✅ |

### 阶段 D: UE 编辑器集成 (P1) ✅

| # | 任务 | 说明 | 状态 |
|---|------|------|------|
| D1 | Slate UI "Create Skill" 按钮 | `OnCreateSkillClicked()` | ✅ |
| D2 | 自然语言输入对话框 | `OpenSkillCreationDialog()` 模态窗口 | ✅ |
| D3 | 生成进度显示 | `StartSkillGeneration()` + `PollSkillGenerationProgress()` | ✅ |
| D4 | 预览与确认界面 | `OpenSkillPreviewDialog()` + `ShowCppRequirementDialog()` | ✅ |

### 阶段 E: 团队同步 (P1) ✅

| # | 任务 | 说明 | 状态 |
|---|------|------|------|
| E1 | 团队库 Git 工作流 | `team_skills/.gitignore` + `README.md` | ✅ |
| E2 | Skill 版本管理 | 跨层级版本比较 | ✅ |
| E3 | 依赖自动解析 | `check-deps` 命令 + install 后自动检查 | ✅ |

### MCP 精简 (附加优化) ✅

| 优化 | 说明 | 效果 |
|------|------|------|
| 去重 | 移除 context_provider 与 Skill 文件重复注册的工具 | -5 |
| 内化 | assess_risk / analyze_error / get_dynamic_prompt 内化到流程 | -3 |
| 合并 | memory_get/set/search/list → memory | -3 |
| 合并 | 12 个 skill_* → skill_list + skill_manage + skill_generate | -9 |
| 排除 | 写操作工具由 run_ue_python 替代 | -14 |
| 移除 | knowledge_index / knowledge_stats | -2 |
| **v1→v2 总计** | **55 → 22 个 MCP Tools** | **-60%** |
| v2.1 重构 | Skill 不再注册 MCP 工具，全部通过 run_python + execute_skill() API 调用 | -21（降为 1 个） |
| **v1→v2.1 总计** | **55 → 1 个 MCP Tool（run_ue_python）** | **-98%** |

---

## 11. 命名规范

### 11.1 Skill 名称

- **格式**: 蛇形命名 (snake_case)
- **示例**: `generate_material_documentation` `batch_rename_actors`
- **规则**:
  - 全小写
  - 单词间用下划线分隔
  - 动词开头
  - 不超过 64 字符

### 11.2 目录结构

Skill 统一放在 UE 插件运行时目录 `Skills/` 的分层子目录中：

```
Skills/
├── 00_official/<skill_name>/         # 官方 Skill
├── 01_team/<skill_name>/             # 团队共享
├── 02_user/<skill_name>/             # 用户个人
└── 99_custom/<skill_name>/           # 临时实验
```

开发资源（模板、枚举）位于 `artclaw/skills/`：

```
artclaw/skills/
├── categories.py                     # 标准分类枚举
└── templates/                        # 开发模板
```
### 11.3 文件命名

```
my_skill/
├── SKILL.md                          # 固定名（AI 文档 + 分发）
├── manifest.json                     # 固定名（MCP 注册）
├── __init__.py                       # 固定名（入口）
└── references/                       # 固定名（参考文档目录）
```

---

## 12. 参考文档

- [OpenClaw Skill Creator 规范](~/AppData/Roaming/npm/node_modules/openclaw/skills/skill-creator/SKILL.md)
- [ArtClaw 系统架构设计](./系统架构设计.md)
- [ArtClaw OpenClaw 宪法](./openClaw宪法.md)
- [UE Editor Agent 开发路线图](../UEClawBridge/specs/开发路线图.md)

---

**下一步**: 
- enable/disable 状态持久化（config.yaml 或 .disabled 标记文件）
- `artclaw skill generate` 接入 AI 后端（当前为模板降级模式）
- Skill 市场（远期）
