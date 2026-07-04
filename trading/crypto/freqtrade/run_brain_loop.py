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
    from trading.crypto.freqtrade.config_template import enabled_segments
    segs = enabled_segments()
    executors = {seg: BrainExecutor(client=cli, learner=(learn if seg == "futures" else None),
                                    segment=seg) for seg in segs}
    bx = executors.get("futures") or next(iter(executors.values()))
    print(f"[brain-loop] start: interval={interval}s allow_live={allow_live} "
          f"segments={segs} learn_every={learn.interval}s", flush=True)
    while True:
        t0 = time.monotonic()
        for seg, ex in executors.items():
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
            except Exception as e:  # never die on a transient bot/API hiccup
                print(f"[brain-loop:{seg}] cycle error: {e!r}", flush=True)
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
        except Exception as e:
            print(f"[brain-learn] cycle error: {e!r}", flush=True)
        time.sleep(max(5.0, interval - (time.monotonic() - t0)))


if __name__ == "__main__":
    sys.exit(main())
