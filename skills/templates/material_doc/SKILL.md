---
name: generate-material-documentation
description: >
  Read a master material's blueprint, extract all parameters (scalar, vector, texture,
  static switch), and generate a comprehensive Markdown documentation file. Use when
  AI needs to: (1) document material parameters for artists, (2) understand material
  structure, (3) generate technical reference for master materials.
---

# 生成材质使用文档

读取 Master Material 的蓝图节点图，提取所有参数（Scalar、Vector、Texture、StaticSwitch），生成完整的 Markdown 文档。

## Tool

`generate_material_documentation(material_path, [output_path])`

## Workflow

1. 提供材质资产路径
2. 工具自动遍历节点图，提取参数信息
3. 生成结构化的 Markdown 文档

## Notes

- Category: material
- Risk level: low (只读操作)
- 适用版本: UE 5.1 - 5.5
