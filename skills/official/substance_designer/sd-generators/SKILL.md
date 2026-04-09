---
name: sd-generators
description: >
  SD 纹理/图案生成器库节点深度分析。覆盖 21 个核心生成器的内部引擎、参数、适用场景。
  分为三类：图案生成器(tile_generator/splatter等)、噪波生成器(perlin/cells/voronoi等)、
  特征纹理生成器(moisture_noise/wood_fibers等)。
  Use when AI needs to: (1) choose the right generator for a material,
  (2) understand generator parameters for fine-tuning,
  (3) know which generators are FX-Map vs Pixel Processor based,
  (4) build custom patterns by combining generators.
  Substance Designer only (run_python).
metadata:
  artclaw:
    version: 1.0.0
    author: ArtClaw
    software: substance_designer
---

# SD 纹理/图案生成器指南

> 21 个核心生成器的引擎类型、参数和最佳实践。
> **选择正确的生成器是材质制作的第一步。**

## 生成器引擎分类

SD 的库节点有三种底层引擎：

| 引擎 | 原理 | 适合 | 代表节点 |
|------|------|------|----------|
| **FX-Map** | 迭代+四叉树渲染图案 | 重复图案、散布 | tile_generator, splatter, cells |
| **Pixel Processor** | 逐像素数学运算 | 数学噪波、距离场 | voronoi |
| **Composite** | 原子节点组合 | 复杂效果 | brick_generator, weave_generator |

## 一、图案生成器（Pattern Generators）

### tile_generator ⭐⭐⭐ (使用率第一！)

**引擎**: FX-Map (4 节点，极简结构)
**内部**: 1 个 FX-Map + 2 个输入 + 1 个输出。所有复杂度在 FX-Map 的函数图中。

**核心参数**:

| 参数 | 默认 | 说明 |
|------|------|------|
| `Nb_X` / `Nb_Y` | 10 | 水平/垂直重复数 |
| `Middle_Size` | (0.5, 0.5) | 砖块大小比例 |
| `Scale` | 1.0 | 整体缩放 |
| `ScaleVariation` | 0.0 | 大小随机变化量 |
| `Interstice` | (0,0,0,0) | 间隙（缝隙宽度） |
| `Offset` | 0.0 | 行偏移量（砖墙效果=0.5） |
| `Offset_Random` | 0.0 | 偏移随机 |
| `Pattern_Type` | 9 | 图案类型(1=方形,2=圆,5=输入图案,9=方形灰度渐变) |
| `Position_Random` | (0,0) | 位置随机抖动 |
| `LuminanceByNumber` | False | 每块不同灰度（用于着色变化！） |
| `Free_Rotation` | 0.0 | 旋转角度 |
| `BlendingMode` | 0 | 混合模式(0=Alpha, 1=Add) |

**典型用法**:
- 瓷砖/砖墙排列: `Offset=0.5` + `Interstice=(缝宽)` + `LuminanceByNumber=True`
- 碎石分布: `Position_Random=(高)` + `ScaleVariation=(高)` + 多层不同参数叠加
- 木板排列: `Nb_X=1` + `Nb_Y=4` + `Offset=0.5`

---

### tile_sampler ⭐⭐

**引擎**: FX-Map (30 节点，比 tile_generator 复杂)
**特点**: 接受**自定义输入图案**（tile_generator 只能用内置形状）

**核心参数**:

| 参数 | 默认 | 说明 |
|------|------|------|
| `x_amount` / `y_amount` | 16 | 重复数 |
| `pattern` | 2 | 内置图案或输入 |
| `scale` | 0.8 | 图案缩放 |
| `scale_random` | 0.0 | 大小随机 |
| `position_random` | 0.0 | 位置随机 |
| `rotation` / `rotation_random` | 0 | 旋转/随机旋转 |
| `color_random` | 0.0 | 灰度随机变化 |
| `blending_mode` | 1(Add) | 混合模式 |
| `displacement_map_intensity` | 0.0 | 位移贴图强度 |

**vs tile_generator**: tile_sampler 更灵活（支持自定义输入+多种映射），但参数更多。

---

### splatter ⭐

**引擎**: FX-Map (4 节点)
**特点**: 自由散布，适合不规则分布

| 参数 | 说明 |
|------|------|
| `Pattern_size_width/height` | 图案大小（%） |
| `Grid_Number` | 网格分辨率 |
| `Disorder` | 位置随机程度 |
| `Rotation_Var` | 旋转随机 |
| `Size_Var` | 大小随机 |
| `PatternSize` | 图案类型 |

---

### splatter_circular

**引擎**: FX-Map
**特点**: 环形散布（碎石环、花瓣等）

| 参数 | 说明 |
|------|------|
| `Number` | 环上点数 (默认12) |
| `Radius` | 环半径 (默认0.25) |
| `CenterOrientation` | 朝向中心 |

---

### shape

**引擎**: FX-Map + 16 个子图引用
**特点**: 单个几何形状（圆、方、三角、星...），通常作为其他生成器的输入

| 参数 | 说明 |
|------|------|
| `Pattern` | 形状类型(1=方,2=盘,3=十字,4=钻石,5=Bell...) |
| `Size` | 大小 |
| `Angle` | 旋转 |

---

### polygon_1

**引擎**: FX-Map
**特点**: 多边形网格排列（六边形瓷砖等）

| 参数 | 说明 |
|------|------|
| `Sides` | 边数 (默认6=六边形) |
| `Explode` | 展开/分离程度 |
| `Gradient` | 渐变模式 |

---

### scratches_generator

**引擎**: FX-Map + 8 个 directionalwarp
**特点**: 随机划痕纹理，适合金属/磨损

| 参数 | 说明 |
|------|------|
| `scratches_amount` | 划痕数量 (默认2048) |
| `scratches_scale` | 划痕大小 |
| `mask_threshold` | 遮罩阈值 |

---

### brick_generator / weave_generator

**引擎**: Composite（纯原子节点组合，不用 FX-Map）
**特点**: 用 blend/transformation/levels 等组合实现

brick_generator 参数: `Bricks`(行列数), `Bevel`(倒角), `Gap`(缝宽), `Offset`(偏移)
weave_generator 参数: `tile_x/y`(密度), `shape`(形状), `weave`(编织模式), `gap`(间距)

---

## 二、噪波生成器（Noise Generators）

### perlin_noise / perlin_noise_zoom ⭐⭐⭐

**引擎**: FX-Map
**perlin_noise**: 标准 Perlin 噪波，有 `scale` 和 `disorder` 参数
**perlin_noise_zoom**: 可控距离的变种，参数为 `Distance`(视距) 和 `Disorder`

**最常用噪波**，几乎所有材质都以它为基础层。

---

### cells_1 / cells_2 / cells_3 / cells_4

**引擎**: FX-Map
**cells_1**: 最简（2 节点），基本细胞纹理
**cells_4**: 最复杂（14 节点），9 个 warp 产生丰富变形

参数: `scale`(密度), `disorder`(不规则度)

**适合**: 石材/碎石/有机物表面的颗粒结构

---

### voronoi ⭐

**引擎**: Pixel Processor（唯一用 PP 而非 FX-Map 的主流噪波）

| 参数 | 说明 |
|------|------|
| `scale` | 细胞大小 |
| `disorder` | 不规则度 |
| `distortion_intensity` | 变形强度 |
| `rounded_curve` | 圆润度 |
| `invert` | 反转 |
| `edge_thickness` | 边缘厚度 |

**为什么用 PP**: Voronoi 需要计算像素到种子点的距离，是纯数学运算，FX-Map 不擅长。

---

### fractal_sum_base

**引擎**: 大型 Composite (112 节点! 47 blend + 20 transformation)
**特点**: 多层噪波叠加（分形），不是基于 FX-Map 或 PP，而是通过大量 blend 叠加不同尺度的噪波。

参数: `Roughness`, `MinLevel`, `MaxLevel`, `GlobalOpacity`

---

### clouds_1 / gaussian_noise

**引擎**: FX-Map
**clouds_1**: 柔和的云状噪波（2 个 FX-Map 叠加）
**gaussian_noise**: 高斯分布随机噪波

---

## 三、特征纹理生成器（Specialty Generators）

### moisture_noise ⭐⭐

**引擎**: 3 个 FX-Map 叠加
**特点**: 模拟水渍/湿润效果，是做旧的核心节点
**参数**: `Pattern_size_width/height`, `Disorder`

---

### wood_fibers_1 / wood_fibers_2

**引擎**: FX-Map
**特点**: 方向性纤维纹理，专用于木材
**参数**: `Disorder`

---

### fibers_1 / fibers_2

**引擎**: FX-Map
**特点**: 通用纤维（纸张、布料）

---

### creased

**引擎**: 2 个 FX-Map + 2 个 directionalwarp
**特点**: 褶皱/折痕纹理
**参数**: `Warp_Intensity`, `Disorder`

---

### starburst

**引擎**: FX-Map
**特点**: 放射状纹理（爆裂效果、弹孔周围的裂纹）
**参数**: `Branches`(分支数), `BlurAmount`, `SizeMin/Max`

---

## 生成器选择决策树

```
需要什么类型的纹理？
│
├→ 规则重复图案
│   ├→ 简单形状排列 → tile_generator
│   ├→ 自定义形状排列 → tile_sampler
│   ├→ 多边形网格 → polygon_1
│   └→ 砖墙排列 → brick_generator
│
├→ 不规则散布
│   ├→ 面散布 → splatter
│   └→ 环形散布 → splatter_circular
│
├→ 噪波/随机纹理
│   ├→ 通用平滑噪波 → perlin_noise
│   ├→ 细胞/颗粒 → cells_1~4
│   ├→ 多边形细胞 → voronoi
│   ├→ 分形高频细节 → fractal_sum_base
│   └→ 柔和云状 → clouds_1
│
├→ 方向性纹理
│   ├→ 木纹 → wood_fibers_1/2
│   ├→ 通用纤维 → fibers_1/2
│   ├→ 划痕 → scratches_generator
│   └→ 编织 → weave_generator
│
└→ 做旧/风化
    ├→ 水渍 → moisture_noise
    ├→ 褶皱 → creased
    └→ 爆裂 → starburst
```

## 关键经验

1. **tile_generator 是万能的**: 调参数就能实现 60% 的图案需求
2. **多层叠加**: 专业材质通常用 3-6 个不同参数的生成器叠加
3. **FX-Map 是绝大多数生成器的底层**: 理解 FX-Map 就理解了 SD 的图案引擎
4. **只有 voronoi 用 Pixel Processor**: 因为需要逐像素距离计算
5. **fractal_sum_base 不用 FX-Map**: 而是通过 112 个原子节点的大型 blend 链实现分形
6. **参数化是关键**: 同一个 tile_generator 通过不同参数能生成瓷砖、碎石、木板等完全不同的图案
