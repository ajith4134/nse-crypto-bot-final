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
_MIN_N, _MAX_N = 4, 60      # ceiling raised 30→60 (owner 2026-07-07: 32 GB box, use it);
                            # the budget-adaptive loop still governs actual growth
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


def _unlimited_opens() -> bool:
    """Brain-decides mode (owner 2026-07-11): NO artificial cap on how many trades open at once.
    The compute-offload made wide screening cheap (Binance WS mirror = RAM), so we feed the whole
    liquid universe to the executor and let the brain's score gate — not a shortlist — decide."""
    return os.environ.get("CRYPTO_UNLIMITED_OPENS", "1") in ("1", "true", "TRUE", "yes", "on")


def _unlimited_budget() -> float:
    try:
        return float(os.environ.get("CRYPTO_UNLIMITED_BUDGET_S", "300") or 300)
    except ValueError:
        return 300.0


def _unlimited_min_qv() -> float:
    """Liquidity floor for the wide universe (skip illiquid dust — not an artificial cap, a
    tradeability guard). Default 3M USDT 24h quote-volume."""
    try:
        return float(os.environ.get("CRYPTO_UNLIMITED_MIN_QV", "3000000") or 3_000_000)
    except ValueError:
        return 3_000_000.0


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
        self._executor = executor                     # crypto: injected override (tests)
        self._executors: dict = {}                    # crypto: BrainExecutor per segment (lazy)
        self._strat_lib = None                        # cached full-library decider (lazy)
        self._strat_cache: dict = {}                  # (symbol, 5m-bar) → strategy-lens memo
        self.cycle_n = 0
        st = state.load_json(_STATUS_FILE, {})
        self.shortlist_n = int(st.get(f"{market}_shortlist_n", 12))
        self.last: dict = st.get(market, {})

    # ── crypto executor (all existing gates) ────────────────────────────────────
    def executor(self, segment: str):
        if self._executor is not None:                # injected (tests): one for all segments
            return self._executor
        # One executor PER SEGMENT — a shared instance would bake in whichever segment
        # asked first, silently routing options/prediction cycles to the futures bot.
        ex = self._executors.get(segment)
        if ex is None:
            from trading.crypto.freqtrade.brain_executor import BrainExecutor
            ex = self._executors[segment] = BrainExecutor(segment=segment)
        return ex

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
        _ts_screen_end = time.monotonic()     # PERF: SCREEN stage boundary (screen = this - t0)

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
        shortlist_n = self.shortlist_n
        # BRAIN-DECIDES (owner 2026-07-11): in unlimited mode feed the FULL liquid universe (from the
        # WS mirror — RAM, ~0 CPU) to the executor and remove the shortlist cap, so the brain can open
        # as many as its score gate passes (300+ possible), never bounded by an artificial shortlist.
        if _unlimited_opens():
            try:
                # SEGMENT-CORRECT full universe: use THIS segment's own tradeable whitelist (626
                # futures / 420 spot / NSE equity), so every selected segment gets its whole
                # universe — never futures symbols leaking into the spot cycle. The executor also
                # evaluates this same whitelist; injecting it here enriches it with fused app_signals.
                uni = list(self.executor(segment).client().whitelist(segment=segment) or [])
                if uni:
                    hot = list(dict.fromkeys(list(hot) + uni))
                    for s in uni:
                        by_sym.setdefault(s, {"symbol": s, "lane": "universe"})
                    shortlist_n = len(hot)               # no cap — the brain's min_score decides
            except Exception:
                pass
        # Open positions ride FREE (2026-07-07 throughput fix): pinning them INTO the
        # shortlist made 3-5 open trades consume nearly all of the floor-4 slots,
        # leaving ~0-1 NEW candidates per cycle — the real reason "max trades
        # unlimited" still opened almost nothing. shortlist_n now budgets NEW symbols
        # only; opens are appended on top (they still need the eyes for exits).
        # LOOK TOP-K BOUND (owner 2026-07-12, final governor-flip lever): the LOOK stage reads
        # per-TF direction (fast_candles) for EVERY pick — ~250 symbols × TFs — which kept cycles
        # over budget even after the VERIFY bound, so the rolling tab pool couldn't sweep coverage
        # to the governor's flip threshold. `hot` is already score-ranked, so read direction only
        # for the top-K most-promising NEW symbols; OPEN trades are always looked at (exits need it).
        # LOOK_TOPK tunes it (default 60); 0 = unbounded (old behaviour, shortlist_n only).
        try:
            look_topk = int(os.environ.get("LOOK_TOPK", "60") or 60)
        except ValueError:
            look_topk = 60
        _cap = min(shortlist_n, look_topk) if look_topk > 0 else shortlist_n
        new_hot = [s for s in hot if s not in open_syms][: _cap]
        picks = [by_sym.get(s, {"symbol": s, "lane": "tradingview"})
                 for s in new_hot]
        picks += [by_sym.get(s, {"symbol": s, "lane": "open-position"})
                  for s in open_syms]
        rep["stages"]["heat"] = {"hot": len(hot), "shortlist": len(picks),
                                 "new": len(new_hot), "pinned_open": len(open_syms)}

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
        # D1 Truth Ledger (Pillar 27): every non-neutral verdict is a directional CLAIM —
        # record it now (taken or not) so its fixed-horizon truth gets measured. Never raises.
        try:
            from trading.direction import truth_ledger
            for s, (d, score) in directions.items():
                if d != "neutral":
                    truth_ledger.record(symbol=s, market=self.market,
                                        segment=segment or "futures",
                                        direction=d, source="funnel_mtf_vote",
                                        confidence=score)
            # D4/D7 shadow league: the microstructure lanes (venue lead-lag, OFI,
            # funding extreme, multi-TF agreement) each stake their own claim on the
            # same candidates — every lane earns a measured hit-rate. Budgeted.
            if self.market == "crypto":
                from trading.direction import micro_features
                micro_features.record_claims(
                    [s for s, (d, _) in directions.items() if d != "neutral"][:12],
                    segment=segment or "futures", budget_s=15)
        except Exception:
            pass
        candidates = [s for s, (d, _) in directions.items()
                      if d != "neutral" or s in open_syms]
        non_neutral_n = len(candidates)
        # TOP-K VERIFY BOUND (owner 2026-07-12): the deep VERIFY lenses (fusion + the 239-strategy
        # lens + ocular) ran on EVERY non-neutral candidate (~100/cycle) → 305s cycles that starved
        # the tab pool → coverage never reached the governor's flip threshold. Rank by LOOK
        # direction STRENGTH (|p_up-0.5|) and deep-verify only the top-K most-promising + every OPEN
        # trade (never dropped — they need their exit signal). The rest are screened but not
        # deep-lensed this cycle. VERIFY_TOPK tunes the cap; 0 = unbounded (old behaviour).
        try:
            topk = int(os.environ.get("VERIFY_TOPK", "30") or 30)
        except ValueError:
            topk = 30
        if topk > 0 and len(candidates) > topk:
            _opens = [s for s in candidates if s in open_syms]
            _rest = sorted((s for s in candidates if s not in open_syms),
                           key=lambda s: -abs(float(directions[s][1]) - 0.5))
            candidates = _opens + _rest[: max(0, topk - len(_opens))]
        rep["stages"]["look"] = {"timeframes": list(tfs), "read": len(charts),
                                 "non_neutral": non_neutral_n,
                                 "deep_verified": len(candidates),
                                 "cands": candidates[:24],
                                 **self.vision.stats}

        # 4 ── VERIFY: top-of-book (screen-mirror + API fail-safe) + risk rules IN CODE
        app_signals: dict = {}
        tradeable = []
        # PERF INSTRUMENTATION (2026-07-12): per-sub-call wall-time so the cycle log shows WHERE
        # the VERIFY seconds go (book vs checklist vs fusion vs ocular vs preview) instead of one
        # opaque total. Near-zero overhead; always on. Read by the run_cycle timing summary below.
        _vt = {"book": 0.0, "checklist": 0.0, "fusion": 0.0, "ocular": 0.0, "preview": 0.0}
        _ts_look_end = time.monotonic()
        # EXPLORE OPEN-ALL (owner 2026-07-06): in paper, until the brain has learned, let EVERY
        # candidate through the VERIFY cull (spread/liq become advisory, still recorded) so the
        # executor can open them all — the risk rules re-arm automatically once it graduates.
        _explore = (not allow_live) and os.environ.get(
            "BRAIN_EXPLORE_OPEN_ALL", "1") in ("1", "true", "TRUE", "yes", "on")
        for s in candidates:
            if time.monotonic() - t0 > budget * 0.85:          # saver I: finish > perfect
                break
            _tb = time.monotonic()
            if _fast_candles():                    # fast API order book (ccxt), no browser OCR
                book = _fast_book(s, self.market)
            else:
                book = self.book.top_of_book(s, self.market, by_sym.get(s, {}).get("lane", ""))
            _vt["book"] += time.monotonic() - _tb
            _tc = time.monotonic()
            sig = human_checklist(s, self.market, self.sessions,
                                  chart=charts.get(s), book=book)
            _vt["checklist"] += time.monotonic() - _tc
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
                    _tf0 = time.monotonic()
                    sig["indicator_fusion"] = _if.fuse(s, self.market, vision=charts.get(s))
                    _vt["fusion"] += time.monotonic() - _tf0
                    # measure fusion as a directional SOURCE so the mirror gate can weight/invert
                    # it by its real hit-rate (wired 2026-07-12; the executor now trades on it).
                    _fz = sig["indicator_fusion"]
                    if _fz.get("available") and _fz.get("direction") in ("long", "short"):
                        try:
                            from trading.direction import truth_ledger as _tl
                            from trading.direction import meta_labeler as _ml0
                            _tl.record(symbol=s, market=self.market, segment=segment or "futures",
                                       direction=_fz["direction"], source="indicator_fusion",
                                       confidence=_fz.get("p_up"),
                                       features=_ml0.lens_features(_fz))   # M1 stacking signal
                        except Exception:
                            pass
                except Exception as e:
                    sig["indicator_fusion"] = {"available": False, "error": str(e)[:120]}
            # STRATEGY LIBRARY lens (owner 2026-07-12: "use ALL the strategy features when
            # opening a trade"): run the full institutional strategy library ensemble on the
            # symbol's (UI-captured) candles — every active strategy votes — and stack it as a
            # meta-labeler source alongside fusion, so the trade-open decision reflects the whole
            # strategy stack, not just indicators+vision. Budget-bounded + opt-out (STRATEGY_LENS=0).
            if os.environ.get("STRATEGY_LENS", "1") in ("1", "true", "TRUE", "yes") \
                    and self.market == "crypto" and time.monotonic() - t0 < budget * 0.9:
                try:
                    _tsl = time.monotonic()
                    sig["strategy_library"] = self._strategy_lens(s)
                    _vt["fusion"] += time.monotonic() - _tsl
                    _sl = sig["strategy_library"]
                    if _sl.get("available") and _sl.get("direction") in ("long", "short"):
                        try:
                            from trading.direction import meta_labeler as _ml1
                            from trading.direction import truth_ledger as _tl1
                            _tl1.record(symbol=s, market=self.market,
                                        segment=segment or "futures",
                                        direction=_sl["direction"], source="strategy_library",
                                        confidence=_sl.get("p_up"),
                                        features=_ml1.lens_features(_sl))
                        except Exception:
                            pass
                except Exception as e:
                    sig["strategy_library"] = {"available": False, "error": str(e)[:120]}
            _to = time.monotonic()
            try:                              # NEW eyes: fused Ocular Cortex perception per
                sig["ocular"] = self.ocular.enrich(   # candidate → learning columns + memory
                    s, lane=by_sym.get(s, {}).get("lane", ""), chart=charts.get(s),
                    book=book, deadline=t0 + budget * 0.9)
            except Exception as e:
                sig["ocular"] = {"error": str(e)[:120]}
            _vt["ocular"] += time.monotonic() - _to
            # ORDER-PREVIEW gate (owner idea): read the BROKER'S OWN pre-trade risk math
            # (margin / liquidation price / impact) from its order ticket — READ, never submit —
            # and attach it so the executor sizes with the broker's numbers. Budget-bounded.
            if os.environ.get("BROKER_ORDER_PREVIEW", "0") in ("1", "true", "TRUE", "yes") \
                    and time.monotonic() - t0 < budget * 0.8:
                try:
                    from trading.broker_sense import broker_features as bfeat
                    bkr = "binance" if self.market == "crypto" else "upstox"
                    _tp = time.monotonic()
                    sig["order_preview"] = bfeat.order_preview(bkr, s, self.sessions)
                    _vt["preview"] += time.monotonic() - _tp
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
        _verify_s = time.monotonic() - _ts_look_end
        rep["stages"]["verify"] = {"checked": len(app_signals), "tradeable": len(tradeable),
                                   **self.book.stats}
        # PERF: stage + VERIFY sub-call breakdown (seconds), so a slow cycle names its own hog.
        rep["stages"]["timing_s"] = {
            "screen": round(_ts_screen_end - t0, 1),
            "look": round(_ts_look_end - _ts_screen_end, 1),
            "verify": round(_verify_s, 1),
            "verify_by": {k: round(v, 1) for k, v in _vt.items() if v >= 0.05},
        }
        print(f"[funnel-timing:{self.market}:{segment}] screen={rep['stages']['timing_s']['screen']}s "
              f"look={rep['stages']['timing_s']['look']}s verify={rep['stages']['timing_s']['verify']}s "
              f"verify_by={rep['stages']['timing_s']['verify_by']} checked={len(app_signals)}", flush=True)

        # 4a ── EXPLORE-WIDE lane (owner 2026-07-07: "max trades is unlimited — why so few
        # opening?"): in paper explore, every OTHER screened candidate the broker pickers
        # surfaced also becomes tradeable with an honest LIGHT signature (lane + the
        # broker's own change% → direction; light:true marks that the deep lenses didn't
        # run). Explore entries take the fast path in the executor — they only need a
        # direction — so breadth costs ~one /forceenter each, while the budget-adaptive
        # deep shortlist above keeps the expensive lenses bounded. Crypto only (the NSE
        # branch needs the deep `directions`); cap via BROKER_SENSE_EXPLORE_WIDE_N
        # (default 16, 0 disables). Fully journaled like every explore entry (#13).
        if _explore and self.market == "crypto":
            try:
                wide_n = int(os.environ.get("BROKER_SENSE_EXPLORE_WIDE_N", "16") or 0)
            except ValueError:
                wide_n = 16
            have = set(app_signals) | open_syms
            # Cross-segment blindness fix (2026-07-07): a pair open in the OTHER segment
            # (same one-engine Freqtrade) must not be re-picked here — re-entering it is
            # a no-op forceenter that wastes the slot and inflates `entered`. Compare in
            # FLAT form (BEL/USDT vs BEL/USDT:USDT are the same book).
            import re as _re

            def _flt(p):
                return _re.sub(r"[^A-Z0-9]", "", (p or "").split(":", 1)[0].upper())
            open_flat = {_flt(p) for p in open_syms}
            try:
                _cli = self.executor(segment).client()
                for _sg in ("futures", "spot"):
                    if _sg != segment:
                        open_flat |= {_flt(p) for p in
                                      (_cli.open_pairs(segment=_sg) or [])}
            except Exception:
                pass
            wide = []
            for r in rows:
                if len(wide) >= wide_n:
                    break
                s = r.get("symbol")
                if not s or s in have or _flt(s) in open_flat:
                    continue
                lane = str(r.get("lane") or "")
                direction = "short" if ("loser" in lane or "short" in lane) else "long"
                try:
                    if r.get("change") is not None:
                        direction = "long" if float(r["change"]) >= 0 else "short"
                except Exception:
                    pass
                app_signals[s] = {"light": True,
                                  "vote": {"direction": direction, "p_up": None},
                                  "screener": {k: r.get(k) for k in
                                               ("lane", "preset", "change", "volume")}}
                tradeable.append(s)
                wide.append(s)
                have.add(s)
            rep["stages"]["explore_wide"] = {"added": len(wide), "cap": wide_n}

        # 4b ── SMART-MONEY SCOUTS + CONSENSUS (W4, owner goal 2026-07-07): named scouts
        # sweep the eyes' captures + this cycle's fusion; Sophie fires only on multi-scout
        # agreement; a fresh consensus for a symbol rides its app_signals (advisory boost,
        # recorded in decision_snapshot like every other lens). Ross alerts; never trades.
        try:
            from trading import scouts as _scouts
            _scouts.run_all(app_signals)
            for _s in list(app_signals):
                _c = _scouts.consensus_for(_s)
                if _c and isinstance(app_signals.get(_s), dict):
                    app_signals[_s]["smart_money_consensus"] = _c
        except Exception as e:
            rep["stages"]["scouts_error"] = f"{type(e).__name__}: {e}"[:100]

        # 5 ── DECIDE + EXECUTE (APIs only, owner's step 8)
        if self.market == "crypto":
            ex = self.executor(segment)
            ex._symbols = sorted(set(tradeable) | open_syms)   # shortlist-only universe
            ex.extra_signals = app_signals                     # → decision_snapshot.app_signals
            # Unlimited mode: the executor gets a FRESH wall-clock budget measured from NOW (not
            # t0), so a slow wide LOOK/fusion stage can never starve it — it always has time to
            # evaluate + OPEN across the whole universe. (2026-07-11: entered=[] because the
            # 281-symbol LOOK ate the t0+300 budget before execute ran.)
            if _unlimited_opens():
                exec_deadline = time.monotonic() + _unlimited_budget()
            else:
                exec_deadline = t0 + budget
            res = ex.run_once(allow_live=allow_live, deadline=exec_deadline)
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

        # 5a ── UI CRAWL (owner goal 2026-07-07, #10/#11): walk the eyes across a few due
        # symbol pages so the app's OWN kline/depth XHRs land in interception → ui_data.
        # BOTH apps get equal coverage (owner: Binance AND Upstox) — crypto→binance,
        # NSE→upstox. Budget-tail slot, never blocks entry.
        if os.environ.get("UI_CRAWL", "1") in ("1", "true", "TRUE", "yes"):
            try:
                from trading.broker_sense import tab_pool, ui_crawl, ui_data
                _syms = sorted(set(tradeable) | open_syms)
                _broker = "binance" if self.market == "crypto" else "upstox"
                # PARKED TAB POOL (THE MOTTO 2026-07-12): one open tab per top-shortlist
                # symbol = the app's own WS streams klines/depth/mark continuously into
                # interception → ui_data/ui_market. This is what keeps fresh coverage
                # ≥80% so the UI-only governor flips ON and STAYS on. Open trades park
                # first — their data must never lapse.
                _prio = sorted(open_syms) + [s for s in tradeable if s not in open_syms]
                # ROLLING coverage (owner 2026-07-12): pass the FULL tradeable shortlist +
                # the open trades as PINS (permanent tabs). The pool slides a window across the
                # whole list, recycling tabs, so every traded symbol gets a fresh web-capture
                # within a sweep → UI-data coverage reaches the governor's flip threshold.
                # direction-collect wants (owner 2026-07-13): pin symbols the direction path
                # asked to collect ALL filters for, so their book/taker/OI/long-short stream in
                # for the next decision — the brain gathers every filter each trade, not just
                # whatever was already fresh. Fresh wants only (<10 min).
                _dwant = set()
                try:
                    import time as _t
                    from trading import state as _st
                    _mk = "nse" if _broker == "upstox" else "crypto"    # wanted file keyed by market
                    _w = (_st.load_json("direction_collect_wanted.json", {}) or {}).get(_mk, {})
                    _dwant = {s for s, ts in _w.items() if _t.time() - float(ts or 0) < 600}
                except Exception:
                    _dwant = set()
                rep["stages"]["tab_pool"] = tab_pool.get_pool(
                    self.sessions, _broker).ensure(_prio, deadline=t0 + budget * 1.1,
                                                   pins=set(open_syms) | _dwant)
                # serial crawl covers the LONG TAIL beyond the parked head
                rep["stages"]["ui_crawl"] = ui_crawl.crawl_once(
                    self.sessions, _syms, deadline=t0 + budget * 1.15, broker=_broker)
                # the GOVERNOR (owner's standing order): flip UI-only-data ON by itself
                # the moment capture coverage is provably warm — no human reminder.
                rep["stages"]["ui_only_governor"] = ui_data.maybe_auto_flip(_syms)
            except Exception as e:
                rep["stages"]["ui_crawl"] = {"error": f"{type(e).__name__}: {e}"[:100]}

        # 5b ── EVIDENCE LANE (W3, owner goal 2026-07-07): blind-baseline virtual entries +
        # skip counterfactuals + horizon resolution — rides THIS cycle's fused prices,
        # zero extra I/O (UI-only-data safe). Judgment must never break trading.
        try:
            from trading import evidence
            _ent = (rep["stages"].get("execute", {}) or {}).get("entered") or []
            evidence.observe_cycle(market=self.market, segment=segment,
                                   signals=app_signals, entered=list(_ent),
                                   vetoed=(rep["stages"].get("execute", {}) or {})
                                   .get("vetoed"))
        except Exception as e:
            rep["stages"]["evidence_error"] = f"{type(e).__name__}: {e}"[:100]

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
        # locked merge — the crypto and NSE funnels are separate PROCESSES writing this
        # same file; an unlocked read-modify-write clobbered the other market's tile
        state.update_json(_STATUS_FILE, {self.market: rep,
                                         f"{self.market}_shortlist_n": self.shortlist_n})
        return rep

    def _strategy_lens(self, symbol: str) -> dict:
        """Run the FULL institutional strategy library ensemble on `symbol` (owner: use ALL
        strategy features on trade-open). Every active strategy votes on the symbol's
        UI-captured candles; the net becomes a stackable directional lens. Cached decider;
        honest {available:False} when data/strategies are absent (never a fake number).

        PER-5m-BAR MEMO (2026-07-12 perf): the 239-strategy ensemble is bar-stable, so running
        it every cycle × every shortlist symbol blew the cycle budget to 303s (starving the tab
        pool → no coverage → governor never flips). Memoized on the symbol's 5m bar so it runs
        ONCE per bar per symbol; the rest of the cycles within that bar reuse it. STRATEGY_LENS_MEMO=0
        disables."""
        _memo = os.environ.get("STRATEGY_LENS_MEMO", "1") in ("1", "true", "TRUE", "yes")
        ck = (symbol, int(time.time() // 300))       # (symbol, 5m-bar epoch)
        if _memo:
            hit = self._strat_cache.get(ck)
            if hit is not None:
                return hit
        try:
            if self._strat_lib is None:
                from trading.crypto.freqtrade.brain_executor import LibraryBrainDecider
                self._strat_lib = LibraryBrainDecider()
            d = self._strat_lib.decide("CRYPTO", symbol, None, in_position=False)
            b = d.get("_brain") or {}
            longs, shorts = int(b.get("longs") or 0), int(b.get("shorts") or 0)
            n = longs + shorts
            if n == 0:
                res = {"available": False, "reason": b.get("reason", "no strategy votes")}
            else:
                net = longs - shorts
                direction = "long" if net > 0 else "short" if net < 0 else "neutral"
                # p_up: fraction of votes that were long, mapped around 0.5 → [0,1]
                p_up = round(0.5 + 0.5 * (net / n), 4)
                res = {"available": True, "direction": direction, "p_up": p_up,
                       "confluence": round(abs(net) / n, 4), "longs": longs, "shorts": shorts,
                       "net": net, "n_strategies": n, "top": b.get("top", []),
                       "action": d.get("action")}
            if _memo:
                if len(self._strat_cache) > 4000:    # bounded — clear rather than grow unbounded
                    self._strat_cache.clear()
                self._strat_cache[ck] = res
            return res
        except Exception as e:
            return {"available": False, "error": str(e)[:120]}

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
