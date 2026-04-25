"""
Result Reporting API - Report tool execution results
===================================================

Provides standardized result reporting for tools:
- success(): Report successful completion with data
- fail(): Report failure with error details
- allow(): Allow pre-event to continue (for triggers)
- reject(): Block pre-event from continuing (for triggers)
"""
from __future__ import annotations

import sys
from typing import Any, Dict, Optional
from . import logger


def success(data: Any = None, message: Optional[str] = None) -> Dict[str, Any]:
    """Report successful tool execution.
    
    Args:
        data: Result data to return
        message: Optional success message
        
    Returns:
        Standardized success result dictionary
    """
    result = {
        "success": True,
        "data": data,
        "error": None
    }
    
    if message:
        result["message"] = message
        logger.info(f"Tool success: {message}")
        
    return result


def fail(error: Optional[str] = None, message: Optional[str] = None, data: Any = None) -> Dict[str, Any]:
    """Report tool execution failure.
    
    Args:
        error: Error description or exception message
        message: Optional failure message  
        data: Optional partial data/context
        
    Returns:
        Standardized failure result dictionary
    """
    result = {
        "success": False,
        "data": data,
        "error": error or "Tool execution failed"
    }
    
    if message:
        result["message"] = message
        
    error_msg = message or error or "Unknown error"
    logger.error(f"Tool failure: {error_msg}")
        
    return result


def allow(message: Optional[str] = None, data: Any = None) -> Dict[str, Any]:
    """Allow a pre-event to continue (for trigger rules).
    
    Args:
        message: Optional message explaining why event is allowed
        data: Optional context data
        
    Returns:
        Result indicating event should proceed
    """
    result = {
        "action": "allow",
        "data": data
    }
    
    if message:
        result["message"] = message
        logger.info(f"Event allowed: {message}")
        
    return result


def reject(reason: Optional[str] = None, data: Any = None) -> Dict[str, Any]:
    """Block a pre-event from continuing (for trigger rules).
    
    Args:
        reason: Reason why event is blocked
        data: Optional context data
        
    Returns:
        Result indicating event should be blocked
    """
    result = {
        "action": "reject", 
        "data": data
    }
    
    if reason:
        result["reason"] = reason
        logger.warning(f"Event rejected: {reason}")
    else:
        result["reason"] = "Event blocked by trigger rule"
        
    return result


def partial(data: Any = None, message: Optional[str] = None, progress: Optional[float] = None) -> Dict[str, Any]:
    """Report partial completion (for long-running tools).
    
    Args:
        data: Partial result data
        message: Progress message
        progress: Progress percentage (0.0-1.0)
        
    Returns:
        Partial result dictionary
    """
    result = {
        "status": "partial",
        "data": data
    }
    
    if message:
        result["message"] = message
        
    if progress is not None:
        result["progress"] = max(0.0, min(1.0, progress))
        
    return result


def from_exception(exc: Exception, message: Optional[str] = None) -> Dict[str, Any]:
    """Create failure result from an exception.
    
    Args:
        exc: Exception that occurred
        message: Optional context message
        
    Returns:
        Failure result with exception details
    """
    error_type = type(exc).__name__
    error_msg = str(exc)
    
    if message:
        full_message = f"{message}: {error_type}: {error_msg}"
    else:
        full_message = f"{error_type}: {error_msg}"
    
    return fail(error=full_message)


def validate_result(result: Dict[str, Any]) -> bool:
    """Validate that a result dictionary has the expected format.
    
    Args:
        result: Result dictionary to validate
        
    Returns:
        True if result format is valid
    """
    if not isinstance(result, dict):
        return False
        
    # Check for success/failure format
    if "success" in result:
        return isinstance(result["success"], bool)
        
    # Check for action format (allow/reject)  
    if "action" in result:
        return result["action"] in ("allow", "reject")
        
    # Check for partial status
    if "status" in result:
        return result["status"] == "partial"
        
    return False


class ToolResult:
    """Tool result context manager for automatic error handling."""
    
    def __init__(self, tool_name: str = ""):
        self.tool_name = tool_name
        self.result = None
    
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Exception occurred, create failure result
            self.result = from_exception(exc_val, f"Tool '{self.tool_name}' failed")
            logger.error(f"Tool '{self.tool_name}' failed with {exc_type.__name__}: {exc_val}")
            return True  # Suppress exception
    
    def set_success(self, data: Any = None, message: Optional[str] = None):
        """Set successful result."""
        self.result = success(data, message)
    
    def set_failure(self, error: Optional[str] = None, message: Optional[str] = None):
        """Set failure result."""
        self.result = fail(error, message)
    
    def get_result(self) -> Dict[str, Any]:
        """Get the final result."""
        if self.result is None:
            return success(message="Tool completed successfully")
        return self.result


def print_result(result: Dict[str, Any]) -> None:
    """Print result in a human-readable format.
    
    Args:
        result: Result dictionary to print
    """
    if result.get("success") is True:
        print("✅ SUCCESS", end="")
        if "message" in result:
            print(f": {result['message']}", end="")
        if "data" in result and result["data"] is not None:
            print(f" | Data: {result['data']}")
        else:
            print()
            
    elif result.get("success") is False:
        print("❌ FAILURE", end="")  
        if "error" in result:
            print(f": {result['error']}", end="")
        if "message" in result:
            print(f" | {result['message']}")
        else:
            print()
            
    elif result.get("action") == "allow":
        print("✅ ALLOWED", end="")
        if "message" in result:
            print(f": {result['message']}")
        else:
            print()
            
    elif result.get("action") == "reject":
        print("🚫 REJECTED", end="")
        if "reason" in result:
            print(f": {result['reason']}")
        else:
            print()
            
    else:
        print(f"📊 RESULT: {result}")


# error 别名（兼容 sdk.result.error() 调用方式）
error = fail