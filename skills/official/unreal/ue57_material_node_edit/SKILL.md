---
name: artclaw-material
description: >
  ArtClaw official Material node graph write operations for UE5. Create, delete, connect,
  and edit MaterialExpression nodes in a Material's node graph, create new Material assets,
  set material properties, and recompile materials. Use when AI needs to: (1) build materials
  from scratch by assembling expression nodes, (2) modify existing material node graphs,
  (3) connect nodes to material property inputs (BaseColor, Roughness, Normal, etc.),
  (4) set material-level properties (BlendMode, ShadingModel, TwoSided), (5) help users
  author procedural or texture-based materials. Works with Material assets (not MaterialInstance
  — use material_ops.py tools for instance parameter overrides). Requires UE Editor running
  with ArtClaw plugin. NOT for: reading node graphs (use get-material-nodes skill), material
  instance parameter queries (use get_material_parameters tool).
---

# ArtClaw Material — 材质节点图操作接口

Official ArtClaw skill providing atomic tools for Material node graph manipulation.
All tools are registered via `@ue_tool` and exposed through MCP.

## Architecture

```
AI (OpenClaw) ──MCP──▶ Skill Hub ──▶ material_node_ops.py (this skill)
                                  ──▶ material_ops.py (existing: instance params, actor materials)
                                  ──▶ get_material_nodes (existing: read node graph)
```

**This skill handles**: node graph write operations (create, delete, connect, edit nodes).
**Existing tools handle**: reading node graphs (`get_material_nodes`), material instance parameters (`get_material_parameters`, `create_material_instance`), actor material assignment (`get_actor_materials`, `set_actor_material`).

## Tools Summary

| Tool | Risk | Description |
|------|------|-------------|
| `create_material` | medium | Create new empty Material asset |
| `create_material_expression` | medium | Add expression node to graph |
| `delete_material_expression` | high | Remove expression node |
| `connect_material_expressions` | medium | Connect two expression nodes |
| `connect_material_property` | medium | Connect node to material property input |
| `set_expression_property` | medium | Set node editor property |
| `set_expression_position` | low | Move node in graph |
| `set_material_properties` | medium | Set BlendMode, ShadingModel, etc. |
| `list_material_expressions` | low | List all nodes (flat, no connections) |
| `recompile_material` | medium | Recompile + validate + save after edits |

## ✅ 核心工作流：先写伪代码，再创建节点

> 📋 **通用节点图工作流**（伪代码→映射→分组创建→验证→布局）见 `dcc-node-graph-workflow` skill。
> 本 skill 专注 UE 材质的 **API 细节、节点类名和属性速查**。

**UE 材质图是纯数据流节点图，伪代码示例：**

```python
# 伪代码
base_color = tex_diffuse * tint_color
roughness  = lerp(0.2, 0.9, tex_roughness.r)
metallic   = param_metallic

# 节点映射
TextureSampleParameter2D  → tex_diffuse / tex_roughness
Constant3Vector           → tint_color
Multiply                  → base_color = tex * tint
ComponentMask(R)          → .r channel
Lerp                      → roughness
ScalarParameter           → metallic
```

## Standard Workflow

1. **Create material** → `create_material(asset_name, package_path)`
2. **Set material properties** → `set_material_properties(material_path, {blend_mode, shading_model, ...})`
3. **Add nodes** → `create_material_expression(material_path, expression_class, pos_x, pos_y)` (repeat)
4. **Set node properties** → `set_expression_property(material_path, node_name, property_name, value)`
5. **Wire nodes together** → `connect_material_expressions(from_node, from_output, to_node, to_input)`
6. **Wire to material outputs** → `connect_material_property(from_node, from_output, "BaseColor")`
7. **Compile + verify** → `recompile_material(material_path, save=true)`

Existing tools for read/query:
- `get_material_nodes(material_path)` — full BFS traversal with connections
- `list_material_expressions(material_path)` — quick flat list
- `get_material_parameters(material_path)` — instance parameter values

## Expression Class Names

Pass full class name (e.g. `MaterialExpressionConstant3Vector`) or short name (e.g. `Constant3Vector`) — the tool auto-prefixes.

Common types:

**Constants**: `Constant`, `Constant2Vector`, `Constant3Vector`, `Constant4Vector`
**Parameters**: `ScalarParameter`, `VectorParameter`, `StaticSwitchParameter`
**Textures**: `TextureSample`, `TextureSampleParameter2D`, `TextureCoordinate`
**Math**: `Add`, `Subtract`, `Multiply`, `Divide`, `Power`, `Lerp`, `Clamp`, `OneMinus`, `Saturate`
**Utility**: `ComponentMask`, `AppendVector`, `Fresnel`, `Noise`, `Time`, `Panner`
**Custom**: `Custom` (HLSL code), `MaterialFunctionCall`, `Comment`

Full list: [references/node_types.md](references/node_types.md)

## Pin Names

When connecting nodes, use pin names:

- **Default/first pin**: empty string `""`
- **TextureSample outputs**: `""` (RGBA), `RGB`, `R`, `G`, `B`, `A`
- **Math node inputs**: `A`, `B`
- **Lerp inputs**: `A`, `B`, `Alpha`
- **Power inputs**: `Base`, `Exponent`
- **Clamp inputs**: `Input`, `Min`, `Max`

## Property Setting

Use `set_expression_property` for node-specific properties:

- **Constant**: `r` (float)
- **Constant3/4Vector**: `constant` ({r, g, b, a})
- **Parameter nodes**: `parameter_name` (str), `default_value`, `group` (str)
- **TextureSample**: `texture` (asset path string)
- **TextureCoordinate**: `coordinate_index` (int), `u_tiling` (float), `v_tiling` (float)
- **Custom**: `code` (HLSL string), `description` (str)
- **Panner**: `speed_x` (float), `speed_y` (float)

## Material Properties

Use `set_material_properties` for top-level material settings:

- `blend_mode`: `Opaque` | `Translucent` | `Masked` | `Additive` | `Modulate`
- `shading_model`: `DefaultLit` | `Unlit` | `Subsurface` | `SubsurfaceProfile` | `ClearCoat`
- `two_sided`: bool
- `opacity_mask_clip_value`: float (for Masked mode)

Details: [references/material_properties.md](references/material_properties.md)

## Example: Create Simple PBR Metal Material

```
1. create_material(asset_name="M_BlueMetal", package_path="/Game/Materials")
2. create_material_expression(material_path="/Game/Materials/M_BlueMetal", expression_class="Constant3Vector", pos_x=-300, pos_y=0)
   → returns node_name e.g. "MaterialExpressionConstant3Vector_0"
3. set_expression_property(..., node_name="MaterialExpressionConstant3Vector_0", property_name="constant", property_value={"r":0.1,"g":0.2,"b":0.8})
4. connect_material_property(..., from_node="MaterialExpressionConstant3Vector_0", from_output="", material_property="BaseColor")
5. create_material_expression(..., expression_class="Constant", pos_x=-300, pos_y=150)
   → "MaterialExpressionConstant_0"
6. set_expression_property(..., node_name="MaterialExpressionConstant_0", property_name="r", property_value=1.0)
7. connect_material_property(..., from_node="MaterialExpressionConstant_0", from_output="", material_property="Metallic")
8. create_material_expression(..., expression_class="Constant", pos_x=-300, pos_y=250)
   → "MaterialExpressionConstant_1"
9. set_expression_property(..., node_name="MaterialExpressionConstant_1", property_name="r", property_value=0.3)
10. connect_material_property(..., from_node="MaterialExpressionConstant_1", from_output="", material_property="Roughness")
11. recompile_material(material_path="/Game/Materials/M_BlueMetal", save=true)
```

## Error Handling

All tools return `{"success": true/false, ...}`. On failure, `error` field contains a human-readable message. Common errors:

- `Material not found` — invalid path
- `Asset is MaterialInstanceConstant, not a Material` — use instance tools instead
- `Unknown expression class` — check references/node_types.md
- `Connection failed` — pin name mismatch or type incompatibility
- `Node not found` — wrong node_name (use list_material_expressions to verify)

## Compile Validation

`recompile_material` **automatically validates** compilation results via shader instruction counts:

- `compile_success: true` — `num_pixel_shader_instructions > 0`
- `compile_success: false` — returns error hint + 0 instructions
- **Only saves on success** — prevents saving broken materials

Response includes `stats` with instruction/sampler/texture counts for debugging.

Common compile failures:
- Custom node HLSL: undefined variables (must be passed as inputs, not assumed)
- Type mismatch: connecting float3 to float1 input
- Missing connections: material property expects input but none connected

## Deployment

Copy `scripts/material_node_ops.py` to the ArtClaw Skills directory:
```
{UEPlugin}/Content/Python/Skills/material_node_ops.py
```
Or place in `00_official/artclaw-material/` as a manifest-based skill.
Skill Hub auto-discovers `@ue_tool` decorated functions on file save.
