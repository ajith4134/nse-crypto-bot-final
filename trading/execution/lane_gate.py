"""Lane gate — kill-criteria parity + freshness gate at the ONE entry chokepoint.

WHY (SELECTION-CRITIQUE 2026-07-17): the lens lane must survive a pre-registered verdict
(n≥100 closed, measured) but the strategy-table/filter lanes never faced one — families
running win 0.23–0.44 with negative avgP kept trading indefinitely. And the momentum
family specifically enters STALE moves (big 4h run-up, flat last hour — the measured
toxic cohort). Every entry lane goes through `CryptoEngineClient.place_order` (the
MlBridgeStrategy emits no automatic entries), so this module gates there:

  check(tag, symbol, direction, segment) -> (allowed, guard, reason)

Two independent gates, both honest and self-adjudicating:
  1. KILL (LANE_KILL=1): an enter_tag with ≥ LANE_KILL_MIN_N closed trades over the
     trailing LANE_KILL_DAYS whose total P&L is negative is RETIRED — refused with a
     recorded refusal count (lane_gate.json, dashboard-readable). Exempt tags
     (LANE_GATE_EXEMPT) protect permanent benchmarks (learned_direction_ctl — the
     mission control lane is never killed).
  2. FRESHNESS (FRESH_GATE=1): momentum-family tags (prefixes MOMENTUM_FRESH_TAGS)
     additionally require the move to still be ALIVE (inception.fresh_ok). A refusal is
     recorded as a truth-ledger claim source="freshcut" taken=False so the labeler
     scores the counterfactual — the gate proves itself with data or gets removed
     (same pattern as reflex_poscut / learned_direction_costcut).

Data: the engine's own closed trades from the freqtrade sqlite (read-only, cached
LANE_GATE_TTL_S). Missing DB / cold cache → fail-open (a blind gate never blocks).
Crypto only — this sits inside the crypto engine client (market isolation intact).
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "stats": {}}
_STATE_FILE = "lane_gate.json"


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default


def _on(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default) in ("1", "true", "TRUE", "yes", "on")


def _db_path() -> str:
    return os.environ.get("LANE_GATE_DB") or os.path.join(
        os.path.expanduser("~"), "tradesv3.dryrun.sqlite")


def _exempt() -> set:
    """Never-kill tags. REVIEW FIX 2026-07-17: the first cut exempted only the control
    lane — but the PRIMARY decision lanes (learned_direction, the live_loop router) are
    net-negative while the brain LEARNS (paper is the experiment, CONVENTIONS §15);
    killing them silently stops most trading and starves the ledger of training data.
    The kill gate exists for the PROLIFERATED strategy/filter tail, not the core.
    lens:* is exempt as a PREFIX: the lens lane has its own pre-registered verdict
    system (B3, n≥100/lens) — two independent executioners would double-judge it."""
    raw = os.environ.get(
        "LANE_GATE_EXEMPT", "learned_direction_ctl,learned_direction,live_loop")
    return {s.strip() for s in raw.split(",") if s.strip()}


def _exempt_prefixes() -> tuple:
    raw = os.environ.get("LANE_GATE_EXEMPT_PREFIX", "lens:")
    return tuple(p.strip() for p in raw.split(",") if p.strip())


def _fresh_prefixes() -> tuple:
    raw = os.environ.get("MOMENTUM_FRESH_TAGS", "filter:,mom_,breakout_,trend_")
    return tuple(p.strip() for p in raw.split(",") if p.strip())


def tag_stats(refresh: bool = False) -> dict:
    """{tag: {n, pnl, win}} over the trailing LANE_KILL_DAYS of CLOSED trades. Cached;
    empty dict on any DB trouble (fail-open)."""
    ttl = _f("LANE_GATE_TTL_S", 600.0)
    with _lock:
        if not refresh and time.monotonic() - _cache["ts"] < ttl:
            return _cache["stats"]
    stats: dict = {}
    try:
        days = _f("LANE_KILL_DAYS", 14.0)
        con = sqlite3.connect(f"file:{_db_path()}?mode=ro", uri=True, timeout=3.0)
        try:
            rows = con.execute(
                "SELECT COALESCE(enter_tag,''), COUNT(*), COALESCE(SUM(close_profit_abs),0), "
                "AVG(CASE WHEN close_profit_abs>0 THEN 1.0 ELSE 0.0 END) "
                "FROM trades WHERE is_open=0 AND close_profit_abs IS NOT NULL "
                "AND open_date >= datetime('now', ?) GROUP BY 1",
                (f"-{int(days)} days",)).fetchall()
        finally:
            con.close()
        stats = {t: {"n": int(n), "pnl": round(float(p), 2), "win": round(float(w or 0), 4)}
                 for t, n, p, w in rows if t}
    except Exception:
        stats = {}
    with _lock:
        _cache["ts"] = time.monotonic()
        _cache["stats"] = stats
    return stats


def killed(tag: str) -> tuple[bool, str]:
    """(True, reason) when `tag` has earned retirement: n ≥ LANE_KILL_MIN_N closed trades
    in the window AND total P&L < 0. Exempt tags never die."""
    if not tag or not _on("LANE_KILL"):
        return False, ""
    if tag in _exempt() or tag.startswith(_exempt_prefixes()):
        return False, ""
    st = tag_stats().get(tag)
    if not st:
        return False, ""
    min_n = int(_f("LANE_KILL_MIN_N", 100))
    # HYSTERESIS (review fix): "any negative total" retired a lane sitting at −$0.01.
    # The loss must be MATERIAL (≥ LANE_KILL_MIN_LOSS USDT over the window) so
    # break-even lanes keep trading and keep generating evidence.
    min_loss = _f("LANE_KILL_MIN_LOSS", 25.0)
    if st["n"] >= min_n and st["pnl"] <= -min_loss:
        return True, (f"lane '{tag}' retired: {st['n']} closed trades, "
                      f"{st['pnl']:+.0f} USDT, win {st['win']:.2f} over the window")
    return False, ""


def _parole(tag: str) -> bool:
    """True when the killed `tag` is due its probation entry (at most one per
    LANE_KILL_PROBATION_H hours, persisted so restarts don't reset the clock).
    0 disables parole entirely."""
    hours = _f("LANE_KILL_PROBATION_H", 6.0)
    if hours <= 0:
        return False
    now = time.time()
    granted = {"ok": False}
    try:
        from trading import state

        def _m(d: dict) -> dict:
            pl = d.setdefault("parole_ts", {})
            last = float(pl.get(tag) or 0.0)
            if now - last >= hours * 3600.0:
                pl[tag] = now
                granted["ok"] = True
            return d
        state.mutate_json(_STATE_FILE, _m, default={})
    except Exception:
        return False
    return granted["ok"]


def _range_pct_4h(symbol: str) -> float | None:
    """Realized 4h high-low range as % of last close, from the persisted RAM-mirror
    candles (readable from EVERY process, unlike the in-RAM mirror). None when the
    mirror is cold or lacks the symbol — a cold mirror must not read as a dead market."""
    try:
        from trading.broker_sense import inception
        s = str(symbol).replace("/USDT:USDT", "USDT").replace("/", "")
        bars = inception._persisted_candles(s, 300, 48)
        if len(bars) < 12:
            return None
        hi = max(b[2] for b in bars)
        lo = min(b[3] for b in bars)
        c = bars[-1][4]
        return 100.0 * (float(hi) - float(lo)) / float(c) if c else None
    except Exception:
        return None


_DV_CACHE: dict = {}                       # symbol -> (ts, median 30d dollar volume)


def _dollar_vol_30d(symbol: str) -> float | None:
    """Median daily dollar volume over the trailing ~30 daily bars, from freqtrade's own
    downloaded candles. Cached 6h (this moves slowly). None when unavailable → fail OPEN."""
    import time as _t
    hit = _DV_CACHE.get(symbol)
    if hit and _t.time() - hit[0] < 21600:
        return hit[1]
    val = None
    try:
        from pathlib import Path
        import pandas as pd
        f = (Path.home() / "trading/crypto/freqtrade/user_data/data/binance/futures" /
             f"{symbol.replace('/', '_').replace(':', '_')}-1d-futures.feather")
        if f.exists():
            df = pd.read_feather(f).tail(31)
            if len(df) >= 10:
                val = float((df["close"] * df["volume"]).median())
    except Exception:
        val = None
    _DV_CACHE[symbol] = (_t.time(), val)
    return val


_TREND_CACHE: dict = {}                    # symbol -> (ts, pct move over N days)


def _trend_pct_nd(symbol: str, days: int = 7) -> float | None:
    """% price move over the trailing `days` daily bars, from freqtrade's own candles.
    Cached 1h. None when unavailable → fail OPEN."""
    import time as _t
    key = (symbol, days)
    hit = _TREND_CACHE.get(key)
    if hit and _t.time() - hit[0] < 3600:
        return hit[1]
    val = None
    try:
        from pathlib import Path
        import pandas as pd
        f = (Path.home() / "trading/crypto/freqtrade/user_data/data/binance/futures" /
             f"{symbol.replace('/', '_').replace(':', '_')}-1d-futures.feather")
        if f.exists():
            df = pd.read_feather(f)
            if len(df) >= days + 1:
                c0 = float(df["close"].iloc[-1])
                cN = float(df["close"].iloc[-(days + 1)])
                if cN:
                    val = (c0 - cN) / cN * 100.0
    except Exception:
        val = None
    _TREND_CACHE[key] = (_t.time(), val)
    return val


def _record_refusal(kind: str, tag: str) -> None:
    try:
        from trading import state

        def _m(d: dict) -> dict:
            k = d.setdefault(kind, {})
            k[tag or "?"] = int(k.get(tag or "?") or 0) + 1
            d["ts"] = time.time()
            return d
        state.mutate_json(_STATE_FILE, _m, default={})
    except Exception:
        pass


def check(tag: str | None, symbol: str, direction: str,
          segment: str | None = None) -> tuple[bool, str, str]:
    """The chokepoint decision: (allowed, guard, reason). guard ∈ '', 'lane_kill',
    'freshness'. Never raises; every refusal is recorded."""
    t = str(tag or "")
    try:
        dead, why = killed(t)
        if dead:
            try:                                # cause-of-death ledger (idempotent per tag)
                from trading.brain import graveyard as _gy
                _st = tag_stats().get(t) or {}
                _gy.record_death(t, kind="lane", stage="lane_kill",
                                 metric=_st.get("pnl"), detail=why, market="crypto")
            except Exception:
                pass
            # PAROLE (live-verification fix 2026-07-17): a killed lane cannot trade, so
            # its record can never improve — permanent death by construction (seen live
            # the same hour: filter:momentum was retired on its OLD 24h-selection record
            # minutes after its selection logic was fixed). One probation entry per
            # LANE_KILL_PROBATION_H keeps evidence flowing at ~2% of the old trade rate,
            # so a genuinely-fixed lane climbs out and a truly-dead one stays down.
            if _parole(t):
                _record_refusal("parole", t)
                return True, "", f"parole entry for retired lane ({why})"
            _record_refusal("killed", t)
            return False, "lane_kill", why
        # STOP-CHURN COOLDOWN (2026-07-17 live catch): with the −3% backstop, lanes were
        # re-entering the SAME pair+direction seconds after a stop_loss close and re-stopping
        # inside a minute (DODOX stopped 14s after entry, re-entered twice) — each churn
        # cycle burns a full stop. Applies to EVERY tag (exempt lanes included: churn guard
        # is orthogonal to lane-kill). A direction FLIP stays allowed — it is a new claim.
        cd_min = _f("STOP_REENTRY_COOLDOWN_MIN", 30.0)
        if cd_min > 0 and symbol:
            try:
                want_short = 1 if (direction or "").upper() == "SHORT" else 0
                con = sqlite3.connect(f"file:{_db_path()}?mode=ro", uri=True, timeout=3.0)
                try:
                    row = con.execute(
                        "SELECT COUNT(*) FROM trades WHERE is_open=0 AND pair=? "
                        "AND is_short=? AND exit_reason='stop_loss' "
                        "AND close_date >= datetime('now', ?)",
                        (symbol, want_short, f"-{int(cd_min)} minutes")).fetchone()
                finally:
                    con.close()
                if row and int(row[0] or 0) > 0:
                    _record_refusal("stop_cooldown", t)
                    try:                        # counterfactual claim — labeler adjudicates
                        from trading.direction import truth_ledger as tl
                        tl.record(symbol=symbol, market="CRYPTO",
                                  segment=(segment or "futures"),
                                  direction=(direction or "LONG").upper(),
                                  source="stopcool", taken=False)
                    except Exception:
                        pass
                    return False, "stop_cooldown", (
                        f"{symbol} {direction}: stopped out within the last "
                        f"{int(cd_min)}m — re-entry blocked (flip allowed)")
            except Exception:
                pass                            # fail-open like every other guard here
        # X17 COUNTER-TREND REFUSAL (owner "do the x17" 2026-07-18) — the SECOND research
        # claim that validated on our own trades. MEASURED over 1,672 closes/36h: entries
        # ALIGNED with the symbol's own 7-day trend returned −0.58% of stake vs −1.48% for
        # entries fighting it (diff +0.91%/trade, t=2.38, holds in 4 of 5 lanes). NOTE the
        # 30-DAY version of this test showed NOTHING — horizon is the parameter, so this is
        # pinned to X17_TREND_DAYS. Per CONVENTIONS §16 (direction must be EARNED) a
        # counter-trend claim is REFUSED, never inverted. A |trend| under X17_NEUTRAL_PCT is
        # "no trend" and both sides stay allowed — forcing a side on a flat chart would be
        # fabricating direction. Counterfactual "counter7cut" adjudicates; no data fails OPEN.
        # X24: the DIP-REVERSION lane is EXEMPT from the counter-trend refusal. Measured on
        # 1.45M labelled rows: buying a big hourly drop INSIDE a 7-day downtrend is the single
        # best signal in the dataset (+0.281% fwd, +0.181% net, n=13,542) — and it is by
        # construction a counter-trend long, exactly what X17 blocks. X17 was validated
        # UNCONDITIONALLY (all entries, t=2.38); this edge is CONDITIONAL on a dip having just
        # happened. Both hold; the conditional one is where the money is, so it gets an
        # exemption rather than X17 being reverted for everyone.
        # spike_fade (2026-07-22): same exemption class — pocket B (spike in a 7d UPtrend,
        # SHORT) is a counter-trend fade measured CONDITIONALLY (+0.087%/trade with-stop).
        # wm_ (owner's window-movers direction experiment): the bandit MUST be free to try
        # both sides or its labels are censored — exempt from the counter-trend refusal.
        if t.startswith(("dip_revert", "spike_fade", "wm_")):
            ct_pct = 0.0
        else:
            ct_pct = _f("X17_COUNTER_TREND_PCT", 0.0)
        if ct_pct > 0 and symbol and direction:
            tr = _trend_pct_nd(symbol, int(_f("X17_TREND_DAYS", 7)))
            if tr is not None and abs(tr) >= _f("X17_NEUTRAL_PCT", 1.0):
                want_long = (direction or "").upper() != "SHORT"
                against = (tr > 0 and not want_long) or (tr < 0 and want_long)
                if against and abs(tr) >= ct_pct:
                    _record_refusal("counter_trend", t)
                    try:
                        from trading.direction import truth_ledger as tl
                        tl.record(symbol=symbol, market="CRYPTO",
                                  segment=(segment or "futures"),
                                  direction=(direction or "LONG").upper(),
                                  source="counter7cut", taken=False)
                    except Exception:
                        pass
                    return False, "counter_trend", (
                        f"{symbol} {direction}: fights its {int(_f('X17_TREND_DAYS', 7))}d "
                        f"trend ({tr:+.1f}%) — counter-trend entries measured −1.48%/trade "
                        f"vs −0.58% aligned")
        # X16 LIQUIDITY FLOOR (2026-07-18) — the ONE research claim that VALIDATED on our
        # own data. Measured over 1,687 closes/36h, win rate rises MONOTONICALLY with the
        # symbol's 30-day median dollar volume: Q1 .450 / Q2 .464 / Q3 .485 / Q4 .508 /
        # Q5 .555 (10.5pp spread, monotone across all five buckets — far harder to get by
        # chance than one bucket standing out). Per-trade P&L is best in Q5 (−1.53) vs Q1
        # (−2.14). Refuse entries below X16_MIN_DOLLAR_VOL_M (millions/day; our measured
        # 20th percentile was $2.5M). Counterfactual source "illiqcut" adjudicates it;
        # no data fails OPEN (a missing feather must not silently halve the universe).
        floor_m = _f("X16_MIN_DOLLAR_VOL_M", 0.0)
        if floor_m > 0 and symbol:
            dv = _dollar_vol_30d(symbol)
            if dv is not None and dv < floor_m * 1e6:
                _record_refusal("illiquid", t)
                try:
                    from trading.direction import truth_ledger as tl
                    tl.record(symbol=symbol, market="CRYPTO",
                              segment=(segment or "futures"),
                              direction=(direction or "LONG").upper(),
                              source="illiqcut", taken=False)
                except Exception:
                    pass
                return False, "illiquid", (
                    f"{symbol}: 30d median ${dv/1e6:.2f}M/day < ${floor_m:.2f}M floor")
        # X11 DEAD-MARKET FLOOR (owner "do X11" 2026-07-18): weekend/off-hours the
        # tokenized stock-perps and frozen coins ranged ~0% while entries kept opening
        # into them (measured Sat 08:00 UTC: 10% of the 877-symbol universe moved 0.00%
        # in 4h; XAU 0.13%, MU 0.43%, DELL 0.56%). A trade needs movement to clear fees —
        # refuse entries whose realized 4h range is under the floor. Every tag, BOTH
        # directions (dead is dead). Counterfactual source "deadcut" adjudicates the
        # gate; X11_MIN_RANGE_PCT=0 reverts; no-data fails OPEN (cold mirror ≠ dead).
        floor_pct = _f("X11_MIN_RANGE_PCT", 0.8)
        if floor_pct > 0 and symbol:
            rng = _range_pct_4h(symbol)
            if rng is not None and rng < floor_pct:
                _record_refusal("dead_market", t)
                try:                            # counterfactual claim — labeler scores it
                    from trading.direction import truth_ledger as tl
                    tl.record(symbol=symbol, market="CRYPTO",
                              segment=(segment or "futures"),
                              direction=(direction or "LONG").upper(),
                              source="deadcut", taken=False)
                except Exception:
                    pass
                return False, "dead_market", (
                    f"{symbol}: 4h range {rng:.2f}% < {floor_pct:.2f}% floor — "
                    "dead market (closed-hours stock-perp / frozen coin)")
        if t.startswith(_fresh_prefixes()) and _on("FRESH_GATE"):
            from trading.broker_sense import inception
            ok, why = inception.fresh_ok(symbol, direction)
            if not ok:
                _record_refusal("freshcut", t)
                try:                            # counterfactual claim — labeler scores it
                    from trading.direction import truth_ledger as tl
                    tl.record(symbol=symbol, market="CRYPTO",
                              segment=(segment or "futures"),
                              direction=(direction or "LONG").upper(),
                              source="freshcut", taken=False)
                except Exception:
                    pass
                return False, "freshness", f"{t}: {why}"
    except Exception:
        return True, "", "gate error (fail-open)"
    return True, "", ""


def status() -> dict:
    """Dashboard snapshot: live per-tag stats, currently-retired lanes, refusal counts."""
    st = tag_stats()
    dead = {}
    for t in st:
        d, why = killed(t)
        if d:
            dead[t] = why
    counters = {}
    try:
        from trading import state
        counters = state.load_json(_STATE_FILE, {}) or {}
    except Exception:
        pass
    return {"enabled": {"lane_kill": _on("LANE_KILL"), "fresh_gate": _on("FRESH_GATE"),
                        "dead_floor_pct": _f("X11_MIN_RANGE_PCT", 0.8)},
            "retired": dead, "tags": st, "refusals": counters,
            "exempt": sorted(_exempt())}
