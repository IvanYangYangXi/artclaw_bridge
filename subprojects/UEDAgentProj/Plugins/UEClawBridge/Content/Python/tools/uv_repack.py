"""
UV Repack Tool - 纯脚本实现
将 Static Mesh 的 UV 岛重排到 0-1 空间，提高贴图利用率。
保持重叠 UV 岛不变。默认不旋转（避免法线问题）。

用法:
  from uv_repack import uv_repack
  result = uv_repack(
      ['/Game/Path/Mesh'],
      material_ids=[0],          # 只处理材质 0 的面
      texture_paths=['/Game/Path/Tex_D', '/Game/Path/Tex_N'],
      overwrite_texture=False,   # False=生成新贴图，True=覆盖原贴图
  )
"""
import unreal
import os


# ── UV 岛提取 ──────────────────────────────────────────────

def _get_face_materials(mesh):
    """获取每个三角形的材质 ID（从 MeshDescription polygon groups）。"""
    md = mesh.get_static_mesh_description(0)
    num_tri = md.get_triangle_count()
    face_mats = []

    for tri in range(num_tri):
        tri_id = unreal.TriangleID(tri)
        try:
            pg = md.get_triangle_polygon_group(tri_id)
            mat_id = pg.id_value if hasattr(pg, 'id_value') else int(str(pg))
        except Exception:
            mat_id = 0
        face_mats.append(mat_id)

    return face_mats


def _extract_uv_islands(mesh_paths, uv_channel=0, material_ids=None):
    """提取 UV 岛，支持材质 ID 过滤。重叠面自动归为同组。"""
    all_face_uvs = []     # [(mesh_idx, face_idx_in_mesh, (uv0, uv1, uv2), mat_id)]
    mesh_objects = []
    mesh_face_counts = []

    for mi, path in enumerate(mesh_paths):
        mesh = unreal.load_asset(path)
        if not mesh:
            return None, f"Mesh not found: {path}"
        mesh_objects.append(mesh)

        md = mesh.get_static_mesh_description(0)
        num_tri = md.get_triangle_count()
        mesh_face_counts.append(num_tri)

        # 获取面材质
        face_mats = _get_face_materials(mesh)

        for tri in range(num_tri):
            mat_id = face_mats[tri] if tri < len(face_mats) else 0

            # 材质过滤
            if material_ids is not None and mat_id not in material_ids:
                all_face_uvs.append((mi, tri, None, mat_id))  # 标记为跳过
                continue

            tri_id = unreal.TriangleID(tri)
            vis = md.get_triangle_vertex_instances(tri_id)
            uvs = []
            for vid in vis:
                uv = md.get_vertex_instance_uv(vid, uv_channel)
                uvs.append((round(uv.x, 6), round(uv.y, 6)))
            all_face_uvs.append((mi, tri, tuple(uvs), mat_id))

    # 只对参与的面做 Union-Find
    active_indices = [gi for gi, (mi, fi, uvs, mat) in enumerate(all_face_uvs) if uvs is not None]
    if len(active_indices) == 0:
        return None, "No triangles match the material filter"

    total = len(all_face_uvs)
    parent = list(range(total))

    uv_to_global = {}
    for gi in active_indices:
        mi, fi, uvs, mat = all_face_uvs[gi]
        for uv in uvs:
            if uv not in uv_to_global:
                uv_to_global[uv] = []
            uv_to_global[uv].append(gi)

    for faces in uv_to_global.values():
        for f in faces[1:]:
            a = faces[0]
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            b = f
            while parent[b] != b:
                parent[b] = parent[parent[b]]
                b = parent[b]
            if a != b:
                parent[b] = a

    # 收集岛
    islands_map = {}
    for gi in active_indices:
        r = gi
        while parent[r] != r:
            parent[r] = parent[parent[r]]
            r = parent[r]
        if r not in islands_map:
            islands_map[r] = []
        islands_map[r].append(gi)

    island_list = []
    for idx, (root, global_faces) in enumerate(islands_map.items()):
        all_uvs = set()
        mesh_indices = set()
        for gi in global_faces:
            mi, fi, uvs, mat = all_face_uvs[gi]
            mesh_indices.add(mi)
            for uv in uvs:
                all_uvs.add(uv)
        xs = [u[0] for u in all_uvs]
        ys = [u[1] for u in all_uvs]
        island_list.append({
            'id': idx,
            'global_faces': global_faces,
            'mesh_indices': list(mesh_indices),
            'min_x': min(xs), 'min_y': min(ys),
            'max_x': max(xs), 'max_y': max(ys),
            'w': max(xs) - min(xs), 'h': max(ys) - min(ys),
        })

    return {
        'all_face_uvs': all_face_uvs,
        'islands': island_list,
        'meshes': mesh_objects,
        'mesh_face_counts': mesh_face_counts,
    }, None


# ── MaxRects 装箱 ─────────────────────────────────────────

def _maxrects_pack(rects, pad, allow_rotation=False):
    """MaxRects Best Area Fit。返回 [(x,y,w,h,id,rotated)] 或 None。"""
    free = [(pad, pad, 1.0 - pad, 1.0 - pad)]
    placements = []
    for w, h, rid in rects:
        best_idx = -1
        best_fit = (1e9, 1e9)
        best_pos = None
        best_rot = False
        for fi in range(len(free)):
            fr = free[fi]
            fw, fh = fr[2] - fr[0], fr[3] - fr[1]
            if w + pad <= fw and h + pad <= fh:
                lf = min(fw - w - pad, fh - h - pad)
                score = (lf, max(fw - w, fh - h))
                if score < best_fit:
                    best_fit, best_idx, best_pos, best_rot = score, fi, (fr[0], fr[1]), False
            if allow_rotation and h + pad <= fw and w + pad <= fh:
                lf = min(fw - h - pad, fh - w - pad)
                score = (lf, max(fw - h, fh - w))
                if score < best_fit:
                    best_fit, best_idx, best_pos, best_rot = score, fi, (fr[0], fr[1]), True
        if best_idx < 0:
            return None
        pw, ph = (h, w) if best_rot else (w, h)
        px, py = best_pos
        placements.append((px, py, pw, ph, rid, best_rot))
        fr = free[best_idx]
        del free[best_idx]
        if fr[2] - (px + pw + pad) > 0.001:
            free.append((px + pw + pad, fr[1], fr[2], fr[3]))
        if fr[3] - (py + ph + pad) > 0.001:
            free.append((fr[0], py + ph + pad, px + pw + pad, fr[3]))
    return placements


def _find_best_scale(island_list, padding, allow_rotation=False):
    """二分搜索最大缩放系数。"""
    lo, hi = 0.1, 200.0
    best_p, best_s = None, 0.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        rects = []
        for i in island_list:
            rects.append((i['w'] * mid, i['h'] * mid, i['id']))
        rects.sort(key=lambda r: r[0] * r[1], reverse=True)
        p = _maxrects_pack(rects, padding, allow_rotation)
        if p is not None:
            best_p, best_s = p, mid
            lo = mid
        else:
            hi = mid
    return best_p, best_s


# ── UV 写回 ───────────────────────────────────────────────

def _apply_uv_transform(data, placements, scale, src_uv, allow_rotation):
    """写回 UV。只改参与的面，不增加 UV 通道。"""
    all_face_uvs = data['all_face_uvs']
    island_list = data['islands']
    meshes = data['meshes']

    place_map = {p[4]: p for p in placements}

    gf_to_isl = {}
    for isl in island_list:
        for gi in isl['global_faces']:
            gf_to_isl[gi] = isl

    total_updated = 0
    for mi, mesh in enumerate(meshes):
        md = mesh.get_static_mesh_description(0)
        num_tri = md.get_triangle_count()
        offset = sum(data['mesh_face_counts'][:mi])

        modified = False
        for fi in range(num_tri):
            gi = offset + fi
            if gi not in gf_to_isl:
                continue
            isl = gf_to_isl[gi]
            if isl['id'] not in place_map:
                continue

            px, py, pw, ph, _, rotated = place_map[isl['id']]
            _, _, orig_uvs, _ = all_face_uvs[gi]

            tri_id = unreal.TriangleID(fi)
            vis = md.get_triangle_vertex_instances(tri_id)

            for vi_idx, vid in enumerate(vis):
                ou = orig_uvs[vi_idx]
                lx = (ou[0] - isl['min_x']) * scale
                ly = (ou[1] - isl['min_y']) * scale
                if rotated and allow_rotation:
                    lx, ly = ly, lx
                md.set_vertex_instance_uv(vid, unreal.Vector2D(lx + px, ly + py), src_uv)
                total_updated += 1
                modified = True

        if modified:
            mesh.build_from_static_mesh_descriptions([md])

    return total_updated


# ── 贴图适配 ──────────────────────────────────────────────

def _export_texture(tex, out_path):
    """导出 UE 贴图到 TGA 文件。"""
    task = unreal.AssetExportTask()
    task.object = tex
    task.filename = out_path
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    return unreal.Exporter.run_asset_export_task(task)


def _import_texture(file_path, dest_path, overwrite_asset=None):
    """导入贴图到 UE 项目。"""
    task = unreal.AssetImportTask()
    task.filename = file_path
    if overwrite_asset:
        parts = overwrite_asset.rsplit('/', 1)
        task.destination_path = parts[0] if len(parts) > 1 else '/Game'
        task.destination_name = parts[-1] if len(parts) > 1 else overwrite_asset
        task.replace_existing = True
    else:
        task.destination_path = dest_path
        task.replace_existing = False
    task.automated = True
    task.save = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    try:
        imported = task.get_editor_property('imported_object_paths')
        if imported and len(imported) > 0:
            return str(imported[0])
    except Exception:
        pass
    # Check if asset exists at expected path
    expected = f"{task.destination_path}/{task.destination_name}" if overwrite_asset else dest_path
    return expected


def _adapt_texture(island_list, placements, scale, allow_rotation,
                   texture_path, output_resolution, bleed_pixels,
                   overwrite, temp_dir):
    """对一张贴图做逆映射适配。"""
    from PIL import Image
    import numpy as np

    place_map = {p[4]: p for p in placements}

    # 导出源贴图
    src_tex = unreal.load_asset(texture_path)
    if not src_tex:
        return None, f"Texture not found: {texture_path}"

    src_name = texture_path.rsplit('/', 1)[-1]
    export_path = os.path.join(temp_dir, f'{src_name}_src.tga')
    if not _export_texture(src_tex, export_path):
        return None, f"Failed to export {texture_path}"

    # 读取源像素
    src_img = Image.open(export_path).convert('RGBA')
    src_w, src_h = src_img.size
    src_arr = np.array(src_img)  # (H, W, 4) uint8

    out_res = output_resolution or max(src_w, src_h)

    # 创建输出图像
    out_arr = np.zeros((out_res, out_res, 4), dtype=np.uint8)
    filled = np.zeros((out_res, out_res), dtype=bool)

    # 逆映射: 向量化——每个 island 一次处理整个 target bounds
    for isl in island_list:
        isl_id = isl['id']
        if isl_id not in place_map:
            continue
        px, py, pw, ph, _, rotated = place_map[isl_id]

        # Target pixel bounds
        min_px = max(0, int(px * out_res) - 1)
        max_px = min(out_res - 1, int((px + pw) * out_res) + 1)
        min_py = max(0, int(py * out_res) - 1)
        max_py = min(out_res - 1, int((py + ph) * out_res) + 1)

        # 生成 target pixel grid
        ox_arr = np.arange(min_px, max_px + 1)
        oy_arr = np.arange(min_py, max_py + 1)
        ox_grid, oy_grid = np.meshgrid(ox_arr, oy_arr)

        # Target UV
        tu = (ox_grid + 0.5) / out_res
        tv = (oy_grid + 0.5) / out_res

        # Local coords
        lx = tu - px
        ly = tv - py

        if rotated and allow_rotation:
            lx, ly = ly, lx

        # Source UV
        su = lx / scale + isl['min_x']
        sv = ly / scale + isl['min_y']

        # Bounds mask
        margin = 0.0005
        mask = ((su >= isl['min_x'] - margin) & (su <= isl['max_x'] + margin) &
                (sv >= isl['min_y'] - margin) & (sv <= isl['max_y'] + margin))

        if not mask.any():
            continue

        # Bilinear sample (vectorized)
        sx = su[mask] * src_w - 0.5
        sy = sv[mask] * src_h - 0.5
        x0 = np.clip(np.floor(sx).astype(int), 0, src_w - 1)
        y0 = np.clip(np.floor(sy).astype(int), 0, src_h - 1)
        x1 = np.minimum(x0 + 1, src_w - 1)
        y1 = np.minimum(y0 + 1, src_h - 1)
        fx = np.clip(sx - x0, 0, 1)
        fy = np.clip(sy - y0, 0, 1)

        # Gather 4 corners
        c00 = src_arr[y0, x0].astype(np.float32)
        c10 = src_arr[y0, x1].astype(np.float32)
        c01 = src_arr[y1, x0].astype(np.float32)
        c11 = src_arr[y1, x1].astype(np.float32)

        fx4 = fx[:, np.newaxis]
        fy4 = fy[:, np.newaxis]
        c = (c00 * (1-fx4)*(1-fy4) + c10 * fx4*(1-fy4) +
             c01 * (1-fx4)*fy4 + c11 * fx4*fy4)
        pixels = np.clip(c, 0, 255).astype(np.uint8)

        # Write to output
        dest_oy = oy_grid[mask]
        dest_ox = ox_grid[mask]
        out_arr[dest_oy, dest_ox] = pixels
        filled[dest_oy, dest_ox] = True

    # Bleed: numpy 向量化
    for _ in range(bleed_pixels):
        empty = ~filled
        if not empty.any():
            break
        new_filled = filled.copy()
        new_arr = out_arr.copy()
        padded = np.pad(out_arr, ((1,1),(1,1),(0,0)), mode='edge')
        padded_f = np.pad(filled, ((1,1),(1,1)), mode='constant', constant_values=False)
        for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
            nf = padded_f[1+dy:out_res+1+dy, 1+dx:out_res+1+dx]
            nv = padded[1+dy:out_res+1+dy, 1+dx:out_res+1+dx]
            m = empty & nf
            if m.any():
                new_arr[m] = nv[m]
                new_filled[m] = True
        out_arr = new_arr
        filled = new_filled

    # 保存
    out_img = Image.fromarray(out_arr, 'RGBA')
    if overwrite:
        out_file = os.path.join(temp_dir, f'{src_name}.png')
    else:
        out_file = os.path.join(temp_dir, f'{src_name}_repacked.png')
    out_img.save(out_file)

    # 导入回 UE
    if overwrite:
        imported = _import_texture(out_file, None, overwrite_asset=texture_path)
    else:
        src_dir = texture_path.rsplit('/', 1)[0] if '/' in texture_path else '/Game'
        imported = _import_texture(out_file, src_dir)

    if imported:
        return {'file': out_file, 'asset': imported}, None
    else:
        return {'file': out_file, 'asset': None}, "Saved to disk but UE import failed"


# ── 主函数 ─────────────────────────────────────────────────

def uv_repack(mesh_paths, src_uv=0, padding=0.002,
              material_ids=None, allow_rotation=False,
              texture_paths=None, output_resolution=None,
              bleed_pixels=4, overwrite_texture=False,
              dry_run=False):
    """
    UV Repack 主函数。

    Args:
        mesh_paths: mesh 路径（str 或 list）
        src_uv: UV 通道（默认 0）
        padding: UV 岛间距
        material_ids: 只处理指定材质 ID 的面（None=全部，list[int]=[0,1]）
        allow_rotation: 是否允许旋转（默认 False）
        texture_paths: 关联贴图路径列表（None=只改 UV）
        output_resolution: 输出贴图分辨率（None=与源同）
        bleed_pixels: 贴图边缘扩展像素
        overwrite_texture: True=覆盖原贴图，False=生成新贴图
        dry_run: True=只分析不写回

    Returns:
        dict: success, scale, utilization, num_islands 等
    """
    if isinstance(mesh_paths, str):
        mesh_paths = [mesh_paths]

    data, err = _extract_uv_islands(mesh_paths, src_uv, material_ids)
    if err:
        return {'success': False, 'error': err}

    island_list = data['islands']
    if len(island_list) == 0:
        return {'success': False, 'error': 'No UV islands found'}

    orig_area = sum(i['w'] * i['h'] for i in island_list)
    placements, scale = _find_best_scale(island_list, padding, allow_rotation)
    if placements is None:
        return {'success': False, 'error': 'Failed to pack islands'}

    used_area = sum(p[2] * p[3] for p in placements)

    result = {
        'success': True,
        'num_islands': len(island_list),
        'num_meshes': len(data['meshes']),
        'scale': round(scale, 4),
        'utilization': round(used_area * 100, 1),
        'orig_utilization': round(orig_area * 100, 2),
        'improvement': f"{scale:.1f}x",
        'material_filter': material_ids,
    }

    if not dry_run:
        n = _apply_uv_transform(data, placements, scale, src_uv, allow_rotation)
        result['vertices_updated'] = n

        # 贴图适配
        if texture_paths:
            saved_dir = unreal.Paths.convert_relative_path_to_full(
                unreal.Paths.project_saved_dir())
            temp_dir = os.path.join(saved_dir, 'UVRepack')
            os.makedirs(temp_dir, exist_ok=True)

            result['textures'] = {}
            for tp in texture_paths:
                tex_result, tex_err = _adapt_texture(
                    island_list, placements, scale, allow_rotation,
                    tp, output_resolution, bleed_pixels,
                    overwrite_texture, temp_dir)
                if tex_err:
                    result['textures'][tp] = {'error': tex_err, **(tex_result or {})}
                else:
                    result['textures'][tp] = tex_result

    return result
