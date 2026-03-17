"""
scene_ops.py - 场景操作 Skill
===============================

P0 核心 Skill：Actor 的增删改查、选择、变换等场景级操作。
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
    """按名称查找 Actor（匹配 name 或 label）"""
    actors = unreal.EditorLevelLibrary.get_all_level_actors()
    for actor in actors:
        if (str(actor.get_name()) == actor_name or
            str(actor.get_actor_label()) == actor_name):
            return actor
    return None


def _prune_actor(actor, include_transform: bool = True) -> dict:
    """将 Actor 转为精简字典"""
    data = {
        "name": str(actor.get_name()),
        "label": str(actor.get_actor_label()),
        "class": str(actor.get_class().get_name()),
    }
    if include_transform:
        try:
            loc = actor.get_actor_location()
            rot = actor.get_actor_rotation()
            scale = actor.get_actor_scale3d()
            data["location"] = {"x": round(loc.x, 2), "y": round(loc.y, 2), "z": round(loc.z, 2)}
            data["rotation"] = {"pitch": round(rot.pitch, 2), "yaw": round(rot.yaw, 2), "roll": round(rot.roll, 2)}
            data["scale"] = {"x": round(scale.x, 2), "y": round(scale.y, 2), "z": round(scale.z, 2)}
        except Exception:
            pass
    # Tags
    try:
        tags = [str(t) for t in actor.tags]
        if tags:
            data["tags"] = tags
    except Exception:
        pass
    return data


def _parse_vector(d: dict, default_x=0.0, default_y=0.0, default_z=0.0) -> unreal.Vector:
    """从 dict 解析 Vector"""
    return unreal.Vector(
        float(d.get("x", default_x)),
        float(d.get("y", default_y)),
        float(d.get("z", default_z)),
    )


def _parse_rotator(d: dict) -> unreal.Rotator:
    """从 dict 解析 Rotator"""
    return unreal.Rotator(
        float(d.get("pitch", 0.0)),
        float(d.get("yaw", 0.0)),
        float(d.get("roll", 0.0)),
    )


# ============================================================================
# Scene Skills - 查询类
# ============================================================================

@ue_tool(
    name="get_selected_actors",
    description="Get the list of currently selected actors in the level editor. "
                "Returns each actor's name, class, location, rotation, scale, and tags. "
                "Use this to understand what the user is working with.",
    category="scene",
    risk_level="low",
)
def get_selected_actors(arguments: dict) -> str:
    """获取当前编辑器中选中的 Actor 列表"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    include_transform = arguments.get("include_transform", True)
    limit = arguments.get("limit", 100)

    try:
        selected = unreal.EditorLevelLibrary.get_selected_level_actors()
        total = len(selected)
        actors = [_prune_actor(a, include_transform) for a in selected[:limit]]

        result = {
            "success": True,
            "count": len(actors),
            "actors": actors,
        }
        if total > limit:
            result["truncated"] = True
            result["total"] = total

        return json.dumps(result, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="get_all_level_actors",
    description="Get all actors in the current level with optional class filter. "
                "Returns name, class, location for each actor. "
                "Use 'class_filter' to narrow results (e.g., 'StaticMeshActor', 'PointLight').",
    category="scene",
    risk_level="low",
)
def get_all_level_actors(arguments: dict) -> str:
    """获取当前关卡中所有 Actor，可按类名过滤"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    class_filter = arguments.get("class_filter", "")
    include_transform = arguments.get("include_transform", True)
    limit = arguments.get("limit", 100)

    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
        total_in_level = len(actors)

        if class_filter:
            actors = [
                a for a in actors
                if class_filter.lower() in str(a.get_class().get_name()).lower()
            ]

        total_filtered = len(actors)
        result_actors = [_prune_actor(a, include_transform) for a in actors[:limit]]

        result = {
            "success": True,
            "total_in_level": total_in_level,
            "filtered_count": total_filtered,
            "count": len(result_actors),
            "actors": result_actors,
        }
        if total_filtered > limit:
            result["truncated"] = True

        return json.dumps(result, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="get_actor_details",
    description="Get detailed information about a specific actor by name. "
                "Returns full transform, class, tags, components, and properties. "
                "Provide either the internal name or the display label.",
    category="scene",
    risk_level="low",
)
def get_actor_details(arguments: dict) -> str:
    """获取指定 Actor 的详细信息"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    actor_name = arguments.get("actor_name", "")
    if not actor_name:
        return json.dumps({"success": False, "error": "actor_name is required"})

    try:
        actor = _find_actor_by_name(actor_name)
        if actor is None:
            return json.dumps({"success": False, "error": f"Actor not found: {actor_name}"})

        data = _prune_actor(actor, include_transform=True)

        # 附加详情
        try:
            data["visible"] = not actor.is_hidden_ed()
        except Exception:
            pass

        try:
            data["mobility"] = str(actor.root_component.mobility) if actor.root_component else "unknown"
        except Exception:
            pass

        # 组件列表
        try:
            components = actor.get_components_by_class(unreal.ActorComponent)
            data["components"] = [
                {"name": str(c.get_name()), "class": str(c.get_class().get_name())}
                for c in components[:20]
            ]
        except Exception:
            pass

        # 父 Actor
        try:
            parent = actor.get_attach_parent_actor()
            if parent:
                data["parent"] = str(parent.get_actor_label())
        except Exception:
            pass

        return json.dumps({"success": True, "actor": data}, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ============================================================================
# Scene Skills - 创建 / 修改 / 删除
# ============================================================================

@ue_tool(
    name="spawn_actor",
    description="Spawn a new actor in the current level by class name or asset path. "
                "Supports setting initial location, rotation, scale, and display label. "
                "For static meshes, provide asset_path like '/Engine/BasicShapes/Cube'. "
                "Returns the spawned actor's name, class, and transform.",
    category="scene",
    risk_level="medium",
)
def spawn_actor(arguments: dict) -> str:
    """在关卡中生成新 Actor"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    asset_path = arguments.get("asset_path", "")
    actor_class = arguments.get("actor_class", "")
    location = arguments.get("location", {"x": 0, "y": 0, "z": 0})
    rotation = arguments.get("rotation", {"pitch": 0, "yaw": 0, "roll": 0})
    scale = arguments.get("scale", None)
    label = arguments.get("label", "")

    if not asset_path and not actor_class:
        return json.dumps({
            "success": False,
            "error": "Either asset_path or actor_class is required"
        })

    try:
        loc = _parse_vector(location)
        rot = _parse_rotator(rotation)

        with unreal.ScopedEditorTransaction("Spawn Actor via AI"):
            if asset_path:
                # 从资产路径生成
                asset = unreal.EditorAssetLibrary.load_asset(asset_path)
                if asset is None:
                    return json.dumps({
                        "success": False,
                        "error": f"Asset not found: {asset_path}"
                    })
                actor = unreal.EditorLevelLibrary.spawn_actor_from_object(
                    asset, loc, rot
                )
            else:
                # 按类名生成
                cls = unreal.EditorAssetLibrary.load_blueprint_class(actor_class)
                if cls is None:
                    return json.dumps({
                        "success": False,
                        "error": f"Actor class not found: {actor_class}"
                    })
                actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
                    cls, loc, rot
                )

            if actor is None:
                return json.dumps({
                    "success": False,
                    "error": "Failed to spawn actor (returned None)"
                })

            # 设置缩放
            if scale:
                actor.set_actor_scale3d(_parse_vector(scale, 1.0, 1.0, 1.0))

            # 设置显示标签
            if label:
                actor.set_actor_label(label)

        return json.dumps({
            "success": True,
            "actor": _prune_actor(actor),
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="delete_actors",
    description="Delete one or more actors from the current level by name. "
                "Provide a list of actor names (internal name or display label). "
                "This operation can be undone with Ctrl+Z.",
    category="scene",
    risk_level="high",
)
def delete_actors(arguments: dict) -> str:
    """删除指定名称的 Actor"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    actor_names = arguments.get("actor_names", [])
    if isinstance(actor_names, str):
        actor_names = [actor_names]
    if not actor_names:
        return json.dumps({"success": False, "error": "actor_names is required (string or list)"})

    try:
        deleted = []
        not_found = []

        with unreal.ScopedEditorTransaction("Delete Actors via AI"):
            for name in actor_names:
                actor = _find_actor_by_name(name)
                if actor is None:
                    not_found.append(name)
                else:
                    label = str(actor.get_actor_label())
                    success = unreal.EditorLevelLibrary.destroy_actor(actor)
                    if success:
                        deleted.append(label)
                    else:
                        not_found.append(name)

        return json.dumps({
            "success": True,
            "deleted_count": len(deleted),
            "deleted": deleted,
            "not_found": not_found,
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="set_actor_transform",
    description="Set the transform (location, rotation, scale) of an actor by name. "
                "Provide any combination of location, rotation, scale — "
                "only the specified fields will be updated.",
    category="scene",
    risk_level="medium",
)
def set_actor_transform(arguments: dict) -> str:
    """设置 Actor 的变换（位置、旋转、缩放）"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    actor_name = arguments.get("actor_name", "")
    if not actor_name:
        return json.dumps({"success": False, "error": "actor_name is required"})

    location = arguments.get("location", None)
    rotation = arguments.get("rotation", None)
    scale = arguments.get("scale", None)

    if location is None and rotation is None and scale is None:
        return json.dumps({
            "success": False,
            "error": "At least one of location, rotation, or scale is required"
        })

    try:
        actor = _find_actor_by_name(actor_name)
        if actor is None:
            return json.dumps({"success": False, "error": f"Actor not found: {actor_name}"})

        with unreal.ScopedEditorTransaction("Set Actor Transform via AI"):
            if location is not None:
                actor.set_actor_location(_parse_vector(location), sweep=False, teleport=True)
            if rotation is not None:
                actor.set_actor_rotation(_parse_rotator(rotation), teleport_physics=True)
            if scale is not None:
                actor.set_actor_scale3d(_parse_vector(scale, 1.0, 1.0, 1.0))

        return json.dumps({
            "success": True,
            "actor": _prune_actor(actor),
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="rename_actor",
    description="Rename an actor's display label in the level. "
                "The internal name remains unchanged. "
                "Provide the current name (or label) and the new label.",
    category="scene",
    risk_level="medium",
)
def rename_actor(arguments: dict) -> str:
    """重命名 Actor 的显示标签"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    actor_name = arguments.get("actor_name", "")
    new_label = arguments.get("new_label", "")
    if not actor_name:
        return json.dumps({"success": False, "error": "actor_name is required"})
    if not new_label:
        return json.dumps({"success": False, "error": "new_label is required"})

    try:
        actor = _find_actor_by_name(actor_name)
        if actor is None:
            return json.dumps({"success": False, "error": f"Actor not found: {actor_name}"})

        old_label = str(actor.get_actor_label())
        with unreal.ScopedEditorTransaction("Rename Actor via AI"):
            actor.set_actor_label(new_label)

        return json.dumps({
            "success": True,
            "old_label": old_label,
            "new_label": new_label,
            "actor": _prune_actor(actor),
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="focus_on_actor",
    description="Focus the viewport camera on a specific actor by name. "
                "Optionally select the actor in the editor. "
                "Useful for navigating to objects of interest.",
    category="scene",
    risk_level="low",
)
def focus_on_actor(arguments: dict) -> str:
    """将视口聚焦到指定 Actor"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    actor_name = arguments.get("actor_name", "")
    select = arguments.get("select", True)
    if not actor_name:
        return json.dumps({"success": False, "error": "actor_name is required"})

    try:
        actor = _find_actor_by_name(actor_name)
        if actor is None:
            return json.dumps({"success": False, "error": f"Actor not found: {actor_name}"})

        if select:
            # 选中该 Actor
            unreal.EditorLevelLibrary.set_selected_level_actors([actor])

        # 聚焦视口
        unreal.EditorLevelLibrary.pilot_level_actor(actor)

        return json.dumps({
            "success": True,
            "focused_on": str(actor.get_actor_label()),
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="select_actors",
    description="Select actors in the level editor by name list. "
                "Clears current selection and selects only the specified actors. "
                "Returns the list of successfully selected actors.",
    category="scene",
    risk_level="low",
)
def select_actors(arguments: dict) -> str:
    """选择指定名称的 Actor"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    actor_names = arguments.get("actor_names", [])
    if isinstance(actor_names, str):
        actor_names = [actor_names]
    if not actor_names:
        return json.dumps({"success": False, "error": "actor_names is required"})

    try:
        found = []
        not_found = []
        actors_to_select = []

        for name in actor_names:
            actor = _find_actor_by_name(name)
            if actor:
                actors_to_select.append(actor)
                found.append(str(actor.get_actor_label()))
            else:
                not_found.append(name)

        unreal.EditorLevelLibrary.set_selected_level_actors(actors_to_select)

        return json.dumps({
            "success": True,
            "selected_count": len(found),
            "selected": found,
            "not_found": not_found,
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="duplicate_actors",
    description="Duplicate one or more actors in the level. "
                "Optionally offset the duplicates from the originals. "
                "Returns the names and transforms of the new actors.",
    category="scene",
    risk_level="medium",
)
def duplicate_actors(arguments: dict) -> str:
    """复制指定的 Actor"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    actor_names = arguments.get("actor_names", [])
    if isinstance(actor_names, str):
        actor_names = [actor_names]
    if not actor_names:
        return json.dumps({"success": False, "error": "actor_names is required"})

    offset = arguments.get("offset", {"x": 100, "y": 0, "z": 0})

    try:
        duplicated = []
        not_found = []

        with unreal.ScopedEditorTransaction("Duplicate Actors via AI"):
            for name in actor_names:
                actor = _find_actor_by_name(name)
                if actor is None:
                    not_found.append(name)
                    continue

                # 选中该 Actor 并复制
                unreal.EditorLevelLibrary.set_selected_level_actors([actor])
                new_actors = unreal.EditorLevelLibrary.get_selected_level_actors()

                # 使用 EditorLevelUtils 或手动方式
                loc = actor.get_actor_location()
                rot = actor.get_actor_rotation()

                # 尝试使用 join_static_mesh_actors / 或直接 spawn
                # 最可靠的方式：通过 EditorLevelLibrary
                dup = unreal.EditorLevelLibrary.spawn_actor_from_object(
                    actor.get_class().get_default_object(),
                    unreal.Vector(
                        loc.x + float(offset.get("x", 100)),
                        loc.y + float(offset.get("y", 0)),
                        loc.z + float(offset.get("z", 0)),
                    ),
                    rot,
                )
                if dup:
                    dup.set_actor_scale3d(actor.get_actor_scale3d())
                    dup.set_actor_label(str(actor.get_actor_label()) + "_Copy")
                    duplicated.append(_prune_actor(dup))

        return json.dumps({
            "success": True,
            "duplicated_count": len(duplicated),
            "duplicated": duplicated,
            "not_found": not_found,
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
