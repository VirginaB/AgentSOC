"""
Core analysis router.

POST /api/analyze        - fully analyze a single log
POST /api/analyze/batch  - analyze up to 50 logs
POST /api/analyze/upload - analyze logs from an uploaded file
GET  /api/alerts         - retrieve stored alerts (with filters)
GET  /api/alerts/{id}    - get a specific alert
GET  /api/similar/{id}   - get similar logs to a given alert
GET  /api/chains         - get detected attack chains
GET  /api/stats          - dashboard summary statistics
POST /api/stream/start   - start replaying dataset (for demo)
POST /api/stream/stop    - stop replay
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import AlertRecord, AttackChainRecord, get_db
from models.schemas import AlertResponse, BatchLogInput, LogInput, StatsResponse, UploadResponse
from services.file_parser import SUPPORTED_EXTENSIONS, parse_uploaded_logs
from services.ingestion import process_log_event
from services.similarity import find_similar
from ws_manager import manager as ws_manager

router = APIRouter(prefix="/api", tags=["analyze"])
logger = logging.getLogger(__name__)

_stream_task: Optional[asyncio.Task] = None
_stream_running = False


@router.post("/analyze", response_model=AlertResponse)
async def analyze_log(
    payload: LogInput,
    db: AsyncSession = Depends(get_db),
):
    result = await process_log_event(
        db=db,
        log_text=payload.log_text,
        source_ip=payload.source_ip,
        include_explanation=True,
        include_similar=False,
        add_similarity=True,
    )
    result["similar_logs"] = find_similar(result["log_text"], top_k=5)

    # Push to all connected WebSocket clients
    await ws_manager.broadcast("new_alert", {
        "id": result["id"],
        "log_text": result["log_text"][:200],
        "label": result["label"],
        "confidence": result["confidence"],
        "risk_score": result["risk_score"],
        "risk_tier": result["risk_tier"],
        "source_ip": result["source_ip"],
        "timestamp": result["timestamp"].isoformat(),
        "chain_count": result["chain_count"],
    })

    return AlertResponse(**result)


@router.post("/analyze/batch")
async def analyze_batch(
    payload: BatchLogInput,
    db: AsyncSession = Depends(get_db),
):
    results = []
    for log_input in payload.logs:
        processed = await process_log_event(
            db=db,
            log_text=log_input.log_text,
            source_ip=log_input.source_ip,
            include_explanation=False,
            include_similar=False,
            add_similarity=True,
        )
        results.append(
            {
                "id": processed["id"],
                "log_text": processed["log_text"][:80],
                "label": processed["label"],
                "risk_tier": processed["risk_tier"],
                "chain_count": processed["chain_count"],
            }
        )

    # Broadcast stats update after batch
    await ws_manager.broadcast("stats_refresh", {})

    return {"processed": len(results), "results": results}


@router.post("/analyze/upload", response_model=UploadResponse)
async def analyze_upload(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    filename = file.filename or "uploaded_file"
    extension = ""
    if "." in filename:
        extension = "." + filename.rsplit(".", 1)[1].lower()

    if extension and extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{extension}'. Supported types: {supported}",
        )

    # Size guard — reject files over 10MB before reading into memory
    MAX_BYTES = 10 * 1024 * 1024
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum upload size is 10MB.",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        parsed_logs = parse_uploaded_logs(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not parsed_logs:
        raise HTTPException(status_code=400, detail="No logs were found in the uploaded file.")

    max_logs = 500
    logs_to_process = parsed_logs[:max_logs]
    skipped = max(len(parsed_logs) - len(logs_to_process), 0)

    results = []
    chains_detected = 0
    for item in logs_to_process:
        processed = await process_log_event(
            db=db,
            log_text=item["log_text"],
            source_ip=item.get("source_ip"),
            include_explanation=False,
            include_similar=False,
            add_similarity=True,
        )
        chains_detected += processed["chain_count"]
        results.append(
            {
                "id": processed["id"],
                "log_text": processed["log_text"][:120],
                "label": processed["label"],
                "risk_tier": processed["risk_tier"],
                "source_ip": processed["source_ip"],
            }
        )

    await ws_manager.broadcast("stats_refresh", {})

    return UploadResponse(
        filename=filename,
        processed=len(results),
        skipped=skipped,
        chains_detected=chains_detected,
        results=results,
    )


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


@router.get("/chains")
async def get_chains(
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AttackChainRecord).order_by(desc(AttackChainRecord.detected_at)).limit(limit)
    )
    chains = result.scalars().all()
    return [_chain_to_dict(c) for c in chains]


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
    Demo stream now calls process_log_event directly instead of via HTTP.
    This avoids the localhost self-call overhead entirely.
    """
    from db import AsyncSessionLocal
    from services.ingestion import process_log_event as _process

    sample_logs = [
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

    index = 0
    while _stream_running and index < len(sample_logs):
        log = sample_logs[index % len(sample_logs)]
        try:
            async with AsyncSessionLocal() as db:
                result = await _process(
                    db=db,
                    log_text=log,
                    source_ip=None,
                    include_explanation=False,
                    include_similar=False,
                    add_similarity=True,
                )
                await ws_manager.broadcast("new_alert", {
                    "id": result["id"],
                    "log_text": result["log_text"][:200],
                    "label": result["label"],
                    "confidence": result["confidence"],
                    "risk_score": result["risk_score"],
                    "risk_tier": result["risk_tier"],
                    "source_ip": result["source_ip"],
                    "timestamp": result["timestamp"].isoformat(),
                    "chain_count": result["chain_count"],
                })
        except Exception as exc:
            logger.warning(f"Stream error on log {index}: {exc}")
        index += 1
        await asyncio.sleep(2)