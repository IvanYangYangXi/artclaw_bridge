# Substance Painter API 测试报告

- **测试时间**: 2026-04-07 23:15 GMT+8
- **SP 版本**: 11.0.1
- **Python 版本**: 3.11.6
- **MCP 工具**: `mcp_sp-editor_run_python`
- **测试项目**: test.spp (Sphere texture set, 2048x2048)

---

## 测试结果汇总

| 类别 | 总数 | 通过 | 失败 | 通过率 |
|---|---|---|---|---|
| 1. 上下文采集 | 4 | 4 | 0 | 100% |
| 2. 项目操作 | 5 | 5 | 0 | 100% |
| 3. 层操作 | 9 | 6 | 3 | 67% |
| 4. 通道操作 | 2 | 2 | 0 | 100% |
| 5. 材质/资源操作 | 3 | 3 | 0 | 100% |
| 6. 导出操作 | 3 | 3 | 0 | 100% |
| 7. 烘焙操作 | 3 | 3 | 0 | 100% |
| **总计** | **29** | **26** | **3** | **90%** |

> 注：功能本身全部可用，3 个"失败"指 SP Python API 不提供该功能（move/duplicate），属于 API 限制。

---

## 1. 上下文采集

| # | 测试 | 结果 | 说明 |
|---|---|---|---|
| 1.1 | get_context | ✅ PASS | 正确返回 software="substance_painter", version="11.0.1", python="3.11.6" |
| 1.2 | S 变量 | ✅ PASS | `S` = `[TextureSet(material_id=783)]`，类型 `list`，包含所有 texture set |
| 1.3 | W 变量 | ✅ PASS | `W` = 项目路径字符串 |
| 1.4 | L 变量 | ✅ PASS | `L` = `substance_painter` 模块，所有核心子模块可导入 |

---

## 2. 项目操作

| # | 测试 | 结果 | 说明 |
|---|---|---|---|
| 2.1 | `project.is_open()` | ✅ PASS | 返回 `True` |
| 2.2 | `project.file_path()` | ✅ PASS | 返回完整路径 |
| 2.3 | `textureset.all_texture_sets()` | ✅ PASS | 返回 1 个 TextureSet，名称 "Sphere" |
| 2.4 | Texture Set 分辨率 | ✅ PASS | `ts.get_resolution()` 返回 `Resolution(width=2048, height=2048)`，有 `.width`/`.height` 属性 |
| 2.5 | `project.needs_saving()` | ✅ PASS | 返回 `False` |

---

## 3. 层操作

| # | 测试 | 结果 | 说明 |
|---|---|---|---|
| 3.1 | 列出层 | ✅ PASS | `get_root_layer_nodes(stack)` 正常，返回 `PaintLayerNode` 列表 |
| 3.2 | 创建填充层 | ✅ PASS | `insert_fill(pos)` 成功创建 `FillLayerNode` |
| 3.3 | 创建绘画层 | ✅ PASS | `insert_paint(pos)` 成功创建 `PaintLayerNode` |
| 3.4 | 创建组层 | ✅ PASS | `insert_group(pos)` 成功创建 `GroupLayerNode` |
| 3.5 | 设置层属性 | ✅ PASS | `set_visible`/`is_visible`/`set_opacity`/`set_blending_mode` 全部正常（需传 channel 参数） |
| 3.6 | 删除层 | ✅ PASS | `delete_node(layer)` 成功删除 |
| 3.7 | 移动层 | ❌ FAIL | **Node 没有 `move()` 方法**，SP Python API 不支持层移动 |
| 3.8 | 复制层 | ❌ FAIL | **Node 没有 `duplicate()` 方法**，SP Python API 不支持层复制 |
| 3.9 | 遮罩操作 | ✅ PASS | `add_mask(MaskBackground.Black)`/`remove_mask()`/`has_mask()` 全部正常 |

### 3.7/3.8 详细说明

SP 11.0.1 的 Python API 中 `Node`/`LayerNode` 类没有 `move()` 和 `duplicate()` 方法。已确认 `dir()` 中不存在这两个方法。

**可用的替代方案**：
- 移动：无直接 API，只能通过删除 + 重新创建模拟
- 复制：无直接 API

---

## 4. 通道操作

| # | 测试 | 结果 | 说明 |
|---|---|---|---|
| 4.1 | 获取通道列表 | ✅ PASS | `stack.all_channels()` 返回 `Dict[ChannelType, Channel]`，7 个通道 |
| 4.2 | 通道类型 | ✅ PASS | BaseColor, Roughness, Metallic, Normal, Specularlevel, User2, User3 |

---

## 5. 材质/资源操作

| # | 测试 | 结果 | 说明 |
|---|---|---|---|
| 5.1 | 搜索资源 | ✅ PASS | `resource.search("smart material")` 返回 159 个结果 |
| 5.2 | 列出 Shelf | ✅ PASS | `Shelves.all()` 返回 5 个 shelf |
| 5.3 | 资源类型枚举 | ✅ PASS | `resource.Type` 包含 SMART_MATERIAL, SMART_MASK 等 14 种类型 |

---

## 6. 导出操作

| # | 测试 | 结果 | 说明 |
|---|---|---|---|
| 6.1 | 列出导出预设 | ✅ PASS | `list_resource_export_presets()` 返回 40 个, `list_predefined_export_presets()` 返回 8 个 |
| 6.2 | 默认导出路径 | ✅ PASS | `get_default_export_path()` 正常返回 |
| 6.3 | 导出状态枚举 | ✅ PASS | `ExportStatus` 有 Success, Error, Warning, Cancelled |

---

## 7. 烘焙操作

| # | 测试 | 结果 | 说明 |
|---|---|---|---|
| 7.1 | 获取烘焙参数 | ✅ PASS | `BakingParameters.from_texture_set(ts)` 返回参数对象 |
| 7.2 | MeshMap 类型 | ✅ PASS | 10 种：AO, BentNormals, Curvature, Height, ID, Normal, Opacity, Position, Thickness, WorldSpaceNormal |
| 7.3 | 烘焙 API | ✅ PASS | `bake_async(ts)` 和 `bake_selected_textures_async()` 可用 |

---

## 🚨 SKILL.md API 错误（重点）

### sp-layer-ops/SKILL.md 错误

| # | 错误描述 | SKILL.md 写法 | 正确 API | 严重度 |
|---|---|---|---|---|
| **E1** | 函数名错误：插入填充层 | `insert_fill_layer(stack, pos)` | `insert_fill(pos)` — 只接受 InsertPosition 参数，不需要 stack | 🔴 **致命** |
| **E2** | 函数名错误：插入绘画层 | `insert_paint_layer(stack, pos)` | `insert_paint(pos)` | 🔴 **致命** |
| **E3** | 函数名错误：插入组层 | `insert_group_layer(stack, pos)` | `insert_group(pos)` | 🔴 **致命** |
| **E4** | 函数名错误：删除层 | `layer.delete()` | `substance_painter.layerstack.delete_node(layer)` — 是模块级函数，不是实例方法 | 🔴 **致命** |
| **E5** | 方法不存在：移动层 | `layer.move(pos)` | ❌ **SP API 不支持**，该方法不存在 | 🟠 **高** |
| **E6** | 方法不存在：复制层 | `layer.duplicate()` | ❌ **SP API 不支持**，该方法不存在 | 🟠 **高** |
| **E7** | 参数缺失：透明度 | `layer.set_opacity(0.75)` | `layer.set_opacity(0.75, channel_type)` — 非 mask 层**必须**传 channel 参数 | 🔴 **致命** |
| **E8** | 参数缺失：混合模式 | `layer.set_blending_mode(BlendingMode.Multiply)` | `layer.set_blending_mode(BlendingMode.Multiply, channel_type)` — 非 mask 层**必须**传 channel 参数 | 🔴 **致命** |
| **E9** | 枚举值不存在 | `BlendingMode.Add` | ❌ 不存在。正确为 `BlendingMode.LinearDodge`（线性减淡/Add） | 🟠 **高** |

### sp-context/SKILL.md 错误

| # | 错误描述 | SKILL.md 写法 | 正确 API | 严重度 |
|---|---|---|---|---|
| **E10** | 通道遍历方式错误 | `for ch in channels: ch.type().name` | `all_channels()` 返回 `Dict[ChannelType, Channel]`，应用 `for ct, ch in channels.items(): ct.name` | 🔴 **致命** |
| **E11** | 层遍历透明度调用错误 | `node.get_opacity()` 不带参数 | 非 mask 层需要 `node.get_opacity(channel_type)` | 🟠 **高** |

### sp-bake-export/SKILL.md 错误

| # | 错误描述 | SKILL.md 写法 | 正确 API | 严重度 |
|---|---|---|---|---|
| **E12** | 函数不存在：全部烘焙 | `baking.bake_all_texture_sets()` | `baking.bake_selected_textures_async()` — 返回 StopSource | 🔴 **致命** |
| **E13** | 函数不存在：单个烘焙 | `baking.bake(ts)` | `baking.bake_async(texture_set)` — 返回 StopSource | 🔴 **致命** |
| **E14** | 函数不存在：获取烘焙参数 | `baking.get_baking_parameters()` | `baking.BakingParameters.from_texture_set(ts)` — 是类方法 | 🔴 **致命** |
| **E15** | 函数不存在：设置烘焙参数 | `baking.set_baking_parameters(params)` | 通过 `BakingParameters` 对象的 `.set()` 方法 | 🔴 **致命** |
| **E16** | 函数不存在：获取默认导出配置 | `export.get_default_export_config()` | ❌ 不存在。导出使用 `export_project_textures(json_config: dict)` | 🔴 **致命** |
| **E17** | 类不存在：导出配置 | `export.ExportConfig` | ❌ 不存在。使用 dict 格式 json_config | 🔴 **致命** |
| **E18** | 类不存在：导出格式枚举 | `export.ExportFormat.PNG` 等 | ❌ 不存在。格式在 json_config 中指定 | 🔴 **致命** |
| **E19** | 方法不存在 | `export.ResourceExportPreset.from_name("...")` | ❌ 不存在。使用 `list_resource_export_presets()` 按名称过滤 | 🔴 **致命** |
| **E20** | 函数名错误 | `export.list_export_presets()` | `export.list_resource_export_presets()` 或 `export.list_predefined_export_presets()` | 🔴 **致命** |
| **E21** | 导出结果访问错误 | `result.textures` 当作列表遍历 | `result.textures` 是 `Dict[Tuple[str,str], List[str]]`，按 (TextureSet, Stack) 分组 | 🟠 **高** |

### sp-operation-rules/SKILL.md 错误

| # | 错误描述 | SKILL.md 写法 | 正确 API | 严重度 |
|---|---|---|---|---|
| **E22** | 层操作 API 名称错误 | "添加层: `insert_layer(...)`" | 实际为 `insert_fill(pos)` / `insert_paint(pos)` / `insert_group(pos)` | 🟠 **高** |

---

## 错误统计

| 严重度 | 数量 |
|---|---|
| 🔴 致命（API 调用会直接报错） | 16 |
| 🟠 高（功能缺失或行为不符） | 6 |
| **总计** | **22** |

---

## 正确 API 参考（修复指南）

### 层操作正确用法

```python
import substance_painter.textureset
import substance_painter.layerstack as ls

ts = substance_painter.textureset.all_texture_sets()[0]
stack = substance_painter.textureset.Stack.from_name(ts.name())
root_layers = ls.get_root_layer_nodes(stack)

# 插入填充层（只需 InsertPosition，不需要 stack）
pos = ls.InsertPosition.above_node(root_layers[-1])
fill = ls.insert_fill(pos)
fill.set_name("MyFill")

# 插入绘画层
paint = ls.insert_paint(pos)

# 插入组层
group = ls.insert_group(pos)

# 在空层栈中插入（使用 from_textureset_stack）
pos = ls.InsertPosition.from_textureset_stack(stack)
fill = ls.insert_fill(pos)

# 删除层（模块级函数，非实例方法）
ls.delete_node(fill)

# 设置透明度（必须传 channel 参数）
ch = substance_painter.textureset.ChannelType.BaseColor
fill.set_opacity(0.75, ch)
fill.set_blending_mode(ls.BlendingMode.Multiply, ch)

# 获取透明度（必须传 channel 参数）
opacity = fill.get_opacity(ch)
blend = fill.get_blending_mode(ch)
```

### 通道遍历正确用法

```python
# all_channels() 返回 Dict[ChannelType, Channel]，不是列表
channels = stack.all_channels()
for channel_type, channel in channels.items():
    print(f"Channel: {channel_type.name}")
```

### 烘焙正确用法

```python
import substance_painter.baking

# 获取烘焙参数（类方法，非模块函数）
params = substance_painter.baking.BakingParameters.from_texture_set(ts)

# 获取 common 参数
common = params.common()  # 返回 dict
output_size = common['OutputSize']

# 烘焙（异步，非同步）
stop = substance_painter.baking.bake_async(ts)  # 单个纹理集
stop = substance_painter.baking.bake_selected_textures_async()  # 所有已启用的
```

### 导出正确用法

```python
import substance_painter.export

# 列出预设
resource_presets = substance_painter.export.list_resource_export_presets()
predefined_presets = substance_painter.export.list_predefined_export_presets()

# 导出使用 json_config dict（不是 ExportConfig 对象）
# 参考 SP 官方文档获取 json_config 格式
result = substance_painter.export.export_project_textures(json_config)

# 结果的 textures 是 Dict[Tuple[str,str], List[str]]
for (ts_name, stack_name), files in result.textures.items():
    for f in files:
        print(f)
```

---

## Adapter 预注入变量评估

| 变量 | 类型 | 内容 | 评价 |
|---|---|---|---|
| `S` | `list[TextureSet]` | 所有纹理集列表 | ✅ 合理，类似选中对象 |
| `W` | `str` | 项目文件路径 | ✅ 合理，对应场景文件 |
| `L` | `module` | `substance_painter` 模块 | ✅ 合理，方便快速导入 |

**建议补充**：
- 无需额外变量，当前 S/W/L 已覆盖核心需求
- `get_context` 返回的 `scene_info` 结构合理且信息完整

---

## BlendingMode 完整参考

实际可用的 `BlendingMode` 枚举值（32 种）：

| 混合模式 | 枚举名 | 备注 |
|---|---|---|
| Normal | `Normal` | 默认 |
| Multiply | `Multiply` | 正片叠底 |
| Screen | `Screen` | 滤色 |
| Overlay | `Overlay` | 叠加 |
| Linear Dodge | `LinearDodge` | 线性减淡 (= Add) |
| Subtract | `Subtract` | 减去 |
| Color Burn | `ColorBurn` | 颜色加深 |
| Color Dodge | `ColorDodge` | 颜色减淡 |
| Darken | `Darken` | 变暗 |
| Difference | `Difference` | 差值 |
| Disable | `Disable` | 禁用 |
| Divide | `Divide` | 划分 |
| Exclusion | `Exclusion` | 排除 |
| Hard Light | `HardLight` | 强光 |
| Inverse Divide | `InverseDivide` | 反向划分 |
| Inverse Subtract | `InverseSubtract` | 反向减去 |
| Lighten | `Lighten` | 变亮 |
| Linear Burn | `LinearBurn` | 线性加深 |
| Linear Light | `LinearLight` | 线性光 |
| Normal Map Combine | `NormalMapCombine` | 法线合并 |
| Normal Map Detail | `NormalMapDetail` | 法线细节 |
| Normal Map Inverse Detail | `NormalMapInverseDetail` | 法线反向细节 |
| Passthrough | `Passthrough` | 直通（组层用） |
| Pin Light | `PinLight` | 点光 |
| Replace | `Replace` | 替换 |
| Saturation | `Saturation` | 饱和度 |
| Signed Addition | `SignedAddition` | 有符号加法 |
| Soft Light | `SoftLight` | 柔光 |
| Tint | `Tint` | 着色 |
| Value | `Value` | 明度 |
| Vivid Light | `VividLight` | 鲜明光 |
| Color | `Color` | 颜色 |

---

## 建议补充的 Skill / API

### 1. sp-resource-ops（新 Skill 建议）
- **内容**：Shelf 管理、资源搜索、导入、Smart Material/Mask 应用
- **API**：
  - `resource.search(query)` — 搜索资源
  - `resource.Shelves.all()` — 列出所有 shelf
  - `resource.import_project_resource()` — 导入资源
  - `layerstack.insert_smart_material(pos, resource_id)` — 应用 Smart Material
  - `layerstack.insert_smart_mask(pos, resource_id)` — 应用 Smart Mask

### 2. sp-display-ops（新 Skill 建议）
- **内容**：视口显示设置、相机控制、环境/色调映射
- **API**：
  - `display.Camera` — 相机控制
  - `display.get/set_environment_resource()` — 环境贴图
  - `display.get/set_tone_mapping()` — 色调映射
  - `display.get/set_color_lut_resource()` — 颜色 LUT

### 3. 补充到现有 Skill
- **sp-layer-ops**：添加 Effect 节点操作（`insert_filter_effect`, `insert_generator_effect`, `insert_fill` 等 effect 用法）
- **sp-context**：添加 `resource.search()` 查询资源的方法
- **sp-operation-rules**：添加 `substance_painter.logging` 模块说明（`log`, `info`, `warning`, `error`）

---

## SP Python API 模块总览

| 模块 | 用途 | Skill 覆盖 |
|---|---|---|
| `substance_painter.project` | 项目管理 | ✅ sp-operation-rules |
| `substance_painter.textureset` | 纹理集 | ✅ sp-context |
| `substance_painter.layerstack` | 层栈操作 | ✅ sp-layer-ops（有误） |
| `substance_painter.export` | 导出 | ✅ sp-bake-export（有误） |
| `substance_painter.baking` | 烘焙 | ✅ sp-bake-export（有误） |
| `substance_painter.resource` | 资源/Shelf | ❌ 无 Skill |
| `substance_painter.display` | 视口显示 | ❌ 无 Skill |
| `substance_painter.ui` | UI 扩展 | ❌ 无 Skill（非必须） |
| `substance_painter.event` | 事件系统 | ❌ 无 Skill（非必须） |
| `substance_painter.application` | 应用信息 | ❌ 无 Skill（非必须） |
| `substance_painter.logging` | 日志 | ❌ 无 Skill（非必须） |
| `substance_painter.colormanagement` | 色彩管理 | ❌ 无 Skill |
| `substance_painter.properties` | 属性系统 | ❌ 无 Skill |
| `substance_painter.source` | 源编辑器 | ❌ 无 Skill |

---

## 结论

### 功能可用性: ✅ 优秀
SP adapter 的基础连接和代码执行完全正常，预注入变量 S/W/L 和 `get_context` 返回信息完整。

### SKILL.md 质量: ❌ 严重问题
四个 SP Skill 中有 **22 处 API 错误**，其中 16 处为致命错误（直接导致代码报错）。主要问题集中在：
1. **函数名臆造**：`insert_fill_layer`, `bake_all_texture_sets`, `get_default_export_config` 等均不存在
2. **方法归属错误**：`layer.delete()` 实为 `delete_node(layer)`
3. **参数遗漏**：`set_opacity`/`set_blending_mode`/`get_opacity`/`get_blending_mode` 在非 mask 层必须传 channel 参数
4. **返回类型错误**：`all_channels()` 返回 dict 非 list，`textures` 返回 dict 非 list
5. **不存在的 API 声明**：`move()`, `duplicate()`, `ExportConfig`, `ExportFormat` 等

### 优先修复建议
1. **立即修复** sp-layer-ops/SKILL.md 的 E1-E9（层操作是最核心最高频的 API）
2. **立即修复** sp-bake-export/SKILL.md 的 E12-E21（导出烘焙 API 几乎全错）
3. **修复** sp-context/SKILL.md 的 E10-E11（通道遍历错误）
4. **修复** sp-operation-rules/SKILL.md 的 E22
5. **新建** sp-resource-ops Skill 覆盖资源管理 API
