---
name: sd-learned-recipes
description: >
  从 SD 内置 PBR 材质逆向分析的材质配方库。包含 10 个材质的节点图结构、
  库节点使用、管线特征，以及跨材质的通用模式总结。
  Use when AI needs to: (1) choose appropriate nodes for a material type,
  (2) reference professional material graph structure,
  (3) understand common SD material building patterns,
  (4) select texture sources for different material categories.
  Substance Designer only (run_python).
metadata:
  artclaw:
    version: 0.1.0
    author: ArtClaw
    software: substance_designer
---

# SD 材质配方库

> 从 SD 12.1.0 内置 PBR 材质逆向分析，10 个材质的真实图结构。
> **制作材质前参考此库，选择正确的纹理源和管线设计。**

## 配方文件

`recipes/` 目录下：
- `_overview.md` — **总览（先读这个）**：跨材质模式总结、纹理源选择规律
- `wood_american_cherry.md` — 木材配方详解（152 节点）
- `metal_002.md` — 金属配方详解（120 节点）

## 关键发现（必读）

### 1. Blend 是 SD 材质的核心
每个材质 30-41 个 blend 节点。**SD 材质制作 = blend 叠加的艺术。**

### 2. 着色用 gradient 渐变映射
每材质 10-13 个 gradient 节点做灰度→颜色映射，是最主流的着色方式。
replace_color 库节点是第二选择。

### 3. Levels 精细控制信号范围
每材质 18-30 个 levels，几乎每个处理环节前后都有 levels 调整。

### 4. 材质类别→纹理源对照表

| 材质 | 主纹理源 | 辅助 |
|------|----------|------|
| 木材 | wood_fibers, directionnal_noise | perlin_noise, bnw_spots |
| 金属 | creased, scratches | perlin_noise, dirt |
| 混凝土 | clouds, fractal_sum | perlin_noise, moisture_noise |
| 砖 | tile_generator, cells | clouds, crystal, shape |
| 布料 | weave, shape | gradient_linear |
| 碎石 | tile_generator, cells | clouds, bnw_spots |

### 5. 输出通道标准模式

| 通道 | 来源 |
|------|------|
| BaseColor | 灰度纹理 → gradient/replace_color → levels |
| Normal | 灰度高度图 → normal 节点(仅1个) → levels |
| Roughness | levels 或 blend |
| Metallic | uniform(非金属=0) 或 blend(金属有遮罩) |
| Height | histogram_range 库节点 |
| AO | ambient_occlusion_2 库节点 |

## 使用方法

```python
# 在制作材质前，读取参考配方
import os, json

recipes_dir = os.path.expanduser(r"~\.openclaw\skills\sd-learned-recipes\recipes")
# 先读总览
with open(os.path.join(recipes_dir, "_overview.md"), "r", encoding="utf-8") as f:
    overview = f.read()
# 再读具体材质配方
with open(os.path.join(recipes_dir, "wood_american_cherry.md"), "r", encoding="utf-8") as f:
    recipe = f.read()
```
