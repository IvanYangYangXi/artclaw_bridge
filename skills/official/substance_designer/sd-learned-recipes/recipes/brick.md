# 砖墙配方

> 从 2 个内置砖墙材质（bricks_001/005）逆向分析。
> 砖墙和瓷砖共享"规则排列"的骨架，但砖墙更强调**每块砖的独特纹理**和**砂浆缝隙**。

## 砖墙的物理特征

- **形状**: 标准砖块交错排列（running bond）
- **每块砖**: 有独特的颜色变化、表面纹理、不完美边缘
- **砂浆**: 比瓷砖缝隙更宽，颜色为浅灰色，粗糙度高
- **风化**: 旧砖墙有明显的侵蚀、缺角、颜色退化

## 核心纹理源

| 库节点 | 用途 | bricks_001 | bricks_005 |
|--------|------|------------|------------|
| **tile_generator** | 砖块排列 | 2 | 1 |
| **replace_color** | 每块砖着色 | 3 | 2 |
| **fractal_sum_base** | 表面粗糙纹理 | 2 | 2 |
| **clouds_2/3** | 中频色调变化 | 2 | 0 |
| **moisture_noise** | 水渍 | 1 | 1 |
| **crystal_1/2** | 砖面晶体纹理 | 0 | 1 |
| **gaussian_spots** | 砂浆斑点 | 1 | 0 |
| **bnw_spots_2** | 表面瑕疵 | 0 | 1 |
| **blur_hq_grayscale** | 高质量模糊 | 2 | 0 |
| **noise_upscale_1** | 细节增强 | 0 | 2 |

## 砖墙管线模式

### 骨架层

```
tile_generator(running bond 排列) → 两路输出：
  ├→ 形状遮罩: 砖面 vs 砂浆
  └→ 随机灰度: 每块砖独特 ID
```

### 砖面纹理层

```
fractal_sum_base → warp → levels → 砖面粗糙纹理
clouds_2 → blur → 中频变化
bnw_spots → 表面瑕疵
blend(多层叠加) → 完整的砖面灰度纹理
```

### 着色层

砖墙用大量 `replace_color`（3 个）实现每块砖的颜色变化：
```
灰度纹理 → replace_color #1 (主色调: 红砖/灰砖)
         → replace_color #2 (变化色: 深色/浅色砖)
         → replace_color #3 (特殊色: 烧焦/退色砖)
→ blend 组合 → gradient 渐变微调 → hsl → levels → OUT:BaseColor
```

### 砂浆处理

```
砖面遮罩 → invert → 砂浆遮罩
  → blend(砂浆颜色, 浅灰) 到 BaseColor
  → blend(高粗糙度) 到 Roughness
  → blend(凹陷) 到 Height
```

## AI 生成砖墙的思考参考

> 通用分析框架参考 `sd-operation-rules` 规则 0。以下是砖墙特有的知识。

### 砖墙的 Height 需要什么？

- **主结构**：tile_generator 做砖块排列（running bond 等砌法）— 砖面凸起，砂浆凹陷
- **砖面细节**：砖表面不是完全平的 — fractal_sum 或 perlin 做微妙起伏
- **有没有破损？** 旧砖墙可能有缺角/碎裂 → 额外遮罩叠加

### 砖墙的着色需要什么？

- **颜色变化来源**：每块砖颜色略有不同（烧制差异）+ 砂浆是灰白色 + 风化/苔藓
- 砖面：tile_generator 的随机灰度值天然可做每块砖的色差遮罩
- 砂浆：用 invert 砖面遮罩分离砂浆区域，单独着色
- 均匀的新砖墙：砖色 + 砂浆色 两层即可
- 旧砖墙：加 moisture_noise 做风化

## 关键参数经验

- **Roughness**: 砖面 0.5-0.8，砂浆 0.8-0.95
- **Metallic**: 始终为 0
- **Height**: 砖面高，砂浆低，对比度比瓷砖更柔和（砂浆不如瓷砖缝深）
- **砖色范围**: 红砖 RGB(150,60,40)~(200,100,70)，灰砖 (100,95,85)~(160,155,145)
