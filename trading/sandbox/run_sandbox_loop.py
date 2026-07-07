"""trading/sandbox/run_sandbox_loop.py — drive the fast paper sandbox on a short interval.

The brain's fast learning lane (owner's decision): while Freqtrade is OFF, the brain trades in the
lightweight sandbox so it can open many trades quickly and learn. Each tick is ~1-2s (no per-coin
backtest). Interval via SANDBOX_INTERVAL (default 20s). Only trades when the sandbox is ENABLED.

    python -m trading.sandbox.run_sandbox_loop
"""
from __future__ import annotations

import os
import time


def main() -> int:
    from trading.sandbox.paper_sandbox import get_sandbox
    interval = float(os.environ.get("SANDBOX_INTERVAL", "20"))
    print(f"[sandbox-loop] start: interval={interval}s (trades only when enabled)", flush=True)
    while True:
        t0 = time.monotonic()
        try:
            sb = get_sandbox()
            if sb.enabled:
                rep = sb.tick()
                if rep.get("opened") or rep.get("closed"):
                    print(f"[sandbox] cycle {rep['cycle']} opened={rep['opened']} "
                          f"closed={rep['closed']} open_now={rep['open_now']} "
                          f"equity={rep['equity']}", flush=True)
        except Exception as e:
            print(f"[sandbox] cycle error: {type(e).__name__}: {e}"[:200], flush=True)
        time.sleep(max(3.0, interval - (time.monotonic() - t0)))


if __name__ == "__main__":
    raise SystemExit(main())
