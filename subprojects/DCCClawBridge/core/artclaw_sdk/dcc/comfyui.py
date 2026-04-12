"""
ComfyUI Adapter for ArtClaw SDK
===============================

Implements DCC backend interface for ComfyUI.
ComfyUI is different from traditional DCCs - it's a node-based workflow system.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional

from .base import BaseDCCBackend
from .. import logger


class ComfyUIAdapter(BaseDCCBackend):
    """ComfyUI DCC backend adapter."""
    
    def __init__(self):
        super().__init__()
        self.dcc_name = "comfyui"
        self.dcc_version = "1.0"  # ComfyUI doesn't have a standard version API
        
        # ComfyUI doesn't have standard imports like other DCCs
        # We'll work with what's typically available in ComfyUI environment
        try:
            # Check if we're in a ComfyUI environment by looking for common modules
            # This is heuristic since ComfyUI doesn't have a standard way to detect itself
            self._detect_comfyui_environment()
        except Exception as e:
            logger.debug(f"ComfyUI environment detection: {e}")
    
    def _detect_comfyui_environment(self):
        """Attempt to detect ComfyUI environment."""
        # Look for ComfyUI-specific modules or paths
        try:
            import folder_paths  # ComfyUI uses this
            self._folder_paths = folder_paths
        except ImportError:
            pass
            
        try:
            import execution  # ComfyUI execution module
            self._execution = execution
        except ImportError:
            pass
            
        try:
            import server  # ComfyUI server module
            self._server = server
        except ImportError:
            pass
    
    def get_dcc_name(self) -> str:
        return self.dcc_name
    
    def get_dcc_version(self) -> str:
        return self.dcc_version
    
    def get_context(self) -> Dict[str, Any]:
        """Get ComfyUI context (workflow/system info)."""
        context = {
            "software": {
                "name": self.get_dcc_name(),
                "version": self.get_dcc_version(),
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}"
            },
            "scene_info": self.get_scene_info(),
            "selected": self.get_selected(),
            "viewport": self.get_viewport_info()
        }
        
        # Add ComfyUI-specific info
        try:
            if hasattr(self, '_folder_paths'):
                context["folder_paths"] = {
                    "models": getattr(self._folder_paths, 'models_dir', None),
                    "output": getattr(self._folder_paths, 'get_output_directory', lambda: None)(),
                    "input": getattr(self._folder_paths, 'get_input_directory', lambda: None)()
                }
        except Exception as e:
            logger.debug(f"Could not get ComfyUI folder paths: {e}")
        
        return context
    
    def get_selected(self) -> List[Dict[str, Any]]:
        """Get 'selected' items in ComfyUI context.
        
        For ComfyUI, this might mean active nodes or current workflow nodes.
        Since ComfyUI doesn't have traditional selection, we return workflow info.
        """
        try:
            # ComfyUI doesn't have traditional object selection
            # We could return active workflow nodes if available
            result = []
            
            # Try to get current workflow or queue information
            if hasattr(self, '_server'):
                try:
                    # Get server instance if available
                    server_instance = getattr(self._server, 'server', None)
                    if server_instance and hasattr(server_instance, 'client_id'):
                        result.append({
                            "name": "ComfyUI Server",
                            "type": "server",
                            "client_id": server_instance.client_id
                        })
                except Exception:
                    pass
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get ComfyUI selected items: {e}")
            return []
    
    def get_scene_path(self) -> Optional[str]:
        """Get current ComfyUI workflow file path.
        
        ComfyUI doesn't have a traditional scene file, but might have a workflow file.
        """
        try:
            # ComfyUI workflows are typically not saved to files directly
            # Return None as there's no standard way to get current workflow path
            return None
        except Exception as e:
            logger.error(f"Failed to get ComfyUI scene path: {e}")
            return None
    
    def get_scene_info(self) -> Dict[str, Any]:
        """Get ComfyUI system information."""
        try:
            info = {
                "type": "comfyui_system",
                "workflow_active": False,
                "queue_size": 0
            }
            
            # Try to get execution queue info
            try:
                if hasattr(self, '_execution'):
                    # Check if there's an execution queue
                    pass  # ComfyUI execution info varies
            except Exception:
                pass
            
            # Try to get model information
            try:
                if hasattr(self, '_folder_paths'):
                    # Could list available models
                    pass
            except Exception:
                pass
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get ComfyUI scene info: {e}")
            return {}
    
    def get_viewport_info(self) -> Dict[str, Any]:
        """Get ComfyUI viewport info.
        
        ComfyUI doesn't have a traditional 3D viewport.
        """
        return {
            "type": "web_interface",
            "has_3d_viewport": False
        }
    
    def rename_object(self, obj_id: str, new_name: str) -> bool:
        """Rename operation not applicable to ComfyUI."""
        logger.warning("Rename operation not supported in ComfyUI")
        return False
    
    def execute_on_main_thread(self, func, *args, **kwargs) -> Any:
        """Execute on ComfyUI main thread."""
        # ComfyUI runs in a web server context
        return func(*args, **kwargs)
    
    def is_main_thread(self) -> bool:
        """ComfyUI thread check."""
        return True  # Assume main thread for now
    
    # ComfyUI-specific methods
    
    def get_available_models(self) -> Dict[str, List[str]]:
        """Get available ComfyUI models."""
        try:
            models = {}
            if hasattr(self, '_folder_paths'):
                # Try to get model lists
                try:
                    import os
                    models_dir = getattr(self._folder_paths, 'models_dir', None)
                    if models_dir and os.path.exists(models_dir):
                        for subdir in os.listdir(models_dir):
                            subdir_path = os.path.join(models_dir, subdir)
                            if os.path.isdir(subdir_path):
                                models[subdir] = os.listdir(subdir_path)
                except Exception as e:
                    logger.debug(f"Could not list ComfyUI models: {e}")
            return models
        except Exception as e:
            logger.error(f"Failed to get ComfyUI models: {e}")
            return {}
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get ComfyUI execution queue status."""
        try:
            # This would need access to ComfyUI's execution system
            return {
                "queue_size": 0,
                "running": False,
                "status": "unknown"
            }
        except Exception as e:
            logger.error(f"Failed to get ComfyUI queue status: {e}")
            return {}
    
    # Object manipulation methods (not applicable to ComfyUI)
    
    def delete_objects(self, objects: List[Dict[str, Any]]) -> int:
        """Delete objects - not applicable to ComfyUI workflow system."""
        logger.warning("delete_objects not applicable to ComfyUI - ComfyUI works with node workflows, not scene objects")
        return 0
    
    def duplicate_objects(self, objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Duplicate objects - not applicable to ComfyUI workflow system."""
        logger.warning("duplicate_objects not applicable to ComfyUI - ComfyUI works with node workflows, not scene objects")
        return []
    
    def export_selected(self, path: str, format: str = "fbx") -> bool:
        """Export selected - not applicable to ComfyUI workflow system."""
        logger.warning("export_selected not applicable to ComfyUI - use workflow execution and image saving instead")
        return False
    
    def import_file(self, path: str) -> List[Dict[str, Any]]:
        """Import file - not applicable to ComfyUI workflow system."""
        logger.warning("import_file not applicable to ComfyUI - use LoadImage nodes in workflows instead")
        return []