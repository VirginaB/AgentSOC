"""
Risk Scoring Service.

Formula:
    score = base_severity × confidence_weight × frequency_weight

Tiers:
    0–30   → LOW
    31–60  → MEDIUM
    61–80  → HIGH
    81–100 → CRITICAL
"""

from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from services.classifier import CATEGORY_BASE_SEVERITY

# Sliding window: track label frequency per source IP (last 5 minutes)
# Structure: { source_ip: deque([(timestamp, label), ...]) }
_frequency_window: dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
WINDOW_SECONDS = 300   # 5 minutes


def compute_risk_score(
    label: str,
    confidence: float,
    source_ip: str = "unknown",
) -> dict:
    """
    Compute a dynamic risk score for a classified log.

    Args:
        label:       Classified event category
        confidence:  Model confidence 0.0–1.0
        source_ip:   Source IP (used for frequency tracking)

    Returns:
        {"score": 74.2, "tier": "HIGH", "factors": {...}}
    """
    now = datetime.now(timezone.utc)

    # 1. Base severity from category
    base = CATEGORY_BASE_SEVERITY.get(label, 30)

    # 2. Confidence weight: scale linearly from 0.7 at low conf to 1.0 at full conf
    #    Minimum floor of 0.7 so low-confidence doesn't obliterate the score entirely
    conf_weight = 0.7 + 0.3 * confidence

    # 3. Frequency boost: count how many times this label appeared from this IP
    #    in the last WINDOW_SECONDS. More repetitions = higher risk.
    window = _frequency_window[source_ip]
    cutoff = now - timedelta(seconds=WINDOW_SECONDS)

    # Evict old entries
    while window and window[0][0] < cutoff:
        window.popleft()

    # Count same-label occurrences
    freq = sum(1 for ts, lbl in window if lbl == label)

    # Log this event
    window.append((now, label))

    # Frequency multiplier: caps at 1.5x after 10 same-type events
    freq_weight = min(1.0 + (freq * 0.05), 1.5)

    # 4. Final score
    raw_score = base * conf_weight * freq_weight
    score = min(round(raw_score, 1), 100.0)

    # 5. Tier
    tier = _score_to_tier(score)

    return {
        "score": score,
        "tier": tier,
        "factors": {
            "base_severity": base,
            "confidence_weight": round(conf_weight, 3),
            "frequency_count": freq,
            "frequency_weight": round(freq_weight, 3),
        },
    }


def _score_to_tier(score: float) -> str:
    if score >= 81:
        return "CRITICAL"
    elif score >= 61:
        return "HIGH"
    elif score >= 31:
        return "MEDIUM"
    else:
        return "LOW"