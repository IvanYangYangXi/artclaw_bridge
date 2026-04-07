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

## 规则 0：API 模块

- SD Python API 模块名是 **`sd`**（不是 `substance_designer`）
- 获取应用实例：

```python
from sd.api.sdapplication import SDApplication
app = SDApplication.getApplication()
```

- 核心管理器：
  - **包管理器**：`app.getPackageMgr()` — 管理 .sbs 包的加载/创建/保存
  - **UI 管理器**：`app.getUIMgr()` — 获取当前图、当前选择等编辑器状态

---

## 规则 1：严格单线程 ⚠️

- **SD API 严格单线程**，所有调用必须在主线程中串行执行
- 不能使用 `threading`、`asyncio` 或任何并发机制调用 SD API
- **调用不存在的节点定义会导致 SD 永久挂起（freeze）**，必须先验证
- 创建节点前**必须**验证定义 ID 存在（见规则 4）

---

## 规则 2：无 Undo API

- SD Python API **不支持 undo group / undo transaction**
- 不存在类似 UE `ScopedTransaction` 或 Maya `undoInfo` 的机制
- **破坏性操作前要格外谨慎**：
  - 删除节点前确认目标正确
  - 断开连接前记录原始连接关系
  - 修改参数前可先读取并打印当前值

---

## 规则 3：节点图操作核心

SD 以**节点图（Graph）**为核心数据结构：

- **包（Package）** → 包含多个 **图（Graph）** → 图包含 **节点（Node）**
- 获取当前图：

```python
graph = app.getUIMgr().getCurrentGraph()
if graph is None:
    print("错误：没有打开的图")
    # 必须中止操作
```

- 创建节点：`node = graph.newNode(definition_id)`
- 获取节点属性：`node.getProperties(category)` / `node.getPropertyFromId(id, category)`
- 连接节点：`output_property.connect(input_property)`

---

## 规则 4：节点定义验证（强制）

**创建任何节点之前，必须先验证其定义 ID 存在。** 跳过验证可能导致 SD 永久挂起。

```python
import sd
from sd.api.sdapplication import SDApplication
from sd.api.sdnode import SDNode

app = SDApplication.getApplication()

# 方法：通过 SDModuleManager 查找定义
module_mgr = app.getModuleMgr()

# 原子节点定义 ID 格式: "sbs::compositing::<name>"
# 例如: "sbs::compositing::blend"
#       "sbs::compositing::levels"
#       "sbs::compositing::normal"

# 创建前验证
definition_id = "sbs::compositing::blend"
try:
    node = graph.newNode(definition_id)
    if node is None:
        print(f"错误：无法创建节点 {definition_id}")
    else:
        print(f"成功创建节点: {node.getIdentifier()}")
except Exception as e:
    print(f"错误：节点定义 {definition_id} 无效 - {e}")
```

---

## 规则 5：常见陷阱 🚫

| 陷阱 | 后果 | 正确做法 |
|------|------|----------|
| `SDUsage.sNew()` | **永久挂起 SD** | **禁止使用** |
| `arrange_nodes()` / 自动布局 | 破坏所有节点连接 | 用 `node.setPosition(SDValueFloat2.sNew(float2(x, y)))` 手动定位 |
| 假设库节点输出名为 `"unique_filter_output"` | 连接失败 | 先用 `node.getProperties(SDPropertyCategory.Output)` 查实际端口名 |
| 不检查 `getCurrentGraph()` 返回值 | NoneType 错误 | 始终判空并中止 |
| 并发调用 SD API | SD 挂起或崩溃 | 严格串行执行 |

---

## 规则 6：PBR 输出标准

SD 图的输出节点使用以下标准标识符（Usage）：

| 通道 | 标识符 | 说明 |
|------|--------|------|
| BaseColor | `basecolor` | 基础颜色/漫反射 |
| Normal | `normal` | 法线贴图 |
| Roughness | `roughness` | 粗糙度 |
| Metallic | `metallic` | 金属度 |
| Height | `height` | 高度图 |
| AO | `ambientocclusion` | 环境遮蔽 |

创建输出节点时，使用 `sbs::compositing::output` 定义 ID，然后设置对应的 usage。

---

## 规则 7：记忆系统集成

与其他 DCC 相同的记忆系统规则：

- **操作前**：通过 `memory_store` 检查是否有相关操作历史和用户偏好
- **操作后**：存储操作结果、参数配置、遇到的问题
- **错误恢复**：记录错误原因和解决方案，避免重复犯错

```python
from memory_store import get_memory_store
memory = get_memory_store()

# 检查操作历史
history = memory.check_operation("sd_create_blend_node")

# 存储操作结果
memory.store("sd_last_operation", {
    "action": "create_node",
    "definition": "sbs::compositing::blend",
    "graph": graph.getIdentifier(),
    "success": True
})
```

---

## 标准操作模板

所有 SD 操作脚本应遵循此结构：

```python
import sd
from sd.api.sdapplication import SDApplication

app = SDApplication.getApplication()
graph = app.getUIMgr().getCurrentGraph()

if graph is None:
    print("错误：没有打开的图")
else:
    try:
        # ========== 操作代码 ==========
        
        # 1. 验证前置条件
        # 2. 执行操作
        # 3. 验证结果
        
        # ========== 操作结束 ==========
        print("操作完成")
    except Exception as e:
        print(f"操作失败: {e}")
```

---

## 关键 import 参考

```python
# 基础
from sd.api.sdapplication import SDApplication
from sd.api.sdpackage import SDPackage
from sd.api.sdgraph import SDGraph
from sd.api.sdnode import SDNode

# 属性
from sd.api.sdproperty import SDProperty, SDPropertyCategory
from sd.api.sdvalue import SDValue
from sd.api.sdvaluefloat import SDValueFloat
from sd.api.sdvaluefloat2 import SDValueFloat2
from sd.api.sdvaluefloat3 import SDValueFloat3
from sd.api.sdvaluefloat4 import SDValueFloat4
from sd.api.sdvalueint import SDValueInt
from sd.api.sdvaluebool import SDValueBool
from sd.api.sdvalueenum import SDValueEnum
from sd.api.sdvaluestring import SDValueString

# 颜色模式
from sd.api.sdvaluecolorrgba import SDValueColorRGBA

# 类型
from sd.api.sdtypefloat import SDTypeFloat
from sd.api.sdtypefloat2 import SDTypeFloat2
from sd.api.sdtypefloat3 import SDTypeFloat3
from sd.api.sdtypefloat4 import SDTypeFloat4
from sd.api.sdtypeint import SDTypeInt
```
