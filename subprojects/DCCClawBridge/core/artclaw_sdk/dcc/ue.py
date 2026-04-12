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
        try:
            selected_actors = self.unreal.EditorUtilityLibrary.get_selected_assets()
            selected_level_actors = self.unreal.EditorLevelLibrary.get_selected_level_actors()
            
            result = []
            
            # Add selected assets
            for asset in selected_actors:
                result.append({
                    "name": asset.get_name(),
                    "path": asset.get_path_name(),
                    "type": "asset",
                    "class": asset.get_class().get_name(),
                    "is_level_actor": False
                })
            
            # Add selected level actors  
            for actor in selected_level_actors:
                result.append({
                    "name": actor.get_name(),
                    "path": actor.get_path_name(), 
                    "type": "actor",
                    "class": actor.get_class().get_name(),
                    "is_level_actor": True,
                    "location": tuple(actor.get_actor_location()),
                    "rotation": tuple(actor.get_actor_rotation())
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
    
    def rename_object(self, obj_path: str, new_name: str) -> bool:
        """Rename a UE actor or asset."""
        try:
            # Try to find actor first
            actor = self.unreal.EditorLevelLibrary.get_actor_reference(obj_path)
            if actor:
                actor.set_actor_label(new_name)
                return True
                
            # Try as asset path
            asset = self.unreal.EditorAssetLibrary.find_asset_data(obj_path)
            if asset:
                return self.unreal.EditorAssetLibrary.rename_asset(obj_path, f"/Game/{new_name}")
                
            return False
            
        except Exception as e:
            logger.error(f"Failed to rename UE object {obj_path}: {e}")
            return False
    
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
    
    def delete_objects(self, objects: List[Dict[str, Any]]) -> int:
        """Delete UE actors from the level."""
        count = 0
        try:
            for obj in objects:
                obj_path = obj.get("path", "")
                if not obj_path:
                    continue
                
                try:
                    # Try to delete as actor
                    actor = self.unreal.EditorLevelLibrary.get_actor_reference(obj_path)
                    if actor:
                        self.unreal.EditorLevelLibrary.destroy_actor(actor)
                        count += 1
                        continue
                    
                    # Try to delete as asset
                    if self.unreal.EditorAssetLibrary.does_asset_exist(obj_path):
                        self.unreal.EditorAssetLibrary.delete_asset(obj_path)
                        count += 1
                        
                except Exception as e:
                    logger.debug(f"Failed to delete UE object {obj_path}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to delete UE objects: {e}")
        return count
    
    def duplicate_objects(self, objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Duplicate UE actors in the level."""
        results = []
        try:
            for obj in objects:
                obj_path = obj.get("path", "")
                if not obj_path or not obj.get("is_level_actor", False):
                    continue  # Only duplicate level actors for now
                
                try:
                    actor = self.unreal.EditorLevelLibrary.get_actor_reference(obj_path)
                    if actor:
                        # UE doesn't have a simple duplicate API, use spawn instead
                        actor_class = actor.get_class()
                        location = actor.get_actor_location()
                        rotation = actor.get_actor_rotation()
                        
                        # Offset the location slightly
                        new_location = self.unreal.Vector(
                            location.x + 100,  # Offset by 100 units
                            location.y,
                            location.z
                        )
                        
                        new_actor = self.unreal.EditorLevelLibrary.spawn_actor_from_class(
                            actor_class, new_location, rotation
                        )
                        
                        if new_actor:
                            results.append({
                                "name": new_actor.get_name(),
                                "path": new_actor.get_path_name(),
                                "type": "actor",
                                "class": new_actor.get_class().get_name(),
                                "is_level_actor": True
                            })
                            
                except Exception as e:
                    logger.debug(f"Failed to duplicate UE actor {obj_path}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to duplicate UE objects: {e}")
        return results
    
    def export_selected(self, path: str, format: str = "fbx") -> bool:
        """Export selected UE assets/actors to file."""
        try:
            format_lower = format.lower()
            
            if format_lower == "fbx":
                # Get selected static meshes and skeletal meshes
                selected_assets = self.unreal.EditorUtilityLibrary.get_selected_assets()
                selected_actors = self.unreal.EditorLevelLibrary.get_selected_level_actors()
                
                # Create export task
                export_task = self.unreal.AssetExportTask()
                export_task.filename = path
                export_task.automated = True
                export_task.replace_identical = True
                
                # Set objects to export
                objects_to_export = []
                
                # Add selected assets
                for asset in selected_assets:
                    if isinstance(asset, (self.unreal.StaticMesh, self.unreal.SkeletalMesh)):
                        objects_to_export.append(asset)
                
                # Add static mesh components from selected actors
                for actor in selected_actors:
                    static_mesh_comp = actor.get_component_by_class(self.unreal.StaticMeshComponent)
                    if static_mesh_comp and static_mesh_comp.static_mesh:
                        objects_to_export.append(static_mesh_comp.static_mesh)
                
                if objects_to_export:
                    export_task.object = objects_to_export[0]  # Export first object
                    self.unreal.Exporter.run_asset_export_task(export_task)
                    return True
                
            logger.warning(f"UE export format '{format}' not implemented or no valid objects selected")
            return False
            
        except Exception as e:
            logger.error(f"Failed to export from UE: {e}")
            return False
    
    def import_file(self, path: str) -> List[Dict[str, Any]]:
        """Import file into UE project."""
        try:
            # Create import task
            import_task = self.unreal.AssetImportTask()
            import_task.filename = path
            import_task.destination_path = "/Game/Imported"  # Default import location
            import_task.automated = True
            import_task.save = True
            import_task.replace_existing = True
            
            # Execute import
            self.unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([import_task])
            
            # Get imported assets
            results = []
            for imported_asset in import_task.imported_object_paths:
                asset = self.unreal.EditorAssetLibrary.find_asset_data(imported_asset)
                if asset:
                    results.append({
                        "name": asset.asset_name,
                        "path": imported_asset,
                        "type": "asset",
                        "class": asset.asset_class
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to import file into UE: {e}")
            return []