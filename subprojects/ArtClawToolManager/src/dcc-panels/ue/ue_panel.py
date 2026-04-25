# Ref: docs/features/phase5-dcc-integration.md
"""
Unreal Engine Quick Panel for ArtClaw Tool Manager.

Provides UE-specific context gathering (selected assets/actors, level name)
and event reporting to the trigger engine.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..common.panel_base import ArtClawQuickPanel


class UEQuickPanel(ArtClawQuickPanel):
    """Quick Panel tailored for the Unreal Engine Editor."""

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    def get_dcc_context(self) -> Dict[str, Any]:
        """Return current UE editor context.

        Safely wraps ``unreal`` module calls so the panel can still be
        instantiated outside UE (e.g. for testing).
        """
        try:
            import unreal  # type: ignore[import-unmanaged]

            selected_assets: List[str] = [
                str(a.get_name())
                for a in unreal.EditorUtilityLibrary.get_selected_assets()
            ]
            selected_actors: List[str] = [
                str(a.get_name())
                for a in unreal.EditorLevelLibrary.get_selected_level_actors()
            ]
            level_name: str = str(
                unreal.EditorLevelLibrary.get_editor_world().get_name()
            )
        except Exception:
            selected_assets = []
            selected_actors = []
            level_name = "unknown"

        return {
            "dcc": "ue5",
            "selected_assets": selected_assets,
            "selected_actors": selected_actors,
            "level": level_name,
        }

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def open_web_manager(self, context: Optional[Dict[str, str]] = None) -> None:
        """Open the web manager pre-populated with UE context."""
        ctx = context or self.get_dcc_context()
        url_params: Dict[str, str] = {
            "dcc": ctx.get("dcc", "ue5"),
            "level": ctx.get("level", ""),
        }
        selected = ctx.get("selected_actors", []) or ctx.get(
            "selected_assets", []
        )
        if selected:
            url_params["selected"] = ",".join(selected[:20])
        super().open_web_manager(url_params)

    # ------------------------------------------------------------------
    # Event reporting
    # ------------------------------------------------------------------

    def report_event(
        self,
        event_type: str,
        timing: str = "post",
        data: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Report a DCC event to the trigger engine.

        Parameters
        ----------
        event_type:
            The type of event (e.g. ``"save"``, ``"import"``).
        timing:
            ``"pre"`` or ``"post"`` relative to the action.
        data:
            Arbitrary payload attached to the event.
        """
        event_data: Dict[str, Any] = {
            "dcc_type": "ue5",
            "event_type": event_type,
            "timing": timing,
            "data": data or {},
        }
        return self._client.post("/dcc-events", data=event_data)
