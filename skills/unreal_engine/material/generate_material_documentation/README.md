# generate_material_documentation

> 样板 Skill — 读取母材质的材质蓝图，创建材质使用文档

## 功能描述

读取 UE 中的母材质（Master Material），自动提取所有参数信息并生成 Markdown 格式的文档。

**提取内容：**
- 材质基本信息（名称、路径、Blend Mode、Shading Model、双面等）
- Scalar 参数（名称、默认值）
- Vector 参数（名称、RGBA 默认值）
- Texture 参数（名称、默认贴图路径）
- Static Switch 参数（名称、默认开关状态）
- 材质图表节点（节点类型、名称、描述）

## 使用方法

### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `material_path` | string | ✅ | - | 母材质的资产路径 |
| `output_format` | string | | `"markdown"` | 输出格式 |
| `include_parameters` | bool | | `true` | 是否包含参数说明 |
| `include_graph` | bool | | `true` | 是否包含节点图信息 |

### 调用示例

```json
{
  "material_path": "/Game/Materials/M_Master",
  "include_parameters": true,
  "include_graph": true
}
```

### 返回示例

```json
{
  "success": true,
  "material_name": "M_Master",
  "material_path": "/Game/Materials/M_Master.M_Master",
  "documentation": "# M_Master 材质文档\n\n## 概览\n...",
  "output_path": "D:/MyProject/Saved/MaterialDocs/M_Master.md",
  "parameter_count": 12,
  "texture_count": 4,
  "expression_count": 23
}
```

## 输出文档结构

```markdown
# M_Master 材质文档

## 概览
- 材质名称: M_Master
- 资产路径: /Game/Materials/M_Master
- Blend Mode: BLEND_Opaque
- ...

## Scalar 参数
| 参数名 | 默认值 |
|--------|--------|
| Metallic | 0.0 |
| Roughness | 0.5 |

## Vector 参数
| 参数名 | R | G | B | A |
|--------|---|---|---|---|
| BaseColor | 1.0 | 1.0 | 1.0 | 1.0 |

## Texture 参数
| 参数名 | 默认贴图 |
|--------|----------|
| DiffuseMap | /Game/Textures/T_Default |

## Static Switch 参数
| 参数名 | 默认值 |
|--------|--------|
| UseNormalMap | True |

## 材质图表节点
| 节点类型 | 名称 | 描述 |
|----------|------|------|
| MaterialExpressionTextureSample | ... | ... |
```

## 注意事项

- **风险级别**: Low（只读操作，不修改任何资产）
- **输出位置**: 文档保存到 `{ProjectDir}/Saved/MaterialDocs/{MaterialName}.md`
- **API 依赖**: 使用 `unreal.MaterialEditingLibrary`，需要 UE 5.1+
- **节点图**: `get_material_expressions()` 在部分 UE 版本中可能不可用，会优雅降级
- **文档大小**: 材质图表节点最多提取 50 个，防止文档过大
