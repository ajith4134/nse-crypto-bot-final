# CORTEX — the Self-Wiring Market Cortex
### The invented ultra-network: a trainable graph organism whose neurons are full ML models

> Synthesis of: 9 videos (211 REQs → 63 CANONs, research/video/MASTER-REQUIREMENTS.md),
> the frontier scan (research/ultra-network-frontier.md), SOTA verdicts
> (research/video-requirements-sota.md), the data plan (research/ultra-network-data-plan.md),
> the saved redesign plan (~/.claude/plans/cryptic-painting-lamport.md), and the already-built
> DGMG substrate (gated_node/cascade_node/dynamic_bus/column_network/structure_search).
> Mandate: full redesign freedom; every CANON must trace to a component (coverage matrix §9).

---

## 0. The invention in one paragraph

CORTEX is a **living graph of frozen model-neurons**. Every neuron is a complete ML model
(XGBoost, LSTM, TCN, transformer, HMM, NEAT-genome, foundation forecaster…). None of them is
ever backpropped through. ALL learning lives in the connective tissue — and that tissue learns
five different ways at five different timescales: **(1) gates** learn by real gradient descent
per tick-batch; **(2) the whole glue graph** learns from realized trade outcomes by Direct
Feedback Alignment broadcast (no chain rule through neurons needed); **(3) topology** grows and
rewires by REINFORCE edges + NEAT speciation on mark-to-market PnL fitness (label-free lane
only); **(4) trust** adapts online every bar by regret-bounded multiplicative weights,
conditioned on soft regime probabilities and reset by Bayesian changepoints; **(5) compute
itself** is routed — easy inputs exit early from cheap tiers, hard inputs escalate to deep
columns, and "stay flat" is a first-class output. The result behaves like one neural network
(forward → loss → backward → optimize → iterate) while its neurons remain black boxes — which
is, per the prior-art scans (2026-06 and 2026-07), a combination no public system has.

## 1. Anatomy (seven tissues)

```
                            ┌─────────────────────────────────────────────┐
                            │  T7 BRAIN HUB  (meta-controller)            │
                            │  regime probs · trust ledger · champion mgr │
                            │  drift sentries · HeadRequests · GUI agent  │
                            └──────────────┬──────────────────────────────┘
                                           │ conditioning + trust bias (never fake wiring)
   x(t) raw bars ─┐   ┌────────────────────▼───────────────────────────────┐
   indicators ────┤   │  T3 REFLEX ARC (conditional compute)               │
   order-book ────┼──►│  tier-1 cheap neurons vote ──agree──► signal out   │
   patterns ──────┤   │        │ disagree (ABC+PABEE)                      │
   (T1 SENSORY)   │   │        ▼                                           │
                  │   │  tier-2 columns (MoD top-k gate picks who runs)    │
                  │   │        │ still uncertain (CALM/conformal)          │
                  │   │        ▼                                           │
                  │   │  tier-3 deep experts (foundation models)           │
                  │   └──────────────┬─────────────────────────────────────┘
                  │                  │ neuron activations (name-keyed bus, T2)
                  │   ┌──────────────▼─────────────────────────────────────┐
                  │   │  T4 GATES & EDGES: Arrow/PHATGOOSE bootstrap +     │
                  └──►│  trained MoE gates (+KAN gates) + trust-bias prior │
                      │  hierarchical over Leiden competence communities   │
                      └──────────────┬─────────────────────────────────────┘
                                     ▼
                      ┌──────────────────────────────────────┐
                      │  T5 HEADS: direct horizon×quantile   │
                      │  tensor + AR long-patch rollout;     │
                      │  path-space stats → risk overlay     │
                      └──────────────┬───────────────────────┘
                                     ▼
                     LOSS/FITNESS (T6): per-head loss (gates, backprop)
                     + trade-outcome error (DFA broadcast to ALL glue)
                     + mark-to-market PnL fitness (evolution lane)
                     + honesty gates (persistence/DLinear/majority floors)
```

**T1 Sensory cortex — features.** pandas-ta-classic indicators with warm-up gating (CANON-24),
fractal S/R + 62 candle patterns fused into proximity signals (CANON-25), NEW order-book
liquidity map — per-level gaps, block detection (size > k·median), cumulative imbalance at
depths 1/5/10/20 — extending trading/psychology (CANON-01/03, KRF premise), pattern-taxonomy
generator emitting entry/stop/target per classical pattern (CANON-02). **Admission law
(CANON-46): a custom signal becomes a feature only after its standalone backtest is
profitable.** All features ride the name-keyed bus with presence masks.

**T2 Connective bus.** The existing DynamicBusNode (P3.7): per-source projection → latent D,
Set-Transformer pooling, presence mask + source-dropout — neurons plug in/out with no
reshaping (window tensor builder with shape verification = CANON-10, shared by all lanes).

**T3 Reflex arc — conditional compute (invention: compute is routed like signal).**
Tier-1 = cheapest neurons (logreg, stumps, DLinear, minGRU/CfC, streaming-TCN). ABC agreement
+ PABEE patience: if tier-1 agrees, that IS the output — zero training needed, works over
black-box sklearn nodes today. Disagreement escalates to tier-2 columns behind a
Mixture-of-Depths top-k capacity router (differentiable, trained with existing gate_train);
still-uncertain inputs reach tier-3 deep experts (Chronos-Bolt/TTM/TabPFN-TS; TimesFM/Moirai
rare). CALM Learn-Then-Test calibrated exit thresholds fuse with the existing crepes conformal
gate → every early exit carries a statistical guarantee. Zellinger early-discard = the
dead-band "stay flat" branch (CANON-49) as a routing outcome, not an afterthought. MSDNet-style
anytime heads at every tier: any CPU-budget cutoff still yields a signal (CANON-51/61).

**T4 Gates & edges — the wiring that trains like a NN.**
- Bootstrap (data-free, instant onboarding of a new neuron): Arrow prototype from the neuron's
  own output statistics + PHATGOOSE per-neuron sigmoid gate trained post-hoc.
- Trained layer: existing gate_train (softmax/top-k, Switch load-balance, noisy) UPGRADED with
  (a) HMoE cost-aware term — prefer cheap neurons, the differentiable CPU-first constraint;
  (b) trust-bias prior logits from T7 (saved-plan TrustLedger.bias_vector);
  (c) KANLinear (vendored efficient-kan single file) replacing nn.Linear inside gates/heads
  ONLY — learnable-activation capacity where parameters are tiny.
- Hierarchy: gates are two-level over **Leiden competence communities** computed from
  co-activation graphs (igraph, saved-plan Step 2) — top gate picks communities, sub-gates
  pick members. Communities double as the dashboard's spatial layout (honest: same clusters).
- Column/segment overlays: 17-column taxonomy (compute grouping) + NEW market-segment/stage
  taxonomy core/segments.py (saved-plan Step 1) as attributes on every neuron.

**T5 Heads — dual forecasting lanes + path-space decisions (CANON-47/48).**
Direct head: horizon×quantile tensor in one pass (Chronos-Bolt blueprint; MQ-RNN
horizon-embedding; N-HiTS interpolation for long horizons). Rollout head: TimesFM-style
long-output-patch AR (many candles per decode step — KRF GPT-style rollout without per-candle
error compounding). Meta-controller picks direct-vs-recursive per horizon/regime (2025
epistemic decision rule). Decisions are made in PATH space: sample N trajectories, trade on
P(TP-before-SL), expected path drawdown, path-consistent sizing. Every head must beat
persistence + DLinear floors per horizon (Diebold-Mariano test, pip dieboldmariano) before the
trust ledger will weight it (CANON-36/44).

**T6 Plasticity — five learning signals, no backprop through neurons (CANON-14 reinvented).**
1. Gate gradients: real backprop/Adam on gates per head loss (existing, P3.5).
2. **DFA broadcast (the enabler):** realized trade-outcome error is broadcast through fixed
   random projections to EVERY gate/glue layer in parallel (vendored DRTP/BioTorch, small).
   The whole organism learns from each closed trade without any gradient through neurons.
3. Forward-Forward local goodness per gate layer + predictive-coding refinement (Predify
   pattern) at test time around frozen columns.
4. Neuron-native fits: OOF/residual targets on each neuron's own fit() (existing Tier B).
5. Evolution (label-free lane ONLY, KRF-11 boundary = CANON-59): GPTSwarm REINFORCE on edge
   probabilities + neat-python 2.0 speciated population (complexity displayed per genome,
   RBT-05), fitness = CANON-41 mark-to-market: (realized+unrealized PnL)/trade ×
   1/(1+avg-underwater) from vectorbt equity — the KRF hidden-loss bug is structurally
   impossible. Zero-cost NAS proxies triage candidate topologies before any backtest is spent
   (CANON-43 telemetry counts every backtest). SENN natural-gradient trigger decides WHEN to
   grow; GradMax init adds neurons without disturbing outputs; DARTS structure_search.py
   prunes within communities.

**T7 Brain hub — the meta-controller (brain-centered hub direction).**
jumpmodels online soft regime probabilities (flap-free) condition every gate and the trust
ledger; BOCD run-length collapse resets trust to regime priors; AdaHedge/EXP3 multiplicative
weights update per-neuron trust each bar from realized loss (~10 lines, regret-bounded);
river ADWIN per-neuron drift sentries down-weight/retrain ONLY the drifted neuron; Frouros
input-drift early warning before PnL degrades (CANON-42); FLAML-ChaCha champion–challenger
picks the k neurons allowed to train online per regime; DESlib competence regions give
finer-than-regime local trust (our documented path to beat stacking). The brain reads
everything, requests heads (existing HeadRequest API), steers the evolution lane's budget
(RD-Agent-style bandit over "what to spawn/retrain next"), and drives Freqtrade/OpenAlgo
execution as today. Per-venue strategy identity preserved (CANON-52).

## 2. The video lanes (faithful implementations, every one a neuron)

| Lane | Spec (video-faithful) | Placement |
|---|---|---|
| numpy-core NN | from-scratch dense net: neuron→layers→ReLU/softmax→CE→backprop→SGD→mini-batches; validated forward-pass vs external weights, MNIST/F-MNIST (CANON-11..14, 23, 31, 32, 35) | nodes/scratch_core.py — pedagogical + the reference implementation the dashboard's "how a neuron works" view renders |
| numpy RNN | Wxh/Whh/Why tanh BPTT, ±5 grad clip, lookback 10/hidden 64/lr .01 (CANON-15) | same module, RNN class |
| LSTM lane | nn.LSTM(F,150)+Linear(150,1) twin of Keras spec; backcandles window; RSI/EMA features (CANON-17) | nodes/video_lanes.py |
| Encoder transformer | custom ~60-line module: Linear(9→64)+learnable pos-emb+2L/8H/FF256+last-step pool (CANON-18) | nodes/video_lanes.py |
| Causal TCN | pytorch-tcn, causal, streaming mode; 64×12 window → next-bar up-probability (CANON-19/27) | nodes/video_lanes.py |
| MLP baseline | sklearn MLPClassifier (video-faithful) + torch MLP; confusion-matrix protocol (CANON-16/37) | nodes/video_lanes.py |
| NEAT lane | neat-python 2.0, custom genome counters + displayed complexity; matching-sim + PnL fitness (CANON-20/59) | nodes/neat_lane.py |
| Barrier labeler | ±barrier/N-bars 3-class + class-balance histogram, ~50-line numpy (CANON-28) | trading/labels.py |
| Risk overlay | dead-band abstention + inverse-σ̂ sizing (arch GARCH, EWMA fallback) + exposure cap (CANON-49) | trading/risk_overlay.py |
| Fitness engine | vectorbt Portfolio.from_signals with fees; scorecard Sharpe/Sortino/CAGR/DD/expectancy/$-per-trade; persistence & majority & buy-and-hold gates (CANON-36/38/39/40/41) | trading/fitness.py |
| Matching sim | order-matching (pip) tier-1 + hftbacktest tier-2 queue-position fills (CANON-03) | trading/simlab.py |
| Rollout engine | predict→append→repeat + direct multi-output head; per-horizon error matrix (CANON-47/48) | trading/rollout.py |
| Portfolio rebalancer | forecasts + skfolio covariance allocation (CANON-50) | existing sizing + skfolio node |
| Serving/UI | existing dashboard + FastAPI-style routes; predicted-path overlay + confidence + recommendation + disclaimers (CANON-53/54/45) | dashboard (T8 below) |

Timeframe doctrine (CANON-06): short-TF lanes run on 1m crypto (Binance Vision downloads),
daily lanes on stooq/dukascopy/bhavcopy history — both doctrines run and are ARBITRATED
empirically per segment by the scorecard. Data per research/ultra-network-data-plan.md;
scalers fit on train only (CANON-08, fixing the videos' own leak); chronological splits
everywhere (CANON-30); truly-unseen live validation via candle_updater hold-out-by-time
(CANON-42).

## 3. Dashboard — the living cortex view (T8)

Saved-plan Steps 4–6 upgraded: run_network.py writes network_state.json (superset schema +
tier/community/segment/trust/complexity per neuron); /api/network/state|trust|refresh
(subprocess, never trains in dashboard process). SigmaNetwork.jsx becomes the cortex view:
Leiden-community clusters (same ones the router uses — honest), semantic zoom, color overlays
(community/column/segment/TIER), per-input firing-path animation (the reflex arc lighting up,
escalation visible), NEAT genome complexity scalar (RBT-05), equity curve + Train band +
per-trade P&L strip + P&L histogram + per-neuron PnL lines (CANON-56), pred-vs-real overlay
conventions (CANON-55), architecture diagrams rendered FROM the real graph (CANON-57),
leaderboard + confusion verdicts (CANON-58), anti-overfit telemetry: backtest counter, param
counts, research-time flags (CANON-43), disclaimers on served predictions (CANON-45).

## 4. What is genuinely new (the invention claims)

1. **Five-signal plasticity stack over frozen heterogeneous neurons** — gradients (gates), DFA
   trade-outcome broadcast (all glue), FF/predictive-coding local signals, native fits,
   PnL-fitness evolution — no public system combines even three over black-box model-neurons.
2. **Compute-as-routed-signal**: ABC/PABEE agreement tiers + MoD capacity routing + calibrated
   conformal exits fused into ONE reflex arc where "stay flat" is a routing outcome.
3. **Regime-conditioned regret-bounded trust** (jump-model probs × AdaHedge × BOCD resets ×
   ADWIN per-neuron × ChaCha champions) as the brain's hand on every gate — the videos' trust
   intuition made mathematically honest.
4. **Data-free neuron onboarding** (Arrow+PHATGOOSE): a newly spawned neuron is routable the
   moment it exists, before any joint training.
5. **Path-space trading heads** (dual direct/rollout, trajectory sampling, P(TP-before-SL))
   wired directly into the risk overlay.
6. The whole organism is **visible live** — the dashboard renders the actual routing graph,
   firing paths, and growth events from real state (honest-wiring rule as a feature).

## 5. Deps to approve (ask-to-install)

Core new pips (5, all tiny/CPU-pure): **pytorch-tcn, neat-python, order-matching,
hftbacktest, dieboldmariano**.
New pips for the frontier mechanisms (7): **river, jumpmodels, frouros, evotorch, flaml,
granite-tsfm, tabpfn-time-series** (deslib already installed? verify — else +1).
Optional quality pips (3): quantstats-lumi, talipp, ta-lib.
Single-file vendors (no pip): efficient-kan, BOCD, DRTP/DFA, DLinear (trivial).
Already installed and reused: torch-cpu, vectorbt 1.0, arch, skfolio, pandas-ta-classic,
chronos-forecasting, darts, neuralforecast, crepes, igraph, sigma.js/graphology (frontend).

## 6. Build order (each step shippable, tested, committed; heavy steps subprocess-safe)

- **B1 Foundations**: core/segments.py + trading/labels.py + trading/fitness.py (vectorbt
  engine + ALL honesty gates + scorecard) + tests. The fitness engine comes FIRST — everything
  else is judged by it.
- **B2 Video lanes**: nodes/scratch_core.py (numpy NN+RNN, MNIST-validated), nodes/
  video_lanes.py (TCN/transformer/LSTM/MLP lanes on the window builder), trading/risk_overlay.py,
  trading/rollout.py + tests. Deps: pytorch-tcn, dieboldmariano.
- **B3 Reflex arc**: nodes/reflex.py — ABC+PABEE tiers over the existing pool, MoD router,
  CALM-calibrated exits fused with crepes, anytime heads; nodes/active_subnet.py hierarchical
  Leiden gates (saved-plan Step 2) + trust bias hook in gated_node.py + core/trust.py
  (saved-plan Step 3, upgraded to AdaHedge+BOCD).
- **B4 Brain hub**: jumpmodels+river+frouros+flaml integration in trading/brain/regime_hub.py;
  champion manager; DFA trainer (vendored) wiring trade outcomes to all gates; deps: river,
  jumpmodels, frouros, flaml.
- **B5 Evolution lane**: nodes/neat_lane.py (neat-python) + GPTSwarm-style REINFORCE edge
  learner + zero-cost triage + SENN/GradMax grow-prune, all fitness-fed by B1; simlab
  (order-matching + hftbacktest). Deps: neat-python, order-matching, hftbacktest, evotorch.
- **B6 Heads + data**: trading/rollout.py direct+AR heads on TTM/Bolt/TabPFN nodes; data
  downloads per plan (Binance Vision 1m, stooq daily, dukascopy EURUSD, bhavcopy NSE);
  deps: granite-tsfm, tabpfn-time-series.
- **B7 Cortex dashboard**: run_network.py + /api/network/* + SigmaNetwork upgrade +
  NetworkPanel (saved-plan Steps 4–6 + §3 additions), rebuild web.
- **B8 Integration**: brain loop drives CORTEX per bar (CANON-51); per-venue identities;
  live-unseen validation protocol armed; full test suite; verify-live; commit.

Every step: /run-tests + /gen-index + /commit-safe; /verify-live at B7/B8. Coverage matrix
in MASTER-REQUIREMENTS.md gets its "Implemented by" column filled as each step lands.

## 7. Honesty & risk register (kept from the research, non-negotiable)

- Frozen-heterogeneous gating beating tuned GBDT is a HYPOTHESIS — benchmark honestly vs
  tuned XGBoost; Caruana static combiner stays as the fallback (existing rule).
- Persistence/DLinear/majority floors gate EVERY lane before trust (CANON-36) — the three
  videos that "looked good" all failed exactly this.
- Routing collapse: Switch load-balance + noisy gating + EM fallback (existing mitigation).
- Mamba official kernels are GPU-only (honest fit 3) — mambapy only, low priority.
- Diffusion lane (CANON-21) parked until its dedicated scan; TSDiff is the vendor candidate.
- paper-first: every new lane trades on paper wallets until the scorecard clears the gates.
