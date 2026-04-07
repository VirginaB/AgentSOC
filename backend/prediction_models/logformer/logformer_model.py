"""
logformer_model.py — LogFormer architecture for inference.

Copied from logformer_scratch.py so the ensemble can import it
without needing the full training script.

Place this file in: backend/prediction_models/logformer/logformer_model.py

IMPORTANT: The Vocabulary class MUST be defined here (not just in the
training script) because best_model.pt was pickled with a Vocabulary object
inside it. When torch.load() unpickles the checkpoint, it looks for
'Vocabulary' in whatever module is on sys.path — if it can't find it,
you get: "Can't get attribute 'Vocabulary' on <module '__main__'>"
"""

import math
import torch
import torch.nn as nn


def simple_tokenize(text: str) -> list[str]:
    return str(text).strip().lower().split()


class Vocabulary:
    """Must match the Vocabulary class used during training exactly."""

    def __init__(self, min_freq=5, pad_token="<PAD>", unk_token="<UNK>"):
        self.min_freq  = min_freq
        self.pad_token = pad_token
        self.unk_token = unk_token
        self.word_freq: dict = {}
        self.stoi:      dict = {}
        self.itos:      list = []

    def build(self, texts):
        for text in texts:
            for token in simple_tokenize(text):
                self.word_freq[token] = self.word_freq.get(token, 0) + 1
        self.itos = [self.pad_token, self.unk_token]
        for word, freq in sorted(self.word_freq.items(), key=lambda x: -x[1]):
            if freq >= self.min_freq:
                self.itos.append(word)
        self.stoi = {w: i for i, w in enumerate(self.itos)}

    def encode(self, text, max_len=128):
        tokens = simple_tokenize(text)[:max_len]
        return [self.stoi.get(token, self.stoi[self.unk_token]) for token in tokens]

    def __len__(self):
        return len(self.itos)


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