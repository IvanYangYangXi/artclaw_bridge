---
name: artclaw-unity-context
description: >
  Unity Editor AI agent context and routing skill for ArtClaw Bridge.
  Use when AI needs to: (1) understand how to operate Unity Editor via ArtClaw MCP,
  (2) determine which Unity sub-skill to load for a task, (3) get project and environment
  context (Unity version, project path, connection status), (4) understand the run_unity_python
  execution model and C# code format.
  NOT for: direct Unity operations — load the specific skill (unity-scene-ops, unity-gameobject-ops,
  unity-asset-ops, unity-component-ops, unity-editor-control) for actual operations.
license: MIT
metadata:
  artclaw:
    display_name: "Unity 上下文与路由"
    author: ArtClaw
    software: unity
    category: utils
    risk_level: low
    version: 1.1.0
    tags: ["unity", "context", "routing", "mcp", "run_unity_python"]
---

# ArtClaw Unity 上下文

UnityClawBridge 的入口 Skill。了解 Unity 环境的接入方式，并路由到正确的操作 Skill。

---

## 执行模型

```
AI → run_unity_python(code="<C# 代码>")
        ↓ MCP :8088
   Python MCP Server
        ↓ HTTP POST :8089
   C# CommandServer（Unity 后台线程接收）
        ↓ _commandQueue
   EditorApplication.update（Unity 主线程）
        ↓ Roslyn/反射执行
   Unity Editor API
        ↓ 结果写入 _results[id]
   Python GET /result/{id}
        ↓
   AI 收到 JSON 结果
```

**核心规则**：
- 所有 Unity API 必须通过 `run_unity_python` 提交 **C# 代码字符串** 执行
- 代码在 Unity 主线程执行，完全支持 `UnityEngine.*` / `UnityEditor.*` 命名空间
- 用 `return Newtonsoft.Json.JsonConvert.SerializeObject(...)` 返回结构化数据
- 始终使用 `Undo.RecordObject` / `Undo.RegisterCreatedObjectUndo` 支持撤销

---

## Skill 路由表

| 任务 | 加载的 Skill |
|------|------------|
| 获取场景信息、打开/保存场景、查找 GameObject | `unity-scene-ops` |
| 创建/删除/移动/复制 GameObject，设置 Transform | `unity-gameobject-ops` |
| 添加/移除/修改组件（Rigidbody、Light、Camera 等）| `unity-component-ops` |
| 导入/搜索/创建/删除资产，实例化 Prefab | `unity-asset-ops` |
| 撤销/重做、Play Mode、构建、菜单执行、控制台 | `unity-editor-control` |

---

## 环境检查

在执行操作前，先确认 Unity 已连接：

```python
run_unity_python(code="""
return Newtonsoft.Json.JsonConvert.SerializeObject(new {
    connected = true,
    unityVersion = UnityEngine.Application.unityVersion,
    projectName = UnityEngine.Application.productName,
    dataPath = UnityEngine.Application.dataPath,
    isPlaying = UnityEditor.EditorApplication.isPlaying,
    isCompiling = UnityEditor.EditorApplication.isCompiling
});
""")
```

---

## C# 代码格式要求

1. **无需命名空间声明**：`UnityEngine` / `UnityEditor` 已自动引入
2. **返回 JSON 字符串**：用 `Newtonsoft.Json.JsonConvert.SerializeObject(...)` 或 `return "{...}"`
3. **支持多行代码**：用换行符分隔语句
4. **变量在调用间共享**（持久命名空间）：可跨调用使用已定义的变量

```csharp
// 最小示例 — 返回当前场景名
return UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;

// 标准示例 — 返回 JSON
var scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
return Newtonsoft.Json.JsonConvert.SerializeObject(new {
    name = scene.name,
    path = scene.path
});
```

---

## 与其他 DCC 的差异

| 维度 | Unity | Maya/Max | UE |
|------|-------|----------|-----|
| 执行语言 | C# | Python | Python |
| MCP 工具名 | `run_unity_python` | `run_python` | `run_ue_python` |
| Python 位置 | 外置进程 | DCC 内置 | UE 内置 |
| 主线程桥接 | HTTP CommandServer | Qt 信号 | Slate tick |
