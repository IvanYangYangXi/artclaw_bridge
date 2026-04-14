---
name: comfyui-workflow-repair
description: >
  ComfyUI Workflow 自动诊断与修复。检测缺失节点、参数错误、连接问题，
  并提供自动修复方案或手动修复指导。
  Use when AI needs to: (1) fix a broken workflow,
  (2) migrate workflow to new ComfyUI version,
  (3) optimize workflow structure.
  ComfyUI only (run_python).
metadata:
  artclaw:
    version: 0.1.0
    author: ArtClaw
    dcc: comfyui
    priority: 97
---

# ComfyUI Workflow 修复器

> 自动诊断 workflow 问题并提供修复方案。

---

## 预注入变量

`run_python` 已注入：`nodes`, `client`

---

## 核心功能

### 1. 诊断 Workflow

```python
from comfyui_workflow_repair import diagnose_workflow

wf = {...}  # 你的 workflow
report = diagnose_workflow(wf)

print(report)
# {
#   "status": "issues_found",
#   "issues": [
#     {
#       "type": "missing_node",
#       "severity": "error",
#       "node_id": "15",
#       "node_type": "OldNodeName",
#       "message": "节点类型不存在",
#       "fixable": True,
#       "suggestion": "替换为 NewNodeName"
#     },
#     {
#       "type": "invalid_connection",
#       "severity": "warning",
#       "message": "节点 3 的输入引用不存在的输出",
#       "fixable": True
#     }
#   ],
#   "can_auto_repair": True
# }
```

### 2. 自动修复

```python
from comfyui_workflow_repair import repair_workflow

fixed_wf = repair_workflow(wf, auto_fix=True)
print("修复完成")
```

### 3. 迁移旧版本 Workflow

```python
from comfyui_workflow_repair import migrate_workflow

# 从旧版本迁移
migrated = migrate_workflow(wf, from_version="0.1", to_version="0.2")
```

---

## 问题类型

| 类型 | 严重程度 | 自动修复 | 说明 |
|------|----------|----------|------|
| missing_node | error | ✅ | 节点类型不存在 |
| deprecated_node | warning | ✅ | 节点已弃用 |
| invalid_connection | error | ✅ | 无效连接 |
| missing_input | error | ❌ | 缺少必填参数 |
| type_mismatch | warning | ⚠️ | 类型不匹配 |
| orphaned_node | info | ✅ | 孤立节点 |

---

## 修复策略

### 节点重命名迁移

```python
MIGRATION_MAP = {
    "CheckpointLoader": "CheckpointLoaderSimple",
    "CLIPTextEncodeSDXL": "CLIPTextEncode",
    # ...
}
```

### 替代节点推荐

```python
ALTERNATIVES = {
    "OldSampler": {
        "replacement": "KSampler",
        "input_mapping": {
            "old_param": "new_param"
        }
    }
}
```

---

## 完整示例

### 修复加载失败的 Workflow

```python
# 1. 加载 workflow（可能来自旧版本）
wf = load_workflow_file("old_workflow.json")

# 2. 诊断
report = diagnose_workflow(wf)

if report["issues"]:
    print(f"发现 {len(report['issues'])} 个问题:")
    for issue in report["issues"]:
        icon = "🔴" if issue["severity"] == "error" else "🟡"
        print(f"{icon} [{issue['type']}] {issue['message']}")
    
    # 3. 自动修复
    if report["can_auto_repair"]:
        print("\n正在自动修复...")
        fixed = repair_workflow(wf)
        
        # 4. 验证
        verify = diagnose_workflow(fixed)
        if verify["status"] == "ok":
            print("✅ 修复成功")
            save_workflow(fixed, "fixed_workflow.json")
        else:
            print("⚠️ 仍有未修复的问题")
else:
    print("✅ Workflow 正常")
```

---

## API 参考

### `diagnose_workflow(workflow) -> dict`

全面诊断 workflow 问题。

### `repair_workflow(workflow, auto_fix=True) -> dict`

修复 workflow，返回修复后的版本。

### `migrate_workflow(workflow, from_version, to_version) -> dict`

迁移旧版本 workflow。

---

*Skill 版本: 0.1.0*
