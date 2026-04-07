"""
LLM service using Ollama (local, free, offline).
Handles two tasks:
  1. explain_log()  — given a log + classification, produce a plain-English threat explanation
  2. chat()         — analyst chat with context of recent alerts
"""

import httpx
import json
import hashlib
import logging
from functools import lru_cache
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Simple in-memory cache so we don't re-run Ollama for the same log twice
_explanation_cache: dict[str, dict] = {}

MITRE_HINTS = {
    "authentication-failed":  "T1110 — Brute Force / Credential Stuffing",
    "privilege-escalation":   "T1068 — Exploitation for Privilege Escalation",
    "network-scan":           "T1046 — Network Service Discovery",
    "ids-alert":              "T1190 — Exploit Public-Facing Application",
    "malware-detected":       "T1059 — Command and Scripting Interpreter",
    "file-deleted":           "T1485 — Data Destruction",
    "data-exfiltration":      "T1041 — Exfiltration Over C2 Channel",
    "process-started":        "T1055 — Process Injection",
    "network-connection":     "T1071 — Application Layer Protocol",
    "configuration-change":   "T1562 — Impair Defenses",
    "user-created":           "T1136 — Create Account",
    "firewall-block":         "T1562.004 — Disable or Modify System Firewall",
}


async def explain_log(
    log_text: str,
    label: str,
    confidence: float,
    risk_score: float,
    risk_tier: str,
) -> dict:
    """
    Ask Mistral to explain this log in plain English.

    Returns:
        {
            "explanation": "This log indicates...",
            "mitre_technique": "T1110 — Brute Force"
        }
    """
    cache_key = hashlib.md5(f"{log_text}{label}".encode()).hexdigest()
    if cache_key in _explanation_cache:
        return _explanation_cache[cache_key]

    mitre_hint = MITRE_HINTS.get(label, "Unknown — requires further investigation")

    prompt = f"""You are a senior cybersecurity analyst working in a Security Operations Center (SOC).

A SIEM system has flagged the following log:

LOG: {log_text}

CLASSIFICATION: {label} (confidence: {confidence:.0%})
RISK SCORE: {risk_score:.0f}/100 — {risk_tier}
MITRE ATT&CK HINT: {mitre_hint}

Provide a concise analysis with exactly these three parts:
1. WHAT HAPPENED: One sentence describing what this log event means technically.
2. WHY IT MATTERS: One sentence explaining the security risk or implication.
3. RECOMMENDED ACTION: One specific action the analyst should take.

Keep your entire response under 100 words. Be direct and specific."""

    result = await _call_ollama(prompt)

    explanation = result.get("response", "Unable to generate explanation.")
    mitre = mitre_hint if label in MITRE_HINTS else _extract_mitre(explanation)

    output = {
        "explanation": explanation.strip(),
        "mitre_technique": mitre,
    }
    _explanation_cache[cache_key] = output
    return output


async def chat_with_analyst(
    message: str,
    history: list[dict],
    recent_alerts: list[dict],
) -> str:
    """
    Answer analyst questions with full context of recent alerts.
    """
    # Build alert context (last 20 alerts, summarized)
    alert_context = _build_alert_context(recent_alerts)

    system_prompt = f"""You are AgentSOC, an intelligent cybersecurity analyst assistant embedded in a SIEM platform.

You have access to the following recent security alerts from the past monitoring period:

{alert_context}

Answer the analyst's questions based on this data. Be concise, accurate, and actionable.
If asked about specific threats, reference the alert data above.
If you don't have enough information, say so clearly.
Keep responses under 150 words unless a detailed breakdown is explicitly requested."""

    # Build conversation history for context
    messages_text = ""
    for msg in history[-6:]:   # last 6 turns only to stay within context
        role = "Analyst" if msg["role"] == "user" else "AgentSOC"
        messages_text += f"\n{role}: {msg['content']}"

    full_prompt = f"{system_prompt}\n\nConversation so far:{messages_text}\n\nAnalyst: {message}\nAgentSOC:"

    result = await _call_ollama(full_prompt)
    return result.get("response", "I was unable to process your question. Please try again.").strip()


async def _call_ollama(prompt: str) -> dict:
    """Low-level HTTP call to the Ollama local server."""
    url = f"{settings.ollama_base_url}/api/generate"
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,      # lower = more focused, less creative
            "num_predict": 200,      # max tokens to generate
        },
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        logger.error("Cannot connect to Ollama. Is it running? Run: ollama serve")
        return {"response": "LLM service unavailable. Please ensure Ollama is running (run: ollama serve)."}
    except httpx.TimeoutException:
        logger.error("Ollama request timed out.")
        return {"response": "LLM response timed out. The model may be loading — please retry in a moment."}
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return {"response": f"LLM error: {str(e)}"}


def _build_alert_context(alerts: list[dict]) -> str:
    """Summarize recent alerts into a compact context string for the LLM."""
    if not alerts:
        return "No recent alerts on record."

    lines = []
    for i, a in enumerate(alerts[:20], 1):
        lines.append(
            f"{i}. [{a.get('risk_tier', '?')}] {a.get('label', '?')} "
            f"(score: {a.get('risk_score', 0):.0f}) "
            f"— {a.get('log_text', '')[:80]}..."
        )
    return "\n".join(lines)


def _extract_mitre(text: str) -> str:
    """Try to pull a MITRE technique ID from LLM output."""
    import re
    match = re.search(r"T\d{4}(?:\.\d{3})?", text)
    if match:
        return match.group(0)
    return "Undetermined — review manually"