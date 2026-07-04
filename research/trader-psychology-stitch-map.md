# Trader Psychology (order-book depth) — stitch map (2026-07-02)

Goal: ultra-advanced crowd-psychology engine from live order-book depth (bid/ask levels ×
quantities) for NSE (OpenAlgo 5-level) + crypto (ccxt), all segments; a per-trade
`trader_psychology` score the brain learns from; and a full `decision_snapshot` journal column
capturing ALL data the brain considered at entry.

Companion research: `orderbook-microstructure-features-oss.md`,
`orderbook-analytics-oss.md`, `lob-crowd-psychology-features.md`.

## Feature × project matrix (per-feature best-of-breed)

| Feature | Best donor | Module taken | Lands in | Glue |
|---|---|---|---|---|
| Multi-level OFI, book imbalance, spread dynamics, Kyle λ, VPIN | CameronScarpati/lob-regime-scanner | `src/features.py` | `vendor/lob_regime_scanner/` → adapted in `trading/brain/psychology.py` | snapshot adapter (5-level cap) |
| Canonical microprice (Stoikov) | sstoikov/microprice | notebook math | `vendor/microprice/` → `psychology.py::microprice()` | port G* estimator to rolling online form; weighted-mid fallback when history is short |
| OBI alpha recipe (imbalance→direction) | nkaz001/algotrading-example (+hftbacktest notebook) | imbalance alpha math | cross-check reference only (formula parity tests) | none |
| Whale wall / ladder detection | pmaji/crypto-whale-watching-app | wall + ladder-cluster logic (`app.py` calc portion) | `vendor/crypto_whale_watching/` → `psychology.py::detect_walls()` | strip Dash UI; %-of-depth thresholds |
| ML direction prediction from stacked snapshots (DeepLOB) | Jeonghwan-Cheon/lob-deep-learning | model + normalization modules | `vendor/lob_deep_learning/` → `trading/brain/psych_deeplob.py` (CPU inference, ring-buffer loader) | snapshot ring buffer (trading/data/depth), online labeling, trains once buffer is deep enough |
| Depth slope / liquidity asymmetry | (gap) | — | from-scratch in `psychology.py` (linear fit per side, Næs–Skjeltorp) | tiny numpy |
| Trade-flow VPIN w/ CIs | hanxixuana/flowrisk | pip `flowrisk` | optional refinement (needs tick trades) | crypto trades via ccxt `fetch_trades`; NSE lacks tick feed → book-based proxy from lob-regime-scanner used instead |

Overlaps resolved: imbalance/OFI exist in 3 donors → keep lob-regime-scanner (tested module),
others are parity references. Microprice exists in lob-regime-scanner too → keep Stoikov's
canonical version. DeepLOB vs TLOB → DeepLOB (lob-deep-learning) now (modular, CPU-friendly);
TLOB noted as upgrade path.

## Composite score (the "trader_psychology" value)

`psych ∈ [-1, 1]` = weighted blend (weights learnable later by TradeOutcomeNet):
OBI(top-k) ⊕ OFI-drift ⊕ microprice-vs-mid ⊕ depth-slope asymmetry ⊕ wall bias ⊕ spread-fear
(z-scored, spread/λ/VPIN act as fear dampeners). Label: euphoric / greedy / balanced /
anxious / fearful / capitulation. Positive = crowd pressure up.

## Data sources per venue/segment

- NSE (intraday/mtf/futures/options/commodities): OpenAlgo `depth` (5 bid/ask levels) via
  existing OpenAlgoClient; quote exchange per segment (memory: commodities-mcx-fut).
- Crypto (futures/spot/options/prediction): ccxt `fetch_order_book` via ExchangeClient
  (binance→bybit fallback); Freqtrade not needed for depth.
- OFI/λ need consecutive snapshots → per-symbol ring buffer in `trading/data/depth/`
  (also feeds DeepLOB training).

## Journal / learning / dashboard wiring (hybrid columns, user-approved)

- `trading/journal/schema.py`: new fields `trader_psychology`, `psych_label`, `psych_obi`,
  `psych_ofi`, `psych_microprice_drift_bps`, `psych_spread_bps`, `psych_depth_slope_bias`,
  `psych_wall_bias`, `psych_deeplob_prob_up` + `decision_snapshot` (JSON, ALL data considered).
- NSE open: `live_loop._entry_context()` + `_open_trade` store psych dict + full snapshot;
  `_journal_close` maps to columns.
- Crypto open: `brain_executor` computes psych at decide time, includes in `_brain`; sidecar
  state file `crypto_entry_meta.json` keyed by pair/open-date → merged by
  `freqtrade_ingest.map_trade` (enter_tag can't carry JSON).
- Full signal (user-approved): psych score modulates entry confidence in BrainDecider +
  brain_executor immediately (paper mode).
- Learning: `trade_features.py` FEATURE_NAMES += psych features → TradeOutcomeNet learns
  profit-direction influence; decision_snapshot available to continual learner.
- Dashboard: Psychology columns in OPEN_TRADE_COLUMNS + closed auto-flow via schema COLUMNS;
  new `/api/trading/psychology` live endpoint + PsychologyPanel (honest wiring).

## From-scratch items (only these)
depth-slope metric; composite score + labels; venue snapshot adapters; sidecar crypto entry
metadata; decision_snapshot builder; ring-buffer recorder; dashboard panel/API glue.
