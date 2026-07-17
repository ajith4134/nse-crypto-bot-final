"""trading/direction/market_state.py — cross-symbol market state: correlation regime,
breadth, BTC lead, and the leader→follower spillover sources.

Built from the owner's 2026-07-17 cross-symbol direction quest (research/direction/
cross-symbol-direction-catalog.md, routes 1/2/4/7/9) on top of the in-RAM mirror — one shared
snapshot per minute over the whole perp universe, zero network on the decision path.

What it provides
----------------
snapshot()      one cached read of the top-of-universe: per-symbol 15m returns off the 5m
                mirror candles, mean pairwise correlation of the top-20 (48×5m returns),
                breadth (fraction of the top-100 with a positive 15m return), BTC/ETH context.
corr_regime()   'high' | 'mid' | 'low' — high = one-factor market (only the leader's side
                matters; per-coin signals are noise around the BTC factor), low = idiosyncratic
                (per-coin signals allowed). A CONDITIONER, recorded on every entry vector.
conditioners()  ev_* fields merged into trading.brain.entry_vector rows.
readings(sym)   the measured direction sources, each recorded to the Truth Ledger:
                  spillover_large   — top-cap follower COPIES an un-followed leader move
                                      (slow information diffusion; lead 16-118s documented)
                  spillover_seesaw  — small-cap follower gets the CONTRA lean (the documented
                                      negative large→small cross-predictability)
                  breadth_tilt      — extreme one-sided breadth = trend day → continuation
                The copy/seesaw split is literature-grounded, NOT a mirror pair: they fire on
                DISJOINT symbol sets (B1 mirror-negation quarantine does not apply).

All sources start unproven → ~0 weight in learned_direction until the ledger proves them
(CONVENTIONS §16). Never raises; empty/None on a cold mirror. MARKET_STATE_SOURCE=0 disables
the readings, the conditioners stay (they are measurement, not direction).
"""
from __future__ import annotations

import math
import os
import threading
import time

_LOCK = threading.RLock()
_SNAP: dict = {}                     # {"ts": epoch, ...} — the cached snapshot
_TTL_S = float(os.environ.get("MARKET_STATE_TTL_S", "60") or 60)

_TOP_CORR = 20                       # symbols in the correlation matrix
_TOP_BREADTH = 100                   # symbols in the breadth set
_CORR_BARS = 48                      # 48 × 5m = 4h of returns for the corr estimate
_RET_BARS = 3                        # 3 × 5m = the 15m return window
_LEADERS = ("BTCUSDT", "ETHUSDT")


def _flag(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default


def _flat(symbol: str) -> str:
    return (symbol or "").upper().split(":")[0].replace("/", "")


def _ret(closes: list[float], k: int) -> float | None:
    """Simple return over the last k bars of a close series (None on short/degenerate)."""
    if len(closes) < k + 1 or not closes[-k - 1]:
        return None
    return closes[-1] / closes[-k - 1] - 1.0


# ── the shared snapshot ──────────────────────────────────────────────────────────────
def snapshot(now: float | None = None) -> dict:
    """One cross-symbol read of the whole market, cached _TTL_S across every caller in the
    process (50 breadth candidates share a single build). {} when the mirror is cold."""
    t = time.time() if now is None else float(now)
    with _LOCK:
        if _SNAP.get("ts") and t - _SNAP["ts"] < _TTL_S:
            return dict(_SNAP)
    snap = _build(t)
    with _LOCK:
        _SNAP.clear()
        _SNAP.update(snap)
    return dict(snap)


def _build(t: float) -> dict:
    out: dict = {"ts": t, "available": False}
    try:
        from trading.broker_sense.binance_stream import get_mirror
        m = get_mirror()
        movers = m.movers(_TOP_BREADTH, by="quote_volume")
        if not movers:
            return out
        rank = {r["symbol"]: i for i, r in enumerate(movers)}
        # per-symbol 15m returns + top-20 close series for the correlation estimate
        rets: dict[str, float] = {}
        series: dict[str, list[float]] = {}
        for r in movers:
            s = r["symbol"]
            bars = m.candles(s, 300, _CORR_BARS + 1)
            closes = [float(b[4]) for b in bars]
            ret = _ret(closes, _RET_BARS)
            if ret is not None:
                rets[s] = ret
            if rank[s] < _TOP_CORR and len(closes) >= _CORR_BARS:
                series[s] = closes[-_CORR_BARS:]
        out["n_symbols"] = len(rets)
        if len(rets) < 10:
            return out
        # mean pairwise correlation of 5m returns across the top-20 (the one-factor meter)
        corr = None
        if len(series) >= 8:
            import numpy as np
            mat = np.asarray([[c2 / c1 - 1.0 for c1, c2 in zip(v[:-1], v[1:])]
                              for v in series.values()], dtype="float64")
            sd = mat.std(axis=1)
            mat = mat[sd > 0]
            if mat.shape[0] >= 8:
                cm = np.corrcoef(mat)
                n = cm.shape[0]
                corr = float((cm.sum() - n) / (n * (n - 1)))
        # breadth + leader context
        ups = sum(1 for v in rets.values() if v > 0)
        breadth = ups / len(rets)
        alt = [v for s, v in rets.items() if s not in _LEADERS]
        alt.sort()
        alt_med = alt[len(alt) // 2] if alt else None
        btc, eth = rets.get("BTCUSDT"), rets.get("ETHUSDT")
        out.update({
            "available": True, "corr_top20": None if corr is None else round(corr, 4),
            "breadth_15m": round(breadth, 4), "btc_ret_15m": btc, "eth_ret_15m": eth,
            "alt_median_ret_15m": alt_med,
            "btc_lead_15m": (None if btc is None or alt_med is None
                             else round(btc - alt_med, 6)),
            "rets_15m": rets, "rank": rank,
        })
    except Exception:
        return out
    return out


def corr_regime(snap: dict | None = None) -> str | None:
    """'high' (one-factor market) | 'mid' | 'low' (idiosyncratic) | None (unknown, not a guess).
    Cut points env-tunable (MARKET_CORR_HIGH/LOW) — crude on purpose, like liquidity_regime."""
    s = snap or snapshot()
    c = s.get("corr_top20")
    if c is None:
        return None
    if c >= _f("MARKET_CORR_HIGH", 0.65):
        return "high"
    if c <= _f("MARKET_CORR_LOW", 0.35):
        return "low"
    return "mid"


def conditioners() -> dict:
    """ev_* conditioner fields for the entry vector (measurement, always on). Honest Nones."""
    s = snapshot()
    return {
        "ev_corr_regime": corr_regime(s),
        "ev_corr_top20": s.get("corr_top20"),
        "ev_breadth_15m": s.get("breadth_15m"),
        "ev_btc_lead_15m": s.get("btc_lead_15m"),
        "ev_alt_median_ret_15m": s.get("alt_median_ret_15m"),
    }


# ── the measured direction sources ────────────────────────────────────────────────────
def readings(symbol: str, *, segment: str = "futures", regime: str | None = None,
             record: bool = True) -> list[tuple[str, float]]:
    """Cross-symbol readings for `symbol` → [(source, p_up)], each recorded to the ledger.
    Emits at most one spillover reading (large XOR seesaw — disjoint by cap rank) plus the
    breadth tilt when breadth is extreme. Never raises."""
    if not _flag("MARKET_STATE_SOURCE"):
        return []
    out: list[tuple[str, float]] = []
    try:
        s = snapshot()
        if not s.get("available"):
            return []
        sym = _flat(symbol)
        lead_min = _f("SPILLOVER_LEAD_MIN", 0.0025)       # leader must move ≥25bp in 15m
        scale = _f("SPILLOVER_SCALE", 0.01)               # tanh scale: 1% gap → strong lean
        if sym not in _LEADERS:
            # the reference leader move: BTC, or ETH when BTC is quiet but ETH moved
            btc, eth = s.get("btc_ret_15m"), s.get("eth_ret_15m")
            lead = btc if btc is not None and (eth is None or abs(btc) >= abs(eth)) else eth
            if lead is not None and abs(lead) >= lead_min:
                own = (s.get("rets_15m") or {}).get(sym)
                rank = (s.get("rank") or {}).get(sym)
                if rank is not None and rank < _TOP_CORR:
                    # large-cap follower: copy the part of the leader move it hasn't priced yet
                    gap = lead - (own or 0.0)
                    if abs(gap) >= lead_min / 2:
                        p = 0.5 + 0.35 * math.tanh(gap / scale)
                        out.append(("spillover_large", min(0.98, max(0.02, round(p, 4)))))
                elif rank is not None:
                    # small-cap follower: the documented seesaw — large-cap returns NEGATIVELY
                    # predict small-cap next-period returns
                    p = 0.5 - 0.35 * math.tanh(lead / scale)
                    out.append(("spillover_seesaw", min(0.98, max(0.02, round(p, 4)))))
        b = s.get("breadth_15m")
        hi, lo = _f("BREADTH_EXTREME_HI", 0.75), _f("BREADTH_EXTREME_LO", 0.25)
        if b is not None and (b >= hi or b <= lo):        # trend day → continuation lean
            p = 0.5 + 0.3 * (b - 0.5) * 2.0
            out.append(("breadth_tilt", min(0.98, max(0.02, round(p, 4)))))
        if record and out:
            try:
                from trading.direction import truth_ledger as _tl
                for src, p in out:
                    _tl.record(symbol=symbol, market="CRYPTO", segment=segment or "futures",
                               direction=("LONG" if p >= 0.5 else "SHORT"), source=src,
                               confidence=(p if p >= 0.5 else 1.0 - p), regime=regime)
            except Exception:
                pass
    except Exception:
        return out
    return out


def status() -> dict:
    """Honest snapshot for the dashboard/verify."""
    s = snapshot()
    return {"enabled": _flag("MARKET_STATE_SOURCE"), "available": s.get("available", False),
            "corr_top20": s.get("corr_top20"), "corr_regime": corr_regime(s),
            "breadth_15m": s.get("breadth_15m"), "btc_lead_15m": s.get("btc_lead_15m"),
            "n_symbols": s.get("n_symbols"), "age_s": round(time.time() - (s.get("ts") or 0), 1)}
