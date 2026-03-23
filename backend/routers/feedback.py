"""
feedback.py — Analyst feedback router
POST /api/feedback
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db import get_db, AlertRecord
from models.schemas import FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/api", tags=["feedback"])

VALID_FEEDBACK = {"correct", "false_positive", "missed"}


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(payload: FeedbackRequest, db: AsyncSession = Depends(get_db)):
    if payload.feedback not in VALID_FEEDBACK:
        raise HTTPException(
            status_code=400,
            detail=f"feedback must be one of: {', '.join(VALID_FEEDBACK)}"
        )

    result = await db.execute(
        select(AlertRecord).where(AlertRecord.id == payload.alert_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.feedback = payload.feedback
    if payload.correct_label:
        alert.feedback_label = payload.correct_label

    await db.commit()
    return FeedbackResponse(success=True, message=f"Feedback '{payload.feedback}' recorded.")