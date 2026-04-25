# Ref: docs/features/phase4-tool-manager.md#ToolScanner
"""
Scan tool directories by reading manifest.json.

Design principle (v2):
  - Official / Marketplace tools live ONLY in {project_root}/tools/{layer}/{dcc}/{tool-name}/
    They are NOT copied to ~/.artclaw/tools/. The project_root is the single source of truth.
  - User tools live in ~/.artclaw/tools/user/{tool-name}/
  - If project_root is not configured or the directory does not exist, the scanner
    raises a RuntimeError with a clear message (misconfiguration, not silently degraded).

Directory structure:
  {project_root}/tools/official/{dcc}/{tool-name}/manifest.json
  {project_root}/tools/marketplace/{dcc}/{tool-name}/manifest.json
  ~/.artclaw/tools/user/{tool-name}/manifest.json

Where layer ∈ {official, marketplace, user}.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.config import settings

_VALID_LAYERS = ("official", "marketplace", "user")


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
    author: str = ""
    created_at: str = ""
    updated_at: str = ""


def _parse_manifest(tool_dir: Path, source: str) -> Optional[ScannedTool]:
    """Parse a manifest.json and return a ScannedTool or None.

    ``source`` is determined by the parent directory layer (not manifest field).
    """
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

    # Always use folder-derived source (authoritative), patch manifest if mismatched
    manifest_source = manifest.get("source", source)
    if manifest_source != source:
        manifest = dict(manifest)
        manifest["source"] = source

    # Auto-generate id from folder structure if not present in manifest
    # id is always authoritative as {source}/{tool_dir.name}
    auto_id = f"{source}/{tool_dir.name}"
    if manifest.get("id") != auto_id:
        manifest = dict(manifest)
        manifest["id"] = auto_id

    # Extract author and timestamps
    author = manifest.get("author", "")
    created_at = manifest.get("createdAt", "")
    updated_at = manifest.get("updatedAt", "")

    # Fallback: use manifest.json file timestamps if not specified
    if not created_at or not updated_at:
        try:
            import datetime as _dt
            stat = manifest_path.stat()
            if not created_at:
                created_at = _dt.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            if not updated_at:
                updated_at = _dt.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    return ScannedTool(
        name=name,
        description=manifest.get("description", ""),
        version=manifest.get("version", "1.0.0"),
        source=source,  # folder-derived, authoritative
        target_dccs=manifest.get("targetDCCs", []),
        implementation_type=impl_type,
        tool_path=str(tool_dir),
        manifest=manifest,
        author=author,
        created_at=created_at,
        updated_at=updated_at,
    )


def _get_project_root() -> str:
    """Read project_root from ~/.artclaw/config.json."""
    from ..services.config_manager import ConfigManager
    cfg = ConfigManager().load()
    return cfg.get("project_root", "")


def _scan_layer_dir(layer_dir: Path, layer_name: str,
                    seen: Dict[str, bool]) -> List[ScannedTool]:
    """Scan all tool sub-directories inside a layer directory.

    Supports two layouts:
      - Flat:   {layer_dir}/{tool-name}/manifest.json
      - Nested: {layer_dir}/{dcc}/{tool-name}/manifest.json
    """
    results: List[ScannedTool] = []
    if not layer_dir.exists():
        return results

    for child in sorted(layer_dir.iterdir()):
        if not child.is_dir():
            continue
        # Flat layout: child is tool dir if manifest.json exists
        if (child / "manifest.json").exists():
            key = f"{layer_name}/{child.name}"
            if key not in seen:
                parsed = _parse_manifest(child, layer_name)
                if parsed is not None:
                    results.append(parsed)
                    seen[key] = True
        else:
            # Nested layout: child is dcc dir, iterate tool dirs inside
            for tool_dir in sorted(child.iterdir()):
                if not tool_dir.is_dir():
                    continue
                key = f"{layer_name}/{tool_dir.name}"
                if key not in seen:
                    parsed = _parse_manifest(tool_dir, layer_name)
                    if parsed is not None:
                        results.append(parsed)
                        seen[key] = True
    return results


def scan_tools(tools_dir: Optional[Path] = None) -> List[ScannedTool]:
    """Scan tool directories and return all discovered tools.

    Scan order:
      1. {project_root}/tools/official/   ← from source repo (official layer)
      2. {project_root}/tools/marketplace/ ← from source repo (marketplace layer)
      3. ~/.artclaw/tools/user/            ← user-created tools (local only)

    Official and marketplace tools are NOT stored in ~/.artclaw/tools/.
    Only user tools live locally.

    Raises RuntimeError if project_root is not configured or does not exist,
    because official/marketplace tools cannot be located without it.
    """
    results: List[ScannedTool] = []
    seen: Dict[str, bool] = {}

    # --- 1 & 2. Official + Marketplace from project_root source repo ---
    project_root = _get_project_root()
    if not project_root:
        raise RuntimeError(
            "project_root 未配置。请在 ArtClaw 配置中设置项目根目录，"
            "官方工具和市集工具需要从源码目录加载。"
            "配置文件: ~/.artclaw/config.json → 字段: project_root"
        )
    repo_tools = Path(project_root) / "tools"
    if not repo_tools.exists():
        raise RuntimeError(
            f"project_root/tools 目录不存在: {repo_tools}\n"
            "请确认 ArtClaw 已正确安装，且 project_root 指向正确的仓库根目录。"
        )
    for layer_name in ("official", "marketplace"):
        layer_dir = repo_tools / layer_name
        results.extend(_scan_layer_dir(layer_dir, layer_name, seen))

    # --- 3. User tools from ~/.artclaw/tools/user/ ---
    user_tools_root = tools_dir or (settings.data_path / "tools")
    user_layer_dir = user_tools_root / "user"
    results.extend(_scan_layer_dir(user_layer_dir, "user", seen))

    return results
