"""
Unreal Engine Adapter for ArtClaw SDK
=====================================

Implements DCC backend interface for Unreal Engine using the unreal module.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional

from .base import BaseDCCBackend
from .. import logger


class UEAdapter(BaseDCCBackend):
    """Unreal Engine DCC backend adapter."""
    
    def __init__(self):
        super().__init__()
        self.dcc_name = "ue"
        try:
            import unreal
            self.unreal = unreal
            # Get version if available
            try:
                self.dcc_version = self.unreal.SystemLibrary.get_engine_version()
            except:
                self.dcc_version = "5.x"
        except ImportError:
            raise RuntimeError("Unreal module not available - not running in UE environment")
    
    def get_dcc_name(self) -> str:
        return self.dcc_name
    
    def get_dcc_version(self) -> str:
        return self.dcc_version
    
    def get_context(self) -> Dict[str, Any]:
        """Get complete UE context."""
        return {
            "software": {
                "name": self.get_dcc_name(),
                "version": self.get_dcc_version(),
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}"
            },
            "scene_info": self.get_scene_info(),
            "selected": self.get_selected(),
            "viewport": self.get_viewport_info()
        }
    
    def get_selected(self) -> List[Dict[str, Any]]:
        """Get currently selected actors."""
        return self.get_selected_assets() + self.get_selected_objects()
    
    def get_selected_assets(self) -> List[Dict[str, Any]]:
        """获取 Content Browser 中选中的资产。"""
        try:
            selected_assets = self.unreal.EditorUtilityLibrary.get_selected_assets()
            result = []
            for asset in selected_assets:
                result.append({
                    "name": asset.get_name(),
                    "path": asset.get_path_name().split(".")[0],
                    "type": asset.get_class().get_name(),  # 使用实际 class 名而非 "asset"
                    "class": asset.get_class().get_name(),
                })
            return result
        except Exception as e:
            logger.error(f"Failed to get UE selected assets: {e}")
            return []

    def get_selected_objects(self) -> List[Dict[str, Any]]:
        """获取 Viewport 中选中的 Actor。"""
        try:
            selected_level_actors = self.unreal.EditorLevelLibrary.get_selected_level_actors()
            result = []
            for actor in selected_level_actors:
                result.append({
                    "name": actor.get_name(),
                    "path": actor.get_path_name(),
                    "type": actor.get_class().get_name(),  # 使用实际 class 名而非 "actor"
                    "class": actor.get_class().get_name(),
                    "is_level_actor": True,
                    "location": tuple(actor.get_actor_location()),
                    "rotation": tuple(actor.get_actor_rotation()),
                })
            return result
        except Exception as e:
            logger.error(f"Failed to get UE selected objects: {e}")
            return []
    
    def get_scene_path(self) -> Optional[str]:
        """Get current level path."""
        try:
            world = self.unreal.EditorLevelLibrary.get_editor_world()
            if world:
                return world.get_path_name()
            return None
        except Exception as e:
            logger.error(f"Failed to get UE scene path: {e}")
            return None
    
    def get_scene_info(self) -> Dict[str, Any]:
        """Get UE level/world information."""
        try:
            world = self.unreal.EditorLevelLibrary.get_editor_world()
            if not world:
                return {}
                
            all_actors = self.unreal.EditorLevelLibrary.get_all_level_actors()
            
            # Count by actor class
            actor_counts = {}
            for actor in all_actors:
                class_name = actor.get_class().get_name()
                actor_counts[class_name] = actor_counts.get(class_name, 0) + 1
            
            return {
                "level_path": world.get_path_name(),
                "level_name": world.get_name(),
                "total_actors": len(all_actors),
                "actor_counts": actor_counts,
                "world_bounds": self._get_world_bounds(world)
            }
            
        except Exception as e:
            logger.error(f"Failed to get UE scene info: {e}")
            return {}
    
    def get_viewport_info(self) -> Dict[str, Any]:
        """Get viewport camera information."""
        try:
            # Get editor viewport camera transform
            viewport_client = self.unreal.EditorLevelLibrary.get_editor_viewport_client()
            if viewport_client:
                camera_location = viewport_client.get_view_location()
                camera_rotation = viewport_client.get_view_rotation()
                
                return {
                    "camera_location": tuple(camera_location),
                    "camera_rotation": tuple(camera_rotation),
                    "viewport_type": "perspective"  # UE default
                }
        except Exception as e:
            logger.debug(f"Could not get UE viewport info: {e}")
            
        return {}
    
    def execute_on_main_thread(self, func, *args, **kwargs) -> Any:
        """Execute on UE main thread."""
        # UE Python already runs on main thread in most cases
        # For more complex scenarios, could use unreal.EditorUtilityLibrary
        return func(*args, **kwargs)
    
    def is_main_thread(self) -> bool:
        """UE Python typically runs on main thread."""
        return True
    
    def _get_world_bounds(self, world) -> Dict[str, Any]:
        """Calculate world bounds from all actors."""
        try:
            all_actors = self.unreal.EditorLevelLibrary.get_all_level_actors() 
            
            if not all_actors:
                return {}
                
            min_x = min_y = min_z = float('inf')
            max_x = max_y = max_z = float('-inf')
            
            for actor in all_actors:
                try:
                    location = actor.get_actor_location()
                    min_x = min(min_x, location.x)
                    max_x = max(max_x, location.x)
                    min_y = min(min_y, location.y) 
                    max_y = max(max_y, location.y)
                    min_z = min(min_z, location.z)
                    max_z = max(max_z, location.z)
                except:
                    continue
            
            if min_x != float('inf'):
                return {
                    "min": (min_x, min_y, min_z),
                    "max": (max_x, max_y, max_z),
                    "center": ((min_x + max_x) / 2, (min_y + max_y) / 2, (min_z + max_z) / 2),
                    "size": (max_x - min_x, max_y - min_y, max_z - min_z)
                }
            
        except Exception as e:
            logger.debug(f"Could not calculate UE world bounds: {e}")
            
        return {}