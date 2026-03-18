"""
get_material_nodes - 获取材质蓝图节点图
========================================

从材质属性入口（BaseColor, Roughness, Normal 等）BFS 遍历所有
连接的 MaterialExpression 节点，返回节点类型、位置、连线和关键属性。

安全设计:
  - 深度限制 max_depth (默认 20, 上限 50)
  - 节点数限制 max_nodes (默认 200, 上限 500)
  - 按节点类名精准读取属性，避免盲目 try/except
  - 74 节点材质实测 < 5ms

Skill Hub 自动发现并注册。保存后热重载生效。
"""

from skill_hub import tool as ue_tool
import json

try:
    import unreal
except ImportError:
    unreal = None


# ============================================================================
# 常量
# ============================================================================

# 材质属性枚举映射表
_MATERIAL_PROPERTIES = [
    ("BaseColor",            "MP_BASE_COLOR"),
    ("Metallic",             "MP_METALLIC"),
    ("Specular",             "MP_SPECULAR"),
    ("Roughness",            "MP_ROUGHNESS"),
    ("Anisotropy",           "MP_ANISOTROPY"),
    ("Normal",               "MP_NORMAL"),
    ("Tangent",              "MP_TANGENT"),
    ("EmissiveColor",        "MP_EMISSIVE_COLOR"),
    ("Opacity",              "MP_OPACITY"),
    ("OpacityMask",          "MP_OPACITY_MASK"),
    ("WorldPositionOffset",  "MP_WORLD_POSITION_OFFSET"),
    ("SubsurfaceColor",      "MP_SUBSURFACE_COLOR"),
    ("AmbientOcclusion",     "MP_AMBIENT_OCCLUSION"),
    ("Refraction",           "MP_REFRACTION"),
    ("MaterialAttributes",   "MP_MATERIAL_ATTRIBUTES"),
    ("FrontMaterial",        "MP_FRONT_MATERIAL"),
]

# 按节点短类名 → 要读取的属性列表（精准匹配，最小化调用）
_CLASS_PROP_MAP = {
    "ScalarParameter":          ["parameter_name", "default_value", "group"],
    "VectorParameter":          ["parameter_name", "default_value", "group"],
    "Constant":                 ["r"],
    "Constant2Vector":          ["r", "g"],
    "Constant3Vector":          ["constant"],
    "Constant4Vector":          ["constant"],
    "TextureSample":            ["texture"],
    "TextureSampleParameter2D": ["parameter_name", "texture", "group"],
    "TextureObject":            ["texture"],
    "StaticSwitchParameter":    ["parameter_name", "default_value", "group"],
    "StaticBoolParameter":      ["parameter_name", "default_value", "group"],
    "MaterialFunctionCall":     ["function"],
    "Comment":                  ["desc"],
}


# ============================================================================
# 辅助函数
# ============================================================================

def _safe_read_prop(node, pname):
    """安全读取单个 editor property，返回字符串或 None"""
    try:
        val = node.get_editor_property(pname)
        if val is None:
            return None
        if hasattr(val, "get_path_name"):
            return str(val.get_path_name())
        return str(val)
    except Exception:
        return None


def _extract_props(node, cls_name: str) -> dict:
    """根据节点类名精准提取属性，最小化 get_editor_property 调用"""
    props = {}
    short = cls_name.replace("MaterialExpression", "")
    prop_names = _CLASS_PROP_MAP.get(short)
    if prop_names is None:
        # 未知类型：只试 parameter_name 和 desc（最多 2 次调用）
        for pn in ("parameter_name", "desc"):
            v = _safe_read_prop(node, pn)
            if v:
                props[pn] = v
        return props
    for pn in prop_names:
        v = _safe_read_prop(node, pn)
        if v is not None:
            props[pn] = v
    return props


# ============================================================================
# Tool
# ============================================================================

@ue_tool(
    name="get_material_nodes",
    description=(
        "Get the blueprint node graph (expression nodes) of a Material asset. "
        "Returns connected expression nodes with class, position, connections, "
        "and key properties. Traverses from material property inputs via BFS "
        "with safety limits. Provide material_path (str). "
        "Optional: max_depth (int, default 20), max_nodes (int, default 200)."
    ),
    category="material",
    risk_level="low",
)
def get_material_nodes(arguments: dict) -> str:
    """获取材质的蓝图节点图（Expression Nodes）"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    material_path = arguments.get("material_path", "")
    if not material_path:
        return json.dumps({"success": False, "error": "material_path is required"})

    max_depth = min(int(arguments.get("max_depth", 20)), 50)
    max_nodes = min(int(arguments.get("max_nodes", 200)), 500)

    try:
        mat = unreal.EditorAssetLibrary.load_asset(material_path)
        if mat is None:
            return json.dumps({
                "success": False,
                "error": f"Material not found: {material_path}",
            })

        if not isinstance(mat, unreal.Material):
            return json.dumps({
                "success": False,
                "error": (
                    f"Asset is {mat.get_class().get_name()}, not a Material. "
                    "Use get_material_parameters for MaterialInstance."
                ),
            })

        mel = unreal.MaterialEditingLibrary
        total_expressions = mel.get_num_material_expressions(mat)

        # --- 1. 材质属性入口 ---
        property_connections = {}
        bfs_queue = []

        for prop_display, prop_attr in _MATERIAL_PROPERTIES:
            prop_enum = getattr(unreal.MaterialProperty, prop_attr, None)
            if prop_enum is None:
                continue
            try:
                node = mel.get_material_property_input_node(mat, prop_enum)
            except Exception:
                continue
            if node is None:
                continue
            try:
                output_name = mel.get_material_property_input_node_output_name(
                    mat, prop_enum
                ) or ""
            except Exception:
                output_name = ""
            property_connections[prop_display] = {
                "node": str(node.get_name()),
                "class": str(node.get_class().get_name()),
                "output": output_name,
            }
            bfs_queue.append((node, 0))

        # --- 2. BFS（带深度 + 节点数限制）---
        visited = {}  # id(node) -> node_name
        nodes_list = []
        truncated = False

        while bfs_queue:
            current, depth = bfs_queue.pop(0)
            nid = id(current)
            if nid in visited:
                continue
            if len(nodes_list) >= max_nodes:
                truncated = True
                break
            if depth > max_depth:
                continue

            cls_name = str(current.get_class().get_name())
            node_name = str(current.get_name())
            visited[nid] = node_name

            # 位置
            try:
                pos = mel.get_material_expression_node_position(current)
                position = [int(pos[0]), int(pos[1])]
            except Exception:
                position = [0, 0]

            # 输入连接
            input_connections = []
            try:
                input_nodes = mel.get_inputs_for_material_expression(mat, current)
                for inp_node in input_nodes:
                    inp_name = str(inp_node.get_name())
                    inp_cls = str(inp_node.get_class().get_name())
                    out_pin = ""
                    try:
                        out_pin = mel.get_input_node_output_name_for_material_expression(
                            current, inp_node
                        ) or ""
                    except Exception:
                        pass
                    input_connections.append({
                        "from": inp_name,
                        "class": inp_cls,
                        "output": out_pin,
                    })
                    if id(inp_node) not in visited:
                        bfs_queue.append((inp_node, depth + 1))
            except Exception:
                pass

            # 精准属性提取
            props = _extract_props(current, cls_name)

            nodes_list.append({
                "name": node_name,
                "class": cls_name,
                "pos": position,
                "inputs": input_connections,
                "props": props,
                "depth": depth,
            })

        return json.dumps({
            "success": True,
            "material": str(mat.get_name()),
            "path": material_path,
            "total_expressions": total_expressions,
            "collected": len(nodes_list),
            "truncated": truncated,
            "property_connections": property_connections,
            "nodes": nodes_list,
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
