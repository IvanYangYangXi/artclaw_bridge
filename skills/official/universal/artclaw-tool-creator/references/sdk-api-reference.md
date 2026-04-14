# artclaw_sdk API Reference

ArtClaw SDK 为工具脚本提供跨 DCC 的统一 API。这是 AI 生成工具脚本时的参考文档。

## 重要说明

这是计划中的 artclaw_sdk API 设计文档，实际 SDK 实现正在开发中。文档描述了 SDK 将提供的 API 接口，作为工具脚本编写的指导。

## 核心模块

### 上下文获取

#### `sdk.get_context() → dict`

获取当前 DCC 环境信息。

**返回值**：
```python
{
    "dcc": "maya"|"ue57"|"max"|"blender"|"comfyui"|"substance-designer"|"substance-painter",
    "version": "2024.0"|"5.7"|"2025"|"4.2"|"1.0"|"2024.1"|"2024.1",
    "scene": "/path/to/current/scene.ma"|"Level1.umap"|"scene.max"|"scene.blend"|None,
    "selected_count": 5
}
```

**示例**：
```python
context = sdk.get_context()
if context["dcc"] != "maya":
    return sdk.result.fail("WRONG_DCC", "此工具仅支持 Maya")
```

#### `sdk.get_selected() → List[SDKObject]`

获取当前选中的对象列表。跨 DCC 统一接口，无需直接调用 DCC API。

**示例**：
```python
selected = sdk.get_selected()
if not selected:
    return sdk.result.fail("NO_SELECTION", "请先选择要处理的对象")
    
for obj in selected:
    print(f"处理对象: {obj.name} (类型: {obj.type})")
```

#### `sdk.get_scene_path() → str`

获取当前场景文件路径。

**返回值**：完整的文件路径字符串，如果未保存则返回空字符串。

## 对象模型

### SDKObject

跨 DCC 的统一对象表示。

**属性**：

- **`name: str`** - 对象名称
- **`type: str`** - 对象类型
  - Maya: `"transform"`, `"mesh"`, `"nurbsCurve"`, `"camera"` 等
  - UE: `"StaticMesh"`, `"SkeletalMesh"`, `"Blueprint"`, `"Material"` 等
  - Blender: `"MESH"`, `"CURVE"`, `"CAMERA"`, `"LIGHT"` 等
- **`path: str`** - 对象在 DCC 中的完整路径
  - Maya: `"|group1|pCube1"`
  - UE: `"/Game/Models/Cube"`
  - Blender: `"Collection/Cube"`

**示例**：
```python
for obj in sdk.get_selected():
    print(f"名称: {obj.name}")
    print(f"类型: {obj.type}")
    print(f"路径: {obj.path}")
```

## 过滤功能

### `sdk.filter_objects(objects, type=None, name_pattern=None, path_pattern=None) → List[SDKObject]`

根据条件过滤对象列表。

**参数**：
- **`objects`**: 要过滤的 SDKObject 列表
- **`type`**: 按类型过滤（字符串或列表）
- **`name_pattern`**: 按名称模式过滤（支持通配符 `*` 和 `?`）
- **`path_pattern`**: 按路径模式过滤（支持通配符）

**示例**：
```python
all_objects = sdk.get_selected()

# 只处理网格对象
meshes = sdk.filter_objects(all_objects, type=["mesh", "MESH", "StaticMesh"])

# 只处理以 SM_ 开头的对象
static_meshes = sdk.filter_objects(all_objects, name_pattern="SM_*")

# 只处理特定路径下的对象
props = sdk.filter_objects(all_objects, path_pattern="*/Props/*")
```

## 参数处理

### `sdk.parse_params(manifest_inputs, raw_params) → dict`

解析和验证用户输入的参数，应用类型转换和默认值。

**参数**：
- **`manifest_inputs`**: manifest.json 中定义的 inputs 列表
- **`raw_params`**: 用户输入的原始参数字典

**返回值**：解析后的参数字典，包含类型转换和默认值。

**示例**：
```python
def my_tool(raw_params):
    manifest_inputs = [
        {"id": "prefix", "type": "string", "default": "SM_", "required": True},
        {"id": "count", "type": "number", "default": 1},
        {"id": "enabled", "type": "boolean", "default": True}
    ]
    
    params = sdk.parse_params(manifest_inputs, raw_params)
    prefix = params["prefix"]    # 确保是字符串
    count = params["count"]      # 确保是数值
    enabled = params["enabled"]  # 确保是布尔值
```

## 结果返回

### `sdk.result.success(data=None, message="") → ResultSuccess`

返回成功结果。

**参数**：
- **`data`**: 结果数据（字典）
- **`message`**: 成功消息

**示例**：
```python
return sdk.result.success(
    data={"processedCount": 10, "files": ["a.fbx", "b.fbx"]},
    message="成功处理 10 个对象"
)
```

### `sdk.result.fail(error="", message="") → ResultFail`

返回失败结果。

**参数**：
- **`error`**: 错误代码（如 `"INVALID_SELECTION"`）
- **`message`**: 错误消息

**示例**：
```python
return sdk.result.fail(
    error="EXPORT_FAILED",
    message="导出失败：目标路径不存在"
)
```

### 触发器专用返回值

用于事件触发器中的 pre 事件：

#### `sdk.result.allow() → ResultAllow`

允许原操作继续执行。

#### `sdk.result.reject(reason) → ResultReject`

阻止原操作执行。

**示例**：
```python
# 保存前命名检查
def check_naming_before_save():
    selected = sdk.get_selected()
    for obj in selected:
        if not obj.name.startswith("SM_"):
            return sdk.result.reject(f"对象 {obj.name} 不符合命名规范")
    
    return sdk.result.allow()
```

## 进度跟踪

用于需要处理多个项目的长时间操作。

### `sdk.progress.start(total) → None`

开始进度跟踪。

**参数**：
- **`total`**: 总项目数

### `sdk.progress.update(current, message="") → None`

更新进度。

**参数**：
- **`current`**: 当前完成数
- **`message`**: 进度消息（可选）

### `sdk.progress.finish() → None`

结束进度跟踪。

**示例**：
```python
def batch_export(objects, export_path):
    sdk.progress.start(total=len(objects))
    
    exported = []
    for i, obj in enumerate(objects):
        # 执行导出操作
        filename = f"{obj.name}.fbx"
        # ... 导出逻辑 ...
        exported.append(filename)
        
        sdk.progress.update(i + 1, message=f"导出 {obj.name}")
    
    sdk.progress.finish()
    return sdk.result.success(data={"files": exported})
```

## 日志输出

### `sdk.log.info(message) → None`

记录信息日志。

### `sdk.log.warning(message) → None`

记录警告日志。

### `sdk.log.error(message) → None`

记录错误日志。

**示例**：
```python
sdk.log.info("开始批量处理")
sdk.log.warning("对象名称不规范，将自动修正")
sdk.log.error("导出失败")
```

## DCC 操作

### `sdk.rename_object(obj, new_name) → bool`

重命名对象。

**参数**：
- **`obj`**: SDKObject 实例
- **`new_name`**: 新名称

**返回值**：成功返回 True，失败返回 False

**示例**：
```python
for obj in selected:
    new_name = f"SM_{obj.name}"
    if sdk.rename_object(obj, new_name):
        sdk.log.info(f"重命名 {obj.name} → {new_name}")
```

### `sdk.delete_objects(objects) → int`

删除对象。

**参数**：
- **`objects`**: SDKObject 列表

**返回值**：实际删除的对象数量

**示例**：
```python
temp_objects = sdk.filter_objects(all_objects, name_pattern="temp_*")
deleted_count = sdk.delete_objects(temp_objects)
```

### `sdk.duplicate_objects(objects) → List[SDKObject]`

复制对象。

**参数**：
- **`objects`**: 要复制的 SDKObject 列表

**返回值**：新创建的对象列表

**示例**：
```python
selected = sdk.get_selected()
duplicates = sdk.duplicate_objects(selected)
for dup in duplicates:
    sdk.rename_object(dup, f"Copy_{dup.name}")
```

## 文件操作

### `sdk.export_selected(path, format="fbx") → bool`

导出选中对象到文件。

**参数**：
- **`path`**: 导出文件路径
- **`format`**: 导出格式（"fbx", "obj", "usd" 等）

**返回值**：成功返回 True，失败返回 False

**示例**：
```python
if sdk.export_selected("/path/to/export/model.fbx", format="fbx"):
    sdk.log.info("导出成功")
else:
    return sdk.result.fail("EXPORT_FAILED", "导出失败")
```

### `sdk.import_file(path) → List[SDKObject]`

导入文件到当前场景。

**参数**：
- **`path`**: 要导入的文件路径

**返回值**：导入的对象列表

**示例**：
```python
imported_objects = sdk.import_file("/path/to/model.fbx")
sdk.log.info(f"导入了 {len(imported_objects)} 个对象")
```

## 完整示例

一个典型的工具脚本结构：

```python
"""批量重命名工具 - 由 Tool Creator 生成"""
import artclaw_sdk as sdk

def batch_rename_objects(prefix="SM_", use_number=True, start_number=1):
    """批量重命名选中对象"""
    
    # 1. 验证环境和选择
    context = sdk.get_context()
    sdk.log.info(f"当前 DCC: {context['dcc']} {context['version']}")
    
    selected = sdk.get_selected()
    if not selected:
        return sdk.result.fail("NO_SELECTION", "请先选择要重命名的对象")
    
    # 2. 过滤对象（可选）
    valid_objects = sdk.filter_objects(selected, type=["mesh", "transform", "StaticMesh"])
    if not valid_objects:
        return sdk.result.fail("NO_VALID_OBJECTS", "选中对象中没有可重命名的类型")
    
    # 3. 开始处理
    sdk.progress.start(total=len(valid_objects))
    renamed_count = 0
    
    for i, obj in enumerate(valid_objects):
        # 生成新名称
        if use_number:
            new_name = f"{prefix}{obj.name}_{start_number + i:02d}"
        else:
            new_name = f"{prefix}{obj.name}"
        
        # 执行重命名
        if sdk.rename_object(obj, new_name):
            renamed_count += 1
            sdk.log.info(f"重命名: {obj.name} → {new_name}")
        else:
            sdk.log.warning(f"重命名失败: {obj.name}")
        
        sdk.progress.update(i + 1, message=f"处理 {obj.name}")
    
    sdk.progress.finish()
    
    # 4. 返回结果
    return sdk.result.success(
        data={
            "renamedCount": renamed_count,
            "totalCount": len(valid_objects),
            "prefix": prefix
        },
        message=f"成功重命名 {renamed_count}/{len(valid_objects)} 个对象"
    )
```

## 错误处理最佳实践

1. **早期验证**：在执行操作前验证环境、选择和参数
2. **清晰错误码**：使用有意义的错误代码如 `"NO_SELECTION"`、`"INVALID_PATH"`
3. **有用的消息**：提供可操作的错误消息
4. **优雅失败**：部分成功时也要报告结果

## 性能建议

1. **批量操作**：尽量批量处理而不是逐个操作
2. **进度反馈**：长时间操作使用 `sdk.progress`
3. **早期退出**：条件不满足时立即返回
4. **资源释放**：确保资源正确释放（SDK 会自动处理）

这个 API 参考覆盖了工具脚本开发的核心需求。实际 SDK 实现会提供更多专用功能，但这个接口集合足以支持大部分工具开发场景。