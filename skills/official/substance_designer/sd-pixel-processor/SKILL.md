---
name: sd-pixel-processor
description: >
  SD Pixel Processor 节点使用指南。Pixel Processor 是 SD 中最强大的像素级计算节点，
  可执行任意数学运算。包含：API 创建流程、函数节点完整参考、常用着色器模式。
  Use when AI needs to: (1) create custom per-pixel effects,
  (2) implement mathematical texture generation (voronoi, noise, gradients),
  (3) build procedural patterns that atom nodes cannot achieve,
  (4) perform pixel-level color/value transformations.
  Substance Designer only (run_python).
metadata:
  artclaw:
    version: 1.0.0
    author: ArtClaw
    software: substance_designer
---

# SD Pixel Processor 使用指南

> Pixel Processor 是 SD 的"像素着色器"——对每个像素执行自定义函数图。
> 适合 AI 使用：本质是数学表达式图，AI 擅长构建数学逻辑。

## 核心概念

```
Pixel Processor 节点
├── 输入: input, input:1, ... (最多 N 个图像输入)
├── perpixel: Function Graph (核心! 对每个像素执行的逻辑)
│   ├── 系统变量: $pos(像素UV坐标), $size(图像尺寸), $tiling, $randomseed
│   ├── 函数节点: 数学运算(add/mul/sin/cos...)、采样(samplelum/samplecol)、逻辑(ifelse)
│   └── 输出: 一个 float/float2/float3/float4 值 → 该像素的颜色
└── 输出: unique_filter_output (处理后的图像)
```

## 创建 Pixel Processor

### 步骤 1: 创建节点

```python
pp = graph.newNode("sbs::compositing::pixelprocessor")
pp.setPosition(float2(x, y))
```

### 步骤 2: 获取/创建 perpixel 函数图

```python
pp_prop = pp.getPropertyFromId("perpixel", SDPropertyCategory.Input)
fg = pp.newPropertyGraph(pp_prop, "SDSBSFunctionGraph")
```

### 步骤 3: 在函数图中添加节点

```python
# 获取当前像素 UV 坐标
pos = fg.newNode("sbs::function::get_float2")
pos.setPosition(float2(-300, 0))
cp = pos.getPropertyFromId("__constant__", SDPropertyCategory.Input)
pos.setPropertyValue(cp, SDValueString.sNew("$pos"))

# 创建常量
c = fg.newNode("sbs::function::const_float1")
c.setPosition(float2(-300, 50))
cp = c.getPropertyFromId("__constant__", SDPropertyCategory.Input)
c.setPropertyValue(cp, SDValueFloat.sNew(0.5))

# 数学运算
mul = fg.newNode("sbs::function::mul")
mul.setPosition(float2(-100, 0))

# 连接
pos.newPropertyConnectionFromId("unique_filter_output", mul, "a")
c.newPropertyConnectionFromId("unique_filter_output", mul, "b")

# 设置输出
fg.setOutputNode(mul, False)
```

## 系统变量（get_*节点的 __constant__ 值）

| 变量 | 类型 | 节点 | 说明 |
|------|------|------|------|
| `$pos` | float2 | get_float2 | 当前像素 UV 坐标 (0~1) |
| `$size` | float2 | get_float2 | 图像尺寸（像素） |
| `$tiling` | int | get_integer1 | 平铺模式 |
| `$randomseed` | int | get_integer1 | 随机种子 |
| `$number` | int | get_integer1 | 迭代索引（FX-Map 中） |
| `$depth` | int | get_integer1 | FX-Map 深度 |
| 自定义参数名 | 各种 | get_float1/int1/bool | 图输入参数 |

## 函数节点完整参考

### 算术运算

| 节点 ID | 输入 | 输出 | 说明 |
|---------|------|------|------|
| `add` | a, b | float* | a + b |
| `sub` | a, b | float* | a - b |
| `mul` | a, b | float* | a * b（同类型） |
| `mulscalar` | a, b(float1) | float* | 向量 × 标量 |
| `div` | a, b | float* | a / b |
| `mod` | a, b | float* | a % b（取模） |
| `neg` | a | float* | -a |
| `abs` | a | float* | |a| |
| `sqrt` | a | float1 | √a |
| `pow` | a, b | float1 | a^b |
| `min` | a, b | float* | min(a,b) |
| `max` | a, b | float* | max(a,b) |
| `floor` | a | float* | 向下取整 |
| `ceil` | a | float* | 向上取整 |
| `lerp` | a, b, t | float* | 线性插值 a+(b-a)*t |

### 三角函数

| 节点 ID | 输入 | 输出 | 说明 |
|---------|------|------|------|
| `sin` | a | float1 | sin(a) |
| `cos` | a | float1 | cos(a) |
| `atan2` | a, b | float1 | atan2(a,b) |

### 逻辑/比较

| 节点 ID | 输入 | 输出 | 说明 |
|---------|------|------|------|
| `ifelse` | condition(bool), iftrue, iffalse | * | 条件分支 |
| `eq` | a, b | bool | a == b |
| `noteq` | a, b | bool | a != b |
| `gt` | a, b | bool | a > b |
| `gteq` | a, b | bool | a >= b |
| `lr` | a, b | bool | a < b |
| `lreq` | a, b | bool | a <= b |
| `and` | a, b | bool | a && b |
| `or` | a, b | bool | a \|\| b |
| `not` | a | bool | !a |

### 类型转换/向量操作

| 节点 ID | 输入 | 输出 | 说明 |
|---------|------|------|------|
| `tofloat` | a(int) | float1 | 整数→浮点 |
| `toint1` | a(float) | int | 浮点→整数 |
| `vector2` | x, y | float2 | 构造 float2 |
| `vector3` | x, y, z | float3 | 构造 float3 |
| `vector4` | x, y, z, w | float4 | 构造 float4 |
| `swizzle1` | a(float2+) | float1 | 提取分量 (.x/.y/.z/.w) |
| `swizzle2` | a(float3+) | float2 | 提取两个分量 |
| `swizzle3` | a(float4) | float3 | 提取三个分量 |
| `cartesian` | a(float2, 极坐标) | float2 | 极坐标→笛卡尔 |

### 采样

| 节点 ID | 输入 | 输出 | 说明 |
|---------|------|------|------|
| `samplelum` | pos(float2) | float1 | 采样灰度输入（对应 input 端口序号） |
| `samplecol` | pos(float2) | float4 | 采样彩色输入 |

### 常量

| 节点 ID | __constant__ | 说明 |
|---------|-------------|------|
| `const_float1` | float 值 | 浮点常量 |
| `const_float2` | float2 值 | 2D 向量常量 |
| `const_float3` | float3 值 | 3D 向量常量 |
| `const_float4` | float4 值 | 4D 向量常量 |
| `const_int1` | int 值 | 整数常量 |
| `const_int2` | int2 值 | 2D 整数常量 |
| `const_bool` | bool 值 | 布尔常量 |

### 变量读写

| 节点 ID | 说明 |
|---------|------|
| `get_float1/2/3/4` | 读取变量（__constant__=变量名） |
| `get_integer1` | 读取整数变量 |
| `get_bool` | 读取布尔变量 |
| `set` | 设置变量值 |
| `sequence` | 顺序执行多个 set |

### 其他

| 节点 ID | 说明 |
|---------|------|
| `rand` | 随机数生成 |
| `instance` | 调用子函数图 |
| `passthrough` | 直通（调试用） |

## 常用 Pixel Processor 模式

### 渐变（Gradient）

```
$pos → swizzle1(.x) → 输出   // 水平渐变 (左黑右白)
$pos → swizzle1(.y) → 输出   // 垂直渐变 (上黑下白)
```

### 圆形遮罩

```
$pos → sub(0.5, 0.5) → mul(自身) → swizzle1(.x) + swizzle1(.y) → sqrt → 输出
// distance from center
```

### 棋盘格

```
$pos.x * scale → floor → mod(2)  ─┐
                                    ├→ add → mod(2) → 输出
$pos.y * scale → floor → mod(2)  ─┘
```

### 采样偏移（扭曲）

```
input:0 在 pos 处采样作为偏移量
$pos + samplelum(input:0, $pos) * strength → samplecol(input:1, 偏移pos) → 输出
```

### Voronoi 噪波（简化版）

核心逻辑：对每个像素，找到最近的随机种子点，输出距离值。
SD 内置 voronoi 用 44-100 个函数节点实现，包含距离计算、边缘检测等。

## ⚠️ 注意事项

1. **perpixel 函数图必须有输出节点**: `fg.setOutputNode(node, False)`
2. **函数节点的所有 ID 都以 `sbs::function::` 为前缀**: `fg.newNode("sbs::function::add")`
3. **__constant__ 属性用于**:
   - `const_*` 节点: 设置常量值（用对应的 SDValue 类型）
   - `get_*` 节点: 设置要读取的变量名（用 SDValueString）
4. **连接**: 与 comp graph 相同，`src.newPropertyConnectionFromId("unique_filter_output", dst, "input_port")`
5. **exec 闭包陷阱**: 函数图的操作代码必须内联，不能放在 def 中
6. **单次调用限制**: ≤10 个函数节点创建+连接（避免超时）
