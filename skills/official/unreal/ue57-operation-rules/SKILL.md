---
name: ue57-operation-rules
description: >
  UE Editor 操作通用规则和最佳实践。所有涉及 UE 场景修改的操作都必须遵守。
  AI 在执行任何 UE 场景操作任务前应先读取此 Skill。
  包含：坐标系、操作后刷新视口、Rotator 安全规则、撤销提示等强制规则。
  Use when AI needs to: (1) perform any scene modification,
  (2) check post-operation best practices,
  (3) ensure viewport refresh after edits,
  (4) understand UE coordinate system.
  UE only (run_ue_python).
metadata:
  artclaw:
    author: ArtClaw
    software: unreal_engine
---

# UE 操作通用规则

所有涉及 UE 场景修改的操作都必须遵守以下规则。

> ⚠️ **仅适用于 Unreal Engine** — 通过 `run_ue_python` 执行

---

## 🌐 规则 0：坐标系

UE 使用 **Z-Up 左手坐标系**：

| 轴 | 方向 | 说明 |
|---|---|---|
| **X** | 前 (Forward) | 角色/相机默认朝向 |
| **Y** | 右 (Right) | 屏幕右侧 |
| **Z** | 上 (Up) | 垂直向上 |

**左手系判定**：左手拇指指向 X（前），食指指向 Y（右），中指指向 Z（上）。

**与其他 DCC 的换算**：
- **从 Maya (Y-Up 右手系) 导入**：Maya Y → UE Z，Maya Z → UE -Y（Maya Z 指向屏幕外 = UE 的 -Y）
- **从 3ds Max (Z-Up 右手系) 导入**：Max Y → UE -Y（Max 的 Y 指向屏幕里 = UE 的 -Y）
- **FBX 导入时 UE 会自动处理轴转换**，手动计算位置时注意上述映射

```python
# UE 坐标示例
pos = unreal.Vector(x=100, y=0, z=50)   # 前方100, 高度50
rot = unreal.Rotator(pitch=-15, yaw=90, roll=0)  # 俯视15°, 朝右
```

---

## 🔄 规则 1：操作完成后必须刷新视口

**每次完成场景修改操作后（包括但不限于：创建/删除 Actor、修改属性、调整光照、材质修改等），必须在最后调用视口刷新。**

```python
import unreal

# ... 执行场景操作 ...

# ✅ 操作结束后刷新视口
unreal.LevelEditorSubsystem().editor_invalidate_viewports()
```

### 何时刷新
- 一个完整任务的**最后一步**执行刷新即可
- 不需要每个小操作都刷新，**批量操作结束后统一刷新一次**
- 如果是多步骤任务（多次 run_ue_python 调用），在**最后一次调用**中刷新

### 刷新代码模板

```python
# 放在操作代码的最末尾
unreal.LevelEditorSubsystem().editor_invalidate_viewports()
print("✅ 视口已刷新")
```

---

## ⚠️ 规则 2：Rotator 必须使用关键字参数

`unreal.Rotator` 的位置参数顺序是 `(roll, pitch, yaw)`，**不是** `(pitch, yaw, roll)`。

```python
# ❌ 禁止使用位置参数
r = unreal.Rotator(-15, 180, 0)  # 实际是 roll=-15, pitch=180, yaw=0

# ✅ 必须使用关键字参数
r = unreal.Rotator(pitch=-15, yaw=180, roll=0)
```

详见 `ue57-camera-transform` Skill。

---

## 💡 规则 3：提示用户可撤销

对场景进行修改后，应告知用户：
- 所有操作支持 **Ctrl+Z 撤销**
- 如果是批量操作，说明修改了哪些内容

---

## 📋 规则 4：操作前确认（破坏性操作）

以下操作执行前应向用户确认：
- **删除 Actor**（除非用户明确指示）
- **批量修改属性**（超过 10 个对象）
- **替换材质/网格体**

非破坏性操作（调整参数、移动位置等）可以直接执行。

---

## 🔧 标准操作收尾模板

```python
import unreal

# ... 所有操作代码 ...

# === 收尾 ===
unreal.LevelEditorSubsystem().editor_invalidate_viewports()
print("✅ 操作完成，视口已刷新")
# 提示：可用 Ctrl+Z 撤销
```

---

## 🧠 规则 5：记忆系统集成

### 反复出错时主动查记忆 (强制)

当同一类操作**连续失败 2 次以上**时，必须先搜索记忆再继续尝试：

```python
from memory_store import get_memory_store
mm = get_memory_store()
if mm:
    hints = mm.manager.search("相关关键词", tag="crash", limit=3)
    hints += mm.manager.search("相关关键词", tag="pattern", limit=3)
    team = mm.manager.search_team_memory("相关关键词", limit=3)
    # 根据找到的规则调整方案
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
