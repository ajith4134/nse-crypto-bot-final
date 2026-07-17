"""E5 — Where does the money actually come from: direction (win%) or exits (capture)?

Closed trades (clean window and all-time):
  - tail concentration: share of gross profit from the top 5% of trades
  - EV decomposition per enter_tag: win%, avg win, avg loss, payoff ratio, total P&L
  - across tags: does win% or payoff ratio better explain total P&L? (rank corr)
  - exit_reason table: which exits make/lose the money
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from exp_common import load_trades, CLEAN_TS

tr = load_trades()
tr["pnl"] = tr["close_profit_abs"].fillna(0.0)

for label, df in (("ALL-TIME", tr), ("CLEAN (post 07-16 21:23)", tr[tr["open_ts"] >= CLEAN_TS])):
    wins, losses = df[df["pnl"] > 0], df[df["pnl"] <= 0]
    gross_w = wins["pnl"].sum()
    top5 = wins["pnl"].nlargest(max(1, int(0.05 * len(df))))
    print(f"— {label}: n={len(df)} totalP&L={df['pnl'].sum():+.0f} USDT "
          f"win%={len(wins)/max(1,len(df)):.3f} avgWin={wins['pnl'].mean():+.2f} "
          f"avgLoss={losses['pnl'].mean():+.2f}")
    print(f"  top-5%-of-trades share of gross wins: {top5.sum()/max(1e-9,gross_w):.2f} "
          f"({len(top5)} trades = {top5.sum():+.0f} of {gross_w:+.0f})")

print("\nper enter_tag (clean window, n>=8):")
cw = tr[tr["open_ts"] >= CLEAN_TS]
rows = []
for tag, g in cw.groupby(cw["enter_tag"].fillna("NULL")):
    if len(g) < 8:
        continue
    w = g[g["pnl"] > 0]; l = g[g["pnl"] <= 0]
    rows.append({"tag": tag, "n": len(g), "win%": len(w)/len(g),
                 "avgWin": w["pnl"].mean() if len(w) else 0.0,
                 "avgLoss": l["pnl"].mean() if len(l) else 0.0,
                 "payoff": (w["pnl"].mean()/abs(l["pnl"].mean()))
                           if len(w) and len(l) and l["pnl"].mean() != 0 else np.nan,
                 "P&L": g["pnl"].sum()})
t = pd.DataFrame(rows).sort_values("P&L", ascending=False)
print(t.round(3).to_string(index=False))
ok = t.dropna(subset=["payoff"])
if len(ok) >= 5:
    r1, p1 = spearmanr(ok["win%"], ok["P&L"])
    r2, p2 = spearmanr(ok["payoff"], ok["P&L"])
    print(f"\nacross tags: rank-corr(win%, P&L)={r1:+.3f} (p={p1:.3f}) | "
          f"rank-corr(payoff, P&L)={r2:+.3f} (p={p2:.3f})")

print("\nper exit_reason (clean window):")
g = cw.groupby(cw["exit_reason"].fillna("NULL")).agg(
    n=("pnl", "size"), pnl=("pnl", "sum"),
    win=("pnl", lambda s: (s > 0).mean())).sort_values("pnl", ascending=False)
print(g.round(2).to_string())
