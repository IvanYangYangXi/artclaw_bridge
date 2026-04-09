---
name: sd-fxmap
description: >
  SD FX-Map 节点使用指南。FX-Map 是 SD 中最强大的图案生成节点，
  能实现所有基于网格的重复/散布/迭代图案。tile_generator/splatter/cells 等核心库节点
  都是 FX-Map 的封装。包含：节点类型、迭代逻辑、函数图参数化、常用图案模式。
  Use when AI needs to: (1) create custom tile/scatter patterns,
  (2) build iterative procedural patterns,
  (3) understand how tile_generator works internally,
  (4) implement patterns that library nodes cannot achieve.
  Substance Designer only (run_python).
metadata:
  artclaw:
    version: 1.0.0
    author: ArtClaw
    software: substance_designer
---

# SD FX-Map 使用指南

> FX-Map 是 SD 的"图案引擎"——通过迭代+四叉树实现复杂的重复图案。
> tile_generator、splatter、cells 等几乎所有图案库节点都是 FX-Map 的高层封装。

## 核心概念

```
FX-Map 节点 (sbs::compositing::fxmaps)
├── 输入: inputpattern (图案图像), inputpattern:1 (第二图案)
├── 属性: colorswitch, background, hurst, opacitymult
└── 内部: SDSBSFxMapGraph (FX-Map 图)
    ├── Quadrant (paramset) — 渲染一个图案实例
    ├── Iterator (addnode) — 循环生成 N 个实例
    └── Switch (switchnode) — 条件分支
    每个节点的参数都可以是 Function Graph (动态计算)
```

## FX-Map 节点类型

### Quadrant (sbs::fxmap::paramset) — 图案渲染器

渲染输入图案的一个实例，控制位置、大小、旋转等。

| 参数 | 类型 | 说明 |
|------|------|------|
| `output0~3` | 连接 | 子节点输入（四叉树分支） |
| `opacity` | float4 | 不透明度 (RGBA) |
| `branchoffset` | float2 | **位置偏移** (0~1, UV 空间) |
| `patterntype` | int | 图案类型 (0=无图案, 1=正方形, 5=输入图案, ...) |
| `frameoffset` | float2 | 图案内部偏移 |
| `patternsize` | float2 | **图案大小** (0~1) |
| `patternrotation` | float | 旋转角度 (弧度) |
| `patternsuppl` | float2 | 补充参数 |
| `blendingmode` | int | 混合模式 (0=Alpha, 1=Add, ...) |
| `randomseed` | int | 随机种子 |
| `imageindex` | int | 选择输入图案 (0=inputpattern, 1=inputpattern:1) |
| `imagefiltering` | int | 图案过滤方式 |

### Iterator (sbs::fxmap::addnode) — 循环节点

将子节点重复 N 次，每次提供不同的 `$number` 值。

| 参数 | 类型 | 说明 |
|------|------|------|
| `output0~1` | 连接 | 子节点 |
| `numberadded` | int | **循环次数** |
| `randomseed` | int | 随机种子 |

### Switch (sbs::fxmap::switchnode) — 条件分支

根据条件选择执行哪个子分支。

## 创建 FX-Map

### 步骤 1: 创建 fxmaps 节点

```python
fxmap = graph.newNode("sbs::compositing::fxmaps")
fxmap.setPosition(float2(x, y))
```

创建后自动包含一个空的 FX-Map 图和一个默认 Quadrant 节点。

### 步骤 2: 访问 FX-Map 图

```python
fxg = fxmap.getReferencedResource()  # → SDSBSFxMapGraph
fxnodes = fxg.getNodes()
# 默认有 1 个 paramset (Quadrant)
quadrant = fxnodes.getItem(0)
```

### 步骤 3: 添加 Iterator

```python
iterator = fxg.newNode("sbs::fxmap::addnode")
iterator.setPosition(float2(0, -100))
# 连接: Iterator → Quadrant
iterator.newPropertyConnectionFromId("unique_filter_output", quadrant, "output0")
```

### 步骤 4: 参数化（Function Graph）

FX-Map 的关键能力：**每个参数都可以是一个函数图**，根据 `$number`（迭代索引）动态计算。

```python
# 设置 Iterator 循环次数
num_prop = iterator.getPropertyFromId("numberadded", SDPropertyCategory.Input)
num_fg = iterator.newPropertyGraph(num_prop, "SDSBSFunctionGraph")
c = num_fg.newNode("sbs::function::const_int1")
cp = c.getPropertyFromId("__constant__", SDPropertyCategory.Input)
c.setPropertyValue(cp, SDValueInt.sNew(16))
num_fg.setOutputNode(c, False)
```

```python
# 设置 Quadrant 位置（根据 $number 计算网格位置）
offset_prop = quadrant.getPropertyFromId("branchoffset", SDPropertyCategory.Input)
fg = quadrant.newPropertyGraph(offset_prop, "SDSBSFunctionGraph")

# 读取 $number
num = fg.newNode("sbs::function::get_integer1")
num_cp = num.getPropertyFromId("__constant__", SDPropertyCategory.Input)
num.setPropertyValue(num_cp, SDValueString.sNew("$number"))

# $number → float
to_f = fg.newNode("sbs::function::tofloat")
num.newPropertyConnectionFromId("unique_filter_output", to_f, "a")

# 后续用 mod、div、floor 等计算网格坐标...
```

### 步骤 5: 设置输出

```python
fxg.setOutputNode(quadrant, False)  # 或 iterator
```

## FX-Map 系统变量

在 FX-Map 的函数图中可用：

| 变量 | 类型 | 说明 |
|------|------|------|
| `$number` | int | 当前迭代索引 (0, 1, 2, ...) |
| `$depth` | int | 四叉树深度 |
| `$totalcount` | int | 总迭代次数 |
| `$size` | float2 | 图像尺寸 |
| `$tiling` | int | 平铺模式 |
| `$randomseed` | int | 随机种子 |

## 常用 FX-Map 图案模式

### 1. 规则网格（tile_generator 的核心）

```
Iterator(N×M次)
  └→ Quadrant
       branchoffset = float2( ($number % N) / N, floor($number / N) / M )
       patternsize = float2(1/N, 1/M)
```

**逻辑**: 每次迭代放一个方块，位置由 $number 计算的行列决定。

### 2. 随机散布（splatter 的核心）

```
Iterator(count次)
  └→ Quadrant
       branchoffset = float2( rand($number * seed1), rand($number * seed2) )
       patternsize = float2(rand_range)
       patternrotation = rand($number) * 2π
```

**逻辑**: 每次迭代随机位置、随机大小、随机旋转。

### 3. 砖墙排列（brick_generator 的核心）

```
Iterator(rows)
  └→ Iterator(cols_per_row)
       └→ Quadrant
            branchoffset.x = col/total_cols + (row%2) * half_brick_offset
            branchoffset.y = row/total_rows
            patternsize = float2(brick_width, brick_height)
```

**逻辑**: 双层迭代，奇偶行有半砖偏移。

### 4. 同心环（cells 的思路）

```
Iterator(ring_count)
  └→ Iterator(points_per_ring)
       └→ Quadrant
            branchoffset = polar_to_cartesian(ring_radius, angle)
```

## 实际案例：tile_generator 内部结构

tile_generator 的 FX-Map 图只有 2 个节点：
- `addnode` (Iterator): numberadded = N×M（由外部参数驱动）
- `paramset` (Quadrant): 139 个函数节点计算 opacity，166 个计算 branchoffset，150 个计算 patternsize

**这揭示了 tile_generator 的复杂度不在图结构，而在函数图的数学逻辑中。**

## ⚠️ 注意事项

1. **新建 fxmaps 节点自动包含 1 个空 Quadrant**: 不需要手动创建
2. **Iterator 输出连接到 Quadrant 的 output0**: `iterator.newPropertyConnectionFromId("unique_filter_output", quadrant, "output0")`
3. **函数图创建**: `node.newPropertyGraph(prop, "SDSBSFunctionGraph")`
4. **函数节点前缀**: `sbs::function::` (在函数图中) vs `sbs::fxmap::` (在 FX-Map 图中)
5. **rand 函数**: 需要种子输入，通常用 `$number * seed` 或 `$number + offset`
6. **单次调用限制**: FX-Map 图节点 ≤3 个，函数图节点 ≤10 个（避免超时）
7. **patterntype**: 0=无图案(用于只计算), 1=正方形, 2=盘, 5=输入图案, 7=Bell
8. **坐标空间**: branchoffset 和 patternsize 都是 0~1 的 UV 空间

## FX-Map vs Pixel Processor 选择

| 场景 | 推荐 |
|------|------|
| 重复/散布图案 | **FX-Map** |
| 像素级数学运算 | **Pixel Processor** |
| 网格排列 | **FX-Map** |
| 距离场/噪波 | **Pixel Processor** |
| 随机散布+旋转 | **FX-Map** |
| 颜色变换/滤镜 | **Pixel Processor** |
| 需要输入图案 | **FX-Map** |
| 不需要输入图像 | **Pixel Processor** |
