#!/usr/bin/env python3
"""Is our 162 ms round-trip latency survivable for passive quoting?

Markout says whether the AVERAGE maker fill is profitable. This asks the separate
question of whether WE could be that average maker. A resting quote is a free option
written to the rest of the market; the only defence is cancelling it before informed
flow arrives. Our cancel takes ~162 ms.

Two measurements, both straight off the recorded book stream:

1. QUOTE LIFETIME -- how long the best bid/ask survives unchanged. If the top of book
   re-prices faster than 162 ms, we can never hold a current quote: every quote we
   have resting is, on average, already stale.

2. PICK-OFF EXPOSURE -- for each moment t, does the mid move by more than the
   half-spread within our 162 ms reaction window? If it does, a quote we wanted to
   pull was still sitting there at a price the market has already left behind, and it
   gets filled precisely when we would least like it to.

Both are properties of the market, independent of any strategy. They bound the fill
quality we could achieve regardless of how good our pricing logic is.
"""
import json
import statistics
import sys
from bisect import bisect_left
from collections import defaultdict

OUR_LATENCY_S = 0.162   # measured VM -> Binance, per the HFT feasibility study


def load_books(path):
    books = defaultdict(list)
    with open(path) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("t") != "B" or r.get("ts") is None:
                continue
            books[r["s"]].append((r["ts"] / 1000.0, float(r["b"]), float(r["a"])))
    for v in books.values():
        v.sort()
    return books


def analyse(bk):
    times = [x[0] for x in bk]

    # 1. quote lifetime: gap between genuine top-of-book PRICE changes
    lifetimes, last_t, last_q = [], None, None
    for t, b, a in bk:
        q = (b, a)
        if q != last_q:
            if last_t is not None:
                lifetimes.append(t - last_t)
            last_t, last_q = t, q
    if not lifetimes:
        return None

    # 2. pick-off exposure at our latency
    picked = tested = 0
    moves = []
    for i, (t, b, a) in enumerate(bk):
        mid = (a + b) / 2.0
        if mid <= 0 or a <= b:
            continue
        hs = (a - b) / 2.0 / mid * 1e4
        j = bisect_left(times, t + OUR_LATENCY_S)
        if j >= len(bk):
            break
        t2, b2, a2 = bk[j]
        mid2 = (a2 + b2) / 2.0
        mv = abs(mid2 - mid) / mid * 1e4
        moves.append(mv)
        tested += 1
        if mv > hs:
            picked += 1

    return {
        "n_book": len(bk),
        "median_life_ms": statistics.median(lifetimes) * 1000,
        "mean_life_ms": statistics.mean(lifetimes) * 1000,
        "pct_life_under_latency": 100.0 * sum(1 for x in lifetimes if x < OUR_LATENCY_S)
                                  / len(lifetimes),
        "pickoff_pct": 100.0 * picked / tested if tested else float("nan"),
        "median_move_bps": statistics.median(moves) if moves else float("nan"),
    }


if __name__ == "__main__":
    books = load_books(sys.argv[1])
    print(f"Latency assumption: {OUR_LATENCY_S*1000:.0f} ms round trip (measured)\n")
    print(f"{'symbol':13s}{'books':>8s}{'med quote life':>16s}"
          f"{'% lives <162ms':>16s}{'pick-off %':>12s}{'med 162ms move':>16s}")
    print("-" * 81)
    for sym, bk in sorted(books.items()):
        r = analyse(bk)
        if not r:
            continue
        print(f"{sym:13s}{r['n_book']:8d}{r['median_life_ms']:13.0f} ms"
              f"{r['pct_life_under_latency']:15.1f}%{r['pickoff_pct']:11.1f}%"
              f"{r['median_move_bps']:13.3f} bps")
    print()
    print("pick-off % = share of moments where the mid moved MORE than the half-spread")
    print("             within our 162 ms cancel window -- i.e. a quote we wanted to pull")
    print("             was still resting at a price the market had already left.")
