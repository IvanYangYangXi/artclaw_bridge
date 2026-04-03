---
name: ue57-camera-transform
description: >
  Set, get, and animate UE Editor viewport camera and CameraActor transforms
  safely. Prevents the common Rotator positional-argument trap (roll,pitch,yaw
  vs pitch,yaw,roll). Use when AI needs to: (1) move or rotate the viewport
  camera, (2) set a CameraActor's transform, (3) look-at a target location, (4)
  orbit around an object, (5) interpolate camera between two poses. NOT for:
  runtime game camera (PlayerCameraManager), Sequencer camera cuts, Maya/Max
  cameras.
metadata:
  artclaw:
    author: ArtClaw
    software: unreal_engine
---

# UE 相机变换操作

安全地操作 UE 编辑器视口相机和 CameraActor 的位置与旋转。

> ⚠️ **仅适用于 Unreal Engine** — 通过 `run_ue_python` 执行

---

## ⚠️ 关键陷阱：Rotator 参数顺序

**这是相机总是转偏的根本原因。**

`unreal.Rotator` 的**位置参数**顺序是 `(roll, pitch, yaw)`，而不是直觉上的 `(pitch, yaw, roll)`：

```python
# ❌ 错误！位置参数顺序是 (roll, pitch, yaw)
r = unreal.Rotator(-15, 180, 0)
# 实际结果: pitch=180, yaw=0, roll=-15  ← 完全错位！

# ✅ 正确！始终使用关键字参数
r = unreal.Rotator(pitch=-15, yaw=180, roll=0)
# 实际结果: pitch=-15, yaw=180, roll=0  ← 符合预期
```

### 强制规则

1. **永远使用关键字参数** 构造 `unreal.Rotator`：`unreal.Rotator(pitch=, yaw=, roll=)`
2. **永远不用位置参数** 构造 Rotator（位置参数顺序是 roll, pitch, yaw，极易出错）
3. `unreal.Vector` 位置参数顺序 `(x, y, z)` 是正常的，可以用位置参数，但推荐关键字参数以保持一致性

### Rotator 含义

| 分量   | 含义             | 轴   | 正方向           |
|--------|------------------|------|------------------|
| pitch  | 俯仰角（上下看） | Y轴  | 正=抬头，负=低头 |
| yaw    | 偏航角（左右看） | Z轴  | 正=右转         |
| roll   | 翻滚角（倾斜）   | X轴  | 正=右倾         |

> **视口相机的 roll 通常应为 0**，除非有特殊需求。如果读取到的 roll 不为 0，可能是之前的错误操作遗留。

---

## 基础操作

### 获取当前视口相机

```python
import unreal

ues = unreal.UnrealEditorSubsystem()
location, rotation = ues.get_level_viewport_camera_info()

print(f"位置: x={location.x:.1f}, y={location.y:.1f}, z={location.z:.1f}")
print(f"旋转: pitch={rotation.pitch:.1f}, yaw={rotation.yaw:.1f}, roll={rotation.roll:.1f}")
```

### 设置视口相机位置和旋转

```python
import unreal

ues = unreal.UnrealEditorSubsystem()

# 始终使用关键字参数！
new_location = unreal.Vector(x=0, y=0, z=500)
new_rotation = unreal.Rotator(pitch=-30, yaw=0, roll=0)

ues.set_level_viewport_camera_info(new_location, new_rotation)
```

### 仅移动视口相机（保持当前旋转）

```python
import unreal

ues = unreal.UnrealEditorSubsystem()
_, current_rotation = ues.get_level_viewport_camera_info()

new_location = unreal.Vector(x=100, y=200, z=300)
ues.set_level_viewport_camera_info(new_location, current_rotation)
```

### 仅旋转视口相机（保持当前位置）

```python
import unreal

ues = unreal.UnrealEditorSubsystem()
current_location, _ = ues.get_level_viewport_camera_info()

new_rotation = unreal.Rotator(pitch=-15, yaw=90, roll=0)
ues.set_level_viewport_camera_info(current_location, new_rotation)
```

---

## 高级操作

### 让视口相机看向目标点

```python
import unreal
import math

ues = unreal.UnrealEditorSubsystem()

# 相机位置
camera_pos = unreal.Vector(x=500, y=500, z=300)

# 目标点
target_pos = unreal.Vector(x=0, y=0, z=100)

# 计算方向
dx = target_pos.x - camera_pos.x
dy = target_pos.y - camera_pos.y
dz = target_pos.z - camera_pos.z

# 计算 yaw 和 pitch
yaw = math.degrees(math.atan2(dy, dx))
horizontal_dist = math.sqrt(dx*dx + dy*dy)
pitch = math.degrees(math.atan2(dz, horizontal_dist))

look_rotation = unreal.Rotator(pitch=pitch, yaw=yaw, roll=0)
ues.set_level_viewport_camera_info(camera_pos, look_rotation)

print(f"相机已移动到 ({camera_pos.x}, {camera_pos.y}, {camera_pos.z})")
print(f"朝向目标 ({target_pos.x}, {target_pos.y}, {target_pos.z})")
print(f"旋转: pitch={pitch:.1f}, yaw={yaw:.1f}")
```

### 围绕目标点旋转（轨道相机）

```python
import unreal
import math

ues = unreal.UnrealEditorSubsystem()

# 参数
target = unreal.Vector(x=0, y=0, z=100)   # 目标点
distance = 800                              # 距离
orbit_yaw = 45                              # 水平角度 (度)
orbit_pitch = -30                           # 垂直角度 (度，负=俯视)

# 计算相机位置（球面坐标转笛卡尔坐标）
yaw_rad = math.radians(orbit_yaw)
pitch_rad = math.radians(orbit_pitch)

cam_x = target.x + distance * math.cos(pitch_rad) * math.cos(yaw_rad)
cam_y = target.y + distance * math.cos(pitch_rad) * math.sin(yaw_rad)
cam_z = target.z + distance * math.sin(-pitch_rad)  # 负号：pitch负=俯视=相机在上方

camera_pos = unreal.Vector(x=cam_x, y=cam_y, z=cam_z)

# 计算朝向目标的旋转
dx = target.x - cam_x
dy = target.y - cam_y
dz = target.z - cam_z
look_yaw = math.degrees(math.atan2(dy, dx))
look_pitch = math.degrees(math.atan2(dz, math.sqrt(dx*dx + dy*dy)))

look_rotation = unreal.Rotator(pitch=look_pitch, yaw=look_yaw, roll=0)
ues.set_level_viewport_camera_info(camera_pos, look_rotation)
```

### 设置 CameraActor 的变换

```python
import unreal

# 找到场景中的 CameraActor
all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
cameras = [a for a in all_actors if isinstance(a, unreal.CameraActor)]

if cameras:
    cam = cameras[0]

    # 设置位置
    cam.set_actor_location(
        unreal.Vector(x=0, y=0, z=500),
        sweep=False,
        teleport=True
    )

    # 设置旋转 — 同样必须用关键字参数！
    cam.set_actor_rotation(
        unreal.Rotator(pitch=-45, yaw=90, roll=0),
        teleport_physics=True
    )

    print(f"已设置 {cam.get_name()} 的变换")
```

### 保存和恢复视口相机状态

```python
import unreal

ues = unreal.UnrealEditorSubsystem()

# 保存当前状态
loc, rot = ues.get_level_viewport_camera_info()
saved = {
    'x': loc.x, 'y': loc.y, 'z': loc.z,
    'pitch': rot.pitch, 'yaw': rot.yaw, 'roll': rot.roll
}

# ... 执行其他操作 ...

# 恢复
ues.set_level_viewport_camera_info(
    unreal.Vector(x=saved['x'], y=saved['y'], z=saved['z']),
    unreal.Rotator(pitch=saved['pitch'], yaw=saved['yaw'], roll=saved['roll'])
)
```

---

## 注意事项

- **视口相机 ≠ CameraActor**：`set_level_viewport_camera_info` 操作的是编辑器视口，不是场景中的 CameraActor
- **Pilot 模式**：`pilot_level_actor(actor)` 会将视口锁定到某个 Actor，操作完用 `eject_pilot_level_actor()` 解除
- **roll 归零**：普通操作时 roll 应为 0，如果发现 roll 不为 0，通常需要修正
- **角度范围**：pitch 范围 [-90, 90]，yaw 范围 [-180, 180]，超出范围会自动归一化
