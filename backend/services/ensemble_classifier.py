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

    logger.info(
        "Ensemble votes | final=%s | confidence=%.2f | votes=%s",
        final_label, confidence, valid,
    )

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
# ═══════════════════════════════════════════════════════════════════════════════

_BASE = r"C:\Users\virgb\New\Desktop\Semester 7\FINAL_YEAR_PROJECT_CODEX\agentsoc\backend\prediction_models"

# ── SVM ───────────────────────────────────────────────────────────────────────

def _load_svm() -> dict:
    import joblib
    return {
        "model":         joblib.load(rf"{_BASE}\svm\svm_tfidf_model.pkl"),
        "vectorizer":    joblib.load(rf"{_BASE}\svm\tfidf_vectorizer.pkl"),
        "label_encoder": joblib.load(rf"{_BASE}\svm\label_encoder.pkl"),
    }

def _predict_svm(data: dict, log_text: str) -> str:
    X    = data["vectorizer"].transform([log_text])
    pred = data["model"].predict(X)[0]
    return data["label_encoder"].inverse_transform([pred])[0]

register_model("svm", _load_svm, _predict_svm)


# ── LSTM ──────────────────────────────────────────────────────────────────────

def _load_lstm() -> dict:
    import sys
    import json
    import torch
    from pathlib import Path

    lstm_dir = Path(rf"{_BASE}\lstm")

    if str(lstm_dir) not in sys.path:
        sys.path.insert(0, str(lstm_dir))

    from lstm_model import BiLSTMClassifier, simple_tokenize

    checkpoint_path = lstm_dir / "best_model.pt"
    device          = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint      = torch.load(str(checkpoint_path), map_location=device, weights_only=False)

    # vocab is saved as a plain stoi dict in this checkpoint
    vocab_stoi    = checkpoint["vocab"]           # { word: index, ... }
    label_classes = checkpoint["label_classes"]   # ["auth-failed", "network-scan", ...]
    cfg           = checkpoint.get("config", {})

    model = BiLSTMClassifier(
        vocab_size   = len(vocab_stoi),
        embed_dim    = cfg.get("EMBED_DIM",   128),
        hidden_dim   = cfg.get("HIDDEN_DIM",  128),
        num_layers   = cfg.get("NUM_LAYERS",  1),
        num_classes  = len(label_classes),
        dropout      = cfg.get("DROPOUT",     0.3),
        bidirectional = True,
    ).to(device)

    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    logger.info(
        "LSTM loaded — vocab=%d  classes=%d  device=%s",
        len(vocab_stoi), len(label_classes), device,
    )

    return {
        "model":         model,
        "vocab":         vocab_stoi,
        "label_classes": label_classes,
        "device":        device,
        "max_len":       cfg.get("MAX_LEN", 150),
        "tokenize":      simple_tokenize,
    }


def _predict_lstm(data: dict, log_text: str) -> str:
    import torch

    vocab    = data["vocab"]
    max_len  = data["max_len"]
    device   = data["device"]
    unk_idx  = vocab.get("<UNK>", 1)

    tokens  = data["tokenize"](log_text)
    encoded = [vocab.get(t, unk_idx) for t in tokens[:max_len]]
    if not encoded:
        encoded = [unk_idx]

    x       = torch.tensor([encoded], dtype=torch.long).to(device)
    lengths = torch.tensor([len(encoded)], dtype=torch.long).to(device)

    with torch.no_grad():
        logits = data["model"](x, lengths)
        pred   = int(torch.argmax(logits, dim=1).item())

    return data["label_classes"][pred]


register_model("lstm", _load_lstm, _predict_lstm)


# ── BERT ──────────────────────────────────────────────────────────────────────

def _load_bert() -> dict:
    raise NotImplementedError

def _predict_bert(data: dict, log_text: str) -> str:
    import torch
    inputs = data["tokenizer"](log_text, return_tensors="pt", truncation=True, max_length=128)
    with torch.no_grad():
        logits = data["model"](**inputs).logits
    return data["classes"][int(logits.argmax())]

register_model("bert", _load_bert, _predict_bert)


# ── SBERT ─────────────────────────────────────────────────────────────────────

def _load_sbert() -> dict:
    import pickle
    from sentence_transformers import SentenceTransformer

    prototype_path = rf"{_BASE}\sbert_approach3\version1_prototypes_mean.pkl"
    with open(prototype_path, "rb") as f:
        proto_data = pickle.load(f)

    model        = SentenceTransformer("all-MiniLM-L6-v2")
    labels_list  = sorted(proto_data["prototypes"].keys())
    proto_matrix = [proto_data["prototypes"][lbl] for lbl in labels_list]

    return {
        "model":            model,
        "labels_list":      labels_list,
        "prototype_matrix": proto_matrix,
        "label_classes":    proto_data["label_classes"],
    }

def _predict_sbert(data: dict, log_text: str) -> str:
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity

    emb      = data["model"].encode([log_text], normalize_embeddings=False)
    sims     = cosine_similarity(emb, data["prototype_matrix"])[0]
    best_idx = int(np.argmax(sims))
    label_id = data["labels_list"][best_idx]
    return data["label_classes"][label_id]

register_model("sbert", _load_sbert, _predict_sbert)


# ── Logformer ─────────────────────────────────────────────────────────────────

def _load_logformer() -> dict:
    import sys
    import __main__
    import torch
    from pathlib import Path

    logformer_dir = Path(rf"{_BASE}\logformer")

    if str(logformer_dir) not in sys.path:
        sys.path.insert(0, str(logformer_dir))

    from logformer_model import LogFormer, Vocabulary, simple_tokenize

    # The checkpoint was saved while the training script ran as __main__,
    # so pickle serialised Vocabulary as __main__.Vocabulary.
    # Patching __main__ lets torch.load find the class during unpickling.
    if not hasattr(__main__, "Vocabulary"):
        __main__.Vocabulary = Vocabulary
    if not hasattr(__main__, "simple_tokenize"):
        __main__.simple_tokenize = simple_tokenize

    checkpoint_path = logformer_dir / "best_model.pt"
    device          = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint      = torch.load(str(checkpoint_path), map_location=device, weights_only=False)

    vocab         = checkpoint["vocab"]
    label_encoder = checkpoint["label_encoder"]
    cfg           = checkpoint.get("config", {})

    # checkpoint["vocab"] is a Vocabulary object — get its stoi dict
    vocab_stoi = vocab.stoi if hasattr(vocab, "stoi") else vocab
    vocab_size = len(vocab_stoi)

    model = LogFormer(
        vocab_size  = vocab_size,
        embed_dim   = cfg.get("EMBED_DIM",   256),
        num_heads   = cfg.get("NUM_HEADS",   4),
        num_layers  = cfg.get("NUM_LAYERS",  4),
        ffn_dim     = cfg.get("FFN_DIM",     1024),
        num_classes = len(label_encoder.classes_),
        dropout     = cfg.get("DROPOUT",     0.1),
        max_len     = cfg.get("MAX_SEQ_LEN", 128),
        pad_idx     = vocab_stoi.get("<PAD>", 0),
    ).to(device)

    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    logger.info(
        "LogFormer loaded — vocab=%d  classes=%d  device=%s",
        vocab_size, len(label_encoder.classes_), device,
    )

    return {
        "model":         model,
        "vocab":         vocab_stoi,
        "label_encoder": label_encoder,
        "device":        device,
        "max_len":       cfg.get("MAX_SEQ_LEN", 128),
        "tokenize":      simple_tokenize,
    }


def _predict_logformer(data: dict, log_text: str) -> str:
    import torch

    vocab    = data["vocab"]
    max_len  = data["max_len"]
    device   = data["device"]
    unk_idx  = vocab.get("<UNK>", 1)

    tokens  = data["tokenize"](log_text)
    encoded = [vocab.get(t, unk_idx) for t in tokens[:max_len]]
    if not encoded:
        encoded = [unk_idx]

    x       = torch.tensor([encoded], dtype=torch.long).to(device)
    lengths = torch.tensor([len(encoded)], dtype=torch.long).to(device)

    with torch.no_grad():
        logits = data["model"](x, lengths)
        pred   = int(torch.argmax(logits, dim=1).item())

    return data["label_encoder"].inverse_transform([pred])[0]


register_model("logformer", _load_logformer, _predict_logformer)