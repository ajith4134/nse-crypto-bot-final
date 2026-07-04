"""AI-scientist idea #6 — LiT: Limit-Order-Book Transformer for short-horizon direction.

A self-attention encoder over microstructure features. Where the psychology engine hand-crafts
OBI / OFI / microprice / depth-slope, LiT LEARNS the interactions: the feature vector is reshaped
into a short token sequence (LOB "levels" / feature groups), each token is embedded + positionally
encoded, a small Transformer encoder attends across them, and an attention-pooled summary → a
logistic head predicts next-bar direction. Robust-to-regime by construction (attention re-weights
per input rather than using fixed coefficients).

Reuse-first: uses torch's built-in ``nn.TransformerEncoder`` (the standard, well-tested
implementation). Graceful logistic fallback if torch is absent — same NodeProtocol either way.
CPU-sized by default.
"""
from __future__ import annotations

import math

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector

try:
    import torch
    import torch.nn as nn
    _HAS_TORCH = True
except Exception:
    _HAS_TORCH = False


if _HAS_TORCH:
    class _PosEnc(nn.Module):
        def __init__(self, d_model: int, max_len: int = 64):
            super().__init__()
            pe = torch.zeros(max_len, d_model)
            pos = torch.arange(0, max_len).unsqueeze(1).float()
            div = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
            pe[:, 0::2] = torch.sin(pos * div)
            pe[:, 1::2] = torch.cos(pos * div[: pe[:, 1::2].shape[1]])
            self.register_buffer("pe", pe.unsqueeze(0))

        def forward(self, x):                      # x: (B, T, d_model)
            return x + self.pe[:, : x.size(1)]

    class _LiT(nn.Module):
        def __init__(self, token_dim: int, seq_len: int, d_model: int = 32, heads: int = 4,
                     layers: int = 2):
            super().__init__()
            self.proj = nn.Linear(token_dim, d_model)
            self.pos = _PosEnc(d_model, max_len=seq_len + 1)
            self.cls = nn.Parameter(torch.zeros(1, 1, d_model))     # attention-pool token
            enc = nn.TransformerEncoderLayer(d_model, heads, dim_feedforward=2 * d_model,
                                             batch_first=True, dropout=0.0)
            self.enc = nn.TransformerEncoder(enc, layers)
            self.head = nn.Sequential(nn.Linear(d_model, d_model), nn.ReLU(), nn.Linear(d_model, 1))

        def forward(self, tokens):                 # tokens: (B, T, token_dim)
            B = tokens.size(0)
            h = self.proj(tokens)
            cls = self.cls.expand(B, -1, -1)
            h = self.pos(torch.cat([cls, h], dim=1))
            h = self.enc(h)
            return self.head(h[:, 0]).squeeze(-1)  # CLS-token readout → logit


class LOBTransformerNode(BaseNode):
    """LiT — transformer over LOB/microstructure feature tokens → p(up)."""

    kind = "lob_transformer"

    def __init__(self, name: str = "lob_transformer", token_dim: int = 4, d_model: int = 32,
                 heads: int = 4, layers: int = 2, epochs: int = 40, max_rows: int = 2000):
        self.name = name
        self.summary = ("LiT order-book transformer: self-attention over microstructure feature "
                        "tokens for short-horizon direction (learned, not hand-crafted OBI/microprice).")
        self.token_dim = int(token_dim)
        self.d_model = int(d_model)
        self.heads = int(heads)
        self.layers = int(layers)
        self.epochs = int(epochs)
        self.max_rows = int(max_rows)
        self.task = "binary"
        self.head = "y"
        self.schema = IOSchema(0, "microstructure/LOB feature rows", "p(up)")
        self._net = None
        self._mean = None
        self._std = None
        self._seq_len = 0
        self._pad = 0
        self._clf = None
        self.fell_back = False

    def _z(self, A):
        return (A - self._mean) / self._std

    def _tokens(self, Az: np.ndarray):
        """Reshape (B, d) → (B, seq_len, token_dim), zero-padding d up to a multiple of token_dim."""
        B, d = Az.shape
        if self._pad:
            Az = np.concatenate([Az, np.zeros((B, self._pad), np.float32)], axis=1)
        return torch.as_tensor(Az.reshape(B, self._seq_len, self.token_dim), dtype=torch.float32)

    def fit(self, X: Matrix, y: Labels) -> "LOBTransformerNode":
        A = np.asarray(X, dtype=np.float32)
        ya = np.asarray(y).astype(int)
        self.schema = IOSchema(A.shape[1], f"{A.shape[1]} microstructure features", "p(up)")
        self._mean = A.mean(0); self._std = A.std(0) + 1e-8
        if len(A) > self.max_rows:
            idx = np.random.default_rng(0).permutation(len(A))[: self.max_rows]; idx.sort()
            A, ya = A[idx], ya[idx]
        Az = self._z(A)

        if not _HAS_TORCH or len(set(ya.tolist())) < 2:
            from sklearn.linear_model import LogisticRegression
            self.fell_back = True
            self._clf = LogisticRegression(max_iter=500).fit(Az, ya) if len(set(ya.tolist())) >= 2 else None
            return self

        d = Az.shape[1]
        self._pad = (-d) % self.token_dim
        self._seq_len = (d + self._pad) // self.token_dim
        torch.manual_seed(0)
        self._net = _LiT(self.token_dim, self._seq_len, self.d_model, self.heads, self.layers)
        opt = torch.optim.Adam(self._net.parameters(), lr=3e-3)
        tok = self._tokens(Az)
        yt = torch.as_tensor(ya, dtype=torch.float32)
        lossf = nn.BCEWithLogitsLoss()
        self._net.train()
        bs = 256
        for _ in range(self.epochs):
            perm = torch.randperm(tok.size(0))
            for s in range(0, tok.size(0), bs):
                idx = perm[s: s + bs]
                opt.zero_grad()
                lossf(self._net(tok[idx]), yt[idx]).backward()
                opt.step()
        self._net.eval()
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        A = np.asarray(X, dtype=np.float32)
        Az = self._z(A)
        if self.fell_back or self._net is None:
            if self._clf is None:
                return [0.5] * len(A)
            return self._clf.predict_proba(Az)[:, 1].tolist()
        with torch.no_grad():
            p = torch.sigmoid(self._net(self._tokens(Az))).cpu().numpy()
        return p.tolist()

    def predict(self, X: Matrix) -> Labels:
        return [1 if p >= 0.5 else 0 for p in self.predict_proba(X)]


def lob_transformer_node(name: str = "lob_transformer") -> LOBTransformerNode:
    """Zero-arg factory (pool + autoload convention)."""
    return LOBTransformerNode(name=name)
