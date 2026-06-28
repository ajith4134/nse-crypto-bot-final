"""trading/brain/continual.py — online/continual learning + experience replay (T8.5).

Reuse-first: the online learner is **River** (incremental ML, concept-drift detection).
`OnlineNode` wraps a River pipeline (StandardScaler → LogisticRegression) as a
NodeProtocol node that keeps learning tick-by-tick and flags regime shifts via ADWIN.
`ReplayBuffer` + `replay_retrain` keep a P&L-weighted memory of past samples so retraining
on fresh data doesn't catastrophically forget old regimes.

All CPU, deterministic (River models have no RNG; replay sampling uses an injected rng).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

import numpy as np
from river import compose, drift, linear_model, preprocessing

from core.node_protocol import BaseNode, IOSchema


def _row_dict(features: list[str], row) -> dict:
    return {f: float(v) for f, v in zip(features, row)}


def _new_model():
    return compose.Pipeline(preprocessing.StandardScaler(), linear_model.LogisticRegression())


class OnlineNode(BaseNode):
    """A continually-learning NodeProtocol node (River) with concept-drift detection."""

    kind = "online"

    def __init__(self, features: list[str], *, name: str = "online", model=None,
                 drift_detector=None):
        self.features = list(features)
        self.name = name
        self.summary = "River online-learning node (drift-aware)"
        self.schema = IOSchema(len(self.features), "features", "p(class=1)")
        self.model = model or _new_model()
        self.drift = drift_detector if drift_detector is not None else drift.ADWIN()
        self.drift_events = 0
        self.n_seen = 0

    # streaming API
    def learn_one(self, row, y) -> bool:
        """Learn one sample; update drift on prediction error. Returns drift_detected."""
        x = _row_dict(self.features, row)
        yb = bool(y)
        p = self.model.predict_proba_one(x).get(True, 0.5) if self.n_seen else 0.5
        err = int((p >= 0.5) != yb)
        self.model.learn_one(x, yb)
        self.n_seen += 1
        self.drift.update(err)
        detected = bool(getattr(self.drift, "drift_detected", False))
        if detected:
            self.drift_events += 1
        return detected

    # NodeProtocol
    def fit(self, X, y) -> "OnlineNode":
        for row, yi in zip(X, y):
            self.learn_one(row, yi)
        return self

    def predict_proba(self, X):
        out = []
        for row in X:
            x = _row_dict(self.features, row)
            proba = self.model.predict_proba_one(x) if self.n_seen else {}
            out.append(float(proba.get(True, 0.5)))
        return out

    def status(self) -> dict:
        return {"name": self.name, "kind": self.kind, "n_seen": self.n_seen,
                "drift_events": self.drift_events, "features": len(self.features)}


@dataclass
class ReplayBuffer:
    """P&L/importance-weighted experience replay buffer (anti-catastrophic-forgetting)."""
    maxlen: int = 5000
    _items: list = field(default_factory=list, init=False)

    def add(self, row, y, *, weight: float = 1.0, ts: float = 0.0) -> None:
        self._items.append({"row": list(row), "y": int(bool(y)),
                            "weight": float(max(weight, 1e-6)), "ts": float(ts)})
        if len(self._items) > self.maxlen:
            self._items = self._items[-self.maxlen:]

    def __len__(self) -> int:
        return len(self._items)

    def sample(self, n: int, rng: np.random.Generator, *, recency_halflife: float = 0.0) -> list:
        if not self._items:
            return []
        w = np.array([it["weight"] for it in self._items], dtype=float)
        if recency_halflife > 0:
            ages = np.arange(len(self._items))[::-1]            # 0 = newest
            w = w * np.power(0.5, ages / recency_halflife)
        p = w / w.sum()
        k = min(n, len(self._items))
        idx = rng.choice(len(self._items), size=k, replace=False, p=p)
        return [self._items[i] for i in idx]


def replay_retrain(features: list[str], new_samples: list, buffer: ReplayBuffer,
                   rng: np.random.Generator, *, replay_k: int = 200,
                   name: str = "online_replay") -> OnlineNode:
    """Train a fresh OnlineNode on replayed past samples interleaved with new ones.

    `new_samples`/replayed items are dicts {row, y[, weight, ts]} (new_samples may also be
    (row, y) tuples). Interleaving old+new is what preserves prior-regime knowledge.
    """
    replay = buffer.sample(replay_k, rng)
    mixed = []
    for s in replay:
        mixed.append((s["row"], s["y"]))
    for s in new_samples:
        mixed.append((s["row"], s["y"]) if isinstance(s, dict) else (s[0], s[1]))
    rng.shuffle(mixed)
    node = OnlineNode(features, name=name)
    for row, y in mixed:
        node.learn_one(row, y)
    return node


def clone_model(model):
    """Deep-copy a River model with its learned state (for meta-init warm-starts)."""
    return copy.deepcopy(model)
