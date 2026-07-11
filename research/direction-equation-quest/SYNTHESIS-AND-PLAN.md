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
