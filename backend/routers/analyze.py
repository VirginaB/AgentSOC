"""
Core analysis router.

POST /api/analyze        — fully analyze a single log
POST /api/analyze/batch  — analyze up to 50 logs
GET  /api/alerts         — retrieve stored alerts (with filters)
GET  /api/alerts/{id}    — get a specific alert
GET  /api/similar/{id}   — get similar logs to a given alert
GET  /api/chains         — get detected attack chains
GET  /api/stats          — dashboard summary statistics
POST /api/stream/start   — start replaying dataset (for demo)
POST /api/stream/stop    — stop replay
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from db import get_db, AlertRecord, AttackChainRecord
from models.schemas import (
    LogInput, BatchLogInput, AlertResponse, AttackChainResponse, StatsResponse
)
from services.classifier import classify_log
from services.llm import explain_log
from services.scorer import compute_risk_score
from services.correlator import ingest_event
from services.similarity import add_to_index, find_similar

router = APIRouter(prefix="/api", tags=["analyze"])
logger = logging.getLogger(__name__)

# Stream state
_stream_task: Optional[asyncio.Task] = None
_stream_running = False


# ─── Single log analysis ─────────────────────────────────────────────────────

@router.post("/analyze", response_model=AlertResponse)
async def analyze_log(
    payload: LogInput,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Full pipeline: classify → score → explain → correlate → store.
    """
    log_text = payload.log_text.strip()
    source_ip = payload.source_ip or _extract_ip(log_text)

    # Step 1: Classify
    classification = classify_log(log_text)
    label = classification["label"]
    confidence = classification["confidence"]

    # Step 2: Score
    score_result = compute_risk_score(label, confidence, source_ip)

    # Step 3: LLM explanation (async — this is the slow step, ~2–5s)
    llm_result = await explain_log(
        log_text=log_text,
        label=label,
        confidence=confidence,
        risk_score=score_result["score"],
        risk_tier=score_result["tier"],
    )

    # Step 4: Store in DB
    alert = AlertRecord(
        log_text=log_text,
        label=label,
        confidence=confidence,
        risk_score=score_result["score"],
        risk_tier=score_result["tier"],
        explanation=llm_result["explanation"],
        mitre_technique=llm_result["mitre_technique"],
        source_ip=source_ip,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    # Step 5: Correlate (check for attack chains)
    chains = ingest_event(source_ip, label, alert.id)
    for chain in chains:
        chain_record = AttackChainRecord(
            chain_name=chain["chain_name"],
            chain_type=chain["chain_type"],
            alert_ids=json.dumps(chain["alert_ids"]),
            source_ip=source_ip,
            severity=chain["severity"],
            description=chain["description"],
            detected_at=datetime.now(timezone.utc),
        )
        db.add(chain_record)
    if chains:
        await db.commit()

    # Step 6: Add to similarity index (background — doesn't block response)
    background_tasks.add_task(add_to_index, alert.id, log_text, label, score_result["tier"])

    # Step 7: Get similar logs
    similar = find_similar(log_text, top_k=5)

    return AlertResponse(
        id=alert.id,
        log_text=log_text,
        label=label,
        confidence=confidence,
        risk_score=score_result["score"],
        risk_tier=score_result["tier"],
        explanation=llm_result["explanation"],
        mitre_technique=llm_result["mitre_technique"],
        source_ip=source_ip,
        timestamp=alert.timestamp,
        similar_logs=similar,
    )


# ─── Batch analysis ───────────────────────────────────────────────────────────

@router.post("/analyze/batch")
async def analyze_batch(
    payload: BatchLogInput,
    db: AsyncSession = Depends(get_db),
):
    """Analyze multiple logs. LLM explanation is skipped for speed — use for bulk ingestion."""
    results = []
    for log_input in payload.logs:
        log_text = log_input.log_text.strip()
        source_ip = log_input.source_ip or _extract_ip(log_text)

        classification = classify_log(log_text)
        score_result = compute_risk_score(
            classification["label"], classification["confidence"], source_ip
        )

        alert = AlertRecord(
            log_text=log_text,
            label=classification["label"],
            confidence=classification["confidence"],
            risk_score=score_result["score"],
            risk_tier=score_result["tier"],
            explanation="",
            mitre_technique="",
            source_ip=source_ip,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(alert)
        results.append({
            "log_text": log_text[:80],
            "label": classification["label"],
            "risk_tier": score_result["tier"],
        })

    await db.commit()
    return {"processed": len(results), "results": results}


# ─── Retrieve alerts ──────────────────────────────────────────────────────────

@router.get("/alerts")
async def get_alerts(
    limit: int = Query(50, le=200),
    tier: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(AlertRecord).order_by(desc(AlertRecord.timestamp)).limit(limit)
    if tier:
        query = query.where(AlertRecord.risk_tier == tier.upper())
    result = await db.execute(query)
    alerts = result.scalars().all()
    return [_alert_to_dict(a) for a in alerts]


@router.get("/alerts/{alert_id}")
async def get_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AlertRecord).where(AlertRecord.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _alert_to_dict(alert)


@router.get("/similar/{alert_id}")
async def get_similar(alert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AlertRecord).where(AlertRecord.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    similar = find_similar(alert.log_text, top_k=5)
    return {"alert_id": alert_id, "similar": similar}


# ─── Attack chains ────────────────────────────────────────────────────────────

@router.get("/chains")
async def get_chains(
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AttackChainRecord)
        .order_by(desc(AttackChainRecord.detected_at))
        .limit(limit)
    )
    chains = result.scalars().all()
    return [_chain_to_dict(c) for c in chains]


# ─── Dashboard stats ──────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(AlertRecord))

    tier_counts = {}
    for tier in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = await db.scalar(
            select(func.count()).select_from(AlertRecord).where(AlertRecord.risk_tier == tier)
        )
        tier_counts[tier] = count or 0

    chains_count = await db.scalar(select(func.count()).select_from(AttackChainRecord))

    correct = await db.scalar(
        select(func.count()).select_from(AlertRecord).where(AlertRecord.feedback == "correct")
    )
    false_pos = await db.scalar(
        select(func.count()).select_from(AlertRecord).where(AlertRecord.feedback == "false_positive")
    )

    total_feedback = (correct or 0) + (false_pos or 0)
    accuracy = round((correct or 0) / total_feedback, 3) if total_feedback > 0 else None

    return StatsResponse(
        total_logs=total or 0,
        critical_count=tier_counts["CRITICAL"],
        high_count=tier_counts["HIGH"],
        medium_count=tier_counts["MEDIUM"],
        low_count=tier_counts["LOW"],
        attack_chains=chains_count or 0,
        correct_feedback=correct or 0,
        false_positives=false_pos or 0,
        accuracy_estimate=accuracy,
    )


# ─── Demo stream ──────────────────────────────────────────────────────────────

@router.post("/stream/start")
async def start_stream(background_tasks: BackgroundTasks):
    global _stream_running
    if _stream_running:
        return {"status": "already running"}
    _stream_running = True
    background_tasks.add_task(_run_demo_stream)
    return {"status": "stream started"}


@router.post("/stream/stop")
async def stop_stream():
    global _stream_running
    _stream_running = False
    return {"status": "stream stopped"}


@router.get("/stream/status")
async def stream_status():
    return {"running": _stream_running}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _extract_ip(log_text: str) -> str:
    import re
    match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", log_text)
    return match.group(0) if match else "unknown"


def _alert_to_dict(a: AlertRecord) -> dict:
    return {
        "id": a.id,
        "log_text": a.log_text,
        "label": a.label,
        "confidence": a.confidence,
        "risk_score": a.risk_score,
        "risk_tier": a.risk_tier,
        "explanation": a.explanation,
        "mitre_technique": a.mitre_technique,
        "source_ip": a.source_ip,
        "timestamp": a.timestamp.isoformat() if a.timestamp else None,
        "feedback": a.feedback,
    }


def _chain_to_dict(c: AttackChainRecord) -> dict:
    import json as _json
    try:
        alert_ids = _json.loads(c.alert_ids) if c.alert_ids else []
    except Exception:
        alert_ids = []
    return {
        "id": c.id,
        "chain_name": c.chain_name,
        "chain_type": c.chain_type,
        "severity": c.severity,
        "source_ip": c.source_ip,
        "description": c.description,
        "alert_ids": alert_ids,
        "detected_at": c.detected_at.isoformat() if c.detected_at else None,
    }


async def _run_demo_stream():
    """
    Replay sample logs one by one with a 1-second delay.
    In production this would read from your SIEVE CSV or a Kafka topic.
    """
    from httpx import AsyncClient

    SAMPLE_LOGS = [
        "Failed password for root from 192.168.1.45 port 22 ssh2",
        "Failed password for root from 192.168.1.45 port 22 ssh2",
        "Failed password for root from 192.168.1.45 port 22 ssh2",
        "Failed password for root from 192.168.1.45 port 22 ssh2",
        "Failed password for root from 192.168.1.45 port 22 ssh2",
        "Accepted password for root from 192.168.1.45 port 22 ssh2",
        "sudo: user root executed /usr/bin/passwd as root",
        "File /etc/shadow accessed by process passwd uid=0",
        "nmap scan detected from 10.0.0.5 targeting 192.168.1.0/24",
        "IDS alert: SYN flood detected from 10.0.0.5",
        "Process python3 started by user nobody uid=65534",
        "File /tmp/.hidden_payload modified",
        "Outbound connection established to 185.220.101.45:4444",
        "User admin created by root",
        "Configuration changed: sshd_config AllowRootLogin yes",
        "Firewall rule added: allow all from any",
        "DNS query for malware-c2.darkweb.onion from 192.168.1.50",
        "HTTP 500 error on /admin/upload endpoint",
        "Bulk file access: 50 files read from /var/sensitive/ in 30s",
        "FTP transfer of 2.3GB to external IP 203.0.113.42",
    ]

    async with AsyncClient(base_url="http://localhost:8000") as client:
        i = 0
        while _stream_running and i < len(SAMPLE_LOGS):
            log = SAMPLE_LOGS[i % len(SAMPLE_LOGS)]
            try:
                await client.post("/api/analyze", json={"log_text": log}, timeout=30)
            except Exception as e:
                logger.warning(f"Stream error on log {i}: {e}")
            i += 1
            await asyncio.sleep(2)   # 1 log every 2 seconds