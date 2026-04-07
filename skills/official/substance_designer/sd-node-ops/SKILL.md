---
name: sd-node-ops
description: >
  SD 节点创建、连接、参数设置指南。包含原子节点和库节点的使用方式。
  Use when AI needs to: (1) create nodes, (2) connect nodes,
  (3) set parameters, (4) build material graphs.
  Substance Designer only (run_python).
metadata:
  artclaw:
    author: ArtClaw
    software: substance_designer
---

# SD 节点操作

> 创建节点、连接节点、设置参数的完整指南。
> ⚠️ **操作前必须先阅读 `sd-operation-rules` Skill。**

---

## 通用前置代码

`run_python` 已预注入以下变量，**直接使用，无需 import**：

- `sd`, `app`, `graph`, `S`, `W`, `L`
- `SDPropertyCategory`, `float2`, `float3`, `float4`, `ColorRGBA`
- `SDValueFloat`, `SDValueInt`, `SDValueBool`, `SDValueString`
- `SDValueFloat2`, `SDValueFloat3`, `SDValueFloat4`, `SDValueColorRGBA`

```python
# ✅ 直接使用预注入变量
if graph is None:
    result = "错误：没有打开的图"

# ❌ 禁止在 exec 中 import sd.api 子模块（会超时死锁）
# from sd.api.sdproperty import SDPropertyCategory  # 禁止！
```

---

## 1. 原子节点（Atomic Nodes）

原子节点是 SD 内置的基础处理节点，定义 ID 格式为 `sbs::compositing::<name>`。

### 常用原子节点定义 ID

| 节点 | 定义 ID | 说明 |
|------|---------|------|
| Blend | `sbs::compositing::blend` | 混合两个输入 |
| Levels | `sbs::compositing::levels` | 色阶调整 |
| Blur | `sbs::compositing::blur` | 模糊 |
| Sharpen | `sbs::compositing::sharpen` | 锐化 |
| Transform 2D | `sbs::compositing::transformation` | 2D 变换（平移/旋转/缩放） |
| Uniform Color | `sbs::compositing::uniform` | 纯色/均匀值 |
| Output | `sbs::compositing::output` | 图输出节点 |
| Normal | `sbs::compositing::normal` | Height → Normal 转换 |
| Curve | `sbs::compositing::curve` | 曲线调整 |
| Gradient Map | `sbs::compositing::gradient` | 渐变映射 |
| HSL | `sbs::compositing::hsl` | HSL 颜色调整 |
| Invert | `sbs::compositing::invert` | 反转 |
| Histogram Scan | `sbs::compositing::histogramselect` | 直方图选择 |
| Histogram Range | `sbs::compositing::histogramshift` | 直方图范围 |
| Distance | `sbs::compositing::distance` | 距离场 |
| Warp | `sbs::compositing::warp` | 扭曲变形 |
| Directional Warp | `sbs::compositing::directionalwarp` | 方向性扭曲 |
| Emboss | `sbs::compositing::emboss` | 浮雕效果 |
| Edge Detect | `sbs::compositing::edgedetect` | 边缘检测 |

### 创建原子节点示例

```python
if graph is None:
    result = "错误：没有打开的图"
else:
    blend_node = graph.newNode("sbs::compositing::blend")
    if blend_node is None:
        result = "错误：无法创建 Blend 节点"
    else:
        blend_node.setPosition(float2(200, 0))
        result = f"创建 Blend 节点: {blend_node.getIdentifier()}"
```

---

## 2. 库节点（Library Nodes / Filters）

库节点是预制的复合节点（来自 SD 的内置库），定义 ID 格式为 `sbs::compositing::<name>`，但需要通过资源路径加载。

### 常用库节点

| 节点 | 资源路径 | 说明 |
|------|----------|------|
| Clouds | `sbs://cloud.sbs/cloud` | 云朵/柔和噪波 |
| Cells | `sbs://cells.sbs/cells_1` 等 | 细胞纹理 |
| Perlin Noise | `sbs://perlin_noise.sbs/perlin_noise` | 柏林噪波 |
| Gaussian Noise | `sbs://noise_gaussian.sbs/noise_gaussian` | 高斯噪波 |
| Grunge Map | `sbs://grunge_map.sbs/grunge_map_001` 等 | 做旧纹理 |
| Tile Generator | `sbs://tile_generator.sbs/tile_generator` | 平铺生成器 |
| Shape | `sbs://shape.sbs/shape` | 基础形状 |
| BnW Spots | `sbs://bnw_spots.sbs/bnw_spots_1` 等 | 黑白斑点 |
| Scratches | `sbs://scratches.sbs/scratches` | 划痕 |

### 创建库节点

库节点通过 `graph.newInstanceNode()` + 资源查找创建：

```python
if graph is None:
    result = "错误：没有打开的图"
else:
    pkg_mgr = app.getPackageMgr()
    # 方法: 通过 SBS 资源路径查找并创建实例
    resource_url = "sbs://perlin_noise.sbs/perlin_noise"
    resource = None
    for pkg in pkg_mgr.getPackages():
        try:
            r = pkg.findResourceFromUrl(resource_url)
            if r is not None:
                resource = r
                break
        except Exception:
            pass
    if resource:
        node = graph.newInstanceNode(resource)
        if node:
            node.setPosition(float2(-400, 0))
            result = f"创建库节点成功: {node.getIdentifier()}"
        else:
            result = "创建库节点失败"
    else:
        result = f"找不到资源: {resource_url}"
```

> **⚠️ 注意**：库节点的输出端口名称不一定是 `"unique_filter_output"`。
> 创建后必须用 `node.getProperties(SDPropertyCategory.Output)` 查看实际端口。

---

## 3. 连接节点

### ⚠️ 核心 API（必读）

SD 的连接 API 在 **SDNode** 上，不在 SDProperty 上：

- **`src_node.newPropertyConnectionFromId(out_port_id, dst_node, in_port_id)`** — 通过端口 ID 连接（推荐）
- **`src_node.newPropertyConnection(out_prop, dst_node, in_prop)`** — 通过属性对象连接
- **`node.getPropertyConnections(prop)`** — 查询某端口的连接
- **`node.deletePropertyConnections(prop)`** — 删除某端口的所有连接
- **`connection.disconnect()`** — 删除单个连接

> ❌ **`prop.connect()` 不存在！** SDProperty 没有 connect 方法。

### 方式 1：通过端口 ID 连接（推荐）

```python
if graph is None:
    result = "错误：没有打开的图"
else:
    uniform_node = graph.newNode("sbs::compositing::uniform")
    levels_node = graph.newNode("sbs::compositing::levels")
    
    if uniform_node and levels_node:
        uniform_node.setPosition(float2(-200, 0))
        levels_node.setPosition(float2(200, 0))
        
        # 通过端口 ID 直接连接
        conn = uniform_node.newPropertyConnectionFromId(
            "unique_filter_output",  # 源节点输出端口 ID
            levels_node,             # 目标节点
            "input1"                 # 目标节点输入端口 ID
        )
        result = f"连接成功: {conn}" if conn else "连接失败"
```

### 方式 2：通过属性对象连接

```python
# 先获取属性对象，再连接
out_prop = src_node.getPropertyFromId("unique_filter_output", SDPropertyCategory.Output)
in_prop = dst_node.getPropertyFromId("input1", SDPropertyCategory.Input)

if out_prop and in_prop:
    conn = src_node.newPropertyConnection(out_prop, dst_node, in_prop)
    result = f"连接成功: {conn}"
```

### 安全连接函数（带端口验证）

```python
def connect_by_id(src_node, src_port_id, dst_node, dst_port_id):
    """通过端口 ID 连接两个节点（带验证）"""
    # 验证源端口存在
    src_prop = src_node.getPropertyFromId(src_port_id, SDPropertyCategory.Output)
    if src_prop is None:
        avail = [p.getId() for p in src_node.getProperties(SDPropertyCategory.Output)]
        print(f"错误：源节点没有输出端口 '{src_port_id}'，可用: {avail}")
        return None
    
    # 验证目标端口存在
    dst_prop = dst_node.getPropertyFromId(dst_port_id, SDPropertyCategory.Input)
    if dst_prop is None:
        avail = [p.getId() for p in dst_node.getProperties(SDPropertyCategory.Input)]
        print(f"错误：目标节点没有输入端口 '{dst_port_id}'，可用: {avail}")
        return None
    
    conn = src_node.newPropertyConnectionFromId(src_port_id, dst_node, dst_port_id)
    print(f"已连接: [{src_node.getIdentifier()}].{src_port_id} -> [{dst_node.getIdentifier()}].{dst_port_id}")
    return conn
```

### 查询已有连接

```python
# 检查节点某个端口的连接
prop = node.getPropertyFromId("input1", SDPropertyCategory.Input)
if prop:
    conns = node.getPropertyConnections(prop)
    if conns and conns.getSize() > 0:
        for i in range(conns.getSize()):
            c = conns.getItem(i)
            src = c.getOutputPropertyNode()
            src_port = c.getOutputProperty()
            print(f"  <- [{src.getIdentifier()}].{src_port.getId()}")
```

---

## 4. 设置节点参数

### 设置基础类型参数

```python
if graph is None:
    result = "错误：没有打开的图"
else:
    node = graph.newNode("sbs::compositing::blend")
    if node:
        node.setPosition(float2(0, 0))
        
        # ---- 设置 Float 参数（推荐方式：setInputPropertyValueFromId）----
        node.setInputPropertyValueFromId("opacity", SDValueFloat.sNew(0.75))
        
        # ---- 设置 Int 参数（如混合模式）----
        node.setInputPropertyValueFromId("blendingmode", SDValueInt.sNew(3))  # Multiply
        
        # ---- 设置 Color (Float4) 参数 ----
        uniform_node = graph.newNode("sbs::compositing::uniform")
        if uniform_node:
            uniform_node.setPosition(float2(-200, 200))
            uniform_node.setInputPropertyValueFromId(
                "outputcolor",
                SDValueFloat4.sNew(float4(0.8, 0.2, 0.1, 1.0))
            )
        
        result = "参数设置完成"
```

### 查找参数再设置（安全模式）

```python
def set_param_safe(node, param_id, value):
    """安全设置参数 — 先查找再设置"""
    prop = node.getPropertyFromId(param_id, SDPropertyCategory.Input)
    if prop is None:
        print(f"警告：节点 {node.getIdentifier()} 没有参数 '{param_id}'")
        print("可用参数:")
        all_props = node.getProperties(SDPropertyCategory.Input)
        if all_props:
            for p in all_props:
                print(f"  - {p.getId()} ({p.getLabel()})")
        return False
    
    node.setPropertyValue(prop, value)
    print(f"设置 {node.getIdentifier()}.{param_id} = {value}")
    return True
```

---

## 5. 创建 PBR 输出节点

为图创建标准 PBR 输出通道：

```python
if graph is None:
    result = "错误：没有打开的图"
else:
    pbr_outputs = [
        {"usage": "basecolor",        "label": "BaseColor",  "pos_y": 0},
        {"usage": "normal",           "label": "Normal",     "pos_y": 150},
        {"usage": "roughness",        "label": "Roughness",  "pos_y": 300},
        {"usage": "metallic",         "label": "Metallic",   "pos_y": 450},
        {"usage": "height",           "label": "Height",     "pos_y": 600},
        {"usage": "ambientocclusion", "label": "AO",         "pos_y": 750},
    ]
    
    output_x = 800  # 输出节点的 X 位置
    created = []
    
    for out_def in pbr_outputs:
        output_node = graph.newNode("sbs::compositing::output")
        if output_node is None:
            print(f"错误：无法创建输出节点 {out_def['label']}")
            continue
        
        output_node.setPosition(float2(output_x, out_def["pos_y"]))
        
        # 设置输出标识符（usage）
        identifier_prop = output_node.getPropertyFromId("identifier", SDPropertyCategory.Annotation)
        if identifier_prop:
            output_node.setPropertyValue(identifier_prop, SDValueString.sNew(out_def["usage"]))
        
        # 设置标签
        label_prop = output_node.getPropertyFromId("label", SDPropertyCategory.Annotation)
        if label_prop:
            output_node.setPropertyValue(label_prop, SDValueString.sNew(out_def["label"]))
        
        created.append(out_def["label"])
        print(f"创建输出: {out_def['label']} ({out_def['usage']})")
    
    print(f"\n共创建 {len(created)} 个 PBR 输出节点: {', '.join(created)}")
```

---

## 6. 节点布局

### 手动设置位置（推荐）

```python
from sd.api.sdbasetypes import float2

# ⚠️ 不要使用 arrange_nodes() — 会破坏连接！
# 使用 setPosition 手动布局

# 标准布局间距
SPACING_X = 250  # 水平间距
SPACING_Y = 150  # 垂直间距

# 示例：线性布局
nodes_in_chain = [node_a, node_b, node_c, node_d]
for i, node in enumerate(nodes_in_chain):
    node.setPosition(float2(i * SPACING_X, 0))

# 示例：分支布局（一个源分到多个目标）
source_node.setPosition(float2(0, 0))
branch_nodes = [target_1, target_2, target_3]
for i, node in enumerate(branch_nodes):
    y_offset = (i - len(branch_nodes) / 2) * SPACING_Y
    node.setPosition(float2(SPACING_X, y_offset))
```

---

## 7. 删除节点和断开连接

```python
# 断开某端口的所有连接
def disconnect_input(node, input_port_id):
    """断开节点指定输入端口的所有连接"""
    prop = node.getPropertyFromId(input_port_id, SDPropertyCategory.Input)
    if prop:
        node.deletePropertyConnections(prop)
        print(f"已断开 {node.getIdentifier()}.{input_port_id} 的所有连接")

# 断开单个连接
def disconnect_one(node, port_id, category):
    """断开指定端口的某个连接"""
    prop = node.getPropertyFromId(port_id, category)
    if prop:
        conns = node.getPropertyConnections(prop)
        if conns and conns.getSize() > 0:
            conns.getItem(0).disconnect()  # 断开第一个连接

# 删除节点
def delete_node(graph, node):
    """从图中删除节点"""
    # ⚠️ 无 undo — 确认后再删
    node_id = node.getIdentifier()
    graph.deleteNode(node)
    print(f"已删除节点: {node_id}")
```

---

## 常见混合模式枚举值

Blend 节点 `blendingmode` 参数的常用值：

| 值 | 模式 |
|----|------|
| 0 | Copy |
| 1 | Add (Linear Dodge) |
| 2 | Subtract |
| 3 | Multiply |
| 4 | Add Sub |
| 5 | Max (Lighten) |
| 6 | Min (Darken) |
| 7 | Switch |
| 8 | Divide |
| 9 | Overlay |
| 10 | Screen |
| 11 | Soft Light |
