# Ref: docs/UEClawBridge/features/xatlas-integration/design.md#2.2
"""
UV 岛提取模块 - Union-Find 实现。
支持材质过滤、PolygonGroup→槽正确映射、多 LOD 共用槽检测。
"""
import unreal


def build_pg_to_slot_map(mesh, lod_idx: int = 0) -> dict:
    """
    构建指定 LOD 的 PolygonGroupID → 材质槽 index 映射。

    UE Section index（PolygonGroupID 顺序编号）与材质槽 index 不一定相同，
    必须通过 StaticMeshEditorSubsystem.get_lod_material_slot 查询。
    """
    subsys = unreal.StaticMeshEditorSubsystem()
    num_sections = mesh.get_num_sections(lod_idx)
    return {sec: subsys.get_lod_material_slot(mesh, lod_idx, sec)
            for sec in range(num_sections)}


def build_lod_slot_info(mesh) -> dict:
    """
    收集所有 LOD 的槽信息。

    Returns:
        {
          lod_idx: {
            "pg_to_slot": {pg_id: slot_idx},
            "slot_to_pgs": {slot_idx: [pg_id, ...]},
            "tri_count": int,
            "has_mesh_desc": bool,
          }
        }
    """
    num_lods = mesh.get_num_lods()
    info = {}
    for lod_idx in range(num_lods):
        pg_to_slot = build_pg_to_slot_map(mesh, lod_idx)
        slot_to_pgs = {}
        for pg, slot in pg_to_slot.items():
            slot_to_pgs.setdefault(slot, []).append(pg)
        try:
            md = mesh.get_static_mesh_description(lod_idx)
            tri_count = md.get_triangle_count() if md else 0
            has_md = tri_count > 0
        except Exception:
            tri_count, has_md = 0, False
        info[lod_idx] = {
            "pg_to_slot": pg_to_slot,
            "slot_to_pgs": slot_to_pgs,
            "tri_count": tri_count,
            "has_mesh_desc": has_md,
        }
    return info


def lods_sharing_slots(mesh, active_slot_ids: set) -> dict:
    """
    返回每个 active 槽在各 LOD 中的共用情况。

    Returns:
        {slot_idx: [lod_idx, ...]}  只含 lod_idx >= 1 且该 LOD 有独立 MeshDesc 的项。
    """
    lod_info = build_lod_slot_info(mesh)
    result = {}
    for slot_id in active_slot_ids:
        shared_lods = [
            lod_idx for lod_idx, info in lod_info.items()
            if lod_idx > 0
            and info["has_mesh_desc"]
            and slot_id in info["slot_to_pgs"]
        ]
        result[slot_id] = shared_lods
    return result


def get_face_material_ids(mesh_desc, tri_count, pg_to_slot: dict):
    """
    返回每个三角形对应的材质槽 index 列表。
    pg_to_slot: build_pg_to_slot_map() 返回值。
    """
    face_mats = []
    for tri in range(tri_count):
        tri_id = unreal.TriangleID(tri)
        try:
            pg = mesh_desc.get_triangle_polygon_group(tri_id)
            pg_id = pg.id_value if hasattr(pg, 'id_value') else int(str(pg))
            mat_id = pg_to_slot.get(pg_id, pg_id)
        except Exception:
            mat_id = 0
        face_mats.append(mat_id)
    return face_mats


def _union_find_root(parent, x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _union(parent, a, b):
    ra, rb = _union_find_root(parent, a), _union_find_root(parent, b)
    if ra != rb:
        parent[rb] = ra


def extract_islands(mesh_paths, uv_channel=0, material_ids=None):
    """
    提取 LOD0 的 UV 岛。重叠 UV 顶点自动合并为同一岛。

    Returns:
        (data_dict, error_str)
        data_dict keys:
            all_face_uvs   : list[(mesh_idx, tri_idx, uvs_tuple|None, mat_id)]
            islands        : list[island_dict]
            meshes         : list[StaticMesh]
            mesh_tri_counts: list[int]
            lod_slot_sharing: {slot_idx: [lod_idx, ...]}  各槽共用的 LOD 列表
    """
    all_face_uvs = []
    mesh_objects = []
    mesh_tri_counts = []
    lod_slot_sharing = {}

    for mi, path in enumerate(mesh_paths):
        mesh = unreal.load_asset(path)
        if not mesh:
            return None, f"Mesh not found: {path}"
        mesh_objects.append(mesh)

        md = mesh.get_static_mesh_description(0)
        tri_count = md.get_triangle_count()
        mesh_tri_counts.append(tri_count)

        pg_to_slot = build_pg_to_slot_map(mesh, 0)
        face_mats = get_face_material_ids(md, tri_count, pg_to_slot)

        for tri in range(tri_count):
            mat_id = face_mats[tri] if tri < len(face_mats) else 0
            if material_ids is not None and mat_id not in material_ids:
                all_face_uvs.append((mi, tri, None, mat_id))
                continue
            tri_id = unreal.TriangleID(tri)
            vis = md.get_triangle_vertex_instances(tri_id)
            uvs = tuple(
                (round(md.get_vertex_instance_uv(v, uv_channel).x, 6),
                 round(md.get_vertex_instance_uv(v, uv_channel).y, 6))
                for v in vis
            )
            all_face_uvs.append((mi, tri, uvs, mat_id))

        # 检测各槽在其他 LOD 的共用情况
        active_slots = set(face_mats) if material_ids is None else \
            {m for m in face_mats if m in material_ids}
        sharing = lods_sharing_slots(mesh, active_slots)
        for slot, lods in sharing.items():
            lod_slot_sharing.setdefault(slot, [])
            lod_slot_sharing[slot] = sorted(set(lod_slot_sharing[slot] + lods))

    active = [gi for gi, (_, _, uvs, _) in enumerate(all_face_uvs) if uvs is not None]
    if not active:
        return None, "No triangles match the material filter"

    # Union-Find：共享 UV 点的面归为同岛
    parent = list(range(len(all_face_uvs)))
    uv_to_faces = {}
    for gi in active:
        for uv in all_face_uvs[gi][2]:
            uv_to_faces.setdefault(uv, []).append(gi)
    for faces in uv_to_faces.values():
        for i in range(1, len(faces)):
            _union(parent, faces[0], faces[i])

    island_map = {}
    for gi in active:
        root = _union_find_root(parent, gi)
        island_map.setdefault(root, []).append(gi)

    islands = []
    for idx, (_, gfaces) in enumerate(island_map.items()):
        all_uvs = {uv for gi in gfaces for uv in all_face_uvs[gi][2]}
        xs = [u[0] for u in all_uvs]
        ys = [u[1] for u in all_uvs]
        mesh_indices = list({all_face_uvs[gi][0] for gi in gfaces})
        islands.append({
            'id': idx,
            'global_faces': gfaces,
            'mesh_indices': mesh_indices,
            'min_x': min(xs), 'max_x': max(xs),
            'min_y': min(ys), 'max_y': max(ys),
            'w': max(xs) - min(xs),
            'h': max(ys) - min(ys),
        })

    return {
        'all_face_uvs': all_face_uvs,
        'islands': islands,
        'meshes': mesh_objects,
        'mesh_tri_counts': mesh_tri_counts,
        'lod_slot_sharing': lod_slot_sharing,
    }, None
