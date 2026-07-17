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
        closes_all: dict[str, list[float]] = {}
        for r in movers:
            s = r["symbol"]
            bars = m.candles(s, 300, _CORR_BARS + 1)
            closes = [float(b[4]) for b in bars]
            closes_all[s] = closes
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
        # E12 (routes 7/10): 1h + 4h return cross-sections off the SAME candle fetch
        rets_1h: dict[str, float] = {}
        rets_4h: dict[str, float] = {}
        for s, closes in closes_all.items():
            r1 = _ret(closes, 12)
            r4 = _ret(closes, _CORR_BARS)
            if r1 is not None:
                rets_1h[s] = r1
            if r4 is not None:
                rets_4h[s] = r4
        alt4 = sorted(v for s, v in rets_4h.items() if s not in _LEADERS)
        alt_med_4h = alt4[len(alt4) // 2] if alt4 else None
        out.update({
            "available": True, "corr_top20": None if corr is None else round(corr, 4),
            "breadth_15m": round(breadth, 4), "btc_ret_15m": btc, "eth_ret_15m": eth,
            "alt_median_ret_15m": alt_med,
            "btc_lead_15m": (None if btc is None or alt_med is None
                             else round(btc - alt_med, 6)),
            "rets_15m": rets, "rank": rank,
            "rets_1h": rets_1h, "rets_4h": rets_4h,
            "btc_ret_4h": rets_4h.get("BTCUSDT"), "alt_median_ret_4h": alt_med_4h,
            "closes": closes_all,
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


# ── E12: the lead-lag / cointegration graph (learning cadence, state-file output) ─────
_GRAPH_FILE = "market_graph.json"
_GRAPH_LAST = [0.0]


def build_graph(force: bool = False) -> dict | None:
    """Routes 5+6 (catalog): estimate the leader→follower LAG edges and the cointegrated
    pairs over the mirror universe, on the learning cadence (MARKET_GRAPH_EVERY_S, 1800).

    Edges (route 5): for each non-leader in the top-60, the best |lagged corr| ≥ 0.25
    against a top-10 leader at lag 1..3 bars (5m), kept only when the two HALVES of the
    window agree on the sign (a crude stability gate — an unstable edge is noise).
    Pairs (route 6): among the top-30, 5m-return corr ≥ 0.8 → OLS hedge ratio over log
    prices; kept when the spread's lag-1 autocorr < 0.97 (mean-reverting-ish, the light
    stand-in for a full ADF — honest label 'coint_lite'). Output → market_graph.json."""
    every = _f("MARKET_GRAPH_EVERY_S", 1800)
    if not force and time.time() - _GRAPH_LAST[0] < every:
        return None
    _GRAPH_LAST[0] = time.time()
    try:
        import numpy as np
        s = snapshot()
        closes = s.get("closes") or {}
        rank = s.get("rank") or {}
        if len(closes) < 20:
            return {"available": False, "reason": "cold mirror"}
        rets = {sym: np.diff(np.asarray(c, dtype="float64")) / np.asarray(c[:-1])
                for sym, c in closes.items() if len(c) >= _CORR_BARS and min(c) > 0}
        leaders = [sym for sym, i in sorted(rank.items(), key=lambda kv: kv[1])[:10]
                   if sym in rets]
        edges: dict[str, dict] = {}
        for sym, r in rets.items():
            if sym in leaders or rank.get(sym, 999) >= 60:
                continue
            best = None
            for ld in leaders:
                lr = rets[ld]
                n = min(len(r), len(lr))
                if n < 24:
                    continue
                for lag in (1, 2, 3):
                    a, b = lr[-n:-lag], r[-n + lag:]
                    if len(a) < 20 or a.std() <= 0 or b.std() <= 0:
                        continue
                    c_full = float(np.corrcoef(a, b)[0, 1])
                    h = len(a) // 2
                    if h < 8 or a[:h].std() <= 0 or b[:h].std() <= 0 \
                            or a[h:].std() <= 0 or b[h:].std() <= 0:
                        continue
                    c1 = float(np.corrcoef(a[:h], b[:h])[0, 1])
                    c2 = float(np.corrcoef(a[h:], b[h:])[0, 1])
                    if abs(c_full) >= 0.25 and c1 * c2 > 0 \
                            and (best is None or abs(c_full) > abs(best["corr"])):
                        best = {"leader": ld, "lag": lag, "corr": round(c_full, 4)}
            if best:
                edges[sym] = best
        pairs = []
        top30 = [sym for sym, i in sorted(rank.items(), key=lambda kv: kv[1])[:30]
                 if sym in rets]
        for i, a in enumerate(top30):
            for b in top30[i + 1:]:
                ra, rb = rets[a], rets[b]
                n = min(len(ra), len(rb))
                if n < 24 or ra[-n:].std() <= 0 or rb[-n:].std() <= 0:
                    continue
                if float(np.corrcoef(ra[-n:], rb[-n:])[0, 1]) < 0.8:
                    continue
                la = np.log(np.asarray(closes[a][-n:], dtype="float64"))
                lb = np.log(np.asarray(closes[b][-n:], dtype="float64"))
                beta = float(np.polyfit(lb, la, 1)[0])
                spread = la - beta * lb
                if spread.std() <= 0:
                    continue
                ac = float(np.corrcoef(spread[:-1], spread[1:])[0, 1])
                if ac < 0.97:                        # coint_lite: spread not a random walk
                    pairs.append({"a": a, "b": b, "beta": round(beta, 5),
                                  "mu": round(float(spread.mean()), 6),
                                  "sd": round(float(spread.std()), 6),
                                  "ac1": round(ac, 4)})
        from trading import state as _st
        out = {"ts": time.time(), "available": True,
               "edges": edges, "pairs": pairs[:20]}
        _st.save_json(_GRAPH_FILE, out)
        return {"available": True, "n_edges": len(edges), "n_pairs": len(pairs[:20])}
    except Exception as e:
        return {"available": False, "error": repr(e)}


def _graph() -> dict:
    try:
        from trading import state as _st
        g = _st.load_json(_GRAPH_FILE, {}) or {}
        if time.time() - float(g.get("ts") or 0) > 4 * _f("MARKET_GRAPH_EVERY_S", 1800):
            return {}                                # stale graph → abstain, never guess
        return g
    except Exception:
        return {}


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
        # ── E12 routes 5/6/7/10/11 (each abstains unless its trigger holds) ──────────
        if sym not in _LEADERS:
            # route 7 — dominance tilt: BTC outrunning the alt median over 4h + BTC up
            # → alts lag (short-alt lean); BTC down + dominance falling → alt-season lean.
            b4, a4 = s.get("btc_ret_4h"), s.get("alt_median_ret_4h")
            if b4 is not None and a4 is not None:
                dom = b4 - a4
                if abs(dom) >= _f("DOMINANCE_MIN", 0.005) and abs(b4) >= 0.002:
                    lean = -0.12 if (dom > 0 and b4 > 0) else (0.12 if dom < 0 else 0.0)
                    if lean:
                        out.append(("dominance_tilt", round(0.5 + lean, 4)))
            # route 10 — rank momentum: cross-sectional 1h decile, ONLY in the LOW-corr
            # (idiosyncratic) regime — in a one-factor market ranks are noise around BTC.
            if corr_regime(s) == "low":
                r1 = s.get("rets_1h") or {}
                own1 = r1.get(sym)
                if own1 is not None and len(r1) >= 30:
                    vals = sorted(r1.values())
                    dec = len(vals) // 10
                    if dec and own1 >= vals[-dec]:
                        out.append(("rank_momentum", 0.62))
                    elif dec and own1 <= vals[dec - 1]:
                        out.append(("rank_momentum", 0.38))
            # route 11 — funding divergence: a strong own-move with crowded funding while
            # the leaders are FLAT = crowd-driven pump/dump → fade candidate.
            own = (s.get("rets_15m") or {}).get(sym)
            lead_abs = max(abs(s.get("btc_ret_15m") or 0.0),
                           abs(s.get("eth_ret_15m") or 0.0))
            if own is not None and abs(own) >= _f("FUND_DIV_MOVE", 0.005) \
                    and lead_abs < lead_min:
                try:
                    from trading.broker_sense.binance_stream import get_mirror
                    fr = (get_mirror().funding(sym) or {}).get("funding_rate")
                except Exception:
                    fr = None
                thr = _f("FUND_DIV_RATE", 0.0003)
                if fr is not None and ((own > 0 and fr >= thr)
                                       or (own < 0 and fr <= -thr)):
                    out.append(("funding_divergence",
                                0.35 if own > 0 else 0.65))     # fade the crowded move
            # route 5 — lead-lag graph: this symbol's measured leader moved within its lag
            # window and the follower hasn't repriced yet → lean by the edge's sign.
            g = _graph()
            edge = (g.get("edges") or {}).get(sym)
            if edge:
                lret = (s.get("rets_15m") or {}).get(edge["leader"])
                own15 = (s.get("rets_15m") or {}).get(sym) or 0.0
                if lret is not None and abs(lret) >= lead_min \
                        and abs(own15) < abs(lret) / 2:
                    sgn = 1.0 if edge["corr"] >= 0 else -1.0
                    p = 0.5 + 0.3 * math.tanh(sgn * lret / scale)
                    out.append(("leadlag_graph", min(0.98, max(0.02, round(p, 4)))))
            # route 6 — pair spread: z-score of the coint_lite spread; |z| ≥ 2 leans this
            # leg toward reversion (direction comes from the SPREAD, not the coin).
            g = g or {}
            for pr in (g.get("pairs") or []):
                if sym not in (pr.get("a"), pr.get("b")):
                    continue
                closes = s.get("closes") or {}
                ca, cb = closes.get(pr["a"]), closes.get(pr["b"])
                if not ca or not cb or ca[-1] <= 0 or cb[-1] <= 0 or not pr.get("sd"):
                    break
                spread = math.log(ca[-1]) - pr["beta"] * math.log(cb[-1])
                z = (spread - pr["mu"]) / pr["sd"]
                if abs(z) >= _f("PAIR_Z_MIN", 2.0):
                    rich_a = z > 0                     # a rich vs b → short a / long b
                    lean_long = (not rich_a) if sym == pr["a"] else rich_a
                    p = 0.5 + (0.14 if lean_long else -0.14) * min(2.0, abs(z) - 1.0)
                    out.append(("pair_spread", min(0.98, max(0.02, round(p, 4)))))
                break
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
