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
    def get_selected_assets(self) -> List[Dict[str, Any]]:
        """获取资源管理器中选中的资产。
        UE: Content Browser 选中的资产。
        其他 DCC: 如无资源管理器对接，返回空列表。"""
        pass

    @abstractmethod
    def get_selected_objects(self) -> List[Dict[str, Any]]:
        """获取场景/视口中选中的对象。"""
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
    
    # ── Object Filtering ──
    
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