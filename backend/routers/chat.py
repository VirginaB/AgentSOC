"""
chat.py — Analyst chat router
POST /api/chat
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from db import get_db, AlertRecord
from models.schemas import ChatRequest, ChatResponse
from services.llm import chat_with_analyst

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    # Fetch last 20 alerts as context
    result = await db.execute(
        select(AlertRecord).order_by(desc(AlertRecord.timestamp)).limit(20)
    )
    alerts = result.scalars().all()
    alert_dicts = [
        {
            "id": a.id,
            "log_text": a.log_text,
            "label": a.label,
            "risk_score": a.risk_score,
            "risk_tier": a.risk_tier,
        }
        for a in alerts
    ]

    reply = await chat_with_analyst(
        message=payload.message,
        history=[m.model_dump() for m in payload.history],
        recent_alerts=alert_dicts,
    )

    return ChatResponse(reply=reply)