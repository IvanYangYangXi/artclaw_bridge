# 混凝土配方

> 从 10 个内置混凝土材质（concrete_002~070, classic_brown, rough_concrete_with_lines, concrete_pavement）逆向分析。
> 混凝土是 SD 内置材质中变种最多的类别，节点数从 41（极简）到 194（极致）。

## 混凝土的物理特征

- **表面**: 粗糙、多孔、不均匀灰色/米色
- **纹理**: 低频大面积色调变化 + 中频气孔/砂粒 + 高频微细节
- **高度变化**: 平坦但有微起伏（浇筑板模缝、气孔凹坑）
- **特殊**: 可能有模板印痕（线条、接缝）、风化剥落

## 核心纹理源

| 库节点 | 用途 | 复杂度 |
|--------|------|--------|
| **tile_generator** | 浇筑板分块、表面图案骨架 | 中-高 |
| **perlin_noise_1/zoom** | 大面积色调变化和起伏 | 必选 |
| **fractal_sum_base/1/4** | 高频表面细节 | 推荐 |
| **moisture_noise** | 水渍斑驳 | 推荐 |
| **bnw_spots_1/2** | 气孔、斑点 | 推荐 |
| **clouds_1/2** | 中频不均匀性 | 可选 |
| **cells_1** | 大颗粒集料 | 高复杂度 |
| **dirt_3/6** | 积灰、污渍 | 做旧层 |

## 管线模式

### 极简混凝土（~41 节点，如 classic_brown_concrete）

```
fractal_sum_2/3 → levels
                    ├→ gradient(着色) → levels → OUT:BaseColor
                    ├→ normal → OUT:Normal
                    ├→ histogram_range → OUT:Height
                    └→ ambient_occlusion_2 → OUT:AO
uniform(0) → OUT:Metallic
levels(从高度派生) → OUT:Roughness
```

**特点**: 单一噪波源 + 极少处理，适合远景或简单场景。

### 标准混凝土（~100 节点，如 concrete_002）

```
阶段1 - 骨架：
  tile_generator → transformation → 板块分区遮罩
  polygon_1 → 几何接缝

阶段2 - 表面纹理：
  perlin_noise_zoom → warp → levels → 大面积起伏
  fractal_sum_4 → directionalwarp → 高频细节
  clouds_1/2 → 中频变化

阶段3 - 叠加混合：
  blend(骨架 + 纹理, 多层叠加)
  → levels(范围调整)

阶段4 - 着色：
  灰度 → gradient(多个, 不同色调范围)
  → replace_color(局部着色)
  → hsl(色调微调)
  → levels → OUT:BaseColor

阶段5 - 输出分叉（共享灰度高度图）：
  高度图 → histogram_range → OUT:Height
  高度图 → normal → OUT:Normal
  高度图 → ambient_occlusion_2 → OUT:AO
  高度图 → levels + blend(做旧) → OUT:Roughness
```

### 复杂混凝土（~194 节点，如 concrete_005）

在标准基础上增加：
- **non_uniform_blur** × 5（柔化各个阶段的过渡）
- **更多 directionalwarp**（方向性风化效果）
- **多层 blend 叠加**（57 个 blend！）
- **更丰富的做旧**: moisture + bnw_spots + dirt

## concrete_002 管线详解

### BaseColor 通道（61 节点，深度 13 层）

**底层纹理源（D8-D13）**:
- `tile_generator` × 2（板块分布 + 表面图案）
- `polygon_1`（几何接缝）
- `perlin_noise_zoom` × 3（不同尺度变化）
- `fractal_sum_4`（高频细节）
- `bnw_spots_1`（微观斑点）
- `clouds_1/2`（中频变化）
- `gradient_linear_1`（渐变遮罩）

**处理链路（D4-D7）**:
- 多个 `blend` 叠加（每层加一种纹理特征）
- `warp` 扭曲（增加自然不规则感）
- `levels` 控制每层的强度范围
- `emboss` 浮雕效果（增强表面凹凸感）

**着色链路（D1-D3）**:
- `gradient` 渐变映射（灰度→混凝土灰色调）
- `replace_color` 库节点（局部颜色替换）
- `hsl` 色相/饱和度微调
- `levels` 最终色阶

## AI 生成混凝土的思考参考

> 通用分析框架参考 `sd-operation-rules` 规则 0。以下是混凝土特有的知识。

### 混凝土的 Height 需要什么？

- **有分区结构吗？**（浇筑板块、模板痕迹）→ 有就用 tile_generator 做分区
- **表面质感**：混凝土表面是粗糙但相对平坦的，主要靠中小尺度细节（气孔、砂粒、裂纹）
- **典型层级**：分区结构(可选) + 表面粗糙度(perlin) + 气孔/砂粒(fractal_sum/bnw_spots)

### 混凝土的着色需要什么？

- **颜色来源**：混凝土本身灰色较均匀，变化主要来自风化/湿润/污渍
- 基础色：灰色底色 + Height 着色（凸起偏浅、凹陷偏深）
- 如果是旧混凝土：加 moisture_noise 做湿润/水渍效果
- 如果有分区：不同板块可以有微妙的色差（replace_color）

### 简单参考管线

```
perlin_noise + fractal_sum → blend → levels → Height
Height → normal + AO + Roughness(levels)
Height → Blend(灰暗+灰亮) → (可选)moisture_noise叠加 → BaseColor
```

## 关键参数经验

- **Roughness 范围**: 0.6-0.95（混凝土很粗糙）
- **Metallic**: 始终为 0
- **Height 范围**: 浇筑面很平，histogram_range 归一化后起伏不大
- **Normal 强度**: 通过 levels 控制 normal 节点输出的强度
