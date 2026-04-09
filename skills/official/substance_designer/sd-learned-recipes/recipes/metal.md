# 金属配方

> 从 5 个内置金属材质（metal_002/003/006, metal_plate_001/004）逆向分析。
> 金属材质与其他类别最大区别：**scratches 是核心**，且 Metallic 通道不是简单的 uniform。

## 金属的物理特征

- **表面**: 光滑到中等粗糙，高反射
- **纹理**: 划痕方向性明显，可能有锈蚀/氧化
- **高度变化**: 整体平坦，划痕和弹孔形成微凹陷
- **特殊**: Metallic 通道需要遮罩（纯金属 vs 氧化/锈蚀区域）

## 两种金属子类型

### 磨损金属（metal_002/003/006）
- 以 **scratches + fractal_sum** 为核心
- 表面不均匀划痕 + 大面积色调变化
- 典型节点数 97-120

### 金属板（metal_plate_001/004）
- 以 **tile_generator + histogram_scan** 为核心
- 规则排列的金属板 + 缝隙 + 表面划痕
- 节点数 85-148，metal_plate_004 含弹孔子图

## 核心纹理源

| 库节点 | 用途 | 重要性 |
|--------|------|--------|
| **scratches_1** | 划痕（金属核心纹理！） | ★★★ |
| **fractal_sum_base** | 表面不均匀性、氧化分布 | ★★★ |
| **histogram_scan** | 遮罩生成（金属/非金属区域分离） | ★★ |
| **moisture_noise** | 水渍/氧化斑 | ★★ |
| **perlin_noise_zoom/1/2** | 大面积色调变化 | ★★ |
| **tile_generator** | 金属板排列（板类） | 板类必选 |
| **dirt_1/2** | 积灰/锈迹 | 做旧 |
| **crystal_1** | 晶体结构纹理（金属微观） | 可选 |
| **cells_1** | 腐蚀坑（高级） | 可选 |
| **replace_color** | 着色（锈蚀/金属色） | ★★ |

## metal_003 管线详解

### BaseColor（69 节点，深度 21 层！最深的管线之一）

**底层纹理构建（D13-D21）**:
```
fractal_sum_base × 2 → warp → blur → 基础不均匀纹理
perlin_noise_zoom → 大面积噪波
crystal_1 × 2 → 微观晶体结构
make_it_tile_patch → 无缝化处理
scratches_1 × 2 → 划痕纹理
```

**叠加处理（D7-D12）**:
```
多层 blend 叠加:
  clouds_1 → levels → blend (叠加中频变化)
  scratches_1 → 更多划痕层
  dirt_2 → 污渍层
  wood_fibers_2 → 方向性纤维纹理（用于金属拉丝效果！）
  cells_1 → 腐蚀坑
```

**着色（D3-D6）**:
```
gradient × 多个 → 不同色调区域
dirmotionblur → 方向性模糊（金属拉丝方向）
warp → 自然弯曲
hsl → 色调微调
levels → 最终输出
```

**关键发现**: metal_003 用了 `wood_fibers_2` 做金属拉丝效果——方向性纤维纹理不限于木材！

### Height 共享管线（D4-D14 共 33 节点）

金属高度图主要来自:
- fractal_sum_base（大面积起伏）
- crystal_1（微观凹凸）
- make_it_tile_patch_grayscale（无缝化）
- 多层 blend 叠加

### Roughness 特殊处理（53 节点）

金属 Roughness 比其他材质复杂：
- **grayscaleconversion**: 从彩色纹理提取灰度信息作为粗糙度遮罩
- **sharpen**: 锐化划痕细节
- **额外的 scratches_1 层**: 划痕区域更粗糙

### Metallic 通道

metal_003 的 Metallic 仍是 `uniform`（纯金属），但 metal_002 和 metal_plate 材质中：
- Metallic = `blend`(uniform(1.0) + 遮罩)
- 遮罩来自 fractal_sum + bnw_spots（锈蚀/氧化区域降低金属度）

## AI 生成金属的思考参考

> 通用分析框架参考 `sd-operation-rules` 规则 0。以下是金属特有的知识。

### 金属的 Height 需要什么？

- **什么类型的金属？** 光滑板材？铸铁？锻造？不同类型表面质感完全不同
- **划痕**：几乎所有金属都有划痕 → scratches_1 是核心纹理源
- **表面不均匀**：fractal_sum 做微妙的高度变化
- **有没有结构？**（板块拼接、铆钉、花纹压印）→ 有就用 tile_generator 做分区

### 金属的着色需要什么？

- **金属色泽本身变化不大**（银、金、铜的底色较均匀）
- **颜色变化主要来自**：反射率变化（划痕更亮）+ 氧化/锈蚀（局部变色）
- 干净金属：底色 + Height 变体做微妙明暗 就够了
- 生锈金属：需要 moisture_noise/bnw_spots 做锈蚀遮罩，锈蚀区 Metallic 降低

### 金属的特殊通道

- **Metallic 不是 0/1**：纯金属区 0.8-1.0，锈蚀/涂层区 0.0-0.3
- **Roughness 关键**：划痕处比光面更粗糙，用 scratches 遮罩叠加

## 关键参数经验

- **Roughness 范围**: 0.15-0.6（金属较光滑，划痕处较粗糙）
- **Metallic**: 0.8-1.0（纯金属区域），锈蚀区域 0.0-0.3
- **划痕方向**: 用 `dirmotionblur` 或 `directionalwarp` 给划痕增加方向感
- **金属拉丝**: 可用 `wood_fibers_2` + `dirmotionblur` 实现
