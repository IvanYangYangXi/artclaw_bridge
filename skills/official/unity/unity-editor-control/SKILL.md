---
name: unity-editor-control
description: >
  Unity Editor state control via run_unity_python: undo/redo, play mode, build, console,
  menu execution, and editor preferences. Use when AI needs to: (1) undo or redo editor operations,
  (2) enter/exit Play Mode, (3) trigger builds (Build Player), (4) read Unity console logs,
  (5) execute editor menu items, (6) refresh the project, (7) get editor/project preferences,
  (8) open editor windows or inspector.
  NOT for: scene operations (use unity-scene-ops), asset management (use unity-asset-ops).
license: MIT
metadata:
  artclaw:
    display_name: "Unity 编辑器控制"
    author: ArtClaw
    software: unity
    category: utils
    risk_level: low
    version: 1.0.0
    tags: ["unity", "editor", "undo", "redo", "play-mode", "build", "console", "menu"]
---

# Unity 编辑器控制

通过 `run_unity_python` 控制 Unity Editor 状态：撤销、Play Mode、构建、控制台日志等。

## 调用方式

```python
run_unity_python(code="<C# 代码>")
```

---

## 操作示例

### 撤销（Undo）

```csharp
UnityEditor.Undo.PerformUndo();
return "{\"undone\": true}";
```

### 重做（Redo）

```csharp
UnityEditor.Undo.PerformRedo();
return "{\"redone\": true}";
```

### 获取当前 Undo 历史

```csharp
return Newtonsoft.Json.JsonConvert.SerializeObject(new {
    undoName = UnityEditor.Undo.GetCurrentGroupName(),
    undoGroupIndex = UnityEditor.Undo.GetCurrentGroup()
});
```

### 进入 Play Mode

```csharp
if (!UnityEditor.EditorApplication.isPlaying) {
    UnityEditor.EditorApplication.isPlaying = true;
    return "{\"entering_play_mode\": true}";
}
return "{\"already_playing\": true}";
```

### 退出 Play Mode

```csharp
if (UnityEditor.EditorApplication.isPlaying) {
    UnityEditor.EditorApplication.isPlaying = false;
    return "{\"exiting_play_mode\": true}";
}
return "{\"not_playing\": true}";
```

### 获取编辑器状态

```csharp
return Newtonsoft.Json.JsonConvert.SerializeObject(new {
    isPlaying = UnityEditor.EditorApplication.isPlaying,
    isPaused = UnityEditor.EditorApplication.isPaused,
    isCompiling = UnityEditor.EditorApplication.isCompiling,
    isUpdating = UnityEditor.EditorApplication.isUpdating,
    unityVersion = UnityEngine.Application.unityVersion,
    productName = UnityEngine.Application.productName,
    companyName = UnityEngine.Application.companyName,
    dataPath = UnityEngine.Application.dataPath
});
```

### 执行菜单项

```csharp
// 执行 Assets/Reimport All 菜单
UnityEditor.EditorApplication.ExecuteMenuItem("Assets/Reimport All");
return "{\"executed\": true}";
```

### 读取控制台日志

```csharp
// 通过 LogEntries 反射读取 Unity 控制台（Unity 内部 API）
var logEntriesType = System.Type.GetType("UnityEditor.LogEntries, UnityEditor");
var getCountMethod = logEntriesType?.GetMethod("GetCount");
var getEntryMethod = logEntriesType?.GetMethod("GetEntryInternal");
int count = (int)(getCountMethod?.Invoke(null, null) ?? 0);
return Newtonsoft.Json.JsonConvert.SerializeObject(new { logCount = count });
```

### 刷新项目（等价于 Ctrl+R）

```csharp
UnityEditor.AssetDatabase.Refresh();
return "{\"refreshed\": true}";
```

### 触发构建（Build Player）

```csharp
// 警告：构建操作耗时，会阻塞编辑器
var buildOptions = new UnityEditor.BuildPlayerOptions {
    scenes = new[] { "Assets/Scenes/Main.unity" },
    locationPathName = "Builds/MyGame.exe",
    target = UnityEditor.BuildTarget.StandaloneWindows64,
    options = UnityEditor.BuildOptions.None
};
var report = UnityEditor.BuildPipeline.BuildPlayer(buildOptions);
return Newtonsoft.Json.JsonConvert.SerializeObject(new {
    result = report.summary.result.ToString(),
    totalErrors = report.summary.totalErrors,
    totalWarnings = report.summary.totalWarnings,
    outputPath = report.summary.outputPath
});
```

### 获取项目设置

```csharp
return Newtonsoft.Json.JsonConvert.SerializeObject(new {
    productName = UnityEditor.PlayerSettings.productName,
    companyName = UnityEditor.PlayerSettings.companyName,
    bundleVersion = UnityEditor.PlayerSettings.bundleVersion,
    apiCompatibilityLevel = UnityEditor.PlayerSettings.GetApiCompatibilityLevel(
        UnityEditor.EditorUserBuildSettings.selectedBuildTargetGroup
    ).ToString(),
    scriptingBackend = UnityEditor.PlayerSettings.GetScriptingBackend(
        UnityEditor.EditorUserBuildSettings.selectedBuildTargetGroup
    ).ToString(),
    activeBuildTarget = UnityEditor.EditorUserBuildSettings.activeBuildTarget.ToString()
});
```

### 打开 Prefab Stage（编辑 Prefab）

```csharp
var prefabAsset = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>("Assets/Prefabs/Enemy.prefab");
if (prefabAsset == null) return "{\"error\": \"Prefab not found\"}";
UnityEditor.SceneManagement.PrefabStageUtility.OpenPrefab("Assets/Prefabs/Enemy.prefab");
return "{\"opened\": true}";
```

### 聚焦 Game Object（在 Scene 视图中）

```csharp
var go = UnityEngine.GameObject.Find("Player");
if (go == null) return "{\"error\": \"Not found\"}";
UnityEditor.Selection.activeGameObject = go;
UnityEditor.SceneView.FrameLastActiveSceneView();
return "{\"focused\": true}";
```

---

## 注意事项

- **Play Mode 切换是异步的**，切换后的代码不能立即查询 Play Mode 状态
- **Build Player 会阻塞**，耗时可能数分钟，建议在 AI 提示用户等待后再触发
- **菜单项路径区分大小写**，路径来自 Unity 菜单栏的实际文字
- 正在编译时（`isCompiling == true`）不要触发场景操作，等待编译完成
