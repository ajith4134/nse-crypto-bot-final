# Independent connectivity audit — 20260704-134719

_Engine: **ast+networkx (fallback)** · modules: 538 · edges: 1457 · report-only._

## 1. Orphan modules (imported by nothing, not entrypoints/tests)
**112** found — candidates for dead subsystems or missing wiring:

- `cognition._sandbox_worker`
- `dashboard.verify_render`
- `eval`
- `nodes.advanced_ml_nodes`
- `nodes.symbolic_node`
- `tools.gen_index`
- `tools.orderbook_collector`
- `trading.advintel`
- `trading.alerts.bot`
- `trading.crypto.freqtrade.launch`
- `trading.crypto.freqtrade.ml_decider`
- `trading.crypto.freqtrade.user_data.strategies.FreqAIDirection`
- `trading.crypto.freqtrade.user_data.strategies.MlBridgeStrategy`
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
- `trading.crypto.freqtrade.user_data.strategies.lib_FlowVolumeBreakout`
- `trading.crypto.freqtrade.user_data.strategies.lib_FlowVwapTrend`
- `trading.crypto.freqtrade.user_data.strategies.lib_MeanrevAtrOverextension`
- `trading.crypto.freqtrade.user_data.strategies.lib_MeanrevBbPctb`
- `trading.crypto.freqtrade.user_data.strategies.lib_MeanrevBollinger`
- `trading.crypto.freqtrade.user_data.strategies.lib_MeanrevCci`
- `trading.crypto.freqtrade.user_data.strategies.lib_MeanrevConnorsRsi2`
- `trading.crypto.freqtrade.user_data.strategies.lib_MeanrevKeltner`
- `trading.crypto.freqtrade.user_data.strategies.lib_MeanrevMfi`
- `trading.crypto.freqtrade.user_data.strategies.lib_MeanrevRsi`
- `trading.crypto.freqtrade.user_data.strategies.lib_MeanrevStochastic`
- `trading.crypto.freqtrade.user_data.strategies.lib_MeanrevStochrsi`
- `trading.crypto.freqtrade.user_data.strategies.lib_MeanrevUltimateOsc`
- `trading.crypto.freqtrade.user_data.strategies.lib_MeanrevVwap`

## 2. Import cycles (circular deps — refactor targets)
- trading.crypto.freqtrade.brain_executor → trading.crypto.freqtrade.percoin_decider → …
- trading.online.live_loop → trading.online.controls → …
- trading.screener.commodities → trading.screener.options → trading.screener.screener → …
- trading.screener.commodities → trading.screener.screener → …
- trading.screener.options → trading.screener.screener → …
- trading.screener.screener → trading.screener → …
- trading.brain.hypothesis → trading.brain → trading.brain.pipeline → …
- cognition → cognition.embodiment → …

## 3. Disconnected islands (clusters not linked to the main graph)
- `tests.test_candle_updater`, `trading.crypto.freqtrade.candle_updater`

## 4. Hubs
**Most depended-on** (change carefully):
- `trading.strategy.freqtrade_strategy_base` ← 81 importers
- `core.node_protocol` ← 71 importers
- `trading.state` ← 53 importers
- `trading` ← 41 importers
- `core` ← 37 importers
- `eval.golden` ← 27 importers
- `core.registry` ← 19 importers
- `trading.strategy.library.base` ← 19 importers
- `nodes.pool` ← 18 importers
- `trading.brain` ← 18 importers
- `nodes.quant_nodes` ← 17 importers
- `trading.crypto.config` ← 16 importers
- `core.llm` ← 14 importers
- `nodes` ← 14 importers
- `nodes.gated_node` ← 14 importers
- `nodes.base_learners` ← 11 importers
- `trading.journal.schema` ← 11 importers
- `trading.strategy.features` ← 11 importers
- `memory.brain` ← 10 importers
- `trading.brain.researcher` ← 10 importers
- `trading.journal.journal` ← 10 importers
- `trading.strategy.genome` ← 10 importers
- `trading.brain.continual` ← 9 importers
- `trading.brain.hypothesis` ← 9 importers
- `trading.crypto.engine_client` ← 9 importers

**Most coupled** (imports the most — split candidates):
- `dashboard.server` → 69 deps
- `run_multi` → 28 deps
- `trading.online.live_loop` → 28 deps
- `run_brain_t8` → 22 deps
- `trading.crypto.freqtrade.brain_executor` → 18 deps
- `trading.brain` → 17 deps
- `trading.brain.boss` → 16 deps
- `tests.test_domain_nodes` → 13 deps
- `nodes.pool` → 12 deps
- `run_phase3` → 12 deps
- `tests.test_phase3` → 12 deps
- `tests.test_cortex_b9_gaps` → 11 deps
- `tests.test_pipeline_t8` → 11 deps
- `trading.crypto.freqtrade.brain_learning` → 11 deps
- `trading.strategy.self_evolve` → 11 deps
- `cognition` → 10 deps
- `dashboard.brain_live` → 10 deps
- `run_network` → 10 deps
- `tests.test_psychology` → 10 deps
- `trading.brain.gui.agent` → 10 deps
- `trading.brain.rnd` → 10 deps
- `core.chat_brain` → 9 deps
- `run_advintel` → 9 deps
- `run_columns` → 9 deps
- `run_trainable` → 9 deps

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
_vulture not available (pip install vulture) — install for unused-function/class detection._

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