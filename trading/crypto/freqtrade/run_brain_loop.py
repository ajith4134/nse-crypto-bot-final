"""run_brain_loop.py — the missing driver: run the brain→Freqtrade entry/exit loop.

This is what was absent. MlBridgeStrategy emits NO automatic entries (by design); entries are
driven over REST /forceenter by the brain ensemble (BrainExecutor). Pressing the Freqtrade "start"
button only sets the bot RUNNING — it does not start this loop, so no trades ever opened.

Paper by default. Set CRYPTO_ALLOW_LIVE=1 to permit live entries (the engine still enforces its own
live guard). Interval via BRAIN_LOOP_SEC (default 60s). Logs each cycle; honest — never fakes fills.

    python -m trading.crypto.freqtrade.run_brain_loop
"""
from __future__ import annotations

import os
import sys
import time

from trading.crypto.freqtrade.brain_executor import BrainExecutor
from trading.crypto.freqtrade.brain_learning import BrainLearningCycle
from trading.crypto.engine_client import CryptoEngineClient


def main() -> int:
    interval = float(os.environ.get("BRAIN_LOOP_SEC", "60"))
    allow_live = os.environ.get("CRYPTO_ALLOW_LIVE", "") in ("1", "true", "TRUE", "yes")
    cli = CryptoEngineClient()
    # The closed learning loop: learn from real outcomes (hypothesis ledger) + research online
    # (ddgs+LLM) + imagine (world-model MCTS), interval-gated (BRAIN_LEARN_SEC, default 900s).
    # Its confirmed hypotheses feed back into the executor as an advisory entry veto.
    learn = BrainLearningCycle()
    # Multi-segment engine: one executor per enabled segment (futures/spot drive the full
    # per-coin brain; options/prediction use their dedicated cycle logic). The learner's
    # veto loop stays on futures — its hypotheses are built from that market's outcomes.
    from trading.brain import boss, mind_events, rnd
    from trading.crypto.freqtrade.config_template import enabled_segments
    segs = enabled_segments()
    executors = {seg: BrainExecutor(client=cli, learner=(learn if seg == "futures" else None),
                                    segment=seg) for seg in segs}
    bx = executors.get("futures") or next(iter(executors.values()))
    print(f"[brain-loop] start: interval={interval}s allow_live={allow_live} "
          f"segments={segs} learn_every={learn.interval}s", flush=True)
    cycle_n = 0
    while True:
        t0 = time.monotonic()
        cycle_n += 1
        # ── boss obedience (trading/brain/boss.py): the operator's chat commands become
        # directives this loop honors EVERY cycle — segments on/off, pause, focus, targets.
        try:
            active = [s for s in enabled_segments()
                      if boss.segment_enabled("CRYPTO", s) is not False]
            for s in ("futures", "spot", "options", "prediction"):
                if boss.segment_enabled("CRYPTO", s) and s not in active:
                    active.append(s)          # boss turned ON a segment beyond env config
            for s in active:
                if s not in executors:
                    executors[s] = BrainExecutor(
                        client=cli, learner=(learn if s == "futures" else None), segment=s)
            paused = boss.is_paused("CRYPTO")
            focus = boss.focus_of("CRYPTO")
        except Exception:
            active, paused, focus = list(executors), False, None
        for seg in active:
            ex = executors[seg]
            if paused:
                continue                       # boss paused entries; engine still manages exits
            if focus and seg != focus and cycle_n % 3:
                continue                       # focused segment runs every cycle, others 1-in-3
            try:
                res = ex.run_once(allow_live=allow_live)
                cnt = cli._client(seg).count() or {}
                # show which strategy the brain CHOSE for each coin it entered
                picks = res.get("picks") or {}
                chosen = ", ".join(f"{s.split('/')[0]}→{picks[s]['strategy']}"
                                   for s in res["entered"] if s in picks) or "—"
                veto = res.get("vetoes") or []
                print(f"[brain-loop:{seg}] {time.strftime('%H:%M:%S')} entered={res['entered']} "
                      f"exited={res['exited']} skipped={res['skipped']} "
                      f"open={cnt.get('current')}/{cnt.get('max')} picks[{chosen}]"
                      + (f" vetoed={veto}" if veto else ""), flush=True)
                # mind stream: credit the learning that OPENED each trade + boss progress
                try:
                    for sym in res["entered"]:
                        pk = picks.get(sym) or {}
                        mind_events.emit(
                            "trade_credit",
                            f"Opened {sym.split('/')[0]} {pk.get('action') or ''} on {seg} via "
                            f"{pk.get('strategy') or 'brain ensemble'}"
                            + (f" (p_win {pk.get('p_win')})" if pk.get("p_win") else ""),
                            salience=0.65, data={"symbol": sym, "segment": seg, **pk})
                    if len(veto) >= 5:
                        mind_events.emit(
                            "problem", f"{len(veto)} entries blocked by my gates on {seg} "
                            f"this cycle (UQ/psychology/hypotheses)", salience=0.55,
                            data={"segment": seg, "vetoed": veto[:10]})
                    boss.report_progress("CRYPTO", seg, int(cnt.get("current") or 0))
                except Exception:
                    pass
            except Exception as e:  # never die on a transient bot/API hiccup
                print(f"[brain-loop:{seg}] cycle error: {e!r}", flush=True)
                try:
                    mind_events.emit("problem", f"Brain-loop cycle error on {seg}: {e!r}"[:200],
                                     salience=0.7, data={"segment": seg})
                except Exception:
                    pass
        # CORTEX B8 trust feedback: closed trades → TrustLedger.update for the
        # experts that fired in the cortex signal (opt-in with CORTEX_SIGNAL=1).
        if os.environ.get("CORTEX_SIGNAL", "") in ("1", "true", "TRUE", "yes"):
            try:
                from trading.cortex_signal import apply_trust_feedback
                credited = apply_trust_feedback(cli.closed_trades())
                if credited:
                    print(f"[cortex-trust] credited {credited} closed trade(s) "
                          f"to the trust ledger", flush=True)
            except Exception as e:
                print(f"[cortex-trust] feedback error: {e!r}", flush=True)
        # Closed learning loop — self-gated by interval; never breaks execution.
        try:
            ls = learn.maybe_run(symbols=bx.symbols())
            if ls:
                lr = ls.get("learned") or {}
                imag = ls.get("imagined") or {}
                fdry = ls.get("foundry") or {}
                print(f"[brain-learn] {time.strftime('%H:%M:%S')} "
                      f"hypotheses={lr.get('n_hypotheses')} confirmed={lr.get('confirmed')} "
                      f"refuted={lr.get('refuted')} researched={len(ls.get('research') or [])} "
                      f"imagined={imag.get('action')}({imag.get('expected_R')}) "
                      f"foundry[specs={fdry.get('n_specs')} new={fdry.get('discovered')} "
                      f"tracked={fdry.get('tracked')}]", flush=True)
                try:
                    mind_events.emit(
                        "learning",
                        f"Learning cycle: {lr.get('n_hypotheses') or 0} hypotheses "
                        f"({lr.get('confirmed') or 0} confirmed / {lr.get('refuted') or 0} "
                        f"refuted), {len(ls.get('research') or [])} topics researched online, "
                        f"foundry tracking {fdry.get('tracked') or 0} strategies",
                        salience=0.6, data={"learned": lr, "foundry": fdry})
                    if fdry.get("discovered"):
                        mind_events.emit(
                            "discovery",
                            f"Strategy Foundry created {fdry['discovered']} NEW strategies "
                            f"this cycle — tracking their real performance now", salience=0.8)
                except Exception:
                    pass
        except Exception as e:
            print(f"[brain-learn] cycle error: {e!r}", flush=True)
            try:
                mind_events.emit("problem", f"Learning cycle error: {e!r}"[:200], salience=0.7)
            except Exception:
                pass
        # R&D drive: the brain INVENTS new functions/features (interval-gated; RND_LOOP=0 off)
        try:
            rnd.maybe_run()
        except Exception as e:
            print(f"[brain-rnd] cycle error: {e!r}", flush=True)
        # boss intensity: 2.0 = cycle twice as often (interval halves), floor 5s
        try:
            eff = interval / boss.intensity()
        except Exception:
            eff = interval
        time.sleep(max(5.0, eff - (time.monotonic() - t0)))


if __name__ == "__main__":
    sys.exit(main())
