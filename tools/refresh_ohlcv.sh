#!/usr/bin/env bash
# Daily OHLCV feather refresh — SELECTION-CRITIQUE 2026-07-17 defect I ("measurement
# debt"): the local 5m/15m/1h history had not refreshed since 07-16, so only 78 of 825
# clean-window trades were retro-measurable. Science must never be data-gated: refresh
# the existing pairs' candles every day.
#
# Deliberately boring: refreshes ONLY the pairs that already have feather files (both
# spot and futures dirs), 3-day lookback (download-data merges incrementally), flock so
# runs never overlap, nice/ionice so live loops keep the cores. Cron: 05:10 UTC daily
# (before the IST market open, crypto quiet hour). Log: logs/ohlcv_refresh.log.
set -u
cd "$HOME" || exit 1
exec 9>"$HOME/.ohlcv_refresh.lock"
flock -n 9 || { echo "$(date -u +%FT%TZ) another refresh is running; skip"; exit 0; }

FT="$HOME/.venv/bin/freqtrade"
UD="$HOME/trading/crypto/freqtrade/user_data"
CFG="$HOME/trading/crypto/freqtrade/config.json"
DATA="$UD/data/binance"
echo "$(date -u +%FT%TZ) refresh starting"

# pairs from the files that exist (BASE_USDT-5m.feather → BASE/USDT)
spot_pairs=$(ls "$DATA"/*-5m.feather 2>/dev/null \
  | sed -E 's#.*/([A-Z0-9]+)_USDT-5m\.feather#\1/USDT#' | sort -u)
fut_pairs=$(ls "$DATA/futures"/*-5m-futures.feather 2>/dev/null \
  | sed -E 's#.*/([A-Z0-9]+)_USDT_USDT-5m-futures\.feather#\1/USDT:USDT#' | sort -u)

run_dl() {  # $1=trading-mode  $2=pairs (newline-separated)
  local mode="$1" pairs="$2"
  [ -z "$pairs" ] && { echo "no $mode pairs found; skip"; return 0; }
  # shellcheck disable=SC2086
  nice -n 15 ionice -c3 "$FT" download-data \
    --config "$CFG" --userdir "$UD" --trading-mode "$mode" \
    --timeframes 5m 15m 1h --days 3 --pairs $pairs \
    2>&1 | tail -5
}

run_dl futures "$fut_pairs"
run_dl spot "$spot_pairs"
echo "$(date -u +%FT%TZ) refresh done (futures $(echo "$fut_pairs" | wc -w) pairs, spot $(echo "$spot_pairs" | wc -w) pairs)"
