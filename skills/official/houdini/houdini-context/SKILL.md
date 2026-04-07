---
name: houdini-context
description: >
  查询 Houdini 编辑器上下文：选中节点、场景信息、节点网络结构。
  Use when AI needs to: (1) get selected nodes, (2) get scene overview,
  (3) check current hip file, (4) inspect node networks.
  Houdini only (run_python).
metadata:
  artclaw:
    author: ArtClaw
    software: houdini
---

# Houdini 编辑器上下文查询

获取当前 Houdini 编辑器状态、选中节点、场景信息、节点网络结构等。

> ⚠️ **仅适用于 Houdini** — 通过 `run_python` 执行，使用 `hou` 模块

---

## 调用方式

通过 MCP 工具 `run_python` 执行 Python 代码来获取 Houdini 编辑器上下文。

---

## 1. 获取选中节点

```python
import hou

selected = hou.selectedNodes()
if selected:
    for node in selected:
        print(f"名称: {node.name()}")
        print(f"  路径: {node.path()}")
        print(f"  类型: {node.type().name()}")
        print(f"  分类: {node.type().category().name()}")
        print("---")
else:
    print("没有选中任何节点")
```

---

## 2. 获取场景信息

```python
import hou

# Hip 文件路径
hip_path = hou.hipFile.path()
hip_name = hou.hipFile.basename()
print(f"文件路径: {hip_path}")
print(f"文件名: {hip_name}")

# 是否有未保存的修改
has_changes = hou.hipFile.hasUnsavedChanges()
print(f"有未保存修改: {has_changes}")

# 帧率
fps = hou.fps()
print(f"帧率: {fps} FPS")

# 帧范围
start = hou.playbar.playbackRange()[0]
end = hou.playbar.playbackRange()[1]
current = hou.frame()
print(f"帧范围: {start} - {end}")
print(f"当前帧: {current}")

# Houdini 版本
version = hou.applicationVersionString()
print(f"Houdini 版本: {version}")
```

---

## 3. 获取 /obj 下的节点树结构

```python
import hou

def print_node_tree(node, indent=0):
    """递归打印节点树"""
    prefix = "  " * indent
    type_name = node.type().name()
    flags = []
    # SOP 节点才有 display/render flag
    if hasattr(node, 'isDisplayFlagSet') and node.isDisplayFlagSet():
        flags.append("D")
    if hasattr(node, 'isRenderFlagSet') and node.isRenderFlagSet():
        flags.append("R")
    flag_str = f" [{','.join(flags)}]" if flags else ""
    print(f"{prefix}{node.name()} ({type_name}){flag_str}")
    for child in node.children():
        print_node_tree(child, indent + 1)

obj = hou.node("/obj")
if obj:
    print("=== /obj 节点树 ===")
    for child in obj.children():
        print_node_tree(child)
else:
    print("未找到 /obj 节点")
```

---

## 4. 获取节点参数列表

```python
import hou

node = hou.node("/obj/geo1/box1")  # 替换为目标节点路径
if node:
    print(f"节点: {node.path()} ({node.type().name()})")
    print("--- 参数列表 ---")
    for parm in node.parms():
        try:
            val = parm.eval()
        except:
            val = "<无法求值>"
        print(f"  {parm.name()} = {val}")
else:
    print("未找到目标节点")
```

### 获取参数模板（含类型和范围信息）

```python
import hou

node = hou.node("/obj/geo1/box1")
if node:
    for pt in node.parmTemplateGroup().entries():
        if isinstance(pt, hou.FolderParmTemplate):
            print(f"[文件夹] {pt.label()}")
            for sub in pt.parmTemplates():
                print(f"  {sub.name()} ({sub.type().name()}) - {sub.label()}")
        else:
            print(f"{pt.name()} ({pt.type().name()}) - {pt.label()}")
```

---

## 5. 获取节点连接关系

```python
import hou

node = hou.node("/obj/geo1")  # 替换为目标父节点
if node:
    print(f"=== {node.path()} 节点连接关系 ===")
    for child in node.children():
        # 输入连接
        inputs = child.inputs()
        if inputs:
            for i, inp in enumerate(inputs):
                if inp is not None:
                    print(f"  {inp.name()} → [{i}] {child.name()}")

        # 如果没有输入，标记为源节点
        if not any(inputs):
            print(f"  [源] {child.name()}")
```

### 获取完整连接图

```python
import hou

def describe_network(parent_path):
    """描述一个节点网络的完整连接图"""
    parent = hou.node(parent_path)
    if not parent:
        print(f"未找到节点: {parent_path}")
        return

    print(f"=== 网络: {parent_path} ===")
    print(f"子节点数量: {len(parent.children())}")
    print()

    for child in parent.children():
        type_name = child.type().name()
        flags = []
        try:
            if child.isDisplayFlagSet():
                flags.append("Display")
            if child.isRenderFlagSet():
                flags.append("Render")
            if child.isBypassed():
                flags.append("Bypass")
        except:
            pass

        flag_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"● {child.name()} ({type_name}){flag_str}")

        # 输入
        for i, inp in enumerate(child.inputs()):
            if inp is not None:
                print(f"  ← 输入[{i}]: {inp.name()}")

        # 输出
        for output in child.outputs():
            print(f"  → 输出到: {output.name()}")

        print()

describe_network("/obj/geo1")
```

---

## 6. 获取当前网络编辑器状态

```python
import hou

# 获取当前网络编辑器中正在查看的路径
desktop = hou.ui.curDesktop()
pane_tabs = desktop.paneTabs()
for tab in pane_tabs:
    if tab.type() == hou.paneTabType.NetworkEditor:
        pwd = tab.pwd()
        print(f"网络编辑器当前路径: {pwd.path()}")
        break
```

---

## 7. 综合场景概览

```python
import hou

print("========== Houdini 场景概览 ==========")
print(f"文件: {hou.hipFile.basename()}")
print(f"路径: {hou.hipFile.path()}")
print(f"版本: {hou.applicationVersionString()}")
print(f"帧率: {hou.fps()} FPS")
print(f"帧范围: {hou.playbar.playbackRange()}")
print(f"当前帧: {hou.frame()}")
print()

# 统计各上下文节点数
contexts = {
    "/obj": "Object 节点",
    "/out": "ROP 渲染节点",
    "/shop": "SHOP 材质",
    "/mat": "MAT 材质",
    "/stage": "LOP/USD 节点",
}
for path, label in contexts.items():
    node = hou.node(path)
    if node:
        count = len(node.children())
        print(f"  {label} ({path}): {count} 个")

print()

# 选中节点
selected = hou.selectedNodes()
print(f"选中节点: {len(selected)} 个")
for s in selected:
    print(f"  - {s.path()} ({s.type().name()})")

print("======================================")
```
