<!-- Ref: docs/specs/sdk-dcc-interface-spec.md -->
# DCC 接口标准化规范

> 定义所有 DCC 插件必须实现的统一接口，覆盖三类宿主环境的差异。
> 索引文档：[SDK/API 标准化总览](./sdk-api-standardization-overview.md)

## 三类宿主环境

ArtClaw 支持的 DCC 按运行环境分为三类，接口设计需兼顾差异：

| 类型 | 代表 | UI 方案 | 线程模型 | asyncio 驱动 |
|------|------|---------|---------|-------------|
| **引擎类** | UE, Unity | C++ Slate 面板 | 主线程 tick 驱动 | Slate tick callback |
| **DCC 类** | Maya, Max, Blender, Houdini, SP, SD | PySide2/6 Qt 面板 | 独立 daemon 线程 | 独立 asyncio 线程 |
| **Web 类** | ComfyUI | Tool Manager Web Chat | 无主线程限制 | 独立线程（直接调用） |

## D1 — DCC Adapter 抽象基类

### 现有定义

`BaseDCCAdapter` 在 `subprojects/DCCClawBridge/adapters/base_adapter.py` 中，
包含 13 个抽象方法分 6 类。

### 标准化方案

所有 DCC（含 UE）统一实现 `BaseDCCAdapter`。UE 需新建 `UEAdapter(BaseDCCAdapter)`，
Python adapter 只负责 MCP/Skill/执行层，UI 部分仍由 C++ Slate 处理。

### 接口清单

#### A. 基本信息（3 个方法）— 所有类型必须实现

```python
@abstractmethod
def get_software_name(self) -> str:
    """返回 DCC 标识名，如 "maya", "unreal_engine", "comfyui" """

@abstractmethod
def get_software_version(self) -> str:
    """返回 DCC 版本号，如 "2023", "5.7", "1.0" """

@abstractmethod
def get_python_version(self) -> str:
    """返回 Python 版本，如 "3.9.7" """
```

#### B. 生命周期（2 个方法）— 所有类型必须实现

```python
@abstractmethod
def on_startup(self) -> None:
    """启动时调用：注册菜单、启动 MCP Server、加载 Skills"""

@abstractmethod
def on_shutdown(self) -> None:
    """关闭时调用：停止 MCP Server、断开连接、清理资源"""
```

#### C. 主线程调度（2 个方法）— 见 D3

```python
@abstractmethod
def execute_on_main_thread(self, fn: Callable, *args) -> Any:
    """在 DCC 主线程执行函数并返回结果（阻塞等待）
    - 引擎类(UE)：直接调用（tick 本身在主线程）
    - DCC 类：maya.utils / bpy.timers / QTimer 等
    - Web 类(ComfyUI)：直接调用（无主线程限制）"""

@abstractmethod
def execute_deferred(self, fn: Callable, *args) -> None:
    """在 DCC 主线程延迟执行（非阻塞，不等待结果）"""
```

#### D. 上下文采集（3 个方法）— 见 D7/D8

```python
@abstractmethod
def get_selected_objects(self) -> list[dict]:
    """返回当前选择对象列表
    - 引擎类：Actor/Component
    - DCC 类：Object/Node/TextureSet
    - Web 类：空列表"""

@abstractmethod
def get_scene_info(self) -> dict:
    """返回场景摘要：{name, object_count, file_path, ...}"""

@abstractmethod
def get_current_file(self) -> str | None:
    """返回当前文件路径，无文件时返回 None"""
```

#### E. UI 集成（2 个方法）— 可选

```python
def get_main_window(self) -> Any | None:
    """返回主窗口句柄（Qt QMainWindow），无 UI 时返回 None
    - 引擎类：None（Slate 不暴露 Qt 窗口）
    - DCC 类：Maya/Max/Blender 主窗口
    - Web 类：None"""

def register_menu(self, menu_name: str, callback: Callable) -> None:
    """注册菜单项，无 UI 时 no-op"""
```

#### F. 代码执行（2 个方法）— 所有类型必须实现

```python
@abstractmethod
def execute_code(self, code: str, context: dict | None = None) -> dict:
    """执行 Python 代码
    返回：{"success": bool, "result": Any, "error": str|None, "output": str}"""

def clear_exec_namespace(self) -> None:
    """清空持久执行命名空间"""
```

### 各类型实现要点

| 方法 | 引擎类(UE) | DCC 类 | Web 类(ComfyUI) |
|------|-----------|--------|-----------------|
| `execute_on_main_thread` | 直接调用 | 跨线程 Future | 直接调用 |
| `get_main_window` | `None` | Qt 主窗口 | `None` |
| `register_menu` | C++ 侧处理 | `cmds.menu` 等 | no-op |
| `get_selected_objects` | Actor 列表 | Object/Node 列表 | `[]` |
| `execute_code` | `exec()` + unreal 模块 | `exec()` + DCC 模块 | `exec()` + S/L 注入 |

## D2 — MCP Server 初始化接口

### 统一接口

```python
class MCPServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080): ...
    def start(self) -> bool: ...
    def stop(self) -> None: ...
    def is_running(self) -> bool: ...
    def register_tool(self, name, description, input_schema, handler,
                      main_thread: bool = False) -> None: ...
```

### 💡 最佳实践：每个 DCC 仅暴露 1 个工具

> **推荐**：每个 DCC 服务仅通过 `register_tool()` 注册 **1 个** MCP 工具（如 `run_python` 或 `run_ue_python`），
> 将所有功能通过该工具的 `code` 参数以 Python 代码方式调用。

**理由**：
- AI 平台对 MCP 工具数量有上限，单工具方案充分利用配额给 Skills；
- 减少工具选择歧义，AI 可直接通过 Skill 机制实现功能分发；
- 降低 MCP Server 复杂度，便于维护和热更新。

**多工具场景**：`register_tool()` 接口仍完整支持，适用于需要精细权限控制（如只读 vs 写入分离）
或需要向 AI 暴露固定参数 Schema 的高级场景。

```python
# ✅ 推荐：单工具注册
server.register_tool(
    name="run_python",
    description="Execute Python code in the DCC environment",
    input_schema={"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
    handler=run_python_handler,
)

# ⚠️ 进阶：多工具注册（需要精细控制时使用）
server.register_tool("get_scene_info", ...)
server.register_tool("set_material", ...)
```

### 驱动模式差异（合理，无需统一实现）

| 类型 | 驱动方式 | 线程 | 说明 |
|------|---------|------|------|
| 引擎类 | Slate tick callback | 主线程内 | `run_until_complete(sleep(0))` |
| DCC 类 | 独立 daemon 线程 | 后台线程 | `asyncio.run()` |
| Web 类 | 独立线程 | 后台线程 | 同 DCC 类 |

### 端口分配（已标准化）

| DCC | 端口 | 状态 |
|-----|------|------|
| UE | 8080 | ✅ 生产 |
| Maya | 8081 | ✅ 生产 |
| Max | 8082 | ✅ 已实现 |
| Blender | 8083 | ✅ 已验证 |
| Houdini | 8084 | ⚠️ 未测试 |
| Substance Painter | 8085 | ✅ 已验证 |
| Substance Designer | 8086 | ✅ 已验证 |
| ComfyUI | 8087 | ✅ 已验证 |

## D3 — 主线程调度抽象

### 问题

7 个 DCC 各有不同的主线程 API，MCP Server 需要统一的调度方式。

### 标准接口

```python
async def execute_on_main_thread(fn, args, timeout=60) -> Any:
    """统一主线程调度入口（MCP Server 内部调用）
    1. 创建 Future
    2. 通过 adapter.execute_on_main_thread() 调度
    3. await Future，带超时和 watchdog 检查"""
```

### 各 DCC 实现映射

| DCC | 底层 API | 阻塞方式 |
|-----|---------|---------|
| UE | 直接调用（已在主线程） | 无需阻塞 |
| Maya | `maya.utils.executeInMainThreadWithResult()` | 内置阻塞 |
| Max | `QTimer.singleShot(0, fn)` + Event | Event.wait() |
| Blender | `bpy.app.timers.register(fn)` + Queue | Queue.get() |
| Houdini | `hdefereval.executeInMainThreadWithResult()` | 内置阻塞 |
| SP | `QTimer` poll (50ms) | Event.wait() |
| SD | Lock + Queue + watchdog | Poll + frozen 检测 |
| ComfyUI | 直接调用 | 无需阻塞 |

## D4 — Tool 注册标准签名

### 推荐方案：装饰器优先

```python
# 推荐方式（声明式，支持 AST 静态分析）
@artclaw_tool(
    name="tool_name",
    description="AI-facing description",
    category="scene",
    risk_level="low",
)
def tool_name(arguments: dict) -> str: ...
```

`@artclaw_tool` 为统一装饰器名称，向后兼容 `@ue_tool`。
`register_tool()` 保留为底层 API，供运行时动态注册场景使用。

## D5 — Tool Handler 返回值契约

```python
# 标准返回格式
{
    "content": [{"type": "text", "text": "结果文本"}],
    "isError": False
}
```

建议定义 `ToolResult` 辅助函数简化构建。

## D6 — 代码执行环境 ExecutionContext

各 DCC 的 `execute_code()` 注入不同的命名空间快捷变量：

| DCC | 注入变量 | 说明 |
|-----|---------|------|
| Maya | `S`(场景), `W`(世界), `L`(cmds), `cmds`, `om` | 持久命名空间 |
| Max | `rt`(pymxs.runtime) | 持久命名空间 |
| Blender | `bpy`, `C`(context), `D`(data) | 持久命名空间 |
| Houdini | `hou` | 持久命名空间 |
| SP | `sp`(substance_painter) | 持久命名空间 |
| SD | `sd`, `app`, `mgr` | 持久命名空间 + 线程锁 |
| ComfyUI | `S`(server), `L`(lib), `save_preview()` | 每次刷新 |
| UE | `unreal` (全局可用) | 无需注入 |

标准接口：`adapter.get_exec_namespace() -> dict`

## D7 — 选择/上下文查询接口（ContextProvider）

引擎和 DCC 的语义差异是固有的，不强制统一数据结构。

### 方案：定义 key 命名约定

```python
def get_context(self) -> dict:
    """返回 DCC 上下文，key 遵循约定：
    - "selection": list[dict]  — 当前选择
    - "scene_name": str        — 场景/关卡名
    - "file_path": str|None    — 当前文件路径
    - "frame_range": tuple|None — 帧范围（动画类 DCC）
    - "active_camera": str|None — 活动摄像机（引擎类）
    """
```

AI Agent 根据 `get_software_name()` 理解具体语义。

## D9 — MCP Resources 支持

**引擎专属扩展**，仅 UE/Unity 等游戏引擎实现。
DCC 类不需要 `resources/list` 和 `resources/read`。

## D10 — UI 集成接口

三类 UI 方案全覆盖，adapter 层不强制 UI 实现：

| 方案 | 适用场景 | 实现方 |
|------|---------|--------|
| C++ Slate 面板 | UE/Unity 等引擎 | 引擎插件(C++) |
| PySide2/6 Qt 面板 | Maya/Max/Blender/Houdini/SP/SD | DCCClawBridge |
| Tool Manager Web Chat | ComfyUI/Headless | Web 前端 |

adapter 的 `get_main_window()` 和 `register_menu()` 为可选方法，
无 UI 场景返回 `None` / no-op。

### Tool Manager Web Chat 的 DCC 选择入口

Tool Manager Web Chat 预留了 DCC 选择下拉框（`StatusBar.tsx`、`Sidebar.tsx`），
当前仅用于显示 DCC 连接状态，未实现功能路由。

**Adapter 不需要感知 Web Chat。** 架构上这是单向的：

```
Web Chat 前端 (React appStore.currentDCC)
    ↓ 仅用于 UI 显示
Tool Manager 后端 (dcc_manager.py)
    ↓ 定期 ping /health 端点
DCC Adapter 的 MCP Server (ws://127.0.0.1:{port})
```

如果未来要实现"用户选择 DCC 后限定 AI 只使用该 DCC 的工具"，
改动点在 **Tool Manager 后端的 `message_router.py`**（注入 DCC 上下文到消息），
adapter 只需保持现有的 MCP Server + `/health` 端点，无需额外改动。
