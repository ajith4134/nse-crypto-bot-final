"""E — Tailgate lock-threshold sweep via candle-path replay (owner-approved follow-up to E5).

For every clean-window closed trade with candle coverage, replay the price path from open
to its ACTUAL close and simulate the profit-tailgate ratchet under a grid of
(arm_pct × giveback_dist). If the simulated lock fires before the real close, the trade is
credited the locked profit at that moment; otherwise it keeps its real outcome (all other
exits — stop, roi, dir_exit — happened in reality and cap the path). Leveraged profit
basis matches live (`profit_pct = price_move × leverage × 100`).

Per-bar ordering (conservative, uniform across the grid): first test the lock with the
bar's ADVERSE extreme against the floor from PRIOR bars, then ratchet the peak with the
bar's favorable extreme. Current production point: arm=3.0 (ATR-scaled), dist=0.30.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
from exp_common import load_trades, bars5, CLEAN_TS

ARMS = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0)
DISTS = (0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6)
PESSIMISTIC = os.environ.get("SWEEP_PESSIMISTIC") == "1"   # exit at bar CLOSE below lock

tr = load_trades()
tr["pnl"] = tr["close_profit_abs"].fillna(0.0)
tr = tr[tr["open_ts"] >= CLEAN_TS].copy()
tr["close_ts"] = tr["close_date"].astype("int64") / 1e9

replayable = []
for r in tr.itertuples():
    arr = bars5(r.pair)
    if arr is None:
        continue
    seg = arr[(arr[:, 0] >= r.open_ts - 300) & (arr[:, 0] <= r.close_ts)]
    if len(seg) < 1:
        continue
    replayable.append((r, seg))
print(f"clean trades: {len(tr)}, replayable with candle paths: {len(replayable)}, "
      f"actual P&L of replayable set: "
      f"{sum(r.pnl for r, _ in replayable):+.0f} USDT")

def replay(r, seg, arm, dist):
    lev = float(r.leverage or 1.0)
    op = float(r.open_rate)
    short = bool(r.is_short)
    notional = float(r.stake_amount) * lev
    peak = 0.0
    locked = None
    for ts, o, h, l, c in seg:
        fav = ((op - l) / op if short else (h - op) / op) * lev * 100.0
        adv = ((op - h) / op if short else (l - op) / op) * lev * 100.0
        if peak >= arm:
            floor = peak * (1.0 - dist)
            if locked is None or floor > locked:
                locked = floor
            probe = (((op - c) / op if short else (c - op) / op) * lev * 100.0
                     if PESSIMISTIC else adv)
            if locked > 0 and probe <= locked:
                # captured: optimistic = the locked level; pessimistic = the bar's
                # CLOSE (the poll saw it after the move — slippage through the lock).
                got = probe if PESSIMISTIC else locked
                return got / 100.0 * float(r.stake_amount)
        peak = max(peak, fav)
    return float(r.pnl)

print(f"\n{'arm%':>5s} " + " ".join(f"d={d:.1f}" .rjust(9) for d in DISTS))
best = (None, -1e18)
for arm in ARMS:
    cells = []
    for dist in DISTS:
        tot = sum(replay(r, seg, arm, dist) for r, seg in replayable)
        cells.append(tot)
        if tot > best[1]:
            best = ((arm, dist), tot)
    print(f"{arm:5.1f} " + " ".join(f"{c:+9.0f}" for c in cells))
print(f"\nbest grid point: arm={best[0][0]}%, dist={best[0][1]} → est {best[1]:+.0f} USDT "
      f"(actual {sum(r.pnl for r, _ in replayable):+.0f})")
