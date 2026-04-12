"""
Substance Designer Adapter for ArtClaw SDK
==========================================

Implements DCC backend interface for Adobe Substance Designer using sd module.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional

from .base import BaseDCCBackend
from .. import logger


class SubstanceDesignerAdapter(BaseDCCBackend):
    """Substance Designer DCC backend adapter."""
    
    def __init__(self):
        super().__init__()
        self.dcc_name = "substance_designer"
        try:
            import sd
            from sd.api.sdapplication import SDApplication
            from sd.api.sdgraph import SDGraph
            from sd.api.sdpackage import SDPackage
            
            self.sd = sd
            self.app = SDApplication.get_instance()
            self.SDGraph = SDGraph
            self.SDPackage = SDPackage
            
            # Try to get version
            try:
                self.dcc_version = str(self.app.getVersion())
            except:
                self.dcc_version = "unknown"
                
        except ImportError:
            raise RuntimeError("Substance Designer SDK not available - not running in SD environment")
    
    def get_dcc_name(self) -> str:
        return self.dcc_name
    
    def get_dcc_version(self) -> str:
        return self.dcc_version
    
    def get_context(self) -> Dict[str, Any]:
        """Get complete Substance Designer context."""
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
        """Get currently selected nodes/graphs in Substance Designer."""
        try:
            result = []
            
            # Try to get current package and graphs
            current_package = self.app.getCurrentPackage()
            if current_package:
                graphs = current_package.getChildrenOfType(self.SDGraph)
                
                for graph in graphs:
                    try:
                        # Get selection within each graph
                        selection = graph.getSelection()
                        
                        for node in selection:
                            node_info = {
                                "name": node.getIdentifier(),
                                "type": "node",
                                "graph": graph.getIdentifier(),
                                "class": node.getDefinition().getId() if node.getDefinition() else "unknown"
                            }
                            
                            # Get node position if available
                            try:
                                pos = node.getPosition()
                                node_info["position"] = [pos.x, pos.y]
                            except:
                                pass
                            
                            result.append(node_info)
                            
                    except Exception as e:
                        logger.debug(f"Could not get selection from SD graph {graph}: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get Substance Designer selection: {e}")
            return []
    
    def get_scene_path(self) -> Optional[str]:
        """Get current Substance Designer package file path."""
        try:
            current_package = self.app.getCurrentPackage()
            if current_package:
                file_path = current_package.getFilePath()
                return file_path if file_path else None
            return None
        except Exception as e:
            logger.error(f"Failed to get SD scene path: {e}")
            return None
    
    def get_scene_info(self) -> Dict[str, Any]:
        """Get Substance Designer package information."""
        try:
            current_package = self.app.getCurrentPackage()
            if not current_package:
                return {}
            
            # Count different resource types
            graphs = current_package.getChildrenOfType(self.SDGraph)
            
            graph_info = []
            total_nodes = 0
            
            for graph in graphs:
                try:
                    nodes = graph.getNodes()
                    node_count = len(nodes)
                    total_nodes += node_count
                    
                    graph_info.append({
                        "name": graph.getIdentifier(),
                        "node_count": node_count,
                        "type": "graph"
                    })
                except Exception as e:
                    logger.debug(f"Could not analyze SD graph {graph}: {e}")
            
            return {
                "package_file": self.get_scene_path() or "untitled.sbs",
                "package_name": current_package.getIdentifier(),
                "graphs": len(graphs),
                "graph_details": graph_info,
                "total_nodes": total_nodes,
                "is_dirty": current_package.isDirty() if hasattr(current_package, 'isDirty') else False
            }
            
        except Exception as e:
            logger.error(f"Failed to get SD scene info: {e}")
            return {}
    
    def get_viewport_info(self) -> Dict[str, Any]:
        """Get Substance Designer viewport info."""
        try:
            # SD has 2D graph view and 3D preview
            return {
                "type": "2d_graph_view",
                "has_3d_preview": True,
                "viewport_type": "node_graph"
            }
        except Exception as e:
            logger.debug(f"Could not get SD viewport info: {e}")
            return {}
    
    def rename_object(self, obj_identifier: str, new_name: str) -> bool:
        """Rename a Substance Designer node or graph."""
        try:
            current_package = self.app.getCurrentPackage()
            if not current_package:
                return False
            
            # Try to find and rename node in any graph
            graphs = current_package.getChildrenOfType(self.SDGraph)
            
            for graph in graphs:
                try:
                    nodes = graph.getNodes()
                    for node in nodes:
                        if node.getIdentifier() == obj_identifier:
                            node.setIdentifier(new_name)
                            return True
                except Exception:
                    continue
            
            # Try to rename graph itself
            for graph in graphs:
                if graph.getIdentifier() == obj_identifier:
                    graph.setIdentifier(new_name)
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to rename SD object {obj_identifier}: {e}")
            return False
    
    def execute_on_main_thread(self, func, *args, **kwargs) -> Any:
        """Execute on Substance Designer main thread."""
        # SD Python API typically runs on main thread
        return func(*args, **kwargs)
    
    def is_main_thread(self) -> bool:
        """SD Python typically runs on main thread."""
        return True
    
    # Substance Designer-specific methods
    
    def get_current_graph(self):
        """Get currently active graph."""
        try:
            current_package = self.app.getCurrentPackage()
            if current_package:
                # Try to get active/focused graph
                graphs = current_package.getChildrenOfType(self.SDGraph)
                if graphs:
                    return graphs[0]  # Return first graph as fallback
            return None
        except Exception as e:
            logger.error(f"Failed to get current SD graph: {e}")
            return None
    
    def compute_graph(self, graph=None) -> bool:
        """Compute/cook a graph."""
        try:
            if graph is None:
                graph = self.get_current_graph()
            
            if graph:
                graph.compute()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to compute SD graph: {e}")
            return False
    
    def get_graph_outputs(self, graph=None) -> List[Dict[str, Any]]:
        """Get outputs from a graph."""
        try:
            if graph is None:
                graph = self.get_current_graph()
            
            if not graph:
                return []
            
            outputs = []
            output_nodes = graph.getOutputNodes()
            
            for output_node in output_nodes:
                try:
                    outputs.append({
                        "name": output_node.getIdentifier(),
                        "type": "output",
                        "usage": output_node.getAnnotationPropertyValueFromId("usage") if hasattr(output_node, 'getAnnotationPropertyValueFromId') else "unknown"
                    })
                except Exception:
                    continue
            
            return outputs
            
        except Exception as e:
            logger.error(f"Failed to get SD graph outputs: {e}")
            return []
    
    # Object manipulation methods (limited applicability to SD)
    
    def delete_objects(self, objects: List[Dict[str, Any]]) -> int:
        """Delete objects - limited to nodes and graphs in SD context."""
        logger.warning("delete_objects limited in Substance Designer - only applies to graph nodes")
        return 0
    
    def duplicate_objects(self, objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Duplicate objects - limited to nodes in SD context."""
        logger.warning("duplicate_objects limited in Substance Designer - only applies to graph nodes")
        return []
    
    def export_selected(self, path: str, format: str = "fbx") -> bool:
        """Export selected - not applicable to SD node graph workflow."""
        logger.warning("export_selected not applicable to Substance Designer - use substance/texture export instead")
        return False
    
    def import_file(self, path: str) -> List[Dict[str, Any]]:
        """Import file - limited to substance/resource imports in SD."""
        logger.warning("import_file limited in Substance Designer - use resource import instead")
        return []