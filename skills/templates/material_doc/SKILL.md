---
name: generate-material-documentation
description: >
  Read a master material's blueprint, extract all parameters (scalar, vector, texture,
  static switch), and generate a comprehensive Markdown documentation file. Use when
  AI needs to: (1) document material parameters for artists, (2) understand material
  structure, (3) generate technical reference for master materials.
  Saves output to Saved/MaterialDocs/. Only reads material data (no modifications).
  Requires UE Editor running with ArtClaw plugin.
license: MIT
metadata:
  artclaw:
    display_name: "生成材质使用文档"
    author: ArtClaw
    software: unreal_engine
    category: material
    risk_level: low
    version: 1.0.0
    tags: ["material", "documentation", "read-only"]
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

- 只读操作，不修改材质
- 适用版本: UE 5.3 - 5.7
