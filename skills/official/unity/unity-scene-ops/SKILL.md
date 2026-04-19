---
name: unity-scene-ops
description: >
  Unity Editor scene operations via run_unity_python MCP tool.
  Use when AI needs to: (1) get scene info or hierarchy, (2) open/save/create scenes,
  (3) find GameObjects by name, tag, or layer, (4) manage Build Settings scene list,
  (5) query scene statistics (object count, dirty state, path).
  NOT for: runtime scene loading (Application.LoadScene), asset creation, component editing.
license: MIT
metadata:
  artclaw:
    display_name: "Unity 场景操作"
    author: ArtClaw
    software: unity
    category: scene
    risk_level: low
    version: 1.0.0
    tags: ["unity", "scene", "hierarchy", "gameobject", "find"]
---

# Unity 场景操作

通过 `run_unity_python` 工具操控 Unity Editor 中的场景。

## 调用方式

所有操作通过 MCP 工具 `run_unity_python` 提交 **C# 代码片段**到 Unity 主线程执行。

```python
# MCP 调用格式
run_unity_python(code="<C# 代码>")
```

---

## 操作示例

### 获取当前场景信息

```csharp
var scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
return Newtonsoft.Json.JsonConvert.SerializeObject(new {
    name = scene.name,
    path = scene.path,
    isDirty = scene.isDirty,
    rootCount = scene.rootCount,
    isLoaded = scene.isLoaded
});
```

### 获取场景层级（所有 GameObject）

```csharp
var scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
var roots = scene.GetRootGameObjects();
var result = new System.Collections.Generic.List<object>();
foreach (var go in roots) {
    result.Add(new {
        name = go.name,
        active = go.activeSelf,
        childCount = go.transform.childCount,
        tag = go.tag,
        layer = go.layer
    });
}
return Newtonsoft.Json.JsonConvert.SerializeObject(result);
```

### 按名称查找 GameObject

```csharp
var go = UnityEngine.GameObject.Find("Player");
if (go == null) return "{\"found\": false}";
return Newtonsoft.Json.JsonConvert.SerializeObject(new {
    found = true,
    name = go.name,
    path = UnityEditor.AnimationUtility.CalculateTransformPath(go.transform, null),
    position = new { x = go.transform.position.x, y = go.transform.position.y, z = go.transform.position.z },
    active = go.activeSelf
});
```

### 按 Tag 查找所有 GameObject

```csharp
var objects = UnityEngine.GameObject.FindGameObjectsWithTag("Enemy");
var result = new System.Collections.Generic.List<object>();
foreach (var go in objects) {
    result.Add(new { name = go.name, active = go.activeSelf });
}
return Newtonsoft.Json.JsonConvert.SerializeObject(new { count = objects.Length, objects = result });
```

### 保存当前场景

```csharp
UnityEditor.SceneManagement.EditorSceneManager.SaveScene(
    UnityEngine.SceneManagement.SceneManager.GetActiveScene()
);
return "{\"saved\": true}";
```

### 新建场景

```csharp
var scene = UnityEditor.SceneManagement.EditorSceneManager.NewScene(
    UnityEditor.SceneManagement.NewSceneSetup.DefaultGameObjects,
    UnityEditor.SceneManagement.NewSceneMode.Single
);
return Newtonsoft.Json.JsonConvert.SerializeObject(new { name = scene.name, created = true });
```

### 打开场景

```csharp
// scenePath: Assets/Scenes/Main.unity
var scene = UnityEditor.SceneManagement.EditorSceneManager.OpenScene(
    "Assets/Scenes/Main.unity",
    UnityEditor.SceneManagement.OpenSceneMode.Single
);
return Newtonsoft.Json.JsonConvert.SerializeObject(new { name = scene.name, opened = true });
```

### 获取 Build Settings 场景列表

```csharp
var scenes = UnityEditor.EditorBuildSettings.scenes;
var result = new System.Collections.Generic.List<object>();
foreach (var s in scenes) {
    result.Add(new { path = s.path, enabled = s.enabled });
}
return Newtonsoft.Json.JsonConvert.SerializeObject(result);
```

### 将场景添加到 Build Settings

```csharp
// scenePath: Assets/Scenes/Level1.unity
var scenes = new System.Collections.Generic.List<UnityEditor.EditorBuildSettingsScene>(
    UnityEditor.EditorBuildSettings.scenes
);
scenes.Add(new UnityEditor.EditorBuildSettingsScene("Assets/Scenes/Level1.unity", true));
UnityEditor.EditorBuildSettings.scenes = scenes.ToArray();
return "{\"added\": true}";
```

---

## 注意事项

- `GameObject.Find` 只搜索激活的 GameObject；用 `Resources.FindObjectsOfTypeAll<GameObject>()` 可搜索非激活
- 保存场景后才能确保变更持久化，编写 AI 流程时建议操作完成后自动保存
- 打开场景会卸载当前场景（`Single` 模式），使用前确认用户意图
