#!/usr/bin/env bash
# Multi-timeframe candle download for top-volume Binance USDT perps (futures).
# Honest: pairs are the real top-300 by 24h quote volume (matches VolumePairList).
set -uo pipefail
cd "$(dirname "$0")"
VENV=~/.venv/bin
LOG=user_data/mtf_download.log
: > "$LOG"

echo "[$(date +%H:%M:%S)] building top-300 USDT perp pair list via ccxt…" | tee -a "$LOG"
PAIRS=$("$VENV/python" - <<'PY' 2>>"$LOG"
import ccxt
ex = ccxt.binanceusdm()
ex.load_markets()
t = ex.fetch_tickers()
rows = []
for sym, mk in ex.markets.items():
    if not mk.get("swap"): continue
    if mk.get("quote") != "USDT": continue
    if not mk.get("active", True): continue
    qv = (t.get(sym) or {}).get("quoteVolume") or 0
    rows.append((qv, sym))
rows.sort(reverse=True)
print(" ".join(s for _, s in rows[:300]))
PY
)
NP=$(wc -w <<< "$PAIRS")
echo "[$(date +%H:%M:%S)] resolved $NP pairs" | tee -a "$LOG"
if [ "$NP" -lt 5 ]; then echo "ABORT: pair list too small" | tee -a "$LOG"; exit 1; fi

echo "[$(date +%H:%M:%S)] starting download-data: tf=1m 5m 15m 1h 4h 1d, days=120, futures" | tee -a "$LOG"
"$VENV/freqtrade" download-data \
  --config config.json \
  --pairs $PAIRS \
  --timeframes 1m 5m 15m 1h 4h 1d \
  --days 120 \
  --trading-mode futures \
  --data-format-ohlcv feather \
  >> "$LOG" 2>&1
echo "[$(date +%H:%M:%S)] DONE rc=$?" | tee -a "$LOG"
