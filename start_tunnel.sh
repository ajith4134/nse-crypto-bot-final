#!/usr/bin/env bash
# Relaunch the dashboard + gateway + pinned public tunnel.
# (Full stack incl. trading engines: use ./start_all.sh)
cd "$(dirname "$0")"
mkdir -p logs
pkill -x node 2>/dev/null; sleep 1
source .dashboard_creds 2>/dev/null
DASH_USER="${DASH_USER:-admin}" DASH_PASS="$DASH_PASS" setsid .venv/bin/python dashboard/server.py 8000 >dashboard/server.log 2>&1 </dev/null &
pgrep -x caddy >/dev/null || setsid "$HOME/.local/bin/caddy" run --config gateway/Caddyfile >logs/caddy.log 2>&1 </dev/null &
pkill -f "cloudflared tunnel" 2>/dev/null
setsid "$HOME/.local/bin/cloudflared" tunnel --url http://localhost:8100 --no-autoupdate >logs/cloudflared.log 2>&1 </dev/null &
setsid bash -c 'npx --yes localtunnel --port 8101 --subdomain ml-network-brain >tunnel.log 2>&1' </dev/null &
sleep 12
CF_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' logs/cloudflared.log | head -1)
if [ -n "$CF_URL" ]; then
  echo "$CF_URL" > public_link.txt
  echo "redir * ${CF_URL}{uri} temporary" > gateway/redirect.caddy
  pkill -x caddy 2>/dev/null; sleep 1
  setsid "$HOME/.local/bin/caddy" run --config gateway/Caddyfile >logs/caddy.log 2>&1 </dev/null &
fi
echo "One link: ${CF_URL:-pending, check logs/cloudflared.log}  ( / dashboard, /frequi/, /openalgo/ )"
echo "Backup:   https://ml-network-brain.loca.lt  (stable name; flaky on heavy pages; pw = server public IP)"
