"""
3ds Max Adapter for ArtClaw SDK
===============================

Implements DCC backend interface for Autodesk 3ds Max using pymxs.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional

from .base import BaseDCCBackend
from .. import logger


class MaxAdapter(BaseDCCBackend):
    """3ds Max DCC backend adapter."""
    
    def __init__(self):
        super().__init__()
        self.dcc_name = "max"
        try:
            import pymxs
            self.rt = pymxs.runtime
            self.dcc_version = str(self.rt.maxversion()[0])  # Major version
        except ImportError:
            raise RuntimeError("pymxs not available - not running in 3ds Max environment")
    
    def get_dcc_name(self) -> str:
        return self.dcc_name
    
    def get_dcc_version(self) -> str:
        return self.dcc_version
    
    def get_context(self) -> Dict[str, Any]:
        """Get complete 3ds Max context."""
        return {
            "software": {
                "name": self.get_dcc_name(),
                "version": self.get_dcc_version(),
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
                "units": {
                    "system": str(self.rt.units.SystemType),
                    "display": str(self.rt.units.DisplayType)
                }
            },
            "scene_info": self.get_scene_info(),
            "selected": self.get_selected(),
            "viewport": self.get_viewport_info()
        }
    
    def get_selected(self) -> List[Dict[str, Any]]:
        """Get currently selected 3ds Max objects."""
        return self.get_selected_assets() + self.get_selected_objects()
    
    def get_selected_assets(self) -> List[Dict[str, Any]]:
        """暂未对接资源管理器。"""
        return []

    def get_selected_objects(self) -> List[Dict[str, Any]]:
        """暂未实现，返回空列表。"""
        try:
            selection = self.rt.selection
            result = []
            
            for i, obj in enumerate(selection):
                try:
                    # Get object properties
                    pos = obj.pos if hasattr(obj, 'pos') else None
                    rotation = obj.rotation if hasattr(obj, 'rotation') else None
                    scale = obj.scale if hasattr(obj, 'scale') else None
                    
                    obj_info = {
                        "name": obj.name,
                        "long_name": obj.name,  # Max doesn't have hierarchical names like Maya
                        "type": str(obj.classID) if hasattr(obj, 'classID') else "unknown",
                        "class_name": str(type(obj).__name__),
                        "index": i
                    }
                    
                    # Add transform info if available
                    if pos is not None:
                        obj_info["position"] = [pos.x, pos.y, pos.z]
                    if rotation is not None:
                        # Convert quaternion to euler if needed
                        try:
                            euler = rotation.asEulerAngles
                            obj_info["rotation"] = [euler.x, euler.y, euler.z]
                        except:
                            obj_info["rotation"] = str(rotation)
                    if scale is not None:
                        obj_info["scale"] = [scale.x, scale.y, scale.z]
                    
                    # Get material info if available
                    if hasattr(obj, 'material') and obj.material:
                        obj_info["material"] = obj.material.name
                    
                    result.append(obj_info)
                    
                except Exception as e:
                    logger.debug(f"Could not get info for Max object {obj}: {e}")
                    result.append({
                        "name": str(obj),
                        "long_name": str(obj),
                        "type": "unknown",
                        "index": i
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get Max selected objects: {e}")
            return []
    
    def get_scene_path(self) -> Optional[str]:
        """Get current 3ds Max scene file path."""
        try:
            scene_name = self.rt.maxFileName
            if scene_name and scene_name != "":
                scene_path = self.rt.maxFilePath + scene_name
                return scene_path
            return None
        except Exception as e:
            logger.error(f"Failed to get Max scene path: {e}")
            return None
    
    def get_scene_info(self) -> Dict[str, Any]:
        """Get 3ds Max scene information."""
        try:
            scene_file = self.get_scene_path() or "untitled"
            
            # Count objects
            all_objects = self.rt.objects
            object_count = len(list(all_objects)) if all_objects else 0
            
            # Count by categories
            geometry_count = 0
            lights_count = 0
            cameras_count = 0
            helpers_count = 0
            
            try:
                for obj in all_objects:
                    if hasattr(obj, 'classID'):
                        class_id = str(obj.classID)
                        if 'Geom' in str(type(obj)) or hasattr(obj, 'mesh'):
                            geometry_count += 1
                        elif 'Light' in str(type(obj)):
                            lights_count += 1
                        elif 'Camera' in str(type(obj)):
                            cameras_count += 1
                        else:
                            helpers_count += 1
            except Exception as e:
                logger.debug(f"Could not count Max objects by type: {e}")
            
            # Animation range
            anim_range = self.rt.animationRange
            start_frame = int(anim_range.start / self.rt.ticksPerFrame)
            end_frame = int(anim_range.end / self.rt.ticksPerFrame)
            current_frame = int(self.rt.currentTime / self.rt.ticksPerFrame)
            
            return {
                "scene_file": scene_file,
                "object_counts": {
                    "total": object_count,
                    "geometry": geometry_count,
                    "lights": lights_count,
                    "cameras": cameras_count,
                    "helpers": helpers_count
                },
                "animation": {
                    "frame_range": [start_frame, end_frame],
                    "current_frame": current_frame,
                    "fps": self.rt.frameRate
                },
                "units": {
                    "system": str(self.rt.units.SystemType),
                    "display": str(self.rt.units.DisplayType)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get Max scene info: {e}")
            return {}
    
    def get_viewport_info(self) -> Dict[str, Any]:
        """Get 3ds Max viewport camera information."""
        try:
            # Get active viewport
            active_viewport = self.rt.viewport.activeViewport
            
            viewport_info = {
                "active_viewport": active_viewport,
                "viewport_type": "unknown"
            }
            
            # Try to get camera info from active viewport
            try:
                # Get viewport type
                viewport_type = self.rt.viewport.getType()
                viewport_info["viewport_type"] = str(viewport_type)
                
                # Get camera transform if in camera view
                if hasattr(self.rt.viewport, 'getCamera'):
                    camera = self.rt.viewport.getCamera()
                    if camera:
                        pos = camera.pos
                        viewport_info.update({
                            "camera": camera.name,
                            "camera_location": [pos.x, pos.y, pos.z],
                            "is_camera_view": True
                        })
                    else:
                        viewport_info["is_camera_view"] = False
                        
            except Exception as e:
                logger.debug(f"Could not get Max viewport camera info: {e}")
            
            return viewport_info
            
        except Exception as e:
            logger.debug(f"Could not get Max viewport info: {e}")
            return {}
    
    def execute_on_main_thread(self, func, *args, **kwargs) -> Any:
        """Execute on 3ds Max main thread."""
        # 3ds Max pymxs typically runs on main thread
        # For more complex scenarios, could use callbacks or deferred execution
        return func(*args, **kwargs)
    
    def is_main_thread(self) -> bool:
        """3ds Max pymxs typically runs on main thread."""
        return True