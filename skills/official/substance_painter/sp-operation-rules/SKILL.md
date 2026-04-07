---
name: sp-operation-rules
description: >
  Substance Painter 操作通用规则和最佳实践。所有涉及 SP 场景修改的操作都必须遵守。
  AI 在执行任何 Substance Painter 操作任务前应先读取此 Skill。
  包含：API 模块、项目状态检查、无 Undo 注意事项、层操作核心、纹理集、导出烘焙等规则。
  Use when AI needs to: (1) perform any Substance Painter operation,
  (2) check SP best practices, (3) understand SP API structure,
  (4) ensure safe operations without undo support.
  Substance Painter only (run_python).
metadata:
  artclaw:
    author: ArtClaw
    software: substance_painter
---

# SP 操作通用规则

所有涉及 Substance Painter 场景修改的操作都必须遵守以下规则。

> ⚠️ **仅适用于 Substance Painter** — 通过 `run_python` 执行

---

## 📦 规则 0：API 模块

SP Python API 模块为 `substance_painter`，**不是** `sp`。

核心子模块：

| 子模块 | 用途 |
|---|---|
| `substance_painter.project` | 项目管理（打开/保存/关闭） |
| `substance_painter.textureset` | 纹理集管理 |
| `substance_painter.layerstack` | 层栈操作（核心） |
| `substance_painter.export` | 纹理导出 |
| `substance_painter.baking` | 贴图烘焙 |

```python
# ✅ 正确导入
import substance_painter.project
import substance_painter.textureset
import substance_painter.layerstack

# ❌ 错误 — 不要用缩写
import substance_painter as sp  # 导入本身可以，但代码中应使用完整模块路径
```

---

## ✅ 规则 1：项目状态检查（强制）

**每次操作前必须检查项目是否已打开。** 未打开项目时大部分 API 调用会抛出异常。

```python
import substance_painter.project

if not substance_painter.project.is_open():
    print("❌ 错误：没有打开的项目，请先打开一个 SP 项目")
else:
    # ... 安全执行操作 ...
    pass
```

### 获取项目路径

```python
import substance_painter.project

if substance_painter.project.is_open():
    file_path = substance_painter.project.file_path()
    print(f"当前项目: {file_path}")
```

---

## ⚠️ 规则 2：无 Undo API — 破坏性操作须谨慎

SP Python API **不支持 undo group 或撤销管理**。一旦执行，无法通过 API 回滚。

### 强制要求

1. **破坏性操作前保存项目**：
```python
import substance_painter.project

# 在删除层、批量修改等操作前先保存
substance_painter.project.save()
print("✅ 项目已保存，准备执行操作")
```

2. **破坏性操作前向用户确认**，包括：
   - 删除层 / 删除层组
   - 批量修改层属性
   - 清空层栈
   - 覆盖导出文件

3. **非破坏性操作可直接执行**（查询信息、添加层、调整参数等）

---

## 🎨 规则 3：层操作核心

SP 的核心工作流围绕 **层（Layer）** 管理。

### 层栈获取

```python
import substance_painter.textureset
import substance_painter.layerstack

# 获取第一个纹理集
ts = substance_painter.textureset.all_texture_sets()[0]
stack = substance_painter.textureset.Stack.from_name(ts.name())

# 获取根层节点列表
root_layers = substance_painter.layerstack.get_root_layer_nodes(stack)
for layer in root_layers:
    print(f"  {layer.get_name()} ({type(layer).__name__})")
```

### 层类型

| 类型 | 说明 |
|---|---|
| `FillLayer` | 填充层 — 用纯色/材质填充 |
| `PaintLayer` | 绘画层 — 手绘笔刷内容 |
| `GroupLayer` | 组层 — 用于组织层结构 |

### 常用层操作

- **添加层**: `substance_painter.layerstack.insert_layer(...)`
- **删除层**: `layer_node.delete()`
- **移动层**: `layer_node.move(...)` 
- **复制层**: `layer_node.duplicate()`
- **设置透明度**: `layer_node.set_opacity(0.5)`
- **设置混合模式**: `layer_node.set_blending_mode(...)`

---

## 🗺️ 规则 4：纹理集（Texture Set）

SP 中每个 mesh/材质对应一个 **Texture Set**。

```python
import substance_painter.textureset

# 获取所有纹理集
all_ts = substance_painter.textureset.all_texture_sets()
for ts in all_ts:
    print(f"纹理集: {ts.name()}")
```

### 常用通道

| 通道 | 说明 |
|---|---|
| `BaseColor` | 基础颜色 |
| `Height` | 高度 |
| `Roughness` | 粗糙度 |
| `Metallic` | 金属度 |
| `Normal` | 法线 |
| `AmbientOcclusion` | 环境光遮蔽 |

---

## 📤 规则 5：导出与烘焙

### 纹理导出

```python
import substance_painter.export

# 使用导出预设导出纹理
config = substance_painter.export.get_default_export_config()
substance_painter.export.export_project_textures(config)
```

### 贴图烘焙

```python
import substance_painter.baking

# 烘焙所有纹理集的贴图
substance_painter.baking.bake_all_texture_sets()
```

---

## 🧠 规则 6：记忆系统集成

### 反复出错时主动查记忆（强制）

当同一类操作 **连续失败 2 次以上** 时，必须先搜索记忆再继续尝试：

```python
from core.memory_store import get_memory_store
mm = get_memory_store()
if mm:
    hints = mm.manager.search("相关关键词", tag="crash", limit=3)
    hints += mm.manager.search("相关关键词", tag="pattern", limit=3)
    team = mm.manager.search_team_memory("相关关键词", limit=3)
    # 根据找到的规则调整方案
```

### 多次尝试后成功时提炼教训（强制）

经过 2 次以上尝试或用户纠正后才正确完成操作时，**必须** 提炼规则并写入记忆：

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

## 📋 标准操作收尾模板

```python
import substance_painter.project

if not substance_painter.project.is_open():
    print("❌ 错误：没有打开的项目")
else:
    # === 操作代码 ===
    # ... 在这里写业务逻辑 ...

    # === 收尾 ===
    print("✅ 操作完成")
```

> **注意**: SP 不像 UE 需要手动刷新视口，UI 会自动更新。
> **注意**: SP 没有 Ctrl+Z 的 API 接口，用户可在 SP GUI 中手动 Ctrl+Z 撤销单步操作。
