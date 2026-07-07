# Independent connectivity audit — 20260704-141024

_Engine: **grimp** · modules: 417 · edges: 1003 · report-only._

## 1. Orphan modules (imported by nothing, not entrypoints/tests)
**55** found — candidates for dead subsystems or missing wiring:

- `cognition._sandbox_worker`
- `core`
- `core.brain`
- `dashboard`
- `dashboard.verify_render`
- `eval`
- `memory`
- `native`
- `nodes`
- `nodes.advanced_ml_nodes`
- `nodes.automl_node`
- `nodes.denoise_nodes`
- `nodes.detect_nodes`
- `nodes.github_t2_feature`
- `nodes.github_t2_predict`
- `nodes.noise_router`
- `nodes.online_nodes`
- `nodes.quant_factor_nodes`
- `nodes.quant_signal_nodes`
- `nodes.symbolic_node`
- `tools`
- `tools.gen_index`
- `tools.orderbook_collector`
- `trading`
- `trading.advintel`
- `trading.alerts.bot`
- `trading.brain`
- `trading.crypto`
- `trading.crypto.freqtrade`
- `trading.crypto.freqtrade.launch`
- `trading.crypto.freqtrade.ml_decider`
- `trading.crypto.mlnb_writer`
- `trading.journal`
- `trading.online`
- `trading.options`
- `trading.strategy`
- `trading.strategy.library`
- `trading.strategy.library.catalog`
- `trading.strategy.library.catalog.alternative_data`
- `trading.strategy.library.catalog.breakout`
- `trading.strategy.library.catalog.event_macro`
- `trading.strategy.library.catalog.high_frequency`
- `trading.strategy.library.catalog.machine_learning`
- `trading.strategy.library.catalog.market_making`
- `trading.strategy.library.catalog.mean_reversion`
- `trading.strategy.library.catalog.meta_systems`
- `trading.strategy.library.catalog.momentum`
- `trading.strategy.library.catalog.multi_indicator`
- `trading.strategy.library.catalog.options`
- `trading.strategy.library.catalog.order_flow`

## 2. Import cycles (circular deps — refactor targets)
- trading.crypto.freqtrade.percoin_decider → trading.crypto.freqtrade.brain_executor → …
- trading.online.controls → trading.online.live_loop → …
- trading.screener.options → trading.screener.screener → …
- trading.screener.options → trading.screener.screener → trading.screener.commodities → …
- trading.screener.commodities → trading.screener.screener → …

## 3. Disconnected islands (clusters not linked to the main graph)
- `tests.test_candle_updater`, `trading.crypto.freqtrade.candle_updater`

## 4. Hubs
**Most depended-on** (change carefully):
- `core.node_protocol` ← 69 importers
- `trading.state` ← 53 importers
- `trading.strategy.library.base` ← 19 importers
- `nodes.quant_nodes` ← 16 importers
- `trading.crypto.config` ← 15 importers
- `core.llm` ← 14 importers
- `trading.journal.schema` ← 11 importers
- `trading.strategy.features` ← 11 importers
- `nodes.gated_node` ← 10 importers
- `trading.journal.journal` ← 10 importers
- `trading.strategy.genome` ← 10 importers
- `trading.brain.hypothesis` ← 9 importers
- `trading.brain.researcher` ← 9 importers
- `trading.crypto.engine_client` ← 9 importers
- `trading.crypto.exchange_client` ← 9 importers
- `trading.strategy.library.features_ext` ← 9 importers
- `eval.golden` ← 8 importers
- `memory.brain` ← 8 importers
- `nodes.pool` ← 8 importers
- `trading.brain.continual` ← 8 importers
- `trading.openalgo_client` ← 8 importers
- `core.registry` ← 7 importers
- `trading.brain.mind_events` ← 7 importers
- `trading.brain.psychology` ← 7 importers
- `trading.brain.trade_features` ← 7 importers

**Most coupled** (imports the most — split candidates):
- `dashboard.server` → 51 deps
- `trading.online.live_loop` → 25 deps
- `trading.brain` → 17 deps
- `trading.crypto.freqtrade.brain_executor` → 14 deps
- `tests.test_domain_nodes` → 12 deps
- `nodes.pool` → 11 deps
- `tests.test_phase3` → 11 deps
- `tests.test_pipeline_t8` → 11 deps
- `trading.brain.boss` → 11 deps
- `cognition` → 10 deps
- `tests.test_cortex_b9_gaps` → 10 deps
- `trading.crypto.freqtrade.brain_learning` → 10 deps
- `dashboard.brain_live` → 9 deps
- `tests.test_execution_t3` → 9 deps
- `trading.brain.gui.agent` → 9 deps
- `trading.brain.pipeline` → 9 deps
- `trading.execution` → 9 deps
- `trading.strategy` → 9 deps
- `trading.strategy.self_evolve` → 9 deps
- `tests.test_alerts_t7` → 8 deps
- `tests.test_columns` → 8 deps
- `tests.test_computer_use` → 8 deps
- `tests.test_journal_t5` → 8 deps
- `tests.test_options_t4` → 8 deps
- `trading.alerts` → 8 deps

## 5. Dashboard honest-wiring (server routes ↔ UI calls)
_Heuristic: dynamic paths built at runtime can cause false positives; confirm each before acting._

**Endpoints defined but never called by the UI:**
- `/api/brain/activity`
- `/api/brain/agent`
- `/api/brain/agent/status`
- `/api/brain/autonomy/status`
- `/api/brain/boss/status`
- `/api/brain/embodiment/status`
- `/api/brain/hybrid/status`
- `/api/brain/librarian/status`
- `/api/brain/memory/status`
- `/api/brain/quiz/status`
- `/api/brain/stream/status`
- `/api/brain/thinking/status`
- `/api/brain/web`
- `/api/knowledge`
- `/api/network/trust`
- `/api/state/routing`
- `/api/trading/advintel/status`
- `/api/trading/alerts/status`
- `/api/trading/brain/decisions`
- `/api/trading/crypto/ingest`
- `/api/trading/crypto/predictions`
- `/api/trading/exits/status`
- `/api/trading/screener/status`
- `/api/trading/sizing/status`
- `/api/trading/status`

**UI calls with no backing route (broken/missing wiring):**
- `/api/trading/brain/decisions${query `

## 6. Dead / unused code
vulture found **8** items (≥80% confidence):

- `dashboard/verify_render.py:48: unreachable 'else' expression (100% confidence)`
- `tests/test_cortex_b8.py:200: unused variable 's_' (100% confidence)`
- `trading/crypto/freqtrade/user_data/strategies/MlBridgeStrategy.py:31: unused variable 'current_rate' (100% confidence)`
- `trading/crypto/freqtrade/user_data/strategies/MlBridgeStrategy.py:31: unused variable 'current_time' (100% confidence)`
- `trading/crypto/freqtrade/user_data/strategies/MlBridgeStrategy.py:31: unused variable 'proposed_leverage' (100% confidence)`
- `trading/crypto/freqtrade/user_data/strategies/MlBridgeStrategy.py:32: unused variable 'entry_tag' (100% confidence)`
- `trading/sizing/position_sizer.py:40: unused import 'DrawdownAdjustedKelly' (90% confidence)`
- `trading/sizing/position_sizer.py:40: unused import 'KellyCriterion' (90% confidence)`

## 7. INDEX.md drift (auto-index vs disk)
- Undocumented on disk: **0** (first 0 shown)
- Stale index entries (in INDEX.md, not on disk): **288**
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