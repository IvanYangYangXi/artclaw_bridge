"""
关卡贴图审计 - DataTable 生成器
================================
将贴图审计CSV数据 + 运行时尺寸 → UE DataTable 资源

功能:
  1. 读取 texture_audit_summary.csv (贴图审计CSV)
  2. 自动获取每张贴图的游戏运行时尺寸(考虑 MaxTextureSize / LODBias)
  3. 通过 PythonStructLib 创建蓝图结构体 S_TextureAuditRow (含 SoftObjectReference)
  4. 创建 DataTable 并填充全部数据
  5. TexturePath 列支持双击跳转到对应贴图资源

输出:
  /Game/__Check__/{level_name}/S_TextureAuditRow  (蓝图结构体)
  /Game/__Check__/{level_name}/DT_TextureAudit    (DataTable)

依赖:
  - texture_audit_summary.csv (由 convert_to_csv.py 生成)
  - 或手动指定 CSV 路径

用法 (在 UEClawBridge run_ue_python 中直接调用各函数):
  from texture_audit_datatable import generate_datatable
  generate_datatable(csv_path, target_dir)
"""
import unreal
import csv
import json
import os

SAVED_DIR = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())


def _sf(v):
    """安全转float"""
    try:
        return float(v)
    except:
        return 0.0


def _si(v):
    """安全转int"""
    try:
        return int(float(v))
    except:
        return 0


def _log(msg):
    unreal.log('[TexAuditDT] ' + str(msg))


# ──────────── Step 1: 获取运行时尺寸 ────────────

def get_texture_runtime_sizes(tex_paths, cache_path=None):
    """
    批量获取贴图运行时尺寸
    
    Args:
        tex_paths: dict  {asset_path: error_str}  error_str 为空表示正常
        cache_path: 可选缓存文件路径
    Returns:
        dict  {asset_path: [runtime_w, runtime_h, source_w, source_h, error]}
    """
    # 尝试读缓存
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            cached = json.load(f)
        if len(cached) >= len(tex_paths) * 0.9:
            _log('Using cached sizes (' + str(len(cached)) + ' entries)')
            return cached

    _log('Computing runtime sizes for ' + str(len(tex_paths)) + ' textures...')
    sizes = {}
    ok = fail = 0

    for path, err in tex_paths.items():
        if err == 'file_not_found':
            sizes[path] = [0, 0, 0, 0, 'file_not_found']
            fail += 1
            continue
        try:
            tex = unreal.EditorAssetLibrary.load_asset(path)
            if tex and isinstance(tex, unreal.Texture2D):
                sx = tex.blueprint_get_size_x()
                sy = tex.blueprint_get_size_y()
                ms = tex.get_editor_property('max_texture_size')
                lb = tex.get_editor_property('lod_bias')
                ex, ey = sx, sy
                for _ in range(lb):
                    ex, ey = max(1, ex // 2), max(1, ey // 2)
                if ms > 0:
                    while ex > ms or ey > ms:
                        ex, ey = max(1, ex // 2), max(1, ey // 2)
                sizes[path] = [ex, ey, sx, sy, '']
                ok += 1
            else:
                sizes[path] = [0, 0, 0, 0, 'not_tex2d']
                fail += 1
        except Exception as e:
            sizes[path] = [0, 0, 0, 0, str(e)[:50]]
            fail += 1

    _log('Sizes done: ok=' + str(ok) + ' fail=' + str(fail))

    if cache_path:
        with open(cache_path, 'w') as f:
            json.dump(sizes, f)

    return sizes


# ──────────── Step 2: 创建蓝图结构体 ────────────

def ensure_struct(target_dir, struct_name='S_TextureAuditRow'):
    """
    确保目标目录下存在带正确字段的蓝图结构体
    如果已存在且字段匹配则直接返回，否则创建新的
    
    Returns: UserDefinedStruct 对象
    """
    psl = unreal.PythonStructLib
    uds_path = target_dir + '/' + struct_name

    # 已存在则验证字段
    if unreal.EditorAssetLibrary.does_asset_exist(uds_path):
        uds = unreal.EditorAssetLibrary.load_asset(uds_path)
        names = psl.get_friendly_names(uds)
        expected = ['TexturePath', 'TextureName', 'RuntimeWidth', 'RuntimeHeight',
                    'SourceWidth', 'SourceHeight', 'FirstUploader', 'LastModifier',
                    'FirstSVNVer', 'LastSVNVer', 'Error']
        # 简单检查: 字段数量和第一个字段名匹配
        if len(names) == len(expected) and 'TexturePath' in str(names):
            _log('Struct OK: ' + uds_path)
            return uds
        else:
            _log('Struct mismatch, recreating...')
            unreal.EditorAssetLibrary.delete_asset(uds_path)

    # 创建新 UDS
    unreal.EditorAssetLibrary.make_directory(target_dir)
    sfac = unreal.StructureFactory()
    uds = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        struct_name, target_dir, None, sfac)
    if not uds:
        _log('ERROR: Failed to create struct')
        return None

    # 添加字段
    tex2d_class = unreal.Texture2D.static_class()
    fields = [
        ('softobjectreference', '', tex2d_class, 'TexturePath'),
        ('string', '', None, 'TextureName'),
        ('int', '', None, 'RuntimeWidth'),
        ('int', '', None, 'RuntimeHeight'),
        ('int', '', None, 'SourceWidth'),
        ('int', '', None, 'SourceHeight'),
        ('string', '', None, 'FirstUploader'),
        ('string', '', None, 'LastModifier'),
        ('string', '', None, 'FirstSVNVer'),
        ('string', '', None, 'LastSVNVer'),
        ('string', '', None, 'Error'),
    ]

    for cat, sub, sub_obj, fname in fields:
        psl.add_variable(uds, cat, sub, sub_obj, 0, False, fname)

    # 删除默认的 MemberVar
    var_names = psl.get_variable_names(uds)
    for vn in var_names:
        if 'MemberVar' in str(vn):
            psl.remove_variable_by_name(uds, str(vn))
            break

    unreal.EditorAssetLibrary.save_asset(uds_path)
    _log('Created struct: ' + uds_path + ' (' + str(len(fields)) + ' fields)')
    return uds


# ──────────── Step 3: 创建并填充 DataTable ────────────

def create_datatable(uds, rows, sizes, target_dir, dt_name='DT_TextureAudit'):
    """
    创建 DataTable 并填充数据
    
    Args:
        uds: UserDefinedStruct
        rows: list of csv rows
        sizes: dict from get_texture_runtime_sizes
        target_dir: UE content path
        dt_name: DataTable asset name
    Returns: bool success
    """
    dt_path = target_dir + '/' + dt_name

    if unreal.EditorAssetLibrary.does_asset_exist(dt_path):
        unreal.EditorAssetLibrary.delete_asset(dt_path)

    fac = unreal.DataTableFactory()
    fac.set_editor_property('struct', uds)
    dt = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        dt_name, target_dir, None, fac)
    if not dt:
        _log('ERROR: Failed to create DataTable')
        return False

    # 构建 JSON
    jdata = []
    for i, row in enumerate(rows):
        tex_name = row[0]
        tex_path = row[1] if len(row) > 1 else ''
        s = sizes.get(tex_path, [0, 0, 0, 0, ''])
        rw, rh = _si(s[0]), _si(s[1])
        sw = _si(s[2]) if len(s) > 2 else 0
        sh = _si(s[3]) if len(s) > 3 else 0
        err_csv = row[8] if len(row) > 8 else ''

        jdata.append({
            "Name": "Row_" + str(i),
            "TexturePath": tex_path + '.' + tex_name if tex_path else '',
            "TextureName": tex_name,
            "RuntimeWidth": rw,
            "RuntimeHeight": rh,
            "SourceWidth": sw,
            "SourceHeight": sh,
            "FirstUploader": row[3] if len(row) > 3 else '',
            "LastModifier": row[6] if len(row) > 6 else '',
            "FirstSVNVer": row[4] if len(row) > 4 else '',
            "LastSVNVer": row[7] if len(row) > 7 else '',
            "Error": err_csv,
        })

    _log('Filling ' + str(len(jdata)) + ' rows...')
    ok = unreal.DataTableFunctionLibrary.fill_data_table_from_json_string(
        dt, json.dumps(jdata))

    if ok:
        cnt = len(unreal.DataTableFunctionLibrary.get_data_table_row_names(dt))
        unreal.EditorAssetLibrary.save_asset(dt_path)
        _log('SUCCESS: ' + str(cnt) + ' rows -> ' + dt_path)
    else:
        _log('FAILED to fill DataTable')

    return ok


# ──────────── 主入口 ────────────

def generate_datatable(csv_path=None, target_dir=None, sizes_cache=None):
    """
    一键生成贴图审计 DataTable
    
    Args:
        csv_path: CSV文件路径 (默认 Saved/texture_audit_summary.csv)
        target_dir: UE目标目录 (默认 /Game/__Check__/L_Miami_WC)
        sizes_cache: 尺寸缓存JSON路径 (可选，加速重复执行)
    Returns: bool success
    """
    if csv_path is None:
        csv_path = os.path.join(SAVED_DIR, 'texture_audit_summary.csv')
    if target_dir is None:
        target_dir = '/Game/__Check__/L_Miami_WC'
    if sizes_cache is None:
        sizes_cache = os.path.join(SAVED_DIR, '_texture_sizes_cache.json')

    _log('=== Generate Texture Audit DataTable ===')
    _log('CSV: ' + csv_path)
    _log('Target: ' + target_dir)

    # 读 CSV
    rows = []
    tex_paths = {}
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader)
        for r in reader:
            if len(r) >= 2:
                rows.append(r)
                tex_paths[r[1]] = r[8] if len(r) > 8 else ''

    _log(str(len(rows)) + ' texture records')

    # 获取运行时尺寸
    sizes = get_texture_runtime_sizes(tex_paths, sizes_cache)

    # 创建结构体
    uds = ensure_struct(target_dir)
    if not uds:
        return False

    # 创建 DataTable
    ok = create_datatable(uds, rows, sizes, target_dir)

    _log('=== Done ===')
    return ok
