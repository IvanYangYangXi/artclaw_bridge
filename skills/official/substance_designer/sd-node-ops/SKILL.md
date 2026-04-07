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

所有节点操作脚本的标准开头：

```python
import sd
from sd.api.sdapplication import SDApplication
from sd.api.sdproperty import SDPropertyCategory
from sd.api.sdvaluefloat import SDValueFloat
from sd.api.sdvaluefloat2 import SDValueFloat2
from sd.api.sdvaluefloat4 import SDValueFloat4
from sd.api.sdvalueint import SDValueInt
from sd.api.sdvaluebool import SDValueBool
from sd.api.sdvaluestring import SDValueString

app = SDApplication.getApplication()
graph = app.getUIMgr().getCurrentGraph()

if graph is None:
    print("错误：没有打开的图")
    # 必须中止
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
import sd
from sd.api.sdapplication import SDApplication

app = SDApplication.getApplication()
graph = app.getUIMgr().getCurrentGraph()

if graph is None:
    print("错误：没有打开的图")
else:
    # 创建 Blend 节点
    blend_node = graph.newNode("sbs::compositing::blend")
    if blend_node is None:
        print("错误：无法创建 Blend 节点")
    else:
        # 设置位置（避免堆叠）
        from sd.api.sdvaluefloat2 import SDValueFloat2
        from sd.api.sdbasetypes import float2
        blend_node.setPosition(float2(200, 0))
        print(f"创建 Blend 节点: {blend_node.getIdentifier()}")
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

库节点通过 `graph.newNode()` 传入资源 URL 创建：

```python
import sd
from sd.api.sdapplication import SDApplication
from sd.api.sdbasetypes import float2

app = SDApplication.getApplication()
graph = app.getUIMgr().getCurrentGraph()
pkg_mgr = app.getPackageMgr()

if graph is None:
    print("错误：没有打开的图")
else:
    # 创建库节点需要先找到对应的资源
    # 方法1: 通过 SBS 资源路径
    try:
        noise_node = graph.newNode("sbs::compositing::uniform")
        if noise_node:
            noise_node.setPosition(float2(-400, 0))
            print(f"创建节点成功: {noise_node.getIdentifier()}")
    except Exception as e:
        print(f"创建失败: {e}")
```

> **⚠️ 注意**：库节点的输出端口名称不一定是 `"unique_filter_output"`。
> 创建后必须用 `node.getProperties(SDPropertyCategory.Output)` 查看实际端口。

---

## 3. 连接节点

### 基本连接流程

连接的核心是：**源节点的输出属性** `.connect()` **目标节点的输入属性**。

```python
import sd
from sd.api.sdapplication import SDApplication
from sd.api.sdproperty import SDPropertyCategory
from sd.api.sdbasetypes import float2

app = SDApplication.getApplication()
graph = app.getUIMgr().getCurrentGraph()

if graph is None:
    print("错误：没有打开的图")
else:
    # 创建两个节点
    uniform_node = graph.newNode("sbs::compositing::uniform")
    levels_node = graph.newNode("sbs::compositing::levels")
    
    if uniform_node and levels_node:
        uniform_node.setPosition(float2(-200, 0))
        levels_node.setPosition(float2(200, 0))
        
        # 获取源节点的输出属性
        out_props = uniform_node.getProperties(SDPropertyCategory.Output)
        # 获取目标节点的输入属性
        in_props = levels_node.getProperties(SDPropertyCategory.Input)
        
        if out_props and in_props:
            # 打印端口名，确认正确
            print("输出端口:")
            for p in out_props:
                print(f"  {p.getId()}")
            print("输入端口:")
            for p in in_props:
                print(f"  {p.getId()}")
            
            # 连接第一个输出到第一个输入
            src_output = out_props[0]
            dst_input = in_props[0]
            src_output.connect(dst_input)
            print("连接成功")
        else:
            print("无法获取端口属性")
```

### 按 ID 查找端口并连接

```python
# 按端口 ID 精确连接
def connect_by_id(src_node, src_port_id, dst_node, dst_port_id):
    """通过端口 ID 连接两个节点"""
    src_prop = src_node.getPropertyFromId(src_port_id, SDPropertyCategory.Output)
    dst_prop = dst_node.getPropertyFromId(dst_port_id, SDPropertyCategory.Input)
    
    if src_prop is None:
        print(f"错误：源节点没有输出端口 '{src_port_id}'")
        # 打印可用端口
        for p in src_node.getProperties(SDPropertyCategory.Output):
            print(f"  可用输出: {p.getId()}")
        return False
    
    if dst_prop is None:
        print(f"错误：目标节点没有输入端口 '{dst_port_id}'")
        for p in dst_node.getProperties(SDPropertyCategory.Input):
            print(f"  可用输入: {p.getId()}")
        return False
    
    src_prop.connect(dst_prop)
    print(f"已连接: {src_node.getIdentifier()}.{src_port_id} -> {dst_node.getIdentifier()}.{dst_port_id}")
    return True
```

---

## 4. 设置节点参数

### 设置基础类型参数

```python
import sd
from sd.api.sdapplication import SDApplication
from sd.api.sdproperty import SDPropertyCategory
from sd.api.sdvaluefloat import SDValueFloat
from sd.api.sdvalueint import SDValueInt
from sd.api.sdvaluebool import SDValueBool
from sd.api.sdvaluefloat4 import SDValueFloat4
from sd.api.sdbasetypes import float2, float4

app = SDApplication.getApplication()
graph = app.getUIMgr().getCurrentGraph()

if graph is None:
    print("错误：没有打开的图")
else:
    # 假设已创建节点
    node = graph.newNode("sbs::compositing::blend")
    if node:
        node.setPosition(float2(0, 0))
        
        # ---- 设置 Float 参数 ----
        # Blend 节点的 opacity 参数
        opacity_prop = node.getPropertyFromId("opacity", SDPropertyCategory.Input)
        if opacity_prop:
            node.setPropertyValue(opacity_prop, SDValueFloat.sNew(0.75))
            print("设置 opacity = 0.75")
        
        # ---- 设置 Int 参数（如混合模式）----
        blending_prop = node.getPropertyFromId("blendingmode", SDPropertyCategory.Input)
        if blending_prop:
            # 混合模式枚举值：0=Copy, 1=Add, 2=Subtract, 3=Multiply ...
            node.setPropertyValue(blending_prop, SDValueInt.sNew(3))
            print("设置 blending mode = Multiply (3)")
        
        # ---- 设置 Color (Float4) 参数 ----
        uniform_node = graph.newNode("sbs::compositing::uniform")
        if uniform_node:
            uniform_node.setPosition(float2(-200, 200))
            color_prop = uniform_node.getPropertyFromId("outputcolor", SDPropertyCategory.Input)
            if color_prop:
                node.setPropertyValue(
                    color_prop, 
                    SDValueFloat4.sNew(float4(0.8, 0.2, 0.1, 1.0))
                )
                print("设置颜色 = (0.8, 0.2, 0.1, 1.0)")
        
        print("参数设置完成")
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
import sd
from sd.api.sdapplication import SDApplication
from sd.api.sdproperty import SDPropertyCategory
from sd.api.sdvaluestring import SDValueString
from sd.api.sdvalueint import SDValueInt
from sd.api.sdvalueenum import SDValueEnum
from sd.api.sdbasetypes import float2

app = SDApplication.getApplication()
graph = app.getUIMgr().getCurrentGraph()

if graph is None:
    print("错误：没有打开的图")
else:
    # PBR 输出通道定义
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
# 断开连接
def disconnect_input(node, input_port_id):
    """断开节点指定输入端口的连接"""
    prop = node.getPropertyFromId(input_port_id, SDPropertyCategory.Input)
    if prop:
        connections = prop.getConnections()
        if connections:
            prop.disconnect()  # 断开所有到此端口的连接
            print(f"已断开 {node.getIdentifier()}.{input_port_id}")
        else:
            print(f"端口 {input_port_id} 没有连接")

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
