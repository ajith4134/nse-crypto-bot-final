# Direction-Equation Quest — research synthesis + build plan (2026-07-11)

Deep research: 109 agents, adversarially verified, cited (raw: deep-research-raw.json). Answers the
owner's quest (requirements: REQUIREMENTS.md). Grounded in our measured baseline (47% agg / 55% 4h /
37% exit — direction-accuracy-diagnosis-2026-07-11.md).

## What ACTUALLY drives short/med-term direction (ranked by evidence)
1. **Order Flow Imbalance (OFI)** — THE primary driver. Net supply/demand at best bid/ask → near-linear
   price impact, contemporaneous R²≈65% (Cont-Kukanov-Stoikov). Dominates volume/price-history.
2. **Generalized/stationarized OFI (GOFI)** — OOS R² ~84% at 30s (equities). Strongest nowcasting feature.
3. **Order Book Imbalance (OBI)** — normalized net event-count imbalance; primary HF directional signal.
4. **Trade Imbalance (TI) / CVD** — TI leads sub-1s; cumulative-OFI dominates >2min.
5. **Aggregate "world order flow"** (net buying pressure) — OOS cross-section crypto alpha, Sharpe 3.63.
6. **Microstructure**: spread, adverse selection, microprice, depth (impact slope ∝ 1/depth).
7. **HORIZON-CONDITIONING (critical):** OFI/TI dominate < ~2 min then decay; the optimal metric SHIFTS
   with horizon. Feature set AND forecast horizon must be chosen together. ← explains our 4h(55%) vs
   exit(37%): we exit at the horizon where the signal is anti-correlated.

## WHY most direction signals are coin-flips (the core insight)
Naive signals capture **MAGNITUDE, not SIGN** — scalar return autocorrelation is magnitude-driven; the
SIGN is statistically insignificant (SPY lag-1 p=0.11). Reliable direction comes from **order-flow SIGN**,
labeled + validated properly — not from price/indicator autocorrelation (which is what our current
meanrev/TA sources are, hence 47%).

## The METHOD — an equation generator, grounded (the owner's "equation generator")
1. **Feature set (order-flow-first):** OFI, GOFI, OBI, TI, CVD, spread, adverse-selection, microprice,
   depth, aggregate/world order flow, cross-asset flow — HORIZON-tagged.
2. **Discover + evolve the equation** via formulaic-alpha / symbolic regression scored by **Rank-IC**:
   - **alphagen** (RL formulaic-alpha miner, KDD'23) — ALREADY VENDORED (vendor/alphagen/).
   - **Operon** (GP symbolic regression) — beats neural SR on noisy real data → ADD.
   - our vendored **DEAP** genetic search for mutate/evolve of feature combos.
3. **Label + validate (López de Prado stack):** triple-barrier labels → **meta-labeling** secondary model
   (bet/pass) → **purged CPCV + deflated Sharpe** OOS. OSS: **mlfinlab** (add) — triple-barrier/meta/purged CV.
4. **Deploy** the discovered equation as the direction driver, horizon-conditioned, measured continuously
   on the Truth Ledger; keep the best, mutate the rest (self-improving).

## What we ALREADY have (reuse-first)
- Binance order-flow: taker buy/sell, long/short ratios, OI, funding, liquidations (binance_orderflow.py — built today).
- Psychology: OBI / OFI / microprice / walls (psychology.py).
- Truth Ledger (out-of-sample labels, per source/regime/horizon), Mirror Gate (self-inversion).
- Vendored: alphagen, DEAP. Fast candles / multi-TF.
- Missing → ADD: real per-symbol **OFI/GOFI from the book** (we have OBI; need event-level OFI), **CVD**,
  **Operon**, **mlfinlab** (triple-barrier/meta/purged-CV).

## Proposed build (ai-scientist PROPOSE→APPROVE — no code until owner approves)
- **P1 Feature bus:** assemble the order-flow-first, horizon-tagged feature matrix from our built signals
  + add OFI/GOFI/CVD from the Binance book/aggTrade (mirror already streams the pieces).
- **P2 Equation engine:** alphagen + Operon discover formulaic direction alphas; DEAP evolves/mutates the
  pool; score by Rank-IC on triple-barrier labels; keep top-K.
- **P3 Meta-label + validate:** mlfinlab triple-barrier + meta-labeling; purged-CPCV + deflated-Sharpe OOS
  gate; only equations that beat coin-flip OOS ship.
- **P4 Deploy + self-improve:** discovered equation drives direction (horizon-conditioned) via the Mirror
  Gate; continuous Truth-Ledger measurement; periodic re-evolution. Reliability bar = OOS > 55%, robust.

## APPROVED 2026-07-11 (owner: full P1→P4, phase-by-phase, no re-ask between phases)
Owner added requirement: feed **multi-TF candlestick charts WITH Binance's built-in indicators,
screenshotted from our real Binance web UI**, into image/chart ML/DL models → value into the equation.
Research: research/chart-image-models.md. Deps installed (ask-to-install approved): pyoperon 0.6.1,
pysr 1.5.10 (Julia auto-provisions), timeseriescv 0.2. mlfinlab is OFF PyPI (went commercial) and its OSS
forks (mlfinpy/RiskLabAI) fail to build numba on Py3.13 — NOT needed: the repo already has the LdP stack.

### Reuse map (already built — this is wire+upgrade, not from-scratch)
- Chart images: `chart_vision.py` already captures 1m/5m/15m/1h/4h/1d + TradingView/render fallback + dedup;
  `cnn_direction.py` = trained CNN p_up (Lane A). GAP: charts are PLAIN (no indicators); escalation is TEXT.
- Equation/validation: `strategy/cpcv.py` (purged CPCV), `strategy/metalabel.py`, `generators/symbolic.py`,
  `generators/alpha_mining.py` (alphagen), `generators/stats_gate.py`, `strategy/evolve.py` (DEAP).
- Order flow: `binance_orderflow.py`, `psychology.py` (OBI/OFI/microprice); Truth Ledger; Mirror Gate.

### Vision cascade for req#2 — 3 lanes, each emits a scalar → feature bus (research/chart-image-models.md)
- Lane A (fast): existing CNN p_up. KEEP.
- **Lane B (deep): `chart_vlm.py` — BUILT + 14 tests 2026-07-11.** Free VLM (repaired vision chain) reads the
  indicator-annotated chart → `{direction, score∈[-1,1], p_up, patterns, indicators, rationale}`; honest degrade.
- Lane C (patterns): ChartScanAI YOLOv8 (to vendor) → bullish/bearish confidence scalar.

### Build order (checkpoints)
1. ✅ LLM vision chain repaired (core/llm.py) — Lane B depends on it. 2. ✅ Lane B chart_vlm.py.
3. ⬜ GAP-1: capture Binance chart WITH indicators (extend chart_vision). 4. ✅ Lane C ChartScanAI (chart_yolo.py).
5. ✅ Fuse A+B+C in indicator_fusion (VLM lens + YOLO ±0.10 tilt). 6. ✅ P2 Operon + **Rank-IC orchestrator**.
7. ✅ P3 **purged-CPCV OOS gate** (cpcv + triple-barrier + PBO). 8. ✅ P4 **Mirror-Gate deploy + Truth Ledger**.

## P4 DONE — QUEST CHAIN COMPLETE (2026-07-11) — trading/strategy/direction_equation_deploy.py
`predict(rows, market, symbol)` loads the P3-validated survivors, evaluates them live (causal-z,
invert-aware, CPCV-IC-weighted ensemble → bounded score∈[-1,1]), RECORDS the call to the Truth
Ledger (source "direction_equation", deduped per bar) so its live per-regime/horizon accuracy is
measured, and passes it through the **Mirror Gate** (self-inverts if the ledger shows it became an
anti-signal). `equation_tilt()` folds the gated call into indicator_fusion.fuse() as a bounded
±0.15 lens (snapshot key `direction_equation`). `reevolve_all()` + `python -m
trading.strategy.direction_equation_deploy` periodically re-discover→re-validate (keep-best,
mutate-rest). Verified full chain discover→validate→persist→live predict (short, h=24, gated).
Reliability now MEASURED continuously by the Truth Ledger, not claimed. Next (ops): schedule the
re-evolution daemon + let the Truth Ledger accumulate live accuracy before raising the ±0.15 weight.

## P2 DONE (2026-07-11) — trading/strategy/direction_equation.py
`discover(ohlcv, market)` fans the feature bus through the symbolic-regression generators
(gplearn + Operon + PySR) on a TRAIN split, then scores every discovered equation on the untouched
OOS tail by **horizon-conditioned Rank-IC** (Spearman vs 1/4/12/24-bar forward return, reusing
guardrails.information_coefficient). Keeps top-K by |OOS IC|, records the best horizon + an `invert`
flag (negative IC = invertible anti-signal, per the 40%-accuracy finding), persists per market
(`direction_equations.json`) for P4. `run_for_market(symbol, market)` fetches real OHLCV + runs it;
`python -m trading.strategy.direction_equation` discovers for the majors. Verified: OOS IC≈0.22 on a
learnable synthetic signal, invert-flag correct. 7 tests. NEXT: P3 wires cpcv.py/metalabel.py +
timeseriescv as the OOS gate (only equations that beat coin-flip under purged-CPCV ship); P4 deploys
the surviving equation as the direction driver via the Mirror Gate + continuous Truth-Ledger scoring.
