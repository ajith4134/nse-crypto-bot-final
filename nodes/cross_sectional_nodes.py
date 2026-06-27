"""Cross-sectional / portfolio nodes — operate ACROSS a multi-asset panel.

These rank/allocate over the whole universe at each timestamp (what single-series
nodes can't do): WorldQuant 101 cross-sectional rank-alphas, cross-sectional
z-scoring (qlib CSZScoreNorm), market-factor / betting-against-beta (a Fama-French
replacement computed from the panel — no external CSV), and HRP portfolio weights
(skfolio). Each node closes over the panel and emits a CAUSAL feature series for
the TARGET asset, aligned to the target's dataset rows, then reads out task-aware.

Panel comes from data/panel.make_panel; returns matrix R is [T, N] (T timestamps,
N assets), target column index given. The node precomputes its cross-sectional
feature matrix F over all T rows ONCE, then slices train/test by the fit→predict
row flow (run_multi calls fit once then predict_output once).
"""
from __future__ import annotations

import warnings

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector


def _readout(task: str):
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(StandardScaler(),
                         Ridge() if task == "regression" else LogisticRegression(max_iter=1000))


class _PanelNode(BaseNode):
    """Base for cross-sectional nodes. Subclass implements `_panel_feats() -> F[T,k]`
    (causal, target-aligned). Concatenates F with the target's own X and reads out."""
    kind = "quant"

    def __init__(self, panel: dict, name: str, summary: str):
        self.panel = panel
        self.R = np.asarray(panel["returns"], dtype=float)        # [T, N]
        self.C = np.asarray(panel["close"], dtype=float)          # [T+1, N] (close has one more row)
        self.tgt = int(panel["target"])
        self.name, self.summary = name, summary
        self.task, self.head = "binary", "y"
        self._classes: list[int] = []
        self._F = None
        self._seen = 0
        self.schema = IOSchema(0, "panel features", "out")

    # subclasses override
    def _panel_feats(self) -> np.ndarray:
        raise NotImplementedError

    def _ensure_F(self):
        if self._F is None:
            with warnings.catch_warnings(), np.errstate(all="ignore"):
                warnings.simplefilter("ignore")
                F = np.asarray(self._panel_feats(), dtype=float)
            F[~np.isfinite(F)] = 0.0
            self._F = F

    def _augment(self, X: Matrix, rows: slice) -> np.ndarray:
        self._ensure_F()
        Xa = np.asarray(X, dtype=float)
        F = self._F[rows]
        if len(F) != len(Xa):                                     # alignment guard: pad/trim
            F = (F[:len(Xa)] if len(F) > len(Xa)
                 else np.vstack([F, np.zeros((len(Xa) - len(F), self._F.shape[1]))]))
        return np.hstack([Xa, F])

    def fit(self, X: Matrix, y: Labels) -> "_PanelNode":
        self._seen = len(X)
        self.schema = IOSchema(len(X[0]), "panel + target features", self.task)
        A = self._augment(X, slice(0, len(X)))
        ya = np.asarray(y)
        if self.task != "regression":
            self._classes = sorted(set(int(v) for v in ya))
            if len(self._classes) < 2:
                return self
        self._ro = _readout(self.task)
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            self._ro.fit(A, ya)
        return self

    def predict_output(self, X: Matrix) -> list[list[float]]:
        A = self._augment(X, slice(self._seen, self._seen + len(X)))
        if self.task == "regression":
            return [[float(v)] for v in self._ro.predict(A)]
        if len(self._classes) < 2:
            return [[1.0]] * len(X)
        proba = self._ro.predict_proba(A)
        cols = list(self._ro.classes_)
        order = [cols.index(c) if c in cols else 0 for c in self._classes]
        return [[float(r[o]) for o in order] for r in proba]

    def predict_proba(self, X: Matrix) -> Vector:
        if self.task == "regression":
            v = [r[0] for r in self.predict_output(X)]
            lo, hi = min(v), max(v)
            return [(x - lo) / (hi - lo) if hi > lo else 0.5 for x in v]
        if len(self._classes) < 2:
            return [float(self._classes[0] if self._classes else 0.0)] * len(X)
        M = self.predict_output(X)
        if self.task == "multiclass":
            return [float(max(r)) for r in M]
        j = self._classes.index(1) if 1 in self._classes else len(self._classes) - 1
        return [float(r[j]) for r in M]

    def predict(self, X: Matrix) -> Labels:
        if self.task == "multiclass":
            return [self._classes[int(np.argmax(r))] for r in self.predict_output(X)]
        if self.task == "regression":
            return [int(round(r[0])) for r in self.predict_output(X)]
        return super().predict(X)


def _xs_rank(value: float, row: np.ndarray) -> float:
    """Cross-sectional percentile rank of `value` within `row` (0..1)."""
    row = row[np.isfinite(row)]
    if len(row) == 0:
        return 0.5
    return float(np.mean(row <= value))


def _xs_z(value: float, row: np.ndarray) -> float:
    row = row[np.isfinite(row)]
    mu, sd = float(np.mean(row)), float(np.std(row))
    return float((value - mu) / sd) if sd > 1e-12 else 0.0


def _mom(R: np.ndarray, t: int, k: int) -> np.ndarray:
    """Per-asset trailing k-sum return at row t (causal)."""
    return np.nansum(R[max(0, t - k + 1):t + 1], axis=0)


def _vol(R: np.ndarray, t: int, k: int) -> np.ndarray:
    w = R[max(0, t - k + 1):t + 1]
    return np.nanstd(w, axis=0) if len(w) > 1 else np.zeros(R.shape[1])


class CrossSectionalRankNode(_PanelNode):
    """qlib/WorldQuant-style cross-sectional RANK of the target's return, momentum,
    and volatility within the universe at each timestamp."""
    def __init__(self, panel):
        super().__init__(panel, "xs_rank", "Cross-sectional rank of return/momentum/vol vs universe.")

    def _panel_feats(self):
        R, t_i = self.R, self.tgt
        F = []
        for t in range(len(R)):
            mom = _mom(R, t, 10); vol = _vol(R, t, 10)
            F.append([_xs_rank(R[t, t_i], R[t]), _xs_rank(mom[t_i], mom), _xs_rank(vol[t_i], vol)])
        return np.asarray(F)


class CrossSectionalZScoreNode(_PanelNode):
    """qlib CSZScoreNorm — cross-sectional z-score of target return/momentum/vol."""
    def __init__(self, panel):
        super().__init__(panel, "xs_zscore", "Cross-sectional z-score vs universe (CSZScoreNorm).")

    def _panel_feats(self):
        R, t_i = self.R, self.tgt
        F = []
        for t in range(len(R)):
            mom = _mom(R, t, 10); vol = _vol(R, t, 10)
            F.append([_xs_z(R[t, t_i], R[t]), _xs_z(mom[t_i], mom), _xs_z(vol[t_i], vol)])
        return np.asarray(F)


class WorldQuant101CSNode(_PanelNode):
    """A subset of WorldQuant 101 CROSS-SECTIONAL rank-alphas evaluated for the target:
    alpha = -rank(returns) (reversion), rank(-delta_close), rank(volume), rank(|ret|)."""
    def __init__(self, panel):
        super().__init__(panel, "wq101_cs", "WorldQuant 101 cross-sectional rank-alphas (target value).")
        self.V = np.asarray(panel["volume"], dtype=float)
        self.Cc = np.asarray(panel["close"], dtype=float)

    def _panel_feats(self):
        R, t_i = self.R, self.tgt
        dC = np.diff(self.Cc, axis=0)                              # [T, N] close delta aligns to R
        F = []
        for t in range(len(R)):
            volrow = self.V[t + 1] if t + 1 < len(self.V) else self.V[-1]
            F.append([
                -_xs_rank(R[t, t_i], R[t]),                        # alpha: -rank(returns) reversion
                _xs_rank(-dC[t, t_i], -dC[t]),                     # rank(-delta close)
                _xs_rank(volrow[t_i], volrow),                     # rank(volume)
                _xs_rank(abs(R[t, t_i]), np.abs(R[t])),            # rank(|return|)
            ])
        return np.asarray(F)


class MarketFactorBetaNode(_PanelNode):
    """Fama-French-style MARKET factor from the panel (no external CSV) + betting-
    against-beta: rolling beta of target vs equal-weight market, residual alpha,
    correlation, and the BAB signal (-beta)."""
    def __init__(self, panel, win: int = 60):
        super().__init__(panel, "market_beta_bab", "Market factor / rolling beta / betting-against-beta.")
        self.win = win

    def _panel_feats(self):
        R, t_i, W = self.R, self.tgt, self.win
        mkt = np.nanmean(R, axis=1)                                # equal-weight market return
        tgt = R[:, t_i]
        F = []
        for t in range(len(R)):
            a, b = max(0, t - W + 1), t + 1
            m, g = mkt[a:b], tgt[a:b]
            if len(m) > 4 and np.std(m) > 1e-12:
                beta = float(np.cov(g, m)[0, 1] / np.var(m))
                alpha = float(np.mean(g - beta * m))
                corr = float(np.corrcoef(g, m)[0, 1]) if np.std(g) > 1e-12 else 0.0
            else:
                beta, alpha, corr = 0.0, 0.0, 0.0
            F.append([beta, alpha, corr, -beta])                  # last = betting-against-beta
        return np.asarray(F)


class HRPWeightNode(_PanelNode):
    """Hierarchical Risk Parity (López de Prado, via skfolio) portfolio: the target
    asset's HRP allocation weight + inverse-vol weight + vol-rank, on a trailing
    window (recomputed every `stride` rows). Falls back to inverse-variance weights."""
    def __init__(self, panel, win: int = 120, stride: int = 10):
        super().__init__(panel, "hrp_weight", "HRP / risk-parity allocation weight for the target asset.")
        self.win, self.stride = win, stride

    def _hrp_weights(self, win_R: np.ndarray) -> np.ndarray:
        try:
            from skfolio.optimization import HierarchicalRiskParity
            import pandas as pd
            df = pd.DataFrame(win_R, columns=[f"a{i}" for i in range(win_R.shape[1])])
            w = HierarchicalRiskParity().fit(df).weights_
            return np.asarray(w, dtype=float)
        except Exception:
            v = np.nanstd(win_R, axis=0)                           # inverse-variance fallback
            iv = 1.0 / np.clip(v ** 2, 1e-12, None)
            return iv / iv.sum()

    def _panel_feats(self):
        R, t_i, W, S = self.R, self.tgt, self.win, self.stride
        F = []
        last_w = np.ones(R.shape[1]) / R.shape[1]
        for t in range(len(R)):
            if t >= 12 and (t % S == 0 or t == len(R) - 1):
                last_w = self._hrp_weights(R[max(0, t - W + 1):t + 1])
            vol = _vol(R, t, 20)
            F.append([float(last_w[t_i]),
                      float(_xs_rank(vol[t_i], vol)),
                      float(last_w[t_i] * R.shape[1])])            # weight relative to equal-weight
        return np.asarray(F)


class MinCVaRWeightNode(_PanelNode):
    """Mean-risk min-CVaR portfolio (skfolio): the target asset's min-CVaR allocation
    weight on a trailing window + its CVaR/vol rank. Inverse-CVaR fallback."""
    def __init__(self, panel, win: int = 120, stride: int = 10):
        super().__init__(panel, "min_cvar_weight", "Min-CVaR (mean-risk) allocation weight for target.")
        self.win, self.stride = win, stride

    def _cvar_weights(self, win_R: np.ndarray) -> np.ndarray:
        try:
            from skfolio.optimization import MeanRisk, ObjectiveFunction
            from skfolio import RiskMeasure
            import pandas as pd
            df = pd.DataFrame(win_R, columns=[f"a{i}" for i in range(win_R.shape[1])])
            m = MeanRisk(risk_measure=RiskMeasure.CVAR,
                         objective_function=ObjectiveFunction.MINIMIZE_RISK)
            return np.asarray(m.fit(df).weights_, dtype=float)
        except Exception:
            cvar = np.array([abs(np.mean(np.sort(win_R[:, i])[:max(1, len(win_R) // 20)]))
                             for i in range(win_R.shape[1])])
            inv = 1.0 / np.clip(cvar, 1e-9, None)
            return inv / inv.sum()

    def _panel_feats(self):
        R, t_i, W, S = self.R, self.tgt, self.win, self.stride
        F = []
        last_w = np.ones(R.shape[1]) / R.shape[1]
        for t in range(len(R)):
            if t >= 12 and (t % S == 0 or t == len(R) - 1):
                last_w = self._cvar_weights(R[max(0, t - W + 1):t + 1])
            vol = _vol(R, t, 20)
            F.append([float(last_w[t_i]), float(_xs_rank(vol[t_i], vol)),
                      float(last_w[t_i] * R.shape[1])])
        return np.asarray(F)


def build_cross_sectional_nodes(panel: dict) -> list:
    """(id, factory) list of cross-sectional/portfolio nodes bound to this panel."""
    classes = [CrossSectionalRankNode, CrossSectionalZScoreNode, WorldQuant101CSNode,
               MarketFactorBetaNode, HRPWeightNode, MinCVaRWeightNode]
    return [(cls(panel).name, (lambda c=cls: c(panel))) for cls in classes]

