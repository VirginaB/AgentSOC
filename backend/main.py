"""
AgentSOC — Autonomous Cybersecurity Analyst
FastAPI backend entry point.

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Interactive API docs:
    http://localhost:8000/docs
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from db import init_db, AsyncSessionLocal
from routers.analyze import router as analyze_router
from routers.chat import router as chat_router
from routers.feedback import router as feedback_router
from ws_manager import manager as ws_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()

# Global watcher reference (so lifespan and toggle endpoints can reach it)
_log_watcher = None


async def _prewarm_models():
    """
    Load ML models at startup in a thread so they don't block the event loop
    and so the first real request is instant.
    """
    logger.info("Pre-warming classifier model (this takes ~60s on first run)...")
    try:
        await asyncio.to_thread(_load_classifier)
        logger.info("Classifier pre-warm complete.")
    except Exception as e:
        logger.warning(f"Classifier pre-warm failed (will load on first request): {e}")

    logger.info("Pre-warming similarity model...")
    try:
        await asyncio.to_thread(_load_similarity)
        logger.info("Similarity model pre-warm complete.")
    except Exception as e:
        logger.warning(f"Similarity pre-warm failed (will load on first request): {e}")


def _load_classifier():
    from services.classifier import get_classifier
    get_classifier()


def _load_similarity():
    from services.similarity import _get_model, _get_index
    _get_model()
    _get_index()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _log_watcher

    logger.info("AgentSOC starting up...")
    await init_db()
    logger.info("Database initialized.")

    # Pre-warm ML models in the background — don't block startup
    asyncio.create_task(_prewarm_models())

    # ── Log watcher is intentionally NOT started here ──────────────────────
    # The analyst must click "Start OS Watcher" in the frontend UI, which
    # calls POST /api/watcher/start. This gives full control over when
    # OS log collection begins and avoids surprise activity on startup.
    # ────────────────────────────────────────────────────────────────────────
    try:
        from services.log_watcher import LogWatcherService

        @asynccontextmanager
        async def _db_factory():
            async with AsyncSessionLocal() as session:
                yield session

        # Build the watcher instance but do NOT call .start() yet
        _log_watcher = LogWatcherService(
            db_factory=_db_factory,
            broadcast_fn=ws_manager.broadcast,
            # sources=["file:/path/to/your.log"],  # override auto-detect here
        )
        logger.info(
            "LogWatcherService created (idle). "
            "Click 'Start OS Watcher' in the UI to begin collection."
        )
    except Exception as e:
        logger.warning(f"LogWatcherService could not be created: {e}. Manual analysis still works.")

    yield

    # Shutdown — stop watcher if it was running
    if _log_watcher and _log_watcher.is_running:
        await _log_watcher.stop()
    logger.info("AgentSOC shutting down.")


app = FastAPI(
    title="AgentSOC",
    description="Autonomous Cybersecurity Analyst — AI-powered SIEM log analysis",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow the React frontend (Vite default ports) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(analyze_router)
app.include_router(chat_router)
app.include_router(feedback_router)


@app.get("/health")
async def health():
    watcher_status = "running" if (_log_watcher and _log_watcher.is_running) else "stopped"
    queue_size = _log_watcher.queue_size if _log_watcher else 0
    return {
        "status": "ok",
        "service": "AgentSOC",
        "version": "1.0.0",
        "log_watcher": watcher_status,
        "queue_size": queue_size,
        "ws_clients": len(ws_manager.active),
    }


@app.get("/api/watcher/status")
async def watcher_status():
    return {
        "running": bool(_log_watcher and _log_watcher.is_running),
        "queue_size": _log_watcher.queue_size if _log_watcher else 0,
        "ws_clients": len(ws_manager.active),
    }


@app.post("/api/watcher/start")
async def watcher_start():
    """Start OS log collection. Called explicitly by the analyst via the UI."""
    if _log_watcher is None:
        return {"running": False, "error": "LogWatcherService not available on this platform."}
    if not _log_watcher.is_running:
        await _log_watcher.start()
        logger.info("LogWatcher started by analyst via UI.")
    return {"running": _log_watcher.is_running}


@app.post("/api/watcher/stop")
async def watcher_stop():
    """Stop OS log collection."""
    if _log_watcher and _log_watcher.is_running:
        await _log_watcher.stop()
        logger.info("LogWatcher stopped by analyst via UI.")
    return {"running": False}


@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket endpoint. The React frontend connects here once on load.
    The server pushes new alerts in real time — no polling needed.

    Message format:
        { "type": "new_alert",    "data": { ...alert fields } }
        { "type": "stats_refresh", "data": {} }
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive. We only push; but we still need to
            # drain client pings/pongs to detect disconnects promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.app_host, port=settings.app_port, reload=True)