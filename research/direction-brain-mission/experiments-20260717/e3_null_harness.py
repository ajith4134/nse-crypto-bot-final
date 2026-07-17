"""E3 — Shuffled-label null harness: how many "proven" buckets does our reliability
machinery invent from pure noise?

Buckets = (source × horizon × regime) over the clean window, n ≥ 30.
"Proven" bar (proxy for what the decider trusts): Wilson 95% lower bound > 0.50.
Compare real data against label permutations that PRESERVE each (symbol, ts, horizon)
outcome — i.e., shuffle which SOURCE said what, keeping the market's actual moves —
by permuting `correct` within (horizon × direction) strata to preserve base rates.
Report: proven buckets real vs null distribution → empirical FDR.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
from exp_common import load_claims, CLEAN_TS

rng = np.random.default_rng(20260717)
N_PERM = 500

cl = load_claims()
cl = cl[(cl["ts"] >= CLEAN_TS) & cl["horizon"].isin(["15m", "1h", "4h"])].copy()
cl["regime"] = cl["regime"].fillna("unknown")
print(f"clean-window labeled claims: {len(cl)}")

def proven_buckets(df, col="correct"):
    out = []
    for key, g in df.groupby(["source", "horizon", "regime"]):
        n = len(g)
        if n < 30:
            continue
        p = g[col].mean()
        # Wilson 95% lower bound
        z = 1.96
        den = 1 + z * z / n
        centre = p + z * z / (2 * n)
        adj = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
        lb = (centre - adj) / den
        if lb > 0.50:
            out.append((key, n, round(p, 3), round(lb, 3)))
    return out

real = proven_buckets(cl)
print(f"\nREAL: {len(real)} proven buckets (Wilson LB>0.5, n>=30):")
for k, n, p, lb in sorted(real, key=lambda r: -r[3])[:15]:
    print(f"  {k[0]:24s} {k[1]:4s} {k[2]:12s} n={n:5d} acc={p:.3f} LB={lb:.3f}")

# permutation: shuffle correct within (horizon, direction) strata
counts = []
strata = cl.groupby(["horizon", "direction"], group_keys=False)
for i in range(N_PERM):
    cl["perm"] = strata["correct"].transform(
        lambda s: s.sample(frac=1, random_state=int(rng.integers(1 << 31))).to_numpy())
    counts.append(len(proven_buckets(cl, "perm")))
counts = np.array(counts)
print(f"\nNULL ({N_PERM} permutations): proven buckets mean={counts.mean():.1f} "
      f"p50={np.median(counts):.0f} p95={np.percentile(counts, 95):.0f} max={counts.max()}")
print(f"P(null >= real {len(real)}) = {(counts >= len(real)).mean():.3f}")
print(f"Empirical FDR if we trust every proven bucket: ~{counts.mean()/max(1,len(real)):.2f}")
