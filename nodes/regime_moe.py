"""AI-scientist idea #7 — Regime-conditioned MoE router (learned gating over frozen experts).

A Mixture-of-Experts node in the project's DGMG spirit ("differentiable gates over frozen
experts"): several diverse experts are fit once and FROZEN, then a small torch gating network learns
— conditioned on the feature vector (which carries the regime signal: vol, trend, microstructure) —
how much to weight each expert PER ROW. So the router picks the best model *per detected regime*,
end-to-end, instead of a static average or a single winner.

  p(y=1 | x) = Σ_e  softmax(gate(x))_e · expert_e.predict_proba(x)

Graceful degradation: if torch is absent the gate falls back to a fixed uniform mixture (still a
valid NodeProtocol node). CPU-sized by default.
"""
from __future__ import annotations

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector

try:
    import torch
    import torch.nn as nn
    _HAS_TORCH = True
except Exception:
    _HAS_TORCH = False


def _default_experts():
    """A diverse, frozen expert bank (different inductive biases → different regime strengths)."""
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.neighbors import KNeighborsClassifier
    return [
        ("logistic", LogisticRegression(max_iter=500)),
        ("rf", RandomForestClassifier(n_estimators=60, max_depth=6, random_state=0)),
        ("gb", GradientBoostingClassifier(random_state=0)),
        ("knn", KNeighborsClassifier(n_neighbors=15)),
    ]


class RegimeMoERouter(BaseNode):
    """Regime-conditioned Mixture-of-Experts: frozen expert bank + learned per-row torch gate."""

    kind = "regime_moe"

    def __init__(self, name: str = "regime_moe", gate_hidden: int = 16, epochs: int = 120,
                 val_frac: float = 0.3):
        self.name = name
        self.summary = ("Regime-conditioned MoE: a learned gate weights frozen diverse experts "
                        "per row by the regime the features imply (DGMG differentiable gating).")
        self.gate_hidden = int(gate_hidden)
        self.epochs = int(epochs)
        self.val_frac = float(val_frac)
        self.task = "binary"
        self.head = "y"
        self.schema = IOSchema(0, "numeric feature rows", "p(class=1)")
        self._experts: list = []
        self._gate = None
        self._mean = None
        self._std = None
        self._n_exp = 0
        self.fell_back = False
        self.expert_weights_: dict = {}      # mean gate weight per expert (interpretability)

    def _z(self, A: np.ndarray) -> np.ndarray:
        return (A - self._mean) / self._std

    def _expert_probs(self, A: np.ndarray) -> np.ndarray:
        """(n_rows, n_experts) matrix of each expert's p(class=1)."""
        cols = []
        for _, est in self._experts:
            try:
                cols.append(est.predict_proba(A)[:, 1])
            except Exception:
                cols.append(np.full(len(A), 0.5))
        return np.column_stack(cols)

    def fit(self, X: Matrix, y: Labels) -> "RegimeMoERouter":
        A = np.asarray(X, dtype=np.float32)
        ya = np.asarray(y).astype(int)
        self.schema = IOSchema(A.shape[1], f"{A.shape[1]} numeric features", "p(class=1)")
        self._mean = A.mean(0)
        self._std = A.std(0) + 1e-8
        Az = self._z(A)

        if len(set(ya.tolist())) < 2:
            self.fell_back = True
            return self

        # train/val split (chronological — no shuffle; regime structure is temporal)
        cut = max(1, int(len(Az) * (1 - self.val_frac)))
        Xtr, ytr, Xva, yva = Az[:cut], ya[:cut], Az[cut:], ya[cut:]

        # fit + FREEZE the expert bank on train
        self._experts = []
        for nm, est in _default_experts():
            try:
                est.fit(Xtr, ytr)
                self._experts.append((nm, est))
            except Exception:
                continue
        self._n_exp = len(self._experts)
        if self._n_exp == 0:
            self.fell_back = True
            return self

        if not _HAS_TORCH or len(Xva) < 8 or len(set(yva.tolist())) < 2:
            self.fell_back = True                # uniform mixture
            self.expert_weights_ = {nm: 1.0 / self._n_exp for nm, _ in self._experts}
            return self

        # learn the gate on val: gate(x) → softmax weights; mixture prob → BCE(yva)
        torch.manual_seed(0)
        self._gate = nn.Sequential(nn.Linear(Az.shape[1], self.gate_hidden), nn.ReLU(),
                                   nn.Linear(self.gate_hidden, self._n_exp))
        opt = torch.optim.Adam(self._gate.parameters(), lr=5e-3)
        xva = torch.as_tensor(Xva, dtype=torch.float32)
        Eva = torch.as_tensor(self._expert_probs(Xva), dtype=torch.float32)   # frozen expert probs
        yv = torch.as_tensor(yva, dtype=torch.float32)
        self._gate.train()
        for _ in range(self.epochs):
            opt.zero_grad()
            w = torch.softmax(self._gate(xva), dim=1)          # (n, n_exp)
            mix = (w * Eva).sum(dim=1).clamp(1e-6, 1 - 1e-6)   # mixture p(class=1)
            loss = nn.functional.binary_cross_entropy(mix, yv)
            loss.backward()
            opt.step()
        self._gate.eval()
        with torch.no_grad():
            wm = torch.softmax(self._gate(xva), dim=1).mean(0).cpu().numpy()
        self.expert_weights_ = {nm: float(wm[i]) for i, (nm, _) in enumerate(self._experts)}
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        A = np.asarray(X, dtype=np.float32)
        if not self._experts:
            return [0.5] * len(A)
        Az = self._z(A)
        E = self._expert_probs(Az)
        if self.fell_back or self._gate is None:
            return E.mean(axis=1).tolist()                     # uniform mixture
        with torch.no_grad():
            w = torch.softmax(self._gate(torch.as_tensor(Az, dtype=torch.float32)), dim=1).cpu().numpy()
        return (w * E).sum(axis=1).tolist()

    def predict(self, X: Matrix) -> Labels:
        return [1 if p >= 0.5 else 0 for p in self.predict_proba(X)]


def regime_moe_node(name: str = "regime_moe") -> RegimeMoERouter:
    """Zero-arg factory (pool + autoload convention)."""
    return RegimeMoERouter(name=name)
