---
name: max-operation-rules
description: >
  3ds Max 操作通用规则和最佳实践。所有涉及 Max 场景修改的操作都必须遵守。
  AI 在执行任何 3ds Max 场景操作任务前应先读取此 Skill。
  包含：坐标系、撤销管理、脚本输出等强制规则。
  Use when AI needs to: (1) perform any 3ds Max scene modification,
  (2) check post-operation best practices,
  (3) understand 3ds Max coordinate system.
  3ds Max only (run_python).
metadata:
  artclaw:
    author: ArtClaw
    software: 3ds_max
---

# 3ds Max 操作通用规则

所有涉及 3ds Max 场景修改的操作都必须遵守以下规则。

> ⚠️ **仅适用于 3ds Max** — 通过 `run_python` 执行

---

## 🌐 规则 0：坐标系

3ds Max 使用 **Z-Up 右手坐标系**：

| 轴 | 方向 | 说明 |
|---|---|---|
| **X** | 右 (Right) | 屏幕右侧 |
| **Y** | 屏幕里 (Away from Viewer) | 面向屏幕时指向屏幕深处 |
| **Z** | 上 (Up) | 垂直向上 |

**右手系判定**：右手拇指指向 X（右），食指指向 Y（屏幕里），中指指向 Z（上）。

**注意：Max 的 Y 轴方向与 Maya 正好相反**（Max Y 指向屏幕里，Maya Z 指向屏幕外）。

**与其他 DCC 的换算**：
- **导出到 UE (Z-Up 左手系)**：Max Y → UE -Y（Max 右手系 Y 对应 UE 左手系 -Y）。Z 轴相同（都是 Up）
- **导出到 Maya (Y-Up 右手系)**：Max Z → Maya Y，Max Y → Maya -Z
- **FBX 导出时 Max 默认 Z-Up**，UE 导入时自动处理手系转换

```python
from pymxs import runtime as rt

# Max 坐标示例
box = rt.Box()
box.pos = rt.Point3(10, 20, 5)  # X=右10, Y=屏幕里20, Z=上5
box.rotation = rt.EulerAngles(45, 0, 0)  # 绕 X 轴旋转 45°
```

---

## 🔄 规则 1：批量操作使用 Undo 管理

使用 `theHold` 或 `undo()` 上下文确保操作可撤销。

```python
from pymxs import runtime as rt

# 方式 1：undo 上下文（推荐）
with rt.undo(True, 'ArtClaw_BatchOperation'):
    # ... 所有修改操作 ...
    pass

# 方式 2：MAXScript undo
rt.execute('undo "ArtClaw Op" on ( /* operations */ )')
```

### 何时使用 Undo 包裹
- 涉及**多个对象或多步操作**时必须使用
- 单个简单操作（如移动一个物体）可以不包裹
- 避免在循环中逐个开关 undo——包裹整个循环

---

## 🖨️ 规则 2：输出方式

Max Python 中 `print` 输出到 MAXScript Listener。确保重要信息用 `print` 输出。

```python
# ✅ 输出到 Listener
print("操作完成: 已修改 5 个对象")
```

---

## 💡 规则 3：提示用户可撤销

对场景进行修改后，应告知用户：
- 所有操作支持 **Ctrl+Z 撤销**
- 如果使用了 undo 块，说明整个批量操作可以一次撤销

---

## 📋 规则 4：操作前确认（破坏性操作）

以下操作执行前应向用户确认：
- **删除节点/对象**（除非用户明确指示）
- **批量修改属性**（超过 10 个对象）
- **重置场景 / 塌陷修改器堆栈**

非破坏性操作（调整参数、移动位置等）可以直接执行。

---

## 📂 规则 5：中文版 Max 路径注意

3ds Max 中文版的脚本/插件路径可能包含 locale 子目录：

```
# 常见 locale 目录
CHS/  (简体中文)
ENU/  (英文)
JPN/  (日文)
```

安装脚本时应自动检测 locale 目录并同步部署。

---

## 🔧 标准操作收尾模板

```python
from pymxs import runtime as rt

with rt.undo(True, 'ArtClaw_Operation'):
    # ... 所有操作代码 ...
    pass

print("✅ 操作完成")
# 提示：可用 Ctrl+Z 撤销
```
