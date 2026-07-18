"""Honest edge test — does ANY feature carry information about the forward move?

Companion to label_dataset.py. Everything here exists to make it HARD to fool ourselves,
because the 2026-07-18 audit found the live system had zero measured entry edge while every
dashboard signal looked plausible.

THE DISCIPLINE:
- **Time-ordered split, never random.** Overlapping windows on financial series make random
  CV report edge that does not exist.
- **Embargo** between train and test so a row adjacent in time cannot leak its label.
- **A shuffled-label control** runs beside every real test. If the real score is not clearly
  above the shuffled score, there is NO edge — this is the check that would have saved us
  ten experiments.
- **Cost-aware scoring.** Accuracy on `y_up` is vanity; what matters is whether acting on the
  signal clears round-trip fees, so we score net-of-cost expectancy too.
"""
from __future__ import annotations

import math

import pandas as pd

COST_PCT = 0.10          # round-trip taker cost, % of notional


def time_split(df: pd.DataFrame, train_frac: float = 0.6, embargo_frac: float = 0.02):
    """Chronological train/test split with an embargo gap between them."""
    d = df.sort_values("ts").reset_index(drop=True)
    n = len(d)
    cut = int(n * train_frac)
    gap = int(n * embargo_frac)
    return d.iloc[:cut], d.iloc[cut + gap:]


def single_feature_ic(df: pd.DataFrame, feature: str, label: str = "fwd_12") -> dict:
    """Spearman-style rank IC plus a t-stat. IC is the honest first look: does the feature
    RANK future returns at all? |IC| under ~0.02 is noise at these sample sizes."""
    d = df[[feature, label]].dropna()
    if len(d) < 200:
        return {"n": len(d), "ic": 0.0, "t": 0.0}
    ic = d[feature].rank().corr(d[label].rank())
    if ic is None or (isinstance(ic, float) and math.isnan(ic)):
        ic = 0.0
    t = ic * math.sqrt(max(1, len(d) - 2)) / math.sqrt(max(1e-9, 1 - ic * ic))
    return {"n": len(d), "ic": float(ic), "t": float(t)}


def quantile_spread(df: pd.DataFrame, feature: str, label: str = "fwd_12",
                    q: int = 5) -> dict:
    """Split the feature into q buckets and report mean forward return per bucket. A real
    signal shows a MONOTONE gradient (the liquidity finding did); a fluke shows one odd
    bucket. Also reports the top-minus-bottom spread NET of round-trip cost."""
    d = df[[feature, label]].dropna()
    if len(d) < q * 100:
        return {"n": len(d), "buckets": [], "spread_net": 0.0}
    try:
        d["b"] = pd.qcut(d[feature].rank(method="first"), q, labels=False)
    except ValueError:
        return {"n": len(d), "buckets": [], "spread_net": 0.0}
    means = d.groupby("b")[label].mean().tolist()
    spread = means[-1] - means[0] if means else 0.0
    return {"n": len(d), "buckets": [round(m, 4) for m in means],
            "spread_net": round(spread - COST_PCT, 4)}


def shuffled_control(df: pd.DataFrame, feature: str, label: str = "fwd_12",
                     seed: int = 7) -> dict:
    """Same IC computation with the label SHUFFLED — the null. Any real result must clear
    this by a wide margin, otherwise we are reading noise."""
    d = df[[feature, label]].dropna().copy()
    if len(d) < 200:
        return {"n": len(d), "ic": 0.0, "t": 0.0}
    d[label] = d[label].sample(frac=1.0, random_state=seed).to_numpy()
    return single_feature_ic(d, feature, label)


def screen(df: pd.DataFrame, features: list[str], label: str = "fwd_12") -> pd.DataFrame:
    """Rank every feature by out-of-sample IC against its own shuffled control.

    Returns one row per feature: train IC, TEST IC, the shuffled-control IC, and the
    net-of-cost quintile spread. Trust nothing whose test IC does not clearly exceed its
    control, no matter how good the story is.
    """
    tr, te = time_split(df)
    out = []
    for f in features:
        if f not in df.columns:
            continue
        a = single_feature_ic(tr, f, label)
        b = single_feature_ic(te, f, label)
        c = shuffled_control(te, f, label)
        qs = quantile_spread(te, f, label)
        out.append({
            "feature": f, "n_test": b["n"],
            "ic_train": round(a["ic"], 4), "ic_test": round(b["ic"], 4),
            "t_test": round(b["t"], 2),
            "ic_shuffled": round(c["ic"], 4),
            "beats_null": abs(b["ic"]) > 3 * max(0.001, abs(c["ic"])) and abs(b["t"]) > 3,
            "q_spread_net": qs["spread_net"],
        })
    return pd.DataFrame(out).sort_values("ic_test", key=lambda s: s.abs(), ascending=False)
