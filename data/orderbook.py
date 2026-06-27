"""Order-book (L2) microstructure input — the project's stated path to real edge.

Binance public depth endpoint (no key) → rich L2 features per snapshot:
microprice deviation, level-1 and multi-level order-book imbalance, spread, and
bid/ask depth slope. `collect()` accumulates a bounded live history (there is NO
free historical L2 — honest limitation noted in the project memory), then
`make_orderbook_dataset()` builds X = OB features with targets = the NEXT
snapshot's mid-price move (direction / magnitude / volatility / regime).
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

from data.sources import CACHE

_BASE = "https://api.binance.com/api/v3"
_UA = {"User-Agent": "ml-brain/0.1"}

OB_FEATURES = ["spread", "l1_imbalance", "imbalance5", "imbalance_all",
               "microprice_dev", "bid_slope", "ask_slope", "depth_ratio"]


def snapshot(symbol="BTCUSDT", levels=20) -> dict:
    url = f"{_BASE}/depth?symbol={symbol}&limit={levels}"
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    bids = [(float(p), float(q)) for p, q in d["bids"]]
    asks = [(float(p), float(q)) for p, q in d["asks"]]
    bid, ask = bids[0][0], asks[0][0]
    bq, aq = bids[0][1], asks[0][1]
    mid = (bid + ask) / 2
    spread = (ask - bid) / mid
    bvol = sum(q for _, q in bids)
    avol = sum(q for _, q in asks)
    bvol5 = sum(q for _, q in bids[:5])
    avol5 = sum(q for _, q in asks[:5])
    micro = (bid * aq + ask * bq) / (bq + aq + 1e-9)        # microprice
    return {
        "mid": mid,
        "spread": spread,
        "l1_imbalance": (bq - aq) / (bq + aq + 1e-9),
        "imbalance5": (bvol5 - avol5) / (bvol5 + avol5 + 1e-9),
        "imbalance_all": (bvol - avol) / (bvol + avol + 1e-9),
        "microprice_dev": (micro - mid) / mid,
        # depth slope: how fast cumulative volume builds away from best price
        "bid_slope": (bids[0][0] - bids[-1][0]) / (sum(q for _, q in bids) + 1e-9),
        "ask_slope": (asks[-1][0] - asks[0][0]) / (sum(q for _, q in asks) + 1e-9),
        "depth_ratio": bvol / (avol + 1e-9),
    }


def collect(symbol="BTCUSDT", n=400, every=1.2) -> str:
    """Collect n live snapshots (~n*every seconds) into a CSV. Bounded (unlike
    tools/orderbook_collector.py which runs forever)."""
    path = os.path.join(CACHE, f"orderbook_{symbol}.csv")
    cols = ["ts", "mid"] + OB_FEATURES
    rows = []
    for _ in range(n):
        try:
            s = snapshot(symbol)
            rows.append([int(time.time()), s["mid"]] + [s[k] for k in OB_FEATURES])
        except Exception:
            pass
        time.sleep(every)
    with open(path, "w", encoding="utf-8") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(str(v) for v in r) + "\n")
    return path


def _targets_from_mid(mids: list[float]) -> dict:
    """Next-snapshot mid move targets (causal), mirroring features.build semantics."""
    n = len(mids) - 1
    rets = [mids[i + 1] / mids[i] - 1 for i in range(n)]
    direction = [1 if r > 0 else 0 for r in rets]
    absr = [abs(r) for r in rets]
    med = sorted(absr)[len(absr) // 2] if absr else 0.0
    volatility = [1 if a > med else 0 for a in absr]
    # regime = terciles of |move|
    order = sorted(range(n), key=lambda k: absr[k])
    regime = [0] * n
    third = max(1, n // 3)
    for rank, idx in enumerate(order):
        regime[idx] = 0 if rank < third else (2 if rank >= 2 * third else 1)
    return {"direction": direction, "magnitude": rets,
            "volatility": volatility, "regime": regime}


def make_orderbook_dataset(symbol="BTCUSDT") -> dict:
    """Build X = L2 features, targets = NEXT snapshot's mid move. Requires a
    collected orderbook_<symbol>.csv (run collect() first)."""
    path = os.path.join(CACHE, f"orderbook_{symbol}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} — run data.orderbook.collect('{symbol}') first")
    header, X, mids = None, [], []
    with open(path, encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        fi = [header.index(k) for k in OB_FEATURES]
        mi = header.index("mid")
        for line in f:
            p = line.strip().split(",")
            if len(p) < len(header):
                continue
            mids.append(float(p[mi]))
            X.append([float(p[k]) for k in fi])
    if len(X) < 30:
        raise RuntimeError(f"only {len(X)} OB snapshots — collect more first")
    tg = _targets_from_mid(mids)
    X = X[:-1]                                   # align to next-move targets
    return {"name": f"{symbol} order-book L2 microstructure", "source": "orderbook",
            "feature_names": OB_FEATURES, "n": len(X), "X": X,
            "y": tg["direction"], "targets": tg}
