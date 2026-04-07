---
name: houdini-node-ops
description: >
  Houdini 节点创建、连接、参数设置的操作指南。
  Use when AI needs to: (1) create nodes, (2) connect nodes,
  (3) set node parameters, (4) build node networks.
  Houdini only (run_python).
metadata:
  artclaw:
    author: ArtClaw
    software: houdini
---

# Houdini 节点操作指南

节点创建、连接、参数设置和常见 SOP 工作流模板。

> ⚠️ **仅适用于 Houdini** — 通过 `run_python` 执行，使用 `hou` 模块
>
> 📌 **前置依赖**: 执行任何修改操作前，请先阅读 `houdini-operation-rules` Skill

---

## 1. 创建常用 SOP 节点

### 基本几何体

```python
import hou

with hou.undos.group("ArtClaw: 创建几何体"):
    geo = hou.node("/obj").createNode("geo", "my_geo")

    # 删除默认的 file 节点（新建 geo 会自带）
    for child in geo.children():
        child.destroy()

    # 创建基本几何体
    box = geo.createNode("box", "my_box")
    sphere = geo.createNode("sphere", "my_sphere")
    tube = geo.createNode("tube", "my_tube")
    torus = geo.createNode("torus", "my_torus")
    grid = geo.createNode("grid", "my_grid")
    circle = geo.createNode("circle", "my_circle")

    # 设置 box 为显示节点
    box.setDisplayFlag(True)
    box.setRenderFlag(True)

    geo.layoutChildren()

print("创建几何体完成")
```

### Transform 节点

```python
import hou

with hou.undos.group("ArtClaw: 创建 Transform"):
    geo = hou.node("/obj/geo1")
    box = geo.node("box1")

    xform = geo.createNode("xform", "move_up")
    xform.setInput(0, box)

    # 设置变换参数
    xform.parmTuple("t").set((0, 5, 0))    # 平移 Y=5
    xform.parmTuple("r").set((0, 45, 0))   # 旋转 Y=45°
    xform.parmTuple("s").set((2, 2, 2))    # 缩放 2x

    xform.setDisplayFlag(True)
    xform.setRenderFlag(True)
    geo.layoutChildren()

print("Transform 创建完成")
```

### Merge 合并节点

```python
import hou

with hou.undos.group("ArtClaw: 合并节点"):
    geo = hou.node("/obj/geo1")

    box = geo.createNode("box", "box1")
    sphere = geo.createNode("sphere", "sphere1")
    sphere.parmTuple("t").set((3, 0, 0))

    merge = geo.createNode("merge", "merge_all")
    merge.setInput(0, box)
    merge.setInput(1, sphere)

    merge.setDisplayFlag(True)
    merge.setRenderFlag(True)
    geo.layoutChildren()

print("Merge 完成")
```

### Group 节点

```python
import hou

with hou.undos.group("ArtClaw: 创建 Group"):
    geo = hou.node("/obj/geo1")
    box = geo.node("box1")

    # 按表达式分组
    group = geo.createNode("groupcreate", "top_faces")
    group.setInput(0, box)
    group.parm("groupname").set("top_group")
    group.parm("grouptype").set(0)          # 0=Points, 1=Prims, 2=Edges
    group.parm("grouptype").set(1)          # Primitives
    group.parm("groupbounding").set(1)      # 启用包围盒过滤
    group.parm("boundtype").set(0)          # Bounding Box
    group.parmTuple("size").set((10, 0.1, 10))
    group.parmTuple("t").set((0, 0.5, 0))   # 只选择顶部

    group.setDisplayFlag(True)
    group.setRenderFlag(True)
    geo.layoutChildren()

print("Group 创建完成")
```

---

## 2. 连接节点 (setInput)

### 基本连接

```python
import hou

# 单输入连接
# node_b 的输入 0 ← node_a 的输出 0
node_b.setInput(0, node_a, 0)

# 多输入连接（如 merge, switch）
merge.setInput(0, node_a, 0)   # 第 1 个输入
merge.setInput(1, node_b, 0)   # 第 2 个输入
merge.setInput(2, node_c, 0)   # 第 3 个输入

# 断开连接
node_b.setInput(0, None)

# 插入节点（在 A 和 B 之间插入 C）
# 假设 B 的输入 0 连着 A
node_c.setInput(0, node_a, 0)
node_b.setInput(0, node_c, 0)
```

### 多输出节点

```python
import hou

# 某些节点有多个输出（如 split, foreach）
# 使用不同的 output_index
node_b.setInput(0, split_node, 0)  # split 的第 1 个输出
node_c.setInput(0, split_node, 1)  # split 的第 2 个输出
```

---

## 3. 设置参数

### 标量参数

```python
import hou

node = hou.node("/obj/geo1/box1")

# 浮点参数
node.parm("sizex").set(2.0)
node.parm("sizey").set(3.0)
node.parm("sizez").set(1.0)

# 整数参数
node.parm("divsx").set(10)    # X 方向细分
node.parm("divsy").set(10)    # Y 方向细分

# 布尔参数（Toggle）
node.parm("dodivs").set(1)    # 启用细分 (1=开, 0=关)
```

### 向量参数 (parmTuple)

```python
import hou

node = hou.node("/obj/geo1/xform1")

# 3 分量向量
node.parmTuple("t").set((1, 2, 3))       # 平移
node.parmTuple("r").set((0, 45, 0))      # 旋转
node.parmTuple("s").set((1, 1, 1))       # 缩放

# 也可以逐分量设置
node.parm("tx").set(1)
node.parm("ty").set(2)
node.parm("tz").set(3)
```

### 字符串参数

```python
import hou

node = hou.node("/obj/geo1/file1")

# 文件路径
node.parm("file").set("$HIP/geo/mesh.bgeo.sc")

# 属性名称
node.parm("group").set("top_group")

# 表达式
node.parm("attribname").set("Cd")
```

### Ramp 参数

```python
import hou

node = hou.node("/obj/geo1/attribramp1")

# 设置 Ramp（浮点型）
ramp_parm = node.parm("ramp")
# 创建 Ramp: 基点位置列表, 值列表, 插值类型列表
ramp = hou.Ramp(
    (hou.rampBasis.Linear, hou.rampBasis.Linear, hou.rampBasis.Linear),
    (0.0, 0.5, 1.0),      # 位置 (keys)
    (0.0, 0.8, 1.0)        # 值 (values)
)
ramp_parm.set(ramp)

# 颜色 Ramp
color_ramp = hou.Ramp(
    (hou.rampBasis.Linear, hou.rampBasis.Linear),
    (0.0, 1.0),                              # 位置
    ((1, 0, 0), (0, 0, 1))                   # RGB 值
)
node.parm("colorramp").set(color_ramp)
```

### 下拉菜单参数

```python
import hou

# 下拉菜单通常用整数索引
node.parm("grouptype").set(0)   # 0=Points
node.parm("grouptype").set(1)   # 1=Primitives
node.parm("grouptype").set(2)   # 2=Edges

# 也可能用字符串值（取决于参数定义）
node.parm("method").set("distance")
```

---

## 4. 创建子网络 (Subnet)

```python
import hou

with hou.undos.group("ArtClaw: 创建子网络"):
    geo = hou.node("/obj/geo1")

    # 创建子网络节点
    subnet = geo.createNode("subnet", "my_tool")

    # 在子网络内创建节点
    box = subnet.createNode("box", "base_box")
    xform = subnet.createNode("xform", "offset")
    xform.setInput(0, box)
    xform.parmTuple("t").set((0, 1, 0))

    # 将子网络的输出连接到内部节点
    # 子网络有自动的 output 节点
    output = subnet.node("output0")
    if not output:
        output = subnet.createNode("output", "output0")
    output.setInput(0, xform)

    subnet.setDisplayFlag(True)
    subnet.setRenderFlag(True)

    subnet.layoutChildren()
    geo.layoutChildren()

print("子网络创建完成")
```

---

## 5. 常见 SOP 工作流模板

### 建模工作流：Box → 细分 → 变形

```python
import hou

with hou.undos.group("ArtClaw: 建模工作流"):
    geo = hou.node("/obj").createNode("geo", "model_geo")
    for child in geo.children():
        child.destroy()

    # 基础形状
    box = geo.createNode("box", "base_shape")
    box.parm("sizex").set(2)
    box.parm("sizey").set(3)
    box.parm("sizez").set(2)

    # 细分
    subdivide = geo.createNode("subdivide", "smooth")
    subdivide.setInput(0, box)
    subdivide.parm("iterations").set(2)

    # 变形 - Mountain 噪波
    mountain = geo.createNode("mountain", "deform")
    mountain.setInput(0, subdivide)
    mountain.parm("height").set(0.3)
    mountain.parm("elementsize").set(1.0)

    # 法线
    normal = geo.createNode("normal", "fix_normals")
    normal.setInput(0, mountain)
    normal.parm("type").set(0)  # 按点

    normal.setDisplayFlag(True)
    normal.setRenderFlag(True)
    geo.layoutChildren()

print("建模工作流创建完成")
```

### 属性操作工作流

```python
import hou

with hou.undos.group("ArtClaw: 属性操作"):
    geo = hou.node("/obj/geo1")

    # 假设已有输入几何体 source_node
    source_node = geo.node("box1")

    # 创建属性 - Attribute Wrangle (VEX)
    wrangle = geo.createNode("attribwrangle", "set_color")
    wrangle.setInput(0, source_node)
    wrangle.parm("snippet").set('''
// 根据高度设置颜色
float h = fit(@P.y, -1, 1, 0, 1);
@Cd = set(h, 0.2, 1.0 - h);
''')

    # 属性传递
    attrib_transfer = geo.createNode("attribtransfer", "transfer_color")
    # 输入 0: 目标几何体, 输入 1: 源几何体
    # attrib_transfer.setInput(0, target_node)
    # attrib_transfer.setInput(1, wrangle)
    attrib_transfer.setInput(0, wrangle)
    attrib_transfer.parm("pointattribs").set("Cd")

    attrib_transfer.setDisplayFlag(True)
    attrib_transfer.setRenderFlag(True)
    geo.layoutChildren()

print("属性操作工作流创建完成")
```

### 散布工作流：地面 + 复制到点

```python
import hou

with hou.undos.group("ArtClaw: 散布工作流"):
    geo = hou.node("/obj").createNode("geo", "scatter_geo")
    for child in geo.children():
        child.destroy()

    # 地面
    grid = geo.createNode("grid", "ground")
    grid.parm("sizex").set(20)
    grid.parm("sizey").set(20)
    grid.parm("rows").set(50)
    grid.parm("cols").set(50)

    # 散点
    scatter = geo.createNode("scatter", "scatter_points")
    scatter.setInput(0, grid)
    scatter.parm("npts").set(200)

    # 要复制的物体
    sphere = geo.createNode("sphere", "instance_shape")
    sphere.parm("scale").set(0.1)

    # Copy to Points
    copytopoints = geo.createNode("copytopoints", "instancer")
    copytopoints.setInput(0, sphere)    # 输入 0: 要复制的几何体
    copytopoints.setInput(1, scatter)   # 输入 1: 目标点

    copytopoints.setDisplayFlag(True)
    copytopoints.setRenderFlag(True)
    geo.layoutChildren()

print("散布工作流创建完成")
```

---

## 6. 常用操作速查

| 操作 | 代码 |
|---|---|
| 创建节点 | `parent.createNode("type", "name")` |
| 删除节点 | `node.destroy()` |
| 连接 | `node.setInput(input_idx, src, output_idx)` |
| 断开连接 | `node.setInput(input_idx, None)` |
| 设置参数 | `node.parm("name").set(value)` |
| 设置向量参数 | `node.parmTuple("name").set((x, y, z))` |
| 设置表达式 | `node.parm("name").setExpression("$F")` |
| 设置关键帧 | `key = hou.Keyframe(); key.setFrame(1); key.setValue(0); node.parm("name").setKeyframe(key)` |
| 显示标记 | `node.setDisplayFlag(True)` |
| 渲染标记 | `node.setRenderFlag(True)` |
| 旁路标记 | `node.bypass(True)` |
| 布局子节点 | `parent.layoutChildren()` |
| 获取几何体 | `node.geometry()` |
| 读取点数量 | `len(node.geometry().points())` |
| 读取面数量 | `len(node.geometry().prims())` |
| 设置节点颜色 | `node.setColor(hou.Color(1, 0, 0))` |
| 添加注释 | `node.setComment("说明"); node.setGenericFlag(hou.nodeFlag.DisplayComment, True)` |
