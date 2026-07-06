"""trading/broker_sense/run_school_monitor.py — DEDICATED App-Driving-School learning monitor.

Owner directive (2026-07-06): stop trading, divert all CPU/RAM to the brain LEARNING both apps
(Binance + Upstox) to 100%. This loop drives repeated read-only explorations of each broker until
every market-data goal route is found (coverage 100%) or a broker plateaus (no new route for
PLATEAU_ROUNDS rounds — some goals may be genuinely un-exposed in the logged-in app).

Runs the brokers SEQUENTIALLY (one browser at a time — clean logs, no map-file write races). Each
round uses the full seed-sweep + full-site crawl. Progress is written to logs/app_school_monitor.log
and a machine-readable snapshot to trading/state/app_school_monitor.json so the dashboard / a
watching agent can report coverage without re-running anything.

    python -m trading.broker_sense.run_school_monitor [budget_s] [max_pages]
"""
from __future__ import annotations

import json
import sys
import time

from trading import state
from trading.broker_sense.app_school import DATA_GOALS, get_school, market_status

BROKERS = ["binance", "upstox"]
PLATEAU_ROUNDS = 4          # stop a broker after this many rounds with no new route learned
_SNAP = "app_school_monitor.json"
# a liquid, always-listed symbol per broker whose chart/depth/news/technicals tabs the brain
# opens like a human (populates the FeatureCatalog with REAL where=<url> per-symbol features).
PRIMARY_SYMBOL = {"binance": "BTC/USDT", "upstox": "RELIANCE"}


def _explore_symbol(broker: str) -> dict:
    """Live per-symbol tab crawl (owner ask 2026-07-06): open the primary symbol's chart/depth/
    news/technicals/option tabs and catalog every real feature + its page URL. Read-only,
    best-effort — never raises into the monitor loop."""
    try:
        from trading.broker_sense import app_explorer
        sym = PRIMARY_SYMBOL.get(broker)
        rep = app_explorer.explore(broker, get_school().sessions(), symbol=sym, max_tabs=6)
        return {"ok": rep.get("ok"), "n_new_features": rep.get("n_new_features", 0),
                "reason": rep.get("reason")}
    except Exception as e:
        return {"ok": False, "reason": f"{type(e).__name__}: {str(e)[:100]}"}


def _market_open(broker: str) -> bool:
    """Only explore a broker while its market is LIVE (shared helper: crypto 24/7, NSE 09:15–15:30
    IST) — the school learns from live traffic only, so after-hours there is nothing to classify."""
    return bool(market_status(broker)["open"])


def _coverage(broker: str) -> dict:
    return get_school().map.coverage(broker)


def _log(msg: str) -> None:
    print(f"[school-monitor {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    budget_s = float(sys.argv[1]) if len(sys.argv) > 1 else 240.0
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    _log(f"START — driving {BROKERS} to 100% (budget={budget_s}s/round, max_pages={max_pages})")
    done: dict = {b: False for b in BROKERS}          # reached 100% or plateaued
    stale: dict = {b: 0 for b in BROKERS}             # consecutive no-progress rounds
    rounds = 0
    while not all(done.values()):
        rounds += 1
        did_work = False
        for b in BROKERS:
            if done[b]:
                continue
            if not _market_open(b):
                _log(f"{b}: market CLOSED — waiting for the session to open (NSE 09:15–15:30 IST)")
                continue
            did_work = True
            before = set(get_school().map.routes.get(b, {}))
            t0 = time.monotonic()
            try:
                rep = get_school().explore(b, budget_s=budget_s, max_clicks=60,
                                           full_site=True, max_pages=max_pages)
            except Exception as e:
                _log(f"{b}: explore error {type(e).__name__}: {str(e)[:120]}")
                rep = {}
            after = set(get_school().map.routes.get(b, {}))
            new = sorted(after - before)
            cov = _coverage(b)
            # per-symbol tab crawl → live FeatureCatalog (chart/depth/news/technicals/option)
            fx = _explore_symbol(b)
            dur = round(time.monotonic() - t0)
            _log(f"{b}: round {rounds} +{dur}s | coverage {cov['pct']}% "
                 f"| learned {sorted(after)} | NEW {new} | missing {cov['missing']} "
                 f"| symbol-feats +{fx.get('n_new_features', 0)} ({PRIMARY_SYMBOL.get(b)}) "
                 f"| err={rep.get('error')}")
            if cov["pct"] >= 100:
                done[b] = True
                _log(f"{b}: ✅ 100% — every goal route learned")
            elif new:
                stale[b] = 0
            else:
                stale[b] += 1
                if stale[b] >= PLATEAU_ROUNDS:
                    done[b] = True
                    _log(f"{b}: ⏹ plateaued at {cov['pct']}% after {stale[b]} flat rounds — "
                         f"still missing {cov['missing']} (likely not exposed in the logged-in app)")
            _snapshot(rounds, done, stale)
        # if nothing ran this round (every remaining broker's market is closed), idle-sleep so we
        # don't busy-loop for hours — re-check every 5 min and auto-resume when a market opens.
        if not did_work and not all(done.values()):
            _log("all remaining markets closed — sleeping 5 min, will auto-resume when one opens")
            time.sleep(300)
    _log(f"DONE after {rounds} rounds: "
         + " · ".join(f"{b} {_coverage(b)['pct']}%" for b in BROKERS))
    _snapshot(rounds, done, stale, finished=True)
    return 0


def _snapshot(rounds: int, done: dict, stale: dict, *, finished: bool = False) -> None:
    school = get_school()
    try:
        from trading.broker_sense.app_explorer import get_catalog
        feats = get_catalog().status()               # per-symbol feature coverage (typed + URLs)
    except Exception:
        feats = {}
    snap = {"rounds": rounds, "finished": finished, "ts": time.time(),
            "brokers": {}}
    for b in BROKERS:
        cov = school.map.coverage(b)
        routes = school.map.routes.get(b, {})
        snap["brokers"][b] = {
            "coverage_pct": cov["pct"], "learned": cov["learned"], "missing": cov["missing"],
            "done": done[b], "stale_rounds": stale[b],
            "routes": {k: {"via": v.get("via"), "url": v.get("url"), "endpoint": v.get("endpoint")}
                       for k, v in routes.items()},
            "pages_known": len(school.map.pages.get(b, {})),
            "links_known": len(school.map.links.get(b, {})),
            "features": feats.get(b, {}),            # {n_features, n_with_url, by_kind, sample}
            "goals_total": len(DATA_GOALS.get(b, {}))}
    state.save_json(_SNAP, snap)


if __name__ == "__main__":
    raise SystemExit(main())
