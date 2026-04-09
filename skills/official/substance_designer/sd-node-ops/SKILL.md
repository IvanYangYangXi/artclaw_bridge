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
| ~~Invert~~ | ~~`sbs::compositing::invert`~~ | ⛔ **不存在！** newNode 返回 None。用 Levels（黑白点互换）或 Blend(Subtract)+Uniform(白) 代替 |
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

Uniform 是唯一能输出颜色的原子节点，但**不能做纹理源**（纯色warp后仍纯色）。

**⛔ 必须显式设 `colorswitch`！默认 False=灰度模式，输出永远是灰色。**

### 灰度模式（用于 Metallic=0, Roughness常量等）

```python
u = graph.newNode("sbs::compositing::uniform")
u.setInputPropertyValueFromId("colorswitch", SDValueBool.sNew(False))  # 灰度
u.setInputPropertyValueFromId("outputcolor", SDValueColorRGBA.sNew(ColorRGBA(0.5, 0.5, 0.5, 1.0)))
```

### 彩色模式（⛔ 必须设 colorswitch=True 否则颜色不生效！）

```python
u = graph.newNode("sbs::compositing::uniform")
u.setInputPropertyValueFromId("colorswitch", SDValueBool.sNew(True))   # ⛔ 必须True!
u.setInputPropertyValueFromId("outputcolor", SDValueColorRGBA.sNew(ColorRGBA(0.36, 0.23, 0.12, 1.0)))
```

**常见错误**: 设了 outputcolor 但忘记设 colorswitch=True → 输出仍然是灰色 → BaseColor 看起来是灰的。

---

## 4. 连接

### ⛔ 原子节点 vs 库节点输出端口名不同！

| 类型 | 输出端口名 | 示例 |
|------|-----------|------|
| **原子节点** (levels/blend/blur/warp/sharpen/curve/normal/hsl/emboss/transformation/uniform) | **`unique_filter_output`** | `levels.newPropertyConnectionFromId("unique_filter_output", dst, "input1")` |
| **库节点** (噪波/纹理生成器) | **各不相同，必须查询** | `"output"` / `"Wood_Fibers"` / `"Noise_Zoom"` 等 |
| **Output 节点** | usage id | — |

**⛔ 原子节点的输出端口永远是 `unique_filter_output`，不是 `output`！**
用 `"output"` 连原子节点会报错：`没有名为 'output' 的输出端口`，导致连接失败，后续链路全断！

```python
# ✅ 原子节点连接
src.newPropertyConnectionFromId("unique_filter_output", dst, "input1")

# ✅ 库节点连接（输出端口名不同，先查询）
lib_node.newPropertyConnectionFromId("output", dst, "input1")  # 或 "Wood_Fibers" 等

# 断开
prop = node.getPropertyFromId("input1", SDPropertyCategory.Input)
node.deletePropertyConnections(prop)
```

### 端口速查

| 节点 | 输入 | 输出 |
|------|------|------|
| blend | `source`, `destination`, `opacity`(连接端口) | `unique_filter_output` |
| levels/curve/blur/normal | `input1` | `unique_filter_output` |
| warp | `input1`, `inputgradient` | `unique_filter_output` |
| directionalwarp | `input1`, `inputintensity` | `unique_filter_output` |
| output | `inputNodeOutput` | (usage id) |
| 库节点 | **查询** | **查询** |

---

## 5. 参数设置

### ⛔ 黄金规则：先查询，再设值！

**每次创建新节点后，第一步永远是查询参数：**
```python
node = graph.newNode("sbs::compositing::levels")
# ⛔ 不要直接猜参数名！先查询
for p in node.getProperties(SDPropertyCategory.Input):
    pid = p.getId()
    if pid.startswith("$"): continue
    v = node.getPropertyValue(p)
    if v is None:
        print(f"  PORT: {pid}")  # 连接端口，不能赋值
    else:
        print(f"  PARAM: {pid} = {v.get()} ({type(v).__name__})")
# → 看到输出后，用正确的参数名和类型设值
```

**已知陷阱（即使查询过也要注意）：**
| 节点 | 参数名 | 正确类型 | 常见错误 |
|------|--------|---------|---------|
| levels | `levelinlow`/`levelinhigh`/`levelinmid` | **SDValueFloat4** | 猜成 `inlow` + SDValueFloat |
| blend | `opacitymult` (标量) | SDValueFloat | 猜成 `opacity` (那是连接端口) |
| transformation | `matrix22` | SDValueFloat4 | — |
| uniform | `outputcolor` | SDValueColorRGBA | ⛔ 必须先设 `colorswitch=True` 才能输出彩色！ |
| gradient | `gradientrgba` | SDValueArray | — |
| 库节点 Enum 参数 | 类型显示 `SDValueEnum` | **用 SDValueInt.sNew(n)** | 无 SDValueEnum.sNew |

### 设值示例

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
| 2 | Subtract |
| 3 | Multiply |
| 5 | Max (Lighten) |
| 6 | Min (Darken) |
| 9 | Overlay |
| 10 | Screen |
| 11 | Soft Light |

### ⚠️ Blend 参数：`opacity` vs `opacitymult`

```python
# ⛔ 错误！opacity 是连接端口，直接赋值会抛 DataIsReadOnly
# blend.setInputPropertyValueFromId("opacity", SDValueFloat.sNew(0.5))

# ✅ 正确：用 opacitymult 控制标量不透明度
blend.setInputPropertyValueFromId("opacitymult", SDValueFloat.sNew(0.5))

# ✅ opacity 端口用于连接灰度纹理遮罩
mask_node.newPropertyConnectionFromId("output", blend, "opacity")
```

---

## 6. PBR 输出节点 + Usage 属性 🔴

```python
out = graph.newNode("sbs::compositing::output")
out.setPosition(float2(600, y))

# 1. identifier 标识
ip = out.getPropertyFromId("identifier", SDPropertyCategory.Annotation)
out.setPropertyValue(ip, SDValueString.sNew("baseColor"))

# 2. label 显示名
lp = out.getPropertyFromId("label", SDPropertyCategory.Annotation)
out.setPropertyValue(lp, SDValueString.sNew("BaseColor"))

# 3. ⛔ usages — 3D 视口渲染必需！不设则该通道不在 3D 视口显示
from sd.api.sdusage import SDUsage
from sd.api.sdvalueusage import SDValueUsage
from sd.api.sdvaluearray import SDValueArray
from sd.api.sdtypeusage import SDTypeUsage

usage = SDUsage.sNew("baseColor", "RGBA", "")  # (name, components, colorSpace)
usage_val = SDValueUsage.sNew(usage)
usage_arr = SDValueArray.sNew(SDTypeUsage.sNew(), 0)
usage_arr.pushBack(usage_val)
usages_prop = out.getPropertyFromId("usages", SDPropertyCategory.Annotation)
out.setPropertyValue(usages_prop, usage_arr)
```

### Usage 通道名对照

| 通道 | identifier | usage name |
|------|------------|------------|
| BaseColor | `baseColor` | `baseColor` |
| Normal | `normal` | `normal` |
| Roughness | `roughness` | `roughness` |
| Metallic | `metallic` | `metallic` |
| Height | `height` | `height` |
| AO | `ambientOcclusion` | `ambientOcclusion` |

> **⛔ `SDUsage.sNew()` 必须传3个参数！** 无参调用会导致 SD 挂起。
> Components 统一用 `"RGBA"`，ColorSpace 用空字符串 `""`。

---

## 7. 着色方案 🔴

**着色 = 把灰度结构映射为彩色。推荐用 Gradient Map（一个节点搞定多色渐变映射）。**

### ⭐ 方案 A：Gradient Map（推荐！更精细，一个节点完成多色映射）

Gradient Map 把灰度输入映射到自定义的颜色渐变。**适合需要精细色调控制的场景。**

```python
from sd.api.sdvaluestruct import SDValueStruct
from sd.api.sdtypestruct import SDTypeStruct
from sd.api.sdvaluearray import SDValueArray

# 1. 创建 gradient map 节点
grad = graph.newNode("sbs::compositing::gradient")
grad.setPosition(float2(x, y))
grad.setInputPropertyValueFromId("colorswitch", SDValueBool.sNew(True))  # True=彩色, False=灰度

# 2. 创建渐变关键点
key_type = SDTypeStruct.sNew("sbs::compositing::gradient_key_rgba")

def make_key(pos, r, g, b, a=1.0, mid=0.5):
    k = SDValueStruct.sNew(key_type)
    k.setPropertyValueFromId('position', SDValueFloat.sNew(pos))
    k.setPropertyValueFromId('value', SDValueColorRGBA.sNew(ColorRGBA(r, g, b, a)))
    k.setPropertyValueFromId('midpoint', SDValueFloat.sNew(mid))
    return k

# 3. 组装渐变数组
arr = SDValueArray.sNew(key_type, 0)
arr.pushBack(make_key(0.0,  0.05, 0.08, 0.18))  # 暗色端
arr.pushBack(make_key(0.5,  0.25, 0.22, 0.20))  # 中间过渡
arr.pushBack(make_key(1.0,  0.55, 0.50, 0.42))  # 亮色端

# 4. 设置到节点
grad.setInputPropertyValueFromId("gradientrgba", arr)

# 5. 连接灰度输入
gray_node.newPropertyConnectionFromId("output_port", grad, "input1")
```

**Gradient Map 关键点参数**：
| 字段 | 类型 | 说明 |
|------|------|------|
| `position` | float (0~1) | 在渐变条上的位置。0=输入灰度最暗处映射的颜色，1=最亮处 |
| `value` | ColorRGBA | 该位置的颜色 |
| `midpoint` | float (0~1) | 与下一个关键点之间的插值中点偏移。0.5=线性，<0.5偏暗，>0.5偏亮 |

**彩色 vs 灰度模式**：
- `colorswitch=True`：输入灰度，输出彩色（用于着色）
- `colorswitch=False`：输入灰度，输出灰度（用于遮罩重映射）

### 方案 B：Uniform + Blend（简单，两色混合）

适合只需要两种颜色之间线性混合的场景。

```python
# 深色
u_dark = graph.newNode("sbs::compositing::uniform")
u_dark.setInputPropertyValueFromId("colorswitch", SDValueBool.sNew(True))
u_dark.setInputPropertyValueFromId("outputcolor", SDValueColorRGBA.sNew(ColorRGBA(0.05, 0.08, 0.15, 1.0)))

# 浅色
u_light = graph.newNode("sbs::compositing::uniform")
u_light.setInputPropertyValueFromId("colorswitch", SDValueBool.sNew(True))
u_light.setInputPropertyValueFromId("outputcolor", SDValueColorRGBA.sNew(ColorRGBA(0.55, 0.50, 0.42, 1.0)))

# Blend: 灰度遮罩控制混合
blend = graph.newNode("sbs::compositing::blend")
u_dark.newPropertyConnectionFromId("unique_filter_output", blend, "source")
u_light.newPropertyConnectionFromId("unique_filter_output", blend, "destination")
gray_node.newPropertyConnectionFromId("output_port", blend, "opacity")  # 灰度遮罩
# 暗处=深色(source)，亮处=浅色(destination)
```

### 方案选择指南

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| 两色渐变（经线/纬线双色） | B: Uniform+Blend | 简单直接 |
| 多色渐变（3+色调过渡） | **A: Gradient Map** | 一个节点搞定多色映射 |
| 精确色调控制（特定灰度范围→特定颜色） | **A: Gradient Map** | position 参数精确控制 |
| 方向性遮罩（灰度→灰度重映射） | **A: Gradient Map(灰度)** | 比 Levels 更灵活 |
| 窄带高亮/暗带 | **A: Gradient Map** | 把关键点挤在窄范围内 |

### ⭐ fabric_009 着色架构参考（5层着色系统）

fabric_009 的着色分 5 层叠加，这是高质量编织材质着色的参考架构：

**Layer 1: 方向性遮罩（灰度 Gradient Map）**
- 源: gradient_linear_1 旋转90° → 多个灰度 gradient map → 提取经纬方向遮罩
- 用途: 控制后续着色层的作用区域（哪个位置用什么颜色）
- 技巧: 把关键点挤在极窄范围(如 0.29~0.33) → 只有编织中特定方向区域被选中

**Layer 2: 主体着色（彩色 Gradient Map）**
- 源: 编织 warp 结果 → gradient map → 编织主色调
- 编织骨架 blur → gradient map → 结构明暗
- 各通过 blend 层层叠加，用 Layer 1 的遮罩控制区域

**Layer 3: 色块离散化（mosaic + Gradient Map）**
- mosaic_grayscale → gradient map → 离散色块 → blend(Multiply, 0.93)
- 模拟纱线批次导致的色差（同一匹布不同区域微妙色调差异）

**Layer 4: 有机化（噪波 + Gradient Map，极微弱叠加）**
- fractal_sum → gradient map → blend(Max, **0.05**) — 5% 有机色差
- bnw_spots → gradient map → blend(Add, **0.06**) — 6% 斑点色差
- 强度极低（5-6%），但打破了着色的机械均匀感

**Layer 5: 精修**
- replace_color: 修正 gradient map 产出的色偏（将某个不想要的颜色→中性灰）
- HSL: 整体色调微调
- levels: 整体明度/对比度微调
