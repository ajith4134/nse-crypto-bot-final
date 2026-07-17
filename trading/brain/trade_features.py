"""trading/brain/trade_features.py — trade rows → ML network inputs → outcome output.

This is the bridge the operator asked for FIRST: take the actual OPEN-trade and
CLOSED-trade column data and feed it, as a numeric feature row, INTO the project's
node network (``GatedMoENode`` over a small panel of real sklearn experts from
``nodes.oss_nodes``) — then read the output the network gives.

Flow:
  1. ``trade_feature_row(trade)`` turns one trade dict (open OR closed, schema- or
     live-loop-keyed) into a fixed, leakage-free numeric vector (entry-time +
     path/excursion features — NEVER the realised P&L, which is the label).
  2. ``TradeOutcomeNet.fit_from_journal(closed_rows)`` builds X (rows) / y (won=1)
     from the CLOSED trades and trains the real network (falls back to a tiny
     numpy logistic regressor only if the node zoo can't be imported/trained, so
     it always returns a real, honest answer offline).
  3. ``TradeOutcomeNet.predict(open_rows)`` pushes each OPEN trade through the
     trained network → {p_win, verdict, expected_R}.

A module-level cache (keyed by the closed-trade count) retrains only when new
closed trades appear, so the dashboard endpoint stays cheap.

Inputs:  list[dict] trade rows.   Outputs: dict reports (JSON-able).
No I/O, no secrets. Offline-safe.
"""
from __future__ import annotations

import datetime as _dt
import math

# ── feature schema (order is the network's input contract) ──────────────────────
_REGIMES = ("trending", "ranging", "volatile", "neutral")
FEATURE_NAMES: list[str] = [
    "dir_sign", "is_crypto", "log_qty", "log_capital", "leverage",
    "brain_confidence", "anomaly_score", "news_compound", "recall_bias",
    "entry_hour_sin", "entry_hour_cos", "mfe_ratio", "mae_ratio",
    *(f"regime_{r}" for r in _REGIMES),
    # order-book trader psychology at entry — the net learns how crowd pressure at the
    # moment of entry influences the profit direction (trading/brain/psychology.py)
    "psych_alignment",          # trader_psychology × dir_sign (crowd with/against the trade)
    "psych_obi", "psych_ofi_sign", "psych_microprice_drift_bps",
    "psych_spread_bps", "psych_depth_slope_bias", "psych_wall_bias", "psych_fear",
]
_CRYPTO_EX = ("binance", "bybit", "okx", "kucoin", "coinbase", "kraken")


def _f(v, default=0.0):
    try:
        if v is None:
            return float(default)
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _is_crypto(trade: dict) -> bool:
    mk = (trade.get("market") or "").upper()
    if mk == "CRYPTO":
        return True
    return (trade.get("exchange") or "").lower() in _CRYPTO_EX


def _brain_telemetry(trade: dict) -> dict:
    """Pull anomaly/news/recall/confidence from the open dict (`brain_entry`) or the
    closed dict (`node_contributions` JSON sidecar + brain_confidence_entry)."""
    out = {"confidence": None, "anomaly_score": 0.0, "news_compound": 0.0, "recall_bias": 0.0}
    be = trade.get("brain_entry")
    if isinstance(be, dict):
        out["confidence"] = be.get("confidence")
        out["anomaly_score"] = _f(be.get("anomaly_score"))
        out["news_compound"] = _f(be.get("news_compound"))
        out["recall_bias"] = _f(be.get("recall_bias"))
        return out
    if trade.get("brain_confidence_entry") is not None:
        out["confidence"] = trade.get("brain_confidence_entry")
    nc = trade.get("node_contributions")
    if isinstance(nc, list) and nc and isinstance(nc[0], dict):
        c = nc[0]
        out["anomaly_score"] = _f(c.get("anomaly_score"))
        out["news_compound"] = _f(c.get("news_compound"))
        out["recall_bias"] = _f(c.get("recall_bias"))
    return out


def _entry_hour(trade: dict) -> int | None:
    if trade.get("entry_hour") is not None:
        try:
            return int(trade["entry_hour"])
        except (TypeError, ValueError):
            pass
    iso = trade.get("entry_datetime") or trade.get("entry_dt") or ""
    try:
        return _dt.datetime.fromisoformat(iso).hour
    except (TypeError, ValueError):
        return None


def _regime(trade: dict) -> str:
    r = (trade.get("market_regime_entry") or "").lower()
    if not r:
        be = trade.get("brain_entry")
        if isinstance(be, dict):
            r = (be.get("regime") or "").lower()
    for known in _REGIMES:
        if known in r:
            return known
    return "neutral"


def trade_feature_row(trade: dict) -> list[float]:
    """One trade dict → the fixed numeric feature vector (FEATURE_NAMES order).

    Works for both open-trade dicts (live_loop keys) and closed-trade dicts
    (schema keys). Leakage-free: realised P&L is never a feature.
    """
    direction = (trade.get("direction") or "LONG").upper()
    dir_sign = 1.0 if direction == "LONG" else -1.0
    qty = _f(trade.get("quantity") or trade.get("Qty") or trade.get("qty"))
    entry = _f(trade.get("entry_price"))
    capital = _f(trade.get("capital") or trade.get("margin_used") or (entry * qty))
    leverage = _f(trade.get("leverage"), 1.0) or 1.0
    bt = _brain_telemetry(trade)
    conf = _f(bt["confidence"], 0.5)

    # path excursions (running for open, full-trade for closed) as a fraction of capital
    if trade.get("mfe") is not None or trade.get("mae") is not None:
        mfe = _f(trade.get("mfe"))
        mae = _f(trade.get("mae"))
    else:
        mfe = _f(trade.get("peak_profit"))
        mae = abs(_f(trade.get("peak_loss")))
    denom = capital if capital else 1.0
    mfe_ratio = mfe / denom
    mae_ratio = mae / denom

    hour = _entry_hour(trade)
    if hour is None:
        hour_sin = hour_cos = 0.0
    else:
        hour_sin = math.sin(2 * math.pi * hour / 24.0)
        hour_cos = math.cos(2 * math.pi * hour / 24.0)

    reg = _regime(trade)
    regime_oh = [1.0 if reg == r else 0.0 for r in _REGIMES]

    # psychology columns: closed-trade schema keys, else the open dict's `psych` sub-dict
    ps = trade.get("psych") if isinstance(trade.get("psych"), dict) else trade
    score = _f(ps.get("trader_psychology"))
    ofi = _f(ps.get("psych_ofi"))
    psych = [
        score * dir_sign,                              # alignment with THIS trade
        _f(ps.get("psych_obi")),
        (1.0 if ofi > 0 else (-1.0 if ofi < 0 else 0.0)),
        _f(ps.get("psych_microprice_drift_bps")),
        _f(ps.get("psych_spread_bps")),
        _f(ps.get("psych_depth_slope_bias")),
        _f(ps.get("psych_wall_bias")),
        _f(ps.get("psych_fear")),
    ]

    return [
        dir_sign, 1.0 if _is_crypto(trade) else 0.0,
        math.log1p(abs(qty)), math.log1p(abs(capital)), leverage,
        conf, bt["anomaly_score"], bt["news_compound"], bt["recall_bias"],
        hour_sin, hour_cos, mfe_ratio, mae_ratio, *regime_oh, *psych,
    ]


def _won(trade: dict) -> int:
    net = trade.get("net_pnl")
    if net is None:
        net = trade.get("net_pnl_crypto")
    if net is None:
        net = trade.get("gross_pnl")
    return 1 if _f(net) > 0 else 0


# ── the network ─────────────────────────────────────────────────────────────────
class _NumpyLogReg:
    """Tiny standardised logistic regression — the offline fallback when the node
    zoo can't be imported/trained. Real fit (gradient descent), real probabilities."""

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
        self.sd = Xa.std(axis=0) + 1e-9
        Xs = (Xa - self.mu) / self.sd
        n, d = Xs.shape
        self.w = np.zeros(d)
        for _ in range(epochs):
            z = Xs @ self.w + self.b
            p = 1.0 / (1.0 + np.exp(-z))
            g = p - ya
            self.w -= lr * (Xs.T @ g) / n + lr * 1e-3 * self.w
            self.b -= lr * g.mean()
        return self

    def predict_proba_row(self, row) -> float:
        import numpy as np
        x = (np.asarray(row, dtype=float) - self.mu) / self.sd
        z = max(-60.0, min(60.0, float(x @ self.w) + self.b))   # clamp: stable sigmoid
        return float(1.0 / (1.0 + math.exp(-z)))


class _TabPFNWrap:
    """Adapts TabPFNClassifier to the engine interface (predict_proba_row → p(win))."""

    def __init__(self, clf):
        self._clf = clf
        self._win_col = list(clf.classes_).index(1)

    def predict_proba_row(self, row) -> float:
        return float(self._clf.predict_proba([list(row)])[0][self._win_col])

    def predict_proba_batch(self, rows: list) -> list[float]:
        """ONE transformer pass for all rows (predict() batches through this)."""
        if not rows:
            return []
        proba = self._clf.predict_proba([list(r) for r in rows])
        return [float(p[self._win_col]) for p in proba]


def clean_window_rows(closed_rows: list | None) -> list:
    """E11-pattern clean-window filter (brain-health 2026-07-17): trades closed before the
    B1/B2 fix batch (2026-07-16 21:23 UTC) carry the measured contaminations — mirror-negation
    lenses, inverted-short-era exits, 456 poisoned USDT|NSE rows. The meta-labeler refit proved
    65% of its file was dirty; these nets trained on the same journal. Fewer honest examples
    beat more dirty ones (728 clean closed rows ≫ MIN_SAMPLES). Rows without a parseable
    exit_datetime are DROPPED (unverifiable era ≠ clean). TRADE_NET_CLEAN_TS=0 disables."""
    import datetime as _dt
    import os as _os
    try:
        cut = float(_os.getenv("TRADE_NET_CLEAN_TS", "1784236980") or 0)
    except (TypeError, ValueError):
        cut = 0.0
    rows = list(closed_rows or [])
    if cut <= 0:
        return rows
    out = []
    for t in rows:
        v = t.get("exit_datetime") if isinstance(t, dict) else None
        if not v:
            continue
        try:
            ts = _dt.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            continue
        if ts >= cut:
            out.append(t)
    return out


class TradeOutcomeNet:
    """Trains the project node network on CLOSED trades, predicts OPEN-trade outcome.

    ``engine`` reports which path actually ran: "gated_moe" (the real node network)
    or "numpy_logreg" (the always-available fallback). ``trained`` is False until
    there are enough closed trades with BOTH outcomes — then predictions are honest
    ``None`` and the verdict falls back to the brain confidence carried on the trade.
    """

    MIN_SAMPLES = 12

    def __init__(self) -> None:
        self.model = None
        self.engine = "untrained"
        self.fallback_reason = ""        # why gated_moe was skipped (honest observability)
        self.trained = False
        self.n_train = 0
        self.oof_accuracy: float | None = None
        self.avg_win_r: float | None = None
        self.avg_loss_r: float | None = None
        self.base_rate: float | None = None

    # build X / y from closed-trade dicts
    @staticmethod
    def _xy(closed_rows: list[dict]):
        X, y = [], []
        for t in closed_rows:
            X.append(trade_feature_row(t))
            y.append(_won(t))
        return X, y

    def fit_from_journal(self, closed_rows: list[dict]) -> "TradeOutcomeNet":
        rows = clean_window_rows(closed_rows)
        rows = [t for t in rows if t.get("entry_price")]
        X, y = self._xy(rows)
        self.n_train = len(X)
        if self.n_train < self.MIN_SAMPLES or len(set(y)) < 2:
            self.trained = False
            self.engine = "untrained"
            return self
        self.base_rate = round(sum(y) / len(y), 4)
        # win/loss R for expected-R mapping (only over trades that have an R-multiple)
        wins = [_f(t.get("r_multiple")) for t in rows if _won(t) and t.get("r_multiple") is not None]
        losses = [_f(t.get("r_multiple")) for t in rows if not _won(t) and t.get("r_multiple") is not None]
        self.avg_win_r = round(sum(wins) / len(wins), 3) if wins else None
        self.avg_loss_r = round(sum(losses) / len(losses), 3) if losses else None

        self._fit_oof(X, y)        # honest leave-one-batch-out accuracy estimate
        # final model on ALL closed trades (the real node network, with fallback)
        self.model = self._train_engine(X, y)
        self.trained = self.model is not None
        return self

    def _train_engine(self, X, y):
        """Try the real GatedMoENode over sklearn experts; fall back to numpy logreg.

        TRADE_NET_ENGINE=tabpfn promotes the TabPFN-v2 challenger (only after it wins
        the OOF duel — trading/brain/challenger.py; never switched silently)."""
        import os as _os
        # HOT-PATH GUARD (2026-07-12): TabPFN is a transformer whose CPU inference costs ~7s per
        # predict (6 in-context forward passes). The live per-symbol decider calls this in a loop
        # over the whole universe → cycles blew to ~1000s and NO trades opened (deadline-deferred).
        # Keep TabPFN for the OFFLINE challenger/attribution (they build it directly), but the LIVE
        # TradeOutcomeNet uses the fast gated-MoE/logreg engine (cached → ~ms) unless explicitly
        # allowed with TRADE_NET_TABPFN_LIVE=1. money-lens: a system that can't finish a cycle and
        # open a trade earns nothing — completing beats a marginally-more-accurate 7s model.
        _want_tabpfn = _os.getenv("TRADE_NET_ENGINE", "").strip().lower() == "tabpfn"
        _tabpfn_live = _os.getenv("TRADE_NET_TABPFN_LIVE", "0").strip().lower() in ("1", "true", "yes", "on")
        if _want_tabpfn and _tabpfn_live:
            try:
                from tabpfn import TabPFNClassifier
                _os.environ.setdefault("TABPFN_ALLOW_CPU_LARGE_DATASET", "1")
                # CPU inference cost scales with the in-context train set: cap at the
                # newest 1200 rows — the same per-fold size the promotion duel measured
                # accuracy on (challenger.py), and ~3× faster than the full journal.
                cap = int(_os.getenv("TABPFN_CONTEXT_ROWS", "1200"))
                Xc, yc = X[-cap:], y[-cap:]
                clf = TabPFNClassifier(device="cpu", n_estimators=2,
                                       ignore_pretraining_limits=True)
                clf.fit(Xc, yc)
                self.engine = "tabpfn_v2"
                return _TabPFNWrap(clf)
            except Exception as e:
                self.fallback_reason = f"tabpfn: {type(e).__name__}: {str(e)[:100]}"
        try:
            from nodes.gated_node import GatedMoENode
            from nodes.oss_nodes import gbdt_node, logreg_node, rf_node
            experts = [logreg_node, lambda: rf_node(120), lambda: gbdt_node(120)]
            node = GatedMoENode(experts, epochs=200, task="binary", name="trade_outcome_gate")
            node.fit(X, y)
            self.engine = "gated_moe"
            return node
        except Exception as e:
            self.fallback_reason = f"{type(e).__name__}: {str(e)[:120]}"
            m = _NumpyLogReg().fit(X, y)
            self.engine = "numpy_logreg"
            return m

    def _fit_oof(self, X, y) -> None:
        """K-fold out-of-fold accuracy so the dashboard shows an HONEST skill number,
        not the in-sample (optimistic) fit."""
        try:
            import numpy as np
            Xa, ya = np.asarray(X, dtype=float), np.asarray(y, dtype=int)
            n = len(ya)
            k = min(5, n)
            idx = np.arange(n)
            folds = np.array_split(idx, k)
            correct = 0
            for f in folds:
                mask = np.ones(n, dtype=bool)
                mask[f] = False
                if len(set(ya[mask].tolist())) < 2:
                    continue
                m = _NumpyLogReg().fit(Xa[mask], ya[mask])
                for i in f:
                    p = m.predict_proba_row(Xa[i])
                    correct += int((p >= 0.5) == bool(ya[i]))
            self.oof_accuracy = round(correct / n, 4) if n else None
        except Exception:
            self.oof_accuracy = None

    def _proba(self, row: list[float]) -> float:
        if self.engine == "gated_moe":
            return float(self.model.predict_proba([row])[0])
        return float(self.model.predict_proba_row(row))

    def predict_one(self, trade: dict) -> dict:
        """Push ONE trade row through the network → outcome output."""
        if not self.trained:
            # honest fallback: surface the brain confidence the trade already carries
            conf = _brain_telemetry(trade)["confidence"]
            return {"p_win": None, "verdict": "insufficient history",
                    "confidence": (round(_f(conf), 4) if conf is not None else None),
                    "expected_R": None, "engine": self.engine}
        p = max(0.0, min(1.0, self._proba(trade_feature_row(trade))))
        return self._outcome_from_p(p)

    def _outcome_from_p(self, p: float) -> dict:
        verdict = "WIN likely" if p >= 0.58 else ("LOSS likely" if p <= 0.42 else "uncertain")
        exp_r = None
        if self.avg_win_r is not None and self.avg_loss_r is not None:
            exp_r = round(p * self.avg_win_r + (1 - p) * self.avg_loss_r, 3)
        return {"p_win": round(p, 4), "verdict": verdict,
                "confidence": round(p, 4), "expected_R": exp_r, "engine": self.engine}

    def predict(self, open_rows: list[dict]) -> list[dict]:
        # TabPFN pays a transformer pass PER CALL — batch all open rows into one pass
        # (75 open trades were ~75 sequential passes otherwise; the gated_moe/logreg
        # engines are cheap either way and keep the per-row path).
        if self.trained and self.engine == "tabpfn_v2" and open_rows:
            feats = [trade_feature_row(t) for t in open_rows]
            probs = self.model.predict_proba_batch(feats)
            return [{"symbol": t.get("symbol"),
                     **self._outcome_from_p(max(0.0, min(1.0, float(p))))}
                    for t, p in zip(open_rows, probs)]
        return [{"symbol": t.get("symbol"), **self.predict_one(t)} for t in (open_rows or [])]

    def info(self) -> dict:
        return {"engine": self.engine, "trained": self.trained, "n_train": self.n_train,
                "oof_accuracy": self.oof_accuracy, "base_rate": self.base_rate,
                "avg_win_R": self.avg_win_r, "avg_loss_R": self.avg_loss_r,
                "fallback_reason": self.fallback_reason,
                "features": FEATURE_NAMES, "min_samples": self.MIN_SAMPLES}


# ── cached singleton (retrain only when the closed-trade count changes) ──────────
_CACHE: dict = {"count": -1, "net": None}


def get_outcome_net(closed_rows: list[dict]) -> TradeOutcomeNet:
    """Return a TradeOutcomeNet trained on `closed_rows`, retraining only when the
    closed-trade count changes (cheap enough for a 4s dashboard poll)."""
    n = len(closed_rows or [])
    if _CACHE["net"] is None or _CACHE["count"] != n:
        _CACHE["net"] = TradeOutcomeNet().fit_from_journal(closed_rows)
        _CACHE["count"] = n
    return _CACHE["net"]
