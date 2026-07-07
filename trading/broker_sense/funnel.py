"""trading/broker_sense/funnel.py — the cascade orchestrator (savers B + I: every cycle
COMPLETES inside a wall-clock budget, by construction — this is what fixes the wedge).

Stages, each cheaper stage culling for the dearer one (owner's steps 3-8):
  1. SCREEN   — the brokers'/TradingView's servers scan the whole universe for free
                (screeners.screen_all); numeric cull on the screener's own columns.
  2. HEAT     — survivors touch the hot watchlist (TTL bound, saver E); open positions
                pinned; only the hot set advances.
  3. LOOK     — candle screenshots × timeframes → batched tiny CNN, borderline → LLM
                (chart_vision); multi-timeframe vote → direction.
  4. VERIFY   — screen-mirror top-of-book + accuracy gate + API fail-safe (book_monitor);
                spread/risk rules IN CODE, never the LLM.
  5. DECIDE + EXECUTE
       crypto — the existing BrainExecutor runs on the shortlist ONLY (every UQ /
                psychology / decision-memory / boss gate intact), with app_signals merged
                into decision_snapshot → journal → learning (decision #6);
       nse    — direction + book rules place paper orders via ExecAdapter (OpenAlgo
                sandbox); the same app_signals are journaled to state.
  6. CLEAN    — all screenshots deleted (chart_vision.wipe()).

Adaptive budget (saver I): the shortlist size shrinks when cycles run hot and grows back
when they're fast, inside [4, 30] — a cycle can be SMALL, but it always finishes.
"""
from __future__ import annotations

import os
import time

from trading import state
from trading.broker_sense import chart_vision as cv
from trading.broker_sense.app_explorer import human_checklist
from trading.broker_sense.book_monitor import BookMonitor
from trading.broker_sense.exec_adapter import ExecAdapter
from trading.broker_sense.ocular_perception import OcularPerception
from trading.broker_sense.screeners import PresetStore, screen_all
from trading.broker_sense.watchlist import HotWatchlist

_STATUS_FILE = "broker_sense_status.json"
_NSE_LOG = "broker_sense_nse_trades.json"
_MIN_N, _MAX_N = 4, 30
# brokers the brain should proactively ask to CONNECT (log into the real account) per market —
# owner's first slice is AngelOne (NSE) + Binance (crypto). Override with BROKER_SENSE_LOGINS.
# the market → primary account broker resolves at call time from data_sources (owner-switchable,
# e.g. nse → upstox after Angel One blocked automated logins). Env BROKER_SENSE_LOGINS overrides.
_LOGIN_BROKERS = {"crypto": ["binance"], "nse": ["angelone"]}   # fallback if state unavailable
_MAX_SPREAD_PCT = 0.5                    # risk rule in CODE: never cross a wide spread
_FULL_TFS = tuple(cv.TIMEFRAMES)
_FAST_TFS = tuple(cv.FAST_TFS)           # budget squeeze → fewer timeframes, never zero


def _budget_s() -> float:
    env = os.environ.get("BROKER_SENSE_BUDGET")
    if env:
        try:
            return float(env)
        except ValueError:
            pass
    try:                                          # durable fallback: config.json (live-truth)
        import json
        with open("/home/karan18190164/trading/crypto/freqtrade/config.json") as fh:
            return float(json.load(fh).get("broker_sense_budget", 60))
    except Exception:
        return 60.0


def _fast_book(symbol: str, market: str) -> dict:
    """Top-of-book the FAST way (ccxt via data_failsafe), no browser OCR. Adds spread_pct so the
    funnel's in-code spread risk rule still applies. Honest empty dict on any miss."""
    try:
        from trading.broker_sense import data_failsafe
        b = data_failsafe.top_of_book(symbol, market) or {}
    except Exception:
        return {}
    bid, ask = b.get("bid"), b.get("ask")
    if isinstance(bid, (int, float)) and isinstance(ask, (int, float)) and bid > 0:
        b["spread_pct"] = round((ask - bid) / bid * 100.0, 4)
    b.setdefault("consistent", True)
    return b


def _fast_candles() -> bool:
    """Read direction from OHLCV data (fast) instead of chart screenshots. Default ON so the whole
    cycle fits the budget; set OCULAR_FAST_CANDLES=0 for the heavier screenshot+CNN vision."""
    return os.environ.get("OCULAR_FAST_CANDLES", "1") not in ("0", "false", "False", "")


def _login_brokers(market: str) -> list[str]:
    """Brokers to proactively ask to connect for `market` (env override, else the defaults)."""
    env = os.environ.get("BROKER_SENSE_LOGINS")
    if env:
        return [b.strip() for b in env.split(",") if b.strip()]
    try:                                     # state-backed primary (owner-switchable)
        from trading.broker_sense.data_sources import primary_broker
        b = primary_broker(market)
        if b:
            return [b]
    except Exception:
        pass
    return _LOGIN_BROKERS.get(market, [])


def _vote(chart: dict) -> tuple[str, float]:
    """Multi-timeframe direction vote → (direction, mean p_up). Neutral unless the
    timeframes actually agree — a human doesn't trade a chart that disagrees with itself."""
    ps = [c["p_up"] for c in chart.values() if c.get("source") != "unavailable"]
    if not ps:
        return "neutral", 0.5
    mean = sum(ps) / len(ps)
    longs = sum(1 for p in ps if p > 0.55)
    shorts = sum(1 for p in ps if p < 0.45)
    if longs >= max(2, len(ps) // 2) and shorts == 0:
        return "long", mean
    if shorts >= max(2, len(ps) // 2) and longs == 0:
        return "short", mean
    return "neutral", mean


class BrokerSenseFunnel:
    """One funnel per market ('crypto' | 'nse')."""

    def __init__(self, market: str, sessions=None, *, executor=None, exec_adapter=None):
        self.market = market
        if sessions is None:
            from trading.broker_sense.sessions import get_sessions
            sessions = get_sessions()
        self.sessions = sessions
        self.presets = PresetStore()
        self.watch = HotWatchlist(market=market)
        # NEW eyes: the Ocular Cortex reads each candidate's fused perception (app order book /
        # funding / OI via interception + a FREE VLM read of the real chart pixels) and links
        # the frame to the decision. ChartVision hands it the app screenshot before deleting it.
        self.ocular = OcularPerception(market=market)
        self.vision = cv.ChartVision(sessions, on_app_shot=self.ocular.on_app_shot)
        self.book = BookMonitor(sessions)
        self.exec = exec_adapter or ExecAdapter()
        self._executor = executor                     # crypto: BrainExecutor (lazy)
        self.cycle_n = 0
        st = state.load_json(_STATUS_FILE, {})
        self.shortlist_n = int(st.get(f"{market}_shortlist_n", 12))
        self.last: dict = st.get(market, {})

    # ── crypto executor (all existing gates) ────────────────────────────────────
    def executor(self, segment: str):
        if self._executor is None:
            from trading.crypto.freqtrade.brain_executor import BrainExecutor
            self._executor = BrainExecutor(segment=segment)
        return self._executor

    # ── the cycle ────────────────────────────────────────────────────────────────
    def run_cycle(self, *, segment: str = "futures", allow_live: bool = False) -> dict:
        t0 = time.monotonic()
        budget = _budget_s()
        self.cycle_n += 1
        self.ocular.reset_cycle()             # fresh per-cycle vision quota + frame cache
        for b in _login_brokers(self.market):     # proactively ask to connect the real account
            try:                                  # (chat shows it up front, not only reactively)
                self.sessions.ensure_login_requested(b)
            except Exception:
                pass
        rep: dict = {"market": self.market, "segment": segment, "cycle": self.cycle_n,
                     "budget_s": budget, "stages": {}}

        # 1 ── SCREEN (their servers) + numeric cull — app lanes hard-capped at 35% of the
        # budget (TV lane is the guaranteed floor; slow broker pages roll to the next bar)
        preset = self.presets.pick(self.market, self.cycle_n)
        rows = screen_all(self.market, self.sessions, preset=preset,
                          deadline=t0 + budget * 0.35)
        rows = [r for r in rows if abs(float(r.get("change") or 0)) >= 0.3]   # cheap cull
        # BROKER-FEATURE fusion (owner: use the apps' OWN built-in pickers). Read every built-in
        # screener in parallel, fuse them (weighted by learned hit-rate), and MERGE the top fused
        # names into the candidate rows — the broker already ranked them, so this is near-free.
        fused_n = 0
        if os.environ.get("BROKER_FEATURES", "1") in ("1", "true", "TRUE", "yes"):
            try:
                from trading.broker_sense import broker_features as bfeat
                bkr = "binance" if self.market == "crypto" else "upstox"
                fmap = bfeat.read_all_features(bkr, self.sessions, limit=25,
                                               parallel=True)
                have = {r["symbol"] for r in rows}
                for c in bfeat.fuse(bkr, fmap):
                    if c["symbol"] not in have and c["side"] != "flat":
                        rows.append({"symbol": c["symbol"], "change": c.get("chg") or 0,
                                     "lane": "broker_feature", "preset": "fusion",
                                     "fusion_score": c["score"], "fusion_features": c["features"]})
                        fused_n += 1
            except Exception:
                pass
        # NSE: keep only the liquid, F&O-eligible universe. The broker-feature pickers
        # (Upstox movers/gainers) surface illiquid micro-caps (DBSTOCKBRO, IOLCP…) the
        # brain rightly abstains on; the owner wants the liquid 500+ intraday names. This
        # runs AFTER fusion so it catches picker candidates too. (2026-07-07 fix)
        if self.market == "nse":
            try:
                from trading.screener.universe import is_liquid
                liq = [r for r in rows if is_liquid(r.get("symbol", ""))]
                if liq:
                    rows = liq
            except Exception:
                pass
        rep["stages"]["screen"] = {"preset": preset, "surfaced": len(rows), "fused": fused_n}

        # 2 ── HEAT: watchlist TTL bound + pin open positions
        for r in rows:
            self.watch.touch(r["symbol"], score=float(r.get("change") or 0))
        open_syms: set = set()
        if self.market == "crypto":
            try:
                open_syms = set(self.executor(segment).client().open_pairs(segment=segment))
                for s in open_syms:
                    self.watch.pin(s)
            except Exception:
                pass
        hot = self.watch.hot()
        by_sym = {r["symbol"]: r for r in rows}
        picks = [by_sym.get(s, {"symbol": s, "lane": "tradingview"})
                 for s in hot][: self.shortlist_n]
        rep["stages"]["heat"] = {"hot": len(hot), "shortlist": len(picks),
                                 "pinned_open": len(open_syms)}

        # 3 ── LOOK: candle images → CNN/LLM (budget-aware timeframe set + HARD deadline:
        # past 70% of the budget, capture switches to the fast local API render so this
        # stage can never wedge on slow broker pages — saver I by construction)
        tfs = _FULL_TFS if (time.monotonic() - t0) < budget * 0.4 else _FAST_TFS
        if _fast_candles():                   # DATA read (fast API OHLCV → direction), no browser
            from trading.broker_sense import fast_candles
            charts = fast_candles.read(picks, self.market, timeframes=tfs,
                                       deadline=t0 + budget * 0.7)
        else:                                 # opt-out: the heavier screenshot+CNN chart vision
            charts = self.vision.read(picks, self.market, timeframes=tfs,
                                      deadline=t0 + budget * 0.7,
                                      hard_deadline=t0 + budget * 0.85)
        directions = {s: _vote(c) for s, c in charts.items()}
        candidates = [s for s, (d, _) in directions.items()
                      if d != "neutral" or s in open_syms]
        rep["stages"]["look"] = {"timeframes": list(tfs), "read": len(charts),
                                 "non_neutral": len(candidates),
                                 **self.vision.stats}

        # 4 ── VERIFY: top-of-book (screen-mirror + API fail-safe) + risk rules IN CODE
        app_signals: dict = {}
        tradeable = []
        # EXPLORE OPEN-ALL (owner 2026-07-06): in paper, until the brain has learned, let EVERY
        # candidate through the VERIFY cull (spread/liq become advisory, still recorded) so the
        # executor can open them all — the risk rules re-arm automatically once it graduates.
        _explore = (not allow_live) and os.environ.get(
            "BRAIN_EXPLORE_OPEN_ALL", "1") in ("1", "true", "TRUE", "yes", "on")
        for s in candidates:
            if time.monotonic() - t0 > budget * 0.85:          # saver I: finish > perfect
                break
            if _fast_candles():                    # fast API order book (ccxt), no browser OCR
                book = _fast_book(s, self.market)
            else:
                book = self.book.top_of_book(s, self.market, by_sym.get(s, {}).get("lane", ""))
            sig = human_checklist(s, self.market, self.sessions,
                                  chart=charts.get(s), book=book)
            sig["screener"] = {k: by_sym.get(s, {}).get(k) for k in
                               ("lane", "preset", "change", "volume")}
            sig["vote"] = {"direction": directions[s][0], "p_up": round(directions[s][1], 4)}
            # INDICATOR FUSION (owner ask 2026-07-06): multi-TF MA/EMA/Boll/SAR/Supertrend/ADX
            # confluence + regime gate + the vision lens (charts) + conformal meta-label + ATR
            # triple-barrier geometry → the entry-price/direction plan. Budget-bounded + opt-out.
            if os.environ.get("INDICATOR_FUSION", "1") in ("1", "true", "TRUE", "yes") \
                    and time.monotonic() - t0 < budget * 0.88:
                try:
                    from trading.broker_sense import indicator_fusion as _if
                    sig["indicator_fusion"] = _if.fuse(s, self.market, vision=charts.get(s))
                except Exception as e:
                    sig["indicator_fusion"] = {"available": False, "error": str(e)[:120]}
            try:                              # NEW eyes: fused Ocular Cortex perception per
                sig["ocular"] = self.ocular.enrich(   # candidate → learning columns + memory
                    s, lane=by_sym.get(s, {}).get("lane", ""), chart=charts.get(s),
                    book=book, deadline=t0 + budget * 0.9)
            except Exception as e:
                sig["ocular"] = {"error": str(e)[:120]}
            # ORDER-PREVIEW gate (owner idea): read the BROKER'S OWN pre-trade risk math
            # (margin / liquidation price / impact) from its order ticket — READ, never submit —
            # and attach it so the executor sizes with the broker's numbers. Budget-bounded.
            if os.environ.get("BROKER_ORDER_PREVIEW", "0") in ("1", "true", "TRUE", "yes") \
                    and time.monotonic() - t0 < budget * 0.8:
                try:
                    from trading.broker_sense import broker_features as bfeat
                    bkr = "binance" if self.market == "crypto" else "upstox"
                    sig["order_preview"] = bfeat.order_preview(bkr, s, self.sessions)
                except Exception:
                    pass
            app_signals[s] = sig
            sp = book.get("spread_pct")
            # broker's own liquidation-price sanity: skip if the preview says the liq price sits
            # absurdly close (a risk the broker itself flags) — free capital-preservation check
            prev = sig.get("order_preview") or {}
            liq_ok = True
            if prev.get("liquidation_price") and book.get("mid"):
                try:
                    dist = abs(prev["liquidation_price"] - book["mid"]) / book["mid"]
                    liq_ok = dist > 0.01               # liq >1% away (else the broker warns it's tight)
                except Exception:
                    liq_ok = True
            if _explore or ((s in open_syms or sp is None or sp <= _MAX_SPREAD_PCT) and liq_ok):
                tradeable.append(s)
        rep["stages"]["verify"] = {"checked": len(app_signals), "tradeable": len(tradeable),
                                   **self.book.stats}

        # 5 ── DECIDE + EXECUTE (APIs only, owner's step 8)
        if self.market == "crypto":
            ex = self.executor(segment)
            ex._symbols = sorted(set(tradeable) | open_syms)   # shortlist-only universe
            ex.extra_signals = app_signals                     # → decision_snapshot.app_signals
            res = ex.run_once(allow_live=allow_live, deadline=t0 + budget)
            rep["stages"]["execute"] = {"entered": res.get("entered"),
                                        "exited": res.get("exited"),
                                        "skipped": res.get("skipped"),
                                        "vetoed": res.get("vetoes"),
                                        "deadline_deferred": res.get("deadline_deferred")}
            traded = len(res.get("entered") or [])
            for sym in (res.get("entered") or []):     # link the frame that drove each entry
                self.ocular.link_entry(sym, self.market)
        else:
            traded = 0
            placed = []
            for s in tradeable:
                d, p = directions[s]
                if d == "neutral":
                    continue
                try:
                    r = self.exec.place(market="nse", symbol=s,
                                        action=("BUY" if d == "long" else "SELL"),
                                        segment=segment, live=False,
                                        enter_tag=f"broker_sense:{preset}")
                    placed.append({"symbol": s, "direction": d, "p_up": round(p, 4),
                                   "app_signals": app_signals.get(s), "ts": time.time(),
                                   "order": {k: r.get(k) for k in ("broker", "live", "ok")}})
                    traded += 1
                except Exception as e:
                    placed.append({"symbol": s, "error": str(e)[:120]})
            for p in placed:                           # link the frame that drove each entry
                if "error" not in p:
                    self.ocular.link_entry(p["symbol"], self.market)
            if placed:
                log = state.load_json(_NSE_LOG, [])
                state.save_json(_NSE_LOG, (log + placed)[-300:])
            rep["stages"]["execute"] = {"entered": [p["symbol"] for p in placed
                                                    if "error" not in p]}
        self.presets.record(self.market, preset, traded=traded, wins=0, pnl=0.0)

        # 6 ── CLEAN (owner's step 7) + adaptive budget (saver I)
        rep["screenshots_deleted"] = cv.wipe() + self.vision.stats.get("deleted", 0)
        took = time.monotonic() - t0
        if took > budget * 0.8:
            self.shortlist_n = max(_MIN_N, self.shortlist_n - 2)
        elif took < budget * 0.5:
            self.shortlist_n = min(_MAX_N, self.shortlist_n + 2)
        rep["took_s"] = round(took, 2)
        rep["ts"] = time.time()              # lets status() pick the freshest across processes
        rep["completed_within_budget"] = took <= budget
        rep["next_shortlist_n"] = self.shortlist_n
        self.last = rep
        st = state.load_json(_STATUS_FILE, {})
        st[self.market] = rep
        st[f"{self.market}_shortlist_n"] = self.shortlist_n
        state.save_json(_STATUS_FILE, st)
        return rep

    # ── dashboard status (honest) ───────────────────────────────────────────────
    def status(self) -> dict:
        from trading.broker_sense.app_explorer import get_catalog
        from trading.broker_sense.brokers import status as broker_status
        from trading.broker_sense.learning_columns import get_registry
        # the driver (run_funnel_loop) and the dashboard run SEPARATE funnel instances;
        # the status file is the cross-process truth — serve whichever report is fresher,
        # else the panel would show the dashboard's own stale cycle forever
        disk = state.load_json(_STATUS_FILE, {}).get(self.market) or {}
        last = disk if disk.get("ts", 0) > (self.last or {}).get("ts", 0) else self.last
        return {
            "market": self.market,
            "last_cycle": last,
            "shortlist_n": self.shortlist_n,
            "watchlist": self.watch.status(),
            "presets": self.presets.status(),
            "brokers": broker_status(),
            "sessions": self.sessions.status() if hasattr(self.sessions, "status") else {},
            "feature_catalog": get_catalog().status(),
            "learning_columns": get_registry().status(),
            "execution": self.exec.status(),
            "ocular": self.ocular.status(),
        }
