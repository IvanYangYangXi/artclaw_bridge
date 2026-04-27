"""Blender 模型批量添加前缀后缀 — 为选中的对象添加前缀或后缀。"""
# ── SDK 头 ──
import os, json
import artclaw_sdk as sdk

def _load_manifest() -> dict:
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)
# ── SDK 头结束 ──

import bpy


def rename_objects(**kwargs):
    """入口函数。"""
    manifest = _load_manifest()
    parsed = sdk.params.parse_params(manifest.get("inputs", []), kwargs)

    prefix = parsed.get("prefix", "")
    suffix = parsed.get("suffix", "")
    separator = parsed.get("separator", "_")
    target = parsed.get("target", "selected")

    # 获取目标对象
    if target == "selected":
        objects = [bpy.data.objects.get(obj["name"]) for obj in sdk.context.get_selected_objects()]
        objects = [o for o in objects if o is not None]
    elif target == "all":
        objects = list(bpy.context.scene.objects)
    elif target == "collection":
        active_col = bpy.context.view_layer.active_layer_collection.collection
        objects = list(active_col.objects)
    else:
        objects = [bpy.data.objects.get(obj["name"]) for obj in sdk.context.get_selected_objects()]
        objects = [o for o in objects if o is not None]

    if not objects:
        return sdk.result.fail("NO_INPUT", "没有找到目标对象")

    if not prefix and not suffix:
        return sdk.result.fail("NO_PARAMS", "前缀和后缀均为空，无需操作。")

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

    return sdk.result.success(
        data={"renamed_count": len(renamed), "renamed_objects": renamed},
        message=f"成功重命名 {len(renamed)} 个对象"
    )


# 直接执行入口（用于 DCC 内测试）
if __name__ == "__main__":
    result = rename_objects(prefix="SM", suffix="LOD0", separator="_", target="selected")
    print(result)
