# 布料/织物配方

> 从 3 个内置布料材质（fabric_002/009/025）逆向分析。
> 布料是 SD 内置材质中节点数最少的类别（51-105），但结构独特。

## 布料的物理特征

- **结构**: 编织图案（经纬交织），周期性重复
- **表面**: 纤维质感，微观起伏
- **颜色**: 相对均匀，但有编织造成的经纬线色差 + 褶皱暗区 + 做旧色斑
- **特殊**: 褶皱（creases）是布料独有的特征

## 三种布料子类型

| 材质 | 节点数 | 编织方式 | 核心特征 |
|------|--------|----------|----------|
| fabric_002 | 71 | weave_2 库节点 | 简单编织 + 褶皱 + 做旧 |
| fabric_009 | 105 | **mesh_1 + transformation链** 构建 | 复杂图案 + 多层着色 |
| fabric_025 | 51 | tile_generator + brick_generator | 规则编织 + 简洁 |

## ⭐⭐ fabric_009 编织方法逆向分析 — 正确的编织构建方式 🔴

### 为什么 fabric_009 不用 weave_generator？

`weave_generator` 和 `weave_2` 输出的是**几何精确的硬边矩形条带**，天生具有"竹编/CG感"。
fabric_009 完全避开了这些节点，而是用 **mesh_1 + 一系列 transformation 做非均匀缩放/tiling** 来从零构建编织结构。

### fabric_009 编织管线完整解析

#### 第一步：生成基础网格纹理

```
mesh_1 (Tiling=1, Rotate_45=False)
    → levels (inLow=0.595, inHigh=0.618, inMid=0.3)
      ↑ 极窄灰度范围! 本质是提取网格线的特定灰度带 → 近似二值化
```

**关键理解**：mesh_1 是一个简单的网格/方格纹理，但 levels 用极窄范围(0.595-0.618)提取出的不是整个网格，而是**网格线条的特定宽度区域**。inMid=0.3 让暗部偏多 → 线条偏细。

#### 第二步：通过非均匀缩放构建纱线

```
levels → transformation_1 (matrix22: 0.4, 0, 0, 0.5464)
    ↑ 非均匀缩放：X方向压到 0.4，Y方向 0.5464
    → 让方格变成略扁的矩形

transformation_1 → transformation_2 (matrix22: 64, 0, 0, 64)
    ↑ 64x64 tiling! 把压扁后的小方格铺满整个画面

transformation_2 分叉到两个不同方向的 transformation：
    → transformation_3 (matrix22: 0.2388, 0, 0, 9.2136) 
        ↑ 极端非均匀拉伸! X压缩到0.24, Y拉伸到9.2
        → 方格变成超长的纵向条纹（这就是"纱线"!）
    → transformation_4 (类似但方向不同 → 横向条纹)
```

**核心原理**：不是直接画纱线，而是把网格方格通过极端非均匀缩放"拉成"纱线状。
因为原始是 mesh 纹理（有自然的灰度渐变），拉伸后的"纱线"天然具有**圆润截面感**，
不像 weave_generator 那样输出扁平硬边条带。

#### 第三步：构建交织结构

```
纵向条纹 (transformation_3) + 横向条纹 (transformation_4)
    → blend (blendingmode=Multiply, opacity=1.0)
    ↑ 两方向相乘 = 只有交叉点最亮 → 自然的编织交叉结构!
    
blend → transformation (offset_y=0.19) → 偏移后
    → 分叉到多个 transformation (各自旋转/偏移/缩放)
    → 构建经纬线不同层的高度差
```

#### 第四步：经纬线高度分离

```
多个 transformation 的输出分别混合：
    → blend (blendingmode=5=Min/Darken) 和 blend (blendingmode=4=Max/Lighten)
    → 把经线和纬线分离成不同层
    → 经线层和纬线层可以有不同的高度和处理
```

#### 第五步：FXMaps 精细化

```
herb_1(纤维碎屑) + blend(经纬混合) → blend(Max, opacity=0.24) → FXMaps 输入

FXMaps 作用: 把平面图案投射到 FX-Map 的迭代散布中
    → 增加编织图案的微观随机性和丰富度
    → 输出的编织更有手工感

FXMaps → transformation → sharpen → 后续着色/混合
```

#### 第六步：消除 CG 感的后处理链（同前已记录）

```
编织结构 
    → blur (intensity=1.37) — 软化边缘
    → non_uniform_blur (Intensity=10.6, Anisotropy=1.0) — 沿纱线方向模糊!
    → warp ×8 (6次 0.01-0.05 微弯曲 + 2次 1.5-5.0 宏观弯曲)
    → 后续着色和输出
```

### fabric_009 方法 vs weave_generator 方法对比 🔴

| 对比项 | fabric_009 (mesh_1 方法) | weave_generator 方法 |
|-------|------------------------|---------------------|
| **纱线截面** | 自然圆润（mesh 灰度渐变经拉伸后保留） | 扁平矩形硬边 |
| **交织结构** | 通过 Multiply 两方向条纹得到，交叉点自然 | 内置算法计算，交叉点几何精确 |
| **可控性** | 通过 transformation 矩阵精确控制密度/比例 | 参数有限(Tiling/Shape/Rotate) |
| **CG感** | 起步就低（因为源是圆润的） | 起步就高（需要大量后处理消除） |
| **灵活性** | 可以做任意编织密度和形态 | 局限于预设的编织模式 |
| **节点数** | 更多（需要多个 transformation） | 更少（一个节点搞定基础编织） |
| **推荐用途** | **高质量布料材质** | 快速原型/简单布料 |

### Agent 实现建议

**当目标是高质量布料时**，应使用 fabric_009 的方法：

1. 用 `mesh_1` 生成基础网格 → levels 提取线条
2. 用 transformation 链构建经纬纱线（关键是非均匀缩放 matrix22）
3. Multiply blend 构建交织结构
4. 后处理链消除 CG 感

**当目标是快速原型或简单布料时**，可以用 weave_generator，但必须：
- 降低 Shape 参数（减少扁平感）
- 必须走完整的"先软后硬"后处理链

## 核心纹理源

| 库节点 | 用途 | 重要性 |
|--------|------|--------|
| **mesh_1** | 基础网格纹理（fabric_009 编织源） | ★★★ fabric_009 核心 |
| **weave_2** | 编织图案生成器 | fabric_002 核心 |
| **gradient_linear_1/2** | 渐变遮罩（经纬线方向性色差！） | ★★★ |
| **Creases_Filter** | 褶皱效果（布料独有！） | ★★★ |
| **stains** | 做旧/污渍/色斑 | ★★ |
| **gradient** (Gradient Map) | 灰度→彩色映射（着色核心！） | ★★★ |
| **perlin_noise_zoom** | 大尺度变化 | ★ |
| **herb_1** | 纤维细节 | ★ |
| **tile_generator** | 规则重复 | fabric_025 |
| **brick_generator** | 编织排列 | fabric_025 |

## ⭐ fabric_002 深度分析（推荐参考基准）

### 管线总览

```
weave_2 → transformation → sharpen → 基础编织灰度
    ↓
gradient_linear_1 → 多个 gradient map(8个!) → 多层 blend 着色
    ↓                                            ↓
编织着色后 BaseColor ←←← Creases_Filter(褶皱层)
    ↓                        ↓
    stains(做旧层) → 最终 BaseColor
    ↓
Height/Normal/AO ← histogram_range ← blend(编织+褶皱Height)
```

### 关键设计模式

#### 1. 编织着色：Gradient Map 多层着色（不是简单 Blend 两色！）

fabric_002 使用 **8 个 gradient (Gradient Map) 节点 + 19 个 blend 节点** 构建着色。
核心思路：
- `gradient_linear_1` 生成方向性渐变 → 作为经纬线的明暗遮罩
- 多个 `transformation` 旋转/偏移渐变 → 构建经线方向和纬线方向的独立遮罩
- 多个 `gradient`(Gradient Map) 把灰度遮罩映射为不同色调
- 大量 `blend` 叠加不同方向的色差 → 最终编织着色

**结果**：BaseColor 有丰富的经纬线色差，不是均匀单色。

#### 2. Height 构建链：编织灰度 + 褶皱叠加

```
weave_2 → transformation → sharpen（锐化编织轮廓）
    → blend(编织结构，主 Height)
    → Creases_Filter → Height 输出（叠加褶皱起伏）
    → blend(编织+褶皱) → levels → histogram_range
    → Height / Normal / AO
```

#### 3. Creases_Filter：褶皱三通道联动 🔴

Creases_Filter 是布料核心节点，输出 3 个通道：
- `basecolor` → blend 到 BaseColor（褶皱处颜色变化）
- `Height` → blend 到 Height（褶皱高度起伏）
- `Specular` → blend 到 Roughness（褶皱处光泽变化）

**三通道联动是布料真实感的关键！不能只影响一个通道。**

#### 4. 做旧层 (stains)

stains 库节点在编织 + 褶皱之后叠加，提供：
- 色斑/污渍（影响 BaseColor）
- 法线扰动（影响 Normal）
- 光泽变化（影响 Roughness/Specular）

### fabric_002 节点统计

| 节点类型 | 数量 | 用途 |
|----------|------|------|
| blend | 19 | 叠加混合（核心） |
| transformation | 12 | 构建经纬线方向的渐变遮罩 |
| output | 9 | PBR 输出 |
| gradient (Gradient Map) | 8 | 灰度→彩色着色（关键！） |
| uniform | 6 | 颜色/灰度常量 |
| levels | 5 | 色阶调整 |
| sharpen | 1 | 锐化编织轮廓 |
| weave_2 | 1 | 编织图案源 |
| Creases_Filter | 1 | 褶皱（布料专用） |
| stains | 1 | 做旧/污渍 |

## 布料材质的关键着色分析

从 fabric_002 可以看出，牛仔布/编织布的颜色变化来源有 3-4 种：

1. **经纬线色差**（结构本身）→ 编织图案中经线和纬线本来就颜色不同，需要方向性着色
2. **褶皱暗区**（使用变形）→ 布料褶皱处颜色变暗，需要 Creases_Filter 的 basecolor 输出
3. **磨损褪色**（使用变形）→ 凸起处/边缘处褪色偏白，需要 mg_cloth_wear 或 Height 变体
4. **污渍/做旧**（环境影响，可选）→ 随机色斑，需要 stains 或 moisture_noise

**不是所有布料都需要全部 4 层。** 一块全新的单色棉布可能只需要经纬色差 + 轻微高度着色。一块旧牛仔裤才需要全部。

## AI 生成布料的思考框架

### 从原料和工艺推导微观表现 🔴

**布料的微观表现完全取决于原料和编织工艺的组合。不同组合产生完全不同的质感。**

#### 原料分析：纤维决定质感基底

| 原料 | 纤维特性 | 微观表现 | SD 纹理源建议 |
|------|---------|---------|-------------|
| **棉花(Cotton)** | 短纤维(25-50mm)绞合成纱，表面粗糙，强吸色 | 可见的纤维绞合纹理，毛刺多，**碎毛明显** | directional_noise(纤维方向) + messy_fibers(碎毛) + herb_1(短纤维) |
| **亚麻(Linen)** | 长纤维但粗细不均，有自然节疤 | 不规则粗细纹理，**结节感**，比棉更粗糙 | directional_noise(粗细不均) + bnw_spots(节疤) |
| **丝绸(Silk)** | 极细长丝(900-1500m连续)，光滑截面圆 | 极光滑，**几乎无可见纤维结构**，高光泽 | 极弱的 directional_noise + Roughness 偏低(0.3-0.5) |
| **涤纶(Polyester)** | 合成长丝，均匀一致，微塑感 | 均匀，无碎毛，**机械感强** | 弱 directional_noise 即可，不需要 messy_fibers |
| **羊毛(Wool)** | 卷曲短纤维，表面有鳞片 | **绒毛感极强**，纤维蓬松，表面不平整 | messy_fibers(高 disorder) + herb_1 + noise_creased(蓬松起伏) |
| **棉+涤混纺** | 兼具棉的吸色和涤的均匀 | 碎毛比纯棉少，比纯涤多，质感介于两者 | 适度的 messy_fibers + 较弱的 herb_1 |

#### 编织工艺分析：结构决定纹路形态

| 编织方式 | 经纬交织规律 | 微观表现 | SD 节点建议 |
|---------|------------|---------|-----------|
| **平纹(Plain)** | 1上1下交替 | 均匀方格网，正反面相同，**最紧密** | weave_generator(weave=1) 或 weave_2(Rotate_45=False) |
| **2/1斜纹(Twill 2/1)** | 经线每2上1下偏移 | **对角线纹路(45°)**，正面经线多 | weave_generator(weave=2) |
| **3/1斜纹(Twill 3/1)** | 经线每3上1下偏移 | 更明显的对角线，经线浮长更长，**正面几乎只看到经线** | weave_generator(weave=3 if supported) |
| **缎纹(Satin)** | 长浮线，交织点分散 | 光滑，**凸起极少**，高光泽 | weave_generator(shape 低) + 弱 sharpen |
| **针织(Knit)** | 线圈互相串套 | **无交织网格，圆弧状线圈**，弹性结构 | 需要自定义 tile_generator 或 fxmaps |

#### 染色工艺分析：颜色来源决定着色策略

| 染色方式 | 工艺特点 | 颜色表现 | 着色策略 |
|---------|---------|---------|---------|
| **纱线染色(Yarn-dyed)** | 编织前对纱线分别染色 | **经纬线可以完全不同颜色** | 必须用 Mask_1/Mask_2 分别着色！ |
| **匹染(Piece-dyed)** | 编织后整块布浸染 | 均匀单色，经纬无色差 | 简单底色 + height shading 即可 |
| **靛蓝浸染(Indigo dye)** | 牛仔布专用，**仅染经线** | 经线=深靛蓝，纬线=本白，**磨损露白芯** | Mask_1→靛蓝色, Mask_2→棉白色, height高处→褪色 |
| **印花(Printing)** | 表面印刷图案 | 图案只影响颜色不影响凹凸 | 只在 BaseColor 叠加，不改 Height |
| **扎染/蜡染** | 局部阻染 | 不规则色域边界 | 用 moisture_noise/clouds 做色域遮罩 |

### ⭐ 牛仔布(Denim)完整推导示例

**原料**: 棉纤维 → 短纤维绞合成纱 → 每根纱线上可见纤维绞合方向和毛刺
**工艺**: 经线靛蓝纱染 + 3/1右手斜纹编织 → 正面主要暴露经线(靛蓝), 斜纹45°角
**经历**: 穿着磨损 → 经线凸起处褪色(露出棉白芯), 折叠褶皱处暗化, 整体做旧色差

**从这个推导得出的 Height 层级**:
1. **编织骨架**(最强): weave_generator 3/1 斜纹 → sharpen → 清晰的斜纹凹凸
2. **纤维方向**(中强): directional_noise 分经纬方向 × Mask_1/Mask_2 遮罩 → 线级纤维纹理
3. **微观毛刺**(弱): scratches_2 + messy_fibers_1 + herb_1 → 碎毛、短纤维、表面不平
4. **褶皱起伏**(中): noise_creased → 大面积布料褶皱
5. **破坏规律性**: perlin_noise_zoom warp + clouds warp → 打破编织的机械重复感

**着色层级**:
1. **经纬分色**: Mask_1→深靛蓝(0.08,0.12,0.28), Mask_2→棉白(0.55,0.50,0.42)
2. **高度着色**: 凸起(经线顶部)→褪色亮蓝(0.25,0.30,0.45), 凹陷→保持深色
3. **褶皱暗化**: creased 遮罩→暗化(0.03,0.04,0.10)
4. **低频色差**: perlin_zoom 遮罩→做旧色调偏移
5. **纤维色彩**: height 细节 overlay 到 BaseColor → 线级明暗变化
6. **方向性渐变**: gradient_linear → 极微弱的方向性色差

### 先分析目标布料

1. **什么布？** 牛仔、亚麻、丝绸、针织……不同布料的编织方式和质感完全不同
2. **编织结构**：weave_2 能表现的斜纹/平纹？还是需要 tile_generator 自定义图案？
3. **表面状态**：全新的？有褶皱？有磨损？有污渍？
4. **颜色特征**：经纬线颜色一样吗？有没有渐变或色差？

### Height 构建

布料的 Height 核心是**编织图案**——weave_2 或其他编织节点的输出：

```
weave_2 → (可选)sharpen(锐化编织轮廓) → 编织 Height
```

是否需要额外 Height 层：
- **褶皱**：如果布料不是完全平展的 → 加 Creases_Filter 或 noise_creased
- **纤维细节**：如果需要近距离质感 → 加 fibers_1/messy_fibers_1
- **全新平整的布**：编织 Height 本身就够了

### 着色构建

布料着色的核心问题是：**经线和纬线颜色一样吗？**

- **一样**（纯色棉布）→ 单层 Blend(底色 + Height遮罩) 就够
- **不一样**（牛仔、格纹）→ 需要方向性着色：gradient_linear + transformation 构建经纬遮罩

然后按需叠加：
- 有褶皱？→ Creases_Filter.basecolor blend 到 BaseColor
- 有磨损？→ mg_cloth_wear 遮罩 + 褪色叠加
- 有污渍？→ stains 或 moisture_noise 叠加

### Roughness 构建

布料的 Roughness 空间变化来源：
- **编织结构**：凸起的线头比凹陷处更光滑（因为磨损） → Height 变体做遮罩
- **褶皱**：褶皱折痕处光泽不同 → Creases_Filter.Specular（如果使用了 Creases_Filter）
- **总体范围**：布料通常 Roughness 0.7-0.95（很粗糙）

### Creases_Filter 三通道联动

如果布料有褶皱，Creases_Filter 是关键节点，它同时输出：
- `basecolor` → blend 到 BaseColor（褶皱处颜色变化）
- `Height` → blend 到 Height（褶皱高度起伏）
- `Specular` → blend 到 Roughness（褶皱处光泽变化）

**三通道联动是布料褶皱真实感的来源。**

### 关键库节点加载路径

| 节点 | sbs 文件 | 说明 |
|------|---------|------|
| weave_2 | `weave_2.sbs` | 标准库路径 |
| gradient_linear_1 | `gradient_linear_1.sbs` | 标准库路径 |
| gradient_linear_2 | `gradient_linear_2.sbs` | 标准库路径 |
| Creases_Filter | `materials/pbr/fabric_002.sbs` (嵌入子图) | ⚠️ 非独立 sbs |
| stains | `materials/pbr/fabric_002.sbs` (嵌入子图) | ⚠️ 非独立 sbs |
| mg_cloth_wear | `mg_cloth_wear.sbs` | 布料磨损（更简单的替代） |
| fabric_weathering | `fabric_weathering.sbs` | 完整布料风化滤镜 |
| non_uniform_blur | `non_uniform_blur.sbs` | 各向异性模糊（消除竹编感核心节点！） |

> **⚠️ Creases_Filter 和 stains 嵌入在 fabric_002.sbs 内**，不是独立的库节点。
> 加载方式：先加载 fabric_002.sbs，再用 `getChildrenResources(True)` 找到子图，
> 然后 `graph.newInstanceNode(子图resource)` 创建实例。
>
> **替代方案**：如果不想依赖 fabric_002.sbs，可以用：
> - `fabric_weathering.sbs` 替代 Creases_Filter + stains（它的输入接口更完整）
> - `mg_cloth_wear.sbs` 作为简化版布料磨损
> - `noise_creased.sbs` 作为褶皱噪波源（更基础的褶皱纹理）

## 关键参数经验

### ⛔ "竹编感"问题与修复 — 所有编织类材质的核心陷阱 🔴

**weave_generator / weave_2 / tile_generator 生成的编织图案天然具有"竹编感"：**
线条硬直、交叉点锐利、截面扁平矩形、间隙清晰。这是几何生成器的通病。

**真实棉纱/织线的物理特征**：
- 截面是**圆润膨胀**的（纤维绞合成纱，自然蓬松），不是扁平条带
- 线路是**微弯曲**的（纱线在编织时受力变形），不是完美直线
- 边缘是**模糊**的（表面纤维外露），不是锐利几何边界
- 交叉处是**柔软挤压**的（纤维互相穿插），不是硬切割

**fabric_009 的消除竹编感管线（从逆向分析得出）**：

```
编织图案(fxmaps/weave)
    → blur(1.0-1.4) ← 软化几何硬边
    → non_uniform_blur(intensity=10.6, anisotropic) ← 沿线方向模糊！关键！
    → warp × 4-6 (intensity=0.01-0.05) ← 微弯曲（线路不规则性）
    → warp × 1-2 (intensity=1.5-5.0) ← 宏观弯曲（布料起伏）
    → sharpen(moderate) ← 在软化后重新强化（不是在之前！）
    → fiber_overlay ← 纤维方向细节
```

**关键数值参考（来自 fabric_009 逆向）**：

| 处理 | 节点 | 参数 | 数值 | 作用 |
|------|------|------|------|------|
| 软化边缘 | blur | intensity | 1.0-1.4 | 消除几何锐边 |
| **方向性软化** | **non_uniform_blur** | **Intensity** | **10.6** | **沿线方向模糊=纱线感！** |
| | | Anisotropy | 1.0 | 完全各向异性 |
| 微弯曲 | warp ×4-6 | intensity | 0.01-0.05 | 每根线的微小弯曲 |
| 宏观弯曲 | warp ×1-2 | intensity | 1.5-5.0 | 布料大面积变形 |
| 重新锐化 | sharpen | intensity | 适中 | 在软化后增强对比 |

**⚠️ 反模式（导致竹编感的做法）**：
- ❌ weave_generator → **sharpen** → ... （先锐化 = 放大竹编感）
- ❌ 只用 1-2 次强 warp（intensity 2-5）→ 扭曲但不柔化
- ❌ 不用 blur / non_uniform_blur → 保留了所有几何硬边
- ❌ shape 参数太高 → 线条太宽太扁

**✅ 正确顺序**: 先模糊(软化) → 再 warp(弯曲) → 再 sharpen(增强) → 再 non_uniform_blur(方向性柔化)

### Levels 圆化截面技巧

Levels 可以把编织图案的矩形截面"圆化"——提升暗部压缩亮部，使线条中心亮边缘暗渐变更自然：
```
原始: ████████  (扁平矩形截面)
Levels 调整后: ▓██████▓  (圆润截面，边缘渐变)
```

### 其他参数经验

- **Roughness 范围**: 0.7-0.95（布料很粗糙）
- **Metallic**: 始终为 0
- **Height 范围**: 编织凹凸感明显但绝对高度小
- **Normal**: 编织图案的法线是核心视觉特征
- **Sharpen intensity**: 适度（1.0-3.0），过高会产生白边
- **关键**: `transformation` 节点大量使用（平均 10+ 个），用于构建编织图案的旋转/偏移

## 加载嵌入子图的代码（Creases_Filter / stains）

```python
import os
pm = app.getPackageMgr()
base = r"C:\Program Files\Adobe\Adobe Substance 3D Designer\resources\packages"
fabric_sbs = os.path.join(base, "materials", "pbr", "fabric_002.sbs")

pkg = pm.getUserPackageFromFilePath(fabric_sbs)
if not pkg:
    pkg = pm.loadUserPackage(fabric_sbs)

# 在包的所有资源中找子图
creases_res = None
stains_res = None
for res in pkg.getChildrenResources(True):
    rid = res.getIdentifier()
    if rid == "Creases_Filter":
        creases_res = res
    elif rid == "stains":
        stains_res = res

# 创建实例节点
if creases_res:
    creases_node = graph.newInstanceNode(creases_res)
    creases_node.setPosition(float2(x, y))
    # 输出: basecolor, Height, Specular（三通道联动）
    # 关键输入: basecolor(彩色), height(灰度), specular(灰度)
    #   + Creases_Frequency, Creases_Sharpness, Creases_Relief_Intensity 等

if stains_res:
    stains_node = graph.newInstanceNode(stains_res)
    stains_node.setPosition(float2(x2, y2))
    # 输出: basecolor, Normal, Specular
    # 关键输入: basecolor(彩色), normal(彩色), height(灰度), specular(灰度)
    #   + type, amount, size 等
```

### 替代方案：fabric_weathering

```python
# fabric_weathering 是独立库节点，一个节点搞定褶皱+磨损+老化
fw_sbs = os.path.join(base, "fabric_weathering.sbs")
fw_pkg = pm.getUserPackageFromFilePath(fw_sbs)
if not fw_pkg:
    fw_pkg = pm.loadUserPackage(fw_sbs)
fw_res = fw_pkg.getChildrenResources(False)[0]
fw_node = graph.newInstanceNode(fw_res)
# 输入: basecolor, height, specular 等 + 风化参数(Dust, Creases, Age...)
# 输出: Normal, Diffuse, Specular, Ambient_Occlusion
# 注意: 没有 Height 输出，需要保留原 Height 链路
```
