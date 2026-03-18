"""
material_node_ops.py - 材质节点图操作接口
==========================================

ArtClaw 官方 Skill：材质节点的创建、删除、连接、属性编辑。
通过 @ue_tool 装饰器注册到 Skill Hub，MCP 自动发现。

接口设计原则：
  - 每个 tool 做一件事，保持原子性
  - 返回 JSON 标准格式 {success, data/error}
  - 所有写操作使用 ScopedEditorTransaction（支持 Ctrl+Z）
  - 高级业务逻辑（如"生成一个金属材质"）不在此处，由 AI 组合调用
"""

from skill_hub import tool as ue_tool
import json

try:
    import unreal
except ImportError:
    unreal = None


# ============================================================================
# 内部辅助
# ============================================================================

def _load_material(material_path: str):
    """加载并验证材质资产，返回 (material, error_json)"""
    mat = unreal.EditorAssetLibrary.load_asset(material_path)
    if mat is None:
        return None, json.dumps({
            "success": False,
            "error": f"Material not found: {material_path}",
        })
    if not isinstance(mat, unreal.Material):
        return None, json.dumps({
            "success": False,
            "error": (
                f"Asset is {mat.get_class().get_name()}, not a Material. "
                "Node graph operations require a Material, not MaterialInstance."
            ),
        })
    return mat, None


def _find_expression_by_name(mat, node_name: str):
    """在材质中按名称查找 MaterialExpression"""
    # 方法1: 通过 load_object 直接加载子对象（最可靠）
    mat_path = str(mat.get_path_name())  # e.g. /Game/Materials/M_Test.M_Test
    full_path = mat_path + ":" + node_name
    try:
        expr = unreal.load_object(name=full_path, outer=None)
        if expr is not None:
            return expr
    except Exception:
        pass

    # 方法2: BFS 从材质属性入口遍历查找
    mel = unreal.MaterialEditingLibrary
    visited = set()
    queue = []

    # 从所有材质属性入口收集根节点
    props = [
        unreal.MaterialProperty.MP_BASE_COLOR,
        unreal.MaterialProperty.MP_METALLIC,
        unreal.MaterialProperty.MP_SPECULAR,
        unreal.MaterialProperty.MP_ROUGHNESS,
        unreal.MaterialProperty.MP_NORMAL,
        unreal.MaterialProperty.MP_EMISSIVE_COLOR,
        unreal.MaterialProperty.MP_OPACITY,
        unreal.MaterialProperty.MP_OPACITY_MASK,
        unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET,
        unreal.MaterialProperty.MP_AMBIENT_OCCLUSION,
        unreal.MaterialProperty.MP_REFRACTION,
    ]
    for prop in props:
        try:
            node = mel.get_material_property_input_node(mat, prop)
            if node is not None:
                queue.append(node)
        except Exception:
            continue

    while queue:
        current = queue.pop(0)
        name = str(current.get_name())
        if name in visited:
            continue
        visited.add(name)
        if name == node_name:
            return current
        # 遍历输入
        try:
            inputs = mel.get_inputs_for_material_expression(mat, current)
            for inp in inputs:
                if inp is not None and str(inp.get_name()) not in visited:
                    queue.append(inp)
        except Exception:
            continue

    return None


def _expression_info(expr) -> dict:
    """将 MaterialExpression 转为精简字典"""
    mel = unreal.MaterialEditingLibrary
    cls_name = str(expr.get_class().get_name())
    name = str(expr.get_name())
    try:
        pos = mel.get_material_expression_node_position(expr)
        position = [int(pos[0]), int(pos[1])]
    except Exception:
        position = [0, 0]
    return {
        "name": name,
        "class": cls_name,
        "position": position,
    }


# ============================================================================
# Tool: 创建材质资产
# ============================================================================

@ue_tool(
    name="create_material",
    description=(
        "Create a new empty Material asset at the specified path. "
        "Provide asset_name and package_path (e.g. '/Game/Materials'). "
        "Optionally set blend_mode ('Opaque','Translucent','Masked','Additive') "
        "and shading_model ('DefaultLit','Unlit','SubsurfaceProfile', etc.)."
    ),
    category="material",
    risk_level="medium",
)
def create_material(arguments: dict) -> str:
    """创建新的空白材质资产"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in UE"})

    asset_name = arguments.get("asset_name", "")
    package_path = arguments.get("package_path", "/Game/Materials")
    blend_mode = arguments.get("blend_mode", "")
    shading_model = arguments.get("shading_model", "")

    if not asset_name:
        return json.dumps({"success": False, "error": "asset_name is required"})

    try:
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        factory = unreal.MaterialFactoryNew()
        mat = asset_tools.create_asset(
            asset_name, package_path, unreal.Material, factory
        )
        if mat is None:
            return json.dumps({"success": False, "error": "Failed to create material"})

        # 设置混合模式
        _BLEND_MODES = {
            "Opaque": unreal.BlendMode.BLEND_OPAQUE,
            "Translucent": unreal.BlendMode.BLEND_TRANSLUCENT,
            "Masked": unreal.BlendMode.BLEND_MASKED,
            "Additive": unreal.BlendMode.BLEND_ADDITIVE,
            "Modulate": unreal.BlendMode.BLEND_MODULATE,
            "AlphaComposite": unreal.BlendMode.BLEND_ALPHA_COMPOSITE,
        }
        if blend_mode and blend_mode in _BLEND_MODES:
            mat.set_editor_property("blend_mode", _BLEND_MODES[blend_mode])

        # 设置着色模型
        _SHADING_MODELS = {
            "DefaultLit": unreal.MaterialShadingModel.MSM_DEFAULT_LIT,
            "Unlit": unreal.MaterialShadingModel.MSM_UNLIT,
            "Subsurface": unreal.MaterialShadingModel.MSM_SUBSURFACE,
            "SubsurfaceProfile": unreal.MaterialShadingModel.MSM_SUBSURFACE_PROFILE,
            "ClearCoat": unreal.MaterialShadingModel.MSM_CLEAR_COAT,
            "TwoSidedFoliage": unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE,
        }
        if shading_model and shading_model in _SHADING_MODELS:
            mat.set_editor_property("shading_model", _SHADING_MODELS[shading_model])

        unreal.EditorAssetLibrary.save_asset(mat.get_path_name())

        return json.dumps({
            "success": True,
            "material": {
                "name": str(mat.get_name()),
                "path": str(mat.get_path_name()),
            },
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ============================================================================
# Tool: 创建材质表达式节点
# ============================================================================

@ue_tool(
    name="create_material_expression",
    description=(
        "Create a MaterialExpression node in a Material's node graph. "
        "Provide material_path, expression_class (e.g. 'MaterialExpressionConstant3Vector', "
        "'MaterialExpressionTextureSample', 'MaterialExpressionMultiply'). "
        "Optional: pos_x, pos_y (int, node position in graph). "
        "Returns the created node name for use in connect/edit calls."
    ),
    category="material",
    risk_level="medium",
)
def create_material_expression(arguments: dict) -> str:
    """在材质节点图中创建表达式节点"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in UE"})

    material_path = arguments.get("material_path", "")
    expression_class = arguments.get("expression_class", "")
    pos_x = int(arguments.get("pos_x", 0))
    pos_y = int(arguments.get("pos_y", 0))

    if not material_path:
        return json.dumps({"success": False, "error": "material_path is required"})
    if not expression_class:
        return json.dumps({"success": False, "error": "expression_class is required"})

    mat, err = _load_material(material_path)
    if err:
        return err

    try:
        mel = unreal.MaterialEditingLibrary

        # 获取表达式类 (使用 getattr 而非 unreal.find_class，后者不存在)
        expr_class = getattr(unreal, expression_class, None)
        if expr_class is None:
            # 尝试加前缀
            if not expression_class.startswith("MaterialExpression"):
                expr_class = getattr(
                    unreal, "MaterialExpression" + expression_class, None
                )
            if expr_class is None:
                return json.dumps({
                    "success": False,
                    "error": f"Unknown expression class: {expression_class}. "
                             "See references/node_types.md for valid types.",
                })

        with unreal.ScopedEditorTransaction("Create Material Expression"):
            expr = mel.create_material_expression(mat, expr_class, pos_x, pos_y)

        if expr is None:
            return json.dumps({
                "success": False,
                "error": "Failed to create expression node",
            })

        return json.dumps({
            "success": True,
            "node": _expression_info(expr),
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ============================================================================
# Tool: 删除材质表达式节点
# ============================================================================

@ue_tool(
    name="delete_material_expression",
    description=(
        "Delete a MaterialExpression node from a Material's node graph. "
        "Provide material_path and node_name (the expression's name as "
        "returned by create_material_expression or get_material_nodes)."
    ),
    category="material",
    risk_level="high",
)
def delete_material_expression(arguments: dict) -> str:
    """删除材质节点图中的表达式节点"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in UE"})

    material_path = arguments.get("material_path", "")
    node_name = arguments.get("node_name", "")

    if not material_path or not node_name:
        return json.dumps({
            "success": False,
            "error": "material_path and node_name are required",
        })

    mat, err = _load_material(material_path)
    if err:
        return err

    try:
        expr = _find_expression_by_name(mat, node_name)
        if expr is None:
            return json.dumps({
                "success": False,
                "error": f"Expression not found: {node_name}",
            })

        mel = unreal.MaterialEditingLibrary
        with unreal.ScopedEditorTransaction("Delete Material Expression"):
            mel.delete_material_expression(mat, expr)

        return json.dumps({
            "success": True,
            "deleted": node_name,
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ============================================================================
# Tool: 连接表达式节点
# ============================================================================

@ue_tool(
    name="connect_material_expressions",
    description=(
        "Connect two MaterialExpression nodes in a Material's node graph. "
        "Provide material_path, from_node (source node name), "
        "from_output (output pin name, e.g. 'RGB', 'R', '' for default), "
        "to_node (destination node name), "
        "to_input (input pin name, e.g. 'A', 'B', 'Coords', '' for default). "
        "Use empty string for default/first pin."
    ),
    category="material",
    risk_level="medium",
)
def connect_material_expressions(arguments: dict) -> str:
    """连接两个材质表达式节点"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in UE"})

    material_path = arguments.get("material_path", "")
    from_node = arguments.get("from_node", "")
    from_output = arguments.get("from_output", "")
    to_node = arguments.get("to_node", "")
    to_input = arguments.get("to_input", "")

    if not material_path or not from_node or not to_node:
        return json.dumps({
            "success": False,
            "error": "material_path, from_node, to_node are required",
        })

    mat, err = _load_material(material_path)
    if err:
        return err

    try:
        from_expr = _find_expression_by_name(mat, from_node)
        if from_expr is None:
            return json.dumps({
                "success": False,
                "error": f"Source node not found: {from_node}",
            })

        to_expr = _find_expression_by_name(mat, to_node)
        if to_expr is None:
            return json.dumps({
                "success": False,
                "error": f"Destination node not found: {to_node}",
            })

        mel = unreal.MaterialEditingLibrary
        with unreal.ScopedEditorTransaction("Connect Material Expressions"):
            result = mel.connect_material_expressions(
                from_expr, from_output, to_expr, to_input
            )

        if not result:
            return json.dumps({
                "success": False,
                "error": (
                    f"Connection failed: {from_node}:{from_output} -> "
                    f"{to_node}:{to_input}. Check pin names and type compatibility."
                ),
            })

        return json.dumps({
            "success": True,
            "connection": {
                "from": from_node,
                "from_output": from_output or "(default)",
                "to": to_node,
                "to_input": to_input or "(default)",
            },
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ============================================================================
# Tool: 连接表达式到材质属性输入
# ============================================================================

@ue_tool(
    name="connect_material_property",
    description=(
        "Connect a MaterialExpression node to a Material property input "
        "(BaseColor, Metallic, Roughness, Normal, EmissiveColor, Opacity, etc.). "
        "Provide material_path, from_node (expression name), "
        "from_output (pin name, '' for default), "
        "material_property (one of: BaseColor, Metallic, Specular, Roughness, "
        "Anisotropy, Normal, Tangent, EmissiveColor, Opacity, OpacityMask, "
        "WorldPositionOffset, SubsurfaceColor, AmbientOcclusion, Refraction)."
    ),
    category="material",
    risk_level="medium",
)
def connect_material_property(arguments: dict) -> str:
    """将表达式节点连接到材质属性输入"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in UE"})

    material_path = arguments.get("material_path", "")
    from_node = arguments.get("from_node", "")
    from_output = arguments.get("from_output", "")
    material_property = arguments.get("material_property", "")

    if not material_path or not from_node or not material_property:
        return json.dumps({
            "success": False,
            "error": "material_path, from_node, material_property are required",
        })

    mat, err = _load_material(material_path)
    if err:
        return err

    # 属性名映射
    _PROP_MAP = {
        "BaseColor": "MP_BASE_COLOR",
        "Metallic": "MP_METALLIC",
        "Specular": "MP_SPECULAR",
        "Roughness": "MP_ROUGHNESS",
        "Anisotropy": "MP_ANISOTROPY",
        "Normal": "MP_NORMAL",
        "Tangent": "MP_TANGENT",
        "EmissiveColor": "MP_EMISSIVE_COLOR",
        "Opacity": "MP_OPACITY",
        "OpacityMask": "MP_OPACITY_MASK",
        "WorldPositionOffset": "MP_WORLD_POSITION_OFFSET",
        "SubsurfaceColor": "MP_SUBSURFACE_COLOR",
        "AmbientOcclusion": "MP_AMBIENT_OCCLUSION",
        "Refraction": "MP_REFRACTION",
    }

    prop_attr = _PROP_MAP.get(material_property)
    if prop_attr is None:
        return json.dumps({
            "success": False,
            "error": f"Unknown material property: {material_property}. "
                     f"Valid: {list(_PROP_MAP.keys())}",
        })

    prop_enum = getattr(unreal.MaterialProperty, prop_attr, None)
    if prop_enum is None:
        return json.dumps({
            "success": False,
            "error": f"MaterialProperty.{prop_attr} not available in this UE version",
        })

    try:
        from_expr = _find_expression_by_name(mat, from_node)
        if from_expr is None:
            return json.dumps({
                "success": False,
                "error": f"Node not found: {from_node}",
            })

        mel = unreal.MaterialEditingLibrary
        with unreal.ScopedEditorTransaction("Connect to Material Property"):
            result = mel.connect_material_property(
                from_expr, from_output, prop_enum
            )

        if not result:
            return json.dumps({
                "success": False,
                "error": (
                    f"Connection failed: {from_node}:{from_output} -> "
                    f"{material_property}. Check output type compatibility."
                ),
            })

        return json.dumps({
            "success": True,
            "connection": {
                "from": from_node,
                "from_output": from_output or "(default)",
                "to_property": material_property,
            },
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ============================================================================
# Tool: 设置节点属性
# ============================================================================

@ue_tool(
    name="set_expression_property",
    description=(
        "Set an editor property on a MaterialExpression node. "
        "Provide material_path, node_name, property_name, property_value. "
        "Common properties: 'r' (Constant), 'constant' (Constant3/4Vector), "
        "'parameter_name' (parameter nodes), 'default_value', 'texture' (path), "
        "'sampler_type', 'group', 'coord_index' (TexCoord). "
        "For vector/color values pass a dict {r,g,b,a}. "
        "For texture pass the asset path string."
    ),
    category="material",
    risk_level="medium",
)
def set_expression_property(arguments: dict) -> str:
    """设置材质表达式节点的属性"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in UE"})

    material_path = arguments.get("material_path", "")
    node_name = arguments.get("node_name", "")
    property_name = arguments.get("property_name", "")
    property_value = arguments.get("property_value")

    if not material_path or not node_name or not property_name:
        return json.dumps({
            "success": False,
            "error": "material_path, node_name, property_name are required",
        })

    mat, err = _load_material(material_path)
    if err:
        return err

    try:
        expr = _find_expression_by_name(mat, node_name)
        if expr is None:
            return json.dumps({
                "success": False,
                "error": f"Node not found: {node_name}",
            })

        # 特殊处理：texture 属性需要加载资产
        if property_name == "texture" and isinstance(property_value, str):
            tex = unreal.EditorAssetLibrary.load_asset(property_value)
            if tex is None:
                return json.dumps({
                    "success": False,
                    "error": f"Texture not found: {property_value}",
                })
            property_value = tex

        # 特殊处理：constant 属性（颜色/向量）
        if property_name == "constant" and isinstance(property_value, dict):
            property_value = unreal.LinearColor(
                r=float(property_value.get("r", 0)),
                g=float(property_value.get("g", 0)),
                b=float(property_value.get("b", 0)),
                a=float(property_value.get("a", 1)),
            )

        # 特殊处理：default_value 为 vector
        if property_name == "default_value" and isinstance(property_value, dict):
            property_value = unreal.LinearColor(
                r=float(property_value.get("r", 0)),
                g=float(property_value.get("g", 0)),
                b=float(property_value.get("b", 0)),
                a=float(property_value.get("a", 1)),
            )

        # 数值型自动转换
        if isinstance(property_value, (int, float)):
            property_value = float(property_value)

        with unreal.ScopedEditorTransaction("Set Expression Property"):
            expr.set_editor_property(property_name, property_value)

        return json.dumps({
            "success": True,
            "node": node_name,
            "property": property_name,
            "value": str(property_value),
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ============================================================================
# Tool: 移动节点位置
# ============================================================================

@ue_tool(
    name="set_expression_position",
    description=(
        "Move a MaterialExpression node to a new position in the graph editor. "
        "Provide material_path, node_name, pos_x (int), pos_y (int)."
    ),
    category="material",
    risk_level="low",
)
def set_expression_position(arguments: dict) -> str:
    """移动材质表达式节点位置"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in UE"})

    material_path = arguments.get("material_path", "")
    node_name = arguments.get("node_name", "")
    pos_x = int(arguments.get("pos_x", 0))
    pos_y = int(arguments.get("pos_y", 0))

    if not material_path or not node_name:
        return json.dumps({
            "success": False,
            "error": "material_path and node_name are required",
        })

    mat, err = _load_material(material_path)
    if err:
        return err

    try:
        expr = _find_expression_by_name(mat, node_name)
        if expr is None:
            return json.dumps({
                "success": False,
                "error": f"Node not found: {node_name}",
            })

        mel = unreal.MaterialEditingLibrary
        mel.set_material_expression_node_position(expr, pos_x, pos_y)

        return json.dumps({
            "success": True,
            "node": node_name,
            "position": [pos_x, pos_y],
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ============================================================================
# Tool: 重编译材质
# ============================================================================

@ue_tool(
    name="recompile_material",
    description=(
        "Recompile a Material after making changes to its node graph. "
        "Call this after finishing a batch of create/connect/edit operations. "
        "Provide material_path. Optionally save=true to save the asset."
    ),
    category="material",
    risk_level="medium",
)
def recompile_material(arguments: dict) -> str:
    """重编译材质并自动验证编译结果"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in UE"})

    material_path = arguments.get("material_path", "")
    save = arguments.get("save", True)

    if not material_path:
        return json.dumps({"success": False, "error": "material_path is required"})

    mat, err = _load_material(material_path)
    if err:
        return err

    try:
        mel = unreal.MaterialEditingLibrary

        # 编译
        mel.recompile_material(mat)

        # 自动验证：通过 shader instruction count 判断编译是否成功
        stats = mel.get_statistics(mat)
        ps_instr = stats.get_editor_property("num_pixel_shader_instructions")
        vs_instr = stats.get_editor_property("num_vertex_shader_instructions")
        num_samplers = stats.get_editor_property("num_samplers")
        num_textures = stats.get_editor_property("num_pixel_texture_samples")

        compile_ok = ps_instr > 0

        # 只有编译成功才保存
        saved = False
        if compile_ok and save:
            unreal.EditorAssetLibrary.save_asset(material_path)
            saved = True

        return json.dumps({
            "success": compile_ok,
            "material": material_path,
            "compiled": compile_ok,
            "compile_error": None if compile_ok else (
                "Compilation failed: 0 pixel shader instructions. "
                "Check node connections and HLSL syntax in Custom nodes. "
                "Common issues: undefined variables, missing inputs, type mismatches."
            ),
            "stats": {
                "pixel_instructions": ps_instr,
                "vertex_instructions": vs_instr,
                "samplers": num_samplers,
                "texture_samples": num_textures,
            },
            "saved": saved,
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ============================================================================
# Tool: 设置材质属性（BlendMode, ShadingModel, TwoSided 等）
# ============================================================================

@ue_tool(
    name="set_material_properties",
    description=(
        "Set top-level properties on a Material asset (not expression nodes). "
        "Provide material_path and a properties dict. "
        "Supported keys: blend_mode ('Opaque','Translucent','Masked','Additive','Modulate'), "
        "shading_model ('DefaultLit','Unlit','Subsurface','SubsurfaceProfile','ClearCoat','TwoSidedFoliage'), "
        "two_sided (bool), opacity_mask_clip_value (float), "
        "is_thin_surface (bool), allow_negative_emissive_color (bool)."
    ),
    category="material",
    risk_level="medium",
)
def set_material_properties(arguments: dict) -> str:
    """设置材质顶层属性"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in UE"})

    material_path = arguments.get("material_path", "")
    properties = arguments.get("properties", {})

    if not material_path:
        return json.dumps({"success": False, "error": "material_path is required"})
    if not properties:
        return json.dumps({"success": False, "error": "properties dict is required"})

    mat, err = _load_material(material_path)
    if err:
        return err

    try:
        applied = {}

        with unreal.ScopedEditorTransaction("Set Material Properties"):
            # BlendMode
            bm = properties.get("blend_mode")
            if bm:
                _BM = {
                    "Opaque": unreal.BlendMode.BLEND_OPAQUE,
                    "Translucent": unreal.BlendMode.BLEND_TRANSLUCENT,
                    "Masked": unreal.BlendMode.BLEND_MASKED,
                    "Additive": unreal.BlendMode.BLEND_ADDITIVE,
                    "Modulate": unreal.BlendMode.BLEND_MODULATE,
                }
                if bm in _BM:
                    mat.set_editor_property("blend_mode", _BM[bm])
                    applied["blend_mode"] = bm

            # ShadingModel
            sm = properties.get("shading_model")
            if sm:
                _SM = {
                    "DefaultLit": unreal.MaterialShadingModel.MSM_DEFAULT_LIT,
                    "Unlit": unreal.MaterialShadingModel.MSM_UNLIT,
                    "Subsurface": unreal.MaterialShadingModel.MSM_SUBSURFACE,
                    "SubsurfaceProfile": unreal.MaterialShadingModel.MSM_SUBSURFACE_PROFILE,
                    "ClearCoat": unreal.MaterialShadingModel.MSM_CLEAR_COAT,
                    "TwoSidedFoliage": unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE,
                }
                if sm in _SM:
                    mat.set_editor_property("shading_model", _SM[sm])
                    applied["shading_model"] = sm

            # Bool / float properties
            if "two_sided" in properties:
                mat.set_editor_property("two_sided", bool(properties["two_sided"]))
                applied["two_sided"] = bool(properties["two_sided"])

            if "opacity_mask_clip_value" in properties:
                val = float(properties["opacity_mask_clip_value"])
                mat.set_editor_property("opacity_mask_clip_value", val)
                applied["opacity_mask_clip_value"] = val

        return json.dumps({
            "success": True,
            "material": material_path,
            "applied": applied,
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ============================================================================
# Tool: 列出材质中的所有表达式节点（轻量版）
# ============================================================================

@ue_tool(
    name="list_material_expressions",
    description=(
        "List all MaterialExpression nodes in a Material (flat list, no connections). "
        "Lighter than get_material_nodes — use for quick inventory. "
        "Returns name, class, position for each node. "
        "Provide material_path. Optional: max_count (default 200)."
    ),
    category="material",
    risk_level="low",
)
def list_material_expressions(arguments: dict) -> str:
    """列出材质中的所有表达式节点"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in UE"})

    material_path = arguments.get("material_path", "")
    max_count = min(int(arguments.get("max_count", 200)), 500)

    if not material_path:
        return json.dumps({"success": False, "error": "material_path is required"})

    mat, err = _load_material(material_path)
    if err:
        return err

    try:
        mel = unreal.MaterialEditingLibrary
        total = mel.get_num_material_expressions(mat)

        # BFS 遍历所有连接的节点
        visited = set()
        queue = []
        nodes = []

        # 从所有材质属性入口收集根节点
        _ALL_PROPS = [
            unreal.MaterialProperty.MP_BASE_COLOR,
            unreal.MaterialProperty.MP_METALLIC,
            unreal.MaterialProperty.MP_SPECULAR,
            unreal.MaterialProperty.MP_ROUGHNESS,
            unreal.MaterialProperty.MP_NORMAL,
            unreal.MaterialProperty.MP_EMISSIVE_COLOR,
            unreal.MaterialProperty.MP_OPACITY,
            unreal.MaterialProperty.MP_OPACITY_MASK,
            unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET,
            unreal.MaterialProperty.MP_AMBIENT_OCCLUSION,
            unreal.MaterialProperty.MP_REFRACTION,
        ]
        for prop in _ALL_PROPS:
            try:
                node = mel.get_material_property_input_node(mat, prop)
                if node is not None:
                    queue.append(node)
            except Exception:
                continue

        while queue and len(nodes) < max_count:
            current = queue.pop(0)
            name = str(current.get_name())
            if name in visited:
                continue
            visited.add(name)
            nodes.append(_expression_info(current))
            try:
                inputs = mel.get_inputs_for_material_expression(mat, current)
                for inp in inputs:
                    if inp is not None and str(inp.get_name()) not in visited:
                        queue.append(inp)
            except Exception:
                continue

        return json.dumps({
            "success": True,
            "material": str(mat.get_name()),
            "path": material_path,
            "total": total,
            "listed": len(nodes),
            "nodes": nodes,
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
