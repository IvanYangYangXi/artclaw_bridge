# ArtClaw Actor 高亮与定位

在 UE 编辑器中高亮、选中、聚焦指定 Actor，快速定位场景中的对象。

> **覆盖原 MCP 工具**: `highlight_actors`（仅 UE）
>
> ⚠️ **仅适用于 Unreal Engine** — Maya/Max 没有等效的视口高亮 API

## 调用方式

通过 MCP 工具 `run_ue_python` 执行 Python 代码实现 Actor 的选中与聚焦。

---

## 基础操作

### 按名称查找并选中 Actor

```python
import unreal

target_name = "BP_Enemy_01"

all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
found = [a for a in all_actors if a.get_name() == target_name]

if found:
    unreal.EditorLevelLibrary.set_selected_level_actors(found)
    print(f"已选中: {target_name}")
else:
    print(f"未找到: {target_name}")
```

### 选中并聚焦（视口飞向目标）

```python
import unreal

target_name = "BP_Enemy_01"

all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
found = [a for a in all_actors if a.get_name() == target_name]

if found:
    actor = found[0]
    # 选中
    unreal.EditorLevelLibrary.set_selected_level_actors([actor])
    # 聚焦视口到该 Actor（等效于编辑器中按 F 键）
    unreal.EditorLevelUtils.pilot_level_actor(actor)
    print(f"已聚焦到: {target_name}")
```

### 模糊搜索并高亮

```python
import unreal

keyword = "Enemy"

all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
matched = [a for a in all_actors if keyword.lower() in a.get_name().lower()]

if matched:
    unreal.EditorLevelLibrary.set_selected_level_actors(matched)
    print(f"找到并选中 {len(matched)} 个包含 '{keyword}' 的 Actor:")
    for a in matched:
        print(f"  - {a.get_name()}")
else:
    print(f"未找到包含 '{keyword}' 的 Actor")
```

---

## 高级操作

### 按类型查找并高亮

```python
import unreal

# 选中所有 StaticMeshActor
all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
static_meshes = [a for a in all_actors if a.get_class().get_name() == "StaticMeshActor"]

unreal.EditorLevelLibrary.set_selected_level_actors(static_meshes)
print(f"已选中 {len(static_meshes)} 个 StaticMeshActor")
```

### 按标签查找

```python
import unreal

tag = "Interactive"

all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
tagged = [a for a in all_actors if tag in [str(t) for t in a.tags]]

if tagged:
    unreal.EditorLevelLibrary.set_selected_level_actors(tagged)
    print(f"已选中 {len(tagged)} 个带有 '{tag}' 标签的 Actor")
```

### 聚焦后恢复视口（取消 Pilot）

```python
import unreal

# 取消视口 Pilot 模式，恢复自由视角
unreal.EditorLevelUtils.eject_pilot_level_actor()
```

---

## 使用建议

- **简单定位**: 按名称查找 + `set_selected_level_actors` + `pilot_level_actor` 三步走
- **批量高亮**: 用模糊搜索或类型过滤选中多个 Actor，在编辑器 Outliner 中也会同步高亮
- **聚焦后记得恢复**: 使用 `pilot_level_actor` 后视口会锁定到 Actor，操作完用 `eject_pilot_level_actor()` 恢复
- 此功能仅限 UE，Maya/Max 中如需定位对象，请使用 `artclaw-context` Skill 查询后手动操作
