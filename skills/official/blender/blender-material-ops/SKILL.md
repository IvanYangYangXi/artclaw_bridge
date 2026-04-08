---
name: blender-material-ops
description: >
  Blender 材质创建与节点操作指南。包含 PBR 材质创建、节点连接、中文版兼容等最佳实践。
  Use when AI needs to: (1) create or edit Blender materials,
  (2) set up Principled BSDF node trees, (3) connect shader nodes,
  (4) handle Chinese Blender node name differences.
  Blender only (run_python).
metadata:
  artclaw:
    author: ArtClaw
    software: blender
    category: material
---

# Blender 材质操作指南

> **强制规则**：
> 1. 用 `node.type` 查找节点（不用 `node.name`，中文版名字不同）
> 2. 创建材质后**必须验证**节点数和颜色值
> 3. `bpy.data.materials.new()` 会自动创建默认 BSDF+Output，**不要再 new 一对**
> 4. 需要重建节点时，**先 `nodes.clear()` 再 new**

---

## 规则 0：use_nodes=True 的隐含行为 🔴

```python
mat = bpy.data.materials.new(name="MyMat")
mat.use_nodes = True
# 此时 mat.node_tree.nodes 已包含:
#   - 1 个 Principled BSDF (type='BSDF_PRINCIPLED')
#   - 1 个 Material Output (type='OUTPUT_MATERIAL')
#   - 1 条 BSDF→Output 连接
# 不需要也不能再 nodes.new() 同类型节点！
```

### ❌ 典型错误（重复节点，材质变灰）

```python
mat = bpy.data.materials.new(name="Wall")
mat.use_nodes = True
# 已经有默认节点了！下面又创建一对 → 总共 4 个节点
bsdf = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')  # 重复!
output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')  # 重复!
# 新 BSDF 没连到 Output，材质显示为灰色
```

---

## 模式 A：创建新材质（最常用）

**直接使用 `use_nodes=True` 创建的默认节点**，只修改参数：

```python
mat = bpy.data.materials.new(name="Wall_Material")
mat.use_nodes = True
tree = mat.node_tree

# 通过 type 查找默认节点（兼容中英文 Blender）
bsdf = None
output = None
for node in tree.nodes:
    if node.type == 'BSDF_PRINCIPLED':
        bsdf = node
    elif node.type == 'OUTPUT_MATERIAL':
        output = node

# 设置参数
bsdf.inputs['Base Color'].default_value = (0.9, 0.85, 0.75, 1.0)
bsdf.inputs['Roughness'].default_value = 0.8
bsdf.inputs['Metallic'].default_value = 0.0

# 验证
assert len(tree.nodes) == 2, f"节点数异常: {len(tree.nodes)}"
assert len(tree.links) == 1, f"连接数异常: {len(tree.links)}"
```

---

## 模式 B：修改已有材质

**只改参数，不碰节点结构**：

```python
mat = bpy.data.materials.get("Wall_Material")
if mat and mat.use_nodes:
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            node.inputs['Base Color'].default_value = (0.95, 0.9, 0.8, 1.0)
            node.inputs['Roughness'].default_value = 0.7
            break
```

---

## 模式 C：重建损坏的材质

**先清除再创建**——材质有重复节点或连接断开时使用：

```python
mat = bpy.data.materials.get("Wall_Material")
if not mat:
    mat = bpy.data.materials.new(name="Wall_Material")

mat.use_nodes = True
tree = mat.node_tree

# 清除所有节点（关键步骤）
tree.nodes.clear()

# 重新创建
bsdf = tree.nodes.new(type='ShaderNodeBsdfPrincipled')
bsdf.location = (0, 0)
bsdf.inputs['Base Color'].default_value = (0.9, 0.85, 0.75, 1.0)
bsdf.inputs['Roughness'].default_value = 0.8

output = tree.nodes.new(type='ShaderNodeOutputMaterial')
output.location = (300, 0)

tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

# 验证
assert len(tree.nodes) == 2
assert len(tree.links) == 1
```

---

## 批量创建材质 + 分配到对象

```python
import bpy

# 材质配置
configs = {
    "Wall_Material": {"color": (0.9, 0.85, 0.75), "roughness": 0.8},
    "Roof_Material": {"color": (0.4, 0.25, 0.2), "roughness": 0.9},
    "Door_Material": {"color": (0.5, 0.3, 0.2), "roughness": 0.6},
    "Window_Material": {"color": (0.7, 0.9, 1.0), "roughness": 0.1},
}

# 创建材质
for name, cfg in configs.items():
    # 如果已存在则删除重建（最干净的方式）
    old = bpy.data.materials.get(name)
    if old:
        bpy.data.materials.remove(old)
    
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    
    # 查找默认 BSDF（不要 new 新的！）
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            node.inputs['Base Color'].default_value = (*cfg["color"], 1.0)
            node.inputs['Roughness'].default_value = cfg["roughness"]
            break

# 分配到对象（按名称关键词匹配）
mapping = {
    "Wall": "Wall_Material", "Base": "Wall_Material",
    "Roof": "Roof_Material", "Chimney": "Roof_Material",
    "Door": "Door_Material", "Knob": "Door_Material",
    "Window": "Window_Material",
}

for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    for keyword, mat_name in mapping.items():
        if keyword in obj.name:
            mat = bpy.data.materials.get(mat_name)
            if mat:
                obj.data.materials.clear()
                obj.data.materials.append(mat)
            break

# 验证结果
result = {}
for name in configs:
    mat = bpy.data.materials.get(name)
    if mat and mat.use_nodes:
        for n in mat.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                result[name] = {
                    "color": [round(x, 3) for x in n.inputs['Base Color'].default_value],
                    "nodes": len(mat.node_tree.nodes),
                }
                break
```

---

## 中文版节点名对照表

| 英文版 node.name | 中文版 node.name | node.type（通用，必须用这个） |
|---|---|---|
| `Principled BSDF` | `原理化 BSDF` | `BSDF_PRINCIPLED` |
| `Material Output` | `材质输出` | `OUTPUT_MATERIAL` |
| `Image Texture` | `图像纹理` | `TEX_IMAGE` |
| `Color Ramp` | `色带` | `VALTORGB` |
| `Mix Shader` | `混合着色器` | `MIX_SHADER` |
| `Normal Map` | `法线贴图` | `NORMAL_MAP` |

> **端口名（socket name）通常保持英文**，如 `'Base Color'`、`'BSDF'`、`'Surface'`。

---

## 常用节点类型速查

### 着色器
| ShaderNode 类名 | node.type |
|---|---|
| `ShaderNodeBsdfPrincipled` | `BSDF_PRINCIPLED` |
| `ShaderNodeBsdfDiffuse` | `BSDF_DIFFUSE` |
| `ShaderNodeEmission` | `EMISSION` |
| `ShaderNodeMixShader` | `MIX_SHADER` |
| `ShaderNodeBsdfTransparent` | `BSDF_TRANSPARENT` |

### 纹理
| ShaderNode 类名 | node.type |
|---|---|
| `ShaderNodeTexImage` | `TEX_IMAGE` |
| `ShaderNodeTexNoise` | `TEX_NOISE` |
| `ShaderNodeTexVoronoi` | `TEX_VORONOI` |
| `ShaderNodeTexChecker` | `TEX_CHECKER` |

### 工具
| ShaderNode 类名 | node.type |
|---|---|
| `ShaderNodeNormalMap` | `NORMAL_MAP` |
| `ShaderNodeBump` | `BUMP` |
| `ShaderNodeValToRGB` | `VALTORGB` |
| `ShaderNodeMapping` | `MAPPING` |
| `ShaderNodeTexCoord` | `TEX_COORD` |
| `ShaderNodeMath` | `MATH` |
| `ShaderNodeMix` | `MIX` |

---

## 诊断材质问题

```python
issues = []
for mat in bpy.data.materials:
    if not mat.use_nodes or not mat.node_tree:
        continue
    nodes = mat.node_tree.nodes
    bsdf_n = sum(1 for n in nodes if n.type == 'BSDF_PRINCIPLED')
    out_n = sum(1 for n in nodes if n.type == 'OUTPUT_MATERIAL')
    if bsdf_n != 1 or out_n != 1:
        issues.append(f"{mat.name}: BSDF={bsdf_n}, Output={out_n} (应为各1个)")
result = issues or ["所有材质正常"]
```
