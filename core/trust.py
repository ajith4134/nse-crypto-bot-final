"""TrustLedger — CORTEX T7: regret-bounded per-node trust (design §1 T7, stitch rows 20-21).

The brain hub's hand on every gate. Per-node trust is learned ONLINE from realized
losses by multiplicative weights:

  * AdaHedge (full-information default): weights w_i ∝ exp(-η·L_i) over cumulative
    losses, with the learning rate η self-tuned from the cumulative mixability gap
    Δ (η = ln(N)/Δ) — the ~15-line trick from de Rooij et al. 2014 "Follow the
    Leader If You Can, Hedge If You Must". No η to hand-tune, regret bounded.
  * EXP3 variant (``exp3=True``): when only the ROUTED node's loss is observed
    (bandit feedback), the loss is importance-weighted by the node's current
    routing probability (ℓ̂ = ℓ / max(p, min_prob)) so the estimate stays unbiased.

Regime resets (stitch row 21): feed any scalar performance stream through
``observe_regime_signal(x)``. A vendored Bayesian online changepoint detector
(vendor/bocd — Adams & MacKay 2007, Gaussian unknown-mean model) tracks the
run-length posterior online; when the posterior mass COLLAPSES onto short run
lengths (the "P(r=0) spike" — in practice the r≤1 mass, since P(r=0) is pinned
near the hazard), cumulative losses are blended back toward uniform so trust
re-opens after a regime break. ``last_changepoint`` exposes the step index.

Gates consume trust via ``bias_vector(names, beta)`` = β·log(trust+ε), added to
gate logits pre-softmax (nodes/gated_node.py ``prior_bias``).

Persistence: JSON at env ``MLNB_TRUST_PATH`` (default brain_memory/node_trust.json),
written on every update — tests monkeypatch the env to a tmpdir.
"""
from __future__ import annotations

import json
import math
import os

import numpy as np

_DEFAULT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "brain_memory", "node_trust.json")
_ETA_CAP = 100.0          # numerical cap on the self-tuned learning rate


class _OnlineBOCD:
    """Online (message-passing) form of the vendored batch ``bocd()`` recursion.

    Same Algorithm-1 steps as vendor/bocd/bocd.py, but keeping only the running
    log message instead of the full T×T posterior matrix, truncated at
    ``max_run`` hypotheses so memory stays bounded on infinite streams.
    """

    def __init__(self, hazard: float = 1 / 100.0, mean0: float = 0.0,
                 var0: float = 2.0, varx: float = 1.0, max_run: int = 512):
        from vendor.bocd.bocd import GaussianUnknownMean
        self.model = GaussianUnknownMean(mean0, var0, varx)
        self.hazard = float(hazard)
        self.max_run = int(max_run)
        self.t = 0
        self.log_message = np.array([0.0])                     # log P(r_0 = 0) = log 1

    def step(self, x: float) -> np.ndarray:
        """Observe x; return the run-length posterior P(r_t = ·) (len t+1, truncated)."""
        from scipy.special import logsumexp
        t = self.t + 1
        log_pis = self.model.log_pred_prob(t, x)[:len(self.log_message)]
        growth = log_pis + self.log_message + math.log(1.0 - self.hazard)
        cp = logsumexp(log_pis + self.log_message + math.log(self.hazard))
        joint = np.append(cp, growth)
        joint = joint - logsumexp(joint)
        self.model.update_params(t, x)
        if len(joint) > self.max_run:                          # fold tail mass into last bin
            tail = logsumexp(joint[self.max_run - 1:])
            joint = np.append(joint[:self.max_run - 1], tail)
            self.model.mean_params = self.model.mean_params[:self.max_run + 1]
            self.model.prec_params = self.model.prec_params[:self.max_run + 1]
        self.log_message = joint
        self.t = t
        return np.exp(joint)


class TrustLedger:
    """Per-node trust ∈ [0,1] from realized losses (AdaHedge / EXP3) + BOCD resets."""

    def __init__(self, path: str | None = None, exp3: bool = False,
                 min_prob: float = 0.01, eps: float = 1e-6,
                 hazard: float = 1 / 100.0, cp_mass: float = 0.5,
                 reset_strength: float = 0.7, bocd_var0: float = 2.0,
                 bocd_varx: float = 1.0):
        self.path = path or os.environ.get("MLNB_TRUST_PATH", _DEFAULT_PATH)
        self.exp3 = bool(exp3)
        self.min_prob = float(min_prob)
        self.eps = float(eps)
        self.hazard = float(hazard)
        self.cp_mass = float(cp_mass)                 # short-run mass that triggers a reset
        self.reset_strength = float(reset_strength)   # 0 = no reset, 1 = full reset to uniform
        self._bocd_kw = {"hazard": hazard, "var0": bocd_var0, "varx": bocd_varx}
        self.losses: dict[str, float] = {}            # cumulative (importance-weighted) loss
        self.counts: dict[str, int] = {}
        self._delta = 0.0                             # AdaHedge cumulative mixability gap
        self._t_regime = 0
        self.last_changepoint: int | None = None
        self._bocd: _OnlineBOCD | None = None
        self._load()

    # ── multiplicative-weights core ──────────────────────────────────────────
    def _eta(self, n_nodes: int) -> float:
        """AdaHedge self-tuned learning rate: η = ln(N)/Δ (capped; greedy at Δ=0)."""
        if self._delta <= 0.0:
            return _ETA_CAP
        return min(math.log(max(n_nodes, 2)) / self._delta, _ETA_CAP)

    def _neutral_loss(self) -> float:
        """Prior cumulative loss for a node never seen: the population mean (neutral)."""
        return (sum(self.losses.values()) / len(self.losses)) if self.losses else 0.0

    def _weights(self, names: list[str]) -> np.ndarray:
        neutral = self._neutral_loss()
        L = np.array([self.losses.get(n, neutral) for n in names], dtype=float)
        if len(L) == 0:
            return L
        w = np.exp(-self._eta(len(L)) * (L - L.min()))
        return w / w.sum()

    def update(self, node: str, loss: float) -> float:
        """Record a realized loss ∈ [0,1] for ``node``; returns its new trust.

        Full-info (default): the round's loss vector is (loss for ``node``, 0
        elsewhere) — valid Hedge feedback when other nodes genuinely incurred no
        loss this round. EXP3 mode: only the routed node was observed, so the
        loss is importance-weighted by its current routing probability.
        """
        loss = float(np.clip(loss, 0.0, 1.0))
        names = sorted(set(self.losses) | {node})
        w = self._weights(names)
        i = names.index(node)
        li = loss / max(float(w[i]), self.min_prob) if self.exp3 else loss
        # AdaHedge mixability gap on this round's (one-hot) loss vector
        eta = self._eta(len(names))
        h = float(w[i]) * li                                        # Hedge (expected) loss
        inner = 1.0 - float(w[i]) * (1.0 - math.exp(-min(eta * li, 700.0)))
        m = -math.log(max(inner, 1e-300)) / eta                     # mix loss
        self._delta += max(0.0, h - m)
        self.losses[node] = self.losses.get(node, self._neutral_loss()) + li
        self.counts[node] = self.counts.get(node, 0) + 1
        self.save()
        return self.trust(node)

    # ── read side ────────────────────────────────────────────────────────────
    def trust(self, node: str) -> float:
        """Normalized trust weight ∈ [0,1] (uniform prior for unseen nodes)."""
        names = sorted(set(self.losses) | {node})
        w = self._weights(names)
        return float(w[names.index(node)])

    def snapshot(self) -> dict:
        names = sorted(self.losses)
        w = self._weights(names)
        return {n: round(float(v), 6) for n, v in zip(names, w)}

    def bias_vector(self, names: list[str], beta: float = 1.0) -> np.ndarray:
        """Gate prior logits β·log(trust+ε), aligned to ``names`` (T4 trust bias)."""
        all_names = sorted(set(self.losses) | set(names))
        w = self._weights(all_names)
        t = {n: float(v) for n, v in zip(all_names, w)}
        return np.array([beta * math.log(t[n] + self.eps) for n in names], dtype=float)

    # ── BOCD regime resets ───────────────────────────────────────────────────
    def observe_regime_signal(self, x: float) -> dict:
        """Feed one scalar of a performance stream; reset trust on run-length collapse."""
        if self._bocd is None:
            self._bocd = _OnlineBOCD(**self._bocd_kw)
        R = self._bocd.step(float(x))
        self._t_regime += 1
        p_short = float(R[:2].sum())                  # mass on run lengths 0 and 1
        fired = False
        recent = (self.last_changepoint is not None
                  and self._t_regime - self.last_changepoint <= 3)
        if p_short >= self.cp_mass and self._t_regime >= 5 and not recent:
            self.last_changepoint = self._t_regime
            self._reset_toward_uniform()
            fired = True
        return {"t": self._t_regime, "p_r0": float(R[0]), "p_short_run": p_short,
                "map_run_length": int(np.argmax(R)), "changepoint": fired}

    def _reset_toward_uniform(self) -> None:
        """Blend cumulative losses toward their mean AND relax the self-tuned
        learning rate after a regime break, so trust genuinely reopens (a loss
        blend alone leaves η huge → weights stay one-hot on the old regime)."""
        if not self.losses:
            return
        rho = self.reset_strength
        mean = self._neutral_loss()
        for n in self.losses:
            self.losses[n] = rho * mean + (1.0 - rho) * self.losses[n]
        spread = max(self.losses.values()) - min(self.losses.values())
        if spread > 0:
            # target η ≈ 1/spread → best/worst weight ratio ≈ e (soft, order kept)
            self._delta = max(self._delta, math.log(max(len(self.losses), 2)) * spread)
        self.save()

    # ── persistence ──────────────────────────────────────────────────────────
    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        blob = {"losses": self.losses, "counts": self.counts, "delta": self._delta,
                "exp3": self.exp3, "t_regime": self._t_regime,
                "last_changepoint": self.last_changepoint}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(blob, f, indent=2)

    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                blob = json.load(f)
            self.losses = {str(k): float(v) for k, v in blob.get("losses", {}).items()}
            self.counts = {str(k): int(v) for k, v in blob.get("counts", {}).items()}
            self._delta = float(blob.get("delta", 0.0))
            self._t_regime = int(blob.get("t_regime", 0))
            lc = blob.get("last_changepoint")
            self.last_changepoint = int(lc) if lc is not None else None
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            pass
