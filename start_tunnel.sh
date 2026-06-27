#!/usr/bin/env bash
# Relaunch the dashboard + pinned public tunnel.
cd "$(dirname "$0")"
pkill -x node 2>/dev/null; sleep 1
source .dashboard_creds 2>/dev/null
DASH_USER="${DASH_USER:-admin}" DASH_PASS="$DASH_PASS" setsid python3 dashboard/server.py 8000 >dashboard/server.log 2>&1 </dev/null &
setsid bash -c 'npx --yes localtunnel --port 8000 --subdomain ml-network-brain >tunnel.log 2>&1' </dev/null &
echo "Dashboard: https://ml-network-brain.loca.lt  (tunnel pw = server public IP)"
