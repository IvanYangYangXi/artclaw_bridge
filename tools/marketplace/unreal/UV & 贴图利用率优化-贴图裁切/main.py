"""
UV & 贴图利用率优化工具 - main.py
====================================
由 ArtClaw Tool Creator 生成。

流程：
  1. 分析 MaterialInstance 关联的所有 StaticMesh 的 UV bbox（共用包围盒取并集）
  2. 从 UE 导出原始贴图为 TGA
  3. 用 Pillow 裁切贴图到 UV bbox 区域（尺寸对齐4的倍数）
  4. 用 UE Python API 修改所有 SM 的 UV（线性重映射到 0~1）
  5. 将裁切后的 TGA 重新导入 UE，替换原贴图资产

依赖：
  - UE Python (unreal module) — 由 ArtClaw run_ue_python 注入
  - Pillow — 需在 UE 外 Python 环境中安装 (pip install Pillow)
  - artclaw_sdk — ArtClaw 统一 SDK
"""

import artclaw_sdk as sdk
import json
import math
import os
import subprocess
import sys
import tempfile


# ─── 公共工具函数 ────────────────────────────────────────────────────────────

def _align4(n: int) -> int:
    """Round up to nearest multiple of 4."""
    return math.ceil(n / 4) * 4


def _best_size(exact_px: int, max_waste: float = 0.20) -> int:
    """
    优先选最小的 2^n 尺寸，条件：浪费率 <= max_waste（默认20%）。
    浪费率 = (2^n - exact_px) / 2^n
    若最小 2^n 浪费超过阈值，fallback 到 align4。

    例：exact=376 → 512 浪费(512-376)/512=26.6% > 20% → fallback align4=376
        exact=330 → 512 浪费(512-330)/512=35.5% > 20% → fallback align4=332
        exact=1496 → 2048 浪费(2048-1496)/2048=27% > 20% → fallback align4=1496
        exact=1800 → 2048 浪费(2048-1800)/2048=12.1% <= 20% → 用2048
    """
    if exact_px <= 0:
        return 4
    # 找满足条件的最小 2^n
    p = 1
    while p < exact_px:
        p <<= 1
    waste = (p - exact_px) / p
    if waste <= max_waste:
        return p
    # fallback: align4
    return _align4(exact_px)


def _resolve_export_dir(export_dir: str, mat_name: str, ue_project_dir: str) -> str:
    if export_dir:
        return export_dir
    return _os.path.join(ue_project_dir, "Saved", "UVOptimize", mat_name)


# ─── Step 1: 分析 UV bbox（在 UE Python 中运行）─────────────────────────────

UE_ANALYZE_CODE = """
import unreal, json

mat_path = {mat_path!r}
tex_param_names_filter = {tex_param_names_filter!r}  # [] means auto
uv_channel = {uv_channel}

ar = unreal.AssetRegistryHelpers.get_asset_registry()
mel = unreal.MaterialEditingLibrary

mat_inst = unreal.load_asset(mat_path)
if not mat_inst:
    result = {{"error": f"Cannot load asset: {{mat_path}}"}}
else:
    parent = mat_inst.parent

    # 找出要优化的贴图参数及其贴图资产路径
    tex_names_all = mel.get_texture_parameter_names(parent) if parent else []
    tex_targets = {{}}  # param_name -> ue_asset_path

    for name in tex_names_all:
        name_str = str(name)
        if tex_param_names_filter and name_str not in tex_param_names_filter:
            continue
        val = mel.get_material_instance_texture_parameter_value(mat_inst, name)
        if not val:
            continue
        tex_path = val.get_path_name().split(".")[0]  # strip outer name
        # 跳过默认贴图（1x1）
        try:
            tw = val.blueprint_get_size_x()
            th = val.blueprint_get_size_y()
        except:
            tw, th = 0, 0
        if tw <= 1 and th <= 1:
            continue
        tex_targets[name_str] = {{
            "ue_path": tex_path,
            "size": [tw, th],
            "srgb": val.srgb,
            "compression": str(val.compression_settings),
        }}

    # 找所有直接引用该 MI 的 StaticMesh（通过 referencers）
    dep_opt = unreal.AssetRegistryDependencyOptions()
    referencers = ar.get_referencers(unreal.Name(mat_path), dep_opt)
    mesh_paths = []
    for ref in referencers:
        for ad in ar.get_assets_by_package_name(ref):
            if str(ad.asset_class_path.asset_name) == "StaticMesh":
                mesh_paths.append(str(ad.package_name))

    # 遍历所有 SM，收集 UV
    global_u_min, global_u_max = float("inf"), float("-inf")
    global_v_min, global_v_max = float("inf"), float("-inf")
    mesh_reports = []

    for mesh_path in mesh_paths:
        mesh = unreal.load_asset(mesh_path)
        if not mesh:
            continue
        mesh_desc = mesh.get_static_mesh_description(0)
        if not mesh_desc:
            continue
        vi_count = mesh_desc.get_vertex_instance_count()
        all_u, all_v = [], []
        for i in range(vi_count):
            vi = unreal.VertexInstanceID(i)
            try:
                uv = mesh_desc.get_vertex_instance_uv(vi, uv_channel)
                all_u.append(uv.x)
                all_v.append(uv.y)
            except:
                pass
        if all_u:
            u0, u1 = min(all_u), max(all_u)
            v0, v1 = min(all_v), max(all_v)
            global_u_min = min(global_u_min, u0)
            global_u_max = max(global_u_max, u1)
            global_v_min = min(global_v_min, v0)
            global_v_max = max(global_v_max, v1)
            mesh_reports.append({{"name": mesh.get_name(), "path": mesh_path,
                                  "vi": vi_count, "u": [u0, u1], "v": [v0, v1]}})

    proj_dir = unreal.SystemLibrary.get_project_directory()
    result = {{
        "mat_name": mat_inst.get_name(),
        "proj_dir": proj_dir,
        "tex_targets": tex_targets,
        "mesh_paths": mesh_paths,
        "mesh_reports": mesh_reports,
        "uv_bbox": {{
            "u_min": global_u_min, "u_max": global_u_max,
            "v_min": global_v_min, "v_max": global_v_max,
        }},
        "utilization_pct": round(
            (global_u_max - global_u_min) * (global_v_max - global_v_min) * 100, 2
        ) if mesh_reports else 0,
    }}
"""

# ─── Step 2: 导出贴图 TGA（在 UE Python 中运行）─────────────────────────────

UE_EXPORT_CODE = """
import unreal
import os as _os

export_jobs = {export_jobs!r}  # list of (ue_path, out_file)
_os.makedirs({export_dir!r}, exist_ok=True)

task_list = []
for ue_path, out_file in export_jobs:
    tex = unreal.load_asset(ue_path)
    if not tex:
        print(f"[WARN] Cannot load: {{ue_path}}")
        continue
    task = unreal.AssetExportTask()
    task.object = tex
    task.filename = out_file
    task.selected = False
    task.replace_identical = True
    task.prompt = False
    task.automated = True
    task.exporter = unreal.TextureExporterTGA()
    task_list.append(task)

if task_list:
    unreal.Exporter.run_asset_export_tasks(task_list)
    result = {{"exported": len(task_list)}}
else:
    result = {{"exported": 0, "warn": "No textures exported"}}
"""

# ─── Step 3: 裁切贴图（外部 Python + Pillow）────────────────────────────────

def _crop_textures(crop_jobs: list, uv_bbox: dict, padding_px: int) -> dict:
    """
    crop_jobs: list of { "label": str, "in_file": str, "out_file": str,
                         "orig_size": [w, h] }
    Returns: { label: { "out_file", "new_size", "crop_rect" } }
    """
    try:
        from PIL import Image
    except ImportError:
        # 尝试自动安装（UE 内置 Python 通常已自带 Pillow 12.x）
        import subprocess
        sdk.log.info("[Crop] Pillow not found, attempting auto-install...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "--quiet"])
            from PIL import Image
            sdk.log.info("[Crop] Pillow installed successfully")
        except Exception as e:
            raise RuntimeError(
                f"Pillow not available and auto-install failed: {e}. "
                "Please run: pip install Pillow"
            )

    report = {}
    for job in crop_jobs:
        label = job["label"]
        in_file = job["in_file"]
        out_file = job["out_file"]

        if not _os.path.exists(in_file):
            report[label] = {"error": f"File not found: {in_file}"}
            continue

        img = Image.open(in_file)
        w, h = img.size

        # UV → pixel (clamp v to [0,1])
        u_min = max(0.0, uv_bbox["u_min"])
        u_max = min(1.0, uv_bbox["u_max"])
        v_min = max(0.0, uv_bbox["v_min"])
        v_max = min(1.0, uv_bbox["v_max"])

        left  = max(0, int(u_min * w) - padding_px)
        right = min(w, math.ceil(u_max * w) + padding_px)
        upper = max(0, int(v_min * h) - padding_px)
        lower = min(h, math.ceil(v_max * h) + padding_px)

        crop_w = right - left
        crop_h = lower - upper
        new_w = _best_size(crop_w)
        new_h = _best_size(crop_h)

        cropped = img.crop((left, upper, right, lower))
        out_img = cropped.resize((new_w, new_h), Image.LANCZOS)

        _os.makedirs(_os.path.dirname(out_file), exist_ok=True)
        out_img.save(out_file, format="TGA")

        report[label] = {
            "out_file": out_file,
            "crop_rect": [left, upper, right, lower],
            "new_size": [new_w, new_h],
            "orig_size": [w, h],
            "saved_pct": round((1 - (new_w * new_h) / (w * h)) * 100, 1),
        }
        sdk.log.info(
            f"[Crop] {label}: {w}×{h} → {new_w}×{new_h} "
            f"(节省 {report[label]['saved_pct']}%)"
        )

    return report


# ─── Step 4: 重映射 UV — FBX 导出 → Python 修改 → 重新导入 ─────────────────
# 不使用 build_from_static_mesh_descriptions，避免引入额外 UV channel 或丢失 LOD。
# 流程：UE 导出 FBX → fbx-sdk / binary patch 修改 UV → UE 导回

# FBX SDK 不可用时的 fallback（仅 LOD0，已知限制）
UE_REMAP_UV_FALLBACK_CODE = """
import unreal

# ⚠️  get_vertex_instance_uv 只操作固定 channel，绝对不要用 range(N) 枚举 channel，会 crash
mesh_paths = {mesh_paths!r}
uv_bbox    = {uv_bbox!r}
uv_channel = {uv_channel}

u_min = uv_bbox["u_min"]; u_max = uv_bbox["u_max"]
v_min = uv_bbox["v_min"]; v_max = uv_bbox["v_max"]
u_span = u_max - u_min
v_span = v_max - v_min

remap_results = []
for mesh_path in mesh_paths:
    mesh = unreal.load_asset(mesh_path)
    if not mesh:
        remap_results.append({{"path": mesh_path, "error": "Cannot load"}})
        continue
    mesh_desc = mesh.get_static_mesh_description(0)
    if not mesh_desc:
        remap_results.append({{"path": mesh_path, "error": "No mesh description"}})
        continue
    vi_count = mesh_desc.get_vertex_instance_count()
    changed = 0
    # 临时关闭 generate_lightmap_u_vs，防止 build 后多出额外 UV channel
    smes = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    orig_build = smes.get_lod_build_settings(mesh, 0)
    orig_gen_lm = orig_build.generate_lightmap_u_vs
    if orig_gen_lm:
        orig_build.generate_lightmap_u_vs = False
        smes.set_lod_build_settings(mesh, 0, orig_build)
    with unreal.ScopedEditorTransaction("UV Remap - " + mesh_path.split("/")[-1]):
        for i in range(vi_count):
            vi = unreal.VertexInstanceID(i)
            uv = mesh_desc.get_vertex_instance_uv(vi, uv_channel)
            new_u = (uv.x - u_min) / u_span if u_span > 0 else 0.0
            new_v = (uv.y - v_min) / v_span if v_span > 0 else 0.0
            mesh_desc.set_vertex_instance_uv(vi, unreal.Vector2D(new_u, new_v), uv_channel)
            changed += 1
        mesh.build_from_static_mesh_descriptions([mesh_desc])
    # 恢复原始 build settings
    if orig_gen_lm:
        orig_build.generate_lightmap_u_vs = True
        smes.set_lod_build_settings(mesh, 0, orig_build)
    unreal.EditorAssetLibrary.save_asset(mesh_path)
    remap_results.append({{"path": mesh_path.split("/")[-1], "vi_remapped": changed, "orig_gen_lm_restored": orig_gen_lm}})

result = {{"remap_results": remap_results}}
"""

UE_EXPORT_FBX_CODE = """
import unreal
import os as _os

mesh_paths  = {mesh_paths!r}
fbx_out_dir = {fbx_out_dir!r}
_os.makedirs(fbx_out_dir, exist_ok=True)

export_results = []
for mesh_path in mesh_paths:
    asset_name = mesh_path.split("/")[-1]
    out_file   = _os.path.join(fbx_out_dir, f"{{asset_name}}.fbx")
    mesh = unreal.load_asset(mesh_path)
    if not mesh:
        export_results.append({{"path": mesh_path, "error": "Cannot load"}})
        continue
    fbx_opt = unreal.FbxExportOption()
    fbx_opt.fbx_export_compatibility = unreal.FbxExportCompatibility.FBX_2013
    fbx_opt.level_of_detail = False
    fbx_opt.collision = False
    task = unreal.AssetExportTask()
    task.object   = mesh
    task.filename = out_file
    task.replace_identical = True
    task.prompt   = False
    task.automated = True
    task.options  = fbx_opt
    task.exporter = unreal.StaticMeshExporterFBX()
    unreal.Exporter.run_asset_export_tasks([task])
    ok = _os.path.exists(out_file)
    export_results.append({{"path": mesh_path, "fbx": out_file, "ok": ok}})

result = {{"export_results": export_results}}
"""

UE_IMPORT_FBX_CODE = """
import unreal
import os as _os

import_jobs = {import_jobs!r}
# list of {{ "fbx_file": str, "mesh_ue_path": str }}

import_results = []
for job in import_jobs:
    fbx_file    = job["fbx_file"]
    mesh_path   = job["mesh_ue_path"]
    pkg_path    = "/".join(mesh_path.split("/")[:-1])
    asset_name  = mesh_path.split("/")[-1]

    if not _os.path.exists(fbx_file):
        import_results.append({{"path": mesh_path, "error": f"FBX not found: {{fbx_file}}"}})
        continue

    task = unreal.AssetImportTask()
    task.filename          = fbx_file
    task.destination_path  = pkg_path
    task.destination_name  = asset_name
    task.replace_existing  = True
    task.automated         = True
    task.save              = True

    opts = unreal.FbxImportUI()
    opts.import_mesh              = True
    opts.import_textures          = False
    opts.import_materials         = False
    opts.import_as_skeletal       = False
    opts.static_mesh_import_data.combine_meshes = True
    opts.static_mesh_import_data.generate_lightmap_u_vs = False
    opts.static_mesh_import_data.auto_generate_collision = False
    task.options = opts

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    unreal.EditorAssetLibrary.save_asset(mesh_path)
    import_results.append({{"path": mesh_path, "ok": True}})

result = {{"import_results": import_results}}
"""

# ─── Step 4b: 用 Python 修改 FBX 的 UV（外部 Python，不依赖 UE）──────────────

def _remap_uv_in_fbx(fbx_jobs: list, uv_channel: int) -> dict:
    """
    用 FBX SDK 修改 FBX 文件中所有 Mesh 的指定 UV channel，线性重映射到 [0,1]。
    bbox 从所有输入 FBX 文件中自动扫描取全局并集（FBX 坐标系），无需外部传入。

    fbx_jobs: list of { "in_fbx": str, "out_fbx": str, "mesh_name": str }
    """
    try:
        import fbx as fbxsdk
    except ImportError:
        import shutil
        report = {}
        for job in fbx_jobs:
            label = job.get("mesh_name", _os.path.basename(job["in_fbx"]))
            shutil.copy2(job["in_fbx"], job["out_fbx"])
            report[label] = {"warning": "fbx SDK not available, copied without UV remap"}
        return report

    # Step 1: 扫描所有 FBX 取全局 UV bbox（FBX 坐标系）
    g_u_min=9999.0; g_u_max=-9999.0
    g_v_min=9999.0; g_v_max=-9999.0

    for job in fbx_jobs:
        in_fbx = job["in_fbx"]
        if not _os.path.exists(in_fbx):
            continue
        manager = fbxsdk.FbxManager.Create()
        ios = fbxsdk.FbxIOSettings.Create(manager, fbxsdk.IOSROOT)
        manager.SetIOSettings(ios)
        importer = fbxsdk.FbxImporter.Create(manager, "")
        importer.Initialize(in_fbx, -1, manager.GetIOSettings())
        scene = fbxsdk.FbxScene.Create(manager, "scene")
        importer.Import(scene)
        importer.Destroy()
        stack = [scene.GetRootNode()]
        while stack:
            node = stack.pop()
            attr = node.GetNodeAttribute()
            if attr and attr.GetAttributeType() == fbxsdk.FbxNodeAttribute.eMesh:
                m = node.GetMesh()
                if uv_channel < m.GetElementUVCount():
                    arr = m.GetElementUV(uv_channel).GetDirectArray()
                    for j in range(arr.GetCount()):
                        pt = arr.GetAt(j)
                        if pt[0] < g_u_min: g_u_min = pt[0]
                        if pt[0] > g_u_max: g_u_max = pt[0]
                        if pt[1] < g_v_min: g_v_min = pt[1]
                        if pt[1] > g_v_max: g_v_max = pt[1]
            for i in range(node.GetChildCount()):
                stack.append(node.GetChild(i))
        manager.Destroy()

    u_span = g_u_max - g_u_min
    v_span = g_v_max - g_v_min
    sdk.log.info(
        f"[FBX UV Remap] Global bbox (FBX space): "
        f"U[{g_u_min:.4f}~{g_u_max:.4f}] V[{g_v_min:.4f}~{g_v_max:.4f}]"
    )

    # Step 2: 用全局 bbox 重映射每个 FBX 的 UV
    report = {}
    for job in fbx_jobs:
        in_fbx  = job["in_fbx"]
        out_fbx = job["out_fbx"]
        label   = job.get("mesh_name", _os.path.basename(in_fbx))

        if not _os.path.exists(in_fbx):
            report[label] = {"error": f"FBX not found: {in_fbx}"}
            continue

        manager = fbxsdk.FbxManager.Create()
        ios = fbxsdk.FbxIOSettings.Create(manager, fbxsdk.IOSROOT)
        manager.SetIOSettings(ios)
        importer = fbxsdk.FbxImporter.Create(manager, "")
        if not importer.Initialize(in_fbx, -1, manager.GetIOSettings()):
            report[label] = {"error": "FBX import init failed"}
            manager.Destroy()
            continue
        scene = fbxsdk.FbxScene.Create(manager, "scene")
        importer.Import(scene)
        importer.Destroy()

        changed = 0
        stack = [scene.GetRootNode()]
        while stack:
            node = stack.pop()
            attr = node.GetNodeAttribute()
            if attr and attr.GetAttributeType() == fbxsdk.FbxNodeAttribute.eMesh:
                m = node.GetMesh()
                if uv_channel < m.GetElementUVCount():
                    arr = m.GetElementUV(uv_channel).GetDirectArray()
                    for j in range(arr.GetCount()):
                        pt = arr.GetAt(j)
                        new_u = (pt[0] - g_u_min) / u_span if u_span > 0 else 0.0
                        new_v = (pt[1] - g_v_min) / v_span if v_span > 0 else 0.0
                        arr.SetAt(j, fbxsdk.FbxVector2(new_u, new_v))
                        changed += 1
            for i in range(node.GetChildCount()):
                stack.append(node.GetChild(i))

        exporter = fbxsdk.FbxExporter.Create(manager, "")
        exporter.Initialize(out_fbx, -1, manager.GetIOSettings())
        exporter.Export(scene)
        exporter.Destroy()
        manager.Destroy()

        report[label] = {"out_fbx": out_fbx, "changed": changed}
        sdk.log.info(f"[FBX UV Remap] {label}: {changed} UV points remapped")

    return report


UE_IMPORT_CODE = """
import unreal
import os as _os

import_jobs = {import_jobs!r}
# list of {{ "tga_file": str, "ue_dest_path": str }}
# 不传 srgb/compression，直接从原始资产读取，保持不变

import_results = []
for job in import_jobs:
    tga_file = job["tga_file"]
    ue_path  = job["ue_dest_path"]

    if not _os.path.exists(tga_file):
        import_results.append({{"ue_path": ue_path, "error": f"TGA not found: {{tga_file}}"}})
        continue

    # 导入前先读取原始资产的所有设置，保证导入后完全还原
    orig = unreal.load_asset(ue_path)
    if orig:
        orig_srgb        = orig.srgb
        orig_compression = orig.compression_settings
        orig_lod_group   = orig.lod_group
        orig_power_of_2  = orig.power_of_two_mode if hasattr(orig, 'power_of_two_mode') else None
    else:
        orig_srgb        = False
        orig_compression = unreal.TextureCompressionSettings.TC_DEFAULT
        orig_lod_group   = unreal.TextureGroup.TEXTUREGROUP_WORLD
        orig_power_of_2  = None

    pkg_path   = "/".join(ue_path.split("/")[:-1])
    asset_name = ue_path.split("/")[-1]

    task = unreal.AssetImportTask()
    task.filename         = tga_file
    task.destination_path = pkg_path
    task.destination_name = asset_name
    task.replace_existing = True
    task.automated        = True
    task.save             = False   # 设置完成后再保存

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    imported = unreal.load_asset(ue_path)
    if imported:
        # 完全还原原始设置
        imported.srgb                = orig_srgb
        imported.compression_settings = orig_compression
        imported.lod_group           = orig_lod_group
        # 非 2^n 尺寸导入后会自动变 NoMips，强制恢复 FromTextureGroup
        imported.mip_gen_settings    = unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP
        if orig_power_of_2 is not None:
            imported.power_of_two_mode = orig_power_of_2
        saved = unreal.EditorAssetLibrary.save_asset(ue_path)
        import_results.append({{
            "ue_path":     ue_path,
            "success":     True,
            "saved":       saved,
            "manual_save_needed": not saved,  # 项目工具拦截时需要手动在 CB 里保存
            "srgb":        imported.srgb,
            "compression": str(imported.compression_settings),
            "mip_gen":     str(imported.mip_gen_settings),
            "size":        [imported.blueprint_get_size_x(), imported.blueprint_get_size_y()],
        }})
    else:
        import_results.append({{"ue_path": ue_path, "error": "Import succeeded but asset not found"}})

result = {{"import_results": import_results}}
"""


# ─── 主入口 ──────────────────────────────────────────────────────────────────

def uv_texture_optimize(raw_params):
    """UV & 贴图利用率优化工具主入口"""

    manifest_inputs = [
        {"id": "material_instance_path", "type": "string", "required": True},
        {"id": "texture_param_names",    "type": "string", "default": ""},
        {"id": "uv_channel",             "type": "number", "default": 0},
        {"id": "padding_px",             "type": "number", "default": 4},
        {"id": "export_dir",             "type": "string", "default": ""},
        {"id": "dry_run",                "type": "boolean","default": False},
    ]
    params = sdk.parse_params(manifest_inputs, raw_params)

    mat_path          = params["material_instance_path"].strip()
    tex_param_filter  = [s.strip() for s in params["texture_param_names"].split(",") if s.strip()]
    uv_channel        = int(params["uv_channel"])
    padding_px        = int(params["padding_px"])
    export_dir_param  = params["export_dir"].strip()
    dry_run           = bool(params["dry_run"])

    if not mat_path:
        return sdk.result.fail("MISSING_INPUT", "请填写材质实例路径")

    context = sdk.get_context()
    if context.get("dcc") != "ue57":
        return sdk.result.fail("WRONG_DCC", f"此工具仅支持 UE5，当前 DCC: {context.get('dcc')}")

    # ── Step 1: 分析 UV bbox ─────────────────────────────────────────────────
    sdk.log.info("Step 1: 分析 UV 分布...")

    analyze_code = UE_ANALYZE_CODE.format(
        mat_path=mat_path,
        tex_param_names_filter=tex_param_filter,
        uv_channel=uv_channel,
    )
    analysis = sdk.run_ue_python(analyze_code)
    if "error" in analysis:
        return sdk.result.fail("ANALYZE_FAILED", analysis["error"])

    mat_name    = analysis["mat_name"]
    proj_dir    = analysis["proj_dir"]
    tex_targets = analysis["tex_targets"]   # {param_name: {ue_path, size, srgb, compression}}
    mesh_paths  = analysis["mesh_paths"]
    uv_bbox     = analysis["uv_bbox"]
    util_pct    = analysis["utilization_pct"]

    if not mesh_paths:
        return sdk.result.fail("NO_MESHES", "未找到引用该材质实例的 StaticMesh 资产")
    if not tex_targets:
        return sdk.result.fail("NO_TEXTURES", "未检测到可优化的贴图参数（贴图尺寸均为1×1或未赋值）")

    sdk.log.info(
        f"  找到 {len(mesh_paths)} 个 SM，{len(tex_targets)} 张贴图\n"
        f"  UV bbox: U[{uv_bbox['u_min']:.4f}~{uv_bbox['u_max']:.4f}] "
        f"V[{uv_bbox['v_min']:.4f}~{uv_bbox['v_max']:.4f}] "
        f"利用率 {util_pct}%"
    )

    if util_pct > 85:
        sdk.log.info("UV 利用率已较高（>85%），无需优化。")
        return sdk.result.success(
            data={"utilization_pct": util_pct, "status": "already_optimal"},
            message=f"UV 利用率已达 {util_pct}%，无需优化"
        )

    export_dir = _resolve_export_dir(export_dir_param, mat_name, proj_dir)
    orig_dir   = _os.path.join(export_dir, "original")
    crop_dir   = _os.path.join(export_dir, "cropped")

    if dry_run:
        # 预演模式：只输出分析报告
        lines = [
            f"[DRY RUN] UV 利用率优化报告",
            f"材质实例: {mat_path}",
            f"关联 SM 数: {len(mesh_paths)}",
            f"UV bbox: U[{uv_bbox['u_min']:.4f}~{uv_bbox['u_max']:.4f}] "
            f"V[{uv_bbox['v_min']:.4f}~{uv_bbox['v_max']:.4f}]",
            f"当前利用率: {util_pct}%（优化后接近 100%）",
            "",
            "将优化的贴图：",
        ]
        for pname, tinfo in tex_targets.items():
            w, h = tinfo["size"]
            u_span = uv_bbox["u_max"] - uv_bbox["u_min"]
            v_span = min(1.0, uv_bbox["v_max"]) - max(0.0, uv_bbox["v_min"])
            new_w = _best_size(math.ceil(u_span * w) + padding_px * 2)
            new_h = _best_size(math.ceil(v_span * h) + padding_px * 2)
            saved = round((1 - new_w * new_h / (w * h)) * 100, 1)
            lines.append(f"  [{pname}] {tinfo['ue_path']}")
            lines.append(f"    {w}×{h} → {new_w}×{new_h}  节省 {saved}%")
        return sdk.result.success(data={"report": "\n".join(lines)}, message="\n".join(lines))

    # ── Step 2: 导出 TGA ──────────────────────────────────────────────────────
    sdk.log.info("Step 2: 导出原始贴图 TGA...")
    _os.makedirs(orig_dir, exist_ok=True)

    export_jobs = []
    for pname, tinfo in tex_targets.items():
        ue_path    = tinfo["ue_path"]
        asset_name = ue_path.split("/")[-1]
        out_file   = _os.path.join(orig_dir, f"{asset_name}.tga")
        export_jobs.append((ue_path, out_file))
        tinfo["orig_tga"] = out_file

    export_code = UE_EXPORT_CODE.format(
        export_jobs=export_jobs,
        export_dir=orig_dir,
    )
    export_result = sdk.run_ue_python(export_code)
    sdk.log.info(f"  导出完成: {export_result.get('exported', 0)} 张")

    # ── Step 3: 裁切贴图 ──────────────────────────────────────────────────────
    sdk.log.info("Step 3: 裁切贴图...")
    crop_jobs = []
    for pname, tinfo in tex_targets.items():
        asset_name = tinfo["ue_path"].split("/")[-1]
        out_file   = _os.path.join(crop_dir, f"{asset_name}_cropped.tga")
        crop_jobs.append({
            "label":    pname,
            "in_file":  tinfo["orig_tga"],
            "out_file": out_file,
            "orig_size": tinfo["size"],
        })
        tinfo["cropped_tga"] = out_file

    crop_report = _crop_textures(crop_jobs, uv_bbox, padding_px)
    for pname, cr in crop_report.items():
        if "error" in cr:
            sdk.log.error(f"  [{pname}] 裁切失败: {cr['error']}")
        else:
            sdk.log.info(
                f"  [{pname}] {cr['orig_size'][0]}×{cr['orig_size'][1]} → "
                f"{cr['new_size'][0]}×{cr['new_size'][1]} "
                f"(节省 {cr['saved_pct']}%)"
            )

    # ── Step 4: FBX 导出 → 修改 UV → 重新导入 ───────────────────────────────
    sdk.log.info("Step 4: 导出 FBX，重映射 UV，重新导入...")
    fbx_dir      = _os.path.join(export_dir, "fbx_original")
    fbx_remap_dir = _os.path.join(export_dir, "fbx_remapped")
    _os.makedirs(fbx_dir, exist_ok=True)
    _os.makedirs(fbx_remap_dir, exist_ok=True)

    # 4a: UE 导出 FBX
    export_fbx_code = UE_EXPORT_FBX_CODE.format(
        mesh_paths=mesh_paths,
        fbx_out_dir=fbx_dir,
    )
    fbx_export_result = sdk.run_ue_python(export_fbx_code)
    fbx_export_ok = [r for r in fbx_export_result.get("export_results", []) if r.get("ok")]
    sdk.log.info(f"  FBX 导出: {len(fbx_export_ok)}/{len(mesh_paths)} 成功")

    # 4b: Python 修改 UV（FBX SDK）
    fbx_jobs = []
    for r in fbx_export_result.get("export_results", []):
        if not r.get("ok"):
            continue
        asset_name = r["path"].split("/")[-1]
        fbx_jobs.append({
            "in_fbx":    r["fbx"],
            "out_fbx":   _os.path.join(fbx_remap_dir, f"{asset_name}.fbx"),
            "mesh_name": asset_name,
        })

    fbx_remap_report = _remap_uv_in_fbx(fbx_jobs, uv_channel)

    # 检查是否有 fallback（FBX SDK 不可用）
    needs_post_import_remap = any("warning" in v for v in fbx_remap_report.values())

    # 4c: UE 重新导入修改后的 FBX
    import_fbx_jobs = []
    for job in fbx_jobs:
        label = job["mesh_name"]
        rr = fbx_remap_report.get(label, {})
        if "error" in rr:
            sdk.log.error(f"  跳过 {label}（FBX UV 修改失败: {rr['error']}）")
            continue
        # 无论是否真的修改了 UV，都重导入（fallback 情况下也需要）
        ue_path = next((r["path"] for r in fbx_export_result.get("export_results", [])
                        if r["path"].split("/")[-1] == label), None)
        if ue_path:
            import_fbx_jobs.append({
                "fbx_file":    job["out_fbx"],
                "mesh_ue_path": ue_path,
            })

    import_fbx_code = UE_IMPORT_FBX_CODE.format(import_jobs=import_fbx_jobs)
    fbx_import_result = sdk.run_ue_python(import_fbx_code)
    for r in fbx_import_result.get("import_results", []):
        if r.get("ok"):
            sdk.log.info(f"  ✅ FBX 重导入: {r['path']}")
        else:
            sdk.log.error(f"  ❌ FBX 重导入失败 {r['path']}: {r.get('error')}")

    # 4d: 若 FBX SDK 不可用，fallback 到 StaticMeshDescription UV remap（已知限制：只改 LOD0）
    if needs_post_import_remap:
        sdk.log.info("  FBX SDK 不可用，使用 StaticMeshDescription 补充 UV 重映射（仅 LOD0）...")
        remap_code = UE_REMAP_UV_FALLBACK_CODE.format(
            mesh_paths=mesh_paths,
            uv_bbox=uv_bbox,
            uv_channel=uv_channel,
        )
        remap_result = sdk.run_ue_python(remap_code)
        for r in remap_result.get("remap_results", []):
            if "error" in r:
                sdk.log.error(f"  UV remap 失败 {r['path']}: {r['error']}")
            else:
                sdk.log.info(f"  UV remapped: {r['path']} ({r['vi_remapped']} vertices)")

    # ── Step 5: 导入裁切后贴图 ───────────────────────────────────────────────
    sdk.log.info("Step 5: 导入新贴图替换原资产...")
    import_jobs = []
    for pname, tinfo in tex_targets.items():
        cr = crop_report.get(pname, {})
        if "error" in cr or "out_file" not in cr:
            sdk.log.error(f"  跳过 [{pname}]（裁切失败）")
            continue
        # 只传 tga 路径和目标 UE 路径，sRGB/压缩/lod_group 从原始资产自动读取保持不变
        import_jobs.append({
            "tga_file":     cr["out_file"],
            "ue_dest_path": tinfo["ue_path"],
        })

    import_code = UE_IMPORT_CODE.format(import_jobs=import_jobs)
    import_result = sdk.run_ue_python(import_code)
    for r in import_result.get("import_results", []):
        if r.get("success"):
            if r.get("manual_save_needed"):
                sdk.log.warning(
                    f"  ⚠️  {r['ue_path'].split('/')[-1]} 导入成功但未能自动保存（项目工具拦截）"
                    f"，请在 Content Browser 手动右键 → Save"
                )
            else:
                sdk.log.info(f"  ✅ 导入成功: {r['ue_path'].split('/')[-1]}")
        else:
            sdk.log.error(f"  ❌ 导入失败 {r['ue_path']}: {r.get('error')}")

    # ── 汇总报告 ──────────────────────────────────────────────────────────────
    total_saved_px = sum(
        (cr["orig_size"][0] * cr["orig_size"][1] - cr["new_size"][0] * cr["new_size"][1])
        for cr in crop_report.values() if "new_size" in cr
    )

    report_lines = [
        f"✅ UV & 贴图优化完成",
        f"材质实例: {mat_path}",
        f"处理 SM 数: {len(mesh_paths)}",
        f"UV 利用率: {util_pct}% → ~100%",
        "",
        "贴图节省明细：",
    ]
    for pname, cr in crop_report.items():
        if "new_size" in cr:
            report_lines.append(
                f"  [{pname}] {cr['orig_size'][0]}×{cr['orig_size'][1]} "
                f"→ {cr['new_size'][0]}×{cr['new_size'][1]}  "
                f"节省 {cr['saved_pct']}%"
            )

    # 收集需要手动保存的资产
    manual_save_list = [
        r["ue_path"].split("/")[-1]
        for r in import_result.get("import_results", [])
        if r.get("manual_save_needed")
    ]
    if manual_save_list:
        report_lines.append("")
        report_lines.append("⚠️  以下贴图需在 Content Browser 手动保存（右键 → Save）：")
        for name in manual_save_list:
            report_lines.append(f"  - {name}")

    return sdk.result.success(
        data={
            "mesh_count": len(mesh_paths),
            "texture_count": len(tex_targets),
            "uv_utilization_before": util_pct,
            "total_saved_pixels": total_saved_px,
            "crop_report": crop_report,
            "export_dir": export_dir,
        },
        message="\n".join(report_lines)
    )
