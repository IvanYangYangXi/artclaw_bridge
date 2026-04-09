# 输出通道标准管线

> **所有 PBR 材质通用**的输出通道构建规则。
> 30 个内置材质无一例外地遵循此模式。

## 核心原则：Height 优先

**Height（高度图）是所有通道的基础**。先构建灰度高度图，然后派生其他通道。

```
                          ┌→ gradient/replace_color → levels → OUT:BaseColor
                          │
Height(灰度) ─→ levels ──┼→ levels → OUT:Roughness
                          │
                          ├→ normal 节点 → OUT:Normal
                          │
                          ├→ histogram_range → OUT:Height
                          │
                          └→ ambient_occlusion_2 → OUT:AO
```

## 各通道详解

### BaseColor（彩色输出）

**管线**: 灰度纹理 → 着色 → HSL微调 → levels → OUT

标准链路：
1. 灰度高度图（或其变体）
2. → `gradient` 渐变映射 或 `replace_color` 库节点（灰度→彩色）
3. → `blend` 叠加多个着色层（深浅变化、污渍等）
4. → `hsl` 调整色相/饱和度（几乎所有材质都有）
5. → `levels` 最终色阶（100%使用率）
6. → OUT:baseColor

**关键发现**: BaseColor 管线最深（8-22 层深度），因为要叠加大量着色层。

### Normal（彩色输出，法线图）

**管线**: 灰度高度图 → normal → shuffle → OUT

标准链路：
1. 灰度高度图（与 Height 通道共享源）
2. → `normal` 原子节点（仅 1 个！灰度→RGB法线）
3. → `shuffle` 通道混洗（调整法线方向，部分材质有）
4. → `uniform` 插入默认法线值（部分材质用作 blend）
5. → OUT:normal

**关键**: 只需 1 个 normal 节点，不要叠加多个。

### Roughness（灰度输出）

**管线**: 灰度纹理 → levels/blend → OUT

标准链路：
1. 从 Height 管线分支，或独立灰度纹理
2. → `levels` 调整范围（粗糙度 0.3-0.9 的典型范围）
3. → `blend` 叠加划痕/磨损/污渍（修改粗糙度分布）
4. → `sharpen` 可选锐化（增强粗糙度对比）
5. → OUT:roughness

**经验**: Roughness 通常比 Height 多 1-3 个额外的 blend 层（叠加磨损效果）。

### Metallic（灰度输出）

**管线**: uniform → OUT（非金属）或 blend → OUT（金属）

- **非金属材质**: `uniform(value=0)` → OUT（100%的混凝土/砖/布/木材/碎石）
- **金属材质**: `blend`(uniform + 遮罩) → OUT（metal 类别用遮罩控制金属/非金属区域）

**关键**: 非金属材质只需 1 个 uniform 节点设为 0。

### Height（灰度输出）

**管线**: 灰度高度图 → histogram_range → OUT

标准链路：
1. 灰度高度图（所有处理完成后的最终高度）
2. → `histogram_range` 库节点（归一化到 0-1 范围，100%使用率）
3. → OUT:height

**关键**: `histogram_range` 是 Height 通道的标配终端节点。

### Ambient Occlusion（灰度输出）

**管线**: 灰度高度图 → ambient_occlusion_2 → OUT

标准链路：
1. 灰度高度图（与 Height 通道共享源）
2. → `ambient_occlusion_2` 库节点（100%使用率）
3. → OUT:ambientOcclusion

**关键**: `ambient_occlusion_2` 是 AO 通道的标配终端节点。

## Height/Normal/AO 共享管线

在 30 个材质中，Height、Normal、AO 三个通道**共享同一个灰度高度图源**：

```
灰度高度图(blend/warp/levels处理后)
    ├→ histogram_range → OUT:Height
    ├→ normal → OUT:Normal  
    └→ ambient_occlusion_2 → OUT:AO
```

这意味着：
- **只需构建一个好的灰度高度图**
- 三个通道从同一点分叉
- 这是 SD 材质最核心的设计模式

## Diffuse/Specular/Glossiness 转换

每个材质都有一个 `basecolor_metallic_roughness_to_diffuse_specular_glossiness` 库节点，
将 PBR MetalRough 工作流转换为 SpecGloss 工作流。这是自动化的，不需要手动处理。

## 实践指导

### 创建一个新 PBR 材质的推荐步骤

1. **选择纹理源**（库节点），参考类别配方
2. **构建灰度高度图**：blend 叠加 + warp 扭曲 + levels 调整
3. **分叉输出**：
   - Height: → histogram_range → OUT
   - Normal: → normal → OUT
   - AO: → ambient_occlusion_2 → OUT
4. **构建 BaseColor**：高度图 → 着色（gradient/replace_color）→ HSL → levels → OUT
5. **构建 Roughness**：从高度图分支 → levels + 额外 blend → OUT
6. **设置 Metallic**：非金属=uniform(0)，金属=blend(遮罩)
