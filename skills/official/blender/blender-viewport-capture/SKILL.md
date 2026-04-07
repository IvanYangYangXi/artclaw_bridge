---
name: blender-viewport-capture
description: >
  捕获 Blender 视口截图用于 AI 分析。支持 OpenGL 渲染截图和渲染预览截图。
  Use when AI needs to: (1) take a screenshot of the current viewport,
  (2) analyze scene composition visually,
  (3) capture rendered preview for AI feedback.
  NOT for: final production rendering, animation rendering.
  Blender only (run_python).
metadata:
  artclaw:
    author: ArtClaw
    software: blender
---

# Blender 视口截图

捕获 Blender 3D 视口画面，用于 AI 视觉分析（构图、光照、场景检查等）。

> ⚠️ **仅适用于 Blender** — 通过 `run_python` 执行

---

## 核心方法

### 方法 1：OpenGL 渲染截图（推荐）

使用 `bpy.ops.render.opengl()` 进行视口 OpenGL 渲染，捕获当前 3D 视口画面。

```python
import bpy
import os
import tempfile

# 保存原始设置
scene = bpy.context.scene
original_path = scene.render.filepath
original_format = scene.render.image_settings.file_format
original_quality = scene.render.image_settings.quality

# 设置输出
output_dir = os.path.join(tempfile.gettempdir(), "artclaw_captures")
os.makedirs(output_dir, exist_ok=True)

import time
timestamp = int(time.time())
output_path = os.path.join(output_dir, f"viewport_{timestamp}.png")

scene.render.filepath = output_path
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.quality = 90

# 执行 OpenGL 渲染（视口截图）
bpy.ops.render.opengl(write_still=True)

# 恢复原始设置
scene.render.filepath = original_path
scene.render.image_settings.file_format = original_format
scene.render.image_settings.quality = original_quality

print(f"✅ 视口截图已保存: {output_path}")
```

### 方法 2：带自定义分辨率的截图

```python
import bpy
import os
import tempfile
import time

scene = bpy.context.scene

# 保存原始设置
original_path = scene.render.filepath
original_format = scene.render.image_settings.file_format
original_quality = scene.render.image_settings.quality
original_res_x = scene.render.resolution_x
original_res_y = scene.render.resolution_y
original_pct = scene.render.resolution_percentage

# 设置截图分辨率
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100

# 设置输出路径
output_dir = os.path.join(tempfile.gettempdir(), "artclaw_captures")
os.makedirs(output_dir, exist_ok=True)
timestamp = int(time.time())
output_path = os.path.join(output_dir, f"viewport_{timestamp}.jpg")

scene.render.filepath = output_path
scene.render.image_settings.file_format = 'JPEG'
scene.render.image_settings.quality = 85

# 执行截图
bpy.ops.render.opengl(write_still=True)

# 恢复所有原始设置
scene.render.filepath = original_path
scene.render.image_settings.file_format = original_format
scene.render.image_settings.quality = original_quality
scene.render.resolution_x = original_res_x
scene.render.resolution_y = original_res_y
scene.render.resolution_percentage = original_pct

print(f"✅ 视口截图已保存: {output_path}")
```

---

## AI 分析用截图（base64 编码返回）

用于将截图直接传递给 AI 进行视觉分析，无需用户手动操作文件。

```python
import bpy
import os
import tempfile
import time
import base64

scene = bpy.context.scene

# 保存原始设置
original_path = scene.render.filepath
original_format = scene.render.image_settings.file_format
original_quality = scene.render.image_settings.quality
original_res_x = scene.render.resolution_x
original_res_y = scene.render.resolution_y
original_pct = scene.render.resolution_percentage

# 使用较小分辨率节省 token
scene.render.resolution_x = 1024
scene.render.resolution_y = 576
scene.render.resolution_percentage = 100

# 临时文件
output_dir = os.path.join(tempfile.gettempdir(), "artclaw_captures")
os.makedirs(output_dir, exist_ok=True)
timestamp = int(time.time())
output_path = os.path.join(output_dir, f"viewport_analyze_{timestamp}.jpg")

scene.render.filepath = output_path
scene.render.image_settings.file_format = 'JPEG'
scene.render.image_settings.quality = 80

# 执行截图
bpy.ops.render.opengl(write_still=True)

# 恢复设置
scene.render.filepath = original_path
scene.render.image_settings.file_format = original_format
scene.render.image_settings.quality = original_quality
scene.render.resolution_x = original_res_x
scene.render.resolution_y = original_res_y
scene.render.resolution_percentage = original_pct

# 读取并编码为 base64
with open(output_path, 'rb') as f:
    img_base64 = base64.b64encode(f.read()).decode('utf-8')

# 获取文件大小
file_size_kb = os.path.getsize(output_path) / 1024

print(f"✅ 截图完成: {scene.render.resolution_x}x{scene.render.resolution_y}")
print(f"   文件: {output_path}")
print(f"   大小: {file_size_kb:.1f} KB")
print(f"   Base64 长度: {len(img_base64)} 字符")

# 将 base64 数据存入 result 变量供 AI 使用
result = {
    "image_base64": img_base64,
    "image_path": output_path,
    "resolution": [1024, 576],
    "format": "JPEG",
    "size_kb": round(file_size_kb, 1),
}
```

---

## 带视口信息的完整截图上下文

```python
import bpy
import os
import tempfile
import time
import base64
import math

scene = bpy.context.scene

# === 1. 收集视口信息 ===
viewport_info = {}
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        space = area.spaces.active
        r3d = space.region_3d
        view_mat = r3d.view_matrix.inverted()
        loc = view_mat.translation
        rot = view_mat.to_euler()
        viewport_info = {
            "camera_location": {"x": round(loc.x, 3), "y": round(loc.y, 3), "z": round(loc.z, 3)},
            "camera_rotation": {
                "x": round(math.degrees(rot.x), 1),
                "y": round(math.degrees(rot.y), 1),
                "z": round(math.degrees(rot.z), 1),
            },
            "view_type": r3d.view_perspective,  # PERSP / ORTHO / CAMERA
            "shading": space.shading.type,       # WIREFRAME / SOLID / MATERIAL / RENDERED
            "view_distance": round(r3d.view_distance, 3),
        }
        break

# === 2. 截图 ===
original_path = scene.render.filepath
original_format = scene.render.image_settings.file_format
original_quality = scene.render.image_settings.quality
original_res_x = scene.render.resolution_x
original_res_y = scene.render.resolution_y
original_pct = scene.render.resolution_percentage

scene.render.resolution_x = 1024
scene.render.resolution_y = 576
scene.render.resolution_percentage = 100

output_dir = os.path.join(tempfile.gettempdir(), "artclaw_captures")
os.makedirs(output_dir, exist_ok=True)
timestamp = int(time.time())
output_path = os.path.join(output_dir, f"viewport_ctx_{timestamp}.jpg")

scene.render.filepath = output_path
scene.render.image_settings.file_format = 'JPEG'
scene.render.image_settings.quality = 80

bpy.ops.render.opengl(write_still=True)

scene.render.filepath = original_path
scene.render.image_settings.file_format = original_format
scene.render.image_settings.quality = original_quality
scene.render.resolution_x = original_res_x
scene.render.resolution_y = original_res_y
scene.render.resolution_percentage = original_pct

# === 3. Base64 编码 ===
with open(output_path, 'rb') as f:
    img_base64 = base64.b64encode(f.read()).decode('utf-8')

# === 4. 场景统计 ===
from collections import Counter
type_counts = dict(Counter(obj.type for obj in bpy.data.objects))

scene_stats = {
    "total_objects": len(bpy.data.objects),
    "by_type": type_counts,
    "total_meshes": len(bpy.data.meshes),
    "total_materials": len(bpy.data.materials),
    "render_engine": scene.render.engine,
    "file": bpy.path.basename(bpy.data.filepath) or "(未保存)",
}

# === 5. 组装结果 ===
result = {
    "image_base64": img_base64,
    "image_path": output_path,
    "resolution": [1024, 576],
    "viewport": viewport_info,
    "scene_stats": scene_stats,
}

print(f"✅ 完整视口上下文已生成")
print(f"   截图: {output_path} ({os.path.getsize(output_path)/1024:.1f} KB)")
print(f"   物体总数: {scene_stats['total_objects']}")
print(f"   视角: {viewport_info.get('view_type', 'N/A')}")
print(f"   着色: {viewport_info.get('shading', 'N/A')}")
```

---

## 清理旧截图

```python
import os
import time
import tempfile

capture_dir = os.path.join(tempfile.gettempdir(), "artclaw_captures")
if os.path.exists(capture_dir):
    max_age_hours = 24
    cutoff = time.time() - max_age_hours * 3600
    deleted = 0
    for filename in os.listdir(capture_dir):
        filepath = os.path.join(capture_dir, filename)
        if os.path.isfile(filepath) and os.path.getmtime(filepath) < cutoff:
            os.remove(filepath)
            deleted += 1
    print(f"🧹 已清理 {deleted} 个过期截图文件")
else:
    print("截图目录不存在，无需清理")
```

---

## 注意事项

- `bpy.ops.render.opengl()` 截取的是当前 3D 视口的 OpenGL 渲染结果，包含叠加层（overlay）、辅助线（gizmo）等
- 如需干净的截图，可在截图前临时关闭叠加层：`space.overlay.show_overlays = False`
- 截图分辨率受 `resolution_x`、`resolution_y` 和 `resolution_percentage` 三个参数共同控制
- JPEG 格式文件更小（适合 AI 分析），PNG 无损但更大
- 临时文件存储在系统临时目录，不会污染项目目录
- 截图操作不需要 Undo 管理（不修改场景数据）
