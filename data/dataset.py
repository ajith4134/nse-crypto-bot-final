"""Assemble per-node golden datasets from cached crypto data.

Bridges sources + features into (X, y) ready for nodes, and provides a
CHRONOLOGICAL split (train on the past, test on the future) — the only honest
split for time series, and the literal 'known I/O first, then predict the
unknown future' loop.
"""
from __future__ import annotations

from data import features as F
from data.sources import fetch_coin, load_coin

MAJORS = ["bitcoin", "ethereum", "binancecoin", "solana"]
TARGETS = {"direction": "y_direction", "regime": "y_regime",
           "volatility": "y_vol_high"}  # classification targets


def ensure(coins: list[str] | None = None, days: int = 365) -> dict:
    """Fetch + cache each coin (skipping any that fail); return {coin: row_count}."""
    counts = {}
    for c in (coins or MAJORS):
        try:
            _, n = fetch_coin(c, days)
            counts[c] = n
        except Exception as e:                      # network / rate-limit -> skip this coin
            print(f"  [warn] fetch {c} failed: {e}")
    return counts


def make_combined(coins: list[str] | None = None, target: str = "direction",
                  days: int = 365) -> dict:
    """Multi-asset dataset: features per coin, concatenated. More samples and
    genuinely many co-existing regimes (each asset has its own dynamics)."""
    coins = coins or MAJORS
    got = ensure(coins, days)
    X, y, tags = [], [], []
    for c in [c for c in coins if c in got]:
        d = make_dataset(c, target)
        X += d["X"]; y += d["y"]; tags += [c] * len(d["X"])
        feats = d["feature_names"]
    return {"X": X, "y": y, "coin_tags": tags, "coins": list(got),
            "feature_names": feats, "n": len(X)}


def make_dataset(coin: str = "bitcoin", target: str = "direction") -> dict:
    rows = load_coin(coin)
    built = F.build(rows)
    if target not in TARGETS:
        raise ValueError(f"unknown classification target '{target}'")
    return {
        "coin": coin, "target": target,
        "feature_names": built["feature_names"],
        "dates": built["dates"],
        "X": built["X"], "y": built[TARGETS[target]],
        "y_return": built["y_return"],
    }


def chrono_split(X: list, y: list, train_frac: float = 0.7) -> tuple:
    cut = int(len(X) * train_frac)
    return X[:cut], y[:cut], X[cut:], y[cut:]
