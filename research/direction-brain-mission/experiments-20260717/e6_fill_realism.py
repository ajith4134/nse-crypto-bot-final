"""E6 — Fill realism / adverse selection: do our paper wins depend on fills a live
limit order would miss?

For closed trades (longs): drawdown-below-entry = (open_rate − min_rate)/open_rate.
  - "bounce" trades (price never dipped ≥0.1% below entry) vs "dip" trades.
  - If wins concentrate in bounce trades, a resting limit below market would
    systematically MISS the winners and CATCH the losers (adverse selection),
    so live capture of the paper edge is worse than it looks. Mirrored for shorts.
Split by entry pos bucket to connect with E1.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
from exp_common import load_trades, bars5, range_pos, pos_bucket, CLEAN_TS

tr = load_trades()
tr["pnl"] = tr["close_profit_abs"].fillna(0.0)
tr = tr[tr["min_rate"].notna() & tr["max_rate"].notna()]
tr["dd_bps"] = np.where(tr["is_short"] == 0,
                        (tr["open_rate"] - tr["min_rate"]) / tr["open_rate"],
                        (tr["max_rate"] - tr["open_rate"]) / tr["open_rate"]) * 1e4
tr["bounce"] = tr["dd_bps"] < 10          # never went ≥10bps against entry
buck = []
for pair, ts in zip(tr["pair"], tr["open_ts"]):
    arr = bars5(pair)
    buck.append(pos_bucket(range_pos(arr, ts)) if arr is not None else None)
tr["bucket"] = buck

for label, df in (("ALL-TIME", tr), ("CLEAN", tr[tr["open_ts"] >= CLEAN_TS])):
    b, d = df[df["bounce"]], df[~df["bounce"]]
    print(f"— {label} (n={len(df)}): bounce n={len(b)} win={(b['pnl']>0).mean():.3f} "
          f"avgP={b['pnl'].mean():+.2f} | dip n={len(d)} win={(d['pnl']>0).mean():.3f} "
          f"avgP={d['pnl'].mean():+.2f}")
    w, l = df[df["pnl"] > 0], df[df["pnl"] <= 0]
    print(f"  median adverse excursion: winners {w['dd_bps'].median():.0f}bps, "
          f"losers {l['dd_bps'].median():.0f}bps | "
          f"winners with dd<10bps: {(w['dd_bps']<10).mean():.2f}")

print("\nby entry pos bucket (clean, longs):")
cl = tr[(tr["open_ts"] >= CLEAN_TS) & (tr["is_short"] == 0)].dropna(subset=["bucket"])
for bk, g in cl.groupby("bucket"):
    b = g[g["bounce"]]
    print(f"  {bk:6s} n={len(g):4d} win={(g['pnl']>0).mean():.3f} "
          f"bounce-share={len(b)/len(g):.2f} bounce-win={(b['pnl']>0).mean() if len(b) else float('nan'):.3f} "
          f"dip-win={(g[~g['bounce']]['pnl']>0).mean() if len(g)-len(b) else float('nan'):.3f}")

# how much win% would a 10bps-better limit entry have missed?
cw = tr[tr["open_ts"] >= CLEAN_TS]
fillable = cw[cw["dd_bps"] >= 10]                  # a 10bps-below limit would fill
print(f"\nCLEAN: limit-10bps-better fills only: n={len(fillable)}/{len(cw)} "
      f"win={(fillable['pnl']>0).mean():.3f} totP&L={fillable['pnl'].sum():+.0f} "
      f"(vs all: win={(cw['pnl']>0).mean():.3f} totP&L={cw['pnl'].sum():+.0f})")
