"""trading/broker_sense/run_upstox_focus.py — drive the Upstox App School to 100%.

Owner order 2026-07-10: trading loops stopped; the browser belongs to LEARNING until
the Upstox map is complete. Runs one `run_app_school upstox` pass per SUBPROCESS (fresh
code each pass, same pattern as the dashboard button), logs coverage after each pass,
and stops on: 100% coverage, market close (NSE 15:30 IST), or a no-progress plateau.
Read-only throughout — the school never touches an order control.

    python -m trading.broker_sense.run_upstox_focus [budget_s_per_pass] [max_passes]
"""
from __future__ import annotations

import json
import subprocess
import sys
import time


def _coverage() -> dict:
    from trading.broker_sense.app_school import get_school
    school = get_school()
    school.map.reload()      # passes run in subprocesses — re-read their saved progress
    return school.map.coverage("upstox")


def _nse_open() -> bool:
    from trading.broker_sense.app_school import market_status
    try:
        return bool(market_status("upstox").get("open"))
    except Exception:
        return True


def _log(msg: str) -> None:
    print(f"[upstox-focus] {msg}", flush=True)


def main() -> int:
    budget_s = float(sys.argv[1]) if len(sys.argv) > 1 else 240.0
    max_passes = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    stale = 0
    for n in range(1, max_passes + 1):
        if not _nse_open():
            _log(f"NSE closed — stopping after pass {n - 1}. Resume at market open.")
            break
        before = _coverage()
        t0 = time.time()
        p = subprocess.run([sys.executable, "-m", "trading.broker_sense.run_app_school",
                            "upstox", str(budget_s), "60"],
                           capture_output=True, text=True, timeout=budget_s + 300)
        line = next((ln for ln in (p.stdout or "").splitlines()
                     if ln.startswith("APP_SCHOOL_RESULT ")), "")
        rep = {}
        if line:
            try:
                rep = json.loads(line.split(" ", 1)[1])
            except Exception:
                rep = {}
        after = _coverage()
        _log(f"pass {n}: {before.get('pct')}% → {after.get('pct')}% "
             f"(+{rep.get('new_pages', '?')} pages, +{rep.get('new_links', '?')} links, "
             f"learned={rep.get('learned')}, err={rep.get('error')}, "
             f"{round(time.time() - t0)}s)")
        if after.get("pct") == 100:
            _log("100% — Upstox map complete.")
            break
        stale = stale + 1 if after.get("pct") == before.get("pct") else 0
        if stale >= 3:
            _log(f"plateau at {after.get('pct')}% after 3 no-progress passes — stopping; "
                 "check broker_endpoints.json 'unknown' rows for missing needles.")
            break
    cov = _coverage()
    _log("FINAL " + json.dumps(cov, default=str)[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
