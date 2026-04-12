# Ref: docs/features/phase3-workflow-library.md#WorkflowService
"""
Workflow business-logic service (filesystem + config, no database).

Combines data from:
  1. ``workflow_scanner`` – live filesystem scan
  2. ``config_manager`` – user preferences (favorites)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..models.data import WorkflowData
from ..services.config_manager import ConfigManager
from ..services.workflow_scanner import scan_workflows

logger = logging.getLogger(__name__)


class WorkflowService:
    """Workflow list + favorite + execute operations (no DB)."""

    def __init__(self, config: ConfigManager):
        self.config = config
        self._cache: List[WorkflowData] = []

    # ------------------------------------------------------------------
    # Scan & build
    # ------------------------------------------------------------------

    def _scan_and_build(self) -> List[WorkflowData]:
        """Scan workflow directories and merge with user prefs."""
        scanned = scan_workflows()
        fav_set = set(self._get_favorite_workflows())

        result: List[WorkflowData] = []
        for s in scanned:
            wd = WorkflowData(
                id=s.id,
                name=s.name,
                description=s.description,
                version=s.version,
                source=s.source,
                target_dcc=s.target_dcc,
                status="installed",
                is_favorited=s.id in fav_set,
                preview_image_path=s.preview_image_path,
                workflow_json=s.workflow_json,
                parameters=s.parameters,
                workflow_path=s.workflow_path,
            )
            result.append(wd)

        self._cache = result
        return result

    # ------------------------------------------------------------------
    # List / Detail
    # ------------------------------------------------------------------

    def list_workflows(
        self,
        *,
        source: Optional[str] = None,
        target_dcc: Optional[str] = None,
        search: Optional[str] = None,
        favorited: Optional[bool] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> Tuple[List[WorkflowData], int]:
        """Filtered + paginated workflow list."""
        items = self._scan_and_build()

        if source and source != "all":
            items = [w for w in items if w.source == source]
        if target_dcc and target_dcc != "all":
            items = [w for w in items if w.target_dcc == target_dcc]
        if favorited is not None:
            items = [w for w in items if w.is_favorited == favorited]
        if search:
            low = search.lower()
            items = [
                w for w in items
                if low in w.name.lower() or low in w.description.lower()
            ]

        reverse = sort_order == "desc"

        def sort_key(w: WorkflowData):
            primary = not w.is_favorited  # favorited first
            secondary = getattr(w, sort_by, w.name)
            if isinstance(secondary, str):
                secondary = secondary.lower()
            return (primary, secondary)

        items.sort(key=sort_key, reverse=reverse)
        if reverse:
            items.sort(key=lambda w: not w.is_favorited)

        total = len(items)
        start = (page - 1) * limit
        page_items = items[start : start + limit]
        return page_items, total

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowData]:
        if not self._cache:
            self._scan_and_build()
        for w in self._cache:
            if w.id == workflow_id:
                return w
        return None

    # ------------------------------------------------------------------
    # Favorite
    # ------------------------------------------------------------------

    def favorite(self, workflow_id: str) -> Optional[WorkflowData]:
        wf = self.get_workflow(workflow_id)
        if not wf:
            return None
        wf.is_favorited = True
        self._set_workflow_favorite(workflow_id, True)
        return wf

    def unfavorite(self, workflow_id: str) -> Optional[WorkflowData]:
        wf = self.get_workflow(workflow_id)
        if not wf:
            return None
        wf.is_favorited = False
        self._set_workflow_favorite(workflow_id, False)
        return wf

    def batch_operation(self, operation: str, workflow_ids: List[str]) -> Dict[str, Any]:
        results = {
            "succeeded": [],
            "failed": [],
            "success_count": 0,
            "failure_count": 0,
        }

        for workflow_id in workflow_ids:
            try:
                if operation == "favorite":
                    wf = self.favorite(workflow_id)
                    if wf:
                        results["succeeded"].append(workflow_id)
                        results["success_count"] += 1
                    else:
                        results["failed"].append({"id": workflow_id, "error": "Workflow not found"})
                        results["failure_count"] += 1
                elif operation == "unfavorite":
                    wf = self.unfavorite(workflow_id)
                    if wf:
                        results["succeeded"].append(workflow_id)
                        results["success_count"] += 1
                    else:
                        results["failed"].append({"id": workflow_id, "error": "Workflow not found"})
                        results["failure_count"] += 1
                elif operation == "delete":
                    results["failed"].append({"id": workflow_id, "error": "Delete operation not yet supported"})
                    results["failure_count"] += 1
                else:
                    results["failed"].append({"id": workflow_id, "error": f"Unknown operation: {operation}"})
                    results["failure_count"] += 1
            except Exception as e:
                logger.error(f"Batch operation failed for workflow {workflow_id}: {e}")
                results["failed"].append({"id": workflow_id, "error": str(e)})
                results["failure_count"] += 1

        return results

    # ------------------------------------------------------------------
    # Parameters
    # ------------------------------------------------------------------

    def get_workflow_parameters(self, workflow_id: str) -> Optional[List[Dict]]:
        wf = self.get_workflow(workflow_id)
        if not wf:
            return None
        return list(wf.parameters) if wf.parameters else []

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute_workflow(
        self, workflow_id: str, params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        wf = self.get_workflow(workflow_id)
        if not wf:
            return None

        wf.use_count = (wf.use_count or 0) + 1

        return {
            "workflow_id": workflow_id,
            "status": "queued",
            "message": f"Workflow '{wf.name}' queued for execution",
            "result": None,
        }

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def publish_workflow(
        self, workflow_id: str, target: str, version: str, description: str
    ) -> Dict[str, Any]:
        """Publish a user workflow to official or marketplace.

        Publish = move (not copy). The workflow is moved from
        ~/.artclaw/workflows/user/{name}/ to {project_root}/workflows/{target}/{dcc}/{name}/
        and removed from the user directory.
        """
        import json
        import shutil
        from pathlib import Path
        from ..services.config_manager import ConfigManager

        wf = self.get_workflow(workflow_id)
        if not wf:
            raise ValueError(f"Workflow not found: {workflow_id}")

        if wf.source != "user":
            raise ValueError("Only user workflows can be published")

        # Source path (user dir)
        source_path = Path(wf.workflow_path)
        if not source_path.exists():
            raise ValueError(f"Source workflow directory not found: {source_path}")

        # Read project_root
        cfg = ConfigManager().load()
        project_root = cfg.get("project_root", "")
        if not project_root:
            raise ValueError("project_root not configured in config.json")

        # Determine DCC directory name
        dcc = wf.target_dcc or "comfyui"
        dcc_dir_map = {
            "ue57": "unreal", "maya2024": "maya", "max2024": "max",
            "blender": "blender", "comfyui": "comfyui",
            "sp": "substance_painter", "sd": "substance_designer",
            "houdini": "houdini", "general": "universal",
        }
        dcc_dir_name = dcc_dir_map.get(dcc, dcc)

        # Target directory: {project_root}/workflows/{target}/{dcc}/{name}/
        target_dir = Path(project_root) / "workflows" / target / dcc_dir_name / wf.name
        if target_dir.exists():
            shutil.rmtree(target_dir)

        # Move (not copy!)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(target_dir))

        # Update workflow.json with new source + version
        workflow_json_path = target_dir / "workflow.json"
        if workflow_json_path.exists():
            with open(workflow_json_path, "r", encoding="utf-8") as f:
                workflow_data = json.load(f)
            if "metadata" in workflow_data:
                workflow_data["metadata"]["source"] = target
                workflow_data["metadata"]["version"] = version
            else:
                workflow_data["source"] = target
                workflow_data["version"] = version
            with open(workflow_json_path, "w", encoding="utf-8") as f:
                json.dump(workflow_data, f, indent=2, ensure_ascii=False)

        # Clear cache to refresh
        self._cache = []

        return {
            "workflow_id": f"{target}/{wf.name}",
            "message": f"Workflow '{wf.name}' published to {target}/{dcc_dir_name} successfully",
            "version": version,
            "target": target,
            "description": description,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_favorite_workflows(self) -> List[str]:
        cfg = self.config.load()
        return cfg.get("workflows", {}).get("favorites", [])

    def _set_workflow_favorite(self, wf_id: str, favorited: bool) -> None:
        with self.config._lock:
            cfg = self.config._ensure_structure(self.config._read())
            wf_section = cfg.setdefault("workflows", {})
            fav_list: List[str] = wf_section.setdefault("favorites", [])
            if favorited and wf_id not in fav_list:
                fav_list.append(wf_id)
            elif not favorited and wf_id in fav_list:
                fav_list.remove(wf_id)
            self.config._write(cfg)
