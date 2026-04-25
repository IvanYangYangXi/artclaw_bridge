# Ref: docs/UEClawBridge/features/xatlas-integration/design.md#4.4
"""
贴图适配模块 - 逆映射 + 双线性采样 + bleed。
包含贴图尺寸计算（2^n 或 4 的倍数规则）。
"""
import os
import math
import unreal


# ── 尺寸计算 ────────────────────────────────────────────────

def _next_pow2(n):
    if n <= 0:
        return 1
    return 1 << math.ceil(math.log2(max(n, 1)))


def _next_mult4(n):
    return max(4, (int(math.ceil(n)) + 3) & ~3)


def calc_target_size(src_size, scale, min_size=64, max_size=8192):
    """
    计算目标贴图尺寸（等密度）。

    规则：
    - 基准值 = src_size / sqrt(scale)，保持 texel 密度与优化前一致
    - 优先 2^n；若 2^n 比基准大超 20% 则改用 4 的倍数
    - 钳制在 [min_size, max_size]

    Returns:
        (target_size, density_ratio)  density_ratio > 1 表示密度提升
    """
    base = src_size / math.sqrt(scale) if scale > 0 else src_size
    p2 = _next_pow2(int(math.ceil(base)))
    waste_ratio = (p2 - base) / base if base > 0 else 0

    if waste_ratio > 0.20:
        chosen = _next_mult4(base)
    else:
        chosen = p2

    chosen = int(max(min_size, min(max_size, chosen)))
    density_ratio = round((chosen / src_size) ** 2 * scale, 3) if src_size > 0 else 1.0
    return chosen, density_ratio


# ── 贴图导出/导入 ────────────────────────────────────────────

def export_texture(tex, out_path):
    task = unreal.AssetExportTask()
    task.object = tex
    task.filename = out_path
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    return unreal.Exporter.run_asset_export_task(task)


def read_texture_props(texture_path: str) -> dict:
    """读取 UE 贴图的原始属性，用于导入后还原。"""
    tex = unreal.load_asset(texture_path)
    if not tex:
        return {}
    return {
        'srgb': tex.srgb,
        'compression': tex.compression_settings,
        'mip_gen': tex.mip_gen_settings,
    }


def import_texture(file_path, dest_ue_path, overwrite=False, orig_props=None):
    """
    导入贴图到 UE，导入后还原 sRGB / 压缩格式 / Mip 设置。
    dest_ue_path: 目标 UE 资产路径（含资产名），如 /Game/Foo/T_Bar
    orig_props: read_texture_props() 返回的属性字典
    """
    task = unreal.AssetImportTask()
    task.filename = file_path
    task.automated = True
    task.save = False  # 先不 save，还原属性后再 save
    if overwrite:
        parts = dest_ue_path.rsplit('/', 1)
        task.destination_path = parts[0] if len(parts) > 1 else '/Game'
        task.destination_name = parts[-1]
        task.replace_existing = True
    else:
        task.destination_path = dest_ue_path.rsplit('/', 1)[0] if '/' in dest_ue_path else '/Game'
        task.replace_existing = False
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    try:
        paths = task.get_editor_property('imported_object_paths')
        imported_path = str(paths[0]) if paths else dest_ue_path
    except Exception:
        imported_path = dest_ue_path

    # 还原原始属性（避免 NRM 被当 sRGB/TC_DEFAULT 处理）
    if orig_props:
        ue_path = imported_path.split('.')[0]
        tex = unreal.load_asset(ue_path)
        if tex:
            if 'srgb' in orig_props:
                tex.srgb = orig_props['srgb']
            if 'compression' in orig_props:
                tex.compression_settings = orig_props['compression']
            if 'mip_gen' in orig_props:
                tex.mip_gen_settings = orig_props['mip_gen']
            unreal.EditorAssetLibrary.save_asset(ue_path)

    return imported_path


# ── 贴图适配（逆映射） ──────────────────────────────────────

def adapt_texture(island_list, placements, scale, allow_rotation,
                  texture_path, output_resolution, bleed_pixels,
                  overwrite, temp_dir):
    """
    对单张贴图做逆映射重采样。
    output_resolution: 已按等密度计算好的目标分辨率，不能 fallback 到原图尺寸。

    Returns:
        (result_dict, error_str)
    """
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return None, "Pillow/numpy not available"

    place_map = {p[4]: p for p in placements}
    src_tex = unreal.load_asset(texture_path)
    if not src_tex:
        return None, f"Texture not found: {texture_path}"

    # 导入前先读取原始属性（sRGB / compression / mip_gen）
    orig_props = read_texture_props(texture_path)

    src_name = texture_path.rsplit('/', 1)[-1]
    export_path = os.path.join(temp_dir, f'{src_name}_src.tga')
    if not export_texture(src_tex, export_path):
        return None, f"Export failed: {texture_path}"

    src_img = Image.open(export_path)
    # 保持原始通道数：RGB 贴图不强制加 alpha，RGBA 保持 RGBA
    src_mode = src_img.mode
    if src_mode not in ('RGB', 'RGBA', 'L'):
        src_img = src_img.convert('RGBA')
        src_mode = 'RGBA'
    src_arr = np.array(src_img)
    src_w, src_h = src_img.size
    n_ch = src_arr.shape[2] if src_arr.ndim == 3 else 1

    # 用导出的 TGA 实际尺寸计算目标分辨率（避免 UE 资产尺寸已被改动的污染）
    if output_resolution is None:
        src_size = max(src_w, src_h)
        out_res, density_ratio = calc_target_size(src_size, scale)
    else:
        out_res = output_resolution
        density_ratio = round((out_res / max(src_w, src_h)) ** 2 * scale, 3)
    out_arr = np.zeros((out_res, out_res, n_ch), dtype=np.uint8)
    filled = np.zeros((out_res, out_res), dtype=bool)

    for isl in island_list:
        if isl['id'] not in place_map:
            continue
        px, py, pw, ph, _, rotated = place_map[isl['id']]

        min_px = max(0, int(px * out_res) - 1)
        max_px = min(out_res - 1, int((px + pw) * out_res) + 1)
        min_py = max(0, int(py * out_res) - 1)
        max_py = min(out_res - 1, int((py + ph) * out_res) + 1)

        ox_arr = np.arange(min_px, max_px + 1)
        oy_arr = np.arange(min_py, max_py + 1)
        ox_grid, oy_grid = np.meshgrid(ox_arr, oy_arr)

        tu = (ox_grid + 0.5) / out_res
        tv = (oy_grid + 0.5) / out_res
        lx = tu - px
        ly = tv - py

        if rotated and allow_rotation:
            lx, ly = ly, lx

        su = lx / scale + isl['min_x']
        sv = ly / scale + isl['min_y']

        margin = 0.0005
        mask = ((su >= isl['min_x'] - margin) & (su <= isl['max_x'] + margin) &
                (sv >= isl['min_y'] - margin) & (sv <= isl['max_y'] + margin))
        if not mask.any():
            continue

        sx = su[mask] * src_w - 0.5
        sy = sv[mask] * src_h - 0.5
        x0 = np.clip(np.floor(sx).astype(int), 0, src_w - 1)
        y0 = np.clip(np.floor(sy).astype(int), 0, src_h - 1)
        x1 = np.minimum(x0 + 1, src_w - 1)
        y1 = np.minimum(y0 + 1, src_h - 1)
        fx = np.clip(sx - x0, 0, 1)
        fy = np.clip(sy - y0, 0, 1)

        fx4, fy4 = fx[:, np.newaxis], fy[:, np.newaxis]
        c = (src_arr[y0, x0].astype(np.float32) * (1 - fx4) * (1 - fy4) +
             src_arr[y0, x1].astype(np.float32) * fx4 * (1 - fy4) +
             src_arr[y1, x0].astype(np.float32) * (1 - fx4) * fy4 +
             src_arr[y1, x1].astype(np.float32) * fx4 * fy4)
        out_arr[oy_grid[mask], ox_grid[mask]] = np.clip(c, 0, 255).astype(np.uint8)
        filled[oy_grid[mask], ox_grid[mask]] = True

    # Bleed
    for _ in range(bleed_pixels):
        empty = ~filled
        if not empty.any():
            break
        new_arr = out_arr.copy()
        new_filled = filled.copy()
        padded = np.pad(out_arr, ((1, 1), (1, 1), (0, 0)), mode='edge')
        padded_f = np.pad(filled, ((1, 1), (1, 1)), mode='constant', constant_values=False)
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nf = padded_f[1 + dy:out_res + 1 + dy, 1 + dx:out_res + 1 + dx]
            nv = padded[1 + dy:out_res + 1 + dy, 1 + dx:out_res + 1 + dx]
            m = empty & nf
            if m.any():
                new_arr[m] = nv[m]
                new_filled[m] = True
        out_arr, filled = new_arr, new_filled

    suffix = '' if overwrite else '_repacked'
    out_file = os.path.join(temp_dir, f'{src_name}{suffix}.png')
    Image.fromarray(out_arr, src_mode).save(out_file)

    dest = texture_path if overwrite else f"{texture_path.rsplit('/', 1)[0]}/{src_name}{suffix}"
    imported = import_texture(out_file, dest, overwrite=overwrite, orig_props=orig_props)
    return {'file': out_file, 'asset': imported,
            'out_size': out_res, 'src_mode': src_mode,
            'density_ratio': density_ratio}, None
