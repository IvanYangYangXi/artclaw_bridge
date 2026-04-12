"""
Progress Reporting API - Report tool execution progress  
======================================================

Provides progress reporting for long-running tools:
- start(): Initialize progress tracking
- update(): Update progress with current status
- finish(): Complete progress tracking
- set_total(): Update total work units
"""
from __future__ import annotations

import time
import threading
from typing import Optional
from . import logger

# Global progress state (thread-local for safety)
_progress_data = threading.local()


def _get_progress_state():
    """Get thread-local progress state."""
    if not hasattr(_progress_data, 'state'):
        _progress_data.state = {
            'active': False,
            'total': 0,
            'current': 0,
            'start_time': None,
            'last_update': None,
            'message': '',
            'tool_manager_url': 'http://localhost:9876'
        }
    return _progress_data.state


def start(total: int = 100, message: Optional[str] = None) -> None:
    """Initialize progress tracking.
    
    Args:
        total: Total number of work units
        message: Initial progress message
    """
    state = _get_progress_state()
    
    state['active'] = True
    state['total'] = max(1, total)  # Ensure total is at least 1
    state['current'] = 0
    state['start_time'] = time.time()
    state['last_update'] = state['start_time']
    state['message'] = message or 'Starting...'
    
    logger.info(f"Progress started: {state['message']} (0/{total})")
    _send_progress_update()


def update(current: int, message: Optional[str] = None) -> None:
    """Update progress with current status.
    
    Args:
        current: Current number of completed work units
        message: Progress message
    """
    state = _get_progress_state()
    
    if not state['active']:
        logger.warning("Progress update called but progress not started")
        return
        
    state['current'] = max(0, min(current, state['total']))
    state['last_update'] = time.time()
    
    if message:
        state['message'] = message
    
    percentage = (state['current'] / state['total']) * 100
    logger.info(f"Progress: {state['current']}/{state['total']} ({percentage:.1f}%) - {state['message']}")
    
    _send_progress_update()


def finish(message: Optional[str] = None) -> None:
    """Complete progress tracking.
    
    Args:
        message: Final completion message
    """
    state = _get_progress_state()
    
    if not state['active']:
        return
        
    state['current'] = state['total']
    state['message'] = message or 'Completed'
    
    elapsed = time.time() - state['start_time']
    logger.info(f"Progress finished: {state['message']} (completed in {elapsed:.1f}s)")
    
    _send_progress_update()
    
    # Reset state
    state['active'] = False


def set_total(total: int) -> None:
    """Update total number of work units.
    
    Args:
        total: New total number of work units
    """
    state = _get_progress_state()
    
    if not state['active']:
        logger.warning("set_total called but progress not started")
        return
        
    old_total = state['total']
    state['total'] = max(1, total)
    
    logger.info(f"Progress total updated: {old_total} -> {state['total']}")
    
    _send_progress_update()


def get_progress() -> dict:
    """Get current progress information.
    
    Returns:
        Dictionary with current progress state
    """
    state = _get_progress_state()
    
    if not state['active']:
        return {'active': False}
        
    elapsed = time.time() - state['start_time']
    percentage = (state['current'] / state['total']) * 100
    
    # Calculate ETA
    eta = None
    if state['current'] > 0 and percentage < 100:
        rate = state['current'] / elapsed
        remaining = state['total'] - state['current']
        eta = remaining / rate if rate > 0 else None
    
    return {
        'active': True,
        'current': state['current'],
        'total': state['total'],
        'percentage': percentage,
        'message': state['message'],
        'elapsed': elapsed,
        'eta': eta
    }


def increment(amount: int = 1, message: Optional[str] = None) -> None:
    """Increment progress by a specified amount.
    
    Args:
        amount: Amount to increment by
        message: Progress message
    """
    state = _get_progress_state()
    
    if not state['active']:
        logger.warning("increment called but progress not started")
        return
        
    new_current = state['current'] + amount
    update(new_current, message)


def set_progress(percentage: float, message: Optional[str] = None) -> None:
    """Set progress by percentage (0.0 - 1.0).
    
    Args:
        percentage: Progress percentage (0.0 - 1.0)
        message: Progress message
    """
    state = _get_progress_state()
    
    if not state['active']:
        logger.warning("set_progress called but progress not started")
        return
        
    percentage = max(0.0, min(1.0, percentage))
    current = int(percentage * state['total'])
    
    update(current, message)


def _send_progress_update() -> None:
    """Send progress update to Tool Manager (if available)."""
    try:
        import requests
        state = _get_progress_state()
        
        progress_data = get_progress()
        
        # Send HTTP request to Tool Manager
        response = requests.post(
            f"{state['tool_manager_url']}/api/v1/progress",
            json=progress_data,
            timeout=1.0  # Quick timeout to avoid blocking
        )
        
        if response.status_code != 200:
            logger.debug(f"Progress update failed: {response.status_code}")
            
    except Exception as e:
        # Don't log errors for progress updates to avoid spam
        # Progress reporting is best-effort
        pass


def set_tool_manager_url(url: str) -> None:
    """Set Tool Manager URL for progress reporting.
    
    Args:
        url: Tool Manager base URL
    """
    state = _get_progress_state()
    state['tool_manager_url'] = url


class ProgressContext:
    """Context manager for automatic progress tracking."""
    
    def __init__(self, total: int = 100, message: Optional[str] = None):
        self.total = total
        self.initial_message = message
        
    def __enter__(self):
        start(self.total, self.initial_message)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            finish(f"Failed: {exc_val}")
        else:
            finish("Completed successfully")
            
    def update(self, current: int, message: Optional[str] = None):
        """Update progress within context."""
        update(current, message)
        
    def increment(self, amount: int = 1, message: Optional[str] = None):
        """Increment progress within context."""
        increment(amount, message)


def progress_decorator(total: int = 100, message: Optional[str] = None):
    """Decorator to automatically add progress tracking to functions.
    
    Args:
        total: Total work units (function should call progress.update())
        message: Initial message
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with ProgressContext(total, message):
                return func(*args, **kwargs)
        return wrapper
    return decorator