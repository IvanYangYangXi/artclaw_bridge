"""
Event Data Helpers — Parse DCC events from TriggerEngine
=========================================================

TriggerEngine calls tool functions with:
    check_sm_naming(params={...}, event_data={...})

event_data format:
    {
        "dcc_type": "ue5",
        "event_type": "asset.save",
        "timing": "pre",
        "data": {"asset_path": "/Game/...", "asset_name": "Wall", ...}
    }

Supported Event Types and Data Fields:
---------------------------------------

### Asset Save Events (asset.save / asset.save.pre)
- asset_path: Asset path (e.g. "/Game/Meshes/Wall")
- asset_name: Asset name (e.g. "Wall")
- asset_class: Asset class (e.g. "StaticMesh")
- package_path: Package path without .AssetName suffix
- file_name: Disk file path
- success: Operation success (post events only)

### Asset Import Events (asset.import / asset.import.pre)
- asset_path: Asset path
- asset_name: Asset name
- asset_class: Asset class
- source_file: Import source file path (e.g. .fbx)
- factory_class: Import factory class name
- success: Operation success (post events only)

### Asset Delete Events (asset.delete / asset.delete.pre)
- asset_path: Asset path
- asset_name: Asset name
- asset_class: Asset class
- asset_paths: List of asset paths for batch operations
- success: Operation success (post events only)

### Level Events (level.load / level.save)
- level_path: Level path
- success: Operation success (post events only)

### Editor Events (editor.startup)
- plugin_version: Plugin version string

Usage:
    from artclaw_sdk import event

    def my_tool(**kwargs):
        evt = event.parse(kwargs)
        print(evt.asset_path)     # "/Game/Meshes/Wall"
        print(evt.asset_name)     # "Wall"
        print(evt.package_path)   # "/Game/Meshes"
        print(evt.source_file)    # "C:/temp/wall.fbx"
        print(evt.dcc_type)       # "ue5"
        print(evt.timing)         # "pre"
        print(evt.event_type)     # "asset.save"
        
        # Intercept checks
        if evt.is_save_intercept:
            print("This is a save pre-event")
        
        print(evt.data)           # {"asset_path": ..., "asset_name": ...}
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional


class EventData:
    """Parsed DCC event with convenient accessors."""

    def __init__(self, raw: Dict[str, Any]):
        self._raw = raw
        self.dcc_type: str = raw.get("dcc_type", "")
        self.event_type: str = raw.get("event_type", "")
        self.timing: str = raw.get("timing", "post")
        self.data: Dict[str, Any] = raw.get("data", {})

    # ── Common data accessors ──

    @property
    def asset_path(self) -> str:
        """Asset path from event data (e.g. '/Game/Meshes/Wall')."""
        return self.data.get("asset_path", "")

    @property
    def asset_name(self) -> str:
        """Asset short name. Auto-extracted from asset_path if not provided."""
        name = self.data.get("asset_name", "")
        if not name and self.asset_path:
            name = self.asset_path.rsplit("/", 1)[-1]
        return name

    @property
    def asset_class(self) -> str:
        """Asset class name (e.g. 'StaticMesh'), if provided."""
        return self.data.get("asset_class", "")

    @property
    def level_path(self) -> str:
        """Level path (for level.save/level.load events)."""
        return self.data.get("level_path", "")

    @property
    def success(self) -> Optional[bool]:
        """Whether the operation succeeded (post events only)."""
        return self.data.get("success")

    # ── Extended data accessors ──

    @property
    def package_path(self) -> str:
        """Package path without .AssetName suffix (for save events)."""
        return self.data.get("package_path", "")

    @property
    def file_name(self) -> str:
        """Disk file path (for save events)."""
        return self.data.get("file_name", "")

    @property
    def source_file(self) -> str:
        """Import source file path, e.g. .fbx (for import events)."""
        return self.data.get("source_file", "")

    @property
    def factory_class(self) -> str:
        """Import factory class name (for import events)."""
        return self.data.get("factory_class", "")

    @property
    def asset_paths(self) -> List[str]:
        """List of asset paths for batch operations (for delete events)."""
        paths = self.data.get("asset_paths", [])
        return paths if isinstance(paths, list) else []

    @property
    def plugin_version(self) -> str:
        """Plugin version string (for editor.startup events)."""
        return self.data.get("plugin_version", "")

    # ── Timing and type checks ──

    @property
    def is_pre(self) -> bool:
        return self.timing == "pre"

    @property
    def is_post(self) -> bool:
        return self.timing == "post"

    # ── Intercept convenience methods ──

    @property
    def is_save_intercept(self) -> bool:
        """True if this is a save pre-event (can intercept/modify)."""
        return self.event_type in ("asset.save.pre", "asset.save") and self.timing == "pre"

    @property
    def is_delete_intercept(self) -> bool:
        """True if this is a delete pre-event (can intercept/modify)."""
        return self.event_type in ("asset.delete.pre", "asset.delete") and self.timing == "pre"

    @property
    def is_import_intercept(self) -> bool:
        """True if this is an import pre-event (can intercept/modify)."""
        return self.event_type in ("asset.import.pre", "asset.import") and self.timing == "pre"

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from event data dict."""
        return self.data.get(key, default)

    def __repr__(self) -> str:
        return f"EventData({self.event_type}, {self.timing}, path={self.asset_path or self.level_path})"


def parse(kwargs: Dict[str, Any]) -> EventData:
    """Parse tool kwargs into an EventData object.

    TriggerEngine calls tools with: fn(params={...}, event_data={...})
    This function extracts and wraps event_data for convenient access.

    Args:
        kwargs: The **kwargs passed to the tool function.

    Returns:
        EventData with convenient accessors for common fields.
    """
    raw = kwargs.get("event_data", {})
    if not isinstance(raw, dict):
        raw = {}
    return EventData(raw)


def get_params(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Extract params dict from tool kwargs.

    Args:
        kwargs: The **kwargs passed to the tool function.

    Returns:
        The params dict (may be empty).
    """
    params = kwargs.get("params", {})
    return params if isinstance(params, dict) else {}
