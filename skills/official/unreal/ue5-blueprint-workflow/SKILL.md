---
name: ue5-blueprint-workflow
description: >
  UE5.6/UE5.7 Blueprint graph workflow for feature implementation, input events, node wiring, and graph validation.
  Use when requests involve adding Blueprint logic, keyboard input behavior, function chains, event graph edits, or pin-level connection guidance.
---

# Blueprint Graph Editing — Python API Reference

> 📋 **通用节点图工作流**（伪代码→映射→分组创建→验证→布局）见 `dcc-node-graph-workflow` skill。
> 本 skill 专注 UE 蓝图的 **API 细节、已知陷阱和节点类名速查**。

ArtClaw 插件通过 `UEClawBridgeAPI` C++ 模块暴露了完整蓝图图编辑 API，Python 可直接调用。

## API 总览

| Python 类 | 方法 | 用途 |
|---|---|---|
| `BlueprintGraphQuery` | `query_blueprint_graph(asset, graph, type, guid, search, positions)` | 查询图/节点/引脚 |
| | `list_blueprint_callables(asset)` | 列出事件/函数/宏入口 |
| `BlueprintGraphEdit` | `add_graph_node(asset, class, graph, x, y, auto_pos, conn_node, conn_pin, props_json)` | 添加节点 |
| | `remove_graph_node(asset, guid)` | 删除节点 |
| | `set_node_positions(asset, positions_json)` | 批量设置位置 |
| | `create_function_graph(asset, name, public, return_json, params_json)` | 创建函数图 |
| `BlueprintGraphConnect` | `connect_graph_pins(asset, src, src_pin, tgt, tgt_pin)` | 连接引脚 |
| | `disconnect_graph_pin(asset, node, pin, tgt, tgt_pin)` | 断开引脚 |
| | `batch_connect_pins(asset, connections_json)` | 批量连接 |
| `BlueprintNodeProperty` | `set_node_property(asset, guid, props_json)` | 设置节点属性/引脚默认值 |
| | `compile_blueprint(asset)` | 编译蓝图（返回详细错误） |
| | `set_blueprint_variable(asset, name, type_json, is_array, category)` | 创建/修改变量 |
| | `validate_blueprint_structure(asset, auto_fix)` | 验证蓝图结构 |

---

## ⚠️ 已知陷阱（今天踩过的坑）

### 1. GUID 格式
- `add_graph_node` 返回带连字符：`67AA3CEF-4779-605E-5C56-DF9471FAD33F`
- `batch_connect_pins` / `query_blueprint_graph(node_guid=...)` 用**无连字符**：`67AA3CEF4779605E5C56DF9471FAD33F`
- 转换：`guid.replace("-", "")`
- **实际上两者都能用，但 query 返回的 GUID 是无连字符的，直接用 query 返回值最安全**

### 2. VariableGet / VariableSet 节点
```python
# ✅ 正确：创建后有正确引脚（蓝图必须先编译，GeneratedClass 需包含该变量）
unreal.BlueprintGraphEdit.add_graph_node(
    BP, "K2Node_VariableGet", GN, x, y, False, "", "",
    json.dumps({"VariableName": "MyVar"})
)
# ⚠️ 前提：蓝图必须先编译过，SegmentCount 等变量存在于 GeneratedClass
# 如果变量不存在于 GeneratedClass，引脚会是空的
```

### 3. ForLoop 宏（K2Node_MacroInstance）
```python
# ⚠️ 必须先加载宏库！否则宏找不到，引脚为空
unreal.load_asset("/Engine/EditorBlueprintResources/StandardMacros")

# ✅ 然后才能创建
unreal.BlueprintGraphEdit.add_graph_node(
    BP, "K2Node_MacroInstance", GN, x, y, False, "", "",
    json.dumps({"MacroName": "ForLoop"})
)
# ForLoop 引脚名：IN(execute, FirstIndex, LastIndex) OUT(LoopBody, Index, Completed)
```

### 4. DynamicCast 节点
```python
# ✅ TargetType 用完整路径，引脚会自动生成
unreal.BlueprintGraphEdit.add_graph_node(
    BP, "K2Node_DynamicCast", GN, x, y, False, "", "",
    json.dumps({"TargetType": "/Script/Engine.SplineMeshComponent"})
)
# 输出引脚名（中文UE）：如 "As样条网格体组件"
# 务必 query 确认实际引脚名，不要硬编码
```

### 5. Class 类型引脚默认值
```python
# ⚠️ 对于 Class 类型引脚（如 AddComponentByClass 的 Class 引脚）
# 不能用字符串设置默认值，必须通过 set_node_property 让其走 DefaultObject 路径
# ✅ 正确
unreal.BlueprintNodeProperty.set_node_property(
    BP, ADD_GUID, json.dumps({"Class": "/Script/Engine.SplineMeshComponent"})
)
# ⛔ 注意：每次 UE 重启后，Live Coding patch 会失效，需要重新设置
```

### 6. K2Node_AddComponent 会崩溃
```python
# ⛔ 禁止直接创建 K2Node_AddComponent，会导致 UE 崩溃
# ✅ 替代方案：用 AddComponentByClass + DynamicCast
unreal.BlueprintGraphEdit.add_graph_node(
    BP, "K2Node_CallFunction", GN, x, y, False, "", "",
    json.dumps({"FunctionReference": {"MemberName": "AddComponentByClass", "MemberParent": "/Script/Engine.Actor"}})
)
# 然后接 K2Node_DynamicCast 转换类型
```

### 7. exec 闭包陷阱
```python
# ⛔ Python exec() 环境中，函数内部无法访问外部 import
def add_node(nc, props=None):
    import json  # ✅ 必须在函数内部 import
    ...

# ⛔ list comprehension 中的变量在 exec() 外层不可见
# [x for x in items if "keyword" in t]  ← t 无法访问
# ✅ 改用显式 for 循环
```

### 8. 编译错误详细信息
```python
# ✅ compile_blueprint 返回详细节点级错误
cr = json.loads(unreal.BlueprintNodeProperty.compile_blueprint(BP))
print(cr["success"])
for e in cr["errors"]:
    print(e)  # 格式: [GraphName] NodeTitle (GUID): 具体错误消息
```

### 9. Construction Script 在 spawn 时立即执行
- 蓝图放置到场景时 CS 立即执行一次（用当时的属性值）
- Python `set_editor_property` 后 CS **不会**自动重新执行
- 用户需要在编辑器中修改属性（或拖拽 Spline 点）来触发重建

---

## 常用函数 FunctionReference 速查

| 功能 | MemberName | MemberParent |
|---|---|---|
| Print String | `PrintString` | `/Script/Engine.KismetSystemLibrary` |
| 整数加减乘除 | `Add_IntInt` / `Subtract_IntInt` | `/Script/Engine.KismetMathLibrary` |
| 浮点运算 | `Divide_DoubleDouble` / `Multiply_DoubleDouble` | `/Script/Engine.KismetMathLibrary` |
| Int→Float | `Conv_IntToDouble` | `/Script/Engine.KismetMathLibrary` |
| Bool→Float | `Conv_BoolToFloat` | `/Script/Engine.KismetMathLibrary` |
| MakeTransform | `MakeTransform` | `/Script/Engine.KismetMathLibrary` |
| Vector 减法 | `Subtract_VectorVector` | `/Script/Engine.KismetMathLibrary` |
| Vector Lerp | `VLerp` | `/Script/Engine.KismetMathLibrary` |
| 获取 Spline 长度 | `GetSplineLength` | `/Script/Engine.SplineComponent` |
| 按距离获取位置 | `GetLocationAtDistanceAlongSpline` | `/Script/Engine.SplineComponent` |
| 按距离获取切线 | `GetTangentAtDistanceAlongSpline` | `/Script/Engine.SplineComponent` |
| 设置 StaticMesh | `SetStaticMesh` | `/Script/Engine.StaticMeshComponent` |
| 设置移动性 | `SetMobility` | `/Script/Engine.SceneComponent` |
| 设置 SplineMesh | `SetStartAndEnd` | `/Script/Engine.SplineMeshComponent` |
| 按类添加组件 | `AddComponentByClass` | `/Script/Engine.Actor` |

---

## 常用节点类名

| 类名 | 用途 | 注意事项 |
|---|---|---|
| `K2Node_CallFunction` | 函数调用 | 必须设 FunctionReference |
| `K2Node_VariableGet` | 读取变量 | 需先编译蓝图；需设 VariableName |
| `K2Node_VariableSet` | 设置变量 | 同上 |
| `K2Node_MacroInstance` | 宏（ForLoop等）| 必须先 load StandardMacros；需设 MacroName |
| `K2Node_DynamicCast` | Cast To | 需设 TargetType；query 确认输出引脚名 |
| `K2Node_IfThenElse` | Branch | 引脚：Condition/True/False |
| `K2Node_Knot` | Reroute 节点 | 引脚：InputPin/OutputPin |
| `K2Node_Event` | 内置事件 | |
| `K2Node_CustomEvent` | 自定义事件 | |
| `K2Node_FunctionEntry` | 函数入口 | |
| `K2Node_FunctionResult` | 函数返回 | |
| `K2Node_SpawnActorFromClass` | SpawnActor | |
| `K2Node_MakeArray` | 创建数组 | |
| `K2Node_Self` | Self 引用 | |
| `K2Node_Sequence` | Sequence | |
| `K2Node_Select` | Select | |
| `K2Node_SwitchInteger` | Switch on Int | |
| `K2Node_Timeline` | 时间轴 | |

---

## 布局规范

- exec 链沿 **y=0** 从左到右，间距 **≥400px**
- 数据节点放在 exec 链**下方**（y=300~1200）
- 同列数据节点 y 间距 **≥200px**
- 远距离连接用**额外的 VariableGet 节点**（每个 getter 负责 1-2 个目标）
- `set_node_positions` 批量设置位置，创建时位置只是参考

```python
positions = [
    {"guid": CS,   "x": 0,    "y": 0},
    {"guid": FOR,  "x": 500,  "y": 0},
    {"guid": ADD,  "x": 1000, "y": 0},
    # 数据节点
    {"guid": SPL1, "x": 500,  "y": 350},
    {"guid": GL,   "x": 900,  "y": 350},
]
unreal.BlueprintGraphEdit.set_node_positions(BP, json.dumps(positions))
```

---

## 完整示例：创建 Spline Mesh 逻辑

```python
import unreal, json

BP = "/Game/MyBP"
GN = "UserConstructionScript"

# ⚠️ 前置：先编译蓝图确保变量存在
bel = unreal.BlueprintEditorLibrary
bel.compile_blueprint(unreal.load_asset(BP))

# ⚠️ 必须加载宏库
unreal.load_asset("/Engine/EditorBlueprintResources/StandardMacros")

# --- 创建节点（分组，每组后 query 验证）---

# 组1: 变量读取
A = unreal.BlueprintGraphEdit.add_graph_node
r = json.loads(A(BP, "K2Node_VariableGet", GN, -600, -100, False, "", "", json.dumps({"VariableName": "SegmentCount"})))
SEG = r["node_guid"]

r = json.loads(A(BP, "K2Node_MacroInstance", GN, 100, 0, False, "", "", json.dumps({"MacroName": "ForLoop"})))
FOR = r["node_guid"]

# --- 连接（batch，一次提交）---
conns = [
    {"from_node": CS, "from_pin": "then", "to_node": FOR, "to_pin": "execute"},
    {"from_node": SEG, "from_pin": "SegmentCount", "to_node": SUB, "to_pin": "A"},
    # ...
]
result = json.loads(unreal.BlueprintGraphConnect.batch_connect_pins(BP, json.dumps(conns)))

# --- 编译验证 ---
cr = json.loads(unreal.BlueprintNodeProperty.compile_blueprint(BP))
if not cr["success"]:
    for e in cr["errors"]:
        print(f"ERROR: {e}")
```

---

## Constraints
- **禁止猜测引脚名**：创建节点后 query 确认
- **VariableGet 前必须编译蓝图**（确保 GeneratedClass 包含变量）
- **ForLoop 前必须 load StandardMacros**
- **禁止创建 K2Node_AddComponent**（会崩溃）
- **Class/Object 引脚**：通过 set_node_property 设置路径字符串
- **exec 闭包**：函数内必须 import json；避免在 comprehension 中访问外部变量
- **不要强制关闭 UE**：用 Live Coding 编译（LiveCoding.Compile 命令），不要 Stop-Process
