"""Live Binance L2 order-book snapshot collector (no key).

Polls the depth endpoint and appends microstructure features (mid, spread,
depth imbalance, bid/ask volume) to data/cache/orderbook_<symbol>.csv. Order
book is a LIVE snapshot — this accumulates real history going forward, which can
later be joined to klines as features. Run in the background.

Run:  python3 tools/orderbook_collector.py [SYMBOL] [interval_seconds]
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

# Self-contained cache path (script may be run directly, with tools/ on sys.path).
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "cache")
os.makedirs(CACHE, exist_ok=True)

_BASE = "https://api.binance.com/api/v3"
_UA = {"User-Agent": "ml-brain/0.1"}


def snapshot(symbol="BTCUSDT", levels=20):
    url = f"{_BASE}/depth?symbol={symbol}&limit={levels}"
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    bids = [(float(p), float(q)) for p, q in d["bids"]]
    asks = [(float(p), float(q)) for p, q in d["asks"]]
    bid, ask = bids[0][0], asks[0][0]
    mid = (bid + ask) / 2
    spread = (ask - bid) / mid
    bvol = sum(q for _, q in bids)
    avol = sum(q for _, q in asks)
    imb = (bvol - avol) / (bvol + avol + 1e-9)        # >0 = bid-heavy (buy pressure)
    return mid, spread, imb, bvol, avol


def main(symbol="BTCUSDT", every=10):
    path = os.path.join(CACHE, f"orderbook_{symbol}.csv")
    new = not os.path.exists(path)
    f = open(path, "a", encoding="utf-8")
    if new:
        f.write("ts,mid,spread,imbalance,bid_vol,ask_vol\n")
        f.flush()
    while True:
        try:
            ts = int(time.time())
            m, s, i, bv, av = snapshot(symbol)
            f.write(f"{ts},{m},{s},{i},{bv},{av}\n")
            f.flush()
        except Exception:
            pass
        time.sleep(every)


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    every = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    main(sym, every)
