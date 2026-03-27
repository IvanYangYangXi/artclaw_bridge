# ArtClaw 记忆管理

记住用户偏好、操作历史、项目规范、用户习惯，管理和维护 ArtClaw 的记忆系统。

> **覆盖原 MCP 工具**: `memory`（store / get / search / list / delete / check_operation / maintain 共 7 个 action）

## 调用方式

通过 MCP 工具 `run_ue_python`（UE）或 `run_python`（Maya/Max）执行 Python 代码操作记忆系统。

> **注意**: Memory Briefing 是自动注入的（在 bridge 层），不需要手动触发。每次对话开始时会自动加载相关记忆上下文。

---

## Python API

### 初始化

**UE 环境:**

```python
from memory_store import get_memory_store
mm = get_memory_store()
```

**DCC 环境 (Maya/Max):**

```python
from memory_core import MemoryManagerV2
mm = MemoryManagerV2.get_instance()
```

---

## 核心方法

### 存储记忆

```python
mm.store(
    key="user_naming_convention",
    value="所有 BP 蓝图以 BP_ 开头，材质以 M_ 开头",
    tag="convention",       # 见下方 tag 枚举
    importance=0.8          # 0.0 ~ 1.0，越高越不容易被清理
)
```

### 读取记忆

```python
result = mm.get(key="user_naming_convention")
print(result)
```

### 搜索记忆（语义搜索）

```python
results = mm.search(query="命名规范", top_k=5)
for r in results:
    print(f"[{r['tag']}] {r['key']}: {r['value']}")
```

### 列出记忆条目

```python
# 按 tag 过滤
entries = mm.list_entries(tag="preference", layer="long_term")
for e in entries:
    print(f"{e['key']}: {e['value']}")
```

### 删除记忆

```python
mm.delete(key="outdated_convention")
```

### 操作前检查（防重复/冲突）

```python
# 执行操作前检查是否有相关的记忆（如之前的错误记录）
check = mm.check_operation(tool="rename_asset", action_hint="批量重命名蓝图")
if check.get("warning"):
    print(f"警告: {check['warning']}")
```

### 维护记忆（清理过期条目）

```python
mm.maintain()
```

---

## Tag 枚举

| Tag | 用途 | 示例 |
|-----|------|------|
| `fact` | 客观事实 | "项目使用 UE 5.3" |
| `preference` | 用户偏好 | "喜欢用蓝图而不是 C++" |
| `convention` | 项目规范 | "材质命名用 M_ 前缀" |
| `operation` | 操作记录 | "刚才批量重命名了 50 个资产" |
| `crash` | 崩溃/错误记录 | "使用 X 功能时 UE 崩溃" |
| `pattern` | 行为模式 | "用户经常在周一整理资产" |
| `context` | 上下文信息 | "当前在做角色动画系统" |

---

## 三级记忆模型

记忆系统采用三级自动流转模型：

| 层级 | 保留时间 | 容量上限 | 说明 |
|------|----------|----------|------|
| `short_term` | 4 小时 | 200 条 | 当前会话的临时记忆，过期自动降级或清除 |
| `mid_term` | 7 天 | 500 条 | 中期记忆，高重要性的短期记忆会升级到此层 |
| `long_term` | 永久 | 1000 条 | 长期记忆，重要的规范、偏好、关键事实 |

- 记忆根据 `importance` 和访问频率自动在层级间流转
- `mm.maintain()` 会触发清理和层级调整
- 高 importance (>0.7) 的记忆更容易被保留到 long_term

---

## 使用建议

- 用户说"记住 XXX"时 → 调用 `mm.store()` 并选择合适的 tag
- 需要回忆之前的操作时 → 用 `mm.search()` 语义搜索
- 执行高风险操作前 → 用 `mm.check_operation()` 检查是否有相关警告
- 定期调用 `mm.maintain()` 保持记忆系统健康
- 不需要手动触发 Memory Briefing，它在 bridge 层自动注入
