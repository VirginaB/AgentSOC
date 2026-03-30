"""
ensemble_classifier.py  —  Modular majority-vote ensemble.

HOW TO ADD A NEW MODEL
──────────────────────
1. Write a loader function that returns a dict:

    def _load_mymodel() -> dict:
        import joblib
        return {"pipeline": joblib.load("models/mymodel.joblib"), "classes": LABELS}

2. Write a predict function that returns a label string:

    def _predict_mymodel(data: dict, log_text: str) -> str:
        return data["classes"][data["pipeline"].predict([log_text])[0]]

3. Register it (one line):

    register_model("mymodel", _load_mymodel, _predict_mymodel)

Nothing else needs to change. Models with NotImplementedError loaders are
automatically skipped — the ensemble runs with however many are ready.
"""

import logging
from collections import Counter
from typing import Callable

logger = logging.getLogger(__name__)

from services.classifier import SIEVE_CATEGORIES as LABELS


# ─── Registry ─────────────────────────────────────────────────────────────────

class _ModelEntry:
    def __init__(self, name, loader_fn, predict_fn):
        self.name       = name
        self.loader_fn  = loader_fn
        self.predict_fn = predict_fn
        self._data      = None
        self._failed    = False

    def predict(self, log_text: str) -> str | None:
        if self._failed:
            return None
        if self._data is None:
            try:
                logger.info(f"Loading model: {self.name}")
                self._data = self.loader_fn()
                logger.info(f"Model loaded: {self.name}")
            except NotImplementedError:
                logger.warning(f"Model '{self.name}' not implemented yet — skipping.")
                self._failed = True
                return None
            except Exception as e:
                logger.error(f"Model '{self.name}' failed to load: {e}")
                self._failed = True
                return None
        try:
            return self.predict_fn(self._data, log_text)
        except Exception as e:
            logger.warning(f"Model '{self.name}' predict error: {e}")
            return None


_registry: dict[str, _ModelEntry] = {}


def register_model(name: str, loader_fn: Callable, predict_fn: Callable):
    _registry[name] = _ModelEntry(name, loader_fn, predict_fn)


# ─── Main ensemble function ───────────────────────────────────────────────────

def ensemble_classify(log_text: str) -> dict:
    """
    Run all registered, available models and return the majority-vote label.

    Returns:
        {
            "label":       "authentication-failed",
            "confidence":  0.67,           # fraction of models that agreed
            "method":      "majority_vote",
            "model_votes": {"svm": "authentication-failed", "bert": "network-scan", ...},
            "vote_counts": {"authentication-failed": 2, "network-scan": 1},
            "top_labels":  [{"label": "authentication-failed", "score": 0.67}]
        }
    """
    if not _registry:
        raise RuntimeError("No models registered in ensemble.")

    raw_votes: dict[str, str | None] = {
        name: entry.predict(log_text)
        for name, entry in _registry.items()
    }

    valid = {k: v for k, v in raw_votes.items() if v is not None}

    if not valid:
        raise RuntimeError("All ensemble models failed to predict.")

    counts = Counter(valid.values())
    final_label, top_count = counts.most_common(1)[0]
    confidence = round(top_count / len(valid), 4)

    top_labels = [
        {"label": lbl, "score": round(cnt / len(valid), 4)}
        for lbl, cnt in counts.most_common()
    ]

    return {
        "label":       final_label,
        "confidence":  confidence,
        "method":      "majority_vote",
        "model_votes": raw_votes,
        "vote_counts": dict(counts),
        "top_labels":  top_labels,
    }


def prewarm():
    """Pre-load all registered models. Call at startup."""
    for entry in _registry.values():
        if not entry._failed and entry._data is None:
            entry.predict("prewarm")


# ═══════════════════════════════════════════════════════════════════════════════
#  MODEL DEFINITIONS
#  ↓ Fill in the loaders for the models you have. Leave the rest as-is.
# ═══════════════════════════════════════════════════════════════════════════════

# ── SVM ───────────────────────────────────────────────────────────────────────


def _load_svm() -> dict:
    import joblib

    model = joblib.load(
        r"C:\Users\virgb\New\Desktop\Semester 7\FINAL_YEAR_PROJECT_CODEX\agentsoc\backend\prediction_models\svm\svm_tfidf_model.pkl"
    )

    vectorizer = joblib.load(
        r"C:\Users\virgb\New\Desktop\Semester 7\FINAL_YEAR_PROJECT_CODEX\agentsoc\backend\prediction_models\svm\tfidf_vectorizer.pkl"
    )

    label_encoder = joblib.load(
        r"C:\Users\virgb\New\Desktop\Semester 7\FINAL_YEAR_PROJECT_CODEX\agentsoc\backend\prediction_models\svm\label_encoder.pkl"
    )

    return {
        "model": model,
        "vectorizer": vectorizer,
        "label_encoder": label_encoder,
    }

def _predict_svm(data: dict, log_text: str) -> str:
    X = data["vectorizer"].transform([log_text])
    pred = data["model"].predict(X)[0]
    label = data["label_encoder"].inverse_transform([pred])[0]
    return label

register_model("svm", _load_svm, _predict_svm)


# ── LSTM ──────────────────────────────────────────────────────────────────────

def _load_lstm() -> dict:
    raise NotImplementedError   # ← implement when ready

def _predict_lstm(data: dict, log_text: str) -> str:
    import torch, numpy as np
    seq = data["tokenizer"].encode(log_text)[:data["max_len"]]
    seq += [0] * (data["max_len"] - len(seq))
    with torch.no_grad():
        logits = data["model"](torch.tensor([seq]))
    return data["classes"][int(logits.argmax())]

register_model("lstm", _load_lstm, _predict_lstm)


# ── BERT ──────────────────────────────────────────────────────────────────────

def _load_bert() -> dict:
    raise NotImplementedError   # ← implement when ready

def _predict_bert(data: dict, log_text: str) -> str:
    import torch
    inputs = data["tokenizer"](log_text, return_tensors="pt", truncation=True, max_length=128)
    with torch.no_grad():
        logits = data["model"](**inputs).logits
    return data["classes"][int(logits.argmax())]

register_model("bert", _load_bert, _predict_bert)


# ── SBERT ─────────────────────────────────────────────────────────────────────

def _load_sbert() -> dict:
    raise NotImplementedError   # ← implement when ready

def _predict_sbert(data: dict, log_text: str) -> str:
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    emb  = data["model"].encode([log_text], normalize_embeddings=True)
    sims = cosine_similarity(emb, data["class_embeddings"])[0]
    return data["classes"][int(np.argmax(sims))]

register_model("sbert", _load_sbert, _predict_sbert)


# ── Logformer ─────────────────────────────────────────────────────────────────

def _load_logformer() -> dict:
    raise NotImplementedError   # ← implement when ready

def _predict_logformer(data: dict, log_text: str) -> str:
    import torch
    inputs = data["tokenizer"](log_text, return_tensors="pt", truncation=True, max_length=128)
    with torch.no_grad():
        out    = data["model"](**inputs)
        logits = out.logits if hasattr(out, "logits") else out
    return data["classes"][int(logits.argmax())]

register_model("logformer", _load_logformer, _predict_logformer)