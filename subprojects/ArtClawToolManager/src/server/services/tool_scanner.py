# Ref: docs/features/phase4-tool-manager.md#ToolScanner
"""
Scan tool directories by reading manifest.json.

Directory strategy:
  - Official/Marketplace: {project_root}/tools/{official|marketplace}/{dcc}/{tool-name}/manifest.json
  - User:                 ~/.artclaw/tools/user/{tool-name}/manifest.json

``project_root`` is read from ``~/.artclaw/config.json``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.config import settings


@dataclass
class ScannedTool:
    """Parsed information from a tool's manifest.json."""
    name: str
    description: str = ""
    version: str = "1.0.0"
    source: str = "user"
    target_dccs: List[str] = field(default_factory=list)
    implementation_type: str = "script"
    tool_path: str = ""
    manifest: Dict[str, Any] = field(default_factory=dict)


def _parse_manifest(tool_dir: Path, source: str) -> Optional[ScannedTool]:
    """Parse a manifest.json and return a ScannedTool or None."""
    manifest_path = tool_dir / "manifest.json"
    if not manifest_path.exists():
        return None

    try:
        text = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(text)
    except Exception:
        return None

    name = manifest.get("name")
    if not name:
        return None

    impl = manifest.get("implementation", {})
    impl_type = impl.get("type", "script")

    return ScannedTool(
        name=name,
        description=manifest.get("description", ""),
        version=manifest.get("version", "1.0.0"),
        source=manifest.get("source", source),
        target_dccs=manifest.get("targetDCCs", []),
        implementation_type=impl_type,
        tool_path=str(tool_dir),
        manifest=manifest,
    )


def _get_project_root() -> str:
    """Read project_root from ~/.artclaw/config.json."""
    from ..services.config_manager import ConfigManager
    cfg = ConfigManager().load()
    return cfg.get("project_root", "")


def scan_tools(tools_dir: Optional[Path] = None) -> List[ScannedTool]:
    """Scan tool directories and return all discovered tools.

    Searches two locations:
      1. {project_root}/tools/{official|marketplace}/{dcc}/{tool-name}/manifest.json
      2. ~/.artclaw/tools/user/{tool-name}/manifest.json
    """
    results: List[ScannedTool] = []

    # --- 1. Official / Marketplace from project_root ---
    project_root = _get_project_root()
    if project_root:
        repo_tools = Path(project_root) / "tools"
        if repo_tools.exists():
            for layer_dir in sorted(repo_tools.iterdir()):
                if not layer_dir.is_dir():
                    continue
                layer_name = layer_dir.name  # official / marketplace
                if layer_name not in ("official", "marketplace"):
                    continue
                for dcc_dir in sorted(layer_dir.iterdir()):
                    if not dcc_dir.is_dir():
                        continue
                    for tool_dir in sorted(dcc_dir.iterdir()):
                        if not tool_dir.is_dir():
                            continue
                        parsed = _parse_manifest(tool_dir, layer_name)
                        if parsed is not None:
                            results.append(parsed)

    # --- 2. User tools from ~/.artclaw/tools/user/ ---
    user_root = tools_dir or (settings.data_path / "tools" / "user")
    if user_root.exists():
        for tool_dir in sorted(user_root.iterdir()):
            if not tool_dir.is_dir():
                continue
            parsed = _parse_manifest(tool_dir, "user")
            if parsed is not None:
                results.append(parsed)

    return results
