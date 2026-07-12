"""trading/broker_sense/vision_worker.py — async deep chart-vision worker (the brain's patient eyes).

Local CPU vision (qwen2.5-vl:7b) reads a full indicator+Volume-Profile chart in ~130s — far too
slow for the live funnel's 30s budget, but PERMANENT and rate-limit-FREE. So instead of blocking
the funnel, this worker reads charts ASYNCHRONOUSLY: it walks the symbols the brain cares about
(open trades + current candidates), renders the annotated multi-TF chart, and gets a full VLM read
(cloud-fast when a free tier is up, local qwen7b when they're throttled — either way it completes),
caching the structured direction read keyed by symbol|tf|bar. `indicator_fusion.fuse()` then folds
the freshest deep read in as its vision lens — so every decision benefits from a real
indicator-chart reading without ever waiting on CPU inference in the hot path.

Honest by construction: a cache entry carries its bar timestamp + age; stale/absent reads simply
don't contribute (fuse falls back to the fast CNN vision). Never raises into the funnel.
"""
from __future__ import annotations

import os
import time

from trading import state

_CACHE_FILE = "broker_sense_vision_deep_cache.json"
_DEFAULT_TFS = ("15m", "1h", "4h")          # bias TFs — where the auction/value-area read matters
_MAX_AGE = 1800.0                           # a deep read is usable for 30 min (bar-scale)
_READ_BUDGET = 220.0                        # per-read wall-clock: lets local qwen7b finish


def _cache() -> dict:
    return state.load_json(_CACHE_FILE, {}) or {}


def _save(cache: dict) -> None:
    state.save_json(_CACHE_FILE, cache)


def _phash(path: str) -> str | None:
    """Cheap 64-bit average-hash of the rendered chart (8x8 grayscale > mean). Lets read_symbol
    skip the EXPENSIVE VLM call when the chart is visually identical to the last read
    (frame-diff gating, #5) — the vision cost is the funnel hog and unchanged charts add nothing.
    None on any failure so it can only ever fall through to a normal read, never block one."""
    try:
        from PIL import Image
        px = list(Image.open(path).convert("L").resize((8, 8)).getdata())
        avg = sum(px) / len(px)
        bits = 0
        for i, p in enumerate(px):
            if p > avg:
                bits |= (1 << i)
        return f"{bits:016x}"
    except Exception:
        return None


def cached_read(symbol: str, tf: str, *, max_age: float = _MAX_AGE) -> dict | None:
    """Freshest cached deep read for (symbol, tf), or None if absent/stale."""
    hit = _cache().get(f"{symbol}|{tf}")
    if hit and (time.time() - hit.get("ts", 0)) <= max_age:
        return hit.get("read")
    return None


def deep_vision(symbol: str, timeframes=_DEFAULT_TFS, *, max_age: float = _MAX_AGE) -> dict | None:
    """{tf: {p_up, direction, source}} for indicator_fusion.fuse()'s `vision` arg — only the TFs
    with a fresh cached deep read. None when nothing fresh (fuse then uses its own vision/CNN)."""
    out = {}
    for tf in timeframes:
        r = cached_read(symbol, tf, max_age=max_age)
        if r and r.get("direction"):
            out[tf] = {"p_up": r.get("p_up", 0.5), "direction": r["direction"], "source": "vlm_deep"}
    return out or None


def read_symbol(symbol: str, market: str = "crypto", timeframes=_DEFAULT_TFS,
                *, budget: float = _READ_BUDGET) -> dict:
    """Render + deep-read each TF for one symbol, caching structured reads. Returns a summary
    {symbol, read: {tf: {...}}, cached_writes}. Never raises."""
    from trading.broker_sense import chart_render, chart_vlm, volume_profile, data_failsafe
    cache = _cache()
    wrote = 0
    got: dict[str, dict] = {}
    for tf in timeframes:
        try:
            rows = data_failsafe.ohlcv(symbol, market, timeframe=tf, limit=chart_render.ANNOT_BARS)
            if not rows:
                continue
            bar_ts = int(rows[-1][0])
            key = f"{symbol}|{tf}"
            prev = cache.get(key)
            if prev and prev.get("bar_ts") == bar_ts:        # same bar already read → skip (cheap)
                got[tf] = prev.get("read")
                continue
            path = chart_render.annotated(rows, symbol, tf)
            if not path:
                continue
            # FRAME-DIFF GATE (#5): if the freshly-rendered chart is pixel-identical to the last
            # read (e.g. a new bar that barely moved), reuse the cached VLM read instead of paying
            # for another qwen2.5-vl pass. VISION_PHASH_GATE=0 disables.
            ph = _phash(path)
            if ph and prev and prev.get("phash") == ph and prev.get("read") \
                    and os.environ.get("VISION_PHASH_GATE", "1") not in ("0", "false", "False"):
                got[tf] = prev["read"]
                cache[key] = {**prev, "ts": time.time(), "bar_ts": bar_ts}
                wrote += 1
                try:
                    os.remove(path)
                except OSError:
                    pass
                continue
            ctx = None
            try:
                vpf = volume_profile.features(rows, market)
                if vpf.get("available"):
                    fa = vpf["failed_auction"]
                    ctx = (f"POC={vpf['poc']} VAH={vpf['vah']} VAL={vpf['val']} zone={vpf['zone']} "
                           f"migration={vpf['migration']['bias']} failed_auction={fa['signal']}")
            except Exception:
                ctx = None
            try:
                read = chart_vlm.read_chart(path, symbol, tf, context=ctx,
                                            timeout=int(budget), total_timeout=budget)
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass
            if read:
                cache[key] = {"ts": time.time(), "bar_ts": bar_ts, "phash": ph, "read": read}
                got[tf] = read
                wrote += 1
        except Exception:
            continue
    if wrote:
        _save(cache)
    return {"symbol": symbol, "read": got, "cached_writes": wrote}


def _target_symbols(limit: int = 12) -> list[tuple[str, str]]:
    """Symbols worth a deep read: OPEN trades first, then current top candidates. Returns
    (symbol, market) pairs. Best-effort from state; empty when nothing is active."""
    seen: set = set()
    out: list[tuple[str, str]] = []

    def _add(sym, market):
        if sym and sym not in seen:
            seen.add(sym)
            out.append((sym, market))

    try:                                                     # open trades (crypto + nse)
        for t in (state.load_json("open_trades.json", []) or []):
            _add(t.get("symbol") or t.get("pair"), t.get("market", "crypto"))
    except Exception:
        pass
    try:                                                     # current candidates the funnel shortlisted
        cands = state.load_json("broker_sense_candidates.json", {}) or {}
        for market, lst in (cands.items() if isinstance(cands, dict) else []):
            for c in (lst or [])[:limit]:
                _add((c.get("symbol") if isinstance(c, dict) else c), market)
    except Exception:
        pass
    return out[:limit]


def run_once(limit: int = 8) -> dict:
    """One pass over the target symbols. Returns {symbols, reads_written}."""
    targets = _target_symbols(limit)
    written = 0
    for sym, market in targets:
        written += read_symbol(sym, market).get("cached_writes", 0)
    return {"symbols": len(targets), "reads_written": written}


def loop(interval: float = 120.0, limit: int = 8) -> None:
    """Continuous deep-read daemon (run as its own process — CPU-heavy, decoupled from the funnel).
    Kill-switch: VISION_WORKER=0."""
    while os.getenv("VISION_WORKER", "1").strip().lower() not in ("0", "false", "off"):
        try:
            run_once(limit)
        except Exception:
            pass
        time.sleep(max(10.0, interval))


if __name__ == "__main__":               # standalone daemon entrypoint (separate process)
    loop()
