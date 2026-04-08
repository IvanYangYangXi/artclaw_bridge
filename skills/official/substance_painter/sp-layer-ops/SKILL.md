---
name: sp-layer-ops
description: >
  SP 层操作指南：创建、删除、移动、复制层，设置混合模式和透明度。
  Use when AI needs to: (1) add/delete layers, (2) move/duplicate layers,
  (3) set blend mode/opacity, (4) manage masks.
  Substance Painter only (run_python).
metadata:
  artclaw:
    version: 0.0.1
    author: ArtClaw
    software: substance_painter
---

# SP 层操作

Substance Painter 层管理：创建、删除、移动、复制层，设置混合模式和透明度，管理遮罩。

> ⚠️ **仅适用于 Substance Painter** — 通过 `run_python` 执行
> ⚠️ **SP 无 Undo API** — 破坏性操作前建议先保存项目（参见 sp-operation-rules）

---

## 前置：获取目标纹理集的层栈

所有层操作都需要先指定目标纹理集（Texture Set）和层栈（Stack）。

```python
import substance_painter.project
import substance_painter.textureset
import substance_painter.layerstack

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    # 获取第一个纹理集（或按名称查找）
    ts = substance_painter.textureset.all_texture_sets()[0]
    stack = substance_painter.textureset.Stack.from_name(ts.name())
    print(f"目标纹理集: {ts.name()}")
```

---

## 添加层

### 添加 Fill Layer（填充层）

```python
import substance_painter.project
import substance_painter.textureset
import substance_painter.layerstack

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    ts = substance_painter.textureset.all_texture_sets()[0]
    stack = substance_painter.textureset.Stack.from_name(ts.name())

    # 在层栈顶部插入一个填充层（只需 InsertPosition，不需要 stack 参数）
    root = substance_painter.layerstack.get_root_layer_nodes(stack)
    pos = substance_painter.layerstack.InsertPosition.above_node(root[-1]) if root else substance_painter.layerstack.InsertPosition.from_textureset_stack(stack)
    new_layer = substance_painter.layerstack.insert_fill(pos)
    new_layer.set_name("MyFillLayer")
    print(f"✅ 已添加填充层: {new_layer.get_name()}")
```

### 添加 Paint Layer（绘画层）

```python
import substance_painter.project
import substance_painter.textureset
import substance_painter.layerstack

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    ts = substance_painter.textureset.all_texture_sets()[0]
    stack = substance_painter.textureset.Stack.from_name(ts.name())

    root = substance_painter.layerstack.get_root_layer_nodes(stack)
    pos = substance_painter.layerstack.InsertPosition.above_node(root[-1]) if root else substance_painter.layerstack.InsertPosition.from_textureset_stack(stack)
    new_layer = substance_painter.layerstack.insert_paint(pos)
    new_layer.set_name("MyPaintLayer")
    print(f"✅ 已添加绘画层: {new_layer.get_name()}")
```

### 添加 Group（组层）

```python
import substance_painter.project
import substance_painter.textureset
import substance_painter.layerstack

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    ts = substance_painter.textureset.all_texture_sets()[0]
    stack = substance_painter.textureset.Stack.from_name(ts.name())

    root = substance_painter.layerstack.get_root_layer_nodes(stack)
    pos = substance_painter.layerstack.InsertPosition.above_node(root[-1]) if root else substance_painter.layerstack.InsertPosition.from_textureset_stack(stack)
    new_group = substance_painter.layerstack.insert_group(pos)
    new_group.set_name("MyGroup")
    print(f"✅ 已添加组层: {new_group.get_name()}")
```

---

## 删除层

> ⚠️ **破坏性操作** — 建议先保存项目

```python
import substance_painter.project
import substance_painter.textureset
import substance_painter.layerstack

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    # 先保存项目
    substance_painter.project.save()

    ts = substance_painter.textureset.all_texture_sets()[0]
    stack = substance_painter.textureset.Stack.from_name(ts.name())
    root_layers = substance_painter.layerstack.get_root_layer_nodes(stack)

    # 按名称查找并删除（delete_node 是模块级函数，不是实例方法）
    target_name = "要删除的层名"
    for layer in root_layers:
        if layer.get_name() == target_name:
            substance_painter.layerstack.delete_node(layer)
            print(f"✅ 已删除层: {target_name}")
            break
    else:
        print(f"❌ 未找到层: {target_name}")
```

---

## 移动层顺序

> ⚠️ **SP Python API 不支持移动层** — `layer.move()` 方法不存在。
> 如需调整层顺序，可以在 SP GUI 中手动拖拽，或通过删除+重新创建层来实现。

---

## 复制层

> ⚠️ **SP Python API 不支持复制层** — `layer.duplicate()` 方法不存在。
> 如需复制层，请在 SP GUI 中使用 Ctrl+D。

---

## 设置混合模式和透明度

```python
import substance_painter.project
import substance_painter.textureset
import substance_painter.layerstack

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    ts = substance_painter.textureset.all_texture_sets()[0]
    stack = substance_painter.textureset.Stack.from_name(ts.name())
    root_layers = substance_painter.layerstack.get_root_layer_nodes(stack)

    if root_layers:
        layer = root_layers[-1]

        # 非 mask 层操作透明度和混合模式时，必须指定 channel_type 参数
        ch = substance_painter.textureset.ChannelType.BaseColor

        # 设置透明度 (0.0 ~ 1.0)
        layer.set_opacity(0.75, ch)
        print(f"✅ 透明度设为 75%")

        # 设置混合模式
        # 常用混合模式: Normal, Multiply, Screen, Overlay, LinearDodge(=Add), Subtract
        layer.set_blending_mode(substance_painter.layerstack.BlendingMode.Multiply, ch)
        print(f"✅ 混合模式设为 Multiply")
```

### 常用混合模式

| 混合模式 | 枚举值 | 说明 |
|---|---|---|
| Normal | `BlendingMode.Normal` | 默认 |
| Multiply | `BlendingMode.Multiply` | 正片叠底 |
| Screen | `BlendingMode.Screen` | 滤色 |
| Overlay | `BlendingMode.Overlay` | 叠加 |
| Linear Dodge | `BlendingMode.LinearDodge` | 线性减淡（= Add） |
| Subtract | `BlendingMode.Subtract` | 减去 |

---

## 遮罩操作

### 添加黑色遮罩

```python
import substance_painter.project
import substance_painter.textureset
import substance_painter.layerstack

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    ts = substance_painter.textureset.all_texture_sets()[0]
    stack = substance_painter.textureset.Stack.from_name(ts.name())
    root_layers = substance_painter.layerstack.get_root_layer_nodes(stack)

    if root_layers:
        layer = root_layers[-1]

        # 添加黑色遮罩（隐藏层内容）
        layer.add_mask(substance_painter.layerstack.MaskBackground.Black)
        print(f"✅ 已为 '{layer.get_name()}' 添加黑色遮罩")
```

### 添加白色遮罩

```python
        # 添加白色遮罩（显示层内容）
        layer.add_mask(substance_painter.layerstack.MaskBackground.White)
        print(f"✅ 已为 '{layer.get_name()}' 添加白色遮罩")
```

### 移除遮罩

```python
        # 移除遮罩
        if layer.has_mask():
            layer.remove_mask()
            print(f"✅ 已移除 '{layer.get_name()}' 的遮罩")
        else:
            print(f"ℹ️ '{layer.get_name()}' 没有遮罩")
```

---

## 使用建议

- 始终先检查 `substance_painter.project.is_open()`
- 删除操作前先 `substance_painter.project.save()` 保存
- 使用 `InsertPosition.above_node()` / `InsertPosition.below_node()` 控制插入位置
- 插入层函数只需 `InsertPosition` 参数，不需要 `stack`：`insert_fill(pos)` / `insert_paint(pos)` / `insert_group(pos)`
- 删除层使用模块级函数 `substance_painter.layerstack.delete_node(layer)`，不是 `layer.delete()`
- `set_opacity()` / `set_blending_mode()` / `get_opacity()` 对非 mask 层必须传 `channel_type` 参数
- SP API 不支持 `layer.move()` 和 `layer.duplicate()`
- 批量操作时，先获取所有层的引用再执行修改，避免迭代中修改集合
- 层名可重复，按名称查找时注意可能匹配多个
