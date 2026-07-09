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
    from trading.crypto.freqtrade.micro_policy import distill_once
    while True:
        try:
            rep = distill_once()
            print(f"[micro-distill] {time.strftime('%F %T')} {rep}", flush=True)
        except Exception as e:                   # noqa: BLE001 — daemon must survive anything
            print(f"[micro-distill] ERROR {type(e).__name__}: {e}", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
