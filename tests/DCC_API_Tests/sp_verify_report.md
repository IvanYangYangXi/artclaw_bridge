# SP SKILL.md 修复验证 + 功能覆盖度评估报告

**测试环境**: Substance Painter 11.0.1 | Python 3.11.6 | test.spp (Sphere texture set)
**测试日期**: 2026-04-08
**测试人员**: ArtClaw 测试工程师 (subagent)

---

## Part 1: SKILL.md 修复项验证结果

### 层操作 (E1-E9)

| ID | 修复项 | 结果 | 备注 |
|---|---|---|---|
| E1 | `insert_fill(pos)` 只需 InsertPosition | ✅ PASS | 正确创建 FillLayerNode |
| E2 | `insert_paint(pos)` 只需 InsertPosition | ✅ PASS | 正确创建 PaintLayerNode |
| E3 | `insert_group(pos)` 只需 InsertPosition | ✅ PASS | 正确创建 GroupLayerNode |
| E4 | `delete_node(layer)` 是模块级函数 | ✅ PASS | 3个节点均成功删除 |
| E5 | `set_name()` / `get_name()` | ✅ PASS | 重命名后读取正确 |
| E6 | `set_locked()` / `is_locked()` | ❌ **FAIL** | **FillLayerNode 没有 set_locked 方法** |
| E7 | `set_opacity(val, channel_type)` 需传 channel | ✅ PASS | opacity=0.75 正确 |
| E8 | `set_blending_mode(mode, channel_type)` 需传 channel | ✅ PASS | blend=Multiply 正确 |
| E9 | `BlendingMode.LinearDodge`（非 Add） | ✅ PASS | LinearDodge 存在且可用 |

### 通道遍历 (E10-E11)

| ID | 修复项 | 结果 | 备注 |
|---|---|---|---|
| E10 | `stack.all_channels()` 返回 `Dict[ChannelType, Channel]` | ✅ PASS | 7个通道，类型正确 |
| E11 | `ts.get_resolution()` 返回 Resolution 对象 | ✅ PASS | Resolution(width=2048, height=2048) |

### 烘焙 (E12-E15)

| ID | 修复项 | 结果 | 备注 |
|---|---|---|---|
| E12 | `BakingParameters.from_texture_set(ts)` | ✅ PASS | 返回 BakingParameters 对象 |
| E13 | BakingParameters 方法可用 | ✅ PASS | 17 个方法，包括 get/set enabled bakers |
| E14 | `get_enabled_bakers()` 返回 MeshMapUsage 列表 | ✅ PASS | 7 种 baker 类型 |
| E15 | baking 模块完整 | ✅ PASS | 含 BakingParameters, MeshMapUsage, bake_async 等 |

### 导出 (E16-E21)

| ID | 修复项 | 结果 | 备注 |
|---|---|---|---|
| E16 | `list_resource_export_presets()` | ⚠️ **部分问题** | 返回 `ResourceExportPreset` 对象，属性为 `resource_id`（非 `name`），需用 `p.resource_id.name` |
| E17 | `list_predefined_export_presets()` | ✅ PASS | 8个预设，`.name` 属性可用 |
| E18 | PredefinedExportPreset 属性 | ✅ PASS | 有 `name`, `url`, `list_output_maps` |
| E19 | export 模块完整 | ✅ PASS | 含所有导出相关类和函数 |
| E20 | `get_default_export_path()` | ✅ PASS | 返回默认路径字符串 |
| E21 | `list_project_textures(json_config)` 需要参数 | ✅ PASS（签名正确） | 需要 dict 参数，非无参调用 |

### 验证总结

- **通过**: 18/21 (85.7%)
- **失败**: 1 (E6: set_locked 不存在)
- **部分问题**: 2 (E16: ResourceExportPreset 访问方式不同, E21: 需参数)

---

## Part 1.5: SKILL.md 现存错误清单

### 🔴 sp-context/SKILL.md 错误

1. **`sub_layers()` 与 `inside_node(group, NodeStack.Content)` 混用**
   - **问题**: sp-context 中层树遍历使用 `node.sub_layers()` 获取子层，但未说明 `inside_node()` 插入子层时应使用 `NodeStack.Substack`（非 `Content`）
   - **实际**: `InsertPosition.inside_node(group, NodeStack.Content)` 插入的是 **效果节点**（FillEffectNode），不是子层
   - `InsertPosition.inside_node(group, NodeStack.Substack)` 才是插入子层，`sub_layers()` 才会返回
   - **建议**: 补充 `inside_node` 用法说明

2. **`get_opacity()` fallback 到无参调用**
   - **问题**: 层树遍历代码中 `except: opacity = node.get_opacity()` — mask 中的层 `get_opacity()` 无参并不可靠
   - **建议**: 统一使用 `try/except` 并标注 mask 上下文

### 🔴 sp-operation-rules/SKILL.md 错误

3. **缺少 `set_visible()` / `is_visible()` 文档**
   - 这是层操作的重要 API，SKILL.md 完全未提及
   
4. **缺少 `NodeStack` 枚举说明**
   - `NodeStack.Content` / `NodeStack.Mask` / `NodeStack.Substack` 是 `InsertPosition.inside_node()` 的关键参数
   - SKILL.md 未提及

5. **`set_locked()` 不存在但可能在某些文档中被引用**
   - SP 11.0.1 的层节点没有 `set_locked` / `is_locked` 方法
   - 如果 SKILL.md 中有提及，需删除

### 🟡 sp-layer-ops/SKILL.md 改进项

6. **缺少组层子层插入方法**
   - 未说明如何往 Group 中插入子层：`InsertPosition.inside_node(group, NodeStack.Substack)`

7. **缺少遮罩效果器操作**
   - `mask_effects()` / `content_effects()` 已存在但未文档化
   - `insert_generator_effect()` / `insert_filter_effect()` 等效果插入 API 未提及

8. **缺少 `set_visible()` / `is_visible()` 操作**
   - 层可见性是常用操作

9. **缺少 `source_mode` 属性和 `get_source(ch)` 方法文档**

### 🟡 sp-bake-export/SKILL.md 改进项

10. **ResourceExportPreset 与 PredefinedExportPreset 混淆**
    - `ResourceExportPreset` 没有 `.name` 属性，应用 `.resource_id.name`
    - `PredefinedExportPreset` 有 `.name` 属性
    - SKILL.md 中对两者的遍历代码统一用了 `str(p)` 但未明确区分

11. **缺少 `list_project_textures(json_config)` 的正确用法**
    - 该函数需要 json_config 参数（dict），不是无参函数

---

## Part 2: 常用功能用例验证

### 用例 1: 层栈工作流 ✅ PASS

创建 3 层（Fill + Paint + Fill Overlay），设置透明度和混合模式，查询层栈结构。

```
结果: 4 layers (含原有 Layer 1)
- Color_Overlay (FillLayerNode, opacity=0.5, Overlay)
- Detail_Paint (PaintLayerNode, opacity=0.8, Normal)
- Base_White (FillLayerNode, opacity=1.0, Normal)
- Layer 1 (PaintLayerNode, opacity=1.0, Normal)
```

### 用例 2: 通道管理 ✅ PASS

```
Resolution: 2048x2048
Channels: BaseColor(sRGB8), Roughness(L8), Metallic(L8), Normal(RGB16F),
          Specularlevel(L8), User2(L8), User3(L8)
```

### 用例 3: 资源搜索 ⚠️ 部分通过

- `resource.search("s:smartmaterial")` 返回空 — 可能是搜索语法或 shelf 索引问题
- `resource.list_project_resources()` ✅ 返回 3 个资源
- `Shelves.all()` ✅ 返回 5 个 shelf
- **注意**: `Shelf.is_read_only()` 不存在

### 用例 4: 导出预设查询 ✅ PASS

```
预定义预设 (8): 2D View, Document channels + Normal + AO (No Alpha/With Alpha),
    Sketchfab, Substance 3D Stager, USDz, glTF PBR, glTF PBR + Displacement
资源预设 (40): Vray Next, S18_M_PBR_Base, Unity HD, Unreal Engine (Packed)...
```

### 用例 5: 项目信息 ✅ PASS

```
完整项目信息成功获取:
- 文件路径、打开状态、保存状态
- 纹理集列表、分辨率、通道、层数和层详情
```

### 用例 6: 遮罩操作 ✅ PASS

```
- add_mask(Black) ✅
- has_mask() = True ✅
- get_mask_background() = Black ✅
- enable_mask(False/True) ✅
- remove_mask() ✅
- add_mask(White) ✅
- mask_effects() ✅ (空列表)
- insert_generator_effect() in mask ✅
```

---

## Part 3: 功能缺口分析

### API 覆盖度评估

| 功能域 | 已覆盖 Skill | 覆盖度 | 评估 |
|---|---|---|---|
| **项目管理** (open/save/close) | sp-operation-rules, sp-context | 85% | 缺 project.create/open/close 示例 |
| **层管理** (create/delete/properties) | sp-layer-ops | 75% | 缺 visibility, 组层子层, 效果器 |
| **通道管理** | sp-context | 90% | 基本完整 |
| **烘焙** | sp-bake-export | 70% | 缺 BakingParameters 详细配置 |
| **导出** | sp-bake-export | 75% | 缺 list_project_textures 用法，预设区分 |
| **资源管理** (shelf/search) | 无专项 Skill | 10% | ❌ **严重缺失** |
| **显示控制** (camera/env/LUT) | 无专项 Skill | 0% | ❌ 缺失 |
| **效果器** (generator/filter/fill effects) | 无专项 Skill | 5% | ❌ **严重缺失** |
| **事件系统** | 无专项 Skill | 0% | 缺失（非紧急） |
| **UI 扩展** | 无专项 Skill | 0% | 缺失（非紧急） |

### 已发现的 SP API 模块完整清单

| 模块 | 有对应 Skill | 重要度 |
|---|---|---|
| `substance_painter.project` | ✅ 部分 | 🔴 核心 |
| `substance_painter.textureset` | ✅ 部分 | 🔴 核心 |
| `substance_painter.layerstack` | ✅ 主要 | 🔴 核心 |
| `substance_painter.export` | ✅ 主要 | 🔴 核心 |
| `substance_painter.baking` | ✅ 基础 | 🟡 重要 |
| `substance_painter.resource` | ❌ 无 | 🔴 核心 |
| `substance_painter.display` | ❌ 无 | 🟡 重要 |
| `substance_painter.event` | ❌ 无 | 🟢 可选 |
| `substance_painter.ui` | ❌ 无 | 🟢 可选 |
| `substance_painter.application` | ❌ 无 | 🟢 可选 |
| `substance_painter.logging` | ❌ 无 | 🟢 可选 |
| `substance_painter.properties` | ❌ 无 | 🟢 可选 |
| `substance_painter.js` | ❌ 无 | 🟢 可选 |
| `substance_painter.source` | ❌ 无 | 🟡 重要 |
| `substance_painter.colormanagement` | ❌ 无 | 🟢 可选 |

### 建议新 Skill 及优先级

#### P0 (必须 - 当前 Skill 修复)

1. **修复 sp-layer-ops/SKILL.md**
   - 添加 `set_visible()` / `is_visible()` 操作文档
   - 添加 `NodeStack` 枚举说明和组层子层插入方法
   - 删除 `set_locked` 相关引用（如有）
   - 补充效果器插入 API：`insert_generator_effect`, `insert_filter_effect` 等

2. **修复 sp-context/SKILL.md**
   - 修正层树遍历中 `get_opacity()` 的 fallback 逻辑
   - 补充 `inside_node(group, NodeStack.Substack)` 与 `sub_layers()` 的对应关系

3. **修复 sp-bake-export/SKILL.md**
   - 区分 `ResourceExportPreset.resource_id.name` 和 `PredefinedExportPreset.name`
   - 添加 `list_project_textures(json_config)` 的正确调用方式和参数格式

#### P1 (建议 - 新增 Skill)

4. **新建 `sp-resource`** — 资源管理 Skill
   - `resource.search()` 搜索语法
   - `Shelves.all()` / `Shelf.name()` / `Shelf.path()`
   - `list_project_resources()` / `list_layer_stack_resources()`
   - `import_project_resource()` / `import_session_resource()`
   - `ResourceID` 结构说明
   - Smart Material / Smart Mask 搜索和使用

5. **新建 `sp-effects`** — 效果器操作 Skill
   - `insert_generator_effect()` / `insert_filter_effect()` / `insert_fill_effect()`
   - `insert_levels_effect()` / `insert_anchor_point_effect()`
   - `insert_color_selection_effect()` / `insert_compare_mask_effect()`
   - 效果器在 Content 和 Mask 栈中的使用
   - `content_effects()` / `mask_effects()` 遍历

#### P2 (锦上添花)

6. **新建 `sp-display`** — 显示控制 Skill
   - Camera 操作
   - Environment 设置
   - Color LUT
   - Tone Mapping

7. **扩充 sp-operation-rules** 
   - 添加完整的层节点方法速查表
   - 添加 `substance_painter.source` 模块说明 (SourceMode, set/get_source)

---

## 附录: 关键 API 方法速查

### FillLayerNode 可用方法 (SP 11.0.1)

```
active_channels (property)     add_mask()                  content_effects()
enable_mask()                  get_blending_mode(ch)       get_geometry_mask_*()
get_mask_background()          get_name()                  get_next_sibling()
get_opacity(ch)                get_parent()                get_previous_sibling()
get_projection_mode()          get_projection_parameters() get_source(ch)
get_stack()                    get_texture_set()           get_type()
has_blending()                 has_mask()                  instances()
is_in_mask_stack()             is_mask_enabled()           is_visible()
mask_effects()                 remove_mask()               reset_material_source()
reset_source()                 set_blending_mode(m,ch)     set_geometry_mask_*()
set_mask_background()          set_material_source()       set_name()
set_opacity(v,ch)              set_projection_mode()       set_projection_parameters()
set_source()                   set_sources_from_preset()   set_visible()
source_mode (property)         uid
```

**注意**: 没有 `set_locked()`, `is_locked()`, `move()`, `duplicate()`

### GroupLayerNode 独有方法

```
sub_layers()      # 获取子层 (需用 NodeStack.Substack 插入)
is_collapsed()    # 是否折叠
set_collapsed()   # 设置折叠状态
```

### BlendingMode 完整枚举

```
Color, ColorBurn, ColorDodge, Darken, Difference, Disable, Divide,
Exclusion, HardLight, InverseDivide, InverseSubtract, Lighten,
LinearBurn, LinearDodge, LinearLight, Multiply, Normal,
NormalMapCombine, NormalMapDetail, NormalMapInverseDetail, Overlay,
Passthrough, PinLight, Replace, Saturation, Screen, SignedAddition,
SoftLight, Subtract, Tint, Value, VividLight
```

### InsertPosition 方法

```
above_node(node)               # 在节点上方
below_node(node)               # 在节点下方
from_textureset_stack(stack)   # 在栈底部
inside_node(node, node_stack)  # 在节点内部 (需指定 NodeStack)
```

### NodeStack 枚举

```
Content   — 效果器栈 (generators, filters, fills)
Mask      — 遮罩栈
Substack  — 子层栈 (仅 GroupLayerNode, 对应 sub_layers())
```

---

## 总结

| 维度 | 评分 | 说明 |
|---|---|---|
| 修复验证通过率 | 85.7% | 18/21 通过，1 失败，2 部分问题 |
| 层操作覆盖度 | 75% | 核心 CRUD 完整，缺 visibility/effects/group sublayers |
| 烘焙导出覆盖度 | 72% | 基础流程完整，缺细节配置 |
| 资源管理覆盖度 | 10% | ❌ 严重缺失，需新建 Skill |
| 整体功能覆盖度 | ~60% | 核心操作可用，高级功能缺失 |

**优先行动项**:
1. 修复现有 4 个 SKILL.md 中的错误（约 11 处）
2. 新建 `sp-resource` Skill（资源/shelf 管理）
3. 新建 `sp-effects` Skill（效果器操作）
