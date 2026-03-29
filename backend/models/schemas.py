from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ─── Requests ────────────────────────────────────────────────────────────────

class LogInput(BaseModel):
    log_text: str = Field(..., min_length=1, description="Raw log message to analyze")
    source_ip: Optional[str] = Field(None, description="Source IP if known")

class BatchLogInput(BaseModel):
    logs: List[LogInput] = Field(..., max_length=50)


class UploadBatchResult(BaseModel):
    id: int
    log_text: str
    label: str
    risk_tier: str
    source_ip: Optional[str] = None


class UploadResponse(BaseModel):
    filename: str
    processed: int
    skipped: int
    chains_detected: int
    results: List[UploadBatchResult] = []

class ChatMessage(BaseModel):
    role: str          # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []

class FeedbackRequest(BaseModel):
    alert_id: int
    feedback: str      # "correct" | "false_positive" | "missed"
    correct_label: Optional[str] = None


# ─── Responses ───────────────────────────────────────────────────────────────

class ClassificationResult(BaseModel):
    label: str
    confidence: float
    top_labels: List[dict] = []    # [{label, score}]

class RiskScore(BaseModel):
    score: float                   # 0–100
    tier: str                      # LOW / MEDIUM / HIGH / CRITICAL
    factors: dict = {}             # breakdown of what drove the score

class AlertResponse(BaseModel):
    id: Optional[int] = None
    log_text: str
    label: str
    confidence: float
    risk_score: float
    risk_tier: str
    explanation: str
    mitre_technique: str
    source_ip: Optional[str] = None
    timestamp: datetime
    similar_logs: List[dict] = []

class AttackChainResponse(BaseModel):
    id: Optional[int] = None
    chain_name: str
    chain_type: str
    severity: str
    source_ip: str
    description: str
    events: List[dict] = []        # list of alert summaries in the chain
    detected_at: datetime

class ChatResponse(BaseModel):
    reply: str
    sources: List[str] = []        # alert IDs referenced

class FeedbackResponse(BaseModel):
    success: bool
    message: str

class StatsResponse(BaseModel):
    total_logs: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    attack_chains: int
    correct_feedback: int
    false_positives: int
    accuracy_estimate: Optional[float] = None
