# DCC 扩展计划 — Blender / Houdini / Substance Painter / Substance Designer

> 目标：将 ArtClaw Bridge 的 AI Agent 能力扩展到 Blender、Houdini、Substance Painter、Substance Designer 四个 DCC
>
> 参考项目：
> - [blender-mcp](https://github.com/ahujasid/blender-mcp) — Blender MCP，Socket 通信 + addon.py 插件
> - [fxhoudinimcp](https://github.com/healkeiser/fxhoudinimcp) — Houdini MCP，168 tools，hwebserver HTTP 通信
> - [substance-painter-mcp](https://github.com/Navelol/substance-painter-mcp) — Substance Painter MCP，TCP Socket 通信
> - [substance-designer-mcp](https://github.com/matthieuhuguet/substance-designer-mcp) — Substance Designer MCP，TCP Socket + 79 材质配方
> - [dcc-mcp](https://github.com/loonghao/dcc-mcp) — 通用 DCC MCP 框架（概念性，开发中）

---

## 一、参考项目分析

### 1. blender-mcp (ahujasid)

| 维度 | 详情 |
|------|------|
| **架构** | Blender addon（Socket Server）+ 独立 MCP Server（stdio），两者通过 TCP socket 通信 |
| **通信方式** | Blender addon 监听 localhost:9876，MCP Server 通过 socket 发送 JSON 命令 |
| **核心能力** | 场景查询、物体 CRUD、材质控制、代码执行、Poly Haven 资产下载、Hyper3D 模型生成、Sketchfab 搜索 |
| **工具设计** | 多个独立 MCP Tool（get_scene_info, create_object, set_material, execute_blender_code 等） |
| **可借鉴** | 代码执行 tool 是核心（类似我们的 run_python），viewport 截图回传给 AI |
| **我们的优势** | 我们有 Skill 生态 + 记忆系统 + 多平台支持，blender-mcp 只是单工具集 |

**关键启发**：
- Blender 用 Python 内嵌解释器，我们的 `run_python` 模式完美适配
- viewport 截图 → AI 分析是一个高价值功能，SP 也可以做
- Poly Haven / Sketchfab 集成思路可以做成通用 Skill

### 2. fxhoudinimcp (healkeiser)

| 维度 | 详情 |
|------|------|
| **架构** | Houdini 内 hwebserver（HTTP Server）+ 独立 MCP Server（stdio），HTTP/JSON 通信 |
| **通信方式** | Houdini 内置 hwebserver 监听 localhost:8100，MCP Server HTTP 请求 |
| **工具数量** | **168 tools + 8 resources + 6 prompts**，覆盖极其全面 |
| **覆盖领域** | Scene/Node/Param/SOPs/LOPs-USD/DOPs/PDG-TOPs/COPs/HDA/Animation/Render/VEX/Viewport/Workflows/Materials/CHOPs/Cache/Takes |
| **主线程安全** | `hdefereval.executeInMainThreadWithResult()` 确保 hou.* 调用在主线程 |
| **代码执行** | 有 execute_python/execute_hscript 工具，但也保留大量专用工具 |

**关键启发**：
- Houdini 用 hwebserver 内置 HTTP Server，不需要自己写 socket
- 168 个工具的方式 ≠ 我们的路线（我们精简到 run_python + Skill 指导）
- 但它的**功能覆盖列表**是极好的参考 — 告诉我们 Houdini 侧应该做到什么程度
- Workflow prompts（一键 Pyro/RBD/FLIP/Vellum setup）思路值得做成 Skill
- Houdini 20.5+ 才有 hwebserver，要确认版本支持

### 3. substance-painter-mcp (Navelol)

| 维度 | 详情 |
|------|------|
| **架构** | Painter 内 plugin（TCP Server）+ 独立 MCP Server（stdio），TCP socket 通信 |
| **通信方式** | Painter plugin 监听 localhost:9876，MCP Server 通过 TCP 发送 JSON |
| **工具数量** | ~50 tools，分 7 组（Project/TextureSet/Export/Layer/Camera/Resource/Python） |
| **核心能力** | 层操作、材质管理、贴图集、烘焙、导出、资源搜索、Python 沙盒执行 |
| **安全设计** | execute_python 有 3 层沙盒：AST 验证 + 受限 builtins + 长度限制 |
| **主线程安全** | Qt 主线程处理（Painter 内嵌 Python + Qt） |

**关键启发**：
- SP 是 Qt + Python 应用，和我们的 DCCClawBridge 技术栈一致
- SP 的 API 主要是 `substance_painter.layerstack` / `substance_painter.textureset` 等
- Layer 操作是 SP 的核心（add/delete/move/duplicate/mask/blend mode）
- 烘焙 + 导出控制是高价值功能
- 安全沙盒设计值得参考（我们目前没有限制 run_python 的代码执行范围）

### 4. substance-designer-mcp (matthieuhuguet)

| 维度 | 详情 |
|------|------|
| **架构** | SD 内 plugin（TCP Server 端口 9881）+ 独立 MCP Server（stdio），TCP length-prefix 通信 |
| **通信方式** | SD plugin 监听 localhost:9881，每个命令使用独立 TCP 连接（无持久连接） |
| **工具数量** | 22 tools，含图操作 + 节点 CRUD + 连接 + 参数 + 材质配方 |
| **核心能力** | 图创建/查询、节点创建（原子节点+库节点）、连接管理、参数设置、PBR 材质一键生成 |
| **亮点功能** | **79 个内置材质配方**（pro_granite/pro_steel 等，37-44 节点的专业级材质图） |
| **主线程安全** | Qt Signal/Slot queued connection |
| **SD 版本** | 15.x（Python 3.11 内嵌） |
| **已知陷阱** | SDUsage.sNew() 永久挂起、newNode(未知定义) 永久挂起、arrange_nodes() 破坏连接 |

**关键启发**：
- SD 是纯节点图编辑器，操作模式类似 UE 的 Material Editor — 我们有 Material 节点编辑经验
- **79 个材质配方**非常有价值 — 可以迁移/参考做成 Skill 的 recipe 系统
- SD 的 API 限制很多（单线程、易挂起），需要严格的验证层
- 与 SP 共享 Adobe Substance 3D 生态，安装路径结构类似
- length-prefix framing 协议比 SP 的裸 JSON 更可靠

### 5. dcc-mcp (loonghao)

| 维度 | 详情 |
|------|------|
| **状态** | 早期开发中，代码基本是脚手架，"Frontend API under development" |
| **思路** | 通用 DCC MCP 框架，adapter 模式适配不同 DCC |
| **价值** | 概念上和我们类似，但我们的实现远超它 |

**结论**：loonghao/dcc-mcp 还在起步阶段，没有可直接复用的代码，但验证了"通用 DCC 框架"方向的市场需求。

---

## 二、ArtClaw 现有架构的适配分析

### 我们的已有优势

| 基础设施 | 状态 | 新 DCC 复用 |
|----------|------|------------|
| bridge_core.py（平台无关通信核心） | ✅ 成熟 | 直接复用 |
| bridge_config.py（配置管理） | ✅ 成熟 | 直接复用 |
| bridge_dcc.py（Qt UI 框架） | ✅ 成熟 | Blender ✅ (PySide6) / Houdini ✅ / SP ✅ |
| memory_core.py（记忆系统 v2） | ✅ 成熟 | 直接复用 |
| skill_hub.py（Skill 管理） | ✅ 成熟 | 直接复用 |
| knowledge_base.py（知识库） | ✅ 成熟 | 直接复用 |
| mcp_server.py（WebSocket MCP） | ✅ 成熟 | 需适配 |
| install.py（部署脚本） | ✅ 成熟 | 扩展 DCC 列表 |
| OpenClaw Skill（SKILL.md） | ✅ 成熟 | 新增 DCC 专用 Skill |

### 各 DCC 适配复杂度

| DCC | Python 环境 | UI 框架 | 通信可选方案 | 适配难度 |
|-----|------------|---------|------------|---------|
| **Blender** | bpy 内嵌 Python | **PySide6（pip 安装）** | Qt 独立窗口 + bpy.app.timers | ⭐⭐ 中 |
| **Houdini** | hou 内嵌 Python | Qt (PySide2/6) | hwebserver / socket / xmlrpc | ⭐⭐ 中 |
| **Substance Painter** | SP 内嵌 Python | Qt (PySide2) | TCP socket plugin | ⭐⭐ 中 |
| **Substance Designer** | SD 内嵌 Python 3.11 | Qt (PySide2) | TCP socket plugin | ⭐⭐ 中 |

### Blender Qt 方案（方案 A：独立 Qt 窗口）

Blender **没有内置 Qt**，但我们选择**在子线程启动独立 QApplication**，复用全套 Qt UI：

**架构**：
```
Blender 主线程 (bpy)          子线程 (Qt)
┌─────────────────────┐      ┌─────────────────────────┐
│  blender_addon.py   │      │  QApplication 事件循环    │
│  - 注册 addon       │◄────►│  bridge_dcc.py (复用)     │
│  - bpy.app.timers   │queue │  artclaw_ui/ (复用)       │
│  - 主线程 bpy 操作   │      │  独立悬浮窗口             │
└─────────────────────┘      └─────────────────────────┘
```

**关键设计**：
- Blender addon 启动时，`threading.Thread` 中创建 `QApplication` + Qt 窗口
- Qt 窗口作为**独立悬浮窗**（非嵌入 Blender），与 Maya/Max 体验一致
- `bridge_dcc.py` + `artclaw_ui/` **零改动**直接复用
- Blender ↔ Qt 通过 `queue.Queue` 双向通信
- bpy 操作必须回到主线程：Qt 侧通过 queue 投递 → `bpy.app.timers.register()` 在主线程执行
- MCP `run_python` 的代码执行也必须调度到 Blender 主线程

**PySide 依赖**：
- Blender 4.x 使用 Python 3.11+，需要 **PySide6**（PySide2 不支持 3.11+）
- install.py 安装时自动 `pip install PySide6` 到 Blender 的 Python 环境
- Blender 3.x (Python 3.10) 可用 PySide2 或 PySide6
- `bridge_dcc.py` 已经兼容 PySide2/PySide6（`try: from PySide6 ... except: from PySide2 ...`）

**风险**：
- 双事件循环（bpy + Qt）需要严格线程隔离
- 部分用户可能抵触额外安装 PySide6（~30MB）
- Blender Python 版本跳跃大，PySide 兼容性需要持续跟进

---

## 三、开发计划

### Phase 1: Blender 适配（优先级 P0）

> Blender 是开源 3D 软件中用户量最大的，MCP 生态也最活跃（blender-mcp 星标最高）
> 采用方案 A：独立 Qt 窗口，复用 bridge_dcc.py + artclaw_ui/

**1.1 基础通信层 + Qt 集成** (~3 天)
- [ ] 新增 `adapters/blender_adapter.py`（bpy 适配层，~300 行）
- [ ] 新增 `blender_addon.py`（Blender addon 入口，负责：注册 addon、启动 Qt 子线程、bpy.app.timers 主线程调度）
- [ ] 新增 `blender_qt_bridge.py`（~200 行，Blender ↔ Qt 线程桥接：queue 双向通信 + 主线程调度器）
- [ ] 复用 `bridge_dcc.py`（Qt UI 通信层，零改动）
- [ ] 复用 `artclaw_ui/`（完整 Chat Panel + Settings，零改动）
- [ ] MCP Server 实例（端口 8083），注册 `run_python` 工具
- [ ] Session 隔离：`agent/blender-editor`
- [ ] `run_python` 代码执行调度到 Blender 主线程（通过 `bpy.app.timers.register()`）

**1.2 核心 API 适配** (~2 天)
- [ ] `blender_adapter.py` 实现 BaseAdapter 接口：
  - `get_selected_objects()` → bpy.context.selected_objects
  - `get_scene_info()` → bpy.context.scene 遍历
  - `execute_code(code)` → exec(code, {"bpy": bpy, ...})
- [ ] DCC Context 注入（首条消息前缀）
- [ ] Viewport 截图（bpy.ops.render.opengl + 临时文件 → base64）

**1.3 OpenClaw Skills** (~2 天)
- [ ] `blender_operation_rules` — Blender 操作规范 Skill（坐标系 Z-up、undo 规则等）
- [ ] `blender_context` — 场景/选择查询 Skill
- [ ] `blender_highlight` — 选择/聚焦物体 Skill
- [ ] `blender_viewport_capture` — 截图 Skill

**1.4 安装部署** (~1 天)
- [ ] install.py 新增 Blender 支持（自动检测 Blender 安装路径）
- [ ] 自动 `pip install PySide6` 到 Blender 的 Python 环境
- [ ] Blender addon 自动安装到 `%APPDATA%\Blender Foundation\Blender\{version}\scripts\addons\`
- [ ] OpenClaw agent 配置自动注入（MCP server blender-editor）
- [ ] bridge_dcc.py PySide2/PySide6 兼容确认（`try/except` import）

**预估总工时**: ~8 天

---

### Phase 2: Houdini 适配（优先级 P0）

> Houdini 是 VFX 行业核心工具，程序化生成能力与 AI 结合潜力巨大

**2.1 基础通信层** (~2 天)
- [ ] 新增 `adapters/houdini_adapter.py`（hou 适配层，~300 行）
- [ ] 复用 `bridge_dcc.py`（Houdini 有 Qt/PySide2）
- [ ] Houdini shelf tool 入口：`houdini_shelf.py`（启动 + Panel）
- [ ] MCP Server 实例（端口 8084），注册 `run_python` 工具
- [ ] Session 隔离：`agent/houdini-editor`
- [ ] 主线程安全：`hdefereval.executeInMainThreadWithResult()`

**2.2 核心 API 适配** (~2 天)
- [ ] `houdini_adapter.py` 实现 BaseAdapter 接口：
  - `get_selected_objects()` → hou.selectedNodes()
  - `get_scene_info()` → hou.node("/obj").children() 遍历
  - `execute_code(code)` → exec(code, {"hou": hou, ...})
- [ ] DCC Context 注入
- [ ] Viewport 截图（hou.SceneViewer.flipbookSettings + 截图）

**2.3 Houdini 专用 Skill** (~3 天)
- [ ] `houdini_operation_rules` — 操作规范（Y-up、节点网络规则、cook 机制）
- [ ] `houdini_context` — 场景/节点树查询
- [ ] `houdini_node_ops` — 节点创建/连接/参数设置指南
- [ ] `houdini_simulation` — Pyro/RBD/FLIP/Vellum 工作流（参考 fxhoudinimcp 的 workflow prompts）
- [ ] `houdini_hda` — HDA 创建/管理指南
- [ ] `houdini_viewport_capture` — 截图

**2.4 安装部署** (~1 天)
- [ ] install.py 新增 Houdini 支持
- [ ] 自动安装到 `$HOUDINI_USER_PREF_DIR/scripts/python/`
- [ ] Shelf tool 自动注册
- [ ] OpenClaw agent 配置注入

**预估总工时**: ~8 天

---

### Phase 3: Substance Painter 适配（优先级 P1）

> SP 是贴图制作核心工具，与 UE 资产管线直接关联

**3.1 基础通信层** (~2 天)
- [ ] 新增 `adapters/substance_painter_adapter.py`（SP API 适配层，~300 行）
- [ ] 复用 `bridge_dcc.py`（SP 有 Qt/PySide2）
- [ ] SP plugin 入口：`sp_plugin.py`（在 SP Python 环境中运行）
- [ ] MCP Server 实例（端口 8085），注册 `run_python` 工具
- [ ] Session 隔离：`agent/substance-painter-editor`
- [ ] 主线程安全：Qt 信号机制（与 Maya/Max 一致）

**3.2 核心 API 适配** (~2 天)
- [ ] `substance_painter_adapter.py` 实现：
  - `get_project_info()` → substance_painter.project
  - `get_texture_sets()` → substance_painter.textureset
  - `get_layers()` → substance_painter.layerstack
  - `execute_code(code)` → exec(code, {"substance_painter": sp, ...})
- [ ] DCC Context 注入
- [ ] Viewport 截图（substance_painter.ui.get_main_window → grabFramebuffer）

**3.3 SP 专用 Skill** (~3 天)
- [ ] `sp_operation_rules` — SP 操作规范
- [ ] `sp_context` — 项目/纹理集/层查询
- [ ] `sp_layer_ops` — 层操作指南（add/delete/move/mask/blend mode/fill）
- [ ] `sp_bake_export` — 烘焙 + 导出工作流
- [ ] `sp_resource` — 资源搜索/导入
- [ ] `sp_viewport_capture` — 截图

**3.4 安装部署** (~1 天)
- [ ] install.py 新增 SP 支持
- [ ] 自动安装到 SP plugins 目录
- [ ] OpenClaw agent 配置注入

**预估总工时**: ~8 天

---

### Phase 3.5: Substance Designer 适配（优先级 P1）

> SD 是程序化材质制作核心工具，节点图编辑模式与 UE Material Editor 类似，我们有丰富经验

**3.5.1 基础通信层** (~2 天)
- [ ] 新增 `adapters/substance_designer_adapter.py`（SD API 适配层，~300 行）
- [ ] 复用 `bridge_dcc.py`（SD 有 Qt/PySide2）
- [ ] SD plugin 入口：`sd_plugin.py`（在 SD Python 环境中运行）
- [ ] MCP Server 实例（端口 8086），注册 `run_python` 工具
- [ ] Session 隔离：`agent/substance-designer-editor`
- [ ] 主线程安全：Qt Signal/Slot queued connection（与 SP 一致）
- [ ] **严格单线程约束**：SD API 不支持并行调用，需要在 adapter 层加请求队列

**3.5.2 核心 API 适配** (~2 天)
- [ ] `substance_designer_adapter.py` 实现：
  - `get_scene_info()` → sd.api.SDApplication 获取 packages/graphs
  - `get_graph_info()` → 遍历节点和连接
  - `execute_code(code)` → exec(code, {"sd": sd_module, ...})
- [ ] DCC Context 注入
- [ ] **节点定义验证层**：创建节点前验证 definition 存在（防止 SD 挂起）
- [ ] 2D 预览截图（SD 的 2D View 输出）

**3.5.3 SD 专用 Skill** (~3 天)
- [ ] `sd_operation_rules` — SD 操作规范（单线程约束、节点验证、端口命名规则）
- [ ] `sd_context` — Package/Graph/Node 查询
- [ ] `sd_node_ops` — 节点创建/连接/参数设置指南（含原子节点+库节点区分）
- [ ] `sd_material_recipes` — 材质配方系统（参考 substance-designer-mcp 的 79 个配方）
- [ ] `sd_pbr_workflow` — PBR 材质图完整工作流（BaseColor/Normal/Height/Roughness/AO/Metallic 输出）

**3.5.4 安装部署** (~1 天)
- [ ] install.py 新增 SD 支持
- [ ] 自动安装到 `%USERPROFILE%\Documents\Adobe\Adobe Substance 3D Designer\python\sduserplugins\`
- [ ] OpenClaw agent 配置注入

**预估总工时**: ~8 天

---

### Phase 4: 公共设施增强（与 Phase 1-3.5 穿插进行）

**4.1 adapter 抽象层增强** (~1 天)
- [ ] `base_adapter.py` 新增 viewport 截图接口
- [ ] 统一 DCC Context 注入格式
- [ ] 新增 `get_dcc_version()` / `get_python_version()` 标准接口

**4.2 Blender Qt 桥接验证** (~1 天)
- [ ] 验证 PySide6 在 Blender 4.x Python 3.11+ 环境中的兼容性
- [ ] 验证双事件循环（bpy + Qt）稳定性（长时间运行测试）
- [ ] 验证 bpy.app.timers 主线程调度性能（高频操作场景）
- [ ] bridge_dcc.py 确认 PySide2/PySide6 双兼容无遗漏

**4.3 通用 Skill 增强** (~1 天)
- [ ] `artclaw-context` Skill 更新：支持 Blender/Houdini/SP 的 context 获取
- [ ] `artclaw-memory` / `artclaw-knowledge` / `artclaw-skill-manage` 已通用，无需改动
- [ ] `artclaw-highlight` 评估各 DCC 是否可行

**4.4 install.py 统一** (~1 天)
- [ ] DCC 检测增强（Blender/Houdini/SP/SD 安装路径自动发现）
- [ ] 交互式选择扩展（7 选项：UE/Maya/Max/Blender/Houdini/SP/SD）
- [ ] config.json 自动写入新 DCC 配置
- [ ] verify_sync.py 覆盖新 DCC

**预估总工时**: ~5 天

---

## 四、端口分配

| DCC | MCP 端口 | Session ID | OpenClaw Agent |
|-----|---------|------------|----------------|
| UE | 8080 | agent/ue-editor | ue-editor-agent |
| Maya | 8081 | agent/maya-editor | maya-editor-agent |
| Max | 8082 | agent/max-editor | max-editor-agent |
| **Blender** | **8083** | **agent/blender-editor** | **blender-editor-agent** |
| **Houdini** | **8084** | **agent/houdini-editor** | **houdini-editor-agent** |
| **SP** | **8085** | **agent/sp-editor** | **sp-editor-agent** |
| **SD** | **8086** | **agent/sd-editor** | **sd-editor-agent** |

---

## 五、文件结构规划

```
subprojects/DCCClawBridge/
├── adapters/
│   ├── base_adapter.py          # 已有
│   ├── maya_adapter.py          # 已有
│   ├── max_adapter.py           # 已有
│   ├── blender_adapter.py       # 新增
│   ├── houdini_adapter.py       # 新增
│   └── substance_painter_adapter.py  # 新增
│   └── substance_designer_adapter.py # 新增
├── core/                        # 共享核心（已有，不改）
├── artclaw_ui/                  # Qt UI（Maya/Max/Houdini/SP/SD/Blender 共用）
├── bridge_dcc.py                # Qt 通信（Maya/Max/Houdini/SP/SD/Blender 共用）
├── blender_addon.py             # 新增：Blender addon 入口（注册 + 启动 Qt 子线程）
├── blender_qt_bridge.py         # 新增：Blender ↔ Qt 线程桥接（queue + bpy.app.timers）
├── houdini_shelf.py             # 新增：Houdini shelf tool 入口
├── sp_plugin.py                 # 新增：SP plugin 入口
├── sd_plugin.py                 # 新增：SD plugin 入口
└── mcp_server.py                # 已有，增加 DCC 类型参数

skills/official/
├── universal/                   # 通用 Skill
├── unreal/                      # UE Skill
├── maya/                        # Maya Skill
├── max/                         # Max Skill
├── blender/                     # 新增
│   ├── blender_operation_rules/
│   ├── blender_context/
│   ├── blender_highlight/
│   └── blender_viewport_capture/
├── houdini/                     # 新增
│   ├── houdini_operation_rules/
│   ├── houdini_context/
│   ├── houdini_node_ops/
│   ├── houdini_simulation/
│   ├── houdini_hda/
│   └── houdini_viewport_capture/
└── substance_painter/           # 新增
    ├── sp_operation_rules/
    ├── sp_context/
    ├── sp_layer_ops/
    ├── sp_bake_export/
    ├── sp_resource/
    └── sp_viewport_capture/
├── substance_designer/          # 新增
    ├── sd_operation_rules/
    ├── sd_context/
    ├── sd_node_ops/
    ├── sd_material_recipes/
    └── sd_pbr_workflow/
```

---

## 六、从参考项目借鉴但不照搬

### 我们的核心差异（竞争优势）

| 维度 | 参考项目方式 | ArtClaw 方式 |
|------|------------|-------------|
| **工具数量** | 每个操作一个 MCP tool（168个） | 1 个 `run_python` + Skill 按需加载 |
| **扩展性** | 加功能 = 改 MCP Server 代码 | 加功能 = 写新 Skill（SKILL.md + Python） |
| **记忆** | 无 | 三级记忆系统 + 团队记忆 |
| **知识库** | 无 | 本地知识库 + 语义搜索 |
| **多平台** | 只支持 Claude/Cursor | OpenClaw + LobsterAI + Claude 多平台 |
| **部署** | 手动配置 | install.py/install.bat 一键部署 |
| **UI** | 无/简单 addon panel | 完整 Chat Panel + Settings + Skill 管理 |

### 值得借鉴的功能点

1. **fxhoudinimcp 的 Workflow Prompts** → 做成 Skill
   - 一键 Pyro/RBD/FLIP/Vellum setup
   - 复杂操作流的最佳实践封装

2. **blender-mcp 的外部资产集成** → 通用 Skill
   - Poly Haven 资产下载
   - Sketchfab 模型搜索
   - 可以做成跨 DCC 的通用 Skill

3. **substance-painter-mcp 的安全沙盒** → 评估
   - AST 验证 + 受限 builtins
   - 我们目前 run_python 没有限制，考虑可选安全模式

4. **fxhoudinimcp 的 Resources** → 评估
   - MCP Resources 提供文档/上下文（我们用 Skill + 知识库替代）

5. **substance-designer-mcp 的材质配方系统** → 做成 Skill
   - 79 个内置材质配方（37-44 节点的专业级 PBR 材质图）
   - 可以迁移为 `sd_material_recipes` Skill，AI 通过自然语言一键生成材质
   - 配方架构值得参考：将专业知识封装为可复用的模板

---

## 七、里程碑与优先级

| 阶段 | 目标 | 优先级 | 预估工时 | 依赖 |
|------|------|--------|---------|------|
| **Phase 1** | Blender 基础适配 | P0 | 8 天 | 无 |
| **Phase 2** | Houdini 基础适配 | P0 | 8 天 | 无 |
| **Phase 3** | Substance Painter 适配 | P1 | 8 天 | 无 |
| **Phase 3.5** | Substance Designer 适配 | P1 | 8 天 | 无 |
| **Phase 4** | 公共设施增强 | P0 | 4 天 | 与 1-3.5 穿插 |
| **总计** | — | — | **~36 天** | — |

### 推荐执行顺序

```
Week 1-2:  Phase 1 (Blender) + Phase 4.1-4.2 (公共设施)
Week 3-4:  Phase 2 (Houdini)
Week 5-6:  Phase 3 (Substance Painter) + Phase 3.5 (Substance Designer)
Week 7:    Phase 4.3-4.4 (收尾)
```

> Phase 1 和 Phase 2 可以并行（如果人力允许），它们之间没有依赖。
> Phase 3 和 Phase 3.5 同属 Adobe Substance 3D 系列，共享安装路径结构和 Qt 通信模式，适合放一起做。
> Phase 4 的公共设施增强与 Phase 1-3.5 穿插进行，特别是 Blender Qt 桥接验证需要在 Phase 1 期间完成。

---

## 八、风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| Blender Qt 双事件循环不稳定 | UI 卡死/崩溃 | 严格线程隔离，bpy 操作只走主线程 queue + timers |
| Blender 用户抵触安装 PySide6 (~30MB) | 用户流失 | install.py 自动安装，可选项说明 |
| Blender Python 版本跳跃（3.10→3.12+） | PySide 兼容性 | 持续跟进 PySide6 版本，CI 多版本测试 |
| Houdini hwebserver 版本限制（20.5+） | 低版本用户无法使用 | 退回 xmlrpc/socket 方案做 fallback |
| SP 内嵌 Python 版本较旧 | API 兼容问题 | 测试 SP 2024/2025 确认 Python 版本 |
| SD API 严格单线程 + 易挂起 | 工具调用超时/SD 假死 | adapter 层加请求队列 + 节点定义预验证 |
| 各 DCC 主线程安全机制不同 | 崩溃风险 | 统一在 adapter 层处理，不暴露给上层 |
| Skill 内容编写需要各 DCC 深度知识 | Skill 质量 | 参考项目的工具列表 + 官方文档 |

---

## 附录：参考项目 Star 与活跃度

| 项目 | Stars (约) | 最近更新 | 成熟度 |
|------|-----------|---------|--------|
| blender-mcp | ~5000+ | 活跃 | 成熟，社区活跃 |
| fxhoudinimcp | ~500+ | 活跃 | 成熟，功能全面 |
| substance-painter-mcp | ~200+ | 近期 | 可用，功能完整 |
| substance-designer-mcp | ~100+ | 近期 | 可用，79 材质配方亮点 |
| dcc-mcp | ~100+ | 开发中 | 早期，脚手架 |
