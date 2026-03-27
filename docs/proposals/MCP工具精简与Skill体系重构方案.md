# MCP 工具精简与 Skill 体系重构方案

> 日期: 2026-03-27
> 作者: 小优
> 状态: 提案 v2（已审核宪法文档）
> 审核依据: 系统架构设计.md / skill-management-system.md / openClaw集成方案.md / 记忆管理系统设计.md / 项目目录结构说明.md

---

## 1. 背景与动机

### 1.1 问题

MCP 工具在 AI 每轮请求时**全量注入** system prompt（name + description + input_schema），不论是否使用。工具越多，上下文浪费越大，AI 选错工具的概率越高。

### 1.2 现状盘点（代码审查）

**UE 侧 (UEClawBridge)** — 内置 MCP 工具:

| # | 工具名 | 来源 | 注册为 MCP? |
|---|--------|------|------------|
| 1 | `run_ue_python` | tools/universal_proxy.py | ✅ |
| 2 | `get_editor_context` | tools/context_provider.py | ✅ |
| 3 | `highlight_actors` | tools/context_provider.py | ✅ |
| 4 | `memory` | memory_store.py | ✅ |
| 5 | `knowledge_search` | knowledge_base.py | ✅ |
| 6 | `skill_list` | skill_mcp_tools.py | ✅ |
| 7 | `skill_manage` | skill_mcp_tools.py | ✅ |
| 8 | `skill_generate` | skill_mcp_tools.py | ✅ |
| — | `assess_risk` | tools/risk_confirmation.py | ❌ 已内化 |
| — | `analyze_error` | tools/self_healing.py | ❌ 已内化 |

**+ SkillHub 动态注册的 ArtClaw Skill**（每个 Skill = 1 个额外 MCP 工具）

**DCC 侧 (DCCClawBridge, Maya/Max)** — 内置 MCP 工具:

| # | 工具名 | 来源 |
|---|--------|------|
| 1 | `run_python` | mcp_server.py |
| 2 | `get_editor_context` | mcp_server.py |
| 3 | `get_selected_objects` | mcp_server.py |
| 4 | `get_scene_info` | mcp_server.py |
| 5 | `knowledge_search` | core/knowledge_base.py |
| 6 | `memory` | core/memory_store.py |

**+ SkillRuntime 动态注册的 ArtClaw Skill**

### 1.3 DCC MCP 架构现状

**是的，每个 DCC 软件运行独立的 MCP Server**。这是正确的设计：

```
Maya 进程 (Python 3.9)  ──  MCP Server ws://127.0.0.1:8081
Max 进程 (Python 3.11)  ──  MCP Server ws://127.0.0.1:8082
UE 进程 (Python 3.11)   ──  MCP Server ws://127.0.0.1:8080
```

**原因**：
- Maya/Max/UE 各自有内嵌 Python 解释器，版本/环境完全独立
- MCP Server 运行在 DCC 进程内部，通过 adapter 调用该 DCC 的原生 API
- 共享的是**代码骨架** (`mcp_server.py`, `bridge_core.py`, `memory_core.py`)，不是进程
- `mcp-bridge` 插件在 OpenClaw Gateway 端按配置分别连接各 MCP Server

这意味着每个 DCC 的工具都独立注入 AI 上下文。当 UE + Maya + Max 同时连接时，AI 看到的工具数量是三者之和（通过 `mcp_ue-editor-agent_*` / `mcp_maya-primary_*` / `mcp_max-primary_*` 前缀区分）。

**这进一步强化了精简的必要性**：3 套 × 6-8 个工具 = 18-24 个 MCP 工具同时占用上下文。

---

## 2. 重构目标

### 2.1 MCP 层：每个 DCC 只保留 1 个核心 MCP 工具

| DCC | 保留的 MCP 工具 | 说明 |
|-----|----------------|------|
| UE | `run_ue_python` | 万能执行器，唯一能实时操作 UE 进程的通道 |
| Maya | `run_python` | 万能执行器 |
| Max | `run_python` | 万能执行器 |

**为什么只留 1 个而不是 2 个（去掉 `get_editor_context`）：**

- `get_editor_context` 的功能完全可以通过 `run_python` 一行代码实现
- UE 侧：`run_ue_python` 已有 `inject_context=true` 参数，自动注入编辑器状态
- DCC 侧：`adapter.get_selected_objects()` / `adapter.get_scene_info()` 都是可通过 `run_python` 调用的 Python API
- 少 1 个工具 = 3 套 DCC 少 3 个 MCP 工具定义

**`knowledge_search` 包进 `run_python`：**

`knowledge_search` 本质是调用 `KnowledgeBase.search(query, top_k)` 这个 Python API。AI 完全可以通过 `run_python` 来调用：

```python
# AI 通过 run_python 调知识库
from knowledge_base import get_knowledge_base
kb = get_knowledge_base()
results = kb.search("set material color", top_k=5)
print(results)
```

**注意**：`knowledge_search` 的 Python API (`get_knowledge_base()`) 保留不动，只是不再注册为独立 MCP 工具。OpenClaw Skill 的 SKILL.md 会指导 AI 如何通过 `run_python` 调用它。

### 2.2 Skill 层：ArtClaw 从"Skill 运行时"转型为"Skill 市集"

**核心变化**：

| | 现在 | 重构后 |
|---|---|---|
| **ArtClaw Skill 运行时** | 加载 Skill → 注册为 MCP 工具 → 常驻上下文 | **移除 MCP 注册**，保留 Python 库函数供 `run_python` 调用 |
| **ArtClaw 市集** | 管理 Skill 包（create/install/publish） | 管理 Skill 包 + **同时分发 OpenClaw SKILL.md** |
| **OpenClaw Skill** | 不涉及 ArtClaw | 按需加载，匹配时读 SKILL.md 指导 AI |
| **用户创建 Skill** | 放 ArtClaw `02_user/` 层，注册为 MCP | 默认放 `~/.openclaw/skills/`，想共享再推到市集 |

### 2.3 Token 节省预估

| 场景 | 精简前 | 精简后 | 节省 |
|------|--------|--------|------|
| 单 DCC (UE) | 8+ 个内置工具 + N 个 Skill 工具 | 1 个工具 | **~90%+** |
| 三 DCC 同时连接 | 24+ 个工具 (~5,000-8,000 tokens) | 3 个工具 (~600 tokens) | **~90%** |
| OpenClaw 内置工具 | ~15 个 (~3,000 tokens) | 不变 | — |

---

## 3. 详细迁移映射

### 3.1 UE 侧

| 原 MCP 工具 | 迁移方式 | 新的调用路径 |
|-------------|---------|-------------|
| `run_ue_python` | **保留** | 唯一 MCP 工具 |
| `get_editor_context` | → OpenClaw Skill | SKILL.md 指导 AI 调 `run_ue_python` 获取上下文 |
| `highlight_actors` | → OpenClaw Skill | SKILL.md 指导 AI 调 `run_ue_python` 执行高亮 |
| `memory` | → OpenClaw Skill | SKILL.md 指导 AI 调 `run_ue_python` 操作 memory API |
| `knowledge_search` | → OpenClaw Skill | SKILL.md 指导 AI 调 `run_ue_python` 操作 kb API |
| `skill_list` | → OpenClaw Skill | SKILL.md 指导 AI 调 `run_ue_python` 查 skill_hub |
| `skill_manage` | → OpenClaw Skill | 同上 |
| `skill_generate` | → OpenClaw Skill | 同上 |
| SkillHub 动态注册的 Skill | **不再注册为 MCP 工具** | AI 通过 `run_python` + Skill 的 Python API 调用 |

### 3.2 DCC 侧 (Maya/Max)

| 原 MCP 工具 | 迁移方式 | 新的调用路径 |
|-------------|---------|-------------|
| `run_python` | **保留** | 唯一 MCP 工具 |
| `get_editor_context` | → OpenClaw Skill | `run_python` 调 adapter API |
| `get_selected_objects` | → OpenClaw Skill | `run_python` 调 adapter API |
| `get_scene_info` | → OpenClaw Skill | `run_python` 调 adapter API |
| `memory` | → OpenClaw Skill | `run_python` 调 memory API |
| `knowledge_search` | → OpenClaw Skill | `run_python` 调 kb API |
| SkillRuntime 动态注册的 Skill | **不再注册为 MCP 工具** | 同上 |

---

## 4. OpenClaw Skill 设计

### 4.1 Skill 列表

| Skill 名称 | 触发词/场景 | 覆盖原 MCP 工具 |
|-----------|------------|-----------------|
| `artclaw-context` | 编辑器状态、选中对象、场景信息、当前关卡 | `get_editor_context` + `get_selected_objects` + `get_scene_info` |
| `artclaw-memory` | 记住、记忆、之前做过、操作历史、偏好 | `memory` |
| `artclaw-knowledge` | 搜索文档、API文档、怎么用、查一下 | `knowledge_search` |
| `artclaw-skill-manage` | 创建skill、管理技能、安装skill | `skill_list` + `skill_manage` + `skill_generate` |
| `artclaw-highlight` | 高亮、定位actor、聚焦、选中 | `highlight_actors` |

### 4.2 Skill 存放位置

```
~/.openclaw/skills/
├── artclaw-context/
│   └── SKILL.md
├── artclaw-memory/
│   └── SKILL.md
├── artclaw-knowledge/
│   └── SKILL.md
├── artclaw-skill-manage/
│   └── SKILL.md
└── artclaw-highlight/
│   └── SKILL.md
```

**为什么是 OpenClaw Skill 而不是 ArtClaw Skill：**
- ArtClaw Skill 运行时的机制是 `加载 → 注册为 MCP 工具`，本质上还是常驻上下文
- OpenClaw Skill 是纯 SKILL.md 匹配 + 按需读取，未命中时只占 ~30 tokens（一行描述）
- 目的就是减少 MCP 注入，放回 ArtClaw 等于换个马甲

### 4.3 SKILL.md 设计要点

每个 SKILL.md 需要包含：

1. **触发描述**（让 OpenClaw 匹配引擎准确识别）
2. **可用的 Python API 列表**（AI 通过 run_python 调用的函数签名）
3. **示例代码片段**（降低 AI 代码生成出错概率）
4. **DCC 差异说明**（UE 用 `run_ue_python`，Maya/Max 用 `run_python`，API 可能不同）

**示例: `artclaw-context/SKILL.md`**

```markdown
# ArtClaw Context - 编辑器上下文查询

## 触发场景
查询当前编辑器状态、选中对象、场景信息、当前关卡/文件、视口信息。

## 使用方式
通过 MCP 工具 `run_ue_python`（UE）或 `run_python`（Maya/Max）调用以下 API。

### UE 编辑器上下文
\```python
# 选中的 Actor 列表
S = unreal.EditorLevelLibrary.get_selected_level_actors()
for a in S:
    print(f"{a.get_name()} ({a.get_class().get_name()}) at {a.get_actor_location()}")

# 当前关卡名
level = unreal.EditorLevelLibrary.get_editor_world().get_name()

# 总 Actor 数
all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
print(f"Total actors: {len(all_actors)}")
\```

### Maya 编辑器上下文
\```python
import maya.cmds as cmds
# 选中对象
sel = cmds.ls(selection=True, long=True)
# 当前场景文件
scene_file = cmds.file(query=True, sceneName=True)
# 场景对象总数
all_objects = cmds.ls(dag=True, long=True)
\```

### Max 编辑器上下文
\```python
import pymxs
rt = pymxs.runtime
# 选中对象
sel = list(rt.selection)
# 当前场景文件
scene_file = rt.maxFilePath + rt.maxFileName
\```
```

### 4.4 ArtClaw 市集分发 OpenClaw Skill

`artclaw skill install` 命令需要增加新行为：

```
artclaw skill install <skill-name>
  ├── 1. 下载/复制 Skill 包
  ├── 2. 将 SKILL.md → ~/.openclaw/skills/<skill-name>/SKILL.md
  ├── 3. 将 Python 库文件 → DCC 的 Python 路径（如果有）
  └── 4. 注册到 OpenClaw 的 skill 列表
```

**install.bat** 也需要更新：在部署 DCC 插件的同时，将 OpenClaw Skill 文件复制到 `~/.openclaw/skills/`。

---

## 5. ArtClaw Skill 运行时重构

### 5.1 核心变化：不再注册为 MCP 工具

**现在 (skill_hub.py / skill_runtime.py)**:
```python
# _register_skill_to_mcp → 每个 skill 都注册为 MCP 工具
self._mcp_server.register_tool(
    name=skill_name,
    description=info["description"],
    input_schema=info["input_schema"],
    handler=info["handler"],
)
```

**重构后**:
```python
# Skill 仍然加载为 Python 模块，但不注册 MCP 工具
# handler 函数作为可调用的 Python API 保留
# AI 通过 run_python 调用: skill_hub.execute_skill("batch_rename", {...})
```

### 5.2 SkillHub 保留的能力

| 能力 | 保留? | 说明 |
|------|-------|------|
| 分层加载 (00/01/02/99) | ✅ | 层级和优先级不变 |
| manifest.json 解析 | ✅ | 元数据管理不变 |
| Python 模块加载 + 热重载 | ✅ | 保留，skill 的 Python 函数仍需可调用 |
| MCP 工具注册 | ❌ **移除** | 不再把 skill 注册为 MCP 工具 |
| MCP tools/list 通知 | ❌ **移除** | 无需通知 MCP 客户端刷新 |
| `execute_skill(name, params)` API | ✅ **新增** | 统一执行入口，供 `run_python` 调用 |
| Skill 目录扫描 | ✅ | 保留，支持 hot reload |

### 5.3 新增 `execute_skill` 统一入口

```python
class SkillHub:
    def execute_skill(self, skill_name: str, params: dict) -> dict:
        """
        统一 Skill 执行入口，供 run_python 调用。
        
        用法 (AI 通过 run_python 执行):
            from skill_hub import get_skill_hub
            hub = get_skill_hub()
            result = hub.execute_skill("batch_rename_actors", {"prefix": "SM_"})
        """
        if skill_name not in self._registered_skills:
            return {"success": False, "error": f"Skill 未找到: {skill_name}"}
        
        info = self._registered_skills[skill_name]
        handler = info.get("handler")
        try:
            result = handler(params)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def list_skills(self, category=None, software=None) -> list:
        """列出可用 Skill，供 artclaw-skill-manage Skill 查询"""
        ...
```

### 5.4 对 ArtClaw 宪法文档的影响

需要更新的宪法文档：

| 文档 | 更新内容 |
|------|---------|
| `docs/specs/系统架构设计.md` §五 | Skill 不再注册为 MCP 工具，改为 Python 库 API |
| `docs/specs/系统架构设计.md` §六.6.4 | memory MCP 工具接口说明改为 Python API |
| `docs/specs/skill-management-system.md` §9 | MCP 接口扩展章节重写 |
| `docs/specs/skill-management-system.md` §8 | UE 编辑器内集成改为 OpenClaw Skill 触发 |
| `docs/specs/openClaw集成方案.md` §6.1 | Tools 清单缩减为 run_python 系列 |
| `docs/specs/记忆管理系统设计.md` §七 | MCP 工具接口改为 Python API + OpenClaw Skill |
| `docs/specs/项目目录结构说明.md` | 新增 `~/.openclaw/skills/` 目录说明 |

---

## 6. `run_python` / `run_ue_python` 增强

作为唯一 MCP 工具，`run_python` 需要增强其 description，让 AI 知道它能调用哪些内部 API：

### 6.1 Description 增强

```
"在 DCC 软件中执行 Python 代码。
上下文变量: S=选中对象列表, W=当前场景文件, L=DCC命令模块。
所有写操作都有 Undo 支持。

可用的内部 API（import 后直接调用）:
- knowledge_base.get_knowledge_base().search(query, top_k) - 搜索知识库
- memory_store / memory_core - 记忆读写
- skill_hub.get_skill_hub().execute_skill(name, params) - 执行已注册 Skill
- skill_hub.get_skill_hub().list_skills() - 列出可用 Skill"
```

> **注意**：description 增长会增加这一个工具的 token 开销（~50-100 tokens），但远小于之前 8 个工具的总开销。

### 6.2 UE 侧 `inject_context` 增强

UE 的 `run_ue_python` 已有 `inject_context=true` 参数，可以自动注入上下文变量。考虑增强返回信息：

```python
# inject_context=true 时自动注入:
# S = 选中 Actor 列表（前 20 个的名称和类型）
# W = 当前关卡路径
# L = unreal（命令模块）
# SCENE_STATS = {"total_actors": N, "static_meshes": M, ...}
```

这样 AI 不需要额外调用 `get_editor_context`，执行 `run_ue_python` 时就能拿到环境信息。

---

## 7. 实施步骤

### Phase 1: 创建 OpenClaw Skill（零风险，可并行验证）

1. 在 `~/.openclaw/skills/` 下创建 5 个 Skill 目录
2. 编写 SKILL.md，覆盖各 DCC 的 API 调用方式
3. 验证 OpenClaw Agent 能正确匹配和加载

### Phase 2: 增强 `run_python` / `run_ue_python`

1. 更新 description，列出可用内部 API
2. UE 侧增强 `inject_context` 返回信息
3. 新增 `SkillHub.execute_skill()` 和 `list_skills()` 入口
4. 确保 `knowledge_base.get_knowledge_base()` 在 `run_python` 上下文中可调用

### Phase 3: 移除 MCP 工具注册

1. **UE 侧**:
   - `context_provider.py`: `register_tools()` 不再注册 `get_editor_context` 和 `highlight_actors`（函数保留）
   - `memory_store.py`: `init_memory_store()` 不再注册 `memory` MCP 工具（Python API 保留）
   - `knowledge_base.py`: `init_knowledge_base()` 不再注册 `knowledge_search` MCP 工具（Python API 保留）
   - `skill_mcp_tools.py`: `register_skill_tools()` 不再注册任何工具（Python API 保留）
   - `skill_hub.py`: `_register_skill_to_mcp()` 改为 `_register_skill_api()`，只注册到内部字典不注册 MCP

2. **DCC 侧**:
   - `mcp_server.py`: `_init_builtin_tools()` 只注册 `run_python`，移除其他 4 个
   - `core/knowledge_base.py`: 不注册 MCP 工具
   - `core/memory_store.py`: 不注册 MCP 工具
   - `core/skill_runtime.py`: 不注册 MCP 工具，改为 `_register_skill_api()`

### Phase 4: 更新部署与文档

1. `install.bat`: 增加 OpenClaw Skill 文件复制步骤
2. `setup_openclaw_config.py`: 更新 `tools.allow` 配置（工具减少后通配符仍有效）
3. 更新所有宪法文档（见第 5.4 节）
4. 更新 MEMORY.md

### Phase 5: 回滚机制

- 所有原 handler 函数保留，只注释掉 `register_tool` 调用
- 增加环境变量 `ARTCLAW_LEGACY_MCP=true`，开启后恢复全部 MCP 注册
- 在 `mcp_server.py` 启动时检查此变量

---

## 8. 风险评估

| 风险 | 严重性 | 概率 | 缓解 |
|------|--------|------|------|
| OpenClaw Skill 描述匹配不到 → AI 不知道可用功能 | 中 | 中 | SKILL.md 描述覆盖尽可能多的触发词；`run_python` description 列出核心 API |
| AI 通过 `run_python` 调 API 比直接 MCP 工具多一步 | 低 | 高 | SKILL.md 提供现成代码片段，AI 复制即用 |
| memory briefing 注入不再有专用 MCP 工具提醒 AI 查记忆 | 中 | 低 | briefing 自动注入机制不受影响（在 bridge 层面实现，不依赖 MCP 工具） |
| SkillHub 热重载后新 Skill 对 AI 不立即可见 | 低 | 中 | AI 可通过 `run_python` 调 `list_skills()` 查看最新列表 |
| `run_python` description 过长导致上下文反而增加 | 低 | 低 | 控制在 ~200 tokens 以内，远低于之前 8 个工具总量 |

---

## 9. ArtClaw Skill 创建流程（重构后）

### 用户创建 Skill

```
用户: "创建一个批量重命名的 artclaw 技能"
    │
    ▼
OpenClaw 匹配到 artclaw-skill-manage Skill → 读 SKILL.md
    │
    ▼
AI 通过 run_python 调用:
  from skill_hub import get_skill_hub
  hub = get_skill_hub()
  # 1. 生成 Skill 代码和 manifest
  # 2. 保存到 Skills/02_user/batch_rename/
  # 3. 热加载注册
    │
    ▼
同时生成 OpenClaw SKILL.md → 保存到 ~/.openclaw/skills/batch-rename/
    │
    ▼
用户立即可用（下次匹配到时自动加载 SKILL.md）
```

### 分享到市集

```
artclaw skill publish batch_rename --target team
  ├── 1. 打包 Skill Python 代码 + manifest + SKILL.md
  ├── 2. 推送到 artclaw/team_skills/
  └── 3. 其他人 artclaw skill install batch_rename 时自动部署到双端
```

---

## 10. 预期收益

| 指标 | 现在 | 重构后 |
|------|------|--------|
| UE MCP 工具数 | 8 + N (Skill) | **1** |
| DCC MCP 工具数 | 6 + N (Skill) | **1** |
| 三 DCC 同时连接工具数 | 24+ | **3** |
| 每轮 tool tokens | ~5,000-8,000 | **~600** |
| AI 工具选择准确率 | 低（工具多且名称相似） | 高（每个 DCC 只有 1 个选择） |
| 新 Skill 上下文成本 | 每个 Skill = 1 个 MCP 工具定义 (~200 tokens) | 0（不注册 MCP） |
| 代码改动量 | — | 中等（注释掉注册 + 新增 execute_skill API） |

---

## 11. 决策确认

| # | 决策 | 状态 |
|---|------|------|
| 1 | 每个 DCC 只保留 1 个 MCP 工具 (`run_python`) | ✅ Ivan 确认 |
| 2 | `knowledge_search` 包进 `run_python` | ✅ Ivan 确认 |
| 3 | Skill 注册在 OpenClaw | ✅ Ivan 确认 |
| 4 | `get_editor_context` 不保留为独立 MCP 工具 | 待确认 |
| 5 | ArtClaw 从 Skill 运行时转为 Skill 市集 | ✅ Ivan 确认方向 |
| 6 | 一步到位执行 | ✅ Ivan 确认 |
