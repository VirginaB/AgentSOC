"""
Log classifier using HuggingFace zero-shot classification.
Model: facebook/bart-large-mnli (no training needed)

The 30 SIEVE categories are used directly as candidate labels.
When you're ready to swap in your Phase I fine-tuned BERT,
just replace the _classify_single method — the interface stays the same.
"""

from transformers import pipeline
from config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# The 30 SIEVE event categories — these are your classification targets
SIEVE_CATEGORIES = [
    "authentication-failed",
    "authentication-success",
    "privilege-escalation",
    "file-access",
    "file-modified",
    "file-deleted",
    "file-created",
    "process-started",
    "process-terminated",
    "network-connection",
    "network-scan",
    "network-blocked",
    "ids-alert",
    "malware-detected",
    "http-request-success",
    "http-request-failed",
    "dns-query",
    "ssh-session",
    "ftp-transfer",
    "email-sent",
    "email-received",
    "user-created",
    "user-deleted",
    "user-modified",
    "system-error",
    "system-startup",
    "system-shutdown",
    "firewall-allow",
    "firewall-block",
    "configuration-change",
]

# Severity baseline per category (used by the risk scorer)
CATEGORY_BASE_SEVERITY = {
    "authentication-failed": 55,
    "authentication-success": 10,
    "privilege-escalation": 88,
    "file-access": 30,
    "file-modified": 45,
    "file-deleted": 60,
    "file-created": 25,
    "process-started": 35,
    "process-terminated": 20,
    "network-connection": 30,
    "network-scan": 72,
    "network-blocked": 50,
    "ids-alert": 90,
    "malware-detected": 95,
    "http-request-success": 5,
    "http-request-failed": 20,
    "dns-query": 10,
    "ssh-session": 40,
    "ftp-transfer": 35,
    "email-sent": 10,
    "email-received": 10,
    "user-created": 40,
    "user-deleted": 50,
    "user-modified": 45,
    "system-error": 30,
    "system-startup": 5,
    "system-shutdown": 15,
    "firewall-allow": 5,
    "firewall-block": 40,
    "configuration-change": 50,
}

_classifier = None


def get_classifier():
    """Lazy-load the classifier (only on first call — model is ~1.6GB)."""
    global _classifier
    if _classifier is None:
        logger.info(f"Loading classifier model: {settings.classifier_model}")
        logger.info("This will take ~60 seconds on first load and download ~1.6GB...")
        _classifier = pipeline(
            "zero-shot-classification",
            model=settings.classifier_model,
            device=-1,         # CPU. Change to 0 if you have a GPU.
        )
        logger.info("Classifier model loaded successfully.")
    return _classifier


def classify_log(log_text: str) -> dict:
    """
    Classify a single log message.

    Returns:
        {
            "label": "authentication-failed",
            "confidence": 0.91,
            "top_labels": [
                {"label": "authentication-failed", "score": 0.91},
                {"label": "network-scan", "score": 0.05},
                ...
            ]
        }
    """
    clf = get_classifier()

    # Preprocess: strip timestamps, IPs, PIDs — keep the meaningful tokens
    clean_log = _preprocess(log_text)

    result = clf(
        clean_log,
        candidate_labels=SIEVE_CATEGORIES,
        multi_label=False,
    )

    top_labels = [
        {"label": label, "score": round(score, 4)}
        for label, score in zip(result["labels"][:5], result["scores"][:5])
    ]

    return {
        "label": result["labels"][0],
        "confidence": round(result["scores"][0], 4),
        "top_labels": top_labels,
    }


def _preprocess(log_text: str) -> str:
    """
    Light preprocessing: lowercase, remove pure noise tokens.
    Keeps IPs/usernames because they're semantically useful for zero-shot.
    """
    import re

    text = log_text.strip().lower()

    # Remove common noise: timestamps like [2024-01-01 12:00:00]
    text = re.sub(r"\[\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^\]]*\]", "", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\S*", "", text)

    # Remove PID-like patterns: [1234] or (pid=1234)
    text = re.sub(r"\(pid=\d+\)", "", text)
    text = re.sub(r"\[\d{3,6}\]", "", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text if text else log_text  # fallback to original if preprocessing empties it