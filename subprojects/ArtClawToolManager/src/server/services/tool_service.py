# Ref: docs/features/phase4-tool-manager.md#ToolService
"""
Tool business-logic service (filesystem + config, no database).

Combines data from:
  1. ``tool_scanner`` – live filesystem scan of ~/.artclaw/tools/
  2. ``config_manager`` – user preferences (pin/disable/favorite)
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from ..models.data import ToolData
from ..services.config_manager import ConfigManager
from ..services.tool_scanner import scan_tools

from ..core.config import settings


class ToolService:
    """Tool CRUD + lifecycle operations (no DB)."""

    def __init__(self, config: ConfigManager):
        self.config = config
        self._cache: List[ToolData] = []

    # ------------------------------------------------------------------
    # Scan & build
    # ------------------------------------------------------------------

    def _scan_and_build(self) -> List[ToolData]:
        """Scan tools directory and merge with user prefs."""
        scanned = scan_tools()
        cfg = self.config.load()
        tools_cfg = cfg.get("tools", {})
        disabled_set = set(tools_cfg.get("disabled", []))
        pinned_set = set(tools_cfg.get("pinned", []))
        fav_set = set(tools_cfg.get("favorites", []))

        result: List[ToolData] = []
        for s in scanned:
            tool_id = f"{s.source}/{s.name}"
            is_disabled = tool_id in disabled_set
            td = ToolData(
                id=tool_id,
                name=s.name,
                description=s.description,
                version=s.version,
                source=s.source,
                target_dccs=s.target_dccs,
                status="disabled" if is_disabled else "installed",
                tool_path=s.tool_path,
                implementation_type=s.implementation_type,
                manifest=s.manifest,
                is_enabled=not is_disabled,
                is_pinned=tool_id in pinned_set,
                is_favorited=tool_id in fav_set,
            )
            result.append(td)

        self._cache = result
        return result

    # ------------------------------------------------------------------
    # Config helpers for tools
    # ------------------------------------------------------------------

    def _set_tool_pref(self, key: str, tool_id: str, value: bool) -> None:
        """Set a tool preference in config.json under tools.{key}."""
        with self.config._lock:
            cfg = self.config._ensure_structure(self.config._read())
            tools = cfg.setdefault("tools", {})
            lst: List[str] = tools.setdefault(key, [])
            if value and tool_id not in lst:
                lst.append(tool_id)
            elif not value and tool_id in lst:
                lst.remove(tool_id)
            self.config._write(cfg)

    # ------------------------------------------------------------------
    # List / Detail
    # ------------------------------------------------------------------

    def list_tools(
        self,
        *,
        source: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> Tuple[List[ToolData], int]:
        """Filtered + paginated tool list."""
        items = self._scan_and_build()

        if source and source != "all":
            items = [t for t in items if t.source == source]
        if search:
            low = search.lower()
            items = [
                t for t in items
                if low in t.name.lower() or low in t.description.lower()
            ]

        reverse = sort_order == "desc"

        def sort_key(t: ToolData):
            primary = not t.is_pinned
            secondary = getattr(t, sort_by, t.name)
            if isinstance(secondary, str):
                secondary = secondary.lower()
            return (primary, secondary)

        items.sort(key=sort_key, reverse=reverse)
        if reverse:
            items.sort(key=lambda t: not t.is_pinned)

        total = len(items)
        start = (page - 1) * limit
        page_items = items[start : start + limit]
        return page_items, total

    def get_tool(self, tool_id: str) -> Optional[ToolData]:
        if not self._cache:
            self._scan_and_build()
        for t in self._cache:
            if t.id == tool_id:
                return t
        return None

    # ------------------------------------------------------------------
    # Create / Update / Delete (file-based)
    # ------------------------------------------------------------------

    def create_tool(self, name: str, description: str = "",
                    version: str = "1.0.0", source: str = "user",
                    target_dccs: List[str] = None,
                    implementation_type: str = "script",
                    manifest: Dict[str, Any] = None) -> ToolData:
        """Create a new tool by writing manifest.json to disk.

        User tools go to ~/.artclaw/tools/user/{name}/.
        """
        tool_id = f"{source}/{name}"

        # User tools always go under ~/.artclaw/tools/user/
        tools_root = settings.data_path / "tools" / "user" / name
        if tools_root.exists():
            raise ValueError(f"Tool already exists: {tool_id}")

        if manifest is None:
            manifest = {}
        manifest.setdefault("name", name)
        manifest.setdefault("description", description)
        manifest.setdefault("version", version)
        manifest.setdefault("targetDCCs", target_dccs or [])
        manifest.setdefault("implementation", {"type": implementation_type})

        tools_root.mkdir(parents=True, exist_ok=True)
        manifest_path = tools_root / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        td = ToolData(
            id=tool_id,
            name=name,
            description=description,
            version=version,
            source=source,
            target_dccs=target_dccs or [],
            status="installed",
            tool_path=str(tools_root),
            implementation_type=implementation_type,
            manifest=manifest,
        )
        self._cache.append(td)
        return td

    def update_tool(self, tool_id: str, **kwargs: Any) -> Optional[ToolData]:
        """Partial update of a tool (update manifest on disk)."""
        tool = self.get_tool(tool_id)
        if not tool:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(tool, key):
                setattr(tool, key, value)

        # Update manifest on disk
        if tool.tool_path:
            manifest_path = os.path.join(tool.tool_path, "manifest.json")
            if os.path.exists(manifest_path):
                manifest = tool.manifest.copy()
                if "name" in kwargs and kwargs["name"]:
                    manifest["name"] = kwargs["name"]
                if "description" in kwargs and kwargs["description"]:
                    manifest["description"] = kwargs["description"]
                if "version" in kwargs and kwargs["version"]:
                    manifest["version"] = kwargs["version"]
                if "target_dccs" in kwargs and kwargs["target_dccs"] is not None:
                    manifest["targetDCCs"] = kwargs["target_dccs"]
                if "implementation_type" in kwargs and kwargs["implementation_type"]:
                    manifest.setdefault("implementation", {})["type"] = kwargs["implementation_type"]
                if "manifest" in kwargs and kwargs["manifest"]:
                    manifest.update(kwargs["manifest"])
                tool.manifest = manifest
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2, ensure_ascii=False)

        return tool

    def delete_tool(self, tool_id: str) -> bool:
        """Delete a tool by removing its directory."""
        tool = self.get_tool(tool_id)
        if not tool:
            return False
        if tool.tool_path and os.path.isdir(tool.tool_path):
            shutil.rmtree(tool.tool_path, ignore_errors=True)
        self._cache = [t for t in self._cache if t.id != tool_id]
        # Clean up prefs
        self._set_tool_pref("disabled", tool_id, False)
        self._set_tool_pref("pinned", tool_id, False)
        self._set_tool_pref("favorites", tool_id, False)
        return True

    # ------------------------------------------------------------------
    # Toggle operations
    # ------------------------------------------------------------------

    def enable_tool(self, tool_id: str) -> Optional[ToolData]:
        tool = self.get_tool(tool_id)
        if not tool:
            return None
        tool.is_enabled = True
        tool.status = "installed"
        self._set_tool_pref("disabled", tool_id, False)
        return tool

    def disable_tool(self, tool_id: str) -> Optional[ToolData]:
        tool = self.get_tool(tool_id)
        if not tool:
            return None
        tool.is_enabled = False
        tool.status = "disabled"
        self._set_tool_pref("disabled", tool_id, True)
        return tool

    def pin_tool(self, tool_id: str) -> Optional[ToolData]:
        tool = self.get_tool(tool_id)
        if not tool:
            return None
        tool.is_pinned = True
        self._set_tool_pref("pinned", tool_id, True)
        return tool

    def unpin_tool(self, tool_id: str) -> Optional[ToolData]:
        tool = self.get_tool(tool_id)
        if not tool:
            return None
        tool.is_pinned = False
        self._set_tool_pref("pinned", tool_id, False)
        return tool

    def favorite_tool(self, tool_id: str) -> Optional[ToolData]:
        tool = self.get_tool(tool_id)
        if not tool:
            return None
        tool.is_favorited = True
        self._set_tool_pref("favorites", tool_id, True)
        return tool

    def unfavorite_tool(self, tool_id: str) -> Optional[ToolData]:
        tool = self.get_tool(tool_id)
        if not tool:
            return None
        tool.is_favorited = False
        self._set_tool_pref("favorites", tool_id, False)
        return tool

    # ------------------------------------------------------------------
    # Batch
    # ------------------------------------------------------------------

    def batch_operation(
        self, operation: str, tool_ids: List[str]
    ) -> Dict[str, Any]:
        op_map = {
            "enable": self.enable_tool,
            "disable": self.disable_tool,
            "pin": self.pin_tool,
            "unpin": self.unpin_tool,
            "favorite": self.favorite_tool,
            "unfavorite": self.unfavorite_tool,
            "delete": self.delete_tool,
        }
        fn = op_map.get(operation)
        if fn is None:
            return {
                "succeeded": 0,
                "failed": len(tool_ids),
                "errors": [
                    {"tool_id": tid, "error": f"Unknown operation: {operation}"}
                    for tid in tool_ids
                ],
            }

        succeeded = 0
        failed = 0
        errors: List[Dict[str, str]] = []
        for tid in tool_ids:
            try:
                result = fn(tid)
                if result is None and operation != "delete":
                    raise ValueError(f"Tool not found: {tid}")
                if result is False and operation == "delete":
                    raise ValueError(f"Tool not found: {tid}")
                succeeded += 1
            except Exception as exc:
                failed += 1
                errors.append({"tool_id": tid, "error": str(exc)})

        return {"succeeded": succeeded, "failed": failed, "errors": errors}

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def publish_tool(
        self, tool_id: str, target: str, version: str, description: str
    ) -> Dict[str, Any]:
        """Publish a user tool to official or marketplace.

        Publish = move (not copy). The tool is moved from
        ~/.artclaw/tools/user/{name}/ to {project_root}/tools/{target}/{dcc}/{name}/
        and removed from the user directory.
        """
        from pathlib import Path
        from ..services.config_manager import ConfigManager

        tool = self.get_tool(tool_id)
        if not tool:
            raise ValueError(f"Tool not found: {tool_id}")

        if tool.source != "user":
            raise ValueError("Only user tools can be published")

        # Source path (user dir)
        source_path = Path(tool.tool_path)
        if not source_path.exists():
            raise ValueError(f"Source tool directory not found: {source_path}")

        # Read project_root
        cfg = ConfigManager().load()
        project_root = cfg.get("project_root", "")
        if not project_root:
            raise ValueError("project_root not configured in config.json")

        # Determine DCC from target_dccs or default to 'universal'
        dcc = tool.target_dccs[0] if tool.target_dccs else "universal"
        # Map DCC ids to directory names
        dcc_dir_map = {
            "ue57": "unreal", "maya2024": "maya", "max2024": "max",
            "blender": "blender", "comfyui": "comfyui",
            "sp": "substance_painter", "sd": "substance_designer",
            "houdini": "houdini", "general": "universal",
        }
        dcc_dir_name = dcc_dir_map.get(dcc, dcc)

        # Target directory: {project_root}/tools/{target}/{dcc}/{name}/
        target_dir = Path(project_root) / "tools" / target / dcc_dir_name / tool.name
        if target_dir.exists():
            shutil.rmtree(target_dir)

        # Move (not copy!)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(target_dir))

        # Update manifest.json with new source + version
        manifest_path = target_dir / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            manifest_data["source"] = target
            manifest_data["version"] = version
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2, ensure_ascii=False)

        # Clear cache to refresh
        self._cache = []

        return {
            "tool_id": f"{target}/{tool.name}",
            "message": f"Tool '{tool.name}' published to {target}/{dcc_dir_name} successfully",
            "version": version,
            "target": target,
            "description": description,
        }

    # ------------------------------------------------------------------
    # Preset management
    # ------------------------------------------------------------------

    def _read_manifest(self, tool: ToolData) -> Dict[str, Any]:
        """Read manifest.json from disk."""
        if not tool.tool_path:
            return {}
        manifest_path = os.path.join(tool.tool_path, "manifest.json")
        if not os.path.exists(manifest_path):
            return {}
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_manifest(self, tool: ToolData, manifest: Dict[str, Any]) -> None:
        """Write manifest.json to disk."""
        if not tool.tool_path:
            return
        manifest_path = os.path.join(tool.tool_path, "manifest.json")
        os.makedirs(tool.tool_path, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        tool.manifest = manifest

    def list_presets(self, tool_id: str) -> Optional[List[Dict[str, Any]]]:
        """List all presets for a tool."""
        tool = self.get_tool(tool_id)
        if not tool:
            return None
        manifest = self._read_manifest(tool) if tool.tool_path else tool.manifest
        return manifest.get("presets", [])

    def create_preset(
        self,
        tool_id: str,
        name: str,
        description: str = "",
        is_default: bool = False,
        values: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Create a new preset for a tool."""
        tool = self.get_tool(tool_id)
        if not tool:
            raise ValueError(f"Tool not found: {tool_id}")

        manifest = self._read_manifest(tool) if tool.tool_path else tool.manifest.copy()
        presets: List[Dict[str, Any]] = manifest.setdefault("presets", [])

        now = datetime.now(timezone.utc).isoformat()
        preset = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "description": description,
            "isDefault": is_default,
            "values": values or {},
            "createdAt": now,
            "updatedAt": now,
        }

        # If this is set as default, unset others
        if is_default:
            for p in presets:
                p["isDefault"] = False

        presets.append(preset)
        self._write_manifest(tool, manifest)
        return preset

    def update_preset(
        self,
        tool_id: str,
        preset_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_default: Optional[bool] = None,
        values: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update an existing preset."""
        tool = self.get_tool(tool_id)
        if not tool:
            raise ValueError(f"Tool not found: {tool_id}")

        manifest = self._read_manifest(tool) if tool.tool_path else tool.manifest.copy()
        presets: List[Dict[str, Any]] = manifest.get("presets", [])

        target = None
        for p in presets:
            if p.get("id") == preset_id:
                target = p
                break

        if target is None:
            raise ValueError(f"Preset not found: {preset_id}")

        if name is not None:
            target["name"] = name
        if description is not None:
            target["description"] = description
        if values is not None:
            target["values"] = values
        if is_default is not None:
            if is_default:
                for p in presets:
                    p["isDefault"] = False
            target["isDefault"] = is_default
        target["updatedAt"] = datetime.now(timezone.utc).isoformat()

        self._write_manifest(tool, manifest)
        return target

    def delete_preset(self, tool_id: str, preset_id: str) -> None:
        """Delete a preset."""
        tool = self.get_tool(tool_id)
        if not tool:
            raise ValueError(f"Tool not found: {tool_id}")

        manifest = self._read_manifest(tool) if tool.tool_path else tool.manifest.copy()
        presets: List[Dict[str, Any]] = manifest.get("presets", [])
        original_len = len(presets)
        manifest["presets"] = [p for p in presets if p.get("id") != preset_id]

        if len(manifest["presets"]) == original_len:
            raise ValueError(f"Preset not found: {preset_id}")

        self._write_manifest(tool, manifest)

    def set_default_preset(self, tool_id: str, preset_id: str) -> Dict[str, Any]:
        """Set a preset as the default (unset all others)."""
        return self.update_preset(tool_id, preset_id, is_default=True)
