# 着色管线：灰度→彩色

> 30 个内置材质的着色策略分析。
> 着色是材质制作中最影响最终效果的环节。

## 三种着色方案（按使用率排序）

### 方案 1: Gradient 渐变映射（最常用）

**使用率**: 100%材质都用 gradient，平均每材质 10 个。

**原理**: 灰度值 0→1 映射到颜色渐变条。
- 黑色区域 → 暗色（如深棕色）
- 白色区域 → 亮色（如浅黄色）
- 中间值 → 渐变过渡

**适用**: 需要平滑颜色过渡的场景（木纹、石材纹理、金属色泽变化）。

**管线**:
```
灰度纹理 → gradient(渐变映射) → 彩色纹理
```

**API 提示**: Gradient 节点的 `gradientrgba` 参数设置非常复杂（需要编码渐变控制点），
建议用 Blend 着色方案替代，或使用 `replace_color` 库节点。

### 方案 2: Replace_Color 库节点（第二选择）

**使用率**: 80%材质使用，平均 2-4 个。

**原理**: 将灰度范围映射到指定的目标颜色。比 gradient 更精确地控制特定灰度值的着色。

**适用**: 需要离散颜色区域的场景（砖块不同颜色、瓷砖花色、锈迹斑点）。

**管线**:
```
灰度纹理 → replace_color(库节点) → 彩色纹理
```

### 方案 3: Blend 着色（简单可控）

**原理**: 用灰度纹理作为两种颜色之间的混合遮罩。

**适用**: AI 生成材质时最推荐的方案（API 简单，效果可预测）。

**管线**:
```
[Uniform 深色(Color)] → Blend.source
[Uniform 浅色(Color)] → Blend.destination  
[灰度纹理]            → Blend.opacity
Blend 输出 = 彩色纹理
```

## 多层着色叠加

内置材质从不只用一层着色——它们叠加 3-8 层着色实现丰富的颜色变化：

```
层1: 基础色调（gradient: 主色→高光色）
层2: 暗部细节（blend: 叠加深色污渍遮罩）
层3: 高光变化（gradient: 不同饱和度）
层4: 微观色彩（blend: 斑点/噪波着色）
层5: 最终 HSL 微调
```

### 典型的多层着色链路（来自 concrete_002 分析）

```
D3: blend (组合多个着色层)
D4: gradient + blend (两路着色)
D5: levels + replace_color + blend + levels (精细着色 + 色阶)
D6: highpass + emboss + gradient + levels + levels + blend (纹理+着色+调整)
```

## 颜色微调节点

### HSL（色相/饱和度/亮度）

**使用率**: 70%材质在 BaseColor 末端使用 HSL。

**位置**: 着色完成后、levels 之前。用于统一调整整体色调。

**管线位置**:
```
着色后的彩色纹理 → hsl(微调色相偏移) → levels → OUT:BaseColor
```

### Levels（色阶）

**使用率**: 100%，每个材质的每个通道末端都有 levels。

**作用**: 调整最终的明暗范围和对比度。是所有通道的"终端调整器"。

## AI 生成材质的着色推荐

### 简单材质（<50 节点）

用 Blend 着色，2-3 层：
1. 基础色调: `Uniform深色 + Uniform浅色 + 灰度纹理 → Blend`
2. 变化层: `Uniform变化色 + 上一层 + noise遮罩 → Blend`
3. HSL 微调 + levels 输出

### 中等材质（50-100 节点）

混合使用：
1. 主体着色用 replace_color 库节点
2. 细节叠加用 Blend
3. 最终 HSL + levels

### 专业材质（100+ 节点）

参考具体类别配方（concrete.md、metal.md 等），使用多层 gradient + replace_color。
