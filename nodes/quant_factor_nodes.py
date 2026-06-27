"""Quant-finance FACTOR feature nodes — single-series (price/return) factor
engines wrapped behind the project NodeProtocol (core/node_protocol.py).

These reuse the COPY pattern from nodes/quant_nodes.py: the task-aware readout
machinery (`_HeadBase` / `_WindowFeat`).  `_WindowFeat` gives every node a
CAUSAL trailing-window contract — for row i the window is
col[max(0, i-W+1) : i+1] (past+present only, NO look-ahead).  Each subclass sets
`NFEAT` (fixed feature-vector length) + `_features(window) -> list[float]`.
`_WindowFeat` already: zeros short windows (<12), suppresses warnings, hstacks
the named factor vector onto the raw X row, and fits a task-aware readout
(LogisticRegression(max_iter=1000) for classification / Ridge() for regression)
with a degenerate single-class guard.  Column 0 is treated as price/close.

Nodes (all single-asset, single-series factors over the causal close-window):

  1. Alpha158Node          — compact causal operator engine + a 59-factor
                             CLOSE-BASED subset of Microsoft qlib's Alpha158
                             (ROC/Ref, MA, STD, MAX/MIN, QTLU/QTLD, RSV,
                             BETA/RSQR/RESI, CORR, CNTP/CNTN, SUMP/SUMN).
  2. WQTimeSeriesAlphaNode — 14 TIME-SERIES (non cross-sectional) WorldQuant-101
                             style alphas (ts_rank, delta, decay_linear,
                             ts_min/ts_max/ts_argmin/ts_argmax, correlation,
                             signed power).  Cross-sectional rank alphas are OUT
                             OF SCOPE.
  3. EmpyricalRiskNode     — rolling empyrical risk metrics on the trailing
                             RETURNS window (sharpe, sortino, max-dd, VaR,
                             downside risk, tail ratio, annual vol) with numpy
                             fallbacks.

Every per-feature computation is wrapped in try/except so a single bad factor
emits 0.0 instead of breaking the (fixed-length) vector or the graph.
"""
from __future__ import annotations

import contextlib
import warnings

import numpy as np

from core.node_protocol import IOSchema
from nodes.quant_nodes import _HeadBase, _WindowFeat  # COPY pattern (reuse-first)

__all__ = [
    "Alpha158Node", "alpha158_node",
    "WQTimeSeriesAlphaNode", "wq_timeseries_alpha_node",
    "EmpyricalRiskNode", "empyrical_risk_node",
]


@contextlib.contextmanager
def _quiet():
    """Suppress library warnings + numpy floating errors around fragile math."""
    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore")
        yield


def _fin(v: float) -> float:
    """Finite-or-zero coercion (degenerate guard for every emitted feature)."""
    try:
        v = float(v)
        return v if np.isfinite(v) else 0.0
    except Exception:
        return 0.0


# --------------------------------------------------------------------------- #
#  1. Alpha158Node — causal operator engine + close-based qlib Alpha158 subset
# --------------------------------------------------------------------------- #
class Alpha158Node(_WindowFeat):
    """Compact CAUSAL re-implementation of a CLOSE-BASED subset (~59 factors) of
    Microsoft qlib's Alpha158.  Operators (Ref/Mean/Std/Max/Min/Quantile/Corr/
    Slope/Rsquare/Resi/Cnt/Sum) are evaluated over trailing sub-windows of the
    causal close-window — only past+present, never future.  Emits a fixed-length,
    named feature vector (see FEATURE_NAMES); each factor is individually
    try/except-guarded so a bad factor becomes 0.0 rather than corrupting length.
    """
    kind = "quant"

    _ROC_D = (1, 2, 5, 10, 20, 30, 60)
    _MA_D = (5, 10, 20, 30, 60)
    _STD_D = (5, 10, 20, 60)
    _MAX_D = (5, 10, 20, 60)
    _MIN_D = (5, 10, 20, 60)
    _QTLU_D = (5, 20, 60)
    _QTLD_D = (5, 20, 60)
    _RSV_D = (5, 10, 20, 60)
    _BETA_D = (5, 10, 20, 60)
    _RSQR_D = (10, 20, 60)
    _RESI_D = (10, 20, 60)
    _CORR_D = (10, 20, 60)
    _CNTP_D = (5, 20, 60)
    _CNTN_D = (5, 20, 60)
    _SUMP_D = (5, 20, 60)
    _SUMN_D = (5, 20, 60)

    FEATURE_NAMES = (
        [f"ROC{d}" for d in _ROC_D]
        + [f"MA{d}" for d in _MA_D]
        + [f"STD{d}" for d in _STD_D]
        + [f"MAX{d}" for d in _MAX_D]
        + [f"MIN{d}" for d in _MIN_D]
        + [f"QTLU{d}" for d in _QTLU_D]
        + [f"QTLD{d}" for d in _QTLD_D]
        + [f"RSV{d}" for d in _RSV_D]
        + [f"BETA{d}" for d in _BETA_D]
        + [f"RSQR{d}" for d in _RSQR_D]
        + [f"RESI{d}" for d in _RESI_D]
        + [f"CORR{d}" for d in _CORR_D]
        + [f"CNTP{d}" for d in _CNTP_D]
        + [f"CNTN{d}" for d in _CNTN_D]
        + [f"SUMP{d}" for d in _SUMP_D]
        + [f"SUMN{d}" for d in _SUMN_D]
    )
    NFEAT = len(FEATURE_NAMES)

    def __init__(self, name: str = "alpha158", col: int = 0, W: int = 64):
        super().__init__(
            name,
            f"qlib Alpha158 close-based causal subset ({self.NFEAT} factors: "
            "ROC/Ref, MA, STD, MAX/MIN, QTLU/QTLD, RSV, BETA/RSQR/RESI, CORR, "
            "CNTP/CNTN, SUMP/SUMN) + X readout.",
            col, W,
        )

    # -- causal linear regression of values vs time index ------------------- #
    @staticmethod
    def _linfit(y: np.ndarray):
        n = len(y)
        if n < 2:
            return 0.0, 0.0, 0.0
        x = np.arange(n, dtype=float)
        coef = np.polyfit(x, y, 1)
        pred = np.polyval(coef, x)
        ss_res = float(np.sum((y - pred) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        return float(coef[0]), float(r2), float(y[-1] - pred[-1])

    def _features(self, win) -> list[float]:
        with _quiet():
            w = np.asarray(win, dtype=float)
            n = len(w)
            c = float(w[-1]) if n else 0.0
            cd = c if c != 0 else 1.0          # safe divisor for /close ratios
            feats: list[float] = []

            def sl(d):                          # trailing d-length sub-window
                return w[-min(d, n):]

            def add(v):
                feats.append(_fin(v))

            # ROC / Ref: close / Ref(close, d) - 1
            for d in self._ROC_D:
                try:
                    ref = w[-1 - d] if n > d else w[0]
                    add(c / ref - 1.0 if ref != 0 else 0.0)
                except Exception:
                    add(0.0)
            # MA: Mean(close, d) / close
            for d in self._MA_D:
                try:
                    add(float(np.mean(sl(d))) / cd)
                except Exception:
                    add(0.0)
            # STD: Std(close, d) / close
            for d in self._STD_D:
                try:
                    add(float(np.std(sl(d))) / cd)
                except Exception:
                    add(0.0)
            # MAX: Max(close, d) / close
            for d in self._MAX_D:
                try:
                    add(float(np.max(sl(d))) / cd)
                except Exception:
                    add(0.0)
            # MIN: Min(close, d) / close
            for d in self._MIN_D:
                try:
                    add(float(np.min(sl(d))) / cd)
                except Exception:
                    add(0.0)
            # QTLU: 80th-pct(close, d) / close
            for d in self._QTLU_D:
                try:
                    add(float(np.percentile(sl(d), 80)) / cd)
                except Exception:
                    add(0.0)
            # QTLD: 20th-pct(close, d) / close
            for d in self._QTLD_D:
                try:
                    add(float(np.percentile(sl(d), 20)) / cd)
                except Exception:
                    add(0.0)
            # RSV: (close - Min) / (Max - Min)
            for d in self._RSV_D:
                try:
                    s = sl(d)
                    lo, hi = float(np.min(s)), float(np.max(s))
                    add((c - lo) / (hi - lo) if hi > lo else 0.0)
                except Exception:
                    add(0.0)
            # BETA: slope of close~time / close
            for d in self._BETA_D:
                try:
                    slope, _, _ = self._linfit(sl(d))
                    add(slope / cd)
                except Exception:
                    add(0.0)
            # RSQR: R^2 of close~time
            for d in self._RSQR_D:
                try:
                    _, r2, _ = self._linfit(sl(d))
                    add(r2)
                except Exception:
                    add(0.0)
            # RESI: residual of last close vs close~time fit / close
            for d in self._RESI_D:
                try:
                    _, _, resid = self._linfit(sl(d))
                    add(resid / cd)
                except Exception:
                    add(0.0)
            # CORR: corr(close, log(index)) over trailing d
            for d in self._CORR_D:
                try:
                    s = sl(d)
                    if len(s) >= 2 and float(np.std(s)) > 0:
                        idx = np.log(np.arange(1, len(s) + 1, dtype=float))
                        add(float(np.corrcoef(s, idx)[0, 1]))
                    else:
                        add(0.0)
                except Exception:
                    add(0.0)
            # CNTP: fraction of up days over trailing d
            for d in self._CNTP_D:
                try:
                    diff = np.diff(sl(d))
                    add(float(np.mean(diff > 0)) if len(diff) else 0.0)
                except Exception:
                    add(0.0)
            # CNTN: fraction of down days over trailing d
            for d in self._CNTN_D:
                try:
                    diff = np.diff(sl(d))
                    add(float(np.mean(diff < 0)) if len(diff) else 0.0)
                except Exception:
                    add(0.0)
            # SUMP: gains / (gains + losses) over trailing d
            for d in self._SUMP_D:
                try:
                    diff = np.diff(sl(d))
                    g = float(np.sum(diff[diff > 0]))
                    l = float(-np.sum(diff[diff < 0]))
                    add(g / (g + l) if (g + l) > 0 else 0.5)
                except Exception:
                    add(0.0)
            # SUMN: losses / (gains + losses) over trailing d
            for d in self._SUMN_D:
                try:
                    diff = np.diff(sl(d))
                    g = float(np.sum(diff[diff > 0]))
                    l = float(-np.sum(diff[diff < 0]))
                    add(l / (g + l) if (g + l) > 0 else 0.5)
                except Exception:
                    add(0.0)

        return feats


def alpha158_node() -> Alpha158Node:
    return Alpha158Node()


# --------------------------------------------------------------------------- #
#  2. WQTimeSeriesAlphaNode — time-series WorldQuant-101 alphas (single asset)
# --------------------------------------------------------------------------- #
class WQTimeSeriesAlphaNode(_WindowFeat):
    """14 TIME-SERIES (non cross-sectional) WorldQuant-101 style alpha operators
    computed on one asset's causal close-window (+ derived returns):
    ts_rank, delta, decay_linear, ts_min/ts_max/ts_argmin/ts_argmax,
    correlation(close, returns), signed power.  Cross-sectional rank-based alphas
    are intentionally OUT OF SCOPE.  Each operator is try/except-guarded.
    """
    kind = "quant"

    FEATURE_NAMES = [
        "ts_rank_close_5", "ts_rank_close_10",
        "delta_close_1", "delta_close_5",
        "decay_linear_ret_5", "decay_linear_ret_10",
        "ts_argmax_close_10", "ts_argmin_close_10",
        "ts_max_close_10", "ts_min_close_10",
        "corr_close_ret_10", "signed_power_ret_2",
        "ts_rank_ret_10", "delta_ret_1",
    ]
    NFEAT = len(FEATURE_NAMES)

    def __init__(self, name: str = "wq_ts_alpha", col: int = 0, W: int = 64):
        super().__init__(
            name,
            f"WorldQuant-101 time-series alphas ({self.NFEAT}: ts_rank/delta/"
            "decay_linear/ts_min/ts_max/ts_argmin/ts_argmax/corr/signed_power) "
            "on single-asset close window + X readout.",
            col, W,
        )

    # -- time-series operator primitives ------------------------------------ #
    @staticmethod
    def _ts_rank(s: np.ndarray) -> float:
        """Rank of the last value within s, normalised to [0, 1]."""
        if len(s) < 2:
            return 0.0
        return float(np.mean(s <= s[-1]))

    @staticmethod
    def _decay_linear(s: np.ndarray) -> float:
        """Linearly-weighted (more recent = heavier) average of s."""
        n = len(s)
        if n == 0:
            return 0.0
        w = np.arange(1, n + 1, dtype=float)
        return float(np.dot(s, w) / w.sum())

    def _features(self, win) -> list[float]:
        with _quiet():
            w = np.asarray(win, dtype=float)
            n = len(w)
            c = float(w[-1]) if n else 0.0
            cd = c if c != 0 else 1.0
            ret = np.diff(w) / np.where(w[:-1] == 0, 1.0, w[:-1]) if n > 1 \
                else np.zeros(1)
            feats: list[float] = []

            def sl(s, d):
                return s[-min(d, len(s)):]

            def add(v):
                feats.append(_fin(v))

            # ts_rank(close, d)
            for d in (5, 10):
                try:
                    add(self._ts_rank(sl(w, d)))
                except Exception:
                    add(0.0)
            # delta(close, d) / close
            for d in (1, 5):
                try:
                    ref = w[-1 - d] if n > d else w[0]
                    add((c - ref) / cd)
                except Exception:
                    add(0.0)
            # decay_linear(returns, d)
            for d in (5, 10):
                try:
                    add(self._decay_linear(sl(ret, d)))
                except Exception:
                    add(0.0)
            # ts_argmax / ts_argmin(close, 10), normalised by window length
            for fn in (np.argmax, np.argmin):
                try:
                    s = sl(w, 10)
                    add(float(fn(s)) / max(1, len(s) - 1))
                except Exception:
                    add(0.0)
            # ts_max / ts_min(close, 10) / close
            for fn in (np.max, np.min):
                try:
                    add(float(fn(sl(w, 10))) / cd)
                except Exception:
                    add(0.0)
            # correlation(close, returns, 10)
            try:
                cc = sl(w, 10)
                rr = sl(ret, 10)
                m = min(len(cc), len(rr))
                cc, rr = cc[-m:], rr[-m:]
                if m >= 2 and np.std(cc) > 0 and np.std(rr) > 0:
                    add(float(np.corrcoef(cc, rr)[0, 1]))
                else:
                    add(0.0)
            except Exception:
                add(0.0)
            # signed_power(last return, 2): sign(r) * |r|^2
            try:
                r = float(ret[-1])
                add(np.sign(r) * abs(r) ** 2)
            except Exception:
                add(0.0)
            # ts_rank(returns, 10)
            try:
                add(self._ts_rank(sl(ret, 10)))
            except Exception:
                add(0.0)
            # delta(returns, 1)
            try:
                add(float(ret[-1] - ret[-2]) if len(ret) > 1 else 0.0)
            except Exception:
                add(0.0)

        return feats


def wq_timeseries_alpha_node() -> WQTimeSeriesAlphaNode:
    return WQTimeSeriesAlphaNode()


# --------------------------------------------------------------------------- #
#  3. EmpyricalRiskNode — rolling empyrical risk metrics on trailing returns
# --------------------------------------------------------------------------- #
class EmpyricalRiskNode(_WindowFeat):
    """Rolling risk metrics from `empyrical` (empyrical-reloaded) computed on the
    trailing RETURNS window derived from the causal price/close-window:
    [sharpe_ratio, sortino_ratio, max_drawdown, value_at_risk, downside_risk,
    tail_ratio, annual_volatility].  Each metric is try/except-guarded with a
    robust numpy fallback (so a differing empyrical signature degrades, not
    breaks).
    """
    kind = "quant"

    FEATURE_NAMES = [
        "sharpe_ratio", "sortino_ratio", "max_drawdown", "value_at_risk",
        "downside_risk", "tail_ratio", "annual_volatility",
    ]
    NFEAT = len(FEATURE_NAMES)

    def __init__(self, name: str = "empyrical_risk", col: int = 0, W: int = 96):
        super().__init__(
            name,
            f"empyrical rolling risk metrics ({self.NFEAT}: sharpe/sortino/"
            "max_dd/VaR/downside_risk/tail_ratio/annual_vol) on trailing "
            "returns + X readout.",
            col, W,
        )

    # -- numpy fallbacks (used if empyrical raises / signature differs) ------ #
    @staticmethod
    def _np_sharpe(r):
        sd = float(np.std(r))
        return float(np.mean(r)) / sd * np.sqrt(252.0) if sd > 0 else 0.0

    @staticmethod
    def _np_sortino(r):
        downside = r[r < 0]
        dd = float(np.sqrt(np.mean(downside ** 2))) if len(downside) else 0.0
        return float(np.mean(r)) / dd * np.sqrt(252.0) if dd > 0 else 0.0

    @staticmethod
    def _np_maxdd(r):
        cum = np.cumprod(1.0 + r)
        peak = np.maximum.accumulate(cum)
        return float(np.min((cum - peak) / np.where(peak == 0, 1.0, peak)))

    @staticmethod
    def _np_var(r):
        return float(np.percentile(r, 5))

    @staticmethod
    def _np_downside(r):
        downside = r[r < 0]
        return float(np.sqrt(np.mean(downside ** 2)) * np.sqrt(252.0)) \
            if len(downside) else 0.0

    @staticmethod
    def _np_tail(r):
        lo = abs(float(np.percentile(r, 5)))
        hi = abs(float(np.percentile(r, 95)))
        return hi / lo if lo > 0 else 0.0

    @staticmethod
    def _np_annvol(r):
        return float(np.std(r) * np.sqrt(252.0))

    def _features(self, win) -> list[float]:
        with _quiet():
            w = np.asarray(win, dtype=float)
            r = np.diff(w) / np.where(w[:-1] == 0, 1.0, w[:-1]) if len(w) > 1 \
                else np.zeros(1)
            r = r[np.isfinite(r)]
            if len(r) < 3:
                return [0.0] * self.NFEAT

            try:
                import empyrical as ep
            except Exception:
                ep = None

            def guard(ep_fn, np_fn):
                # try empyrical first, numpy fallback on any failure/non-finite
                if ep is not None and ep_fn is not None:
                    try:
                        v = float(ep_fn(r))
                        if np.isfinite(v):
                            return _fin(v)
                    except Exception:
                        pass
                try:
                    return _fin(np_fn(r))
                except Exception:
                    return 0.0

            feats = [
                guard(getattr(ep, "sharpe_ratio", None) if ep else None,
                      self._np_sharpe),
                guard(getattr(ep, "sortino_ratio", None) if ep else None,
                      self._np_sortino),
                guard(getattr(ep, "max_drawdown", None) if ep else None,
                      self._np_maxdd),
                guard(getattr(ep, "value_at_risk", None) if ep else None,
                      self._np_var),
                guard(getattr(ep, "downside_risk", None) if ep else None,
                      self._np_downside),
                guard(getattr(ep, "tail_ratio", None) if ep else None,
                      self._np_tail),
                guard(getattr(ep, "annual_volatility", None) if ep else None,
                      self._np_annvol),
            ]
        return feats


def empyrical_risk_node() -> EmpyricalRiskNode:
    return EmpyricalRiskNode()
