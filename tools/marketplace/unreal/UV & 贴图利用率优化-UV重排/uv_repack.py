# Ref: docs/UEClawBridge/features/xatlas-integration/design.md
"""
UV Repack Tool - 重写版主模块。
将 Static Mesh 的 UV 岛重排到 0-1 空间，提高贴图利用率。

核心改进：
- 正确的 MaxRects free list 分割（修复旧版 bug）
- 统一 scale：所有岛等比缩放，保证纹理密度一致
- 贴图尺寸：2^n 优先；浪费 > 20% 改用 4 的倍数
- 模块化拆分：islands / pack / texture 三个子模块

用法:
    from uv_repack import uv_repack
    result = uv_repack(
        ['/Game/Mesh/SM_Foo'],
        material_ids=[0],
        texture_paths=['/Game/Tex/T_Foo_D'],
        dry_run=True,          # 只分析，不写回
    )
"""
import os
import unreal
from uv_repack_islands import extract_islands
from uv_repack_pack import find_best_scale, calc_utilization
from uv_repack_texture import adapt_texture, calc_target_size


# ── UV 写回 ────────────────────────────────────────────────

def _apply_uv_transform(data, placements, scale, src_uv, allow_rotation):
    """
    将装箱结果写回 UV。
    - LOD0：处理被过滤选中的面
    - LOD1+：对共用同一材质槽的 LOD，用相同的 island 变换写回对应面的 UV
    """
    all_face_uvs = data['all_face_uvs']
    islands = data['islands']
    meshes = data['meshes']
    mesh_tri_counts = data['mesh_tri_counts']
    lod_slot_sharing = data.get('lod_slot_sharing', {})

    place_map = {p[4]: p for p in placements}
    gface_to_isl = {gi: isl for isl in islands for gi in isl['global_faces']}

    # 预建 island 的 UV 变换查表（按 mat_id 分组，供 LOD 写回使用）
    # 对 LOD1+，我们用相同的 scale + 平移，但需要从 LOD 自己的 UV 坐标逆推
    # LOD 共用 LOD0 贴图 → 其 UV 坐标系与 LOD0 相同 → 使用相同 island AABB 变换
    slot_isl_map = {}  # slot_id → list of (island, placement)
    for isl in islands:
        mat_ids = {all_face_uvs[gi][3] for gi in isl['global_faces'] if all_face_uvs[gi][2]}
        if isl['id'] not in place_map:
            continue
        for mat_id in mat_ids:
            slot_isl_map.setdefault(mat_id, []).append((isl, place_map[isl['id']]))

    total_updated = 0

    for mi, mesh in enumerate(meshes):
        # ── LOD0 写回 ──────────────────────────────────────
        md0 = mesh.get_static_mesh_description(0)
        tri_offset = sum(mesh_tri_counts[:mi])
        modified = False

        for fi in range(mesh_tri_counts[mi]):
            gi = tri_offset + fi
            isl = gface_to_isl.get(gi)
            if isl is None or isl['id'] not in place_map:
                continue
            px, py, _, _, _, rotated = place_map[isl['id']]
            orig_uvs = all_face_uvs[gi][2]
            vis = md0.get_triangle_vertex_instances(unreal.TriangleID(fi))
            for vi_idx, vid in enumerate(vis):
                ou = orig_uvs[vi_idx]
                lx = (ou[0] - isl['min_x']) * scale
                ly = (ou[1] - isl['min_y']) * scale
                if rotated and allow_rotation:
                    lx, ly = ly, lx
                md0.set_vertex_instance_uv(vid, unreal.Vector2D(lx + px, ly + py), src_uv)
                total_updated += 1
                modified = True

        if modified:
            mesh.build_from_static_mesh_descriptions([md0])

        # ── LOD1+ 写回（共用槽）────────────────────────────
        num_lods = mesh.get_num_lods()
        if num_lods <= 1:
            continue

        from uv_repack_islands import build_pg_to_slot_map, get_face_material_ids

        for lod_idx in range(1, num_lods):
            # 确认该 LOD 有哪些槽与 LOD0 处理槽重叠
            active_slots_in_lod = set()
            for slot_id, shared_lods in lod_slot_sharing.items():
                if lod_idx in shared_lods:
                    active_slots_in_lod.add(slot_id)
            if not active_slots_in_lod:
                continue

            md_lod = mesh.get_static_mesh_description(lod_idx)
            if not md_lod:
                continue
            lod_tri_count = md_lod.get_triangle_count()
            pg_to_slot_lod = build_pg_to_slot_map(mesh, lod_idx)
            face_mats_lod = get_face_material_ids(md_lod, lod_tri_count, pg_to_slot_lod)

            lod_modified = False
            for fi in range(lod_tri_count):
                mat_id = face_mats_lod[fi] if fi < len(face_mats_lod) else 0
                if mat_id not in active_slots_in_lod:
                    continue
                isls_for_slot = slot_isl_map.get(mat_id, [])
                if not isls_for_slot:
                    continue

                vis = md_lod.get_triangle_vertex_instances(unreal.TriangleID(fi))
                tri_id = unreal.TriangleID(fi)
                for vid in vis:
                    uv = md_lod.get_vertex_instance_uv(vid, src_uv)
                    u, v = uv.x, uv.y
                    # 找该 UV 点所属的 island（匹配 AABB）
                    best_isl, best_p = None, None
                    for isl, p in isls_for_slot:
                        margin = 0.001
                        if (isl['min_x'] - margin <= u <= isl['max_x'] + margin and
                                isl['min_y'] - margin <= v <= isl['max_y'] + margin):
                            best_isl, best_p = isl, p
                            break
                    if best_isl is None:
                        continue
                    px, py, _, _, _, rotated = best_p
                    lx = (u - best_isl['min_x']) * scale
                    ly = (v - best_isl['min_y']) * scale
                    if rotated and allow_rotation:
                        lx, ly = ly, lx
                    md_lod.set_vertex_instance_uv(
                        vid, unreal.Vector2D(lx + px, ly + py), src_uv)
                    total_updated += 1
                    lod_modified = True

            if lod_modified:
                mesh.build_from_static_mesh_descriptions([md_lod])

    return total_updated


# ── 贴图处理 ───────────────────────────────────────────────

def _process_textures(islands, placements, scale, allow_rotation,
                      texture_paths, output_resolution, bleed_pixels, overwrite):
    saved_dir = unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_saved_dir())
    temp_dir = os.path.join(saved_dir, 'UVRepack')
    os.makedirs(temp_dir, exist_ok=True)

    tex_results = {}
    for tp in texture_paths:
        res, err = adapt_texture(
            islands, placements, scale, allow_rotation,
            tp, output_resolution, bleed_pixels, overwrite, temp_dir,
        )
        entry = res or {}
        if err:
            entry['error'] = err
        tex_results[tp] = entry

    return tex_results


# ── 主函数 ────────────────────────────────────────────────

def uv_repack(mesh_paths, src_uv=0, padding=0.002,
              material_ids=None, allow_rotation=False,
              texture_paths=None, output_resolution=None,
              bleed_pixels=4, overwrite_texture=False,
              dry_run=False):
    """
    UV Repack 主函数。

    Args:
        mesh_paths      : str 或 list[str]，Mesh UE 路径
        src_uv          : UV 通道（默认 0）
        padding         : UV 岛间距（0-1 空间）
        material_ids    : 只处理指定材质 ID；None = 全部
        allow_rotation  : 允许旋转 90°（默认 False，避免法线问题）
        texture_paths   : 关联贴图路径；None = 只改 UV
        output_resolution: 输出贴图分辨率；None = 自动计算
        bleed_pixels    : 贴图边缘扩展像素数
        overwrite_texture: True = 覆盖原贴图；False = 生成 _repacked 副本
        dry_run         : True = 只分析，不写回

    Returns:
        dict with keys: success, num_islands, scale, utilization,
                        orig_utilization, improvement, [vertices_updated],
                        [textures]
    """
    if isinstance(mesh_paths, str):
        mesh_paths = [mesh_paths]

    data, err = extract_islands(mesh_paths, src_uv, material_ids)
    if err:
        return {'success': False, 'error': err}

    islands = data['islands']
    if not islands:
        return {'success': False, 'error': 'No UV islands found'}

    orig_util = sum(i['w'] * i['h'] for i in islands)
    placements, scale = find_best_scale(islands, padding, allow_rotation)

    if not placements:
        return {'success': False, 'error': 'Packing failed: cannot fit islands into 0-1 space'}

    new_util = calc_utilization(placements)

    result = {
        'success': True,
        'num_islands': len(islands),
        'num_meshes': len(data['meshes']),
        'scale': round(scale, 4),
        'utilization': round(new_util * 100, 1),
        'orig_utilization': round(orig_util * 100, 2),
        'improvement': f'{scale / max(orig_util ** 0.5, 1e-6):.2f}x scale',
        'material_filter': material_ids,
    }

    if dry_run:
        return result

    result['vertices_updated'] = _apply_uv_transform(
        data, placements, scale, src_uv, allow_rotation)

    if texture_paths:
        result['textures'] = _process_textures(
            islands, placements, scale, allow_rotation,
            texture_paths, output_resolution, bleed_pixels, overwrite_texture,
        )

    return result
