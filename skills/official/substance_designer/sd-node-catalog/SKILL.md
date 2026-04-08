---
name: sd-node-catalog
description: >
  SD 库节点目录：71 个常用库节点的端口名、参数、分类信息。
  AI 创建库节点前必须查询此目录，确认正确的 sbs 文件名、输出端口名和参数。
  Use when AI needs to: (1) find the correct sbs filename for a library node,
  (2) check output port names before connecting, (3) check parameter names and defaults,
  (4) choose appropriate noise/texture generators for a material.
  Substance Designer only (run_python).
metadata:
  artclaw:
    version: 0.1.0
    author: ArtClaw
    software: substance_designer
---

# SD 节点目录

> 71 个常用库节点的完整信息，从 SD 12.1.0 内置库自动扫描生成。
> **创建库节点前必须查此目录，确认端口名和参数。**

## 数据文件

`node_catalog.json` 位于本 Skill 目录下，JSON 格式：

```json
{
  "noise_perlin_noise": {
    "sbs_file": "noise_perlin_noise.sbs",
    "resource_id": "perlin_noise",
    "output_ports": ["output"],
    "params": {
      "scale": {"type": "int", "default": "32"},
      "disorder": {"type": "float", "default": "0.0"}
    },
    "category": "noise"
  }
}
```

## 查询方法

```python
import os, json

# 加载目录
cat_path = os.path.expanduser(r"~\.openclaw\skills\sd-node-catalog\node_catalog.json")
with open(cat_path, "r", encoding="utf-8") as f:
    catalog = json.load(f)

# 查询节点信息
info = catalog.get("noise_perlin_noise")
if info:
    print(f"sbs: {info['sbs_file']}")
    print(f"output_ports: {info['output_ports']}")
    print(f"params: {list(info['params'].keys())}")
```

## 按分类浏览

### noise (35 个) — 噪波/纹理生成
通用有机噪波、细胞纹理、分形等，材质的纹理基础。

| 常用节点 | 输出端口 | 关键参数 | 特点 |
|----------|----------|----------|------|
| noise_perlin_noise | `output` | scale, disorder | 通用有机噪波 |
| noise_clouds_1~3 | `output` | scale, disorder | 柔和低频变化 |
| noise_cells_1~4 | `output` | scale, disorder | 颗粒/细胞纹理 |
| noise_voronoi | `output` | scale, style, disorder | 泰森多边形 |
| noise_fractal_sum_base | `output` | Roughness, MinLevel, MaxLevel | 复杂分形 |
| noise_gaussian_noise | `output` | scale, disorder | 均匀随机噪点 |
| white_noise | `White_Noise` | (无参数) | 纯白噪声 |
| noise_plasma | `output` | scale, disorder | 等离子纹理 |
| noise_creased | `output` | scale, warp_intensity | 褶皱纹理 |
| noise_crystal_1~2 | `output` | scale, disorder | 晶体纹理 |
| noise_fluid | `output` | scale, warp_intensity | 流体纹理 |
| perlin_noise_zoom | `Noise_Zoom` | (查 catalog) | 可缩放柏林噪波 |

### directional (13 个) — 方向性纹理
有明确纹理方向的节点，适合木纹、纤维、划痕等材质。

| 常用节点 | 输出端口 | 关键参数 | 特点 |
|----------|----------|----------|------|
| wood_fibers_1 | `Wood_Fibers` | Disorder | **木纹专用** |
| wood_fibers_2 | `Wood_Noise` | (无参数) | 木纹变体 |
| fibers_1 | `Rope` | Tiling | 绳索/纤维 |
| fibers_2 | `Fiber` | Tiling | 纤维变体 |
| directionnal_noise | `Directionnal_Noise` | (无参数) | 通用方向性噪波 |
| noise_directional_noise_1~4 | `output` | scale, angle, disorder | 可控角度方向噪波 |
| noise_directional_scratches | `output` | scale, angle, pattern_amount | 方向性划痕 |
| noise_messy_fibers_1~3 | `output` | scale, angle, lines_number | 杂乱纤维 |

### pattern (8 个) — 规则图案
几何图案生成器。

| 常用节点 | 输出端口 | 关键参数 | 特点 |
|----------|----------|----------|------|
| tile_generator | `TileGenerator` | Nb_X, Nb_Y, Scale | **最强大的图案生成器** |
| shape | `Simple_Shape` | Pattern, Size | 基础几何形状 |
| brick_generator | `Bricks_Generator` | Bricks, Gap, Bevel | 砖块图案 |
| pattern_stripes | `Stripes` | Stripes, Width, Softness | 条纹 |
| pattern_fibers_1~2 | `output` | Tiling | 纤维图案 |
| horizontal_lines | 查 catalog | 查 catalog | 水平线 |
| stripes | 查 catalog | 查 catalog | 条纹变体 |

### grunge (10 个) — 做旧/污渍
磨损、脏污、划痕效果。

| 常用节点 | 输出端口 | 关键参数 |
|----------|----------|----------|
| noise_grunge_map_001~005 | `output` | balance, contrast, invert |
| noise_dirt_1~5 | `output` | scale, disorder |
| scratches | 查 catalog | 查 catalog |

### gradient (3 个) — 渐变
线性渐变，常用于遮罩或方向参考。

| 节点 | 输出端口 | 参数 |
|------|----------|------|
| gradient_linear_1 | `Simple_Gradient` | Tiling, rotation |
| gradient_linear_2 | `Simple_Gradient_2` | Tiling, rotation |
| gradient_linear_3 | `output` | Tiling, position, rotation |

### utility (2 个) — 工具节点

| 节点 | 输出端口 | 用途 |
|------|----------|------|
| ambient_occlusion_2 | `ambient_occlusion` | 从高度图生成 AO |
| histogram_range | `output` | 直方图范围调整 |

## 使用原则

1. **创建库节点前必查 catalog** — 确认 sbs_file 和 output_ports
2. **连接前确认端口名** — 不要猜，catalog 里有精确值
3. **选择纹理源时考虑材质特征**：
   - 木纹 → `wood_fibers_1/2` + `noise_clouds` (扰动)
   - 金属 → `noise_directional_noise/scratches`
   - 石材 → `noise_cells` + `noise_clouds`
   - 布料 → `fibers` + `tile_generator`
   - 做旧 → `noise_grunge_map` + `noise_dirt`
