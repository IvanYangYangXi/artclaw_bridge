# Ref: docs/features/official-system-tools.md#AlertsAPI
"""Alert management API routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ..schemas.alert import (
    AlertCreateRequest,
    AlertUpdateRequest, 
    AlertResponse,
    AlertListResponse
)
from ..services.alert_service import AlertService

router = APIRouter()

# Alert service instance
alert_service = AlertService()


@router.get("/alerts", response_model=AlertListResponse)
async def get_alerts(
    resolved: Optional[bool] = Query(None, description="Filter by resolved status")
):
    """Get alerts with optional resolved filter."""
    try:
        alerts = alert_service.get_alerts(resolved=resolved)
        stats = alert_service.get_stats()
        
        return AlertListResponse(
            alerts=alerts,
            total=len(alerts),
            unresolved=stats["unresolved"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alerts: {str(e)}")


@router.get("/alerts/stats")
async def get_alert_stats():
    """Get alert statistics."""
    try:
        stats = alert_service.get_stats()
        return JSONResponse(stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alert stats: {str(e)}")


@router.post("/alerts/cleanup")
async def cleanup_alerts(
    days: int = Query(7, ge=1, description="Days threshold for cleanup")
):
    """Clean up old resolved alerts."""
    try:
        cleaned_count = alert_service.cleanup_old_alerts(days)
        return JSONResponse({
            "message": f"Cleaned up {cleaned_count} old alerts",
            "cleanedCount": cleaned_count
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup alerts: {str(e)}")


@router.get("/alerts/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: str):
    """Get alert by ID."""
    alert = alert_service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return AlertResponse(**alert.dict())


@router.post("/alerts", response_model=AlertResponse, status_code=201)
async def create_alert(request: AlertCreateRequest):
    """Create a new alert."""
    try:
        alert = alert_service.create_alert(request)
        if not alert:
            raise HTTPException(status_code=500, detail="Failed to create alert")
        
        return AlertResponse(**alert.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create alert: {str(e)}")


@router.patch("/alerts/{alert_id}", response_model=AlertResponse)
async def update_alert(alert_id: str, request: AlertUpdateRequest):
    """Update an alert."""
    try:
        alert = alert_service.update_alert(alert_id, request)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return AlertResponse(**alert.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update alert: {str(e)}")


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str):
    """Delete an alert."""
    try:
        success = alert_service.delete_alert(alert_id)
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return JSONResponse({"message": "Alert deleted successfully"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete alert: {str(e)}")