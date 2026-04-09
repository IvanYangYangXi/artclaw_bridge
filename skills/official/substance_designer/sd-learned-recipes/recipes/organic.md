# 碎石/纸张/纸板配方

> 从 3 个内置有机材质（gravel, paper_005, cardboard_001）逆向分析。
> 这三个材质虽然物理特征不同，但共享"颗粒/纤维散布"的管线逻辑。

## 物理特征对比

| 材质 | 节点数 | 特征 | 核心结构 |
|------|--------|------|----------|
| gravel | 144 | 大小不一的石子散布 | tile_generator × 6 + cells_1 |
| paper_005 | 146 | 纤维纸张，半透明 | fibers_2 + directionalwarp |
| cardboard_001 | 190 | 瓦楞纸板，层状结构 | cells_4 + fur_1 + directionalwarp |

## 碎石（Gravel）

### 核心纹理源

| 库节点 | 数量 | 用途 |
|--------|------|------|
| **tile_generator** | **6** | 石子分布（不同大小层级！） |
| **cells_1** | 2 | 石子形状的细胞纹理 |
| **clouds_2/3** | 2 | 石子表面变化 |
| **bnw_spots_1/2** | 2 | 微观表面瑕疵 |
| **invert_grayscale** | 1 | 反转（石子凸起→缝隙凹陷） |

### 碎石管线核心逻辑

碎石用 **6 个 tile_generator** 的原因：多尺度石子分布

```
tile_generator #1 → 大石子分布（少量，大尺寸）
tile_generator #2 → 中石子分布
tile_generator #3 → 小石子填充
tile_generator #4-6 → 形状变化/随机偏移/颜色随机
    ↓
cells_1 → 石子的圆润形状
    ↓
多层 blend 叠加（50 个 blend！最多的材质之一）
warp × 12 → 自然不规则感
blur × 12 → 柔化石子边缘
    ↓
着色: gradient × 6 + hsl × 7 → 每颗石子不同颜色
```

### BaseColor 管线（89 节点，深度 22 层）

底层 tile_generator 生成多尺度分布 → cells_1 提供石子形状 → 大量 warp 和 blur 柔化 → gradient/hsl 着色。

**关键发现**: 碎石的 `hsl` 使用量异常高（7 个），用于每颗石子的色相偏移。

### AI 生成碎石推荐（~40 节点）

1. `tile_generator` #1 → 大石子分布
2. `tile_generator` #2 → 小石子填充
3. `cells_1` → 石子圆润形状
4. blend 叠加 + warp 扭曲 → 灰度高度图
5. 着色: 多个 Blend 层（深灰/棕/米色）
6. `bnw_spots_1` → 表面瑕疵
7. 输出分叉 + Roughness(高，0.7-0.95) + Metallic(0)

---

## 纸张（Paper_005）

### 核心纹理源

| 库节点 | 用途 |
|--------|------|
| **fibers_2** | 纸张纤维（核心！） |
| **clouds_1** | 纤维密度变化 |
| **herb_1** | 杂质颗粒 |
| **checker_1** | 网格图案（纸张水印/压印） |
| **waveform_1** | 波纹（纸张表面起伏） |
| **gradient_linear_2** × 2 | 渐变遮罩 |
| **non_uniform_blur** × 3 | 柔化纤维边缘 |

### 纸张管线核心逻辑

```
fibers_2 → 纤维方向纹理
checker_1 → 网格结构
waveform_1 → 表面波纹
    ↓
directionalwarp × 5 → 纤维方向变形（纸张也有方向性！）
blur × 8 → 柔化
blend × 48 → 多层叠加
    ↓
gradient × 12 → 着色（纸张黄白色调）
non_uniform_blur → 柔化色彩过渡
```

### 特殊：Opacity 通道

paper_005 是唯一有 **opacity** 输出的材质（纸张半透明/穿孔）。

### AI 生成纸张推荐（~35 节点）

1. `fibers_2` → 纤维纹理
2. `clouds_1` → 密度变化
3. `directionalwarp` → 纤维方向
4. blend 叠加 → 灰度纹理
5. 着色: Blend(Uniform米白 + Uniform浅黄 + opacity=灰度)
6. 输出 + Roughness(高，0.7-0.9) + Metallic(0)

---

## 纸板（Cardboard_001）

### 核心纹理源

| 库节点 | 用途 |
|--------|------|
| **cells_4** | 瓦楞结构 |
| **fur_1** | 纤维杂质 |
| **crystal_1** | 压痕纹理 |
| **grunge_map_009** | 做旧 |
| **replace_color** × 4 | 着色（使用最多！） |

### 纸板管线核心逻辑

纸板是节点最多的材质之一（190 个），因为：
- **directionalwarp × 15**: 大量方向性变形（瓦楞纸的波纹结构）
- **blend × 52**: 最多的 blend 叠加
- **gradient × 17**: 最多的着色层
- **transformation × 18**: 大量平铺/缩放调整

### AI 生成纸板推荐（~40 节点）

1. `cells_4` → 瓦楞基础结构
2. `fur_1` → 纤维层
3. 多个 `directionalwarp` → 波纹方向
4. blend 叠加 → 灰度纹理
5. `replace_color` × 2 → 纸板棕色着色
6. `grunge_map_009` → 做旧
7. 输出 + Roughness(高) + Metallic(0)

## 共同特征

这三个材质的共同点：
1. **Roughness 都很高**（0.7-0.95）
2. **Metallic 都为 0**
3. **大量 blend 叠加**（48-52 个）
4. **有方向性**（纸张纤维/纸板瓦楞/碎石无，但有多尺度分布）
5. **着色层丰富**（gradient 6-17 个 + replace_color 多个）
