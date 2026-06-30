#!/usr/bin/env bash
# Build the vendored FreqUI and deploy it into Freqtrade's served UI dir — NON-DESTRUCTIVELY.
#
# The dashboard server writes two runtime OVERLAY files into the served dir that the forked FreqUI
# reads same-origin: mlnb_status.json (carries the dashboard tunnel url for controls) and
# mlnb_markets.json (the markets screener rows). A naive `rm -rf installed && cp dist installed`
# DELETES those, which silently breaks the crypto controls ("Set: failed") and empties the markets
# table. This script rsyncs the fresh build over the served dir while PRESERVING the overlay files.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

DEST="$ROOT/.venv/lib/python3.13/site-packages/freqtrade/rpc/api_server/ui/installed"
SRC="$ROOT/vendor/frequi/dist"

echo "→ building FreqUI (vite)…"
( cd vendor/frequi && npm run build >/dev/null 2>&1 ) && echo "  build ok" || { echo "  BUILD FAILED"; exit 1; }

[ -f "$SRC/index.html" ] || { echo "no dist/index.html — build produced nothing"; exit 1; }
mkdir -p "$DEST"

echo "→ deploying dist → installed/ (preserving mlnb_*.json overlay files)…"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete --exclude 'mlnb_status.json' --exclude 'mlnb_markets.json' --exclude 'mlnb_candles.json' "$SRC/" "$DEST/"
else
  # rsync-less fallback: overwrite assets in place, never delete the overlay files
  cp -r "$SRC/." "$DEST/"
fi
echo "  deployed. overlay files intact:"
ls -1 "$DEST"/mlnb_*.json 2>/dev/null || echo "  (no overlay files yet — dashboard writer will create them)"
echo "Done. Hard-refresh FreqUI (Ctrl+Shift+R) to load the new bundle."
