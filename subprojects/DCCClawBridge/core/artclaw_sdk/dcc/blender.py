"""
Blender Adapter for ArtClaw SDK
===============================

Implements DCC backend interface for Blender using bpy module.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional

from .base import BaseDCCBackend
from .. import logger


class BlenderAdapter(BaseDCCBackend):
    """Blender DCC backend adapter."""
    
    def __init__(self):
        super().__init__()
        self.dcc_name = "blender"
        try:
            import bpy
            self.bpy = bpy
            self.dcc_version = ".".join(map(str, bpy.app.version))
        except ImportError:
            raise RuntimeError("bpy not available - not running in Blender environment")
    
    def get_dcc_name(self) -> str:
        return self.dcc_name
    
    def get_dcc_version(self) -> str:
        return self.dcc_version
    
    def get_context(self) -> Dict[str, Any]:
        """Get complete Blender context."""
        return {
            "software": {
                "name": self.get_dcc_name(),
                "version": self.get_dcc_version(),
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
                "build_info": {
                    "date": self.bpy.app.build_date.decode() if self.bpy.app.build_date else "unknown",
                    "hash": self.bpy.app.build_hash.decode() if self.bpy.app.build_hash else "unknown"
                }
            },
            "scene_info": self.get_scene_info(),
            "selected": self.get_selected(),
            "viewport": self.get_viewport_info()
        }
    
    def get_selected(self) -> List[Dict[str, Any]]:
        """Get currently selected Blender objects."""
        return self.get_selected_assets() + self.get_selected_objects()
    
    def get_selected_assets(self) -> List[Dict[str, Any]]:
        """Blender 无内置资源管理器，返回空列表。"""
        return []

    def get_selected_objects(self) -> List[Dict[str, Any]]:
        """获取场景中选中的 Blender 对象。"""
        try:
            selected = self.bpy.context.selected_objects
            result = []
            
            for obj in selected:
                try:
                    # Get object properties
                    obj_info = {
                        "name": obj.name,
                        "long_name": obj.name,  # Blender uses unique names
                        "type": obj.type,
                        "location": list(obj.location),
                        "rotation": list(obj.rotation_euler),
                        "scale": list(obj.scale),
                        "is_active": obj == self.bpy.context.active_object
                    }
                    
                    # Add mesh-specific info
                    if obj.type == 'MESH' and obj.data:
                        mesh = obj.data
                        obj_info.update({
                            "vertices": len(mesh.vertices),
                            "edges": len(mesh.edges),
                            "faces": len(mesh.polygons),
                            "materials": len(obj.material_slots)
                        })
                    
                    # Add light-specific info
                    elif obj.type == 'LIGHT' and obj.data:
                        light = obj.data
                        obj_info.update({
                            "light_type": light.type,
                            "energy": light.energy
                        })
                    
                    # Add camera-specific info
                    elif obj.type == 'CAMERA' and obj.data:
                        camera = obj.data
                        obj_info.update({
                            "focal_length": camera.lens,
                            "sensor_width": camera.sensor_width
                        })
                    
                    result.append(obj_info)
                    
                except Exception as e:
                    logger.debug(f"Could not get info for Blender object {obj.name}: {e}")
                    result.append({
                        "name": obj.name,
                        "long_name": obj.name,
                        "type": "unknown"
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get Blender selected objects: {e}")
            return []
    
    def get_scene_path(self) -> Optional[str]:
        """Get current Blender file path."""
        try:
            filepath = self.bpy.data.filepath
            return filepath if filepath else None
        except Exception as e:
            logger.error(f"Failed to get Blender scene path: {e}")
            return None
    
    def get_scene_info(self) -> Dict[str, Any]:
        """Get Blender scene information."""
        try:
            scene = self.bpy.context.scene
            
            # Count objects by type
            object_counts = {}
            for obj in self.bpy.data.objects:
                obj_type = obj.type
                object_counts[obj_type] = object_counts.get(obj_type, 0) + 1
            
            return {
                "scene_file": self.get_scene_path() or "untitled.blend",
                "scene_name": scene.name,
                "object_counts": object_counts,
                "total_objects": len(self.bpy.data.objects),
                "animation": {
                    "frame_range": [scene.frame_start, scene.frame_end],
                    "current_frame": scene.frame_current,
                    "fps": scene.render.fps
                },
                "render_engine": scene.render.engine,
                "collections": len(self.bpy.data.collections),
                "materials": len(self.bpy.data.materials),
                "textures": len(self.bpy.data.textures),
                "units": {
                    "system": scene.unit_settings.system,
                    "length": scene.unit_settings.length_unit,
                    "scale": scene.unit_settings.scale_length
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get Blender scene info: {e}")
            return {}
    
    def get_viewport_info(self) -> Dict[str, Any]:
        """Get Blender viewport information."""
        try:
            viewport_info = {}
            
            # Get active area and space
            if hasattr(self.bpy.context, 'area') and self.bpy.context.area:
                area = self.bpy.context.area
                if area.type == 'VIEW_3D':
                    space = area.spaces.active
                    if space.type == 'VIEW_3D':
                        region_3d = space.region_3d
                        
                        viewport_info.update({
                            "viewport_type": "3D_VIEW",
                            "view_perspective": region_3d.view_perspective,
                            "view_location": list(region_3d.view_location),
                            "view_rotation": list(region_3d.view_rotation),
                            "view_distance": region_3d.view_distance,
                            "is_perspective": region_3d.is_perspective
                        })
                        
                        # Get active camera info
                        if self.bpy.context.scene.camera:
                            camera = self.bpy.context.scene.camera
                            viewport_info.update({
                                "scene_camera": camera.name,
                                "camera_location": list(camera.location),
                                "camera_rotation": list(camera.rotation_euler)
                            })
            
            return viewport_info
            
        except Exception as e:
            logger.debug(f"Could not get Blender viewport info: {e}")
            return {}
    
    def execute_on_main_thread(self, func, *args, **kwargs) -> Any:
        """Execute on Blender main thread."""
        # Blender Python typically runs on main thread
        # For deferred execution, could use bpy.app.timers
        return func(*args, **kwargs)
    
    def is_main_thread(self) -> bool:
        """Blender Python typically runs on main thread."""
        return True