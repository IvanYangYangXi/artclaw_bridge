---
name: sp-context
description: >
  查询 SP 项目上下文：项目信息、纹理集、层结构、通道列表。
  Use when AI needs to: (1) get project info, (2) list texture sets,
  (3) inspect layer stack, (4) check channels.
  Substance Painter only (run_python).
metadata:
  artclaw:
    author: ArtClaw
    software: substance_painter
---

# SP 项目上下文查询

获取当前 Substance Painter 项目状态、纹理集信息、层栈结构、通道列表等。

> **仅适用于 Substance Painter** — 通过 `run_python` 执行

---

## 项目信息

获取当前项目的基本信息：文件路径、保存状态等。

```python
import substance_painter.project

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    file_path = substance_painter.project.file_path()
    needs_saving = substance_painter.project.needs_saving()
    print(f"项目路径: {file_path}")
    print(f"需要保存: {'是' if needs_saving else '否'}")
```

---

## 纹理集列表与分辨率

列出所有纹理集及其分辨率。

```python
import substance_painter.project
import substance_painter.textureset

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    all_ts = substance_painter.textureset.all_texture_sets()
    print(f"纹理集总数: {len(all_ts)}")
    for ts in all_ts:
        res = ts.get_resolution()
        print(f"  {ts.name()} — 分辨率: {res.width}x{res.height}")
```

---

## 层栈遍历（递归打印层树）

递归遍历层栈，打印完整层树结构。

```python
import substance_painter.project
import substance_painter.textureset
import substance_painter.layerstack

def print_layer_tree(nodes, indent=0):
    """递归打印层树"""
    prefix = "  " * indent
    for node in nodes:
        name = node.get_name()
        opacity = node.get_opacity()
        node_type = type(node).__name__
        print(f"{prefix}├─ {name} ({node_type}, opacity={opacity:.0%})")
        # 如果是组层，递归打印子层
        if hasattr(node, 'sub_layers'):
            children = node.sub_layers()
            if children:
                print_layer_tree(children, indent + 1)

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    all_ts = substance_painter.textureset.all_texture_sets()
    for ts in all_ts:
        print(f"\n=== 纹理集: {ts.name()} ===")
        stack = substance_painter.textureset.Stack.from_name(ts.name())
        root_layers = substance_painter.layerstack.get_root_layer_nodes(stack)
        if root_layers:
            print_layer_tree(root_layers)
        else:
            print("  (空层栈)")
```

---

## 通道列表

查看纹理集中已启用的通道。

```python
import substance_painter.project
import substance_painter.textureset

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    all_ts = substance_painter.textureset.all_texture_sets()
    for ts in all_ts:
        print(f"\n=== 纹理集: {ts.name()} ===")
        stack = substance_painter.textureset.Stack.from_name(ts.name())
        channels = stack.all_channels()
        for ch in channels:
            print(f"  通道: {ch.type().name}")
```

---

## 综合查询（一次性获取全部上下文）

适合在对话开始时快速了解项目全貌。

```python
import substance_painter.project
import substance_painter.textureset
import substance_painter.layerstack

def get_full_context():
    """获取 SP 完整项目上下文"""
    if not substance_painter.project.is_open():
        print("❌ 没有打开的项目")
        return

    # 1. 项目信息
    print("=== 项目信息 ===")
    print(f"路径: {substance_painter.project.file_path()}")
    print(f"需要保存: {'是' if substance_painter.project.needs_saving() else '否'}")

    # 2. 纹理集
    all_ts = substance_painter.textureset.all_texture_sets()
    print(f"\n=== 纹理集 ({len(all_ts)}) ===")
    for ts in all_ts:
        res = ts.get_resolution()
        print(f"  {ts.name()} — {res.width}x{res.height}")

        # 3. 通道
        stack = substance_painter.textureset.Stack.from_name(ts.name())
        channels = stack.all_channels()
        ch_names = [ch.type().name for ch in channels]
        print(f"    通道: {', '.join(ch_names)}")

        # 4. 层栈概览（仅根层）
        root_layers = substance_painter.layerstack.get_root_layer_nodes(stack)
        print(f"    根层数: {len(root_layers)}")
        for layer in root_layers:
            print(f"      ├─ {layer.get_name()} ({type(layer).__name__})")

get_full_context()
```

---

## 使用建议

- 需要快速了解项目概况时，使用 **综合查询**
- 只需看层结构时，使用 **层栈遍历**
- 复杂查询可以组合多个代码片段，一次性获取所有信息
- 始终先检查 `substance_painter.project.is_open()`
