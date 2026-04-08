---
name: sd-learned-recipes
description: >
  从 SD 内置 30 个 PBR 材质逆向分析的材质配方库。包含 7 个类别配方 + 3 个通用功能配方，
  涵盖混凝土/金属/瓷砖/砖墙/布料/木材/有机物的节点图结构、管线设计和制作逻辑。
  Use when AI needs to: (1) choose appropriate nodes for a material type,
  (2) reference professional material graph structure,
  (3) understand common SD material building patterns,
  (4) select texture sources for different material categories,
  (5) plan a material pipeline before building.
  Substance Designer only (run_python).
metadata:
  artclaw:
    version: 1.0.1
    author: ArtClaw
    software: substance_designer
---

# SD 材质配方库

> 从 SD 12.1.0 全部 **30 个**内置 PBR 材质逆向分析，提炼出可复用的制作配方。
> **制作任何材质前，先查此库选择正确的管线设计和纹理源。**

## 配方文件索引

### 通用配方（所有材质适用）

| 文件 | 内容 | 何时读取 |
|------|------|----------|
| `recipes/_overview.md` | 总览 + 跨材质统计 + 选择指南 | **必读**：开始前 |
| `recipes/output_pipeline.md` | 输出通道标准管线（Height优先原则） | **必读**：构建输出时 |
| `recipes/coloring.md` | 着色管线：灰度→彩色的三种方案 | 需要 BaseColor 时 |
| `recipes/weathering.md` | 做旧/风化/污渍叠加的三级策略 | 需要真实感时 |

### 类别配方（按需读取）

| 文件 | 材质数 | 适用 |
|------|--------|------|
| `recipes/concrete.md` | 10 个 | 混凝土/水泥/路面 |
| `recipes/metal.md` | 5 个 | 金属/金属板/锈蚀 |
| `recipes/tile.md` | 5 个 | 瓷砖/地砖/马赛克 |
| `recipes/brick.md` | 2 个 | 砖墙/砌体 |
| `recipes/fabric.md` | 3 个 | 布料/织物/编织 |
| `recipes/wood.md` | 2 个 | 木材/木板/木纹 |
| `recipes/organic.md` | 3 个 | 碎石/纸张/纸板 |

## 快速决策树

```
要做什么材质？
├→ 硬质表面
│   ├→ 有规则排列？ → tile.md 或 brick.md
│   ├→ 金属？ → metal.md
│   └→ 粗糙不规则？ → concrete.md
├→ 有机/软质
│   ├→ 编织结构？ → fabric.md
│   ├→ 木纹方向性？ → wood.md
│   └→ 颗粒/纤维？ → organic.md
└→ 不确定 → 先读 _overview.md 的类别纹理源表
```

## 核心发现速查

1. **Height 优先**: 先构建灰度高度图，Normal/AO/Height 三通道从同一源分叉
2. **Blend 是核心**: 平均每材质 33 个 blend（SD 材质 = blend 叠加的艺术）
3. **着色在末端**: 灰度处理完成后才进入着色环节
4. **做旧必备**: moisture_noise(80%使用率) + bnw_spots(60%)
5. **tile_generator 万能**: 不只用于瓷砖，碎石(6个)、木板(5个)、混凝土(3个)都用

## 使用方法

```python
# 在 SD 中读取配方
import os
recipes_dir = os.path.expanduser(r"~\.openclaw\skills\sd-learned-recipes\recipes")

# 先读总览
with open(os.path.join(recipes_dir, "_overview.md"), "r", encoding="utf-8") as f:
    overview = f.read()

# 再读对应类别
with open(os.path.join(recipes_dir, "concrete.md"), "r", encoding="utf-8") as f:
    recipe = f.read()
```
