# Cross-symbol direction catalog — every way symbol relations can call direction

Drafted 2026-07-17 from the two uploaded videos + literature. Repo wiring verified by read-only scan 2026-07-17 (see "Repo wiring state" at bottom).

Rule zero (CONVENTIONS §16): each route below is a HYPOTHESIS. It earns a side only after out-of-sample sign accuracy beats the martingale baseline on our own ledger; until then it ABSTAINS.

## A. Cross-symbol (the user's core ask)

1. **Leader→follower spillover**: BTC/ETH (and sector leaders) move first; small caps repeat within minutes (slow information diffusion). Feature: leader's last 1-15m return → follower's next-bar sign.
2. **Seesaw (negative lead-lag)**: top-5 coin returns NEGATIVELY predict small-coin next-period returns (documented in J. Empirical Finance 2023). Opposite sign of naive copy-the-leader — must let the data pick the sign PER PAIR via the truth ledger.
3. **Rolling beta-to-BTC + residual momentum**: decompose alt return = β·BTC + residual; trade the residual's own momentum/reversal (removes the common factor our correlations are dominated by).
4. **Correlation-regime switch**: rolling 1h/4h pairwise corr matrix; average corr HIGH = one-factor market (only BTC direction matters, alts = leveraged BTC); corr LOW = idiosyncratic regime (per-coin signals allowed). Use as a GATE/conditioner, like liquidity_regime + clock_phase.
5. **Lead-lag network (TAM/ternary or cross-corr at lags)**: estimate the full leader-graph over the ~165-symbol RAM universe; trade only edges with stable sign and lead ≥ our action latency; re-estimate daily; feed graph as adjacency to the cortex/column network.
6. **Cointegration / pairs spread**: find cointegrated pairs (e.g. ETH/BTC, sector twins); z-score of spread → mean-reversion side on BOTH legs. Direction comes from the SPREAD, not the coin.
7. **BTC dominance / ETH-BTC ratio as regime symbol**: dominance rising + BTC up = alts lag → short-alt/long-BTC tilt; dominance falling = alt season tilt. The ratio series is itself a tradable direction conditioner.
8. **Sector/cluster co-movement**: cluster by correlation (L1s, memes, DeFi, AI); when a cluster's leader breaks its value area with acceptance (video A grammar), followers in the same cluster inherit the side until they've repriced.
9. **Breadth/diffusion index**: fraction of the universe above its session VWAP / with positive 15m return. Extreme one-sided breadth = trend day (continuation); mixed = rotation (fade edges). Cheap, RAM-only.
10. **Relative-strength rank momentum**: cross-sectional rank of 1h/4h returns; long top-decile vs short bottom-decile IF corr-regime = LOW; in HIGH-corr regime ranks are noise around the BTC factor.
11. **Funding/OI divergence across symbols** (if RAM mirror has funding/OI): symbol pumping WITH rising OI+funding vs pumping while leaders flat = crowd-driven → fade candidate; pumping WITH leader confirmation = follow.
12. **Stress asymmetry**: our book-state research says flow only predicts when STRESSED; correlations also spike in crashes (downside co-movement > upside). In stressed regime, leader's down-move is the highest-confidence short broadcast to the whole cluster.

## B. From video A (within-symbol, but fixes timing/exit — our measured gap)

13. **Opening-range value-area grammar**: first-15m profile → VAH/VAL; trap (close back inside) = fade to opposite VA edge; acceptance+pullback = continuation; trail per candle beyond the VA. Re-anchor "open" for crypto: UTC 00:00, US equity open 13:30 UTC, and funding timestamps 00/08/16 UTC (matches our clock_phase conditioner).
14. **Cross-symbol version of 13**: BTC's own VAH/VAL events broadcast expected side to high-β followers (leader event + follower not-yet-moved = timed entry on the follower).

## C. From video B (guardrails, not entries)

15. **Random-walk null gate**: any cycle/period/seasonality feature must beat detrended+windowed random-walk null; returns-space only, never price-space.
16. **Martingale baseline gate**: every direction source's OOS sign accuracy must beat "tomorrow = today" persistence; in-sample fit quality is inadmissible evidence.

## Sizing/consumption plan (to align with existing architecture)

- Each route = a SOURCE in the truth-ledger-weighted source table (like lens:<name> paper lanes): abstain-by-default, n≥100 closed before any verdict, no inversion of losers (retire instead).
- Correlation-regime + stress + clock_phase are CONDITIONERS recorded on every trade row, so post-mortem mining (pysubgroup) can find WHERE each route works.

## Repo wiring state (verified 2026-07-17, read-only scan)

**Already built:**
- VP engine: `trading/broker_sense/volume_profile.py` — POC/VAH/VAL (70%, outward-from-POC), per-UTC-day session profiles + value migration bias, `failed_auction()` (= video A's TRAP play, both sides), `absorption()`, `order_plan()` (structure stop/target, rr gate), `features()` tilt.
  - Consumed ONLY as a ±0.15 confluence nudge in `indicator_fusion.py` (§4f) + structure risk barriers (§6b). NOT a truth-ledger source, NOT an enter_tag lane → its hit-rate is invisible to the ledger.
- Cross-symbol features: `trading/feature_bus.py` MARKET_NAMES = btc_ret_1, rel_ret_btc, corr_btc_20 (cortex arc features only). Venue lead-lag lane `trading/direction/micro_features.py::venue_gap` (~0.54 measured) — cross-VENUE, not cross-asset.
- Cointegration: `foundry_strategies._pair_cointegration` + stat-arb catalog family — DATA_GATED spec, not live.
- Lead-lag-ish learner: `nodes/intermarket_gnn.py` (PyG GCN over |corr| kNN graph) — network layer only, not on trade path.
- In-RAM mirror `trading/broker_sense/binance_stream.py::BinanceUniverseMirror` has EVERYTHING routes 1-12 need synchronously: 1m/5m/15m candles for every USDⓈ-M perp (`get_mirror().candles(sym, tf, n)`), funding, OI+long/short (coverage lane ~200 syms), 20-level book (top-N), taker flow, all-market liquidations.
- Side decided at: `brain_executor.LibraryBrainDecider._learned_filter_side` (line ~418) → `learned_direction.decide()` (Hedge over truth-ledger-weighted sources, abstain default).

**Missing (the build surface):**
- Opening-range (first-N-min) anchored profile — engine only does rolling + daily session windows. (Video A play needs an `anchor_ts` param.)
- Acceptance+pullback-at-VA continuation (pullback.py is ATR-based, not VA-anchored; lib_ComboPullbackContinuation not VA-tied).
- VP as its own ledger source/enter_tag (currently anonymous inside fusion).
- Routes 1,2,5,7,9,10,11,12,14: no leader→follower spillover/seesaw source, no lead-lag graph, no dominance/breadth/rank features on the trade path.
- Spectral/Fourier: confined to ML feature nodes (ssqueezepy, librosa, antropy) — NOT on trade path; the video-B trap is not present. Guardrail (routes 15-16) still worth adding as a foundry/researcher gate for any "cycle" strategy.

**⚠ Verify before building:** scan quoted `learned_direction.py` header as "proven-wrong sources are inverted" — but the inverters were killed 2026-07-16 (commits b21a277/5463975; wrong = RETIRED, never flipped). Check whether that's stale docstring or live code before touching the driver.
