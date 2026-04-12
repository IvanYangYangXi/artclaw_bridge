# Ref: docs/features/phase3-workflow-library.md#WorkflowScanner
"""
Scan workflow directories for installed workflow templates.

Directory strategy:
  - Official/Marketplace: {project_root}/workflows/{official|marketplace}/{dcc}/{name}/workflow.json
  - User:                 ~/.artclaw/workflows/user/{name}/workflow.json
  - Skills:               ~/.openclaw/skills/{name}/workflow.json (skills that ship a workflow)

``project_root`` is read from ``~/.artclaw/config.json``.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ScannedWorkflow:
    """Parsed information from a single workflow directory."""
    id: str
    name: str
    description: str = ""
    version: str = "0.0.0"
    source: str = "official"
    target_dcc: str = "comfyui"
    preview_image_path: str = ""
    workflow_json: Dict[str, Any] = field(default_factory=dict)
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    workflow_path: str = ""


def _find_preview(directory: Path) -> str:
    """Return the path of a preview image if one exists."""
    for name in ("preview.png", "preview.jpg", "preview.webp", "thumbnail.png"):
        candidate = directory / name
        if candidate.exists():
            return str(candidate)
    return ""


def _parse_workflow_json(workflow_dir: Path, source_hint: str = "official") -> Optional[ScannedWorkflow]:
    """Parse ``workflow.json`` and return a :class:`ScannedWorkflow` or None."""
    wf_file = workflow_dir / "workflow.json"
    if not wf_file.exists():
        return None

    try:
        raw = json.loads(wf_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to parse %s: %s", wf_file, exc)
        return None

    # Metadata may live at top level or inside a "metadata" key.
    meta: Dict[str, Any] = raw.get("metadata", raw)

    name = meta.get("name", "")
    if not name:
        # Fallback: use directory name
        name = workflow_dir.name

    wf_id = meta.get("id", workflow_dir.name)
    description = meta.get("description", "")
    version = str(meta.get("version", "0.0.0"))
    source = meta.get("source", source_hint)
    target_dcc = meta.get("target_dcc", meta.get("dcc", "comfyui"))

    # Parameters for execution form
    parameters = meta.get("parameters", [])
    if not isinstance(parameters, list):
        parameters = []

    preview = _find_preview(workflow_dir)

    return ScannedWorkflow(
        id=wf_id,
        name=name,
        description=description,
        version=version,
        source=source,
        target_dcc=target_dcc,
        preview_image_path=preview,
        workflow_json=raw,
        parameters=parameters,
        workflow_path=str(workflow_dir),
    )


def _get_project_root() -> str:
    """Read project_root from ~/.artclaw/config.json."""
    from ..services.config_manager import ConfigManager
    cfg = ConfigManager().load()
    return cfg.get("project_root", "")


def _scan_directory(root: Path, source_hint: str = "official") -> List[ScannedWorkflow]:
    """Scan *root* for child directories containing workflow.json."""
    if not root.exists():
        return []

    results: List[ScannedWorkflow] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        parsed = _parse_workflow_json(child, source_hint)
        if parsed is not None:
            results.append(parsed)
    return results


def scan_workflows(
    workflows_dir: Optional[Path] = None,
    skills_dir: Optional[Path] = None,
) -> List[ScannedWorkflow]:
    """Discover all workflow templates from the standard directories.

    Searches:
      1. {project_root}/workflows/{official|marketplace}/{dcc}/ — official + marketplace
      2. ~/.artclaw/workflows/user/ — user workflows
      3. ~/.openclaw/skills/ — skills that ship a workflow.json

    Duplicates (same id) are de-duplicated; the first occurrence wins.
    """
    seen_ids: set[str] = set()
    results: List[ScannedWorkflow] = []

    def _add(wf: ScannedWorkflow) -> None:
        if wf.id not in seen_ids:
            seen_ids.add(wf.id)
            results.append(wf)

    # --- 1. Official / Marketplace from project_root ---
    project_root = _get_project_root()
    if project_root:
        repo_wf = Path(project_root) / "workflows"
        if repo_wf.exists():
            for layer_dir in sorted(repo_wf.iterdir()):
                if not layer_dir.is_dir():
                    continue
                layer_name = layer_dir.name  # official / marketplace
                if layer_name not in ("official", "marketplace"):
                    continue
                for dcc_dir in sorted(layer_dir.iterdir()):
                    if not dcc_dir.is_dir():
                        continue
                    for wf_dir in sorted(dcc_dir.iterdir()):
                        if not wf_dir.is_dir():
                            continue
                        parsed = _parse_workflow_json(wf_dir, layer_name)
                        if parsed is not None:
                            _add(parsed)

    # --- 2. User workflows from ~/.artclaw/workflows/user/ ---
    user_root = workflows_dir or (settings.data_path / "workflows" / "user")
    if user_root.exists():
        for wf in _scan_directory(user_root, "user"):
            _add(wf)

    # --- 3. Skills that ship a workflow.json ---
    sk_root = skills_dir or settings.skills_path
    for wf in _scan_directory(sk_root, "official"):
        _add(wf)

    logger.info("Scanned %d workflows from disk", len(results))
    return results
