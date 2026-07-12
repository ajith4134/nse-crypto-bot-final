"""Nightly micro-policy distillation daemon (invent-beyond #4).

Runs the FULL per-coin strategy tournament off-cycle (nice priority) and refreshes the
distilled table + LightGBM student that give the funnel its ~ms decide() fast path.
First run fires immediately (a fresh box has no table), then every MICRO_DISTILL_INTERVAL_S
(default 24h). Errors never kill the loop — an honest error report lands in the state file
via micro_policy.status().

    .venv/bin/python -m trading.crypto.freqtrade.run_micro_distill
"""
from __future__ import annotations

import os
import time


def main() -> None:
    try:
        os.nice(10)                              # never compete with the funnel's cycle budget
    except Exception:
        pass
    interval = float(os.environ.get("MICRO_DISTILL_INTERVAL_S", str(24 * 3600)))
    # FAST RETRY (2026-07-12 perf fix): the distill's whole value is populating the ms fast-path
    # table. If it produces ZERO coins (engine API not reachable at boot — the historical failure
    # mode: every attempt logged "could not connect to :8080" then slept 24h, leaving the table
    # empty so ALL ~600 symbols fell through to the 7.5s teacher = the 400-538s scan), retry in
    # minutes, not a day — and skip the other heavy jobs until the fast-path actually exists.
    retry = float(os.environ.get("MICRO_DISTILL_RETRY_S", "300"))
    from trading.crypto.freqtrade.micro_policy import distill_once
    while True:
        ok = False
        try:
            rep = distill_once()
            ok = int(rep.get("coins", 0)) > 0
            print(f"[micro-distill] {time.strftime('%F %T')} {rep}", flush=True)
        except Exception as e:                   # noqa: BLE001 — daemon must survive anything
            print(f"[micro-distill] ERROR {type(e).__name__}: {e}", flush=True)
        if not ok:
            print(f"[micro-distill] no coins distilled — fast-path still empty; "
                  f"retrying in {retry:.0f}s (skip dream/challenger until it exists)", flush=True)
            time.sleep(retry)
            continue
        # Dream-Trainer phase-2 (2026-07-10): nightly world-model imagination replay of
        # the newest closed trades — MCTS per trade, so it lives HERE (nice-10, its own
        # process), never in the dashboard/learn thread. Kill-switch: DREAM_REPLAY=0.
        if os.environ.get("DREAM_REPLAY", "1") != "0":
            try:
                from trading.brain import dreamer
                sec = dreamer.imagine_replay()
                print(f"[dream-replay] {time.strftime('%F %T')} replayed="
                      f"{sec.get('n_replayed')} skipped={sec.get('n_skipped')} "
                      f"agreeR={sec.get('mean_R_when_agree')} "
                      f"disagreeR={sec.get('mean_R_when_disagree')}", flush=True)
            except Exception as e:               # noqa: BLE001
                print(f"[dream-replay] ERROR {type(e).__name__}: {e}", flush=True)
        # TradeOutcomeNet champion/challenger duel (de-stagnation #6, 2026-07-10): TabPFN-v2
        # vs the incumbent on the same OOF protocol — CPU-minutes, so it lives in this
        # nice-10 daemon (the module docstring's contract). Kill-switch: CHALLENGER_DUEL=0.
        if os.environ.get("CHALLENGER_DUEL", "1") != "0":
            try:
                from trading.brain import challenger
                rep = challenger.duel()
                print(f"[challenger] {time.strftime('%F %T')} "
                      f"verdict={rep.get('verdict')} "
                      f"champion={(rep.get('champion') or {}).get('engine')} "
                      f"champ_acc={(rep.get('champion') or {}).get('oof_accuracy')} "
                      f"chal_acc={(rep.get('challenger') or {}).get('oof_accuracy')}",
                      flush=True)
            except Exception as e:               # noqa: BLE001
                print(f"[challenger] ERROR {type(e).__name__}: {e}", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
