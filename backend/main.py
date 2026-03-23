"""
AgentSOC — Autonomous Cybersecurity Analyst
FastAPI backend entry point.

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Interactive API docs:
    http://localhost:8000/docs
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from db import init_db
from routers.analyze import router as analyze_router
from routers.chat import router as chat_router
from routers.feedback import router as feedback_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logger.info("AgentSOC starting up...")
    await init_db()
    logger.info("Database initialized.")
    logger.info("Tip: classifier model loads on first request (~60s). Be patient.")
    yield
    logger.info("AgentSOC shutting down.")


app = FastAPI(
    title="AgentSOC",
    description="Autonomous Cybersecurity Analyst — AI-powered SIEM log analysis",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow React frontend (localhost:5173) to call the API
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
    return {"status": "ok", "service": "AgentSOC", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.app_host, port=settings.app_port, reload=True)