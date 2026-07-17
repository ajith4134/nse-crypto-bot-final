"""trading/broker_sense/volume_profile.py — Volume Profile / Value Area engine.

Implements the "world-champion" auction strategy the owner uploaded (2026-07-11 video,
research/video/champions-chart-strategy/understanding.md) as reusable features + rules, for
EVERY symbol and segment the brain opens (crypto/NSE/MCX/…):

  1. Volume Profile — volume-at-price histogram; Point of Control (POC = max-volume price) and
     the 70% Value Area (VAH/VAL) via the standard market-profile expansion.
  2. Value-area migration — POC/VAH/VAL shift session-over-session ("building higher" = buyers
     in control → bullish bias). Session = one DAY per segment (owner's choice): UTC day for
     24/7 crypto, the IST trading day for NSE/MCX.
  3. Failed-auction signal — price exits the value area then CLOSES BACK INSIDE with a volume
     pickup ⇒ the auction failed ⇒ reversion trade (long if it failed below, short if above).
  4. Absorption — declining volume on a directional move + an outsized-volume candle ⇒ the move
     isn't funded (sellers/buyers can't push through) — confirms the failed auction.

Pure-numpy, CPU-cheap, no new heavy deps. Honest by construction: every function degrades to a
neutral/empty result when candles are insufficient — never fabricates a level.
"""
from __future__ import annotations

# IST offset (seconds) for the NSE/MCX "daily session" boundary.
_IST_OFFSET = 5 * 3600 + 30 * 60
VA_PCT = 0.70                    # fraction of volume that defines the Value Area (market-profile std)
_MIN_BARS = 20


def _ms(ts) -> int:
    """Normalize a candle timestamp to milliseconds (accepts s or ms)."""
    ts = int(ts)
    return ts if ts > 1_000_000_000_000 else ts * 1000


def session_key(ts, market: str = "crypto") -> int:
    """Integer day-bucket for the segment (owner's 'daily session' for every symbol/segment).

    crypto (24/7) → UTC calendar day. NSE/MCX/equities → IST calendar day (UTC+5:30), so an
    Indian trading day maps to one session even though it spans two UTC dates in the evening."""
    sec = _ms(ts) // 1000
    if market and market != "crypto":
        sec += _IST_OFFSET
    return sec // 86400


def volume_profile(rows: list, bins: int = 0, *, min_bars: int = _MIN_BARS) -> dict:
    """Volume-at-price histogram + POC + 70% Value Area over `rows` (OHLCV [ts,o,h,l,c,v]).

    Each candle's volume is spread across the price bins its high–low range spans (TPO-style),
    so wide bars fund the whole range they traded, not just the close. Returns {available,
    poc, vah, val, va_pct, price_lo, price_hi, bin_size, hist:[(mid_price, volume)]}.
    `min_bars` relaxes the bar floor for short anchored windows (opening range = 15 one-minute
    bars); the default keeps every existing caller's behavior."""
    import numpy as np
    if not rows or len(rows) < min_bars:
        return {"available": False}
    a = np.asarray([[float(r[2]), float(r[3]), float(r[4]),
                     float(r[5]) if len(r) > 5 else 0.0] for r in rows], dtype="float64")
    highs, lows, vols = a[:, 0], a[:, 1], a[:, 3]
    lo, hi = float(lows.min()), float(highs.max())
    if hi <= lo or vols.sum() <= 0:
        return {"available": False}
    n = bins or max(10, min(60, len(rows) // 2))     # ~2 bars/bin, clamped
    edges = np.linspace(lo, hi, n + 1)
    bin_size = (hi - lo) / n
    hist = np.zeros(n, dtype="float64")
    for h, l, v in zip(highs, lows, vols):
        if v <= 0:
            continue
        lo_i = int(np.clip((l - lo) / bin_size, 0, n - 1))
        hi_i = int(np.clip((h - lo) / bin_size, 0, n - 1))
        span = hi_i - lo_i + 1
        hist[lo_i:hi_i + 1] += v / span              # spread volume across the bars' range
    total = hist.sum()
    if total <= 0:
        return {"available": False}
    poc_i = int(hist.argmax())
    # value area: grow outward from the POC, always taking the heavier adjacent side, to 70%
    lo_i = hi_i = poc_i
    acc = hist[poc_i]
    target = VA_PCT * total
    while acc < target and (lo_i > 0 or hi_i < n - 1):
        up = hist[hi_i + 1] if hi_i < n - 1 else -1.0
        dn = hist[lo_i - 1] if lo_i > 0 else -1.0
        if up >= dn:
            hi_i += 1
            acc += hist[hi_i]
        else:
            lo_i -= 1
            acc += hist[lo_i]
    mids = edges[:-1] + bin_size / 2.0
    return {
        "available": True,
        "poc": round(float(mids[poc_i]), 8),
        "vah": round(float(edges[hi_i + 1]), 8),
        "val": round(float(edges[lo_i]), 8),
        "va_pct": round(float(acc / total), 4),
        "price_lo": round(lo, 8), "price_hi": round(hi, 8),
        "bin_size": round(bin_size, 8),
        "hist": [(round(float(m), 8), round(float(v), 6)) for m, v in zip(mids, hist)],
    }


def session_profiles(rows: list, market: str = "crypto", max_sessions: int = 6) -> list[dict]:
    """Per-session (daily) value areas, oldest→newest, for migration analysis."""
    if not rows:
        return []
    groups: dict[int, list] = {}
    for r in rows:
        groups.setdefault(session_key(r[0], market), []).append(r)
    out = []
    for key in sorted(groups)[-max_sessions:]:
        vp = volume_profile(groups[key])
        if vp.get("available"):
            out.append({"session": key, "poc": vp["poc"], "vah": vp["vah"], "val": vp["val"]})
    return out


def value_migration(rows: list, market: str = "crypto") -> dict:
    """Are the daily value areas building higher (bullish) or lower (bearish) session-over-session?
    Returns {bias:'bullish'|'bearish'|'neutral', slope, n_sessions, detail}."""
    profs = session_profiles(rows, market)
    if len(profs) < 2:
        return {"bias": "neutral", "slope": 0.0, "n_sessions": len(profs),
                "detail": "insufficient sessions"}
    pocs = [p["poc"] for p in profs]
    # normalized average step of the POC across sessions
    steps = [(pocs[i] - pocs[i - 1]) / (abs(pocs[i - 1]) or 1.0) for i in range(1, len(pocs))]
    slope = sum(steps) / len(steps)
    rising = all(pocs[i] >= pocs[i - 1] for i in range(1, len(pocs)))
    falling = all(pocs[i] <= pocs[i - 1] for i in range(1, len(pocs)))
    if slope > 0.0008 and rising:
        bias = "bullish"
    elif slope < -0.0008 and falling:
        bias = "bearish"
    elif slope > 0.0015:
        bias = "bullish"
    elif slope < -0.0015:
        bias = "bearish"
    else:
        bias = "neutral"
    return {"bias": bias, "slope": round(slope, 6), "n_sessions": len(profs),
            "detail": f"POC {pocs[0]:.6g}→{pocs[-1]:.6g} over {len(profs)} sessions"}


def _vol_trend(vols: list[float]) -> float:
    """Sign-normalized slope of recent volume (>0 rising, <0 declining)."""
    if len(vols) < 3:
        return 0.0
    n = len(vols)
    xs = list(range(n))
    mx = sum(xs) / n
    mv = sum(vols) / n
    denom = sum((x - mx) ** 2 for x in xs) or 1.0
    slope = sum((xs[i] - mx) * (vols[i] - mv) for i in range(n)) / denom
    return slope / (mv or 1.0)


def absorption(rows: list, lookback: int = 6) -> dict:
    """Declining volume on a directional move + an outsized-volume candle = absorption (the move
    isn't funded). Returns {absorbing, side, detail}. side='bid' (buyers absorbing a drop) or
    'ask' (sellers absorbing a rally)."""
    if not rows or len(rows) < lookback + 2:
        return {"absorbing": False, "side": None, "detail": "insufficient bars"}
    seg = rows[-lookback:]
    closes = [float(r[4]) for r in seg]
    vols = [float(r[5]) if len(r) > 5 else 0.0 for r in seg]
    price_move = closes[-1] - closes[0]
    vtrend = _vol_trend(vols)
    avg_v = (sum(vols) / len(vols)) or 1.0
    spike = vols[-1] > 1.6 * avg_v                      # a wall/absorption candle
    declining = vtrend < -0.05
    if declining and price_move < 0:                    # falling price on fading volume → bid absorb
        return {"absorbing": True, "side": "bid",
                "detail": f"down move on declining volume (vtrend {vtrend:+.2f}"
                          f"{', spike' if spike else ''})"}
    if declining and price_move > 0:                    # rising price on fading volume → ask absorb
        return {"absorbing": True, "side": "ask",
                "detail": f"up move on declining volume (vtrend {vtrend:+.2f}"
                          f"{', spike' if spike else ''})"}
    return {"absorbing": False, "side": None,
            "detail": f"vtrend {vtrend:+.2f}, move {price_move:+.6g}"}


def failed_auction(rows: list, market: str = "crypto") -> dict:
    """The video's core: price EXITED the value area then CLOSED BACK INSIDE with a volume
    pickup ⇒ the auction failed ⇒ reversion. Returns {signal:'long'|'short'|'none', strength
    ∈[0,1], vah, val, poc, absorption, detail}."""
    vp = volume_profile(rows)
    if not vp.get("available") or len(rows) < 4:
        return {"signal": "none", "strength": 0.0, "detail": "no value area", **{}}
    vah, val, poc = vp["vah"], vp["val"], vp["poc"]
    prev, cur = rows[-2], rows[-1]
    prev_c, cur_c = float(prev[4]), float(cur[4])
    prev_l, prev_h = float(prev[3]), float(prev[2])
    vols = [float(r[5]) if len(r) > 5 else 0.0 for r in rows[-6:]]
    avg_prev = (sum(vols[:-1]) / max(1, len(vols) - 1)) or 1.0
    vol_pickup = (float(cur[5]) if len(cur) > 5 else 0.0) > avg_prev     # "volume picks up"
    absorb = absorption(rows)
    inside = val <= cur_c <= vah                        # current bar closed back inside the VA
    sig, strength, detail = "none", 0.0, "inside value area"
    # A real excursion = the prior bar CLOSED beyond the value area (a wick nicking the edge is
    # not "price dipping below the value area" — that gave flat-market false fires). The wick
    # only adds strength. failed BELOW → long; failed ABOVE → short.
    if prev_c < val and inside:
        sig = "long"
        strength = 0.5 + 0.15 * vol_pickup + 0.25 * (absorb["absorbing"] and absorb["side"] == "bid") \
            + 0.1 * (prev_l < val)
        detail = f"closed below VAL {val:.6g}, back inside"
    elif prev_c > vah and inside:
        sig = "short"
        strength = 0.5 + 0.15 * vol_pickup + 0.25 * (absorb["absorbing"] and absorb["side"] == "ask") \
            + 0.1 * (prev_h > vah)
        detail = f"closed above VAH {vah:.6g}, back inside"
    return {"signal": sig, "strength": round(min(1.0, strength), 3), "vah": vah, "val": val,
            "poc": poc, "vol_pickup": vol_pickup, "absorption": absorb, "detail": detail}


def opening_range_profile(rows: list, anchor_epoch: float, minutes: int = 15,
                          *, min_bars: int = 8, bins: int = 24) -> dict:
    """Value area of the OPENING RANGE — the first `minutes` after `anchor_epoch` (a session
    open), per the owner's 2026-07-17 "first candle value" video (research/video/
    vp-first-candle-value/): profile ONLY that window, and the resulting VAH/VAL — not the raw
    range high/low — are the levels the trap/acceptance grammar plays against.

    `rows` are OHLCV(+v) bars of any timeframe covering the window (1m intended). Bars without
    volume (the in-RAM mark-price mirror) degrade to a TPO profile — every bar weighted equally,
    which is the ORIGINAL Steidlmayer market profile — and `basis` records which one was used,
    so the ledger can split edges by evidence quality. Honest {available: False} when the window
    isn't covered (anchor before data starts, or too few bars)."""
    if not rows:
        return {"available": False, "reason": "no rows"}
    a_ms = _ms(anchor_epoch if anchor_epoch > 1_000_000_000_000 else int(anchor_epoch))
    end_ms = a_ms + minutes * 60_000
    win = [r for r in rows if a_ms <= _ms(r[0]) < end_ms]
    if len(win) < min_bars:
        return {"available": False, "reason": f"window has {len(win)} bars (<{min_bars})"}
    # the window must actually START at the anchor — a fetch whose history begins mid-window
    # would profile a truncated range and hand back false levels
    if _ms(win[0][0]) - a_ms > 2 * max(60_000, (end_ms - a_ms) // max(1, len(win))):
        return {"available": False, "reason": "window not covered from anchor"}
    has_vol = any(len(r) > 5 and float(r[5]) > 0 for r in win)
    if not has_vol:                                    # TPO degrade: equal weight per bar
        win = [[r[0], r[1], r[2], r[3], r[4], 1.0] for r in win]
    vp = volume_profile(win, bins=bins, min_bars=min_bars)
    if not vp.get("available"):
        return {"available": False, "reason": "profile unavailable"}
    return {**vp, "anchor_ts": a_ms // 1000, "end_ts": end_ms // 1000,
            "n_bars": len(win), "basis": "volume" if has_vol else "tpo",
            "or_high": max(float(r[2]) for r in win),
            "or_low": min(float(r[3]) for r in win)}


def value_area_events(rows: list, va: dict, *, max_trap_bars: int = 3,
                      accept_bars: int = 2, touch_tol: float = 0.0015) -> dict:
    """The video's two-sided event grammar at the value-area edges, as a state machine over the
    bars AFTER the opening-range window (`rows`, oldest→newest, [ts,o,h,l,c(,v)]).

    TRAP (reversal): a bar CLOSES beyond VAH/VAL, then within `max_trap_bars` a bar closes back
    inside → the breakout crowd is trapped; side = against the excursion; stop = the excursion
    extreme; target = the OPPOSITE value-area edge; trail once price leaves the VA.
    ACCEPTANCE (continuation): `accept_bars` consecutive closes beyond the edge = the market
    accepts the new prices; the entry is the PULLBACK — a bar that touches the edge (within
    `touch_tol`) while still closing beyond it; stop = that bar's extreme; no fixed target
    (trail each candle per the video).

    Only an event that COMPLETES ON THE LAST BAR is reported (the caller runs once per cycle —
    a stale trigger must never open a late trade). Returns {event, side, level, stop, target,
    trail, strength, bars_out, detail}; event='' when nothing fired NOW."""
    none = {"event": "", "side": "", "detail": "no event on last bar"}
    if not rows or not va or not va.get("available"):
        return none
    vah, val = float(va["vah"]), float(va["val"])
    if vah <= val:
        return none
    # state over the walk: 0=inside, +1=closed above (excursion), +2=accepted above,
    #                                -1=closed below,             -2=accepted below
    state, bars_out = 0, 0
    exc_hi, exc_lo = vah, val                        # excursion extremes while outside
    fired: dict | None = None
    for i, r in enumerate(rows):
        c, h, l = float(r[4]), float(r[2]), float(r[3])
        last = i == len(rows) - 1
        fired = None
        if state >= 1:
            exc_hi = max(exc_hi, h)
        if state <= -1:
            exc_lo = min(exc_lo, l)
        if state == 0:
            if c > vah:
                state, bars_out, exc_hi = 1, 1, h
            elif c < val:
                state, bars_out, exc_lo = -1, 1, l
        elif state == 1:                              # excursion above VAH
            if val <= c <= vah:                       # closed back inside → buyers trapped
                if bars_out <= max_trap_bars:
                    fired = {"event": "trap", "side": "short", "level": vah,
                             "stop": exc_hi, "target": val, "trail": "beyond_va",
                             "bars_out": bars_out,
                             "detail": f"trapped above VAH {vah:.6g} after {bars_out} bar(s)"}
                state, bars_out = 0, 0
            elif c < val:                             # blew straight through → flip excursion
                state, bars_out, exc_lo = -1, 1, l
            else:
                bars_out += 1
                if bars_out >= accept_bars:
                    state = 2
        elif state == -1:                             # excursion below VAL (mirror)
            if val <= c <= vah:
                if bars_out <= max_trap_bars:
                    fired = {"event": "trap", "side": "long", "level": val,
                             "stop": exc_lo, "target": vah, "trail": "beyond_va",
                             "bars_out": bars_out,
                             "detail": f"trapped below VAL {val:.6g} after {bars_out} bar(s)"}
                state, bars_out = 0, 0
            elif c > vah:
                state, bars_out, exc_hi = 1, 1, h
            else:
                bars_out += 1
                if bars_out >= accept_bars:
                    state = -2
        elif state == 2:                              # accepted above → wait for the pullback
            if c < val:
                state, bars_out, exc_lo = -1, 1, l
            elif c < vah:                             # acceptance failed (late trap = no play)
                state, bars_out = 0, 0
            elif l <= vah * (1.0 + touch_tol):        # pullback touched VAH, closed above → go
                fired = {"event": "accept_pullback", "side": "long", "level": vah,
                         "stop": l, "target": None, "trail": "candle_low",
                         "bars_out": bars_out,
                         "detail": f"acceptance above VAH {vah:.6g}, pullback touched"}
                state, bars_out = 0, 0                # one entry per acceptance
        elif state == -2:                             # accepted below (mirror)
            if c > vah:
                state, bars_out, exc_hi = 1, 1, h
            elif c > val:
                state, bars_out = 0, 0
            elif h >= val * (1.0 - touch_tol):
                fired = {"event": "accept_pullback", "side": "short", "level": val,
                         "stop": h, "target": None, "trail": "candle_high",
                         "bars_out": bars_out,
                         "detail": f"acceptance below VAL {val:.6g}, pullback touched"}
                state, bars_out = 0, 0
        if fired and last:
            depth = abs(fired["stop"] - fired["level"]) / ((vah - val) or 1.0)
            fired["strength"] = round(min(1.0, 0.55 + 0.25 * min(1.0, depth)), 3)
            return fired
    return none


def order_plan(rows: list, direction: str, market: str = "crypto",
               swing: int = 10) -> dict | None:
    """After-entry management (the video's rule): target the value-area edge, stop beyond the
    recent swing. Long → target VAH (and beyond), stop below the swing low; short → target VAL,
    stop above the swing high. Returns {entry, target, stop, rr, basis} or None when there is no
    value area / neutral direction. The exec layer uses this in place of the ATR barrier when a
    failed-auction is the driver, so risk is defined by structure, not a fixed multiple."""
    if direction not in ("long", "short") or not rows or len(rows) < _MIN_BARS:
        return None
    vp = volume_profile(rows)
    if not vp.get("available"):
        return None
    entry = float(rows[-1][4])
    seg = rows[-swing:]
    swing_low = min(float(r[3]) for r in seg)
    swing_high = max(float(r[2]) for r in seg)
    if direction == "long":
        target, stop = vp["vah"], min(swing_low, vp["val"])
    else:
        target, stop = vp["val"], max(swing_high, vp["vah"])
    risk = abs(entry - stop)
    reward = abs(target - entry)
    rr = round(reward / risk, 2) if risk > 0 else None
    return {"entry": round(entry, 8), "target": round(target, 8), "stop": round(stop, 8),
            "rr": rr, "poc": vp["poc"], "basis": "volume_profile_value_area"}


def features(rows: list, market: str = "crypto") -> dict:
    """One aggregate VP/VA feature object for indicator_fusion + the decision snapshot.

    Emits a BOUNDED directional tilt∈[-1,1] (POC position + value migration + failed auction)
    for the fusion to nudge with, plus the raw levels/signals for the snapshot and the equation.
    Neutral + available=False when candles are insufficient (honest degrade)."""
    vp = volume_profile(rows)
    if not vp.get("available"):
        return {"available": False, "tilt": 0.0}
    close = float(rows[-1][4])
    vah, val, poc = vp["vah"], vp["val"], vp["poc"]
    span = (vah - val) or (vp["bin_size"] or 1.0)
    pos = (close - poc) / (span or 1.0)                 # where price sits vs the value area
    mig = value_migration(rows, market)
    fa = failed_auction(rows, market)
    # tilt: value-migration bias + failed-auction reversion (dominant) + mild POC-reversion
    tilt = 0.0
    tilt += {"bullish": 0.35, "bearish": -0.35}.get(mig["bias"], 0.0)
    if fa["signal"] == "long":
        tilt += 0.5 * fa["strength"]
    elif fa["signal"] == "short":
        tilt -= 0.5 * fa["strength"]
    tilt += -0.15 * max(-1.0, min(1.0, pos))            # price far above value → mild fade
    tilt = max(-1.0, min(1.0, tilt))
    zone = "above_value" if close > vah else "below_value" if close < val else "in_value"
    return {
        "available": True, "tilt": round(tilt, 4),
        "poc": poc, "vah": vah, "val": val, "va_pct": vp["va_pct"], "zone": zone,
        "pos_vs_poc": round(pos, 4), "migration": mig, "failed_auction": fa,
    }
