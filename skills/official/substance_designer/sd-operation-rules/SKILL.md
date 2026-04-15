---
name: sd-operation-rules
description: >
  Substance Designer 操作通用规则。所有 SD 图操作前必读。
  Use when AI needs to: (1) perform any SD graph modification,
  (2) check post-operation best practices, (3) understand SD API constraints.
  Substance Designer only (run_python).
metadata:
  artclaw:
    version: 0.0.2
    author: ArtClaw
    software: substance_designer
---

# SD 操作规则

> 📋 **通用节点图工作流**（伪代码→映射→分组创建→验证→布局）见 `dcc-node-graph-workflow` skill。
> 本 skill 专注 SD 的 **API 约束、截图验证流程和致命陷阱**。

---

## 🔴 代码拆分规则

**每次 run_python 调用做一个逻辑步骤**（通常 3-5 个节点操作）。

**避免：**
- ⛔ 一次调用创建整个图（10+ 节点 + 全部设参 + 全部连线）→ 中间报错后续全丢
- ⛔ 截图和预写分析放同一次调用 → 分析不是基于真实观察

**推荐模式：**
```
调用1: 创建 mesh_1 + levels，设参连线
调用2: save_preview(levels) ← 只截图，不写分析
       → 看到图后分析 → 通过则继续
调用3: 创建 transformation × 2 + blend
调用4: save_preview(blend) → 分析 → 通过则继续
```

---

## 🔴 参数设置规则

**⛔ 禁止猜测参数名和类型！创建节点后第一步永远是动态查询。**

```python
# ✅ 正确：先查询，再设值
node = graph.newNode("sbs::compositing::levels")
for p in node.getProperties(SDPropertyCategory.Input):
    pid = p.getId()
    if pid.startswith("$"): continue
    v = node.getPropertyValue(p)
    if v is None: print(f"  PORT: {pid}")      # 连接端口
    else: print(f"  PARAM: {pid} = {v.get()} ({type(v).__name__})")
```

**已知陷阱：**

| 节点 | 参数名 | 正确类型 | 常见错误 |
|------|--------|---------|---------|
| levels | `levelinlow/levelinhigh/levelinmid` | **Float4** | 猜成 `inlow` + Float |
| blend | `opacitymult` (标量) | SDValueFloat | 猜成 `opacity`（那是连接端口） |
| uniform | `colorswitch` | SDValueBool | ⛔ 不设 = 输出永远灰色 |
| 库节点 Enum | — | **SDValueInt.sNew(n)** | 无 SDValueEnum.sNew |

---

## 🔴 截图驱动的迭代循环

### 截图两步法（⛔ 必须分两次调用）

**步骤 1** (run_python): 只截图
```python
save_preview(node, "CP1_structure")
```

**步骤 2** (看到图后): 逐维度分析，写出判断

#### 4 个必须分析的维度

| 维度 | 检查点 | 问题信号 |
|------|--------|---------|
| **亮度/对比度** | 是否有足够动态范围？ | 全黑→立即向上游追查 |
| **图案正确性** | 是否符合预期？ | artifact/意外图案 |
| **密度/比例尺** | 基于物理尺度声明检查 | 太稀/太密 → 调 scale |
| **CG 感** | 看起来是否过于规则？ | 需要 warp/噪波打破 |

**分析输出格式：**
```
[CP1] 分析 (attempt N/3):
  亮度: 正常/全黑/...
  图案: 正确/有artifact/...
  密度: 合理/过密/...
  CG感: 无/有...
  判定: ✅通过 / ⛔需修复
  修复: [根因 → 具体改法]
```

**修复循环（⛔ 最多 3 次，超出则报告并停止）：**
```
截图 → 分析 → 有问题?
  → 向上游逐节点截图追查 → 找第一个出问题的节点
  → 修复 → 重新截图验证 → retry_count++
  → retry_count >= 3? 停！汇报，请求人工指导
```

---

## 🔴 参考工程优先原则

**⛔ 禁止从零构建功能模块！先查参考工程有没有可复用的。**

| 优先级 | 方式 | 示例 |
|--------|------|------|
| 1⃣ 加载参考工程子图 | loadUserPackage → newInstanceNode | Creases_Filter、fabric_weathering |
| 2⃣ 复制参考工程节点链参数 | 按参考工程参数值重建 | fabric_009 的 mesh_1+transformation 编织链 |
| 3⃣ 复用参考工程管线架构 | 替换纹理源，保留管线结构 | fabric_009 的 5层着色架构 |
| 4⃣ 自己构建 | 仅当参考工程完全没有时 | — |

**Phase 1.5 必须声明：**
```
功能模块拆解:
  1. [编织结构] → 来源: fabric_009 mesh_1+transformation 链 (搬运)
  2. [褶皱效果] → 来源: fabric_002 Creases_Filter 子图 (加载实例)
  3. [着色管线] → 来源: fabric_009 5层着色架构 (复用结构, 调整颜色)
  4. [xxx]     → 来源: 无参考, 需自行构建
```

---

## API 速查

### 预注入变量（直接用）
`sd`, `app`, `graph`, `S`, `W`, `SDPropertyCategory`, `float2/3/4`, `ColorRGBA`
`SDValueFloat/Int/Bool/String/Float2/Float3/Float4/ColorRGBA`, `save_preview`

⛔ **禁止** `from sd.api.xxx import` — 会死锁！
唯一例外: `from sd.api.sbs.sdsbscompgraph import SDSBSCompGraph` 和 `import os`

### 图/节点操作

```python
# 获取节点
nodes = graph.getNodes()
for i in range(nodes.getSize()):
    n = nodes.getItem(i)
    print(n.getIdentifier(), n.getDefinition().getId())

# 按 UID 查找
node = graph.getNodeFromId("1567756690")

# 输出节点
output_nodes = graph.getOutputNodes()
```

### 连接（⛔ 原子 vs 库节点输出端口名不同！）

```python
# 原子节点输出端口永远是 "unique_filter_output"
levels.newPropertyConnectionFromId("unique_filter_output", blend, "input1")

# 库节点输出端口各不相同，必须先查询
for p in lib_node.getProperties(SDPropertyCategory.Output):
    print(p.getId())  # 可能是 "output" / "Wood_Fibers" / "Noise_Zoom" 等
lib_node.newPropertyConnectionFromId("output", next_node, "input1")

# 断开（⛔ 禁止 connection.disconnect() — SD挂起）
prop = node.getPropertyFromId("input1", SDPropertyCategory.Input)
node.deletePropertyConnections(prop)
```

### 库节点加载

```python
import os
pm = app.getPackageMgr()
base = r"C:\Program Files\Adobe\Adobe Substance 3D Designer\resources\packages"
path = os.path.join(base, "noise_perlin_noise.sbs")
pkg = pm.getUserPackageFromFilePath(path) or pm.loadUserPackage(path)
node = graph.newInstanceNode(pkg.getChildrenResources(False)[0])
```

### 新建图（⛔ 必须立即设格式，否则 SD 崩溃）

```python
from sd.api.sbs.sdsbscompgraph import SDSBSCompGraph
pkg = app.getPackageMgr().newUserPackage()
g = SDSBSCompGraph.sNew(pkg)
g.setIdentifier("MyMaterial")
g.setPropertyValue(g.getPropertyFromId("$format", SDPropertyCategory.Input), SDValueInt.sNew(1))
g.setPropertyValue(g.getPropertyFromId("$outputsize", SDPropertyCategory.Input), SDValueInt2.sNew(int2(2, 2)))  # ⛔ (2,2)=1024² 不是(10,10)!
app.getPackageMgr().savePackageAs(pkg, path)
# ⛔ 必须重新获取 graph（sNew 返回的会 stale）
pkg = app.getPackageMgr().getUserPackageFromFilePath(path)
graph = pkg.getChildrenResources(False)[0]
```

### PBR Output + Usage（⛔ 不设 usages → 3D 视口不显示）

```python
from sd.api.sdusage import SDUsage
from sd.api.sdvalueusage import SDValueUsage
from sd.api.sdvaluearray import SDValueArray
from sd.api.sdtypeusage import SDTypeUsage

out = graph.newNode("sbs::compositing::output")
out.setPropertyValue(out.getPropertyFromId("identifier", SDPropertyCategory.Annotation), SDValueString.sNew("baseColor"))
out.setPropertyValue(out.getPropertyFromId("label", SDPropertyCategory.Annotation), SDValueString.sNew("BaseColor"))
arr = SDValueArray.sNew(SDTypeUsage.sNew(), 0)
arr.pushBack(SDValueUsage.sNew(SDUsage.sNew("baseColor", "RGBA", "")))  # ⛔ 必须传3个参数！
out.setPropertyValue(out.getPropertyFromId("usages", SDPropertyCategory.Annotation), arr)
# inputNodeOutput: prev_node.newPropertyConnectionFromId("unique_filter_output", out, "inputNodeOutput")
```

---

## ⛔ 致命操作

| 操作 | 后果 |
|------|------|
| `graph.newNode("不存在的id")` | SD 永久挂起 |
| `SDUsage.sNew()` 无参数 | SD 永久挂起 |
| `$outputsize` 设 (10,10) | Cooker 爆内存 → SD 死亡 |
| `connection.disconnect()` | SD 挂起 5-10 分钟 |
| `sbs::compositing::invert` | 不存在（返回 None） |
| `blend.setInputPropertyValueFromId("opacity", ...)` | DataIsReadOnly |
| exec 闭包中用 def | import 不可见，全部内联 |

---

## 结构信号共享原则

**所有通道的变化必须由同一结构信号驱动：**
```
编织骨架 → 同时作为 Height blend.opacity + BaseColor blend.opacity
non_uniform_blur → 同时作为 Height warp.gradient + BaseColor warp.gradient
```
**反模式：** Height 用一个噪波，BaseColor 用另一个 → 通道不关联 → 假。

---

## 阶段检查点

| 阶段 | 检查内容 |
|------|---------|
| CP1: 主结构 | 图案骨架、密度、灰度范围 |
| CP2: 质感处理 | CG 感消除、对比度保持 |
| CP3: 着色 | 颜色、过渡自然度 |
| CP4: 通道联动 | 各通道变化是否关联 |
| CP5: PBR 输出 | 全通道逐个检查 |
