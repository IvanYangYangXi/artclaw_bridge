# 瓷砖配方

> 从 5 个内置瓷砖材质（tiles_002/003/008/011/025）逆向分析。
> 瓷砖类的核心特征：**规则几何图案 + 缝隙 + 表面细节**。

## 瓷砖的物理特征

- **形状**: 规则的几何重复图案（方形、六边形、马赛克等）
- **缝隙**: 瓷砖之间的灌缝（grout）——颜色深、粗糙度高、凹陷
- **表面**: 每块砖表面可能有不同颜色/纹理
- **高度**: 砖面高 + 缝隙低

## 核心纹理源

| 库节点 | 用途 | 重要性 |
|--------|------|--------|
| **tile_generator** | 瓷砖排列骨架（核心！平均 3-5 个） | ★★★ |
| **polygon_1** | 六边形/多边形瓷砖形状 | tiles_002/025 |
| **replace_color** | 每块砖着不同色（核心着色方式） | ★★★ |
| **perlin_noise_zoom** | 大尺度色调变化 | ★★ |
| **moisture_noise** | 缝隙湿润 + 表面水渍 | ★★ |
| **bnw_spots** | 表面瑕疵 | ★ |
| **clouds_1/2** | 中频变化 | ★ |
| **scratches_1** | 表面磨损 | 可选 |
| **crystal_1** | 石材纹理（仿石瓷砖） | 可选 |

## 瓷砖管线核心模式

### 骨架层：tile_generator 的多重角色

内置瓷砖材质通常有 **2-5 个 tile_generator**，分别用于：
1. **形状遮罩**: 砖面 vs 缝隙的二值遮罩
2. **颜色随机**: 每块砖一个随机灰度值，用于着色变化
3. **偏移随机**: 每块砖随机偏移，破坏完美规则感
4. **细节图案**: 砖面内部的次级图案

### 缝隙处理

```
tile_generator(形状遮罩) → levels(调整缝宽)
    ├→ invert → 缝隙遮罩
    │   → blend 到 BaseColor（缝隙更暗）
    │   → blend 到 Roughness（缝隙更粗糙）
    │   → blend 到 Height（缝隙凹陷）
    └→ 砖面遮罩
        → 限制纹理只出现在砖面上
```

### 每块砖着色变化

```
tile_generator(随机灰度) → replace_color(灰度→每块砖不同颜色)
                         → 或 gradient(灰度→颜色渐变)
```

## tiles_003 管线详解

### BaseColor（76 节点，深度 19 层）

**底层（D14-D19）**:
```
tile_generator × 4 (形状 + 随机 + 偏移 + 细节)
perlin_noise_zoom × 3 (不同尺度变化)
white_noise (随机种子)
fur_2 (表面微纤维)
```

**纹理处理（D7-D13）**:
```
多层 warp 扭曲（14 个 warp! 自然不规则感）
levels 控制每层范围
blend 叠加各层
directionalwarp 方向性变形
non_uniform_blur 柔化过渡
```

**着色（D3-D6）**:
```
replace_color → 每块砖着色
gradient × 12 → 多层渐变映射
blend 叠加着色层
hsl 微调
levels → OUT:BaseColor
```

### Height/Normal/AO 共享管线（14 节点，深度 7）

瓷砖的高度图相对简单：
```
tile_generator → 砖面遮罩
bnw_spots_3 → 表面微起伏
perlin_noise_zoom → 自然变化
warp + levels → 处理
→ histogram_range/normal/ambient_occlusion_2 三路输出
```

### Roughness（91 节点，最复杂的通道！）

瓷砖 Roughness 比 BaseColor 还复杂——因为需要区分：
- 砖面（光滑，roughness 低）
- 缝隙（粗糙，roughness 高）
- 划痕区域（中等 roughness）
- 污渍区域（高 roughness）

## AI 生成瓷砖的推荐步骤

### 简单方形瓷砖（~30 节点）

1. `tile_generator` #1 → 形状遮罩（砖面 vs 缝隙）
2. `tile_generator` #2 → 随机灰度（每块砖不同）
3. Blend(Uniform暗色 + Uniform亮色 + 随机灰度) → 基础着色
4. 缝隙遮罩 → Blend 到 BaseColor（缝隙变暗）
5. 缝隙遮罩 → Blend 到 Height（缝隙凹陷）
6. 输出: Height/Normal/AO 从高度图分叉
7. Roughness: 缝隙遮罩叠加粗糙度变化

### 带纹理的瓷砖（~60 节点）

在简单版基础上：
1. 增加 `perlin_noise_zoom`（大面积变化）
2. 用 `warp` 扭曲砖面纹理（增加自然感）
3. 用 `replace_color` 替代 Blend 着色（更丰富的颜色）
4. 增加 `bnw_spots`（表面瑕疵）
5. `moisture_noise` 做旧

## 关键参数经验

- **Roughness**: 砖面 0.2-0.5，缝隙 0.7-0.95
- **Metallic**: 始终为 0
- **Height**: 砖面高（~0.8），缝隙低（~0.2），对比度明显
- **tile_generator**: 控制砖的大小、间距、随机偏移是关键参数
