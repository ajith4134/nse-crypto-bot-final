"""Live per-trade watcher — grades every trade opened AFTER an experiment epoch.

Owner requirement (2026-07-17): after every experiment/change, check the LIVE trades that
open under it — per-trade direction grade vs subsequent price, sizing sanity, exit quality —
instead of only waiting for batch verdicts.

Run:  .venv/bin/python research/direction-brain-mission/live_watch.py [--epoch ISO]

Reads (read-only):
  - Freqtrade REST /status + /trades (creds from trading/crypto/freqtrade/config.json)
  - trading/state/journal.json           (closed trades, all lanes)
  - trading/state/profit_tailgate_locks.json

Prints one compact report:
  [OPEN]  every trade opened since epoch: tag, side, age, current profit %, live grade
  [CLOSED] every close since epoch: tag, side, pnl, exit_reason, notional (sizing sanity)
  [ANOMALY] wallet-lane notional > MAX_WALLET_NOTIONAL, lock dist > 0.2 (crypto),
            stop_loss exits worse than -3.5% of stake  → these drive keep/revert calls.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "trading" / "state"
EPOCH_FILE = Path(__file__).with_name("live_watch_epoch.txt")
MAX_WALLET_NOTIONAL = 5000.0     # post-fix wallet trades must be ≤ ~4% of 100k
TG_DIST_MAX = 0.2                # TAILGATE_DIST_MAX_CRYPTO


def _ft_api():
    cfg = json.loads((ROOT / "trading/crypto/freqtrade/config.json").read_text())
    api = cfg.get("api_server", {})
    host = f"http://{api.get('listen_ip_address', '127.0.0.1')}:{api.get('listen_port', 8080)}"
    return host, api.get("username", ""), api.get("password", "")


def _ft_get(path: str):
    import requests
    host, user, pw = _ft_api()
    tok = requests.post(f"{host}/api/v1/token/login", auth=(user, pw), timeout=8).json()
    hdr = {"Authorization": f"Bearer {tok['access_token']}"}
    return requests.get(f"{host}/api/v1{path}", headers=hdr, timeout=10).json()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epoch", default=None, help="ISO ts; default = stored epoch file")
    ap.add_argument("--set-epoch", action="store_true", help="store NOW as the new epoch")
    args = ap.parse_args()

    if args.set_epoch:
        EPOCH_FILE.write_text(dt.datetime.utcnow().isoformat())
        print("epoch set:", EPOCH_FILE.read_text())
        return
    epoch = args.epoch or (EPOCH_FILE.read_text().strip() if EPOCH_FILE.exists()
                           else dt.datetime.utcnow().isoformat())
    now = dt.datetime.utcnow()
    print(f"=== live_watch — epoch {epoch}  now {now.isoformat(timespec='seconds')} ===")

    anomalies: list[str] = []

    # ---- open freqtrade trades opened since epoch, graded live -------------------------
    try:
        oc = _ft_get("/status")
    except Exception as e:                                    # noqa: BLE001
        oc = []
        print(f"[OPEN] freqtrade unreachable: {e}")
    fresh = [t for t in oc if (t.get("open_date") or "") >= epoch.replace("T", " ")[:19]
             or (t.get("open_date") or "").replace(" ", "T") >= epoch[:19]]
    print(f"[OPEN] {len(fresh)} trades opened since epoch (of {len(oc)} open)")
    for t in sorted(fresh, key=lambda x: x.get("open_date") or ""):
        side = "SHORT" if t.get("is_short") else "LONG"
        prof = t.get("profit_pct")
        age_min = None
        try:
            od = dt.datetime.fromisoformat(str(t["open_date"]).replace(" ", "T")[:19])
            age_min = (now - od).total_seconds() / 60
        except Exception:                                     # noqa: BLE001
            pass
        grade = "?" if prof is None else ("✓" if prof > 0 else "✗")
        # grade only counts once the trade has lived ≥15m (avoid entry-noise verdicts)
        mature = age_min is not None and age_min >= 15
        print(f"  {t.get('pair', '?'):22s} {side:5s} tag={str(t.get('enter_tag'))[:28]:28s} "
              f"age={age_min and int(age_min)}m profit={prof}% "
              f"grade={'(young)' if not mature else grade} stake={t.get('stake_amount')} "
              f"lev={t.get('leverage')}")

    # ---- closed trades since epoch (journal, all lanes) --------------------------------
    j = json.loads((STATE / "journal.json").read_text())
    rows = j if isinstance(j, list) else j.get("trades", j.get("rows", []))
    closed = [r for r in rows if (r.get("exit_datetime") or "") >= epoch
              and (r.get("exchange", "") or "").upper() not in ("NSE", "NFO", "MCX")]
    print(f"[CLOSED] {len(closed)} crypto closes since epoch")
    greens = 0
    for r in closed[-40:]:
        pnl = float(r.get("net_pnl") or r.get("pnl") or 0)
        greens += pnl > 0
        tag = (r.get("strategy_name") or r.get("enter_tag") or "?")[:24]
        notional = 0.0
        try:
            notional = float(r["entry_price"]) * float(r["quantity"])
        except Exception:                                     # noqa: BLE001
            pass
        mark = "✓" if pnl > 0 else "✗"
        print(f"  {mark} {str(r.get('symbol'))[:20]:20s} {str(r.get('direction'))[:5]:5s} "
              f"tag={tag:24s} pnl={pnl:9.2f} exit={str(r.get('exit_reason') or '?')[:14]:14s} "
              f"notional={notional:9.0f}")
        if tag in ("momentum", "brain", "live_loop") and notional > MAX_WALLET_NOTIONAL:
            anomalies.append(f"wallet-lane notional {notional:.0f} > {MAX_WALLET_NOTIONAL:.0f} "
                             f"on {r.get('symbol')} (sizing fix NOT effective)")
        if (r.get("exit_reason") == "stop_loss") and notional and pnl / notional < -0.035:
            anomalies.append(f"stop_loss deeper than -3.5% of notional on {r.get('symbol')} "
                             f"({100 * pnl / notional:.1f}%) — ML_STOPLOSS not enforced?")
    if closed:
        print(f"[CLOSED] green ratio since epoch: {greens}/{min(len(closed), 40)} shown; "
              f"all-closed green={sum(1 for r in closed if float(r.get('net_pnl') or r.get('pnl') or 0) > 0)}"
              f"/{len(closed)}")

    # ---- tailgate lock sanity ----------------------------------------------------------
    try:
        locks = json.loads((STATE / "profit_tailgate_locks.json").read_text())
        bad = {k: v for k, v in locks.items()
               if isinstance(v, dict) and str(k).startswith("CRYPTO")
               and float(v.get("dist") or 0) > TG_DIST_MAX + 0.01}
        print(f"[LOCKS] {len(locks)} live locks; {len(bad)} with dist > {TG_DIST_MAX}")
        for k, v in list(bad.items())[:6]:
            anomalies.append(f"lock dist {v.get('dist')} > {TG_DIST_MAX} on {k}")
    except Exception as e:                                    # noqa: BLE001
        print("[LOCKS] unreadable:", e)

    print(f"[ANOMALY] {len(anomalies)}")
    for a in anomalies:
        print("  !!", a)


if __name__ == "__main__":
    sys.exit(main())
