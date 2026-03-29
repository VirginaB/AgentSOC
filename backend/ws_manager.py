"""
ws_manager.py — WebSocket connection manager + broadcaster.

Keeps a registry of active WebSocket connections.
Call broadcast(data) from anywhere to push an event to all connected clients.
"""

import json
import logging
from typing import Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"WS client connected. Total: {len(self.active)}")

    def disconnect(self, ws: WebSocket):
        self.active = [c for c in self.active if c is not ws]
        logger.info(f"WS client disconnected. Total: {len(self.active)}")

    async def broadcast(self, event_type: str, data: Any):
        if not self.active:
            return
        payload = json.dumps({"type": event_type, "data": data})
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()