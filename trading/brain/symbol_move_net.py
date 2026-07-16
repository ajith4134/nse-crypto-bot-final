"""trading/brain/symbol_move_net.py — the brain's OUTPUT network, changed on owner ask 2026-07-13.

The old bridge (trade_features.TradeOutcomeNet) answered "will this trade WIN?" → a single p_win.
The owner wants the network to answer the two questions that actually place a trade, now that every
symbol carries a rich RAM feature set (all filters/screeners + 24h volume + psychology + candles):

    predict(symbol_context) →
        direction        : LONG | SHORT | NEUTRAL     (Head B — an explicit call)
        p_up             : calibrated P(price rises)   (the classifier's probability)
        expected_move_pct: signed % the symbol is expected to move   (Head A — sign = direction,
                                                                       |value| = conviction / size)

Two heads over ONE shared, RAM-enriched feature vector:
  • Head A (magnitude): a standardized ridge regressor (always-available, closed-form) — optionally the
    project node network (GatedMoENode task="regression") when the zoo imports — trained on the realised
    signed move `(exit-entry)/entry*100` of every closed trade.
  • Head B (direction): the SAME GatedMoENode binary classifier / numpy-logreg fallback the outcome net
    uses, but the target is the symbol's realised UP/DOWN, not win/loss — so it is a genuine directional
    model whose hit-rate the Truth Ledger can score like any other source.

Reuses trade_features.trade_feature_row for the base vector and APPENDS the RAM market-context features
(the all-filter p_up set + 24h volume) captured at entry (decision_snapshot.market_context) so training
and live inference share ONE contract. Journal-trained, cached by closed-trade count, offline-honest.

Flags: SYMBOL_MOVE_NET=1 (on; default-on in paper — the learning lab). Never raises into a loop.
"""
from __future__ import annotations

import math
import os

from trading.brain.trade_features import (FEATURE_NAMES, _entry_hour, _f, _won,
                                          trade_feature_row)

# the RAM market-context features appended to the base vector (owner ask: "more symbol data as input").
# Each all-market filter/screener rides in as its p_up (0.5 = neutral when absent); 24h volume is logged.
_FILTER_KINDS = ("momentum", "funding", "taker", "book_imbalance", "longshort",
                 "oi_trend", "liquidations", "pcr")
_RAM_FEATURES = [*(f"flt_{k}" for k in _FILTER_KINDS), "log_quote_volume_24h", "pct_change_24h"]
MOVE_FEATURE_NAMES = [*FEATURE_NAMES, *_RAM_FEATURES]
# SERVE-SAFE vector (B1/B2 fix 2026-07-16): ONLY features that exist identically at train time
# (closed row) AND consult time (live candidate). The old full vector included the trade's own
# realized excursions (mfe/mae — outcome leakage) and trade-shaped fields (qty/capital/side) that
# live candidates default to constants — the model learned the leak, then served a near-constant
# (measured: p_up ≈ 0.2937 for every symbol, 99.3% SHORT votes). Same disease as the
# direction_model f_*/m_* dead pipe.
SERVE_FEATURE_NAMES = [*_RAM_FEATURES, "hour_sin", "hour_cos"]


def enabled() -> bool:
    return os.environ.get("SYMBOL_MOVE_NET", "1") in ("1", "true", "TRUE", "yes", "on")


def _market_context(trade: dict) -> dict:
    ds = trade.get("decision_snapshot")
    if isinstance(ds, dict):
        mc = ds.get("market_context")
        if isinstance(mc, dict):
            return mc
    mc = trade.get("market_context")
    return mc if isinstance(mc, dict) else {}


def _ram_row(trade: dict) -> list[float]:
    """The RAM market-context slice of the feature vector (filters + 24h volume). Missing filter →
    0.5 (neutral p_up); missing volume → 0. Order matches _RAM_FEATURES."""
    mc = _market_context(trade)
    flt = mc.get("filters") if isinstance(mc.get("filters"), dict) else {}
    row = [_f(flt.get(f"filter:{k}"), 0.5) for k in _FILTER_KINDS]
    qv = _f(mc.get("quote_volume_24h"), 0.0)
    row.append(math.log1p(max(0.0, qv)))
    row.append(_f(mc.get("pct_change_24h"), 0.0))
    return row


def move_feature_row(trade: dict) -> list[float]:
    """Full RAM-enriched feature vector (MOVE_FEATURE_NAMES order) for a trade OR a live candidate
    dict. Reuses the outcome net's base row so the two nets share one feature convention."""
    return [*trade_feature_row(trade), *_ram_row(trade)]


def serve_feature_row(trade: dict) -> list[float]:
    """SERVE-SAFE vector (SERVE_FEATURE_NAMES order): RAM market-context slice + clock. Identical
    availability at train (closed row: entry hour) and consult (live candidate: hour of now), so
    the heads cannot learn anything they will not be given at decision time."""
    hour = _entry_hour(trade)
    if hour is None:
        import time as _t
        hour = _t.localtime().tm_hour
    return [*_ram_row(trade),
            math.sin(2 * math.pi * hour / 24.0), math.cos(2 * math.pi * hour / 24.0)]


def _move_pct(trade: dict) -> float | None:
    """Realised signed move of the SYMBOL over the trade: (exit-entry)/entry*100. This is the
    regression label — the symbol's actual price movement, independent of the trade's side."""
    entry = _f(trade.get("entry_price"))
    exit_ = _f(trade.get("exit_price"))
    if not entry or not exit_:
        return None
    return (exit_ - entry) / entry * 100.0


# ── Head A: standardized ridge regression (always-available, closed-form) ─────────────
class _NumpyRidge:
    def __init__(self, lam: float = 1.0) -> None:
        self.w = None
        self.b = 0.0
        self.mu = None
        self.sd = None
        self.lam = lam

    def fit(self, X, y):
        import numpy as np
        Xa = np.asarray(X, dtype=float)
        ya = np.asarray(y, dtype=float)
        self.mu = Xa.mean(axis=0)
        self.sd = Xa.std(axis=0)
        self.sd[self.sd < 1e-6] = 1.0            # zero-variance features contribute 0 (no blow-up)
        Xs = (Xa - self.mu) / self.sd
        n, d = Xs.shape
        A = Xs.T @ Xs + self.lam * np.eye(d)
        self.w = np.linalg.solve(A, Xs.T @ (ya - ya.mean()))
        self.b = float(ya.mean())
        return self

    def predict_row(self, row) -> float:
        import numpy as np
        x = (np.asarray(row, dtype=float) - self.mu) / self.sd
        x = np.clip(x, -6.0, 6.0)                 # clamp OOD inputs so a tiny-capital ratio can't blow up
        return float(x @ self.w + self.b)


class _NumpyLogRegDir:
    """Standardized logistic regression for the direction head (p_up). Real gradient fit."""

    def __init__(self) -> None:
        self.w = None
        self.b = 0.0
        self.mu = None
        self.sd = None

    def fit(self, X, y, epochs: int = 400, lr: float = 0.1):
        import numpy as np
        Xa = np.asarray(X, dtype=float)
        ya = np.asarray(y, dtype=float)
        self.mu = Xa.mean(axis=0)
        self.sd = Xa.std(axis=0)
        self.sd[self.sd < 1e-6] = 1.0            # zero-variance features contribute 0 (no blow-up)
        Xs = (Xa - self.mu) / self.sd
        n, d = Xs.shape
        self.w = np.zeros(d)
        for _ in range(epochs):
            p = 1.0 / (1.0 + np.exp(-(Xs @ self.w + self.b)))
            g = p - ya
            self.w -= lr * (Xs.T @ g) / n + lr * 1e-3 * self.w
            self.b -= lr * g.mean()
        return self

    def predict_proba_row(self, row) -> float:
        import numpy as np
        x = np.clip((np.asarray(row, dtype=float) - self.mu) / self.sd, -6.0, 6.0)
        z = max(-60.0, min(60.0, float(x @ self.w) + self.b))
        return float(1.0 / (1.0 + math.exp(-z)))


class SymbolMoveNet:
    """Two-head symbol-move network: direction (p_up) + expected signed move %."""

    MIN_SAMPLES = 20
    # bands (%): how far |expected_move| must clear to call a side vs abstain, and p_up conviction band
    NEUTRAL_MOVE_PCT = 0.15
    NEUTRAL_PUP_BAND = 0.04
    # winsorise the move-% label: a handful of leveraged micro-caps swing ±hundreds of % and would
    # otherwise dominate the least-squares fit (MAE 163%). Clip to a sane per-trade move range so the
    # regressor learns the typical signal, not the outliers. The SIGN (direction) is always preserved.
    MOVE_CLIP_PCT = 25.0

    def __init__(self) -> None:
        self.dir_model = None
        self.move_model = None
        self.dir_engine = "untrained"
        self.trained = False
        self.n_train = 0
        self.dir_oof_acc: float | None = None
        self.move_mae: float | None = None
        self.up_rate: float | None = None
        self.fallback_reason = ""

    # ── training ──────────────────────────────────────────────────────────────────
    def fit_from_journal(self, closed_rows: list[dict]) -> "SymbolMoveNet":
        X, y_dir, y_move = [], [], []
        for t in (closed_rows or []):
            mv = _move_pct(t)
            if mv is None:
                continue
            X.append(serve_feature_row(t))
            y_dir.append(1 if mv > 0 else 0)
            y_move.append(max(-self.MOVE_CLIP_PCT, min(self.MOVE_CLIP_PCT, mv)))  # winsorised label
        self.n_train = len(X)
        if self.n_train < self.MIN_SAMPLES or len(set(y_dir)) < 2:
            self.trained = False
            self.dir_engine = "untrained"
            return self
        self.up_rate = round(sum(y_dir) / len(y_dir), 4)
        self._fit_oof(X, y_dir)
        self.dir_model = self._train_dir(X, y_dir)
        self.move_model = _NumpyRidge(lam=2.0).fit(X, y_move)
        self._move_mae(X, y_move)
        self.trained = self.dir_model is not None and self.move_model is not None
        return self

    def _train_dir(self, X, y):
        """Direction classifier: the project node network (GatedMoENode binary) over sklearn experts,
        numpy-logreg fallback — same engine family as the outcome net, target = symbol UP/DOWN."""
        try:
            from nodes.gated_node import GatedMoENode
            from nodes.oss_nodes import gbdt_node, logreg_node, rf_node
            node = GatedMoENode([logreg_node, lambda: rf_node(120), lambda: gbdt_node(120)],
                                epochs=200, task="binary", name="symbol_direction_gate")
            node.fit(X, y)
            self.dir_engine = "gated_moe"
            return node
        except Exception as e:
            self.fallback_reason = f"{type(e).__name__}: {str(e)[:120]}"
            m = _NumpyLogRegDir().fit(X, y)
            self.dir_engine = "numpy_logreg"
            return m

    def _fit_oof(self, X, y) -> None:
        try:
            import numpy as np
            Xa, ya = np.asarray(X, dtype=float), np.asarray(y, dtype=int)
            n = len(ya)
            folds = np.array_split(np.arange(n), min(5, n))
            correct = 0
            for fdx in folds:
                mask = np.ones(n, dtype=bool)
                mask[fdx] = False
                if len(set(ya[mask].tolist())) < 2:
                    continue
                m = _NumpyLogRegDir().fit(Xa[mask], ya[mask])
                for i in fdx:
                    correct += int((m.predict_proba_row(Xa[i]) >= 0.5) == bool(ya[i]))
            self.dir_oof_acc = round(correct / n, 4) if n else None
        except Exception:
            self.dir_oof_acc = None

    def _move_mae(self, X, y) -> None:
        try:
            import numpy as np
            Xa, ya = np.asarray(X, dtype=float), np.asarray(y, dtype=float)
            n = len(ya)
            folds = np.array_split(np.arange(n), min(5, n))
            err, cnt = 0.0, 0
            for fdx in folds:
                mask = np.ones(n, dtype=bool)
                mask[fdx] = False
                m = _NumpyRidge(lam=2.0).fit(Xa[mask], ya[mask])
                for i in fdx:
                    err += abs(m.predict_row(Xa[i]) - ya[i])
                    cnt += 1
            self.move_mae = round(err / cnt, 4) if cnt else None
        except Exception:
            self.move_mae = None

    # ── inference ───────────────────────────────────────────────────────────────────
    def _p_up(self, row) -> float:
        if self.dir_engine == "gated_moe":
            return float(self.dir_model.predict_proba([row])[0])
        return float(self.dir_model.predict_proba_row(row))

    def predict_one(self, ctx: dict) -> dict:
        """ctx: a trade dict OR a live candidate carrying the same keys (entry_price, direction,
        decision_snapshot.market_context, psychology…). Returns direction + p_up + expected move %."""
        if not self.trained:
            return {"direction": "NEUTRAL", "p_up": None, "expected_move_pct": None,
                    "size_hint": 0.0, "engine": self.dir_engine, "trained": False}
        row = serve_feature_row(ctx)
        p_up = max(0.0, min(1.0, self._p_up(row)))
        move = float(self.move_model.predict_row(row))
        move = max(-self.MOVE_CLIP_PCT, min(self.MOVE_CLIP_PCT, move))   # bound to trained range
        # direction: BOTH heads must agree past their neutral band, else abstain (honest neutral).
        dir_up = p_up > 0.5 + self.NEUTRAL_PUP_BAND
        dir_dn = p_up < 0.5 - self.NEUTRAL_PUP_BAND
        move_up = move > self.NEUTRAL_MOVE_PCT
        move_dn = move < -self.NEUTRAL_MOVE_PCT
        if dir_up and move_up:
            direction = "LONG"
        elif dir_dn and move_dn:
            direction = "SHORT"
        else:
            direction = "NEUTRAL"
        # size hint ∈ [0,1]: conviction from the direction margin scaled by the move magnitude
        size = min(1.0, abs(p_up - 0.5) * 2.0 * min(1.0, abs(move) / 1.0)) if direction != "NEUTRAL" else 0.0
        return {"direction": direction, "p_up": round(p_up, 4),
                "expected_move_pct": round(move, 4), "size_hint": round(size, 3),
                "engine": self.dir_engine, "trained": True}

    def predict(self, rows: list[dict]) -> list[dict]:
        return [{"symbol": t.get("symbol"), **self.predict_one(t)} for t in (rows or [])]

    def info(self) -> dict:
        return {"trained": self.trained, "n_train": self.n_train,
                "dir_engine": self.dir_engine, "dir_oof_accuracy": self.dir_oof_acc,
                "move_mae_pct": self.move_mae, "up_rate": self.up_rate,
                "fallback_reason": self.fallback_reason,
                "features": SERVE_FEATURE_NAMES, "min_samples": self.MIN_SAMPLES,
                "enabled": enabled()}


# ── cached singleton (retrain only when the closed-trade count changes) ──────────────
_CACHE: dict = {"count": -1, "net": None}


def get_move_net(closed_rows: list[dict]) -> SymbolMoveNet:
    n = len(closed_rows or [])
    if _CACHE["net"] is None or _CACHE["count"] != n:
        _CACHE["net"] = SymbolMoveNet().fit_from_journal(closed_rows)
        _CACHE["count"] = n
    return _CACHE["net"]


# ── live consult (train OFF the hot path, predict cheap) ─────────────────────────────
# The funnel-learn daemon calls refresh() so training (GatedMoENode fit over the journal, ~seconds)
# NEVER runs in the per-candidate decision path (the TabPFN hot-path lesson). The executor calls
# consult() which only does one cheap forward pass on the already-trained cached net.
_LIVE: dict = {"net": None}


def refresh(closed_rows: list[dict] | None = None) -> dict:
    """Train/retrain the live net from the journal and cache it. Off-hot-path (daemon). Returns info."""
    if not enabled():
        return {"enabled": False}
    try:
        if closed_rows is None:
            from trading.journal.journal import TradeJournal
            closed_rows = [t.to_dict() for t in TradeJournal().trades]
        _LIVE["net"] = get_move_net(closed_rows)
        return _LIVE["net"].info()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:120]}"}


def ensure_trained_once() -> bool:
    """Train the live net ONCE per process if it isn't already (e.g. the dashboard, which never
    runs the funnel daemon). SYNCHRONOUS by design: the GatedMoENode fit uses torch, which
    DEADLOCKS in a daemon thread — so callers must invoke this from a cached / single-flight path
    (not a per-request hot loop). Bounded ~seconds, single-flight, never raises. Returns trained?."""
    if _LIVE.get("net") is not None:
        return True
    if not enabled() or _LIVE.get("_training"):
        return _LIVE.get("net") is not None
    _LIVE["_training"] = True
    try:
        refresh()
    except Exception:
        pass
    finally:
        _LIVE["_training"] = False
    return _LIVE.get("net") is not None


def consult(ctx: dict) -> dict:
    """Predict for ONE live candidate from the cached net — cheap (one forward pass), never trains,
    never raises. Returns the untrained/neutral shape until refresh()/ensure_trained_once() ran."""
    net = _LIVE["net"]
    if net is None or not enabled():
        return {"direction": "NEUTRAL", "p_up": None, "expected_move_pct": None,
                "size_hint": 0.0, "trained": False}
    try:
        return net.predict_one(ctx)
    except Exception:
        return {"direction": "NEUTRAL", "p_up": None, "expected_move_pct": None,
                "size_hint": 0.0, "trained": False}
