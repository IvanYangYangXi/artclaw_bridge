---
name: blender-operation-rules
description: >
  Blender 操作通用规则和最佳实践。所有涉及 Blender 场景修改的操作都必须遵守。
  AI 在执行任何 Blender 场景操作任务前应先读取此 Skill。
  包含：坐标系、撤销管理、脚本输出、上下文检查、破坏性操作确认等强制规则。
  Use when AI needs to: (1) perform any Blender scene modification,
  (2) check post-operation best practices,
  (3) understand Blender coordinate system.
  Blender only (run_python).
metadata:
  artclaw:
    author: ArtClaw
    software: blender
---

# Blender 操作通用规则

所有涉及 Blender 场景修改的操作都必须遵守以下规则。

> ⚠️ **仅适用于 Blender** — 通过 `run_python` 执行

---

## 🌐 规则 0：坐标系

Blender 使用 **Z-Up 右手坐标系**：

| 轴 | 方向 | 说明 |
|---|---|---|
| **X** | 右 (Right) | 屏幕右侧 |
| **Y** | 前 (Forward) | 指向屏幕里（远离观察者） |
| **Z** | 上 (Up) | 垂直向上 |

**右手系判定**：右手拇指指向 X（右），食指指向 Y（前/屏幕里），中指指向 Z（上）。

**与其他 DCC 的换算**：
- **导出到 UE (Z-Up 左手系)**：Blender Y → UE X，Blender X → UE Y（近似，FBX 导出时勾选 "Apply Transform" 会自动处理轴转换）
- **导出到 Maya (Y-Up 右手系)**：Blender Z → Maya Y，Blender Y → Maya -Z
- **导出到 3ds Max (Z-Up 右手系)**：坐标系一致，但注意 Max 默认面法线朝向可能不同
- **FBX 导出**：Blender FBX exporter 默认 Apply Scalings = "FBX All"，Forward = "-Y Forward"，Up = "Z Up"

```python
import bpy

# Blender 坐标示例
obj = bpy.context.active_object
if obj:
    obj.location = (10, 5, 3)       # X=右10, Y=前5, Z=上3
    obj.rotation_euler = (0.785, 0, 0)  # 绕 X 轴旋转约 45°（弧度）
```

---

## 🔄 规则 1：Undo 管理

Blender 的 Python 脚本操作默认**不自动创建 Undo 步骤**（除非通过 `bpy.ops` 调用）。对于直接修改数据的操作，需要手动推送 Undo 点。

### 使用 `bpy.ops.ed.undo_push`

```python
import bpy

# 在修改操作前推送 Undo 点
bpy.ops.ed.undo_push(message='ArtClaw: 操作描述')

# ... 执行修改操作 ...

# 操作完成后告知用户
print("✅ 操作完成（Ctrl+Z 可撤销）")
```

### 注意事项
- `bpy.ops.ed.undo_push()` 在**执行时**保存当前状态快照，之后的修改可被撤销
- 如果操作全部通过 `bpy.ops.*` 完成（如 `bpy.ops.mesh.primitive_cube_add()`），Blender 会自动管理 Undo，无需手动推送
- 直接操作 `bpy.data` 或对象属性时（如 `obj.location = ...`）才需要手动 Undo 推送
- 始终告知用户操作支持 **Ctrl+Z 撤销**

---

## 🖨️ 规则 2：使用 print 输出

Blender Python 控制台和系统控制台显示 `print` 输出。所有需要用户可见的信息必须用 `print`。

```python
# ✅ 用户可见（Blender Python 控制台 / 系统控制台）
print("操作完成：已移动 5 个对象")

# ⚠️ logging 也可用，但不如 print 直观
import logging
logging.info("操作完成")  # 需要配置 handler 才能在控制台显示
```

> **提示**：Blender 有两个控制台 — Python 控制台（编辑器区域类型）和系统控制台（Window → Toggle System Console）。`print` 输出在两者中都可见。

---

## ⚙️ 规则 3：上下文注意

很多 `bpy.ops` 操作依赖当前上下文（激活对象、编辑模式、区域类型等）。操作前必须确认上下文正确。

### 检查和切换模式

```python
import bpy

# 检查当前模式
current_mode = bpy.context.mode  # 'OBJECT', 'EDIT_MESH', 'SCULPT', etc.

# 确保在物体模式
if bpy.context.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

# 切换到编辑模式（需要有激活对象）
if bpy.context.active_object:
    bpy.ops.object.mode_set(mode='EDIT')
```

### 检查激活对象

```python
import bpy

active = bpy.context.active_object
if active is None:
    print("⚠️ 没有激活对象，请先选择一个对象")
else:
    print(f"激活对象: {active.name} (类型: {active.type})")
```

### 常见上下文问题
- `bpy.ops.object.*` 需要在 `OBJECT` 模式下
- `bpy.ops.mesh.*` 需要在 `EDIT` 模式下且激活对象为 Mesh
- `bpy.ops.transform.*` 需要有选中的对象
- 某些操作需要特定的 `area.type`（如 `VIEW_3D`）。在脚本中可以用上下文覆盖：

```python
# 上下文覆盖示例（当不在 3D 视口中时）
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        with bpy.context.temp_override(area=area):
            bpy.ops.view3d.snap_cursor_to_center()
        break
```

---

## ⚠️ 规则 4：操作前确认（破坏性操作）

以下操作执行前应向用户确认：
- **删除物体**（`bpy.data.objects.remove()` / `bpy.ops.object.delete()`）
- **删除数据块**（`bpy.data.meshes.remove()` 等）
- **清空场景**（删除所有对象）
- **批量修改**（超过 10 个对象的批量操作）
- **清除 Orphan Data**（`bpy.ops.outliner.orphans_purge()`）

非破坏性操作（调整参数、移动位置、添加修改器等）可以直接执行。

---

## 📝 规则 5：常用快捷代码

```python
import bpy
import math

# ===== 选择 =====
selected = bpy.context.selected_objects      # 所有选中物体
active = bpy.context.active_object           # 激活物体（绿色高亮）

# 通过名称获取物体
obj = bpy.data.objects.get('Cube')           # 返回 None 如果不存在

# 选中/取消选中
obj.select_set(True)                         # 选中
obj.select_set(False)                        # 取消选中
bpy.context.view_layer.objects.active = obj  # 设为激活物体

# 全选 / 取消全选
bpy.ops.object.select_all(action='SELECT')   # 全选
bpy.ops.object.select_all(action='DESELECT') # 取消全选

# ===== 创建物体 =====
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(3, 0, 0))
bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=2, location=(0, 3, 0))

# ===== 变换 =====
obj.location = (1, 2, 3)                             # 位置
obj.rotation_euler = (math.radians(45), 0, 0)         # 旋转（欧拉角，弧度）
obj.rotation_euler.x = math.radians(90)               # 单轴旋转
obj.scale = (2, 2, 2)                                 # 缩放

# ===== 材质 =====
mat = bpy.data.materials.new(name="MyMaterial")
mat.use_nodes = True
obj.data.materials.append(mat)                        # 添加材质到物体

# ===== 修改器 =====
mod = obj.modifiers.new(name="Subdiv", type='SUBSURF')
mod.levels = 2                                        # 视口细分级别
mod.render_levels = 3                                  # 渲染细分级别

# ===== 父子关系 =====
child_obj.parent = parent_obj
child_obj.matrix_parent_inverse = parent_obj.matrix_world.inverted()

# ===== 集合 =====
collection = bpy.data.collections.new("MyCollection")
bpy.context.scene.collection.children.link(collection)
collection.objects.link(obj)                           # 将物体加入集合
```

---

## 🧠 规则 6：记忆系统集成

### 反复出错时主动查记忆（强制）

当同一类操作**连续失败 2 次以上**时，必须先搜索记忆再继续尝试：

```python
from core.memory_store import get_memory_store
mm = get_memory_store()
if mm:
    hints = mm.manager.search("相关关键词", tag="crash", limit=3)
    hints += mm.manager.search("相关关键词", tag="pattern", limit=3)
    team = mm.manager.search_team_memory("相关关键词", limit=3)
```

### 多次尝试后成功时提炼教训（强制）

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

### 发现反直觉行为时记录（强制）

```python
mm.manager.record(
    key="pattern:API或行为描述",
    value="实际行为 vs 预期行为，正确用法",
    tag="pattern",
    importance=0.9,
    source="gotcha"
)
```

---

## 🔧 标准操作收尾模板

```python
import bpy

bpy.ops.ed.undo_push(message='ArtClaw_Operation')

# ========== 所有操作代码 ==========

# ... 在此编写具体操作 ...

# ========== 操作结束 ==========

print("✅ 操作完成")
# 提示：可用 Ctrl+Z 撤销
```

> **注意**：如果操作全部通过 `bpy.ops.*` 完成，可省略 `undo_push` 行，因为 `bpy.ops` 调用自带 Undo 管理。
