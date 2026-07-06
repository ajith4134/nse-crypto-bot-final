"""trading/broker_sense/chart_vision.py — screenshot the candles, read them, delete them.

Owner's step 4: for each screener pick, open that symbol's candle chart at 1m/5m/15m/30m/1h
(24 bars), SCREENSHOT it, and let ML/DL read the direction off the IMAGE.

Capture chain (rule-4 fail-safe — a chart read never goes missing):
  1. the pick's own broker-app chart page (sessions.py, logged-in context);
  2. TradingView's public chart (?symbol&interval — no login);
  3. LOCAL RENDER: pull candles via API (data_failsafe.ohlcv) and draw them with matplotlib
     — same 24-bar candlestick picture, source honestly marked "render:api".

Savers D + F: every screenshot is sha256-hashed — identical to the last bar's hash ⇒ the
cached direction is reused and inference is SKIPPED; fresh images go to the CNN as ONE
batch. Screenshots are DELETED after inference (owner's step 7) — `wipe()` also runs every
cycle end as a belt-and-braces sweep.
"""
from __future__ import annotations

import hashlib
import os
import time

from trading import state
from trading.broker_sense import data_failsafe
from trading.broker_sense.brokers import REGISTRY

# tf → TradingView interval. Owner ask (2026-07-06): 1m,5m,15m,1h,4h,1d — scalp→swing ladder,
# the higher TFs (4h/1d) set the directional bias for indicator_fusion, the lower ones the timing.
TIMEFRAMES = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240", "1d": "D"}
FAST_TFS = ("5m", "15m", "1h")   # past the soft deadline only these render — finish > perfect
BARS = 24
_CACHE_FILE = "broker_sense_vision_cache.json"
_SHOT_DIR = "chart_shots"
_TV_FMT = "https://www.tradingview.com/chart/?symbol={symbol}&interval={interval}"


def _shot_dir():
    d = state._path(_SHOT_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def wipe() -> int:
    """Delete ALL chart screenshots (owner's step 7). Returns how many were removed."""
    n = 0
    d = state._path(_SHOT_DIR)
    if d.exists():
        for p in d.glob("*.png"):
            try:
                p.unlink()
                n += 1
            except OSError:
                pass
    return n


def _tv_symbol(symbol: str, market: str) -> str:
    if market == "crypto":
        return "BINANCE:" + symbol.split("/")[0] + "USDT"
    return "NSE:" + symbol.split("/")[0]


class ChartVision:
    """Capture + cache + batched-read of candle charts for one funnel cycle."""

    def __init__(self, sessions=None, on_app_shot=None):
        self.sessions = sessions
        self.cache = state.load_json(_CACHE_FILE, {})       # "sym|tf" -> {sha, result, bar_ts}
        self.stats = {"captured": 0, "cache_hits": 0, "rendered": 0, "deleted": 0}
        # optional sink: real app chart pixels handed to the Ocular Cortex for a FREE VLM read
        # right before the screenshot is deleted (bounded by the sink's own per-cycle quota)
        self.on_app_shot = on_app_shot
        self._shot_seen: set = set()

    # ── capture one (symbol, tf) → png path + provenance ───────────────────────
    def _capture_app(self, symbol: str, market: str, tf: str, lane: str,
                     deadline: float | None = None) -> tuple[str, str] | None:
        """Try the pick's broker app first, then TradingView public chart. The page-load
        timeout shrinks to the time left before `deadline` so one slow page can't eat
        the whole LOOK stage."""
        if self.sessions is None:
            return None
        tries = []
        app = REGISTRY.get(lane)
        if app is not None and app.chart_url and app.market in (market, "both"):
            tries.append((lane, app.chart_url.format(symbol=symbol.split("/")[0],
                                                     interval=TIMEFRAMES[tf])))
        tries.append(("tradingview", _TV_FMT.format(symbol=_tv_symbol(symbol, market),
                                                    interval=TIMEFRAMES[tf])))
        for broker, url in tries:
            timeout_ms = 15000
            if deadline is not None:
                left = (deadline - time.monotonic()) * 1000
                if left < 6000:                 # not enough for load+paint → render path
                    return None
                timeout_ms = int(min(timeout_ms, left - 4000))
            try:
                pg = self.sessions.page(broker, url, timeout_ms=timeout_ms)
                if pg is None:
                    continue
                pg.wait_for_timeout(3500)                    # let the canvas paint
                path = str(_shot_dir() / f"{symbol.split('/')[0]}_{tf}_{int(time.time())}.png")
                pg.screenshot(path=path, full_page=False)
                try:                                          # decision #6: mine chart-page text
                    from trading.broker_sense.learning_columns import discover_from_text
                    discover_from_text(broker, (pg.inner_text("body") or "")[:8000],
                                       symbol=symbol)
                except Exception:
                    pass
                pg.close()
                return path, f"screenshot:{broker}"
            except Exception:
                continue
        return None

    def _render_api(self, symbol: str, market: str, tf: str) -> tuple[str, str] | None:
        """Rule-4 fallback: draw the same 24 candles locally from API data."""
        rows = data_failsafe.ohlcv(symbol, market, timeframe=tf, limit=BARS)
        if not rows:
            return None
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(2.4, 2.4), dpi=100)
        for i, r in enumerate(rows[-BARS:]):
            o, h, l, c = float(r[1]), float(r[2]), float(r[3]), float(r[4])
            up = c >= o
            ax.plot([i, i], [l, h], lw=0.7, color="0.4")
            ax.add_patch(plt.Rectangle((i - 0.33, min(o, c)), 0.66, abs(c - o) or 1e-9,
                                       color=("white" if up else "black"), ec="0.2", lw=0.4))
        ax.set_axis_off()
        fig.tight_layout(pad=0)
        path = str(_shot_dir() / f"{symbol.split('/')[0]}_{tf}_r{int(time.time())}.png")
        fig.savefig(path, facecolor="0.75")
        plt.close(fig)
        self.stats["rendered"] += 1
        return path, "render:api"

    # ── the per-cycle batch read ────────────────────────────────────────────────
    def read(self, picks: list[dict], market: str,
             timeframes=tuple(TIMEFRAMES), deadline: float | None = None,
             hard_deadline: float | None = None) -> dict[str, dict[str, dict]]:
        """For every pick × timeframe: capture (or reuse cache), then ONE batched CNN pass;
        borderline rows escalate to the LLM; screenshots deleted after inference.
        Returns {symbol: {tf: {p_up, direction, source, chart_source}}}.

        Deadlines (time.monotonic values, saver I): past `deadline`, browser captures stop
        and only the FAST_TFS still render locally (a render is ~2s of matplotlib — doing
        all five timeframes for every leftover pick blew the 2026-07-05 budget by 40%);
        past `hard_deadline`, the rest is marked unavailable and rolls to the next cycle."""
        from trading.broker_sense.cnn_direction import get_model, llm_escalate
        self._shot_seen.clear()                                # per-cycle: allow one fresh
        jobs: list[tuple[str, str, str, str]] = []             # app-pixel VLM read per symbol
        out: dict[str, dict[str, dict]] = {}
        bar_now = int(time.time() // 300)                      # 5m bar index for cache keying
        for pick in picks:
            sym, lane = pick["symbol"], pick.get("lane", "tradingview")
            out.setdefault(sym, {})
            for tf in timeframes:
                key = f"{sym}|{tf}"
                now = time.monotonic()
                over = deadline is not None and now > deadline
                dead = hard_deadline is not None and now > hard_deadline
                if dead or (over and tf not in FAST_TFS):      # finish > perfect (saver I)
                    out[sym][tf] = {"p_up": 0.5, "direction": "neutral",
                                    "source": "unavailable", "chart_source": "none"}
                    continue
                cap = (None if over else
                       self._capture_app(sym, market, tf, lane, deadline=deadline)) or \
                    self._render_api(sym, market, tf)
                if cap is None:                                # total miss → neutral, honest
                    out[sym][tf] = {"p_up": 0.5, "direction": "neutral",
                                    "source": "unavailable", "chart_source": "none"}
                    continue
                path, chart_source = cap
                self.stats["captured"] += 1
                sha = hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
                hit = self.cache.get(key)
                if hit and hit.get("sha") == sha:              # saver D: same pixels ⇒ reuse
                    out[sym][tf] = {**hit["result"], "chart_source": chart_source,
                                    "cached": True}
                    self.stats["cache_hits"] += 1
                    os.remove(path)
                    self.stats["deleted"] += 1
                    continue
                jobs.append((sym, tf, path, chart_source))
                self.cache[key] = {"sha": sha, "bar_ts": bar_now, "result": None}
        # saver F: one batched forward over everything fresh
        results = get_model().predict([j[2] for j in jobs])
        # saver B means the borderline FEW: LLM escalation is quota-capped per cycle and
        # stops at the deadline — an unbounded escalate-everything loop wedged live 2026-07-05
        llm_quota = 3
        for (sym, tf, path, chart_source), res in zip(jobs, results):
            if res.get("escalate") and llm_quota > 0 and \
                    (deadline is None or time.monotonic() < deadline):
                esc = llm_escalate(sym, tf, data_failsafe.ohlcv(sym, market, tf, 8) or [])
                llm_quota -= 1
                if esc:
                    res = {**esc, "escalated_from": "cnn"}
            res["chart_source"] = chart_source
            out[sym][tf] = res
            self.cache[f"{sym}|{tf}"]["result"] = {k: res[k] for k in
                                                   ("p_up", "direction", "source")}
            if (self.on_app_shot is not None and chart_source.startswith("screenshot:")
                    and sym not in self._shot_seen):           # one real-pixel read per symbol
                try:
                    self.on_app_shot(sym, tf, open(path, "rb").read())
                    self._shot_seen.add(sym)
                except Exception:
                    pass
            try:                                               # owner's step 7: delete
                os.remove(path)
                self.stats["deleted"] += 1
            except OSError:
                pass
        # bound + persist the cache (current bar only is useful)
        self.cache = {k: v for k, v in self.cache.items()
                      if v.get("bar_ts", 0) >= bar_now - 2 and v.get("result")}
        state.save_json(_CACHE_FILE, self.cache)
        wipe()                                                 # belt-and-braces sweep
        return out
