"""
Attack Chain Correlation Engine.

Maintains a sliding time window of events per source IP.
When the sequence of event labels matches a pre-defined attack chain template,
fires an AttackChain detection.

Templates are loaded from backend/data/attack_chains.json.
"""

import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Load attack chain templates once at startup
_TEMPLATES_PATH = Path(__file__).parent.parent / "data" / "attack_chains.json"

def _load_templates() -> list[dict]:
    try:
        with open(_TEMPLATES_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"attack_chains.json not found at {_TEMPLATES_PATH}. No chain detection.")
        return []

ATTACK_TEMPLATES = _load_templates()

# Per-IP event buffer: { source_ip: deque([(timestamp, label, alert_id), ...]) }
_event_buffer: dict[str, deque] = defaultdict(lambda: deque(maxlen=200))


def ingest_event(source_ip: str, label: str, alert_id: int) -> list[dict]:
    """
    Record a new event and check all templates for matches.

    Returns:
        List of detected attack chains (empty list if none detected).
    """
    now = datetime.now(timezone.utc)
    ip = source_ip or "unknown"

    # Add to buffer
    _event_buffer[ip].append((now, label, alert_id))

    # Check each template
    detected = []
    for template in ATTACK_TEMPLATES:
        chain = _check_template(ip, template, now)
        if chain:
            detected.append(chain)

    return detected


def _check_template(ip: str, template: dict, now: datetime) -> dict | None:
    """
    Check if the events for this IP match the given template within its time window.
    Returns a chain dict if matched, None otherwise.
    """
    window_secs = template.get("window_seconds", 300)
    cutoff = now - timedelta(seconds=window_secs)
    sequence = template.get("sequence", [])

    if not sequence:
        return None

    # Filter to events within the window
    recent = [
        (ts, lbl, aid)
        for ts, lbl, aid in _event_buffer[ip]
        if ts >= cutoff
    ]

    if not recent:
        return None

    # Check each step in the sequence is satisfied (order matters)
    matched_events = []
    cursor = 0   # position in recent events list

    for step in sequence:
        required_label = step["label"]
        required_count = step.get("min_count", 1)
        found_count = 0
        step_events = []

        while cursor < len(recent) and found_count < required_count:
            ts, lbl, aid = recent[cursor]
            if lbl == required_label:
                found_count += 1
                step_events.append({"label": lbl, "alert_id": aid, "timestamp": ts.isoformat()})
            cursor += 1

        if found_count < required_count:
            return None   # This step not satisfied → no match

        matched_events.extend(step_events)

    # All steps matched!
    return {
        "chain_name": template["name"],
        "chain_type": template["id"],
        "severity": template["severity"],
        "mitre": template.get("mitre", ""),
        "description": template["description"],
        "source_ip": ip,
        "events": matched_events,
        "detected_at": now.isoformat(),
        "alert_ids": [e["alert_id"] for e in matched_events],
    }


def get_recent_chains_for_ip(ip: str) -> list[str]:
    """Return the labels of recent events for a given IP (for display)."""
    return [lbl for _, lbl, _ in _event_buffer.get(ip, [])]