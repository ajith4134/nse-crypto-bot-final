#!/usr/bin/env bash
# Restart the dark-pro dashboard on :8000, detached. Safe pattern: matches only the
# real python process (".venv/bin/python dashboard/server.py"), never the caller's
# shell — a bare `pkill -f dashboard/server.py` kills the invoking wrapper too.
set -u
cd "$(dirname "$0")/.."
source .dashboard_creds 2>/dev/null || true
pkill -f "\.venv/bin/python dashboard/server\.py" 2>/dev/null
sleep 2
# NO_LOOP=1: the dashboard is the control-plane/VIEWER — it must NOT run the heavy in-process
# online paper-trading loop. That loop's net.predict/sklearn calls trigger a slow threadpoolctl
# scan over every loaded .so (many, since foundation-model libs load torch/chronos/etc.), which
# holds the GIL and WEDGES the HTTP server → Cloudflare 524 at ~90s (root-caused via py-spy
# 2026-07-03). Real trading runs in its own process (run_brain_loop.py / Freqtrade), unaffected.
# Run the online paper loop separately if wanted: .venv/bin/python -m trading.online.live_loop
NO_LOOP="${DASH_NO_LOOP:-1}" BRAIN_LOOP=1 setsid .venv/bin/python dashboard/server.py 8000 >dashboard/server.log 2>&1 </dev/null &
echo "dashboard restarting (pid $!)"
