"""
Context API - Query DCC context information
==========================================

Provides unified access to:
- get_context(): Complete editor context
- get_selected(): Currently selected objects
- get_scene_path(): Current scene/file path  
- get_scene_info(): Scene metadata
- get_viewport_info(): Viewport/camera state
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from . import _current_adapter, logger


def get_context() -> Dict[str, Any]:
    """Get complete DCC editor context information.
    
    Returns:
        Dict containing:
        - software: DCC name and version
        - scene_info: Current scene metadata
        - selected: Currently selected objects
        - viewport: Viewport/camera state (if available)
    """
    if not _current_adapter:
        logger.warning("No DCC adapter available")
        return {}
    
    try:
        return _current_adapter.get_context()
    except Exception as e:
        logger.error(f"Failed to get context: {e}")
        return {}


def get_selected() -> List[Dict[str, Any]]:
    """Get currently selected objects.
    
    Returns:
        List of selected object dictionaries with:
        - name: Object short name
        - long_name: Full path/identifier  
        - type: Object type
        - Additional DCC-specific properties
    """
    if not _current_adapter:
        logger.warning("No DCC adapter available")
        return []
        
    try:
        return _current_adapter.get_selected()
    except Exception as e:
        logger.error(f"Failed to get selected objects: {e}")
        return []


def get_scene_path() -> Optional[str]:
    """Get current scene/file path.
    
    Returns:
        Current scene file path or None if unsaved
    """
    if not _current_adapter:
        logger.warning("No DCC adapter available")
        return None
        
    try:
        return _current_adapter.get_scene_path()
    except Exception as e:
        logger.error(f"Failed to get scene path: {e}")
        return None


def get_scene_info() -> Dict[str, Any]:
    """Get scene metadata and statistics.
    
    Returns:
        Dict containing scene information like:
        - object_count: Total objects in scene
        - file_path: Current file path
        - frame_range: Animation range (if applicable)
        - Additional DCC-specific metadata
    """
    if not _current_adapter:
        logger.warning("No DCC adapter available") 
        return {}
        
    try:
        return _current_adapter.get_scene_info()
    except Exception as e:
        logger.error(f"Failed to get scene info: {e}")
        return {}


def get_viewport_info() -> Dict[str, Any]:
    """Get viewport/camera state information.
    
    Returns:
        Dict containing viewport information like:
        - camera_position: Current camera position
        - camera_rotation: Current camera rotation
        - viewport_size: Viewport dimensions
        - Additional DCC-specific viewport data
    """
    if not _current_adapter:
        logger.warning("No DCC adapter available")
        return {}
        
    try:
        return _current_adapter.get_viewport_info()
    except Exception as e:
        logger.error(f"Failed to get viewport info: {e}")
        return {}


def get_selected_assets() -> List[Dict[str, Any]]:
    """获取资源管理器中选中的资产文件。"""
    if not _current_adapter:
        return []
    try:
        return _current_adapter.get_selected_assets()
    except Exception as e:
        logger.error(f"Failed to get selected assets: {e}")
        return []


def get_selected_objects() -> List[Dict[str, Any]]:
    """获取场景/视口中选中的对象。"""
    if not _current_adapter:
        return []
    try:
        return _current_adapter.get_selected_objects()
    except Exception as e:
        logger.error(f"Failed to get selected objects: {e}")
        return []