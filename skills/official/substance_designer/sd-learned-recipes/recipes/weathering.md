# 做旧/风化/污渍叠加配方

> 从 30 个内置材质提炼的做旧效果通用模式。
> 做旧层是区分"CG感"和"真实感"的关键。

## 核心发现

80%的内置材质都有 2-5 层做旧效果叠加。做旧效果主要通过以下方式实现：
1. **专用噪波库节点**提供做旧遮罩
2. **Blend**（通常用 Multiply/Overlay 混合模式）叠加到基础纹理上
3. 做旧同时影响 **BaseColor + Roughness**（脏的地方更暗且更粗糙）

## 做旧库节点速查表

| 库节点 | 使用率 | 效果 | 典型应用 |
|--------|--------|------|----------|
| **moisture_noise** | 80% | 湿润/水渍斑驳 | 混凝土水痕、金属水渍 |
| **bnw_spots_1/2/3** | 60% | 随机斑点/瑕疵 | 表面小斑点、微观瑕疵 |
| **dirt_1/2/3/4/5/6** | 40% | 灰尘/泥土/划痕 | 积灰、泥渍、使用磨损 |
| **scratches_1/2/4** | 30% | 划痕纹理 | 金属划痕、表面磨损 |
| **clouds_2/3** | 30% | 云朵状变化 | 大面积色调变化、不均匀性 |
| **fur_1/2** | 15% | 毛绒/纤维杂质 | 纸板纤维、混凝土气孔 |
| **grunge_map_00x** | 10% | 综合做旧纹理 | 整体做旧叠加 |

## 三级做旧策略

### 第 1 级：大面积色调变化（必做）

**目标**: 打破均匀感，增加自然的明暗变化。

```
[moisture_noise 或 clouds_2] → levels(调整对比度)
    ↓
[基础纹理] → Blend(opacity=做旧遮罩, mode=Multiply) → 有大面积变化的纹理
```

**影响通道**: BaseColor（变暗）+ Roughness（变粗糙）

### 第 2 级：中频瑕疵（推荐）

**目标**: 添加中等尺度的不均匀性——水渍、污渍、局部变色。

```
[bnw_spots_1/2] → levels(控制密度和大小)
    ↓
[第1级结果] → Blend(opacity=瑕疵遮罩) → 有瑕疵的纹理
```

**影响通道**: BaseColor + Roughness

### 第 3 级：微观细节（高质量材质）

**目标**: 微小的表面瑕疵——灰尘颗粒、指纹、微划痕。

```
[dirt_3/scratches_1] → levels + blur(柔化边缘)
    ↓
[第2级结果] → Blend(低opacity) → 最终纹理
```

**影响通道**: 主要影响 Roughness，轻微影响 BaseColor

## 做旧对各通道的影响

| 通道 | 做旧效果 | 典型做法 |
|------|----------|----------|
| **BaseColor** | 变暗/变脏 | Blend(Multiply) + 暗色遮罩 |
| **Roughness** | 变粗糙 | Blend(Add/Screen) + 粗糙度遮罩 |
| **Normal** | 通常不受做旧影响 | — |
| **Height** | 通常不受做旧影响 | 轻微凹坑可选 |
| **Metallic** | 金属氧化/锈蚀 | 仅金属材质：Blend(遮罩)降低金属度 |

## 各类别做旧重点

### 混凝土
- **必做**: moisture_noise（水渍必备）+ bnw_spots（气孔斑点）
- **可选**: dirt 系列（灰尘积累）

### 金属
- **必做**: scratches（划痕是金属核心特征）+ moisture_noise
- **可选**: dirt（积灰）、grunge_map（综合做旧）

### 砖墙
- **必做**: moisture_noise（砖缝湿润）+ bnw_spots（砖面斑驳）
- **可选**: fractal_sum（大面积色调变化）

### 瓷砖
- **必做**: moisture_noise（缝隙水渍）+ dirt（缝隙积灰）
- **可选**: scratches（表面磨损）

### 木材
- **必做**: bnw_spots（木材瑕疵/节疤）+ moisture_noise
- **可选**: dirt_4（水平划痕/使用痕迹）

### 布料
- **可选做旧较少**: Creases_Filter（褶皱）+ 轻微 scratches

## AI 生成材质的做旧推荐

### 最简做旧（2 步）
1. `moisture_noise` → levels → Blend(opacity) 到 BaseColor
2. 同一遮罩 → levels(不同范围) → Blend 到 Roughness

### 标准做旧（4 步）
1. moisture_noise → 大面积色调变化
2. bnw_spots_1 → 中频瑕疵
3. 将两个遮罩分别 Blend 到 BaseColor 和 Roughness
4. Levels 微调最终范围

### 关键提醒
- **做旧遮罩必须是灰度**（库节点输出本身就是灰度）
- **用 Levels 控制做旧强度**（而不是直接改 Blend opacity 参数）
- **同一个做旧遮罩应同时影响多个通道**（保持物理一致性）
