"""
UV & 贴图利用率优化工具
纯 UE Python 实现，直接注入 DCC 执行。
分析材质实例关联的所有 SM 的 UV bbox，裁切贴图到实际使用区域，重映射 UV。
"""
# ── SDK 头 ──
import os, json
import artclaw_sdk as sdk

def _load_manifest() -> dict:
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)
# ── SDK 头结束 ──

import unreal
import math


def uv_texture_optimize(**kwargs):
    """入口函数。kwargs 由 Tool Manager 传入（keyword arguments）。"""
    manifest = _load_manifest()
    parsed = sdk.params.parse_params(manifest.get("inputs", []), kwargs)
    
    # ===== 内联辅助函数 =====
    def _best_size(n):
        """2^n 优先，浪费超过 20% 则退到 4 的倍数。最小 4。"""
        if n <= 4:
            return 4
        p = 1
        while p < n:
            p <<= 1
        if (p - n) / p <= 0.20:
            return p
        return math.ceil(n / 4) * 4

    def _analyze(mat_path, tex_param_filter, uv_channel):
        """Step 1: 分析材质实例关联的 SM 和 UV bbox。"""
        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        # 规范化路径: 去掉 ".ObjectName" 后缀 (如 /Game/.../MI_Foo.MI_Foo → /Game/.../MI_Foo)
        if "." in mat_path.split("/")[-1]:
            mat_path = mat_path.split(".")[0]

        mat_inst = unreal.load_asset(mat_path)
        if not mat_inst:
            return None, f"Cannot load asset: {mat_path}"

        parent = mat_inst.parent
        # 只获取材质实例实际覆盖的贴图参数（不处理 parent 默认贴图）
        tex_targets = {}
        if hasattr(mat_inst, 'texture_parameter_values'):
            for tpv in mat_inst.texture_parameter_values:
                try:
                    name_str = str(tpv.parameter_info.name)
                except Exception:
                    continue
                if tex_param_filter and name_str not in tex_param_filter:
                    continue
                val = tpv.parameter_value
                if not val:
                    continue
                tex_path = val.get_path_name().split(".")[0]
                try:
                    tw = val.blueprint_get_size_x()
                    th = val.blueprint_get_size_y()
                except Exception:
                    tw, th = 0, 0
                if tw <= 1 and th <= 1:
                    continue
                tex_targets[name_str] = {
                    "ue_path": tex_path, "size": [tw, th],
                    "srgb": val.srgb,
                    "compression": str(val.compression_settings),
                }

        # 找引用此材质的 SM
        dep_opt = unreal.AssetRegistryDependencyOptions()
        referencers = ar.get_referencers(unreal.Name(mat_path), dep_opt)
        mesh_paths = []
        if referencers:
            for ref in referencers:
                for ad in ar.get_assets_by_package_name(ref):
                    if str(ad.asset_class_path.asset_name) == "StaticMesh":
                        mesh_paths.append(str(ad.package_name))

        # 收集 UV bbox
        g_umin, g_umax = float("inf"), float("-inf")
        g_vmin, g_vmax = float("inf"), float("-inf")
        mesh_reports = []

        for mp in mesh_paths:
            mesh = unreal.load_asset(mp)
            if not mesh:
                continue
            md = mesh.get_static_mesh_description(0)
            if not md:
                continue
            vi_count = md.get_vertex_instance_count()
            us, vs = [], []
            for i in range(vi_count):
                vi = unreal.VertexInstanceID(i)
                try:
                    uv = md.get_vertex_instance_uv(vi, uv_channel)
                    us.append(uv.x)
                    vs.append(uv.y)
                except Exception:
                    pass
            if us:
                u0, u1 = min(us), max(us)
                v0, v1 = min(vs), max(vs)
                g_umin = min(g_umin, u0)
                g_umax = max(g_umax, u1)
                g_vmin = min(g_vmin, v0)
                g_vmax = max(g_vmax, v1)
                mesh_reports.append({"name": mesh.get_name(), "path": mp,
                                     "vi": vi_count, "u": [u0, u1], "v": [v0, v1]})

        proj_dir = unreal.SystemLibrary.get_project_directory()
        uv_bbox = {"u_min": g_umin, "u_max": g_umax, "v_min": g_vmin, "v_max": g_vmax}
        util_pct = round((g_umax - g_umin) * (g_vmax - g_vmin) * 100, 2) if mesh_reports else 0

        return {
            "mat_name": mat_inst.get_name(),
            "proj_dir": proj_dir,
            "tex_targets": tex_targets,
            "mesh_paths": mesh_paths,
            "mesh_reports": mesh_reports,
            "uv_bbox": uv_bbox,
            "utilization_pct": util_pct,
        }, None

    def _export_textures(tex_targets, export_dir):
        """Step 2: 导出贴图为 TGA。"""
        os.makedirs(export_dir, exist_ok=True)
        for pname, tinfo in tex_targets.items():
            tex = unreal.load_asset(tinfo["ue_path"])
            if not tex:
                continue
            out_file = os.path.join(export_dir, f"{tinfo['ue_path'].split('/')[-1]}.tga")
            task = unreal.AssetExportTask()
            task.object = tex
            task.filename = out_file
            task.replace_identical = True
            task.prompt = False
            task.automated = True
            unreal.Exporter.run_asset_export_task(task)
            tinfo["orig_tga"] = out_file

    def _crop_textures(tex_targets, uv_bbox, padding_px, crop_dir):
        """Step 3: 裁切贴图（PIL）。
        
        裁切后 resize 到 2^n 尺寸（UE 要求）。
        对法线/混合贴图使用 NEAREST 插值避免破坏方向数据，
        对 BaseColor 使用 LANCZOS 高质量插值。
        """
        try:
            from PIL import Image
        except ImportError:
            return {"error": "PIL (Pillow) not installed. Please install: pip install Pillow"}
        os.makedirs(crop_dir, exist_ok=True)
        report = {}

        u_min = max(0.0, uv_bbox["u_min"])
        u_max = min(1.0, uv_bbox["u_max"])
        v_min = max(0.0, uv_bbox["v_min"])
        v_max = min(1.0, uv_bbox["v_max"])

        for pname, tinfo in tex_targets.items():
            orig_tga = tinfo.get("orig_tga")
            if not orig_tga or not os.path.exists(orig_tga):
                report[pname] = {"error": f"TGA not found: {orig_tga}"}
                continue

            img = Image.open(orig_tga)
            w, h = img.size

            left = max(0, int(u_min * w) - padding_px)
            right = min(w, math.ceil(u_max * w) + padding_px)
            upper = max(0, int(v_min * h) - padding_px)
            lower = min(h, math.ceil(v_max * h) + padding_px)

            cropped = img.crop((left, upper, right, lower))
            crop_w, crop_h = cropped.size

            # resize 到 2^n（UE 贴图尺寸要求）
            new_w = _best_size(crop_w)
            new_h = _best_size(crop_h)

            # sRGB=True 的贴图（BaseColor 等）用 LANCZOS，
            # 非 sRGB 的贴图（Normal/Mix 等）用 NEAREST 避免破坏数据
            is_srgb = tinfo.get("srgb", False)
            resample = Image.LANCZOS if is_srgb else Image.NEAREST
            out_img = cropped.resize((new_w, new_h), resample)

            out_file = os.path.join(crop_dir, f"{tinfo['ue_path'].split('/')[-1]}_cropped.tga")
            out_img.save(out_file, format="TGA")
            tinfo["cropped_tga"] = out_file

            report[pname] = {
                "out_file": out_file,
                "orig_size": [w, h], "new_size": [new_w, new_h],
                "crop_rect": [left, upper, right, lower],
                "saved_pct": round((1 - new_w * new_h / (w * h)) * 100, 1),
            }
        return report

    def _remap_uvs(mesh_paths, uv_bbox, uv_channel):
        """Step 4: 重映射 UV 到 0-1。
        
        使用 C++ MeshUVOpsAPI.remap_mesh_uv 修改 SourceModel MeshDescription，
        通过 CommitMeshDescription + PostEditChange 正确 rebuild RenderData，
        不会产生多余 UV 通道（避免 build_from_static_mesh_descriptions 的 8 UV bug）。
        """
        u_min = uv_bbox["u_min"]
        u_span = uv_bbox["u_max"] - u_min
        v_min = uv_bbox["v_min"]
        v_span = uv_bbox["v_max"] - v_min
        results = []

        offset = unreal.Vector2D(u_min, v_min)
        scale = unreal.Vector2D(1.0 / u_span if u_span > 0 else 1.0,
                                1.0 / v_span if v_span > 0 else 1.0)

        for mp in mesh_paths:
            count = unreal.MeshUVOpsAPI.remap_mesh_uv(mp, uv_channel, offset, scale, 0)
            if count >= 0:
                results.append({"path": mp.split("/")[-1], "vi_remapped": count})
            else:
                results.append({"path": mp.split("/")[-1], "error": "remap failed"})

        return results

    def _reimport_textures(tex_targets, crop_report):
        """Step: 导入裁切后的贴图替换原资产。
        
        ⚠️ 不调用 save_asset — 项目可能有 AssetAuditor 插件，
        save 时会自动触发审计（弹对话框、修改压缩格式等），
        打乱渲染资源状态，导致后续 build mesh crash。
        贴图导入后标记 dirty，让用户手动保存或工具最后统一保存。
        """
        results = []
        for pname, tinfo in tex_targets.items():
            cr = crop_report.get(pname, {})
            if "error" in cr or "out_file" not in cr:
                results.append({"param": pname, "error": "Crop failed"})
                continue

            ue_path = tinfo["ue_path"]
            tga_file = cr["out_file"]

            # 读取原始属性
            orig = unreal.load_asset(ue_path)
            orig_srgb = orig.srgb if orig else False
            orig_compression = orig.compression_settings if orig else unreal.TextureCompressionSettings.TC_DEFAULT

            pkg_path = "/".join(ue_path.split("/")[:-1])
            asset_name = ue_path.split("/")[-1]

            task = unreal.AssetImportTask()
            task.filename = tga_file
            task.destination_path = pkg_path
            task.destination_name = asset_name
            task.replace_existing = True
            task.automated = True
            task.save = False
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

            imported = unreal.load_asset(ue_path)
            if imported:
                imported.srgb = orig_srgb
                imported.compression_settings = orig_compression
                imported.mip_gen_settings = unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP
                # 不 save — 避免触发 AssetAuditor
                results.append({
                    "param": pname, "success": True,
                    "size": [imported.blueprint_get_size_x(), imported.blueprint_get_size_y()],
                })
            else:
                results.append({"param": pname, "error": "Import failed"})

        return results
    
    # ===== 主逻辑 =====
    mat_path = parsed.get("material_instance_path", "").strip()
    tex_filter_str = parsed.get("texture_param_names", "")
    tex_filter = [s.strip() for s in tex_filter_str.split(",") if s.strip()] if tex_filter_str else []
    uv_channel = int(parsed.get("uv_channel", 0))
    padding_px = int(parsed.get("padding_px", 4))
    export_dir_param = parsed.get("export_dir", "").strip()
    dry_run = bool(parsed.get("dry_run", False))

    if not mat_path:
        return sdk.result.fail("NO_INPUT", "请填写材质实例路径")

    # Step 1: 分析
    analysis, err = _analyze(mat_path, tex_filter, uv_channel)
    if err:
        return sdk.result.fail("ANALYSIS_ERROR", err)

    uv_bbox = analysis["uv_bbox"]
    util_pct = analysis["utilization_pct"]
    tex_targets = analysis["tex_targets"]
    mesh_paths = analysis["mesh_paths"]

    if not mesh_paths:
        return sdk.result.fail("NO_MESH", "未找到引用该材质实例的 StaticMesh")
    if not tex_targets:
        return sdk.result.fail("NO_TEXTURE", "未检测到可优化的贴图")
    if util_pct > 85:
        return sdk.result.success(
            data={"utilization_pct": util_pct, "message": "UV 利用率已达 85% 以上，无需优化"},
            message=f"UV 利用率已达 {util_pct}%，无需优化"
        )

    # 导出目录
    proj_dir = analysis["proj_dir"]
    if export_dir_param:
        export_dir = export_dir_param
    else:
        export_dir = os.path.join(proj_dir, "Saved", "UVOptimize", analysis["mat_name"])
    orig_dir = os.path.join(export_dir, "original")
    crop_dir = os.path.join(export_dir, "cropped")

    if dry_run:
        lines = [
            f"[DRY RUN] UV 贴图利用率优化预览",
            f"材质实例: {mat_path}",
            f"关联 SM: {len(mesh_paths)} 个",
            f"UV bbox: U[{uv_bbox['u_min']:.4f}~{uv_bbox['u_max']:.4f}] "
            f"V[{uv_bbox['v_min']:.4f}~{uv_bbox['v_max']:.4f}]",
            f"当前利用率: {util_pct}%",
            "", "待优化贴图:",
        ]
        for pname, tinfo in tex_targets.items():
            w, h = tinfo["size"]
            u_span = uv_bbox["u_max"] - uv_bbox["u_min"]
            v_span = min(1.0, uv_bbox["v_max"]) - max(0.0, uv_bbox["v_min"])
            new_w = math.ceil(u_span * w) + padding_px * 2
            new_h = math.ceil(v_span * h) + padding_px * 2
            saved = round((1 - new_w * new_h / (w * h)) * 100, 1)
            lines.append(f"  [{pname}] {tinfo['ue_path']}")
            lines.append(f"    {w}×{h} → {new_w}×{new_h}  省 {saved}%")
        return sdk.result.success(
            data={"dry_run": True, "report": "\n".join(lines)},
            message="\n".join(lines)
        )

    # Step 2: 导出原始贴图
    _export_textures(tex_targets, orig_dir)

    # Step 3: 裁切贴图（PIL，纯文件操作，不触发 UE）
    crop_report = _crop_textures(tex_targets, uv_bbox, padding_px, crop_dir)

    # Step 4: 重映射 UV + build mesh（先于贴图导入！）
    # ⚠️ 执行顺序至关重要：
    # build_from_static_mesh_descriptions 和 import_asset_tasks 都会释放/重建渲染资源。
    # 如果先 import 贴图再 build mesh，两者释放的渲染资源会冲突导致 UE crash:
    #   "A FRenderResource was deleted without being released first!"
    # 所以必须先完成所有 mesh build，最后再导入贴图。
    remap_results = _remap_uvs(mesh_paths, uv_bbox, uv_channel)

    # Step 5: 导入裁切贴图（mesh build 全部完成后）
    import_results = _reimport_textures(tex_targets, crop_report)

    # Step 6: 统一保存所有修改（贴图 + mesh）
    # 放在最后，避免中途 save 触发 AssetAuditor 插件干扰渲染资源
    saved_assets = []
    for pname, tinfo in tex_targets.items():
        try:
            unreal.EditorAssetLibrary.save_asset(tinfo["ue_path"])
            saved_assets.append(tinfo["ue_path"])
        except Exception:
            pass
    for mp in mesh_paths:
        try:
            unreal.EditorAssetLibrary.save_asset(mp)
            saved_assets.append(mp)
        except Exception:
            pass

    # 汇总
    report_lines = [
        f"✅ UV & 贴图优化完成",
        f"材质实例: {mat_path}",
        f"关联 SM: {len(mesh_paths)} 个",
        f"UV 利用率: {util_pct}% → ~100%",
        "", "贴图节省:",
    ]
    for pname, cr in crop_report.items():
        if "new_size" in cr:
            report_lines.append(
                f"  [{pname}] {cr['orig_size'][0]}×{cr['orig_size'][1]} "
                f"→ {cr['new_size'][0]}×{cr['new_size'][1]}  省 {cr['saved_pct']}%"
            )

    return sdk.result.success(
        data={
            "report": "\n".join(report_lines),
            "mesh_count": len(mesh_paths),
            "texture_count": len(tex_targets),
            "uv_utilization_before": util_pct,
            "crop_report": crop_report,
            "remap_results": remap_results,
            "import_results": import_results,
        },
        message="\n".join(report_lines)
    )


# --- ArtClaw Tool Manager auto-call ---
# 由 Tool Manager _execute_on_dcc 动态注入参数调用，
# 此处仅作 guard，不硬编码参数。
if __name__ == "__main__":
    import json as _json, sys as _sys
    # 支持命令行: python main.py '{"material_instance_path": "..."}'
    if len(_sys.argv) > 1:
        _params = _json.loads(_sys.argv[1])
        _result = uv_texture_optimize(**_params)
        print(_json.dumps(_result, ensure_ascii=False, default=str))
    
    # ===== 内联辅助函数 =====
    def _best_size(n):
        """2^n 优先，浪费超过 20% 则退到 4 的倍数。最小 4。"""
        if n <= 4:
            return 4
        p = 1
        while p < n:
            p <<= 1
        if (p - n) / p <= 0.20:
            return p
        return math.ceil(n / 4) * 4

    def _analyze(mat_path, tex_param_filter, uv_channel):
        """Step 1: 分析材质实例关联的 SM 和 UV bbox。"""
        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        # 规范化路径: 去掉 ".ObjectName" 后缀 (如 /Game/.../MI_Foo.MI_Foo → /Game/.../MI_Foo)
        if "." in mat_path.split("/")[-1]:
            mat_path = mat_path.split(".")[0]

        mat_inst = unreal.load_asset(mat_path)
        if not mat_inst:
            return None, f"Cannot load asset: {mat_path}"

        parent = mat_inst.parent
        # 只获取材质实例实际覆盖的贴图参数（不处理 parent 默认贴图）
        tex_targets = {}
        if hasattr(mat_inst, 'texture_parameter_values'):
            for tpv in mat_inst.texture_parameter_values:
                try:
                    name_str = str(tpv.parameter_info.name)
                except Exception:
                    continue
                if tex_param_filter and name_str not in tex_param_filter:
                    continue
                val = tpv.parameter_value
                if not val:
                    continue
                tex_path = val.get_path_name().split(".")[0]
                try:
                    tw = val.blueprint_get_size_x()
                    th = val.blueprint_get_size_y()
                except Exception:
                    tw, th = 0, 0
                if tw <= 1 and th <= 1:
                    continue
                tex_targets[name_str] = {
                    "ue_path": tex_path, "size": [tw, th],
                    "srgb": val.srgb,
                    "compression": str(val.compression_settings),
                }

        # 找引用此材质的 SM
        dep_opt = unreal.AssetRegistryDependencyOptions()
        referencers = ar.get_referencers(unreal.Name(mat_path), dep_opt)
        mesh_paths = []
        if referencers:
            for ref in referencers:
                for ad in ar.get_assets_by_package_name(ref):
                    if str(ad.asset_class_path.asset_name) == "StaticMesh":
                        mesh_paths.append(str(ad.package_name))

        # 收集 UV bbox
        g_umin, g_umax = float("inf"), float("-inf")
        g_vmin, g_vmax = float("inf"), float("-inf")
        mesh_reports = []

        for mp in mesh_paths:
            mesh = unreal.load_asset(mp)
            if not mesh:
                continue
            md = mesh.get_static_mesh_description(0)
            if not md:
                continue
            vi_count = md.get_vertex_instance_count()
            us, vs = [], []
            for i in range(vi_count):
                vi = unreal.VertexInstanceID(i)
                try:
                    uv = md.get_vertex_instance_uv(vi, uv_channel)
                    us.append(uv.x)
                    vs.append(uv.y)
                except Exception:
                    pass
            if us:
                u0, u1 = min(us), max(us)
                v0, v1 = min(vs), max(vs)
                g_umin = min(g_umin, u0)
                g_umax = max(g_umax, u1)
                g_vmin = min(g_vmin, v0)
                g_vmax = max(g_vmax, v1)
                mesh_reports.append({"name": mesh.get_name(), "path": mp,
                                     "vi": vi_count, "u": [u0, u1], "v": [v0, v1]})

        proj_dir = unreal.SystemLibrary.get_project_directory()
        uv_bbox = {"u_min": g_umin, "u_max": g_umax, "v_min": g_vmin, "v_max": g_vmax}
        util_pct = round((g_umax - g_umin) * (g_vmax - g_vmin) * 100, 2) if mesh_reports else 0

        return {
            "mat_name": mat_inst.get_name(),
            "proj_dir": proj_dir,
            "tex_targets": tex_targets,
            "mesh_paths": mesh_paths,
            "mesh_reports": mesh_reports,
            "uv_bbox": uv_bbox,
            "utilization_pct": util_pct,
        }, None

    def _export_textures(tex_targets, export_dir):
        """Step 2: 导出贴图为 TGA。"""
        os.makedirs(export_dir, exist_ok=True)
        for pname, tinfo in tex_targets.items():
            tex = unreal.load_asset(tinfo["ue_path"])
            if not tex:
                continue
            out_file = os.path.join(export_dir, f"{tinfo['ue_path'].split('/')[-1]}.tga")
            task = unreal.AssetExportTask()
            task.object = tex
            task.filename = out_file
            task.replace_identical = True
            task.prompt = False
            task.automated = True
            unreal.Exporter.run_asset_export_task(task)
            tinfo["orig_tga"] = out_file

    def _crop_textures(tex_targets, uv_bbox, padding_px, crop_dir):
        """Step 3: 裁切贴图（PIL）。
        
        裁切后 resize 到 2^n 尺寸（UE 要求）。
        对法线/混合贴图使用 NEAREST 插值避免破坏方向数据，
        对 BaseColor 使用 LANCZOS 高质量插值。
        """
        try:
            from PIL import Image
        except ImportError:
            return {"error": "PIL (Pillow) not installed. Please install: pip install Pillow"}
        os.makedirs(crop_dir, exist_ok=True)
        report = {}

        u_min = max(0.0, uv_bbox["u_min"])
        u_max = min(1.0, uv_bbox["u_max"])
        v_min = max(0.0, uv_bbox["v_min"])
        v_max = min(1.0, uv_bbox["v_max"])

        for pname, tinfo in tex_targets.items():
            orig_tga = tinfo.get("orig_tga")
            if not orig_tga or not os.path.exists(orig_tga):
                report[pname] = {"error": f"TGA not found: {orig_tga}"}
                continue

            img = Image.open(orig_tga)
            w, h = img.size

            left = max(0, int(u_min * w) - padding_px)
            right = min(w, math.ceil(u_max * w) + padding_px)
            upper = max(0, int(v_min * h) - padding_px)
            lower = min(h, math.ceil(v_max * h) + padding_px)

            cropped = img.crop((left, upper, right, lower))
            crop_w, crop_h = cropped.size

            # resize 到 2^n（UE 贴图尺寸要求）
            new_w = _best_size(crop_w)
            new_h = _best_size(crop_h)

            # sRGB=True 的贴图（BaseColor 等）用 LANCZOS，
            # 非 sRGB 的贴图（Normal/Mix 等）用 NEAREST 避免破坏数据
            is_srgb = tinfo.get("srgb", False)
            resample = Image.LANCZOS if is_srgb else Image.NEAREST
            out_img = cropped.resize((new_w, new_h), resample)

            out_file = os.path.join(crop_dir, f"{tinfo['ue_path'].split('/')[-1]}_cropped.tga")
            out_img.save(out_file, format="TGA")
            tinfo["cropped_tga"] = out_file

            report[pname] = {
                "out_file": out_file,
                "orig_size": [w, h], "new_size": [new_w, new_h],
                "crop_rect": [left, upper, right, lower],
                "saved_pct": round((1 - new_w * new_h / (w * h)) * 100, 1),
            }
        return report

    def _remap_uvs(mesh_paths, uv_bbox, uv_channel):
        """Step 4: 重映射 UV 到 0-1。
        
        使用 C++ MeshUVOpsAPI.remap_mesh_uv 修改 SourceModel MeshDescription，
        通过 CommitMeshDescription + PostEditChange 正确 rebuild RenderData，
        不会产生多余 UV 通道（避免 build_from_static_mesh_descriptions 的 8 UV bug）。
        """
        u_min = uv_bbox["u_min"]
        u_span = uv_bbox["u_max"] - u_min
        v_min = uv_bbox["v_min"]
        v_span = uv_bbox["v_max"] - v_min
        results = []

        offset = unreal.Vector2D(u_min, v_min)
        scale = unreal.Vector2D(1.0 / u_span if u_span > 0 else 1.0,
                                1.0 / v_span if v_span > 0 else 1.0)

        for mp in mesh_paths:
            count = unreal.MeshUVOpsAPI.remap_mesh_uv(mp, uv_channel, offset, scale, 0)
            if count >= 0:
                results.append({"path": mp.split("/")[-1], "vi_remapped": count})
            else:
                results.append({"path": mp.split("/")[-1], "error": "remap failed"})

        return results

    def _reimport_textures(tex_targets, crop_report):
        """Step: 导入裁切后的贴图替换原资产。
        
        ⚠️ 不调用 save_asset — 项目可能有 AssetAuditor 插件，
        save 时会自动触发审计（弹对话框、修改压缩格式等），
        打乱渲染资源状态，导致后续 build mesh crash。
        贴图导入后标记 dirty，让用户手动保存或工具最后统一保存。
        """
        results = []
        for pname, tinfo in tex_targets.items():
            cr = crop_report.get(pname, {})
            if "error" in cr or "out_file" not in cr:
                results.append({"param": pname, "error": "Crop failed"})
                continue

            ue_path = tinfo["ue_path"]
            tga_file = cr["out_file"]

            # 读取原始属性
            orig = unreal.load_asset(ue_path)
            orig_srgb = orig.srgb if orig else False
            orig_compression = orig.compression_settings if orig else unreal.TextureCompressionSettings.TC_DEFAULT

            pkg_path = "/".join(ue_path.split("/")[:-1])
            asset_name = ue_path.split("/")[-1]

            task = unreal.AssetImportTask()
            task.filename = tga_file
            task.destination_path = pkg_path
            task.destination_name = asset_name
            task.replace_existing = True
            task.automated = True
            task.save = False
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

            imported = unreal.load_asset(ue_path)
            if imported:
                imported.srgb = orig_srgb
                imported.compression_settings = orig_compression
                imported.mip_gen_settings = unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP
                # 不 save — 避免触发 AssetAuditor
                results.append({
                    "param": pname, "success": True,
                    "size": [imported.blueprint_get_size_x(), imported.blueprint_get_size_y()],
                })
            else:
                results.append({"param": pname, "error": "Import failed"})

        return results
    
    # ===== 主逻辑 =====
    mat_path = raw_params.get("material_instance_path", "").strip()
    tex_filter_str = raw_params.get("texture_param_names", "")
    tex_filter = [s.strip() for s in tex_filter_str.split(",") if s.strip()] if tex_filter_str else []
    uv_channel = int(raw_params.get("uv_channel", 0))
    padding_px = int(raw_params.get("padding_px", 4))
    export_dir_param = raw_params.get("export_dir", "").strip()
    dry_run = bool(raw_params.get("dry_run", False))

    if not mat_path:
        return {"success": False, "error": "请填写材质实例路径"}

    # Step 1: 分析
    analysis, err = _analyze(mat_path, tex_filter, uv_channel)
    if err:
        return {"success": False, "error": err}

    uv_bbox = analysis["uv_bbox"]
    util_pct = analysis["utilization_pct"]
    tex_targets = analysis["tex_targets"]
    mesh_paths = analysis["mesh_paths"]

    if not mesh_paths:
        return {"success": False, "error": "未找到引用该材质实例的 StaticMesh"}
    if not tex_targets:
        return {"success": False, "error": "未检测到可优化的贴图"}
    if util_pct > 85:
        return {"success": True, "message": f"UV 利用率已达 {util_pct}%，无需优化"}

    # 导出目录
    proj_dir = analysis["proj_dir"]
    if export_dir_param:
        export_dir = export_dir_param
    else:
        export_dir = os.path.join(proj_dir, "Saved", "UVOptimize", analysis["mat_name"])
    orig_dir = os.path.join(export_dir, "original")
    crop_dir = os.path.join(export_dir, "cropped")

    if dry_run:
        lines = [
            f"[DRY RUN] UV 贴图利用率优化预览",
            f"材质实例: {mat_path}",
            f"关联 SM: {len(mesh_paths)} 个",
            f"UV bbox: U[{uv_bbox['u_min']:.4f}~{uv_bbox['u_max']:.4f}] "
            f"V[{uv_bbox['v_min']:.4f}~{uv_bbox['v_max']:.4f}]",
            f"当前利用率: {util_pct}%",
            "", "待优化贴图:",
        ]
        for pname, tinfo in tex_targets.items():
            w, h = tinfo["size"]
            u_span = uv_bbox["u_max"] - uv_bbox["u_min"]
            v_span = min(1.0, uv_bbox["v_max"]) - max(0.0, uv_bbox["v_min"])
            new_w = math.ceil(u_span * w) + padding_px * 2
            new_h = math.ceil(v_span * h) + padding_px * 2
            saved = round((1 - new_w * new_h / (w * h)) * 100, 1)
            lines.append(f"  [{pname}] {tinfo['ue_path']}")
            lines.append(f"    {w}×{h} → {new_w}×{new_h}  省 {saved}%")
        return {"success": True, "dry_run": True, "report": "\n".join(lines)}

    # Step 2: 导出原始贴图
    _export_textures(tex_targets, orig_dir)

    # Step 3: 裁切贴图（PIL，纯文件操作，不触发 UE）
    crop_report = _crop_textures(tex_targets, uv_bbox, padding_px, crop_dir)

    # Step 4: 重映射 UV + build mesh（先于贴图导入！）
    # ⚠️ 执行顺序至关重要：
    # build_from_static_mesh_descriptions 和 import_asset_tasks 都会释放/重建渲染资源。
    # 如果先 import 贴图再 build mesh，两者释放的渲染资源会冲突导致 UE crash:
    #   "A FRenderResource was deleted without being released first!"
    # 所以必须先完成所有 mesh build，最后再导入贴图。
    remap_results = _remap_uvs(mesh_paths, uv_bbox, uv_channel)

    # Step 5: 导入裁切贴图（mesh build 全部完成后）
    import_results = _reimport_textures(tex_targets, crop_report)

    # Step 6: 统一保存所有修改（贴图 + mesh）
    # 放在最后，避免中途 save 触发 AssetAuditor 插件干扰渲染资源
    saved_assets = []
    for pname, tinfo in tex_targets.items():
        try:
            unreal.EditorAssetLibrary.save_asset(tinfo["ue_path"])
            saved_assets.append(tinfo["ue_path"])
        except Exception:
            pass
    for mp in mesh_paths:
        try:
            unreal.EditorAssetLibrary.save_asset(mp)
            saved_assets.append(mp)
        except Exception:
            pass

    # 汇总
    report_lines = [
        f"✅ UV & 贴图优化完成",
        f"材质实例: {mat_path}",
        f"关联 SM: {len(mesh_paths)} 个",
        f"UV 利用率: {util_pct}% → ~100%",
        "", "贴图节省:",
    ]
    for pname, cr in crop_report.items():
        if "new_size" in cr:
            report_lines.append(
                f"  [{pname}] {cr['orig_size'][0]}×{cr['orig_size'][1]} "
                f"→ {cr['new_size'][0]}×{cr['new_size'][1]}  省 {cr['saved_pct']}%"
            )

    return {
        "success": True,
        "report": "\n".join(report_lines),
        "mesh_count": len(mesh_paths),
        "texture_count": len(tex_targets),
        "uv_utilization_before": util_pct,
        "crop_report": crop_report,
        "remap_results": remap_results,
        "import_results": import_results,
    }


# --- ArtClaw Tool Manager auto-call ---
# 由 Tool Manager _execute_on_dcc 动态注入参数调用，
# 此处仅作 guard，不硬编码参数。
if __name__ == "__main__":
    import json as _json, sys as _sys
    # 支持命令行: python main.py '{"material_instance_path": "..."}'
    if len(_sys.argv) > 1:
        _params = _json.loads(_sys.argv[1])
        _result = uv_texture_optimize(**_params)
        print(_json.dumps(_result, ensure_ascii=False, default=str))


