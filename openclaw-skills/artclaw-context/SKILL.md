# ArtClaw 编辑器上下文查询

获取当前编辑器状态、选中对象、场景信息、关卡/文件名、视口信息、对象数量等。

> **覆盖原 MCP 工具**: `get_editor_context`, `get_selected_objects`, `get_scene_info`

## 调用方式

通过 MCP 工具 `run_ue_python`（UE）或 `run_python`（Maya/Max）执行 Python 代码来获取编辑器上下文。

---

## UE (Unreal Engine)

使用 `run_ue_python` 工具执行以下代码。

> **提示**: `run_ue_python` 支持 `inject_context=true` 参数，会自动注入以下便捷变量：
> - `S` — 当前选中的 actors 列表
> - `W` — 当前 editor world
> - `L` — 当前关卡名称

### 获取选中对象

```python
import unreal

selected = unreal.EditorLevelLibrary.get_selected_level_actors()
for actor in selected:
    print(f"{actor.get_name()} ({actor.get_class().get_name()})")
```

或使用 `inject_context=true` 后直接用 `S`：

```python
# inject_context=true 时可直接使用
for actor in S:
    print(actor.get_name())
```

### 获取场景所有对象

```python
import unreal

all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
print(f"场景对象总数: {len(all_actors)}")
for actor in all_actors:
    print(f"  {actor.get_name()} - {actor.get_class().get_name()}")
```

### 获取当前关卡/世界名称

```python
import unreal

world = unreal.EditorLevelLibrary.get_editor_world()
print(f"当前关卡: {world.get_name()}")
```

### 获取视口信息

```python
import unreal

# 获取活动视口的摄像机位置和旋转
viewport = unreal.UnrealEditorSubsystem().get_level_viewport_camera_info()
```

---

## Maya

使用 `run_python` 工具执行以下代码。

### 获取选中对象

```python
import maya.cmds as cmds

selected = cmds.ls(selection=True)
print(f"选中对象: {selected}")
```

### 获取当前场景文件

```python
import maya.cmds as cmds

scene_name = cmds.file(query=True, sceneName=True)
print(f"当前场景: {scene_name}")
```

### 获取场景所有对象

```python
import maya.cmds as cmds

all_objects = cmds.ls(dag=True)
print(f"场景对象总数: {len(all_objects)}")
for obj in all_objects:
    print(f"  {obj} - {cmds.objectType(obj)}")
```

### 获取场景概览

```python
import maya.cmds as cmds

meshes = cmds.ls(type='mesh')
transforms = cmds.ls(type='transform')
cameras = cmds.ls(type='camera')
print(f"Meshes: {len(meshes)}, Transforms: {len(transforms)}, Cameras: {len(cameras)}")
```

---

## 3ds Max

使用 `run_python` 工具执行以下代码。

### 获取选中对象

```python
import pymxs
rt = pymxs.runtime

selected = rt.selection
for obj in selected:
    print(f"{obj.name} ({rt.classOf(obj)})")
```

### 获取当前场景文件

```python
import pymxs
rt = pymxs.runtime

file_path = rt.maxFilePath + rt.maxFileName
print(f"当前场景: {file_path}")
```

### 获取场景所有对象

```python
import pymxs
rt = pymxs.runtime

all_objects = rt.objects
print(f"场景对象总数: {all_objects.count}")
for obj in all_objects:
    print(f"  {obj.name} - {rt.classOf(obj)}")
```

---

## 使用建议

- 需要快速了解场景概况时，先查对象总数和选中对象
- UE 中推荐使用 `inject_context=true` 简化代码
- 复杂查询可以组合多个 API，一次性获取所有需要的信息
