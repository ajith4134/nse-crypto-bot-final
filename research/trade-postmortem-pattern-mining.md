# Trade Post-Mortem & Excursion Engine — research + design (2026-07-13)

Owner ask: mine the common patterns/anomalies across ALL winning trades vs ALL losing
trades so the brain knows *why* each trade closed in profit/loss; on close, record the
peak profit (MFE) & peak loss (MAE) reached after entry with timestamps relative to
entry and derive an "ideal entry offset" to perfect the entry point; feed both back into
the entry decision. Both markets, market-isolated. Deep method, reuse-first.

## What already exists (build ON this, don't duplicate)
- `trading/journal/schema.py` — ClosedTrade already has `mae/mae_time/mae_pct`,
  `mfe/mfe_time/mfe_pct`, `entry_efficiency/exit_efficiency`, `decision_snapshot`,
  `feature_attribution` (SHAP top drivers), `market_regime_entry`, psych_*, p_up, etc.
- `trading/journal/quality.py` — derives mae_pct/mfe_pct/efficiency FROM mae/mfe currency.
- `trading/crypto/freqtrade_ingest.py`
  - `map_trade()` sets `mfe/mae` currency from Freqtrade max_rate/min_rate — but NOT the
    peak TIMESTAMPS on the closed record.
  - `_peak_fields()` — REAL 1-minute candle replay that returns peak profit/loss USDT +
    `peak_profit_time`/`peak_loss_time`; currently only used for the OPEN-trade display.
- `trading/direction/truth_ledger.py` — per-(source|market|regime|horizon) Wilson hit-rates;
  `source_reliability()` is how any new directional source gets weighted.
- `trading/direction/learned_direction.py` — `decide(readings)` weights each source by its
  measured edge; a NEW source auto-self-corrects once the ledger scores it.
- `trading/broker_sense/indicator_fusion.py` — `_fuse_uncached()` returns direction/p_up +
  `meta` (carries `size_mult`); the feedback seam.

## Gaps (net-new work)
1. Closed-trade MFE/MAE peak TIMESTAMPS not persisted (crypto has the replay, unused for
   closed rows); NSE closed trades get no MFE/MAE at all.
2. No "ideal entry offset" derivation per (symbol, regime).
3. No winning-vs-losing pattern miner. ← core capability.
4. No feedback from post-mortem into fusion/learned_direction.

## Library scan (reuse-first, no license filter)
| lib | role | fit | installed |
|-----|------|-----|-----------|
| **pysubgroup** | Subgroup Discovery: conjunctive rules maximising target deviation (WRAcc/StandardQF) over a binary target | **PERFECT** — literally "find the feature combos where win-rate deviates most from base rate", human-readable rules like `regime=trend & confluence>0.6 → 78% win (base 45%)` | NO → install |
| imodels | RuleFit / skope-rules / Bayesian rule lists | good alt/secondary (sparse predictive rules) | NO |
| wittgenstein | RIPPER/IREP rule induction | usable fallback (predictive rules) | YES |
| shap | per-trade feature attribution | already used (`feature_attribution`); reuse for per-trade "why" | YES |
| sklearn | trees/GBM for a fallback importance + discretisation | yes | YES |

**Chosen:** pysubgroup as the primary miner (exactly subgroup discovery), shap already
present for per-trade attribution, with a pure-pandas grouped-stats + wittgenstein fallback
so the engine degrades gracefully if the dep is ever missing (never data-gates).

- pysubgroup: https://github.com/flemmerich/pysubgroup (BSD, pure-python, pandas) — Apriori/
  BeamSearch + StandardQF/WRAcc quality functions; `ps.SubgroupDiscoveryTask` API.

## Design — `trading/brain/postmortem.py`
- `trade_features(trade_dict)` → flat feature dict + `win` target (net_pnl>0), from
  decision_snapshot + journal columns; market-scoped.
- `mine_patterns(market)` → pysubgroup twice (target win / target loss) → ranked rules +
  grouped-stat commonalities; persist `postmortem_patterns.json` (per market).
- `excursion(trade_dict)` → MFE/MAE peak + time-since-entry (reuse `_peak_fields` for crypto,
  local feathers for both); `ideal_entry_offset_pct` = adverse heat before the favourable
  run (LONG: (entry-min_before_mfe)/entry). Aggregate per (symbol, regime).
- `explain_trade(trade_dict)` → matched winning/losing subgroups + shap drivers = the
  human-readable "reason won/lost".
- `pattern_signal(features, market, regime)` → {p_up, size_mult, matched}; registered as
  truth-ledger source `postmortem_pattern` → learned_direction weights it by measured edge
  (self-correcting). Wired into `_fuse_uncached` (reading + meta.size_mult) and learned_direction.
- `entry_offset(symbol, regime)` → wired into fusion barriers/entry-price nudge.
- `backfill()` — populate patterns + excursion aggregates from the existing journal FIRST
  (backfill-before-wire), so the panel & feedback ship with real data.
- Dashboard: `/api/trading/postmortem` + React panel.

Isolation: everything market-keyed; feedback reads only the candidate's market bucket.
Flags: `POSTMORTEM=1` (engine), `POSTMORTEM_FEEDBACK=1` (close-the-loop gate; report-only if 0).
