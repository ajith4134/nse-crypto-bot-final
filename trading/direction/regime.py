"""trading/direction/regime.py — D5: the direction regime classifier (goal Pillar 27).

Why: momentum-style entries in a ranging market are the measured failure (buy the
spike → mean reversion eats it), and mean-reversion entries in a trend bleed the other
way. Direction accuracy is CONDITIONAL on regime, so every Truth-Ledger claim and
every Mirror-Gate lookup is bucketed by THIS label — the gate then learns per regime
(e.g. a source can be trusted in trend and inverted in chop, test-pinned in
test_mirror_gate.test_regime_bucket_beats_cross_regime_sum).

Method (grounded, cheap, CPU-trivial — Kaufman's Efficiency Ratio, the standard
trendiness measure from KAMA): over the last `_ER_BARS` 5m closes,
    ER = |close_now − close_then| / Σ|Δclose|
ER ≥ threshold and rising prices → trend_up; falling → trend_down; else chop.
A large jump between the current ER and the ER half a window ago means the market is
CHANGING state → "transition" (the abstain-worthy moment; regime-switch literature —
see research/direction-accuracy-program/sota-research.md §4 — says stale-regime
models are the danger, not either stable regime).

Data: the same local 5m feathers candle_updater keeps fresh (zero network); the
result is cached in the state dir for ~60s so every process shares one read.
Symbols without local candles fall back to the MARKET regime (BTC perp), and if even
that is unreadable the honest answer is "unknown" — never a guessed label.

Levers: DIRECTION_REGIME_ER (default 0.35), DIRECTION_REGIME_JUMP (default 0.25).
"""
from __future__ import annotations

import os
import time

from trading import state

_FILE = "direction_regime.json"                # {key: {"regime", "er", "ts"}}
_TTL_S = 60.0
_ER_BARS = 48                                  # 4h of 5m bars
_MARKET_SYMBOL = "BTC/USDT:USDT"


def _env_f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _er(closes) -> tuple[float | None, bool]:
    """(efficiency ratio, rising?) over the sequence; None when degenerate."""
    if closes is None or len(closes) < 8:
        return None, False
    net = float(closes[-1]) - float(closes[0])
    path = sum(abs(float(closes[i + 1]) - float(closes[i]))
               for i in range(len(closes) - 1))
    if path <= 0:
        return None, False
    return abs(net) / path, net > 0


def _classify_closes(closes) -> dict:
    """Pure classification from a close series (test oracle — no I/O)."""
    thr = _env_f("DIRECTION_REGIME_ER", 0.35)
    jump = _env_f("DIRECTION_REGIME_JUMP", 0.25)
    if closes is None or len(closes) < _ER_BARS // 2 + 8:
        return {"regime": "unknown", "er": None}
    now_er, rising = _er(closes[-_ER_BARS:])
    prev_er, _ = _er(closes[-_ER_BARS:-_ER_BARS // 2] if len(closes) >= _ER_BARS
                     else closes[:len(closes) // 2])
    if now_er is None:
        return {"regime": "unknown", "er": None}
    if prev_er is not None and abs(now_er - prev_er) > jump:
        return {"regime": "transition", "er": round(now_er, 4)}
    if now_er >= thr:
        return {"regime": "trend_up" if rising else "trend_down",
                "er": round(now_er, 4)}
    return {"regime": "chop", "er": round(now_er, 4)}


def classify(symbol: str | None = None, segment: str = "futures") -> dict:
    """Regime for one symbol (or the market when None): {"regime", "er", "basis"}.
    Cached ~60s per key in the state dir; falls back symbol → market → unknown."""
    key = f"{segment}|{symbol or 'MARKET'}"
    now = time.time()
    cached = (state.load_json(_FILE, {}) or {}).get(key)
    if cached and now - float(cached.get("ts") or 0) < _TTL_S:
        return cached
    out = {"regime": "unknown", "er": None, "basis": "none", "ts": now}
    try:
        from trading.direction.truth_ledger import _closes, _feather_for
        for sym, basis in ((symbol, "symbol"), (_MARKET_SYMBOL, "market")):
            if not sym:
                continue
            path, _ = _feather_for(sym, segment if basis == "symbol" else "futures")
            data = _closes(path) if path else None
            if not data:
                continue
            ts_arr, close_arr = data
            if now - float(ts_arr[-1]) > 3 * 3600:
                continue                        # stale candles → not an honest read
            res = _classify_closes(close_arr.tolist())
            if res["regime"] != "unknown":
                out = {**res, "basis": basis, "ts": now}
                break
    except Exception:
        pass

    def _m(d: dict) -> dict:
        d[key] = out
        if len(d) > 300:                        # bound the cache file
            for k in sorted(d, key=lambda k: d[k].get("ts") or 0)[:100]:
                d.pop(k, None)
        return d
    try:
        state.mutate_json(_FILE, _m, default={})
    except Exception:
        pass
    return out


def market_regime() -> str:
    """The market-level regime label (BTC perp basis) — the default bucket key for
    Truth-Ledger claims whose caller didn't compute a per-symbol read."""
    return str(classify(None).get("regime") or "unknown")
