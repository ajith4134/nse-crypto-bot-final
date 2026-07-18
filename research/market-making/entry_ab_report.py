#!/usr/bin/env python3
"""Randomized taker-vs-maker ENTRY A/B — intention-to-treat readout.

Reads exec_choice_log.jsonl rows carrying an "arm" (written when EXEC_AB=1) and joins
them to Freqtrade's ORDERS table -- not the trades table, because a maker order that
was cancelled never becomes a trade, and that miss is the entire cost being measured.

The headline is INTENTION-TO-TREAT: mean P&L per DECISION, where a decision whose order
never filled contributes 0 (we simply did not trade). Analysing per-fill instead would
silently drop the maker arm's misses and flatter it -- which is exactly the error the
pre-existing non-randomized stats made.

Endpoints, in descending order of statistical power:
  1. fill rate          -- binomial, tight at n~400/arm.
  2. slippage vs mid    -- low variance, the direct causal channel.
  3. ITT P&L/decision   -- the number that actually decides it, and the weakest: at
                           sigma~8.4% per trade a ~0.3% effect needs ~9,800/arm (~18
                           days at 1,100 closes/day). Reported with a CI so it is read
                           as "not yet resolved" rather than "no difference".
"""
import json
import math
import sqlite3
import statistics
import sys
import time
from collections import defaultdict

DB = "tradesv3.dryrun.sqlite"
LOG = "trading/state/exec_choice_log.jsonl"
WINDOW_S = 180.0
GRACE_S = 5.0


def flat(p):
    return (p or "").replace("/", "").split(":")[0].upper()


def load_orders(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.execute("PRAGMA busy_timeout=10000")
    # NOTE: ft_is_entry exists in Freqtrade's REST payload but NOT as a column on the
    # orders table — the entry leg has to be inferred from side vs trade direction here.
    rows = c.execute(
        "select o.id, o.ft_pair, o.order_date, o.status, o.filled, o.average, o.price,"
        "       o.order_type, t.close_profit, t.is_short, t.is_open"
        "  from orders o join trades t on o.ft_trade_id = t.id"
        " where (t.is_short = 0 and o.ft_order_side = 'buy')"
        "    or (t.is_short = 1 and o.ft_order_side = 'sell')"
    ).fetchall()
    out = defaultdict(list)
    for oid, pair, od, status, filled, avg, price, otype, prof, short, isopen in rows:
        if not od:
            continue
        try:
            ts = time.mktime(time.strptime(od.split(".")[0], "%Y-%m-%d %H:%M:%S"))
        except Exception:
            continue
        out[flat(pair)].append({
            "id": oid, "ts": ts, "status": status, "filled": float(filled or 0),
            "rate": avg or price, "type": otype, "profit": prof,
            "short": short, "open": isopen,
        })
    return out


def main(log_path, db):
    decisions = []
    for line in open(log_path):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("arm") and r.get("ts"):
            decisions.append(r)
    decisions.sort(key=lambda r: r["ts"])
    if not decisions:
        print("No randomized decisions yet — set EXEC_AB=1 and let the loops run.")
        print("(rows without an 'arm' field are pre-experiment policy decisions)")
        return

    orders, used = load_orders(db), set()
    for d in decisions:
        best = None
        for o in orders.get(d.get("symbol"), []):
            if o["id"] in used:
                continue
            dt = o["ts"] - d["ts"]
            if -GRACE_S <= dt <= WINDOW_S and (best is None or dt < best[0]):
                best = (dt, o)
        if best:
            used.add(best[1]["id"])
            d["_o"] = best[1]

    print(f"{len(decisions):,} randomized decisions "
          f"({sum(1 for d in decisions if d.get('_o')):,} matched to an order)\n")

    by = defaultdict(list)
    for d in decisions:
        by[d["arm"]].append(d)

    print(f"{'arm':10s}{'decisions':>11s}{'orders':>8s}{'filled':>8s}{'fill rate':>11s}"
          f"{'slip bps':>11s}{'ITT pnl%':>11s}{'pnl%|fill':>11s}")
    print("-" * 81)
    summary = {}
    for arm, ds in sorted(by.items()):
        placed = [d for d in ds if d.get("_o")]
        filled = [d for d in placed if d["_o"]["filled"] > 0]
        slips = []
        for d in filled:
            mid, rate = d.get("mid"), d["_o"]["rate"]
            if mid and rate:
                sgn = -1.0 if d["_o"]["short"] else 1.0
                slips.append(sgn * (float(rate) - float(mid)) / float(mid) * 1e4)
        # ITT: every decision counts; an unfilled one contributes 0 (no trade taken)
        itt = [(d["_o"]["profit"] * 100 if d.get("_o") and d["_o"]["filled"] > 0
                and d["_o"]["profit"] is not None and not d["_o"]["open"] else 0.0)
               for d in ds]
        oncef = [d["_o"]["profit"] * 100 for d in filled
                 if d["_o"]["profit"] is not None and not d["_o"]["open"]]
        summary[arm] = itt
        # Fill rate MUST be over DECISIONS, not over matched orders. When a maker entry
        # is cancelled with nothing filled, Freqtrade deletes the trade AND its order row
        # (verified: order 19932 was status=open/filled=0, then gone minutes later). So a
        # miss leaves no trace in the DB — dividing by matched orders would silently drop
        # every miss from the denominator and report the maker arm at ~100% fill, which is
        # backwards from the truth the experiment exists to measure.
        print(f"{arm:10s}{len(ds):11d}{len(placed):8d}{len(filled):8d}"
              f"{(100*len(filled)/len(ds) if ds else float('nan')):10.1f}%"
              f"{(statistics.mean(slips) if slips else float('nan')):11.3f}"
              f"{(statistics.mean(itt) if itt else float('nan')):11.3f}"
              f"{(statistics.mean(oncef) if oncef else float('nan')):11.3f}")

    if len(summary) == 2:
        (a, xs), (b, ys) = sorted(summary.items())
        if len(xs) > 2 and len(ys) > 2:
            d = statistics.mean(ys) - statistics.mean(xs)
            se = math.sqrt(statistics.pvariance(xs) / len(xs)
                           + statistics.pvariance(ys) / len(ys))
            print(f"\nITT difference ({b} - {a}): {d:+.4f}%  "
                  f"95% CI [{d-1.96*se:+.4f}, {d+1.96*se:+.4f}]")
            if se > 0 and abs(d) < 1.96 * se:
                need = int(2 * ((statistics.pstdev(xs + ys) or 0) ** 2) * 7.85 / max(d ** 2, 1e-9))
                print(f"NOT RESOLVED — CI spans zero. At this effect size ~{need:,}/arm "
                      f"would be needed. Read the slippage and fill-rate columns instead.")
            else:
                print("Difference is significant at 95% — but confirm the fill-rate column "
                      "first: paper overstates maker fills (no queue model).")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else LOG,
         sys.argv[2] if len(sys.argv) > 2 else DB)
