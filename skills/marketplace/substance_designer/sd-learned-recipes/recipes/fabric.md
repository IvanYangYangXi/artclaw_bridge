# 布料/织物配方

> 从 3 个内置布料材质（fabric_002/009/025）逆向分析。
> 布料是 SD 内置材质中节点数最少的类别（51-105），但结构独特。

## 布料的物理特征

- **结构**: 编织图案（经纬交织），周期性重复
- **表面**: 纤维质感，微观起伏
- **颜色**: 相对均匀，可能有渐变/褶皱暗区
- **特殊**: 褶皱（creases）是布料独有的特征

## 三种布料子类型

| 材质 | 节点数 | 编织方式 | 核心特征 |
|------|--------|----------|----------|
| fabric_002 | 71 | weave_2 库节点 | 简单编织 + 褶皱 |
| fabric_009 | 105 | mosaic_grayscale 构建 | 复杂图案 + 多层着色 |
| fabric_025 | 51 | tile_generator + brick_generator | 规则编织 + 简洁 |

## 核心纹理源

| 库节点 | 用途 | 重要性 |
|--------|------|--------|
| **weave_2** | 编织图案生成器 | fabric_002 核心 |
| **shape** | 基础形状（编织单元） | ★★ |
| **gradient_linear_1/2** | 渐变遮罩（褶皱阴影） | ★★ |
| **Creases_Filter** | 褶皱效果（布料独有！） | ★★ |
| **perlin_noise_zoom** | 大尺度变化 | ★ |
| **mosaic_grayscale** | 马赛克图案 | fabric_009 |
| **herb_1** | 纤维细节 | ★ |
| **tile_generator** | 规则重复 | fabric_025 |
| **brick_generator** | 编织排列 | fabric_025 |

## 布料管线模式

### 编织结构层（核心）

**方案 A: 使用 weave_2 库节点（最简单）**
```
weave_2 → 编织图案（灰度）
shape → 编织单元形状
gradient_linear_1/2 → 方向性渐变
blend(叠加) → 编织纹理
```

**方案 B: 手工构建（更灵活）**
```
tile_generator / brick_generator → 重复单元排列
transformation(多个) → 旋转/缩放/偏移 构建经纬线
blend(叠加) → 编织图案
```

**方案 C: 复杂图案（fabric_009 风格）**
```
mosaic_grayscale → 基础图案
多个 transformation → 偏移组合
gradient(多个) → 图案内着色
warp → 自然弯曲
```

### 褶皱层（布料独有）

```
Creases_Filter(库节点) → 褶皱遮罩
  → blend 到 BaseColor（褶皱处变暗）
  → blend 到 Roughness（褶皱处可能更光滑/粗糙）
  → blend 到 Normal（褶皱凹凸）
```

### 着色特点

布料着色相对简单（颜色变化少）：
- 主色调: gradient 或 Blend(两种 uniform 色)
- 渐变阴影: gradient_linear 提供方向性明暗
- HSL 微调

## fabric_009 管线详解（最复杂的布料）

### BaseColor（75 节点，深度 19 层）

**特殊点**:
- `mosaic_grayscale` 生成马赛克图案（非典型布料做法）
- 大量 `transformation`（15 个！构建复杂编织图案）
- `non_uniform_blur_grayscale` 柔化图案边缘
- 两个 `replace_color` 着色层
- `perlin_noise_zoom` × 2 增加自然变化
- `bnw_spots_1 + fractal_sum_1` 做旧层

### Height/Normal/AO 共享管线

与 BaseColor **共享大量节点**（71/75 节点重叠！）
布料的高度图 = 编织图案本身的凹凸。

## AI 生成布料的推荐步骤

### 简单编织布料（~25 节点）

1. `weave_2` → 编织图案
2. `gradient_linear_1` → 方向性渐变遮罩
3. blend(编织 + 渐变) → 灰度纹理
4. 着色: Blend(Uniform暗色 + Uniform亮色 + opacity=灰度)
5. `Creases_Filter` → 褶皱层 → blend 到各通道
6. 输出: Height/Normal/AO 分叉 + Roughness + Metallic(0)

### 带图案布料（~50 节点）

1. `tile_generator` + `shape` → 构建编织单元
2. 多个 `transformation` → 组合经纬线图案
3. 用 `replace_color` 着不同颜色区域
4. `herb_1` → 纤维微细节叠加
5. `Creases_Filter` → 褶皱
6. 输出

## 关键参数经验

- **Roughness 范围**: 0.7-0.95（布料很粗糙）
- **Metallic**: 始终为 0
- **Height 范围**: 编织凹凸感明显但绝对高度小
- **Normal**: 编织图案的法线是核心视觉特征
- **关键**: `transformation` 节点大量使用（平均 10+ 个），用于构建编织图案的旋转/偏移
