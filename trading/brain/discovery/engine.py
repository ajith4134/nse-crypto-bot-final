"""Concept Discovery Engine — "idea discovery mode" (pure-self feature invention).

Pipeline (research/concept-discovery-engine.md):
  perception → INVENT (WindowEncoder) → READ OUT (SAEProbe) → NAME (namer) → SEE (manifold).
The net invents its own market features; we probe, name, and visualize them, then feed the
useful ones back — no human feature engineering.

Two lanes (paper-trading experimentation, no real money):
  * EXPERIMENT — fully autonomous, UNGATED: every discovered feature is usable immediately.
  * VALIDATED  — proof-gated: a feature is promoted only if it clears a predictive-stability
    gate (sign-consistent forward-return correlation across two out-of-sample halves). This is
    the lightweight stand-in for the full anti-overfit (Pillar 20) + causal (Pillar 19) gates;
    those node-level gates apply when a promoted feature is wired into a live strategy.

CPU-first; every heavy stage self-guards so partial stacks still produce output. State persists
to trading/state/concept_discovery.json for the dashboard ConceptSpacePanel.
"""
from __future__ import annotations

import json
import os
import time

import numpy as np

from .encoders import WindowEncoder, make_windows
from .probe import SAEProbe
from .manifold import project
from .namer import name_feature

try:
    from trading.state import STATE_DIR as _SD
    _PATH = os.path.join(str(_SD), "concept_discovery.json")
except Exception:
    _PATH = os.path.join(os.path.expanduser("~"), ".mlnb_concept_discovery.json")


class ConceptDiscoveryEngine:
    def __init__(self, window: int = 24, latent_dim: int = 16, dict_size: int = 32,
                 top_features: int = 12, use_llm: bool = True, seed: int = 0):
        self.window = window
        self.latent_dim = latent_dim
        self.dict_size = dict_size
        self.top_features = top_features
        self.use_llm = use_llm
        self.seed = seed
        self.result_: dict | None = None

    # ---- the gate for the VALIDATED lane -------------------------------------- #
    @staticmethod
    def _validate(activation: np.ndarray, fwd_ret: np.ndarray) -> tuple[bool, float]:
        """Sign-consistent forward-return correlation across two OOS halves."""
        a, r = np.asarray(activation, float), np.asarray(fwd_ret, float)
        m = min(len(a), len(r))
        a, r = a[:m], r[:m]
        if m < 20 or np.std(a) < 1e-9:
            return False, 0.0
        h = m // 2
        with np.errstate(all="ignore"):
            c1 = np.corrcoef(a[:h], r[:h])[0, 1]
            c2 = np.corrcoef(a[h:], r[h:])[0, 1]
        c1 = 0.0 if not np.isfinite(c1) else c1
        c2 = 0.0 if not np.isfinite(c2) else c2
        ok = (abs(c1) > 0.08) and (np.sign(c1) == np.sign(c2)) and (abs(c2) > 0.05)
        return bool(ok), float((c1 + c2) / 2.0)

    def discover(self, series, ohlcv: np.ndarray | None = None) -> dict:
        """Run the full pipeline on a price series (1-D closes) or an OHLCV matrix."""
        src = np.asarray(ohlcv, float) if ohlcv is not None else np.asarray(series, float)
        close = src[:, 3] if (src.ndim == 2 and src.shape[1] >= 4) else np.asarray(series, float).reshape(-1)
        W = make_windows(src, w=self.window, stride=1)
        n = len(W)
        # forward return aligned to each window's end (for the validation gate)
        ends = np.array(range(self.window, len(close) + 1))[:n]
        fwd = np.zeros(n)
        for i, e in enumerate(ends):
            fwd[i] = (close[min(e, len(close) - 1)] - close[e - 1]) / (abs(close[e - 1]) + 1e-9)

        enc = WindowEncoder(latent_dim=self.latent_dim, seed=self.seed).fit(W)
        Z = enc.encode(W)
        probe = SAEProbe(dict_size=self.dict_size, seed=self.seed).fit(Z)
        F = probe.features(Z)                                    # [n, dict_size]

        # rank features by activation energy; keep the top ones
        energy = F.sum(0)
        top = list(np.argsort(energy)[::-1][:self.top_features])
        maxwin = probe.max_activating(F[:, top] if top else F, k=5)
        closes_win = [W[i] for i in range(n)]

        feats = []
        n_valid = 0
        for rank, j in enumerate(top):
            act = F[:, j]
            widx = maxwin.get(rank, [])
            windows = [closes_win[i] for i in widx]
            named = name_feature(int(j), windows, use_llm=self.use_llm)
            valid, score = self._validate(act, fwd)
            n_valid += int(valid)
            feats.append({
                "id": int(j),
                "name": named["name"],
                "description": named["description"],
                "lane": "validated" if valid else "experiment",
                "gate_score": round(score, 4),
                "activation_rate": round(float(np.mean(act > 1e-6)), 3),
                "energy": round(float(energy[j]), 3),
                "max_windows": [int(i) for i in widx],
            })

        man = project(Z, seed=self.seed)
        self.result_ = {
            "features": feats,
            "manifold": man,
            "stats": {"n_windows": n, "latent_dim": int(Z.shape[1]),
                      "dict_size": self.dict_size, "encoder": enc.backend,
                      "n_experiment": len(feats) - n_valid, "n_validated": n_valid,
                      "sae": probe._sae is not None, "llm": self.use_llm},
            "ts": time.time(),
        }
        return self.result_

    def save(self) -> None:
        if self.result_ is None:
            return
        try:
            os.makedirs(os.path.dirname(_PATH), exist_ok=True)
            with open(_PATH, "w", encoding="utf-8") as f:
                json.dump(self.result_, f)
        except Exception:
            pass

    @staticmethod
    def load() -> dict:
        try:
            with open(_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"features": [], "manifold": {"points": [], "n_clusters": 0}, "stats": {}}

    def to_json(self) -> dict:
        return self.result_ or self.load()
