---
name: sp-layer-ops
description: >
  SP 层操作指南：创建、删除、移动、复制层，设置混合模式和透明度。
  Use when AI needs to: (1) add/delete layers, (2) move/duplicate layers,
  (3) set blend mode/opacity, (4) manage masks.
  Substance Painter only (run_python).
metadata:
  artclaw:
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

    # 在层栈顶部插入一个填充层
    new_layer = substance_painter.layerstack.insert_fill_layer(
        stack,
        substance_painter.layerstack.InsertPosition.above_node(
            substance_painter.layerstack.get_root_layer_nodes(stack)[-1]
        )
    )
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

    new_layer = substance_painter.layerstack.insert_paint_layer(
        stack,
        substance_painter.layerstack.InsertPosition.above_node(
            substance_painter.layerstack.get_root_layer_nodes(stack)[-1]
        )
    )
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

    new_group = substance_painter.layerstack.insert_group_layer(
        stack,
        substance_painter.layerstack.InsertPosition.above_node(
            substance_painter.layerstack.get_root_layer_nodes(stack)[-1]
        )
    )
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

    # 按名称查找并删除
    target_name = "要删除的层名"
    for layer in root_layers:
        if layer.get_name() == target_name:
            layer.delete()
            print(f"✅ 已删除层: {target_name}")
            break
    else:
        print(f"❌ 未找到层: {target_name}")
```

---

## 移动层顺序

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

    if len(root_layers) >= 2:
        # 将第一个层移到最后一个层的上面
        source = root_layers[0]
        target = root_layers[-1]
        source.move(
            substance_painter.layerstack.InsertPosition.above_node(target)
        )
        print(f"✅ 已将 '{source.get_name()}' 移到 '{target.get_name()}' 上方")
```

---

## 复制层

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
        # 复制最顶层
        original = root_layers[-1]
        duplicated = original.duplicate()
        print(f"✅ 已复制层: {original.get_name()} → {duplicated.get_name()}")
```

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

        # 设置透明度 (0.0 ~ 1.0)
        layer.set_opacity(0.75)
        print(f"✅ 透明度设为 75%")

        # 设置混合模式
        # 常用混合模式: Normal, Multiply, Screen, Overlay, Add, Subtract
        layer.set_blending_mode(substance_painter.layerstack.BlendingMode.Multiply)
        print(f"✅ 混合模式设为 Multiply")
```

### 常用混合模式

| 混合模式 | 枚举值 | 说明 |
|---|---|---|
| Normal | `BlendingMode.Normal` | 默认 |
| Multiply | `BlendingMode.Multiply` | 正片叠底 |
| Screen | `BlendingMode.Screen` | 滤色 |
| Overlay | `BlendingMode.Overlay` | 叠加 |
| Add | `BlendingMode.Add` | 线性减淡 |
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
- 批量操作时，先获取所有层的引用再执行修改，避免迭代中修改集合
- 层名可重复，按名称查找时注意可能匹配多个
