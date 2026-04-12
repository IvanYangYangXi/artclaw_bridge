"""
Base DCC Backend Interface  
==========================

Abstract interface that all DCC backends must implement.
Provides unified API for context queries, object manipulation,
and viewport operations across different DCC applications.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseDCCBackend(ABC):
    """Abstract base class for DCC-specific backends."""
    
    def __init__(self):
        self.dcc_name = "unknown"
        self.dcc_version = "unknown"
    
    # ── Basic Information ──
    
    @abstractmethod
    def get_dcc_name(self) -> str:
        """Get DCC application name (e.g., 'maya', 'ue', 'max')."""
        pass
    
    @abstractmethod  
    def get_dcc_version(self) -> str:
        """Get DCC application version."""
        pass
    
    # ── Context Queries ──
    
    @abstractmethod
    def get_context(self) -> Dict[str, Any]:
        """Get complete DCC context information."""
        pass
    
    @abstractmethod
    def get_selected(self) -> List[Dict[str, Any]]:
        """Get currently selected objects."""
        pass
    
    @abstractmethod
    def get_scene_path(self) -> Optional[str]:
        """Get current scene/file path."""
        pass
    
    @abstractmethod
    def get_scene_info(self) -> Dict[str, Any]:
        """Get scene metadata and statistics."""
        pass
    
    def get_viewport_info(self) -> Dict[str, Any]:
        """Get viewport/camera state (optional, not all DCCs support this)."""
        return {}
    
    # ── Object Operations ──
    
    def rename_object(self, obj_id: str, new_name: str) -> bool:
        """Rename an object (optional, not all DCCs support this).
        
        Args:
            obj_id: Object identifier  
            new_name: New object name
            
        Returns:
            True if successful
        """
        return False
    
    def filter_objects(
        self, 
        objects: List[Dict[str, Any]], 
        **criteria
    ) -> List[Dict[str, Any]]:
        """Filter objects by criteria (delegated to filters module by default).
        
        Args:
            objects: List of objects to filter
            **criteria: Filter criteria (type, name_pattern, etc.)
            
        Returns:
            Filtered list of objects
        """
        # Import here to avoid circular imports
        from .. import filters
        return filters.filter_objects(objects, **criteria)
    
    # ── Thread Safety ──
    
    def execute_on_main_thread(self, func, *args, **kwargs) -> Any:
        """Execute function on DCC main thread (if required).
        
        Default implementation just calls the function directly.
        Override for DCCs that require main thread execution.
        """
        return func(*args, **kwargs)
    
    def is_main_thread(self) -> bool:
        """Check if currently on DCC main thread.
        
        Returns:
            True if on main thread (default assumes yes)
        """
        return True
    
    # ── Additional Object Operations ──
    
    def delete_objects(self, objects: List[Dict[str, Any]]) -> int:
        """Delete objects from the scene.
        
        Args:
            objects: List of object dictionaries to delete
            
        Returns:
            Number of objects successfully deleted
        """
        return 0
    
    def duplicate_objects(self, objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Duplicate objects in the scene.
        
        Args:
            objects: List of object dictionaries to duplicate
            
        Returns:
            List of newly created object dictionaries
        """
        return []
    
    def export_selected(self, path: str, format: str = "fbx") -> bool:
        """Export selected objects to file.
        
        Args:
            path: Output file path
            format: Export format (fbx, obj, etc.)
            
        Returns:
            True if export was successful
        """
        return False
    
    def import_file(self, path: str) -> List[Dict[str, Any]]:
        """Import file into scene.
        
        Args:
            path: Path to file to import
            
        Returns:
            List of imported object dictionaries
        """
        return []