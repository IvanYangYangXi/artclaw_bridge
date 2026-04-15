---
name: dcc-node-graph-workflow
description: >
  通用 DCC 节点图工作流：适用于所有节点图操作（UE 蓝图、SD 材质、UE 材质）。
  核心思路：先写伪代码，再映射节点，再创建连接。
  Use when AI needs to: build any node graph (Blueprint/SD/UE Material) from scratch or
  add complex logic to an existing graph. Activate BEFORE the DCC-specific skill to plan
  the approach, then switch to the specific skill for API details.
metadata:
  artclaw:
    version: 1.0.1
    author: ArtClaw
    software: all
---

# DCC 节点图通用工作流

三类 DCC 的节点图本质相同：**有向数据流 + 执行流（蓝图独有）**。
工作方式完全对应，统一用以下流程处理。

---

## 核心原则

**对节点图的理解要和对代码的理解一样严谨。**
AI 对代码逻辑（循环、条件、数据变换）的理解远强于对节点位置/引脚名的感知。
先用代码表达逻辑，再翻译成节点——出错概率大幅降低。

---

## 三类 DCC 对照表

| 概念 | UE 蓝图 | SD 材质 | UE 材质 |
|------|---------|---------|---------|
| 节点图 | EdGraph | SDGraph | MaterialGraph |
| 节点创建 | `add_graph_node` | `graph.newNode` | `create_material_expression` |
| 节点连接 | `connect_graph_pins` | `newPropertyConnectionFromId` | `connect_material_expressions` |
| 引脚/端口查询 | `query_blueprint_graph(node_guid)` | `getProperties(SDPropertyCategory.Input)` | `list_material_expressions` |
| 属性设置 | `set_node_property` | `setInputPropertyValueFromId` | `set_expression_property` |
| 编译/验证 | `compile_blueprint` → 详细错误 | `save_preview` → 截图分析 | `recompile_material` → 指令数 |
| 执行流 | Exec 引脚（then/execute） | 无（纯数据流） | 无（纯数据流） |

---

## 标准流程（5步）

### Step 1：写伪代码

用 Python/C++ 风格写出完整逻辑。**不考虑节点，只考虑逻辑。**

```python
# UE 蓝图伪代码示例
for i in range(SegmentCount):
    startDist = (i / SegmentCount) * splineLength
    endDist   = ((i + 1) / SegmentCount) * splineLength
    smc = AddComponent(SplineMeshComponent)
    smc.mesh = Mesh
    if bCanBend:
        startTan = GetTangentAtDist(startDist)
        endTan   = GetTangentAtDist(endDist)
    else:
        startTan = endTan = endPos - startPos
    smc.SetStartAndEnd(startPos, startTan, endPos, endTan)

# SD 材质伪代码示例
weave   = mesh_1(tiling=20) + rotate(90°)
warped  = warp(weave, perlin_noise(scale=4), intensity=0.05)
color   = gradient_map(warped, colors=[(0.0, dark), (0.5, mid), (1.0, light)])
output_baseColor(color)
output_height(weave)

# UE 材质伪代码示例
base_color = tex_diffuse * tint_color
roughness  = lerp(0.2, 0.9, tex_roughness.r)
metallic   = param_metallic
normal     = tex_normal
```

### Step 2：映射节点

将伪代码每一行映射到对应的节点类型和函数名。

**UE 蓝图：**
```
for i in range(N)           → K2Node_MacroInstance(MacroName="ForLoop")
i / N → float               → K2Node_CallFunction(Divide_DoubleDouble)
AddComponent(T)             → K2Node_CallFunction(AddComponentByClass) + K2Node_DynamicCast
if bCanBend                 → K2Node_CallFunction(VLerp, Alpha=bCanBend as float)
```

**SD 材质：**
```
mesh_1(tiling=20)           → 库节点 pattern_mesh_1.sbs
rotate(90°)                 → sbs::compositing::transformation
warp(src, grad, intensity)  → sbs::compositing::warp
perlin_noise                → 库节点 noise_perlin_noise.sbs
gradient_map(x, colors)     → sbs::compositing::gradient (colorswitch=True)
```

**UE 材质：**
```
tex_diffuse                 → MaterialExpressionTextureSampleParameter2D
tint_color                  → MaterialExpressionConstant3Vector
* (multiply)                → MaterialExpressionMultiply
lerp(a, b, t)               → MaterialExpressionLinearInterpolate
param_metallic              → MaterialExpressionScalarParameter
```

### Step 3：验证节点可用性

**在大规模创建前，先单独测试每种新节点类型：**
- 创建一个 → 查询其引脚/参数 → 确认与预期一致 → 再批量创建
- 特别是：不熟悉的函数名、新的节点类型、中文版 UE 的引脚名

```python
# 验证示例（UE 蓝图）
r = json.loads(unreal.BlueprintGraphEdit.add_graph_node(
    BP, "K2Node_MacroInstance", GN, 0, 0, False, "", "",
    json.dumps({"MacroName": "ForLoop"})
))
rq = json.loads(unreal.BlueprintGraphQuery.query_blueprint_graph(BP, node_guid=r["node_guid"]))
node = rq.get("node", {})
print([p["name"] for p in node.get("inputs", [])])   # 确认引脚名
print([p["name"] for p in node.get("outputs", [])])
```

### Step 4：分组创建 + 即时验证

**每组 3-8 个节点，创建后立即验证，不要一次性创建整个图。**

| DCC | 验证方式 | 验证时机 |
|-----|---------|---------|
| UE 蓝图 | `compile_blueprint` → 检查 errors | 每组节点创建并连接后 |
| SD 材质 | `save_preview` → 截图分析 | 每个关键节点连到 output 后 |
| UE 材质 | `recompile_material` → 检查 compile_success | 每阶段完成后 |

**分组原则：**
- 一个语义完整的功能块放一组（如"距离计算"、"Spline查询"、"着色管线"）
- 中间如果报错，只需重建当前组，不影响已完成的组
- 连接前先确认所有节点 GUID

### Step 5：布局整理

最后统一调整节点位置，提高可读性。

**布局原则：**
- 数据流从**左到右**（输入在左，输出在右）
- 执行流（蓝图 exec 链）沿 **y=0** 水平展开
- 数据节点放在 exec 链**下方**（y=300~1200）
- 节点间距：X 方向 ≥400px，Y 方向 ≥200px
- 长距离连接用**额外的 getter 节点**（每个 getter 负责 1-2 个目标）或 Reroute 节点

```python
# UE 蓝图批量设置位置
positions = [
    {"guid": CS,   "x": 0,    "y": 0},     # exec 链
    {"guid": FOR,  "x": 500,  "y": 0},
    {"guid": ADD,  "x": 1000, "y": 0},
    {"guid": SPL1, "x": 500,  "y": 350},   # 数据节点在下方
    {"guid": GL,   "x": 900,  "y": 350},
]
unreal.BlueprintGraphEdit.set_node_positions(BP, json.dumps(positions))
```

---

## 常见错误模式

| 错误 | 原因 | 修复 |
|------|------|------|
| 节点创建成功但引脚为空 | 需要特殊初始化（VariableGet/MacroInstance/DynamicCast）| 查 DCC specific skill |
| 连接失败：引脚不存在 | 猜了引脚名 | 先 query 节点确认实际引脚名 |
| 节点可用但功能错误 | 节点映射时选错了 | 重看伪代码，重新映射 |
| 编译成功但运行结果不对 | 逻辑映射有误（如 A/B 接反） | 回到伪代码验证映射 |
| 所有 start 位置相同 | 某个数据引脚断开，用了默认值 | query 节点检查未连接引脚 |

---

## 配套 Skill 参考

| 场景 | 使用的 Skill |
|------|------------|
| UE 蓝图节点图 | `ue5-blueprint-workflow` |
| SD 材质节点图 | `sd-operation-rules` + `sd-node-ops` |
| UE 材质节点图 | `ue57_material_node_edit` |
| Blender 材质 | `blender-material-ops` |
