---
name: sd-node-ops
description: >
  SD 节点创建、连接、参数设置指南。包含原子节点和库节点的正确使用方式。
  Use when AI needs to: (1) create nodes, (2) connect nodes,
  (3) set parameters, (4) build material graphs.
  Substance Designer only (run_python).
metadata:
  artclaw:
    version: 0.2.0
    author: ArtClaw
    software: substance_designer
---

# SD 节点操作

> ⚠️ **操作前必须先阅读 `sd-operation-rules`**

---

## 1. 原子节点

原子节点是**处理节点**（调整/混合/变形），不是纹理生成器。

```python
node = graph.newNode("sbs::compositing::levels")
node.setPosition(float2(0, 0))
```

### 常用原子节点

| 节点 | 定义 ID | 用途 |
|------|---------|------|
| Blend | `sbs::compositing::blend` | 混合两个输入 |
| Levels | `sbs::compositing::levels` | 色阶/对比度调整 |
| Normal | `sbs::compositing::normal` | 灰度高度图→法线图 |
| Warp | `sbs::compositing::warp` | 扭曲（gradient=灰度） |
| DirectionalWarp | `sbs::compositing::directionalwarp` | 方向扭曲（intensity=灰度） |
| Uniform | `sbs::compositing::uniform` | 纯色（灰度或彩色） |
| Output | `sbs::compositing::output` | PBR 输出通道 |
| Curve | `sbs::compositing::curve` | 曲线调整 |
| HSL | `sbs::compositing::hsl` | HSL 颜色调整 |
| Blur | `sbs::compositing::blur` | 模糊 |
| Sharpen | `sbs::compositing::sharpen` | 锐化 |
| Invert | `sbs::compositing::invert` | 反转 |
| Transform 2D | `sbs::compositing::transformation` | 平移/旋转/缩放 |
| Gradient Map | `sbs::compositing::gradient` | 灰度→彩色渐变映射 |
| Emboss | `sbs::compositing::emboss` | 浮雕 |
| Edge Detect | `sbs::compositing::edgedetect` | 边缘检测 |

---

## 2. 库节点（噪波/纹理生成器）🔴

**所有纹理生成节点都是库节点**，从 SD 安装目录的 `.sbs` 文件加载。

### 加载方式（内联写法，不要用 def）

```python
import os
pm = app.getPackageMgr()
base = r"C:\Program Files\Adobe\Adobe Substance 3D Designer\resources\packages"

# 加载 .sbs 包
path = os.path.join(base, "noise_perlin_noise.sbs")
pkg = pm.getUserPackageFromFilePath(path)
if not pkg:
    pkg = pm.loadUserPackage(path)

# 获取图资源并创建实例
res = pkg.getChildrenResources(False)[0]
node = graph.newInstanceNode(res)
node.setPosition(float2(-800, 0))
```

### 常用库节点

| 用途 | 文件名 | 输出端口 | 特点 |
|------|--------|----------|------|
| 通用噪波 | `noise_perlin_noise.sbs` | `output` | 有机随机纹理 |
| 柔和噪波 | `noise_clouds_1.sbs` | `output` | 低频柔和变化 |
| 细胞纹理 | `noise_cells_1.sbs` | `output` | 颗粒/石材 |
| 分形噪波 | `noise_fractal_sum_base.sbs` | `output` | 复杂自相似纹理 |
| 泰森多边形 | `noise_voronoi.sbs` | `output` | 裂纹/细胞 |
| 高斯噪波 | `noise_gaussian_noise.sbs` | `output` | 随机均匀噪点 |
| **木纹纤维** | `wood_fibers_1.sbs` | `Wood_Fibers` | **木材专用** |
| 纤维 | `fibers_1.sbs` | 查询 | 方向性纤维 |
| 方向性噪波 | `noise_directional_noise_1.sbs` | 查询 | 方向性强 |
| 方向性划痕 | `noise_directional_scratches.sbs` | 查询 | 划痕效果 |
| 条纹 | `pattern_stripes.sbs` | 查询 | 规则条纹 |
| 做旧 | `noise_grunge_map_001.sbs` | 查询 | 脏旧效果 |

**⚠️ 输出端口名不统一！** 创建后必须查询：
```python
for p in node.getProperties(SDPropertyCategory.Output):
    print(p.getId())
```

### 库节点参数查询

```python
# 查看库节点可调参数（跳过 $ 开头的系统参数）
for p in node.getProperties(SDPropertyCategory.Input):
    pid = p.getId()
    if not pid.startswith("$"):
        v = node.getPropertyValue(p)
        print(f"  {pid} = {v.get() if v else '?'}")
```

---

## 3. Uniform 节点详解

Uniform 是唯一能输出颜色的原子节点，但**不能做纹理源**。

### 灰度模式（用于 Warp gradient / Metallic=0 等）

```python
u = graph.newNode("sbs::compositing::uniform")
u.setInputPropertyValueFromId("colorswitch", SDValueBool.sNew(False))  # 灰度
# outputcolor 的 r 分量决定灰度值（0=黑, 1=白）
u.setInputPropertyValueFromId("outputcolor", SDValueColorRGBA.sNew(ColorRGBA(0.5, 0.5, 0.5, 1.0)))
```

### 彩色模式（用于 Blend 着色的颜色源）

```python
u = graph.newNode("sbs::compositing::uniform")
u.setInputPropertyValueFromId("colorswitch", SDValueBool.sNew(True))  # 彩色
u.setInputPropertyValueFromId("outputcolor", SDValueColorRGBA.sNew(ColorRGBA(0.36, 0.23, 0.12, 1.0)))
```

---

## 4. 连接

```python
# 原子节点连接
src.newPropertyConnectionFromId("unique_filter_output", dst, "input1")

# 库节点连接（输出端口名不同）
lib_node.newPropertyConnectionFromId("output", dst, "input1")  # 或 "Wood_Fibers" 等

# 断开
prop = node.getPropertyFromId("input1", SDPropertyCategory.Input)
node.deletePropertyConnections(prop)
```

### 端口速查

| 节点 | 输入 | 输出 |
|------|------|------|
| blend | `source`, `destination`, `opacity` | `unique_filter_output` |
| levels/curve/blur/normal | `input1` | `unique_filter_output` |
| warp | `input1`, `inputgradient` | `unique_filter_output` |
| directionalwarp | `input1`, `inputintensity` | `unique_filter_output` |
| output | `inputNodeOutput` | (usage id) |
| 库节点 | **查询** | **查询** |

---

## 5. 参数设置

```python
# Float
node.setInputPropertyValueFromId("intensity", SDValueFloat.sNew(5.0))

# Int（如混合模式）
node.setInputPropertyValueFromId("blendingmode", SDValueInt.sNew(3))  # Multiply

# Bool
node.setInputPropertyValueFromId("colorswitch", SDValueBool.sNew(False))

# Color
node.setInputPropertyValueFromId("outputcolor", SDValueColorRGBA.sNew(ColorRGBA(0.5, 0.3, 0.1, 1.0)))
```

### Blend 混合模式

| 值 | 模式 |
|----|------|
| 0 | Copy |
| 1 | Add |
| 3 | Multiply |
| 5 | Max (Lighten) |
| 6 | Min (Darken) |
| 9 | Overlay |
| 10 | Screen |
| 11 | Soft Light |

---

## 6. PBR 输出节点

```python
out = graph.newNode("sbs::compositing::output")
out.setPosition(float2(600, y))
ip = out.getPropertyFromId("identifier", SDPropertyCategory.Annotation)
out.setPropertyValue(ip, SDValueString.sNew("baseColor"))
lp = out.getPropertyFromId("label", SDPropertyCategory.Annotation)
out.setPropertyValue(lp, SDValueString.sNew("BaseColor"))
```

---

## 7. 着色方案：Blend 替代 Gradient Map

Gradient Map 的渐变参数设置复杂，推荐用 Blend 着色：

```
[Uniform 深色(Color, colorswitch=True)] → blend.source
[Uniform 浅色(Color, colorswitch=True)] → blend.destination  
[灰度纹理]                              → blend.opacity
blend 输出 = 根据灰度混合的彩色纹理
```

这样灰度纹理的暗部显示深色，亮部显示浅色。
