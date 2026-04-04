---
name: maya-operation-rules
description: >
  Maya 操作通用规则和最佳实践。所有涉及 Maya 场景修改的操作都必须遵守。
  AI 在执行任何 Maya 场景操作任务前应先读取此 Skill。
  包含：坐标系、撤销块、脚本输出、中文版路径等强制规则。
  Use when AI needs to: (1) perform any Maya scene modification,
  (2) check post-operation best practices,
  (3) understand Maya coordinate system.
  Maya only (run_python).
metadata:
  artclaw:
    author: ArtClaw
    software: maya
---

# Maya 操作通用规则

所有涉及 Maya 场景修改的操作都必须遵守以下规则。

> ⚠️ **仅适用于 Maya** — 通过 `run_python` 执行

---

## 🌐 规则 0：坐标系

Maya 使用 **Y-Up 右手坐标系**：

| 轴 | 方向 | 说明 |
|---|---|---|
| **X** | 右 (Right) | 屏幕右侧 |
| **Y** | 上 (Up) | 垂直向上 |
| **Z** | 屏幕外 (Toward Viewer) | 面向屏幕时指向你 |

**右手系判定**：右手拇指指向 X（右），食指指向 Y（上），中指指向 Z（屏幕外）。

**与其他 DCC 的换算**：
- **导出到 UE (Z-Up 左手系)**：Maya Y → UE Z，Maya Z → UE -Y
- **导出到 3ds Max (Z-Up 右手系)**：Maya Y → Max Z，Maya Z → Max -Y
- **FBX 导出时勾选 "Up Axis" 设置**，Maya 默认导出 Y-Up，UE 导入时自动转换

```python
import maya.cmds as cmds

# Maya 坐标示例
cmds.move(10, 5, 3, 'pCube1')  # X=右10, Y=上5, Z=向屏幕外3
cmds.rotate(45, 0, 0, 'pCube1')  # 绕 X 轴旋转 45°
```

---

## 🔄 规则 1：批量操作使用 Undo 块

多步修改操作应包裹在 `undoInfo` 块中，让用户可以一次 Ctrl+Z 撤销整个操作。

```python
import maya.cmds as cmds

cmds.undoInfo(openChunk=True, chunkName='ArtClaw_BatchOperation')
try:
    # ... 所有修改操作 ...
    pass
finally:
    cmds.undoInfo(closeChunk=True)
```

### 何时使用 Undo 块
- 涉及**多个对象或多步操作**时必须使用
- 单个简单操作（如移动一个物体）可以不包裹
- `finally` 确保异常时也能正确关闭 chunk

---

## 🖨️ 规则 2：使用 print 而非 logging

Maya 脚本编辑器**不显示** Python `logging` 模块的输出。所有需要用户可见的信息必须用 `print`。

```python
# ❌ 用户看不到
import logging
logging.info("操作完成")

# ✅ 用户可见
print("操作完成")
```

---

## 💡 规则 3：提示用户可撤销

对场景进行修改后，应告知用户：
- 所有操作支持 **Ctrl+Z 撤销**
- 如果使用了 Undo 块，说明整个批量操作可以一次撤销

---

## 📋 规则 4：操作前确认（破坏性操作）

以下操作执行前应向用户确认：
- **删除节点/对象**（除非用户明确指示）
- **批量修改属性**（超过 10 个对象）
- **清空场景 / 删除历史**

非破坏性操作（调整参数、移动位置等）可以直接执行。

---

## 📂 规则 5：中文版 Maya 路径注意

Maya 中文版的脚本路径带 locale 子目录，安装和读取文件时注意：

```
# 英文版
Documents/maya/2023/scripts/

# 中文版（zh_CN 优先级更高）
Documents/maya/2023/zh_CN/scripts/
Documents/maya/2023/scripts/
```

- 写入脚本时**两个目录都要写**
- `zh_CN/scripts/` 优先级高于 `scripts/`，只写后者会被前者的旧文件覆盖

---

## 🔧 标准操作收尾模板

```python
import maya.cmds as cmds

cmds.undoInfo(openChunk=True, chunkName='ArtClaw_Operation')
try:
    # ... 所有操作代码 ...
    pass
finally:
    cmds.undoInfo(closeChunk=True)

print("✅ 操作完成")
# 提示：可用 Ctrl+Z 撤销
```

---

## 🧠 规则 6：记忆系统集成

### 反复出错时主动查记忆 (强制)

当同一类操作**连续失败 2 次以上**时，必须先搜索记忆再继续尝试：

```python
from core.memory_store import get_memory_store
mm = get_memory_store()
if mm:
    hints = mm.manager.search("相关关键词", tag="crash", limit=3)
    hints += mm.manager.search("相关关键词", tag="pattern", limit=3)
    team = mm.manager.search_team_memory("相关关键词", limit=3)
```

### 多次尝试后成功时提炼教训 (强制)

经过 2 次以上尝试或用户纠正后才正确完成操作时，**必须**提炼规则并写入记忆：

```python
mm.manager.record(
    key="pattern:简短问题描述",
    value="一句话规则：什么情况 + 正确做法",
    tag="pattern",
    importance=0.8,
    source="retry_learned"
)
```

### 发现反直觉行为时记录 (强制)

```python
mm.manager.record(
    key="pattern:API或行为描述",
    value="实际行为 vs 预期行为，正确用法",
    tag="pattern",
    importance=0.9,
    source="gotcha"
)
```
