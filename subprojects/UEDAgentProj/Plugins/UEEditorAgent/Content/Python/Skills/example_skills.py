"""
Example Skills - UE Editor Agent
================================

示例 Skill 文件。将 .py 文件放入 Skills/ 目录即可自动发现。
使用 @ue_agent.tool 装饰器声明 MCP Tool。

保存文件后 Skill Hub 会自动热重载，无需重启 UE。
"""

# 导入装饰器 — 从 skill_hub 模块导入
from skill_hub import tool as ue_tool
import json

try:
    import unreal
except ImportError:
    unreal = None  # 允许在 UE 外部测试


@ue_tool(
    name="list_actor_classes",
    description="List all unique actor classes in the current level. "
                "Useful for understanding what types of objects exist.",
    category="level",
    risk_level="low",
)
def list_actor_classes(arguments: dict) -> str:
    """统计当前关卡中所有 Actor 的类别分布"""
    if unreal is None:
        return json.dumps({"error": "Not running in UE"})

    actors = unreal.EditorLevelLibrary.get_all_level_actors()
    class_counts = {}
    for actor in actors:
        cls_name = actor.get_class().get_name()
        class_counts[cls_name] = class_counts.get(cls_name, 0) + 1

    # 按数量排序
    sorted_classes = sorted(class_counts.items(), key=lambda x: -x[1])

    return json.dumps({
        "total_actors": len(actors),
        "unique_classes": len(class_counts),
        "classes": [
            {"class": cls, "count": cnt}
            for cls, cnt in sorted_classes[:50]
        ],
    })


@ue_tool(
    name="find_actors_by_name",
    description="Find actors in the level by name pattern (case-insensitive substring match). "
                "Returns actor names, classes, and locations.",
    category="level",
    risk_level="low",
)
def find_actors_by_name(arguments: dict) -> str:
    """按名称模式搜索 Actor"""
    if unreal is None:
        return json.dumps({"error": "Not running in UE"})

    pattern = arguments.get("pattern", "").lower()
    if not pattern:
        return json.dumps({"error": "pattern is required"})

    limit = arguments.get("limit", 20)

    actors = unreal.EditorLevelLibrary.get_all_level_actors()
    results = []

    for actor in actors:
        label = str(actor.get_actor_label())
        if pattern in label.lower():
            loc = actor.get_actor_location()
            results.append({
                "name": label,
                "class": actor.get_class().get_name(),
                "location": {"x": loc.x, "y": loc.y, "z": loc.z},
            })
            if len(results) >= limit:
                break

    return json.dumps({
        "pattern": pattern,
        "found": len(results),
        "actors": results,
    })


@ue_tool(
    name="get_level_stats",
    description="Get comprehensive statistics about the current level: "
                "actor counts, bounding box, memory estimates.",
    category="level",
    risk_level="low",
)
def get_level_stats(arguments: dict) -> str:
    """获取当前关卡的详细统计信息"""
    if unreal is None:
        return json.dumps({"error": "Not running in UE"})

    actors = unreal.EditorLevelLibrary.get_all_level_actors()

    stats = {
        "total_actors": len(actors),
        "static_meshes": 0,
        "lights": 0,
        "cameras": 0,
        "blueprints": 0,
        "other": 0,
    }

    for actor in actors:
        cls = actor.get_class().get_name()
        if "StaticMeshActor" in cls:
            stats["static_meshes"] += 1
        elif "Light" in cls:
            stats["lights"] += 1
        elif "Camera" in cls:
            stats["cameras"] += 1
        elif "Blueprint" in cls or cls.endswith("_C"):
            stats["blueprints"] += 1
        else:
            stats["other"] += 1

    return json.dumps(stats)
