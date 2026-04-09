---
name: sd-node-catalog
description: >
  SD 节点选型目录 + 动态查询。包含库节点的 sbs 文件名、输出端口、用途分类，
  供 AI 选择合适的纹理源。详细参数和端口通过动态查询获取（永远准确）。
  Use when AI needs to: (1) find the correct sbs filename for a library node,
  (2) choose appropriate noise/texture generators for a material,
  (3) dynamically query node params/ports before setting values.
  Substance Designer only (run_python).
metadata:
  artclaw:
    version: 0.3.0
    author: ArtClaw
    software: substance_designer
---

# SD 节点目录

## 设计原则

- **选型用静态目录**：sbs 文件名、输出端口名、用途分类 → 帮 Agent 决定"用哪个节点"
- **参数/端口用动态查询**：创建节点后实时查询 → 永远准确，不怕 SD 版本变化
- **为什么不静态记录参数？** 因为 SD 的"参数"和"连接端口"都是 Input 属性，静态记录容易混淆（如 blend 的 `opacity` 实际是连接端口，`opacitymult` 才是标量参数）

---

## 动态查询：节点参数和端口 🔴

**创建节点后，用以下代码查询可设参数和连接端口：**

```python
# === 查询节点的可设参数（有默认值的）和连接端口（值为 None 的） ===
params = {}
ports = []
for p in node.getProperties(SDPropertyCategory.Input):
    pid = p.getId()
    if pid.startswith("$"):
        continue
    v = node.getPropertyValue(p)
    val = v.get() if v else None
    if val is None:
        ports.append(pid)      # 连接端口（只能连线，不能 setInputPropertyValueFromId）
    else:
        params[pid] = val      # 可赋值参数
print(f"可设参数: {list(params.keys())}")
print(f"连接端口: {ports}")

# 查询输出端口
outputs = [p.getId() for p in node.getProperties(SDPropertyCategory.Output)]
print(f"输出端口: {outputs}")
```

> **⚠️ 连接端口（`val is None`）不能用 `setInputPropertyValueFromId` 赋值，会抛 `DataIsReadOnly`！**
> 连接端口只能通过 `src.newPropertyConnectionFromId(out_port, dst, port_name)` 接收连线。

---

## 原子节点速查

原子节点用 `graph.newNode(definition_id)` 创建。

| 节点 | 定义 ID | 用途 |
|------|---------|------|
| Blend | `sbs::compositing::blend` | 混合两个输入 |
| Levels | `sbs::compositing::levels` | 色阶/对比度调整 |
| Normal | `sbs::compositing::normal` | 灰度→法线图 |
| Warp | `sbs::compositing::warp` | 扭曲变形 |
| DirectionalWarp | `sbs::compositing::directionalwarp` | 方向扭曲 |
| Uniform | `sbs::compositing::uniform` | 纯色（灰度/彩色） |
| Output | `sbs::compositing::output` | PBR 输出通道 |
| Curve | `sbs::compositing::curve` | 曲线调整 |
| HSL | `sbs::compositing::hsl` | HSL 颜色调整 |
| Blur | `sbs::compositing::blur` | 模糊 |
| Sharpen | `sbs::compositing::sharpen` | 锐化 |
| Transform 2D | `sbs::compositing::transformation` | 平移/旋转/缩放 |
| Gradient Map | `sbs::compositing::gradient` | 灰度→彩色渐变映射 |
| Emboss | `sbs::compositing::emboss` | 浮雕 |

> **⛔ 不存在的原子节点（newNode 返回 None）：**
> `sbs::compositing::invert`、`sbs::compositing::edgedetect`、`sbs::compositing::histogramselect`
> 反转用 Levels（黑白点互换）或 Blend(Subtract)+Uniform(白) 实现。

---

## 库节点选型目录

库节点从 SD 安装目录 `.sbs` 文件加载。**输出端口是稳定的，可以信任此表；参数动态查询。**

### noise — 噪波/纹理生成

| 节点 | sbs 文件 | 输出端口 | 用途 |
|------|---------|----------|------|
| perlin_noise | `noise_perlin_noise.sbs` | `output` | 通用有机噪波 |
| clouds_1~3 | `noise_clouds_1.sbs` | `output` | 柔和低频变化 |
| cells_1~4 | `noise_cells_1.sbs` | `output` | 颗粒/细胞纹理 |
| voronoi | `noise_voronoi.sbs` | `output` | 泰森多边形/裂纹 |
| fractal_sum_base | `noise_fractal_sum_base.sbs` | `output` | 复杂分形 |
| gaussian_noise | `noise_gaussian_noise.sbs` | `output` | 均匀随机噪点 |
| white_noise | `white_noise.sbs` | `White_Noise` | 纯白噪声 |
| plasma | `noise_plasma.sbs` | `output` | 等离子纹理 |
| creased | `noise_creased.sbs` | `output` | 褶皱纹理 |
| crystal_1~2 | `noise_crystal_1.sbs` | `output` | 晶体纹理 |
| fluid | `noise_fluid.sbs` | `output` | 流体纹理 |
| perlin_noise_zoom | `perlin_noise_zoom.sbs` | `Noise_Zoom` | 可缩放柏林噪波 |

### directional — 方向性纹理

| 节点 | sbs 文件 | 输出端口 | 用途 |
|------|---------|----------|------|
| wood_fibers_1 | `wood_fibers_1.sbs` | `Wood_Fibers` | 木纹纤维 |
| wood_fibers_2 | `wood_fibers_2.sbs` | `Wood_Noise` | 木纹变体 |
| fibers_1 | `fibers_1.sbs` | `Rope` | 绳索/纤维 |
| fibers_2 | `fibers_2.sbs` | `Fiber` | 纤维变体 |
| directionnal_noise | `directionnal_noise.sbs` | `Directionnal_Noise` | 通用方向性噪波 |
| directional_noise_1~4 | `noise_directional_noise_1.sbs` | `output` | 可控角度方向噪波 |
| directional_scratches | `noise_directional_scratches.sbs` | `output` | 方向性划痕 |
| messy_fibers_1~3 | `noise_messy_fibers_1.sbs` | `output` | 杂乱纤维 |

### pattern — 规则图案

| 节点 | sbs 文件 | 输出端口 | 用途 |
|------|---------|----------|------|
| tile_generator | `tile_generator.sbs` | `TileGenerator` | **最强大的图案生成器** |
| shape | `shape.sbs` | `Simple_Shape` | 基础几何形状 |
| brick_generator | `brick_generator.sbs` | `Bricks_Generator` | 砖块图案 |
| pattern_stripes | `pattern_stripes.sbs` | `Stripes` | 条纹 |
| pattern_fibers_1~2 | `pattern_fibers_1.sbs` | `output` | 纤维图案 |

### weave — 编织图案

| 节点 | sbs 文件 | 输出端口 | 用途 |
|------|---------|----------|------|
| weave_1 | `weave_1.sbs` | 动态查询 | 编织 v1 |
| weave_2 | `weave_2.sbs` | `Weave_2` | 编织 v2（布料常用） |
| weave_3 | `weave_3.sbs` | 动态查询 | 编织 v3 |
| weave_4 | `weave_4.sbs` | 动态查询 | 编织 v4 |
| weave_generator | `weave_generator.sbs` | 动态查询 | 编织生成器（可配置） |
| pattern_weave_1~2 | `pattern_weave_1.sbs` | 动态查询 | 编织图案 |

### grunge — 做旧/污渍

| 节点 | sbs 文件 | 输出端口 | 用途 |
|------|---------|----------|------|
| grunge_map_001~005 | `noise_grunge_map_001.sbs` | `output` | 做旧纹理 |
| dirt_1~5 | `noise_dirt_1.sbs` | `output` | 污渍/灰尘 |

### gradient — 渐变

| 节点 | sbs 文件 | 输出端口 | 用途 |
|------|---------|----------|------|
| gradient_linear_1 | `gradient_linear_1.sbs` | `Simple_Gradient` | 线性渐变 |
| gradient_linear_2 | `gradient_linear_2.sbs` | `Simple_Gradient_2` | 渐变变体 |
| gradient_linear_3 | `gradient_linear_3.sbs` | `output` | 渐变 v3 |

### utility — 工具

| 节点 | sbs 文件 | 输出端口 | 用途 |
|------|---------|----------|------|
| ambient_occlusion_2 | `ambient_occlusion_2.sbs` | `ambient_occlusion` | Height→AO |
| histogram_range | `histogram_range.sbs` | `output` | Height 归一化 |
| non_uniform_blur | `non_uniform_blur.sbs` | `Non_Uniform_Blur` | 各向异性模糊（消除几何硬边→有机质感） |
| replace_color | `replace_color.sbs` | `ToTargetColor` | 精确替换指定颜色(SourceColor→TargetColor) |
| mosaic_grayscale | `mosaic.sbs` | `Mosaic` | 离散化色块（需要 Source + Effect 两个输入） |
| mesh_1 | `mesh_1.sbs` | `Mesh` | 基础网格纹理（fabric_009 编织骨架源） |
| grayscaleconversion | **原子节点** `sbs::compositing::grayscaleconversion` | `unique_filter_output` | 彩色→灰度（channelsweights 控制 RGB 权重） |
| shuffle | **原子节点** `sbs::compositing::shuffle` | `unique_filter_output` | 通道重组（需要 input1 + input2） |

### pbr_converter — PBR 管线转换

| 节点 | sbs 文件 | 输出端口 | 用途 |
|------|---------|----------|------|
| basecolor_metallic_roughness_to_diffuse_specular_glossiness | `pbr_converter.sbs` | 动态查询 | Metal/Rough → Spec/Gloss 转换 |

---

## 选型指南

| 材质类型 | 推荐纹理源 |
|---------|-----------|
| 木纹 | `wood_fibers_1/2` + `noise_clouds`（扰动） |
| 金属 | `directional_noise/scratches` + `fractal_sum_base` |
| 石材 | `cells` + `clouds` |
| 布料/编织 | **高质量**: `mesh_1` + `transformation`链(fabric_009方法) + `gradient_linear` + `non_uniform_blur`；**快速**: `weave_2` + `fibers` + `gradient_linear` |
| 砖墙 | `brick_generator` + `tile_generator` |
| 瓷砖 | `tile_generator` + `shape` |
| 做旧 | `grunge_map` + `dirt` + `moisture_noise` |

---

## 使用流程

1. **选节点**：查上表确定 sbs 文件名和输出端口
2. **加载创建**：`loadUserPackage(sbs_path)` → `newInstanceNode(res)`
3. **动态查询参数**：用上面的查询代码获取可设参数和连接端口
4. **设参连线**：`setInputPropertyValueFromId` 设参数，`newPropertyConnectionFromId` 连端口
5. **截图检查**：`save_preview(node, "label")` 看输出效果
