# Blender ArtClaw API 测试报告

- **测试时间:** 2026-04-07 23:15 (Asia/Shanghai)
- **Blender 版本:** 5.1.0
- **Python 版本:** 3.13.9
- **MCP 工具:** `mcp_blender-editor_run_python`
- **测试人:** ArtClaw 测试工程师 (子代理)

---

## 1. 上下文采集

| # | 测试用例 | 结果 | 说明 |
|---|---------|------|------|
| 1.1 | get_context 基础信息 | ✅ PASS | 返回 software="blender", version="5.1.0", python="3.13.9" |
| 1.2 | S 变量 (选中对象列表) | ✅ PASS | S 返回选中对象列表，格式 `[{'name': 'Cube', 'type': 'MESH'}]` |
| 1.3 | W 变量 (场景文件) | ✅ PASS | W 返回当前场景文件路径（新建文件时为空字符串） |
| 1.4 | L 变量 (bpy 模块) | ✅ PASS | L 是 bpy 模块，has_ops=True, has_data=True |

**小结:** 上下文采集 4/4 通过。

---

## 2. 场景操作

| # | 测试用例 | 结果 | 说明 |
|---|---------|------|------|
| 2.1 | 创建 Cube | ✅ PASS | `bpy.ops.mesh.primitive_cube_add()` 正常 |
| 2.2 | 创建 Sphere | ✅ PASS | `bpy.ops.mesh.primitive_uv_sphere_add()` 正常 |
| 2.3 | 创建 Cylinder | ✅ PASS | `bpy.ops.mesh.primitive_cylinder_add()` 正常 |
| 2.4 | 创建 Empty | ✅ PASS | `bpy.ops.object.empty_add()` 正常 |
| 2.5 | 创建 Camera | ✅ PASS | `bpy.ops.object.camera_add()` 正常 |
| 2.6 | 创建 Light | ✅ PASS | `bpy.ops.object.light_add()` 正常 |
| 2.7 | 选择对象 | ✅ PASS | `obj.select_set(True)` + `view_layer.objects.active` 正常 |
| 2.8 | 移动/旋转/缩放 | ✅ PASS | `obj.location`, `obj.rotation_euler`, `obj.scale` 均可读写 |
| 2.9 | 重命名对象 | ✅ PASS | `obj.name = "NewName"` 正常 |
| 2.10 | Parent-Child 关系 | ✅ PASS | `child.parent = parent` 正常 |
| 2.11 | 自定义属性 | ✅ PASS | `obj["key"] = value` 支持 int/str/float |
| 2.12 | 删除对象 | ✅ PASS | `bpy.ops.object.delete()` 正常 |

**小结:** 场景操作 12/12 通过。

---

## 3. 材质操作

| # | 测试用例 | 结果 | 说明 |
|---|---------|------|------|
| 3.1 | 创建材质 | ✅ PASS | `bpy.data.materials.new()` + `use_nodes=True` 正常 |
| 3.2 | 赋予材质到对象 | ✅ PASS | `obj.data.materials.append(mat)` 正常 |
| 3.3 | Principled BSDF 参数设置 | ✅ PASS | Base Color / Metallic / Roughness 均可设置（第一次运行因 assert 格式问题 FAIL，重试后确认 API 功能正常） |
| 3.4 | 创建和连接 Shader 节点 | ✅ PASS | `nodes.new()`, `links.new()` 正常，TexCoord→Noise→BSDF 连接成功 |

**⚠️ 注意 (Blender 5.1 变化):**
- Principled BSDF 输入名称有变化（对比 Blender 3.x/4.x）：
  - `Specular` → `Specular IOR Level`
  - `Transmission` → `Transmission Weight`
  - `Coat` → `Coat Weight`, `Coat Roughness`, etc.
  - 新增: `Thin Film Thickness`, `Thin Film IOR`, `Diffuse Roughness`
- 完整输入列表: Base Color, Metallic, Roughness, IOR, Alpha, Normal, Weight, Diffuse Roughness, Subsurface Weight, Subsurface Radius, Subsurface Scale, Subsurface IOR, Subsurface Anisotropy, Specular IOR Level, Specular Tint, Anisotropic, Anisotropic Rotation, Tangent, Transmission Weight, Coat Weight, Coat Roughness, Coat IOR, Coat Tint, Coat Normal, Sheen Weight, Sheen Roughness, Sheen Tint, Emission Color, Emission Strength, Thin Film Thickness, Thin Film IOR

**小结:** 材质操作 4/4 通过。

---

## 4. 修改器操作

| # | 测试用例 | 结果 | 说明 |
|---|---------|------|------|
| 4.1 | 添加 Subdivision 修改器 | ✅ PASS | `obj.modifiers.new(type='SUBSURF')` 正常 |
| 4.2 | 添加 Mirror 修改器 | ✅ PASS | `obj.modifiers.new(type='MIRROR')` 正常 |
| 4.3 | 添加 Solidify 修改器 | ✅ PASS | `obj.modifiers.new(type='SOLIDIFY')` 正常 |
| 4.4 | 设置修改器参数 | ✅ PASS | `mod.levels`, `mod.thickness` 等均可读写 |
| 4.5 | 删除修改器 | ✅ PASS | `obj.modifiers.remove(mod)` 正常 |
| 4.6 | 应用修改器 | ✅ PASS | `bpy.ops.object.modifier_apply(modifier=name)` 正常 |

**小结:** 修改器操作 6/6 通过。

---

## 5. 动画操作

| # | 测试用例 | 结果 | 说明 |
|---|---------|------|------|
| 5.1 | 插入关键帧 | ✅ PASS | `obj.keyframe_insert(data_path="location", frame=N)` 正常 |
| 5.2 | 设置帧范围 | ✅ PASS | `scene.frame_start`, `scene.frame_end` 可读写 |
| 5.3 | 读取关键帧数据 | ⚠️ PASS (需注意) | **Blender 5.1 使用 Layered Action 系统**，不再使用 `action.fcurves`，而是 `action.layers[].strips[].channelbags[].fcurves` |

**⚠️ 重要 (Blender 5.1 Breaking Change):**
```python
# Blender 4.x (Legacy)
action = obj.animation_data.action
for fc in action.fcurves:  # ❌ Blender 5.1 没有此属性

# Blender 5.1 (Layered Action)
action = obj.animation_data.action
for layer in action.layers:
    for strip in layer.strips:
        for channelbag in strip.channelbags:
            for fc in channelbag.fcurves:
                # 访问 fc.data_path, fc.array_index, fc.keyframe_points
```
- `action.is_action_layered` = True (新版默认)
- `action.is_action_legacy` = False

**小结:** 动画操作 3/3 通过（但需注意 API 变化）。

---

## 6. 数据查询

| # | 测试用例 | 结果 | 说明 |
|---|---------|------|------|
| 6.1 | 列出所有对象 | ✅ PASS | `bpy.data.objects` 返回 (name, type) 列表 |
| 6.2 | 列出所有材质 | ✅ PASS | `bpy.data.materials` 正常 |
| 6.3 | 列出所有集合 | ✅ PASS | `bpy.data.collections` 正常 |
| 6.4 | 对象信息查询 | ✅ PASS | `mesh.vertices`, `mesh.polygons`, `mesh.edges` 均可访问 |

**小结:** 数据查询 4/4 通过。

---

## 7. Undo 支持

| # | 测试用例 | 结果 | 说明 |
|---|---------|------|------|
| 7.1 | undo_push | ✅ PASS | `bpy.ops.ed.undo_push(message="...")` 正常 |
| 7.2 | Undo 创建操作 | ✅ PASS | 创建对象后 `bpy.ops.ed.undo()` 可以正确撤销，对象数量恢复 |

**小结:** Undo 支持 2/2 通过。

---

## 8. 额外测试（未完成 - Blender 挂起）

以下测试在批量执行时导致 Blender 主线程阻塞超时（可能由 `addon_utils.modules()` 扫描引起），未能完成：

| # | 测试用例 | 结果 | 说明 |
|---|---------|------|------|
| 8.1 | 集合操作(创建+链接对象) | ⏳ 未完成 | 代码逻辑正确，但因超时未能验证 |
| 8.2 | 渲染设置 | ⏳ 未完成 | `scene.render.engine` 等设置 |
| 8.3 | 视口信息获取 | ⏳ 未完成 | `space.shading.type` |
| 8.4 | 导入导出 API 可用性 | ⏳ 未完成 | `bpy.ops.import_scene` / `bpy.ops.export_scene` |
| 8.5 | 模式切换 (Object↔Edit) | ⏳ 未完成 | `bpy.ops.object.mode_set()` |
| 8.6 | BMesh 数据访问 | ⏳ 未完成 | `bmesh.new()` / `bm.from_mesh()` |
| 8.7 | 插件管理 API | ❌ BLOCKED | `addon_utils.modules()` 可能是导致 Blender 挂起的原因 |

**⚠️ 超时原因分析:**
- 将多个测试（包括 `addon_utils.modules()` 全量扫描和 `bpy.ops.object.mode_set()`）放在同一个代码块中执行
- `addon_utils.modules()` 会扫描所有插件目录，在大型安装中可能非常耗时
- 建议：避免在 MCP 执行中调用 `addon_utils.modules()`，或设置更长的超时时间

---

## 汇总

| 类别 | 总数 | 通过 | 失败 | 未完成 |
|------|------|------|------|--------|
| 上下文采集 | 4 | 4 | 0 | 0 |
| 场景操作 | 12 | 12 | 0 | 0 |
| 材质操作 | 4 | 4 | 0 | 0 |
| 修改器操作 | 6 | 6 | 0 | 0 |
| 动画操作 | 3 | 3 | 0 | 0 |
| 数据查询 | 4 | 4 | 0 | 0 |
| Undo 支持 | 2 | 2 | 0 | 0 |
| 额外测试 | 7 | 0 | 0 | 7 |
| **总计** | **42** | **35** | **0** | **7** |

**通过率: 35/35 = 100% (已执行的测试全部通过)**
**未完成: 7 项 (因 Blender 主线程超时阻塞)**

---

## 9. 缺失 API 评估

### 9.1 预注入变量评估

当前预注入变量：
- `S` — 选中对象列表 ✅ 足够
- `W` — 场景文件路径 ✅ 足够
- `L` — bpy 模块 ✅ 足够

**建议增加的预注入变量:**

| 变量 | 用途 | 优先级 |
|------|------|--------|
| `C` | `bpy.context` 的快捷引用，Blender 脚本中极常用 | 🔴 高 |
| `D` | `bpy.data` 的快捷引用，数据访问核心 | 🔴 高 |
| `O` | `bpy.context.active_object` 当前活动对象 | 🟡 中 |

> 注: Blender 自带的 Python 控制台默认预注入 `C = bpy.context` 和 `D = bpy.data`，这是 Blender 社区的标准惯例。

### 9.2 建议补充的 Skill

| Skill 名称 | 描述 | 优先级 |
|------------|------|--------|
| `blender-operation-rules` | Blender 操作通用规则（类似 maya-operation-rules），包含：坐标系(Z-up, 右手系)、Undo 管理、模式切换注意事项、Blender 5.x Layered Action 变化、上下文覆盖等 | 🔴 高 |
| `blender-modeling` | 建模操作指南：BMesh 操作、Edit Mode 操作、常用建模 ops、Mesh 数据结构 | 🟡 中 |
| `blender-material` | 材质/着色器操作指南：节点类型速查、Principled BSDF 5.1 输入名对照表、常见材质配方 | 🟡 中 |
| `blender-context` | 上下文查询 Skill（类似 ue57-artclaw-context），标准化获取场景信息的方式 | 🟡 中 |
| `blender-animation` | 动画操作指南：**重点包含 Blender 5.1 Layered Action 新 API 文档**、NLA 操作、Driver 设置 | 🟡 中 |
| `blender-viewport-capture` | 视口截图能力（类似 ue57-viewport-capture） | 🟢 低 |

### 9.3 未覆盖的重要场景

| 场景 | 说明 | 优先级 |
|------|------|--------|
| **Edit Mode 操作** | 顶点/边/面选择、变换、Loop Cut、Bevel 等操作需要上下文覆盖（context override）才能在脚本中使用 | 🔴 高 |
| **上下文覆盖 (Context Override)** | 很多 bpy.ops 操作需要正确的上下文（area, region, space 等），MCP 远程执行时可能缺少 3D Viewport 上下文 | 🔴 高 |
| **节点组 (Node Groups)** | 创建/管理自定义 Shader 节点组、Geometry Nodes | 🟡 中 |
| **Geometry Nodes** | Blender 的核心功能，程序化建模 | 🟡 中 |
| **Grease Pencil** | 2D/3D 绘画标注 | 🟢 低 |
| **Sculpt Mode** | 雕刻模式操作 | 🟢 低 |
| **Compositing** | 合成节点操作 | 🟢 低 |
| **File I/O** | FBX/OBJ/USD/glTF 导入导出（需测试具体 operator 可用性） | 🟡 中 |
| **Constraints** | 约束系统（Track To, Copy Location 等） | 🟡 中 |
| **Armature/Rigging** | 骨骼创建、权重绘制、Pose Mode | 🟡 中 |
| **渲染执行** | `bpy.ops.render.render()` 在 MCP 中是否阻塞 | 🟡 中 |

### 9.4 Blender 5.1 重要 API 变化记录

1. **Layered Action System**: `action.fcurves` 已移除，必须通过 `action.layers[].strips[].channelbags[].fcurves` 访问
2. **Principled BSDF 输入重命名**: Specular → Specular IOR Level, Transmission → Transmission Weight 等
3. **中文默认名称**: 中文版 Blender 默认对象名为中文（立方体、球体、柱体等），脚本中硬编码英文名会失败
4. **`addon_utils.modules()` 性能问题**: 全量扫描可能导致主线程长时间阻塞

---

## 10. 失败用例详细分析

### 首次 Principled BSDF 测试 (3.3 初次运行)

- **现象:** `[FAIL] Principled BSDF参数设置 — ` (空错误信息)
- **原因:** 第一次测试中 assert 语句 `assert bsdf.inputs['Metallic'].default_value == 0.8` 因浮点精度失败（实际值 0.800000011920929）
- **修复:** 使用 `abs(actual - expected) < 0.01` 代替精确比较
- **状态:** 重试后 PASS，API 功能本身无问题

### Blender 挂起导致的超时 (Test 8 批次)

- **现象:** 将 7 个测试打包执行后，Blender 不再响应 MCP 请求
- **可能原因:**
  1. `addon_utils.modules()` 扫描全部插件文件系统，阻塞时间过长
  2. `bpy.ops.object.mode_set(mode='EDIT')` 在 MCP 执行上下文中可能缺少必要的 area/region 信息
  3. 多个 `bpy.ops` 操作串联执行可能超出 MCP 超时限制
- **修复建议:**
  1. MCP adapter 增加超时保护/中断机制
  2. 避免在单次执行中调用高开销的扫描操作
  3. 考虑增加执行超时配置参数
  4. 添加 watchdog 线程检测主线程阻塞

---

## 11. 总结与建议

### 核心结论
1. **Blender 5.1 adapter 基础功能完善** — 所有已测试的核心 API（场景操作、材质、修改器、动画、数据查询、Undo）均正常工作
2. **预注入变量 S/W/L 工作正常** — 但建议增加 `C`(context) 和 `D`(data) 以符合 Blender 社区惯例
3. **Blender 5.1 有重要 API 变化** — 特别是 Layered Action 系统，需要在 Skill 文档中明确记录

### 优先行动项
1. 🔴 **创建 `blender-operation-rules` Skill** — 记录坐标系、Undo、模式切换、5.1 API 变化等核心规则
2. 🔴 **增加 `C` 和 `D` 预注入变量** — `C = bpy.context`, `D = bpy.data`
3. 🔴 **增加超时保护** — 防止长时间操作导致 Blender 主线程永久阻塞
4. 🟡 **创建 `blender-material` Skill** — 特别是 Principled BSDF 5.1 输入名对照表
5. 🟡 **创建 `blender-animation` Skill** — 重点记录 Layered Action 新 API
6. 🟡 **测试 Edit Mode 和上下文覆盖** — 确认 MCP 远程执行是否支持需要 3D Viewport 上下文的操作
