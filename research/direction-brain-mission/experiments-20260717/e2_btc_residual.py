"""E2 — Do our lenses predict RELATIVE (vs-BTC) moves better than absolute moves?

For every labeled clean-window claim with candle coverage:
  raw     = sign(symbol move over horizon)
  resid   = sign(symbol move − beta·BTC move)   [beta from 5 days of 5m returns]
Score each source's claimed direction against both. Also report how much of each
symbol's 15m/1h variance BTC explains (the common-factor share).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
from exp_common import bars5, close_at, load_claims, CLEAN_TS

HOR = {"15m": 900, "1h": 3600}
btc = bars5("BTC/USDT")

# per-symbol beta from aligned 5m log-returns over the last ~5 days of shared bars
def beta_r2(arr):
    ts_b, cl_b = btc[:, 0], btc[:, 4]
    ts_s, cl_s = arr[:, 0], arr[:, 4]
    common, ib, isym = np.intersect1d(ts_b, ts_s, return_indices=True)
    if len(common) < 300:
        return None, None
    ib, isym = ib[-1500:], isym[-1500:]
    rb = np.diff(np.log(cl_b[ib]))
    rs = np.diff(np.log(cl_s[isym]))
    ok = np.isfinite(rb) & np.isfinite(rs)
    rb, rs = rb[ok], rs[ok]
    if rb.std() == 0 or len(rb) < 200:
        return None, None
    beta = np.cov(rs, rb)[0, 1] / rb.var()
    r2 = np.corrcoef(rs, rb)[0, 1] ** 2
    return float(beta), float(r2)

claims = load_claims()
cl = claims[(claims["ts"] >= CLEAN_TS) & claims["horizon"].isin(HOR)].copy()

betas, r2s, raw_ok, res_ok = {}, {}, [], []
rows = []
for sym, ts, hor, d, corr, src, taken in zip(cl["symbol"], cl["ts"], cl["horizon"],
                                             cl["direction"], cl["correct"],
                                             cl["source"], cl["taken"]):
    arr = bars5(sym)
    if arr is None:
        continue
    if sym not in betas:
        betas[sym], r2s[sym] = beta_r2(arr)
    beta = betas[sym]
    if beta is None:
        continue
    s = HOR[hor]
    a, b = close_at(arr, ts), close_at(arr, ts + s)
    ba, bb = close_at(btc, ts), close_at(btc, ts + s)
    if None in (a, b, ba, bb) or min(a, ba) <= 0:
        continue
    sym_mv = np.log(b / a)
    btc_mv = np.log(bb / ba)
    resid = sym_mv - beta * btc_mv
    want = 1 if d == "LONG" else -1
    rows.append({"source": src, "horizon": hor, "taken": bool(taken),
                 "raw_ok": (np.sign(sym_mv) == want) if sym_mv != 0 else False,
                 "res_ok": (np.sign(resid) == want) if resid != 0 else False,
                 "recorded_ok": bool(corr)})
df = pd.DataFrame(rows)
r2v = pd.Series({s: r for s, r in r2s.items() if r is not None})
print(f"— E2: {len(df)} scored claims, {len(r2v)} symbols —")
print(f"BTC common-factor share (R² of 5m returns): median={r2v.median():.3f} "
      f"p25={r2v.quantile(.25):.3f} p75={r2v.quantile(.75):.3f}")
print(f"sanity: recomputed raw accuracy {df['raw_ok'].mean():.3f} vs recorded "
      f"{df['recorded_ok'].mean():.3f} (should be close)\n")

print(f"{'source':28s} {'hor':4s} {'n':>5s} {'raw':>6s} {'resid':>6s} {'Δ':>6s}")
for (src, hor), g in sorted(df.groupby(["source", "horizon"]),
                            key=lambda kv: -len(kv[1])):
    if len(g) < 100:
        continue
    print(f"{src:28s} {hor:4s} {len(g):5d} {g['raw_ok'].mean():6.3f} "
          f"{g['res_ok'].mean():6.3f} {g['res_ok'].mean()-g['raw_ok'].mean():+6.3f}")
tot = df.groupby("horizon")[["raw_ok", "res_ok"]].mean()
print("\nALL sources pooled:")
print(tot.round(3))
