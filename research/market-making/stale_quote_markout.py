#!/usr/bin/env python3
"""What WE would earn -- not what the average maker earns.

analyze_markout.py measures every maker fill on the wire. But that population is
dominated by firms who cancel in microseconds. They successfully avoid the worst
fills; we cannot. So their average is not our average.

This splits the same fills by whether the top of book moved during the 162 ms
immediately BEFORE the fill:

  FRESH  -- book was stable for the prior 162 ms. A quote resting here was still
            correctly priced. Fast and slow makers both get these.
  STALE  -- the book re-priced within the prior 162 ms. A fast maker had already
            cancelled and re-quoted; we would still be sitting at the old price,
            so this fill lands on US and not on them.

The STALE column is the honest estimate of our fill quality. The gap between the
two columns is the cost of being 162 ms slow, in basis points, measured rather
than assumed.
"""
import json
import statistics
import sys
from bisect import bisect_right, bisect_left
from collections import defaultdict

MAKER_FEE_BPS = 2.0
OUR_LATENCY_S = 0.162
HORIZON = 10.0


def load(path):
    books, trades = defaultdict(list), defaultdict(list)
    with open(path) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("ts") is None:
                continue
            ts = r["ts"] / 1000.0
            if r["t"] == "B":
                books[r["s"]].append((ts, float(r["b"]), float(r["a"])))
            else:
                trades[r["s"]].append((ts, float(r["p"]), float(r["q"]), bool(r["m"])))
    for v in books.values():
        v.sort()
    for v in trades.values():
        v.sort()
    return books, trades


def run(books, trades):
    print(f"Horizon {HORIZON:.0f}s | maker fee {MAKER_FEE_BPS} bps | latency "
          f"{OUR_LATENCY_S*1000:.0f} ms\n")
    print(f"{'symbol':13s}{'fresh n':>9s}{'fresh net':>11s}{'stale n':>9s}"
          f"{'stale net':>11s}{'latency cost':>14s}")
    print("-" * 67)
    for sym in sorted(trades):
        bk, tr = books.get(sym), trades[sym]
        if not bk or not tr:
            continue
        times = [x[0] for x in bk]
        # price-change timeline: when did the top of book actually re-price?
        chg, last_q = [], None
        for t, b, a in bk:
            if (b, a) != last_q:
                chg.append(t)
                last_q = (b, a)

        fresh, stale = [], []
        for ts, p, q, maker_is_buyer in tr:
            i = bisect_right(times, ts) - 1
            if i < 0:
                continue
            t0, b, a = bk[i]
            mid = (a + b) / 2.0
            if mid <= 0 or a <= b:
                continue
            j = bisect_left(times, ts + HORIZON)
            if j >= len(bk):
                continue
            _, b2, a2 = bk[j]
            mid2 = (a2 + b2) / 2.0
            hs = (a - b) / 2.0 / mid * 1e4
            side = 1.0 if maker_is_buyer else -1.0
            net = hs + side * (mid2 - mid) / mid * 1e4 - MAKER_FEE_BPS

            # did the book re-price within our latency window before this fill?
            k = bisect_left(chg, ts - OUR_LATENCY_S)
            moved = k < len(chg) and chg[k] <= ts
            (stale if moved else fresh).append(net)

        if not fresh and not stale:
            continue
        fm = statistics.mean(fresh) if fresh else float("nan")
        sm = statistics.mean(stale) if stale else float("nan")
        cost = (sm - fm) if (fresh and stale) else float("nan")
        print(f"{sym:13s}{len(fresh):9d}{fm:11.3f}{len(stale):9d}{sm:11.3f}{cost:14.3f}")

    print()
    print("STALE = fills arriving after the book already re-priced. A microsecond maker")
    print("        has cancelled by then; we have not. These are the fills we inherit.")
    print("'latency cost' = stale net - fresh net, in bps. This is what 162 ms costs us.")


if __name__ == "__main__":
    b, t = load(sys.argv[1])
    run(b, t)
