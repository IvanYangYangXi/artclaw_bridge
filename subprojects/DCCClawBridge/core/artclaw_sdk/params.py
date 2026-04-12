"""
Parameter Parsing API - Parse and validate tool parameters
=========================================================

Handles parameter parsing from tool manifests:
- parse_params(): Parse raw parameters against manifest schema  
- validate_required(): Validate required parameters
- cast_values(): Cast parameter values to correct types
- get_default_values(): Get default values from manifest
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union
from . import logger


def parse_params(
    manifest_inputs: List[Dict[str, Any]], 
    raw_params: Dict[str, Any]
) -> Dict[str, Any]:
    """Parse raw parameters against tool manifest input schema.
    
    Args:
        manifest_inputs: Tool manifest input definitions
        raw_params: Raw parameter values from user/DCC
        
    Returns:
        Parsed and validated parameters with type casting
        
    Raises:
        ValueError: If required parameters are missing or invalid
    """
    if not manifest_inputs:
        return raw_params.copy()
        
    result = {}
    required_missing = []
    
    # Process each input definition
    for input_def in manifest_inputs:
        param_name = input_def.get("name")
        if not param_name:
            continue
            
        param_type = input_def.get("type", "string")
        is_required = input_def.get("required", False)
        default_value = input_def.get("default")
        
        # Check if parameter provided
        if param_name in raw_params:
            raw_value = raw_params[param_name]
            try:
                # Cast value to correct type
                parsed_value = cast_value(raw_value, param_type)
                result[param_name] = parsed_value
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to cast parameter '{param_name}' to {param_type}: {e}")
                # Use raw value if casting fails
                result[param_name] = raw_value
        elif is_required:
            required_missing.append(param_name)
        elif default_value is not None:
            result[param_name] = default_value
    
    # Add any extra parameters not in manifest
    for key, value in raw_params.items():
        if key not in result:
            result[key] = value
            
    # Check for required parameters
    if required_missing:
        raise ValueError(f"Required parameters missing: {', '.join(required_missing)}")
        
    return result


def cast_value(value: Any, target_type: str) -> Any:
    """Cast a value to the specified type.
    
    Args:
        value: Value to cast
        target_type: Target type ('string', 'number', 'boolean', 'array', 'object')
        
    Returns:
        Value cast to target type
        
    Raises:
        ValueError: If casting fails
    """
    if value is None:
        return None
        
    target_type = target_type.lower()
    
    if target_type == "string":
        return str(value)
        
    elif target_type in ("number", "float", "double"):
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                return float(value) if '.' in value else int(value)
            except ValueError:
                raise ValueError(f"Cannot convert '{value}' to number")
        raise ValueError(f"Cannot convert {type(value).__name__} to number")
        
    elif target_type in ("integer", "int"):
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                raise ValueError(f"Cannot convert '{value}' to integer")
        raise ValueError(f"Cannot convert {type(value).__name__} to integer")
        
    elif target_type in ("boolean", "bool"):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on", "enabled")
        if isinstance(value, (int, float)):
            return bool(value)
        return bool(value)
        
    elif target_type == "array":
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                # Try to parse as JSON array
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            # Split comma-separated string
            return [item.strip() for item in value.split(",") if item.strip()]
        if hasattr(value, '__iter__') and not isinstance(value, (str, dict)):
            return list(value)
        return [value]  # Wrap single value
        
    elif target_type == "object":
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Cannot convert {type(value).__name__} to object")
        
    else:
        # Unknown type, return as-is
        logger.warning(f"Unknown parameter type '{target_type}', returning value as-is")
        return value


def validate_required(
    params: Dict[str, Any], 
    required_params: List[str]
) -> List[str]:
    """Validate that required parameters are present.
    
    Args:
        params: Parameter dictionary
        required_params: List of required parameter names
        
    Returns:
        List of missing required parameter names
    """
    missing = []
    
    for param_name in required_params:
        if param_name not in params or params[param_name] is None:
            missing.append(param_name)
            
    return missing


def get_default_values(manifest_inputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract default values from manifest input definitions.
    
    Args:
        manifest_inputs: Tool manifest input definitions
        
    Returns:
        Dictionary of parameter names to default values
    """
    defaults = {}
    
    for input_def in manifest_inputs:
        param_name = input_def.get("name")
        default_value = input_def.get("default")
        
        if param_name and default_value is not None:
            defaults[param_name] = default_value
            
    return defaults


def merge_with_defaults(
    params: Dict[str, Any],
    manifest_inputs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Merge parameters with default values from manifest.
    
    Args:
        params: User-provided parameters
        manifest_inputs: Tool manifest input definitions
        
    Returns:
        Parameters merged with defaults
    """
    defaults = get_default_values(manifest_inputs)
    
    # Start with defaults, override with provided params
    result = defaults.copy()
    result.update(params)
    
    return result


def normalize_param_names(params: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize parameter names (convert to lowercase, replace spaces/dashes).
    
    Args:
        params: Parameter dictionary
        
    Returns:
        Dictionary with normalized parameter names
    """
    normalized = {}
    
    for key, value in params.items():
        # Convert to lowercase, replace spaces and dashes with underscores
        normalized_key = key.lower().replace(" ", "_").replace("-", "_")
        normalized[normalized_key] = value
        
    return normalized