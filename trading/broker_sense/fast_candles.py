"""trading/broker_sense/fast_candles.py — direction from OHLCV DATA, not chart screenshots.

The funnel's LOOK stage read direction by screenshotting candle charts × timeframes and running a
CNN — accurate but slow (the browser render dominated the cycle). This reads the SAME candles as
raw OHLCV via the fast API (reusing data_failsafe.ohlcv → ccxt/Freqtrade) and computes direction
directly with plain indicators (EMA cross + RSI + momentum). No browser, no screenshots, no CNN →
the whole cycle fits the budget. Same output shape as ChartVision.read so it's a drop-in.

Honest: this is a transparent momentum/trend read of the real candles — not a black box; and it
returns 'unavailable' (never a fake number) when the data can't be fetched."""
from __future__ import annotations

import time

from trading.broker_sense import data_failsafe

_BARS = 50


def _ema(vals: list[float], n: int) -> float:
    if not vals:
        return 0.0
    k = 2.0 / (n + 1)
    e = vals[0]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
    return e


def _rsi(closes: list[float], n: int = 14) -> float:
    if len(closes) <= n:
        return 50.0
    gains = losses = 0.0
    for i in range(-n, 0):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    if losses == 0:
        return 100.0
    rs = (gains / n) / (losses / n)
    return 100.0 - 100.0 / (1.0 + rs)


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def direction_from_ohlcv(rows: list) -> dict:
    """Compute p_up ∈ [0,1] + direction from raw candles: EMA(9)vs(21) trend + RSI + momentum."""
    try:
        closes = [float(r[4]) for r in rows if r and len(r) >= 5]
    except (TypeError, ValueError):
        closes = []
    if len(closes) < 15:
        return {"p_up": 0.5, "direction": "neutral", "source": "unavailable"}
    ema_f, ema_s = _ema(closes[-30:], 9), _ema(closes[-30:], 21)
    rsi_v = _rsi(closes, 14)
    base = closes[-6] if len(closes) >= 6 and closes[-6] else closes[0]
    mom = (closes[-1] - base) / base if base else 0.0
    score = 0.5
    score += 0.16 if ema_f > ema_s else -0.16          # trend
    score += 0.10 * _clamp(mom * 12.0, -1.0, 1.0)      # momentum
    score += 0.12 * _clamp((rsi_v - 50.0) / 50.0, -1.0, 1.0)   # RSI bias
    p_up = round(_clamp(score, 0.02, 0.98), 4)
    direction = "long" if p_up > 0.55 else "short" if p_up < 0.45 else "neutral"
    return {"p_up": p_up, "direction": direction, "source": "fast:ohlcv"}


_UNAVAIL = {"p_up": 0.5, "direction": "neutral", "source": "unavailable", "chart_source": "none"}
_MAX_TFS = 3                                     # direction needs a few TFs, not all — keep it fast


def _ohlcv_fast(sym: str, market: str, tf: str) -> list | None:
    """Candles the FAST way: ccxt fetch_ohlcv on the cached exchange (~200ms) — skips the slow
    Freqtrade-REST-first path in data_failsafe. Falls back to data_failsafe only if ccxt fails."""
    if market == "crypto":
        try:
            from trading.broker_sense.app_school import _ccxt_exchange
            ex = _ccxt_exchange("futures" if ":" in sym else "spot")
            rows = ex.fetch_ohlcv(sym, timeframe=tf, limit=_BARS)
            if rows:
                return rows
        except Exception:
            pass
    try:
        return data_failsafe.ohlcv(sym, market, timeframe=tf, limit=_BARS)
    except Exception:
        return None


def read(picks: list[dict], market: str, timeframes=("5m", "15m", "1h"),
         deadline: float | None = None) -> dict[str, dict[str, dict]]:
    """Per pick × timeframe: fetch OHLCV (fast API) → direction. Same shape as ChartVision.read.
    Fetches run in PARALLEL (I/O-bound) so the whole LOOK stage is ~2-3s, not ~25s; bounded by
    `deadline` (time.monotonic) so it never overruns the budget."""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FTimeout, as_completed
    tfs = tuple(timeframes)[:_MAX_TFS]
    jobs = [(p["symbol"], tf) for p in picks for tf in tfs]
    # PRE-FILL unavailable: any job that doesn't finish by the deadline keeps this honest default,
    # so a hung/slow fetch never leaves a hole (and never blocks the cycle — see below).
    out: dict[str, dict[str, dict]] = {p["symbol"]: {tf: dict(_UNAVAIL) for tf in tfs}
                                       for p in picks}
    if not jobs or (deadline is not None and time.monotonic() > deadline):
        return out

    def _one(job):
        sym, tf = job
        if deadline is not None and time.monotonic() > deadline:   # queued past budget → skip fetch
            return sym, tf, dict(_UNAVAIL)
        rows = _ohlcv_fast(sym, market, tf)     # ccxt direct (fast); data_failsafe as fallback
        if not rows:
            return sym, tf, dict(_UNAVAIL)
        res = direction_from_ohlcv(rows)
        res["chart_source"] = "fast:ohlcv"
        return sym, tf, res

    # HARD wall-clock bound: collect via as_completed with the remaining budget, then shut the pool
    # down WITHOUT waiting. A rate-limited venue makes individual ccxt/data_failsafe fetches take
    # seconds with no timeout; pool.map + the context-manager's wait-shutdown used to block on the
    # slowest straggler and blew the LOOK stage to 400-540s, starving VERIFY/fusion → no fusion
    # claims, no entries. Now unfinished jobs simply keep their pre-filled UNAVAIL. (2026-07-12)
    pool = ThreadPoolExecutor(max_workers=min(12, len(jobs)))
    try:
        futs = [pool.submit(_one, job) for job in jobs]
        remaining = None if deadline is None else max(0.05, deadline - time.monotonic())
        try:
            for fut in as_completed(futs, timeout=remaining):
                try:
                    sym, tf, res = fut.result()
                    out[sym][tf] = res
                except Exception:
                    pass
        except _FTimeout:
            pass                                # budget hit — stragglers keep their UNAVAIL default
    finally:
        pool.shutdown(wait=False, cancel_futures=True)   # never block the cycle on a hung fetch
    return out
