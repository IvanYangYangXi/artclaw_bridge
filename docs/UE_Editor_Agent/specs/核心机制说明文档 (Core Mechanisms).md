# UE Editor Agent - 核心机制说明文档 (Core Mechanisms)

## 1. 自动能力发现机制 (Auto-Discovery Mechanism)
为了实现“写完 Python 逻辑，AI 立即能用”，系统构建了一套基于反射的自动映射机制。

- **工作流**：
    1. **扫描器 (Scanner)**：UE 插件启动时，遍历 `Skills/` 目录下的所有 Python 脚本。
    2. **内省 (Introspection)**：利用 Python `inspect` 库提取带有 `@ue_agent.tool` 装饰器的函数签名、类型注解及 Docstring。
    3. **Schema 转换**：将 Python 元数据转换为 **MCP Tool Definition (JSON-Schema)**。
    4. **注册 (Registration)**：通过 MCP 协议向 OpenClaw 发送 `notifications/initialized`，宣告可用工具集。

## 2. 动态 Skill 热加载机制 (Dynamic Hot-Reload)
支持在不重启虚幻引擎的情况下，实时更新 Agent 的能力。

- **监听器 (Watcher)**：使用 `unreal.DirectoryWatcher` 监控 Skills 文件夹。
- **重载逻辑**：
    - 当 `.py` 文件变更时，触发 `importlib.reload()`。
    - 重新触发“自动能力发现机制”，更新 MCP Server 的工具快照。
    - **OpenClaw 同步**：通过 WebSocket 向 OpenClaw 发送 `tool_list_changed` 通知，确保 AI 大脑中的工具描述永远是最新的。

## 3. 安全可逆执行机制 (Safe Execution & Undo)
AI 的操作必须是受控且可撤销的，防止其“跑偏”导致场景损毁。

- **事务包装 (Transaction Wrapper)**：
    所有通过 MCP 调用的 Python/C++ 接口均被强制包裹在 `unreal.ScopedEditorTransaction` 中。
    ```python
    with unreal.ScopedEditorTransaction("AI Agent 操作: " + task_name):
        # 执行具体逻辑
        func(*args, **kwargs)
    ```
- **原子化操作**：复杂的 Skill 逻辑被拆分为多个原子 Tool 调用，每一步成功后才推进下一步，失败则触发 `Cancel` 事务。

## 4. 混合 UI 交互机制 (Hybrid UI Interaction)
AI 不是全自动运行，而是在关键节点与开发者协同。

- **原生对话框调度**：
    当 Skill 脚本调用 `agent_ui.confirm(...)` 时，C++ 层的 **Native UI Manager** 会在 UE 编辑器视图中心弹出标准 Slate 窗口。
- **状态阻塞与回调**：
    Python 协程会暂停执行，等待用户点击“确定/取消”后，通过回调将布尔值传回 Python 逻辑，决定是否继续执行后续 MCP 指令。

## 5. C++ 与 Python 通讯穿透 (Bridge Mechanism)
解决 Python 无法操作贴图像素或底层渲染句柄的问题。

- **C++ 暴露给 Python**：
    使用 `UFUNCTION(BlueprintCallable)` 或 `pybind11` 将高性能 C++ 函数暴露。
- **Python 封装为 Tool**：
    Python 脚本作为“胶水层”，调用这些 C++ 接口，并挂载 MCP 装饰器，使其对 AI 可见。
    - *示例*：C++ 处理纹理压缩 -> Python 包装逻辑 -> MCP 暴露给 AI。

## 6. MCP 资源流转机制 (Resource Streaming)
如何让 AI “看到”海量资产而不引起内存爆炸。

- **懒加载 (Lazy Loading)**：AI 请求资源时，系统仅返回资产路径（ObjectPath）和类型（Class）。
- **按需采样 (On-demand Sampling)**：
    只有当 AI 明确要求“分析这个材质的参数”时，系统才会读取该资产的具体 Property 字段并转为 JSON 传给模型。

---

**核心流程图解**:
`用户描述` -> `OpenClaw 路由` -> `MCP Tool 调用` -> `UE Python 胶水层` -> `UE Transaction (Undo)` -> `UE Engine 执行` -> `反馈/UI 确认`
