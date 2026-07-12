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
    print(f"[funnel-loop] start: markets={sorted(funnels)} allow_live={allow_live} "
          f"budget={os.environ.get('BROKER_SENSE_BUDGET', '60')}s "
          f"(brokers' servers screen the universe; APIs execute only)", flush=True)
    mind_events.emit("learning", "Broker-Sense funnel loop started — I now pick trades by "
                     "reading the broker apps themselves", salience=0.7)
    cycle = 0
    while True:
        cycle += 1
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
                segments = ["equity"]
            if active is not None:
                segments = [s for s in segments if s in active]
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
                try:
                    rep = funnel.run_cycle(segment=seg, allow_live=allow_live)
                    ex = rep["stages"].get("execute", {})
                    print(f"[funnel:{market}:{seg}] {time.strftime('%H:%M:%S')} "
                          f"screened={rep['stages']['screen']['surfaced']} "
                          f"shortlist={rep['stages']['heat']['shortlist']} "
                          f"non_neutral={rep['stages']['look']['non_neutral']} "
                          f"entered={ex.get('entered')} took={rep['took_s']}s "
                          f"(budget ok={rep['completed_within_budget']} "
                          f"next_n={rep['next_shortlist_n']})", flush=True)
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
                            res = funnel.executor(seg).run_once(
                                allow_live=allow_live,
                                deadline=time.monotonic() + _bud)
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
        _deadline = max(time.time() + 2.0, _next_bar_close())
        _last_tab_refresh = 0.0
        _last_captcha_scan = 0.0
        while True:
            try:
                _rel = sessions.release_if_login_locked()
                if _rel:
                    print(f"[funnel-loop] yielded profile(s) {_rel} to operator login", flush=True)
            except Exception as _e:
                print(f"[funnel-loop] release check error: {_e!r}", flush=True)
            # CAPTCHA WATCHDOG on EVERY open tab (2026-07-12): a Binance security check on an
            # IDLE tab (options/parked tab the driver opened + left) was invisible to the
            # per-action guard, so the operator never got a solve window. Scan all tabs each
            # poll so the take-control banner + noVNC come up within ~2s of the popup.
            if time.time() - _last_captcha_scan >= float(
                    os.environ.get("HANDOFF_CHECK_S", "4") or 4):
                _last_captcha_scan = time.time()
                for _bkr in ("binance", "upstox"):
                    try:
                        if sessions.guard_all_pages(_bkr):
                            print(f"[handoff] challenge detected on an idle {_bkr} tab — "
                                  f"take-control raised", flush=True)
                    except Exception as _e:
                        print(f"[handoff] scan error: {_e!r}", flush=True)
            # KEEP THE PARKED TABS WARM between cycles (2026-07-12): the per-cycle
            # tab_pool.ensure() runs at the tail of the budget with no time to snap, so
            # the mirror froze during the 5-min sleep and the app's kline/depth streams
            # lapsed. Snapshot + heal the parked tabs here on the OWNER thread (Playwright
            # is thread-bound) every ~UI_TAB_SNAP_S so the eyes keep MOVING and the streams
            # stay live → the UI-only governor can actually reach fresh coverage.
            if "crypto" in funnels and time.time() - _last_tab_refresh >= float(
                    os.environ.get("UI_TAB_SNAP_S", "20") or 20):
                _last_tab_refresh = time.time()
                try:
                    from trading.broker_sense import tab_pool
                    _tr = tab_pool.get_pool(sessions, "binance").refresh(
                        deadline=time.monotonic() + 8.0)
                    if _tr.get("snapped") or _tr.get("healed"):
                        print(f"[tab-pool] refresh snapped={_tr['snapped']} "
                              f"healed={_tr['healed']} dead={_tr['dead']}", flush=True)
                except Exception as _e:
                    print(f"[tab-pool] refresh error: {_e!r}", flush=True)
            _remain = _deadline - time.time()
            if _remain <= 0:
                break
            time.sleep(min(2.0, _remain))


if __name__ == "__main__":
    sys.exit(main())
