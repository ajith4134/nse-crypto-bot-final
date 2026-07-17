"""E6b — Counterfactual early-abort curve: what if every trade were aborted the moment
adverse excursion hit X bps?

For each threshold X: trades whose recorded max adverse excursion ≥ X are assumed
closed at −(X+10)bps on notional (10bps slippage+fees allowance); trades that never
reached X keep their actual P&L. Estimate of abs P&L uses stake×leverage×bps (the
freqtrade futures approximation) — labeled ESTIMATE, direction of effect is the point.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from exp_common import load_trades, CLEAN_TS

tr = load_trades()
tr["pnl"] = tr["close_profit_abs"].fillna(0.0)
tr = tr[tr["min_rate"].notna() & tr["max_rate"].notna()]
tr["dd_bps"] = np.where(tr["is_short"] == 0,
                        (tr["open_rate"] - tr["min_rate"]) / tr["open_rate"],
                        (tr["max_rate"] - tr["open_rate"]) / tr["open_rate"]) * 1e4
cw = tr[tr["open_ts"] >= CLEAN_TS].copy()
notional = cw["stake_amount"] * cw["leverage"].fillna(1.0)
print(f"clean n={len(cw)} actual P&L={cw['pnl'].sum():+.0f} USDT "
      f"win%={(cw['pnl']>0).mean():.3f}")
print(f"{'X bps':>6s} {'aborted':>8s} {'kept-win%':>9s} {'est P&L':>9s} {'winners cut':>11s}")
for X in (30, 50, 75, 100, 150, 200, 300):
    hit = cw["dd_bps"] >= X
    est = np.where(hit, -(X + 10) / 1e4 * notional, cw["pnl"])
    kept = cw[~hit]
    wcut = ((cw["pnl"] > 0) & hit).sum()
    print(f"{X:6d} {hit.sum():8d} {(kept['pnl']>0).mean():9.3f} {est.sum():+9.0f} "
          f"{wcut:11d}")
