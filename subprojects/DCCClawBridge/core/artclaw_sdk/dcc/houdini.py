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
    
    def rename_object(self, obj_path: str, new_name: str) -> bool:
        """Rename a Houdini node."""
        try:
            node = self.hou.node(obj_path)
            if node:
                node.setName(new_name)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to rename Houdini node {obj_path}: {e}")
            return False
    
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
    
    def delete_objects(self, objects: List[Dict[str, Any]]) -> int:
        """Delete Houdini nodes."""
        count = 0
        try:
            for obj in objects:
                node_path = obj.get("path", "")
                if not node_path:
                    continue
                
                node = self.hou.node(node_path)
                if node:
                    node.destroy()
                    count += 1
                    
        except Exception as e:
            logger.error(f"Failed to delete Houdini nodes: {e}")
        return count
    
    def duplicate_objects(self, objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Duplicate Houdini nodes."""
        results = []
        try:
            for obj in objects:
                node_path = obj.get("path", "")
                if not node_path:
                    continue
                
                node = self.hou.node(node_path)
                if node and node.parent():
                    # Copy the node within its parent
                    parent = node.parent()
                    new_node = parent.copyItems([node])[0] if parent.copyItems([node]) else None
                    
                    if new_node:
                        results.append({
                            "name": new_node.name(),
                            "path": new_node.path(),
                            "type": new_node.type().name(),
                            "category": new_node.type().category().name() if new_node.type().category() else "unknown"
                        })
                        
        except Exception as e:
            logger.error(f"Failed to duplicate Houdini nodes: {e}")
        return results
    
    def export_selected(self, path: str, format: str = "fbx") -> bool:
        """Export selected Houdini geometry to file."""
        try:
            selected_nodes = self.hou.selectedNodes()
            if not selected_nodes:
                logger.warning("No Houdini nodes selected for export")
                return False
            
            format_lower = format.lower()
            
            # Filter for geometry nodes
            geo_nodes = [node for node in selected_nodes if node.type().name() == "geo"]
            if not geo_nodes:
                logger.warning("No geometry nodes selected for export")
                return False
            
            # For now, export the first geometry node
            geo_node = geo_nodes[0]
            
            if format_lower == "fbx":
                # Create ROP FBX node for export
                rop_context = self.hou.node("/out")
                if not rop_context:
                    rop_context = self.hou.node("/").createNode("obj").createOutputNode("rop_fbx")
                
                fbx_rop = rop_context.createNode("rop_fbx")
                fbx_rop.parm("soppath").set(geo_node.path())
                fbx_rop.parm("sopoutput").set(path)
                fbx_rop.render()
                fbx_rop.destroy()
                
            elif format_lower == "obj":
                # Use geometry ROP
                geo_rop = self.hou.node("/out").createNode("rop_geometry")
                geo_rop.parm("soppath").set(geo_node.path())
                geo_rop.parm("sopoutput").set(path)
                geo_rop.render()
                geo_rop.destroy()
                
            elif format_lower in ("bgeo", "bgeo.sc"):
                # Native Houdini format
                geo_rop = self.hou.node("/out").createNode("rop_geometry")
                geo_rop.parm("soppath").set(geo_node.path())
                geo_rop.parm("sopoutput").set(path)
                geo_rop.render()
                geo_rop.destroy()
                
            else:
                logger.warning(f"Unsupported Houdini export format: {format}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to export from Houdini: {e}")
            return False
    
    def import_file(self, path: str) -> List[Dict[str, Any]]:
        """Import file into Houdini scene."""
        try:
            results = []
            ext = path.lower().rsplit(".", 1)[-1] if "." in path else ""
            
            # Get obj context
            obj_context = self.hou.node("/obj")
            if not obj_context:
                logger.error("Could not access /obj context in Houdini")
                return []
            
            # Create appropriate importer based on file type
            if ext == "fbx":
                # Create FBX import node
                fbx_node = obj_context.createNode("fbx")
                fbx_node.parm("fbxfile").set(path)
                fbx_node.parm("reload").pressButton()
                
                results.append({
                    "name": fbx_node.name(),
                    "path": fbx_node.path(),
                    "type": "fbx",
                    "category": "Object"
                })
                
            elif ext == "obj":
                # Create geometry node with File SOP
                geo_node = obj_context.createNode("geo")
                file_sop = geo_node.createNode("file")
                file_sop.parm("file").set(path)
                
                results.append({
                    "name": geo_node.name(),
                    "path": geo_node.path(),
                    "type": "geo",
                    "category": "Object"
                })
                
            elif ext in ("bgeo", "sc"):
                # Native Houdini geometry
                geo_node = obj_context.createNode("geo")
                file_sop = geo_node.createNode("file")
                file_sop.parm("file").set(path)
                
                results.append({
                    "name": geo_node.name(),
                    "path": geo_node.path(),
                    "type": "geo",
                    "category": "Object"
                })
                
            elif ext == "hip":
                # Merge another Houdini file
                self.hou.hipFile.merge(path)
                # Note: This will merge into existing scene, harder to track new objects
                results.append({
                    "name": "merged_scene",
                    "path": path,
                    "type": "merge",
                    "category": "File"
                })
                
            else:
                # Generic file import via File SOP
                geo_node = obj_context.createNode("geo")
                file_sop = geo_node.createNode("file")
                file_sop.parm("file").set(path)
                
                results.append({
                    "name": geo_node.name(),
                    "path": geo_node.path(),
                    "type": "geo",
                    "category": "Object"
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to import file into Houdini: {e}")
            return []