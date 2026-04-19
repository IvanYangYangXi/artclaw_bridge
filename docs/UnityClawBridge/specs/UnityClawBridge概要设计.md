# UnityClawBridge 概要设计与开发规划

**版本**：0.2.0 | **创建**：2026-04-19 | **更新**：2026-04-19 | **状态**：骨架完成，M1 进行中

---

## 一、项目定位

**UnityClawBridge** 是 ArtClaw Bridge 的 Unity Editor 接入子项目，
让 Unity Editor 通过 MCP 协议接入 AI Agent（OpenClaw、Claude Desktop 等），
获得 AI 操控 Unity 场景、资产、编辑器的能力。

**在 ArtClaw 体系中的位置**：
```
AI Agent（OpenClaw/Claude）
    ↓ MCP JSON-RPC
UnityClawBridge（Python MCP Server, 端口 8088）
    ↓ HTTP 命令通道
Unity C# CommandServer（端口 8089）
    ↓ EditorApplication.update
Unity Editor 主线程 API（UnityEngine / UnityEditor）
```

---

## 二、技术架构

### 2.1 核心约束与选型依据

| 约束 | Unity 具体情况 | 应对方案 |
|------|--------------|---------|
| **主线程限制** | Unity API 只能在主线程调用 | C# CommandServer + EditorApplication.update 消费队列 |
| **Python 环境** | Unity 不内置 Python 运行时 | 启动外置 Python 进程（系统 Python 3.9+）|
| **跨进程通信** | Python ↔ C# 进程隔离 | HTTP 轮询（同机器，低延迟）|
| **MCP 工具** | 遵循 v2.6 单工具规范 | 仅暴露 `run_unity_python` 1 个工具 |

### 2.2 进程架构

```
Unity Editor 进程（C#）
├── UnityClawBridgeBootstrap  [InitializeOnLoad] 启动引导
├── CommandServer             [InitializeOnLoad] HTTP 命令服务器 :8089
├── UnityClawDashboard        EditorWindow 状态面板
└── EditorApplication.update  主线程命令消费

外置 Python 进程（由 Bootstrap 启动）
├── bootstrap.py              入口 + asyncio 事件循环
├── mcp_server.py             MCP WebSocket Server :8088
└── unity_adapter.py          DCC 适配层（HTTP → C# CommandServer）
```

### 2.3 代码执行流程

```
AI 调用 run_unity_python(code="...")
    ↓ MCP tools/call
Python mcp_server.py
    ↓ HTTP POST /execute {id, code}
C# CommandServer（后台线程接收）
    ↓ 入队 _commandQueue
EditorApplication.update（主线程）
    ↓ 出队，调用 EvaluateCode()
Unity API 执行 → 结果写入 _results[id]
    ↓
Python 轮询 GET /result/{id}
    ↓ 返回 MCP result
AI 收到执行结果
```

---

## 三、开发路线图

### M0 · 项目骨架（当前阶段）✅

| 交付物 | 状态 |
|--------|------|
| 目录结构 / package.json | ✅ |
| C# Bootstrap + Dashboard | ✅ |
| C# CommandServer（HTTP :8089）| ✅ |
| Python bootstrap.py + MCP Server | ✅ |
| Python UnityAdapter | ✅ |
| 示例 Skill × 2（场景信息、创建GameObject）| ✅ |
| 设计文档 | ✅ |

---

### M1 · 基础链路打通（目标 2 周）

**目标**：AI 能通过 run_unity_python 执行简单 Unity API 调用，Dashboard 显示状态。

#### M1.1 C# 执行引擎完善

**当前问题**：CommandServer.EvaluateCode() 只有占位实现。

**方案选型**：

| 方案 | 可行性 | 说明 |
|------|--------|------|
| **方案A：Unity Python for Applications** | ⭐⭐⭐ | Unity 官方包 `com.unity.scripting.python`，支持在编辑器内运行 Python。Unity 2022+ 可用。需购买 Unity Pro/企业版 |
| **方案B：反射 + 代码路由表** | ⭐⭐ | 无依赖，解析代码中的 API 调用，通过 C# 反射执行。覆盖范围有限 |
| **方案C：Roslyn 脚本（C# 执行）** | ⭐⭐⭐ | AI 提交 C# 代码片段，通过 Roslyn 编译执行。与 Unity 完全兼容 |
| **方案D：eval-style 解析器** | ⭐ | 自行解析 Python AST，实现太复杂不推荐 |

**推荐**：**方案C（Roslyn C# 执行）** 作为主路线，无需外部依赖，覆盖完整 Unity API。
方案A（Unity Python）作为备选，若用户有 Unity Pro 可选开启。

**实现要点（方案C）**：
```csharp
// 使用 Microsoft.CodeAnalysis.CSharp.Scripting
var script = CSharpScript.Create(code, 
    ScriptOptions.Default
        .AddImports("UnityEngine", "UnityEditor", "System")
        .AddReferences(typeof(UnityEngine.GameObject).Assembly));
var result = await script.RunAsync();
```

#### M1.2 Python 端完善

- [ ] `bootstrap.py`：集成共享 `mcp_server.py`（从 `core/` 导入）
- [ ] `unity_adapter.py`：完善 `get_selected_objects()` 和 `get_scene_info()` 的真实实现
- [ ] 启动时自动检测 Python 可执行文件路径

#### M1.3 Dashboard 完善

- [ ] 显示实时连接状态（Python 进程 PID、端口）
- [ ] 显示最近 5 条 AI 执行日志
- [ ] 一键打开 Python 日志文件

**验收标准**：
```
AI → run_unity_python("get_scene_info()") → 返回正确的场景名和对象数
AI → run_unity_python("Debug.Log('Hello from AI')") → Unity Console 显示日志
```

---

### M2 · 执行引擎（目标 1 个月）

**目标**：完整的代码执行能力 + 持久命名空间。

| 任务 | 说明 |
|------|------|
| Roslyn 脚本引擎集成 | 支持 C# 代码在编辑器运行时执行 |
| 持久命名空间 | 跨调用保持变量（`_execNamespace`） |
| 错误信息中文化 | 异常信息符合 ArtClaw 规范 |
| 上下文注入 | `Selection`, `ActiveScene`, `AssetDatabase` 等快捷访问 |
| Python 端 `get_selected_objects()` 真实实现 | 通过 CommandServer 查询 `Selection.gameObjects` |

---

### M3 · P0 核心 Skill 开发（目标 2 个月）

**目标**：30 个 P0 Skill，覆盖 Unity 日常编辑操作。（参考 CoplayDev/unity-mcp 工具分类扩充）

#### 已完成的 Skill（M0 输出）

| Skill | 路径 | 覆盖操作 |
|-------|------|---------|
| `artclaw-unity-context` | `skills/official/unity/` | 入口路由、环境检查 |
| `unity-scene-ops` | `skills/official/unity/` | 8 种场景操作 |
| `unity-gameobject-ops` | `skills/official/unity/` | 10 种 GameObject 操作 |
| `unity-component-ops` | `skills/official/unity/` | 8 种组件操作 |
| `unity-asset-ops` | `skills/official/unity/` | 8 种资产操作 |
| `unity-editor-control` | `skills/official/unity/` | 8 种编辑器控制 |

#### M3 补充 Skill（基于参考项目扩充）

**材质与着色器（Material）~6 个**：

| Skill | 覆盖操作 |
|-------|---------|
| `unity-material-ops` | 创建材质、设置属性（颜色/纹理/金属度/粗糙度）、URP/HDRP 材质、Shader 切换 |

**物理系统（Physics）~4 个**：

| Skill | 覆盖操作 |
|-------|---------|
| `unity-physics-ops` | 物理设置、Layer 碰撞矩阵、关节管理、Raycast 查询（参考 CoplayDev 21个物理动作）|

**动画（Animation）~4 个**：

| Skill | 覆盖操作 |
|-------|---------|
| `unity-animation-ops` | Animator Controller 操作、AnimationClip、Blend Tree、过渡参数 |

**代码生成（Scripting）~4 个**：

| Skill | 覆盖操作 |
|-------|---------|
| `unity-scripting-ops` | 创建 MonoBehaviour/ScriptableObject、脚本模板、编辑脚本文件、Roslyn 验证 |

**构建（Build）~3 个**：

| Skill | 覆盖操作 |
|-------|---------|
| `unity-build-ops` | 触发构建、切换平台、配置 Player Settings、批量跨平台构建（参考 CoplayDev）|

**包管理（Package）~2 个**：

| Skill | 覆盖操作 |
|-------|---------|
| `unity-package-ops` | 安装/卸载/搜索 UPM 包、Scoped Registries（参考 CoplayDev）|

---

### M4 · 平台集成（目标 3 个月）

**目标**：与 OpenClaw/WorkBuddy 平台完整联调，接入 SDK 标准化接口。

| 任务 | 说明 |
|------|------|
| 接入 SDK 标准化（sdk-api-standardization-overview.md）| 实现 D1~D10 接口 |
| 记忆系统集成 | 接入 `core/memory_core.py`（`MemoryManagerV2`）|
| DCCEventManager 集成 | Tool Manager 事件触发（文件保存等）|
| `install.py` 集成 | 一键安装 UnityClawBridge + 共享核心 |
| mcp_configs 模板 | `mcp_configs/official/unity-editor-agent/` |
| OpenClaw 联调 | 完整链路测试（AI → MCP → Unity）|

---

### M5 · Skill 生态扩展（持续）

P1/P2 Skill（~60个），覆盖：
- 动画（Animator、AnimationClip）
- UI（Canvas、UGUI）
- 光照（Light、Lightmap、HDRI）
- 物理（Rigidbody、Collider）
- 渲染（Camera、RenderPipeline 切换）
- 代码生成（新建 MonoBehaviour 脚本）
- 包管理（Package Manager 操作）

---

## 四、目录结构

```
subprojects/UnityClawBridge/
├── Editor/
│   └── Scripts/                     # C# 编辑器脚本
│       ├── UnityClawBridgeBootstrap.cs  # [InitializeOnLoad] 启动引导
│       ├── CommandServer.cs            # HTTP 命令服务器 :8089
│       └── UnityClawDashboard.cs       # EditorWindow 状态面板
│
├── Python/                          # 外置 Python 进程
│   ├── bootstrap.py                 # 入口 + MCP Server 启动
│   ├── unity_adapter.py             # UnityAdapter（BaseDCCAdapter 子类）
│   ├── requirements.txt
│   └── skills/                      # Skill 源码（开发用）
│       ├── scene/
│       │   └── skill_get_scene_info.py
│       ├── gameobject/
│       │   └── skill_create_gameobject.py
│       └── asset/
│
├── Resources/                       # 图标等资源
├── package.json                     # Unity Package Manifest
└── README.md

skills/official/unity/               # 项目级 Skill 目录（安装目录）
├── artclaw-unity-context/
│   └── SKILL.md

docs/UnityClawBridge/
├── specs/
│   └── UnityClawBridge 概要设计.md   # 本文档
├── features/                        # 各阶段实现文档
└── troubleshooting/                 # 排错记录
```

---

## 五、端口规划

| 组件 | 端口 | 说明 |
|------|------|------|
| MCP WebSocket Server | **8088** | AI → MCP 工具调用 |
| C# CommandServer (HTTP) | **8089** | Python → Unity 主线程执行 |

---

## 六、核心依赖

| 依赖 | 版本 | 说明 |
|------|------|------|
| Unity | 2022.3+ LTS | 最低要求 |
| .NET | 4.x / .NET Standard 2.1 | Unity 内置 |
| Python | 3.9+ | 系统安装，不内置 |
| websockets | ≥11.0 | Python MCP Server |
| aiohttp | ≥3.9 | Python 异步 HTTP |
| requests | ≥2.31 | Python 同步 HTTP 轮询 |
| Microsoft.CodeAnalysis (Roslyn) | M2 引入 | C# 脚本执行 |

---

## 七、与 UEClawBridge 对比

| 维度 | UEClawBridge | UnityClawBridge |
|------|-------------|-----------------|
| 语言 | C++ + Python | C# + Python |
| Python 环境 | UE 内置 Python 插件 | 系统 Python（外置进程）|
| 主线程调度 | register_slate_post_tick_callback | EditorApplication.update |
| 通信机制 | Python 直接调用 UE Python API | HTTP 跨进程桥接 |
| UI 框架 | Slate（C++）| EditorWindow（C#）|
| MCP 工具 | `run_ue_python` | `run_unity_python` |

---

## 九、参考项目对比分析

### 两个高星 Unity MCP 项目

| 维度 | CoplayDev/unity-mcp | IvanMurzak/Unity-MCP | **UnityClawBridge** |
|------|--------------------|--------------------|---------------------|
| 架构 | C# 内置 MCP HTTP Server | C# 内置 MCP + 任意C#方法转工具 | **Python 外置 MCP + C# CommandServer** |
| Python | 无（纯 C#）| 无（纯 C#）| **有（ArtClaw 标准架构）**|
| 工具数 | 40+ | 100+ | Skill 生态（可无限扩展）|
| 多实例 | ✅ 支持实例路由 | ✅ | 单实例（当前方案）|
| batch_execute | ✅（比单次快10-100x）| ✅ | **M1 需实现批量执行**|
| 物理系统 | ✅ 21个动作 | ✅ | M5 规划 |
| 构建系统 | ✅ 跨平台构建 | ✅ | M3 规划 |
| Profiler | ✅ 14个动作 | ✅ | M5+ |
| 包管理 | ✅ | ✅ | M5+ |
| Roslyn 验证 | ✅ validate_script | ✅ | **M1 核心目标**|

### 我们方案的核心优势

1. **ArtClaw 统一架构**：与 Maya/Max/UE 共享 Skill 生态、记忆系统、Tool Manager
2. **Skill 热插拔**：新能力通过 Skill 扩展，无需修改 C# 代码
3. **完整 AI 工具链**：接入 OpenClaw/WorkBuddy，而非仅支持 Claude Desktop

### 从参考项目复用的设计

从 CoplayDev/unity-mcp 采纳的设计决策：

| 特性 | 采纳 | 说明 |
|------|------|------|
| 工具分类体系（scene/gameobject/asset/component/editor）| ✅ | 映射为我们的 Skill 分类 |
| Newtonsoft.Json 替代 JsonUtility | ✅ | CommandServer 中已采纳（支持匿名对象）|
| `batch_execute` 批量执行 | 计划 M1 | 避免多次 HTTP 往返，提升 AI 效率 10-100x |
| Undo 支持（RegisterCreatedObjectUndo 等）| ✅ | 所有 Skill 代码模板已包含 |
| SerializedObject API 修改组件属性 | ✅ | unity-component-ops Skill 中已采纳 |
| validate_script（Roslyn 预验证）| 计划 M1 | 执行前验证 C# 代码语法 |
| Unity 实例版本信息注入 | ✅ | health 端点已返回 unity_version |

---

## 八、风险与注意事项

| 风险 | 级别 | 应对 |
|------|------|------|
| Python 未安装 | 中 | Bootstrap 检测失败时显示明确提示，引导安装 |
| Unity Python for Applications 需要 Pro | 中 | 默认走 Roslyn 方案，Unity Python 作为可选增强 |
| HTTP 轮询延迟 | 低 | 同机器通信 <5ms，可接受 |
| 端口冲突 | 低 | CommandServer 自动探测可用端口（8089 起）|
| 不支持 Runtime（仅 Editor）| 设计限制 | 明确定位为 Editor 工具，不支持 Play Mode 外部调用 |
