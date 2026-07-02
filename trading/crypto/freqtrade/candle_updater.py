"""trading/crypto/freqtrade/candle_updater.py — keep OHLCV candle data continuously fresh.

Loops forever: refresh the multi-timeframe candle data for the top-volume USDT perps (incremental —
freqtrade download-data only fetches the missing recent candles, so cycles after the first are fast),
writing a STATUS file the forked FreqUI reads same-origin to show a live "candles: updating / updated
Nm ago" indicator. Honest: pairs are the real top-N by 24h quote volume (matches VolumePairList).

Run (in the persistent session, since the agent sandbox reaps daemons):
  nohup setsid .venv/bin/python -m trading.crypto.freqtrade.candle_updater >dashboard/candle_updater.log 2>&1 &

Env knobs: CANDLE_UPDATE_INTERVAL (s, default 900), CANDLE_UPDATE_PAIRS (default 300),
CANDLE_UPDATE_DAYS (default 120), CANDLE_UPDATE_TFS (default "1m 5m 15m 1h 4h 1d").
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
INTERVAL = int(os.getenv("CANDLE_UPDATE_INTERVAL", "900"))
N_PAIRS = int(os.getenv("CANDLE_UPDATE_PAIRS", "300"))
DAYS = os.getenv("CANDLE_UPDATE_DAYS", "120")
TFS = os.getenv("CANDLE_UPDATE_TFS", "1m 5m 15m 1h 4h 1d").split()


def _uidir() -> str:
    import freqtrade as _ft
    return os.path.join(os.path.dirname(_ft.__file__), "rpc", "api_server", "ui", "installed")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_status(uidir: str, **fields) -> None:
    try:
        with open(os.path.join(uidir, "mlnb_candles.json"), "w") as f:
            json.dump(fields, f)
    except Exception:
        pass


def _top_pairs(n: int) -> list[str]:
    """Top-n USDT perps by 24h quote volume (real ccxt data, matches the pairlist)."""
    try:
        import ccxt
        ex = ccxt.binanceusdm()
        ex.load_markets()
        tickers = ex.fetch_tickers()
        rows = []
        for sym, mk in ex.markets.items():
            if not mk.get("swap") or mk.get("quote") != "USDT" or not mk.get("active", True):
                continue
            qv = (tickers.get(sym) or {}).get("quoteVolume") or 0
            rows.append((qv, sym))
        rows.sort(reverse=True)
        return [s for _, s in rows[:n]]
    except Exception:
        return []


def run_cycle(uidir: str, cycle: int) -> None:
    pairs = _top_pairs(N_PAIRS)
    if len(pairs) < 5:
        _write_status(uidir, state="error", reason="pair list too small", updated_at=_now(), cycle=cycle)
        return
    _write_status(uidir, state="updating", started_at=_now(), pairs=len(pairs),
                  timeframes=TFS, days=int(DAYS), cycle=cycle)
    cmd = [os.path.join(ROOT, ".venv", "bin", "freqtrade"), "download-data",
           "--config", os.path.join(HERE, "config.json"),
           "--pairs", *pairs, "--timeframes", *TFS,
           "--days", str(DAYS), "--trading-mode", "futures",
           "--data-format-ohlcv", "feather"]
    rc = 1
    try:
        rc = subprocess.run(cmd, cwd=HERE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL).returncode
    except Exception as e:
        _write_status(uidir, state="error", reason=str(e), updated_at=_now(), cycle=cycle)
        return
    _write_status(uidir, state="idle", updated_at=_now(), pairs=len(pairs),
                  timeframes=TFS, days=int(DAYS), cycle=cycle, last_rc=rc)


def main() -> int:
    uidir = _uidir()
    os.makedirs(uidir, exist_ok=True)
    cycle = 0
    while True:
        cycle += 1
        run_cycle(uidir, cycle)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
