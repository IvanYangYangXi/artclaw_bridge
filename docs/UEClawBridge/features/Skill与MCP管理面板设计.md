# Skill 与 MCP 管理面板设计

**版本**: v1.0  
**日期**: 2026-03-27  
**状态**: 规划中  
**关联**: `docs/specs/skill-management-system.md` v2.1

---

## 1. 背景与问题

### 1.1 当前 Skill 目录现状

项目内存在多个 Skill 相关目录，职责有重叠：

| 目录 | 内容 | 类型 | 问题 |
|------|------|------|------|
| `skills/` (项目根) | 模板 + categories.py | 开发资源 | 仅模板，无实际 Skill |
| `team_skills/` (项目根) | .gitkeep + README | 团队 Skill 源码 | 空目录，未使用 |
| `openclaw-skills/` (项目根) | 5 个 artclaw-* SKILL.md | OpenClaw 触发文档 | 新建，与 skills/ 概念重叠 |
| `UEClawBridge/.../Skills/00_official/` | 3 个完整 Skill 包 | ArtClaw 运行时 Skill | 实际运行的 Skill |
| `UEClawBridge/.../Skills/01_team/` | .gitkeep | 团队 Skill 运行时 | 空目录 |
| `DCCClawBridge/skills/common\|maya\|max/` | .gitkeep | DCC Skill 运行时 | 空目录 |
| `~/.openclaw/skills/artclaw-*` | 5 个安装后的 SKILL.md | OpenClaw 安装位置 | 与 openclaw-skills/ 副本 |
| `~/.artclaw/skills/` | 用户 Skill | 用户个人库 | 设计中，未实际使用 |

### 1.2 两种 Skill 类型

当前实际存在两种不同性质的 Skill：

| 特征 | ArtClaw Skill（DCC 内运行） | OpenClaw Skill（AI 触发文档） |
|------|---------------------------|------------------------------|
| 文件 | manifest.json + `__init__.py` + SKILL.md | 仅 SKILL.md |
| 运行 | `skill_hub.execute_skill()` 在 DCC 进程内执行 Python | AI 读取 SKILL.md 后通过 `run_python` 生成代码执行 |
| 注册 | skill_hub / skill_runtime 内部字典 | OpenClaw 框架按需加载 |
| 管理 | `artclaw skill` CLI | 手动复制文件 |
| 例子 | `artclaw_material`, `get_material_nodes` | `artclaw-context`, `artclaw-memory` |

**核心区别**: ArtClaw Skill 是**预编写的可执行代码包**；OpenClaw Skill 是**指导 AI 即时生成代码的参考文档**。

### 1.3 统一方向

两者不矛盾，应合并为**统一的 Skill 体系**：

- 每个 Skill 可以**同时具备**两种能力：有 `__init__.py` 时可直接执行，有 `SKILL.md` 时可作为 AI 文档
- 分层保持不变：`系统(official)` > `市集(marketplace)` > `用户(user)`
- 目录统一，不再分散

---

## 2. 统一目录规划

### 2.1 项目源码目录（合并后）

```
artclaw_bridge/
├── skills/                           # 统一 Skill 源码目录
│   ├── templates/                    # 开发模板（保留）
│   │   ├── basic/
│   │   ├── advanced/
│   │   └── material_doc/
│   ├── categories.py                 # 分类枚举（保留）
│   │
│   ├── official/                     # 系统（官方）Skill
│   │   ├── artclaw_material/         # 完整 Skill 包 (manifest + __init__ + SKILL.md)
│   │   ├── get_material_nodes/
│   │   ├── generate_material_documentation/
│   │   ├── artclaw-context/          # 纯文档 Skill (SKILL.md only)
│   │   ├── artclaw-highlight/
│   │   ├── artclaw-knowledge/
│   │   ├── artclaw-memory/
│   │   └── artclaw-skill-manage/
│   │
│   └── marketplace/                  # 市集（团队共享）Skill — Git 管理
│       └── ...
│
├── (删除) openclaw-skills/           # 合并到 skills/official/
├── (删除) team_skills/               # 合并到 skills/marketplace/
```

**变更说明**:
- `openclaw-skills/` → 合并到 `skills/official/`（这 5 个 artclaw-* 就是官方 Skill）
- `team_skills/` → 重命名为 `skills/marketplace/`（语义更清晰）
- `skills/templates/` 和 `categories.py` 保留不动
- 新增 `skills/official/` 和 `skills/marketplace/`

### 2.2 运行时目录（DCC 内部）

```
UEClawBridge/Content/Python/Skills/   # UE 运行时（install.bat 部署）
├── official/                         # 来自 skills/official/ （重命名 00→official）
├── marketplace/                      # 来自 skills/marketplace/（重命名 01→marketplace）
├── user/                             # 来自 ~/.artclaw/skills/ （重命名 02→user）
└── custom/                           # 临时实验（重命名 99→custom）
```

> **注意**: 数字前缀 `00_/01_/02_/99_` 改为语义名称 `official/marketplace/user/custom`，代码里靠 `LAYER_PRIORITY` 字典控制优先级，不再依赖目录排序。

### 2.3 OpenClaw 安装目录

```
~/.openclaw/skills/                   # OpenClaw 框架加载
├── artclaw-context/SKILL.md          # 来自 skills/official/artclaw-context/
├── artclaw-memory/SKILL.md
├── ...
```

install.bat 从 `skills/official/` 里扫描带 SKILL.md 的目录，复制 SKILL.md 到此处。

### 2.4 用户本地目录

```
~/.artclaw/skills/                    # 用户个人 Skill（不进 Git）
└── my_custom_skill/
    ├── manifest.json
    ├── __init__.py
    └── SKILL.md
```

---

## 3. Skill 分类与安装策略

### 3.1 系统 Skill（official）

- **来源**: `skills/official/`
- **安装时机**: `install.bat` **默认安装**，不需用户选择
- **更新**: 随项目更新自动覆盖
- **包含**:
  - 完整 Skill 包（如 `artclaw_material`，有可执行代码）
  - 纯文档 Skill（如 `artclaw-context`，仅 SKILL.md 指导 AI）
- **示例**: `artclaw_material`, `get_material_nodes`, `artclaw-context`, `artclaw-memory` 等
- **UI 展示**: 锁定图标 🔒，不可卸载，可禁用

### 3.2 市集 Skill（marketplace）

- **来源**: `skills/marketplace/`（团队 Git） 或远期在线市集
- **安装时机**: 用户**手动选择安装**
- **更新**: 用户主动触发更新
- **发布**: 用户可将自己的 Skill 发布到市集（团队层）或提交到系统（官方层 — 需审核）
- **UI 展示**: 可安装、卸载、更新、启用/禁用

### 3.3 用户 Skill（user）

- **来源**: `~/.artclaw/skills/` 或在编辑器内创建
- **安装**: 本地创建或从市集安装
- **UI 展示**: 完全可管理

---

## 4. UI 设计：MCP 与 Skill 管理面板

### 4.1 入口

在 Dashboard 底部工具栏增加一个 **⚙ 管理** 按钮，点击打开管理面板（新 Tab 或侧滑面板）。

> 底部工具栏变更: `[+ 新会话] [创建 Skill] [⚙ 管理] [语言] [发送模式]`

### 4.2 管理面板布局

管理面板分为两个 Tab：**MCP 连接** 和 **Skill 管理**。

```
┌──────────────────────────────────────────────────┐
│  [MCP 连接]    [Skill 管理]                        │
├──────────────────────────────────────────────────┤
│                                                  │
│  (Tab 内容区)                                     │
│                                                  │
└──────────────────────────────────────────────────┘
```

### 4.3 MCP 连接 Tab

显示当前 MCP Server 状态和已连接的工具信息。

```
┌──────────────────────────────────────────────────┐
│  MCP Server 状态                                  │
│  ● 运行中  ws://127.0.0.1:8080                   │
│  已注册工具: 1 (run_ue_python)                    │
│  活跃连接: 1                                      │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │ 已注册工具列表                               │  │
│  │                                            │  │
│  │  ☑ run_ue_python                           │  │
│  │    万能 Python 执行器 (v2.6)               │  │
│  │    调用次数: 42  平均耗时: 0.3s             │  │
│  │                                            │  │
│  │  (LEGACY 模式下显示全部旧工具)              │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  [刷新]  [查看日志]  [重启 MCP Server]            │
└──────────────────────────────────────────────────┘
```

**功能**:
- 展示 MCP Server 运行状态（端口、连接数、已注册工具）
- 显示各工具的调用统计
- 提供刷新/重启操作

### 4.4 Skill 管理 Tab

分三个区域展示，通过筛选栏切换。

```
┌──────────────────────────────────────────────────┐
│  筛选: [全部 ▼] [分类 ▼] [🔍 搜索...]          │
├──────────────────────────────────────────────────┤
│                                                  │
│  ── 系统 Skill (official) ──────────── 5/8 启用  │
│                                                  │
│  🔒 ☑ artclaw-context    编辑器上下文查询        │
│  🔒 ☑ artclaw-memory     项目记忆管理            │
│  🔒 ☑ artclaw-knowledge  知识库搜索              │
│  🔒 ☑ artclaw-highlight  Actor 高亮定位          │
│  🔒 ☑ artclaw-skill-manage  Skill 管理           │
│  🔒 ☑ artclaw_material   材质分析与操作          │
│  🔒 ☐ get_material_nodes 材质节点提取            │
│  🔒 ☑ generate_material_documentation 材质文档   │
│                                                  │
│  ── 市集 Skill (marketplace) ──────── 2/3 启用   │
│                                                  │
│     ☑ team_batch_rename   批量重命名 v1.2.0      │
│       [更新可用: v1.3.0] [更新] [卸载]           │
│     ☑ team_light_setup    灯光预设 v2.0.1        │
│     ☐ team_uv_tools       UV 工具集 v1.0.0       │
│       [卸载]                                     │
│                                                  │
│  ── 用户 Skill (user) ───────────── 1/1 启用     │
│                                                  │
│     ☑ my_custom_tool      自定义工具 v0.1.0      │
│       [编辑] [发布到市集] [发布到系统] [删除]    │
│                                                  │
├──────────────────────────────────────────────────┤
│  [安装 Skill...] [创建 Skill] [刷新]            │
└──────────────────────────────────────────────────┘
```

**每行 Skill 信息**:
- 勾选框：启用/禁用
- 锁定图标（系统 Skill）
- 名称 + 简短描述
- 版本号
- 操作按钮（根据类型不同）

**操作按钮**:

| 操作 | 系统 | 市集 | 用户 |
|------|------|------|------|
| 启用/禁用 | ☑ | ☑ | ☑ |
| 卸载 | ✗ | ☑ | ☑ |
| 更新 | 随安装器更新 | ☑ | ✗ |
| 编辑 | ✗ | ✗ | ☑ |
| 发布到市集 | ✗ | ✗ | ☑ |
| 发布到系统 | ✗ | ✗ | ☑ (需审核) |
| 删除 | ✗ | ✗ | ☑ |
| 查看详情 | ☑ | ☑ | ☑ |

### 4.5 Skill 详情弹窗

点击 Skill 名称或"查看详情"弹出：

```
┌──────────────────────────────────────────────────┐
│  artclaw_material — 材质分析与操作                │
├──────────────────────────────────────────────────┤
│                                                  │
│  版本: 1.0.0                                     │
│  作者: ArtClaw Official                          │
│  分类: material                                  │
│  适用: unreal_engine 5.3+                        │
│  风险: low                                       │
│  层级: official                                  │
│                                                  │
│  描述:                                           │
│  读取并分析材质蓝图结构，提取参数、节点连接关    │
│  系，生成文档或执行批量材质操作。                  │
│                                                  │
│  文件:                                           │
│  ☑ manifest.json (MCP 注册元数据)                │
│  ☑ __init__.py (可执行代码)                      │
│  ☑ SKILL.md (AI 文档)                            │
│  ☑ references/ (参考文档)                        │
│                                                  │
│                         [启用/禁用]    [关闭]     │
└──────────────────────────────────────────────────┘
```

### 4.6 安装 Skill 弹窗

点击"安装 Skill..."按钮弹出：

```
┌──────────────────────────────────────────────────┐
│  安装 Skill                                      │
├──────────────────────────────────────────────────┤
│                                                  │
│  来源: (●) 市集浏览  ( ) 本地文件  ( ) Git URL   │
│                                                  │
│  [市集浏览模式下显示可安装的 Skill 列表]          │
│                                                  │
│  可用 Skill:                                     │
│  ☐ team_asset_validator  资产规范检查  v1.0.0    │
│  ☐ team_level_builder    关卡快速搭建  v2.1.0    │
│  ☐ community_uv_layout   UV 自动布局   v3.0.0   │
│                                                  │
│                          [安装选中]    [取消]     │
└──────────────────────────────────────────────────┘
```

### 4.7 发布 Skill 弹窗

点击"发布到市集"或"发布到系统"按钮弹出：

```
┌──────────────────────────────────────────────────┐
│  发布 Skill: my_custom_tool                      │
├──────────────────────────────────────────────────┤
│                                                  │
│  发布目标: (●) 市集（团队） ( ) 系统（官方）     │
│                                                  │
│  版本: [1.0.0    ]                               │
│  变更说明: [________________________]             │
│                                                  │
│  发布检查:                                       │
│  ☑ manifest.json 格式正确                        │
│  ☑ __init__.py 存在                              │
│  ☑ SKILL.md 存在                                 │
│  ☐ 无语法错误 (未检查)                           │
│                                                  │
│                            [发布]      [取消]     │
└──────────────────────────────────────────────────┘
```

---

## 5. 实现要点

### 5.1 目录重构（一次性迁移）

1. `skills/official/` ← 合并 `UEClawBridge/.../Skills/00_official/*` + `openclaw-skills/*`
2. `skills/marketplace/` ← 重命名 `team_skills/`（保留 README、.gitignore）
3. 删除 `openclaw-skills/` 目录
4. UE 运行时目录改名: `00_official` → `official`, `01_team` → `marketplace`, `02_user` → `user`, `99_custom` → `custom`
5. 更新 `skill_hub.py` / `skill_loader.py` 中的层级常量
6. 更新 `install.bat`: 从 `skills/official/` 部署到 UE 和 OpenClaw

### 5.2 启用/禁用持久化

- 禁用状态写入 `~/.artclaw/config.json` 的 `disabled_skills` 数组
- `skill_hub.py` 加载时跳过 disabled 列表中的 Skill
- UI 勾选框变更时写入文件 + 通知 skill_hub 热更新

### 5.3 C++ UI 实现

- 管理面板: 新建 `SUEAgentManagePanel.h/cpp`
- 入口: Dashboard 底部新增 ⚙ 按钮，点击弹出或切换到管理面板
- MCP Tab: 读取 `_bridge_status.json` 获取 MCP Server 信息
- Skill Tab: 通过 Python 调用 `skill_hub.list_skills()` 获取数据
- 操作: 通过 Python 调用 `skill_hub.manage_skill(action, name)` 执行

### 5.4 Python API 扩展

`skill_hub.py` 需要新增：

```python
# 新增 API
def get_skill_details(name: str) -> dict         # 详情（含文件列表、统计）
def set_skill_enabled(name: str, enabled: bool)  # 启用/禁用
def get_disabled_skills() -> list                 # 获取禁用列表
def publish_skill(name: str, target: str, version: str, message: str) -> dict  # 发布
def install_skill(source: str, source_type: str) -> dict  # 安装
def check_updates() -> list                       # 检查可用更新
def get_mcp_status() -> dict                      # MCP Server 状态
```

### 5.5 DCC 侧适配

- DCCClawBridge 的 `skill_runtime.py` 同步新增对应 API
- DCC 管理面板使用 Qt 实现（`artclaw_ui/manage_panel.py`）
- 布局和功能与 UE 版本一致

---

## 6. 开发分期

### Phase 1: 目录重构 + 数据模型（P0）
- 合并目录结构
- 更新 skill_hub / skill_loader 层级常量
- 更新 install.bat
- 启用/禁用持久化

### Phase 2: MCP 管理 Tab（P1）
- C++ 管理面板框架 (`SUEAgentManagePanel`)
- MCP 连接状态展示
- 工具列表 + 调用统计

### Phase 3: Skill 管理 Tab — 查看与控制（P1）
- Skill 列表展示（三层分区）
- 启用/禁用勾选
- 详情弹窗
- 搜索/筛选

### Phase 4: Skill 管理 Tab — 安装与发布（P2）
- 安装 Skill（本地/市集/Git）
- 发布到市集/系统
- 版本更新检测与执行
- 发布前检查（lint）

### Phase 5: DCC 侧适配（P2）
- Qt 版管理面板
- skill_runtime.py API 同步

---

## 7. 对现有文档的影响

| 文档 | 需要更新 |
|------|----------|
| `docs/specs/skill-management-system.md` | §3 目录结构、§5 层级名称 |
| `docs/skills/CONTRIBUTING.md` | 发布流程 |
| `install.bat` | 部署路径 |
| `UE插件UI交互功能清单.md` | 新增管理面板章节 |
