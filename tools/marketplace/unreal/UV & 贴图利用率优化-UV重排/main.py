# Ref: docs/UEClawBridge/features/xatlas-integration/design.md
"""
UV & 贴图利用率优化-UV重排 - 入口模块
v1.2: 引用检测改为按材质实例维度判断（材质→贴图→UV槽三者联动跳过）
"""
# ── SDK 头 ──
import os as _os, json as _json_mod
import artclaw_sdk as sdk

def _load_manifest():
    return _json_mod.loads(
        open(_os.path.join(_os.path.dirname(__file__), "manifest.json"),
             encoding="utf-8").read()
    )
# ── SDK 头结束 ──

import sys
import os

_TOOLS_PATH = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_PATH not in sys.path:
    sys.path.insert(0, _TOOLS_PATH)


def _parse_paths(raw: str) -> list:
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _parse_material_ids(raw: str):
    if not raw or not raw.strip():
        return None
    try:
        return [int(x.strip()) for x in raw.split(",") if x.strip()]
    except ValueError:
        return None


# 统计引用时只关心这些资产类型
_REF_ASSET_CLASSES = frozenset({
    "Material", "MaterialInstance", "MaterialInstanceConstant",
    "StaticMesh", "SkeletalMesh", "Blueprint", "World",
})
_MESH_ASSET_CLASSES = frozenset({"StaticMesh", "SkeletalMesh"})


def _count_mi_refs(ar, mi_path: str, dep_opt) -> int:
    """统计材质实例被多少个相关资产（Mesh/Blueprint/World/其他MI）引用。"""
    import unreal
    refs = ar.get_referencers(unreal.Name(mi_path), dep_opt) or []
    count = 0
    for ref in refs:
        for ad in ar.get_assets_by_package_name(ref):
            if str(ad.asset_class_path.asset_name) in _REF_ASSET_CLASSES:
                count += 1
                break
    return count


def _collect_slot_info(mesh_paths: list, material_ids, ar, dep_opt):
    """
    收集每个材质槽的信息：材质实例路径、引用数、贴图列表。

    Returns:
        list of {
            slot_idx, mi_path, mi_ref_count,
            textures: [ue_path, ...]
        }
        去掉不是 MaterialInstance 或无有效贴图的槽。
    """
    import unreal
    seen_mi = {}   # mi_path -> ref_count（缓存避免重复查询）
    slots = []

    for mesh_path in mesh_paths:
        mesh = unreal.load_asset(mesh_path)
        if not mesh:
            continue
        for slot_idx, slot in enumerate(mesh.static_materials):
            if material_ids is not None and slot_idx not in material_ids:
                continue
            mi = slot.material_interface if slot else None
            if not mi or not isinstance(mi, unreal.MaterialInstance):
                continue
            mi_path = mi.get_path_name().split(".")[0]

            if mi_path not in seen_mi:
                seen_mi[mi_path] = _count_mi_refs(ar, mi_path, dep_opt)
            mi_ref_count = seen_mi[mi_path]

            # 收集该 MI 上覆盖的有效贴图
            tex_paths = []
            seen_tex = set()
            for tpv in getattr(mi, 'texture_parameter_values', []):
                tex = tpv.parameter_value
                if not tex:
                    continue
                try:
                    w, h = tex.blueprint_get_size_x(), tex.blueprint_get_size_y()
                except Exception:
                    continue
                if w <= 1 and h <= 1:
                    continue
                tp = tex.get_path_name().split(".")[0]
                if tp not in seen_tex:
                    seen_tex.add(tp)
                    tex_paths.append(tp)

            if tex_paths:
                slots.append({
                    "mesh_path": mesh_path,
                    "slot_idx": slot_idx,
                    "mi_path": mi_path,
                    "mi_ref_count": mi_ref_count,
                    "textures": tex_paths,
                })
    return slots


def _expand_meshes_for_shared(mesh_paths: list, mi_paths: list, ar, dep_opt) -> list:
    """
    skip=False 时：查找引用这些 MI 的所有 Mesh，合并到 mesh_paths 统一装箱。
    """
    import unreal
    extra = set()
    for mi_path in mi_paths:
        refs = ar.get_referencers(unreal.Name(mi_path), dep_opt) or []
        for ref in refs:
            for ad in ar.get_assets_by_package_name(ref):
                if str(ad.asset_class_path.asset_name) in _MESH_ASSET_CLASSES:
                    extra.add(str(ad.package_name))
    return list(dict.fromkeys(mesh_paths + [p for p in extra if p not in mesh_paths]))


def _build_report(raw: dict, dry_run: bool, skipped: list, modified: list) -> str:
    lines = []
    if not raw.get("success"):
        lines.append(f"[失败] {raw.get('error', '未知错误')}")
        return "\n".join(lines)

    tag = "[预览]" if dry_run else "[完整优化]"
    lines += [
        f"{tag} UV 重排报告",
        f"Mesh 数量   : {raw.get('num_meshes', '-')}",
        f"UV 岛数量   : {raw.get('num_islands', '-')}",
        f"材质槽过滤  : {raw.get('material_filter') or '全部'}",
        f"缩放系数    : {raw.get('scale', '-')} （统一，纹理密度一致）",
        f"原始利用率  : {raw.get('orig_utilization', '-')}%",
        f"重排后利用率: {raw.get('utilization', '-')}%",
        f"提升        : {raw.get('improvement', '-')}",
    ]
    if "vertices_updated" in raw:
        lines.append(f"顶点已写回  : {raw['vertices_updated']}")

    if raw.get("textures"):
        lines.append("\n贴图适配结果:")
        for tp, info in raw["textures"].items():
            name = tp.rsplit("/", 1)[-1]
            if "error" in info:
                lines.append(f"  [{name}] 失败: {info['error']}")
            else:
                dr = info.get("density_ratio")
                sz = info.get("out_size")
                lines.append(f"  [{name}] 已生成 {sz}px"
                             + (f"  密度比 {dr}" if dr else "")
                             + f"  -> {info.get('asset', '').split('.')[0]}")

    if skipped:
        lines.append("\n跳过的材质槽（材质实例被多资产引用）:")
        for s in skipped:
            lines.append(f"  [Slot {s['slot_idx']} / {s['mi_path'].rsplit('/',1)[-1]}] {s['reason']}")

    if modified and not dry_run:
        lines.append(f"\n修改的资源（共 {len(modified)} 个）:")
        for m in modified:
            lines.append(f"  {m}")

    return "\n".join(lines)


def uv_repack_tool(**kwargs):
    """入口函数，由 ArtClaw Tool Manager 通过 keyword arguments 调用。"""
    manifest = _load_manifest()
    parsed = sdk.params.parse_params(manifest.get("inputs", []), kwargs)
    
    # 获取 mesh 路径：参数优先，fallback 到选中的 StaticMesh
    mesh_paths_str = parsed.get("mesh_paths", "")
    if mesh_paths_str:
        mesh_paths = [p.strip() for p in mesh_paths_str.split(",") if p.strip()]
    else:
        selected = sdk.context.get_selected_assets()
        mesh_paths = [a["path"] for a in selected if a.get("class") == "StaticMesh" or a.get("type") == "StaticMesh"]
    
    if not mesh_paths:
        return sdk.result.fail("NO_INPUT", "未指定 Mesh 路径，且 Content Browser 中无选中的 StaticMesh。")

    import unreal

    material_ids      = _parse_material_ids(parsed.get("material_ids", ""))
    uv_channel        = int(parsed.get("uv_channel", 0))
    padding           = float(parsed.get("padding", 0.002))
    allow_rotation    = bool(parsed.get("allow_rotation", False))
    skip_shared       = bool(parsed.get("skip_shared_textures", True))
    overwrite_texture = bool(parsed.get("overwrite_texture", True))
    bleed_pixels      = int(parsed.get("bleed_pixels", 4))
    dry_run           = bool(parsed.get("dry_run", False))

    # ── 手动指定贴图路径时直接走旧逻辑（不做引用检测）──────
    tex_paths_manual = _parse_paths(parsed.get("texture_paths", ""))
    if tex_paths_manual:
        texture_paths = tex_paths_manual
        skipped_slots = []
        active_mat_ids = material_ids
    else:
        # ── 按材质实例维度收集槽信息并做引用检测 ──────────
        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        dep_opt = unreal.AssetRegistryDependencyOptions()
        slots = _collect_slot_info(mesh_paths, material_ids, ar, dep_opt)

        skipped_slots = []
        ok_slots = []
        shared_mi_paths = []

        for s in slots:
            if s["mi_ref_count"] > 1:
                if skip_shared:
                    skipped_slots.append({
                        "slot_idx": s["slot_idx"],
                        "mi_path": s["mi_path"],
                        "reason": f"材质实例被 {s['mi_ref_count']} 个资产引用，已跳过",
                    })
                else:
                    ok_slots.append(s)
                    shared_mi_paths.append(s["mi_path"])
            else:
                ok_slots.append(s)

        # skip=False 时扩展 Mesh 范围
        if shared_mi_paths and not skip_shared:
            mesh_paths = _expand_meshes_for_shared(mesh_paths, shared_mi_paths, ar, dep_opt)

        # 跳过的槽对应的 material_ids 要从处理范围里剔除
        skipped_slot_ids = {s["slot_idx"] for s in skipped_slots}
        if material_ids is None:
            # 全部槽中去掉跳过的
            all_slot_ids = {s["slot_idx"] for s in slots}
            active_mat_ids = sorted(all_slot_ids - skipped_slot_ids) or None
            if active_mat_ids is not None and len(active_mat_ids) == len(all_slot_ids):
                active_mat_ids = None  # 没有跳过任何槽，还原 None=全部
        else:
            active_mat_ids = [i for i in material_ids if i not in skipped_slot_ids] or None

        # 去重合并所有待处理槽的贴图
        seen = set()
        texture_paths = []
        for s in ok_slots:
            for tp in s["textures"]:
                if tp not in seen:
                    seen.add(tp)
                    texture_paths.append(tp)

    final_tex = texture_paths or None

    # ── 调用核心模块 ──────────────────────────────────────
    try:
        import importlib, uv_repack as _m
        importlib.reload(_m)
        from uv_repack import uv_repack
    except ImportError as exc:
        return sdk.result.fail("IMPORT_ERROR", f"无法导入 uv_repack 模块: {exc}")

    raw = uv_repack(
        mesh_paths=mesh_paths,
        src_uv=uv_channel,
        padding=padding,
        material_ids=active_mat_ids,
        allow_rotation=allow_rotation,
        texture_paths=final_tex,
        bleed_pixels=bleed_pixels,
        overwrite_texture=overwrite_texture,
        dry_run=dry_run,
    )

    # ── 整理修改资源列表 ──────────────────────────────────
    modified_assets = []
    if not dry_run and raw.get("success"):
        modified_assets.extend(mesh_paths)
        for tp, info in (raw.get("textures") or {}).items():
            if "error" not in info and info.get("asset"):
                modified_assets.append(info["asset"].split(".")[0])

    report = _build_report(raw, dry_run, skipped_slots, modified_assets)

    return sdk.result.success(
        data={
            "report": report,
            "modified_assets": modified_assets,
            "skipped_slots": skipped_slots,
            "num_islands": raw.get("num_islands"),
            "scale": raw.get("scale"),
            "utilization_before": raw.get("orig_utilization"),
            "utilization_after": raw.get("utilization"),
            "dry_run": dry_run,
        },
        message=report
    )


if __name__ == "__main__":
    import json as _json, sys as _sys
    if len(_sys.argv) > 1:
        _params = _json.loads(_sys.argv[1])
        print(_json.dumps(uv_repack_tool(**_params), ensure_ascii=False, default=str))


# 统计引用时只关心这些资产类型
_REF_ASSET_CLASSES = frozenset({
    "Material", "MaterialInstance", "MaterialInstanceConstant",
    "StaticMesh", "SkeletalMesh", "Blueprint", "World",
})
_MESH_ASSET_CLASSES = frozenset({"StaticMesh", "SkeletalMesh"})


def _count_mi_refs(ar, mi_path: str, dep_opt) -> int:
    """统计材质实例被多少个相关资产（Mesh/Blueprint/World/其他MI）引用。"""
    import unreal
    refs = ar.get_referencers(unreal.Name(mi_path), dep_opt) or []
    count = 0
    for ref in refs:
        for ad in ar.get_assets_by_package_name(ref):
            if str(ad.asset_class_path.asset_name) in _REF_ASSET_CLASSES:
                count += 1
                break
    return count


def _collect_slot_info(mesh_paths: list, material_ids, ar, dep_opt):
    """
    收集每个材质槽的信息：材质实例路径、引用数、贴图列表。

    Returns:
        list of {
            slot_idx, mi_path, mi_ref_count,
            textures: [ue_path, ...]
        }
        去掉不是 MaterialInstance 或无有效贴图的槽。
    """
    import unreal
    seen_mi = {}   # mi_path -> ref_count（缓存避免重复查询）
    slots = []

    for mesh_path in mesh_paths:
        mesh = unreal.load_asset(mesh_path)
        if not mesh:
            continue
        for slot_idx, slot in enumerate(mesh.static_materials):
            if material_ids is not None and slot_idx not in material_ids:
                continue
            mi = slot.material_interface if slot else None
            if not mi or not isinstance(mi, unreal.MaterialInstance):
                continue
            mi_path = mi.get_path_name().split(".")[0]

            if mi_path not in seen_mi:
                seen_mi[mi_path] = _count_mi_refs(ar, mi_path, dep_opt)
            mi_ref_count = seen_mi[mi_path]

            # 收集该 MI 上覆盖的有效贴图
            tex_paths = []
            seen_tex = set()
            for tpv in getattr(mi, 'texture_parameter_values', []):
                tex = tpv.parameter_value
                if not tex:
                    continue
                try:
                    w, h = tex.blueprint_get_size_x(), tex.blueprint_get_size_y()
                except Exception:
                    continue
                if w <= 1 and h <= 1:
                    continue
                tp = tex.get_path_name().split(".")[0]
                if tp not in seen_tex:
                    seen_tex.add(tp)
                    tex_paths.append(tp)

            if tex_paths:
                slots.append({
                    "mesh_path": mesh_path,
                    "slot_idx": slot_idx,
                    "mi_path": mi_path,
                    "mi_ref_count": mi_ref_count,
                    "textures": tex_paths,
                })
    return slots


def _expand_meshes_for_shared(mesh_paths: list, mi_paths: list, ar, dep_opt) -> list:
    """
    skip=False 时：查找引用这些 MI 的所有 Mesh，合并到 mesh_paths 统一装箱。
    """
    import unreal
    extra = set()
    for mi_path in mi_paths:
        refs = ar.get_referencers(unreal.Name(mi_path), dep_opt) or []
        for ref in refs:
            for ad in ar.get_assets_by_package_name(ref):
                if str(ad.asset_class_path.asset_name) in _MESH_ASSET_CLASSES:
                    extra.add(str(ad.package_name))
    return list(dict.fromkeys(mesh_paths + [p for p in extra if p not in mesh_paths]))


def _build_report(raw: dict, dry_run: bool, skipped: list, modified: list) -> str:
    lines = []
    if not raw.get("success"):
        lines.append(f"[失败] {raw.get('error', '未知错误')}")
        return "\n".join(lines)

    tag = "[预览]" if dry_run else "[完整优化]"
    lines += [
        f"{tag} UV 重排报告",
        f"Mesh 数量   : {raw.get('num_meshes', '-')}",
        f"UV 岛数量   : {raw.get('num_islands', '-')}",
        f"材质槽过滤  : {raw.get('material_filter') or '全部'}",
        f"缩放系数    : {raw.get('scale', '-')} （统一，纹理密度一致）",
        f"原始利用率  : {raw.get('orig_utilization', '-')}%",
        f"重排后利用率: {raw.get('utilization', '-')}%",
        f"提升        : {raw.get('improvement', '-')}",
    ]
    if "vertices_updated" in raw:
        lines.append(f"顶点已写回  : {raw['vertices_updated']}")

    if raw.get("textures"):
        lines.append("\n贴图适配结果:")
        for tp, info in raw["textures"].items():
            name = tp.rsplit("/", 1)[-1]
            if "error" in info:
                lines.append(f"  [{name}] 失败: {info['error']}")
            else:
                dr = info.get("density_ratio")
                sz = info.get("out_size")
                lines.append(f"  [{name}] 已生成 {sz}px"
                             + (f"  密度比 {dr}" if dr else "")
                             + f"  -> {info.get('asset', '').split('.')[0]}")

    if skipped:
        lines.append("\n跳过的材质槽（材质实例被多资产引用）:")
        for s in skipped:
            lines.append(f"  [Slot {s['slot_idx']} / {s['mi_path'].rsplit('/',1)[-1]}] {s['reason']}")

    if modified and not dry_run:
        lines.append(f"\n修改的资源（共 {len(modified)} 个）:")
        for m in modified:
            lines.append(f"  {m}")

    return "\n".join(lines)
