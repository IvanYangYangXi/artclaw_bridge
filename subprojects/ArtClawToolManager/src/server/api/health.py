# Ref: docs/api/api-design.md#HealthCheck
"""Health check endpoint."""

from fastapi import APIRouter

from ..core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check – always returns 200 when the server is up."""
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "service": "artclaw-tool-manager",
            "version": settings.APP_VERSION,
        },
    }
