# Independent connectivity audit — 20260713-054103

_Engine: **ast+networkx (fallback)** · modules: 809 · edges: 2707 · report-only._

## 1. Orphan modules (imported by nothing, not entrypoints/tests)
**126** found — candidates for dead subsystems or missing wiring:

- `.cortex_build_job`
- `cognition._sandbox_worker`
- `dashboard.verify_render`
- `eval`
- `native.rolling_vp`
- `nodes.advanced_ml_nodes`
- `nodes.loop_nodes`
- `nodes.symbolic_node`
- `scratchpad.cap_trading`
- `scratchpad.discover_aiselect`
- `scratchpad.nav_restart`
- `scratchpad.qa_binance_panel`
- `scratchpad.qa_handoff_panel`
- `scratchpad.relaunch_funnel`
- `scratchpad.verify_llm_creds`
- `tools.gen_index`
- `tools.gen_upstox_census`
- `tools.orderbook_collector`
- `tools.remote_login_browser`
- `trading.advintel`
- `trading.alerts.bot`
- `trading.altdata`
- `trading.crypto.freqtrade.launch`
- `trading.crypto.freqtrade.ml_decider`
- `trading.crypto.freqtrade.user_data.strategies.FreqAIDirection`
- `trading.crypto.freqtrade.user_data.strategies.MlBridgeStrategy`
- `trading.crypto.freqtrade.user_data.strategies.MlBridgeStrategySpot`
- `trading.crypto.freqtrade.user_data.strategies.lib_BreakoutAtrChannel`
- `trading.crypto.freqtrade.user_data.strategies.lib_BreakoutBollingerSqueeze`
- `trading.crypto.freqtrade.user_data.strategies.lib_BreakoutDonchianTrailing`
- `trading.crypto.freqtrade.user_data.strategies.lib_BreakoutGapAndGo`
- `trading.crypto.freqtrade.user_data.strategies.lib_BreakoutInsideBar`
- `trading.crypto.freqtrade.user_data.strategies.lib_BreakoutLwVolatility`
- `trading.crypto.freqtrade.user_data.strategies.lib_BreakoutOpeningRange`
- `trading.crypto.freqtrade.user_data.strategies.lib_BreakoutRangeExpansion`
- `trading.crypto.freqtrade.user_data.strategies.lib_BreakoutTtmSqueeze`
- `trading.crypto.freqtrade.user_data.strategies.lib_ComboAdxGatedCross`
- `trading.crypto.freqtrade.user_data.strategies.lib_ComboBollingerRsi`
- `trading.crypto.freqtrade.user_data.strategies.lib_ComboElderTripleScreen`
- `trading.crypto.freqtrade.user_data.strategies.lib_ComboEmaCloud`
- `trading.crypto.freqtrade.user_data.strategies.lib_ComboPullbackContinuation`
- `trading.crypto.freqtrade.user_data.strategies.lib_ComboRsiMacd`
- `trading.crypto.freqtrade.user_data.strategies.lib_ComboSupertrendRsi`
- `trading.crypto.freqtrade.user_data.strategies.lib_ComboTrendDay`
- `trading.crypto.freqtrade.user_data.strategies.lib_ComboVwapRsi`
- `trading.crypto.freqtrade.user_data.strategies.lib_FlowAccumulation`
- `trading.crypto.freqtrade.user_data.strategies.lib_FlowChaikinAdosc`
- `trading.crypto.freqtrade.user_data.strategies.lib_FlowMfiTrend`
- `trading.crypto.freqtrade.user_data.strategies.lib_FlowObvTrend`
- `trading.crypto.freqtrade.user_data.strategies.lib_FlowRvolShock`

## 2. Import cycles (circular deps — refactor targets)
- trading.crypto.freqtrade.brain_executor → trading.crypto.freqtrade.micro_policy → trading.crypto.freqtrade.percoin_decider → …
- trading.crypto.freqtrade.brain_executor → trading.crypto.freqtrade.percoin_decider → …
- trading.direction.regime → trading.direction.truth_ledger → trading.broker_sense.broker_features → trading.brain.boss → trading.broker_sense.account_watchlist → trading.broker_sense.watchlist_study → trading.direction.micro_features → …
- trading.direction.regime → trading.direction.truth_ledger → trading.broker_sense.broker_features → trading.brain.boss → trading.broker_sense.account_watchlist → trading.broker_sense.watchlist_study → …
- trading.direction.regime → trading.direction.truth_ledger → trading.broker_sense.broker_features → trading.brain.boss → trading.online.controls → trading.online.live_loop → trading.direction.dir_exit → trading.direction.micro_features → …
- trading.direction.regime → trading.direction.truth_ledger → trading.broker_sense.broker_features → trading.brain.boss → trading.online.controls → trading.online.live_loop → trading.direction.dir_exit → …
- trading.direction.regime → trading.direction.truth_ledger → trading.broker_sense.broker_features → trading.brain.boss → trading.online.live_loop → trading.direction.dir_exit → trading.direction.micro_features → …
- trading.direction.regime → trading.direction.truth_ledger → trading.broker_sense.broker_features → trading.brain.boss → trading.online.live_loop → trading.direction.dir_exit → …
- trading.direction.regime → trading.direction.truth_ledger → …
- trading.evidence → trading.broker_sense.broker_features → trading.brain.boss → trading.broker_sense.account_watchlist → trading.broker_sense.watchlist_study → trading.broker_sense.indicator_fusion → …
- trading.evidence → trading.broker_sense.broker_features → trading.brain.boss → trading.online.controls → trading.online.live_loop → trading.broker_sense.stock_xray → trading.broker_sense.indicator_fusion → …
- trading.evidence → trading.broker_sense.broker_features → trading.brain.boss → trading.online.live_loop → trading.broker_sense.stock_xray → trading.broker_sense.indicator_fusion → …
- trading.crypto.freqtrade_ingest → trading.broker_sense.broker_features → trading.brain.boss → trading.online.controls → trading.online.live_loop → …
- trading.crypto.freqtrade_ingest → trading.broker_sense.broker_features → trading.brain.boss → trading.online.live_loop → …
- trading.crypto.freqtrade_ingest → trading.strategy.champion_bandit → trading.broker_sense.broker_features → trading.brain.boss → trading.online.controls → trading.online.live_loop → …
- trading.crypto.freqtrade_ingest → trading.strategy.champion_bandit → trading.broker_sense.broker_features → trading.brain.boss → trading.online.live_loop → …
- trading.broker_sense.watchlist_study → trading.broker_sense.indicator_fusion → trading.strategy.direction_equation_deploy → trading.direction.mirror_gate → trading.direction.truth_ledger → trading.broker_sense.broker_features → trading.brain.boss → trading.broker_sense.account_watchlist → …
- trading.broker_sense.watchlist_study → trading.broker_sense.indicator_fusion → trading.strategy.direction_equation_deploy → trading.direction.truth_ledger → trading.broker_sense.broker_features → trading.brain.boss → trading.broker_sense.account_watchlist → …
- trading.broker_sense.watchlist_study → trading.direction.micro_features → trading.direction.truth_ledger → trading.broker_sense.broker_features → trading.brain.boss → trading.broker_sense.account_watchlist → …
- trading.broker_sense.watchlist_study → trading.direction.truth_ledger → trading.broker_sense.broker_features → trading.brain.boss → trading.broker_sense.account_watchlist → …
- trading.direction.dir_exit → trading.direction.micro_features → trading.direction.truth_ledger → trading.broker_sense.broker_features → trading.brain.boss → trading.online.controls → trading.online.live_loop → …
- trading.direction.dir_exit → trading.direction.micro_features → trading.direction.truth_ledger → trading.broker_sense.broker_features → trading.brain.boss → trading.online.live_loop → …
- trading.direction.dir_exit → trading.direction.mirror_gate → trading.direction.truth_ledger → trading.broker_sense.broker_features → trading.brain.boss → trading.online.controls → trading.online.live_loop → …
- trading.direction.dir_exit → trading.direction.mirror_gate → trading.direction.truth_ledger → trading.broker_sense.broker_features → trading.brain.boss → trading.online.live_loop → …
- trading.direction.dir_exit → trading.direction.truth_ledger → trading.broker_sense.broker_features → trading.brain.boss → trading.online.controls → trading.online.live_loop → …

## 3. Disconnected islands (clusters not linked to the main graph)
- `tests.test_rl_execution`, `trading.execution.rl_exec_env`, `trading.execution.rl_execution`
- `tests.test_candle_updater`, `trading.crypto.freqtrade.candle_updater`
- `tests.test_skill_learnings`, `tools.skill_learnings`

## 4. Hubs
**Most depended-on** (change carefully):
- `trading.state` ← 205 importers
- `trading` ← 160 importers
- `core.node_protocol` ← 88 importers
- `trading.broker_sense` ← 82 importers
- `trading.strategy.freqtrade_strategy_base` ← 81 importers
- `trading.brain` ← 61 importers
- `core` ← 54 importers
- `core.llm` ← 30 importers
- `eval.golden` ← 28 importers
- `trading.direction` ← 24 importers
- `core.registry` ← 23 importers
- `trading.broker_sense.sessions` ← 21 importers
- `nodes.pool` ← 20 importers
- `trading.brain.mind_events` ← 20 importers
- `trading.strategy.library.base` ← 20 importers
- `trading.crypto.engine_client` ← 19 importers
- `trading.direction.truth_ledger` ← 19 importers
- `nodes` ← 17 importers
- `nodes.quant_nodes` ← 17 importers
- `trading.broker_sense.brokers` ← 17 importers
- `trading.broker_sense.ui_data` ← 17 importers
- `trading.openalgo_client` ← 17 importers
- `trading.crypto.config` ← 16 importers
- `trading.strategy.features` ← 16 importers
- `memory.neurons` ← 15 importers

**Most coupled** (imports the most — split candidates):
- `dashboard.routes.trading_ext` → 69 deps
- `dashboard.routes.brain_ext` → 43 deps
- `trading.crypto.freqtrade.brain_executor` → 37 deps
- `trading.online.live_loop` → 36 deps
- `dashboard.server` → 34 deps
- `trading.broker_sense.funnel` → 29 deps
- `run_multi` → 28 deps
- `dashboard.routes.post_ext` → 27 deps
- `trading.broker_sense.run_funnel_loop` → 25 deps
- `run_brain_t8` → 22 deps
- `trading.broker_sense.indicator_fusion` → 22 deps
- `trading.crypto.freqtrade.brain_learning` → 19 deps
- `trading.brain.boss` → 18 deps
- `tests.test_broker_sense` → 17 deps
- `trading.brain` → 17 deps
- `trading.crypto.freqtrade_ingest` → 17 deps
- `trading.strategy.autoresearch` → 15 deps
- `nodes.pool` → 13 deps
- `tests.test_domain_nodes` → 13 deps
- `tests.test_ui_market_motto` → 13 deps
- `trading.brain.vision.human_ui` → 13 deps
- `trading.broker_sense.broker_features` → 13 deps
- `trading.strategy.direction_equation` → 13 deps
- `run_phase3` → 12 deps
- `tests.test_phase3` → 12 deps

## 5. Dashboard honest-wiring (server routes ↔ UI calls)
_Heuristic: dynamic paths built at runtime can cause false positives; confirm each before acting._

**Endpoints defined but never called by the UI:**
- `/api/brain/activity`
- `/api/brain/agent`
- `/api/brain/agent/status`
- `/api/brain/autonomy/status`
- `/api/brain/boss`
- `/api/brain/embodiment/status`
- `/api/brain/hybrid/status`
- `/api/brain/librarian/status`
- `/api/brain/memory/status`
- `/api/brain/quiz/status`
- `/api/brain/stream/status`
- `/api/brain/thinking/status`
- `/api/brain/web`
- `/api/knowledge`
- `/api/network/autoload`
- `/api/network/trust`
- `/api/state/routing`
- `/api/trading/account_watchlist`
- `/api/trading/advintel/status`
- `/api/trading/alerts/status`
- `/api/trading/brain/decisions`
- `/api/trading/crypto/ingest`
- `/api/trading/crypto/predictions`
- `/api/trading/curiosity`
- `/api/trading/dreams`
- `/api/trading/exits/status`
- `/api/trading/gate_tuning`
- `/api/trading/learning_curve`
- `/api/trading/live_browser/frame`
- `/api/trading/memory_search`
- `/api/trading/mirror/frame`
- `/api/trading/onchain`
- `/api/trading/remote_login`
- `/api/trading/screener/status`
- `/api/trading/sizing/status`
- `/api/trading/status`
- `/api/trading/ui_health`

**UI calls with no backing route (broken/missing wiring):**
- `/api/trading/brain/decisions${query `

## 6. Dead / unused code
_vulture not available (vulture error: Command '['/home/karan18190164/.venv/bin/python', '-m', 'vulture', '/home/karan18190164', '/home/karan18190164/cognition', '/home/karan18190164/core', '/home/karan18190164/dashboard', '/home/karan18190164/eval', '/home/karan18190164/memory', '/home/karan18190164/native', '/home/karan18190164/nodes', '/home/karan18190164/scratchpad', '/home/karan18190164/tests', '/home/karan18190164/tools', '/home/karan18190164/trading', '--min-confidence', '80']' timed out after 180 seconds) — install for unused-function/class detection._

## 7. INDEX.md drift (auto-index vs disk)
- Undocumented on disk: **2** (first 2 shown)
  - `.cortex_build_job.py`
  - `tests/test_consult.py`
- Stale index entries (in INDEX.md, not on disk): **511**
  - `_catalog/_impl_crypto_deriv.py`
  - `_catalog/_impl_crypto_options.py`
  - `_catalog/_impl_ml_direction.py`
  - `_catalog/_impl_multi_asset.py`
  - `_catalog/_impl_nse_factor.py`
  - `_catalog/_impl_orderflow.py`
  - `_catalog/alternative_data.py`
  - `_catalog/breakout.py`
  - `_catalog/event_macro.py`
  - `_catalog/high_frequency.py`
  - `_catalog/machine_learning.py`
  - `_catalog/market_making.py`
  - `_catalog/mean_reversion.py`
  - `_catalog/meta_systems.py`
  - `_catalog/momentum.py`
  - `_catalog/multi_indicator.py`
  - `_catalog/options.py`
  - `_catalog/order_flow.py`
  - `_catalog/pattern.py`
  - `_catalog/statistical_arbitrage.py`
  - `_catalog/trend.py`
  - `_catalog/volatility.py`
  - `_catalog/volume_flow.py`
  - `_cognition/_sandbox_worker.py`
  - `_cognition/active_inference.py`

---
_Next: an independent reviewer interprets each item with fresh eyes and proposes better connections + function usage. This tool reports; it does not edit._