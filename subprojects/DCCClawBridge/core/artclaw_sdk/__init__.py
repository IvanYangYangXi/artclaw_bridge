"""
ArtClaw SDK - Runtime Package for DCC Tools
===========================================

Auto-detects current DCC environment and provides unified API for:
- Context queries (selected objects, scene info)
- Object filtering and manipulation
- Result/progress reporting
- Parameter parsing

Usage:
    from artclaw_sdk import context, result, progress

    # Get current context
    selected = context.get_selected()
    scene_path = context.get_scene_path()
    
    # Report results
    result.success(data={"processed": len(selected)})
    
    # Report progress
    progress.start(total=100)
    progress.update(50, "Processing...")
    progress.finish()
"""
from __future__ import annotations

import sys
import logging
from typing import Any, Dict, List, Optional

__version__ = "1.0.0"
__all__ = [
    "context", "filters", "params", "result", "progress", "logger", "log",
    "event",
    "get_current_dcc", "is_available",
    # Convenience functions
    "get_context", "get_selected", "get_selected_assets", "get_selected_objects", 
    "get_scene_path", "parse_params", "rename_object",
    "delete_objects", "duplicate_objects", "export_selected", "import_file",
    "filter_objects"
]

# Global DCC adapter instance
_current_adapter: Optional[Any] = None
_dcc_type: Optional[str] = None

_internal_logger = logging.getLogger("artclaw_sdk")


def get_current_dcc() -> str:
    """Get current DCC environment identifier."""
    return _dcc_type or "unknown"


def is_available() -> bool:
    """Check if SDK is properly initialized in a DCC environment.""" 
    return _current_adapter is not None


def _detect_dcc_environment():
    """Auto-detect current DCC environment and initialize adapter."""
    global _current_adapter, _dcc_type
    
    # Try UE (Unreal Engine)
    try:
        import unreal
        from .dcc.ue import UEAdapter
        _current_adapter = UEAdapter()
        _dcc_type = "ue"
        _internal_logger.info("ArtClaw SDK: Initialized for Unreal Engine")
        return
    except ImportError:
        pass
    
    # Try Maya
    try:
        import maya.cmds
        from .dcc.maya import MayaAdapter  
        _current_adapter = MayaAdapter()
        _dcc_type = "maya"
        _internal_logger.info("ArtClaw SDK: Initialized for Maya")
        return
    except ImportError:
        pass
    
    # Try 3ds Max
    try:
        import pymxs
        from .dcc.max import MaxAdapter
        _current_adapter = MaxAdapter()
        _dcc_type = "max" 
        _internal_logger.info("ArtClaw SDK: Initialized for 3ds Max")
        return
    except ImportError:
        pass
    
    # Try Houdini
    try:
        import hou
        from .dcc.houdini import HoudiniAdapter
        _current_adapter = HoudiniAdapter()
        _dcc_type = "houdini"
        _internal_logger.info("ArtClaw SDK: Initialized for Houdini")
        return
    except ImportError:
        pass
    
    # Try Blender
    try:
        import bpy
        from .dcc.blender import BlenderAdapter
        _current_adapter = BlenderAdapter()
        _dcc_type = "blender"
        _internal_logger.info("ArtClaw SDK: Initialized for Blender")
        return
    except ImportError:
        pass
    
    # Try ComfyUI (check for server module or specific imports)
    try:
        # ComfyUI detection - look for common ComfyUI modules
        from .dcc.comfyui import ComfyUIAdapter
        _current_adapter = ComfyUIAdapter()
        _dcc_type = "comfyui"
        _internal_logger.info("ArtClaw SDK: Initialized for ComfyUI")
        return
    except ImportError:
        pass
    
    # Try Substance Designer
    try:
        import sd
        from .dcc.substance_designer import SubstanceDesignerAdapter
        _current_adapter = SubstanceDesignerAdapter()
        _dcc_type = "substance_designer"
        _internal_logger.info("ArtClaw SDK: Initialized for Substance Designer")
        return
    except ImportError:
        pass
        
    # Try Substance Painter
    try:
        import substance_painter
        from .dcc.substance_painter import SubstancePainterAdapter
        _current_adapter = SubstancePainterAdapter()
        _dcc_type = "substance_painter"
        _internal_logger.info("ArtClaw SDK: Initialized for Substance Painter")
        return
    except ImportError:
        pass
    
    # No DCC detected
    _internal_logger.warning("ArtClaw SDK: No supported DCC environment detected")
    _dcc_type = "unknown"


# Initialize on import
_detect_dcc_environment()

# Import and expose modules (these will use the global _current_adapter)
from . import context
from . import filters  
from . import params
from . import result
from . import progress

from . import logger
# log 别名（兼容 sdk.log.info() 调用方式）
from . import logger as log
from .params import parse_params


# ── Convenience Functions ──
# These delegate directly to the current adapter for easier API usage

def get_context() -> Dict[str, Any]:
    """Get current DCC context.
    
    Returns:
        Dictionary containing DCC info, scene info, selected objects, etc.
    """
    if _current_adapter:
        return _current_adapter.get_context()
    return {"dcc": "unknown", "error": "No DCC environment detected"}


def get_selected() -> List[Dict[str, Any]]:
    """Get currently selected objects.
    
    Returns:
        List of selected object dictionaries
    """
    if _current_adapter:
        return _current_adapter.get_selected()
    return []


def get_scene_path() -> Optional[str]:
    """Get current scene file path.
    
    Returns:
        Current scene file path or None if unsaved
    """
    if _current_adapter:
        return _current_adapter.get_scene_path()
    return None


def rename_object(obj_id: str, new_name: str) -> bool:
    """Rename an object.
    
    Args:
        obj_id: Object identifier (path or name)
        new_name: New object name
        
    Returns:
        True if successful
    """
    if _current_adapter:
        return _current_adapter.rename_object(obj_id, new_name)
    return False


def delete_objects(objects: list) -> int:
    """Delete objects from the scene.
    
    Args:
        objects: List of object dictionaries to delete
        
    Returns:
        Number of objects successfully deleted
    """
    if _current_adapter:
        return _current_adapter.delete_objects(objects)
    return 0


def duplicate_objects(objects: list) -> list:
    """Duplicate objects in the scene.
    
    Args:
        objects: List of object dictionaries to duplicate
        
    Returns:
        List of newly created object dictionaries
    """
    if _current_adapter:
        return _current_adapter.duplicate_objects(objects)
    return []


def export_selected(path: str, format: str = "fbx") -> bool:
    """Export selected objects to file.
    
    Args:
        path: Output file path
        format: Export format (fbx, obj, etc.)
        
    Returns:
        True if export was successful
    """
    if _current_adapter:
        return _current_adapter.export_selected(path, format)
    return False


def import_file(path: str) -> list:
    """Import file into scene.
    
    Args:
        path: Path to file to import
        
    Returns:
        List of imported object dictionaries
    """
    if _current_adapter:
        return _current_adapter.import_file(path)
    return []


def filter_objects(objects: list, **criteria) -> list:
    """Filter objects by criteria.
    
    Args:
        objects: List of objects to filter
        **criteria: Filter criteria (type, name_pattern, etc.)
        
    Returns:
        Filtered list of objects
    """
    from . import filters as _filters
    return _filters.filter_objects(objects, **criteria)


def get_selected_assets() -> List[Dict[str, Any]]:
    """获取资源管理器中选中的资产文件（UE Content Browser 等）。
    非 UE 的 DCC 如无资源管理器对接，返回空列表。"""
    if _current_adapter:
        return _current_adapter.get_selected_assets()
    return []


def get_selected_objects() -> List[Dict[str, Any]]:
    """获取场景/视口中选中的对象（UE Actor、Blender Object 等）。"""
    if _current_adapter:
        return _current_adapter.get_selected_objects()
    return []