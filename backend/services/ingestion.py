import json
from datetime import datetime, timezone

from db import AlertRecord, AttackChainRecord
from services.classifier import classify_log
from services.correlator import ingest_event
from services.llm import explain_log
from services.scorer import compute_risk_score
from services.similarity import add_to_index, find_similar


def extract_ip(log_text: str) -> str:
    import re

    match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", log_text)
    return match.group(0) if match else "unknown"


async def process_log_event(
    *,
    db,
    log_text: str,
    source_ip: str | None = None,
    include_explanation: bool = True,
    include_similar: bool = False,
    add_similarity: bool = True,
) -> dict:
    clean_log = log_text.strip()
    resolved_ip = source_ip or extract_ip(clean_log)

    classification = classify_log(clean_log)
    label = classification["label"]
    confidence = classification["confidence"]
    score_result = compute_risk_score(label, confidence, resolved_ip)

    explanation = ""
    mitre_technique = ""
    if include_explanation:
        llm_result = await explain_log(
            log_text=clean_log,
            label=label,
            confidence=confidence,
            risk_score=score_result["score"],
            risk_tier=score_result["tier"],
        )
        explanation = llm_result["explanation"]
        mitre_technique = llm_result["mitre_technique"]

    alert = AlertRecord(
        log_text=clean_log,
        label=label,
        confidence=confidence,
        risk_score=score_result["score"],
        risk_tier=score_result["tier"],
        explanation=explanation,
        mitre_technique=mitre_technique,
        source_ip=resolved_ip,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    chains = ingest_event(resolved_ip, label, alert.id)
    for chain in chains:
        db.add(
            AttackChainRecord(
                chain_name=chain["chain_name"],
                chain_type=chain["chain_type"],
                alert_ids=json.dumps(chain["alert_ids"]),
                source_ip=resolved_ip,
                severity=chain["severity"],
                description=chain["description"],
                detected_at=datetime.now(timezone.utc),
            )
        )
    if chains:
        await db.commit()

    if add_similarity:
        add_to_index(alert.id, clean_log, label, score_result["tier"])

    similar_logs = find_similar(clean_log, top_k=5) if include_similar else []

    return {
        "id": alert.id,
        "log_text": clean_log,
        "label": label,
        "confidence": confidence,
        "risk_score": score_result["score"],
        "risk_tier": score_result["tier"],
        "explanation": explanation,
        "mitre_technique": mitre_technique,
        "source_ip": resolved_ip,
        "timestamp": alert.timestamp,
        "similar_logs": similar_logs,
        "chain_count": len(chains),
    }
