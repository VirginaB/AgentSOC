"""
lstm_model.py — BiLSTM architecture for inference.

Copied from lstm_text_all_versions_optimized.py so the ensemble
can import it without needing the full training script.

Place this file in: backend/prediction_models/lstm_out/lstm_model.py
"""

import torch
import torch.nn as nn


def simple_tokenize(text: str) -> list[str]:
    return str(text).strip().split()


class BiLSTMClassifier(nn.Module):
    def __init__(
        self,
        vocab_size,
        embed_dim=128,
        hidden_dim=128,
        num_layers=1,
        num_classes=2,
        dropout=0.3,
        bidirectional=True,
    ):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.lstm = nn.LSTM(
            embed_dim,
            hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=bidirectional,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.drop = nn.Dropout(dropout)
        factor = 2 if bidirectional else 1
        self.fc = nn.Linear(hidden_dim * factor, num_classes)
        self.bidirectional = bidirectional

    def forward(self, x, lengths=None):
        emb = self.embedding(x)
        if lengths is None or lengths.sum().item() == 0:
            logits = self.fc(self.drop(emb.mean(dim=1)))
            return logits
        packed = nn.utils.rnn.pack_padded_sequence(
            emb, lengths.cpu(), batch_first=True, enforce_sorted=False
        )
        _, (hn, _) = self.lstm(packed)
        last = torch.cat([hn[-2], hn[-1]], dim=1) if self.bidirectional else hn[-1]
        return self.fc(self.drop(last))