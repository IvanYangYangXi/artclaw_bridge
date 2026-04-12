"""
Blender 模型批量加前缀后缀工具
"""
import bpy


def rename_objects(prefix="", suffix="", separator="_", target="selected"):
    """批量为 Blender 对象名称添加前缀和/或后缀。

    Args:
        prefix: 前缀文本
        suffix: 后缀文本
        separator: 分隔符
        target: 目标范围 (selected/all/collection)

    Returns:
        dict: {"renamed_count": int, "renamed_objects": [{"old": str, "new": str}]}
    """
    # 确定目标对象
    if target == "selected":
        objects = list(bpy.context.selected_objects)
    elif target == "all":
        objects = list(bpy.context.scene.objects)
    elif target == "collection":
        active_col = bpy.context.view_layer.active_layer_collection.collection
        objects = list(active_col.objects)
    else:
        objects = list(bpy.context.selected_objects)

    if not objects:
        return {
            "renamed_count": 0,
            "renamed_objects": [],
            "message": "没有找到目标对象"
        }

    if not prefix and not suffix:
        return {
            "renamed_count": 0,
            "renamed_objects": [],
            "message": "前缀和后缀都为空，无需操作"
        }

    renamed = []
    for obj in objects:
        old_name = obj.name
        new_name = old_name

        if prefix:
            new_name = prefix + separator + new_name
        if suffix:
            new_name = new_name + separator + suffix

        obj.name = new_name
        renamed.append({"old": old_name, "new": obj.name})

    return {
        "renamed_count": len(renamed),
        "renamed_objects": renamed,
        "message": f"已重命名 {len(renamed)} 个对象"
    }


# 直接执行入口（用于 DCC 内测试）
if __name__ == "__main__":
    result = rename_objects(prefix="SM", suffix="LOD0", separator="_", target="selected")
    print(result)
