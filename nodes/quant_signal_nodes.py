"""Quant-finance SIGNAL + LABELING nodes behind the project NodeProtocol.

These nodes wrap classic systematic-trading signals (AQR time-series momentum,
RenTec/Ornstein-Uhlenbeck mean reversion, Ernie-Chan Bollinger/z-score
reversion) and Lopez-de-Prado labelling machinery (META-LABELING and
TRIPLE-BARRIER features) as graph nodes.

All shared machinery is reused from nodes/quant_nodes.py:

  * `_HeadBase`  — task-aware readout (LogisticRegression for binary/multiclass,
    Ridge for regression), with the project's `predict_proba` / `predict` /
    `predict_output` surface (binary -> [1-p, p] rows; multiclass -> class
    probs; regression -> [value] rows) and a degenerate-class guard.
  * `_WindowFeat` — CAUSAL trailing-window design: for each row i the window is
    close[max(0, i-W+1) : i+1] of the chosen column (close == col 0 by default),
    so only past+present is ever used (no look-ahead).  Windows shorter than 12
    fall back to a fixed-length zero feature vector, and numeric/optimizer
    warnings are suppressed inside the feature computation.

mlfinpy / mlfinlab are NOT available in this environment, so META-LABELING and
TRIPLE-BARRIER are SELF-IMPLEMENTED here in plain numpy (both are simple and
well documented).  This module depends on NEITHER mlfinlab NOR mlfinpy.

Each node is a class + a NO-ARG factory.  Every feature computation is wrapped
in try/except returning zeros so a node can never break the prediction graph.
"""
from __future__ import annotations

import warnings

import numpy as np

from nodes.quant_nodes import _HeadBase, _WindowFeat  # reused base machinery


# --------------------------------------------------------------------------- #
#  Small numeric helpers (causal — operate only on the trailing window)
# --------------------------------------------------------------------------- #
def _log_returns(win: np.ndarray) -> np.ndarray:
    """Log returns of a (strictly-positive-ish) price window; robust to <=0."""
    w = np.asarray(win, dtype=float)
    if len(w) < 2:
        return np.zeros(0, dtype=float)
    base = np.where(np.abs(w[:-1]) < 1e-12, 1e-12, w[:-1])
    r = (w[1:] - w[:-1]) / base                     # simple returns (robust)
    return r[np.isfinite(r)]


def _realized_vol(win: np.ndarray) -> float:
    r = _log_returns(win)
    v = float(np.std(r)) if len(r) else 0.0
    return v if np.isfinite(v) and v > 0 else 1e-8


# --------------------------------------------------------------------------- #
#  1. TSMOMNode — AQR time-series momentum
# --------------------------------------------------------------------------- #
class TSMOMNode(_WindowFeat):
    """AQR-style TIME-SERIES MOMENTUM signal node (kind='quant').

    From the causal trailing window of the close column it derives:
      * vol-scaled k-period returns for k in {1, 3, 6, 12}: each k-period return
        divided by realized vol * sqrt(k) (captures both SIGN and SIZE of the
        move, normalised so different horizons are comparable) -> 4 feats,
      * 12-1 momentum: cumulative return from t-12 to t-1 (skips the most recent
        bar, the classic short-term-reversal-avoiding momentum) -> 1 feat,
      * vol-scaled trend: OLS slope of price vs time over the window, divided by
        realized vol -> 1 feat.
    These 6 features are concatenated with the raw X row and fed to the task
    readout, which turns the momentum signal into a calibrated prediction.
    """

    kind = "quant"
    NFEAT = 6

    def __init__(self, name: str = "tsmom", col: int = 0, W: int = 64):
        super().__init__(
            name,
            "AQR time-series momentum: vol-scaled k-period returns "
            "(k=1,3,6,12), 12-1 momentum, vol-scaled trend -> readout.",
            col, W,
        )

    def _features(self, win) -> list[float]:
        try:
            w = np.asarray(win, dtype=float)
            vol = _realized_vol(w)
            feats: list[float] = []
            for k in (1, 3, 6, 12):
                if len(w) > k and abs(w[-1 - k]) > 1e-12:
                    rk = (w[-1] - w[-1 - k]) / w[-1 - k]
                    feats.append(rk / (vol * np.sqrt(k)))   # sign+size, scaled
                else:
                    feats.append(0.0)
            # 12-1 momentum: t-12 -> t-1 (skip most recent bar)
            if len(w) > 12 and abs(w[-12]) > 1e-12:
                mom_12_1 = (w[-2] - w[-12]) / w[-12]
            else:
                mom_12_1 = 0.0
            feats.append(mom_12_1)
            # vol-scaled trend (OLS slope vs time)
            t = np.arange(len(w), dtype=float)
            slope = float(np.polyfit(t, w, 1)[0]) if len(w) >= 2 else 0.0
            scale = float(np.mean(np.abs(w))) or 1.0
            feats.append((slope / scale) / vol)
            return [float(v) if np.isfinite(v) else 0.0 for v in feats]
        except Exception:
            return [0.0] * self.NFEAT


def tsmom_node() -> TSMOMNode:
    return TSMOMNode()


# --------------------------------------------------------------------------- #
#  2. OUMeanReversionNode — Ornstein-Uhlenbeck / RenTec-style mean reversion
# --------------------------------------------------------------------------- #
class OUMeanReversionNode(_WindowFeat):
    """Ornstein-Uhlenbeck / RenTec-style MEAN-REVERSION node (kind='quant').

    Fits an AR(1) model  x_t = a + phi*x_{t-1} + e  on the trailing window (the
    discrete-time analogue of an OU process) and derives:
      * half-life of mean reversion = -ln(2) / ln(phi)  (how many bars to revert
        half-way; only meaningful for 0 < phi < 1),
      * z-score of the current price vs the rolling window mean,
      * mean-reversion speed kappa = -ln(phi)  (continuous-time OU speed),
      * distance-to-mean (current price minus mean, scaled by window std).
    Robust if phi >= 1 (no mean reversion): half-life is capped at the window
    length and speed set to 0, so a trending window degrades gracefully.
    """

    kind = "quant"
    NFEAT = 4

    def __init__(self, name: str = "ou_meanrev", col: int = 0, W: int = 64):
        super().__init__(
            name,
            "Ornstein-Uhlenbeck/AR(1) mean reversion: [half-life, z-score, "
            "kappa speed, distance-to-mean] -> readout (robust if phi>=1).",
            col, W,
        )

    def _features(self, win) -> list[float]:
        try:
            w = np.asarray(win, dtype=float)
            x_prev, x_next = w[:-1], w[1:]
            # AR(1) slope phi via covariance / variance of the lagged series
            xp_c = x_prev - x_prev.mean()
            denom = float(np.dot(xp_c, xp_c))
            phi = float(np.dot(xp_c, x_next - x_next.mean()) / denom) \
                if denom > 1e-12 else 0.0
            mu, sd = float(w.mean()), float(w.std())
            # half-life + speed, guarded against phi out of (0, 1)
            if 0.0 < phi < 1.0:
                kappa = -np.log(phi)
                half_life = np.log(2.0) / kappa
                half_life = min(half_life, float(len(w)))   # cap
            else:                                            # phi>=1 -> no MR
                kappa = 0.0
                half_life = float(len(w))
            z = (w[-1] - mu) / sd if sd > 1e-12 else 0.0
            dist = (w[-1] - mu) / sd if sd > 1e-12 else 0.0
            feats = [half_life, z, kappa, dist]
            return [float(v) if np.isfinite(v) else 0.0 for v in feats]
        except Exception:
            return [0.0] * self.NFEAT


def ou_meanrev_node() -> OUMeanReversionNode:
    return OUMeanReversionNode()


# --------------------------------------------------------------------------- #
#  3. BollingerZNode — Ernie-Chan Bollinger / z-score reversion
# --------------------------------------------------------------------------- #
class BollingerZNode(_WindowFeat):
    """Ernie-Chan BOLLINGER / Z-SCORE reversion node (kind='quant').

    Classic Bollinger-band reversion features over the trailing window:
      * z = (close - MA) / STD            (standardised deviation from the mean),
      * %B = (close - lower) / (upper - lower)   with upper/lower = MA +/- 2*STD,
      * bandwidth = (upper - lower) / MA  (band width relative to price),
      * RSI-like = Wilder relative-strength index of the window, scaled to [0,1].
    These four features feed the task readout.
    """

    kind = "quant"
    NFEAT = 4

    def __init__(self, name: str = "bollinger_z", col: int = 0, W: int = 64):
        super().__init__(
            name,
            "Ernie-Chan Bollinger/z-score reversion: [z, %B, bandwidth, "
            "RSI-like] -> readout.",
            col, W,
        )

    def _features(self, win) -> list[float]:
        try:
            w = np.asarray(win, dtype=float)
            ma, sd = float(w.mean()), float(w.std())
            upper, lower = ma + 2.0 * sd, ma - 2.0 * sd
            z = (w[-1] - ma) / sd if sd > 1e-12 else 0.0
            band = upper - lower
            pct_b = (w[-1] - lower) / band if band > 1e-12 else 0.5
            bandwidth = band / ma if abs(ma) > 1e-12 else 0.0
            # RSI-like (Wilder), scaled to [0, 1]
            d = np.diff(w)
            gains = d[d > 0].sum()
            losses = -d[d < 0].sum()
            if losses < 1e-12:
                rsi = 1.0 if gains > 0 else 0.5
            else:
                rs = gains / losses
                rsi = 1.0 - 1.0 / (1.0 + rs)             # == 100-100/(1+rs), /100
            feats = [z, pct_b, bandwidth, rsi]
            return [float(v) if np.isfinite(v) else 0.0 for v in feats]
        except Exception:
            return [0.0] * self.NFEAT


def bollinger_z_node() -> BollingerZNode:
    return BollingerZNode()


# --------------------------------------------------------------------------- #
#  4. MetaLabelingNode — Lopez de Prado META-LABELING (self-implemented)
# --------------------------------------------------------------------------- #
class MetaLabelingNode(_WindowFeat):
    """Lopez-de-Prado META-LABELING node (kind='ml') — SELF-IMPLEMENTED.

    TWO-STAGE design (no mlfinlab/mlfinpy dependency):

      STAGE 1 - PRIMARY model (decides the SIDE).  A simple, transparent rule
        proposes a direction from the trailing window: the sign of a fast-vs-slow
        moving-average crossover (a MA-crossover momentum primary).  This is the
        `primary_side` in {-1, +1}.

      STAGE 2 - SECONDARY / META model (decides whether to ACT).  In de Prado's
        scheme the meta-label is "was the primary signal correct?", and a
        secondary classifier learns P(act | features) to filter the primary's
        calls (improving precision and sizing).  Here the SECONDARY model is the
        node's task readout (`_HeadBase`): it receives the `primary_side` plus the
        window context features and is trained to predict the actual head/target
        `y`.  Because `primary_side` is an input feature, the readout effectively
        learns *when the primary is right vs wrong* and corrects/abstains from it
        — i.e. it learns the meta-label conditional on context, exactly the
        meta-labeling idea, while still emitting calibrated class probabilities
        through `predict_proba` / `predict_output`.

    Window features fed to the secondary model:
      [primary_side, primary_strength (MA gap, vol-scaled), realized vol,
       recent momentum].
    """

    kind = "ml"
    NFEAT = 4

    def __init__(self, name: str = "meta_labeling", col: int = 0, W: int = 64,
                 fast: int = 5, slow: int = 20):
        super().__init__(
            name,
            "Lopez de Prado meta-labeling: PRIMARY MA-crossover proposes a "
            "side; SECONDARY readout learns when to ACT on it (meta-label) and "
            "emits calibrated probs.",
            col, W,
        )
        self.fast = fast
        self.slow = slow

    def _features(self, win) -> list[float]:
        try:
            w = np.asarray(win, dtype=float)
            # STAGE 1: PRIMARY MA-crossover side
            f = max(1, min(self.fast, len(w)))
            s = max(f + 1, min(self.slow, len(w)))
            ma_fast = float(w[-f:].mean())
            ma_slow = float(w[-s:].mean())
            gap = ma_fast - ma_slow
            primary_side = 1.0 if gap >= 0.0 else -1.0
            vol = _realized_vol(w)
            scale = float(np.mean(np.abs(w))) or 1.0
            primary_strength = (gap / scale) / vol           # confidence proxy
            mom = (w[-1] - w[0]) / w[0] if abs(w[0]) > 1e-12 else 0.0
            feats = [primary_side, primary_strength, vol, mom]
            return [float(v) if np.isfinite(v) else 0.0 for v in feats]
        except Exception:
            return [0.0] * self.NFEAT


def meta_labeling_node() -> MetaLabelingNode:
    return MetaLabelingNode()


# --------------------------------------------------------------------------- #
#  5. TripleBarrierNode — Lopez de Prado triple-barrier features (self-impl.)
# --------------------------------------------------------------------------- #
class TripleBarrierNode(_WindowFeat):
    """Lopez-de-Prado TRIPLE-BARRIER feature node (kind='quant') — SELF-IMPL.

    The triple-barrier method labels a path by which of three barriers it touches
    FIRST: an UPPER profit-take (+k*vol cumulative return), a LOWER stop-loss
    (-k*vol), or a VERTICAL time barrier (a fixed horizon).  No mlfinlab/mlfinpy.

    CAUSAL feature extraction: using ONLY the past trailing window, we replay the
    method over every anchor j in the window (cumulative simple return forward
    from j, barriers = +/- k * realized_vol * sqrt(steps), vertical = horizon)
    and summarise the path geometry:
      * first-barrier-touched label for the most-recent feasible anchor
        (+1 upper, -1 lower, 0 vertical/none),
      * average time-to-barrier across anchors (in bars),
      * realized vol used to size the barriers,
      * upper-barrier touch frequency,
      * lower-barrier touch frequency.
    These five features feed the task readout.
    """

    kind = "quant"
    NFEAT = 5

    def __init__(self, name: str = "triple_barrier", col: int = 0, W: int = 64,
                 k: float = 1.5, horizon: int = 10):
        super().__init__(
            name,
            "Lopez de Prado triple-barrier features: [first-touch label, "
            "time-to-barrier, vol, up-touch freq, down-touch freq] -> readout.",
            col, W,
        )
        self.k = k
        self.horizon = horizon

    def _features(self, win) -> list[float]:
        try:
            w = np.asarray(win, dtype=float)
            vol = _realized_vol(w)
            up_thr, lo_thr = self.k * vol, -self.k * vol
            n = len(w)
            horizon = max(1, min(self.horizon, n - 1))
            up_cnt = lo_cnt = vt_cnt = 0
            times: list[int] = []
            last_label = 0.0
            anchors = range(0, n - 1)
            for j in anchors:
                p0 = w[j]
                if abs(p0) < 1e-12:
                    continue
                end = min(j + horizon, n - 1)
                touched, t_touch, label = False, end - j, 0.0
                for t in range(j + 1, end + 1):
                    cr = (w[t] - p0) / p0                  # cumulative return
                    if cr >= up_thr:
                        touched, t_touch, label = True, t - j, 1.0
                        up_cnt += 1
                        break
                    if cr <= lo_thr:
                        touched, t_touch, label = True, t - j, -1.0
                        lo_cnt += 1
                        break
                if not touched:
                    vt_cnt += 1
                times.append(t_touch)
                last_label = label                          # most-recent anchor
            total = max(1, up_cnt + lo_cnt + vt_cnt)
            avg_time = float(np.mean(times)) if times else float(horizon)
            feats = [last_label, avg_time, vol,
                     up_cnt / total, lo_cnt / total]
            return [float(v) if np.isfinite(v) else 0.0 for v in feats]
        except Exception:
            return [0.0] * self.NFEAT


def triple_barrier_node() -> TripleBarrierNode:
    return TripleBarrierNode()
