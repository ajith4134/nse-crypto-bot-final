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
                    if active is not None:
                        extra = [s for s in extra if s in active]
                    for seg in extra:
                        try:
                            res = funnel.executor(seg).run_once(allow_live=allow_live)
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
        try:                                          # W8: one morning briefing per IST day
            from trading.brain import briefing
            if briefing.due():
                b = briefing.generate()
                print(f"[briefing] morning brief {b.get('date')} delivered "
                      f"({len(b.get('sections') or {})} sections)", flush=True)
        except Exception as e:
            print(f"[briefing] error: {e!r}", flush=True)
        try:                                          # the closed learning loop, unchanged
            _lead = funnels.get("crypto") or funnels.get("nse")
            ls = learn.maybe_run(symbols=list(((_lead.last if _lead else {}).get("stages", {})
                                               .get("execute", {}) or {}).get("entered")
                                              or []) or None) if _lead else None
            if ls:
                print(f"[funnel-learn] cycle ran: "
                      f"{(ls.get('learned') or {}).get('n_hypotheses')} hypotheses", flush=True)
        except Exception as e:
            print(f"[funnel-learn] error: {e!r}", flush=True)
        time.sleep(max(2.0, _next_bar_close() - time.time()))    # saver C: bar-close trigger


if __name__ == "__main__":
    sys.exit(main())
