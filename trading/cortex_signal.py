"""CORTEX B8 — CortexSignalSource: the per-bar live signal pipeline (CANON-51).

Design §6-B8: the brain loop drives CORTEX per bar. One bar in, one honest
decision out:

    OHLCV df ──> features (trading/features_ta, WARM-UP GATED, CANON-24;
                 psychology metadata attached when a psych_fn is available)
             ──> ReflexArc conditional-compute signal (tiered escalation;
                 "stay flat" is a first-class routing outcome, CANON-49)
             ──> RiskOverlay position fraction (dead band + inverse-σ̂ sizing
                 from arch GARCH / EWMA fallback + hard exposure cap)
             ──> {symbol, side, size_fraction, confidence, tier_reached,
                  experts_fired, regime_probs, ...}

PAPER-FIRST / SIGNAL-ONLY: this module never places orders. Execution stays
with the existing loops (BrainExecutor → Freqtrade, LiveTradeLoop → OpenAlgo),
which consult it OPT-IN via env CORTEX_SIGNAL=1 (shadow) / CORTEX_TRADE=1.

Honest degradation: whenever the arc is unfit, data is short, or the feature
warm-up eats every row, the source returns a FLAT signal that SAYS WHY
(``reason``) instead of inventing a number.

Trust feedback (T7): every non-flat signal records which experts fired
(``record_pending``); when the venue later closes a trade on that pair,
``apply_trust_feedback`` turns the realized outcome into a TrustLedger.update
for exactly those experts — the reflex arc's tiers earn/lose routing trust
from real closed trades.
"""
from __future__ import annotations

import os
import time

import numpy as np

FLAT_SIDE = "flat"

# feature names (scale-invariant transforms of trading/features_ta indicators)
CANDLE_FEATURE_NAMES = ["rsi", "d_ema_fast", "d_ema_mid", "d_ema_slow", "d_sma",
                        "bb_pos", "ma_slope_n", "ret_1"]
# order-book psychology features (trading/brain/psychology.snapshot_features):
# joined per-bar from the RECORDED depth history the live engine appends
# continuously — the SAME file serves training and live rows (no serve skew).
# psych_ok = 1 when a fresh-enough snapshot backed the bar, 0 when zero-filled.
PSYCH_FEATURE_NAMES = ["ob_obi5", "ob_spread_bps", "ob_slope_bias",
                       "ob_wall_bias", "ob_gap_bias", "psych_ok"]
# the full brain feature bus (trading/feature_bus.py): higher-timeframe context,
# BTC/cross-market context, and the live-recorded brain signals (regime probs,
# learner bias, fear, LLM p_up) — every stream the brain owns, one vector.
from trading.feature_bus import LIVE_NAMES as BUS_LIVE_NAMES
from trading.feature_bus import MARKET_NAMES as BUS_MARKET_NAMES
from trading.feature_bus import MTF_NAMES as BUS_MTF_NAMES
FEATURE_NAMES = (CANDLE_FEATURE_NAMES + PSYCH_FEATURE_NAMES
                 + BUS_MTF_NAMES + BUS_MARKET_NAMES + BUS_LIVE_NAMES)

# pooled cross-pair fitting: refit the shared arc once this many distinct
# pairs' feature histories have been seen (features are scale-invariant by
# design, so one arc reads every pair honestly).
POOL_MIN_PAIRS = int(os.environ.get("CORTEX_POOL_MIN", "8"))

_PENDING_STATE = "cortex_pending.json"          # pair -> experts awaiting outcome
_SHADOW_STATE = "cortex_shadow.json"            # last shadow decisions (dashboard)


# ── feature build (CANON-24 warm-up gated, scale-invariant) ──────────────────
def _psych_block(feat, symbol: str | None) -> np.ndarray:
    """(n,6) psychology block for the gated feature frame: 5 order-book
    features as-of-joined from the recorded depth history + psych_ok flag.
    Bars without a fresh-enough snapshot (≤3 bar-widths old) are zero-filled
    with psych_ok=0 — the net learns the flag, nothing is faked."""
    n = len(feat)
    block = np.zeros((n, len(PSYCH_FEATURE_NAMES)))
    if symbol is None or "date" not in getattr(feat, "columns", []):
        return block
    try:
        from trading.brain.psychology import load_depth_features
        ts, F = load_depth_features(symbol)
        if len(ts) == 0:
            return block
        import pandas as pd
        bar_ts = pd.to_datetime(feat["date"]).astype("int64").to_numpy() / 1e9
        width = float(np.median(np.diff(bar_ts))) if n > 2 else 900.0
        idx = np.searchsorted(ts, bar_ts, side="right") - 1
        for i in range(n):
            j = idx[i]
            if j >= 0 and (bar_ts[i] - ts[j]) <= 3 * width:
                block[i, :5] = F[j]
                block[i, 5] = 1.0
    except Exception:
        pass                                            # honest zero block on failure
    return block


def build_features(df, symbol: str | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(X (n,14), close (n,)) from an OHLCV DataFrame, warm-up rows dropped.

    All features are unitless so an arc fitted on one coin's scale still reads
    another coin honestly (relative distances to MAs, %B, 1-bar return). When
    `symbol` is given, the recorded order-book psychology block is joined
    per bar (OBI/spread/slope/walls/gap + psych_ok flag)."""
    from trading.features_ta import add_indicators, gate_warmup
    feat = gate_warmup(add_indicators(df))
    if len(feat) == 0:
        return np.zeros((0, len(FEATURE_NAMES))), np.zeros(0)
    close = feat["close"] if "close" in feat.columns else feat["Close"]
    c = close.to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        width = (feat["bb_upper"] - feat["bb_lower"]).to_numpy(dtype=float)
        bb_pos = (c - feat["bb_lower"].to_numpy(dtype=float)) / np.where(width == 0, np.nan, width)
        ret_1 = np.concatenate([[0.0], np.diff(c) / np.where(c[:-1] == 0, np.nan, c[:-1])])
        X = np.column_stack([
            feat["rsi"].to_numpy(dtype=float) / 100.0,
            c / feat["ema_fast"].to_numpy(dtype=float) - 1.0,
            c / feat["ema_mid"].to_numpy(dtype=float) - 1.0,
            c / feat["ema_slow"].to_numpy(dtype=float) - 1.0,
            c / feat["sma"].to_numpy(dtype=float) - 1.0,
            bb_pos,
            feat["ma_slope"].to_numpy(dtype=float) / np.where(c == 0, np.nan, c),
            ret_1,
        ])
    from trading.feature_bus import live_block, market_block, mtf_block
    X = np.column_stack([X, _psych_block(feat, symbol),
                         mtf_block(feat), market_block(feat, symbol),
                         live_block(feat, symbol)])
    good = np.isfinite(X).all(axis=1)
    return X[good], c[good]


def default_arc(**kw):
    """Two-tier ReflexArc over the cheap→deep sklearn pool nodes (B3 recipe)."""
    from nodes import pool
    from nodes.reflex import ReflexArc
    tier1_names = {"sk_logreg", "sk_stump", "sk_gaussnb", "logreg", "stump"}
    tier2_names = {"sk_rf100", "sk_gbdt", "sk_tree5"}
    t1, t2 = [], []
    for f, n in zip(pool.factories(), pool.names()):
        if n in tier1_names:
            t1.append(f)
        elif n in tier2_names:
            t2.append(f)
    if not t1:
        raise RuntimeError("no cheap tier-1 factories available in nodes.pool")
    tiers = [t1, t2] if t2 else [t1]
    args = dict(escalate_margin=0.7, patience=1, capacity=0.5, alpha=0.15,
                epochs=60, folds=2, seed=7)
    args.update(kw)
    return ReflexArc(tiers, **args)


class CortexSignalSource:
    """Per-bar CORTEX signal (CANON-51). Signal-only; never executes."""

    def __init__(self, arc=None, hub=None, *, overlay=None, min_bars: int = 60,
                 auto_fit: bool = True, psych_fn=None,
                 dead_band: float = 0.05, target_risk: float = 0.01,
                 exposure_cap: float = 1.0):
        from trading.risk_overlay import RiskOverlay
        self.arc = arc                      # ReflexArc, fitted or lazy (fit on first signal)
        self.hub = hub                      # BrainHub (regime probs), optional
        self.overlay = overlay or RiskOverlay(dead_band=dead_band,
                                              target_risk=target_risk,
                                              exposure_cap=exposure_cap)
        self.min_bars = int(min_bars)
        self.auto_fit = bool(auto_fit)
        self.psych_fn = psych_fn            # optional callable(symbol) -> dict metadata
        self.last_error: str | None = None
        # cross-pair pooling: per-pair (X,y) stash; once POOL_MIN_PAIRS distinct
        # pairs have been seen the shared arc is refit on ALL of them pooled.
        self._pool: dict = {}
        self._pooled = False

    # ── fitting ──────────────────────────────────────────────────────────────
    def _fitted(self) -> bool:
        return self.arc is not None and hasattr(self.arc, "_tier0")

    def fit(self, df, symbol: str | None = None) -> "CortexSignalSource":
        """Fit the arc on next-bar-up labels from `df` (chronological, no leak)."""
        X, close = build_features(df, symbol)
        if len(X) < 20:
            raise ValueError(f"too few warm feature rows to fit ({len(X)})")
        y = (close[1:] > close[:-1]).astype(int)       # label for row i uses i+1
        if self.arc is None:
            self.arc = default_arc()
        self.arc.fit(X[:-1].tolist(), y.tolist())
        return self

    def _stash_and_maybe_pool(self, symbol: str, X, close) -> None:
        """Stash this pair's (X,y) and refit the shared arc pooled at every
        DOUBLING of distinct pairs seen (8, 16, 32, … — user mandate: train on
        ALL pairs, so the arc keeps converging toward the full universe as the
        loop touches it). Features are scale-invariant so pooling is honest."""
        try:
            y = (close[1:] > close[:-1]).astype(int)
            self._pool[symbol] = (X[:-1][-800:], y[-800:])     # bounded memory
            n = len(self._pool)
            next_at = POOL_MIN_PAIRS if not self._pooled else self._pooled * 2
            if n >= next_at:
                Xp = np.vstack([x for x, _ in self._pool.values()])
                yp = np.concatenate([v for _, v in self._pool.values()])
                arc = default_arc()
                arc.fit(Xp.tolist(), yp.tolist())
                self.arc = arc
                self._pooled = n                               # last pool size
                print(f"[cortex] arc refit POOLED on {n} pairs "
                      f"({len(yp)} rows, {Xp.shape[1]} features incl. order-book)",
                      flush=True)
        except Exception as e:
            self.last_error = f"pool refit failed: {e!r}"

    # ── the per-bar decision ─────────────────────────────────────────────────
    def _flat(self, symbol: str, reason: str, **extra) -> dict:
        out = {"symbol": symbol, "side": FLAT_SIDE, "size_fraction": 0.0,
               "confidence": 0.0, "tier_reached": None, "experts_fired": [],
               "regime_probs": None, "regime_label": None, "reason": reason}
        out.update(extra)
        return out

    def _regime(self, feature_row) -> tuple[list | None, str | None]:
        if self.hub is None:
            return None, None
        try:
            probs = self.hub.regime.proba_online(np.asarray(feature_row, dtype=float))
            return [round(float(p), 4) for p in probs], self.hub.regime.label(probs)
        except Exception:
            return None, None                          # honest: regime model unfit

    def signal(self, symbol: str, df) -> dict:
        """One bar → one decision dict. Never raises; degrades to flat+reason."""
        try:
            return self._signal(symbol, df)
        except Exception as e:                          # honest failure, not a crash
            self.last_error = repr(e)
            return self._flat(symbol, f"cortex error: {e!r}")

    def _signal(self, symbol: str, df) -> dict:
        if df is None or len(df) < self.min_bars:
            n = 0 if df is None else len(df)
            return self._flat(symbol, f"insufficient bars ({n} < {self.min_bars})")
        X, close = build_features(df, symbol)
        if len(X) == 0:
            return self._flat(symbol, "warm-up gating left no feature rows")
        if not self._fitted():
            if not self.auto_fit or len(X) < 20:
                return self._flat(symbol, "reflex arc unfit (no model; refusing to guess)")
            try:                                       # lazy first-bar fit on this history
                y = (close[1:] > close[:-1]).astype(int)
                if self.arc is None:
                    self.arc = default_arc()
                self.arc.fit(X[:-1].tolist(), y.tolist())
            except Exception as e:
                return self._flat(symbol, f"reflex arc fit failed: {e!r}")
        # cross-pair pooling: every pair's history strengthens the shared arc
        self._stash_and_maybe_pool(symbol, X, close)

        row = X[-1]
        regime_probs, regime_label = self._regime(row)
        pred = self.arc.predict([row.tolist()])[0]
        log = (self.arc.compute_log or [None])[0] or {}
        tier = log.get("tier")
        experts = list(log.get("experts") or [])
        conf = float(log.get("confidence") or 0.0)
        base = {"tier_reached": tier, "experts_fired": experts,
                "regime_probs": regime_probs, "regime_label": regime_label,
                "exit_via": log.get("exit")}
        if self.psych_fn is not None:
            try:
                base["psychology"] = self.psych_fn(symbol)
            except Exception:
                base["psychology"] = None
        # feature-bus recorder: today's brain signals become TOMORROW's
        # trainable features (regime probs, fear) — history accrues per bar.
        try:
            from trading.feature_bus import record_live
            rec = {}
            if regime_probs:
                for i, p in enumerate(regime_probs[:3]):
                    rec[f"regime_p{i}"] = p
            psy = base.get("psychology") or {}
            if isinstance(psy, dict) and psy.get("psych_fear") is not None:
                rec["psych_fear"] = psy["psych_fear"]
            if rec:
                record_live(symbol, rec)
        except Exception:
            pass

        if pred is None:                               # stay-flat ROUTING outcome
            return self._flat(symbol, "reflex arc stayed flat (calibrated abstention)",
                              confidence=conf, **base)

        p_up = conf if int(pred) == 1 else 1.0 - conf  # binary class → up-probability
        with np.errstate(divide="ignore", invalid="ignore"):
            rets = np.diff(close) / np.where(close[:-1] == 0, np.nan, close[:-1])
        from trading.risk_overlay import forecast_sigma
        sigma = forecast_sigma(rets[np.isfinite(rets)])
        frac = self.overlay.position(p_up, sigma)
        if frac == 0.0:                                # dead band (CANON-49)
            return self._flat(symbol, "risk overlay dead band (edge too small)",
                              confidence=conf, p_up=round(p_up, 4),
                              sigma_hat=round(float(sigma), 6), **base)
        side = "long" if frac > 0 else "short"
        return {"symbol": symbol, "side": side,
                "size_fraction": round(float(abs(frac)), 6),
                "confidence": round(conf, 4), "p_up": round(p_up, 4),
                "sigma_hat": round(float(sigma), 6), **base}


# ── process-wide source (the brain loop's handle) ────────────────────────────
_SOURCE: CortexSignalSource | None = None


def get_cortex_source() -> CortexSignalSource:
    global _SOURCE
    if _SOURCE is None:
        _SOURCE = CortexSignalSource()
    return _SOURCE


# ── trust feedback: closed trades → TrustLedger.update per fired expert ──────
def record_pending(symbol: str, side: str, experts_fired: list, *, ts: float | None = None) -> None:
    """Remember which experts fired for a non-flat cortex signal on `symbol`."""
    if not experts_fired:
        return
    try:
        from trading.state import load_json, save_json
        pend = load_json(_PENDING_STATE, {})
        pend[str(symbol)] = {"side": side, "experts": list(experts_fired),
                             "ts": float(ts if ts is not None else time.time())}
        save_json(_PENDING_STATE, pend)
    except Exception:
        pass                                            # never break the loop


def record_shadow(segment: str, symbol: str, cortex: dict, decider_action) -> None:
    """Persist the latest shadow comparison (dashboard/audit trail)."""
    try:
        from trading.state import load_json, save_json
        shad = load_json(_SHADOW_STATE, {})
        shad[f"{segment}:{symbol}"] = {
            "ts": time.time(), "cortex": {k: cortex.get(k) for k in
                ("side", "size_fraction", "confidence", "tier_reached",
                 "experts_fired", "regime_label", "reason")},
            "decider_action": decider_action}
        save_json(_SHADOW_STATE, shad)
    except Exception:
        pass


def apply_trust_feedback(closed_trades: list, *, ledger=None) -> int:
    """Match closed trades against pending cortex signals; TrustLedger.update
    each fired expert with the realized outcome (loss ∈ [0,1]; win→0, loss→1,
    scaled by |profit_ratio| when present). Returns #trades credited."""
    try:
        from trading.state import load_json, save_json
        pend = load_json(_PENDING_STATE, {})
        if not pend or not closed_trades:
            return 0
        if ledger is None:
            from core.trust import TrustLedger
            ledger = TrustLedger()
        credited = 0
        for t in closed_trades:
            if not isinstance(t, dict):
                continue
            pair = t.get("pair") or t.get("symbol")
            rec = pend.get(str(pair))
            if not rec:
                continue
            close_ts = t.get("close_timestamp")
            if close_ts is not None and float(close_ts) / 1000.0 < rec.get("ts", 0.0):
                continue                                # trade predates the signal
            profit = t.get("profit_abs")
            ratio = t.get("profit_ratio")
            if profit is None and ratio is None:
                continue
            won = (float(profit) if profit is not None else float(ratio)) > 0.0
            mag = min(1.0, abs(float(ratio))) if ratio is not None else 1.0
            loss = (1.0 - mag) / 2.0 if won else 0.5 + mag / 2.0  # win→<0.5, loss→>0.5
            for expert in rec.get("experts", []):
                try:
                    ledger.update(str(expert), float(np.clip(loss, 0.0, 1.0)))
                except Exception:
                    pass
            pend.pop(str(pair), None)
            credited += 1
        save_json(_PENDING_STATE, pend)
        return credited
    except Exception:
        return 0
