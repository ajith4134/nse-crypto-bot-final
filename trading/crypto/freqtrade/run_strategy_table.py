"""trading/crypto/freqtrade/run_strategy_table.py — daemon for the per-coin best-strategy table.

    .venv/bin/python -m trading.crypto.freqtrade.run_strategy_table

Runs strategy_table.refresh() every STRATEGY_TABLE_INTERVAL_S seconds (default 300 = one 5m bar) at
low CPU priority (nice) so the expensive per-coin tournament NEVER runs in the live entry path — the
breadth lane + the Strategy column read the persisted table O(1). One pass per interval; a long pass
just delays the next (no overlap). Ctrl-C / SIGTERM exit cleanly. Kill-switch: STRATEGY_TABLE=0
(honored by start_all + loop_keeper so it isn't respawned)."""
from __future__ import annotations

import logging
import os
import signal
import sys
import time

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("strategy_table.daemon")

_STOP = False


def _sig(_signum, _frame):
    global _STOP
    _STOP = True


def main() -> int:
    try:
        os.nice(10)                      # background teacher: yield to the trade loops
    except Exception:
        pass
    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)
    from trading.crypto.freqtrade import strategy_table
    interval = strategy_table._cfg_int("STRATEGY_TABLE_INTERVAL_S", 300)
    log.info("strategy-table driver up (interval=%ss, nice=10)", interval)
    while not _STOP:
        try:
            rec = strategy_table.refresh()
            log.info("[strategy_table] pass: updated=%s/%s open=%s table=%s took=%ss",
                     rec.get("updated"), rec.get("attempted"), rec.get("open_coins"),
                     rec.get("table_size"), rec.get("took_s"))
        except Exception:
            log.exception("refresh crashed (driver continues)")
        for _ in range(max(1, interval)):
            if _STOP:
                break
            time.sleep(1)
    log.info("strategy-table driver stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
