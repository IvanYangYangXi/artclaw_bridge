"""
UV & 贴图利用率优化工具
纯 UE Python 实现，直接注入 DCC 执行。
分析材质实例关联的所有 SM 的 UV bbox，裁切贴图到实际使用区域，重映射 UV。
"""
import unreal
import os
import math
import json


def uv_texture_optimize(**raw_params):
    """入口函数。raw_params 由 Tool Manager 传入（keyword arguments）。"""
    
    # ===== 内联辅助函数 =====
    def _align4(n):
        return math.ceil(n / 4) * 4

    def _best_size(exact_px, max_waste=0.20):
        """选最小 2^n 尺寸，浪费不超过 max_waste 则用 2^n，否则 align4。"""
        if exact_px <= 0:
            return 4
        p = 1
        while p < exact_px:
            p <<= 1
        waste = (p - exact_px) / p
        return p if waste <= max_waste else _align4(exact_px)

    def _analyze(mat_path, tex_param_filter, uv_channel):
        """Step 1: 分析材质实例关联的 SM 和 UV bbox。"""
        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        mel = unreal.MaterialEditingLibrary
        mat_inst = unreal.load_asset(mat_path)
        if not mat_inst:
            return None, f"Cannot load asset: {mat_path}"

        parent = mat_inst.parent
        tex_names_all = mel.get_texture_parameter_names(parent) if parent else []
        tex_targets = {}

        for name in tex_names_all:
            name_str = str(name)
            if tex_param_filter and name_str not in tex_param_filter:
                continue
            val = mel.get_material_instance_texture_parameter_value(mat_inst, name)
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
        """Step 3: 裁切贴图（PIL）。"""
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

            crop_w = right - left
            crop_h = lower - upper
            new_w = _best_size(crop_w)
            new_h = _best_size(crop_h)

            cropped = img.crop((left, upper, right, lower))
            out_img = cropped.resize((new_w, new_h), Image.LANCZOS)

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
        """Step 4: 重映射 UV 到 0-1。"""
        u_min = uv_bbox["u_min"]
        u_span = uv_bbox["u_max"] - u_min
        v_min = uv_bbox["v_min"]
        v_span = uv_bbox["v_max"] - v_min
        results = []

        for mp in mesh_paths:
            mesh = unreal.load_asset(mp)
            if not mesh:
                results.append({"path": mp, "error": "Cannot load"})
                continue
            md = mesh.get_static_mesh_description(0)
            if not md:
                results.append({"path": mp, "error": "No mesh description"})
                continue

            # 临时关闭 lightmap UV 生成
            smes = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
            orig_build = smes.get_lod_build_settings(mesh, 0)
            orig_gen_lm = orig_build.generate_lightmap_u_vs
            if orig_gen_lm:
                orig_build.generate_lightmap_u_vs = False
                smes.set_lod_build_settings(mesh, 0, orig_build)

            vi_count = md.get_vertex_instance_count()
            changed = 0
            for i in range(vi_count):
                vi = unreal.VertexInstanceID(i)
                uv = md.get_vertex_instance_uv(vi, uv_channel)
                new_u = (uv.x - u_min) / u_span if u_span > 0 else 0.0
                new_v = (uv.y - v_min) / v_span if v_span > 0 else 0.0
                md.set_vertex_instance_uv(vi, unreal.Vector2D(new_u, new_v), uv_channel)
                changed += 1
            mesh.build_from_static_mesh_descriptions([md])

            # 恢复 build settings
            if orig_gen_lm:
                orig_build.generate_lightmap_u_vs = True
                smes.set_lod_build_settings(mesh, 0, orig_build)

            unreal.EditorAssetLibrary.save_asset(mp)
            results.append({"path": mp.split("/")[-1], "vi_remapped": changed})

        return results

    def _reimport_textures(tex_targets, crop_report):
        """Step 5: 导入裁切后的贴图替换原资产。"""
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
                saved = unreal.EditorAssetLibrary.save_asset(ue_path)
                results.append({
                    "param": pname, "success": True, "saved": saved,
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
            new_w = _best_size(math.ceil(u_span * w) + padding_px * 2)
            new_h = _best_size(math.ceil(v_span * h) + padding_px * 2)
            saved = round((1 - new_w * new_h / (w * h)) * 100, 1)
            lines.append(f"  [{pname}] {tinfo['ue_path']}")
            lines.append(f"    {w}×{h} → {new_w}×{new_h}  省 {saved}%")
        return {"success": True, "dry_run": True, "report": "\n".join(lines)}

    # Step 2: 导出
    _export_textures(tex_targets, orig_dir)

    # Step 3: 裁切
    crop_report = _crop_textures(tex_targets, uv_bbox, padding_px, crop_dir)

    # Step 4: 重映射 UV
    remap_results = _remap_uvs(mesh_paths, uv_bbox, uv_channel)

    # Step 5: 导入裁切贴图
    import_results = _reimport_textures(tex_targets, crop_report)

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


# --- ArtClaw Tool Manager: auto-call ---
import json as _json
_result = uv_texture_optimize(**{'material_instance_path': '/Game/Scenes/Prop/Module/Catwalk/Material/aa_TEST_MI_Props_WallRail', 'texture_param_names': '', 'uv_channel': 0, 'padding_px': 4, 'export_dir': '', 'dry_run': False})
if _result is not None:
    print(_json.dumps(_result, ensure_ascii=False, default=str))
