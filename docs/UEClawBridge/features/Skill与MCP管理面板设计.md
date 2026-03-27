# Skill 与 MCP 管理面板设计

**版本**: v1.4  
**日期**: 2026-03-27  
**状态**: Phase 1-5 全部完成  
**关联**: `docs/specs/skill-management-system.md` v2.1

---

## 1. 核心概念

### 1.1 两种 Skill 能力

一个 Skill 目录可以同时具备两种能力：

| | 可执行代码包 | AI 参考文档 |
|---|---|---|
| **标志文件** | `__init__.py` + `manifest.json` | `SKILL.md` |
| **运行方式** | `execute_skill("name", params)` 直接调用 | AI 读 SKILL.md → 生成代码 → `run_python` 执行 |
| **适用** | 复杂固定逻辑（材质节点操作几百行） | 简单灵活逻辑（查选中对象几行） |
| **可同时存在** | ☑ | ☑ |

### 1.2 三个位置与副本关系

```
① 项目源码（唯一编辑位置，Git 管理）
   skills/official/unreal/ue54_artclaw_material/

        │ install.bat 或 管理面板一键同步
        ▼

② DCC 运行时目录                               ③ OpenClaw Skills 目录
   UEClawBridge/.../Skills/official/               ~/.openclaw/skills/
   └── ue54_artclaw_material/                      └── ue54_artclaw_material/
       ├── manifest.json                               └── SKILL.md (仅文档)
       ├── __init__.py  ← 执行位置
       └── SKILL.md
```

**用户创建的 Skill** 不经过项目源码，直接在运行时目录创建：

```
用户在编辑器内创建 Skill
        ↓
直接写入 ② DCC 运行时: Skills/user/ue54_my_tool/
同时写入 ③ OpenClaw: ~/.openclaw/skills/ue54_my_tool/SKILL.md
        ↓
skill_hub 热加载 → 立即可用
        ↓
用户想分享 → "发布"到 ① 项目源码 skills/marketplace/
```

### 1.3 运行时如何知道源码位置

**通过配置文件**，不硬编码：

```json
// ~/.artclaw/config.json
{
  "project_root": "D:\\MyProject_D\\artclaw_bridge",
  "disabled_skills": [],
  "pinned_skills": []
}
```

- `project_root` 在 install.bat 运行时自动写入
- 也可通过管理面板手动设置
- 有了 project_root，即可定位 `skills/marketplace/`、`skills/official/` 等源码目录
- **无 project_root 时**：发布/更新功能不可用，只显示已安装的 Skill

---

## 2. Skill 命名规范

### 2.1 命名格式

```
{dcc}{major_version}_{skill_name}
```

| 部分 | 说明 | 示例 |
|------|------|------|
| `dcc` | 软件缩写：`ue` / `maya` / `max` / 空(通用) | `ue` |
| `major_version` | 大版本号（两位数字） | `54` = UE 5.4 |
| `skill_name` | 功能描述（snake_case） | `artclaw_material` |

### 2.2 命名示例

| Skill | 命名 | 说明 |
|------|------|------|
| UE 5.4 材质操作 | `ue54_artclaw_material` | UE 专用 |
| Maya 2024 曲线工具 | `maya24_curve_tools` | Maya 专用 |
| Max 2025 修改器 | `max25_modifier_stack` | Max 专用 |
| 通用记忆管理 | `artclaw-memory` | 无 DCC 前缀 = 通用 |
| UE 5.5 高亮 | `ue55_highlight_actors` | 版本敏感 |

### 2.3 通用 Skill 不加前缀

跨 DCC 的纯文档 Skill（如 artclaw-context/memory/knowledge）不加 DCC 前缀：
- `artclaw-context`（SKILL.md 内部按 DCC 分节描述不同用法）
- `artclaw-memory`
- `artclaw-knowledge`
- `artclaw-skill-manage`

### 2.4 创建时自动补全

AI 创建 Skill 时，skill_hub 自动补全命名：

```python
def auto_name(user_name: str, software: str, version: str) -> str:
    """
    user_name: "material_ops"
    software: "unreal_engine", version: "5.4.1"
    → "ue54_material_ops"
    """
    prefix_map = {
        "unreal_engine": f"ue{version.replace('.','')[:2]}",  # "5.4.1" → "ue54"
        "maya": f"maya{version[:2]}",                          # "2024" → "maya24"
        "3ds_max": f"max{version[:2]}",                        # "2025" → "max25"
        "universal": "",
    }
    prefix = prefix_map.get(software, "")
    clean = user_name.lstrip("_").lower()
    if prefix and not clean.startswith(prefix):
        return f"{prefix}_{clean}"
    return clean
```

artclaw-skill-manage SKILL.md 中更新创建流程，提示 AI 使用 `auto_name()` 或手动遵循命名规范。

---

## 3. Skill 完整生命周期

### 3.1 核心原则：一个 Skill 在运行时只有一份

每个 Skill 在运行时目录中**只能存在于一个层级**。发布 = 搬家，不是复制。这避免了同一 Skill 在 user/ 和 marketplace/ 各一份导致的冲突。

### 3.2 创建

```
用户: "帮我创建一个批量重命名 Actor 的技能"
        ↓
AI 自动检测环境: UE 5.4
AI 自动命名: ue54_batch_rename_actors
AI 确认摘要:
  "📦 名称: ue54_batch_rename_actors
   📂 分类: scene     🎯 适用: UE 5.4+
   ⚠️ 风险: medium   📁 位置: user 层
   确认创建？"
        ↓
用户确认 → AI 生成代码 → 写入:
  ② Skills/user/ue54_batch_rename_actors/
     ├── manifest.json  (自动生成，version: "0.1.0")
     ├── __init__.py    (AI 写的代码)
     └── SKILL.md       (AI 写的文档)
  ③ ~/.openclaw/skills/ue54_batch_rename_actors/
     └── SKILL.md       (同步复制)
        ↓
skill_hub 热加载 → 立即可用
```

此时 Skill **只在 user 层**，是私有的。

### 3.3 修改

用户在管理面板点 [编辑] → 打开 Skill **当前所在目录**（此时是 `Skills/user/ue54_batch_rename_actors/`）。

修改代码 → skill_hub 文件监控检测变更 → 热重载。无需额外操作。

### 3.4 发布到市集

```
管理面板点 [发布...] → 选择"市集"
        ↓
检查通过 → 版本号: 0.1.0 → 1.0.0（自动递增到正式版）
        ↓
执行（原子操作）:
  1. 复制到项目源码: skills/marketplace/unreal/ue54_batch_rename_actors/
  2. git add + commit
  3. 运行时: 移动 Skills/user/ → Skills/marketplace/（搬家，不是复制）
  4. 更新 skill_hub 注册信息（层级从 user → marketplace）
  5. 同步更新 ~/.openclaw/skills/ 的 SKILL.md
        ↓
提示用户 git push 分享给团队
```

**关键**: 发布后 `user/` 中的原件**被移走**，此 Skill 现在属于 marketplace 层。

### 3.5 发布后继续修改

Skill 已在 marketplace 层。用户点 [编辑] → 打开 `Skills/marketplace/ue54_batch_rename_actors/`。

```
修改代码 → 热重载 → 本地立即生效
        ↓
想同步给团队 → 点 [发布...] → 版本自动递增 1.0.0 → 1.0.1
        ↓
更新项目源码 skills/marketplace/ → git commit → push
```

**编辑始终操作 Skill 当前所在的运行时目录**，不存在两份文件的问题。

### 3.6 发布到系统（晋升）

```
管理面板点 [发布...] → 选择"系统（需审核）"
        ↓
检查通过 → 创建 Git 分支 feat/skill-ue54_batch_rename_actors
        ↓
复制到项目源码: skills/official/unreal/ue54_batch_rename_actors/
git commit → 创建 PR
        ↓
（此时运行时目录不动，仍在 marketplace 层）
        ↓
PR 审核通过 → 合并到 main
        ↓
下次 install.bat 或一键同步 → 运行时: 移动 marketplace/ → official/
```

**注意**: 系统发布是异步的（等 PR 合并），运行时层级升级要等同步操作。

### 3.7 团队成员安装市集 Skill

```
git pull → 新 Skill 出现在 skills/marketplace/unreal/
        ↓
方式 A: 运行 install.bat → 自动安装到运行时 Skills/marketplace/
方式 B: 管理面板 [安装...] → 选择市集中的 Skill → 安装
方式 C: 管理面板 [一键同步] → 自动检测源码 vs 运行时差异 → 增量更新
```

### 3.8 日常管理操作

```
┌─────────────────────────────────────────────────────┐
│                    管理面板                           │
│                                                     │
│  查看    → Skill 列表 + 详情弹窗                    │
│  启用    → ☑ → skill_hub 注册 + SKILL.md 激活       │
│  禁用    → ☐ → skill_hub 移除 + SKILL.md.disabled   │
│  钉选    → 📌 → 强制注入 AI 上下文，优先使用        │
│  编辑    → 打开 Skill 当前所在目录（user/market 均可）│
│  更新    → 从源码复制新版到运行时（市集 Skill）      │
│  发布    → 搬家到 marketplace/official + git commit  │
│  卸载    → 删除运行时 + OpenClaw 的文件              │
│  删除    → 卸载 + 从源码目录也删除（仅用户 Skill）   │
│  创建    → AI 对话式创建                             │
│  安装    → 从市集/本地 安装到运行时                   │
│  同步    → 批量检测差异 + 增量更新                    │
└─────────────────────────────────────────────────────┘
```

### 3.9 防冲突规则总结

| 场景 | 处理 |
|------|------|
| 发布 user → marketplace | **移动**，不是复制。user/ 原件删除 |
| 晋升 marketplace → official | PR 合并后同步时**移动** |
| install.bat 安装 | 只镜像 official/ + marketplace/，**不动** user/ 和 custom/ |
| 同名 Skill 跨层 | 高优先级层覆盖低优先级层（已有冲突检测） |
| 发布时目标层已有同名 | 比较版本号：新版覆盖旧版；相同版本阻止并提示 |
| 运行时发现 user/ 和 marketplace/ 都有同名 | 提示用户清理（迁移遗留），只加载高优先级的 |

### 3.10 同步方式汇总

| 方式 | 场景 | 说明 |
|------|------|------|
| **install.bat** | 首次安装/大版本更新 | 全量部署 official + marketplace → 运行时 |
| **管理面板一键同步** | 日常增量 | 检测源码 vs 运行时版本差异，增量复制 |
| **管理面板单个更新** | 特定 Skill | 点 [更新] 按钮 |
| **管理面板安装** | 新 Skill | 从市集选择安装 |
| **文件监控** | 开发调试 | skill_hub 检测到文件变更自动热重载（已实现） |

---

## 4. 启用/禁用/钉选 — 与 Agent 的交互

### 4.1 三种状态

| 状态 | 含义 | 对 AI 的影响 |
|------|------|-------------|
| **☑ 启用** | Skill 已注册，AI 可按需调用 | AI 在需要时**可能**使用此 Skill（由 AI 判断） |
| **☐ 禁用** | Skill 未注册，对 AI 不可见 | AI **完全看不到**此 Skill |
| **📌 钉选** | 启用 + 强制注入上下文 | AI **必定看到**此 Skill 的描述，优先使用 |

### 4.2 启用 vs 钉选的区别

这是 Ivan 问的核心问题——"勾选是指告诉 agent 使用这个 skill 来执行会话内容"。

答案是：需要两层控制。

**启用（默认状态）**：Skill 注册在 skill_hub 中，但 AI 不一定知道它存在。AI 需要通过以下方式发现：
- 通过 OpenClaw Skill 的 SKILL.md 匹配（意图触发）
- 通过 `list_skills()` 主动查询
- 通过 execute_skill 直接调用（如果 AI 已知名称）

**钉选（主动推荐）**：将 Skill 的描述强制注入到 AI 的**每轮对话上下文**中。相当于告诉 AI："你当前有这些工具可用，优先用。"

```
钉选实现方式:
1. pinned_skills 列表存入 ~/.artclaw/config.json
2. bridge 层的 _enrich_with_briefing() 在每条消息前注入:
   "[可用 Skill] ue54_batch_rename_actors: 批量重命名 Actor（execute_skill 调用）"
3. AI 看到注入内容 → 知道有此 Skill → 相关任务优先用它
```

### 4.3 用户操作示例

| 场景 | 用户操作 | 效果 |
|------|----------|------|
| "这个 Skill 我不需要" | ☐ 禁用 | AI 看不到，不会使用 |
| "有这个 Skill 就好，需要时 AI 自己判断" | ☑ 启用（默认） | AI 可发现可使用，但不强制 |
| "我接下来要做材质相关工作，确保 AI 用这个" | 📌 钉选 | AI 每轮都看到此 Skill，优先使用 |
| "材质工作做完了" | 取消 📌，保持 ☑ | 回到默认，不再强制注入 |

### 4.4 管理面板交互

每行 Skill 的左侧有两个控件：

```
📌 ☑ ue54_artclaw_material    材质操作 v1.0.1   UE
│   │
│   └─ 启用/禁用 勾选框
└───── 钉选图标（点击切换，钉选时高亮）
```

---

## 5. 发布与版本号

### 5.1 版本号自动递增

发布弹窗打开时，根据当前版本自动计算默认值：

```python
def next_version(current: str, bump: str = "patch") -> str:
    """
    current: "1.2.3"
    bump="patch" → "1.2.4"
    bump="minor" → "1.3.0"
    bump="major" → "2.0.0"
    """
    major, minor, patch = [int(x) for x in current.split(".")]
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    elif bump == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump == "major":
        return f"{major + 1}.0.0"
```

### 5.2 发布弹窗

```
┌──────────────────────────────────────────────────┐
│  发布 Skill: ue54_batch_rename_actors            │
├──────────────────────────────────────────────────┤
│  目标: (●) 市集（团队，无需审核）                 │
│        ( ) 系统（官方，需 PR 审核）               │
│                                                  │
│  当前版本: 1.2.0                                 │
│  新版本:   [1.2.1    ] [patch ▼]                 │
│            默认 patch +1，可选 minor/major        │
│                                                  │
│  变更说明: [修复了多选时的命名冲突______]          │
│                                                  │
│  检查结果:                                       │
│  ☑ manifest.json 有效                            │
│  ☑ __init__.py 存在，无语法错误                  │
│  ☑ SKILL.md 存在                                 │
│  ☑ 命名规范: ue54_ 前缀正确                      │
│  ☑ 无安全风险                                    │
│                                                  │
│                           [发布]      [取消]      │
└──────────────────────────────────────────────────┘
```

### 5.3 审核流程

**市集（团队）**：复制到 `skills/marketplace/{dcc}/` → git commit → 提示 push，**无审核**。

**系统（官方）**：创建 Git 分支 `feat/skill-{name}` → 复制到 `skills/official/{dcc}/` → git commit → 创建 PR → **项目维护者 code review** → 合并。

---

## 6. DCC 区分

### 6.1 目录结构

```
skills/
├── templates/                    # 开发模板
├── categories.py                 # 分类枚举
│
├── official/                     # 系统 Skill
│   ├── universal/                # 通用（无 DCC 前缀）
│   │   ├── artclaw-context/
│   │   ├── artclaw-memory/
│   │   ├── artclaw-knowledge/
│   │   └── artclaw-skill-manage/
│   ├── unreal/                   # UE 专用
│   │   ├── ue54_artclaw_material/
│   │   ├── ue54_get_material_nodes/
│   │   ├── ue54_generate_material_documentation/
│   │   └── ue54_highlight_actors/
│   ├── maya/
│   └── max/
│
└── marketplace/
    ├── universal/
    ├── unreal/
    ├── maya/
    └── max/
```

### 6.2 install.bat 部署逻辑

安装 UE 插件时：
1. 复制 `skills/official/universal/*` → `Skills/official/`
2. 复制 `skills/official/unreal/*` → `Skills/official/`
3. 复制 `skills/marketplace/universal/*` → `Skills/marketplace/`（如果有）
4. 复制 `skills/marketplace/unreal/*` → `Skills/marketplace/`（如果有）
5. 扫描所有带 SKILL.md 的 Skill → 复制 SKILL.md 到 `~/.openclaw/skills/`

### 6.3 管理面板筛选

默认只显示 `通用 + 当前 DCC` 的 Skill。DCC 筛选器可切换查看其他 DCC 的（仅查看，不可启用不匹配的）。

---

## 7. OpenClaw skills 不含 Python 代码的说明

**无风险**。原因：

`~/.openclaw/skills/` 中的 SKILL.md 不是代码执行位置，它是 **AI 的参考文档**。

```
AI 收到用户请求 "分析这个材质"
        ↓
OpenClaw 框架匹配到 artclaw-context/SKILL.md
        ↓
AI 阅读 SKILL.md，了解如何调用 API
        ↓
AI 通过 MCP 工具 run_ue_python 发送 Python 代码
        ↓
代码在 DCC 进程内的 ② 运行时目录执行
```

SKILL.md 只提供"怎么做"的说明，真正的执行发生在 DCC 进程内。没有 Python 代码在 OpenClaw 侧执行。

如果 Skill 是代码包类型（有 `__init__.py`），AI 也不需要看到代码——AI 只需要知道 `execute_skill("name", params)` 的调用方式和参数说明，这些信息都在 SKILL.md 或 manifest 的 tools 字段中。

---

## 8. 补充：已识别的分歧与待确认项

### 8.1 现有 Skill 改名的迁移成本

现有 3 个 UE 官方 Skill（`artclaw_material`, `get_material_nodes`, `generate_material_documentation`）需要加 `ue54_` 前缀。改名涉及：
- 目录名变更
- manifest.json 的 name 字段更新
- `__init__.py` 中 `@ue_tool(name=...)` 装饰器的 name 更新
- skill_hub 的内部注册字典 key 变更
- 如果已有记忆引用了旧名，需要兼容映射

**建议**：维护一个 `_NAME_ALIAS_MAP`，旧名自动映射到新名，渐进迁移。

### 8.2 版本号粒度：Skill 名称 vs manifest

命名包含大版本号（`ue54_`），manifest 中也有 `software_version.min`。两者的关系：
- 名称的版本是**面向用户的快速识别**（"这是 UE 5.4 的"）
- manifest 的 version range 是**运行时兼容性检查**（5.4+ 都能用还是只有 5.4）

如果一个 Skill 兼容 UE 5.4~5.5，命名用 `ue54_`（以最低兼容版本命名），manifest 设 `min: 5.4, max: 5.5`。

### 8.3 钉选的上下文 token 成本

每个钉选的 Skill 会往每轮对话注入一段描述（约 50-100 tokens）。钉选过多会增加上下文长度。

**建议**：限制最多钉选 5 个，超出时提示用户取消不需要的。

### 8.4 远期在线市集的注册表格式

当前方案基于 Git 本地目录。远期如果要做在线市集（类似 ClawHub），需要：
- 注册表 API（list/search/download）
- 包分发格式（.zip？.skill？）
- 身份认证 + 签名验证

**建议**：暂不设计，当前 Git 模式够用，远期再扩展。

### 8.5 DCC 运行时目录的用户 Skill 备份

用户 Skill 直接创建在运行时目录 `Skills/user/`，如果用户重装插件（install.bat /MIR）会被覆盖删除。

**方案**：
- install.bat 不对 `user/` 和 `custom/` 目录使用 `/MIR`（只镜像 official + marketplace）
- 管理面板提供"导出 Skill"功能
- 发布到市集后 user/ 原件已搬走，不受 install.bat 影响

### 8.6 发布后的编辑归属

发布采用**搬家语义**（move，不是 copy），确保一个 Skill 在运行时只有一份。详见 §3.4-3.5。

潜在边界情况和处理：
- **发布后 install.bat 覆盖**：install.bat 从源码 marketplace/ 部署到运行时 marketplace/，与发布后的状态一致，无冲突
- **两人同时发布同名 Skill**：Git 层面冲突，走 Git merge 流程解决
- **用户想撤回发布**：管理面板提供 [移回用户层] 操作，从 marketplace → user 反向搬家
- **startup 时发现 user/ 和 marketplace/ 有同名 Skill**：skill_hub 只加载高优先级的（marketplace），日志警告提示清理

### 8.6 DCC 同时运行多个版本时的 Skill 冲突

如果用户同时开了 UE 5.4 和 5.5，两个运行时的 `Skills/` 各自独立，不冲突。但 `~/.openclaw/skills/` 是共享的——两个版本的 SKILL.md 可能不同。

**方案**：SKILL.md 是纯文档，内容差异不大（通常只是 API 调用方式的细微区别），共享无问题。如果确实不兼容，SKILL.md 内部按版本分节说明。

---

## 9. 开发分期

### Phase 1: 目录重构 + 改名迁移（P0）

**1a. 目录合并**
- 创建 `skills/official/universal/`, `skills/official/unreal/`, `skills/marketplace/`
- 移动现有 UE Skill 到 `skills/official/unreal/`
- 移动 openclaw-skills 的 5 个 artclaw-* 到 `skills/official/universal/`
- 删除 `openclaw-skills/` 和 `team_skills/`

**1b. 改名迁移**
- 现有 3 个 UE Skill 加 `ue54_` 前缀（`artclaw_material` → `ue54_artclaw_material` 等）
- 更新每个 Skill 的 manifest.json name 字段 + `__init__.py` 中的 `@ue_tool(name=...)` 装饰器
- skill_hub 中添加 `_NAME_ALIAS_MAP` 兼容旧名（旧名自动映射到新名，打印 deprecation 警告）
- 更新 artclaw-skill-manage SKILL.md 的创建流程文档

**1c. 代码更新**
- skill_hub.py / skill_loader.py 层级常量: `00_official` → `official`, `01_team` → `marketplace`, `02_user` → `user`, `99_custom` → `custom`
- 优先级由 `LAYER_PRIORITY` 字典控制，不依赖目录排序
- install.bat: 按 DCC 选择性部署 + 不镜像 user/custom

**1d. 配置体系**
- `~/.artclaw/config.json`: project_root + disabled_skills + pinned_skills
- install.bat 自动写入 project_root
- 启用/禁用 + 钉选持久化

### Phase 2: 管理面板框架 + MCP Tab（P1）✅ 已实现
- C++ SUEAgentManagePanel 外壳 + Tab 切换
- **文件拆分**: ManagePanel(外壳) / McpTab / SkillTab / ManageUtils(共享工具)
- MCP Tab 读取 `~/.openclaw/openclaw.json` 中所有 MCP Server 配置
- 显示每个 Server 的名称、类型、URL、连接状态（端口探测）
- 每个 Server 可启用/禁用（写回 openclaw.json 的 `enabled` 字段）
- "安装 MCP" 按钮 — 弹窗填写 Server ID + URL，写入 openclaw.json
- 连接状态通过 Python socket 探测端口（8080-8085）
- 显示名称映射: ue-editor-agent→"UE Claw Bridge", maya-primary→"Maya Claw Bridge", max-primary→"3ds Max Claw Bridge"

### Phase 3: Skill Tab — 查看/启用/禁用/钉选 + 已安装分类（P1）✅ 已实现
- 双来源 Skill 列表:
  - ① skill_hub._all_manifests（代码包 Skill，标记 install_status=full）
  - ② ~/.openclaw/skills/ 目录扫描（仅文档 Skill，标记 install_status=doc_only）
  - 按 name 去重，代码包优先
- **层级筛选**: All / Official / Market / User / OpenClaw（新增 openclaw 层 = 仅文档安装）
- **安装状态筛选**: All / Full (代码+文档) / Doc (仅 SKILL.md)
- 勾选启用/禁用 + 钉选（持久化到 ~/.artclaw/config.json）
- 详情弹窗增加安装类型显示
- 钉选上下文注入（bridge 层 `_enrich_with_briefing()`）

#### C++ 文件结构
```
Source/UEClawBridge/
├── Public/
│   ├── UEAgentManagePanel.h   — 外壳 (Tab 切换)
│   ├── UEAgentMcpTab.h        — MCP Server 管理
│   ├── UEAgentSkillTab.h      — Skill 管理
│   └── UEAgentManageUtils.h   — 共享工具 (Python IPC / 文件 IO)
└── Private/
    ├── UEAgentManagePanel.cpp  — ~100 行
    ├── UEAgentMcpTab.cpp       — ~500 行
    ├── UEAgentSkillTab.cpp     — ~600 行
    └── UEAgentManageUtils.cpp  — ~80 行
```

#### 设计决策 (v1.3)

**MCP "添加" 而非 "安装"**：面板里的按钮是添加连接配置（写 openclaw.json），不是安装 MCP 包。真正的安装（下载 npm 包 / git clone / 配置环境）应该直接在聊天中让 AI 做，比 UI 弹窗灵活得多。

**Skill 安装/卸载/未安装列表**：属于 Phase 4，需要对比项目源码 vs 运行时目录的差异。当前 Phase 3 只显示已安装的。

**Skill 文件路径显示**：详情弹窗显示 `source_dir`，让 AI 在聊天中收到"修改 xxx Skill"的请求时，知道改哪个目录下的文件。

**安装状态命名**：
- "运行时" (Runtime) = 有代码包，可 `execute_skill()` 直接执行
- "文档" (Guide) = 只有 SKILL.md，AI 读文档后通过 `run_python` 操作

### Phase 4: Skill Tab — 安装/更新/发布/同步（P2）✅ 已实现
- Python 层: `skill_sync.py` (531行) — 扫描/对比/安装/卸载/更新/同步/发布
  - `compare_source_vs_runtime()` 对比项目源码 vs 运行时差异
  - `install_skill()` / `install_all_available()` 从源码安装到运行时
  - `uninstall_skill()` 从运行时删除
  - `update_skill()` / `update_all()` 覆盖安装更新
  - `sync_all()` 一键同步（安装+更新）
  - `publish_skill()` 搬家语义发布到市集 + git commit
- C++ SkillTab 增强:
  - 新增 "未安装" 筛选项（来自 `compare_source_vs_runtime().available`）
  - 每行 Skill 根据状态显示不同操作按钮:
    - 未安装 → [安装]
    - 可更新 → [更新]
    - user/custom 层 → [卸载] [发布]
  - "一键同步" 按钮（安装全部未安装 + 更新全部过期）
  - 发布弹窗: 选择版本递增方式 (patch/minor/major) + 变更说明

### Phase 5: Skill 创建命名优化（P2）✅ 已实现
- `auto_name()` 已在 skill_hub.py 中实现
- `artclaw-skill-manage` SKILL.md 已更新: 增加 Phase 4 sync API 文档
- SKILL.md 已同步到 `~/.openclaw/skills/`
- Qt 版管理面板（DCC 侧）→ 暂缓，当前 UE Slate 版足够验证
