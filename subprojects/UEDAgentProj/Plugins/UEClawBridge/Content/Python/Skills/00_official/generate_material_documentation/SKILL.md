---
name: generate-material-documentation
description: >
  Read a master material's blueprint, extract all parameters (scalar, vector, texture,
  static switch), and generate a comprehensive Markdown documentation file. Use when AI
  needs to: (1) document material parameters for artists, (2) generate technical reference
  for master materials, (3) create handoff documentation for material setups. Saves output
  to Saved/MaterialDocs/. Only reads material data (no modifications). Requires UE Editor
  running with ArtClaw plugin.
---

# 生成材质使用文档

读取 Master Material 的蓝图节点图，提取所有参数，生成 Markdown 格式技术文档。

## Tool

`generate_material_documentation(material_path, [output_format], [include_parameters], [include_graph])`

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `material_path` | string | required | 母材质资产路径，如 `/Game/Materials/M_Master` |
| `output_format` | string | `"markdown"` | 输出格式 |
| `include_parameters` | bool | `true` | 是否包含参数说明 |
| `include_graph` | bool | `true` | 是否包含节点图信息 |

### Returns

- `documentation` — 完整 Markdown 文档文本
- `output_path` — 保存到 `{ProjectDir}/Saved/MaterialDocs/{MaterialName}.md`
- `parameter_count` / `texture_count` / `expression_count` — 统计

## 提取内容

- 材质基本信息（名称、路径、Blend Mode、Shading Model、双面等）
- Scalar 参数（名称、默认值）
- Vector 参数（名称、RGBA 默认值）
- Texture 参数（名称、默认贴图路径）
- Static Switch 参数（名称、默认开关状态）
- 材质图表节点（最多 50 个，类型 + 名称 + 描述）

## Notes

- Risk level: low（只读操作）
- 节点图依赖 `MaterialEditingLibrary.get_material_expressions()`，部分 UE 版本可能不可用（优雅降级）
- 适用版本: UE 5.1+
