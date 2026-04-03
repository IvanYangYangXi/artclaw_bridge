"""
ue57_viewport_capture - UE Viewport Screenshot & Scene Analysis Skill

Captures viewport screenshots (color/depth/normal), collects camera transform
and scene statistics, prepares analysis context for AI vision models.

Uses SceneCapture2D + RenderTarget approach for multi-buffer support.
"""

import unreal
import os
import time
import base64
import json
from pathlib import Path


# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_RESOLUTION = (1920, 1080)
ANALYSIS_RESOLUTION = (1024, 576)   # For AI analysis, save tokens
SCREENSHOT_DIR = os.path.join(unreal.Paths.project_saved_dir(), "ViewportCaptures")

# Buffer types and their SceneCaptureSource mapping
BUFFER_TYPES = {
    "color":    unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR,
    "base_color": unreal.SceneCaptureSource.SCS_BASE_COLOR,
    "depth":    unreal.SceneCaptureSource.SCS_SCENE_DEPTH,
    "normal":   unreal.SceneCaptureSource.SCS_NORMAL,
    "hdr":      unreal.SceneCaptureSource.SCS_FINAL_COLOR_HDR,
}


# ── Helper Functions ─────────────────────────────────────────────────────────

def _ensure_dir(dir_path):
    """Ensure directory exists."""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def _get_timestamp():
    """Get timestamp string for filenames."""
    return time.strftime("%Y%m%d_%H%M%S")


def _get_viewport_camera_info():
    """Get current viewport camera transform and FOV."""
    try:
        location, rotation = unreal.EditorLevelLibrary.get_level_viewport_camera_info()
        return {
            "location": {"x": location.x, "y": location.y, "z": location.z},
            "rotation": {"pitch": rotation.pitch, "yaw": rotation.yaw, "roll": rotation.roll},
        }
    except Exception as e:
        return {"error": str(e)}


def _get_scene_stats():
    """Collect scene statistics for analysis context."""
    all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
    
    stats = {
        "total_actors": len(all_actors),
        "by_class": {},
        "lights": [],
        "cameras": [],
    }
    
    for actor in all_actors:
        class_name = actor.get_class().get_name()
        stats["by_class"][class_name] = stats["by_class"].get(class_name, 0) + 1
        
        # Collect light info
        if "Light" in class_name:
            light_info = {"name": actor.get_name(), "class": class_name}
            loc = actor.get_actor_location()
            light_info["location"] = {"x": loc.x, "y": loc.y, "z": loc.z}
            stats["lights"].append(light_info)
        
        # Collect camera info
        if "Camera" in class_name:
            cam_info = {"name": actor.get_name(), "class": class_name}
            loc = actor.get_actor_location()
            cam_info["location"] = {"x": loc.x, "y": loc.y, "z": loc.z}
            stats["cameras"].append(cam_info)
    
    # Sort by_class by count descending
    stats["by_class"] = dict(sorted(stats["by_class"].items(), key=lambda x: x[1], reverse=True))
    
    return stats


def _image_to_base64(image_path, max_size=1024):
    """Read image file and return base64 string.
    
    Args:
        image_path: Path to image file
        max_size: Unused (resizing done at capture time since PIL unavailable)
        
    Returns:
        base64 encoded string of the image
    """
    if not os.path.exists(image_path):
        return None
    
    with open(image_path, "rb") as f:
        data = f.read()
    
    return base64.b64encode(data).decode("utf-8")


def _cleanup_temp_actors(actors):
    """Delete temporary actors created for capture."""
    for actor in actors:
        try:
            unreal.EditorLevelLibrary.destroy_actor(actor)
        except Exception:
            pass


# ── Core Capture Functions ───────────────────────────────────────────────────

def capture_viewport_scenecapture(
    resolution=None,
    buffers=None,
    output_dir=None,
    filename_prefix=None,
):
    """Capture viewport using SceneCapture2D approach.
    
    Creates a temporary SceneCapture2D actor at the current viewport camera
    position, captures specified buffers to RenderTargets, and exports as images.
    
    Args:
        resolution: Tuple (width, height). Default (1920, 1080).
        buffers: List of buffer types to capture. 
                 Options: "color", "base_color", "depth", "normal", "hdr"
                 Default: ["color"]
        output_dir: Output directory. Default: {Project}/Saved/ViewportCaptures/
        filename_prefix: Prefix for output files. Default: "capture_{timestamp}"
        
    Returns:
        dict with keys:
            - images: {buffer_name: file_path}
            - camera: viewport camera transform
            - resolution: (width, height)
            - timestamp: capture timestamp
    """
    if resolution is None:
        resolution = DEFAULT_RESOLUTION
    if buffers is None:
        buffers = ["color"]
    if output_dir is None:
        output_dir = SCREENSHOT_DIR
    
    _ensure_dir(output_dir)
    
    timestamp = _get_timestamp()
    if filename_prefix is None:
        filename_prefix = f"capture_{timestamp}"
    
    width, height = resolution
    
    # Get current viewport camera info
    camera_info = _get_viewport_camera_info()
    
    # Get viewport camera transform
    location, rotation = unreal.EditorLevelLibrary.get_level_viewport_camera_info()
    
    temp_actors = []
    image_paths = {}
    
    try:
        for buffer_name in buffers:
            if buffer_name not in BUFFER_TYPES:
                print(f"Warning: Unknown buffer type '{buffer_name}', skipping.")
                continue
            
            capture_source = BUFFER_TYPES[buffer_name]
            
            # Create RenderTarget
            world = unreal.EditorLevelLibrary.get_editor_world()
            
            # Use RGBA8 for all PNG-exportable buffers, RGBA16F only for HDR (exports as EXR)
            if buffer_name == "hdr":
                rt_format = unreal.TextureRenderTargetFormat.RTF_RGBA16F
            else:
                rt_format = unreal.TextureRenderTargetFormat.RTF_RGBA8
            
            render_target = unreal.RenderingLibrary.create_render_target2d(
                world, width, height, rt_format
            )
            
            # Spawn SceneCapture2D actor
            capture_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
                unreal.SceneCapture2D, location, rotation
            )
            temp_actors.append(capture_actor)
            
            # Configure capture component
            capture_comp = capture_actor.capture_component2d
            capture_comp.texture_target = render_target
            capture_comp.capture_source = capture_source
            capture_comp.capture_every_frame = False
            capture_comp.capture_on_movement = False
            
            # Capture the scene
            capture_comp.capture_scene()
            
            # Export to file - choose format based on buffer type
            out_filename = f"{filename_prefix}_{buffer_name}"
            write_options = unreal.ImageWriteOptions()
            write_options.overwrite_file = True
            write_options.async_ = False
            
            if buffer_name == "hdr":
                out_path = os.path.join(output_dir, f"{out_filename}.exr")
                write_options.format = unreal.DesiredImageFormat.EXR
            elif buffer_name in ("color", "base_color"):
                # Use JPG for color buffers (much smaller file size)
                out_path = os.path.join(output_dir, f"{out_filename}.jpg")
                write_options.format = unreal.DesiredImageFormat.JPG
                write_options.compression_quality = 85
            else:
                # PNG for depth/normal (precision matters)
                out_path = os.path.join(output_dir, f"{out_filename}.png")
                write_options.format = unreal.DesiredImageFormat.PNG
            
            render_target.export_to_disk(out_path, write_options)
            
            image_paths[buffer_name] = out_path
            print(f"Captured {buffer_name} -> {out_path}")
            
            # Release render target (no world arg needed)
            try:
                unreal.RenderingLibrary.release_render_target2d(render_target)
            except Exception:
                pass
    
    finally:
        # Cleanup temp actors
        _cleanup_temp_actors(temp_actors)
    
    result = {
        "images": image_paths,
        "camera": camera_info,
        "resolution": list(resolution),
        "timestamp": timestamp,
    }
    
    return result


def capture_viewport_highres(
    resolution=None,
    output_dir=None,
    filename=None,
    camera_actor=None,
):
    """Capture viewport using take_high_res_screenshot (color only).
    
    Simpler approach, captures the viewport as-is.
    
    Args:
        resolution: Tuple (width, height). Default (1920, 1080).
        output_dir: Output directory path.
        filename: Output filename (without extension).
        camera_actor: Optional CameraActor to capture from.
        
    Returns:
        dict with image_path, camera info, task object
    """
    if resolution is None:
        resolution = DEFAULT_RESOLUTION
    
    timestamp = _get_timestamp()
    if filename is None:
        filename = f"highres_{timestamp}"
    if output_dir is None:
        output_dir = SCREENSHOT_DIR
    
    _ensure_dir(output_dir)
    
    width, height = resolution
    full_path = os.path.join(output_dir, filename)
    
    camera_info = _get_viewport_camera_info()
    
    task = unreal.AutomationLibrary.take_high_res_screenshot(
        width, height, full_path,
        camera=camera_actor,
        capture_hdr=False,
        force_game_view=True,
    )
    
    return {
        "image_path": full_path + ".png",
        "camera": camera_info,
        "resolution": list(resolution),
        "timestamp": timestamp,
        "task": task,
    }


# ── Analysis Context Builder ─────────────────────────────────────────────────

def build_analysis_context(
    capture_result,
    mode="general",
    custom_prompt=None,
    include_stats=True,
    analysis_max_size=1024,
):
    """Build analysis context from capture result.
    
    Reads captured images, converts to base64, collects scene metadata,
    and assembles a structured context dict for AI analysis.
    
    Args:
        capture_result: Return value from capture_viewport_scenecapture()
        mode: Analysis mode - "general", "composition", "lighting", 
              "performance", "color", "custom"
        custom_prompt: Custom analysis prompt (used when mode="custom")
        include_stats: Whether to include scene statistics
        analysis_max_size: Max image dimension for base64 encoding
        
    Returns:
        dict with:
            - images_base64: {buffer_name: base64_string}
            - camera: camera transform
            - scene_stats: scene statistics (if include_stats)
            - analysis_prompt: pre-built analysis prompt
            - mode: analysis mode used
    """
    context = {
        "camera": capture_result.get("camera", {}),
        "resolution": capture_result.get("resolution", []),
        "timestamp": capture_result.get("timestamp", ""),
        "mode": mode,
        "images_base64": {},
    }
    
    # Convert images to base64
    images = capture_result.get("images", {})
    for buffer_name, img_path in images.items():
        b64 = _image_to_base64(img_path, max_size=analysis_max_size)
        if b64:
            context["images_base64"][buffer_name] = b64
    
    # Single image path (from highres capture)
    if "image_path" in capture_result:
        b64 = _image_to_base64(capture_result["image_path"], max_size=analysis_max_size)
        if b64:
            context["images_base64"]["color"] = b64
    
    # Scene stats
    if include_stats:
        context["scene_stats"] = _get_scene_stats()
    
    # Analysis prompt
    context["analysis_prompt"] = _get_analysis_prompt(mode, custom_prompt, context)
    
    return context


def _get_analysis_prompt(mode, custom_prompt, context):
    """Generate analysis prompt based on mode."""
    
    camera_desc = ""
    cam = context.get("camera", {})
    if cam and "location" not in cam.get("error", ""):
        loc = cam.get("location", {})
        rot = cam.get("rotation", {})
        camera_desc = (
            f"相机位置: ({loc.get('x',0):.1f}, {loc.get('y',0):.1f}, {loc.get('z',0):.1f}), "
            f"旋转: (Pitch={rot.get('pitch',0):.1f}, Yaw={rot.get('yaw',0):.1f}, Roll={rot.get('roll',0):.1f})"
        )
    
    buffers_desc = ", ".join(context.get("images_base64", {}).keys())
    
    base_info = f"""
## 截图信息
- 分辨率: {context.get('resolution', [])}
- 可用 Buffer: {buffers_desc}
- {camera_desc}
""".strip()
    
    prompts = {
        "general": f"""{base_info}

请对这个 UE 场景截图进行综合分析，包括但不限于：
1. 场景内容描述（可见的物体、环境、氛围）
2. 构图评价（视觉焦点、空间层次、引导线）
3. 光照分析（光源方向、阴影质量、色温）
4. 颜色与色调（主色调、对比度、饱和度）
5. 潜在优化建议（画面质量、性能、场景搭建）
如果提供了深度图/法线图，请结合分析空间关系和几何质量。""",

        "composition": f"""{base_info}

请分析这个 UE 场景截图的 **构图与视觉设计**：
1. 三分法与黄金比例的运用
2. 视觉焦点和引导线
3. 前景/中景/背景的空间层次
4. 视觉重心和平衡感
5. 景深效果和空间透视
6. 改进建议：如何通过调整物体位置、相机角度优化构图""",

        "lighting": f"""{base_info}

请分析这个 UE 场景截图的 **光照与氛围**：
1. 主光源方向、强度、色温
2. 辅助光和环境光
3. 阴影质量（硬/软阴影、阴影漏光）
4. 全局光照效果（间接光照、反射、AO）
5. 曝光和色调映射
6. 光照对氛围/情绪的影响
7. 优化建议""",

        "performance": f"""{base_info}

请分析这个 UE 场景截图的 **潜在性能问题**：
1. 是否存在过度绘制（透明物体堆叠、粒子密集区域）
2. 几何复杂度（远处可见的高面数物体）
3. 光源数量和类型（动态光 vs 烘焙光）
4. 材质复杂度的视觉线索
5. LOD 和 Culling 的效果
6. 后处理效果的使用
如果有深度图，分析渲染距离和可能的遮挡剔除优化机会。
如果有法线图，分析几何细节和法线贴图的使用情况。""",

        "color": f"""{base_info}

请分析这个 UE 场景截图的 **色彩与调色**：
1. 主色调和配色方案
2. 色彩对比度和饱和度
3. 色温统一性
4. 色彩分区和过渡
5. 后处理调色效果
6. 优化建议：色彩平衡、氛围增强""",
    }
    
    if mode == "custom" and custom_prompt:
        return f"{base_info}\n\n{custom_prompt}"
    
    return prompts.get(mode, prompts["general"])


# ── Convenience Functions ────────────────────────────────────────────────────

def quick_capture(buffers=None):
    """Quick capture with defaults. Returns capture result dict.
    
    Args:
        buffers: List of buffer types. Default: ["color"]
                 Options: "color", "base_color", "depth", "normal", "hdr"
    """
    return capture_viewport_scenecapture(
        resolution=DEFAULT_RESOLUTION,
        buffers=buffers or ["color"],
    )


def quick_analyze(mode="general", buffers=None, custom_prompt=None, 
                   analysis_resolution=None):
    """Capture + build analysis context in one call.
    
    Captures at a smaller resolution (default 1024x576) to save tokens when
    sending to AI for analysis. Use capture_viewport_scenecapture() separately 
    if you need full-resolution images.
    
    Args:
        mode: "general", "composition", "lighting", "performance", "color", "custom"
        buffers: Buffer types to capture. Default: ["color"]
        custom_prompt: Custom prompt (when mode="custom")
        analysis_resolution: Resolution for analysis capture. Default: ANALYSIS_RESOLUTION (1024x576)
        
    Returns:
        Analysis context dict with base64 images and prompt
    """
    if analysis_resolution is None:
        analysis_resolution = ANALYSIS_RESOLUTION
    
    capture = capture_viewport_scenecapture(
        resolution=analysis_resolution,
        buffers=buffers or ["color"],
    )
    
    return build_analysis_context(
        capture,
        mode=mode,
        custom_prompt=custom_prompt,
    )


def cleanup_captures(max_age_hours=24):
    """Clean up old capture files.
    
    Args:
        max_age_hours: Delete files older than this many hours. Default: 24.
        
    Returns:
        Number of files deleted.
    """
    if not os.path.exists(SCREENSHOT_DIR):
        return 0
    
    now = time.time()
    deleted = 0
    
    for f in os.listdir(SCREENSHOT_DIR):
        fpath = os.path.join(SCREENSHOT_DIR, f)
        if os.path.isfile(fpath):
            age_hours = (now - os.path.getmtime(fpath)) / 3600
            if age_hours > max_age_hours:
                os.remove(fpath)
                deleted += 1
    
    return deleted
