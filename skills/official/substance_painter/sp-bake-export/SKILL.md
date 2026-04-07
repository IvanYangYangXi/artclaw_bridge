---
name: sp-bake-export
description: >
  SP 烘焙与导出工作流：烘焙贴图、配置导出预设、批量导出。
  Use when AI needs to: (1) bake texture maps, (2) export textures,
  (3) configure export settings.
  Substance Painter only (run_python).
metadata:
  artclaw:
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
    # 烘焙所有纹理集的所有贴图
    substance_painter.baking.bake_all_texture_sets()
    print("✅ 所有纹理集烘焙完成")
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

    # 烘焙该纹理集
    substance_painter.baking.bake(ts)
    print(f"✅ 纹理集 '{ts.name()}' 烘焙完成")
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
import substance_painter.baking

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    # 获取当前烘焙参数
    params = substance_painter.baking.get_baking_parameters()
    print(f"当前烘焙参数: {params}")

    # 修改烘焙参数（具体可用字段取决于 SP 版本）
    # params["common"]["output_size"] = [2048, 2048]
    # substance_painter.baking.set_baking_parameters(params)
```

---

## 纹理导出

### 使用默认配置导出

```python
import substance_painter.project
import substance_painter.export

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    # 获取默认导出配置
    config = substance_painter.export.get_default_export_config()

    # 执行导出
    result = substance_painter.export.export_project_textures(config)

    if result.status == substance_painter.export.ExportStatus.Success:
        print("✅ 纹理导出成功")
        print(f"导出文件:")
        for file_path in result.textures:
            print(f"  {file_path}")
    else:
        print(f"❌ 导出失败: {result.message}")
```

### 列出导出预设

```python
import substance_painter.project
import substance_painter.export

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    # 列出所有可用的导出预设
    presets = substance_painter.export.list_export_presets()
    print("可用导出预设:")
    for preset in presets:
        print(f"  {preset}")
```

### 使用指定预设导出

```python
import substance_painter.project
import substance_painter.export
import substance_painter.textureset

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    # 构建自定义导出配置
    export_preset = substance_painter.export.ResourceExportPreset.from_name(
        "Unreal Engine 4 (Packed)"  # 预设名称
    )

    config = substance_painter.export.ExportConfig()
    config.export_preset = export_preset
    config.export_path = "D:/Export/Textures"

    # 添加要导出的纹理集
    all_ts = substance_painter.textureset.all_texture_sets()
    for ts in all_ts:
        config.export_list.append(ts)

    result = substance_painter.export.export_project_textures(config)
    if result.status == substance_painter.export.ExportStatus.Success:
        print(f"✅ 导出成功，文件数: {len(result.textures)}")
    else:
        print(f"❌ 导出失败: {result.message}")
```

### 配置导出路径和格式

```python
import substance_painter.project
import substance_painter.export

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    config = substance_painter.export.get_default_export_config()

    # 设置导出路径
    config.export_path = "D:/Export/MyProject"

    # 设置文件格式 (png, tga, exr, tiff, psd 等)
    config.default_format = substance_painter.export.ExportFormat.PNG

    # 设置导出分辨率
    config.default_size = [2048, 2048]

    result = substance_painter.export.export_project_textures(config)
    if result.status == substance_painter.export.ExportStatus.Success:
        print(f"✅ 导出到: {config.export_path}")
    else:
        print(f"❌ 导出失败: {result.message}")
```

---

## 常用导出预设

| 预设名称 | 适用引擎/场景 |
|---|---|
| `Unreal Engine 4 (Packed)` | UE4/UE5 — ORM 打包格式 |
| `Unity 5 (Standard Metallic)` | Unity — Standard 材质 |
| `PBR Metallic Roughness` | 通用 PBR |
| `glTF PBR Metal Roughness` | glTF/WebGL |

---

## 常用导出格式

| 格式 | 枚举值 | 说明 |
|---|---|---|
| PNG | `ExportFormat.PNG` | 通用无损 |
| TGA | `ExportFormat.TGA` | 游戏行业常用 |
| EXR | `ExportFormat.EXR` | HDR 高动态范围 |
| TIFF | `ExportFormat.TIFF` | 印刷/高品质 |
| PSD | `ExportFormat.PSD` | Photoshop 兼容 |

---

## 完整工作流示例：烘焙 + 导出

```python
import substance_painter.project
import substance_painter.baking
import substance_painter.export

if not substance_painter.project.is_open():
    print("❌ 没有打开的项目")
else:
    # 1. 先保存项目
    substance_painter.project.save()
    print("✅ 项目已保存")

    # 2. 烘焙所有贴图
    substance_painter.baking.bake_all_texture_sets()
    print("✅ 贴图烘焙完成")

    # 3. 导出纹理
    config = substance_painter.export.get_default_export_config()
    config.export_path = "D:/Export/FinalTextures"

    result = substance_painter.export.export_project_textures(config)
    if result.status == substance_painter.export.ExportStatus.Success:
        print(f"✅ 导出完成，共 {len(result.textures)} 个文件")
        for f in result.textures:
            print(f"  {f}")
    else:
        print(f"❌ 导出失败: {result.message}")

    print("✅ 烘焙 + 导出工作流完成")
```

---

## 使用建议

- 烘焙前确保已设置好高模（如有），否则只能烘焙 AO、Curvature 等不需要高模的贴图
- 导出前先 `list_export_presets()` 查看可用预设，选择匹配目标引擎的预设
- 批量导出多个纹理集时，所有纹理集共享同一导出配置
- 大型项目烘焙耗时较长，烘焙过程中 API 会阻塞直到完成
- 导出路径不存在时 SP 会自动创建目录
