---
name: houdini-operation-rules
description: >
  Houdini 操作通用规则和最佳实践。所有涉及 Houdini 场景修改的操作都必须遵守。
  AI 在执行任何 Houdini 场景操作任务前应先读取此 Skill。
  包含：坐标系、Undo 包装、节点操作基础、Cook 机制、上下文规则等强制规则。
  Use when AI needs to: (1) perform any Houdini scene modification,
  (2) check post-operation best practices,
  (3) understand Houdini coordinate system,
  (4) learn node-based workflow fundamentals.
  Houdini only (run_python).
metadata:
  artclaw:
    author: ArtClaw
    software: houdini
---

# Houdini 操作通用规则

所有涉及 Houdini 场景修改的操作都必须遵守以下规则。

> ⚠️ **仅适用于 Houdini** — 通过 `run_python` 执行，使用 `hou` 模块

---

## 🌐 规则 0：坐标系

Houdini 使用 **Y-Up 右手坐标系**（与 Maya 一致）：

| 轴 | 方向 | 说明 |
|---|---|---|
| **X** | 右 (Right) | 屏幕右侧 |
| **Y** | 上 (Up) | 垂直向上 |
| **Z** | 前/外 (Forward) | 朝向屏幕外（面向你） |

**右手系判定**：右手拇指指向 X（右），食指指向 Y（上），中指指向 Z（屏幕外）。

**与其他 DCC 的换算**：
- **与 Maya**：坐标轴方向一致，无需转换
- **到 UE (Z-Up 左手系)**：Houdini Y → UE Z，Houdini Z → UE -Y
- **到 3ds Max (Z-Up 右手系)**：Houdini Y → Max Z，Houdini Z → Max -Y

```python
import hou

# Houdini 坐标示例
node = hou.node("/obj/geo1")
node.parm("tx").set(100)  # X = 右 100
node.parm("ty").set(50)   # Y = 上 50
node.parm("tz").set(0)    # Z = 前 0
```

---

## 🔄 规则 1：Undo 包装（强制）

**所有修改操作必须包裹在 undo group 中**，确保用户可以一次 Ctrl+Z 撤销整个操作。

```python
import hou

with hou.undos.group("ArtClaw: 操作描述"):
    # ... 所有修改操作放在这里 ...
    geo = hou.node("/obj").createNode("geo", "my_geo")
    box = geo.createNode("box", "my_box")
```

> ⚠️ **禁止**在 undo group 外直接执行场景修改操作。

---

## 🔗 规则 2：节点操作基础

Houdini 以**节点网络**为核心，几乎所有操作都是创建/连接/设置节点参数。

### 获取节点

```python
node = hou.node("/obj/geo1")          # 通过完整路径获取
children = node.children()             # 获取子节点列表
child = node.node("box1")             # 获取相对路径子节点
```

### 创建节点

```python
parent = hou.node("/obj/geo1")
box = parent.createNode("box", "my_box")       # (节点类型, 节点名称)
xform = parent.createNode("xform", "move_up")  # 创建 Transform 节点
```

### 连接节点

```python
# xform 的第 0 个输入 ← box 的第 0 个输出
xform.setInput(0, box, 0)

# 多输入节点（如 merge）
merge = parent.createNode("merge")
merge.setInput(0, box, 0)
merge.setInput(1, sphere, 0)
```

### 设置参数

```python
box.parm("sizex").set(2.0)            # 标量参数
box.parm("scale").set(1.5)
xform.parmTuple("t").set((0, 5, 0))   # 向量参数（translate）
```

### 布局节点

```python
parent.layoutChildren()               # 自动排列所有子节点
```

### 设置显示/渲染标记

```python
node.setDisplayFlag(True)             # 蓝色显示标记
node.setRenderFlag(True)              # 紫色渲染标记
```

---

## 🍳 规则 3：Cook 机制

- Houdini 的节点修改后需要 **cook** 才能计算出结果
- **大部分参数修改会自动触发 cook**，无需手动干预
- 需要强制 cook 时：`node.cook(force=True)`

### 批量修改优化

批量修改大量节点/参数时，可暂时禁用自动更新以提升性能：

```python
import hou

# 切换到手动更新模式
hou.setUpdateMode(hou.updateMode.Manual)

with hou.undos.group("ArtClaw: 批量操作"):
    # ... 大量节点创建/修改 ...
    for i in range(100):
        node = parent.createNode("box", f"box_{i}")
        node.parm("sizex").set(i * 0.1)

# 恢复自动更新
hou.setUpdateMode(hou.updateMode.AutoUpdate)
```

> ⚠️ **务必恢复** `AutoUpdate` 模式，否则用户界面不会刷新。

---

## 📢 规则 4：输出方式

| 方式 | 用途 | 说明 |
|---|---|---|
| `print(...)` | 脚本输出 | 输出到 Python Shell，**推荐用于 ArtClaw** |
| `hou.ui.displayMessage(...)` | 用户提示 | 弹窗显示，需要用户点击确认 |

```python
# ✅ 推荐：print 输出
print(f"创建了 {len(nodes)} 个节点")

# ⚠️ 仅在需要用户确认时使用
# hou.ui.displayMessage("操作完成！")
```

---

## 📂 规则 5：节点上下文

Houdini 的节点按**上下文**组织在不同层级：

| 路径 | 上下文 | 放置内容 |
|---|---|---|
| `/obj` | Object | geo, cam, light 等对象级节点 |
| `/obj/geo1` | SOP | 几何体操作节点（box, transform, merge 等） |
| `/out` | ROP | 渲染输出节点（mantra, karma, filecache 等） |
| `/shop` | SHOP | 旧版材质着色器 |
| `/mat` | MAT | 新版材质网络（推荐） |
| `/stage` | LOP | USD/Solaris 阶段 |

```python
# 正确：在 geo 节点内创建 SOP 节点
geo = hou.node("/obj/geo1")
box = geo.createNode("box")

# 错误：不要在 /obj 下直接创建 SOP 节点
# hou.node("/obj").createNode("box")  # ❌ 会报错
```

> ⚠️ 创建节点前，确认你在正确的上下文层级中操作。

---

## 🧠 规则 6：记忆系统集成

与其他 DCC 保持一致的记忆使用策略：

- **操作前**：如果类似操作之前失败过，先搜索记忆查找教训
- **操作失败**：记录错误原因和解决方案到记忆系统
- **操作成功**：如果是复杂或首次操作，记录成功方案供后续复用

```python
# 使用 artclaw-memory skill 进行记忆读写
# 搜索: memory_store.get_memory_store().search("houdini pyro setup")
# 存储: memory_store.get_memory_store().store(key, value, category)
```

---

## ✅ 标准操作收尾模板

所有 Houdini 操作脚本应遵循以下结构：

```python
import hou

with hou.undos.group("ArtClaw: 操作名称"):
    # ① 获取目标节点
    geo = hou.node("/obj/geo1")
    if not geo:
        raise Exception("未找到 /obj/geo1 节点")

    # ② 执行操作
    box = geo.createNode("box", "my_box")
    box.parm("sizex").set(2.0)

    # ③ 设置显示标记（如果需要）
    box.setDisplayFlag(True)
    box.setRenderFlag(True)

    # ④ 布局节点
    geo.layoutChildren()

# ⑤ 输出结果
print("操作完成: 创建了 box 节点")
```

---

## ⚠️ 常见陷阱

1. **节点名称冲突**：同一层级下节点名不能重复，`createNode` 会自动添加数字后缀（如 `box1`, `box2`）
2. **路径大小写**：Houdini 节点名称区分大小写
3. **参数不存在**：设置参数前用 `node.parm("name")` 检查是否返回 `None`
4. **HDA 锁定**：HDA（Houdini Digital Asset）内部节点默认锁定，需要先 `node.allowEditingOfContents()` 才能修改
5. **删除节点**：使用 `node.destroy()` 而非 `delete`
6. **空选择**：操作前检查 `hou.selectedNodes()` 是否为空
