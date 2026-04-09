# SD 内置 PBR 材质配方总览

> 从 SD 12.1.0 全部 30 个内置 PBR 材质逆向分析。
> **制作材质前参考此库，选择正确的纹理源和管线设计。**

## 配方索引

| 文件 | 内容 | 适用场景 |
|------|------|----------|
| `_overview.md` | 本文件：跨材质统计 + 选择指南 | 开始前必读 |
| `output_pipeline.md` | 输出通道标准管线 | 所有材质通用 |
| `coloring.md` | 着色管线：灰度→彩色 | 需要 BaseColor 时 |
| `weathering.md` | 做旧/风化/污渍叠加 | 需要真实感时 |
| `concrete.md` | 混凝土/水泥配方 | 10 个混凝土材质总结 |
| `metal.md` | 金属配方 | 5 个金属材质总结 |
| `tile.md` | 瓷砖/地砖配方 | 5 个瓷砖材质总结 |
| `brick.md` | 砖墙配方 | 2 个砖墙材质总结 |
| `fabric.md` | 布料/织物配方 | 3 个布料材质总结 |
| `wood.md` | 木材/木板配方 | 2 个木材材质总结 |
| `organic.md` | 碎石/纸张/纸板配方 | 3 个有机材质总结 |

## 30 材质统计摘要

| 材质 | 节点数 | 库节点 | 类别 |
|------|--------|--------|------|
| bricks_001 | 144 | 24 | brick |
| bricks_005 | 107 | 19 | brick |
| cardboard_001 | 190 | 23 | organic |
| classic_brown_concrete | 41 | 9 | concrete |
| concrete_002 | 98 | 22 | concrete |
| concrete_005 | 194 | 33 | concrete |
| concrete_006 | 151 | 27 | concrete |
| concrete_010 | 133 | 11 | concrete |
| concrete_011 | 113 | 18 | concrete |
| concrete_044 | 92 | 14 | concrete |
| concrete_070 | 49 | 11 | concrete |
| concrete_pavement | 100 | 19 | concrete |
| fabric_002 | 71 | 9 | fabric |
| fabric_009 | 105 | 17 | fabric |
| fabric_025 | 51 | 11 | fabric |
| gravel | 144 | 16 | organic |
| metal_002 | 120 | 19 | metal |
| metal_003 | 114 | 17 | metal |
| metal_006 | 97 | 19 | metal |
| metal_plate_001 | 85 | 24 | metal |
| metal_plate_004 | 148 | 28 | metal |
| old_painted_planks | 170 | 24 | wood |
| paper_005 | 146 | 22 | organic |
| rough_concrete_with_lines | 78 | 12 | concrete |
| tiles_002 | 129 | 19 | tile |
| tiles_003 | 121 | 19 | tile |
| tiles_008 | 149 | 22 | tile |
| tiles_011 | 139 | 22 | tile |
| tiles_025 | 130 | 22 | tile |
| wood_american_cherry | 152 | 17 | wood |

## 全局库节点使用排行（Top 30）

| 排名 | 库节点 | 引用次数 | 角色 |
|------|--------|----------|------|
| 1 | **tile_generator** | 50 | 图案骨架生成（砖/瓷砖/碎石分布） |
| 2 | **replace_color** | 43 | 着色主力（灰度→指定颜色映射） |
| 3 | ambient_occlusion_2 | 30 | AO 通道标配（每个材质必有） |
| 4 | histogram_range | 30 | Height 通道标配（归一化范围） |
| 5 | BMR_to_DSG | 30 | PBR→漫反射/高光转换（每个材质必有） |
| 6 | **moisture_noise** | 24 | 风化/湿润效果（80%材质使用） |
| 7 | **fractal_sum_base** | 20 | 通用分形噪波（高频细节） |
| 8 | **perlin_noise_zoom** | 19 | 大尺度噪波变化（63%材质） |
| 9 | non_uniform_blur_grayscale | 18 | 非均匀模糊（柔化边缘/过渡） |
| 10 | perlin_noise_1 | 15 | 标准柏林噪波 |
| 11 | clouds_2 | 13 | 云朵噪波（中频变化） |
| 12 | bnw_spots_2 | 13 | 黑白斑点（微观瑕疵） |
| 13 | noise_upscale_1 | 13 | 噪波放大（细节增强） |
| 14 | histogram_scan | 13 | 直方图扫描（选区/遮罩） |
| 15 | bnw_spots_1 | 12 | 黑白斑点（不同分布） |
| 16 | scratches_1 | 12 | 划痕（金属核心纹理） |

## 按类别的核心纹理源

| 类别 | 主纹理源（必选） | 辅助纹理（可选） | 关键特征 |
|------|------------------|------------------|----------|
| **混凝土** | tile_generator, perlin_noise_1 | moisture_noise, non_uniform_blur | 粗糙表面 + 湿润斑驳 |
| **金属** | scratches_1, fractal_sum_base | histogram_scan, moisture_noise | 划痕 + 金属反射变化 |
| **砖墙** | tile_generator, fractal_sum_base | replace_color, gaussian_spots | 规则排列 + 每块颜色变化 |
| **瓷砖** | tile_generator, polygon_1 | replace_color, moisture_noise | 几何图案 + 缝隙 |
| **布料** | shape/weave_2, gradient_linear | Creases_Filter, perlin_noise_zoom | 编织结构 + 褶皱 |
| **木材** | wood_fibers_2, tile_generator | directionnal_noise, bnw_spots | 年轮纤维 + 方向性 |
| **碎石** | tile_generator, cells_1 | clouds_2/3, bnw_spots | 散布颗粒 + 自然变化 |

## 核心模式发现

### 1. 所有材质的共享骨架

```
纹理源(库节点) → [levels调整] → [warp/directionalwarp扭曲] → [blend叠加] → [着色] → 输出
```

每个材质都遵循这个基本链路，区别在于纹理源选择和 blend 叠加策略。

### 2. Blend 是 SD 的核心操作

平均每材质 33 个 blend 节点（占总节点 25-35%）。
SD 材质制作 = **多层 blend 叠加的艺术**。

### 3. Height 是所有通道的基础

Height(高度图)通常是最深的管线，Normal/AO 直接从 Height 派生：
- Normal = Height → normal 节点
- AO = Height → ambient_occlusion_2 库节点
- BaseColor = Height + 着色层
- Roughness = Height 的变体 + 额外调整

### 4. 着色发生在管线末端

灰度纹理先完成所有处理（blend/warp/levels），最后才进入着色环节：
- gradient 渐变映射（最常用）
- replace_color 库节点（第二选择）
- HSL 调整（微调色相/饱和度）

### 5. 三种做旧/风化层

- **moisture_noise**: 湿润/水渍效果（80%使用率）
- **bnw_spots**: 表面瑕疵/斑点
- **dirt 系列**: 污渍/灰尘
