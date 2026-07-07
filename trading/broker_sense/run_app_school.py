"""trading/broker_sense/run_app_school.py — run ONE App Driving School crawl in its own process.

Playwright's sync API is bound to the thread that created the browser; driving it from the
dashboard's ad-hoc daemon thread raises `greenlet.error: cannot switch to a different thread`.
So the dashboard spawns THIS as a subprocess (its own main thread + own browser) — the same
subprocess pattern the dashboard uses for strategy builds. Read-only; never places an order.

    python -m trading.broker_sense.run_app_school <broker> [budget_s] [max_pages]
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    broker = (sys.argv[1] if len(sys.argv) > 1 else "binance").lower()
    budget_s = float(sys.argv[2]) if len(sys.argv) > 2 else 150.0
    max_pages = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    from trading.broker_sense.app_school import get_school
    rep = get_school().explore(broker, budget_s=budget_s, max_clicks=40,
                               full_site=True, max_pages=max_pages)
    # compact machine-readable line for the caller (dashboard / monitor loop)
    out = {k: rep.get(k) for k in ("broker", "error", "new_pages", "new_links",
                                   "popups_closed", "clicked", "learned", "coverage",
                                   "pages_known", "links_known")}
    out["clicked"] = len(rep.get("clicked", []))
    print("APP_SCHOOL_RESULT " + json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
