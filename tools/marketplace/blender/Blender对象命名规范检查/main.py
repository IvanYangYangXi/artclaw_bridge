"""Blender 对象命名规范检查工具。

触发器场景：挂载 file.save.pre 或 file.save.post，在保存时自动检查场景中对象是否
符合命名前缀规范（如 SM_、SK_、BP_ 等），并汇报违规列表。

手动运行场景：输入 prefixes / target 参数，返回完整命名检查报告。

返回格式（触发器要求）：
    allow  → 全部合规（或无可检查对象）
    reject → 有违规对象，reason 中包含违规列表摘要
    error  → 执行异常
"""
# ── SDK 头 ──
import os
import json
import artclaw_sdk as sdk

def _load_manifest() -> dict:
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)
# ── SDK 头结束 ──

# Blender 默认生成的名称，跳过检查
_DEFAULT_NAMES = {
    "Cube", "Sphere", "Cylinder", "Cone", "Torus", "Plane",
    "Circle", "IcoSphere", "Monkey", "Empty",
    "Camera", "Light", "Sun", "Spot", "Area", "Point",
    "Armature", "Lamp", "Curve", "Text", "Surface", "Metaball",
}


def _get_objects(target: str) -> list:
    """根据 target 参数获取目标对象列表。"""
    import bpy  # 延迟 import，仅在 Blender 内部执行时才可用
    if target == "selected":
        return list(bpy.context.selected_objects)
    elif target == "collection":
        active_col = bpy.context.view_layer.active_layer_collection.collection
        return list(active_col.all_objects)
    else:  # all
        return list(bpy.context.scene.objects)


def check_naming(event_data=None, **kwargs):
    """命名规范检查入口。

    触发器调用时传入 event_data；手动调用时传入 kwargs。
    返回 {"action": "allow"/"reject", "reason": str} 供触发器框架使用，
    同时在 data 字段附上完整报告供手动调用查阅。
    """
    manifest = _load_manifest()

    # 从 event_data 或 kwargs 中解析参数
    if event_data is not None:
        # 触发器调用：使用 manifest 默认值
        inputs = manifest.get("inputs", [])
        params = {inp["id"]: inp.get("default") for inp in inputs}
    else:
        # 手动调用：解析 kwargs
        params = sdk.params.parse_params(manifest.get("inputs", []), kwargs)

    prefixes_raw = params.get("prefixes", "SM_,SK_,BP_,VFX_,MAT_,TEX_,CH_,ENV_,PROP_") or ""
    prefixes = [p.strip() for p in prefixes_raw.split(",") if p.strip()]
    target = params.get("target", "all")
    skip_defaults = params.get("skip_default_names", True)
    if isinstance(skip_defaults, str):
        skip_defaults = skip_defaults.lower() not in ("false", "0", "no")

    try:
        objects = _get_objects(target)
    except Exception as e:
        return {"action": "error", "reason": f"获取对象列表失败: {e}"}

    if not objects:
        return {
            "action": "allow",
            "reason": "场景中没有可检查的对象",
            "data": {"total": 0, "violations": [], "pass_rate": "N/A"},
        }

    violations = []
    checked = 0

    for obj in objects:
        name = obj.name

        # 跳过 Blender 默认命名（基础名，去掉末尾 .001 等后缀）
        base_name = name.split(".")[0] if "." in name else name
        if skip_defaults and base_name in _DEFAULT_NAMES:
            continue

        checked += 1

        # 前缀检查（prefixes 为空时跳过）
        if prefixes:
            has_valid_prefix = any(name.startswith(p) for p in prefixes)
            if not has_valid_prefix:
                violations.append({
                    "name": name,
                    "type": obj.type,
                    "reason": f"缺少规范前缀（期望：{'/'.join(prefixes[:5])}{'...' if len(prefixes) > 5 else ''}）",
                })

    total = checked
    violation_count = len(violations)
    pass_rate = f"{((total - violation_count) / total * 100):.1f}%" if total > 0 else "N/A"

    if violation_count == 0:
        return sdk.result.success(
            data={"total": total, "violations": [], "pass_rate": pass_rate},
            message=f"命名规范检查通过，共检查 {total} 个对象",
        ) if event_data is None else {
            "action": "allow",
            "reason": f"命名规范检查通过（{total} 个对象均合规）",
            "data": {"total": total, "violations": [], "pass_rate": pass_rate},
        }

    # 有违规：构建摘要消息
    preview_names = [v["name"] for v in violations[:5]]
    more = f"…等共 {violation_count} 个" if violation_count > 5 else f"共 {violation_count} 个"
    summary = f"命名不规范 {more} 对象：{', '.join(preview_names)}"

    if event_data is None:
        # 手动调用：返回完整报告（不是 reject，只是 warn）
        return sdk.result.success(
            data={"total": total, "violations": violations, "pass_rate": pass_rate},
            message=summary,
        )
    else:
        # 触发器调用：返回 reject 让框架通知用户
        return {
            "action": "reject",
            "reason": summary,
            "data": {"total": total, "violations": violations, "pass_rate": pass_rate},
        }


# 直接执行入口（用于 DCC 内测试）
if __name__ == "__main__":
    result = check_naming(prefixes="SM_,SK_", target="all")
    print(result)
