# ArtClaw 知识库搜索

搜索 UE/Maya/Max API 文档、代码示例、命名规范等技术知识库，在写代码前先查正确用法。

> **覆盖原 MCP 工具**: `knowledge_search`

## 调用方式

通过 MCP 工具 `run_ue_python`（UE）或 `run_python`（Maya/Max）执行 Python 代码搜索知识库。

---

## Python API

### UE 环境

```python
from knowledge_base import get_knowledge_base

kb = get_knowledge_base()
results = kb.search("如何创建动态材质实例", top_k=5)

for r in results:
    print(f"[{r['score']:.2f}] {r['title']}")
    print(f"  来源: {r['source']}")
    print(f"  内容: {r['text'][:200]}")
    print()
```

### DCC 环境 (Maya/Max)

```python
from core.knowledge_base import get_knowledge_base

kb = get_knowledge_base()
results = kb.search("如何批量设置关键帧", top_k=5)

for r in results:
    print(f"[{r['score']:.2f}] {r['title']}")
    print(f"  来源: {r['source']}")
    print(f"  内容: {r['text'][:200]}")
    print()
```

---

## 返回值格式

`kb.search()` 返回 `list[dict]`，每个 dict 包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | str | 文档标题 |
| `text` | str | 匹配的文档内容片段 |
| `source` | str | 来源（如 UE 官方文档、项目 Wiki 等） |
| `score` | float | 相关度评分（0.0 ~ 1.0，越高越相关） |

---

## 典型使用场景

### 查询 UE API 用法

```python
from knowledge_base import get_knowledge_base
kb = get_knowledge_base()

# 查 Niagara 粒子系统 API
results = kb.search("Niagara particle system spawn emitter", top_k=3)
```

### 查询 Maya API 用法

```python
from core.knowledge_base import get_knowledge_base
kb = get_knowledge_base()

# 查 Maya skinCluster 权重操作
results = kb.search("skinCluster set weights Python API", top_k=3)
```

### 查询命名规范

```python
kb = get_knowledge_base()
results = kb.search("资产命名规范 naming convention", top_k=5)
```

### 查询代码示例

```python
kb = get_knowledge_base()
results = kb.search("批量导入 FBX 示例代码", top_k=3)
```

---

## 使用建议

- **写复杂代码前先搜索**: 在编写 UE/Maya Python 代码前，先用知识库确认正确的 API 用法，避免用错参数或调用已废弃的接口
- **混合语言搜索**: 可以用中文描述需求 + 英文 API 关键词组合搜索，效果更好
- **调整 top_k**: 简单查询用 `top_k=3`，复杂或模糊查询用 `top_k=5~10`
- **检查 score**: 低于 0.3 的结果相关性较低，可能需要换个关键词重新搜索
