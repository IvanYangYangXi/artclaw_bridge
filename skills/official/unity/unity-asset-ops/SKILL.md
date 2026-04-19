---
name: unity-asset-ops
description: >
  Unity Editor asset management via run_unity_python: import, find, create, move, and delete assets.
  Use when AI needs to: (1) search assets by type or name (AssetDatabase.FindAssets), (2) import
  external files, (3) instantiate prefabs in scene, (4) create prefabs from GameObjects, (5) create
  materials and assign shaders, (6) move/rename/delete assets, (7) refresh AssetDatabase,
  (8) get asset info (path, GUID, type).
  NOT for: modifying component properties (use unity-component-ops), scene hierarchy (use unity-gameobject-ops).
license: MIT
metadata:
  artclaw:
    display_name: "Unity 资产操作"
    author: ArtClaw
    software: unity
    category: asset
    risk_level: medium
    version: 1.0.0
    tags: ["unity", "asset", "prefab", "material", "import", "assetdatabase"]
---

# Unity 资产操作

通过 `run_unity_python` 在 Unity Editor 中管理资产（Asset）。

## 调用方式

```python
run_unity_python(code="<C# 代码>")
```

---

## 操作示例

### 搜索资产（按类型）

```csharp
// type: Prefab / Material / Texture2D / AudioClip / AnimationClip / Script ...
var guids = UnityEditor.AssetDatabase.FindAssets("t:Prefab", new[] { "Assets" });
var result = new System.Collections.Generic.List<object>();
foreach (var guid in guids) {
    var path = UnityEditor.AssetDatabase.GUIDToAssetPath(guid);
    result.Add(new { guid = guid, path = path, name = System.IO.Path.GetFileNameWithoutExtension(path) });
}
return Newtonsoft.Json.JsonConvert.SerializeObject(new { count = guids.Length, assets = result });
```

### 按名称搜索资产

```csharp
// 搜索名为 "Player" 的所有资产
var guids = UnityEditor.AssetDatabase.FindAssets("Player", new[] { "Assets" });
var result = new System.Collections.Generic.List<object>();
foreach (var guid in guids) {
    var path = UnityEditor.AssetDatabase.GUIDToAssetPath(guid);
    var type = UnityEditor.AssetDatabase.GetMainAssetTypeAtPath(path);
    result.Add(new { path = path, type = type?.Name ?? "Unknown" });
}
return Newtonsoft.Json.JsonConvert.SerializeObject(result);
```

### 在场景中实例化 Prefab

```csharp
// prefabPath: Assets/Prefabs/Enemy.prefab
var prefab = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>("Assets/Prefabs/Enemy.prefab");
if (prefab == null) return "{\"error\": \"Prefab not found\"}";
var instance = (UnityEngine.GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(prefab);
instance.name = "Enemy";
instance.transform.position = UnityEngine.Vector3.zero;
UnityEditor.Undo.RegisterCreatedObjectUndo(instance, "Instantiate Prefab");
return Newtonsoft.Json.JsonConvert.SerializeObject(new {
    instantiated = true,
    name = instance.name,
    instanceId = instance.GetInstanceID()
});
```

### 将 GameObject 保存为 Prefab

```csharp
// goName: 场景中的 GameObject 名, savePath: Assets/Prefabs/MyPrefab.prefab
var go = UnityEngine.GameObject.Find("MyObject");
if (go == null) return "{\"error\": \"GameObject not found\"}";
var prefab = UnityEditor.PrefabUtility.SaveAsPrefabAsset(go, "Assets/Prefabs/MyPrefab.prefab");
return Newtonsoft.Json.JsonConvert.SerializeObject(new {
    created = true,
    path = UnityEditor.AssetDatabase.GetAssetPath(prefab)
});
```

### 创建材质

```csharp
// 创建使用 Standard shader 的材质
var mat = new UnityEngine.Material(UnityEngine.Shader.Find("Standard"));
mat.color = UnityEngine.Color.red;
UnityEditor.AssetDatabase.CreateAsset(mat, "Assets/Materials/RedMaterial.mat");
UnityEditor.AssetDatabase.SaveAssets();
return Newtonsoft.Json.JsonConvert.SerializeObject(new {
    created = true,
    path = "Assets/Materials/RedMaterial.mat"
});
```

### 给 Renderer 设置材质

```csharp
// goName: GameObject 名, matPath: 材质资产路径
var go = UnityEngine.GameObject.Find("Cube");
var renderer = go?.GetComponent<UnityEngine.MeshRenderer>();
if (renderer == null) return "{\"error\": \"MeshRenderer not found\"}";
var mat = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Material>("Assets/Materials/RedMaterial.mat");
if (mat == null) return "{\"error\": \"Material not found\"}";
UnityEditor.Undo.RecordObject(renderer, "Set Material");
renderer.sharedMaterial = mat;
return "{\"success\": true}";
```

### 移动/重命名资产

```csharp
// oldPath → newPath
var error = UnityEditor.AssetDatabase.MoveAsset(
    "Assets/Textures/old_name.png",
    "Assets/Textures/new_name.png"
);
if (!string.IsNullOrEmpty(error)) return Newtonsoft.Json.JsonConvert.SerializeObject(new { error = error });
return "{\"moved\": true}";
```

### 删除资产

```csharp
// path: Assets/Temp/unwanted.prefab
bool deleted = UnityEditor.AssetDatabase.DeleteAsset("Assets/Temp/unwanted.prefab");
return Newtonsoft.Json.JsonConvert.SerializeObject(new { deleted = deleted });
```

### 刷新资产数据库

```csharp
UnityEditor.AssetDatabase.Refresh();
return "{\"refreshed\": true}";
```

### 获取资产信息

```csharp
var path = "Assets/Prefabs/Player.prefab";
var guid = UnityEditor.AssetDatabase.AssetPathToGUID(path);
var type = UnityEditor.AssetDatabase.GetMainAssetTypeAtPath(path);
var importer = UnityEditor.AssetImporter.GetAtPath(path);
return Newtonsoft.Json.JsonConvert.SerializeObject(new {
    path = path,
    guid = guid,
    type = type?.Name ?? "Unknown",
    importerType = importer?.GetType().Name ?? "None"
});
```

---

## AssetDatabase.FindAssets 搜索语法

| 过滤器 | 示例 | 说明 |
|--------|------|------|
| `t:TYPE` | `t:Prefab` | 按资产类型 |
| `l:LABEL` | `l:Enemy` | 按标签 |
| 名称 | `Player` | 按名称模糊搜索 |
| 组合 | `Enemy t:Prefab` | 名称+类型组合 |

## 注意事项

- 资产路径必须以 `Assets/` 开头
- 创建/修改资产后调用 `AssetDatabase.SaveAssets()` 确保写入磁盘
- 删除资产不可撤销，需用户确认后再执行
- `risk_level: medium` — 资产删除/移动操作不可撤销，执行前需确认
