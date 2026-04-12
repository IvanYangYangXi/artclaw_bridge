# Ref: docs/features/phase5-dcc-integration.md
"""
DCC Events API endpoint — receives events from DCC adapters and feeds
them into the TriggerEngine.

Endpoints:
    POST /api/v1/dcc-events         — submit a DCC event
    GET  /api/v1/dcc-events/stats   — trigger engine statistics
    POST /api/v1/dcc-events/reload  — force-reload rules from DB
"""
from __future__ import annotations

from fastapi import APIRouter

from ..schemas.common import ok, err
from ..schemas.dcc_event import DCCEvent
from ..services.trigger_engine import TriggerEngine

router = APIRouter()

# The engine reference is injected at startup via ``init_dcc_events()``.
_trigger_engine: TriggerEngine | None = None


def init_dcc_events(trigger_engine: TriggerEngine) -> None:
    """Wire the trigger engine instance into this router module."""
    global _trigger_engine
    _trigger_engine = trigger_engine


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.post("/dcc-events")
async def handle_dcc_event(event: DCCEvent):
    """Receive a DCC event and evaluate it against all trigger rules.

    Returns a trigger-result summary with matched/executed counts.
    """
    if _trigger_engine is None:
        return err("ENGINE_NOT_READY", "Trigger engine not initialized")

    result = await _trigger_engine.handle_dcc_event(
        event.event_type, event.model_dump()
    )
    return ok(result)


@router.get("/dcc-events/stats")
async def get_trigger_stats():
    """Return trigger engine statistics (rule counts, scheduler status)."""
    if _trigger_engine is None:
        return ok({
            "running": False,
            "total_rules": 0,
            "scheduled_jobs": 0,
            "event_rules": 0,
        })
    return ok(_trigger_engine.get_stats())


@router.post("/dcc-events/reload")
async def reload_trigger_rules():
    """Force-reload trigger rules from triggers.json."""
    if _trigger_engine is None:
        return err("ENGINE_NOT_READY", "Trigger engine not initialized")

    await _trigger_engine.reload_rules()
    return ok({"reloaded": True, **_trigger_engine.get_stats()})
