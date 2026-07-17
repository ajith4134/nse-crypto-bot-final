"""run_funnel_loop.py — the Broker-Sense driver (replaces the wedged run_brain_loop).

Owner decision #5: the old crypto brain loop stays PAUSED; this loop is the one driver.
It keeps everything the old loop honored — boss obedience (pause/focus/segments), the
BrainLearningCycle, mind-events — but the universe scan now happens on the BROKERS'
servers and every cycle completes inside its budget (saver I).

Saver C — event-driven, not polling: the loop sleeps to the NEXT 5-MINUTE CANDLE CLOSE
(plus a small settle delay) instead of a blind fixed timer; work happens exactly when new
bars exist. Markets: crypto always; NSE only inside exchange hours (BROKER_SENSE_NSE=1).

    python -m trading.broker_sense.run_funnel_loop
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import time

_BAR_S = 300
_SETTLE_S = 5.0


def _next_bar_close() -> float:
    now = time.time()
    return (int(now // _BAR_S) + 1) * _BAR_S + _SETTLE_S


def _nse_open() -> bool:
    ist = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
    if ist.weekday() >= 5:
        return False
    hm = ist.hour * 60 + ist.minute
    return 9 * 60 + 15 <= hm <= 15 * 60 + 30


_LAST_STAGES: dict = {}   # per-iteration stage timings (see the loop-period profiler)


def main() -> int:
    from trading.brain import boss, mind_events
    from trading.broker_sense.funnel import BrokerSenseFunnel
    from trading.broker_sense.sessions import get_sessions
    from trading.crypto.freqtrade.brain_learning import BrainLearningCycle
    from trading.crypto.freqtrade.config_template import enabled_segments

    allow_live = os.environ.get("CRYPTO_ALLOW_LIVE", "") in ("1", "true", "TRUE", "yes")
    do_nse = os.environ.get("BROKER_SENSE_NSE", "1") in ("1", "true", "TRUE", "yes")
    # SEPARATE LOOPS (2026-07-07): NSE and crypto run in their OWN processes so a slow
    # crypto cycle (seen blowing 120s→2455s) can NEVER starve NSE — previously they
    # shared one sequential loop and NSE never got its turn during market hours, so no
    # NSE trades opened. Select this process's markets with BROKER_SENSE_MARKETS
    # (e.g. "nse" or "crypto"); default = both (back-compat single-process mode).
    # markets from CLI arg (visible to pgrep for per-market idempotency) or env
    want = (sys.argv[1] if len(sys.argv) > 1 else "") or os.environ.get("BROKER_SENSE_MARKETS", "")
    want_set = {m.strip().lower() for m in want.split(",") if m.strip()} or {"crypto", "nse"}
    sessions = get_sessions()
    funnels: dict = {}
    if "crypto" in want_set:
        funnels["crypto"] = BrokerSenseFunnel("crypto", sessions)
    if "nse" in want_set and do_nse:
        funnels["nse"] = BrokerSenseFunnel("nse", sessions)
    learn = BrainLearningCycle()
    # OFF-HOT-PATH LEARNING (2026-07-12): the foundry (backtest/OOS scoring) + DEAP evolution +
    # meta-labeler retrain are CPU-heavy and used to run INLINE in the funnel loop — py-spy caught
    # strategy/generators+backtest+fitness in the MainThread, blocking per-symbol entries. Run them
    # on a dedicated daemon thread (interval-gated by maybe_run itself, browser-free by design) so
    # the entry cycle NEVER waits on evolution. The main loop just feeds it the latest entered syms.
    import threading as _threading
    _learn_ctx: dict = {"symbols": None}

    _pm_last = [0.0]                                  # post-mortem re-mine throttle (off hot path)

    def _learn_worker():
        from trading.direction import meta_labeler as _ml
        while True:
            try:
                ls = learn.maybe_run(symbols=_learn_ctx.get("symbols"))
                if ls:
                    print(f"[funnel-learn] cycle ran (off-thread): "
                          f"{(ls.get('learned') or {}).get('n_hypotheses')} hypotheses", flush=True)
                mt = _ml.maybe_train()               # D6 6-hourly retrain (also off the hot path)
                if mt:
                    print(f"[direction-meta] {mt}", flush=True)
                # POST-MORTEM re-mine (owner ask 2026-07-13): rebuild the winning/losing
                # trade-pattern rules + MFE/MAE excursion aggregates from the closed-trade
                # journal so the panel and the close-the-loop feedback stay fresh. Heavy
                # (pandas/pysubgroup, ~15s) → OFF the hot path here, throttled; the request
                # route only ever reads the state files this writes. POSTMORTEM_MINE_S tunes.
                _pmi = float(os.environ.get("POSTMORTEM_MINE_S", "1800") or 1800)
                if time.time() - _pm_last[0] >= _pmi:
                    _pm_last[0] = time.time()
                    try:
                        from trading.brain import postmortem as _pmod
                        if _pmod._enabled():
                            print(f"[postmortem] re-mined {_pmod.backfill()}", flush=True)
                    except Exception as e:
                        print(f"[postmortem] mine error: {e!r}", flush=True)
                # E1 OPE (2026-07-17): label matured vote-log rows HERE (this process owns
                # the mirror price history) and, on the OPE_EVERY_S cadence, spawn the
                # ISOLATED evaluation subprocess (candidate configs mutate LEARNED_DIR_*
                # env — doing that in-process would rewire the live decider mid-cycle).
                try:
                    from trading.direction import ope as _ope
                    _or = _ope.maybe_run()
                    if _or and (_or.get("label", {}).get("labeled")
                                or _or.get("evaluate")):
                        print(f"[ope] {_or}", flush=True)
                except Exception as e:
                    print(f"[ope] error: {e!r}", flush=True)
                # E4 lesson-prior distiller (2026-07-17): batched LLM read of fresh
                # closed-trade lessons → per-symbol direction prior table. One call per
                # LESSON_PRIOR_EVERY_S; the hot-path lens only ever reads the table.
                try:
                    from trading.direction import lesson_prior as _lp
                    _ld = _lp.maybe_distill()
                    if _ld and _ld.get("distilled"):
                        print(f"[lesson-prior] {_ld}", flush=True)
                except Exception as e:
                    print(f"[lesson-prior] error: {e!r}", flush=True)
                # E5 on-chain snapshot refresh (free keyless HTTP; the hot-path lens only
                # ever reads the cached state file).
                try:
                    from trading.direction import onchain_source as _ocs
                    _ocs.refresh()
                except Exception as e:
                    print(f"[onchain] error: {e!r}", flush=True)
                    # SYMBOL-MOVE NET (owner 2026-07-13): retrain the multi-head direction+move% net
                    # here (GatedMoENode fit ~seconds) so the per-candidate consult() only ever does a
                    # cheap forward pass — training NEVER touches the hot decision path (TabPFN lesson).
                    try:
                        from trading.brain import symbol_move_net as _smn
                        if _smn.enabled():
                            _si = _smn.refresh()
                            print(f"[symbol-move-net] trained dir_acc={_si.get('dir_oof_accuracy')} "
                                  f"move_mae%={_si.get('move_mae_pct')} n={_si.get('n_train')}", flush=True)
                    except Exception as e:
                        print(f"[symbol-move-net] train error: {e!r}", flush=True)
            except Exception as e:
                print(f"[funnel-learn] error: {e!r}", flush=True)
            time.sleep(float(os.environ.get("FUNNEL_LEARN_POLL_S", "30") or 30))

    _threading.Thread(target=_learn_worker, daemon=True, name="funnel-learn").start()
    if "crypto" in funnels:
        # Binance compute-offload (2026-07-11): start the all-market WS in-RAM mirror so the
        # universe scan + order-flow read off Binance's PUSHED data (RAM, ~0 CPU) instead of a
        # per-cycle ccxt fetch of ~400 tickers. Kill switch: BINANCE_STREAM=0. Best-effort.
        try:
            from trading.broker_sense.binance_stream import get_mirror
            get_mirror().start()
            print("[binance-mirror] all-market WS mirror started", flush=True)
        except Exception as e:
            print(f"[binance-mirror] start skipped: {e!r}", flush=True)
        # D3 FAST SWEEPER (2026-07-11): armed pullback entries wait for a retrace that
        # lives on second-scale, but funnel cycles are 20-40min when budgets overrun —
        # sampling the price once per cycle expired 7/8 armed entries without a single
        # trigger. This thread sweeps every PULLBACK_SWEEP_SEC (default 45s, 0=off)
        # using cached quotes/feathers; pullback.sweep pops each trigger under the
        # state-file lock so it can never double-enter with the in-cycle sweep.
        import threading

        def _pullback_sweeper(funnel):
            from trading.direction import pullback as _pb
            # R2 REFLEX LANE (owner-approved 2026-07-11): Binance bookTicker ticks
            # fire armed entries in SECONDS. reflex.run blocks for the funnel's
            # lifetime and returns only when REFLEX_LANE=0 or the websocket stack
            # is unavailable — the polling loop below stays as the honest fallback.
            try:
                from trading.direction import reflex as _rx
                _rx.run(funnel.executor, allow_live=allow_live)
                print("[reflex] lane off — polling fallback active", flush=True)
            except Exception as e:
                print(f"[reflex] lane failed ({e!r}) — polling fallback", flush=True)
            while True:
                try:
                    sec = float(os.environ.get("PULLBACK_SWEEP_SEC", "45") or 45)
                    if sec <= 0:
                        time.sleep(300)
                        continue
                    time.sleep(sec)
                    if not _pb.enabled():
                        continue
                    try:
                        if boss.is_paused("CRYPTO"):
                            continue
                    except Exception:
                        pass
                    armed = _pb.status().get("armed") or []
                    for seg in sorted({r.get("segment") or "futures" for r in armed}):
                        if seg not in ("futures", "spot"):
                            continue
                        r = funnel.executor(seg).sweep_pullbacks(allow_live=allow_live)
                        if r.get("entered") or r.get("queued"):
                            print(f"[pullback-sweep:{seg}] entered={r['entered']} "
                                  f"queued={r['queued']}", flush=True)
                except Exception as e:
                    print(f"[pullback-sweep] error: {e!r}", flush=True)
                    time.sleep(30)

        # Pin the sync-Playwright browser to THIS (main loop) thread before the sweeper starts,
        # so the reflex/sweeper thread can never claim it and trigger the greenlet cross-thread
        # crash (it degrades to the API path instead). See sessions.claim_browser_owner.
        sessions.claim_browser_owner()
        threading.Thread(target=_pullback_sweeper, args=(funnels["crypto"],),
                         daemon=True, name="pullback-sweeper").start()
    if "nse" in funnels:
        # NSE compute-offload (owner 2026-07-14): start the Zerodha Kite (KiteTicker) all-universe
        # WS in-RAM mirror so NSE SELECTION reads candles/quote/depth off the owner's PAID Zerodha
        # push feed (RAM, ~0 CPU) instead of a per-cycle OpenAlgo REST quote/depth — the exact
        # crypto pattern (binance_stream) with Zerodha in place of Binance. DATA ONLY: order
        # placement stays on the OpenAlgo/broker order API. Kill switch: KITE_STREAM=0. Idle no-op
        # when kiteconnect/creds are missing (callers keep their OpenAlgo fallback). Best-effort.
        try:
            from trading.broker_sense.kite_stream import get_kite_mirror
            from trading.screener.universe import NSE_FO_STOCKS
            km = get_kite_mirror()
            syms = list(NSE_FO_STOCKS)
            try:                                          # add the account watchlist if present
                from trading.broker_sense import account_watchlist
                wl = account_watchlist.status() or {}
                for r in (wl.get("items") or wl.get("watchlist") or wl.get("symbols") or []):
                    s = r.get("symbol") if isinstance(r, dict) else r
                    if s:
                        syms.append(str(s))
            except Exception:
                pass
            km.subscribe_symbols(syms)
            # ALSO stream the F&O contracts already held (exec_adapter only covers ones it places
            # from now on) — otherwise their MTM stays on OpenAlgo's REST-quote fallback, which
            # rate-limited Zerodha and hung positionbook. Runs before start() so they ride the
            # first subscribe batch.
            km.subscribe_held_contracts()
            km.start()
            print(f"[kite-mirror] status: {km.status()}", flush=True)
        except Exception as e:
            print(f"[kite-mirror] start skipped: {e!r}", flush=True)
    print(f"[funnel-loop] start: markets={sorted(funnels)} allow_live={allow_live} "
          f"budget={os.environ.get('BROKER_SENSE_BUDGET', '60')}s "
          f"(brokers' servers screen the universe; APIs execute only)", flush=True)
    mind_events.emit("learning", "Broker-Sense funnel loop started — I now pick trades by "
                     "reading the broker apps themselves", salience=0.7)
    cycle = 0
    # CONTINUOUS STREAM TICK (owner 2026-07-12, "make it ultra-advanced"): Playwright sync
    # only processes a parked tab's WebSocket frames when the owner thread touches that page,
    # so the funnel's long CPU brain-work (foundry/learning/study) starved the app's kline
    # streams → coverage lapsed, the UI-only governor never flipped, and the mirror froze.
    # This tick pumps every parked tab's queued frames (klines/depth → ui_data) + refreshes
    # the mirror, and is called at EVERY natural break in the cycle so streaming stays
    # continuous. Owner-thread only (Playwright is thread-bound); crypto only. Near-free.
    _last_stream = [0.0]
    _last_cg = [0.0]                                  # CoinGecko bulk-candle refresh throttle

    def _stream_tick(*, force: bool = False) -> None:
        if "crypto" not in funnels:
            return
        try:
            snap_s = float(os.environ.get("UI_TAB_SNAP_S", "20") or 20)
        except ValueError:
            snap_s = 20.0
        try:
            from trading.broker_sense import tab_pool
            pool = tab_pool.get_pool(sessions, "binance")
            pool.pump(budget_s=1.5)                       # process queued WS frames (cheap)
            if force or time.time() - _last_stream[0] >= snap_s:
                _last_stream[0] = time.time()
                pool.refresh(deadline=time.monotonic() + 6.0)   # snapshot + heal (mirror)
                # ADVANCE the rolling window (recycle tabs across the whole shortlist) so
                # UI-data coverage sweeps every traded symbol between cycles → governor flips.
                pool.roll(deadline=time.monotonic() + 8.0)
                try:
                    if sessions.guard_all_pages("binance"):     # CAPTCHA watchdog on all tabs
                        print("[handoff] challenge on an idle tab — take-control raised",
                              flush=True)
                except Exception:
                    pass
        except Exception as _e:
            print(f"[stream-tick] error: {_e!r}", flush=True)

    _iter_t0 = [time.monotonic()]          # start of the PREVIOUS iteration (for the true period)
    while True:
        cycle += 1
        # ITERATION PROFILER (2026-07-16). Five theories about the ~16-min cadence were wrong —
        # crawl, tournament, lane budget, "execute means placing orders", nav_brain — because every
        # one reasoned from the `took=` timer, which covers ONLY funnel.run_once(). It does NOT cover
        # the filter lane, the CoinGecko browser door, login/nav, or the sleep. So the gap was always
        # invisible to the number people were reading. This prints the TRUE iteration period and
        # attributes it, so the next question is answered by measurement instead of a plausible story.
        _now = time.monotonic()
        _period = _now - _iter_t0[0]
        _iter_t0[0] = _now
        _stage_t = {"_start": _now}
        if cycle > 1:
            print(f"[loop-period] cycle={cycle - 1} TOTAL={_period:.1f}s "
                  f"stages={ {k: round(v, 1) for k, v in _LAST_STAGES.items()} } "
                  f"unaccounted={_period - sum(_LAST_STAGES.values()):.1f}s", flush=True)
        _LAST_STAGES.clear()
        # BROWSER MEMORY CAP (2026-07-17, the VM wedge): restart any Chromium that has grown past
        # BROWSER_MAX_RSS_MB. Done HERE, at the top of the work half, on purpose — the cycle is
        # about to re-open its tabs anyway, so a restart costs nothing, whereas recycling during
        # the sleep half would kill the parked tabs _stream_tick() is pumping. The login survives
        # in the on-disk profile; tab_pool re-opens its tabs (it prunes closed pages already).
        try:
            _fat = sessions.recycle_fat_browsers()
            if _fat:
                print(f"[funnel-loop] recycled fat browser(s) {_fat} — RSS over the cap", flush=True)
        except Exception as _e:
            print(f"[funnel-loop] browser recycle error: {_e!r}", flush=True)
        for market, funnel in funnels.items():
            if market == "nse" and not _nse_open():
                continue
            mkt = "CRYPTO" if market == "crypto" else "NSE"
            try:
                if boss.is_paused(mkt):
                    continue
                # CPU SAVE (owner: "save computing power"): a market with EVERY segment turned off
                # does ZERO work this cycle — no login, no crawl, no screen/look/verify. Turning
                # segments off literally frees the cores for the segments you DO want.
                if not boss.active_segments(mkt):
                    continue
            except Exception:
                pass
            # GLOBAL segment focus (owner's dashboard toggles gate the whole brain): only run the
            # segments the boss/dashboard currently has ACTIVE. Turning a segment off stops the
            # funnel focusing on it (news/research/pickers honor the same active_segments list).
            try:
                active = set(boss.active_segments(mkt))
            except Exception:
                active = None
            segments = ["futures"]
            if market == "crypto":
                try:
                    segments = [s for s in enabled_segments()
                                if s in ("futures", "spot")] or ["futures"]
                except Exception:
                    segments = ["futures"]
            else:
                # HONOR ACTIVE SEGMENTS (owner 2026-07-16): the NSE funnel used to hardcode
                # ["equity"] and then intersect with active — so when the boss had NSE set to
                # futures-only (a real dashboard state), ["equity"] ∩ {"futures"} = [] and the
                # funnel silently did NOTHING (no cycle, no log). Run whichever active NSE segments
                # this funnel can EXECUTE (exec_adapter routes equity→NSE, futures/commodities→
                # near-month FUT on NFO/MCX, options→nearest-weekly ATM/OTM CE·PE on NFO/BFO).
                segments = ["equity", "futures", "commodities", "options"]
            if active is not None:
                servable = [s for s in segments if s in active]
                unserved = sorted(active - set(segments))
                if not servable and active:
                    # NEVER a silent all-skip (2026-07-10 rule): say WHY NSE opened nothing.
                    print(f"[funnel:{market}] cycle skipped — active segments {sorted(active)} "
                          f"not executable by the broker-sense funnel (serves {segments})",
                          flush=True)
                elif unserved:
                    print(f"[funnel:{market}] segments {unserved} active but not served here, "
                          f"running {servable}", flush=True)
                segments = servable
            # NAV_BRAIN=1 (2026-07-11): route the live browsing through the intelligent
            # Planner-Actor-Validator loop — navigate the Binance UI purposefully to the ACTIVE
            # segments (never an off one), self-correcting when stuck, instead of the dumb loop.
            # Guarded + bounded; a nav error never touches the trading cycle.
            if market == "crypto" and os.environ.get("NAV_BRAIN", "0") == "1":
                try:
                    from trading.broker_sense.nav_brain import from_human_ui
                    from trading.brain.vision.human_ui import HumanUI
                    _pg = sessions.page("binance")
                    if _pg is not None:
                        try:
                            _nb = from_human_ui(HumanUI(_pg), market="crypto")
                            _r = _nb.navigate("open and view the enabled crypto trading segments")
                            print(f"[nav_brain:crypto] {time.strftime('%H:%M:%S')} "
                                  f"steps={_r['steps']} replans={_r['replans']} "
                                  f"completed={_r['completed']} allowed={_r['allowed_segments']}",
                                  flush=True)
                        finally:
                            try:
                                _pg.close()                # sessions.page() opens a NEW tab → close it
                            except Exception:
                                pass
                except Exception as _e:
                    print(f"[nav_brain:crypto] error: {_e!r}", flush=True)
            for seg in segments:
                _stream_tick()                        # keep tabs streaming between segments
                try:
                    rep = funnel.run_cycle(segment=seg, allow_live=allow_live)
                    _stream_tick(force=True)          # pump right after the CPU-heavy scan
                    ex = rep["stages"].get("execute", {})
                    print(f"[funnel:{market}:{seg}] {time.strftime('%H:%M:%S')} "
                          f"screened={rep['stages']['screen']['surfaced']} "
                          f"shortlist={rep['stages']['heat']['shortlist']} "
                          f"non_neutral={rep['stages']['look']['non_neutral']} "
                          f"entered={ex.get('entered')} took={rep['took_s']}s "
                          f"(budget ok={rep['completed_within_budget']} "
                          f"next_n={rep['next_shortlist_n']}) "
                          # name the hog on the SAME line as took= — the [funnel-timing:] line is
                          # printed before execute/crawl run, so it can never explain an overrun
                          f"timing={rep['stages'].get('timing_s')}", flush=True)
                    # Binance-filter TOP-N breadth lane (Stage 1b, owner idea 2026-07-12): a
                    # PARALLEL candidate lane — rank the whole UI-captured universe by the active
                    # filter preset and open the adaptive top-N (side via learned_direction).
                    # Kill-switched (BINANCE_FILTER_LANE=0 → zero cost). Crypto only; never kills
                    # the loop. This is the motto-pure breadth fix for the 40-vs-10 collapse.
                    if market == "crypto":
                        try:
                            from trading.broker_sense import binance_filter_lane as _bfl
                            if _bfl.enabled():
                                # raised budget (owner 2026-07-13, lever 3): the parallel + fast lane
                                # can process the whole top-N, so give it a bigger slice than one cycle
                                # budget (FILTER_LANE_BUDGET_MULT, default 1.5×) to open the full breadth.
                                _flb = float(os.environ.get("BROKER_SENSE_BUDGET", "120") or 120) * \
                                    float(os.environ.get("FILTER_LANE_BUDGET_MULT", "1.5") or 1.5)
                                _flr = funnel.executor(seg).open_filter_lane(
                                    allow_live=allow_live,
                                    deadline=time.monotonic() + _flb)
                                if _flr.get("entered") or _flr.get("error"):
                                    print(f"[filter-lane:{market}:{seg}] "
                                          f"preset={_flr.get('preset')} "
                                          f"ranked={_flr.get('ranked')} "
                                          f"entered={_flr.get('entered')} "
                                          f"skipped={_flr.get('skipped')} "
                                          f"err={_flr.get('error')}", flush=True)
                        except Exception as _e:
                            print(f"[filter-lane:{market}:{seg}] error: {_e!r}", flush=True)
                        # B3 LENS PAPER LANE (2026-07-16): every orphaned lens trades under
                        # its own identity (enter_tag lens:<name>). Kill-switched LENS_LANE.
                        try:
                            from trading.brain import lens_lane as _lla
                            if _lla.enabled():
                                _llr = funnel.executor(seg).open_lens_lane(
                                    allow_live=allow_live)
                                if _llr.get("entered") or _llr.get("error"):
                                    print(f"[lens-lane:{market}:{seg}] "
                                          f"nominated={_llr.get('nominated')} "
                                          f"entered={_llr.get('entered')} "
                                          f"skipped={_llr.get('skipped')} "
                                          f"err={_llr.get('error')}", flush=True)
                        except Exception as _e:
                            print(f"[lens-lane:{market}:{seg}] error: {_e!r}", flush=True)
                except Exception as e:               # a cycle error never kills the loop
                    print(f"[funnel:{market}:{seg}] cycle error: {e!r}", flush=True)
            if market == "crypto":
                # OPTIONS/PREDICTION drivers (owner 2026-07-09: "the brain trades ALL the
                # segments I enabled on the dashboard"). These segments have dynamic
                # universes with their OWN cycle logic inside BrainExecutor.run_once —
                # they don't need the broker-picker shortlist — but since the funnel
                # replaced run_brain_loop as the crypto trade driver, NOTHING was driving
                # them: options was toggled ON yet never opened a trade. Drive them here.
                try:
                    extra = [s for s in enabled_segments()
                             if s in ("options", "prediction")]
                    # fail-CLOSED (2026-07-11): the optional drivers used to run UNGATED when
                    # active_segments couldn't be read (active=None → filter skipped), so options
                    # opened while toggled off. If the gate is unreadable, drive nothing optional.
                    extra = [s for s in extra if s in active] if active is not None else []
                    for seg in extra:
                        try:
                            # honest time box (2026-07-11): a model-heavy decide() in the
                            # options driver once held this loop 30+ min — extra segments
                            # get the same budget as a funnel cycle; the rest defers.
                            _bud = float(os.environ.get("BROKER_SENSE_BUDGET", "120") or 120)
                            _stream_tick()            # pump before the model-heavy options run
                            res = funnel.executor(seg).run_once(
                                allow_live=allow_live,
                                deadline=time.monotonic() + _bud)
                            _stream_tick(force=True)
                            # ALWAYS log (2026-07-10): silent all-skipped cycles previously
                            # looked identical to the driver being dead — 4.5h of "options
                            # opens nothing" was invisible because only non-empty cycles
                            # printed. Skip reasons make an empty cycle self-explaining.
                            print(f"[funnel:crypto:{seg}] "
                                  f"{time.strftime('%H:%M:%S')} "
                                  f"entered={res.get('entered')} "
                                  f"exited={res.get('exited')} "
                                  f"skipped={res.get('skipped')} "
                                  f"universe={res.get('universe')} "
                                  f"reasons={res.get('skip_reasons')}", flush=True)
                            # persist for the Brain Cockpit segment tiles (served by the
                            # engine's /api/v1/mlnb/funnel): "crypto:<seg>" key, same file
                            # the main funnel cycles report into.
                            try:
                                # locked merge — never clobber the other funnel process's tile
                                from trading import state as _st
                                _st.update_json("broker_sense_status.json", {f"crypto:{seg}": {
                                    "segment": seg, "ts": time.time(),
                                    "stages": {"execute": {
                                        "entered": res.get("entered"),
                                        "exited": res.get("exited"),
                                        "skipped": res.get("skipped"),
                                        "skip_reasons": res.get("skip_reasons"),
                                    }},
                                    "universe": res.get("universe"),
                                }})
                            except Exception:
                                pass
                        except Exception as e:
                            print(f"[funnel:crypto:{seg}] cycle error: {e!r}", flush=True)
                except Exception as e:
                    print(f"[funnel:crypto:extra-segments] error: {e!r}", flush=True)
            _stream_tick()                            # pump before watchlist/study block
            try:
                # BRAIN-OPEN mirror, IN-PROCESS (owner 2026-07-07 — the durable home the
                # start_all.sh note promised): this funnel OWNS its broker's chromium
                # profile, so IT mirrors open trades — crypto → Binance ⭐ Favorites,
                # NSE → the Upstox 'Brain-Open' watchlist. Fast no-op when in sync;
                # the account write stays gated behind BROKER_WATCHLIST_WRITE.
                if market == "crypto":
                    from trading.broker_sense import binance_watchlist as _bw
                    _wrep = _bw.apply_sync(sessions=funnel.sessions)
                else:
                    from trading.broker_sense import account_watchlist as _aw
                    _wrep = _aw.apply_sync(sessions=funnel.sessions)
                if _wrep.get("added") or _wrep.get("removed") or _wrep.get("error"):
                    print(f"[watchlist:{market}] added={_wrep.get('added')} "
                          f"removed={_wrep.get('removed')} err={_wrep.get('error')}",
                          flush=True)
            except Exception as e:
                print(f"[watchlist:{market}] error: {e!r}", flush=True)
            try:
                # W watchlist-study (Pillar 27): save this cycle's candidates to the
                # app watchlist (via the mirrors above), study each saved symbol
                # (multi-TF chart + micro lanes + regime → StudyReport + an
                # "app_study" Truth-Ledger claim), auto-drop when studied + gone.
                from trading.broker_sense import watchlist_study as _ws
                if _ws.enabled():
                    _f = funnels.get(market)
                    _cands = (((getattr(_f, "last", None) or {}).get("stages", {})
                               .get("look", {}) or {}).get("cands")) or []
                    _seg = ((getattr(_f, "last", None) or {}).get("segment")
                            or ("futures" if market == "crypto" else "intraday"))
                    _ws.propose(_cands, market=market, segment=_seg)
                    _sr = _ws.study_round(sessions=funnel.sessions, market=market)
                    if _sr.get("studied"):
                        print(f"[study:{market}] studied={_sr['studied']} "
                              f"claims={_sr['claims']}", flush=True)
            except Exception as e:
                print(f"[study:{market}] error: {e!r}", flush=True)
            _stream_tick(force=True)                  # pump + snapshot after the study block
        try:                                          # W8: one morning briefing per IST day
            from trading.brain import briefing
            if briefing.due():
                b = briefing.generate()
                print(f"[briefing] morning brief {b.get('date')} delivered "
                      f"({len(b.get('sections') or {})} sections)", flush=True)
        except Exception as e:
            print(f"[briefing] error: {e!r}", flush=True)
        try:                                          # feed the OFF-THREAD learner its symbols
            _lead = funnels.get("crypto") or funnels.get("nse")
            _learn_ctx["symbols"] = (list(((_lead.last if _lead else {}).get("stages", {})
                                           .get("execute", {}) or {}).get("entered") or [])
                                     or None) if _lead else None
        except Exception:
            pass
        # COINGECKO BULK-CANDLE DOOR (owner 2026-07-12): the only web source of BULK multi-bar
        # candles — 168 hourly points × up to 500 coins per refresh → the candle door gains a broad
        # HOURLY series for hundreds of symbols so far MORE become direction-readable + tradeable
        # (Binance web gives only 1 bar/symbol in bulk). Owner-thread (browser); slow cadence
        # (COINGECKO_REFRESH_S, default 1800s — the sparkline only updates every ~6h). Crypto only.
        if "crypto" in funnels and time.time() - _last_cg[0] >= float(
                os.environ.get("COINGECKO_REFRESH_S", "1800") or 1800):
            _last_cg[0] = time.time()
            try:
                from trading.broker_sense import coingecko_feed as _cg
                _cgr = _cg.refresh(sessions, deadline=time.monotonic() + 30.0)
                print(f"[coingecko] bulk-candle door: fed={_cgr.get('fed')} "
                      f"pages={_cgr.get('pages')} err={_cgr.get('errors')}", flush=True)
            except Exception as _e:
                print(f"[coingecko] error: {_e!r}", flush=True)
        try:                                          # D1 Truth Ledger (Pillar 27): resolve due
            from trading.direction import truth_ledger    # claims each cycle — cheap (15s budget),
            tr = truth_ledger.tick(budget_s=15)           # stays inline so labels stay fresh
            if tr.get("resolved") or tr.get("expired"):
                print(f"[direction-truth] resolved={tr['resolved']} "
                      f"pending={tr['still_pending']} expired={tr['expired']}",
                      flush=True)
        except Exception as e:
            print(f"[direction-truth] error: {e!r}", flush=True)
        # saver C: sleep to the next bar close — but poll every ~2s so that when the operator
        # opens a Live-Browser login we hand over the shared Chromium profile promptly (one
        # process per profile) instead of colliding for a whole cycle. Release runs here, on the
        # loop's OWN thread (Playwright sync contexts are thread-bound).
        # everything above = the WORK half of the iteration; everything below = the SLEEP half.
        # Splitting them settles the question directly: if TOTAL-work is large, the loop is idling to
        # the next bar close (a pacing choice, not a bottleneck); if work is large, profile the work.
        _LAST_STAGES["work"] = time.monotonic() - _stage_t["_start"]
        _sleep_t0 = time.monotonic()
        _deadline = max(time.time() + 2.0, _next_bar_close())
        while True:
            try:
                _rel = sessions.release_if_login_locked()
                if _rel:
                    print(f"[funnel-loop] yielded profile(s) {_rel} to operator login", flush=True)
            except Exception as _e:
                print(f"[funnel-loop] release check error: {_e!r}", flush=True)
            # CONTINUOUS STREAM + CAPTCHA WATCHDOG (2026-07-12): pump the parked tabs' WS
            # frames every poll (so klines/depth keep flowing into ui_data through the whole
            # sleep), snapshot on the UI_TAB_SNAP_S cadence (mirror keeps moving), and scan
            # every tab for a challenge (take-control comes up within ~2s of a popup).
            _stream_tick()
            _remain = _deadline - time.time()
            if _remain <= 0:
                break
            time.sleep(min(2.0, _remain))
        _LAST_STAGES["sleep_to_bar"] = time.monotonic() - _sleep_t0


if __name__ == "__main__":
    sys.exit(main())
