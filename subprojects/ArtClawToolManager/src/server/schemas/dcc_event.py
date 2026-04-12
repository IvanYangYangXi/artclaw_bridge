# Ref: docs/features/phase5-dcc-integration.md
"""
Pydantic schemas for DCC event ingestion.

These are used by the ``/api/v1/dcc-events`` endpoint to receive events
from DCC adapters (UE, Maya, ComfyUI, etc.) and return trigger results.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DCCEvent(BaseModel):
    """Incoming DCC event payload."""

    dcc_type: str = Field(
        ..., description="DCC identifier: 'ue57', 'maya2024', 'comfyui', etc."
    )
    event_type: str = Field(
        ..., description="Dot-separated event name: 'asset.save', 'file.export', etc."
    )
    timing: str = Field(
        default="post", description="'pre' or 'post'"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary event payload from the DCC adapter.",
    )


class TriggerResultDetail(BaseModel):
    """Execution detail for a single matched rule."""

    rule_id: str
    executed: bool


class TriggerResult(BaseModel):
    """Summary returned after evaluating an event against all trigger rules."""

    triggered: bool = False
    rules_matched: int = 0
    rules_executed: int = 0
    details: List[TriggerResultDetail] = Field(default_factory=list)
    
    # Pre-event blocking fields
    blocked: Optional[bool] = Field(
        default=None, 
        description="Whether the pre-event should be blocked (only for timing='pre')"
    )
    block_reason: Optional[str] = Field(
        default=None, 
        description="Reason why the event was blocked"
    )
