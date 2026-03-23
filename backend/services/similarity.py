"""
Semantic Similarity Service using Sentence-BERT + FAISS.

Model: all-MiniLM-L6-v2 (only 22MB, fast on CPU)
As logs are analyzed, their embeddings are stored in a FAISS index.
/api/similar?alert_id=X returns the 5 most semantically similar past logs.
"""

import numpy as np
import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_model = None
_index = None          # FAISS index
_stored_alerts = []    # parallel list: index i → alert dict

EMBEDDING_DIM = 384    # all-MiniLM-L6-v2 output dimension


def _get_model():
    global _model
    if _model is None:
        logger.info("Loading sentence-transformers/all-MiniLM-L6-v2 (~22MB)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Similarity model loaded.")
    return _model


def _get_index():
    """Lazy-initialize FAISS index."""
    global _index
    if _index is None:
        try:
            import faiss
            _index = faiss.IndexFlatIP(EMBEDDING_DIM)   # Inner product = cosine similarity on normalized vecs
        except ImportError:
            logger.error("faiss-cpu not installed. Run: pip install faiss-cpu")
            raise
    return _index


def add_to_index(alert_id: int, log_text: str, label: str, risk_tier: str):
    """
    Encode a log and add it to the FAISS index.
    Call this after every new alert is created.
    """
    model = _get_model()
    index = _get_index()

    embedding = model.encode([log_text], normalize_embeddings=True)   # shape: (1, 384)
    index.add(np.array(embedding, dtype=np.float32))

    _stored_alerts.append({
        "alert_id": alert_id,
        "log_text": log_text,
        "label": label,
        "risk_tier": risk_tier,
    })


def find_similar(log_text: str, top_k: int = 5) -> list[dict]:
    """
    Find the top_k most semantically similar past logs.

    Returns:
        [{"alert_id": 12, "log_text": "...", "label": "...", "similarity": 0.91}, ...]
    """
    if not _stored_alerts:
        return []

    model = _get_model()
    index = _get_index()

    if index.ntotal == 0:
        return []

    embedding = model.encode([log_text], normalize_embeddings=True)
    query_vec = np.array(embedding, dtype=np.float32)

    k = min(top_k + 1, index.ntotal)   # +1 because the log itself might be in the index
    distances, indices = index.search(query_vec, k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0 or idx >= len(_stored_alerts):
            continue
        alert = _stored_alerts[idx]
        # Skip if it's the exact same text (similarity ≈ 1.0)
        if dist > 0.999:
            continue
        results.append({
            **alert,
            "similarity": round(float(dist), 4),
        })
        if len(results) >= top_k:
            break

    return results