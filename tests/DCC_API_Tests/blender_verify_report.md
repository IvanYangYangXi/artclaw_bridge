# Blender ArtClaw 验证报告

> **测试环境**: Blender 5.1.0 | Python 3.13.9 | 中文界面  
> **测试时间**: 2026-04-08  
> **MCP 工具**: `mcp_blender-editor_run_python`

---

## 修复验证

| 状态 | 验证项 | 说明 |
|------|--------|------|
| ✅ PASS | 预注入变量 C | `C` 类型为 `Context`，等于 `bpy.context` |
| ✅ PASS | 预注入变量 D | `D` 类型为 `BlendData`，`D.objects` 可访问（初始3个对象） |
| ✅ PASS | 预注入变量 bpy/S/W/L | 所有标准预注入变量均可用（通过 `get_context` 验证） |
| ✅ PASS | blender-operation-rules Skill | 文件存在且内容完整，包含所有 7 条规则 + 标准模板 + 坐标系对比 |
| ✅ PASS | Skill 覆盖 Blender 5.x 变化 | 包含 Layered Action 系统、Principled BSDF 输入名变化、中文版适配 |
| ✅ PASS | Skill 覆盖 temp_override | 规则 6 包含 `C.temp_override()` 使用指南 |

---

## 用例验证

| 状态 | 用例 | 说明 |
|------|------|------|
| ✅ PASS | 用例 1: 场景搭建 | 成功创建 Ground(10x)、3个球体(随机位置+颜色)、Sun Light、Camera，共6个对象，所有变换正确 |
| ✅ PASS | 用例 2: 材质工作流 | PBR 材质创建成功；**注意**：中文版 Blender 节点名为中文（`原理化 BSDF`），必须用 `n.type == 'BSDF_PRINCIPLED'` 查找而非 `nodes.get("Principled BSDF")`；Noise Texture→Roughness 连接正常 |
| ✅ PASS | 用例 3: 修改器工作流 | Subdivision Surface(levels=2) + Displacement 修改器添加成功，堆栈顺序正确 |
| ✅ PASS | 用例 4: 动画工作流 | 关键帧插入成功（帧1/30/60）；Layered Action 系统验证通过（`is_action_layered=True`）；FCurves 通过 `layers→strips→channelbags→fcurves` 路径正确读取 |
| ✅ PASS | 用例 5: 数据查询 | 成功列出所有6个对象的类型、位置、材质、修改器信息 |
| ✅ PASS | 用例 6: 集合管理 | "Props" 集合创建成功，3个球体全部移入；原集合保留 Ground/Sun_Light/Main_Camera |
| ✅ PASS | 用例 7: 导入导出 | `import_scene`: fbx, gltf; `export_scene`: fbx, gltf（`import_mesh`/`export_mesh` 为空，格式统一在 scene 级别） |
| ✅ PASS | 用例 8: Edit Mode 操作 | `C.temp_override()` 可用且工作正常；成功进入 Edit Mode、选择全部顶点(482个)、使用 bmesh 读取数据、返回 Object Mode |

---

## 功能覆盖度分析

### 1. 已有 Skill/API 支持的常用功能

| 功能类别 | Skill | 覆盖情况 |
|----------|-------|----------|
| 操作通用规则 | `blender-operation-rules` | ✅ 完整：坐标系、Undo、预注入变量、5.x 适配、中文版、temp_override |
| 知识库搜索 | `artclaw-knowledge` | ✅ 可用 |
| 记忆系统 | `artclaw-memory` | ✅ 可用 |
| Skill 管理 | `artclaw-skill-manage` | ✅ 可用 |
| 场景视觉分析 | `scene-vision-analyzer` | ✅ 可用（通用，非 Blender 专属） |

### 2. 缺少 Skill 但 API 可用的常用功能

| 功能类别 | API 可用性 | 建议 Skill |
|----------|-----------|-----------|
| 场景搭建 | ✅ `bpy.ops.mesh.primitive_*_add` / `bpy.ops.object.light_add` / `bpy.ops.object.camera_add` | `blender-scene-builder` |
| 材质/着色器工作流 | ✅ `mat.node_tree.nodes` / `links` 完整 API | `blender-material-ops` |
| 修改器工作流 | ✅ `obj.modifiers.new()` 完整 API | `blender-modifier-ops` |
| 动画工作流 | ✅ `keyframe_insert` + Layered Action API | `blender-animation-ops` |
| 数据查询/场景信息 | ✅ `D.objects` / `D.materials` / `D.collections` | `blender-context`（类似 `ue57-artclaw-context`） |
| 集合管理 | ✅ `D.collections` 完整 API | （可纳入 `blender-context`） |
| Edit Mode / BMesh 操作 | ✅ `temp_override` + `bmesh` 完整 API | `blender-mesh-ops` |
| 导入导出 | ✅ `bpy.ops.import_scene.fbx/gltf` / `bpy.ops.export_scene.fbx/gltf` | `blender-io` |
| 渲染设置 | ✅ `C.scene.render` / `C.scene.cycles` 完整 API | `blender-render` |
| UV 操作 | ✅ `bpy.ops.uv.*`（需 temp_override） | `blender-uv-ops` |
| 骨骼/绑定 | ✅ `bpy.ops.object.armature_add` / `bpy.data.armatures` | `blender-rigging` |
| 粒子系统 | ✅ `obj.particle_systems` | `blender-particles` |
| Geometry Nodes | ✅ `node_tree` API | `blender-geo-nodes` |

### 3. API 不可用或有限制的功能

| 功能 | 限制说明 |
|------|----------|
| 实时视口截图 | 无 `bpy.ops.render.opengl` 的 MCP 等效（需 temp_override + 可能阻塞） |
| 文件打开 | `bpy.ops.wm.open_mainfile()` 被 Skill 明确禁止（状态不一致风险） |
| 插件管理 | `addon_utils.modules()` 被禁止（性能问题） |
| GPU 渲染 | 可设置参数但实际渲染可能超时 |
| Compositor 实时预览 | 需要渲染才能看到效果 |
| 视口 Gizmo 交互 | 纯 API 无法模拟鼠标拖拽式交互 |

### 4. 建议创建的新 Skill（按优先级排序）

| 优先级 | Skill 名称 | 理由 |
|--------|-----------|------|
| 🔴 P0 | `blender-context` | **最基础**：场景信息查询、选中对象详情、对标 UE 的 `ue57-artclaw-context` |
| 🔴 P0 | `blender-material-ops` | **高频需求**：材质创建/编辑/节点连接，中文版 Blender 节点名适配是关键痛点 |
| 🟡 P1 | `blender-scene-builder` | 场景搭建常用操作的封装：对象创建、变换、灯光、相机 |
| 🟡 P1 | `blender-modifier-ops` | 修改器添加/删除/排序/应用的标准操作 |
| 🟡 P1 | `blender-animation-ops` | 关键帧管理 + Layered Action 5.x 适配（这是最容易出错的地方） |
| 🟡 P1 | `blender-mesh-ops` | Edit Mode 操作：顶点/边/面选择、BMesh 操作、temp_override 封装 |
| 🟢 P2 | `blender-io` | 导入导出工作流（FBX/glTF 参数配置） |
| 🟢 P2 | `blender-render` | 渲染设置（引擎/分辨率/采样/输出格式） |
| 🟢 P2 | `blender-uv-ops` | UV 展开/编辑操作 |
| 🟢 P2 | `blender-viewport-capture` | 视口截图（对标 UE 的 `ue57-viewport-capture`） |
| ⚪ P3 | `blender-rigging` | 骨骼/绑定操作 |
| ⚪ P3 | `blender-geo-nodes` | Geometry Nodes 图操作 |
| ⚪ P3 | `blender-particles` | 粒子系统设置 |

---

## 关键发现

### 中文版 Blender 适配是核心痛点
- 默认节点名为中文：`原理化 BSDF`、`噪波纹理`、`材质输出`
- **`blender-operation-rules` 已覆盖对象名问题**（规则 5），但**节点名问题未单独强调**
- **建议**：在 `blender-operation-rules` 中增加 "规则 8：着色器节点中文名适配"，或在 `blender-material-ops` Skill 中内置按类型查找节点的辅助函数

### Blender 5.1 Layered Action 适配验证通过
- `action.is_action_layered == True` 确认 5.1 默认使用 Layered Action
- `blender-operation-rules` 规则 3 提供的遍历代码**完全正确**，测试验证通过

### temp_override 在 MCP 环境下可用
- `C.temp_override()` 在 MCP 远程执行环境中正常工作
- Edit Mode / BMesh 操作均可通过此方式完成
- 这为 UV、骨骼等高级操作提供了基础

### 与 UE ArtClaw 的功能对比
- UE 侧有 12+ 专属 Skill（context、highlight、camera、material、viewport-capture 等）
- Blender 侧仅有 1 个通用规则 Skill（`blender-operation-rules`）
- **Blender API 能力不亚于 UE**，但 Skill 覆盖度远低于 UE

---

## 总结

| 指标 | 结果 |
|------|------|
| 修复验证 | **6/6 全部 PASS** |
| 用例验证 | **8/8 全部 PASS** |
| 已有 Skill 数 | 1（`blender-operation-rules`） |
| API 可用但缺 Skill | 13 个功能类别 |
| 建议新 Skill 数 | 13（P0: 2, P1: 4, P2: 4, P3: 3） |
| 整体评估 | **API 能力完整，Skill 覆盖度不足** — Blender 的 bpy API 非常强大，所有测试用例均一次通过或简单适配后通过，但缺少封装好的 Skill 意味着 AI 需要更多底层知识才能正确操作 |
