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
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

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
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

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
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    actor_name = arguments.get("actor_name", "")
    if not actor_name:
        return json.dumps({"success": False, "error": "需要提供 actor_name 参数"})

    try:
        actor = _find_actor_by_name(actor_name)
        if actor is None:
            return json.dumps({"success": False, "error": f"未找到 Actor: {actor_name}"})

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
# Scene Skills - 视口感知
# ============================================================================

def _is_in_view_frustum(actor_loc, cam_loc, cam_forward, cam_right, cam_up,
                        h_half_rad, v_half_rad, max_distance):
    """判断一个点是否在视锥体内（简化版：基于角度 + 距离）"""
    import math
    dx = actor_loc.x - cam_loc.x
    dy = actor_loc.y - cam_loc.y
    dz = actor_loc.z - cam_loc.z
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    if dist < 1.0:
        return True, dist
    if dist > max_distance:
        return False, dist
    # 归一化方向
    inv_dist = 1.0 / dist
    dir_x, dir_y, dir_z = dx * inv_dist, dy * inv_dist, dz * inv_dist
    # 与相机前方的夹角（水平 + 垂直分别判断）
    dot_forward = dir_x * cam_forward[0] + dir_y * cam_forward[1] + dir_z * cam_forward[2]
    if dot_forward <= 0:
        return False, dist
    dot_right = dir_x * cam_right[0] + dir_y * cam_right[1] + dir_z * cam_right[2]
    dot_up = dir_x * cam_up[0] + dir_y * cam_up[1] + dir_z * cam_up[2]
    # 水平角 = atan2(dot_right, dot_forward)
    h_angle = abs(math.atan2(dot_right, dot_forward))
    v_angle = abs(math.atan2(dot_up, dot_forward))
    return (h_angle <= h_half_rad and v_angle <= v_half_rad), dist


def _rotation_to_vectors(rot):
    """将 Rotator 转为前/右/上方向向量（UE 坐标系）"""
    import math
    pitch_rad = math.radians(rot.pitch)
    yaw_rad = math.radians(rot.yaw)
    roll_rad = math.radians(rot.roll)
    # UE: X=Forward, Y=Right, Z=Up
    cp = math.cos(pitch_rad)
    sp = math.sin(pitch_rad)
    cy = math.cos(yaw_rad)
    sy = math.sin(yaw_rad)
    forward = (cp * cy, cp * sy, sp)
    right = (sy, -cy, 0)  # 简化（忽略 roll）
    up = (-sp * cy, -sp * sy, cp)
    return forward, right, up


@ue_tool(
    name="get_actors_in_view",
    description="Get actors visible in the current editor viewport using frustum culling. "
                "Returns actors within the camera's field of view, sorted by distance. "
                "Use 'fov' to override FOV (default 90), 'max_distance' to limit range, "
                "'class_filter' to narrow by class. Great for understanding what the user sees.",
    category="scene",
    risk_level="low",
)
def get_actors_in_view(arguments: dict) -> str:
    """获取当前视口可见的 Actor 列表（基于视锥体裁剪）"""
    if unreal is None:
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    import math

    fov = float(arguments.get("fov", 90.0))
    max_distance = float(arguments.get("max_distance", 50000.0))
    class_filter = arguments.get("class_filter", "")
    limit = arguments.get("limit", 50)
    include_transform = arguments.get("include_transform", True)

    try:
        # 获取视口相机信息
        cam_info = unreal.EditorLevelLibrary.get_level_viewport_camera_info()
        if cam_info is None:
            return json.dumps({"success": False, "error": "无法获取视口相机信息"})

        cam_loc, cam_rot = cam_info
        forward, right, up = _rotation_to_vectors(cam_rot)

        # 视锥体半角（水平用 FOV，垂直按 16:9 估算）
        h_half_rad = math.radians(fov / 2.0)
        v_half_rad = math.radians(fov / 2.0 * 9.0 / 16.0)

        # 遍历所有 Actor
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
        visible = []

        for actor in actors:
            # 跳过隐藏的 Actor
            try:
                if actor.is_hidden_ed():
                    continue
            except Exception:
                pass

            # 类过滤
            cls_name = str(actor.get_class().get_name())
            if class_filter and class_filter.lower() not in cls_name.lower():
                continue

            # 跳过 WorldSettings, GameMode 等非空间 Actor
            if cls_name in ("WorldSettings", "GameModeBase", "GameStateBase",
                            "PlayerStart", "DefaultPawn", "GameSession",
                            "HUD", "PlayerState", "SpectatorPawn",
                            "GameNetworkManager", "WorldPartitionMiniMap",
                            "WorldDataLayers", "LevelScriptActor"):
                continue

            actor_loc = actor.get_actor_location()
            in_view, dist = _is_in_view_frustum(
                actor_loc, cam_loc, forward, right, up,
                h_half_rad, v_half_rad, max_distance
            )
            if in_view:
                entry = _prune_actor(actor, include_transform)
                entry["distance"] = round(dist, 1)
                visible.append(entry)

        # 按距离排序
        visible.sort(key=lambda x: x["distance"])
        total_visible = len(visible)
        visible = visible[:limit]

        result = {
            "success": True,
            "count": len(visible),
            "camera": {
                "location": {"x": round(cam_loc.x, 2), "y": round(cam_loc.y, 2), "z": round(cam_loc.z, 2)},
                "rotation": {"pitch": round(cam_rot.pitch, 2), "yaw": round(cam_rot.yaw, 2), "roll": round(cam_rot.roll, 2)},
                "fov": fov,
            },
            "actors": visible,
        }
        if total_visible > limit:
            result["truncated"] = True
            result["total_visible"] = total_visible

        return json.dumps(result, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@ue_tool(
    name="get_spatial_context",
    description="Get spatial context around a specific actor or location. "
                "Returns nearby actors with relative direction (N/S/E/W/Above/Below) "
                "and distance. Helps AI understand scene layout for editing decisions. "
                "Provide 'actor_name' or 'location' {x,y,z}. Use 'radius' to set search range.",
    category="scene",
    risk_level="low",
)
def get_spatial_context(arguments: dict) -> str:
    """获取指定 Actor 或位置周围的空间上下文"""
    if unreal is None:
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    import math

    actor_name = arguments.get("actor_name", "")
    location = arguments.get("location", None)
    radius = float(arguments.get("radius", 5000.0))
    limit = arguments.get("limit", 30)

    try:
        # 确定中心点
        if actor_name:
            center_actor = _find_actor_by_name(actor_name)
            if center_actor is None:
                return json.dumps({"success": False, "error": f"未找到 Actor: {actor_name}"})
            center = center_actor.get_actor_location()
            center_label = str(center_actor.get_actor_label())
        elif location:
            center = unreal.Vector(
                float(location.get("x", 0)),
                float(location.get("y", 0)),
                float(location.get("z", 0)),
            )
            center_label = f"({center.x:.0f}, {center.y:.0f}, {center.z:.0f})"
        else:
            return json.dumps({"success": False, "error": "需要提供 actor_name 或 location"})

        # 遍历所有 Actor 找附近的
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
        nearby = []

        for actor in actors:
            cls_name = str(actor.get_class().get_name())
            # 跳过非空间 Actor
            if cls_name in ("WorldSettings", "GameModeBase", "GameStateBase",
                            "GameSession", "HUD", "PlayerState",
                            "GameNetworkManager", "WorldPartitionMiniMap",
                            "WorldDataLayers", "LevelScriptActor"):
                continue

            # 跳过自身
            if actor_name and (str(actor.get_name()) == actor_name or
                               str(actor.get_actor_label()) == actor_name):
                continue

            loc = actor.get_actor_location()
            dx = loc.x - center.x
            dy = loc.y - center.y
            dz = loc.z - center.z
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)

            if dist > radius:
                continue

            # 计算相对方位
            direction = _calc_direction(dx, dy, dz)

            entry = {
                "name": str(actor.get_name()),
                "label": str(actor.get_actor_label()),
                "class": cls_name,
                "distance": round(dist, 1),
                "direction": direction,
                "relative_offset": {
                    "x": round(dx, 1),
                    "y": round(dy, 1),
                    "z": round(dz, 1),
                },
            }
            nearby.append(entry)

        # 按距离排序
        nearby.sort(key=lambda x: x["distance"])
        total_nearby = len(nearby)
        nearby = nearby[:limit]

        result = {
            "success": True,
            "center": center_label,
            "center_location": {
                "x": round(center.x, 2),
                "y": round(center.y, 2),
                "z": round(center.z, 2),
            },
            "radius": radius,
            "count": len(nearby),
            "nearby_actors": nearby,
        }
        if total_nearby > limit:
            result["truncated"] = True
            result["total_nearby"] = total_nearby

        return json.dumps(result, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def _calc_direction(dx, dy, dz) -> str:
    """根据相对偏移计算方位描述（UE坐标: X=前/北, Y=右/东, Z=上）"""
    import math
    h_dist = math.sqrt(dx * dx + dy * dy)
    parts = []

    # 垂直方位
    if abs(dz) > h_dist * 0.5:
        if dz > 0:
            parts.append("上方")
        else:
            parts.append("下方")

    # 水平方位（UE: X+ = 北/前, Y+ = 东/右）
    if h_dist > 1.0:
        angle = math.degrees(math.atan2(dy, dx))  # -180 ~ 180
        if -22.5 <= angle < 22.5:
            parts.append("北")
        elif 22.5 <= angle < 67.5:
            parts.append("东北")
        elif 67.5 <= angle < 112.5:
            parts.append("东")
        elif 112.5 <= angle < 157.5:
            parts.append("东南")
        elif angle >= 157.5 or angle < -157.5:
            parts.append("南")
        elif -157.5 <= angle < -112.5:
            parts.append("西南")
        elif -112.5 <= angle < -67.5:
            parts.append("西")
        elif -67.5 <= angle < -22.5:
            parts.append("西北")

    return " ".join(parts) if parts else "同位置"


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
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    asset_path = arguments.get("asset_path", "")
    actor_class = arguments.get("actor_class", "")
    location = arguments.get("location", {"x": 0, "y": 0, "z": 0})
    rotation = arguments.get("rotation", {"pitch": 0, "yaw": 0, "roll": 0})
    scale = arguments.get("scale", None)
    label = arguments.get("label", "")

    if not asset_path and not actor_class:
        return json.dumps({
            "success": False,
            "error": "需要提供 asset_path 或 actor_class"
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
                        "error": f"未找到资产: {asset_path}"
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
                        "error": f"未找到 Actor 类: {actor_class}"
                    })
                actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
                    cls, loc, rot
                )

            if actor is None:
                return json.dumps({
                    "success": False,
                    "error": "生成 Actor 失败（返回 None）"
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
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    actor_names = arguments.get("actor_names", [])
    if isinstance(actor_names, str):
        actor_names = [actor_names]
    if not actor_names:
        return json.dumps({"success": False, "error": "需要提供 actor_names 参数（字符串或列表）"})

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
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    actor_name = arguments.get("actor_name", "")
    if not actor_name:
        return json.dumps({"success": False, "error": "需要提供 actor_name 参数"})

    location = arguments.get("location", None)
    rotation = arguments.get("rotation", None)
    scale = arguments.get("scale", None)

    if location is None and rotation is None and scale is None:
        return json.dumps({
            "success": False,
            "error": "至少需要提供 location、rotation 或 scale 之一"
        })

    try:
        actor = _find_actor_by_name(actor_name)
        if actor is None:
            return json.dumps({"success": False, "error": f"未找到 Actor: {actor_name}"})

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
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    actor_name = arguments.get("actor_name", "")
    new_label = arguments.get("new_label", "")
    if not actor_name:
        return json.dumps({"success": False, "error": "需要提供 actor_name 参数"})
    if not new_label:
        return json.dumps({"success": False, "error": "需要提供 new_label 参数"})

    try:
        actor = _find_actor_by_name(actor_name)
        if actor is None:
            return json.dumps({"success": False, "error": f"未找到 Actor: {actor_name}"})

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
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    actor_name = arguments.get("actor_name", "")
    select = arguments.get("select", True)
    if not actor_name:
        return json.dumps({"success": False, "error": "需要提供 actor_name 参数"})

    try:
        actor = _find_actor_by_name(actor_name)
        if actor is None:
            return json.dumps({"success": False, "error": f"未找到 Actor: {actor_name}"})

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
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    actor_names = arguments.get("actor_names", [])
    if isinstance(actor_names, str):
        actor_names = [actor_names]
    if not actor_names:
        return json.dumps({"success": False, "error": "需要提供 actor_names 参数"})

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
        return json.dumps({"success": False, "error": "未在 Unreal Engine 中运行"})

    actor_names = arguments.get("actor_names", [])
    if isinstance(actor_names, str):
        actor_names = [actor_names]
    if not actor_names:
        return json.dumps({"success": False, "error": "需要提供 actor_names 参数"})

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
