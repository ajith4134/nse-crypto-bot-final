"""GitHub tier-2 feature / anomaly nodes (signal • math • graph • ml).

Wraps installed GitHub OSS projects behind the project NodeProtocol, in the
multi-output contract (task in {binary,multiclass,regression}; predict_output
rows = class-probs or [value]). The task-aware readout, degenerate-class guard,
short-window handling and CAUSAL trailing windows are inherited from
`nodes/quant_nodes.py` (`_HeadBase` / `_WindowFeat`) — imported, not re-written.

Each node reads a 1-D signal from feature column `col` (default 0). Window nodes
use CAUSAL trailing windows of length `W` (no look-ahead); fit-once nodes fit a
single model on the training series and apply it row-wise. Every per-feature
computation is wrapped in robust guards: any failing third-party path degrades to
a cheap NumPy fallback, NaN/Inf are scrubbed to 0.0, and warnings are silenced.

A few projects (ssqueezepy, scikit-dimension) currently cannot import on this
env (numba requires NumPy <=2.3, installed 2.5). Their nodes therefore run on the
robust NumPy fallbacks today, and will transparently switch to the real library
once the dependency conflict is resolved (the real path is tried first).
"""
from __future__ import annotations

import time
import warnings

import numpy as np

from core.node_protocol import IOSchema, Labels, Matrix, Vector
# COPY (import) the task-aware readout machinery and causal-window base.
from nodes.quant_nodes import _HeadBase, _WindowFeat


def _clean(vals: list[float], n: int) -> list[float]:
    """Force a feature row to length `n`, finite floats only (NaN/Inf -> 0.0)."""
    out = []
    for v in vals[:n]:
        try:
            f = float(v)
        except Exception:
            f = 0.0
        out.append(f if np.isfinite(f) else 0.0)
    out += [0.0] * (n - len(out))
    return out


def _ohlc(win) -> "object":
    """Synthetic OHLC DataFrame from a close window (open=close, high/low band)."""
    import pandas as pd
    c = np.asarray(win, float)
    return pd.DataFrame({
        "open": c, "high": c * 1.001 + 1e-9, "low": c * 0.999 - 1e-9,
        "close": c, "volume": np.ones_like(c),
    })


# --------------------------------------------------------------------------- #
# 1. SSQueezeNode  (kind="signal")  — ssqueezepy synchrosqueezed-CWT band energy
# --------------------------------------------------------------------------- #
class SSQueezeNode(_WindowFeat):
    """Per-window synchrosqueezed CWT (`ssqueezepy.ssq_cwt`): fraction of total
    time-frequency energy in 4 frequency bands (low->high). Robust fallback to an
    rFFT periodogram split into the same 4 bands when ssqueezepy is unavailable."""
    kind = "signal"
    NFEAT = 4
    _ssq = "?"   # cached import probe: "?" untried, callable, or None

    def __init__(self, name="ssqueeze_bands", col=0, W=64):
        super().__init__(name, "ssqueezepy synchrosqueezed-CWT 4-band energy fractions.", col, W)

    @classmethod
    def _get_ssq(cls):
        if cls._ssq == "?":
            try:
                from ssqueezepy import ssq_cwt
                cls._ssq = ssq_cwt
            except Exception:
                cls._ssq = None
        return cls._ssq

    @staticmethod
    def _bands(energy: np.ndarray) -> list[float]:
        energy = np.nan_to_num(np.asarray(energy, float), nan=0.0, posinf=0.0, neginf=0.0)
        tot = float(energy.sum())
        if tot <= 0:
            return [0.0, 0.0, 0.0, 0.0]
        parts = np.array_split(energy, 4)
        return [float(p.sum() / tot) for p in parts]

    def _features(self, win):
        x = np.asarray(win, float)
        x = x - x.mean()
        ssq = self._get_ssq()
        if ssq is not None:
            try:
                Tx = ssq(x)[0]                       # (freq, time) synchrosqueezed
                energy = (np.abs(Tx) ** 2).sum(axis=1)
                return _clean(self._bands(energy), self.NFEAT)
            except Exception:
                pass
        # Fallback: rFFT periodogram -> 4 contiguous frequency bands.
        spec = np.abs(np.fft.rfft(x)) ** 2
        return _clean(self._bands(spec[1:] if spec.size > 1 else spec), self.NFEAT)


# --------------------------------------------------------------------------- #
# 2. ScikitDimNode  (kind="math")  — intrinsic dimension of a delay embedding
# --------------------------------------------------------------------------- #
class ScikitDimNode(_WindowFeat):
    """Per-window delay-embedding (dim=5, tau=1) then intrinsic-dimension estimate
    via scikit-dimension (`skdim.id.MLE`, fallback `TwoNN`). Robust fallback to a
    self-contained TwoNN maximum-likelihood estimator in pure NumPy."""
    kind = "math"
    NFEAT = 1
    EMB = 5
    _skdim = "?"

    def __init__(self, name="skdim_intrinsic", col=0, W=64):
        super().__init__(name, "scikit-dimension intrinsic dimension of a delay embedding.", col, W)

    @classmethod
    def _get_skdim(cls):
        if cls._skdim == "?":
            try:
                import skdim
                cls._skdim = skdim
            except Exception:
                cls._skdim = None
        return cls._skdim

    def _embed(self, x: np.ndarray) -> np.ndarray:
        m = self.EMB
        n = len(x) - (m - 1)
        if n < m + 2:
            return np.empty((0, m))
        return np.stack([x[i:i + m] for i in range(n)])

    @staticmethod
    def _twonn(pts: np.ndarray) -> float:
        """TwoNN MLE intrinsic dimension (Facco et al.) — robust NumPy version."""
        if len(pts) < 4:
            return 0.0
        d = np.sqrt(((pts[:, None, :] - pts[None, :, :]) ** 2).sum(-1))
        np.fill_diagonal(d, np.inf)
        srt = np.sort(d, axis=1)
        r1, r2 = srt[:, 0], srt[:, 1]
        mask = (r1 > 1e-12) & (r2 > r1)
        if mask.sum() < 3:
            return 0.0
        mu = r2[mask] / r1[mask]
        s = float(np.log(mu).sum())
        return float(mask.sum() / s) if s > 1e-12 else 0.0

    def _features(self, win):
        x = np.asarray(win, float)
        pts = self._embed(x)
        if len(pts) < 4:
            return [0.0]
        sk = self._get_skdim()
        if sk is not None:
            for est in ("MLE", "TwoNN"):
                try:
                    val = getattr(sk.id, est)().fit(pts).dimension_
                    return _clean([val], 1)
                except Exception:
                    continue
        return _clean([self._twonn(pts)], 1)


# --------------------------------------------------------------------------- #
# 3. Node2VecGraphNode  (kind="graph")  — visibility-graph node2vec embedding
# --------------------------------------------------------------------------- #
class Node2VecGraphNode(_WindowFeat):
    """Per-window natural visibility graph (`ts2vg`) embedded with node2vec
    (dims=8, walk_length=10, num_walks=10); feature = the mean node embedding.
    SLOW (node2vec trains a tiny word2vec per window) -> typically FLAGGED. A wall
    time-budget bounds the cost: once exceeded, remaining windows fall back to 8
    plain visibility-graph degree/topology statistics (also the hard fallback if
    ts2vg / node2vec raise)."""
    kind = "graph"
    NFEAT = 8
    EMB_BUDGET_S = 12.0          # per-_augment wall budget for node2vec embeddings

    def __init__(self, name="node2vec_visgraph", col=0, W=40):
        super().__init__(name, "ts2vg visibility-graph node2vec mean embedding (dims=8).", col, W)
        self._deadline = 0.0

    def _augment(self, X):
        self._deadline = time.time() + self.EMB_BUDGET_S   # reset budget per call
        return super()._augment(X)

    @staticmethod
    def _vg(win):
        from ts2vg import NaturalVG
        return NaturalVG().build(np.asarray(win, float)).as_networkx()

    @staticmethod
    def _degree_stats(g) -> list[float]:
        import networkx as nx
        n = g.number_of_nodes()
        degs = np.array([d for _, d in g.degree()], float) if n else np.zeros(1)
        try:
            trans = nx.transitivity(g)
        except Exception:
            trans = 0.0
        try:
            ncomp = nx.number_connected_components(g)
        except Exception:
            ncomp = 1.0
        dens = (2.0 * g.number_of_edges() / (n * (n - 1))) if n > 1 else 0.0
        return [float(degs.mean()), float(degs.std()), float(degs.max()),
                float(degs.min()), float(np.median(degs)), float(dens),
                float(trans), float(ncomp)]

    def _features(self, win):
        try:
            g = self._vg(win)
        except Exception:
            return [0.0] * self.NFEAT
        if time.time() < self._deadline:               # within budget -> node2vec
            try:
                from node2vec import Node2Vec
                n2v = Node2Vec(g, dimensions=8, walk_length=10, num_walks=10,
                               workers=1, quiet=True, seed=42)
                model = n2v.fit(window=3, min_count=1, batch_words=64, seed=42)
                emb = np.array([model.wv[str(k)] for k in g.nodes()], float)
                if emb.size:
                    return _clean(list(emb.mean(axis=0)), self.NFEAT)
            except Exception:
                pass
        return _clean(self._degree_stats(g), self.NFEAT)   # fast fallback


# --------------------------------------------------------------------------- #
# 4. FeatureEngineNode  (kind="ml")  — feature-engine row-level augmentation
# --------------------------------------------------------------------------- #
class FeatureEngineNode(_HeadBase):
    """feature-engine row-level transformers, FIT-ONCE on the training matrix:
    LagFeatures (lags 1/2/3) + WindowFeatures (rolling mean/std, window 5) over
    column `col`, concatenated with the raw features, then the task-aware readout.
    Robust fallback: if feature-engine is unavailable, append manual lag/rolling
    features computed in NumPy."""
    kind = "ml"

    def __init__(self, name="feature_engine_ts", col=0):
        super().__init__(name, "feature-engine lag + rolling-window feature augmentation (fit-once).", col)
        self._tf = None
        self._var = f"f{col}"

    def _frame(self, X):
        import pandas as pd
        return pd.DataFrame(np.asarray(X, float),
                            columns=[f"f{i}" for i in range(len(X[0]))])

    def fit(self, X, y):
        try:
            from feature_engine.timeseries.forecasting import LagFeatures, WindowFeatures
            df = self._frame(X)
            lf = LagFeatures(variables=[self._var], periods=[1, 2, 3], missing_values="ignore")
            wf = WindowFeatures(variables=[self._var], window=[5],
                                functions=["mean", "std"], missing_values="ignore")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                lf.fit(df)
                wf.fit(lf.transform(df))
            self._tf = (lf, wf)
        except Exception:
            self._tf = None
        return super().fit(X, y)

    def _augment(self, X):
        base = np.asarray(X, float)
        if self._tf is not None:
            try:
                lf, wf = self._tf
                df = self._frame(X)
                with warnings.catch_warnings(), np.errstate(all="ignore"):
                    warnings.simplefilter("ignore")
                    out = wf.transform(lf.transform(df))
                extra = out.drop(columns=df.columns).to_numpy(float)
                extra = np.nan_to_num(extra, nan=0.0, posinf=0.0, neginf=0.0)
                return np.hstack([base, extra])
            except Exception:
                pass
        return np.hstack([base, self._manual(base)])    # NumPy fallback

    def _manual(self, base: np.ndarray) -> np.ndarray:
        c = base[:, self.col]
        feats = []
        for lag in (1, 2, 3):
            v = np.concatenate([np.zeros(lag), c[:-lag]]) if lag < len(c) else np.zeros_like(c)
            feats.append(v)
        roll_m, roll_s = np.zeros_like(c), np.zeros_like(c)
        for i in range(len(c)):
            w = c[max(0, i - 4): i + 1]
            roll_m[i], roll_s[i] = w.mean(), w.std()
        feats += [roll_m, roll_s]
        out = np.column_stack(feats)
        return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)


# --------------------------------------------------------------------------- #
# 5. StockStatsNode  (kind="signal")  — stockstats indicators
# --------------------------------------------------------------------------- #
class StockStatsNode(_WindowFeat):
    """Per-window stockstats indicators on a synthetic OHLC frame (close=window):
    RSI(14), MACD, Bollinger-band width, CCI — last values as features."""
    kind = "signal"
    NFEAT = 4

    def __init__(self, name="stockstats_ind", col=0, W=64):
        super().__init__(name, "stockstats RSI/MACD/Boll-width/CCI last-value features.", col, W)

    def _features(self, win):
        from stockstats import StockDataFrame
        sdf = StockDataFrame.retype(_ohlc(win))
        out = []
        for ind in ("rsi_14", "macd"):
            try:
                out.append(float(sdf[ind].iloc[-1]))
            except Exception:
                out.append(0.0)
        try:
            out.append(float(sdf["boll_ub"].iloc[-1] - sdf["boll_lb"].iloc[-1]))
        except Exception:
            out.append(0.0)
        try:
            out.append(float(sdf["cci"].iloc[-1]))
        except Exception:
            out.append(0.0)
        return _clean(out, self.NFEAT)


# --------------------------------------------------------------------------- #
# 6. PandasTAClassicNode  (kind="signal")  — pandas-ta-classic incl candlestick
# --------------------------------------------------------------------------- #
class PandasTAClassicNode(_WindowFeat):
    """Per-window pandas-ta-classic indicators on a synthetic OHLC frame: RSI,
    MACD line, Bollinger-band width, CCI, plus a Doji candlestick-pattern flag —
    last values as features."""
    kind = "signal"
    NFEAT = 5

    def __init__(self, name="pandas_ta_classic_ind", col=0, W=64):
        super().__init__(name, "pandas-ta-classic RSI/MACD/Boll/CCI + Doji pattern features.", col, W)

    def _features(self, win):
        import contextlib
        import io
        import pandas_ta_classic as pta
        df = _ohlc(win)
        o, h, l, c = df["open"], df["high"], df["low"], df["close"]
        out = []
        _sink = contextlib.redirect_stdout(io.StringIO())  # pta prints on short windows
        _sink.__enter__()

        def last(series):
            try:
                return float(np.asarray(series, float)[-1])
            except Exception:
                return 0.0

        out.append(last(pta.rsi(c)))
        try:
            macd = pta.macd(c)
            out.append(float(macd.iloc[-1, 0]))
        except Exception:
            out.append(0.0)
        try:
            bb = pta.bbands(c)
            out.append(float(bb.iloc[-1, 2] - bb.iloc[-1, 0]))   # upper - lower
        except Exception:
            out.append(0.0)
        out.append(last(pta.cci(h, l, c)))
        try:
            doji = pta.cdl_pattern(o, h, l, c, name="doji")
            out.append(float(np.asarray(doji, float)[-1]))
        except Exception:
            out.append(0.0)
        _sink.__exit__(None, None, None)
        return _clean(out, self.NFEAT)


# --------------------------------------------------------------------------- #
# 7. TANode  (kind="signal")  — ta (bukosabino) momentum/volatility/trend
# --------------------------------------------------------------------------- #
class TANode(_WindowFeat):
    """Per-window ta (bukosabino) indicators on the close window: RSI (momentum),
    MACD line + signal (trend), Bollinger-band width (volatility) — last values."""
    kind = "signal"
    NFEAT = 4

    def __init__(self, name="ta_bukosabino_ind", col=0, W=64):
        super().__init__(name, "ta RSI/MACD/MACD-signal/Boll-width last-value features.", col, W)

    def _features(self, win):
        import pandas as pd
        from ta.momentum import RSIIndicator
        from ta.trend import MACD
        from ta.volatility import BollingerBands
        c = pd.Series(np.asarray(win, float))
        out = []

        def last(series):
            try:
                return float(series.iloc[-1])
            except Exception:
                return 0.0

        try:
            out.append(last(RSIIndicator(c).rsi()))
        except Exception:
            out.append(0.0)
        try:
            m = MACD(c)
            out.append(last(m.macd()))
            out.append(last(m.macd_signal()))
        except Exception:
            out += [0.0, 0.0]
        try:
            bb = BollingerBands(c)
            out.append(last(bb.bollinger_hband() - bb.bollinger_lband()))
        except Exception:
            out.append(0.0)
        return _clean(out, self.NFEAT)


# --------------------------------------------------------------------------- #
# 8. ADTKAnomalyNode  (kind="ml")  — adtk unsupervised anomaly score
# --------------------------------------------------------------------------- #
class ADTKAnomalyNode(_HeadBase):
    """adtk unsupervised anomaly detection on the column-`col` series, FIT-ONCE:
    a QuantileAD detector learns thresholds on the training series, then a per-row
    anomaly flag is appended to the raw features for the task-aware readout.
    Robust fallback: a causal rolling z-score outlier flag in NumPy."""
    kind = "ml"

    def __init__(self, name="adtk_anomaly", col=0):
        super().__init__(name, "adtk QuantileAD per-row anomaly flag feature (fit-once).", col)
        self._det = None

    def fit(self, X, y):
        col = np.asarray([row[self.col] for row in X], float)
        try:
            from adtk.detector import QuantileAD
            det = QuantileAD(high=0.98, low=0.02)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                det.fit(self._series(col))
            self._det = det
        except Exception:
            self._det = None
        return super().fit(X, y)

    @staticmethod
    def _series(col: np.ndarray):
        import pandas as pd
        from adtk.data import validate_series
        idx = pd.date_range("2000-01-01", periods=len(col), freq="h")
        return validate_series(pd.Series(np.asarray(col, float), index=idx))

    def _flags(self, col: np.ndarray) -> np.ndarray:
        if self._det is not None:
            try:
                with warnings.catch_warnings(), np.errstate(all="ignore"):
                    warnings.simplefilter("ignore")
                    a = self._det.detect(self._series(col))
                return np.nan_to_num(np.asarray(a.astype(float).fillna(0.0)), nan=0.0)
            except Exception:
                pass
        # Fallback: causal rolling z-score (|z|>3) outlier flag.
        out = np.zeros(len(col))
        for i in range(len(col)):
            w = col[max(0, i - 63): i + 1]
            sd = w.std()
            if sd > 1e-12 and abs(col[i] - w.mean()) / sd > 3.0:
                out[i] = 1.0
        return out

    def _augment(self, X):
        base = np.asarray(X, float)
        col = base[:, self.col]
        flag = self._flags(col).reshape(-1, 1)
        return np.hstack([base, flag])


# --------------------------------------------------------------------------- #
# NO-ARG factories
# --------------------------------------------------------------------------- #
def ssqueeze_node(): return SSQueezeNode()
def scikit_dim_node(): return ScikitDimNode()
def node2vec_graph_node(): return Node2VecGraphNode()
def feature_engine_node(): return FeatureEngineNode()
def stockstats_node(): return StockStatsNode()
def pandas_ta_classic_node(): return PandasTAClassicNode()
def ta_node(): return TANode()
def adtk_anomaly_node(): return ADTKAnomalyNode()
