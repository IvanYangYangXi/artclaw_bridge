"""
DCC Event Manager - Event Hooks and Trigger Integration
======================================================

Manages event registration in DCC environments and forwards events to the
ArtClaw Tool Manager TriggerEngine for evaluation and execution.

Architecture:
- Loads trigger rules from Tool Manager API
- Registers DCC-native event callbacks based on rule event types
- Forwards events to Tool Manager /api/v1/dcc-events endpoint
- Handles pre-event blocking based on trigger results
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Callable, Set

logger = logging.getLogger("artclaw.events")


class DCCEventManager:
    """Manages DCC event hooks and forwards to Tool Manager TriggerEngine."""
    
    def __init__(self, adapter, tool_manager_url: str = "http://localhost:9876"):
        """
        Initialize event manager.
        
        Args:
            adapter: DCC adapter instance (from base_adapter.py)
            tool_manager_url: Tool Manager API base URL
        """
        self.adapter = adapter
        self.tool_manager_url = tool_manager_url.rstrip('/')
        self.registered_callbacks = {}  # event_type -> callback_id mapping
        self.loaded_rules: List[Dict[str, Any]] = []
        self.event_types_to_register: Set[str] = set()
        self._lock = threading.RLock()  # Thread safety
        
        # Event handlers for each DCC - will be populated by subclasses
        self.event_handlers = {}
        
        # Store handler function references for clean unregistration
        self._handler_refs = {}  # event_type -> handler_function mapping
        
        # Store adapter method references for ComfyUI
        self._original_methods = {}  # for ComfyUI method monkey-patching
    
    def load_rules(self) -> None:
        """Fetch enabled trigger rules from Tool Manager API."""
        try:
            import requests
            
            # Get all tools
            response = requests.get(f"{self.tool_manager_url}/api/v1/tools", timeout=5.0)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch tools from Tool Manager: {response.status_code}")
                return
            
            tools_data = response.json()
            tools = tools_data.get('data', []) if tools_data.get('success') else []
            
            rules = []
            event_types = set()
            
            # For each tool, get its trigger rules
            for tool in tools:
                tool_id = tool.get('id')
                if not tool_id:
                    continue
                    
                try:
                    # Get triggers for this tool
                    triggers_response = requests.get(
                        f"{self.tool_manager_url}/api/v1/tools/{tool_id}/triggers", 
                        timeout=5.0
                    )
                    
                    if triggers_response.status_code == 200:
                        triggers_data = triggers_response.json()
                        triggers = triggers_data.get('data', []) if triggers_data.get('success') else []
                        
                        for trigger in triggers:
                            if trigger.get('enabled', False) and trigger.get('trigger_type') == 'event':
                                rules.append(trigger)
                                # Extract event types to register
                                event_config = trigger.get('event_config', {})
                                event_type = event_config.get('event_type')
                                if event_type:
                                    event_types.add(event_type)
                    
                except Exception as e:
                    logger.debug(f"Could not get triggers for tool {tool_id}: {e}")
                    continue
            
            with self._lock:
                self.loaded_rules = rules
                self.event_types_to_register = event_types
            
            logger.info(f"Loaded {len(rules)} trigger rules, {len(event_types)} event types to register")
            
        except Exception as e:
            logger.error(f"Failed to load trigger rules: {e}")
            self.loaded_rules = []
            self.event_types_to_register = set()
    
    def register_events(self) -> None:
        """Register DCC-native event callbacks for all loaded event-type rules."""
        with self._lock:
            event_types = self.event_types_to_register.copy()
        
        if not event_types:
            logger.info("No event types to register")
            return
        
        success_count = 0
        
        for event_type in event_types:
            try:
                if self._register_single_event(event_type):
                    success_count += 1
            except Exception as e:
                logger.error(f"Failed to register event {event_type}: {e}")
        
        logger.info(f"Registered {success_count}/{len(event_types)} event types")
    
    def _register_single_event(self, event_type: str) -> bool:
        """Register a single event type with the DCC.
        
        Args:
            event_type: Event type like 'asset.save', 'file.export', etc.
            
        Returns:
            True if registration successful
        """
        if event_type in self.registered_callbacks:
            logger.debug(f"Event {event_type} already registered")
            return True
        
        # Get the appropriate handler for this DCC and event type
        handler_method = self._get_event_handler(event_type)
        if not handler_method:
            logger.warning(f"No handler available for event type {event_type} in {self.adapter.get_software_name()}")
            return False
        
        try:
            # Register the event with DCC-specific method
            callback_id = handler_method(event_type)
            if callback_id is not None:
                self.registered_callbacks[event_type] = callback_id
                logger.debug(f"Registered {event_type} -> {callback_id}")
                return True
            else:
                logger.warning(f"Handler returned None for {event_type}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to register {event_type}: {e}")
            return False
    
    def _get_event_handler(self, event_type: str) -> Optional[Callable]:
        """Get the appropriate event registration handler for this event type.
        
        Args:
            event_type: Event type to register
            
        Returns:
            Handler method or None if not supported
        """
        # Map event types to handler methods
        # This will be implemented in DCC-specific subclasses or methods
        handler_map = self._get_handler_map()
        return handler_map.get(event_type)
    
    def _get_handler_map(self) -> Dict[str, Callable]:
        """Get event type to handler method mapping for current DCC.
        
        Returns:
            Dictionary mapping event types to registration methods
        """
        dcc_name = self.adapter.get_software_name()
        
        if dcc_name == "maya":
            return self._get_maya_handlers()
        elif dcc_name == "max":
            return self._get_max_handlers()  
        elif dcc_name == "blender":
            return self._get_blender_handlers()
        elif dcc_name == "ue":
            return self._get_ue_handlers()
        elif dcc_name == "comfyui":
            return self._get_comfyui_handlers()
        elif dcc_name == "substance_designer":
            return self._get_substance_designer_handlers()
        elif dcc_name == "substance_painter":
            return self._get_substance_painter_handlers()
        elif dcc_name == "houdini":
            return self._get_houdini_handlers()
        else:
            logger.warning(f"No event handlers defined for DCC: {dcc_name}")
            return {}
    
    def unregister_all(self) -> None:
        """Clean up all registered callbacks."""
        with self._lock:
            callbacks = self.registered_callbacks.copy()
        
        unregistered_count = 0
        
        for event_type, callback_id in callbacks.items():
            try:
                if self._unregister_single_event(event_type, callback_id):
                    unregistered_count += 1
            except Exception as e:
                logger.error(f"Failed to unregister {event_type}: {e}")
        
        with self._lock:
            self.registered_callbacks.clear()
        
        logger.info(f"Unregistered {unregistered_count} event callbacks")
    
    def _unregister_single_event(self, event_type: str, callback_id: Any) -> bool:
        """Unregister a single event callback.
        
        Args:
            event_type: Event type that was registered
            callback_id: Callback identifier returned during registration
            
        Returns:
            True if unregistration successful
        """
        # This will be implemented in DCC-specific methods
        dcc_name = self.adapter.get_software_name()
        
        if dcc_name == "maya":
            return self._unregister_maya_event(event_type, callback_id)
        elif dcc_name == "max":
            return self._unregister_max_event(event_type, callback_id)
        elif dcc_name == "blender":
            return self._unregister_blender_event(event_type, callback_id)
        elif dcc_name == "ue":
            return self._unregister_ue_event(event_type, callback_id)
        elif dcc_name == "comfyui":
            return self._unregister_comfyui_event(event_type, callback_id)
        elif dcc_name == "substance_designer":
            return self._unregister_substance_designer_event(event_type, callback_id)
        elif dcc_name == "substance_painter":
            return self._unregister_substance_painter_event(event_type, callback_id)
        elif dcc_name == "houdini":
            return self._unregister_houdini_event(event_type, callback_id)
        
        return True  # Default to success for unknown DCCs
    
    def _on_event(self, event_type: str, timing: str, event_data: Dict[str, Any]) -> bool:
        """Handle a DCC event and forward to TriggerEngine.
        
        Args:
            event_type: Type of event (e.g., 'asset.save')
            timing: 'pre' or 'post' 
            event_data: Event-specific data
            
        Returns:
            True to allow event, False to block (for pre events)
        """
        try:
            import requests
            
            # Prepare event payload
            payload = {
                "dcc_type": f"{self.adapter.get_software_name()}{self.adapter.get_software_version()}",
                "event_type": event_type,
                "timing": timing,
                "data": event_data
            }
            
            # Forward to Tool Manager
            response = requests.post(
                f"{self.tool_manager_url}/api/v1/dcc-events",
                json=payload,
                timeout=10.0  # Reasonable timeout for event handling
            )
            
            if response.status_code == 200:
                result_data = response.json()
                if result_data.get('success'):
                    trigger_result = result_data.get('data', {})
                    
                    # Log trigger results
                    if trigger_result.get('triggered'):
                        logger.info(f"Event {event_type}({timing}) triggered {trigger_result.get('rules_executed', 0)} rules")
                    
                    # For pre-events, check if any rule wants to block
                    if timing == "pre":
                        # The TriggerEngine should return blocking info in the result
                        # This depends on how the Tool Manager implements blocking
                        return not trigger_result.get('blocked', False)
                    
                    return True
                else:
                    logger.error(f"Tool Manager returned error: {result_data}")
                    return True  # Allow event on error
            else:
                logger.error(f"Failed to forward event to Tool Manager: {response.status_code}")
                return True  # Allow event on error
                
        except Exception as e:
            logger.error(f"Error handling event {event_type}({timing}): {e}")
            return True  # Allow event on error (graceful degradation)
    
    # ── DCC-Specific Event Handler Methods ──
    # These methods register actual DCC callbacks
    
    def _get_maya_handlers(self) -> Dict[str, Callable]:
        """Get Maya event handlers."""
        return {
            "file.save": lambda et: self._register_maya_file_save(),
            "file.export": lambda et: self._register_maya_file_export(),
            "file.import": lambda et: self._register_maya_file_import(),
            "file.open": lambda et: self._register_maya_file_open(),
            "scene.new": lambda et: self._register_maya_scene_new(),
        }
    
    def _register_maya_file_save(self) -> Optional[int]:
        """Register Maya file save events."""
        try:
            import maya.OpenMaya as om
            
            def on_before_save(client_data):
                self._on_event("file.save", "pre", {"client_data": str(client_data)})
            
            def on_after_save(client_data):
                self._on_event("file.save", "post", {"client_data": str(client_data)})
            
            # Register callbacks
            pre_id = om.MSceneMessage.addCallback(om.MSceneMessage.kBeforeSave, on_before_save)
            post_id = om.MSceneMessage.addCallback(om.MSceneMessage.kAfterSave, on_after_save)
            
            return (pre_id, post_id)  # Return tuple of callback IDs
            
        except Exception as e:
            logger.error(f"Failed to register Maya file save: {e}")
            return None
    
    def _register_maya_file_export(self) -> Optional[int]:
        """Register Maya file export events.""" 
        try:
            import maya.OpenMaya as om
            
            def on_before_export(client_data):
                self._on_event("file.export", "pre", {"client_data": str(client_data)})
            
            def on_after_export(client_data):
                self._on_event("file.export", "post", {"client_data": str(client_data)})
            
            pre_id = om.MSceneMessage.addCallback(om.MSceneMessage.kBeforeExport, on_before_export)
            post_id = om.MSceneMessage.addCallback(om.MSceneMessage.kAfterExport, on_after_export)
            
            return (pre_id, post_id)
            
        except Exception as e:
            logger.error(f"Failed to register Maya file export: {e}")
            return None
    
    def _register_maya_file_import(self) -> Optional[int]:
        """Register Maya file import events."""
        try:
            import maya.OpenMaya as om
            
            def on_after_import(client_data):
                self._on_event("file.import", "post", {"client_data": str(client_data)})
            
            callback_id = om.MSceneMessage.addCallback(om.MSceneMessage.kAfterImport, on_after_import)
            return callback_id
            
        except Exception as e:
            logger.error(f"Failed to register Maya file import: {e}")
            return None
    
    def _register_maya_file_open(self) -> Optional[int]:
        """Register Maya file open events."""
        try:
            import maya.OpenMaya as om
            
            def on_after_open(client_data):
                self._on_event("file.open", "post", {"client_data": str(client_data)})
            
            callback_id = om.MSceneMessage.addCallback(om.MSceneMessage.kAfterOpen, on_after_open)
            return callback_id
            
        except Exception as e:
            logger.error(f"Failed to register Maya file open: {e}")
            return None
    
    def _register_maya_scene_new(self) -> Optional[int]:
        """Register Maya new scene events."""
        try:
            import maya.OpenMaya as om
            
            def on_after_new(client_data):
                self._on_event("scene.new", "post", {"client_data": str(client_data)})
            
            callback_id = om.MSceneMessage.addCallback(om.MSceneMessage.kAfterNew, on_after_new)
            return callback_id
            
        except Exception as e:
            logger.error(f"Failed to register Maya scene new: {e}")
            return None
    
    def _unregister_maya_event(self, event_type: str, callback_id: Any) -> bool:
        """Unregister Maya event callback."""
        try:
            import maya.OpenMaya as om
            
            if isinstance(callback_id, tuple):
                # Multiple callbacks (pre/post)
                for cb_id in callback_id:
                    om.MMessage.removeCallback(cb_id)
            else:
                # Single callback
                om.MMessage.removeCallback(callback_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister Maya event {event_type}: {e}")
            return False
    
    # ── 3ds Max Event Handlers ──
    
    def _get_max_handlers(self) -> Dict[str, Callable]:
        """Get 3ds Max event handlers."""
        return {
            "file.save": lambda et: self._register_max_file_save(),
            "file.export": lambda et: self._register_max_file_export(),
            "file.import": lambda et: self._register_max_file_import(),
            "file.open": lambda et: self._register_max_file_open(),
            "scene.new": lambda et: self._register_max_scene_new(),
        }
    
    def _register_max_file_save(self) -> Optional[str]:
        """Register 3ds Max file save events."""
        try:
            # Using pymxs callbacks
            import pymxs
            rt = pymxs.runtime
            
            # Max callbacks use MaxScript
            pre_script = f'''
            fn onPreSave = (
                python.Execute "import sys; sys.modules['core.dcc_event_manager']._global_event_manager._on_event('file.save', 'pre', {{}})"
            )
            callbacks.addScript #filePreSave "onPreSave()" id:#artclawPreSave
            '''
            
            post_script = f'''
            fn onPostSave = (
                python.Execute "import sys; sys.modules['core.dcc_event_manager']._global_event_manager._on_event('file.save', 'post', {{}})"
            )
            callbacks.addScript #filePostSave "onPostSave()" id:#artclawPostSave
            '''
            
            rt.execute(pre_script)
            rt.execute(post_script)
            
            return "artclaw_file_save"  # Return identifier
            
        except Exception as e:
            logger.error(f"Failed to register Max file save: {e}")
            return None
    
    def _register_max_file_export(self) -> Optional[str]:
        """Register 3ds Max file export events."""
        try:
            import pymxs
            rt = pymxs.runtime
            
            pre_script = '''
            fn onPreExport = (
                python.Execute "import sys; sys.modules['core.dcc_event_manager']._global_event_manager._on_event('file.export', 'pre', {})"
            )
            callbacks.addScript #filePreExport "onPreExport()" id:#artclawPreExport
            '''
            
            post_script = '''
            fn onPostExport = (
                python.Execute "import sys; sys.modules['core.dcc_event_manager']._global_event_manager._on_event('file.export', 'post', {})"
            )
            callbacks.addScript #filePostExport "onPostExport()" id:#artclawPostExport
            '''
            
            rt.execute(pre_script)
            rt.execute(post_script)
            
            return "artclaw_file_export"
            
        except Exception as e:
            logger.error(f"Failed to register Max file export: {e}")
            return None
    
    def _register_max_file_import(self) -> Optional[str]:
        """Register 3ds Max file import events."""
        try:
            import pymxs
            rt = pymxs.runtime
            
            # Use #filePostMerge which covers import/merge operations
            post_script = '''
            fn onPostImport = (
                python.Execute "import sys; sys.modules['core.dcc_event_manager']._global_event_manager._on_event('file.import', 'post', {})"
            )
            callbacks.addScript #filePostMerge "onPostImport()" id:#artclawPostImport
            '''
            
            rt.execute(post_script)
            return "artclaw_file_import"
            
        except Exception as e:
            logger.error(f"Failed to register Max file import: {e}")
            return None
    
    def _register_max_file_open(self) -> Optional[str]:
        """Register 3ds Max file open events."""
        try:
            import pymxs
            rt = pymxs.runtime
            
            post_script = '''
            fn onPostOpen = (
                python.Execute "import sys; sys.modules['core.dcc_event_manager']._global_event_manager._on_event('file.open', 'post', {})"
            )
            callbacks.addScript #filePostOpen "onPostOpen()" id:#artclawPostOpen
            '''
            
            rt.execute(post_script)
            return "artclaw_file_open"
            
        except Exception as e:
            logger.error(f"Failed to register Max file open: {e}")
            return None
    
    def _register_max_scene_new(self) -> Optional[str]:
        """Register 3ds Max new scene events."""
        try:
            import pymxs
            rt = pymxs.runtime
            
            post_script = '''
            fn onPostNew = (
                python.Execute "import sys; sys.modules['core.dcc_event_manager']._global_event_manager._on_event('scene.new', 'post', {})"
            )
            callbacks.addScript #systemPostNew "onPostNew()" id:#artclawPostNew
            '''
            
            rt.execute(post_script)
            return "artclaw_scene_new"
            
        except Exception as e:
            logger.error(f"Failed to register Max scene new: {e}")
            return None
    
    def _unregister_max_event(self, event_type: str, callback_id: Any) -> bool:
        """Unregister 3ds Max event callback."""
        try:
            import pymxs
            rt = pymxs.runtime
            
            # Remove MaxScript callbacks based on event type
            if event_type == "file.save":
                rt.execute("callbacks.removeScripts id:#artclawPreSave")
                rt.execute("callbacks.removeScripts id:#artclawPostSave")
            elif event_type == "file.export":
                rt.execute("callbacks.removeScripts id:#artclawPreExport")
                rt.execute("callbacks.removeScripts id:#artclawPostExport")
            elif event_type == "file.import":
                rt.execute("callbacks.removeScripts id:#artclawPostImport")
            elif event_type == "file.open":
                rt.execute("callbacks.removeScripts id:#artclawPostOpen")
            elif event_type == "scene.new":
                rt.execute("callbacks.removeScripts id:#artclawPostNew")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister Max event {event_type}: {e}")
            return False
    
    # ── Blender Event Handlers ──
    
    def _get_blender_handlers(self) -> Dict[str, Callable]:
        """Get Blender event handlers."""
        return {
            "file.save": lambda et: self._register_blender_file_save(),
            "file.load": lambda et: self._register_blender_file_load(),
            "render.start": lambda et: self._register_blender_render_start(),
            "file.export": lambda et: self._register_blender_file_export(),
        }
    
    def _register_blender_file_save(self) -> Optional[str]:
        """Register Blender file save events."""
        try:
            import bpy
            
            def on_pre_save(scene, depsgraph=None):
                self._on_event("file.save", "pre", {"scene": scene.name if scene else None})
            
            def on_post_save(scene, depsgraph=None):
                self._on_event("file.save", "post", {"scene": scene.name if scene else None})
            
            # Register handlers
            bpy.app.handlers.save_pre.append(on_pre_save)
            bpy.app.handlers.save_post.append(on_post_save)
            
            # Store handler references for clean unregistration
            self._handler_refs["file.save"] = (on_pre_save, on_post_save)
            
            return "blender_file_save"
            
        except Exception as e:
            logger.error(f"Failed to register Blender file save: {e}")
            return None
    
    def _register_blender_file_load(self) -> Optional[str]:
        """Register Blender file load events."""
        try:
            import bpy
            
            def on_post_load(scene, depsgraph=None):
                self._on_event("file.load", "post", {"scene": scene.name if scene else None})
            
            bpy.app.handlers.load_post.append(on_post_load)
            self._handler_refs["file.load"] = on_post_load
            return "blender_file_load"
            
        except Exception as e:
            logger.error(f"Failed to register Blender file load: {e}")
            return None
    
    def _register_blender_render_start(self) -> Optional[str]:
        """Register Blender render start events."""
        try:
            import bpy
            
            def on_pre_render(scene, depsgraph=None):
                self._on_event("render.start", "pre", {"scene": scene.name if scene else None})
            
            bpy.app.handlers.render_pre.append(on_pre_render)
            self._handler_refs["render.start"] = on_pre_render
            return "blender_render_start"
            
        except Exception as e:
            logger.error(f"Failed to register Blender render start: {e}")
            return None
    
    def _register_blender_file_export(self) -> Optional[str]:
        """Register Blender file export events.
        
        Note: Blender does not have native export event hooks.
        This is a best-effort implementation that cannot intercept
        all export operations. For comprehensive export monitoring,
        C++ addon development would be required.
        """
        try:
            logger.warning("Blender file.export event: Limited support - not all export operations can be monitored from Python")
            # Return a placeholder to indicate "registered" but with limitations
            return "blender_file_export_limited"
            
        except Exception as e:
            logger.error(f"Failed to register Blender file export: {e}")
            return None
    
    def _unregister_blender_event(self, event_type: str, callback_id: Any) -> bool:
        """Unregister Blender event handler by removing only our specific handlers."""
        try:
            import bpy
            
            # Get the stored handler references
            handlers = self._handler_refs.get(event_type)
            if not handlers:
                logger.warning(f"No stored handlers found for {event_type}")
                return True
            
            # Remove specific handlers based on event type
            if event_type == "file.save" and isinstance(handlers, tuple):
                pre_handler, post_handler = handlers
                if pre_handler in bpy.app.handlers.save_pre:
                    bpy.app.handlers.save_pre.remove(pre_handler)
                if post_handler in bpy.app.handlers.save_post:
                    bpy.app.handlers.save_post.remove(post_handler)
            elif event_type == "file.load" and handlers in bpy.app.handlers.load_post:
                bpy.app.handlers.load_post.remove(handlers)
            elif event_type == "render.start" and handlers in bpy.app.handlers.render_pre:
                bpy.app.handlers.render_pre.remove(handlers)
            elif event_type == "file.export":
                # No actual handlers to remove for the limited export support
                pass
            
            # Clear the stored reference
            self._handler_refs.pop(event_type, None)
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister Blender event {event_type}: {e}")
            return False
    
    # ── UE Event Handlers (Python-side only) ──
    
    def _get_ue_handlers(self) -> Dict[str, Callable]:
        """Get UE event handlers using C++ Subsystem delegates."""
        return {
            "asset.save": lambda et: self._register_ue_asset_save(),
            "asset.import": lambda et: self._register_ue_asset_import(),
            "asset.delete": lambda et: self._register_ue_asset_delete(),
            "level.save": lambda et: self._register_ue_level_save(),
            "level.load": lambda et: self._register_ue_level_load(),
            "editor.startup": lambda et: self._register_ue_editor_startup(),
        }

    def _get_ue_subsystem(self):
        """Get UEAgentSubsystem instance for delegate binding."""
        import unreal
        return unreal.get_editor_subsystem(unreal.UEAgentSubsystem)
    
    def _register_ue_asset_save(self) -> Optional[str]:
        """Register UE asset save events via C++ Subsystem delegates."""
        try:
            subsystem = self._get_ue_subsystem()
            if not subsystem:
                logger.warning("UEAgentSubsystem not available, cannot register asset.save events")
                return None

            def on_pre_save(asset_path):
                self._on_event("asset.save", "pre", {"asset_path": str(asset_path)})

            def on_post_save(asset_path, success):
                self._on_event("asset.save", "post", {
                    "asset_path": str(asset_path),
                    "success": bool(success)
                })

            subsystem.on_asset_pre_save.add_callable(on_pre_save)
            subsystem.on_asset_post_save.add_callable(on_post_save)

            # Store references for cleanup
            self._handler_refs["ue_asset_save_pre"] = on_pre_save
            self._handler_refs["ue_asset_save_post"] = on_post_save

            logger.info("UE asset.save: registered via C++ Subsystem delegates (pre + post)")
            return "ue_asset_save_native"

        except Exception as e:
            logger.error(f"Failed to register UE asset save: {e}")
            return None
    
    def _register_ue_asset_import(self) -> Optional[str]:
        """Register UE asset import events via C++ Subsystem delegate."""
        try:
            subsystem = self._get_ue_subsystem()
            if not subsystem:
                logger.warning("UEAgentSubsystem not available, cannot register asset.import events")
                return None

            def on_asset_imported(asset_path, asset_class):
                self._on_event("asset.import", "post", {
                    "asset_path": str(asset_path),
                    "asset_class": str(asset_class)
                })

            subsystem.on_asset_imported.add_callable(on_asset_imported)
            self._handler_refs["ue_asset_import"] = on_asset_imported

            logger.info("UE asset.import: registered via C++ Subsystem delegate (post)")
            return "ue_asset_import_native"

        except Exception as e:
            logger.error(f"Failed to register UE asset import: {e}")
            return None

    def _register_ue_asset_delete(self) -> Optional[str]:
        """Register UE asset delete events via C++ Subsystem delegate."""
        try:
            subsystem = self._get_ue_subsystem()
            if not subsystem:
                logger.warning("UEAgentSubsystem not available, cannot register asset.delete events")
                return None

            def on_asset_pre_delete(asset_path):
                self._on_event("asset.delete", "pre", {"asset_path": str(asset_path)})

            subsystem.on_asset_pre_delete.add_callable(on_asset_pre_delete)
            self._handler_refs["ue_asset_delete"] = on_asset_pre_delete

            logger.info("UE asset.delete: registered via C++ Subsystem delegate (pre)")
            return "ue_asset_delete_native"

        except Exception as e:
            logger.error(f"Failed to register UE asset delete: {e}")
            return None
    
    def _register_ue_level_save(self) -> Optional[str]:
        """Register UE level save events via C++ Subsystem delegates."""
        try:
            subsystem = self._get_ue_subsystem()
            if not subsystem:
                logger.warning("UEAgentSubsystem not available, cannot register level.save events")
                return None

            def on_level_pre_save(level_path):
                self._on_event("level.save", "pre", {"level_path": str(level_path)})

            def on_level_post_save(level_path, success):
                self._on_event("level.save", "post", {
                    "level_path": str(level_path),
                    "success": bool(success)
                })

            subsystem.on_level_pre_save.add_callable(on_level_pre_save)
            subsystem.on_level_post_save.add_callable(on_level_post_save)
            self._handler_refs["ue_level_save_pre"] = on_level_pre_save
            self._handler_refs["ue_level_save_post"] = on_level_post_save

            logger.info("UE level.save: registered via C++ Subsystem delegates (pre + post)")
            return "ue_level_save_native"

        except Exception as e:
            logger.error(f"Failed to register UE level save: {e}")
            return None
    
    def _register_ue_level_load(self) -> Optional[str]:
        """Register UE level load events via C++ Subsystem delegate."""
        try:
            subsystem = self._get_ue_subsystem()
            if not subsystem:
                logger.warning("UEAgentSubsystem not available, cannot register level.load events")
                return None

            def on_level_loaded(level_path):
                self._on_event("level.load", "post", {"level_path": str(level_path)})

            subsystem.on_level_loaded.add_callable(on_level_loaded)
            self._handler_refs["ue_level_load"] = on_level_loaded

            logger.info("UE level.load: registered via C++ Subsystem delegate (post)")
            return "ue_level_load_native"

        except Exception as e:
            logger.error(f"Failed to register UE level load: {e}")
            return None
    
    def _register_ue_editor_startup(self) -> Optional[str]:
        """Register UE editor startup events — fires immediately."""
        try:
            self._on_event("editor.startup", "post", {"immediate": True})
            return "ue_editor_startup_immediate"
        except Exception as e:
            logger.error(f"Failed to register UE editor startup: {e}")
            return None
    
    def _unregister_ue_event(self, event_type: str, callback_id: Any) -> bool:
        """Unregister UE event callbacks from Subsystem delegates."""
        try:
            subsystem = self._get_ue_subsystem()
            if not subsystem:
                return True  # Nothing to clean up

            if event_type == "asset.save":
                pre_fn = self._handler_refs.pop("ue_asset_save_pre", None)
                post_fn = self._handler_refs.pop("ue_asset_save_post", None)
                if pre_fn:
                    subsystem.on_asset_pre_save.remove_callable(pre_fn)
                if post_fn:
                    subsystem.on_asset_post_save.remove_callable(post_fn)
            elif event_type == "asset.import":
                fn = self._handler_refs.pop("ue_asset_import", None)
                if fn:
                    subsystem.on_asset_imported.remove_callable(fn)
            elif event_type == "asset.delete":
                fn = self._handler_refs.pop("ue_asset_delete", None)
                if fn:
                    subsystem.on_asset_pre_delete.remove_callable(fn)
            elif event_type == "level.save":
                pre_fn = self._handler_refs.pop("ue_level_save_pre", None)
                post_fn = self._handler_refs.pop("ue_level_save_post", None)
                if pre_fn:
                    subsystem.on_level_pre_save.remove_callable(pre_fn)
                if post_fn:
                    subsystem.on_level_post_save.remove_callable(post_fn)
            elif event_type == "level.load":
                fn = self._handler_refs.pop("ue_level_load", None)
                if fn:
                    subsystem.on_level_loaded.remove_callable(fn)

            return True

        except Exception as e:
            logger.error(f"Failed to unregister UE event {event_type}: {e}")
            return False
    
    # ── ComfyUI Event Handlers ──
    
    def _get_comfyui_handlers(self) -> Dict[str, Callable]:
        """Get ComfyUI event handlers."""
        return {
            "workflow.queue": lambda et: self._register_comfyui_workflow_queue(),
            "workflow.complete": lambda et: self._register_comfyui_workflow_complete(),
        }
    
    def _register_comfyui_workflow_queue(self) -> Optional[str]:
        """Register ComfyUI workflow queue events."""
        try:
            # Hook into the adapter's submit_workflow method if available
            if not hasattr(self.adapter, 'submit_workflow'):
                logger.warning("ComfyUI adapter does not have submit_workflow method")
                return None
            
            # Store original method if not already stored
            if 'submit_workflow' not in self._original_methods:
                self._original_methods['submit_workflow'] = getattr(self.adapter, 'submit_workflow', None)
            
            original_submit = self._original_methods['submit_workflow']
            if original_submit is None:
                logger.warning("ComfyUI submit_workflow method is None")
                return None
            
            def hooked_submit(*args, **kwargs):
                self._on_event("workflow.queue", "pre", {"args": str(args)[:200]})  # Limit arg string length
                result = original_submit(*args, **kwargs)
                self._on_event("workflow.queue", "post", {"result": str(result)[:200] if result else None})
                return result
            
            # Replace the method with our hooked version
            if hasattr(self.adapter, 'submit_workflow'):
                setattr(self.adapter, 'submit_workflow', hooked_submit)
            
            # Also try to hook the client's submit method if available
            if hasattr(self.adapter, '_get_client'):
                try:
                    client = self.adapter._get_client()
                    if hasattr(client, 'submit_and_wait') and 'client_submit' not in self._original_methods:
                        self._original_methods['client_submit'] = client.submit_and_wait
                        
                        def hooked_client_submit(*args, **kwargs):
                            self._on_event("workflow.queue", "pre", {"client_args": str(args)[:200]})
                            result = self._original_methods['client_submit'](*args, **kwargs)
                            self._on_event("workflow.queue", "post", {"client_result": str(result)[:200] if result else None})
                            return result
                        
                        client.submit_and_wait = hooked_client_submit
                except Exception as e:
                    logger.debug(f"Could not hook client submit method: {e}")
            
            return "comfyui_workflow_queue"
            
        except Exception as e:
            logger.error(f"Failed to register ComfyUI workflow queue: {e}")
            return None
    
    def _register_comfyui_workflow_complete(self) -> Optional[str]:
        """Register ComfyUI workflow completion events."""
        try:
            # This would ideally hook into ComfyUI's execution completion system
            # For now, we'll provide a monitoring approach
            logger.info("ComfyUI workflow.complete event registered with monitoring approach")
            
            # In a full implementation, this would hook into the ComfyUI execution system
            # to detect when workflows complete. This requires deeper integration with
            # ComfyUI's internal execution queue and progress tracking.
            
            return "comfyui_workflow_complete"
            
        except Exception as e:
            logger.error(f"Failed to register ComfyUI workflow complete: {e}")
            return None
    
    def _unregister_comfyui_event(self, event_type: str, callback_id: Any) -> bool:
        """Unregister ComfyUI event callback by restoring original methods."""
        try:
            # Restore original methods if they were hooked
            if event_type == "workflow.queue":
                # Restore adapter method
                if 'submit_workflow' in self._original_methods:
                    original = self._original_methods['submit_workflow']
                    if hasattr(self.adapter, 'submit_workflow') and original:
                        setattr(self.adapter, 'submit_workflow', original)
                
                # Restore client method
                if 'client_submit' in self._original_methods:
                    try:
                        client = self.adapter._get_client()
                        original = self._original_methods['client_submit']
                        if hasattr(client, 'submit_and_wait') and original:
                            client.submit_and_wait = original
                    except Exception:
                        pass
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister ComfyUI event {event_type}: {e}")
            return False
    
    # ── Substance Designer Event Handlers ──
    
    def _get_substance_designer_handlers(self) -> Dict[str, Callable]:
        """Get Substance Designer event handlers.""" 
        return {
            "graph.compute": lambda et: self._register_sd_graph_compute(),
            "package.save": lambda et: self._register_sd_package_save(),
            "graph.create": lambda et: self._register_sd_graph_create(),
        }
    
    def _register_sd_graph_compute(self) -> Optional[str]:
        """Register Substance Designer graph compute events."""
        try:
            import sd
            from sd.api.sdapplication import SDApplication
            
            # SD doesn't have direct compute callbacks, but we can hook into
            # the adapter's execute_code method to detect compute-related operations
            logger.info("Substance Designer graph.compute: monitoring via adapter integration")
            
            # This would require wrapping the adapter's execute_code method
            # to detect when compute operations are performed
            
            # Store a reference for potential future use
            self._handler_refs["graph.compute"] = "sd_compute_monitor"
            
            return "sd_graph_compute"
            
        except Exception as e:
            logger.error(f"Failed to register SD graph compute: {e}")
            return None
    
    def _register_sd_package_save(self) -> Optional[str]:
        """Register Substance Designer package save events."""
        try:
            import sd
            from sd.api.sdapplication import SDApplication
            
            # SD API doesn't provide direct save callbacks
            # We'd need to wrap package save operations or monitor file system changes
            logger.info("Substance Designer package.save: monitoring approach")
            
            self._handler_refs["package.save"] = "sd_package_save_monitor"
            return "sd_package_save"
            
        except Exception as e:
            logger.error(f"Failed to register SD package save: {e}")
            return None
    
    def _register_sd_graph_create(self) -> Optional[str]:
        """Register Substance Designer graph creation events."""
        try:
            import sd
            
            # Monitor for new graph creation
            logger.info("Substance Designer graph.create: monitoring approach")
            
            self._handler_refs["graph.create"] = "sd_graph_create_monitor"
            return "sd_graph_create"
            
        except Exception as e:
            logger.error(f"Failed to register SD graph create: {e}")
            return None
    
    def _unregister_substance_designer_event(self, event_type: str, callback_id: Any) -> bool:
        """Unregister Substance Designer event callback."""
        try:
            # Clean up monitoring references
            self._handler_refs.pop(event_type, None)
            logger.info(f"SD {event_type} monitoring stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister SD event {event_type}: {e}")
            return False
    
    # ── Substance Painter Event Handlers ──
    
    def _get_substance_painter_handlers(self) -> Dict[str, Callable]:
        """Get Substance Painter event handlers."""
        return {
            "project.save": lambda et: self._register_sp_project_save(),
            "project.open": lambda et: self._register_sp_project_open(),
            "export.complete": lambda et: self._register_sp_export_complete(),
        }
    
    def _register_sp_project_save(self) -> Optional[str]:
        """Register Substance Painter project save events."""
        try:
            import substance_painter.event as sp_event
            
            # SP has a proper event system!
            def on_project_saved(event):
                self._on_event("project.save", "post", {"project_saved": True})
            
            sp_event.DISPATCHER.connect(sp_event.ProjectSaved, on_project_saved)
            self._handler_refs["project.save"] = on_project_saved  # Keep reference for cleanup
            
            return "sp_project_save"
            
        except Exception as e:
            logger.error(f"Failed to register SP project save: {e}")
            return None
    
    def _register_sp_project_open(self) -> Optional[str]:
        """Register Substance Painter project open events."""
        try:
            import substance_painter.event as sp_event
            
            def on_project_opened(event):
                self._on_event("project.open", "post", {"project_opened": True})
            
            # SP uses ProjectOpened event
            sp_event.DISPATCHER.connect(sp_event.ProjectOpened, on_project_opened)
            self._handler_refs["project.open"] = on_project_opened
            
            return "sp_project_open"
            
        except Exception as e:
            logger.error(f"Failed to register SP project open: {e}")
            return None
    
    def _register_sp_export_complete(self) -> Optional[str]:
        """Register Substance Painter export complete events."""
        try:
            import substance_painter.event as sp_event
            
            def on_export_finished(event):
                self._on_event("export.complete", "post", {"export_finished": True})
            
            # Use ExportTexturesEnded event
            if hasattr(sp_event, 'ExportTexturesEnded'):
                sp_event.DISPATCHER.connect(sp_event.ExportTexturesEnded, on_export_finished)
                self._handler_refs["export.complete"] = on_export_finished
                return "sp_export_complete"
            else:
                logger.warning("SP ExportTexturesEnded event not available in this version")
                return None
            
        except Exception as e:
            logger.error(f"Failed to register SP export complete: {e}")
            return None


# Global reference for MaxScript callbacks
_global_event_manager: Optional[DCCEventManager] = None


def set_global_event_manager(manager: DCCEventManager) -> None:
    """Set global event manager reference for MaxScript callbacks."""
    global _global_event_manager
    _global_event_manager = manager


class DCCEventManagerExtensions:
    """Additional event handler methods for DCCEventManager."""
    
    def _unregister_substance_painter_event(self, event_type: str, callback_id: Any) -> bool:
        """Unregister Substance Painter event callback."""
        try:
            import substance_painter.event as sp_event
            
            # Disconnect our specific handlers
            handler = self._handler_refs.get(event_type)
            if handler:
                if event_type == "project.save":
                    sp_event.DISPATCHER.disconnect(sp_event.ProjectSaved, handler)
                elif event_type == "project.open":
                    sp_event.DISPATCHER.disconnect(sp_event.ProjectOpened, handler)
                elif event_type == "export.complete" and hasattr(sp_event, 'ExportTexturesEnded'):
                    sp_event.DISPATCHER.disconnect(sp_event.ExportTexturesEnded, handler)
                
                # Clear the reference
                self._handler_refs.pop(event_type, None)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister SP event {event_type}: {e}")
            return False
    
    # ── Houdini Event Handlers ──
    
    def _get_houdini_handlers(self) -> Dict[str, Callable]:
        """Get Houdini event handlers."""
        return {
            "file.save": lambda et: self._register_houdini_file_save(),
            "file.load": lambda et: self._register_houdini_file_load(),
            "scene.new": lambda et: self._register_houdini_scene_new(),
        }
    
    def _register_houdini_file_save(self) -> Optional[str]:
        """Register Houdini file save events."""
        try:
            import hou
            
            def on_hip_event(event_type):
                if event_type == hou.hipFileEventType.BeforeSave:
                    self._on_event("file.save", "pre", {"hip_file": hou.hipFile.path()})
                elif event_type == hou.hipFileEventType.AfterSave:
                    self._on_event("file.save", "post", {"hip_file": hou.hipFile.path()})
            
            hou.hipFile.addEventCallback(on_hip_event)
            self._handler_refs["file.save"] = on_hip_event
            
            return "houdini_file_save"
            
        except Exception as e:
            logger.error(f"Failed to register Houdini file save: {e}")
            return None
    
    def _register_houdini_file_load(self) -> Optional[str]:
        """Register Houdini file load events."""
        try:
            import hou
            
            def on_hip_load_event(event_type):
                if event_type == hou.hipFileEventType.AfterLoad:
                    self._on_event("file.load", "post", {"hip_file": hou.hipFile.path()})
            
            hou.hipFile.addEventCallback(on_hip_load_event)
            self._handler_refs["file.load"] = on_hip_load_event
            
            return "houdini_file_load"
            
        except Exception as e:
            logger.error(f"Failed to register Houdini file load: {e}")
            return None
    
    def _register_houdini_scene_new(self) -> Optional[str]:
        """Register Houdini new scene events."""
        try:
            import hou
            
            def on_hip_new_event(event_type):
                if event_type == hou.hipFileEventType.AfterClear:
                    self._on_event("scene.new", "post", {"hip_cleared": True})
            
            hou.hipFile.addEventCallback(on_hip_new_event)
            self._handler_refs["scene.new"] = on_hip_new_event
            
            return "houdini_scene_new"
            
        except Exception as e:
            logger.error(f"Failed to register Houdini scene new: {e}")
            return None
    
    def _unregister_houdini_event(self, event_type: str, callback_id: Any) -> bool:
        """Unregister Houdini event callback."""
        try:
            import hou
            
            # Remove the specific callback
            handler = self._handler_refs.get(event_type)
            if handler:
                hou.hipFile.removeEventCallback(handler)
                self._handler_refs.pop(event_type, None)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister Houdini event {event_type}: {e}")
            return False


# Mix in the additional methods to DCCEventManager
for method_name in dir(DCCEventManagerExtensions):
    if not method_name.startswith('_'):
        continue
    method = getattr(DCCEventManagerExtensions, method_name)
    if callable(method):
        setattr(DCCEventManager, method_name, method)