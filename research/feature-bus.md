# Feature Bus — every brain data stream → one CORTEX feature vector

Date: 2026-07-04 · Built in-repo (no OSS search needed — pure glue over existing
modules; user mandate: "the brain has a lot of other data which can be fed to
the neural network" + "use this on every trade it opens").

## The design rule
A feature may enter TRAINING only if it has HISTORY. Live-only values create
train/serve skew if zero-filled silently — so every block carries an `ok` flag
and live-only sources get a RECORDER so history accrues (the depth recorder
proved this pattern: 457 pairs × 39MB of L2 snapshots existed by the time we
needed them).

## The 28-feature vector (trading/cortex_signal.FEATURE_NAMES)
| Block | Names | History source |
|---|---|---|
| Candle TA (8) | rsi, d_ema_fast/mid/slow, d_sma, bb_pos, ma_slope_n, ret_1 | candles (full) |
| Order-book (6) | ob_obi5, ob_spread_bps, ob_slope_bias, ob_wall_bias, ob_gap_bias, psych_ok | trading/data/depth/*.jsonl (since psych recorder started) |
| Multi-TF (4) | h1_d_ema, h1_rsi, h1_ret, h1_vol | candles resampled (full, no look-ahead: last COMPLETED 1h bar) |
| BTC/market (3) | btc_ret_1, rel_ret_btc, corr_btc_20 | BTC feather on disk (full) |
| Live brain (7) | regime_p0/1/2, learner_bias, psych_fear, llm_p_up, live_ok | trading/data/brain_feats/*.jsonl (accrues from 2026-07-04) |

## Key modules
- trading/feature_bus.py — mtf_block / market_block / live_block + record_live
- trading/brain/psychology.py — snapshot_features (pure, train/serve parity),
  load_depth_features (mtime-cached: 8.5s cold → 0.04s warm)
- trading/cortex_signal.py — build_features(df, symbol) assembles all blocks;
  _signal records regime/fear per bar via record_live; CortexSignalSource pools
  cross-pair (POOL_MIN_PAIRS=8, env CORTEX_POOL_MIN) and refits the shared arc
  once enough pairs seen — features are scale-invariant so one arc reads all.
- run_network.py — _real_dataset_multi: pooled blocks across pairs
  (ML_NETWORK_PAIRS=24 default, ML_NETWORK_ROWS=400; cap LOGGED, never silent),
  per-pair chronological walk-forward pooled.

## Candidate future blocks (recorder-first, same pattern)
funding rate + open interest (ccxt fetch_funding_rate — recordable now),
fear&greed index, LLM forecast p_up (LLMForecastNode → record_live llm_p_up),
cross-sectional breadth (pct of pairs above their 1h EMA — derivable from
candles, no recorder needed), trade-journal outcome priors per pair.
