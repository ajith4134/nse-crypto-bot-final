"""E1 — Is the bottom-of-range entry edge mechanical mean-reversion or signal timing?

a) NULL GRID: random (symbol, time) pseudo-entries with NO signal → P(up | pos bucket)
   at 15m/1h/4h. If bottom→up >> top→up unconditionally, the effect is market mechanics.
b) CLAIMS: labeled-claim accuracy by pos bucket, compared against the null base rate in
   the same bucket (skill above mechanics).
c) TRADES: all closed trades win% + profit by entry pos bucket, longs AND shorts —
   the honest big-n version of yesterday's 35-trade table.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
from exp_common import (bars5, close_at, fwd_ret, range_pos, pos_bucket,
                        load_claims, load_trades, flat, CLEAN_TS)

rng = np.random.default_rng(20260717)
HOR = {"15m": 900, "1h": 3600, "4h": 14400}

# ── a) null grid ────────────────────────────────────────────────────────────────
claims = load_claims()
syms = claims["symbol"].value_counts().head(150).index.tolist()
rows = []
for sym in syms:
    arr = bars5(sym)
    if arr is None or len(arr) < 500:
        continue
    lo_t, hi_t = arr[50, 0], arr[-1, 0] - 14400
    for ts in rng.uniform(lo_t, hi_t, 60):
        rp = range_pos(arr, ts)
        bk = pos_bucket(rp)
        if bk is None:
            continue
        r = {"sym": sym, "bucket": bk, "era": "clean" if ts >= CLEAN_TS else "hist"}
        for h, s in HOR.items():
            fr = fwd_ret(arr, ts, s)
            if fr is not None:
                r[h] = fr
        rows.append(r)
null = pd.DataFrame(rows)
print(f"— E1a NULL GRID: {len(null)} pseudo-entries, {null['sym'].nunique()} symbols —")
for h in HOR:
    g = null.dropna(subset=[h]).groupby("bucket")[h]
    up = g.apply(lambda s: (s > 0).mean())
    med = g.median()
    n = g.size()
    print(f"  {h}: " + "  ".join(
        f"{b}: P(up)={up.get(b, float('nan')):.3f} med={med.get(b, float('nan'))*100:+.3f}% n={n.get(b, 0)}"
        for b in ("bottom", "mid", "top")))

# ── b) claims accuracy by pos bucket ────────────────────────────────────────────
cl = claims[claims["ts"] >= CLEAN_TS].copy()
pos, buck = [], []
for sym, ts in zip(cl["symbol"], cl["ts"]):
    arr = bars5(sym)
    rp = range_pos(arr, ts) if arr is not None else None
    pos.append(rp); buck.append(pos_bucket(rp))
cl["rp"], cl["bucket"] = pos, buck
cov = cl.dropna(subset=["bucket"])
print(f"\n— E1b CLAIMS (clean window): {len(cov)}/{len(cl)} with pos coverage —")
for h in ("15m", "1h"):
    sub = cov[cov["horizon"] == h]
    for d in ("LONG", "SHORT"):
        s2 = sub[sub["direction"] == d]
        g = s2.groupby("bucket")["correct"]
        print(f"  {h} {d}: " + "  ".join(
            f"{b}: acc={g.mean().get(b, float('nan')):.3f} n={g.size().get(b, 0)}"
            for b in ("bottom", "mid", "top")))

# ── c) all closed trades by entry pos ───────────────────────────────────────────
tr = load_trades()
buck, rps = [], []
for pair, ts in zip(tr["pair"], tr["open_ts"]):
    arr = bars5(pair)
    rp = range_pos(arr, ts) if arr is not None else None
    rps.append(rp); buck.append(pos_bucket(rp))
tr["rp"], tr["bucket"] = rps, buck
cov = tr.dropna(subset=["bucket"])
print(f"\n— E1c CLOSED TRADES: {len(cov)}/{len(tr)} with pos coverage —")
for short in (0, 1):
    sub = cov[cov["is_short"] == short]
    g = sub.groupby("bucket")
    print(f"  {'SHORT' if short else 'LONG '}: " + "  ".join(
        f"{b}: win={(g['close_profit'].apply(lambda s: (s > 0).mean())).get(b, float('nan')):.3f} "
        f"avgP={(g['close_profit'].mean()).get(b, float('nan'))*100:+.3f}% n={g.size().get(b, 0)}"
        for b in ("bottom", "mid", "top")))
# clean-window-only repeat (the era yesterday's n=35 came from)
cc = cov[cov["open_ts"] >= CLEAN_TS]
print(f"  clean-window only ({len(cc)} trades):")
for short in (0, 1):
    sub = cc[cc["is_short"] == short]
    g = sub.groupby("bucket")
    print(f"  {'SHORT' if short else 'LONG '}: " + "  ".join(
        f"{b}: win={(g['close_profit'].apply(lambda s: (s > 0).mean())).get(b, float('nan')):.3f} "
        f"n={g.size().get(b, 0)}" for b in ("bottom", "mid", "top")))
