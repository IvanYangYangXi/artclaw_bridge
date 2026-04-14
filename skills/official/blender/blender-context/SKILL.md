---
name: blender-context
description: >
  查询 Blender 编辑器上下文：当前选择、场景信息、文件名、视口相机状态、集合结构。
  Use when AI needs to: (1) get selected objects, (2) get scene overview,
  (3) check current file, (4) inspect viewport state,
  (5) get collection hierarchy.
  Blender only (run_python).
metadata:
  artclaw:
    version: 0.1.0
    author: ArtClaw
    software: blender
---

# Blender 编辑器上下文查询

获取当前 Blender 编辑器状态、选中对象、场景信息、文件名、视口相机等。

> ⚠️ **仅适用于 Blender** — 通过 `run_python` 执行

---

## 获取选中物体列表

```python
import bpy

selected = bpy.context.selected_objects
active = bpy.context.active_object

print(f"选中物体数量: {len(selected)}")
for obj in selected:
    is_active = " ★" if obj == active else ""
    print(f"  {obj.name} (类型: {obj.type}){is_active}")

if active:
    print(f"\n激活物体: {active.name}")
else:
    print("\n无激活物体")
```

---

## 获取场景信息

```python
import bpy

scene = bpy.context.scene
filepath = bpy.data.filepath

print(f"文件路径: {filepath or '(未保存)'}")
print(f"文件名: {bpy.path.basename(filepath) or '(未保存)'}")
print(f"场景名称: {scene.name}")
print(f"物体总数: {len(bpy.data.objects)}")
print(f"网格数量: {len(bpy.data.meshes)}")
print(f"材质数量: {len(bpy.data.materials)}")
print(f"纹理/图像数量: {len(bpy.data.images)}")
print(f"帧范围: {scene.frame_start} - {scene.frame_end}")
print(f"当前帧: {scene.frame_current}")
print(f"FPS: {scene.render.fps}")
print(f"渲染引擎: {scene.render.engine}")
print(f"渲染分辨率: {scene.render.resolution_x} x {scene.render.resolution_y}")

# 按类型统计物体
from collections import Counter
type_counts = Counter(obj.type for obj in bpy.data.objects)
print("\n物体类型统计:")
for obj_type, count in sorted(type_counts.items()):
    print(f"  {obj_type}: {count}")
```

---

## 获取激活物体详情

```python
import bpy
import math

active = bpy.context.active_object
if active is None:
    print("⚠️ 没有激活物体")
else:
    loc = active.location
    rot = active.rotation_euler
    scl = active.scale

    print(f"名称: {active.name}")
    print(f"类型: {active.type}")
    print(f"位置: ({loc.x:.3f}, {loc.y:.3f}, {loc.z:.3f})")
    print(f"旋转: ({math.degrees(rot.x):.1f}°, {math.degrees(rot.y):.1f}°, {math.degrees(rot.z):.1f}°)")
    print(f"缩放: ({scl.x:.3f}, {scl.y:.3f}, {scl.z:.3f})")
    print(f"可见: {active.visible_get()}")
    print(f"隐藏: {active.hide_viewport}")

    # 材质信息
    if hasattr(active.data, 'materials') and active.data is not None:
        mats = active.data.materials
        print(f"\n材质 ({len(mats)} 个):")
        for i, mat in enumerate(mats):
            if mat:
                print(f"  [{i}] {mat.name}")
            else:
                print(f"  [{i}] (空槽位)")

    # 修改器信息
    if hasattr(active, 'modifiers'):
        mods = active.modifiers
        if mods:
            print(f"\n修改器 ({len(mods)} 个):")
            for mod in mods:
                print(f"  {mod.name} (类型: {mod.type})")

    # 约束信息
    if hasattr(active, 'constraints'):
        cons = active.constraints
        if cons:
            print(f"\n约束 ({len(cons)} 个):")
            for con in cons:
                print(f"  {con.name} (类型: {con.type})")

    # 网格数据（如果是 MESH 类型）
    if active.type == 'MESH' and active.data:
        mesh = active.data
        print(f"\n网格数据:")
        print(f"  顶点数: {len(mesh.vertices)}")
        print(f"  边数: {len(mesh.edges)}")
        print(f"  面数: {len(mesh.polygons)}")
        print(f"  UV 层: {len(mesh.uv_layers)}")
```

---

## 获取视口相机信息

```python
import bpy
import math

# 获取 3D 视口
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        space = area.spaces.active
        region_3d = space.region_3d

        # 视口相机变换
        view_mat = region_3d.view_matrix.inverted()
        loc = view_mat.translation
        rot = view_mat.to_euler()

        print("=== 视口相机 ===")
        print(f"位置: ({loc.x:.3f}, {loc.y:.3f}, {loc.z:.3f})")
        print(f"旋转: ({math.degrees(rot.x):.1f}°, {math.degrees(rot.y):.1f}°, {math.degrees(rot.z):.1f}°)")
        print(f"视角类型: {region_3d.view_perspective}")  # 'PERSP', 'ORTHO', 'CAMERA'
        print(f"视距: {region_3d.view_distance:.3f}")
        print(f"焦点: ({region_3d.view_location.x:.3f}, {region_3d.view_location.y:.3f}, {region_3d.view_location.z:.3f})")

        # 着色方式
        print(f"\n着色模式: {space.shading.type}")  # 'WIREFRAME', 'SOLID', 'MATERIAL', 'RENDERED'
        print(f"叠加层: {'开启' if space.overlay.show_overlays else '关闭'}")

        # 场景相机
        cam = bpy.context.scene.camera
        if cam:
            print(f"\n场景相机: {cam.name}")
            cam_loc = cam.location
            cam_rot = cam.rotation_euler
            print(f"  位置: ({cam_loc.x:.3f}, {cam_loc.y:.3f}, {cam_loc.z:.3f})")
            print(f"  旋转: ({math.degrees(cam_rot.x):.1f}°, {math.degrees(cam_rot.y):.1f}°, {math.degrees(cam_rot.z):.1f}°)")
            if cam.data:
                print(f"  焦距: {cam.data.lens:.1f}mm")
                print(f"  传感器尺寸: {cam.data.sensor_width:.1f}mm")
        else:
            print("\n场景相机: (未设置)")

        break
else:
    print("⚠️ 未找到 3D 视口")
```

---

## 获取集合 (Collection) 结构

```python
import bpy

def print_collection_tree(collection, indent=0):
    """递归打印集合树结构"""
    prefix = "  " * indent
    obj_count = len(collection.objects)
    excluded = ""

    # 检查集合在当前视图层中是否被排除
    layer_collection = find_layer_collection(
        bpy.context.view_layer.layer_collection, collection.name
    )
    if layer_collection and layer_collection.exclude:
        excluded = " [已排除]"

    print(f"{prefix}📁 {collection.name} ({obj_count} 个物体){excluded}")

    # 打印集合中的对象
    for obj in collection.objects:
        hidden = " [隐藏]" if obj.hide_viewport else ""
        print(f"{prefix}  └─ {obj.name} ({obj.type}){hidden}")

    # 递归子集合
    for child in collection.children:
        print_collection_tree(child, indent + 1)

def find_layer_collection(layer_col, name):
    """在 LayerCollection 树中查找指定名称的集合"""
    if layer_col.name == name:
        return layer_col
    for child in layer_col.children:
        result = find_layer_collection(child, name)
        if result:
            return result
    return None

# 打印完整集合树
print("=== 集合结构 ===")
print_collection_tree(bpy.context.scene.collection)
```

---

## 一键获取完整上下文

将以上信息整合为一次调用，快速获取完整编辑器状态：

```python
import bpy
import math
from collections import Counter

print("=" * 50)
print("BLENDER EDITOR CONTEXT")
print("=" * 50)

# 1. 文件信息
filepath = bpy.data.filepath
print(f"\n📄 文件: {bpy.path.basename(filepath) or '(未保存)'}")
print(f"   路径: {filepath or 'N/A'}")
print(f"   Blender 版本: {'.'.join(str(v) for v in bpy.app.version)}")

# 2. 场景概览
scene = bpy.context.scene
print(f"\n🎬 场景: {scene.name}")
print(f"   物体总数: {len(bpy.data.objects)}")
type_counts = Counter(obj.type for obj in bpy.data.objects)
for t, c in sorted(type_counts.items()):
    print(f"     {t}: {c}")
print(f"   帧范围: {scene.frame_start}-{scene.frame_end} (当前: {scene.frame_current})")
print(f"   FPS: {scene.render.fps}")
print(f"   渲染引擎: {scene.render.engine}")

# 3. 选择状态
selected = bpy.context.selected_objects
active = bpy.context.active_object
print(f"\n🎯 选择: {len(selected)} 个物体")
for obj in selected[:20]:  # 最多显示 20 个
    tag = " ★" if obj == active else ""
    print(f"   {obj.name} ({obj.type}){tag}")
if len(selected) > 20:
    print(f"   ... 还有 {len(selected) - 20} 个")

# 4. 当前模式
print(f"\n⚙️ 模式: {bpy.context.mode}")

print("\n" + "=" * 50)
```

---

## 使用建议

- 需要快速了解场景概况时，使用「一键获取完整上下文」
- 需要特定信息时，使用对应的单独代码段
- 视口相机信息在分析构图和布局时特别有用
- 集合结构有助于理解场景组织方式
