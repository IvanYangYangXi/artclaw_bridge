---
name: comfyui-workflow-validator
description: >
  验证 ComfyUI Workflow 的节点是否可用。
  在提交 workflow 前检查所有节点类型是否存在。
  Use when AI needs to: (1) validate workflow before submission,
  (2) check if nodes are available, (3) debug workflow issues.
  ComfyUI only (run_python).
metadata:
  artclaw:
    version: 0.1.0
    author: ArtClaw
    dcc: comfyui
    priority: 95
---

# ComfyUI Workflow 验证器

> 在提交 workflow 前验证所有节点是否可用。

---

## 快速使用

```python
from comfyui_workflow_validator import validate_workflow

# 验证 workflow 文件
result = validate_workflow("/path/to/workflow.json")
if result["valid"]:
    print("✓ 所有节点都可用")
else:
    print(f"✗ 有 {len(result['missing_nodes'])} 个节点不可用")
    for node in result["missing_nodes"]:
        print(f"  - {node}")
```

---

## 完整示例

```python
# 1. 加载 workflow
import json
with open("my_workflow.json", "r") as f:
    workflow = json.load(f)

# 2. 验证
from comfyui_workflow_validator import validate_workflow_dict
result = validate_workflow_dict(workflow)

# 3. 处理结果
if result["valid"]:
    print("✓ Workflow 验证通过，可以提交")
    # 提交 workflow
    client.submit_and_wait(workflow)
else:
    print("✗ Workflow 验证失败")
    print("\n缺失的节点:")
    for node in result["missing_nodes"]:
        print(f"  - {node}")
    print("\n建议:")
    print("  1. 安装缺失的节点包")
    print("  2. 或替换为等效的可用节点")
```

---

## API 参考

### `validate_workflow(file_path: str) -> dict`

验证 workflow 文件。

**参数:**
- `file_path`: workflow JSON 文件路径

**返回:**
```python
{
    "valid": bool,           # 是否全部可用
    "nodes": list,           # 所有节点类型
    "available_nodes": list, # 可用节点
    "missing_nodes": list    # 缺失节点
}
```

### `validate_workflow_dict(workflow: dict) -> dict`

验证 workflow 字典。

### `get_available_nodes() -> list`

获取 ComfyUI 所有可用节点列表。

---

## 预注入变量

`run_python` 已注入：`client`

---

*Skill 版本: 0.1.0*
