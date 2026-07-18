#!/usr/bin/env python3
"""Did our PASSIVE (limit-at-touch) entries actually fill?

exec_choice.py logs every entry decision (market vs limit-at-touch) and grades the
slippage of the ones that became trades. But grade_fills() iterates over TRADES --
so a limit order that never filled is invisible to it. The reported "limit beats
market by 6.75 bps" is therefore measured only on limits that survived to become
a trade, which is exactly the sample you cannot draw that conclusion from.

This joins decisions -> trades to recover the missing half:

  fill rate      -- how often each order type actually became a trade
  time to fill   -- how long the passive orders waited
  MISS COST      -- the whole point. For decisions that never filled, where did
                    price go afterwards? If unfilled longs were the ones that ran
                    up, passive entry is silently discarding our winners, and the
                    slippage saving is an accounting illusion.

Matching is greedy and 1:1 in time order: each trade is consumed by at most one
decision, so two decisions on the same symbol cannot both claim the same fill.
"""
import json
import sqlite3
import statistics
import sys
import time
from collections import defaultdict

DB = "tradesv3.dryrun.sqlite"
LOG = "trading/state/exec_choice_log.jsonl"
MATCH_WINDOW_S = 900.0    # freqtrade's default entry unfilledtimeout is 10 min
GRACE_S = 5.0             # decision is logged just before the REST call


def flat(p):
    return (p or "").replace("/", "").split(":")[0].upper()


def load_decisions(path):
    out = []
    for line in open(path):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("ts"):
            out.append(r)
    out.sort(key=lambda r: r["ts"])
    return out


def load_trades(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.execute("PRAGMA busy_timeout=10000")
    rows = c.execute(
        "select id, pair, open_date, open_rate, close_profit, is_short, is_open "
        "from trades order by open_date"
    ).fetchall()
    out = defaultdict(list)
    for tid, pair, od, rate, prof, short, isopen in rows:
        if not od:
            continue
        try:
            ts = time.mktime(time.strptime(od.split(".")[0], "%Y-%m-%d %H:%M:%S"))
        except Exception:
            continue
        out[flat(pair)].append({"id": tid, "ts": ts, "rate": rate,
                                "profit": prof, "short": short, "open": isopen})
    return out


def match(decisions, trades):
    used = set()
    for d in decisions:
        sym, ts = d.get("symbol"), d["ts"]
        best = None
        for t in trades.get(sym, []):
            if t["id"] in used:
                continue
            dt = t["ts"] - ts
            if -GRACE_S <= dt <= MATCH_WINDOW_S:
                if best is None or dt < best[0]:
                    best = (dt, t)
        if best:
            used.add(best[1]["id"])
            d["_fill_dt"] = best[0]
            d["_trade"] = best[1]
    return decisions


def report(decisions):
    by = defaultdict(list)
    for d in decisions:
        by[d.get("order_type") or "?"].append(d)

    print(f"{'order_type':12s}{'decisions':>11s}{'filled':>9s}{'fill rate':>11s}"
          f"{'med wait':>11s}{'mean pnl%':>11s}")
    print("-" * 65)
    for ot, ds in sorted(by.items()):
        filled = [d for d in ds if d.get("_trade")]
        waits = [d["_fill_dt"] for d in filled]
        pnl = [d["_trade"]["profit"] * 100 for d in filled
               if d["_trade"]["profit"] is not None and not d["_trade"]["open"]]
        print(f"{ot:12s}{len(ds):11d}{len(filled):9d}{100*len(filled)/len(ds):10.1f}%"
              f"{statistics.median(waits) if waits else float('nan'):9.1f} s"
              f"{statistics.mean(pnl) if pnl else float('nan'):11.3f}")

    print()
    print("By decision reason (reason -> what the policy was thinking):")
    print(f"{'reason':16s}{'type':8s}{'n':>7s}{'filled':>8s}{'fill rate':>11s}{'mean pnl%':>11s}")
    print("-" * 61)
    byr = defaultdict(list)
    for d in decisions:
        byr[(d.get("reason"), d.get("order_type"))].append(d)
    for (rs, ot), ds in sorted(byr.items(), key=lambda kv: -len(kv[1])):
        filled = [d for d in ds if d.get("_trade")]
        pnl = [d["_trade"]["profit"] * 100 for d in filled
               if d["_trade"]["profit"] is not None and not d["_trade"]["open"]]
        print(f"{str(rs):16s}{str(ot):8s}{len(ds):7d}{len(filled):8d}"
              f"{100*len(filled)/len(ds):10.1f}%"
              f"{statistics.mean(pnl) if pnl else float('nan'):11.3f}")


if __name__ == "__main__":
    ds = load_decisions(sys.argv[1] if len(sys.argv) > 1 else LOG)
    tr = load_trades(sys.argv[2] if len(sys.argv) > 2 else DB)
    print(f"{len(ds):,} decisions | {sum(len(v) for v in tr.values()):,} trades in db\n")
    report(match(ds, tr))
