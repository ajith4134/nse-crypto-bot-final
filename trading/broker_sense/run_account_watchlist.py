"""trading/broker_sense/run_account_watchlist.py — keep the Upstox 'Brain-Open' watchlist
in sync with the open trades, on a loop, in its OWN headed process.

Runs a HEADED browser (auto-Xvfb) because Upstox Pro won't render headless, and drives the
watchlist via the human-UI vision engine (trading/broker_sense/account_watchlist.apply_sync).
Isolated in its own process so the (heavier) headed browser never blocks the trade loops or
the dashboard. Only works during NSE market hours + when the Upstox login is live; each cycle
retries, so a transient vision-provider rate-limit or an expired login self-heals honestly
next cycle (the status file records the reason for the dashboard).

    BROKER_SENSE_HEADED=1 BROKER_WATCHLIST_WRITE=1 python -m trading.broker_sense.run_account_watchlist
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import time


def _nse_open() -> bool:
    ist = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
    if ist.weekday() >= 5:
        return False
    hm = ist.hour * 60 + ist.minute
    return 9 * 60 + 10 <= hm <= 15 * 60 + 35        # a little padding around the session


def main() -> int:
    os.environ.setdefault("BROKER_SENSE_HEADED", "1")     # this loop MUST render Upstox
    from trading.broker_sense import account_watchlist as aw
    from trading.broker_sense.sessions import get_sessions

    period = float(os.environ.get("ACCOUNT_WATCHLIST_PERIOD_S", "120"))
    write = os.environ.get("BROKER_WATCHLIST_WRITE") in ("1", "true", "TRUE", "yes")
    print(f"[acct-watchlist] start: watchlist={aw.WATCHLIST_NAME} write_enabled={write} "
          f"period={period}s (headed Upstox via Xvfb; syncs to open trades)", flush=True)
    sessions = get_sessions()
    while True:
        try:
            if _nse_open():
                rep = aw.apply_sync(sessions=sessions)
                print(f"[acct-watchlist] {time.strftime('%H:%M:%S')} "
                      f"added={rep.get('added')} removed={rep.get('removed')} "
                      f"login_ok={rep.get('login_ok')} err={rep.get('error')}", flush=True)
            else:
                # market closed → don't spin the browser; just refresh the desired-state view
                aw.status()
        except Exception as e:
            print(f"[acct-watchlist] cycle error: {e!r}", flush=True)
        time.sleep(period)


if __name__ == "__main__":
    sys.exit(main())
