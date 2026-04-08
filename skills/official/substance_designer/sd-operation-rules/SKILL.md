---
name: sd-operation-rules
description: >
  Substance Designer 操作通用规则和最佳实践。所有涉及 SD 图操作的任务都必须遵守。
  AI 在执行任何 SD 操作任务前应先读取此 Skill。
  包含：API 模块、单线程约束、节点验证、常见陷阱、PBR 输出标准。
  Use when AI needs to: (1) perform any SD graph modification,
  (2) check post-operation best practices, (3) understand SD API constraints.
  Substance Designer only (run_python).
metadata:
  artclaw:
    version: 0.2.0
    author: ArtClaw
    software: substance_designer
---

# SD 操作通用规则

> **强制规则**：所有 Substance Designer 操作任务，执行前必须遵守。

---

## 规则 0：思考先行 🔴

**执行任何材质制作前，必须先分析再动手：**

1. **分析目标材质的物理特征**：纹理形态（条纹/颗粒/编织？）、方向性、颜色变化、粗糙度范围、是否金属
2. **规划节点管线**：确定用哪些噪波源、处理链路、通道映射
3. **确认通道格式**：哪些环节是灰度，哪些是彩色，在哪里做灰度→彩色的转换

**不要用 Uniform 纯色节点做纹理源** — 纯色经过 Warp/DirectionalWarp 处理后仍然是纯色，没有任何纹理效果。纹理源必须用**噪波库节点**（Perlin Noise、Clouds、Cells、Wood Fibers 等）。

---

## 规则 1：预注入变量

直接使用，无需 import：

| 变量 | 说明 |
|------|------|
| `sd`, `app`, `graph` | SD 模块、应用实例、当前活动图 |
| `S`, `W`, `L` | 节点列表、文件路径、sd 模块 |
| `SDPropertyCategory` | 属性分类枚举 |
| `float2`/`float3`/`float4`/`ColorRGBA` | 向量/颜色类型 |
| `SDValueFloat`/`Int`/`Bool`/`String` | 值类型 |
| `SDValueFloat2`/`Float3`/`Float4`/`ColorRGBA` | 向量值类型 |

```python
# ❌ 禁止在 exec 中 import sd.api 子模块（会超时死锁）
from sd.api.sdproperty import SDPropertyCategory  # 禁止！
```

**唯一允许的 import 例外**：`from sd.api.sbs.sdsbscompgraph import SDSBSCompGraph`（创建图时）和 `import os`（文件路径操作）。

---

## 规则 2：⚠️ 变量不跨调用持久 — 最常见致命错误！

> **每次 `run_python` 调用都是独立的 `exec()` 环境。
> 上一次调用中创建的局部变量（如 `wood_fibers`、`warp1`、`perlin_zoom`）
> 在下一次调用中完全不存在！直接引用 = `NameError`。**

### ✅ 正确做法：用节点 ID 跨调用恢复引用

```python
# === 第 1 次调用：创建节点，打印 ID ===
node = graph.newNode("sbs::compositing::blend")
node.setPosition(float2(200, 0))
node_id = node.getDefinition().getId()  # 不够唯一
# 用 UID 更可靠：
uid = node.getIdentifier()  # 或记住位置
result = f"blend node created, uid={uid}"

# === 第 2 次调用：通过 ID 恢复 ===
# ❌ blend1 = ...  # NameError! 上次的变量不存在
# ✅ 重新获取：
nodes = graph.getNodes()
for n in nodes:
    # 通过位置/类型/UID 匹配
    pos = n.getPosition()
    def_id = n.getDefinition().getId()
```

### ✅ 最佳实践：单次调用完成所有关联操作

```python
# 在同一次调用中创建节点 + 连接，避免跨调用引用
node_a = graph.newInstanceNode(res_a)
node_a.setPosition(float2(0, 0))
node_b = graph.newNode("sbs::compositing::warp")
node_b.setPosition(float2(200, 0))
node_a.newPropertyConnectionFromId("output", node_b, "input1")
# ↑ 全部在一次调用中完成，变量有效
```

### 预注入变量是例外

`graph`、`app`、`sd`、`SDPropertyCategory` 等**预注入变量**每次调用都可用（由 adapter 注入），不受此限制。

---

## 规则 3：严格单线程 + 代码简短 ⚠️

- **每次工具调用的代码 <30 行**
- **单次调用上限**：≤3 个节点创建 + ≤3 条连接
- **超过就分多次调用**（但注意规则 2：把有引用关系的节点创建+连接放同一次调用）
- **禁止** `threading`、`asyncio`

### ⛔ 超时 = MCP 永久死亡

一旦超时，SD MCP 连接永久失效，唯一恢复方式：用户重启 SD。

### 规则 2 和规则 3 的平衡

- **优先保证引用完整性**（规则 2）：把创建+连接放同一次调用
- **如果节点太多**，按"组"拆分：每组内部在一次调用中完成创建+连接
- **组之间的连接**：下一次调用中通过 `graph.getNodes()` + 位置/类型匹配恢复引用后再连接

---

## 规则 4：exec 闭包陷阱 🔴

**`import` 的模块在 `def` 函数体内不可见**（Python exec 闭包规则）。

```python
# ❌ os 在 def 内部不可见
import os
def get_path(name):
    return os.path.join(base, name)  # NameError: 'os' is not defined

# ✅ 不用 def，全部内联写
import os
path = os.path.join(base, name)
```

---

## 规则 5：节点分类 — 原子 vs 库

### 原子节点 — `graph.newNode(definition_id)`

SD 内置基础处理节点，**没有纹理生成能力**（只有 Uniform 纯色）：

```
sbs::compositing::blend           # 混合
sbs::compositing::levels          # 色阶
sbs::compositing::curve           # 曲线
sbs::compositing::hsl             # HSL 调整
sbs::compositing::blur            # 模糊
sbs::compositing::normal          # Height→Normal
sbs::compositing::warp            # 扭曲（需要灰度 gradient 输入）
sbs::compositing::directionalwarp # 方向扭曲（需要灰度 intensity 输入）
sbs::compositing::transformation  # 2D 变换
sbs::compositing::uniform         # 纯色（灰度或彩色）
sbs::compositing::output          # 图输出
sbs::compositing::gradient        # 渐变映射（灰度→彩色，但参数设置复杂）
sbs::compositing::invert          # 反转
sbs::compositing::sharpen         # 锐化
sbs::compositing::emboss          # 浮雕
sbs::compositing::edgedetect      # 边缘检测
sbs::compositing::histogramselect # 直方图选择
```

### 库节点 — 噪波/纹理生成器 ⚠️

**所有噪波和纹理生成节点都是库节点**，需要从 SD 安装目录加载 `.sbs` 包：

```python
import os
pm = app.getPackageMgr()
base = r"C:\Program Files\Adobe\Adobe Substance 3D Designer\resources\packages"

path = os.path.join(base, "noise_perlin_noise.sbs")
pkg = pm.getUserPackageFromFilePath(path)
if not pkg:
    pkg = pm.loadUserPackage(path)
res = pkg.getChildrenResources(False)[0]
node = graph.newInstanceNode(res)
node.setPosition(float2(x, y))
```

### 常用库节点 sbs 文件名

| 类别 | 文件名 | 输出端口 | 说明 |
|------|--------|----------|------|
| **噪波** | `noise_perlin_noise.sbs` | `output` | 柏林噪波（通用） |
| | `noise_clouds_1.sbs` | `output` | 云朵噪波（柔和） |
| | `noise_cells_1.sbs` | `output` | 细胞纹理 |
| | `noise_fractal_sum_base.sbs` | `output` | 分形噪波 |
| | `noise_gaussian_noise.sbs` | `output` | 高斯噪波 |
| | `noise_voronoi.sbs` | `output` | 泰森多边形 |
| **方向性** | `wood_fibers_1.sbs` | `Wood_Fibers` | 木纹纤维 |
| | `fibers_1.sbs` | 查询 | 纤维纹理 |
| | `noise_directional_noise_1.sbs` | 查询 | 方向性噪波 |
| | `noise_directional_scratches.sbs` | 查询 | 方向性划痕 |
| **图案** | `pattern_stripes.sbs` | 查询 | 条纹 |
| | `noise_grunge_map_001.sbs` | 查询 | 做旧纹理 |
| | `noise_messy_fibers_1.sbs` | 查询 | 杂乱纤维 |

**⚠️ 库节点的输出端口名不是 `unique_filter_output`！** 创建后必须查询：
```python
for p in node.getProperties(SDPropertyCategory.Output):
    print(p.getId())
```

---

## 规则 6：通道格式 🔴

SD 中最重要的概念。格式不匹配 = 节点全黑或结果错误。

### 图全局格式（创建图后必须设置）

```python
# 新图默认 $format=0 (Grayscale) + $outputsize=(0,0)，不设置全黑！
fmt_prop = graph.getPropertyFromId("$format", SDPropertyCategory.Input)
if fmt_prop:
    graph.setPropertyValue(fmt_prop, SDValueInt.sNew(1))  # 1=Color

size_prop = graph.getPropertyFromId("$outputsize", SDPropertyCategory.Input)
if size_prop:
    graph.setPropertyValue(size_prop, SDValueInt2.sNew(int2(10, 10)))  # 1024²
```

### 节点通道格式规则

| 节点 | 输入格式 | 输出格式 | 说明 |
|------|----------|----------|------|
| Uniform (`colorswitch=False`) | — | **灰度** | 用于 Warp gradient、Height |
| Uniform (`colorswitch=True`) | — | **彩色** | 用于 BaseColor 颜色源 |
| 噪波库节点 | — | **灰度** | Perlin/Clouds/Cells 等 |
| Warp | input1=任意, **inputgradient=灰度** | 跟随 input1 | gradient 必须灰度 |
| DirectionalWarp | input1=任意, **inputintensity=灰度** | 跟随 input1 | intensity 必须灰度 |
| Normal | **灰度**（高度图） | **彩色**（法线图） | 输入必须灰度 |
| Gradient Map | **灰度** | **彩色** | 灰度→颜色映射 |
| Blend | source=彩色, dest=彩色, opacity=灰度 | 彩色 | 做颜色着色用 |
| Levels / Curve | 任意 | 跟随输入 | 纯调整节点 |
| Output | 任意 | — | BaseColor/Normal=彩色, Roughness/Height/Metallic=灰度 |

### 着色方案：灰度→彩色

Gradient Map 的渐变参数（`gradientrgba`）通过 API 设置很复杂。推荐用 **Blend 着色**：

```
[Uniform 深色(Color)] → Blend.source
[Uniform 浅色(Color)] → Blend.destination
[灰度纹理]            → Blend.opacity（用灰度纹理做混合遮罩）
Blend 输出 = 彩色纹理
```

---

## 规则 7：连接 API

```python
# 连接（推荐方式）
conn = src.newPropertyConnectionFromId("output_port", dst, "input_port")

# 断开（安全方式）
prop = node.getPropertyFromId("input1", SDPropertyCategory.Input)
node.deletePropertyConnections(prop)

# ⛔ 禁止 connection.disconnect()（SD 挂起 5-10 分钟）
# ❌ SDProperty 没有 connect() 方法
```

### 常见端口 ID

| 节点 | 输入端口 | 输出端口 |
|------|----------|----------|
| blend | source, destination, opacity | unique_filter_output |
| levels/curve/hsl/blur/normal | input1 | unique_filter_output |
| warp | input1, **inputgradient** | unique_filter_output |
| directionalwarp | input1, **inputintensity** | unique_filter_output |
| output | inputNodeOutput | (usage id) |
| 库节点 | **查询** | **查询**（不是 unique_filter_output） |

---

## 规则 8：PBR 输出

```python
out = graph.newNode("sbs::compositing::output")
out.setPosition(float2(x, y))
# identifier 决定 PBR 通道
ip = out.getPropertyFromId("identifier", SDPropertyCategory.Annotation)
out.setPropertyValue(ip, SDValueString.sNew("baseColor"))  # 或 normal/roughness/metallic/height/ambientOcclusion
```

| 通道 | identifier | 期望格式 |
|------|------------|----------|
| BaseColor | `baseColor` | 彩色 |
| Normal | `normal` | 彩色（RGB法线） |
| Roughness | `roughness` | 灰度 |
| Metallic | `metallic` | 灰度 |
| Height | `height` | 灰度 |
| AO | `ambientOcclusion` | 灰度 |

---

## 规则 9：创建新包和图

```python
pkg_mgr = app.getPackageMgr()
pkg = pkg_mgr.newUserPackage()

from sd.api.sbs.sdsbscompgraph import SDSBSCompGraph
graph = SDSBSCompGraph.sNew(pkg)
graph.setIdentifier("MyMaterial")

# 立即初始化格式！
fmt_p = graph.getPropertyFromId("$format", SDPropertyCategory.Input)
graph.setPropertyValue(fmt_p, SDValueInt.sNew(1))
size_p = graph.getPropertyFromId("$outputsize", SDPropertyCategory.Input)
graph.setPropertyValue(size_p, SDValueInt2.sNew(int2(10, 10)))

# 保存
pkg_mgr.savePackageAs(pkg, r"C:\path\to\file.sbs")
```

赋值 `graph = ...` 后 adapter 会记住，下次调用 `graph` 自动指向新图。

### ❌ 常见错误 API

| 错误 | 正确 |
|------|------|
| `pkg_mgr.newPackage()` | `pkg_mgr.newUserPackage()` |
| `pkg.saveAsFile(path)` | `pkg_mgr.savePackageAs(pkg, path)` |
| `ui_mgr.setCurrentGraph()` | 不存在 |
| `pkg_mgr.getPackages()` | `pkg_mgr.getUserPackages()`（getPackages 遍历系统包会超时） |

---

## 规则 10：⛔ 致命操作

| 操作 | 后果 |
|------|------|
| `graph.newNode("不存在的id")` | SD 永久挂起 |
| `SDUsage.sNew()` | SD 永久挂起 |
| `connection.disconnect()` | SD 挂起 5-10 分钟 |
| `graph.getNodeDefinitions()` | 可能超时 |
| `pkg_mgr.getPackages()` | 遍历系统包超时 |
| Uniform 做纹理源 | 不会报错但结果全黑/均匀色 |

---

## 推荐工作流

1. `get_context` — 确认连接和图状态
2. **分析目标材质特征**（规则 0）
3. **查 `sd-learned-recipes`** — 找相似材质配方参考，了解该类材质用哪些纹理源
4. **查 `sd-node-catalog`** — 确认库节点的 sbs 文件名、输出端口名、参数
5. 加载需要的库节点 sbs 包
6. 分步创建节点（每次 ≤3 个）
7. 分步连接（注意通道格式匹配）
8. 设置参数
9. `graph.compute()` + 保存
