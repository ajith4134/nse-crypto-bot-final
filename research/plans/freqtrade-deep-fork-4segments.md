# Freqtrade deep fork — ONE engine, 4 segments, ONE URL

Date: 2026-07-02 · Owner request: redesign Freqtrade after reading its entire source, extend it
natively with Spot / Options / Prediction next to Futures, by copying its framework code — NOT
separate tunnels/URLs. User explicitly chose the DEEP FORK over multi-instance.

## Source basis
- Vendored: `vendor/freqtrade` @ upstream tag **2026.6**, commit `b604e2fd70539f7f73d3c62c16ce0b155bbab319`
  (same version as the pip install it replaces). All divergences carry `# mlnb:` comments.
- Full-source read done via 4 parallel mapping passes (core loop / exchange / RPC-API / persistence-config).
  Key findings condensed below; raw maps in this file's git history + session transcript.

## Why deep fork is hard (found collision points)
| Collision | Where | Fix in fork |
|---|---|---|
| `Trade.session` module-level scoped_session; 2nd `init_db()` rebinds ALL models | `persistence/models.py:48-100` | ONE shared DB + ONE `init_db()`; per-segment isolation via a `bot_segment` column + ContextVar filter |
| Session scopefunc = thread id | `models.py:29-42` | each segment bot runs in its OWN thread → own session on the shared engine (sqlite WAL) |
| `PairLocks.timeframe` classvar overwritten per bot | `pairlock_middleware.py:24`, `freqtradebot.py:111` | all segments run the same 5m timeframe; locks are pair-scoped and pair formats differ per segment (BTC/USDT vs BTC/USDT:USDT vs option symbols) — documented residual risk |
| `ApiServer` singleton + single RPC (`add_rpc_handler` raises on 2nd call) | `rpc/api_server/webserver.py:118-168` | keep ONE ApiServer; convert `_rpc` → `_rpcs: dict[segment→RPC]`; `get_rpc` dependency reads `?segment=` query param; default = aggregate/futures |
| SIGTERM handler process-global | `commands/trade_commands.py:23` | MultiWorker owns the handler, fans shutdown to all 4 bots |
| `LocalTrade.bt_*` class lists | `trade_model.py:387-394` | backtest-only; unused in live/dry — no change |
| Wallets `_update_dry()` reads `Trade.get_trades_proxy()` (would sum ALL bots) | `wallets.py:105-183` | fixed automatically by the ContextVar segment filter on Trade queries |
| Exchange asyncio loop | per-instance (`exchange.py:346`) | SAFE — 4 Exchange objects = 4 loops |
| Dry-run order sim | per-instance dict (`exchange.py:252,1143`) | SAFE |

## Design
### 1. Editable fork install
`.venv/bin/pip install -e vendor/freqtrade --no-deps` — replaces the pip 2026.6 wheel with the
vendored source at the identical version; FreqUI installed dir (with mlnb overlays) is preserved
by re-deploying via tools/deploy_frequi.sh.

### 2. Segment isolation (persistence)
- `Trade.bot_segment: str|None` new column (+ migration in `persistence/migrations.py`).
- New `freqtrade/persistence/segment_context.py`: `current_segment` ContextVar + helpers.
- `Trade.get_trades_query/get_trades_proxy/get_open_trades/total_open_trades_stakes/…` add
  `WHERE bot_segment == current_segment` when the ContextVar is set; `None` = see everything
  (aggregate API view, backtesting untouched).
- Each bot thread sets the ContextVar at loop entry; RPC sets it per request from the route.
- ONE sqlite DB (existing `tradesv3.dryrun.sqlite`), WAL already on.

### 3. New trading modes
- `enums/tradingmode.py`: add `OPTION = "option"`, `PREDICTION = "prediction"`; extend
  `TRADING_MODES` + config schema enum. Enum column stores strings → old rows unaffected.

### 4. Segment engines (all reuse FreqtradeBot unchanged)
| Segment | Exchange class | Mode | Data |
|---|---|---|---|
| futures | Binance (existing) | FUTURES, dry-run per current config | Binance USDT-M public |
| spot | Binance (existing) | SPOT dry-run | Binance spot public |
| options | **new `exchange/deribit.py`** subclass: allow `market["type"]=="option"` in `market_is_tradable`, no-op leverage/margin/positions, candles from underlying index | OPTION dry-run | Deribit public API (no keys needed for dry-run) |
| prediction | **new `exchange/predictionpaper.py`**: synthetic ccxt-less markets from Polymarket Gamma/CLOB public API; tickers = CLOB midpoint; base dry-run order machinery | PREDICTION dry-run | Polymarket public (no keys) |

### 5. MultiWorker (single process, one port, one URL)
New `freqtrade/worker_multi.py` (framework-side, copies Worker's throttle/state logic) +
our glue `trading/crypto/freqtrade/multi_engine.py`:
- builds 4 configs from the ONE `config.json` + per-segment override block `segments: {...}`;
- `init_db()` once; starts 4 bot threads; first bot's RPCManager registers the ApiServer;
  subsequent bots attach via `ApiServer.add_rpc_handler(segment=...)` (fork change);
- one port :8080 → already fronted by Caddy `/frequi/*` → SAME public URL, zero new tunnels.

### 6. API/UI
- `deps.get_rpc(segment: str|None)` → per-segment RPC; `GET /api/v1/segments` lists them.
- Trade rows carry `bot_segment` in API responses; FreqUI TradeList gets a segment column,
  MlnbControls segment buttons flip from "staged" labels to live per-segment toggles that hit
  same-origin `/api/trading/*` (bug fix: report real HTTP status instead of "no tunnel URL";
  root cause of the screenshot was the dashboard :8000 hung — restart handled by ops skill).
- Brain loop (`run_brain_loop.py`) passes `segment` on /forceenter so the chosen engine executes.

### 7. Drawback mitigations (deep-fork risks the user asked to compensate)
- Divergence tracking: every fork edit commented `# mlnb:`; `vendor/README.md` records origin
  commit; future upstream bumps via /vendor-update skill diffing the `# mlnb:` set.
- Same-version editable install → behavior identical for the already-live futures path.
- Segment filter defaults OFF (ContextVar unset) → backtesting/hyperopt code paths untouched.
- Staged rollout: futures+spot first (proven Binance class), then options, then prediction.
- Tests: per-segment engine boot smoke (STATE_DIR + tmp db), segment query isolation unit
  tests, API segment-routing tests.

## Data/API answer (user offered keys)
No paid keys needed now: Binance public data (futures+spot), Deribit public (options dry-run),
Polymarket public (prediction paper). Live options later would need a Deribit account; live
prediction would need a Polymarket wallet — ask then, not now. Bybit not needed (Binance covers
both modes with the existing tested subclass).

## Reuse notes (build-from-oss)
- The framework being copied IS Freqtrade (vendored above) — no external search needed for the
  engine. Options/prediction data clients reuse public REST via existing `requests`/ccxt deps;
  vendor/funding-rate-arbitrage + gamma-scalping remain available for strategy logic later.

## Status 2026-07-02 — SHIPPED (paper)
Live-verified through the public URL: `/frequi/api/v1/segments` → all 4; whitelists spot=287,
options=30 (liquidity-filtered ATM Deribit strikes), prediction=46 (Polymarket); forced paper
entries succeeded on spot (BTC/USDT), options (AVAX ATM put), prediction (World-Cup market);
aggregate /status merges per-bot; FreqUI shows Segment column; brain loop runs one executor per
segment. tests/test_multisegment.py 8/8 green. Known follow-ups: upstream pytest suite needs
pytest-mock installed; live (non-paper) spot/options/prediction is a deliberate later step;
single-segment RELOAD_CONFIG restarts the shared API server (whole-process restart is the
supported path).
