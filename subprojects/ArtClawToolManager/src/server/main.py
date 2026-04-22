# Ref: docs/specs/architecture-design.md#SystemArchitecture
"""
ArtClaw Tool Manager - FastAPI Backend
======================================

Entry point: registers all routers (REST + WebSocket), configures CORS,
and starts background services (Gateway client, DCC monitoring)
via the lifespan context manager.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .api import health, sessions, skills, system, workflows, tools, triggers, filter_presets, alerts
from .core.config import settings

# WebSocket infrastructure
from .websocket.manager import ConnectionManager
from .websocket.chat_ws import router as ws_router, init_chat_ws
from .websocket.message_router import MessageRouter
from .services.gateway_client import GatewayClient
from .services.dcc_manager import DCCManager
from .services.trigger_engine import TriggerEngine
from .api import dcc_events

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared instances (created in lifespan, accessible via app.state)
# ---------------------------------------------------------------------------

ws_manager = ConnectionManager()
gateway_client = GatewayClient(
    gateway_url=settings.resolved_api_url,
    token=settings.resolved_token,
    agent_id=settings.resolved_agent_id,
)
dcc_manager = DCCManager()
message_router = MessageRouter(ws_manager, gateway_client, dcc_manager)
trigger_engine: TriggerEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle."""
    print("[ArtClaw] Tool Manager starting ...")

    logger.info("Skills dir -> %s", settings.skills_path)

    # 1. Inject shared instances into WebSocket endpoint
    init_chat_ws(ws_manager, message_router)

    # 2. Start Gateway client (non-blocking, reconnects in background)
    await gateway_client.start()
    print(f"[ArtClaw] Gateway: {'connected' if gateway_client.connected else 'not connected'} ({settings.GATEWAY_API_URL})")

    # 3. Start DCC health-check monitoring
    await dcc_manager.start_monitoring()

    # 3.5 Sync manifest triggers into triggers.json (idempotent)
    try:
        from .services.tool_scanner import scan_tools
        from .services.trigger_service import TriggerService
        scanned_tools = scan_tools()
        imported = TriggerService().sync_manifest_triggers(scanned_tools)
        if imported:
            print(f"[ArtClaw] Synced {imported} manifest triggers")
    except Exception as e:
        logger.warning("Manifest trigger sync failed: %s", e)

    # 4. Start trigger engine (loads from triggers.json)
    global trigger_engine
    trigger_engine = TriggerEngine()
    dcc_events.init_dcc_events(trigger_engine)
    await trigger_engine.start()

    # Store on app.state for access from API routes if needed
    app.state.ws_manager = ws_manager
    app.state.gateway_client = gateway_client
    app.state.dcc_manager = dcc_manager
    app.state.trigger_engine = trigger_engine

    yield

    # Shutdown
    print("[ArtClaw] Tool Manager shutting down ...")
    if trigger_engine:
        await trigger_engine.stop()
    await dcc_manager.stop_monitoring()
    await gateway_client.disconnect()


app = FastAPI(
    title="ArtClaw Tool Manager API",
    description="Unified tool manager backend – REST API + WebSocket",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REST Routers ---
app.include_router(health.router,    prefix="/api/v1",          tags=["health"])
app.include_router(system.router,    prefix="/api/v1/system",   tags=["system"])
app.include_router(skills.router,    prefix="/api/v1/skills",   tags=["skills"])
app.include_router(sessions.router,  prefix="/api/v1/sessions",  tags=["sessions"])
app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["workflows"])
app.include_router(tools.router,     prefix="/api/v1/tools",    tags=["tools"])
app.include_router(triggers.router,  prefix="/api/v1",          tags=["triggers"])
app.include_router(dcc_events.router, prefix="/api/v1", tags=["dcc-events"])
app.include_router(filter_presets.router, prefix="/api/v1/filter-presets", tags=["filter-presets"])
app.include_router(alerts.router,    prefix="/api/v1",          tags=["alerts"])

# --- WebSocket Router ---
app.include_router(ws_router, tags=["websocket"])


@app.get("/api/v1")
async def api_root():
    """API index."""
    return {
        "name": "ArtClaw Tool Manager API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "endpoints": {
            "health":    "/api/v1/health",
            "system":    "/api/v1/system/status",
            "skills":    "/api/v1/skills",
            "sessions":  "/api/v1/sessions",
            "workflows": "/api/v1/workflows",
            "tools":     "/api/v1/tools",
            "triggers":  "/api/v1/tools/{id}/triggers",
            "dcc-events": "/api/v1/dcc-events",
            "filter-presets": "/api/v1/filter-presets",
            "alerts":    "/api/v1/alerts",
            "websocket": "ws://localhost:9876/ws/chat/{session_id}",
        },
    }


# --- Static Files (Frontend SPA) ---
# Must be registered LAST so API/WS/docs routes take priority.
_DIST_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"
if _DIST_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_DIST_DIR / "assets")), name="static-assets")

    @app.get("/{path:path}")
    async def _spa_fallback(path: str):
        """Serve index.html for all non-API routes (SPA client-side routing)."""
        file = _DIST_DIR / path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(str(_DIST_DIR / "index.html"))


def main():
    """Dev-mode entry point."""
    uvicorn.run(
        "src.server.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        reload_dirs=["src/server"],
        log_level="info",
    )


if __name__ == "__main__":
    main()
