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

echo "[2/7] Freqtrade (crypto engine)  :8080  — ACTIVE (owner graduated from the sandbox 2026-07-06)."
echo "      Set CRYPTO_ENGINE=sandbox to fall back to the fast paper-learning sandbox."
# SHORTS ENABLED (owner 2026-07-22: "huge sudden profit symbols placing short"): the earlier
# LONG-only opening order is superseded — confirmed SHORTs (spike_fade lane) may now open.
# Must be exported BEFORE the freqtrade launch below (practice_gate reads it in-engine) and
# also covers the notebook runner further down.
export NOTEBOOK_LONG_ONLY="${NOTEBOOK_LONG_ONLY:-0}"
if [ "${CRYPTO_ENGINE:-freqtrade}" = "freqtrade" ] && ! pgrep -f "freqtrade trade" >/dev/null; then
  .venv/bin/python -m trading.crypto.freqtrade.launch   # regenerates config.json + start.sh
  setsid bash trading/crypto/freqtrade/start.sh >logs/freqtrade.log 2>&1 </dev/null &
fi

echo "[3/7] Candle updater — DISABLED 2026-07-12 (owner: remove its API load)"
# candle_updater ran `freqtrade download-data` over ~300 pairs × 6 TFs × 120d in a loop —
# a HUGE Binance REST burst that was a top -1003/418 IP-ban contributor and pure anti-motto
# (data must come from web-navigation, not API polling). It only fed FreqUI's "candles
# updating" freshness badge, NOT the brain's trade candles (those come from the UI-only
# doors / multi-venue pool). Removed. Set CANDLE_UPDATER=1 to re-enable if ever needed.
if [ "${CANDLE_UPDATER:-0}" = "1" ]; then
  pgrep -f "freqtrade.candle_updater" >/dev/null || \
    setsid .venv/bin/python -m trading.crypto.freqtrade.candle_updater >logs/candle_updater.log 2>&1 </dev/null &
fi

echo "[4/7] Brain loop (this is what actually opens crypto trades)"
# CORTEX shadow mode: log the cortex signal beside the live decider every bar
# (paper-first — promote to live with CORTEX_TRADE=1). See memory cortex-network-built.
export CORTEX_SIGNAL="${CORTEX_SIGNAL:-1}"
# UQ gate: PAPER learn-lab lets every directional signal through so trades actually
# open (calibrated p_up is currently < θ0.55 for most coins → all abstained otherwise).
# REVERT to UQ_GATE=1 before going live (capital-preservation). See memory pillar17-conformal-uq.
export UQ_GATE="${UQ_GATE:-0}"
# High-throughput paper mode + profit tailgating (owner)
export CRYPTO_MIN_SCORE="${CRYPTO_MIN_SCORE:-0.25}"
export CRYPTO_MIN_PSR="${CRYPTO_MIN_PSR:-0.10}"
export PROFIT_TAILGATE="${PROFIT_TAILGATE:-1}"
# Direction-driver + vision-exit + Binance-filter TOP-N breadth lane (owner 2026-07-12).
# Exported HERE so every respawn (loop_keeper included) carries them, not just manual restarts.
# See memory: direction-driver-replaces-vote, binance-filter-topn-lane.
export VISION_EXIT="${VISION_EXIT:-trade}"                 # vision-read exit acts (not shadow)
export LEARNED_DIRECTION="${LEARNED_DIRECTION:-1}"         # reliability-weighted direction gate
export BINANCE_FILTER_LANE="${BINANCE_FILTER_LANE:-1}"     # top-N breadth lane ON (kill: =0)
export BINANCE_FILTER_PRESET="${BINANCE_FILTER_PRESET:-momentum}"
# MULTI-PRESET breadth (owner 2026-07-13): rank the full RAM universe across several presets so
# diverse dislocations open, not just the same momentum movers. TOPN raised 20→50 (bigger union).
export BINANCE_FILTER_PRESETS="${BINANCE_FILTER_PRESETS:-momentum,squeeze,funding_extreme,liquidity}"
export BINANCE_FILTER_TOPN="${BINANCE_FILTER_TOPN:-50}"
# UI-ONLY DATA (owner goal 2026-07-07): 1 = the eyes' captured trading-app payloads are
# the ONLY market-data source (every free-API poll/fallback disabled; misses are honest
# data-failures in the evidence lane). Flip to 1 once /api/trading/ui_data shows the
# eyes' per-symbol candle coverage is warm (the funnel goes dark on uncovered symbols).
export UI_ONLY_DATA="${UI_ONLY_DATA:-0}"
# Strategy CREATION/MUTATION/EVOLUTION engine (DEAP NSGA-II). PAPER learn-lab: armed so the
# brain breeds new strategies each learning cycle and trades the best guardrail-passed survivor
# (trading/strategy/evolved_link.py). REVERT to =0 before going live until the paper→live
# promotion gate is proven. See memory strategy-foundry / project-prime-directive.
export STRATEGY_EVOLUTION_ENABLED="${STRATEGY_EVOLUTION_ENABLED:-1}"
# Strategy-Generator Portfolio (trading/strategy/generators): the DEAP evolver + 6 SOTA
# generators, all scored through ONE CPCV+DSR+PBO + family-wise gate. Per-generator kill
# switches (all default ON). Flip PYSR_GEN=0 if the Julia warm-up makes the brain cycle slow,
# or LLM_MUTATION/RD_AGENT=0 to cut LLM calls. FWER_GATE=1 = family-wise error control on.
export LLM_MUTATION="${LLM_MUTATION:-1}"        # ② LLM-as-mutation-operator (needs an LLM key)
export PYSR_GEN="${PYSR_GEN:-1}"                # ③ PySR symbolic regression (Julia warm-up ~min)
export ALPHA_MINING="${ALPHA_MINING:-1}"        # ⑤ formulaic-alpha mining (AlphaGen vocabulary)
export OPTUNA_GEN="${OPTUNA_GEN:-1}"            # ⑥ Optuna NSGA-II linear-alpha tuner
export RD_AGENT="${RD_AGENT:-1}"                # ⑦ RD-Agent(Q) LLM factor researcher (needs LLM)
export FWER_GATE="${FWER_GATE:-1}"             # ⑥ family-wise (StepM) error control in the gate
# STRATEGY-ON-EVERY-TRADE (owner 2026-07-13): the per-coin best-strategy table (run_strategy_table
# producer) feeds the funnel two ways. STRATEGY_TABLE=1 runs the producer + the ATTRIBUTION (every
# trade's Strategy column shows a real library/created/evolved/researched strategy — pure learning).
# STRATEGY_DIRECTION=1 turns on the SYNERGY: the tournament's best strategy is a measured direction
# source AND a gate-clearing strategy DRIVES the breadth entry (tag = its name). =0 to shadow.
export STRATEGY_TABLE="${STRATEGY_TABLE:-1}"
export STRATEGY_DIRECTION="${STRATEGY_DIRECTION:-1}"
# ZERO-LAG RAM budget (owner 2026-07-06): use ~27 of 32 GB, spare 5 GB. RAM headroom feeds
# warm candle/quote/book caches (hold ALL whitelisted pairs in memory → no re-fetch lag) for the
# Binance (crypto) + Upstox (NSE) funnel. Broker-picker parallelism stays ban-safe (NOT raised).
export BRAIN_RAM_BUDGET_GB="${BRAIN_RAM_BUDGET_GB:-27}"
export BROKER_SENSE_BUDGET="${BROKER_SENSE_BUDGET:-120}"   # longer scan/cycle using the headroom
# HEADED-under-Xvfb by default (2026-07-11): Upstox Pro hangs headless AND the Live
# Video mirror needs a real display to capture — a reboot used to silently drop both
# funnels back to headless (live stream "unavailable", NSE eyes blind). Costs ~1.5GB
# per chromium; set 0 to fall back to headless.
export BROKER_SENSE_HEADED="${BROKER_SENSE_HEADED:-1}"
# NAV_BRAIN=1 (2026-07-11, verified live): route the funnel's Binance browsing through the
# intelligent Planner-Actor-Validator loop (nav_brain) — purposeful, segment-gated, self-correcting.
export NAV_BRAIN="${NAV_BRAIN:-1}"
export BRAIN_WARM_ALL_PAIRS="${BRAIN_WARM_ALL_PAIRS:-1}"   # keep every pair's candles warm in RAM
# EXPLORE OPEN-ALL: PAPER-open EVERY candidate blindly (direction from app data, vetoes advisory) to
# fill the journal. OWNER TURNED THIS OFF 2026-07-12: the brain now SELECTS trades with the full
# 239-strategy library tournament (percoin_decider) + the safety gates — strategy-driven, higher-
# conviction entries instead of blind explore. Set BRAIN_EXPLORE_OPEN_ALL=1 to re-enable exploration.
export BRAIN_EXPLORE_OPEN_ALL="${BRAIN_EXPLORE_OPEN_ALL:-0}"
# GRADUATION SIGNAL (owner 2026-07-06): graduate on the brain CONSISTENTLY PICKING PROFITABLE /
# CORRECT-DIRECTION trades, NOT a raw trade COUNT (thousands of trades exist yet a big count proves
# no skill). ACC = rolling win-rate the brain must hold over the last WINDOW closed trades before it
# earns the selective gate (a profitable directional trade == a correct entry direction). At today's
# ~34% last-50 win rate this keeps exploring; it graduates only once the brain sustains 55%+.
export BRAIN_EXPLORE_GRADUATE_ACC="${BRAIN_EXPLORE_GRADUATE_ACC:-0.55}"
export BRAIN_EXPLORE_GRADUATE_WINDOW="${BRAIN_EXPLORE_GRADUATE_WINDOW:-50}"
# EXPLORE-WIDE breadth (owner 2026-07-07: "32 GB RAM — open more trades"): screened picker
# candidates beyond the deep shortlist enter light per cycle (paper explore only).
export BROKER_SENSE_EXPLORE_WIDE_N="${BROKER_SENSE_EXPLORE_WIDE_N:-40}"
# BRAIN-OPEN mirrors run IN the funnel processes (crypto → Binance ⭐ Favorites, NSE →
# Upstox 'Brain-Open'); the account write is ON per the owner's 2026-07-07 order.
export BROKER_WATCHLIST_WRITE="${BROKER_WATCHLIST_WRITE:-1}"
# Legacy count gate — used only when ACC is unset/0. 0 = never graduate on count.
export BRAIN_EXPLORE_GRADUATE_N="${BRAIN_EXPLORE_GRADUATE_N:-0}"
# TRADE DRIVER: the broker-sense funnel (below) is the SOLE driver — it selects trades from
# Binance's built-in ranked pickers/features + discovered URLs (API OHLCV as fallback). The old
# API-path run_brain_loop is OFF by default (set USE_API_BRAIN_LOOP=1 to run it too — NOT advised,
# both call /forceenter → double entries). Owner directive 2026-07-06.
if [ "${CRYPTO_ENGINE:-freqtrade}" = "freqtrade" ] && [ "${USE_API_BRAIN_LOOP:-0}" = "1" ]; then
  pgrep -f "freqtrade.run_brain_loop" >/dev/null || \
    CORTEX_SIGNAL="$CORTEX_SIGNAL" UQ_GATE="$UQ_GATE" \
    STRATEGY_EVOLUTION_ENABLED="$STRATEGY_EVOLUTION_ENABLED" \
    LLM_MUTATION="$LLM_MUTATION" PYSR_GEN="$PYSR_GEN" ALPHA_MINING="$ALPHA_MINING" \
    OPTUNA_GEN="$OPTUNA_GEN" RD_AGENT="$RD_AGENT" FWER_GATE="$FWER_GATE" \
    setsid .venv/bin/python -m trading.crypto.freqtrade.run_brain_loop >logs/brain_loop.log 2>&1 </dev/null &
fi
# Brain SANDBOX loop: fast paper learning — ONLY when CRYPTO_ENGINE=sandbox. The owner has
# graduated to Freqtrade (CRYPTO_ENGINE=freqtrade), so the sandbox stays OFF unless explicitly
# re-selected. Code is kept; this is just the engine switch (2026-07-06).
if [ "${CRYPTO_ENGINE:-freqtrade}" = "sandbox" ]; then
  pgrep -f "sandbox.run_sandbox_loop" >/dev/null || \
    setsid .venv/bin/python -m trading.sandbox.run_sandbox_loop >logs/sandbox_loop.log 2>&1 </dev/null &
fi
# Broker-Sense funnel: THE trade driver. Screens the universe on the BROKERS' servers (Binance
# built-in ranked pickers/features + discovered URLs), selects entries for crypto (always) + NSE
# (Upstox, inside exchange hours), API OHLCV as fallback. Paper-first. Uses the RAM budget above.
# SEPARATE PROCESSES (2026-07-07): crypto and NSE each run in their OWN funnel process, so a slow
# crypto cycle (blew 120s→2455s) can never starve NSE and stop NSE trades opening during market
# hours. Select the market with BROKER_SENSE_MARKETS. Shared env below.
_bs_env() { echo "CORTEX_SIGNAL=$CORTEX_SIGNAL UQ_GATE=$UQ_GATE BRAIN_RAM_BUDGET_GB=$BRAIN_RAM_BUDGET_GB \
UI_ONLY_DATA=$UI_ONLY_DATA \
BROKER_SENSE_BUDGET=$BROKER_SENSE_BUDGET BRAIN_WARM_ALL_PAIRS=$BRAIN_WARM_ALL_PAIRS \
BRAIN_EXPLORE_OPEN_ALL=$BRAIN_EXPLORE_OPEN_ALL BRAIN_EXPLORE_GRADUATE_N=$BRAIN_EXPLORE_GRADUATE_N \
BRAIN_EXPLORE_GRADUATE_ACC=$BRAIN_EXPLORE_GRADUATE_ACC BRAIN_EXPLORE_GRADUATE_WINDOW=$BRAIN_EXPLORE_GRADUATE_WINDOW \
BROKER_SENSE_EXPLORE_WIDE_N=$BROKER_SENSE_EXPLORE_WIDE_N BROKER_WATCHLIST_WRITE=$BROKER_WATCHLIST_WRITE \
BROKER_SENSE_HEADED=$BROKER_SENSE_HEADED NAV_BRAIN=$NAV_BRAIN"; }
pgrep -f "run_funnel_loop crypto" >/dev/null || \
  env $(_bs_env) \
  setsid .venv/bin/python -m trading.broker_sense.run_funnel_loop crypto >>logs/funnel_crypto.log 2>&1 </dev/null &
# NSE funnel kill-switch (owner 2026-07-13): set NSE_FUNNEL_OFF=1 in .env to keep the NSE
# trading funnel stopped across restarts/loop_keeper respawns. Crypto is unaffected. Read
# straight from .env so it works even when start_all runs without .env in its environment.
_NSE_OFF="${NSE_FUNNEL_OFF:-$(grep -E '^NSE_FUNNEL_OFF=' .env 2>/dev/null | tail -1 | cut -d= -f2)}"
# KITE_STREAM (owner 2026-07-14): the NSE funnel starts the Zerodha in-RAM data mirror so SELECTION
# reads off the PAID Zerodha feed instead of per-cycle OpenAlgo REST. The feed is OpenAlgo's unified
# WebSocket (:8765) — OpenAlgo fronts Zerodha (runs KiteTicker, owns the DAILY token, maps symbols),
# so NO kiteconnect and NO KITE_ACCESS_TOKEN are needed; it uses the existing OPENALGO_API_KEY.
# Default ON; set KITE_STREAM=0 in .env to disable (mirror is an idle no-op → OpenAlgo REST fallback).
[ "${_NSE_OFF:-0}" = "1" ] || pgrep -f "run_funnel_loop nse" >/dev/null || \
  env $(_bs_env) BROKER_SENSE_NSE=1 KITE_STREAM="${KITE_STREAM:-1}" \
  setsid .venv/bin/python -m trading.broker_sense.run_funnel_loop nse >>logs/funnel_nse.log 2>&1 </dev/null &

echo "[5/7] Dashboard (brain + NSE trading)  :8000  — VIEWER (NO_LOOP=1, no in-process trading)"
# NO_LOOP=1 (2026-07-07): the dashboard must NOT run the heavy trade loop in-process — a big
# watchlist pricing tick starves the GIL and wedges the HTTP server (memory dashboard-524-wedge).
# The live trade loop runs as its OWN process below, so the UI stays responsive.
pgrep -f "dashboard/server.py" >/dev/null || \
  DASH_USER="${DASH_USER:-admin}" DASH_PASS="${DASH_PASS:-}" BRAIN_LOOP=1 NO_LOOP=1 \
  STRATEGY_EVOLUTION_ENABLED="$STRATEGY_EVOLUTION_ENABLED" \
  setsid .venv/bin/python dashboard/server.py 8000 >dashboard/server.log 2>&1 </dev/null &

# Online live trade loop — its OWN process (NSE intraday/mtf/options + crypto paper driver).
# Separate from the dashboard (no GIL wedge) AND from the funnels (no cross-market blocking):
# three independent loops. This is the NSE OPTIONS driver (all indices incl. BSE Sensex/Bankex).
pgrep -f "trading.online.run_live_loop" >/dev/null || \
  CORTEX_SIGNAL="$CORTEX_SIGNAL" UQ_GATE="$UQ_GATE" \
  BRAIN_EXPLORE_OPEN_ALL="$BRAIN_EXPLORE_OPEN_ALL" BRAIN_EXPLORE_GRADUATE_N="$BRAIN_EXPLORE_GRADUATE_N" \
  setsid .venv/bin/python -m trading.online.run_live_loop >>logs/live_loop.log 2>&1 </dev/null &

# PRACTICE NOTEBOOK (2026-07-21 owner): the brain's rough/calculating paper. Its own process —
# ticks pending confirmations (~20s), drains Freqtrade gate-requests, and PRACTISES a cheap real
# direction on the WHOLE ~500-symbol universe every ~60s (predict + grade, opens nothing). The
# confirmation gate that blocks un-confirmed entries lives in MlBridgeStrategy.confirm_trade_entry
# + funnel propose(); this daemon is what advances/grades them. Kill-switch: NOTEBOOK_ENABLED=0.
# Flag falls back to ~/.env (owner turned the feature OFF 2026-07-22; cron relaunches must
# agree with .env, not with cron's empty environment).
NB_ON="${NOTEBOOK_ENABLED:-$(grep -oP '^NOTEBOOK_ENABLED=\K.*' .env 2>/dev/null | tail -1 || echo 1)}"
if [ "${NB_ON:-1}" != "0" ]; then
  pgrep -f "trading.brain.run_practice_notebook" >/dev/null || \
    setsid nice -n 5 .venv/bin/python -m trading.brain.run_practice_notebook \
      >>logs/practice_notebook.log 2>&1 </dev/null &
fi

# DIP-REVERSION lane (X24, 2026-07-21 owner "implement all three"): the ONLY entry rule with
# measured out-of-sample edge (+0.438%/trade net at -3% dips, n=5,849; research/direction-brain-
# mission/X23-RESULT.md). Buys big hourly drops in liquid 7d-downtrend coins at 1x with a ~2%
# price stop + time exit (rules keyed on the dip_revert enter_tag in MlBridgeStrategy). These
# LONGs still pass through the Practice Notebook gate. Kill-switch: DIP_LANE=0.
if [ "${DIP_LANE:-1}" != "0" ]; then
  pgrep -f "trading.research.dip_lane" >/dev/null || \
    setsid nice -n 5 .venv/bin/python -m trading.research.dip_lane \
      >>logs/dip_lane.log 2>&1 </dev/null &
fi

# Micro-policy distillation (invent-beyond #4): nightly full-tournament teacher run → per-coin
# winner table + LightGBM student, so the funnel's selective decide() answers in ~ms. nice-10,
# its own process — never inside a funnel cycle. Kill-switch: MICRO_POLICY=0 (the executor
# then simply never consults the student; this daemon may still refresh the table).
pgrep -f "trading.crypto.freqtrade.run_micro_distill" >/dev/null || \
  setsid .venv/bin/python -m trading.crypto.freqtrade.run_micro_distill >>logs/micro_distill.log 2>&1 </dev/null &

# Autoresearch driver (invent-beyond #5): the CONTINUOUS strategy-research loop — every cycle it
# breeds new strategies (DEAP + the SOTA generator portfolio) through the CPCV+DSR+FWER gate into
# the SkillLibrary, so strategy research + skill_library NEVER go stale. The foundry only creates
# INSIDE the funnel cycle; THIS is the dedicated background scientist (autoresearch.json). It was
# never wired into boot before 2026-07-13, so it died in the Jul-7 VM stop and stayed dead ~6 days
# (skill_library went stale). nice-10, its own process. Kill-switch: AUTORESEARCH=0. Needs the same
# generator env as the evolver so breed() isn't gated off.
if [ "${AUTORESEARCH:-1}" != "0" ]; then
  pgrep -f "trading.strategy.run_autoresearch" >/dev/null || \
    STRATEGY_EVOLUTION_ENABLED="$STRATEGY_EVOLUTION_ENABLED" \
    LLM_MUTATION="$LLM_MUTATION" PYSR_GEN="$PYSR_GEN" ALPHA_MINING="$ALPHA_MINING" \
    OPTUNA_GEN="$OPTUNA_GEN" RD_AGENT="$RD_AGENT" FWER_GATE="$FWER_GATE" \
    setsid .venv/bin/python -m trading.strategy.run_autoresearch >>logs/autoresearch.log 2>&1 </dev/null &
fi

# Per-coin best-STRATEGY table (2026-07-13): the nice-10 producer that runs the expensive per-coin
# tournament (library + created + evolved + researched, 241 static + 311 brain-created as of
# 2026-07-16, grows over time — see trading/strategy/library/registry.py) OUT of the hot entry path and
# writes per_coin_strategy.json. The breadth lane + the Strategy column read it O(1) so EVERY open
# trade shows a real library/created strategy (attribution) and — with STRATEGY_DIRECTION=1 — a
# gate-clearing strategy drives the entry. Kill-switch: STRATEGY_TABLE=0.
if [ "${STRATEGY_TABLE:-1}" != "0" ]; then
  pgrep -f "trading.crypto.freqtrade.run_strategy_table" >/dev/null || \
    setsid .venv/bin/python -m trading.crypto.freqtrade.run_strategy_table >>logs/strategy_table.log 2>&1 </dev/null &
fi

# Account-watchlist mirror (owner 2026-07-07): keep a dedicated 'Brain-Open' watchlist in the
# REAL Upstox account == current open trades, so the owner SEES the brain's picks in the Upstox
# app. Driven by the human-UI vision engine on a HEADED browser (auto-Xvfb).
#   OPT-IN (ACCOUNT_WATCHLIST=1) — OFF by default, on purpose: a chromium persistent PROFILE can
#   be held by only ONE process, and the NSE funnel already owns the Upstox profile for screening.
#   Running this as a SECOND process fights that lock (and a headed chromium costs ~1.5 GB). The
#   durable home is INSIDE the funnel process (shares the session) — a follow-up. Until then,
#   enable this only when the funnel is NOT using Upstox. Needs the Upstox login live (daily QR).
if [ "${ACCOUNT_WATCHLIST:-0}" = "1" ]; then
  pgrep -f "trading.broker_sense.run_account_watchlist" >/dev/null || \
    BROKER_SENSE_HEADED=1 BROKER_WATCHLIST_WRITE="${BROKER_WATCHLIST_WRITE:-1}" \
    setsid .venv/bin/python -m trading.broker_sense.run_account_watchlist >>logs/account_watchlist.log 2>&1 </dev/null &
fi

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
# CANONICAL public link = THIS VM's own HTTPS entrance — no third-party tunnel at all (2026-07-16).
# History: cloudflared quick tunnels are free but ROTATE their hostname every restart (dead
# bookmarks + a de-registered Zerodha redirect); the ngrok reserved domain was stable but died on
# the free 1GB bandwidth cap (ERR_NGROK_725), taking the dashboards AND the broker login with it.
# Caddy now serves :443 directly off the VM's GCP external IP via free sslip.io wildcard DNS with a
# real Let's Encrypt cert — no cap, no interstitial, nothing to pay. See gateway/Caddyfile.
# The IP is READ FROM GCP METADATA at boot, never hardcoded: this VM's external IP is ephemeral, so a
# stop/start hands it a new one (2026-07-17: 34.131.60.2 -> 34.131.91.14) and every hardcoded copy
# silently pointed the public link at an IP we no longer own. Caddy reads $PUBLIC_HOST from the env.
EXT_IP=$(curl -s --max-time 5 -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip)
if [[ ! "$EXT_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "WARN: could not read external IP from GCP metadata (got '${EXT_IP}'); public HTTPS link will be unavailable." >&2
  EXT_IP=""
fi
export PUBLIC_HOST="${EXT_IP:+${EXT_IP}.sslip.io}"
PUBLIC_URL="${PUBLIC_HOST:+https://${PUBLIC_HOST}}"
echo "$PUBLIC_URL" > public_link.txt
echo "redir * ${PUBLIC_URL}{uri} temporary" > gateway/redirect.caddy
# Sync OpenAlgo's broker OAuth host to the live ephemeral IP too. Caddy/redirect above
# already track $PUBLIC_HOST, but OpenAlgo reads REDIRECT_URL/HOST_SERVER from its own .env
# at boot; a stop/start that reassigns the IP used to leave these two stale, so Zerodha's
# callback bounced the browser to an IP we no longer own (ERR_CONNECTION_TIMED_OUT).
# NOTE: the Zerodha Kite Connect app's registered redirect URL is ALSO IP-bound and lives on
# Zerodha's console (not syncable from here) — reserve a STATIC external IP to end this churn.
if [[ -n "$PUBLIC_HOST" && -f srv/openalgo/.env ]]; then
  sed -i -E "s|^(REDIRECT_URL[[:space:]]*=[[:space:]]*').*(/zerodha/callback')|\1https://${PUBLIC_HOST}\2|" srv/openalgo/.env
  sed -i -E "s|^(HOST_SERVER[[:space:]]*=[[:space:]]*').*(')|\1https://${PUBLIC_HOST}\2|" srv/openalgo/.env
fi
pkill -x caddy 2>/dev/null; sleep 1
setsid "$HOME/.local/bin/caddy" run --config gateway/Caddyfile >logs/caddy.log 2>&1 </dev/null &
echo; echo "== Health =="
printf "%-45s %s\n" "OpenAlgo   http://127.0.0.1:5000/"        "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:5000/)"
printf "%-45s %s\n" "Freqtrade  http://127.0.0.1:8080/api/v1/ping" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:8080/api/v1/ping)"
printf "%-45s %s\n" "Dashboard  http://127.0.0.1:8000/"        "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:8000/)"
printf "%-45s %s\n" "Gateway    http://127.0.0.1:8100/"        "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:8100/)"
echo
echo "================= ONE LINK (STABLE — survives restarts, no tunnel) ================="
echo "  ${PUBLIC_URL}   (direct HTTPS off this VM · Let's Encrypt · free · no bandwidth cap)"
echo "    /          -> brain + NSE trading dashboard"
echo "    /frequi/   -> FreqUI (crypto / Freqtrade)"
echo "    /openalgo/ -> OpenAlgo (NSE broker platform)"
echo "  Also saved to ~/public_link.txt."
echo "  Secondary (rotates each restart, optional): ${CF_URL:-<pending>}"
echo "  Backup (stable name, flaky on heavy pages):"
echo "  https://ml-network-brain.loca.lt  (tunnel pw = server public IP)"
echo "============================================"
