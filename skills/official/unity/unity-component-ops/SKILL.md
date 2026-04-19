---
name: unity-component-ops
description: >
  Unity Editor component management: add, remove, get, and modify components on GameObjects
  via run_unity_python. Use when AI needs to: (1) add components (Rigidbody, Collider, Light,
  Camera, AudioSource, etc.), (2) remove components, (3) get component property values,
  (4) set component property values (serialized fields), (5) list all components on a GameObject.
  NOT for: creating GameObjects (use unity-gameobject-ops), script creation (use unity-editor-control).
license: MIT
metadata:
  artclaw:
    display_name: "Unity 组件操作"
    author: ArtClaw
    software: unity
    category: scene
    risk_level: low
    version: 1.0.0
    tags: ["unity", "component", "rigidbody", "collider", "light", "camera", "monobehaviour"]
---

# Unity 组件操作

通过 `run_unity_python` 在 Unity Editor 中管理 GameObject 组件。

## 调用方式

```python
run_unity_python(code="<C# 代码>")
```

---

## 操作示例

### 列出 GameObject 所有组件

```csharp
var go = UnityEngine.GameObject.Find("Player");
if (go == null) return "{\"error\": \"Not found\"}";
var components = go.GetComponents<UnityEngine.Component>();
var result = new System.Collections.Generic.List<object>();
foreach (var c in components) {
    result.Add(new {
        type = c.GetType().Name,
        fullType = c.GetType().FullName,
        enabled = (c is UnityEngine.Behaviour b) ? (bool?)b.enabled : null
    });
}
return Newtonsoft.Json.JsonConvert.SerializeObject(new { count = components.Length, components = result });
```

### 添加 Rigidbody

```csharp
var go = UnityEngine.GameObject.Find("Player");
if (go == null) return "{\"error\": \"Not found\"}";
if (go.GetComponent<UnityEngine.Rigidbody>() != null) return "{\"exists\": true}";
var rb = UnityEditor.Undo.AddComponent<UnityEngine.Rigidbody>(go);
return Newtonsoft.Json.JsonConvert.SerializeObject(new { added = true, mass = rb.mass, useGravity = rb.useGravity });
```

### 添加 BoxCollider

```csharp
var go = UnityEngine.GameObject.Find("Wall");
var col = UnityEditor.Undo.AddComponent<UnityEngine.BoxCollider>(go);
col.size = new UnityEngine.Vector3(1f, 1f, 1f);
return "{\"added\": true}";
```

### 添加 Light

```csharp
var go = UnityEngine.GameObject.Find("LightObj");
var light = UnityEditor.Undo.AddComponent<UnityEngine.Light>(go);
light.type = UnityEngine.LightType.Point;
light.color = UnityEngine.Color.white;
light.intensity = 1.0f;
light.range = 10f;
return Newtonsoft.Json.JsonConvert.SerializeObject(new {
    added = true, type = light.type.ToString(), intensity = light.intensity, range = light.range
});
```

### 添加 Camera

```csharp
var go = UnityEngine.GameObject.Find("MainCam");
var cam = UnityEditor.Undo.AddComponent<UnityEngine.Camera>(go);
cam.fieldOfView = 60f;
cam.nearClipPlane = 0.1f;
cam.farClipPlane = 1000f;
return "{\"added\": true}";
```

### 移除组件

```csharp
var go = UnityEngine.GameObject.Find("Player");
var rb = go?.GetComponent<UnityEngine.Rigidbody>();
if (rb == null) return "{\"error\": \"Component not found\"}";
UnityEditor.Undo.DestroyObjectImmediate(rb);
return "{\"removed\": true}";
```

### 获取组件属性（以 Rigidbody 为例）

```csharp
var go = UnityEngine.GameObject.Find("Player");
var rb = go?.GetComponent<UnityEngine.Rigidbody>();
if (rb == null) return "{\"error\": \"Rigidbody not found\"}";
return Newtonsoft.Json.JsonConvert.SerializeObject(new {
    mass = rb.mass,
    drag = rb.drag,
    angularDrag = rb.angularDrag,
    useGravity = rb.useGravity,
    isKinematic = rb.isKinematic
});
```

### 修改组件属性（Rigidbody）

```csharp
var go = UnityEngine.GameObject.Find("Player");
var rb = go?.GetComponent<UnityEngine.Rigidbody>();
if (rb == null) return "{\"error\": \"Rigidbody not found\"}";
UnityEditor.Undo.RecordObject(rb, "Modify Rigidbody");
rb.mass = 2.0f;
rb.useGravity = true;
rb.isKinematic = false;
return "{\"success\": true}";
```

### 通过 SerializedObject 修改组件属性（通用方式）

```csharp
// 适用于修改任意序列化字段，包括自定义 MonoBehaviour
var go = UnityEngine.GameObject.Find("Player");
var comp = go?.GetComponent<UnityEngine.Rigidbody>();
if (comp == null) return "{\"error\": \"Component not found\"}";
var so = new UnityEditor.SerializedObject(comp);
var prop = so.FindProperty("m_Mass");
if (prop == null) return "{\"error\": \"Property not found\"}";
prop.floatValue = 5.0f;
so.ApplyModifiedProperties();
return "{\"success\": true, \"newValue\": 5.0}";
```

### 启用/禁用组件

```csharp
var go = UnityEngine.GameObject.Find("Enemy");
var renderer = go?.GetComponent<UnityEngine.MeshRenderer>();
if (renderer == null) return "{\"error\": \"MeshRenderer not found\"}";
UnityEditor.Undo.RecordObject(renderer, "Toggle Component");
renderer.enabled = false;  // 或 true
return Newtonsoft.Json.JsonConvert.SerializeObject(new { enabled = renderer.enabled });
```

---

## 常用组件类型速查

| 类型 | 完整名称 | 说明 |
|------|----------|------|
| `Rigidbody` | `UnityEngine.Rigidbody` | 3D 物理刚体 |
| `Rigidbody2D` | `UnityEngine.Rigidbody2D` | 2D 物理刚体 |
| `BoxCollider` | `UnityEngine.BoxCollider` | 盒型碰撞体 |
| `SphereCollider` | `UnityEngine.SphereCollider` | 球型碰撞体 |
| `MeshRenderer` | `UnityEngine.MeshRenderer` | 网格渲染器 |
| `MeshFilter` | `UnityEngine.MeshFilter` | 网格过滤器 |
| `Light` | `UnityEngine.Light` | 灯光 |
| `Camera` | `UnityEngine.Camera` | 相机 |
| `AudioSource` | `UnityEngine.AudioSource` | 音频源 |
| `Animator` | `UnityEngine.Animator` | 动画控制器 |
| `Canvas` | `UnityEngine.Canvas` | UI 画布 |

## 注意事项

- **使用 `Undo.AddComponent`** 而非 `go.AddComponent`：支持撤销
- **使用 `Undo.DestroyObjectImmediate`** 而非直接 Destroy：支持撤销
- 修改属性时用 `Undo.RecordObject` 或 `SerializedObject.ApplyModifiedProperties`
- `SerializedObject` 方式是最通用的属性修改方式，支持自定义 MonoBehaviour
