# DIRECTION ACCURACY PROGRAM — master plan (2026-07-10)

**STATUS: APPROVED by owner 2026-07-10 (full program, in order). Pillar 27 registered
in /goal. SOTA grounding: sota-research.md (same dir). Build follows the execution
order below; each step tests + verifies live before the next.**

Owner's order: trades lose because the DIRECTION (long/short, call/put) is wrong.
Invent a way to pick the correct direction "every time or close to it" — 80%+ if 100%
is impossible. Plus: broker-app watchlist funnel, live screen mirror, register as goal.
This file is the durable plan — safe to resume from after any interruption.

## 0. Measured ground truth (2026-07-10, 1,665 closed crypto trades)
- Total PnL **-4,247 USDT**; win rate **34.5%** (LONG 38%, SHORT 29%); payoff ~1.15:1.
- Honest direction check (entry→exit price sign vs chosen side): **40.3% correct**
  (LONG 43.3%, SHORT 36.0%). Sub-15-minute holds: **34.9%**.
- Confidence is ANTI-calibrated: conf≈1.0 trades were right **29%** of the time;
  conf≈0.8 → 0/14. `brain_correct` empty on 1,188/1,665 rows (learning starved).
- Interpretation: the brain systematically enters AFTER the move (momentum-chasing
  into short-horizon mean reversion). A 29-40%-accurate signal is not noise — it is a
  60-71%-accurate signal pointed the wrong way. This is the "common pattern in the
  random sequence" the owner asked us to find, and it is exploitable.
- Video-1 lesson (research/video/vidup1): 52% accuracy × 3.92 R/R prints money;
  34.5% × 1.15 bleeds. Direction accuracy AND payoff asymmetry are separate levers —
  pull both.

## Honest physics of the 80% ask
100% is impossible (no-arbitrage). Unconditional 80% at 5m-4h horizons is beyond any
published system. The honest route to "80% correct trades" is **selectivity**:
predict direction on EVERYTHING, but TRADE only the slice where calibrated
P(direction correct) is high, abstain otherwise (we already have conformal UQ /
pillar 17 machinery for exactly this). Targets, measured on the Truth Ledger:
- Phase 1 exit: ≥55% on taken trades (from 40.3%) — flip + timing + regime fixes.
- Phase 2 exit: ≥65% on taken trades at ≥30% coverage — meta-labeler gating.
- Phase 3 goal: **≥80% on taken trades** at whatever coverage survives, floor ≥10
  trades/day across segments; plus R/R ≥2 enforced so even misses stay cheap.

## D-features (DirectionOracle program)
- **D1. Direction Truth Ledger** (`trading/direction/truth_ledger.py`)
  Label EVERY closed trade AND every skipped candidate with fixed-horizon outcomes
  (15m/1h/4h, from candle_updater data): did price go up or down after the decision?
  Per-source × per-regime × per-horizon rolling hit-rates with Wilson CIs. Backfills
  from the 1,665-trade journal + decision_snapshot on day one. Fixes brain_correct
  starvation. THE measuring stick for every other D-feature; feeds a Direction panel.
- **D2. Mirror Gate (anti-signal inversion)** (`trading/direction/mirror_gate.py`)
  For each (source, regime, horizon) bucket with n≥30: CI-upper <45% → INVERT the
  vote; CI straddles 45-55% → ABSTAIN; CI-lower >55% → pass through. Turns today's
  measured 29-40% buckets into 60-71% immediately. Zero new data needed. The single
  highest-impact/lowest-effort item.
- **D3. Entry-timing flip (pullback entry)** (in funnel executor)
  <15m holds are 34.9% correct → entries fire at local extremes. After a direction
  verdict, require a retrace of k×ATR (or OB microprice reversion) before entering —
  enter ON the pullback, not the pump. Converts mean reversion from enemy to
  entry discount. Lever: `ENTRY_PULLBACK_ATR` (default 0.5), per-segment.
- **D4. Microstructure direction features** (`trading/direction/micro_features.py`)
  The freshest information, all from data we already fetch (zero-cost):
  (a) cross-venue lead-lag gap — binance vs bybit/okx/kucuin mid-price gaps from the
  multi-venue pool (vidup2's real mechanism); (b) OFI/microprice/walls from the
  trader-psychology module; (c) funding-rate snap + basis change; (d) multi-TF
  trend agreement (15m/1h/4h) from the app + candles (owner's multi-timeframe ask).
- **D5. Regime-conditional direction** (BOCD/HMM we have + per-regime models)
  Momentum logic ONLY in trend regime; mean-reversion sign in chop; abstain in
  regime-transition windows. The measured failure = momentum behavior in chop.
- **D6. Direction meta-labeler** (`trading/direction/meta_labeler.py`, lightgbm)
  López de Prado meta-labeling: primary signal proposes side; secondary GBDT predicts
  P(side correct) from D4 features + regime + source hit-rates + decision_snapshot;
  triple-barrier labels from D1. Calibrated (isotonic) + conformal abstention gate →
  the accuracy-coverage dial that reaches 80%-on-taken. Nightly retrain in learn loop
  (CPU, seconds). Champion/challenger via existing challenger.py protocol.
- **D7. Direction Colosseum (self-experimenting shadow league)**
  Every direction source (per-coin strategies, cortex, TradeOutcomeNet, LLM forecast,
  app-signal fusion, D4 features, mirror-gated variants) makes a SHADOW prediction
  per candidate per cycle → D1 scores them at horizon → weights update (the existing
  bandit/off-policy lanes). Sources must EARN live weight by beating 55% CI on shadow.
  This is the owner's "experiment yourself and discover" demand, running forever.
- **D8. Validate + Size stages (vidup1)** — pre-trade audit gate: independent second
  opinion (cheap local LLM/micro_llm + rules: liquidity, spread, event windows) must
  not veto; then fractional-Kelly sizing from calibrated P(correct) with per-segment
  caps. Asymmetric barriers enforced: target ≥2× stop (ATR-based) so the payoff lever
  is pulled with the accuracy lever.
- **D9. NSE call/put = same oracle** — the perp/underlying direction verdict maps to
  CE/PE exactly as the options cycle already does (brain_executor maps LONG→C/
  SHORT→P); options `no_direction` starvation ends because D2/D6 always emit a
  verdict-or-abstain with a calibrated number attached. Same Truth Ledger, same gates,
  fed by Upstox/OpenAlgo data for NSE symbols.

## W. Watchlist Study Funnel (owner flow, Binance + Upstox built-ins)
`trading/broker_sense/watchlist_study.py` — extends human_ui + Brain-Open mirror:
1. Funnel shortlist → brain SAVES symbols to the app's native watchlist/favorites
   (Brain-Open mirror already does adds/removes — reuse).
2. One by one, OPEN each saved symbol's detail page in the app (fast_nav routes).
3. STUDY with eyes: multi-timeframe chart reads (switch TF via app controls),
   indicators shown by the app, candle patterns (candlestick_cnn vendored), order
   depth/volume/trades tab — everything lands in a StudyReport (X-Ray extension).
4. StudyReport feeds DirectionOracle (D6 features) → verdict + calibrated P.
5. Trade opens via API only (execution stays API-only, standing rule).
6. On trade close → REMOVE symbol from app watchlist (mirror already prunes).
Levers: WATCHLIST_STUDY=1, study depth budget, per-broker cadence. Paper-first.

## M. Live Screen Mirror (real video, not frames)
Current: throttled JPEGs per action (screen_mirror.py). Upgrade path (zero-cost):
- M1: ffmpeg x11grab on each brain Xvfb display → MJPEG (multipart/x-mixed-replace)
  endpoint via dashboard (`/api/trading/mirror/stream/<broker>`) at 2-4 fps,
  ~1-2% CPU per stream, starts/stops on viewer demand (no viewers → no capture).
- M2: dashboard MirrorPanel swaps <img> polling for the MJPEG stream + click markers
  overlaid from actions.jsonl. Fallback to current frames when ffmpeg unavailable.

## Execution order (each step ships + verifies before the next)
1. D1 Truth Ledger + backfill + panel  (foundation; also fixes brain_correct gap)
   ✅ SHIPPED 2026-07-10: trading/direction/truth_ledger.py (+state.mutate_json),
   9 unit tests green, hooks live in funnel.py (_vote claims) + brain_executor
   (entries + options decide) + run_funnel_loop tick; 3,455 journal trades
   backfilled → 11,067 labels, 127 buckets; /api/trading/direction/truth +
   DirectionTruthPanel verified rendering real data (0 console errors).
   FIRST FINDINGS: SHORT calls 63% correct at 4h (CI 61-65) but 32.5% at exit —
   exits destroy good calls; LONG bad everywhere (42-45%); meanrev_stochrsi
   23.9%@exit n=138 = prime Mirror-Gate invert candidate; 'momentum' source
   73-80% (n=15, unproven yet).
2. D2 Mirror Gate                       (instant accuracy jump from existing data)
   ✅ SHIPPED 2026-07-10: trading/direction/mirror_gate.py, 8 unit tests green,
   wired at all 3 crypto entry-decision points (explore fast path incl. its
   default-LONG bias, selective path, options CE/PE decide); inverted claims
   re-recorded as "mirror:<source>" so flips earn their own track record;
   /api/trading/direction/truth now carries mirror.status(). Conservative by
   design: full Wilson CI must clear the bar (at 1h nothing inverts yet;
   MIRROR_HORIZON=15m would already invert meanrev_stochrsi). Buckets tighten
   every cycle now that the funnel records every claim.
   Levers: MIRROR_GATE, MIRROR_MIN_N=30, MIRROR_INVERT_CI=0.45,
   MIRROR_TRUST_CI=0.55, MIRROR_HORIZON=1h.
3. D3 Pullback entry + D8 asymmetric barriers (timing + payoff levers)
   ✅ D3 SHIPPED 2026-07-11: trading/direction/pullback.py (arm→sweep state machine,
   k×ATR or pct fallback, runaway/expiry honest counts, 8 tests) wired at all 3
   executor entry sites + sweep-and-enter after the tailgate pass; "armed" count in
   the cycle report. Levers: PULLBACK_ENTRY/_ATR/_PCT/_TTL_MIN/_RUNAWAY_ATR.
   ✅ D8 SHIPPED 2026-07-11 (validate+size): regime-TRANSITION block for non-explore
   entries unless ledger-TRUSTED (REGIME_TRANSITION_BLOCK), and fractional-Kelly
   stake scaling from the meta-labeler's calibrated p (KELLY_SCALE, only while the
   model is proven).
4. D4 micro features + D5 regime conditioning
   ✅ SHIPPED 2026-07-11: trading/direction/micro_features.py (venue_leadlag via
   exchange-pool tickers, psych_ofi, funding_extreme from local funding feathers,
   mtf_agree from 15m/1h/4h feathers; 8 tests) recording shadow claims per funnel
   cycle; trading/direction/regime.py (Kaufman-ER trend_up/trend_down/chop/transition
   + 60s shared cache, 8 tests) — DEFAULT regime for all crypto claims + gate lookups
   (NSE keeps the cross-broker regime).
5. D6 meta-labeler + conformal abstention (the 80% dial)
   ✅ SHIPPED 2026-07-11: trading/direction/meta_labeler.py (LightGBM + isotonic,
   time-ordered holdout, 6 tests) trained on 7,676 real ledger examples → holdout
   AUC 0.509 → HONESTY GUARD holds it ADVISORY (backfill rows lack regime/lane
   features); 6-hourly retrain in the funnel loop; executor gate blocks only when
   AUC ≥ META_MIN_AUC and never in explore. Truth ledger now emits training
   examples on every resolution (direction_truth_train.jsonl).
6. D7 Colosseum shadow league          (perpetual self-experimentation)
   ✅ RUNNING 2026-07-11 by composition: funnel_mtf_vote + 4 micro lanes +
   app_study + mirror:<source> flips all stake measured claims every cycle; the
   Truth panel is the league table; live weight = mirror-gate TRUSTED + meta prior.
7. W watchlist study funnel            (app-native evidence → oracle)
   ✅ SHIPPED 2026-07-11: trading/broker_sense/watchlist_study.py (study set →
   app watchlist via BOTH Brain-Open mirrors; per-symbol StudyReport = multi-TF
   chart read + micro lanes + regime, fused verdict; "app_study" ledger claims;
   auto-drop when studied+gone; 8 tests) wired into the funnel loop per market.
8. M live mirror                       (see it all happen)
   ✅ SHIPPED 2026-07-11: trading/broker_sense/live_mirror.py (ffmpeg x11grab →
   MJPEG generator, viewer-demand spawn/kill, viewer cap, nice 10) +
   /api/trading/mirror/stream (multipart) + LIVE VIDEO toggle in BrainMirrorPanel
   with honest 503 fallback to frame polling when no headed display is up.
9. D9 NSE wiring end-to-end + goal pillar registration
   ✅ SHIPPED 2026-07-11: live_loop._open_trade records every NSE/options/BSE entry
   claim + passes it through the Mirror Gate (invert/abstain honored as first-class
   refusals); NSE funnel candidates already recorded via the shared funnel hook;
   NSE labels resolve via the quote-probe path. Pillar 27 registered 2026-07-10.
Tests at every step; paper-only until Truth Ledger proves the numbers.

## Already fixed today (same session, before this plan)
- Funnel wedge (no new crypto trades): boot-time memory backfill did 3 sync LLM
  calls/note with no budget → main thread hung on SSL read for 2h+. Fixed
  (use_llm=False backfill + 20s/45s LLM budget), both funnels restarted, entries
  verified at 20:57 (14 pairs).
- Tailgate equal-profit bug: live_loop displayed the ratcheted lock but decided
  exits off a fresh peak×(1−dist) line — exits now fire on the displayed lock's
  own decision (`_dec["exit"]`); 2 regression tests added; crypto engine-side
  enforcement verified firing (`tailgate_lock` exits in freqtrade log).

## Goal pillar (register on approval)
**Pillar 27 — Direction Supremacy:** every trade's side comes from a measured,
calibrated, self-correcting direction oracle; taken-trade direction accuracy ≥80%
via abstention, tracked live on the Truth Ledger panel; no signal earns live weight
without beating 55% CI in shadow.
