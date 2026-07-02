#!/usr/bin/env bash
# Boot the ENTIRE bot after a VPS restart — one command, one public link.
#   bash ~/start_all.sh
# Starts: OpenAlgo (NSE), Freqtrade (crypto), candle updater, brain loop,
# dashboard, Caddy gateway, public tunnel. Safe to re-run (skips running parts).
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p logs
source .dashboard_creds 2>/dev/null || true

echo "[1/7] OpenAlgo (NSE engine)  :5000 REST  :8765 WS"
bash srv/openalgo/start_local.sh

echo "[2/7] Freqtrade (crypto engine)  :8080"
if ! pgrep -f "freqtrade trade" >/dev/null; then
  .venv/bin/python -m trading.crypto.freqtrade.launch   # regenerates config.json + start.sh
  setsid bash trading/crypto/freqtrade/start.sh >logs/freqtrade.log 2>&1 </dev/null &
fi

echo "[3/7] Candle updater (FreqUI charts on all timeframes)"
pgrep -f "freqtrade.candle_updater" >/dev/null || \
  setsid .venv/bin/python -m trading.crypto.freqtrade.candle_updater >logs/candle_updater.log 2>&1 </dev/null &

echo "[4/7] Brain loop (this is what actually opens crypto trades)"
pgrep -f "freqtrade.run_brain_loop" >/dev/null || \
  setsid .venv/bin/python -m trading.crypto.freqtrade.run_brain_loop >logs/brain_loop.log 2>&1 </dev/null &

echo "[5/7] Dashboard (brain + NSE trading)  :8000"
pgrep -f "dashboard/server.py" >/dev/null || \
  DASH_USER="${DASH_USER:-admin}" DASH_PASS="${DASH_PASS:-}" \
  setsid .venv/bin/python dashboard/server.py 8000 >dashboard/server.log 2>&1 </dev/null &

echo "[6/7] Gateway (Caddy, single entry point)  :8100"
pgrep -x caddy >/dev/null || \
  setsid "$HOME/.local/bin/caddy" run --config gateway/Caddyfile >logs/caddy.log 2>&1 </dev/null &

echo "[7/7] Public tunnels -> gateway"
# PRIMARY: cloudflared (handles parallel asset loads; localtunnel 502s on JS-heavy
# pages like FreqUI/OpenAlgo). URL changes on each restart -> saved to ~/public_link.txt
if ! pgrep -f "cloudflared tunnel" >/dev/null; then
  setsid "$HOME/.local/bin/cloudflared" tunnel --url http://localhost:8100 --no-autoupdate >logs/cloudflared.log 2>&1 </dev/null &
fi
# STABLE: ngrok reserved static domain -> gateway :8100. This is the permanent
# public URL registered as Zerodha's REDIRECT_URL/HOST_SERVER in srv/openalgo/.env,
# so the broker OAuth login + callback both land on ONE stable domain (no
# cross-domain session-cookie loop). Free tier shows a one-time "Visit Site"
# interstitial whose cookie then suppresses it for 7 days per browser.
pgrep -f "ngrok http" >/dev/null || \
  setsid "$HOME/.local/bin/ngrok" http --domain=claw-repent-carving.ngrok-free.dev 8100 --log=stdout >logs/ngrok.log 2>&1 </dev/null &

# loca.lt tunnel -> :8101 (legacy backup callback path; ngrok above is now the
# primary stable Zerodha redirect. Everything else redirects to the cloudflared URL)
pgrep -f "localtunnel --port 8101" >/dev/null || \
  setsid bash -c 'npx --yes localtunnel --port 8101 --subdomain ml-network-brain >tunnel.log 2>&1' </dev/null &

sleep 12
CF_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' logs/cloudflared.log | head -1)
if [ -n "$CF_URL" ]; then
  echo "$CF_URL" > public_link.txt
  echo "redir * ${CF_URL}{uri} temporary" > gateway/redirect.caddy
  pkill -x caddy 2>/dev/null; sleep 1
  setsid "$HOME/.local/bin/caddy" run --config gateway/Caddyfile >logs/caddy.log 2>&1 </dev/null &
fi
echo; echo "== Health =="
printf "%-45s %s\n" "OpenAlgo   http://127.0.0.1:5000/"        "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:5000/)"
printf "%-45s %s\n" "Freqtrade  http://127.0.0.1:8080/api/v1/ping" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:8080/api/v1/ping)"
printf "%-45s %s\n" "Dashboard  http://127.0.0.1:8000/"        "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:8000/)"
printf "%-45s %s\n" "Gateway    http://127.0.0.1:8100/"        "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:8100/)"
echo
echo "================= ONE LINK ================="
echo "  ${CF_URL:-<cloudflared URL pending — check: grep trycloudflare logs/cloudflared.log>}"
echo "    /          -> brain + NSE trading dashboard"
echo "    /frequi/   -> FreqUI (crypto / Freqtrade)"
echo "    /openalgo/ -> OpenAlgo (NSE broker platform)"
echo "  (URL changes each restart; also saved to ~/public_link.txt)"
echo "  STABLE link (Zerodha login + all; click 'Visit Site' once per 7 days):"
echo "  https://claw-repent-carving.ngrok-free.dev"
echo "  Backup (stable name, flaky on heavy pages):"
echo "  https://ml-network-brain.loca.lt  (tunnel pw = server public IP)"
echo "============================================"
