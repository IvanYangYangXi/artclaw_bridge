---
name: ue5-blueprint-workflow
description: >
  UE5.6/UE5.7 Blueprint graph workflow for feature implementation, input events, node wiring, and graph validation.
  Use when requests involve adding Blueprint logic, keyboard input behavior, function chains, event graph edits, or pin-level connection guidance.
---

# Blueprint Graph Editing — Python API Reference

ArtClaw 插件通过 C++ `UFUNCTION(BlueprintCallable)` 暴露了完整的蓝图图编辑 API，**Python 可直接调用**。

> ⚠️ 这些 API 来自 `UEClawBridgeAPI` 模块（C++ 实现），不是 UE 原生 Python API。
> 标准 `unreal` 模块不暴露 EdGraph 节点操作，但我们的扩展 API 完整覆盖了。

## API 总览

| Python 类 | 方法 | 用途 |
|---|---|---|
| `BlueprintGraphQuery` | `query_blueprint_graph(asset, graph, type, guid, search, positions)` | 查询图/节点/引脚/连接 |
| | `list_blueprint_callables(asset)` | 列出事件/函数/宏入口 |
| | `query_blueprint_info(asset, include)` | 查询组件/变量/接口/父类 |
| `BlueprintGraphEdit` | `add_graph_node(asset, class, graph, x, y, auto_pos, connect_node, connect_pin, props_json)` | 添加节点 |
| | `remove_graph_node(asset, guid)` | 删除节点 |
| | `set_node_positions(asset, positions_json)` | 批量设位置 |
| | `create_function_graph(asset, name, public, return_json, params_json)` | 创建函数图 |
| `BlueprintGraphConnect` | `connect_graph_pins(asset, src_node, src_pin, tgt_node, tgt_pin)` | 连接引脚 |
| | `disconnect_graph_pin(asset, node, pin, tgt_node, tgt_pin)` | 断开引脚 |
| | `insert_graph_node(asset, class, src_guid, src_pin, tgt_guid, tgt_pin, graph)` | 在连接间插入节点 |
| | `batch_connect_pins(asset, connections_json)` | 批量连接 |
| `BlueprintNodeProperty` | `set_node_property(asset, guid, props_json)` | 设置节点属性/引脚默认值 |
| | `compile_blueprint(asset)` | 编译蓝图 |
| | `modify_interface(asset, action, interface)` | 添加/移除接口 |
| | `set_blueprint_variable(asset, name, type_json, is_array, category)` | 创建/修改变量 |
| | `validate_blueprint_structure(asset, auto_fix)` | 验证蓝图结构 |
| `EnhancedInputAPI` | `query_input_mapping_context(asset)` | 查询输入映射上下文 |
| | `create_input_action(asset, value_type)` | 创建 InputAction |
| | `add_input_mapping(context, action, key, modifiers_json)` | 添加键位映射 |
| | `query_input_action(asset)` | 查询 InputAction 信息 |

## 关键调用示例

### 1) 查询蓝图图结构
```python
import unreal, json
result = unreal.BlueprintGraphQuery.query_blueprint_graph(
    "/Game/BP/BP_MyActor",  # asset_path
    "EventGraph",           # graph_name (空=全部)
    "",                     # graph_type
    "",                     # node_guid (空=全部节点)
    "",                     # search
    False                   # include_positions
)
data = json.loads(result)
# data["graphs"][0]["nodes"] → [{class, title, guid, inputs, outputs}, ...]
```

### 2) 添加函数调用节点
```python
import unreal, json
props = json.dumps({
    "FunctionReference": {
        "MemberName": "PrintString",
        "MemberParent": "/Script/Engine.KismetSystemLibrary"
    }
})
result = unreal.BlueprintGraphEdit.add_graph_node(
    "/Game/BP/BP_MyActor",   # asset_path
    "K2Node_CallFunction",   # node_class
    "EventGraph",            # graph_name
    0, 0,                    # pos_x, pos_y
    True,                    # auto_position
    "",                      # connect_to_node (GUID, 用于相对定位)
    "",                      # connect_to_pin
    props                    # properties_json
)
data = json.loads(result)
new_guid = data["node_guid"]  # 用于后续连接
```

### 3) 连接引脚
```python
result = unreal.BlueprintGraphConnect.connect_graph_pins(
    "/Game/BP/BP_MyActor",
    "1F707DA44FFDC79BD17A049FEFD344DE",  # source_node GUID (无连字符)
    "then",                               # source_pin
    "67AA3CEF4779605E5C56DF9471FAD33F",  # target_node GUID (无连字符)
    "execute"                             # target_pin
)
# ⚠️ GUID 格式: add_graph_node 返回带连字符，connect 需要去掉连字符
```

### 4) 批量连接
```python
conns = json.dumps([
    {"from_node": "GUID_A", "from_pin": "then", "to_node": "GUID_B", "to_pin": "execute"},
    {"from_node": "GUID_B", "from_pin": "ReturnValue", "to_node": "GUID_C", "to_pin": "InString"}
])
result = unreal.BlueprintGraphConnect.batch_connect_pins("/Game/BP/BP_MyActor", conns)
```

### 5) 编译蓝图
```python
result = unreal.BlueprintNodeProperty.compile_blueprint("/Game/BP/BP_MyActor")
data = json.loads(result)
# data: {success, compiled, errors[], error_count, warnings[], warning_count, status}
```

### 6) 设置引脚默认值
```python
props = json.dumps({"InString": "Hello World", "bPrintToScreen": "true"})
result = unreal.BlueprintNodeProperty.set_node_property(
    "/Game/BP/BP_MyActor",
    "67AA3CEF4779605E5C56DF9471FAD33F",
    props
)
```

## GUID 格式注意

- `add_graph_node` 返回的 `node_guid` 带连字符: `67AA3CEF-4779-605E-5C56-DF9471FAD33F`
- `connect_graph_pins` / `query_blueprint_graph` 使用**无连字符** GUID: `67AA3CEF4779605E5C56DF9471FAD33F`
- 转换: `guid.replace("-", "")`

## 常用节点类名

| 类名 | 用途 |
|---|---|
| `K2Node_CallFunction` | 函数调用（需设 FunctionReference） |
| `K2Node_VariableGet` | 读取变量 |
| `K2Node_VariableSet` | 设置变量 |
| `K2Node_Event` | 事件节点（BeginPlay/Tick 等） |
| `K2Node_CustomEvent` | 自定义事件 |
| `K2Node_InputKey` | 键盘输入事件 |
| `K2Node_InputAction` | 输入 Action 事件 |
| `K2Node_IfThenElse` | Branch 分支 |
| `K2Node_MacroInstance` | 宏调用 |
| `K2Node_FunctionEntry` | 函数入口 |
| `K2Node_FunctionResult` | 函数返回 |
| `K2Node_SpawnActorFromClass` | SpawnActor |
| `K2Node_DynamicCast` | Cast To |
| `K2Node_GetArrayItem` | 数组取值 |
| `K2Node_ForEachElementInEnum` | ForEach 枚举 |
| `K2Node_MakeArray` | 创建数组 |
| `K2Node_Literal` | 字面量（对象引用） |
| `K2Node_Self` | Self 引用 |
| `K2Node_Knot` | Reroute 节点 |
| `K2Node_TemporaryVariable` | 局部变量 |
| `K2Node_Sequence` | Sequence |
| `K2Node_ExecutionSequence` | 执行序列 |
| `K2Node_Select` | Select |
| `K2Node_SwitchInteger` | Switch on Int |
| `K2Node_SwitchString` | Switch on String |
| `K2Node_SwitchName` | Switch on Name |
| `K2Node_SwitchEnum` | Switch on Enum |
| `K2Node_Timeline` | 时间轴 |
| `K2Node_Delay` | Delay |

# Workflow

## 1) 查询先行
操作任何蓝图前，先用 `query_blueprint_graph` 了解现有图结构、节点 GUID 和引脚名。

## 2) 添加节点
用 `add_graph_node` 创建节点。对 `K2Node_CallFunction` 必须在 `properties_json` 中传 `FunctionReference`（含 `MemberName` + `MemberParent`），否则节点无引脚。

## 3) 查询引脚名
添加节点后，用 `query_blueprint_graph(asset, "", "", node_guid)` 查看该节点的实际引脚名称，**不要猜测引脚名**。

## 4) 连接引脚
- exec 引脚先连（锁定执行顺序），再连 data 引脚
- 用 `batch_connect_pins` 提高效率
- 引脚名区分大小写

## 5) 设置属性/默认值
- 节点属性用 `set_node_property`
- 引脚默认值也通过 `set_node_property` 设置（属性名=引脚名）
- 变量用 `set_blueprint_variable`

## 6) 编译验证
每次修改后调用 `compile_blueprint` 检查错误。

## 7) 分步执行
- 每步 5-8 个节点为一组
- 每组完成后 query 验证
- 不要一次性创建大量节点

# Constraints
- **禁止猜测引脚名**：创建节点后必须 query 确认实际引脚名称
- **GUID 格式**：连接时用无连字符格式
- **FunctionReference 必填**：CallFunction 节点必须指定 MemberName + MemberParent
- **先查后改**：修改前 query，修改后 compile
- Prefer Enhanced Input (`UInputAction`/`UInputMappingContext`) for new input systems

# Failure Handling
- **节点创建失败**: 检查 NodeClass 拼写（可省略 `UK2Node_` 前缀），API 会自动尝试添加前缀
- **连接失败**: query 确认引脚名和类型是否匹配，检查 GUID 格式
- **编译错误**: 检查是否有悬空引脚或类型不匹配
- **属性设置失败**: API 会尝试将不存在的属性名匹配为引脚默认值
- **函数未找到**: 检查 MemberParent 路径格式（如 `/Script/Engine.KismetSystemLibrary`）
