"""
Object Filtering API - Filter and query objects by criteria
==========================================================

Provides unified object filtering across DCC environments:
- filter_objects(): Filter by type, name patterns, path patterns
- filter_by_type(): Filter by object type
- filter_by_name(): Filter by name patterns (regex/wildcard)
- filter_by_path(): Filter by path patterns
"""
from __future__ import annotations

import re
import fnmatch
from typing import Any, Dict, List, Optional, Union
from . import logger


def filter_objects(
    objects: List[Dict[str, Any]], 
    type: Optional[Union[str, List[str]]] = None,
    type_filter: Optional[Union[str, List[str]]] = None,
    name_pattern: Optional[str] = None,
    path_pattern: Optional[str] = None,
    use_regex: bool = True,
    **kwargs,
) -> List[Dict[str, Any]]:
    """Filter objects by multiple criteria.
    
    Args:
        objects: List of object dictionaries to filter
        type: Object type(s) to match (str or list). Alias for type_filter.
        type_filter: Object type(s) to match (str or list)
        name_pattern: Name pattern to match (regex by default, set use_regex=False for wildcard)
        path_pattern: Path pattern to match (regex by default, set use_regex=False for wildcard)
        use_regex: Whether patterns are regex (default: True)
        
    Returns:
        Filtered list of objects matching all criteria
    """
    if not objects:
        return []
    
    # Accept both `type` and `type_filter` as parameter name
    effective_type = type or type_filter
        
    result = objects[:]
    
    # Filter by type
    if effective_type:
        result = filter_by_type(result, effective_type)
    
    # Filter by name pattern  
    if name_pattern:
        result = filter_by_name(result, name_pattern, use_regex)
    
    # Filter by path pattern
    if path_pattern:
        result = filter_by_path(result, path_pattern, use_regex)
        
    return result


def filter_by_type(
    objects: List[Dict[str, Any]], 
    type_filter: Union[str, List[str]]
) -> List[Dict[str, Any]]:
    """Filter objects by type.
    
    Args:
        objects: List of object dictionaries
        type_filter: Object type(s) to match
        
    Returns:
        Objects matching the specified type(s)
    """
    if not objects:
        return []
        
    # Normalize to list
    if isinstance(type_filter, str):
        type_filter = [type_filter]
        
    # Case-insensitive type matching
    type_filter_lower = [t.lower() for t in type_filter]
    
    result = []
    for obj in objects:
        obj_type = obj.get("type", "").lower()
        if obj_type in type_filter_lower:
            result.append(obj)
            
    return result


def filter_by_name(
    objects: List[Dict[str, Any]],
    name_pattern: str,
    use_regex: bool = False
) -> List[Dict[str, Any]]:
    """Filter objects by name pattern.
    
    Args:
        objects: List of object dictionaries
        name_pattern: Pattern to match against object names
        use_regex: Whether pattern is regex (default: wildcard)
        
    Returns:
        Objects with names matching the pattern
    """
    if not objects or not name_pattern:
        return objects
        
    result = []
    
    if use_regex:
        try:
            pattern = re.compile(name_pattern, re.IGNORECASE)
        except re.error as e:
            logger.error(f"Invalid regex pattern '{name_pattern}': {e}")
            return objects
            
        for obj in objects:
            name = obj.get("name", "")
            if pattern.search(name):
                result.append(obj)
    else:
        # Use fnmatch for wildcard patterns
        for obj in objects:
            name = obj.get("name", "")
            if fnmatch.fnmatch(name.lower(), name_pattern.lower()):
                result.append(obj)
                
    return result


def filter_by_path(
    objects: List[Dict[str, Any]],
    path_pattern: str, 
    use_regex: bool = False
) -> List[Dict[str, Any]]:
    """Filter objects by path pattern.
    
    Args:
        objects: List of object dictionaries
        path_pattern: Pattern to match against object paths
        use_regex: Whether pattern is regex (default: wildcard)
        
    Returns:
        Objects with paths matching the pattern
    """
    if not objects or not path_pattern:
        return objects
        
    result = []
    
    if use_regex:
        try:
            pattern = re.compile(path_pattern, re.IGNORECASE)
        except re.error as e:
            logger.error(f"Invalid regex pattern '{path_pattern}': {e}")
            return objects
            
        for obj in objects:
            # Check both long_name and path fields
            path = obj.get("long_name") or obj.get("path", "")
            if pattern.search(path):
                result.append(obj)
    else:
        # Use fnmatch for wildcard patterns
        for obj in objects:
            path = obj.get("long_name") or obj.get("path", "")
            if fnmatch.fnmatch(path.lower(), path_pattern.lower()):
                result.append(obj)
                
    return result


def find_objects_by_name(
    objects: List[Dict[str, Any]], 
    name: str, 
    exact_match: bool = False
) -> List[Dict[str, Any]]:
    """Find objects by name (exact or partial match).
    
    Args:
        objects: List of object dictionaries
        name: Name to search for
        exact_match: Whether to require exact match (default: partial)
        
    Returns:
        Objects with matching names
    """
    if not objects or not name:
        return []
        
    result = []
    name_lower = name.lower()
    
    for obj in objects:
        obj_name = obj.get("name", "").lower()
        
        if exact_match:
            if obj_name == name_lower:
                result.append(obj)
        else:
            if name_lower in obj_name:
                result.append(obj)
                
    return result


def group_by_type(objects: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group objects by their type.
    
    Args:
        objects: List of object dictionaries
        
    Returns:
        Dictionary mapping object types to lists of objects
    """
    if not objects:
        return {}
        
    groups = {}
    
    for obj in objects:
        obj_type = obj.get("type", "unknown")
        if obj_type not in groups:
            groups[obj_type] = []
        groups[obj_type].append(obj)
        
    return groups