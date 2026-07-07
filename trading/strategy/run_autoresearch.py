"""trading/strategy/run_autoresearch.py — daemon entry for the live autoresearch loop.

    .venv/bin/python -m trading.strategy.run_autoresearch

Runs autoresearch.run_cycle() every AUTORESEARCH_INTERVAL_S seconds (default 900) at low
CPU priority (nice) so it never starves the funnels/Freqtrade — the researcher is a
background scientist, not a hot path. One cycle per interval; a long cycle simply delays
the next (no overlap). Ctrl-C / SIGTERM exit cleanly."""
from __future__ import annotations

import logging
import os
import signal
import sys
import time

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("autoresearch.daemon")

_STOP = False


def _sig(_signum, _frame):
    global _STOP
    _STOP = True


def main() -> int:
    try:
        os.nice(10)                      # background scientist: yield to the trade loops
    except Exception:
        pass
    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)
    from trading.strategy import autoresearch
    interval = autoresearch._cfg_int("AUTORESEARCH_INTERVAL_S", 900)  # shared safe parse
    log.info("live autoresearch driver up (interval=%ss, nice=10)", interval)
    while not _STOP:
        try:
            rec = autoresearch.run_cycle()
            log.info("[autoresearch] cycle %s: %s tested=%s admitted=%s took=%ss",
                     rec.get("cycle"), rec.get("result"), rec.get("tested"),
                     rec.get("admitted"), rec.get("took_s"))
        except Exception:
            log.exception("cycle crashed (driver continues)")
        for _ in range(max(1, interval)):
            if _STOP:
                break
            time.sleep(1)
    log.info("autoresearch driver stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
