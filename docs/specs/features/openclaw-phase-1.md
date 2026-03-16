# OpenClaw Phase 1 — 执行网关与安全沙盒

> **路线图对应**：阶段 1：开放网关与安全沙盒
> **集成方案对应**：§8 Phase 1

---

## 阶段目标

让 OpenClaw 能安全驱动 UE 执行 Python，具备错误回传、回滚与稳定执行能力。

---

## Feature 清单与实现状态

### `feature/openclaw-run-ue-python` ✅ 已完成

**需求**：暴露 `run_ue_python(code: str)`，返回标准化执行结果与可读 Traceback。

**实现文件**：`Content/Python/tools/universal_proxy.py`

**MCP Tool Schema**：
```json
{
  "name": "run_ue_python",
  "description": "Execute Python code in the Unreal Editor context...",
  "inputSchema": {
    "type": "object",
    "properties": {
      "code": {
        "type": "string",
        "description": "Python code to execute in UE context"
      },
      "inject_context": {
        "type": "boolean",
        "default": true,
        "description": "Inject shortcut variables (S, W, L, etc.)"
      }
    },
    "required": ["code"]
  }
}
```

**执行链路**：
```
OpenClaw → tools/call "run_ue_python" → JSON-RPC → MCPServer
  → Static Guard (AST 预审)
  → Risk Assessment (风险评估)
  → ScopedEditorTransaction (事务包装)
  → exec(code, globals) (主线程执行)
  → 返回 stdout 捕获 + 异常 Traceback
```

**返回格式**：
```json
{
  "content": [{"type": "text", "text": "执行结果或错误信息"}],
  "isError": false
}
```

**验收**：
- [x] OpenClaw 可发送 Python 代码并获得执行结果
- [x] 语法错误 / 运行时异常返回完整 Traceback
- [x] 支持多行脚本和复杂逻辑

---

### `feature/openclaw-static-guard` ✅ 已完成

**需求**：执行前做 AST 静态预审，拦截危险调用。

**实现文件**：`Content/Python/tools/static_guard.py`

**黑名单规则**：

| 规则类型 | 示例 | 动作 |
|----------|------|------|
| 模块调用 | `os.system()`, `subprocess.run()` | 拦截 |
| 危险导入 | `__import__('os')` | 拦截 |
| 内建滥用 | `exec()`, `eval()`, `compile()` | 拦截 |
| 文件操作 | `open()` 写模式 | 警告 |

**执行流程**：
1. `ast.parse(code)` 解析代码为 AST
2. `ast.walk()` 遍历所有节点
3. 匹配黑名单模式 → 返回拦截原因
4. 若命中，`run_ue_python` 拒绝执行并返回错误

**验收**：
- [x] `os.system('rm -rf /')` 被拦截
- [x] 正常 `unreal` API 调用不受影响
- [x] 拦截信息清晰可读

---

### `feature/openclaw-undo-transaction-guard` ✅ 已完成

**需求**：自动包裹 `ScopedEditorTransaction`，支持 Ctrl+Z 撤销。

**实现位置**：`Content/Python/tools/universal_proxy.py::run_ue_python()`

**机制**：
```python
with unreal.ScopedEditorTransaction("AI Agent Action") as txn:
    exec(code, exec_globals)
```

- 所有 AI 通过 `run_ue_python` 触发的场景变更都包在同一个事务中
- 用户按 Ctrl+Z 即可一键撤销整个 AI 操作
- 事务名称包含 "AI Agent Action" 前缀，便于在 Undo History 中识别

**验收**：
- [x] AI 创建 10 个物体后，单次 Ctrl+Z 全部撤销
- [x] Undo History 中可见 "AI Agent Action" 条目

---

### `feature/openclaw-main-thread-dispatch` ✅ 已完成

**需求**：所有 UE API 调用回到主线程，消除线程崩溃风险。

**实现**：`Content/Python/mcp_server.py::_UEAsyncBridge`

**核心机制**：
```python
# 不创建任何额外线程
# asyncio 事件循环通过 UE 的 Slate tick 驱动

def _on_tick(self, delta_time):
    """每次 Slate tick 推进 asyncio 一小步"""
    self._loop.stop()
    self._loop.run_forever()
```

这意味着：
- WebSocket 接收/发送 → 在主线程 tick 间隙处理
- `tools/call` → handler 在主线程上执行
- `exec(code)` → 在主线程上执行
- **无需任何线程锁或 GameThread 调度**

**验收**：
- [x] 连续高频执行 `run_ue_python` 不崩溃
- [x] 无 "Assertion failed" 或 "Accessed from wrong thread" 错误
- [x] `unreal.EditorLevelLibrary` 等 API 正常工作

---

### `feature/openclaw-context-shortcuts` ✅ 已完成

**需求**：注入 `S` / `W` / `L` 等快捷上下文，降低代码生成复杂度。

**实现位置**：`Content/Python/tools/universal_proxy.py::run_ue_python()`

**注入的快捷变量**：

| 变量 | 类型 | 含义 |
|------|------|------|
| `S` | `list[unreal.Actor]` | 当前选中的 Actor 列表 |
| `W` | `unreal.World` | 当前编辑器世界 |
| `L` | `unreal.EditorLevelLibrary` | 关卡编辑常用库 |
| `A` | `unreal.EditorAssetLibrary` | 资产编辑常用库 |
| `U` | `unreal` | unreal 模块本身 |

**效果对比**：
```python
# 无快捷变量 (AI 需要写更多代码)
actors = unreal.EditorLevelLibrary.get_selected_level_actors()
for a in actors:
    unreal.EditorLevelLibrary.set_actor_location(a, unreal.Vector(0,0,0), False, False)

# 有快捷变量 (AI 生成更简洁)
for a in S:
    L.set_actor_location(a, U.Vector(0,0,0), False, False)
```

**验收**：
- [x] AI 生成的代码可以直接使用 `S`, `W`, `L` 等变量
- [x] `inject_context=false` 时不注入

---

## 阶段验收总结

| 验收项 | 状态 |
|--------|------|
| OpenClaw 可执行中等复杂度 UE Python 指令 | ✅ |
| 执行失败能返回错误给 OpenClaw | ✅ 完整 Traceback |
| 可撤销场景修改 | ✅ ScopedEditorTransaction |
| 执行过程不发生线程崩溃 | ✅ Slate tick 驱动 asyncio |
| 危险代码被拦截 | ✅ AST Static Guard |

---

## OpenClaw 侧端到端验证

```
1. 启动 UE → 插件自动启动 MCP Server (ws://localhost:8080)
2. 启动 OpenClaw Gateway → mcp-bridge 插件连接到 MCP Server
3. 在 OpenClaw Agent 对话中说: "在场景中创建一个红色的球体"
4. Agent 调用 mcp_ue-editor-agent_run_ue_python(code="...")
5. UE 执行代码 → 场景中出现红色球体
6. UE Output Log 记录完整执行链路
7. Ctrl+Z 撤销 → 球体消失
```
