"""
context_provider.py - 动态上下文感知与资源映射
=================================================

阶段 2.2: 将 UE 编辑器状态映射为 MCP Resources。
阶段 2.5: 编辑器模式智能过滤。
阶段 2.6: 运行时数据精简。

宪法约束:
  - 开发路线图 §2.2: UE 编辑器状态映射为 MCP 资源 URI (unreal://level/selection)
  - 开发路线图 §2.5: 实时监测编辑器模式，动态调整 AI 的 System Prompt
  - 开发路线图 §2.6: UObject 转为极简 JSON，仅保留 Name/Class/Transform/Tags
  - 核心机制 §6: MCP 资源流转，懒加载 + 按需采样
"""

import json
from typing import Any, Dict, List, Optional

import unreal

from init_unreal import UELogger


# ============================================================================
# 1. 数据精简器 (阶段 2.6)
# ============================================================================

def prune_actor(actor) -> dict:
    """
    将 Actor 转换为极简 JSON 字典。

    宪法约束:
      - 开发路线图 §2.6: 仅保留 Name, Class, Transform, Tags
      - 核心机制 §6: 防止海量无效属性引起 Token 溢出
    """
    data = {
        "name": str(actor.get_name()),
        "class": str(actor.get_class().get_name()),
        "label": str(actor.get_actor_label()),
    }

    try:
        loc = actor.get_actor_location()
        rot = actor.get_actor_rotation()
        scale = actor.get_actor_scale3d()
        data["transform"] = {
            "location": {"x": round(loc.x, 2), "y": round(loc.y, 2), "z": round(loc.z, 2)},
            "rotation": {"pitch": round(rot.pitch, 2), "yaw": round(rot.yaw, 2), "roll": round(rot.roll, 2)},
            "scale": {"x": round(scale.x, 2), "y": round(scale.y, 2), "z": round(scale.z, 2)},
        }
    except Exception:
        data["transform"] = None

    try:
        tags = [str(t) for t in actor.tags]
        if tags:
            data["tags"] = tags
    except Exception:
        pass

    # 父子关系
    try:
        parent = actor.get_attach_parent_actor()
        if parent:
            data["parent"] = str(parent.get_name())
    except Exception:
        pass

    # 可见性
    try:
        data["visible"] = not actor.is_hidden_ed()
    except Exception:
        pass

    return data


def prune_actor_list(actors, max_count: int = 200) -> List[dict]:
    """批量精简 Actor 列表，限制数量。"""
    result = []
    for i, actor in enumerate(actors):
        if i >= max_count:
            result.append({"_truncated": True, "total": len(actors), "shown": max_count})
            break
        try:
            result.append(prune_actor(actor))
        except Exception as e:
            result.append({"name": "?", "error": str(e)})
    return result


def prune_asset(asset_path: str) -> dict:
    """将资产路径转为精简信息。"""
    data = {"path": asset_path}
    try:
        asset_data = unreal.EditorAssetLibrary.find_asset_data(asset_path)
        if asset_data:
            data["class"] = str(asset_data.asset_class)
            data["name"] = str(asset_data.asset_name)
    except Exception:
        pass
    return data


# ============================================================================
# 2. 编辑器模式检测 (阶段 2.5)
# ============================================================================

class EditorMode:
    """编辑器模式常量"""
    LEVEL = "level"             # 关卡编辑
    BLUEPRINT = "blueprint"     # 蓝图编辑
    MATERIAL = "material"       # 材质编辑
    SEQUENCER = "sequencer"     # 序列器
    UNKNOWN = "unknown"


def detect_editor_mode() -> str:
    """
    检测当前编辑器模式。

    宪法约束:
      - 开发路线图 §2.5: 实时监测当前编辑器模式
    """
    # 默认为关卡编辑模式（最常见）
    # UE Python API 对当前活跃编辑器的检测能力有限
    # 后续可通过 C++ 扩展更精确的检测
    try:
        # 检查是否有 Actor 选中（意味着在关卡编辑模式）
        selection = unreal.EditorLevelLibrary.get_selected_level_actors()
        if selection:
            return EditorMode.LEVEL
    except Exception:
        pass

    return EditorMode.LEVEL


def get_mode_context(mode: str) -> dict:
    """
    根据编辑器模式返回上下文提示。

    宪法约束:
      - 开发路线图 §2.5: 动态调整 AI 的 System Prompt
    """
    contexts = {
        EditorMode.LEVEL: {
            "mode": "level",
            "hint": "User is editing a level. Prefer EditorLevelLibrary and Actor operations.",
            "preferred_apis": [
                "unreal.EditorLevelLibrary",
                "unreal.EditorActorSubsystem",
            ],
        },
        EditorMode.BLUEPRINT: {
            "mode": "blueprint",
            "hint": "User is editing a blueprint. Prefer blueprint-related APIs.",
            "preferred_apis": [
                "unreal.EditorAssetLibrary",
            ],
        },
        EditorMode.MATERIAL: {
            "mode": "material",
            "hint": "User is editing a material. Prefer material-related APIs.",
            "preferred_apis": [
                "unreal.MaterialEditingLibrary",
            ],
        },
    }
    return contexts.get(mode, {"mode": mode, "hint": "Unknown mode", "preferred_apis": []})


# ============================================================================
# 3. MCP Resource Provider (阶段 2.2)
# ============================================================================

# 资源 URI 定义
RESOURCE_DEFINITIONS = [
    {
        "uri": "unreal://level/selection",
        "name": "Selected Actors",
        "description": "Currently selected actors in the level editor",
        "mimeType": "application/json",
    },
    {
        "uri": "unreal://level/all_actors",
        "name": "All Level Actors",
        "description": "All actors in the current level (pruned)",
        "mimeType": "application/json",
    },
    {
        "uri": "unreal://editor/context",
        "name": "Editor Context",
        "description": "Current editor mode, selection count, viewport info",
        "mimeType": "application/json",
    },
    {
        "uri": "unreal://editor/viewport",
        "name": "Viewport Camera",
        "description": "Current viewport camera location and rotation",
        "mimeType": "application/json",
    },
    {
        "uri": "unreal://project/info",
        "name": "Project Info",
        "description": "Current project name, engine version, etc.",
        "mimeType": "application/json",
    },
]


def read_resource(uri: str) -> dict:
    """
    读取指定 URI 的资源内容。

    宪法约束:
      - 开发路线图 §2.2: AI 通过读取资源实时获取当前选中项、活动资产路径、视口相机位置
      - 核心机制 §6: 懒加载 + 按需采样
    """
    if uri == "unreal://level/selection":
        return _read_selection()
    elif uri == "unreal://level/all_actors":
        return _read_all_actors()
    elif uri == "unreal://editor/context":
        return _read_editor_context()
    elif uri == "unreal://editor/viewport":
        return _read_viewport()
    elif uri == "unreal://project/info":
        return _read_project_info()
    else:
        raise ValueError(f"Unknown resource URI: {uri}")


def _read_selection() -> dict:
    """读取当前选中的 Actor 列表"""
    try:
        actors = unreal.EditorLevelLibrary.get_selected_level_actors()
        return {
            "count": len(actors),
            "actors": prune_actor_list(actors),
        }
    except Exception as e:
        return {"count": 0, "actors": [], "error": str(e)}


def _read_all_actors() -> dict:
    """读取当前关卡所有 Actor"""
    try:
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
        return {
            "count": len(actors),
            "actors": prune_actor_list(actors, max_count=500),
        }
    except Exception as e:
        return {"count": 0, "actors": [], "error": str(e)}


def _read_editor_context() -> dict:
    """读取编辑器上下文信息"""
    mode = detect_editor_mode()
    mode_ctx = get_mode_context(mode)

    try:
        selection = unreal.EditorLevelLibrary.get_selected_level_actors()
        sel_count = len(selection)
    except Exception:
        sel_count = 0

    try:
        all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
        actor_count = len(all_actors)
    except Exception:
        actor_count = 0

    return {
        "mode": mode_ctx,
        "selection_count": sel_count,
        "total_actors": actor_count,
        "level_name": str(unreal.EditorLevelLibrary.get_editor_world().get_name()) if sel_count >= 0 else "Unknown",
    }


def _read_viewport() -> dict:
    """读取视口相机位置"""
    try:
        loc, rot = unreal.EditorLevelLibrary.get_level_viewport_camera_info()
        return {
            "location": {"x": round(loc.x, 2), "y": round(loc.y, 2), "z": round(loc.z, 2)},
            "rotation": {"pitch": round(rot.pitch, 2), "yaw": round(rot.yaw, 2), "roll": round(rot.roll, 2)},
        }
    except Exception as e:
        return {"error": str(e)}


def _read_project_info() -> dict:
    """读取项目信息"""
    info = {}
    try:
        info["project_name"] = str(unreal.Paths.get_project_file_path())
        info["engine_version"] = str(unreal.SystemLibrary.get_engine_version())
    except Exception:
        pass
    try:
        info["project_dir"] = str(unreal.Paths.project_dir())
        info["project_content_dir"] = str(unreal.Paths.project_content_dir())
    except Exception:
        pass
    return info


# ============================================================================
# 4. MCP 注册
# ============================================================================

def register_resources(mcp_server) -> None:
    """注册 MCP Resources 到服务器。"""
    # 替换占位的 resources/list 和 resources/read 处理器
    mcp_server._resource_definitions = RESOURCE_DEFINITIONS
    mcp_server._resource_reader = read_resource
    UELogger.info(f"Phase 2 resources registered: {len(RESOURCE_DEFINITIONS)} resources")


def register_tools(mcp_server) -> None:
    """注册阶段 2 的 MCP Tools。"""

    # --- 2.2: 获取选中 Actor ---
    mcp_server.register_tool(
        name="get_selected_actors",
        description=(
            "Get the list of currently selected actors in the level editor. "
            "Returns pruned data: name, class, transform, tags, parent."
        ),
        input_schema={
            "type": "object",
            "properties": {},
        },
        handler=lambda args: json.dumps(_read_selection(), default=str),
    )

    # --- 2.2: 获取编辑器上下文 ---
    mcp_server.register_tool(
        name="get_editor_context",
        description=(
            "Get current editor context: mode, selection count, total actors, level name. "
            "Use this to understand what the user is currently working on."
        ),
        input_schema={
            "type": "object",
            "properties": {},
        },
        handler=lambda args: json.dumps(_read_editor_context(), default=str),
    )

    # --- 2.4: 视口操作 ---
    mcp_server.register_tool(
        name="focus_on_actor",
        description=(
            "Focus the viewport camera on a specific actor by name. "
            "Optionally highlight the actor for visual feedback."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "actor_name": {
                    "type": "string",
                    "description": "Name of the actor to focus on",
                },
                "highlight": {
                    "type": "boolean",
                    "description": "Whether to highlight the actor (default: true)",
                    "default": True,
                },
            },
            "required": ["actor_name"],
        },
        handler=_handle_focus_on_actor,
    )

    mcp_server.register_tool(
        name="highlight_actors",
        description=(
            "Select and highlight actors by name in the viewport. "
            "The viewport will focus on the selected actors."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "actor_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of actor names to highlight",
                },
            },
            "required": ["actor_names"],
        },
        handler=_handle_highlight_actors,
    )

    # --- 2.4: 视口相机 ---
    mcp_server.register_tool(
        name="get_viewport_camera",
        description="Get the current viewport camera location and rotation.",
        input_schema={
            "type": "object",
            "properties": {},
        },
        handler=lambda args: json.dumps(_read_viewport(), default=str),
    )

    mcp_server.register_tool(
        name="set_viewport_camera",
        description=(
            "Set the viewport camera to a specific location and rotation. "
            "Useful for navigating to specific areas in the level."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "location": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "z": {"type": "number"},
                    },
                    "description": "Camera location (x, y, z)",
                },
                "rotation": {
                    "type": "object",
                    "properties": {
                        "pitch": {"type": "number"},
                        "yaw": {"type": "number"},
                        "roll": {"type": "number"},
                    },
                    "description": "Camera rotation (pitch, yaw, roll)",
                },
            },
        },
        handler=_handle_set_viewport_camera,
    )

    UELogger.info("Phase 2 tools registered: 5 tools")


# ============================================================================
# 5. Tool Handlers (阶段 2.4)
# ============================================================================

def _handle_focus_on_actor(arguments: dict) -> str:
    """
    视口聚焦到指定 Actor。

    宪法约束:
      - 开发路线图 §2.4: focus_on_actor，自动高亮受影响 Actor
    """
    actor_name = arguments.get("actor_name", "")
    highlight = arguments.get("highlight", True)

    try:
        all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
        target = None
        for a in all_actors:
            if str(a.get_name()) == actor_name or str(a.get_actor_label()) == actor_name:
                target = a
                break

        if target is None:
            return json.dumps({"success": False, "error": f"Actor not found: {actor_name}"})

        if highlight:
            # 选中 Actor（会在视口中高亮）
            unreal.EditorLevelLibrary.set_selected_level_actors([target])

        # 聚焦视口
        unreal.EditorLevelLibrary.pilot_level_actor(target)

        return json.dumps({
            "success": True,
            "actor": prune_actor(target),
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def _handle_highlight_actors(arguments: dict) -> str:
    """
    高亮选中多个 Actor。

    宪法约束:
      - 开发路线图 §2.4: highlight_actors，支持多个 Actor 同时高亮
    """
    actor_names = arguments.get("actor_names", [])

    try:
        all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
        name_set = set(actor_names)
        found = []

        for a in all_actors:
            if str(a.get_name()) in name_set or str(a.get_actor_label()) in name_set:
                found.append(a)

        if found:
            unreal.EditorLevelLibrary.set_selected_level_actors(found)

        return json.dumps({
            "success": True,
            "found": len(found),
            "requested": len(actor_names),
            "actors": prune_actor_list(found),
        }, default=str)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def _handle_set_viewport_camera(arguments: dict) -> str:
    """
    设置视口相机位置。

    宪法约束:
      - 开发路线图 §2.4: 视口相机平滑平移至目标区域
    """
    try:
        loc_data = arguments.get("location", {})
        rot_data = arguments.get("rotation", {})

        loc = unreal.Vector(
            loc_data.get("x", 0),
            loc_data.get("y", 0),
            loc_data.get("z", 0),
        )
        rot = unreal.Rotator(
            rot_data.get("pitch", 0),
            rot_data.get("yaw", 0),
            rot_data.get("roll", 0),
        )

        unreal.EditorLevelLibrary.set_level_viewport_camera_info(loc, rot)

        return json.dumps({
            "success": True,
            "location": {"x": loc.x, "y": loc.y, "z": loc.z},
            "rotation": {"pitch": rot.pitch, "yaw": rot.yaw, "roll": rot.roll},
        })

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
