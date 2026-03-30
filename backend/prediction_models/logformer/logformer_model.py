"""
logformer_model.py — LogFormer architecture for inference.

Copied from logformer_scratch.py so the ensemble can import it
without needing the full training script.

Place this file in: backend/prediction_models/logformer/logformer_model.py
"""

import math
import torch
import torch.nn as nn


def simple_tokenize(text: str) -> list[str]:
    return str(text).strip().lower().split()


class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=5000):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        self.register_buffer("pe", pe)

    def forward(self, x):
        return x + self.pe[:, : x.size(1)]


class LogFormer(nn.Module):
    def __init__(
        self,
        vocab_size,
        embed_dim=256,
        num_heads=4,
        num_layers=4,
        ffn_dim=1024,
        num_classes=29,
        dropout=0.1,
        max_len=128,
        pad_idx=0,
    ):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=pad_idx)
        self.pos_encoding = PositionalEncoding(embed_dim, max_len)
        self.dropout = nn.Dropout(dropout)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=num_heads,
            dim_feedforward=ffn_dim,
            dropout=dropout,
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.fc = nn.Linear(embed_dim, num_classes)
        self.pad_idx = pad_idx

    def forward(self, x, lengths=None):
        mask = x == self.pad_idx
        x = self.embedding(x)
        x = self.pos_encoding(x)
        x = self.dropout(x)
        x = self.transformer(x, src_key_padding_mask=mask)

        if lengths is not None:
            mask_expanded = mask.unsqueeze(-1).expand(x.size())
            sum_embeddings = torch.sum(x * ~mask_expanded, dim=1)
            lengths_clamped = lengths.clamp(min=1).unsqueeze(-1)
            x = sum_embeddings / lengths_clamped.float()
        else:
            x = x.mean(dim=1)

        return self.fc(x)