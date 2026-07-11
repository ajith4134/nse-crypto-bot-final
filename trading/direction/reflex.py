"""trading/direction/reflex.py — R2: the Reflex fast lane (Pillars 27 + 9).

Armed pullback entries (D3) used to wait for a poll: the sweeper sampled prices every
PULLBACK_SWEEP_SEC (45s) from quote/feather sources that UI-only mode often Nones.
This lane subscribes to Binance's PUBLIC bookTicker websocket (keyless, zero-cost,
no REST weight) for exactly the symbols currently armed — one watcher per venue
(futures + spot) — and fires the existing sweep-and-enter path the moment a tick
crosses a row's retrace or runaway line: signal→order in seconds. The decision stays
with the SAME pullback state machine: `pullback.sweep` pops rows under the
cross-process state lock, so the reflex lane, the polling fallback, and the in-cycle
sweep can never double-enter one row.

Honest observability: reflex_lane.json carries per-venue connection state, subscribed
streams, tick counts, triggers fired, and tick→order latency — surfaced through
pullback.status() (Direction panel). Misses stay honest: no websocket stack → the
caller's polling loop still sweeps; a dropped connection degrades to polling-cadence
sweeps for that venue until the stream is back.

Levers: REFLEX_LANE=1 (0 → polling only), REFLEX_RESYNC_S (5, armed-set refresh),
PULLBACK_SWEEP_SEC (45, offline fallback cadence inside this loop too).
"""
from __future__ import annotations

import json
import os
import time

from trading import state

_STATE = "reflex_lane.json"
_WS_URL = {"spot": "wss://stream.binance.com:9443/stream?streams=",
           "fut": "wss://fstream.binance.com/stream?streams="}


def enabled() -> bool:
    return os.environ.get("REFLEX_LANE", "1") in ("1", "true", "TRUE", "yes", "on")


def _env_f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _venue_sym(row: dict) -> tuple[str, str]:
    """Armed row → (venue, ws symbol). 'ADA/USDT:USDT' → ('fut', 'ADAUSDT');
    'ADA/USDT' → ('spot', 'ADAUSDT')."""
    sym = str(row.get("symbol") or "")
    flat = sym.split(":")[0].replace("/", "").upper()
    return ("fut" if ":" in sym else "spot"), flat


def crossed(row: dict, mid: float) -> str | None:
    """Cheap wake-up filter on one tick: 'trigger' / 'runaway' / None. The
    authoritative decision is still pullback.sweep (same math, under the lock)."""
    try:
        from trading.direction.pullback import _dist
        ref = float(row["ref_price"])
        d = _dist(row)
        run_mult = _env_f("PULLBACK_RUNAWAY_ATR", 1.5)
        if row.get("direction") == "LONG":
            if mid <= ref - d:
                return "trigger"
            if mid >= ref + run_mult * d:
                return "runaway"
        else:
            if mid >= ref + d:
                return "trigger"
            if mid <= ref - run_mult * d:
                return "runaway"
    except Exception:
        return None
    return None


def _armed_maps() -> tuple[dict, dict]:
    """Current armed rows → ({(venue, WSSYM): [row, ...]}, {venue: {stream, ...}})."""
    rows = (state.load_json("direction_pullback.json", {}) or {}).get("armed") or {}
    by_key: dict = {}
    streams: dict = {"spot": set(), "fut": set()}
    for row in rows.values():
        if row.get("segment") not in ("futures", "spot"):
            continue
        venue, ws = _venue_sym(row)
        by_key.setdefault((venue, ws), []).append(row)
        streams[venue].add(f"{ws.lower()}@bookTicker")
    return by_key, streams


class _Stats:
    """Shared, flushed-to-state counters (single event loop → no locking needed)."""

    def __init__(self) -> None:
        self.venues: dict = {"fut": {"connected": False, "streams": []},
                             "spot": {"connected": False, "streams": []}}
        self.ticks = 0
        self.triggers = 0
        self.entered_total = 0
        self.last_latency_ms: float | None = None
        self.reconnects = 0
        self._last_flush = 0.0

    def flush(self, force: bool = False, **extra) -> None:
        if not force and time.monotonic() - self._last_flush < 10:
            return
        self._last_flush = time.monotonic()
        try:
            state.save_json(_STATE, {"enabled": enabled(), "venues": self.venues,
                                     "ticks": self.ticks, "triggers": self.triggers,
                                     "entered_total": self.entered_total,
                                     "last_latency_ms": self.last_latency_ms,
                                     "reconnects": self.reconnects,
                                     "ts": time.time(), **extra})
        except Exception:
            pass


def run(executor_for, *, allow_live: bool = False) -> None:
    """Blocking reflex loop (call from the sweeper thread). Returns only when
    REFLEX_LANE is off or the websocket stack is unavailable — the caller then
    falls back to polling. Never raises out."""
    try:
        import asyncio

        import websockets
    except Exception as e:                        # no ws stack → polling fallback
        state.save_json(_STATE, {"enabled": False,
                                 "error": f"websockets unavailable: {e}"[:200],
                                 "ts": time.time()})
        return
    if not enabled():
        state.save_json(_STATE, {"enabled": False, "error": "REFLEX_LANE=0",
                                 "ts": time.time()})
        return

    stats = _Stats()

    def _fire(venue: str, ws_sym: str, mid: float, t_tick: float) -> None:
        """One crossing tick → sweep exactly the matching segment at this price."""
        by_key, _ = _armed_maps()
        hits = [r for r in (by_key.get((venue, ws_sym)) or []) if crossed(r, mid)]
        if not hits:
            return
        stats.triggers += 1
        for seg in sorted({r.get("segment") or "futures" for r in hits}):
            try:
                syms = {r["symbol"] for r in hits
                        if (r.get("segment") or "futures") == seg}

                def _pf(s, _syms=syms, _mid=mid):
                    return _mid if s in _syms else None   # others keep their own price path
                r = executor_for(seg).sweep_pullbacks(allow_live=allow_live,
                                                      price_fn=_pf)
                if r.get("entered") or r.get("queued"):
                    lat = round((time.time() - t_tick) * 1000, 1)
                    stats.entered_total += len(r.get("entered") or [])
                    stats.last_latency_ms = lat
                    print(f"[reflex:{seg}] tick {ws_sym}@{mid} → "
                          f"entered={r['entered']} queued={r['queued']} "
                          f"latency={lat}ms", flush=True)
                    stats.flush(force=True)
            except Exception as e:
                print(f"[reflex] fire error: {e!r}", flush=True)

    async def _watch_venue(venue: str) -> None:
        resync_s = _env_f("REFLEX_RESYNC_S", 5)
        poll_s = _env_f("PULLBACK_SWEEP_SEC", 45)
        last_offline_poll = 0.0
        while enabled():
            _, streams = _armed_maps()
            names = sorted(streams.get(venue) or [])
            if not names:
                stats.venues[venue] = {"connected": False, "streams": [],
                                       "idle": "nothing armed"}
                stats.flush()
                await asyncio.sleep(resync_s)
                continue
            url = _WS_URL[venue] + "/".join(names)
            try:
                async with websockets.connect(url, ping_interval=20,
                                              close_timeout=3) as ws:
                    stats.venues[venue] = {"connected": True, "streams": names}
                    stats.flush(force=True)
                    last_check = time.monotonic()
                    while True:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=resync_s)
                        except asyncio.TimeoutError:
                            raw = None
                        # resubscribe when the armed set changed (checked even while
                        # ticks flow — a busy stream must not pin a stale set)
                        if time.monotonic() - last_check > resync_s:
                            last_check = time.monotonic()
                            _, now_streams = _armed_maps()
                            if sorted(now_streams.get(venue) or []) != names:
                                break
                        if raw is None:
                            continue
                        t_tick = time.time()
                        try:
                            d = (json.loads(raw).get("data") or {})
                            b, a = d.get("b"), d.get("a")
                            if b is None or a is None:
                                continue
                            stats.ticks += 1
                            _fire(venue, str(d.get("s") or "").upper(),
                                  (float(b) + float(a)) / 2.0, t_tick)
                            stats.flush()
                        except Exception:
                            continue
            except Exception as e:
                stats.venues[venue] = {"connected": False, "streams": names,
                                       "error": str(e)[:160]}
                stats.reconnects += 1
                stats.flush(force=True)
                # offline → keep D3 honest with a polling-cadence sweep
                if time.monotonic() - last_offline_poll > poll_s:
                    last_offline_poll = time.monotonic()
                    try:
                        seg = "futures" if venue == "fut" else "spot"
                        executor_for(seg).sweep_pullbacks(allow_live=allow_live)
                    except Exception:
                        pass
                await asyncio.sleep(min(30.0, 2.0 * (1 + stats.reconnects % 8)))
        stats.venues[venue] = {"connected": False, "streams": [],
                               "error": "REFLEX_LANE=0"}
        stats.flush(force=True)

    async def _session() -> None:
        await asyncio.gather(_watch_venue("fut"), _watch_venue("spot"))

    try:
        asyncio.run(_session())
    except Exception as e:
        state.save_json(_STATE, {"enabled": enabled(),
                                 "error": f"reflex loop died: {e}"[:200],
                                 "ts": time.time()})
