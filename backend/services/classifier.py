"""
classifier.py — Log classification entry point.

Tries the ensemble first. Falls back to zero-shot BART if no ensemble
models are available (e.g. during early development).

Nothing else in the codebase needs to change — classify_log() interface
is identical to before.
"""

import logging
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SIEVE_CATEGORIES = [
    "authentication-failed", "authentication-success", "privilege-escalation",
    "file-access", "file-modified", "file-deleted", "file-created",
    "process-started", "process-terminated", "network-connection",
    "network-scan", "network-blocked", "ids-alert", "malware-detected",
    "http-request-success", "http-request-failed", "dns-query", "ssh-session",
    "ftp-transfer", "email-sent", "email-received", "user-created",
    "user-deleted", "user-modified", "system-error", "system-startup",
    "system-shutdown", "firewall-allow", "firewall-block", "configuration-change",
]

CATEGORY_BASE_SEVERITY = {
    "authentication-failed": 55, "authentication-success": 10,
    "privilege-escalation": 88, "file-access": 30, "file-modified": 45,
    "file-deleted": 60, "file-created": 25, "process-started": 35,
    "process-terminated": 20, "network-connection": 30, "network-scan": 72,
    "network-blocked": 50, "ids-alert": 90, "malware-detected": 95,
    "http-request-success": 5, "http-request-failed": 20, "dns-query": 10,
    "ssh-session": 40, "ftp-transfer": 35, "email-sent": 10,
    "email-received": 10, "user-created": 40, "user-deleted": 50,
    "user-modified": 45, "system-error": 30, "system-startup": 5,
    "system-shutdown": 15, "firewall-allow": 5, "firewall-block": 40,
    "configuration-change": 50,
}

# ─── Zero-shot fallback ───────────────────────────────────────────────────────

_zeroshot = None

def _get_zeroshot():
    global _zeroshot
    if _zeroshot is None:
        from transformers import pipeline
        logger.info(f"Loading zero-shot classifier: {settings.classifier_model}")
        _zeroshot = pipeline("zero-shot-classification",
                             model=settings.classifier_model, device=-1)
        logger.info("Zero-shot classifier loaded.")
    return _zeroshot

def _zeroshot_classify(log_text: str) -> dict:
    clf    = _get_zeroshot()
    result = clf(_preprocess(log_text), candidate_labels=SIEVE_CATEGORIES, multi_label=False)
    return {
        "label":      result["labels"][0],
        "confidence": round(result["scores"][0], 4),
        "top_labels": [{"label": l, "score": round(s, 4)}
                       for l, s in zip(result["labels"][:5], result["scores"][:5])],
        "method":     "zero_shot",
    }

# ─── Public API ───────────────────────────────────────────────────────────────

def classify_log(log_text: str) -> dict:
    clean = _preprocess(log_text)

    if getattr(settings, "use_ensemble", True):
        try:
            from services.ensemble_classifier import ensemble_classify
            result = ensemble_classify(clean)
            result.setdefault("top_labels",
                              [{"label": result["label"], "score": result["confidence"]}])
            return result
        except RuntimeError as e:
            # All models failed/not implemented — fall through to zero-shot
            logger.warning(f"Ensemble unavailable ({e}). Using zero-shot.")
        except Exception as e:
            logger.error(f"Ensemble error: {e}. Using zero-shot.")

    return _zeroshot_classify(clean)


def get_classifier():
    """Called by main.py prewarm. Loads whichever classifier is active."""
    if getattr(settings, "use_ensemble", True):
        try:
            from services.ensemble_classifier import prewarm
            prewarm()
            return
        except Exception:
            pass
    _get_zeroshot()


def _preprocess(log_text: str) -> str:
    import re
    text = log_text.strip().lower()
    text = re.sub(r"\[\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^\]]*\]", "", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\S*", "", text)
    text = re.sub(r"\(pid=\d+\)", "", text)
    text = re.sub(r"\[\d{3,6}\]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if text else log_text