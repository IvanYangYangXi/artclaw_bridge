---
name: get-material-nodes
description: >
  Get the blueprint node graph (expression nodes) of a UE Material asset. BFS traversal
  from material property inputs (BaseColor, Roughness, Normal, etc.) returning node class,
  position, connections, and key properties. Use when AI needs to: (1) inspect how a material
  is wired, (2) understand node structure before editing, (3) compare materials, (4) document
  material graphs. Requires UE Editor running with ArtClaw plugin. NOT for MaterialInstance
  parameter queries (use get_material_parameters instead).
---

# Get Material Nodes — 材质节点图查询

从材质属性入口（BaseColor、Roughness、Normal 等 16 个属性）通过 BFS 遍历所有连接的 MaterialExpression 节点。

## Tool

`get_material_nodes(material_path, [max_depth], [max_nodes])`

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `material_path` | string | required | Content browser path, e.g. `/Game/Materials/M_Example` |
| `max_depth` | int | 20 | BFS max depth (upper limit: 50) |
| `max_nodes` | int | 200 | Max collected nodes (upper limit: 500) |

### Returns

Each node includes:
- **class** — e.g. `MaterialExpressionVectorParameter`
- **pos** — editor graph position `[x, y]`
- **inputs** — input connections (source node, output pin name)
- **props** — key properties (parameter_name, default_value, texture, etc.)

Top-level response includes `property_connections` mapping material properties to their directly connected nodes.

## Safety

- Per-class property reading (no blind `get_editor_property`)
- Depth + node count dual limits prevent hangs on complex materials
- Returns `truncated: true` when limits are hit
- 74-node sky material benchmarked at < 5ms

## Limitations

- Only `Material` assets — not `MaterialInstance` (use `get_material_parameters`)
- Only connected nodes reachable via BFS — floating nodes are inaccessible through Python API
- `total_expressions` vs `collected` difference = floating node count
