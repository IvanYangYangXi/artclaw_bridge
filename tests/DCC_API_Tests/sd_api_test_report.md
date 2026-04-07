# Substance Designer API 测试报告

**测试日期**: 2026-04-07  
**测试环境**: SD 12.1.0 | Python 3.9.9 | ArtClaw MCP sd-editor  
**测试项目**: new_project.sbs (1 graph, 14 nodes)  
**测试人员**: ArtClaw 测试工程师 (subagent)

---

## 测试结果汇总

| 类别 | 总数 | 通过 | 失败 | 跳过/不确定 |
|------|------|------|------|-------------|
| 上下文采集 | 7 | 7 | 0 | 0 |
| 节点创建 | 4 | 4 | 0 | 0 |
| 节点连接 | 6 | 5 | 0 | 1 |
| 节点参数 | 5 | 5 | 0 | 0 |
| 节点查询 | 6 | 6 | 0 | 0 |
| 包管理 | 2 | 2 | 0 | 0 |
| 节点删除 | 1 | 1 | 0 | 0 |
| 输出节点配置 | 3 | 3 | 0 | 0 |
| SKILL.md API 审计 | 4 | 0 | 4 | 0 |
| **总计** | **38** | **33** | **4** | **1** |

---

## 1. 上下文采集

| # | 测试用例 | 结果 | 说明 |
|---|---------|------|------|
| 1.1 | get_context 基础信息 | ✅ PASS | 返回 software=substance_designer, version=12.1.0, python=3.9.9 |
| 1.2 | S 变量（节点列表） | ✅ PASS | `type=list, len=14`, 元素为 `SDSBSCompNode` |
| 1.3 | W 变量（文件路径） | ✅ PASS | `C:/Users/yangjili/Documents/Alchemist/new_project.sbs` |
| 1.4 | graph 变量（当前图） | ✅ PASS | `type=SDSBSCompGraph, id=main_graph` |
| 1.5 | app 变量 | ✅ PASS | `type=SDApplication`, `getPackageMgr()` 和 `getUIMgr()` 均可用 |
| 1.6 | L 变量 | ✅ PASS | `L is sd` 为 True，等同于 sd 模块 |
| 1.7 | 预注入值类型检查 | ✅ PASS | 所有 16 个预注入变量类型正确：SDPropertyCategory(EnumMeta), float2/3/4(PyCStructType), SDValue*(type) |

---

## 2. 节点创建

| # | 测试用例 | 结果 | 说明 |
|---|---------|------|------|
| 2.1 | 创建原子节点 | ✅ PASS | uniform, blend, levels, blur, normal, curve 全部成功 |
| 2.2 | 创建输出节点 | ✅ PASS | `graph.newNode("sbs::compositing::output")` 成功 |
| 2.3 | 设置节点位置 | ✅ PASS | `node.setPosition(float2(500, 300))` → 读回 `(500.0, 300.0)` |
| 2.4 | ⛔ `newNode("不存在的id")` | ✅ PASS (文档验证) | 文档正确标注为 **SD 永久挂起** — 不实测 |

---

## 3. 节点连接（重点测试）

| # | 测试用例 | 结果 | 说明 |
|---|---------|------|------|
| 3.1 | `newPropertyConnectionFromId` | ✅ PASS | 返回 `SDConnection` 对象，连接成功 |
| 3.2 | `newPropertyConnection` (属性对象) | ✅ PASS | 通过 `getPropertyFromId` 获取属性后连接成功 |
| 3.3 | `SDProperty.connect()` 不存在 | ✅ PASS | 确认 SDProperty 没有 `connect` 方法 (`hasattr=False`) |
| 3.4 | `getPropertyConnections` | ✅ PASS | 返回 `SDArray[SDConnection]`，可用 `getSize()`/`getItem()` |
| 3.5 | `connection.disconnect()` | ⚠️ HANG | **调用后导致 SD 挂起 5-10 分钟**，最终恢复但操作结果不确定 |
| 3.6 | `deletePropertyConnections` | ✅ PASS | 正确断开指定端口的所有连接，before=1, after=0 |

### ⚠️ 重大发现：SDConnection 方向语义

SD API 的 SDConnection 方向命名与直觉**相反**：

```
连接: NodeA.output → NodeB.input
SDConnection.getInputPropertyNode()  → 返回 NodeA (源节点，数据流入连接)
SDConnection.getOutputPropertyNode() → 返回 NodeB (目标节点，数据流出连接)
SDConnection.getInputProperty()      → 返回源端口 (unique_filter_output)
SDConnection.getOutputProperty()     → 返回目标端口 (input1)
```

**sd-operation-rules SKILL.md 中的描述是错的**：
```python
# SKILL 写的（❌ 语义错误）：
src_node = c.getOutputPropertyNode()  # 文档说是"源节点"，实际是目标节点
src_port = c.getOutputProperty()      # 文档说是"源端口"，实际是目标端口
```

### ⚠️ 重大发现：`connection.disconnect()` 导致 SD 挂起

两次调用 `disconnect()` 都导致 SD API 完全无响应 5-10 分钟。建议：
- **避免使用 `connection.disconnect()`**
- 改用 `node.deletePropertyConnections(prop)` 断开连接

---

## 4. 节点参数

| # | 测试用例 | 结果 | 说明 |
|---|---------|------|------|
| 4.1 | `setInputPropertyValueFromId` (Float4) | ✅ PASS | 设置 uniform outputcolor 为 (0.5, 0.3, 0.1, 1.0) |
| 4.2 | `getInputPropertyValueFromId` | ✅ PASS | 读回 `SDValueColorRGBA`，值正确 |
| 4.3 | `getPropertyFromId` + `setPropertyValue` | ✅ PASS | 通过属性对象设置值成功 |
| 4.4 | `setInputPropertyValueFromId` (Bool) | ✅ PASS | 设置 `colorswitch=True`，读回正确 |
| 4.5 | 列出节点所有参数 | ✅ PASS | `getProperties(SDPropertyCategory.Input)` 返回完整参数列表 |

### 补充发现
- Uniform 节点输入参数：`$outputsize`, `$format`, `$pixelsize`, `$pixelratio`, `$tiling`, `$randomseed`, `colorswitch`, `outputcolor`
- 系统参数以 `$` 开头
- `setAnnotationPropertyValueFromId` / `getAnnotationPropertyValueFromId` 是设置注解属性的快捷方法（文档未提及）

---

## 5. 节点查询

| # | 测试用例 | 结果 | 说明 |
|---|---------|------|------|
| 5.1 | `graph.getNodes()` | ✅ PASS | 返回 `SDArray`，支持 `getSize()` / `getItem()` / 迭代 |
| 5.2 | `node.getDefinition().getId()` | ✅ PASS | 正确返回定义 ID 如 `sbs::compositing::uniform` |
| 5.3 | `node.getPosition()` | ✅ PASS | 返回 `float2` 类型 |
| 5.4 | `getProperties(Output)` | ✅ PASS | Uniform 输出端口: `unique_filter_output` |
| 5.5 | `graph.getNodeFromId()` | ✅ PASS | 通过 ID 精确查找节点 |
| 5.6 | `graph.getOutputNodes()` | ✅ PASS | 返回 5 个输出节点 |

### 补充发现
- `SDArray` 同时支持 `getSize()/getItem()` 和 Python 迭代协议
- `graph.getNodeFromId()` 和 `graph.getOutputNodes()` 未在任何 SKILL.md 中提及，建议补充

---

## 6. 包管理

| # | 测试用例 | 结果 | 说明 |
|---|---------|------|------|
| 6.1 | `app.getPackageMgr().getUserPackages()` | ✅ PASS | 返回 1 个用户包 |
| 6.2 | `pkg.getChildrenResources(False)` | ✅ PASS | 返回 1 个 `SDSBSCompGraph` 资源 |

---

## 7. 节点删除

| # | 测试用例 | 结果 | 说明 |
|---|---------|------|------|
| 7.1 | `graph.deleteNode()` | ✅ PASS | 创建临时节点后删除，节点数从 31 降到 30 |

---

## 8. 输出节点配置

| # | 测试用例 | 结果 | 说明 |
|---|---------|------|------|
| 8.1 | 读取 Annotation 属性 | ✅ PASS | 输出节点有 `label`, `identifier`, `usages`, `description`, `mipmaps`, `format` 等 |
| 8.2 | 设置 output label | ✅ PASS | 通过 `setPropertyValue(label_prop, SDValueString)` |
| 8.3 | 设置 output identifier (usage) | ✅ PASS | 设置为 `roughness` 并读回验证 |

### 补充发现
- `setAnnotationPropertyValueFromId("label", SDValueString.sNew("xxx"))` 是更简洁的设置方式
- `getAnnotationPropertyValueFromId("label")` 是更简洁的读取方式
- 这两个快捷方法未在 SKILL.md 中提及

---

## 9. SKILL.md API 审计

### 9.1 sd-operation-rules SKILL.md

| 问题 | 严重程度 | 详情 |
|------|----------|------|
| SDConnection 方向语义错误 | 🔴 严重 | 规则 5 中 `c.getOutputPropertyNode()` 被描述为"源节点"，实际返回**目标节点** |
| `connection.disconnect()` 未标注风险 | 🔴 严重 | 实测发现 `disconnect()` 导致 SD 挂起 5-10 分钟，应标注为危险操作 |
| 缺少 `setAnnotationPropertyValueFromId` | 🟡 中等 | 这是设置注解属性的快捷方法，比 `getPropertyFromId + setPropertyValue` 更简洁 |
| 缺少 `graph.getNodeFromId()` | 🟡 中等 | 精确查找节点的便捷方法 |
| 缺少 `graph.getOutputNodes()` | 🟡 中等 | 获取所有输出节点的便捷方法 |

**修复建议**：

```python
# ❌ 当前文档（语义错误）
c = conns.getItem(0)
src_node = c.getOutputPropertyNode()   # 实际返回的是目标节点！
src_port = c.getOutputProperty()       # 实际返回的是目标端口！

# ✅ 正确理解
c = conns.getItem(0)
src_node = c.getInputPropertyNode()    # 源节点（数据流入连接的节点）
src_port = c.getInputProperty()        # 源端口
dst_node = c.getOutputPropertyNode()   # 目标节点（数据流出连接的节点）
dst_port = c.getOutputProperty()       # 目标端口

# ⚠️ disconnect() 危险！
# connection.disconnect()  # 可能导致 SD 挂起！
# ✅ 替代方案：
node.deletePropertyConnections(prop)   # 安全的断开连接方式
```

---

### 9.2 sd-node-ops SKILL.md

| 问题 | 严重程度 | 详情 |
|------|----------|------|
| 节点布局部分有 `from sd.api.sdbasetypes import float2` | 🟡 中等 | 违反"不要 import sd.api 子模块"规则，应使用预注入的 `float2` |
| SDConnection 查询部分同样有方向语义错误 | 🔴 严重 | 与 operation-rules 相同问题 |
| `disconnect_one` 函数使用 `disconnect()` | 🔴 严重 | 此方法会导致 SD 挂起 |

---

### 9.3 sd-context SKILL.md — ⛔ **严重错误最多**

| 问题 | 严重程度 | 详情 |
|------|----------|------|
| 所有代码示例使用 `from sd.api.xxx import ...` | 🔴 致命 | 会导致超时死锁！每个 Section 的"前置代码"都是错的 |
| 使用 `SDApplication.getApplication()` | 🔴 致命 | 此 API 不存在！正确方式是 `sd.getContext().getSDApplication()` |
| Section 6 使用 `prop.getConnections()` | 🔴 致命 | SDProperty 没有 `getConnections` 方法！应用 `node.getPropertyConnections(prop)` |
| Section 6 使用 `conn.getNode()` 和 `conn.getId()` | 🔴 致命 | SDConnection 没有这些方法！正确是 `conn.getInputPropertyNode()` / `conn.getInputProperty().getId()` |

**详细错误位置**：

```python
# ❌ sd-context Section 1-7 所有代码的前置部分：
import sd
from sd.api.sdapplication import SDApplication  # ← 会死锁！
from sd.api.sdproperty import SDPropertyCategory  # ← 会死锁！
app = SDApplication.getApplication()  # ← 不存在的 API！

# ✅ 正确方式（使用预注入变量）：
# app, graph, SDPropertyCategory 等已预注入，直接使用
```

```python
# ❌ sd-context Section 6（连接关系查询）：
connections = prop.getConnections()  # ← SDProperty 没有此方法！
for conn in connections:
    src_node = conn.getNode()       # ← SDConnection 没有此方法！
    src_prop_id = conn.getId()      # ← SDConnection 没有此方法！

# ✅ 正确方式：
conns = node.getPropertyConnections(prop)  # 在 SDNode 上调用
for i in range(conns.getSize()):
    c = conns.getItem(i)
    src_node = c.getInputPropertyNode()     # 源节点
    src_port = c.getInputProperty().getId()  # 源端口 ID
```

---

### 9.4 sd-material-recipes SKILL.md — ⛔ **使用了不存在的 API**

| 问题 | 严重程度 | 详情 |
|------|----------|------|
| 通用工具函数的前置代码使用 `from sd.api.xxx import ...` | 🔴 致命 | 会死锁 |
| 使用 `SDApplication.getApplication()` | 🔴 致命 | 不存在 |
| `connect()` 函数使用 `src_prop.connect(dst_prop)` | 🔴 致命 | **SDProperty 没有 connect 方法！** |
| `connect()` 回退逻辑也用 `src_props[0].connect(dst_props[0])` | 🔴 致命 | 同上，不存在 |

**详细错误**：

```python
# ❌ sd-material-recipes 的 connect() 函数：
def connect(src_node, src_port, dst_node, dst_port):
    src_prop = src_node.getPropertyFromId(src_port, SDPropertyCategory.Output)
    dst_prop = dst_node.getPropertyFromId(dst_port, SDPropertyCategory.Input)
    if src_prop and dst_prop:
        src_prop.connect(dst_prop)  # ← 不存在！SDProperty 没有 connect 方法！

# ✅ 正确方式：
def connect(src_node, src_port, dst_node, dst_port):
    conn = src_node.newPropertyConnectionFromId(src_port, dst_node, dst_port)
    return conn is not None
```

**这意味着 sd-material-recipes 中所有 3 个配方的连接代码都无法工作**。

---

## SDProperty 完整方法列表（实测）

```
getCategory, getClassName, getDefaultValue, getDescription, getId, getLabel,
getType, getTypes, isConnectable, isFunctionOnly, isPrimary, isReadOnly,
isVariadic, mAPIContext, mHandle, ownHandle, release
```

**不存在的方法**（被 SKILL.md 错误引用的）：
- ❌ `connect()` — 不存在
- ❌ `getConnections()` — 不存在

---

## SDNode 完整方法列表（实测）

```
deleteProperty, deletePropertyConnections, deletePropertyGraph,
getAnnotationPropertyValueFromId, getClassName, getDefinition, getIdentifier,
getInputPropertyInheritanceMethodFromId, getInputPropertyValueFromId,
getPosition, getProperties, getPropertyConnections, getPropertyFromId,
getPropertyGraph, getPropertyInheritanceMethod, getPropertyValue,
getPropertyValueFromId, getReferencedResource, mAPIContext, mHandle,
newProperty, newPropertyConnection, newPropertyConnectionFromId,
newPropertyGraph, ownHandle, release, setAnnotationPropertyValueFromId,
setInputPropertyInheritanceMethodFromId, setInputPropertyValueFromId,
setPosition, setPropertyInheritanceMethod, setPropertyValue
```

---

## SDGraph 完整方法列表（实测）

```
compute, delete, deleteGraphObject, deleteNode, deleteProperty,
getAnnotationPropertyValueFromId, getClassName, getEmbedMethod,
getExposedInSBSAR, getFilePath, getGraphObjects, getGraphType, getIcon,
getIdentifier, getInputPropertyValueFromId, getMetadataDict,
getNodeDefinitions, getNodeFromId, getNodes, getOutputNodes, getPackage,
getProperties, getPropertyAnnotationValueFromId, getPropertyAnnotations,
getPropertyFromId, getPropertyInheritanceMethod,
getPropertyMetadataDictFromId, getPropertyValue, getPropertyValueFromId,
getType, getUID, getUrl, mAPIContext, mHandle, newInstanceNode, newNode,
newProperty, ownHandle, release, sNew, sNewFromFile,
setAnnotationPropertyValueFromId, setIcon, setIdentifier,
setInputPropertyValueFromId, setOutputNode, setPropertyAnnotationValueFromId,
setPropertyInheritanceMethod, setPropertyValue
```

---

## SDConnection 完整方法列表（实测）

```
disconnect, getClassName, getInputProperty, getInputPropertyNode,
getOutputProperty, getOutputPropertyNode, mAPIContext, mHandle, ownHandle,
release
```

**不存在的方法**（被 SKILL.md 错误引用的）：
- ❌ `getNode()` — 不存在
- ❌ `getId()` — 不存在

---

## 关键发现总结

### 🔴 致命问题（会导致代码完全无法运行）

1. **sd-context SKILL.md 整体不可用** — 所有 7 个 Section 的代码都使用 `from sd.api.xxx import ...` 和 `SDApplication.getApplication()`，两者都会导致死锁或 AttributeError
2. **sd-context Section 6 使用了 3 个不存在的 API** — `prop.getConnections()`, `conn.getNode()`, `conn.getId()`
3. **sd-material-recipes 的 connect() 函数使用不存在的 `SDProperty.connect()`** — 所有材质配方的连接代码都无法工作
4. **`connection.disconnect()` 导致 SD 挂起 5-10 分钟** — 应标记为 ⛔ 致命陷阱

### 🟡 中等问题（功能缺失或描述不准确）

5. **SDConnection 方向语义描述反了** — `getInputPropertyNode()` 返回源节点，`getOutputPropertyNode()` 返回目标节点
6. **缺少便捷方法文档** — `setAnnotationPropertyValueFromId`, `getAnnotationPropertyValueFromId`, `graph.getNodeFromId()`, `graph.getOutputNodes()`

### ✅ 正确的部分

- `sd-operation-rules` 的预注入变量表 — 完整且正确
- `sd-operation-rules` 的常用原子节点定义 ID — 正确
- `sd-operation-rules` 的 "SDProperty 没有 connect 方法" 警告 — 正确
- `sd-node-ops` 的连接 API 描述（方式 1 和 2） — 正确
- `sd-node-ops` 的参数设置方法 — 正确

---

## 建议补充的 API / Skill

### 建议补充到现有 SKILL 的 API

1. **`graph.getNodeFromId(identifier)`** — 通过 ID 精确查找节点
2. **`graph.getOutputNodes()`** — 获取所有输出节点的便捷方法
3. **`node.setAnnotationPropertyValueFromId(prop_id, value)`** — 快捷设置注解
4. **`node.getAnnotationPropertyValueFromId(prop_id)`** — 快捷读取注解
5. **`graph.compute()`** — 强制计算图
6. **`graph.setIdentifier(name)`** — 修改图名称
7. **`node.getReferencedResource()`** — 获取库节点引用的资源
8. **`node.getPropertyGraph(prop)`** — 获取参数的函数图
9. **`graph.getGraphObjects()`** — 获取图中的注释/框架等对象

### 建议新增 SKILL

1. **sd-connection-guide** — 专门的连接操作指南，包含：
   - SDConnection 方向语义的正确解释
   - `disconnect()` 的挂起风险和替代方案
   - 批量连接/断开的安全模式
   
2. **sd-troubleshooting** — SD API 常见问题和陷阱：
   - `disconnect()` 挂起问题
   - `import sd.api.*` 死锁问题
   - `SDApplication.getApplication()` 不存在问题
   - `newNode("无效ID")` 永久挂起问题

### ⛔ 致命陷阱表（建议添加到 sd-operation-rules）

| 操作 | 后果 | 说明 |
|------|------|------|
| `graph.newNode("不存在的id")` | SD 永久挂起 | 创建前必须验证 definition_id |
| `SDUsage.sNew()` | SD 永久挂起 | 绝对禁止 |
| `connection.disconnect()` | SD 挂起 5-10 分钟 | **改用 `node.deletePropertyConnections(prop)`** |
| `from sd.api.xxx import ...` | 超时死锁 | 使用预注入变量 |
| `SDApplication.getApplication()` | AttributeError | 使用预注入的 `app` 或 `sd.getContext().getSDApplication()` |

---

## 附录：测试清理确认

所有测试创建的 18 个临时节点已全部清理，图恢复到原始 14 个节点状态。
