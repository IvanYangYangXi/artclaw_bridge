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
    author: ArtClaw
    software: substance_designer
---

# SD 操作通用规则

> **强制规则**：所有涉及 Substance Designer 场景操作的 AI 任务，执行前必须遵守以下规则。

---

## 规则 0：API 模块与版本

- SD Python API 模块名是 **`sd`**
- 当前版本：**SD 12.1.0**（Python 3.9.9）
- 获取应用实例（**唯一正确方式**）：

```python
import sd
app = sd.getContext().getSDApplication()
```

- **❌ 错误方式**（会报 `has no attribute 'getApplication'`）：
```python
# 禁止！以下写法不存在
from sd.api import SDApplication
app = SDApplication.getApplication()  # ← 不存在的 API
```

- 核心管理器：
  - **包管理器**：`app.getPackageMgr()` — 管理 .sbs 包
  - **UI 管理器**：`app.getUIMgr()` — 获取当前图、编辑器状态

---

## 规则 1：预注入变量（直接使用，无需 import）

`execute_code` 已预注入以下变量，**直接使用即可，无需 import**：

| 变量 | 类型 | 说明 |
|------|------|------|
| `sd` | module | sd 模块 |
| `app` | SDApplication | 应用实例 |
| `graph` | SDSBSCompGraph / None | 当前活动图 |
| `S` | list | 当前图的节点列表 |
| `W` | str | 当前文件路径 |
| `L` | module | sd 模块（同 sd） |
| `SDPropertyCategory` | enum | 属性分类枚举 |
| `float2` / `float3` / `float4` | class | 向量类型 |
| `ColorRGBA` | class | 颜色类型 |
| `SDValueFloat` | class | 浮点值 |
| `SDValueInt` | class | 整数值 |
| `SDValueBool` | class | 布尔值 |
| `SDValueString` | class | 字符串值 |
| `SDValueFloat2/3/4` | class | 向量值 |
| `SDValueColorRGBA` | class | 颜色值 |

```python
# ✅ 正确：直接使用预注入变量
if graph is None:
    result = "错误：没有打开的图"
else:
    nodes = graph.getNodes()
    result = f"节点数: {len(nodes)}"
```

```python
# ❌ 错误：在 exec 中 import sd.api 子模块会超时死锁
from sd.api.sdproperty import SDPropertyCategory  # 会超时！
```

---

## 规则 2：严格单线程 + 代码简短 ⚠️

- **SD API 严格单线程**，所有调用必须在主线程中串行执行
- **每次工具调用的代码要尽量简短**（<30 行），避免超时
- **单次调用安全上限**：≤3 个节点创建 + ≤3 条连接，超过应分多次调用
- 复杂操作分多次调用完成，每次完成一个步骤
- **禁止**在 exec 代码中使用 `threading`、`asyncio`
- **禁止**在 exec 代码中 `import sd.api.*` 子模块（用预注入变量代替）

### ⛔ 超时恢复

**一旦单次调用超时，SD 的 MCP 连接会永久失效**——后续所有 API 调用都会超时。
唯一恢复方式：**用户手动重启 Substance Designer**。

因此必须严格控制单次调用的操作量，宁可多调几次也不要一次做太多。

---

## 规则 3：无 Undo API

- SD Python API **不支持 undo group / undo transaction**
- **破坏性操作前要格外谨慎**：
  - 删除节点前确认目标正确
  - 修改参数前先读取并打印当前值

---

## 规则 4：节点创建（关键陷阱）

### 原子节点

```python
# 使用 definition_id 创建
node = graph.newNode("sbs::compositing::blend")
if node is None:
    result = "创建节点失败"
```

### 库节点（Library nodes）

```python
# 必须通过 resource URL + newInstanceNode
pkg_mgr = app.getPackageMgr()
resource = None
for pkg in pkg_mgr.getPackages():
    try:
        r = pkg.findResourceFromUrl(resource_url)
        if r is not None:
            resource = r
            break
    except Exception:
        pass
if resource:
    node = graph.newInstanceNode(resource)
```

### ⛔ 致命陷阱

| 操作 | 后果 | 说明 |
|------|------|------|
| `graph.newNode("不存在的id")` | **SD 永久挂起** | 创建前必须验证 definition_id |
| `SDUsage.sNew()` | **SD 永久挂起** | **绝对禁止** |
| `connection.disconnect()` | **SD 挂起 5-10 分钟** | 改用 `node.deletePropertyConnections(prop)` |
| `graph.getNodeDefinitions()` | 可能极慢/超时 | 避免在工具调用中使用 |

### 常用原子节点定义 ID

```
sbs::compositing::blend          # 混合
sbs::compositing::levels         # 色阶
sbs::compositing::curve          # 曲线
sbs::compositing::hsl            # HSL 调整
sbs::compositing::blur           # 模糊
sbs::compositing::sharpen        # 锐化
sbs::compositing::normal         # 法线
sbs::compositing::warp           # 扭曲
sbs::compositing::directionalwarp # 方向扭曲
sbs::compositing::transformation # 变换
sbs::compositing::distance       # 距离
sbs::compositing::gradient       # 渐变
sbs::compositing::uniform        # 纯色
sbs::compositing::output         # 输出节点
sbs::compositing::input          # 输入节点
sbs::compositing::text           # 文字
```

---

## 规则 5：节点连接

连接 API 在 **SDNode** 上，不在 SDProperty 上：

```python
# ✅ 方式 1：通过端口 ID 连接（推荐）
conn = src_node.newPropertyConnectionFromId(
    "unique_filter_output",  # 源输出端口 ID
    dst_node,                # 目标节点
    "input1"                 # 目标输入端口 ID
)

# ✅ 方式 2：通过属性对象连接
out_prop = src_node.getPropertyFromId("unique_filter_output", SDPropertyCategory.Output)
in_prop = dst_node.getPropertyFromId("input1", SDPropertyCategory.Input)
conn = src_node.newPropertyConnection(out_prop, dst_node, in_prop)

# ❌ 错误：SDProperty 没有 connect 方法！
# out_prop.connect(in_prop)  # 不存在！会 AttributeError
```

### 查询连接

```python
# 查询某端口的连接
prop = node.getPropertyFromId("input1", SDPropertyCategory.Input)
conns = node.getPropertyConnections(prop)  # -> SDArray[SDConnection]
if conns and conns.getSize() > 0:
    c = conns.getItem(0)
    # ⚠️ SDConnection 方向会随查询端口翻转！不要依赖 getInput/OutputPropertyNode 的绝对方向
    # 从 Input 端口查: getInputPropertyNode()=对面(源), getOutputPropertyNode()=自己(目标)
    # 从 Output 端口查: getInputPropertyNode()=对面(目标), getOutputPropertyNode()=自己(源)
    # 推荐: 只用 deletePropertyConnections 管理连接，避免解析 SDConnection 方向
```

### 删除连接

```python
# ✅ 推荐：删除某端口的所有连接（安全可靠）
node.deletePropertyConnections(prop)

# ⛔ 禁止使用 connection.disconnect() — 会导致 SD 挂起 5-10 分钟！
```

### 常见端口 ID

| 节点 | 输入端口 | 输出端口 |
|------|----------|----------|
| blend | source, destination, opacity | unique_filter_output |
| levels/curve/hsl/blur | input1 | unique_filter_output |
| warp | input1, inputgradient | unique_filter_output |
| directionalwarp | input1, **inputintensity** (非 inputgradient!) | unique_filter_output |

**⚠️ 库节点的端口名可能不同**，使用前必须先查询：
```python
for p in node.getProperties(SDPropertyCategory.Output):
    print(p.getId())
```

---

## 规则 6：参数设置

```python
# 设置浮点参数
node.setInputPropertyValueFromId("opacitymult", SDValueFloat.sNew(0.5))

# 设置整数参数（如混合模式）
node.setInputPropertyValueFromId("blendingmode", SDValueInt.sNew(3))  # Multiply

# 设置位置
node.setPosition(float2(100.0, 200.0))
```

**⚠️ SD 12: 对 float 参数传 SDValueInt2/3/4 会静默崩溃** — 类型必须匹配。

---

## 规则 6.5：便捷 API

常用但不常见的 API，补充参考：

```python
# 通过 ID 精确查找节点（不需遍历）
node = graph.getNodeFromId("1234567890")

# 获取图中所有输出节点
output_nodes = graph.getOutputNodes()

# 快捷读写注解属性（identifier、label、description 等）
node.setAnnotationPropertyValueFromId("identifier", SDValueString.sNew("basecolor"))
value = node.getAnnotationPropertyValueFromId("identifier")
# ⚠️ 返回的是 SDValueString 对象，需 .get() 提取字符串:
# actual_str = value.get()
```

---

## 规则 7：PBR 输出标准

| 通道 | Usage 标识符 | 说明 |
|------|-------------|------|
| BaseColor | `baseColor` | 基础颜色 |
| Normal | `normal` | 法线贴图 |
| Roughness | `roughness` | 粗糙度 |
| Metallic | `metallic` | 金属度 |
| Height | `height` | 高度图 |
| AO | `ambientOcclusion` | 环境遮蔽 |

---

## 标准操作模板

```python
# 预注入变量已可用：sd, app, graph, S, W, L,
# SDPropertyCategory, float2, SDValueFloat, SDValueInt, 等

if graph is None:
    result = "错误：没有打开的图"
else:
    try:
        # 1. 验证前置条件
        # 2. 执行操作（简短！）
        # 3. 返回结果
        result = "操作完成"
    except Exception as e:
        result = f"操作失败: {e}"
```

---

## 推荐工作流（多步骤）

1. `get_context` — 确认 SD 连接和当前图状态
2. 创建节点（一次创建 1-3 个）
3. 查询节点端口 ID（库节点必须）
4. 逐个连接节点
5. 设置参数
6. 验证图结构
