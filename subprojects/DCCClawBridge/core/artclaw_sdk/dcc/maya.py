"""
Maya Adapter for ArtClaw SDK
============================

Implements DCC backend interface for Autodesk Maya using maya.cmds.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional

from .base import BaseDCCBackend
from .. import logger


class MayaAdapter(BaseDCCBackend):
    """Maya DCC backend adapter."""
    
    def __init__(self):
        super().__init__()
        self.dcc_name = "maya"
        try:
            import maya.cmds as cmds
            import maya.utils
            self.cmds = cmds
            self.utils = maya.utils
            self.dcc_version = cmds.about(version=True)
        except ImportError:
            raise RuntimeError("Maya modules not available - not running in Maya environment")
    
    def get_dcc_name(self) -> str:
        return self.dcc_name
    
    def get_dcc_version(self) -> str:
        return self.dcc_version
    
    def get_context(self) -> Dict[str, Any]:
        """Get complete Maya context."""
        return {
            "software": {
                "name": self.get_dcc_name(),
                "version": self.get_dcc_version(),
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
                "up_axis": self.cmds.upAxis(query=True, axis=True),
                "units": {
                    "linear": self.cmds.currentUnit(query=True, linear=True),
                    "angular": self.cmds.currentUnit(query=True, angle=True),
                    "time": self.cmds.currentUnit(query=True, time=True)
                }
            },
            "scene_info": self.get_scene_info(),
            "selected": self.get_selected(),
            "viewport": self.get_viewport_info()
        }
    
    def get_selected(self) -> List[Dict[str, Any]]:
        """Get currently selected Maya objects."""
        return self.get_selected_assets() + self.get_selected_objects()
    
    def get_selected_assets(self) -> List[Dict[str, Any]]:
        """暂未对接资源管理器。"""
        return []

    def get_selected_objects(self) -> List[Dict[str, Any]]:
        """获取场景中选中的 Maya 对象。"""
        try:
            selected = self.cmds.ls(selection=True, long=True) or []
            result = []
            
            for obj in selected:
                short_name = obj.split("|")[-1]
                try:
                    obj_type = self.cmds.objectType(obj)
                    shapes = self.cmds.listRelatives(obj, shapes=True, fullPath=True) or []
                    
                    # Get transform info if it's a transform node
                    transform_info = {}
                    if self.cmds.objectType(obj) == "transform":
                        try:
                            transform_info = {
                                "translation": self.cmds.xform(obj, query=True, translation=True, worldSpace=True),
                                "rotation": self.cmds.xform(obj, query=True, rotation=True, worldSpace=True),
                                "scale": self.cmds.xform(obj, query=True, scale=True, relative=True)
                            }
                        except:
                            pass
                    
                    result.append({
                        "name": short_name,
                        "long_name": obj,
                        "type": obj_type,
                        "shapes": [s.split("|")[-1] for s in shapes],
                        **transform_info
                    })
                    
                except Exception as e:
                    logger.debug(f"Could not get info for Maya object {obj}: {e}")
                    result.append({
                        "name": short_name,
                        "long_name": obj,
                        "type": "unknown"
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get Maya selected objects: {e}")
            return []
    
    def get_scene_path(self) -> Optional[str]:
        """Get current Maya scene file path."""
        try:
            path = self.cmds.file(query=True, sceneName=True)
            return path if path else None
        except Exception as e:
            logger.error(f"Failed to get Maya scene path: {e}")
            return None
    
    def get_scene_info(self) -> Dict[str, Any]:
        """Get Maya scene information."""
        try:
            scene_file = self.cmds.file(query=True, sceneName=True) or "untitled"
            
            # Count objects by type
            all_transforms = self.cmds.ls(type="transform") or []
            all_meshes = self.cmds.ls(type="mesh") or []
            all_curves = self.cmds.ls(type="nurbsCurve") or []
            all_surfaces = self.cmds.ls(type="nurbsSurface") or []
            all_lights = self.cmds.ls(type="light") or []
            all_cameras = self.cmds.ls(type="camera") or []
            
            # Animation range
            start_frame = self.cmds.playbackOptions(query=True, minTime=True)
            end_frame = self.cmds.playbackOptions(query=True, maxTime=True)
            current_frame = self.cmds.currentTime(query=True)
            
            return {
                "scene_file": scene_file,
                "object_counts": {
                    "transforms": len(all_transforms),
                    "meshes": len(all_meshes),
                    "curves": len(all_curves),
                    "surfaces": len(all_surfaces),
                    "lights": len(all_lights),
                    "cameras": len(all_cameras)
                },
                "animation": {
                    "frame_range": [int(start_frame), int(end_frame)],
                    "current_frame": int(current_frame),
                    "fps": self.cmds.currentUnit(query=True, time=True)
                },
                "scene_units": {
                    "linear": self.cmds.currentUnit(query=True, linear=True),
                    "angular": self.cmds.currentUnit(query=True, angle=True),
                    "time": self.cmds.currentUnit(query=True, time=True)
                },
                "up_axis": self.cmds.upAxis(query=True, axis=True)
            }
            
        except Exception as e:
            logger.error(f"Failed to get Maya scene info: {e}")
            return {}
    
    def get_viewport_info(self) -> Dict[str, Any]:
        """Get Maya viewport camera information."""
        try:
            # Get active viewport
            active_panel = self.cmds.getPanel(withFocus=True)
            if not active_panel or not self.cmds.getPanel(typeOf=active_panel) == "modelPanel":
                # Find first model panel if no active one
                model_panels = self.cmds.getPanel(type="modelPanel") or []
                active_panel = model_panels[0] if model_panels else None
            
            if active_panel:
                # Get camera from panel
                camera = self.cmds.modelPanel(active_panel, query=True, camera=True)
                if camera:
                    # Get camera transform
                    camera_transform = self.cmds.listRelatives(camera, parent=True)[0] if self.cmds.listRelatives(camera, parent=True) else camera
                    
                    translation = self.cmds.xform(camera_transform, query=True, translation=True, worldSpace=True)
                    rotation = self.cmds.xform(camera_transform, query=True, rotation=True, worldSpace=True)
                    
                    # Get camera properties
                    focal_length = self.cmds.getAttr(f"{camera}.focalLength")
                    
                    return {
                        "active_panel": active_panel,
                        "camera": camera,
                        "camera_transform": camera_transform,
                        "camera_location": translation,
                        "camera_rotation": rotation,
                        "focal_length": focal_length,
                        "viewport_type": "perspective" if camera != "top" and camera != "front" and camera != "side" else "orthographic"
                    }
            
        except Exception as e:
            logger.debug(f"Could not get Maya viewport info: {e}")
            
        return {}
    
    def execute_on_main_thread(self, func, *args, **kwargs) -> Any:
        """Execute on Maya main thread."""
        return self.utils.executeInMainThreadWithResult(func, *args, **kwargs)
    
    def is_main_thread(self) -> bool:
        """Check if on Maya main thread."""
        try:
            # Try a safe Maya command that requires main thread
            self.cmds.currentTime(query=True)
            return True
        except:
            return False