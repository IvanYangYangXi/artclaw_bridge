"""
material_ops.py - 材质操作 Skill
==================================

P0 核心 Skill：材质查询、设置、创建材质实例等操作。
Skill Hub 自动发现并注册。保存后热重载生效。
"""

from skill_hub import tool as ue_tool
import json

try:
    import unreal
except ImportError:
    unreal = None  # 允许在 UE 外部测试


# ============================================================================
# 辅助函数
# ============================================================================

def _find_actor_by_name(actor_name: str):
    """按名称查找 Actor"""
    actors = unreal.EditorLevelLibrary.get_all_level_actors()
    for actor in actors:
        if (str(actor.get_name()) == actor_name or
            str(actor.get_actor_label()) == actor_name):
            return actor
    return None


def _get_static_mesh_component(actor):
    """获取 Actor 的第一个 StaticMeshComponent"""
    components = actor.get_components_by_class(unreal.StaticMeshComponent)
    return components[0] if components else None


def _prune_material_info(material) -> dict:
    """将材质对象转为精简字典"""
    if material is None:
        return {"name": "None", "class": "None", "path": ""}
    return {
        "name": str(material.get_name()),
        "class": str(material.get_class().get_name()),
        "path": str(material.get_path_name()),
    }


# ============================================================================
# Material Skills - 查询
# ============================================================================

@ue_tool(
    name="get_actor_materials",
    description="Get all materials assigned to an actor's mesh components. "
                "Returns material name, class, path, and slot index for each material. "
                "Works with Static Mesh Actors and other actors with mesh components.",
    category="material",
    risk_level="low",
)
def get_actor_materials(arguments: dict) -> str:
    """获取 Actor 上的所有材质"""
    if unreal is None:
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    actor_name = arguments.get("actor_name", "")
    if not actor_name:
        return json.dumps({"success": False, "error": "需要提供 actor_name 参数"})

    try:
        actor = _find_actor_by_name(actor_name)
        if actor is None:
            return json.dumps({"success": False, "error": f"未找到 Actor: {actor_name}"})

        # 尝试获取所有 PrimitiveComponent
        mesh_components = actor.get_components_by_class(unreal.PrimitiveComponent)
        if not mesh_components:
            return json.dumps({
                "success": False,
                "error": f"Actor '{actor_name}' 没有网格组件"
            })

        all_materials = []
        for comp in mesh_components:
            comp_name = str(comp.get_name())
            try:
                num_mats = comp.get_num_materials()
                for i in range(num_mats):
                    mat = comp.get_material(i)
                    all_materials.append({
                        "component": comp_name,
                        "slot_index": i,
                        **_prune_material_info(mat),
                    })
            except Exception:
                pass

        return json.dumps({
            "success": True,
            "actor": actor_name,
            "material_count": len(all_materials),
            "materials": all_materials,
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="get_material_parameters",
    description="Get the editable parameters of a material or material instance. "
                "Returns scalar, vector, and texture parameters with their current values. "
                "Provide the material asset path.",
    category="material",
    risk_level="low",
)
def get_material_parameters(arguments: dict) -> str:
    """获取材质的可编辑参数"""
    if unreal is None:
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    material_path = arguments.get("material_path", "")
    if not material_path:
        return json.dumps({"success": False, "error": "需要提供 material_path 参数"})

    try:
        mat = unreal.EditorAssetLibrary.load_asset(material_path)
        if mat is None:
            return json.dumps({
                "success": False,
                "error": f"未找到材质: {material_path}"
            })

        result = {
            "success": True,
            "material": str(mat.get_name()),
            "class": str(mat.get_class().get_name()),
            "scalar_parameters": [],
            "vector_parameters": [],
            "texture_parameters": [],
        }

        # 材质实例的参数提取
        if isinstance(mat, unreal.MaterialInstance):
            # Scalar
            try:
                scalar_params = unreal.MaterialEditingLibrary.get_scalar_parameter_names(mat)
                for param_name in scalar_params:
                    val = unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(mat, str(param_name))
                    result["scalar_parameters"].append({
                        "name": str(param_name),
                        "value": round(float(val), 4),
                    })
            except Exception:
                pass

            # Vector
            try:
                vector_params = unreal.MaterialEditingLibrary.get_vector_parameter_names(mat)
                for param_name in vector_params:
                    val = unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(mat, str(param_name))
                    result["vector_parameters"].append({
                        "name": str(param_name),
                        "value": {"r": round(val.r, 4), "g": round(val.g, 4), "b": round(val.b, 4), "a": round(val.a, 4)},
                    })
            except Exception:
                pass

            # Texture
            try:
                texture_params = unreal.MaterialEditingLibrary.get_texture_parameter_names(mat)
                for param_name in texture_params:
                    tex = unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(mat, str(param_name))
                    result["texture_parameters"].append({
                        "name": str(param_name),
                        "value": str(tex.get_path_name()) if tex else "None",
                    })
            except Exception:
                pass

        return json.dumps(result, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ============================================================================
# Material Skills - 修改
# ============================================================================

@ue_tool(
    name="set_actor_material",
    description="Set a material on an actor's mesh component by slot index. "
                "Provide the actor name, material asset path, and slot index (default 0). "
                "The material must already exist in the content browser.",
    category="material",
    risk_level="medium",
)
def set_actor_material(arguments: dict) -> str:
    """设置 Actor 的材质"""
    if unreal is None:
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    actor_name = arguments.get("actor_name", "")
    material_path = arguments.get("material_path", "")
    slot_index = arguments.get("slot_index", 0)

    if not actor_name:
        return json.dumps({"success": False, "error": "需要提供 actor_name 参数"})
    if not material_path:
        return json.dumps({"success": False, "error": "需要提供 material_path 参数"})

    try:
        actor = _find_actor_by_name(actor_name)
        if actor is None:
            return json.dumps({"success": False, "error": f"未找到 Actor: {actor_name}"})

        material = unreal.EditorAssetLibrary.load_asset(material_path)
        if material is None:
            return json.dumps({
                "success": False,
                "error": f"未找到材质: {material_path}"
            })

        mesh_comp = _get_static_mesh_component(actor)
        if mesh_comp is None:
            # 尝试 PrimitiveComponent
            comps = actor.get_components_by_class(unreal.PrimitiveComponent)
            mesh_comp = comps[0] if comps else None

        if mesh_comp is None:
            return json.dumps({
                "success": False,
                "error": f"Actor '{actor_name}' 没有网格组件"
            })

        num_slots = mesh_comp.get_num_materials()
        if slot_index >= num_slots:
            return json.dumps({
                "success": False,
                "error": f"插槽索引 {slot_index} 超出范围（该 Actor 有 {num_slots} 个材质插槽）"
            })

        old_mat = mesh_comp.get_material(slot_index)
        old_mat_name = str(old_mat.get_name()) if old_mat else "None"

        with unreal.ScopedEditorTransaction("Set Material via AI"):
            mesh_comp.set_material(slot_index, material)

        return json.dumps({
            "success": True,
            "actor": actor_name,
            "slot_index": slot_index,
            "old_material": old_mat_name,
            "new_material": str(material.get_name()),
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="create_material_instance",
    description="Create a new Material Instance Constant from a parent material. "
                "Provide the parent material path and the desired name/directory for the instance. "
                "Optionally set initial scalar and vector parameter overrides.",
    category="material",
    risk_level="medium",
)
def create_material_instance(arguments: dict) -> str:
    """创建材质实例"""
    if unreal is None:
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    parent_path = arguments.get("parent_path", "")
    instance_name = arguments.get("instance_name", "")
    target_dir = arguments.get("target_dir", "/Game/Materials/Instances")
    scalar_overrides = arguments.get("scalar_overrides", {})
    vector_overrides = arguments.get("vector_overrides", {})

    if not parent_path:
        return json.dumps({"success": False, "error": "需要提供 parent_path 参数"})
    if not instance_name:
        return json.dumps({"success": False, "error": "需要提供 instance_name 参数"})

    try:
        # 加载父材质
        parent = unreal.EditorAssetLibrary.load_asset(parent_path)
        if parent is None:
            return json.dumps({
                "success": False,
                "error": f"未找到父材质: {parent_path}"
            })

        # 创建材质实例
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        factory = unreal.MaterialInstanceConstantFactoryNew()
        instance = asset_tools.create_asset(
            instance_name,
            target_dir,
            unreal.MaterialInstanceConstant,
            factory,
        )

        if instance is None:
            return json.dumps({
                "success": False,
                "error": "创建材质实例失败"
            })

        # 设置父材质
        unreal.MaterialEditingLibrary.set_material_instance_parent(instance, parent)

        # 设置 scalar 参数覆盖
        for param_name, value in scalar_overrides.items():
            unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
                instance, param_name, float(value)
            )

        # 设置 vector 参数覆盖
        for param_name, value in vector_overrides.items():
            if isinstance(value, dict):
                color = unreal.LinearColor(
                    r=float(value.get("r", 0)),
                    g=float(value.get("g", 0)),
                    b=float(value.get("b", 0)),
                    a=float(value.get("a", 1)),
                )
            else:
                color = unreal.LinearColor(r=0, g=0, b=0, a=1)
            unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
                instance, param_name, color
            )

        # 保存
        unreal.EditorAssetLibrary.save_asset(instance.get_path_name())

        return json.dumps({
            "success": True,
            "instance": {
                "name": str(instance.get_name()),
                "path": str(instance.get_path_name()),
                "parent": str(parent.get_name()),
            },
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
