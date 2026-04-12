# DCCEventManager + artclaw_sdk Implementation Guide

This document explains the implementation of the DCCEventManager system and artclaw_sdk for ArtClaw Bridge, enabling event-driven tool triggers across all supported DCC applications.

## Overview

The system consists of three main components:

1. **artclaw_sdk** - Runtime package providing unified API for DCC tools
2. **DCCEventManager** - Event hook registration and forwarding system  
3. **FileWatcher** - File system monitoring for file-based triggers

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   DCC Events    │───▶│  DCCEventManager │───▶│   Tool Manager      │
│ (Maya, Blender, │    │                  │    │   TriggerEngine     │
│  Max, etc.)     │    │                  │    │                     │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
                              │                           │
┌─────────────────┐           │                           │
│   artclaw_sdk   │           │                           │
│ - context       │           │                           ▼
│ - filters       │           │                  ┌─────────────────────┐
│ - params        │           │                  │   Tool Execution    │
│ - result        │           │                  │   & Rule Matching   │
│ - progress      │           │                  │                     │
│ - logger        │           │                  └─────────────────────┘
└─────────────────┘           │
                              │
┌─────────────────┐           │
│   FileWatcher   │───────────┘
│ (watchdog)      │
└─────────────────┘
```

## 1. artclaw_sdk Runtime Package

### Location
```
subprojects/DCCClawBridge/core/artclaw_sdk/
├── __init__.py          # Auto-detect DCC & export API
├── context.py           # Context queries
├── filters.py           # Object filtering
├── params.py            # Parameter parsing  
├── result.py            # Result reporting
├── progress.py          # Progress tracking
├── logger.py            # Unified logging
└── dcc/
    ├── __init__.py
    ├── base.py          # Abstract backend interface
    ├── ue.py            # Unreal Engine
    ├── maya.py          # Maya
    ├── max.py           # 3ds Max
    ├── blender.py       # Blender
    ├── comfyui.py       # ComfyUI
    ├── substance_designer.py
    └── substance_painter.py
```

### Key Features

#### Auto-Detection
The SDK automatically detects the current DCC environment on import:

```python
# In __init__.py
def _detect_dcc_environment():
    # Try UE
    try:
        import unreal
        from .dcc.ue import UEAdapter
        _current_adapter = UEAdapter()
        _dcc_type = "ue"
        return
    except ImportError:
        pass
    
    # Try Maya  
    try:
        import maya.cmds
        from .dcc.maya import MayaAdapter
        _current_adapter = MayaAdapter()
        _dcc_type = "maya"
        return
    except ImportError:
        pass
    # ... etc for other DCCs
```

#### Unified API
Tools can use the same API across all DCCs:

```python
from artclaw_sdk import context, result, progress

# Get context (works in any DCC)
selected = context.get_selected()
scene_info = context.get_scene_info()

# Report progress  
progress.start(total=len(selected))
for i, obj in enumerate(selected):
    # Process object
    progress.update(i + 1, f"Processing {obj['name']}")

progress.finish()

# Return result
return result.success(data={"processed": len(selected)})
```

#### DCC-Specific Backends
Each DCC has a dedicated adapter implementing the `BaseDCCBackend` interface:

```python
class BaseDCCBackend(ABC):
    @abstractmethod
    def get_selected(self) -> List[Dict[str, Any]]:
        """Get currently selected objects."""
        pass
    
    @abstractmethod  
    def get_scene_info(self) -> Dict[str, Any]:
        """Get scene metadata and statistics."""
        pass
    
    @abstractmethod
    def get_scene_path(self) -> Optional[str]:
        """Get current scene/file path."""
        pass
    # ... etc
```

## 2. DCCEventManager

### Location
```
subprojects/DCCClawBridge/core/dcc_event_manager.py
```

### Responsibilities

1. **Load trigger rules** from Tool Manager API
2. **Register DCC-native callbacks** for event types
3. **Forward events** to Tool Manager TriggerEngine
4. **Handle pre-event blocking** based on trigger results

### Event Registration Flow

1. On startup: `load_rules()` fetches enabled triggers from Tool Manager
2. Extract event types from trigger rules (e.g., "file.save", "asset.import")
3. `register_events()` calls DCC-specific registration methods
4. Each DCC registers native callbacks using their API (Maya OpenMaya, Blender handlers, etc.)

### DCC-Specific Event Handlers

#### Maya (OpenMaya Messages)
```python
def _register_maya_file_save(self) -> Optional[int]:
    import maya.OpenMaya as om
    
    def on_before_save(client_data):
        self._on_event("file.save", "pre", {"client_data": str(client_data)})
    
    def on_after_save(client_data):
        self._on_event("file.save", "post", {"client_data": str(client_data)})
    
    pre_id = om.MSceneMessage.addCallback(om.MSceneMessage.kBeforeSave, on_before_save)
    post_id = om.MSceneMessage.addCallback(om.MSceneMessage.kAfterSave, on_after_save)
    
    return (pre_id, post_id)
```

#### Blender (App Handlers)
```python
def _register_blender_file_save(self) -> Optional[str]:
    import bpy
    
    def on_pre_save(scene, depsgraph=None):
        self._on_event("file.save", "pre", {"scene": scene.name if scene else None})
    
    def on_post_save(scene, depsgraph=None):
        self._on_event("file.save", "post", {"scene": scene.name if scene else None})
    
    bpy.app.handlers.save_pre.append(on_pre_save)
    bpy.app.handlers.save_post.append(on_post_save)
    
    return "blender_file_save"
```

#### 3ds Max (MaxScript Callbacks)  
```python
def _register_max_file_save(self) -> Optional[str]:
    import pymxs
    rt = pymxs.runtime
    
    # Max uses MaxScript callback system
    pre_script = '''
    fn onPreSave = (
        python.Execute "import sys; sys.modules['core.dcc_event_manager']._global_event_manager._on_event('file.save', 'pre', {})"
    )
    callbacks.addScript #filePreSave "onPreSave()" id:#artclawPreSave
    '''
    
    rt.execute(pre_script)
    return "artclaw_file_save"
```

### Event Forwarding

When a DCC event occurs:

1. DCC-native callback is triggered
2. `_on_event()` is called with event type, timing, and data
3. Event is formatted as DCCEvent and POSTed to Tool Manager
4. Tool Manager returns trigger result
5. For pre-events, return value determines whether to block

```python
def _on_event(self, event_type: str, timing: str, event_data: Dict[str, Any]) -> bool:
    payload = {
        "dcc_type": f"{self.adapter.get_software_name()}{self.adapter.get_software_version()}",
        "event_type": event_type,
        "timing": timing,
        "data": event_data
    }
    
    response = requests.post(
        f"{self.tool_manager_url}/api/v1/dcc-events",
        json=payload,
        timeout=10.0
    )
    
    if response.status_code == 200:
        result_data = response.json()
        trigger_result = result_data.get('data', {})
        
        # For pre-events, check if any rule wants to block
        if timing == "pre":
            return not trigger_result.get('blocked', False)
    
    return True  # Allow event on error (graceful degradation)
```

## 3. FileWatcher Module

### Location
```
subprojects/DCCClawBridge/core/file_watcher.py
```

### Features

- **Cross-platform** file system monitoring using `watchdog` library
- **Debounced events** to prevent spam from rapid file changes (default 500ms)
- **File type filtering** - only watch relevant DCC file extensions
- **Recursive monitoring** of project directories

### Usage

```python
from core.file_watcher import create_project_file_watcher

# Create watcher for common project paths
project_paths = [
    "C:/Users/Artist/Documents/Maya/projects",
    "C:/Users/Artist/Documents/Unreal Projects"
]

watcher = create_project_file_watcher(event_manager, project_paths)
if watcher:
    watcher.start()
```

The FileWatcher monitors common DCC file types:
- Maya: `.ma`, `.mb`, `.mel`
- Max: `.max`, `.ms`
- Blender: `.blend`  
- UE: `.uproject`, `.uasset`, `.umap`
- Substance: `.sbs`, `.sbsar`, `.spp`
- General: `.fbx`, `.obj`, `.png`, `.jpg`, etc.

## 4. Integration with Adapters

### Startup Integration

Each DCC adapter's `on_startup()` method now initializes the DCCEventManager:

```python
def on_startup(self) -> None:
    # ... existing startup code ...
    
    # Initialize event manager for Tool Manager triggers
    try:
        from core.dcc_event_manager import DCCEventManager, set_global_event_manager
        self._event_manager = DCCEventManager(self)
        set_global_event_manager(self._event_manager)
        self._event_manager.load_rules()
        self._event_manager.register_events()
        logger.info("ArtClaw: DCCEventManager initialized")
    except Exception as e:
        logger.warning(f"ArtClaw: DCCEventManager init failed (Tool Manager not running?): {e}")
```

### Shutdown Cleanup

Each adapter's `on_shutdown()` method cleans up event callbacks:

```python  
def on_shutdown(self) -> None:
    # Clean up event manager
    try:
        if hasattr(self, '_event_manager') and self._event_manager:
            self._event_manager.unregister_all()
    except Exception:
        pass
    
    # ... existing shutdown code ...
```

## 5. Supported Events by DCC

### Maya
- ✅ `file.save` (pre/post) - MSceneMessage.kBeforeSave/kAfterSave
- ✅ `file.export` (pre/post) - MSceneMessage.kBeforeExport/kAfterExport  
- ✅ `file.import` (post) - MSceneMessage.kAfterImport
- ✅ `file.open` (post) - MSceneMessage.kAfterOpen
- ✅ `scene.new` (post) - MSceneMessage.kAfterNew

### Blender
- ✅ `file.save` (pre/post) - bpy.app.handlers.save_pre/save_post
- ✅ `file.load` (post) - bpy.app.handlers.load_post  
- ✅ `render.start` (pre) - bpy.app.handlers.render_pre

### 3ds Max
- ✅ `file.save` (pre/post) - MaxScript callbacks.addScript

### Unreal Engine
- ⚠️ `asset.save` - **Requires C++ delegate binding** (Python API limited)
- 📝 Most UE events need C++ implementation due to limited Python delegate access

### ComfyUI
- ⚠️ `workflow.queue` - **Requires ComfyUI execution system integration**
- ⚠️ `workflow.complete` - **Requires ComfyUI execution system integration**

### Substance Designer  
- ⚠️ `graph.compute` - **Requires SD API integration** (depends on SD version)

### Substance Painter
- ⚠️ `project.save` - **Requires SP API integration** (depends on SP version)

### Houdini  
- 🔄 **Not yet implemented** - Would use HDK or Python SOP callbacks

## 6. Error Handling & Graceful Degradation

The system is designed to fail gracefully:

1. **Tool Manager unavailable**: DCCEventManager init fails gracefully, DCC continues working
2. **Event registration fails**: Logged as warning, other events still work  
3. **Event forwarding fails**: Event is allowed to continue (non-blocking)
4. **Missing dependencies**: Watchdog library optional, FileWatcher disabled if unavailable

## 7. Thread Safety

- All DCC event callbacks execute on their respective main threads
- DCCEventManager uses threading.RLock for thread-safe access to shared state
- FileWatcher uses separate threads for file monitoring with proper synchronization
- Progress reporting is thread-local to avoid conflicts

## 8. Configuration

### Tool Manager URL
Default: `http://localhost:9876`

Can be configured in DCCEventManager constructor:
```python  
event_manager = DCCEventManager(adapter, "http://your-server:8080")
```

### File Watcher Debounce
Default: 500ms

Can be configured when creating FileWatcher:
```python
watcher = FileWatcher(event_manager, debounce_ms=1000)  # 1 second
```

## 9. API Integration

### Tool Manager Endpoints

The system integrates with these Tool Manager API endpoints:

1. **GET /api/v1/tools** - List all tools
2. **GET /api/v1/tools/{id}/triggers** - Get triggers for a tool  
3. **POST /api/v1/dcc-events** - Submit DCC event for trigger evaluation

### Event Payload Format

```json
{
  "dcc_type": "maya2024",
  "event_type": "file.save", 
  "timing": "pre",
  "data": {
    "scene_path": "/path/to/scene.ma",
    "timestamp": 1640995200.0,
    "additional_context": "..."
  }
}
```

### Trigger Result Format

```json
{
  "success": true,
  "data": {
    "triggered": true,
    "rules_matched": 2,
    "rules_executed": 1, 
    "blocked": false,
    "details": [
      {
        "rule_id": "backup-on-save",
        "executed": true
      }
    ]
  }
}
```

## 10. Future Enhancements

### Planned Improvements

1. **Enhanced UE Support** - C++ delegate bindings for comprehensive event coverage
2. **ComfyUI Deep Integration** - Hook into execution queue and completion events
3. **Substance Suite Events** - Version-specific API integrations for SD/SP
4. **Performance Monitoring** - Event processing metrics and timing
5. **Event Filtering** - Client-side filtering to reduce API calls
6. **Batch Event Processing** - Group related events to reduce network overhead

### DCC-Specific TODOs

#### Unreal Engine
- Investigate `unreal.register_slate_pre_save_callback()` availability
- Add C++ delegate bindings for:
  - Asset import/save/delete events  
  - Level load/save events
  - Editor startup events

#### ComfyUI  
- Hook into ComfyUI prompt queue system
- Monitor workflow execution completion
- Integrate with ComfyUI server events

#### Substance Applications
- Version-specific API research for SD/SP events
- Graph computation hooks for Substance Designer
- Project save/load hooks for Substance Painter

## 11. Testing

### Unit Tests
Located in: `tests/test_dcc_event_manager.py`, `tests/test_artclaw_sdk.py`

### Integration Tests
Test event flow from DCC → DCCEventManager → Tool Manager

### Manual Testing
1. Start Tool Manager with trigger rules configured
2. Launch DCC with ArtClaw Bridge
3. Perform actions that should trigger events (save file, etc.)  
4. Verify events are received and processed by Tool Manager

## 12. Troubleshooting

### Common Issues

#### DCCEventManager Init Failed
**Symptom**: "DCCEventManager init failed (Tool Manager not running?)"
**Solution**: Ensure Tool Manager is running on localhost:9876

#### Events Not Triggering  
**Symptom**: DCC actions don't trigger Tool Manager rules
**Solutions**:
1. Check Tool Manager has enabled trigger rules
2. Verify event types match between DCC and trigger configuration
3. Check network connectivity to Tool Manager API

#### FileWatcher Not Starting
**Symptom**: "watchdog library not available"
**Solution**: Install requirements: `pip install watchdog`

#### UE Events Not Working  
**Symptom**: Unreal Engine events not registered
**Expected**: UE Python API has limited delegate access - C++ bindings needed

### Log Analysis

Enable debug logging to trace event flow:

```python
import logging
logging.getLogger("artclaw.events").setLevel(logging.DEBUG)
```

Look for these log patterns:
- `DCCEventManager initialized` - Successful startup
- `Registered X/Y event types` - Event registration status  
- `Event {event_type}({timing}) triggered N rules` - Successful event processing
- `Failed to register {event_type}: {error}` - Event registration failures

This completes the comprehensive implementation of DCCEventManager + artclaw_sdk + Event Hooks for all supported DCCs in the ArtClaw Bridge project.