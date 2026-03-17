"""
level_ops.py - 关卡操作 Skill
================================

P0 核心 Skill：关卡查询、保存、加载、Actor 统计等操作。
Skill Hub 自动发现并注册。保存后热重载生效。
"""

from skill_hub import tool as ue_tool
import json

try:
    import unreal
except ImportError:
    unreal = None  # 允许在 UE 外部测试


# ============================================================================
# Level Skills - 查询
# ============================================================================

@ue_tool(
    name="get_current_level",
    description="Get information about the currently open level. "
                "Returns the level name, path, map filename, and basic actor counts.",
    category="level",
    risk_level="low",
)
def get_current_level(arguments: dict) -> str:
    """获取当前打开的关卡信息"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
        if world is None:
            return json.dumps({
                "success": False,
                "error": "No world currently open"
            })

        level_name = str(world.get_name())
        map_name = str(world.get_map_name()) if hasattr(world, 'get_map_name') else level_name

        # 获取关卡路径
        level_path = ""
        try:
            level_path = str(world.get_path_name())
        except Exception:
            pass

        actors = unreal.EditorLevelLibrary.get_all_level_actors()

        return json.dumps({
            "success": True,
            "level": {
                "name": level_name,
                "map_name": map_name,
                "path": level_path,
                "actor_count": len(actors),
            },
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="get_level_actors",
    description="Get a categorized summary of all actors in the current level. "
                "Groups actors by class and returns counts. "
                "More efficient than get_all_level_actors for large levels.",
    category="level",
    risk_level="low",
)
def get_level_actors(arguments: dict) -> str:
    """获取关卡中按类别分组的 Actor 统计"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    top_n = arguments.get("top_n", 20)

    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
        class_counts = {}
        for actor in actors:
            cls_name = str(actor.get_class().get_name())
            class_counts[cls_name] = class_counts.get(cls_name, 0) + 1

        sorted_classes = sorted(class_counts.items(), key=lambda x: -x[1])

        return json.dumps({
            "success": True,
            "total_actors": len(actors),
            "unique_classes": len(class_counts),
            "classes": [
                {"class": cls, "count": cnt}
                for cls, cnt in sorted_classes[:top_n]
            ],
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ============================================================================
# Level Skills - 操作
# ============================================================================

@ue_tool(
    name="save_current_level",
    description="Save the current level to disk. "
                "Returns success/failure status.",
    category="level",
    risk_level="medium",
)
def save_current_level(arguments: dict) -> str:
    """保存当前关卡"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
        if world is None:
            return json.dumps({
                "success": False,
                "error": "No world currently open"
            })

        level_name = str(world.get_name())

        # 保存当前关卡
        success = unreal.EditorLevelLibrary.save_current_level()

        return json.dumps({
            "success": success,
            "level": level_name,
            "message": f"Level '{level_name}' saved successfully" if success else f"Failed to save level '{level_name}'",
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="save_all_dirty_packages",
    description="Save all modified (dirty) assets and levels. "
                "Equivalent to File > Save All in the editor. "
                "Returns the count of packages saved.",
    category="level",
    risk_level="medium",
)
def save_all_dirty_packages(arguments: dict) -> str:
    """保存所有未保存的修改"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    try:
        success = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(
            save_map_packages=True,
            save_content_packages=True,
        )

        return json.dumps({
            "success": success,
            "message": "All dirty packages saved" if success else "Some packages failed to save",
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="open_level",
    description="Open a level by its asset path in the editor. "
                "WARNING: Unsaved changes to the current level will be lost unless saved first. "
                "Path format: '/Game/Maps/MyLevel'.",
    category="level",
    risk_level="high",
)
def open_level(arguments: dict) -> str:
    """打开指定关卡"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    level_path = arguments.get("level_path", "")
    if not level_path:
        return json.dumps({"success": False, "error": "level_path is required"})

    try:
        # 检查关卡是否存在
        if not unreal.EditorAssetLibrary.does_asset_exist(level_path):
            return json.dumps({
                "success": False,
                "error": f"Level not found: {level_path}"
            })

        success = unreal.EditorLevelLibrary.load_level(level_path)

        return json.dumps({
            "success": True,
            "level_path": level_path,
            "message": f"Level opened: {level_path}",
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# ============================================================================
# Level Skills - 视口
# ============================================================================

@ue_tool(
    name="get_viewport_info",
    description="Get the current viewport camera location, rotation, and FOV. "
                "Useful for understanding what the user is looking at.",
    category="level",
    risk_level="low",
)
def get_viewport_info(arguments: dict) -> str:
    """获取当前视口相机信息"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    try:
        # 使用 EditorLevelLibrary 获取视口信息
        loc = unreal.EditorLevelLibrary.get_level_viewport_camera_info()
        if loc is not None:
            # loc 是一个 tuple (location, rotation)
            camera_loc, camera_rot = loc
            return json.dumps({
                "success": True,
                "camera": {
                    "location": {
                        "x": round(camera_loc.x, 2),
                        "y": round(camera_loc.y, 2),
                        "z": round(camera_loc.z, 2),
                    },
                    "rotation": {
                        "pitch": round(camera_rot.pitch, 2),
                        "yaw": round(camera_rot.yaw, 2),
                        "roll": round(camera_rot.roll, 2),
                    },
                },
            }, default=str)
        else:
            return json.dumps({
                "success": False,
                "error": "Could not retrieve viewport camera info"
            })

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="set_viewport_camera",
    description="Set the viewport camera to a specific location and rotation. "
                "Useful for navigating to specific areas or setting up screenshot angles.",
    category="level",
    risk_level="low",
)
def set_viewport_camera(arguments: dict) -> str:
    """设置视口相机的位置和朝向"""
    if unreal is None:
        return json.dumps({"success": False, "error": "Not running in Unreal Engine"})

    location = arguments.get("location", None)
    rotation = arguments.get("rotation", None)

    if location is None and rotation is None:
        return json.dumps({
            "success": False,
            "error": "At least one of location or rotation is required"
        })

    try:
        # 获取当前视口信息作为基准
        current = unreal.EditorLevelLibrary.get_level_viewport_camera_info()
        if current is None:
            return json.dumps({
                "success": False,
                "error": "Could not access viewport camera"
            })

        curr_loc, curr_rot = current

        if location is not None:
            new_loc = unreal.Vector(
                float(location.get("x", curr_loc.x)),
                float(location.get("y", curr_loc.y)),
                float(location.get("z", curr_loc.z)),
            )
        else:
            new_loc = curr_loc

        if rotation is not None:
            new_rot = unreal.Rotator(
                float(rotation.get("pitch", curr_rot.pitch)),
                float(rotation.get("yaw", curr_rot.yaw)),
                float(rotation.get("roll", curr_rot.roll)),
            )
        else:
            new_rot = curr_rot

        unreal.EditorLevelLibrary.set_level_viewport_camera_info(new_loc, new_rot)

        return json.dumps({
            "success": True,
            "camera": {
                "location": {"x": round(new_loc.x, 2), "y": round(new_loc.y, 2), "z": round(new_loc.z, 2)},
                "rotation": {"pitch": round(new_rot.pitch, 2), "yaw": round(new_rot.yaw, 2), "roll": round(new_rot.roll, 2)},
            },
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
