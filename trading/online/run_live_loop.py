"""trading/online/run_live_loop.py — run the OnlineTrader live loop as its OWN process.

Why a separate process (2026-07-07): running the loop IN the dashboard starves the
GIL and wedges the HTTP server (memory: dashboard-524-wedge), so the dashboard runs
NO_LOOP=1 (viewer only). This runner is the NSE derivatives/options + equity paper
driver — it ticks the same LiveTradeLoop the dashboard controls read, but in isolation
so a heavy pricing tick can never block the UI. Pairs with the broker-sense funnel
(NSE equity) and the crypto funnel — three independent loops, none blocking another.

    python -m trading.online.run_live_loop
"""
from __future__ import annotations

import sys
import time


def main() -> int:
    from trading.online.live_loop import start_loop
    loop = start_loop()
    print(f"[live-loop] started (interval={getattr(loop, 'interval_s', '?')}s) — NSE "
          f"intraday/mtf/options + crypto paper driver; dashboard stays NO_LOOP viewer",
          flush=True)
    try:
        while True:                       # keep the daemon tick thread alive
            time.sleep(30)
            if not (getattr(loop, "_thread", None) and loop._thread.is_alive()):
                print("[live-loop] tick thread died — restarting", flush=True)
                loop = start_loop()
    except KeyboardInterrupt:
        loop.stop()
        return 0


if __name__ == "__main__":
    sys.exit(main())
