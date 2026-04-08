# SD 内置 PBR 材质总览

## 统计摘要

| 材质 | 节点数 | 库节点数 | 特征纹理源 |
|------|--------|---------|-----------|
| wood_american_cherry | 152 | 17 | wood_fibers_2, perlin_noise_zoom, directionnal_noise |
| metal_002 | 120 | 19 | creased, perlin_noise_1/2, scratches_1, dirt_1/6 |
| concrete_002 | 98 | 22 | clouds_1/2, fractal_sum_base/4, perlin_noise_zoom |
| bricks_001 | 144 | 24 | tile_generator, cells_1, clouds_2/3, crystal_1 |
| fabric_002 | 71 | 9 | weave_2, shape, gradient_linear_1/2 |
| tiles_002 | 129 | 19 | tile_generator, polygon_1, clouds_1/2, fractal_sum_base |
| gravel | 144 | 16 | tile_generator, cells_1, clouds_2/3, bnw_spots_1/2 |
| old_painted_planks | 170 | 24 | wood_fibers_1/2, tile_generator, cells_1/4, plasma |
| paper_005 | 146 | 22 | fibers_2, clouds_1, herb_1, checker_1, waveform_1 |
| cardboard_001 | 190 | 23 | cells_4, fur_1, crystal_1, grunge_map_009 |

## 跨材质模式总结

### 所有材质共有的库节点
- `ambient_occlusion_2` — 100% 使用率，AO 通道标配
- `histogram_range` — 100%，Height 通道标配
- `replace_color` — 80%，着色的主力工具
- `basecolor_metallic_roughness_to_diffuse_specular_glossiness` — 格式转换

### 最常用原子节点模式
- `blend` 是绝对主力（每材质 30-41 个），SD 材质制作 = blend 的艺术
- `levels` 紧随其后（18-30 个），精细控制每层信号范围
- `gradient` 是主要着色工具（10-13 个），灰度→颜色映射
- `warp` 用于自然感（1-17 个，木材最多）

### 材质类别 → 纹理源选择规律
| 材质类别 | 主纹理源 | 辅助纹理 |
|----------|----------|----------|
| 木材 | wood_fibers, directionnal_noise | perlin_noise, bnw_spots, dirt |
| 金属 | creased, scratches | perlin_noise, dirt, fractal_sum |
| 混凝土 | clouds, fractal_sum | perlin_noise, moisture_noise |
| 砖 | tile_generator, cells | clouds, crystal, shape |
| 布料 | weave, shape | gradient_linear |
| 瓷砖 | tile_generator, polygon | clouds, fractal_sum |
| 碎石 | tile_generator, cells | clouds, bnw_spots |
| 纸张 | fibers, clouds | herb, checker, perlin_noise |
| 纸板 | cells, fur, crystal | grunge_map, perlin_noise |

### 常用着色管线（灰度→BaseColor）
1. 灰度纹理 → `gradient` 渐变映射（最常用，13个/材质）
2. 灰度纹理 → `replace_color` 库节点
3. 灰度纹理 → `blend`(dark uniform + light uniform + opacity mask)（简单方案）

### 输出通道标准来源
| 通道 | 典型来源 |
|------|----------|
| BaseColor | levels (最终色阶调整后输出) |
| Normal | levels → normal 节点 (仅 1 个 normal 节点) |
| Roughness | levels 或 blend |
| Metallic | uniform(非金属=0) 或 blend(金属材质有遮罩) |
| Height | histogram_range 库节点 |
| AO | ambient_occlusion_2 库节点 |
