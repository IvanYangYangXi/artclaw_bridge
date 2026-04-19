---
name: unity-gameobject-ops
description: >
  Unity Editor GameObject creation, deletion, transform, and hierarchy operations via run_unity_python.
  Use when AI needs to: (1) create/delete/duplicate GameObjects, (2) set position/rotation/scale,
  (3) get or set parent-child relationships, (4) set active state, (5) get current editor selection,
  (6) rename GameObjects, (7) move objects in hierarchy.
  NOT for: adding/removing components (use unity-component-ops), asset operations (use unity-asset-ops).
license: MIT
metadata:
  artclaw:
    display_name: "Unity GameObject 操作"
    author: ArtClaw
    software: unity
    category: scene
    risk_level: low
    version: 1.0.0
    tags: ["unity", "gameobject", "transform", "hierarchy", "selection", "create", "delete"]
---

# Unity GameObject 操作

通过 `run_unity_python` 在 Unity Editor 中创建、修改、删除 GameObject。

## 调用方式

```python
run_unity_python(code="<C# 代码>")
```

---

## 操作示例

### 获取当前选中的 GameObject

```csharp
var selection = UnityEditor.Selection.gameObjects;
var result = new System.Collections.Generic.List<object>();
foreach (var go in selection) {
    result.Add(new {
        name = go.name,
        instanceId = go.GetInstanceID(),
        active = go.activeSelf,
        tag = go.tag,
        layer = UnityEngine.LayerMask.LayerToName(go.layer),
        position = new { x = go.transform.position.x, y = go.transform.position.y, z = go.transform.position.z }
    });
}
return Newtonsoft.Json.JsonConvert.SerializeObject(new { count = selection.Length, objects = result });
```

### 创建空 GameObject

```csharp
// name: 要创建的对象名称
var go = new UnityEngine.GameObject("NewObject");
UnityEditor.Undo.RegisterCreatedObjectUndo(go, "Create GameObject");
UnityEditor.Selection.activeGameObject = go;
return Newtonsoft.Json.JsonConvert.SerializeObject(new {
    created = true,
    name = go.name,
    instanceId = go.GetInstanceID()
});
```

### 创建带基础组件的 GameObject（Cube/Sphere/Capsule 等）

```csharp
// primitive: Cube / Sphere / Capsule / Cylinder / Plane / Quad
var go = UnityEngine.GameObject.CreatePrimitive(UnityEngine.PrimitiveType.Cube);
go.name = "MyCube";
UnityEditor.Undo.RegisterCreatedObjectUndo(go, "Create Primitive");
return Newtonsoft.Json.JsonConvert.SerializeObject(new { created = true, name = go.name });
```

### 删除 GameObject

```csharp
// 按名称找到并删除
var go = UnityEngine.GameObject.Find("TargetObject");
if (go != null) {
    UnityEditor.Undo.DestroyObjectImmediate(go);
    return "{\"deleted\": true}";
}
return "{\"deleted\": false, \"error\": \"GameObject not found\"}";
```

### 复制 GameObject

```csharp
var go = UnityEngine.GameObject.Find("SourceObject");
if (go == null) return "{\"error\": \"Source not found\"}";
var copy = UnityEngine.Object.Instantiate(go);
copy.name = go.name + "_Copy";
UnityEditor.Undo.RegisterCreatedObjectUndo(copy, "Duplicate GameObject");
return Newtonsoft.Json.JsonConvert.SerializeObject(new { duplicated = true, newName = copy.name });
```

### 设置 Transform（位置/旋转/缩放）

```csharp
var go = UnityEngine.GameObject.Find("Player");
if (go == null) return "{\"error\": \"Not found\"}";
UnityEditor.Undo.RecordObject(go.transform, "Set Transform");
go.transform.position = new UnityEngine.Vector3(0f, 1f, 0f);
go.transform.eulerAngles = new UnityEngine.Vector3(0f, 90f, 0f);
go.transform.localScale = new UnityEngine.Vector3(1f, 1f, 1f);
return "{\"success\": true}";
```

### 获取 Transform

```csharp
var go = UnityEngine.GameObject.Find("Player");
if (go == null) return "{\"error\": \"Not found\"}";
var t = go.transform;
return Newtonsoft.Json.JsonConvert.SerializeObject(new {
    position = new { x = t.position.x, y = t.position.y, z = t.position.z },
    rotation = new { x = t.eulerAngles.x, y = t.eulerAngles.y, z = t.eulerAngles.z },
    localScale = new { x = t.localScale.x, y = t.localScale.y, z = t.localScale.z }
});
```

### 设置父子关系

```csharp
var child = UnityEngine.GameObject.Find("ChildObject");
var parent = UnityEngine.GameObject.Find("ParentObject");
if (child == null || parent == null) return "{\"error\": \"Object not found\"}";
UnityEditor.Undo.SetTransformParent(child.transform, parent.transform, "Set Parent");
return "{\"success\": true}";
```

### 设置激活状态

```csharp
var go = UnityEngine.GameObject.Find("TargetObject");
if (go == null) return "{\"error\": \"Not found\"}";
UnityEditor.Undo.RecordObject(go, "Set Active");
go.SetActive(false);  // 或 true
return Newtonsoft.Json.JsonConvert.SerializeObject(new { activeSelf = go.activeSelf });
```

### 重命名 GameObject

```csharp
var go = UnityEngine.GameObject.Find("OldName");
if (go == null) return "{\"error\": \"Not found\"}";
UnityEditor.Undo.RecordObject(go, "Rename");
go.name = "NewName";
return "{\"success\": true}";
```

### 批量查询场景中所有 GameObject

```csharp
// 包括非激活的 GameObject
var all = UnityEngine.Object.FindObjectsOfType<UnityEngine.GameObject>(true);
var result = new System.Collections.Generic.List<object>();
foreach (var go in all) {
    result.Add(new {
        name = go.name,
        active = go.activeSelf,
        tag = go.tag,
        layer = UnityEngine.LayerMask.LayerToName(go.layer),
        childCount = go.transform.childCount
    });
}
return Newtonsoft.Json.JsonConvert.SerializeObject(new { count = all.Length, objects = result });
```

---

## 注意事项

- **始终使用 `Undo.RecordObject` / `Undo.RegisterCreatedObjectUndo`**：让操作支持 Ctrl+Z 撤销
- `GameObject.Find` 只能找到激活的对象；`FindObjectsOfType<GameObject>(true)` 可包含非激活
- 删除操作使用 `Undo.DestroyObjectImmediate` 而非 `Object.DestroyImmediate`，支持撤销
