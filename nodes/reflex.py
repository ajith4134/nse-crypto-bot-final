"""ReflexArc — CORTEX T3: conditional compute (compute routed like signal).

Design §1 T3, stitch rows 16-18. Easy inputs exit from cheap tiers; hard inputs
escalate; "stay flat" is a first-class ROUTING OUTCOME (CANON-49 dead-band):

  tier-1  cheapest experts vote. ABC agreement rule (Agreement-Based Cascading:
          fraction of experts agreeing on the class ≥ ``escalate_margin``)
          + PABEE patience counter (Zhou et al. 2020: emit once ``patience``
          consecutive tiers agree) + a calibrated confidence exit → emit.
  tier-2+ Mixture-of-Depths-style capacity router (Raposo et al. 2024): a
          trained top-k gate (the SAME ``gate_train`` primitive, via
          GatedMoENode) selects which experts actually run per input —
          ``capacity`` = fraction of the tier's experts allowed to fire.
  final   deep experts. If the calibrated uncertainty is STILL above threshold
          → output None ("flat"): abstention as a routing outcome, not an
          afterthought.

Calibrated exits (CALM, Schuster et al. 2022 — Learn-Then-Test recipe, Angelopoulos
et al. 2021): on a held-out chronological calibration slice, each tier's exit
threshold λ_t is the SMALLEST confidence such that the tier's accuracy among
calibration inputs with conf ≥ λ_t stays ≥ 1−alpha (with a minimum support so a
lucky prefix can't certify a garbage tier). A tier that never reaches the target
risk gets λ_t = +inf — it can never exit early, by construction. This is the
risk-controlled selection LTT does, in ~15 lines (a raw split-conformal quantile
would be PERMISSIVE for weak tiers — large errors → low threshold — i.e. exactly
wrong for escalation; crepes' CPS wrapper solves a different, regression-shaped
problem, hence the direct recipe here).

Anytime (MSDNet-style, CANON-51/61): per-tier predictions are recorded for
every input (``predictions_by_tier``), so ANY tier cutoff still yields a
signal. ``compute_log`` records tier reached + experts fired per input — the
dashboard's firing-path feed.
"""
from __future__ import annotations

import numpy as np

from core.node_protocol import NodeFactory
from nodes.gated_node import GatedMoENode

FLAT = None                                    # the stay-flat routing outcome


def ltt_threshold(conf: np.ndarray, correct: np.ndarray, alpha: float,
                  min_support: int = 5) -> float:
    """Learn-Then-Test exit threshold (CALM recipe): smallest λ such that the
    empirical accuracy on calibration inputs with conf ≥ λ is ≥ 1−alpha, over
    prefixes with at least ``min_support`` samples. +inf when no λ qualifies
    (tier may never exit early)."""
    conf = np.asarray(conf, dtype=float)
    correct = np.asarray(correct, dtype=float)
    if len(conf) == 0:
        return float("inf")
    order = np.argsort(-conf)                       # descending confidence
    conf_s, corr_s = conf[order], correct[order]
    sizes = np.arange(1, len(conf_s) + 1)
    acc_cum = np.cumsum(corr_s) / sizes
    support = max(1, min(min_support, len(conf_s)))
    ok = np.where((acc_cum >= 1.0 - alpha) & (sizes >= support))[0]
    if len(ok) == 0:
        return float("inf")
    return float(conf_s[ok.max()])                  # most permissive risk-controlled λ


class ReflexArc:
    """Multi-tier conditional-compute arc over frozen expert nodes (T3)."""

    def __init__(self, tiers: list[list[NodeFactory]], escalate_margin: float = 0.7,
                 patience: int = 1, capacity: float = 0.5, alpha: float = 0.1,
                 flat_threshold: float | None = None, calib_frac: float = 0.25,
                 epochs: int = 120, lr: float = 0.05, folds: int = 3,
                 seed: int = 7, task: str = "binary", head: str = "y"):
        if not tiers or not all(tiers):
            raise ValueError("tiers must be a non-empty list of non-empty factory lists")
        if task not in ("binary", "multiclass"):
            raise ValueError("ReflexArc routes class/direction signals (binary|multiclass)")
        self.tiers = tiers
        self.escalate_margin = float(escalate_margin)   # ABC agreement fraction to exit
        self.patience = int(patience)                   # PABEE consecutive-agreement count
        self.capacity = float(capacity)                 # MoD: fraction of tier experts fired
        self.alpha = float(alpha)                       # conformal miscoverage per tier
        self.flat_threshold = flat_threshold            # None → calibrated final threshold
        self.calib_frac = float(calib_frac)
        self.epochs, self.lr, self.folds, self.seed = epochs, lr, folds, seed
        self.task, self.head = task, head
        self.compute_log: list[dict] = []
        self._tier_preds: list[list] = []

    # ── fitting ──────────────────────────────────────────────────────────────
    def _new_expert(self, f):
        e = f()
        e.head, e.task = self.head, self.task
        return e

    def fit(self, X, y) -> "ReflexArc":
        Xa, ya = np.asarray(X, dtype=float), np.asarray(y)
        n = len(Xa)
        cut = max(2, int(n * (1.0 - self.calib_frac)))   # chronological calib slice
        Xtr, ytr = Xa[:cut].tolist(), ya[:cut].tolist()
        Xcal, ycal = Xa[cut:].tolist(), ya[cut:].astype(int)

        # tier-1: cheap experts, fitted independently (zero gate training)
        self._tier0 = []
        for f in self.tiers[0]:
            try:
                self._tier0.append(self._new_expert(f).fit(Xtr, ytr))
            except Exception:
                pass
        if not self._tier0:
            raise ValueError("no tier-1 expert fitted")

        # deeper tiers: MoD capacity router = trained top-k gate over the tier
        self._deep = []
        for tier in self.tiers[1:]:
            k = max(1, int(round(self.capacity * len(tier))))
            node = GatedMoENode(tier, top_k=(k if k < len(tier) else 0),
                                epochs=self.epochs, lr=self.lr, folds=self.folds,
                                seed=self.seed, task=self.task, head=self.head,
                                name=f"reflex_tier{len(self._deep) + 2}")
            self._deep.append(node.fit(Xtr, ytr))

        # calibrated exit threshold per tier (CALM Learn-Then-Test selection)
        self.exit_thresholds = []
        for t in range(len(self.tiers)):
            if len(ycal):
                rows = self._tier_rows(t, Xcal)[0]
                conf = rows.max(axis=1)
                correct = (rows.argmax(axis=1) == ycal).astype(float)
                self.exit_thresholds.append(ltt_threshold(conf, correct, self.alpha))
            else:
                self.exit_thresholds.append(self.escalate_margin)
        self._flat_thr = (self.flat_threshold if self.flat_threshold is not None
                          else self.exit_thresholds[-1])
        return self

    # ── per-tier evaluation ──────────────────────────────────────────────────
    def _tier_rows(self, t: int, X_list) -> tuple[np.ndarray, np.ndarray, list[list[str]]]:
        """(prob rows (n,K), agreement fraction (n,), experts fired per input)."""
        if t == 0:
            per = np.stack([np.asarray(e.predict_output(X_list), dtype=float)
                            for e in self._tier0], axis=0)        # (E, n, K)
            rows = per.mean(axis=0)
            votes = per.argmax(axis=2)                            # (E, n)
            agree = np.array([np.bincount(votes[:, i]).max() / per.shape[0]
                              for i in range(per.shape[1])])
            names = [e.name for e in self._tier0]
            fired = [list(names) for _ in range(per.shape[1])]
            return rows, agree, fired
        node = self._deep[t - 1]
        rows = np.asarray(node.predict_output(X_list), dtype=float)
        _, active = node.active_subnetwork(X_list)                # MoD: who actually ran
        fired = [[node.expert_names[j] for j in range(active.shape[1]) if active[i, j]]
                 for i in range(active.shape[0])]
        return rows, np.ones(len(rows)), fired

    # ── decide: escalation loop ──────────────────────────────────────────────
    def predict(self, X) -> list:
        """Per-input signal: class int, or None (stay flat). Fills compute_log +
        predictions_by_tier as side records (honest per-input firing trace)."""
        X_list = [list(map(float, r)) for r in np.asarray(X, dtype=float)]
        n = len(X_list)
        T = len(self.tiers)
        preds: list = [FLAT] * n
        self.compute_log = [None] * n
        tier_pred_matrix = [[FLAT] * n for _ in range(T)]
        remaining = list(range(n))
        prev_vote = {}
        consec = {i: 0 for i in range(n)}

        for t in range(T):
            if not remaining:
                # carry forward exits so every tier cutoff yields a signal (anytime)
                tier_pred_matrix[t] = list(tier_pred_matrix[t - 1])
                continue
            rows, agree, fired = self._tier_rows(t, [X_list[i] for i in remaining])
            conf = rows.max(axis=1)
            vote = rows.argmax(axis=1)
            if t > 0:
                tier_pred_matrix[t] = list(tier_pred_matrix[t - 1])
            still = []
            for r, i in enumerate(remaining):
                p = int(vote[r])
                tier_pred_matrix[t][i] = p                       # anytime head at tier t
                consec[i] = consec[i] + 1 if prev_vote.get(i) == p else 1
                prev_vote[i] = p
                c = float(conf[r])
                final = (t == T - 1)
                exit_via = None
                if final:
                    exit_via = "final" if c >= self._flat_thr else "stay_flat"
                elif (consec[i] >= self.patience and c >= self.exit_thresholds[t]
                      and (t > 0 or agree[r] >= self.escalate_margin)):
                    exit_via = "agree+calibrated" if t == 0 else "patience+calibrated"
                if exit_via:
                    preds[i] = FLAT if exit_via == "stay_flat" else p
                    self.compute_log[i] = {
                        "i": i, "tier": t, "experts": fired[r],
                        "confidence": round(c, 4),
                        "agreement": round(float(agree[r]), 4),
                        "exit": exit_via, "prediction": preds[i]}
                else:
                    still.append(i)
            remaining = still
        self._last_tier_matrix = tier_pred_matrix
        return preds

    def predictions_by_tier(self, X) -> list[list]:
        """Anytime heads: prediction at EVERY tier cutoff (carry-forward for
        inputs that exited earlier). Call after/instead of predict()."""
        self.predict(X)
        return self._last_tier_matrix
