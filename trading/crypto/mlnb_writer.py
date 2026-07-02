"""trading/crypto/mlnb_writer.py — standalone same-origin overlay writer for the forked FreqUI.

The dashboard server (dashboard/server.py) normally runs this as a background thread, but if that
thread dies the FreqUI loses its two same-origin overlay files and the embedded controls break
(no dashboard_url → every "Set" returns "failed") and the markets table empties. This standalone
daemon regenerates both files every `INTERVAL` seconds, decoupled from the server process so it
survives a dead writer thread without restarting the live trade loop.

  • mlnb_markets.json  — ranked live perp markets (symbol/price/24h%/volume/volatility/funding)
  • mlnb_status.json   — live crypto params + the dashboard's public tunnel URL (for cross-origin
                         control POSTs back to the dashboard)

Run: .venv/bin/python -m trading.crypto.mlnb_writer
"""
from __future__ import annotations

import json
import os
import re
import time

INTERVAL = 10
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _uidir() -> str:
    import freqtrade as _ft
    return os.path.join(os.path.dirname(_ft.__file__), "rpc", "api_server", "ui", "installed")


def _dash_url() -> str:
    """The dashboard's own public tunnel URL (latest trycloudflare URL in cloudflared.log)."""
    try:
        with open(os.path.join(ROOT, "cloudflared.log")) as f:
            urls = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", f.read())
        return urls[-1] if urls else ""
    except Exception:
        return ""


def write_once(uidir: str) -> None:
    from trading.crypto.markets import live_markets
    from trading.crypto.freqtrade import control as ctl
    try:
        rows = live_markets(segment="perp", sort="volume", limit=300)
        if rows:
            with open(os.path.join(uidir, "mlnb_markets.json"), "w") as f:
                json.dump({"rows": rows}, f)
    except Exception:
        pass
    try:
        with open(os.path.join(uidir, "mlnb_status.json"), "w") as f:
            json.dump({"params": ctl.status(), "dashboard_url": _dash_url()}, f)
    except Exception:
        pass


def main() -> int:
    uidir = _uidir()
    os.makedirs(uidir, exist_ok=True)
    while True:
        write_once(uidir)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
