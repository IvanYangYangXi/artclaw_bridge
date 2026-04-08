---
name: sp-bake-export
description: >
  SP 烘焙与导出工作流：烘焙贴图、配置导出预设、批量导出。
  Use when AI needs to: (1) bake texture maps, (2) export textures,
  (3) configure export settings.
  Substance Painter only (run_python).
metadata:
  artclaw:
    version: 0.0.1
    author: ArtClaw
    software: substance_painter
---

# SP 烘焙与导出

Substance Painter 贴图烘焙（Baking）和纹理导出（Export）工作流。

> ⚠️ **仅适用于 Substance Painter** — 通过 `run_python` 执行

---

## 贴图烘焙

### 烘焙所有纹理集的所有贴图

```python
import substance_painter.project
import substance_painter.baking

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    # 异步烘焙所有已选中的纹理集贴图
    # 返回一个可调用的 stop 函数，用于中止烘焙
    substance_painter.baking.bake_selected_textures_async()
    print("✅ 已启动所有纹理集烘焙（异步）")
```

### 烘焙指定纹理集

```python
import substance_painter.project
import substance_painter.textureset
import substance_painter.baking

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    # 获取指定纹理集
    ts = substance_painter.textureset.all_texture_sets()[0]

    # 异步烘焙该纹理集
    substance_painter.baking.bake_async(ts)
    print(f"✅ 纹理集 '{ts.name()}' 已启动烘焙（异步）")
```

### 烘焙贴图类型

SP 支持烘焙的常见贴图类型：

| 贴图类型 | 说明 |
|---|---|
| Normal | 法线贴图（从高模到低模） |
| AO (Ambient Occlusion) | 环境光遮蔽 |
| Curvature | 曲率贴图 |
| World Space Normal | 世界空间法线 |
| Position | 位置贴图 |
| Thickness | 厚度贴图 |
| ID | 材质 ID 贴图 |

### 配置烘焙参数

```python
import substance_painter.project
import substance_painter.textureset
import substance_painter.baking

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    # 通过 BakingParameters.from_texture_set() 获取烘焙参数
    ts = substance_painter.textureset.all_texture_sets()[0]
    params = substance_painter.baking.BakingParameters.from_texture_set(ts)
    print(f"当前烘焙参数: {params}")

    # 修改烘焙参数 — 使用 BakingParameters 对象的方法
    # 具体可用方法取决于 SP 版本
```

---

## 纹理导出

### 列出导出预设

```python
import substance_painter.project
import substance_painter.export

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    # 列出所有用户自定义的资源导出预设
    resource_presets = substance_painter.export.list_resource_export_presets()
    print("用户资源导出预设:")
    for preset in resource_presets:
        print(f"  {preset}")

    # 列出所有预定义的导出预设（如 UE4、Unity 等内置预设）
    predefined_presets = substance_painter.export.list_predefined_export_presets()
    print("预定义导出预设:")
    for preset in predefined_presets:
        print(f"  {preset}")
```

### 使用 JSON 配置导出

SP 的导出 API 使用 dict 格式的 JSON 配置，不存在 `ExportConfig` 类。

```python
import substance_painter.project
import substance_painter.textureset
import substance_painter.export

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    # 获取可用预设
    resource_presets = substance_painter.export.list_resource_export_presets()
    predefined_presets = substance_painter.export.list_predefined_export_presets()

    # 选择一个预设（优先用资源预设，否则用预定义预设）
    all_presets = resource_presets + predefined_presets
    # 按名称过滤（例如查找 UE4 预设）
    target_preset = None
    for p in all_presets:
        if "Unreal" in str(p) or "UE4" in str(p):
            target_preset = p
            break
    if not target_preset and all_presets:
        target_preset = all_presets[0]

    # 构建 JSON 配置（dict 格式）
    json_config = {
        "exportShaderParams": [],
        "exportPath": "D:/Export/Textures",
        "exportList": [],
        "defaultExportPreset": str(target_preset) if target_preset else "",
        "exportParameters": [
            {
                "parameters": {
                    "fileFormat": "png",    # png, tga, exr, tiff, psd 等
                    "sizeLog2": 11,         # 2^11 = 2048
                    "paddingAlgorithm": "diffusion",
                    "dilationDistance": 16
                }
            }
        ]
    }

    # 添加要导出的纹理集
    all_ts = substance_painter.textureset.all_texture_sets()
    for ts in all_ts:
        json_config["exportList"].append({"rootPath": ts.name()})

    # 执行导出
    result = substance_painter.export.export_project_textures(json_config)
    if result.status == substance_painter.export.ExportStatus.Success:
        # result.textures 是 Dict[Tuple[str,str], List[str]]
        # key 是 (纹理集名, 栈名)，value 是文件路径列表
        total_files = sum(len(files) for files in result.textures.values())
        print(f"✅ 导出成功，共 {total_files} 个文件")
        for (ts_name, stack_name), file_list in result.textures.items():
            for f in file_list:
                print(f"  [{ts_name}] {f}")
    else:
        print(f"❌ 导出失败: {result.message}")
```

---

## 常用导出预设

使用 `list_resource_export_presets()` 和 `list_predefined_export_presets()` 获取完整预设列表。

常见预定义预设名称：

| 预设名称 | 适用引擎/场景 |
|---|---|
| `Unreal Engine 4 (Packed)` | UE4/UE5 — ORM 打包格式 |
| `Unity 5 (Standard Metallic)` | Unity — Standard 材质 |
| `PBR Metallic Roughness` | 通用 PBR |
| `glTF PBR Metal Roughness` | glTF/WebGL |

---

## 常用导出格式

在 JSON 配置的 `fileFormat` 字段中指定（字符串），不存在 `ExportFormat` 枚举类。

| 格式 | 配置值 | 说明 |
|---|---|---|
| PNG | `"png"` | 通用无损 |
| TGA | `"tga"` | 游戏行业常用 |
| EXR | `"exr"` | HDR 高动态范围 |
| TIFF | `"tiff"` | 印刷/高品质 |
| PSD | `"psd"` | Photoshop 兼容 |

---

## 完整工作流示例：烘焙 + 导出

```python
import substance_painter.project
import substance_painter.textureset
import substance_painter.baking
import substance_painter.export

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    # 1. 先保存项目
    substance_painter.project.save()
    print("✅ 项目已保存")

    # 2. 烘焙所有贴图（异步）
    substance_painter.baking.bake_selected_textures_async()
    print("✅ 已启动贴图烘焙")

    # 3. 构建导出配置（dict 格式）
    all_ts = substance_painter.textureset.all_texture_sets()
    json_config = {
        "exportShaderParams": [],
        "exportPath": "D:/Export/FinalTextures",
        "exportList": [{"rootPath": ts.name()} for ts in all_ts],
        "defaultExportPreset": "",
        "exportParameters": [
            {
                "parameters": {
                    "fileFormat": "png",
                    "sizeLog2": 11,
                    "paddingAlgorithm": "diffusion",
                    "dilationDistance": 16
                }
            }
        ]
    }

    result = substance_painter.export.export_project_textures(json_config)
    if result.status == substance_painter.export.ExportStatus.Success:
        # result.textures 是 Dict[Tuple[str,str], List[str]]
        total_files = sum(len(files) for files in result.textures.values())
        print(f"✅ 导出完成，共 {total_files} 个文件")
        for (ts_name, stack_name), file_list in result.textures.items():
            for f in file_list:
                print(f"  [{ts_name}] {f}")
    else:
        print(f"❌ 导出失败: {result.message}")

    print("✅ 烘焙 + 导出工作流完成")
```

---

## 使用建议

- 烘焙前确保已设置好高模（如有），否则只能烘焙 AO、Curvature 等不需要高模的贴图
- 导出前先 `list_resource_export_presets()` 或 `list_predefined_export_presets()` 查看可用预设
- 导出使用 `export_project_textures(json_config)`，参数是 dict 格式的 JSON 配置
- `result.textures` 是 `Dict[Tuple[str,str], List[str]]`，key 为 `(纹理集名, 栈名)`
- 烘焙 API 是异步的：`bake_async(ts)` 和 `bake_selected_textures_async()`
- 烘焙参数通过 `BakingParameters.from_texture_set(ts)` 获取
- 批量导出多个纹理集时，所有纹理集共享同一导出配置
- 导出路径不存在时 SP 会自动创建目录
