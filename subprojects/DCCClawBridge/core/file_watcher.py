"""
File Watcher - Monitor file system events and forward to DCCEventManager
=======================================================================

Monitors configured directories for file system changes and forwards
relevant events to the DCCEventManager for trigger evaluation.

Uses the watchdog library for cross-platform file monitoring with
debouncing to prevent spam from rapid file changes.
"""
from __future__ import annotations

import logging
import os
import time
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = None
    FileSystemEvent = None

logger = logging.getLogger("artclaw.filewatcher")


class DebouncedFileHandler(FileSystemEventHandler):
    """File system event handler with debouncing to prevent rapid-fire events."""
    
    def __init__(self, callback: Callable[[str, str, Dict[str, Any]], None], debounce_ms: int = 500):
        """
        Initialize debounced handler.
        
        Args:
            callback: Function to call with (event_type, path, event_data)
            debounce_ms: Debounce delay in milliseconds
        """
        self.callback = callback
        self.debounce_delay = debounce_ms / 1000.0  # Convert to seconds
        self.pending_events: Dict[str, threading.Timer] = {}
        self.lock = threading.RLock()
    
    def _debounced_callback(self, event_type: str, path: str, event_data: Dict[str, Any]):
        """Execute callback after debounce delay."""
        with self.lock:
            # Remove from pending events
            self.pending_events.pop(path, None)
        
        try:
            self.callback(event_type, path, event_data)
        except Exception as e:
            logger.error(f"Error in file watcher callback: {e}")
    
    def _schedule_event(self, event_type: str, path: str, event_data: Dict[str, Any]):
        """Schedule a debounced event."""
        with self.lock:
            # Cancel existing timer for this path
            existing_timer = self.pending_events.get(path)
            if existing_timer:
                existing_timer.cancel()
            
            # Schedule new timer
            timer = threading.Timer(
                self.debounce_delay,
                self._debounced_callback,
                args=(event_type, path, event_data)
            )
            self.pending_events[path] = timer
            timer.start()
    
    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events."""
        if event.is_directory:
            return
            
        self._schedule_event(
            "file.modified",
            event.src_path,
            {
                "path": event.src_path,
                "is_directory": event.is_directory,
                "event_type": "modified"
            }
        )
    
    def on_created(self, event: FileSystemEvent):
        """Handle file creation events.""" 
        self._schedule_event(
            "file.created",
            event.src_path,
            {
                "path": event.src_path,
                "is_directory": event.is_directory,
                "event_type": "created"
            }
        )
    
    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion events."""
        self._schedule_event(
            "file.deleted", 
            event.src_path,
            {
                "path": event.src_path,
                "is_directory": event.is_directory,
                "event_type": "deleted"
            }
        )
    
    def on_moved(self, event: FileSystemEvent):
        """Handle file move/rename events."""
        if hasattr(event, 'dest_path'):
            self._schedule_event(
                "file.moved",
                event.src_path,
                {
                    "src_path": event.src_path,
                    "dest_path": event.dest_path,
                    "is_directory": event.is_directory,
                    "event_type": "moved"
                }
            )


class FileWatcher:
    """File system watcher that forwards events to DCCEventManager."""
    
    def __init__(self, event_manager, debounce_ms: int = 500):
        """
        Initialize file watcher.
        
        Args:
            event_manager: DCCEventManager instance to forward events to
            debounce_ms: Debounce delay in milliseconds (default 500ms)
        """
        if not WATCHDOG_AVAILABLE:
            raise RuntimeError("watchdog library not available - install with: pip install watchdog")
        
        self.event_manager = event_manager
        self.debounce_ms = debounce_ms
        self.observer = Observer()
        self.watched_paths: Dict[str, Any] = {}  # path -> watch handle mapping
        self.file_filters: Set[str] = set()  # File extensions to watch
        self.is_running = False
        
        # Create file event handler
        self.file_handler = DebouncedFileHandler(
            self._on_file_event,
            debounce_ms
        )
    
    def add_watch_path(self, path: str, recursive: bool = True, filters: Optional[List[str]] = None) -> bool:
        """
        Add a directory path to watch.
        
        Args:
            path: Directory path to watch
            recursive: Whether to watch subdirectories
            filters: File extensions to filter (e.g., ['.ma', '.mb', '.fbx'])
            
        Returns:
            True if watch was added successfully
        """
        try:
            abs_path = os.path.abspath(path)
            
            if not os.path.exists(abs_path):
                logger.warning(f"Watch path does not exist: {abs_path}")
                return False
            
            if not os.path.isdir(abs_path):
                logger.warning(f"Watch path is not a directory: {abs_path}")
                return False
            
            # Add file filters
            if filters:
                self.file_filters.update(ext.lower() for ext in filters)
            
            # Add watch to observer
            watch = self.observer.schedule(
                self.file_handler,
                abs_path,
                recursive=recursive
            )
            
            self.watched_paths[abs_path] = watch
            logger.info(f"Added file watch: {abs_path} (recursive={recursive})")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to add watch path {path}: {e}")
            return False
    
    def remove_watch_path(self, path: str) -> bool:
        """
        Remove a watch path.
        
        Args:
            path: Directory path to stop watching
            
        Returns:
            True if watch was removed successfully
        """
        try:
            abs_path = os.path.abspath(path)
            watch = self.watched_paths.get(abs_path)
            
            if watch:
                self.observer.unschedule(watch)
                del self.watched_paths[abs_path]
                logger.info(f"Removed file watch: {abs_path}")
                return True
            else:
                logger.warning(f"No watch found for path: {abs_path}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to remove watch path {path}: {e}")
            return False
    
    def start(self) -> bool:
        """
        Start file watching.
        
        Returns:
            True if started successfully
        """
        try:
            if self.is_running:
                logger.warning("File watcher already running")
                return True
            
            if not self.watched_paths:
                logger.warning("No paths to watch - add paths before starting")
                return False
            
            self.observer.start()
            self.is_running = True
            
            logger.info(f"File watcher started, monitoring {len(self.watched_paths)} paths")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start file watcher: {e}")
            return False
    
    def stop(self) -> None:
        """Stop file watching."""
        try:
            if not self.is_running:
                return
            
            self.observer.stop()
            self.observer.join(timeout=5.0)  # Wait up to 5 seconds
            self.is_running = False
            
            logger.info("File watcher stopped")
            
        except Exception as e:
            logger.error(f"Error stopping file watcher: {e}")
    
    def _on_file_event(self, event_type: str, path: str, event_data: Dict[str, Any]) -> None:
        """
        Handle a file system event.
        
        Args:
            event_type: Type of file event
            path: File path that changed
            event_data: Additional event data
        """
        try:
            # Apply file filters if configured
            if self.file_filters:
                file_ext = Path(path).suffix.lower()
                if file_ext not in self.file_filters:
                    return  # Skip files that don't match filters
            
            # Add file system context
            event_data.update({
                "file_size": os.path.getsize(path) if os.path.exists(path) else 0,
                "timestamp": time.time(),
                "absolute_path": os.path.abspath(path),
                "file_extension": Path(path).suffix.lower(),
                "file_name": Path(path).name
            })
            
            # Forward to event manager
            self.event_manager._on_event(event_type, "post", event_data)
            
        except Exception as e:
            logger.error(f"Error processing file event {event_type} for {path}: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get file watcher status.
        
        Returns:
            Dictionary with status information
        """
        return {
            "running": self.is_running,
            "watched_paths": len(self.watched_paths),
            "paths": list(self.watched_paths.keys()),
            "file_filters": list(self.file_filters),
            "debounce_ms": self.debounce_ms,
            "observer_alive": self.observer.is_alive() if self.is_running else False
        }


def create_project_file_watcher(event_manager, project_paths: List[str]) -> Optional[FileWatcher]:
    """
    Create a file watcher configured for common DCC project files.
    
    Args:
        event_manager: DCCEventManager instance
        project_paths: List of project directory paths to watch
        
    Returns:
        FileWatcher instance or None if creation failed
    """
    try:
        if not WATCHDOG_AVAILABLE:
            logger.warning("watchdog library not available for file watching")
            return None
        
        watcher = FileWatcher(event_manager, debounce_ms=500)
        
        # Common DCC file extensions to watch
        dcc_extensions = [
            # Maya
            '.ma', '.mb', '.mel',
            # 3ds Max  
            '.max', '.ms',
            # Blender
            '.blend',
            # UE
            '.uproject', '.uasset', '.umap',
            # Substance
            '.sbs', '.sbsar', '.spp',
            # General
            '.fbx', '.obj', '.dae', '.gltf', '.glb',
            '.png', '.jpg', '.jpeg', '.tga', '.exr', '.hdr',
            '.json', '.xml', '.config'
        ]
        
        # Add watch paths
        added_count = 0
        for path in project_paths:
            if watcher.add_watch_path(path, recursive=True, filters=dcc_extensions):
                added_count += 1
        
        if added_count == 0:
            logger.warning("No valid project paths added to file watcher")
            return None
        
        logger.info(f"Created project file watcher for {added_count} paths with {len(dcc_extensions)} file types")
        return watcher
        
    except Exception as e:
        logger.error(f"Failed to create project file watcher: {e}")
        return None


def get_default_watch_paths() -> List[str]:
    """
    Get default paths to watch based on common project locations.
    
    Returns:
        List of default project paths
    """
    paths = []
    
    # User documents folder
    try:
        import os
        documents = os.path.expanduser("~/Documents")
        if os.path.exists(documents):
            # Common DCC project folders
            potential_paths = [
                os.path.join(documents, "Maya"),
                os.path.join(documents, "3dsMax"),
                os.path.join(documents, "Unreal Projects"),
                os.path.join(documents, "Blender"),
                os.path.join(documents, "Substance Painter"),
                os.path.join(documents, "Substance Designer"),
                documents  # Documents root as fallback
            ]
            
            for path in potential_paths:
                if os.path.exists(path) and os.path.isdir(path):
                    paths.append(path)
                    
    except Exception as e:
        logger.debug(f"Could not determine default watch paths: {e}")
    
    return paths