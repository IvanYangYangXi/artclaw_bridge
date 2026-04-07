---
name: blender-operation-rules
description: >
  Blender 操作通用规则和最佳实践。所有涉及 Blender 场景修改的操作都必须遵守。
  AI 在执行任何 Blender 场景操作任务前应先读取此 Skill。
  包含：坐标系、Undo 管理、预注入变量、Blender 5.x API 变化、上下文覆盖等强制规则。
  Use when AI needs to: (1) perform any Blender scene modification,
  (2) check post-operation best practices, (3) understand Blender coordinate system.
  Blender only (run_python).
metadata:
  artclaw:
    author: ArtClaw
    software: blender
---

# Blender 操作通用规则

> **强制要求**：所有涉及 Blender 场景修改的 AI 操作都必须遵守以下规则。

---

## 规则 0：预注入变量

`mcp_blender-editor_run_python` 执行代码时，以下变量已自动注入，**无需手动 import 或赋值**：

| 变量 | 值 | 说明 |
|------|------|------|
| `bpy` | `bpy` 模块 | Blender Python API |
| `S` | `list(bpy.context.selected_objects)` | 选中对象列表（执行时快照） |
| `W` | `bpy.data.filepath` | 当前文件路径（未保存则为空字符串） |
| `L` | `bpy` 模块 | 标准 Library 引用（与其他 DCC 统一命名） |
| `C` | `bpy.context` | 上下文（Blender 惯例快捷变量） |
| `D` | `bpy.data` | 数据管理器（Blender 惯例快捷变量） |

- 将返回值赋给 `result` 变量，框架会自动提取并返回。
- `C` 和 `D` 是 Blender 自带 Python 控制台的标准惯例。

---

## 规则 1：坐标系

- Blender 使用 **Z-up 右手坐标系**
- 正面朝 **-Y 方向**（相机默认看向 -Z）
- 旋转单位为 **弧度**，使用 `math.radians()` 转换：

```python
import math
obj.rotation_euler = (math.radians(90), 0, 0)  # 绕 X 轴旋转 90°
```

---

## 规则 2：Undo 管理

- `execute_code` 执行前会自动调用 `bpy.ops.ed.undo_push(message="ArtClaw AI")`
- 用户可通过单次 **Ctrl+Z** 撤销 AI 的操作
- **破坏性操作前**（删除对象、清空场景等），建议先打印当前状态以便确认：

```python
# 删除前先记录
print(f"即将删除 {len(S)} 个对象: {[o.name for o in S]}")
```

---

## 规则 3：Blender 5.x Layered Action 系统（Breaking Change）

> **关键变化**：Blender 5.1+ 中，`action.fcurves` 属性已移除。

- 新版 Action 默认使用 Layered Action 系统：`action.is_action_layered == True`
- FCurves 必须通过分层路径访问：`action.layers[].strips[].channelbags[].fcurves`

### 正确的 FCurves 遍历方式

```python
def get_all_fcurves(action):
    """兼容 Blender 5.x 的 FCurves 获取"""
    fcurves = []
    if hasattr(action, 'is_action_layered') and action.is_action_layered:
        # Blender 5.x Layered Action
        for layer in action.layers:
            for strip in layer.strips:
                for channelbag in strip.channelbags:
                    fcurves.extend(channelbag.fcurves)
    else:
        # Legacy Action（Blender 4.x 及更早）
        fcurves.extend(action.fcurves)
    return fcurves
```

### 错误示例（会在 5.x 报错）

```python
# ❌ 错误：action.fcurves 在 5.x 中不存在
for fc in action.fcurves:
    print(fc.data_path)
```

---

## 规则 4：Principled BSDF 输入名变化（Blender 5.x）

Blender 5.x 中部分 Principled BSDF 输入名已更改：

| 旧名称（4.x） | 新名称（5.x） |
|---------------|---------------|
| `Specular` | `Specular IOR Level` |
| `Transmission` | `Transmission Weight` |

### 新增输入

- `Thin Film Thickness`
- `Thin Film IOR`
- `Diffuse Roughness`

### 完整 Principled BSDF 输入列表（5.x）

`Base Color`, `Metallic`, `Roughness`, `IOR`, `Alpha`,
`Normal`, `Weight`, `Diffuse Roughness`,
`Subsurface Weight`, `Subsurface Radius`, `Subsurface Scale`, `Subsurface IOR`, `Subsurface Anisotropy`,
`Specular IOR Level`, `Specular Tint`,
`Anisotropic`, `Anisotropic Rotation`, `Tangent`,
`Transmission Weight`,
`Coat Weight`, `Coat Roughness`, `Coat IOR`, `Coat Tint`, `Coat Normal`,
`Sheen Weight`, `Sheen Roughness`, `Sheen Tint`,
`Thin Film Thickness`, `Thin Film IOR`,
`Emission Color`, `Emission Strength`

### 安全获取输入的方式

```python
# ✅ 安全：先检查输入是否存在
node = mat.node_tree.nodes.get("Principled BSDF")
if node:
    for input_name in ["Specular IOR Level", "Specular"]:
        inp = node.inputs.get(input_name)
        if inp is not None:
            inp.default_value = 0.5
            break
```

---

## 规则 5：中文版 Blender 注意事项

- 中文版 Blender 的默认对象名为中文：`立方体`、`球体`、`灯光` 等
- **不要硬编码英文名**（`Cube`、`Sphere`），会找不到对象

### 正确做法

```python
# ✅ 通过上下文获取（不依赖名称）
obj = C.active_object
selected = S  # 预注入的选中对象列表

# ✅ 创建后立即获取引用
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
new_cube = C.active_object  # 刚创建的对象自动成为 active
new_cube.name = "MyCube"    # 可以立即重命名
```

### 错误示例

```python
# ❌ 错误：中文版中不存在 "Cube"
obj = D.objects["Cube"]
```

---

## 规则 6：上下文覆盖（Context Override）

很多 `bpy.ops` 操作需要特定的上下文（如 3D Viewport 的 area 和 region）。
通过 MCP 远程执行时，可能缺少正确的上下文环境。

### 使用 `temp_override()` 构建上下文

```python
def get_3d_viewport_context():
    """获取 3D Viewport 上下文用于 bpy.ops 调用"""
    for window in C.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        return {
                            'window': window,
                            'screen': window.screen,
                            'area': area,
                            'region': region,
                        }
    return None

# 使用示例
ctx = get_3d_viewport_context()
if ctx:
    with C.temp_override(**ctx):
        bpy.ops.view3d.snap_cursor_to_center()
```

### 常见需要上下文覆盖的操作

- `bpy.ops.view3d.*` — 3D 视口操作
- `bpy.ops.object.mode_set()` — 模式切换
- `bpy.ops.mesh.*` — 编辑模式下的网格操作
- `bpy.ops.uv.*` — UV 操作

---

## 规则 7：禁止高开销操作

以下操作在 MCP exec 环境中**禁止或应避免**：

### 禁止

- ❌ `addon_utils.modules()` — 遍历所有插件模块，会导致长时间阻塞（10s+）
- ❌ `bpy.ops.wm.open_mainfile()` — 在 exec 中打开文件会导致状态不一致

### 应避免

- ⚠️ 单次执行中串联过多 `bpy.ops` 调用（每个 ops 调用都有开销）
- ⚠️ 大量对象操作时应分批处理（每批 100-500 个）
- ⚠️ 避免在循环中反复调用 `bpy.ops.object.select_all()`

### 大量对象的推荐做法

```python
# ✅ 批量创建对象时使用低级 API
import bmesh

mesh = D.meshes.new("BatchMesh")
obj = D.objects.new("BatchObj", mesh)
C.collection.objects.link(obj)

# 使用 bmesh 进行批量几何操作
bm = bmesh.new()
# ... 操作 ...
bm.to_mesh(mesh)
bm.free()
```

---

## 标准操作模板

```python
# 预注入变量已可用: bpy, S, W, L, C, D
# 无需 import bpy

if not D.objects:
    result = "场景中没有对象"
else:
    try:
        # 你的操作代码
        obj = C.active_object
        if obj:
            result = f"当前活动对象: {obj.name} (类型: {obj.type})"
        else:
            result = f"场景共 {len(D.objects)} 个对象，无活动对象"
    except Exception as e:
        result = f"操作失败: {e}"
```

---

## 附录：与其他 DCC 的坐标系对比

| DCC | Up 轴 | 前方 | 旋转单位 | 手性 |
|-----|--------|------|----------|------|
| **Blender** | Z | -Y | 弧度 | 右手 |
| UE | Z | X | 度 | 左手 |
| Maya | Y | Z | 度 | 右手 |
| 3ds Max | Z | Y | 度 | 右手 |
