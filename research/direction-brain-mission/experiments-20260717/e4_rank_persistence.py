"""E4 — Drift diagnosis: does the RANKING of sources persist across days?

Per UTC day, per source: 1h+15m accuracy (n>=40/day). Spearman rank correlation of
source rankings between consecutive days. Persistent ranking → edges are stable and
levels drift (conditioning/decay is the right fix). Reshuffling ranking → per-source
reliability is a random walk and the decider is chasing noise.

Uses the FULL ledger (not just clean) — drift is a property of the sources, and we
need multiple days; era flagged in output.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from exp_common import load_claims, CLEAN_TS

cl = load_claims()
cl = cl[cl["horizon"].isin(["15m", "1h"])].copy()
cl["day"] = pd.to_datetime(cl["ts"], unit="s", utc=True).dt.strftime("%m-%d")
piv = cl.groupby(["day", "source"])["correct"].agg(["mean", "size"])
piv = piv[piv["size"] >= 40]["mean"].unstack("day")
print("per-day source accuracy (15m+1h pooled, n>=40/day):")
print(piv.round(3).to_string())

days = list(piv.columns)
print("\nday-to-day Spearman rank correlation (sources present both days):")
rhos = []
for a, b in zip(days, days[1:]):
    both = piv[[a, b]].dropna()
    if len(both) >= 5:
        rho, p = spearmanr(both[a], both[b])
        rhos.append(rho)
        print(f"  {a} → {b}: rho={rho:+.3f} (p={p:.3f}, k={len(both)})")
print(f"\nmean rho = {np.mean(rhos):+.3f}" if rhos else "insufficient overlap")

# split-half within the clean window (controls for era changes): first vs second half
cw = cl[cl["ts"] >= CLEAN_TS]
mid = cw["ts"].median()
h1 = cw[cw["ts"] < mid].groupby("source")["correct"].agg(["mean", "size"])
h2 = cw[cw["ts"] >= mid].groupby("source")["correct"].agg(["mean", "size"])
both = h1[h1["size"] >= 60][["mean"]].join(h2[h2["size"] >= 60][["mean"]],
                                           lsuffix="_h1", rsuffix="_h2").dropna()
rho, p = spearmanr(both["mean_h1"], both["mean_h2"])
print(f"\nCLEAN-window split-half ranking: rho={rho:+.3f} (p={p:.3f}, k={len(both)})")
print(both.round(3).to_string())
