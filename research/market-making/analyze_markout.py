#!/usr/bin/env python3
"""Markout / adverse-selection analysis of recorded maker fills.

For every real maker fill observed on the wire:
  m == True  -> resting BID  filled -> maker is LONG  at p
  m == False -> resting ASK  filled -> maker is SHORT at p

Decomposition of the maker's gross edge at horizon h, in basis points:

    gross(h) = half_spread + drift(h)

  half_spread = (ask-bid)/2 / mid          -- what you earn vs mid just by being passive
  drift(h)    = side * (mid(t+h) - mid(t)) / mid(t)
                                           -- ADVERSE SELECTION. Negative means price
                                              ran away from you after you were filled.

  gross(h) is identical to marking the fill price against the future mid, so reporting
  both components keeps the two effects legible rather than netted into one number.

  net(h) = gross(h) - MAKER_FEE_BPS        -- one leg's fee. Exiting costs again.

IMPORTANT interpretation: this measures the AVERAGE maker fill, which is dominated by
fast, well-queued market makers who can cancel in microseconds. Our own fills would be
strictly WORSE -- at 162 ms we cannot pull a stale quote, so we would inherit the fills
those firms successfully avoided. Every number here is therefore an OPTIMISTIC CEILING
on what we could achieve, not an estimate of it.
"""
import json
import statistics
import sys
from bisect import bisect_right
from collections import defaultdict

MAKER_FEE_BPS = 2.0          # Binance USD-M VIP0 maker = 0.020%
HORIZONS = [1.0, 5.0, 10.0, 30.0]


def load(path):
    books = defaultdict(list)   # sym -> [(ts_s, bid, ask)]
    trades = defaultdict(list)  # sym -> [(ts_s, price, qty, maker_is_buyer)]
    bad = 0
    with open(path) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                bad += 1
                continue
            ts = r.get("ts")
            if ts is None:
                bad += 1
                continue
            ts /= 1000.0
            if r["t"] == "B":
                books[r["s"]].append((ts, float(r["b"]), float(r["a"])))
            else:
                trades[r["s"]].append((ts, float(r["p"]), float(r["q"]), bool(r["m"])))
    for v in books.values():
        v.sort()
    for v in trades.values():
        v.sort()
    return books, trades, bad


def mid_at(bk, times, t):
    """Mid from the most recent book update at or before t. None if t is out of range."""
    i = bisect_right(times, t) - 1
    if i < 0 or t > times[-1]:
        return None
    _, b, a = bk[i]
    return (a + b) / 2.0


def analyse(books, trades):
    out = {}
    for sym, tr in sorted(trades.items()):
        bk = books.get(sym)
        if not bk or not tr:
            continue
        times = [x[0] for x in bk]
        rows = []
        for ts, p, q, maker_is_buyer in tr:
            m0 = mid_at(bk, times, ts)
            if not m0:
                continue
            i = bisect_right(times, ts) - 1
            _, b, a = bk[i]
            if a <= b:
                continue
            hs = (a - b) / 2.0 / m0 * 1e4          # half-spread in bps
            side = 1.0 if maker_is_buyer else -1.0  # +1 maker long, -1 maker short
            rec = {"hs": hs, "notional": p * q}
            ok = False
            for h in HORIZONS:
                m1 = mid_at(bk, times, ts + h)
                if m1 is None:
                    rec[h] = None
                    continue
                rec[h] = side * (m1 - m0) / m0 * 1e4   # drift bps
                ok = True
            if ok:
                rows.append(rec)
        if rows:
            out[sym] = rows
    return out


def report(res):
    print(f"{'symbol':13s}{'fills':>7s}{'half-sp':>9s}"
          + "".join(f"{('drift+'+str(int(h))+'s'):>11s}" for h in HORIZONS))
    print("-" * (29 + 11 * len(HORIZONS)))
    for sym, rows in res.items():
        hs = statistics.mean(r["hs"] for r in rows)
        cells = []
        for h in HORIZONS:
            vals = [r[h] for r in rows if r.get(h) is not None]
            cells.append(f"{statistics.mean(vals):11.3f}" if vals else f"{'-':>11s}")
        print(f"{sym:13s}{len(rows):7d}{hs:9.3f}" + "".join(cells))

    print()
    print(f"NET per fill after {MAKER_FEE_BPS} bps maker fee   (= half_spread + drift - fee)")
    print(f"{'symbol':13s}" + "".join(f"{('net+'+str(int(h))+'s'):>11s}" for h in HORIZONS)
          + f"{'verdict':>12s}")
    print("-" * (13 + 11 * len(HORIZONS) + 12))
    for sym, rows in res.items():
        cells, net10 = [], None
        for h in HORIZONS:
            vals = [r["hs"] + r[h] for r in rows if r.get(h) is not None]
            if vals:
                n = statistics.mean(vals) - MAKER_FEE_BPS
                cells.append(f"{n:11.3f}")
                if h == 10.0:
                    net10 = n
            else:
                cells.append(f"{'-':>11s}")
        v = "?" if net10 is None else ("VIABLE" if net10 > 0 else "LOSS")
        print(f"{sym:13s}" + "".join(cells) + f"{v:>12s}")

    print()
    print("Notional-weighted net at +10s (big fills weighted properly):")
    for sym, rows in res.items():
        vals = [(r["hs"] + r[10.0] - MAKER_FEE_BPS, r["notional"])
                for r in rows if r.get(10.0) is not None]
        if not vals:
            continue
        w = sum(n for _, n in vals)
        wm = sum(v * n for v, n in vals) / w if w else 0.0
        med = statistics.median([v for v, _ in vals])
        print(f"  {sym:13s} vw_net={wm:8.3f} bps   median_net={med:8.3f} bps   "
              f"vol=${w:,.0f}")


if __name__ == "__main__":
    books, trades, bad = load(sys.argv[1])
    print(f"loaded: {sum(len(v) for v in books.values()):,} book updates, "
          f"{sum(len(v) for v in trades.values()):,} trades ({bad} unparsed)")
    print()
    report(analyse(books, trades))
