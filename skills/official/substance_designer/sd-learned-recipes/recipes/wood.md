# 木材配方

> 从 2 个内置木材材质（wood_american_cherry, old_painted_planks）逆向分析。
> 木材的核心特征：**方向性极强**（所有纹理沿木纹方向流动）。

## 木材的物理特征

- **年轮**: 同心环/弧线纹理，从树心向外扩散
- **纤维**: 沿树干方向的纤维条纹
- **颜色**: 深浅交替（年轮明暗），可能有节疤
- **方向性**: 所有纹理特征都有明确方向

## 两种木材子类型

| 材质 | 节点数 | 特征 |
|------|--------|------|
| wood_american_cherry | 152 | 纯木纹（年轮+纤维），方向性极强 |
| old_painted_planks | 170 | 木板+旧油漆，有 tile_generator 排列 |

## 核心纹理源

| 库节点 | 用途 | 重要性 |
|--------|------|--------|
| **wood_fibers_1/2** | 木纹纤维（核心！） | ★★★ |
| **directionnal_noise** | 方向性噪波（木纹走向） | ★★★ |
| **tile_generator** | 木板排列（多块拼接） | ★★（板类必选） |
| **perlin_noise_zoom** | 大尺度色调变化 | ★★ |
| **gradient_linear_1/2** | 渐变遮罩 | ★ |
| **bnw_spots_1** | 节疤/瑕疵 | ★ |
| **herb_1** | 微纤维细节 | ★ |
| **dirt_4** | 水平划痕/使用痕迹 | 做旧 |
| **cells_1** | 年轮结构（old_painted_planks 用 3 个） | 高级 |
| **white_noise** | 随机变化种子 | 可选 |

## 木材关键技法：方向性处理

木材是所有材质中 **warp 和 dirmotionblur 使用量最大的**：

| 节点 | wood_american_cherry | 其他材质平均 |
|------|---------------------|-------------|
| warp | **17** | 5 |
| dirmotionblur | **5** | 0-1 |
| directionalwarp | 2 | 2 |

**原因**: 木纹的所有特征都必须沿同一方向流动。大量 warp 让随机噪波"顺着"木纹方向变形。

### 方向性处理链路

```
wood_fibers_2 → 纤维方向的灰度图
perlin_noise_zoom → 扭曲源
    ↓
warp(纤维 + 噪波) → 纤维沿噪波方向弯曲
dirmotionblur → 沿纤维方向拉伸（增强方向感）
directionalwarp → 方向性变形
```

## wood_american_cherry 管线详解

### BaseColor（深度 ~13 层）

**底层纹理源**:
```
wood_fibers_2 → 木纹纤维主体
perlin_noise_zoom × 5次引用 → 大尺度变化（关键分支点！）
directionnal_noise × 4次引用 → 方向性细节
tile_generator × 4 → 年轮排列/木板分块
herb_1 × 4次引用 → 微纤维叠加
```

**处理链路**:
```
17 个 warp → 所有纹理沿木纹方向扭曲
5 个 dirmotionblur → 方向性拉伸
17 个 transformation → 缩放/平铺调整
8 个 blur → 柔化过渡
38 个 blend → 多层叠加
```

**着色链路**:
```
13 个 gradient → 灰度→木材颜色映射
replace_color → 局部颜色替换（节疤等）
hsl → 最终色调微调
levels → 输出
```

### Height/Normal/AO

与 BaseColor 共享大部分管线，从灰度高度图分叉。

## old_painted_planks 的特殊之处

比纯木纹多了：
- **tile_generator × 5** → 木板排列（running bond 式）
- **cells_1 × 3** → 年轮同心圆结构
- **shape** → 木板边缘形状
- **油漆层**: 额外的 blend 叠加彩色油漆 + 剥落遮罩

## AI 生成木材的思考参考

> 通用分析框架参考 `sd-operation-rules` 规则 0。以下是木材特有的知识。

### 木材的 Height 需要什么？

- **主特征是方向性**：木纹是强方向性的 — wood_fibers + warp + dirmotionblur 是核心组合
- **年轮**：wood_fibers 自带年轮结构，用 warp 弯曲让年轮更自然
- **有没有板拼？** 多块木板拼接 → tile_generator 做板块分区 + 板间缝隙

### 木材的着色需要什么？

- **颜色变化来源**：年轮本身的深浅色差（木材最核心的着色）+ 每块板的色调差异(如果是拼板)
- 木纹着色很简单：木纹灰度 → Blend(深色+浅色) 就能表现年轮色差
- 拼板：tile_generator 随机灰度做板间色调差异
- 旧木：加 moisture_noise 或 dirt 做磨损

### 木材的关键技巧

- **warp 数量决定质量**：越多次 warp，纤维弯曲越自然
- **dirmotionblur**：方向与纤维方向一致，是木材标志性处理
- 木材 Roughness 0.4-0.8（抛光低、旧木高），Metallic 始终 0

## 关键参数经验

- **Roughness 范围**: 0.4-0.8（抛光木材更光滑，旧木更粗糙）
- **Metallic**: 始终为 0
- **核心**: warp 节点数量是木材质量的关键指标——越多方向性越自然
- **dirmotionblur**: 方向与木纹纤维方向一致，是木材的标志性处理
- **颜色范围**: 樱桃木 RGB(160,80,40)~(220,160,100)，橡木 (140,100,60)~(200,170,120)
