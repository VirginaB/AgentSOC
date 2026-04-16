"""
mitre.py — MITRE ATT&CK lookup router.

GET /api/mitre/{technique_id}   — fetch by T-code (e.g. T1110 or T1110.001)
GET /api/mitre/by-label/{label} — fetch by classifier label (e.g. authentication-failed)

Data is loaded once at first request from backend/data/mitre_techniques.json.
No internet connection required.
"""

import json
import logging
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mitre", tags=["mitre"])

_TECHNIQUES_PATH = Path(__file__).parent.parent / "data" / "mitre_techniques.json"

# Maps every classifier label → MITRE technique ID
LABEL_TO_TECHNIQUE: dict[str, str] = {
    "authentication-failed":  "T1110",
    "authentication-success": "T1078",
    "privilege-escalation":   "T1068",
    "file-access":            "T1083",
    "file-modified":          "T1565",
    "file-deleted":           "T1485",
    "file-created":           "T1074",
    "process-started":        "T1055",
    "process-terminated":     "T1489",
    "network-connection":     "T1071",
    "network-scan":           "T1046",
    "network-blocked":        "T1562",
    "ids-alert":              "T1190",
    "malware-detected":       "T1059",
    "http-request-success":   "T1190",
    "http-request-failed":    "T1190",
    "dns-query":              "T1071.004",
    "ssh-session":            "T1021",
    "ftp-transfer":           "T1048",
    "email-sent":             "T1566",
    "email-received":         "T1566",
    "user-created":           "T1136",
    "user-deleted":           "T1531",
    "user-modified":          "T1098",
    "system-error":           "T1562",
    "system-startup":         "T1547",
    "system-shutdown":        "T1529",
    "firewall-allow":         "T1562",
    "firewall-block":         "T1562.004",
    "configuration-change":   "T1562",
}

_techniques: dict = {}


def _load_techniques() -> dict:
    global _techniques
    if not _techniques:
        try:
            with open(_TECHNIQUES_PATH, encoding="utf-8") as f:
                _techniques = json.load(f)
            logger.info(f"MITRE techniques loaded: {len(_techniques)} entries.")
        except FileNotFoundError:
            logger.error(f"mitre_techniques.json not found at {_TECHNIQUES_PATH}")
            _techniques = {}
    return _techniques


def _normalize_id(raw: str) -> str:
    """Extract a clean T-code from strings like 'T1110 — Brute Force'."""
    match = re.match(r"(T\d{4}(?:\.\d{3})?)", raw.strip())
    return match.group(1) if match else raw.strip()


@router.get("/by-label/{label}")
async def get_mitre_by_label(label: str):
    """
    Look up MITRE ATT&CK data by classifier label.
    Returns the technique entry for this event category.
    """
    technique_id = LABEL_TO_TECHNIQUE.get(label)
    if not technique_id:
        raise HTTPException(
            status_code=404,
            detail=f"No MITRE mapping found for label '{label}'.",
        )
    techniques = _load_techniques()
    entry = techniques.get(technique_id)
    if not entry:
        raise HTTPException(
            status_code=404,
            detail=f"Technique {technique_id} not found in local database.",
        )
    return entry


@router.get("/{technique_id:path}")
async def get_mitre_technique(technique_id: str):
    """
    Look up MITRE ATT&CK data by technique ID.
    Accepts raw IDs (T1110) or strings like 'T1110 — Brute Force'.
    """
    clean_id = _normalize_id(technique_id)
    techniques = _load_techniques()
    entry = techniques.get(clean_id)
    if not entry:
        raise HTTPException(
            status_code=404,
            detail=f"Technique '{clean_id}' not found in local database.",
        )
    return entry
