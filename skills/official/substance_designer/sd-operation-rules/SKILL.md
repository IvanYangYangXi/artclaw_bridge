---
name: sd-operation-rules
description: >
  Substance Designer 操作通用规则。所有 SD 图操作前必读。
  Use when AI needs to: (1) perform any SD graph modification,
  (2) check post-operation best practices, (3) understand SD API constraints.
  Substance Designer only (run_python).
metadata:
  artclaw:
    version: 0.3.0
    author: ArtClaw
    software: substance_designer
---

# SD 操作规则（精简版）

> 详细材质分析框架、尺度规划、着色架构见 `references/` 目录下的参考文档。

---

## 🔴 代码拆分规则

**每次 run_python 调用可以做一个完整的逻辑步骤**（通常 5-8 个节点操作以内）。

合理分组原则：
- **一个功能组放一次调用**：创建一组相关节点 + 查询参数 + 设参 + 连线 → OK
- **截图单独调用**：截图调用和分析分开，先看到图再写判断
- **首次使用的节点先查询参数**：对不熟悉的节点，创建+查询参数可以单独一次调用，确认参数名后再设值

**核心原则：如果某步出错不会导致大量工作丢失，就可以合并。**

**避免的模式：**
- ⛔ 一次调用创建整个图（10+ 节点 + 全部设参 + 全部连线）→ 中间报错后续全丢
- ⛔ 截图和预写分析文本放同一次调用 → 分析不是基于真实观察

**推荐模式示例：**
```
调用1: 创建 mesh_1 + levels，设参连线，连到 output 以便 compute
调用2: 截图 levels 输出 → 确认灰度范围正确
  → ⛔ 如果全黑/异常 → 立即调参 → 重新截图(最多3次)
  → ✅ 通过 → 继续
调用3: 创建 transformation × 2 + blend，设参连线
调用4: 截图 blend 输出 → 确认混合结果正确
  → ⛔ 全黑 → 向上游逐节点截图追查 → 找到根因 → 修复 → 重新验证
  → ✅ 通过 → 继续
调用5: 创建后处理链(blur + warp + sharpen)
调用6: 截图 sharpen → CP2
```

## 🔴 参数设置规则

**⛔ 禁止猜测参数名和类型！创建节点后第一步永远是动态查询。**

```python
# ✅ 正确：先查询，再设值
node = graph.newNode("sbs::compositing::levels")
for p in node.getProperties(SDPropertyCategory.Input):
    pid = p.getId()
    if pid.startswith("$"): continue
    v = node.getPropertyValue(p)
    if v is None:
        print(f"  PORT: {pid}")  # 连接端口
    else:
        print(f"  PARAM: {pid} = {v.get()} ({type(v).__name__})")
# 看到输出后再设值
```

```python
# ⛔ 错误：直接猜参数名
node.setInputPropertyValueFromId("inlow", SDValueFloat.sNew(0.5))  # 可能是 levelinlow，类型可能是 Float4
```

**已知陷阱：**
- levels: 参数名是 `levelinlow`/`levelinhigh`/`levelinmid`，类型是 **Float4** 不是 Float
- blend: `opacity` 是连接端口不是参数，用 `opacitymult` 设标量值
- transformation: `matrix22` 类型是 Float4 (x=m00, y=m01, z=m10, w=m11)
- uniform: **必须显式设 `colorswitch`**！False=灰度(默认), True=彩色。不设=灰色输出
- 库节点 Enum 参数: 类型显示为 `SDValueEnum`，**用 `SDValueInt.sNew(n)` 设值**（无 SDValueEnum.sNew）
  - 例: gradient_linear_1 的 `rotation`: 0=0°, 1=90°, 2=180°, 3=270°

## 🔴 执行流程（必须逐步遵循，不可跳步）

### Phase 1: 分析规划（动手前）
1. `get_context` 确认编辑器状态
2. 材质科学分析（参考 `references/material_analysis.md`）
3. 声明物理覆盖面积: `"1024² = Xcm × Xcm, 1px = Ymm"`
4. 查 `sd-learned-recipes` 找配方参考
5. 查 `sd-node-catalog` 确认节点 sbs 文件名

### 🔴 参考工程优先原则（Phase 1.5）

**⛔ 禁止从零自己构建功能模块！** 优先从参考/示例工程中搬运已验证的节点组合。

**思考流程：**
1. **分析目标材质属于哪个类别** → 查 sd-learned-recipes 找对应的参考工程
2. **列出需要的功能模块**（如编织结构、后处理链、着色管线、褶皱效果等）
3. **逐个模块检查参考工程中是否有现成的**：
   - 有 → **直接复用**（复制节点组合 + 参数值），只微调适配
   - 没有 → 才考虑自己构建
4. **组合思维**: Agent 的价值在于**选择正确的模块并组合**，不是自己写底层实现

**复用方式（按优先级排序）：**

| 优先级 | 方式 | 示例 |
|--------|------|------|
| 1⃣ **加载参考工程子图** | loadUserPackage → newInstanceNode | Creases_Filter、stains、fabric_weathering |
| 2⃣ **复制参考工程的节点链参数** | 按参考工程的参数值创建相同节点链 | fabric_009 的 mesh_1+levels+transformation 编织链 |
| 3⃣ **参考工程的管线设计** | 复用管线架构，替换具体纹理源 | fabric_002 的着色管线结构(gradient_linear→gradient_map×N→blend×N) |
| 4⃣ 自己构建 | 仅当参考工程中完全没有可复用模块时 | — |

**示例：做牛仔布**
```
✅ 正确: "fabric_009 的编织链用 mesh_1+transformation，我直接用相同参数"
✅ 正确: "fabric_002 有 Creases_Filter 子图，直接 loadUserPackage 实例化"
✅ 正确: "fabric_009 用 8 次 warp 消除 CG 感，我照搬 intensity 参数"
⛔ 错误: "我自己用 perlin_noise 做编织结构"
⛔ 错误: "我自己用 blur+levels 模拟褶皱效果"
```

**Agent 规划输出格式（Phase 1.5 必须声明）：**
```
功能模块拆解:
  1. [编织结构] → 来源: fabric_009 mesh_1+transformation 链 (搬运)
  2. [后处理链] → 来源: fabric_009 warp×8 + non_uniform_blur (搬运参数)
  3. [褶皱效果] → 来源: fabric_002 Creases_Filter 子图 (加载实例)
  4. [着色管线] → 来源: fabric_009 5层着色架构 (复用结构, 调整颜色值)
  5. [xxx] → 来源: 无参考, 需自行构建 ← 仅这种情况才自己写
```

### Phase 2: 构建（截图驱动的迭代循环）

**⛔ 核心原则: 每步操作后截图 → 分析 → 问题则原地修复并重新验证 → 通过后才进下一步。**
**⛔ 绝对禁止: 发现问题后记个 TODO 继续往下走。问题必须当场解决！**

#### 截图粒度：逐节点，不是逐功能组

**每创建一个关键节点并连线后，立即截图该节点的输出。**
- ✅ 创建 levels → 截图 levels 输出 → 确认灰度范围正确 → 创建下一个节点
- ✅ 创建 blend → 截图 blend 输出 → 确认混合结果正确 → 继续
- ⛔ 创建 5 个节点链 → 只截最后一个 → 中间某步就已经黑了但不知道

**可以合并截图的情况**: 连续的简单操作（如多个 transformation 只做坐标变换，不改变灰度范围），
可以在最后一个 transformation 后统一截图。但只要涉及**灰度范围变化**的操作（levels/blend/curve），
必须单独截图确认。

#### 检查点修复循环（⛔ 最多 3 次重试）

```
截图节点输出
  → 视觉分析（4维度）
  → 通过? 
     YES → 进入下一步
     NO  → 诊断根因（向上游逐节点截图追查）
           → 修改参数或重建节点
           → 重新截图验证
           → 仍不通过? retry_count += 1
              → retry_count >= 3? 
                 YES → ⛔ 停！汇报问题，请求人工指导
                 NO  → 继续修复循环
```

**修复时必须做的事：**
1. **向上游追查**: 不是只看当前节点，而是从当前节点往上游逐个截图，找到**第一个出问题的节点**
2. **修改后重新截图**: 改了参数后必须重新截图同一节点验证修复效果
3. **确认下游没被破坏**: 修改上游节点后，下游所有已截图的节点都需要重新验证

**重试 3 次仍不通过的处理:**
- 输出已尝试的方案和每次结果
- 明确说明卡在哪个维度（亮度/图案/密度/CG感）
- 提出可能的替代方案供用户选择
- **不要自行跳过继续下一阶段**

#### 阶段检查点

| 阶段 | 内容 | 截图检查（4维度） | 不通过则 |
|------|------|--------|----------|
| **1. 主结构** | 图案骨架，**每个关键节点单独截图** | **🔍CP1: 每个中间节点亮度正常？最终图案对？密度对？** | ⛔ 修复循环(≤3次) |
| **2. 质感处理** | 软化/扭曲/锐化 | **🔍CP2: CG感消除？对比度保持？** | ⛔ 修复循环(≤3次) |
| **3. 着色** | 灰度→彩色 | **🔍CP3: 颜色对？过渡自然？** | ⛔ 修复循环(≤3次) |
| **4. 通道联动** | 多通道共享结构信号 | **🔍CP4: 各通道变化关联？** | ⛔ 修复循环(≤3次) |
| **5. PBR输出** | 全通道截图 | **🔍CP5: 全通道逐个检查** | ⛔ 修复循环(≤3次) |

### ⛔ compute 注意事项

**SD 只计算从源节点到 output 节点的完整链路上的节点。**
- 新建的节点如果没有连到任何 output 节点 → **不会被 compute** → 截图为空
- **解决方案**: 每个阶段完成后，确保最新节点已连接到至少一个 output 节点，再截图
- **中间节点截图技巧**: 临时把中间节点连到 output → compute → 截图 → 断开恢复原连接
- 如果截图返回 "节点无输出值"，先检查节点到 output 的连接链路是否完整

### 截图方法
```python
# save_preview 是预注入函数，自动缩放+jpg+[IMAGE:]标记
save_preview(node, "CP1_structure")
# 如果变量丢失:
node = graph.getNodeFromId("node_uid")
save_preview(node, "CP1_structure")
```

### ⛔ 截图分析两步法

**步骤1** (run_python): `save_preview(node, "CP1")` ← 只截图，不写分析

**步骤2** (看到图片后): 对照以下维度逐项分析，写出判断：

#### 必须分析的 4 个维度

**A. 亮度/对比度** — 图像是否有足够的动态范围？
- 全黑 / 接近全黑 / 全白 → ⛔ 严重问题！**立即向上游逐节点截图追查衰减位置**
- 对比度过低（灰蒙蒙一片看不清结构）→ 需要 Levels 拉伸
- 对比度合理（能清晰区分图案的亮暗区域）→ ✅

**B. 图案正确性** — 输出的图案是否符合预期？
- 纹理特征是否与目标材质匹配？（编织、噪波、网格...）
- 是否出现了不该有的 artifact？（条带、色块、重复边界）
- 是否与上一步的输出有合理的因果关系？

**C. 密度/比例尺** — 基于物理尺度声明检查
- 在声明的覆盖面积（如 10cm×10cm）下，特征数量是否合理？
- 特征尺寸是否符合真实物理尺寸？（如牛仔纱线约 0.3-0.5mm）
- 太稀疏 → 增加 tiling/scale；太密集 → 降低

**D. CG感** — 是否看起来像计算机生成的？
- 过于规则/对称 → 需要 warp/噪波打破规律
- 硬边/锐利几何边缘 → 需要 blur + sharpen 处理
- 无 → ✅

#### 分析输出格式
```
[CP1] 分析 (attempt N/3):
  亮度/对比度: [描述]
  图案正确性: [描述]
  密度/比例尺: [描述]
  CG感: [描述]
  判定: [✅通过 / ⛔需修复]
  修复方案: [如果需修复：根因是什么 → 具体改什么参数]
```

**⛔ 禁止在截图代码中 print 预写分析！必须看到图片后才写。**
**⛔ 判定为"需修复"后，必须立即执行修复 → 重新截图 → 重新分析。不能跳过！**
**⛔ "全黑"或"接近全黑"是最严重的红线信号 — 必须逐个上游节点截图，找到第一个出问题的位置！**

---

## 🔴 结构信号共享原则

**所有通道的变化必须由同一结构信号驱动：**
```
编织骨架 → 同时作为 Height blend.opacity + BaseColor blend.opacity
non_uniform_blur → 同时作为 Height warp.gradient + BaseColor warp.gradient
perlin_noise → 同时驱动两者宏观 warp
```
**反模式**: Height用一个噪波, BaseColor用另一个噪波 → 通道不关联 → 假。

---

## API 速查

### 预注入变量（直接用，不要 import）
`sd`, `app`, `graph`, `S`, `W`, `SDPropertyCategory`, `float2/3/4`, `ColorRGBA`, `SDValueFloat/Int/Bool/String/Float2/Float3/Float4/ColorRGBA`, `save_preview`

⛔ **禁止** `from sd.api.xxx import` — 会死锁！唯一例外: `from sd.api.sbs.sdsbscompgraph import SDSBSCompGraph` 和 `import os`

### 图/节点查询 API
```python
# 获取图中所有节点（返回 SDArray，不是 Python list）
nodes = graph.getNodes()
for i in range(nodes.getSize()):
    node = nodes.getItem(i)
    uid = node.getIdentifier()     # 字符串 UID (如 "1567756690")
    defn = node.getDefinition().getId()  # 定义 ID (如 "sbs::compositing::blend")
    pos = node.getPosition()       # float2
    print(f"{uid}: {defn} @ ({pos.x}, {pos.y})")

# 按 UID 精确查找
node = graph.getNodeFromId("1567756690")

# 获取输出节点
output_nodes = graph.getOutputNodes()  # 返回 SDArray

# ⛔ 不存在的 API（常见错误）:
# graph.getNodesCount()  ← 不存在！用 graph.getNodes().getSize()
# graph.getNodeFromIndex(i)  ← 不存在！用 graph.getNodes().getItem(i)
```

### 变量丢失恢复
如果之前创建的节点变量丢失（因代码中途报错），用位置或定义 ID 恢复：
```python
nodes = graph.getNodes()
for i in range(nodes.getSize()):
    n = nodes.getItem(i)
    defn = n.getDefinition().getId()
    pos = n.getPosition()
    if "sharpen" in defn:
        sharpen = n
        print(f"找到 sharpen: {n.getIdentifier()}")
        break
```

### 创建新图（⛔ 必须立即设格式）
```python
from sd.api.sbs.sdsbscompgraph import SDSBSCompGraph
pkg = app.getPackageMgr().newUserPackage()
g = SDSBSCompGraph.sNew(pkg)
g.setIdentifier("MyMaterial")
# ⛔ 不设这两行 = Cooker爆内存 → SD死亡
g.setPropertyValue(g.getPropertyFromId("$format", SDPropertyCategory.Input), SDValueInt.sNew(1))
g.setPropertyValue(g.getPropertyFromId("$outputsize", SDPropertyCategory.Input), SDValueInt2.sNew(int2(2, 2)))  # (2,2)=1024² ⛔不是(10,10)!
app.getPackageMgr().savePackageAs(pkg, path)
# ⛔ 必须重新获取graph（sNew返回的会stale）
pkg = app.getPackageMgr().getUserPackageFromFilePath(path)
graph = pkg.getChildrenResources(False)[0]
```

### 库节点加载
```python
import os
pm = app.getPackageMgr()
base = r"C:\Program Files\Adobe\Adobe Substance 3D Designer\resources\packages"
pkg = pm.getUserPackageFromFilePath(os.path.join(base, "noise_perlin_noise.sbs"))
if not pkg: pkg = pm.loadUserPackage(os.path.join(base, "noise_perlin_noise.sbs"))
node = graph.newInstanceNode(pkg.getChildrenResources(False)[0])
# ⚠️ 输出端口名不统一！必须查询:
for p in node.getProperties(SDPropertyCategory.Output): print(p.getId())
```

### 参数查询（创建节点后必做）
```python
for p in node.getProperties(SDPropertyCategory.Input):
    pid = p.getId()
    if pid.startswith("$"): continue
    v = node.getPropertyValue(p)
    val = v.get() if v else None
    if val is None: print(f"  PORT: {pid}")  # 连接端口，不能赋值
    else: print(f"  PARAM: {pid} = {val} ({type(v).__name__})")
```

### 连接
```python
# ⛔ 原子节点输出端口 = "unique_filter_output"（不是 "output"！）
src.newPropertyConnectionFromId("unique_filter_output", dst, "input_port")
# 库节点输出端口各不同，必须查询
lib_node.newPropertyConnectionFromId("output", dst, "input_port")  # 或 "Wood_Fibers" 等
# 断开: node.deletePropertyConnections(node.getPropertyFromId("input1", SDPropertyCategory.Input))
# ⛔ 禁止 connection.disconnect() — SD挂起5-10分钟
```

### ⛔ compute 行为
SD 只计算有完整链路到 output 节点的节点。新建节点如果没连到 output → getPropertyValue 返回 None。
**每个阶段完成后先确认节点到 output 的链路再截图。** 如果中间链断开，可以临时连到 output 截图后再断开。

### Blend 节点
- `opacity` = **连接端口**（接灰度遮罩）⛔ 不能 setInputPropertyValueFromId
- `opacitymult` = **标量参数** (0~1) ✅ 用这个控制不透明度
- blendingmode: 0=Copy, 1=Add, 2=Subtract, 3=Multiply, 5=Max, 6=Min, 9=Overlay

### Output + Usage（⛔ 必须设 usages 否则 3D 视口不显示）
```python
out = graph.newNode("sbs::compositing::output")
ip = out.getPropertyFromId("identifier", SDPropertyCategory.Annotation)
out.setPropertyValue(ip, SDValueString.sNew("baseColor"))
lp = out.getPropertyFromId("label", SDPropertyCategory.Annotation)
out.setPropertyValue(lp, SDValueString.sNew("BaseColor"))
from sd.api.sdusage import SDUsage
from sd.api.sdvalueusage import SDValueUsage
from sd.api.sdvaluearray import SDValueArray
from sd.api.sdtypeusage import SDTypeUsage
arr = SDValueArray.sNew(SDTypeUsage.sNew(), 0)
arr.pushBack(SDValueUsage.sNew(SDUsage.sNew("baseColor", "RGBA", "")))
out.setPropertyValue(out.getPropertyFromId("usages", SDPropertyCategory.Annotation), arr)
```

### ⛔ 致命操作
| 操作 | 后果 |
|------|------|
| `graph.newNode("不存在的id")` | SD永久挂起 |
| `SDUsage.sNew()` 无参数 | SD永久挂起 |
| `$outputsize` 设 (10,10) | Cooker爆内存→SD死亡 |
| `connection.disconnect()` | SD挂起5-10分钟 |
| `sbs::compositing::invert` | 不存在(返回None) |
| `blend.set...("opacity", ...)` | DataIsReadOnly |

### exec 闭包陷阱
`import` 在 `def` 内不可见。全部内联写，不用 def。

### 持久化命名空间
v2.7+ 变量跨调用保留。但最佳实践仍是：同一功能组（创建+设参+连线）放同一次调用。
