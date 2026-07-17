"""M — Owner's hypothesis: do we enter AFTER the momentum has completed?

For every covered closed trade: SIGNED pre-entry run-up = symbol return over the prior
30m/1h/4h in the direction of the trade (long: up-move positive; short: down-move
positive). Large positive signed run-up = we entered late, chasing a completed move.
Buckets → win rate / avg profit. Split by tag family. Also: minutes from entry to the
trade's own MFE (how fast the favorable move exhausts).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
from exp_common import load_trades, bars5, close_at, CLEAN_TS

tr = load_trades()
tr["pnl_pct"] = tr["close_profit"].fillna(0.0) * 100
rows = []
for r in tr.itertuples():
    arr = bars5(r.pair)
    if arr is None:
        continue
    ts = r.open_ts
    now = close_at(arr, ts)
    if now is None or now <= 0:
        continue
    rec = {"pair": r.pair, "short": bool(r.is_short), "tag": r.enter_tag or "NULL",
           "pnl_pct": r.pnl_pct, "win": r.pnl_pct > 0, "clean": ts >= CLEAN_TS}
    ok = True
    for name, sec in (("run30", 1800), ("run60", 3600), ("run240", 14400)):
        past = close_at(arr, ts - sec)
        if past is None or past <= 0:
            ok = False
            break
        raw = (now / past - 1.0) * 100
        rec[name] = -raw if r.is_short else raw       # signed: + = chasing the move
    if ok:
        rows.append(rec)
df = pd.DataFrame(rows)
print(f"covered closed trades: {len(df)} (clean: {df['clean'].sum()})")

for scope, d in (("ALL", df), ("CLEAN", df[df["clean"]])):
    print(f"\n— {scope} (n={len(d)}): signed 1h pre-entry run-up quintiles —")
    d = d.copy()
    d["q"] = pd.qcut(d["run60"], 5, labels=False, duplicates="drop")
    g = d.groupby("q")
    for q, gg in g:
        lo, hi = gg["run60"].min(), gg["run60"].max()
        print(f"  Q{int(q)+1} [{lo:+6.2f}%..{hi:+6.2f}%]: win={gg['win'].mean():.3f} "
              f"avgP={gg['pnl_pct'].mean():+.3f}% n={len(gg)}")

print("\n— per tag family (ALL, n>=25): mean signed run-up vs outcome —")
fam = df.copy()
fam["fam"] = fam["tag"].str.replace(r"^(lens|filter|alpha_crypto|rdagent_crypto)[:_].*",
                                    r"\1:*", regex=True)
for f_, g in fam.groupby("fam"):
    if len(g) < 25:
        continue
    print(f"  {f_:22s} n={len(g):4d} run60={g['run60'].mean():+6.2f}% "
          f"run240={g['run240'].mean():+6.2f}% win={g['win'].mean():.3f} "
          f"avgP={g['pnl_pct'].mean():+.3f}%")

# correlation: does chasing predict losing?
for scope, d in (("ALL", df), ("CLEAN", df[df["clean"]])):
    from scipy.stats import spearmanr
    rho, p = spearmanr(d["run60"], d["pnl_pct"])
    print(f"\n{scope}: Spearman(signed 1h run-up, profit) = {rho:+.3f} (p={p:.4f}, n={len(d)})")
