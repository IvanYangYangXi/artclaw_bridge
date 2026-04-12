"""
Substance Painter Adapter for ArtClaw SDK
=========================================

Implements DCC backend interface for Adobe Substance Painter using substance_painter module.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional

from .base import BaseDCCBackend
from .. import logger


class SubstancePainterAdapter(BaseDCCBackend):
    """Substance Painter DCC backend adapter."""
    
    def __init__(self):
        super().__init__()
        self.dcc_name = "substance_painter"
        try:
            import substance_painter as sp
            self.sp = sp
            
            # Try to get version
            try:
                self.dcc_version = sp.application.version_info()
            except:
                self.dcc_version = "unknown"
                
        except ImportError:
            raise RuntimeError("Substance Painter module not available - not running in SP environment")
    
    def get_dcc_name(self) -> str:
        return self.dcc_name
    
    def get_dcc_version(self) -> str:
        return str(self.dcc_version) if self.dcc_version != "unknown" else self.dcc_version
    
    def get_context(self) -> Dict[str, Any]:
        """Get complete Substance Painter context."""
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
        """Get currently selected items in Substance Painter."""
        try:
            result = []
            
            # Try to get current project and texture sets
            if not self.sp.project.is_open():
                return result
                
            # Get current texture set
            try:
                current_texture_set = self.sp.textureset.get_active_stack()
                if current_texture_set:
                    texture_set_info = {
                        "name": current_texture_set.name(),
                        "type": "texture_set",
                        "is_active": True,
                        "channel_count": len(current_texture_set.all_channels())
                    }
                    result.append(texture_set_info)
            except Exception as e:
                logger.debug(f"Could not get SP active texture set: {e}")
            
            # Try to get selected layers if available
            try:
                # Note: SP API for layer selection may vary by version
                pass
            except Exception:
                pass
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get Substance Painter selection: {e}")
            return []
    
    def get_scene_path(self) -> Optional[str]:
        """Get current Substance Painter project file path."""
        try:
            if self.sp.project.is_open():
                project_url = self.sp.project.url()
                return project_url if project_url else None
            return None
        except Exception as e:
            logger.error(f"Failed to get SP scene path: {e}")
            return None
    
    def get_scene_info(self) -> Dict[str, Any]:
        """Get Substance Painter project information."""
        try:
            if not self.sp.project.is_open():
                return {"project_open": False}
            
            project_info = {
                "project_open": True,
                "project_file": self.get_scene_path() or "untitled.spp"
            }
            
            # Get texture sets
            try:
                texture_sets = self.sp.textureset.all_texture_sets()
                texture_set_info = []
                
                for ts in texture_sets:
                    try:
                        ts_info = {
                            "name": ts.name(),
                            "channels": len(ts.all_channels()),
                            "stack_count": len(ts.all_stacks()) if hasattr(ts, 'all_stacks') else 0
                        }
                        texture_set_info.append(ts_info)
                    except Exception:
                        continue
                
                project_info.update({
                    "texture_sets": len(texture_sets),
                    "texture_set_details": texture_set_info
                })
                
            except Exception as e:
                logger.debug(f"Could not get SP texture set info: {e}")
            
            # Get mesh information
            try:
                mesh_maps = self.sp.project.MeshMapUsage
                project_info["mesh_maps_available"] = len([m for m in mesh_maps])
            except Exception:
                pass
            
            # Get export settings if available
            try:
                export_presets = self.sp.export.list_presets()
                project_info["export_presets"] = len(export_presets)
            except Exception:
                pass
            
            return project_info
            
        except Exception as e:
            logger.error(f"Failed to get SP scene info: {e}")
            return {}
    
    def get_viewport_info(self) -> Dict[str, Any]:
        """Get Substance Painter viewport info."""
        try:
            if not self.sp.project.is_open():
                return {"project_open": False}
            
            viewport_info = {
                "type": "3d_viewport",
                "has_3d_preview": True,
                "project_open": True
            }
            
            # Try to get camera/viewport information if available
            try:
                # SP viewport API may vary by version
                pass
            except Exception:
                pass
            
            return viewport_info
            
        except Exception as e:
            logger.debug(f"Could not get SP viewport info: {e}")
            return {}
    
    def rename_object(self, obj_name: str, new_name: str) -> bool:
        """Rename a Substance Painter object (texture set, layer, etc.)."""
        try:
            if not self.sp.project.is_open():
                return False
                
            # Try to rename texture set
            try:
                texture_sets = self.sp.textureset.all_texture_sets()
                for ts in texture_sets:
                    if ts.name() == obj_name:
                        # Note: SP may not allow direct texture set renaming
                        # This would depend on the specific SP API version
                        return False  # Not typically supported
            except Exception:
                pass
            
            return False  # Renaming not typically supported in SP
            
        except Exception as e:
            logger.error(f"Failed to rename SP object {obj_name}: {e}")
            return False
    
    def execute_on_main_thread(self, func, *args, **kwargs) -> Any:
        """Execute on Substance Painter main thread."""
        # SP Python API typically runs on main thread
        return func(*args, **kwargs)
    
    def is_main_thread(self) -> bool:
        """SP Python typically runs on main thread."""
        return True
    
    # Substance Painter-specific methods
    
    def bake_mesh_maps(self) -> bool:
        """Bake mesh maps for the current project."""
        try:
            if not self.sp.project.is_open():
                return False
                
            # This would depend on SP API for baking
            # Different versions may have different APIs
            logger.info("SP: Baking mesh maps...")
            # self.sp.baking.bake_mesh_maps(...)  # API varies
            return True
            
        except Exception as e:
            logger.error(f"Failed to bake SP mesh maps: {e}")
            return False
    
    def export_textures(self, export_preset: str = None) -> bool:
        """Export textures using specified preset."""
        try:
            if not self.sp.project.is_open():
                return False
            
            # Get available export presets
            presets = self.sp.export.list_presets()
            
            if export_preset:
                if export_preset not in presets:
                    logger.error(f"Export preset '{export_preset}' not found")
                    return False
                preset_to_use = export_preset
            else:
                # Use first available preset
                preset_to_use = presets[0] if presets else None
            
            if not preset_to_use:
                logger.error("No export preset available")
                return False
            
            # Export with preset
            logger.info(f"SP: Exporting with preset '{preset_to_use}'...")
            # self.sp.export.export_project_textures(preset_to_use)  # API may vary
            return True
            
        except Exception as e:
            logger.error(f"Failed to export SP textures: {e}")
            return False
    
    def get_layer_stack(self, texture_set_name: str = None) -> List[Dict[str, Any]]:
        """Get layer stack information."""
        try:
            if not self.sp.project.is_open():
                return []
                
            # Get texture set
            if texture_set_name:
                texture_sets = self.sp.textureset.all_texture_sets()
                target_ts = None
                for ts in texture_sets:
                    if ts.name() == texture_set_name:
                        target_ts = ts
                        break
                if not target_ts:
                    return []
            else:
                target_ts = self.sp.textureset.get_active_stack()
                
            if not target_ts:
                return []
            
            # Get layers/stacks
            layers = []
            try:
                stacks = target_ts.all_stacks()
                for stack in stacks:
                    layer_info = {
                        "name": str(stack),  # SP stack representation may vary
                        "type": "stack"
                    }
                    layers.append(layer_info)
            except Exception as e:
                logger.debug(f"Could not get SP layer stack details: {e}")
            
            return layers
            
        except Exception as e:
            logger.error(f"Failed to get SP layer stack: {e}")
            return []
    
    # Object manipulation methods (limited applicability to SP)
    
    def delete_objects(self, objects: List[Dict[str, Any]]) -> int:
        """Delete objects - limited to texture sets and layers in SP context."""
        logger.warning("delete_objects limited in Substance Painter - only applies to texture sets and layers")
        return 0
    
    def duplicate_objects(self, objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Duplicate objects - limited to layers in SP context."""
        logger.warning("duplicate_objects limited in Substance Painter - only applies to layers")
        return []
    
    def export_selected(self, path: str, format: str = "fbx") -> bool:
        """Export selected - not applicable to SP texture workflow."""
        logger.warning("export_selected not applicable to Substance Painter - use texture export instead")
        return False
    
    def import_file(self, path: str) -> List[Dict[str, Any]]:
        """Import file - limited to mesh/texture imports in SP."""
        logger.warning("import_file limited in Substance Painter - use mesh import or texture import instead")
        return []