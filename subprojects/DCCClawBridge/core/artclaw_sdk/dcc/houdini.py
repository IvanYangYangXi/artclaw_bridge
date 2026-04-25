"""
Houdini Adapter for ArtClaw SDK
===============================

Implements DCC backend interface for SideFX Houdini using hou module.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional

from .base import BaseDCCBackend
from .. import logger


class HoudiniAdapter(BaseDCCBackend):
    """Houdini DCC backend adapter."""
    
    def __init__(self):
        super().__init__()
        self.dcc_name = "houdini"
        try:
            import hou
            self.hou = hou
            self.dcc_version = hou.applicationVersionString()
        except ImportError:
            raise RuntimeError("hou module not available - not running in Houdini environment")
    
    def get_dcc_name(self) -> str:
        return self.dcc_name
    
    def get_dcc_version(self) -> str:
        return self.dcc_version
    
    def get_context(self) -> Dict[str, Any]:
        """Get complete Houdini context."""
        return {
            "software": {
                "name": self.get_dcc_name(),
                "version": self.get_dcc_version(),
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
                "up_axis": "Y"  # Houdini default Y-up
            },
            "scene_info": self.get_scene_info(),
            "selected": self.get_selected(),
            "viewport": self.get_viewport_info()
        }
    
    def get_selected(self) -> List[Dict[str, Any]]:
        """Get currently selected Houdini nodes."""
        return self.get_selected_assets() + self.get_selected_objects()
    
    def get_selected_assets(self) -> List[Dict[str, Any]]:
        """暂未对接资源管理器。"""
        return []

    def get_selected_objects(self) -> List[Dict[str, Any]]:
        """暂未实现，返回空列表。"""
        try:
            selected_nodes = self.hou.selectedNodes()
            result = []
            
            for node in selected_nodes:
                result.append({
                    "name": node.name(),
                    "path": node.path(),
                    "type": node.type().name(),
                    "category": node.type().category().name() if node.type().category() else "unknown"
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get Houdini selected objects: {e}")
            return []
    
    def get_scene_path(self) -> Optional[str]:
        """Get current Houdini hip file path."""
        try:
            hip_path = self.hou.hipFile.path()
            if hip_path and "untitled" not in hip_path.lower():
                return hip_path
            return None
        except Exception as e:
            logger.error(f"Failed to get Houdini scene path: {e}")
            return None
    
    def get_scene_info(self) -> Dict[str, Any]:
        """Get Houdini scene information."""
        try:
            scene_file = self.hou.hipFile.path() or "untitled.hip"
            
            # Count nodes by context
            obj_context = self.hou.node("/obj")
            shop_context = self.hou.node("/shop") 
            mat_context = self.hou.node("/mat")
            
            object_count = 0
            geometry_count = 0
            material_count = 0
            shop_count = 0
            
            if obj_context:
                children = obj_context.children()
                object_count = len(children)
                geometry_count = sum(1 for child in children if child.type().name() == "geo")
            
            if shop_context:
                shop_count = len(shop_context.children())
                
            if mat_context:
                material_count = len(mat_context.children())
            
            # Frame range and FPS
            frame_range = list(self.hou.playbar.frameRange())
            fps = self.hou.fps()
            current_frame = self.hou.frame()
            
            return {
                "scene_file": scene_file,
                "object_count": object_count,
                "geometry_count": geometry_count,
                "material_count": material_count,
                "shop_count": shop_count,
                "frame_range": [int(frame_range[0]), int(frame_range[1])],
                "current_frame": int(current_frame),
                "fps": fps,
                "up_axis": "Y"
            }
            
        except Exception as e:
            logger.error(f"Failed to get Houdini scene info: {e}")
            return {}
    
    def get_viewport_info(self) -> Dict[str, Any]:
        """Get Houdini viewport camera information."""
        try:
            # Houdini viewport access is more complex
            # This is a basic implementation
            viewport_info = {
                "viewport_type": "3d",
                "up_axis": "Y"
            }
            
            # Try to get scene viewer info if available
            try:
                desktop = self.hou.ui.curDesktop()
                scene_viewer = desktop.paneTabOfType(self.hou.paneTabType.SceneViewer)
                if scene_viewer:
                    viewport = scene_viewer.curViewport()
                    if viewport:
                        # Get camera transform
                        camera_transform = viewport.viewTransform()
                        viewport_info.update({
                            "camera_transform": str(camera_transform),
                            "viewport_name": viewport.name()
                        })
            except Exception as e:
                logger.debug(f"Could not get Houdini viewport details: {e}")
            
            return viewport_info
            
        except Exception as e:
            logger.debug(f"Could not get Houdini viewport info: {e}")
            return {}
    
    def execute_on_main_thread(self, func, *args, **kwargs) -> Any:
        """Execute on Houdini main thread."""
        try:
            import hdefereval
            return hdefereval.executeInMainThreadWithResult(func, *args, **kwargs)
        except ImportError:
            # Fallback if hdefereval not available
            return func(*args, **kwargs)
    
    def is_main_thread(self) -> bool:
        """Check if on Houdini main thread."""
        try:
            # Try a safe Houdini operation that requires main thread
            self.hou.frame()
            return True
        except:
            return False