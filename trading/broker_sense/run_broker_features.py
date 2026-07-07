"""trading/broker_sense/run_broker_features.py — read every built-in broker picker in one process.

Like run_app_school, this exists so Playwright runs on its own main thread (the dashboard's
request thread can't drive it — greenlet error). Reads all pickers in PARALLEL, fuses them, and
records snapshots (for new-entry detection + stacking credit). Read-only.

    python -m trading.broker_sense.run_broker_features <broker>
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    broker = (sys.argv[1] if len(sys.argv) > 1 else "binance").lower()
    from trading.broker_sense import broker_features as bf
    fmap = bf.read_all_features(broker, limit=25, parallel=True)
    fused = bf.fuse(broker, fmap)
    out = {"broker": broker,
           "features_read": {k: len(v) for k, v in fmap.items()},
           "fused_top": [{"symbol": c["symbol"], "score": c["score"], "side": c["side"],
                          "n_features": len(c["features"])} for c in fused[:15]]}
    print("BROKER_FEATURES_RESULT " + json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
