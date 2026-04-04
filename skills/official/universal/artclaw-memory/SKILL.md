---
name: artclaw-memory
description: >
  Manage ArtClaw's memory system: store/get/search/list/delete user preferences, operation
  history, project conventions, and user habits. Use when AI needs to: (1) remember user
  preferences or conventions, (2) check operation history (what was done before), (3) store
  lessons learned from errors, (4) maintain and compact memory tiers. Replaces old MCP tool:
  memory (7 actions: store/get/search/list/delete/check_operation/maintain).
---

# ArtClaw 记忆管理

记住用户偏好、操作历史、项目规范、踩坑经验，管理和维护 ArtClaw 的记忆系统。

---

## 何时读取记忆 (必须遵守)

### 1. 对话开始时 — 自动注入 (已实现，无需手动)
Memory Briefing 在 bridge 层自动注入到首条消息，包含团队记忆和个人记忆。

### 2. 反复出错时 — 主动搜索 (强制)
当同一类操作**连续失败 2 次以上**时，必须主动搜索记忆寻找解决方案：

```python
from core.memory_store import get_memory_store
mm = get_memory_store()
if mm:
    # 搜索个人记忆
    hints = mm.manager.search("关键词", tag="crash", limit=3)
    hints += mm.manager.search("关键词", tag="pattern", limit=3)
    # 搜索团队记忆
    team_hints = mm.manager.search_team_memory("关键词", limit=3)
```

### 3. 高风险操作前 — 主动检查 (建议)
执行删除、批量修改、材质替换、导入导出等操作前：

```python
check = mm.manager.check_operation(tool="工具名", action_hint="操作描述")
# 如果有 crash_rules 或 warnings，告知用户风险
```

---

## 何时写入记忆 (必须遵守)

### 核心原则: 只记"付出代价的经验"

- **一次性成功的操作不记录**
- **多次尝试才成功的经验才值得记录**

### 1. 多次尝试后成功 — 提炼规则 (强制)

当你经过 2 次以上尝试或修改才正确完成一个操作时，**必须**提炼规则并记录：

```python
mm.manager.record(
    key="pattern:简短描述",
    value="精炼的规则（一句话说清楚问题和解法）",
    tag="pattern",
    importance=0.8,
    source="retry_learned"
)
```

**规则质量要求**:
- 一句话说清楚：什么情况 + 正确做法
- 示例: "MaterialExpressionMultiply 的 A/B 输入必须显式连接，留空会报错"
- 不要记录过程细节，只记最终结论

### 2. 用户纠正后 — 提炼教训 (强制)

当用户指出错误（"不对"/"错了"/"重做"等）并经过修正后，主动提炼教训：

```python
mm.manager.record(
    key="pattern:被纠正的问题描述",
    value="正确的做法和原因",
    tag="pattern",
    importance=0.8,
    source="user_correction"
)
```

### 3. 发现反直觉行为 — 记录陷阱 (强制)

当发现 API 行为与文档/直觉不符时：

```python
mm.manager.record(
    key="pattern:API或行为描述",
    value="实际行为和正确用法",
    tag="pattern",
    importance=0.9,
    source="gotcha"
)
```

### 4. 崩溃/严重错误 — 记录规则 (强制)

```python
mm.manager.record_crash(
    tool="工具名",
    action="操作名",
    params_summary="参数摘要",
    error="错误信息",
    root_cause="根因分析（一句话）",
    avoidance_rule="避免规则（一句话）",
    severity="high"  # low/medium/high/critical
)
```

### 5. 用户明确说"记住" — 直接存储

```python
mm.manager.record(
    key="合适的key",
    value="用户要记住的内容",
    tag="preference",  # 或 convention/fact
    importance=0.7
)
```

---

## 不要记录的内容

- 纯查询操作（列出 Actor、获取属性等）
- 一次性简单操作（移动物体、改个颜色）
- 已经在团队记忆中存在的规则（避免重复）

---

## Python API 参考

### 初始化

**UE 环境:**
```python
from memory_store import get_memory_store
mm = get_memory_store()
mgr = mm.manager  # MemoryManagerV2 实例
```

**DCC 环境 (Maya/Max):**
```python
from core.memory_store import get_memory_store
mm = get_memory_store()
mgr = mm.manager  # MemoryManagerV2 实例
```

### 核心方法

| 方法 | 用途 |
|------|------|
| `mgr.record(key, value, tag, importance)` | 写入个人记忆 |
| `mgr.get(key)` | 精确读取 |
| `mgr.search(query, tag, limit)` | 搜索个人记忆 |
| `mgr.search_team_memory(query, limit)` | 搜索团队记忆 |
| `mgr.propose_team_rule(rule, category, dcc_tag)` | 提议写入团队记忆 |
| `mgr.promote_to_team(min_importance, dry_run)` | 批量提炼个人→团队 |
| `mgr.delete(key)` | 删除个人记忆 |
| `mgr.record_crash(...)` | 记录崩溃 |
| `mgr.check_operation(tool, action_hint)` | 检查操作历史 |
| `mgr.maintain(full=True)` | 触发维护 |

### Tag 枚举

| Tag | 用途 | 典型 importance |
|-----|------|----------------|
| `crash` | 崩溃/严重错误规则 | 0.8-0.9 |
| `pattern` | 反直觉行为/经验教训 | 0.7-0.9 |
| `convention` | 项目规范/命名约定 | 0.6-0.7 |
| `preference` | 用户偏好 | 0.5-0.6 |
| `fact` | 客观事实 | 0.5 |
| `context` | 临时上下文 | 0.2-0.3 |

### 三级记忆模型

| 层级 | 保留时间 | 说明 |
|------|----------|------|
| `short_term` | 4 小时 | 当前会话临时记忆 |
| `mid_term` | 7 天 | 高重要性的短期记忆自动升级 |
| `long_term` | 永久 | 重要规范、偏好、经验教训 |

记忆根据 importance 和访问频率自动在层级间流转，无需手动管理。

---

## 团队记忆 (team_memory/)

团队共享的高价值规则，存放在项目仓库 `team_memory/` 目录：

| 文件 | 内容 | 加载时机 |
|------|------|----------|
| crash_rules.md | 崩溃规则 | 每次 briefing |
| gotchas.md | 反直觉陷阱 | 每次 briefing |
| conventions.md | 项目规范 | 仅首条消息 |
| platform_differences.md | 跨平台差异 | 仅首条消息 |

团队记忆通过 `search_team_memory()` 搜索，通过 briefing 自动注入。

### 写入团队记忆

当你认为一条经验教训有**团队级价值**（其他人也会踩同样的坑）时，提议写入团队记忆：

```python
result = mgr.propose_team_rule(
    rule_text="Rotator 构造参数顺序是 Pitch,Yaw,Roll，不是 Roll,Pitch,Yaw",
    category="gotcha",   # crash/gotcha/pattern/convention/platform
    dcc_tag="[UE]"       # [UE]/[Maya]/[Max]/[All]，为空则不加标签
)
# result = {"accepted": True/False, "reason": "...", "file": "gotchas.md"}
```

- 自动去重: 与已有规则相似度 >75% 会被拒绝
- 写入后追加到 .md 文件末尾，需要用户 Git commit 才能共享给团队

### 从个人记忆批量提炼

```python
# 预览候选规则（不实际写入）
candidates = mgr.promote_to_team(min_importance=0.7, dry_run=True)
for c in candidates:
    print(f"[{c['category']}] {c['dcc_tag']} {c['rule']}")

# 实际写入
results = mgr.promote_to_team(min_importance=0.7, dry_run=False)
```
