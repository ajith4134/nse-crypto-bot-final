# CORTEX Stitch Map — feature × donor → landing spot

Companion to research/ultra-network-design.md (§6 build order). Every feature below is either
stitched from a named donor or explicitly from-scratch (glue/pedagogical only). Vendored
single-file donors get header comments with repo+commit (vendor/README.md updated).

| # | Feature | Donor (best-of-breed) | What we take | Lands in | Glue needed | Step |
|---|---|---|---|---|---|---|
| 1 | Mark-to-market fitness engine | **vectorbt 1.0 (installed)** | Portfolio.from_signals, fees, equity/drawdown series, stats | trading/fitness.py | scorecard + CANON gates wrapper | B1 |
| 2 | Honesty gates (persistence/majority/buy-hold/DM) | **dieboldmariano (pip)** + numpy | DM test w/ Harvey correction | trading/fitness.py | shift-1 persistence run, majority baseline, CAGR/MaxDD-vs-B&H | B1 |
| 3 | Scorecard metrics | vectorbt `.stats()` (+quantstats-lumi optional tearsheets) | Sharpe/Sortino/CAGR/DD/expectancy/win-rate | trading/fitness.py | $-per-round-trip headline | B1 |
| 4 | Barrier 3-class labeler | from-scratch (~50 numpy lines; mlfinpy later for meta-labeling) | — | trading/labels.py | class-balance histogram check | B1 |
| 5 | Market-segment taxonomy | clone of our core/columns.py pattern | — | core/segments.py | segment_for/group/layout | B1 |
| 6 | Indicators + candle patterns + fractals | **pandas-ta-classic 0.6.52 (installed)** | 193 indicators, 62 CDL patterns, Williams fractals | trading/features_ta.py (thin) | warm-up gating; fractal monotonicity ext (~20 lines) | B2 |
| 7 | Causal TCN probability lane | **pytorch-tcn (pip)** | TCN(causal, streaming, NLC) | nodes/video_lanes.py | last-step Linear→sigmoid head; NodeProtocol wrap | B2 |
| 8 | Encoder-only TS transformer | from-scratch (~60 lines, video spec = cheaper than any dep) | — | nodes/video_lanes.py | window builder + NodeProtocol | B2 |
| 9 | LSTM lane | torch nn.LSTM (installed) | — | nodes/video_lanes.py | Keras-twin config (150 units) | B2 |
| 10 | MLP lanes | sklearn MLPClassifier (installed) + torch MLP | — | nodes/video_lanes.py | confusion-matrix protocol hooks | B2 |
| 11 | numpy NN+RNN pedagogical core | from-scratch BY REQUIREMENT (CANON-11..15) | — | nodes/scratch_core.py | MNIST/F-MNIST validation via torchvision | B2 |
| 12 | Window tensor builder | from-scratch (video spec, np.moveaxis pattern) | — | nodes/video_lanes.py (shared util) | shape verification asserts | B2 |
| 13 | Risk overlay (dead-band+inv-vol+cap) | **arch 8.0 (installed)** GARCH σ̂ | arch_model fit/forecast | trading/risk_overlay.py | EWMA/Parkinson fallback; overlay logic from-scratch (~50 lines, no OSS exists) | B2 |
| 14 | Rollout engine (AR + direct heads) | from-scratch loop (skforecast semantics copied, not dep) | — | trading/rollout.py | per-horizon error matrix; DLinear floor | B2 |
| 15 | DLinear floor baseline | vendor single file (cure-lab/LTSF-Linear) | DLinear module | vendor/dlinear/ → nodes/video_lanes.py | trivial wrap | B2 |
| 16 | Agreement cascade (ABC+PABEE) | steal-mechanism (papers; no repo needed) | agreement/patience rules | nodes/reflex.py | tiers over existing pool | B3 |
| 17 | MoD top-k capacity router | steal-mechanism | top-k capacity routing | nodes/reflex.py | reuse gate_train | B3 |
| 18 | Calibrated exits | **crepes (installed)** + CALM LTT recipe | conformal quantiles | nodes/reflex.py | threshold calibration glue | B3 |
| 19 | Hierarchical Leiden gates | **igraph (installed)** community_leiden | — | nodes/active_subnet.py | per saved plan Step 2 | B3 |
| 20 | Trust ledger (AdaHedge+EXP3) | steal-mechanism (~10 lines) | multiplicative weights | core/trust.py | prior_bias hook in gated_node.py | B3 |
| 21 | BOCD regime resets | vendor single file (gwgundersen/bocd) | run-length posterior | vendor/bocd/ → core/trust.py | reset trigger glue | B3 |
| 22 | KAN gates | vendor single file (Blealtan/efficient-kan) | KANLinear | vendor/efficient_kan/ → nodes/gated_node.py opt-in | drop-in Linear swap flag | B3 |
| 23 | Regime probabilities | **jumpmodels (pip)** | predict_proba_online | trading/brain/regime_hub.py | conditioning vector → gates+trust | B4 |
| 24 | Per-neuron drift sentries | **river (pip)** ADWIN + **frouros (pip)** input-drift | detectors | trading/brain/regime_hub.py | per-node error streams from journal | B4 |
| 25 | Champion–challenger online slots | **flaml (pip)** ChaCha pattern | champion mgmt | trading/brain/regime_hub.py | k-challengers per regime | B4 |
| 26 | DFA trade-outcome trainer | vendor small (ChFrenkel/DirectRandomTargetProjection) | DFA/DRTP update rule | vendor/dfa/ → nodes/dfa_trainer.py | fixed random projections → all gate layers | B4 |
| 27 | NEAT evolvable lane | **neat-python 2.0 (pip)** | genome/speciation/checkpoint | nodes/neat_lane.py | ~50-line genome subclass (op counters, complexity scalar); fitness from #1 | B5 |
| 28 | REINFORCE edge learner | steal-mechanism (GPTSwarm idea) | edge-probability REINFORCE | nodes/edge_learner.py | PnL reward from #1 | B5 |
| 29 | Zero-cost topology triage | steal-mechanism (snip/synflow scores) | proxy scores | nodes/edge_learner.py | pre-backtest ranking | B5 |
| 30 | Grow/prune triggers | steal-mechanism (SENN trigger + GradMax init) | — | nodes/edge_learner.py + structure_search.py | integrate existing DARTS module | B5 |
| 31 | Matching simulator tier-1 | **order-matching (pip)** | price-time engine | trading/simlab.py | psychology-free env for NEAT | B5 |
| 32 | Realistic-fill simulator tier-2 | **hftbacktest (pip)** | queue-position fills | trading/simlab.py | L2 replay adapter | B5 |
| 33 | Evolution search driver | **evotorch (pip)** | CMA-ES/PGPE | nodes/edge_learner.py | gate/coefficient search | B5 |
| 34 | Direct quantile head | **granite-tsfm TTM + chronos-forecasting Bolt (pip/installed)** | pretrained forecasters | nodes/foundation upgrade + trading/rollout.py | horizon×quantile tensor adapter | B6 |
| 35 | Zero-shot tabular forecaster | **tabpfn-time-series (pip)** | TabPFN-TS node | nodes/foundation_nodes.py add | feature block reuse | B6 |
| 36 | Data downloads | Binance Vision dumps, stooq, dukascopy-node, bhavcopy (per data plan) | — | tools/download_market_data.py | per research/ultra-network-data-plan.md | B6 |
| 37 | Portfolio rebalancer | **skfolio (installed)** | covariance allocators | existing sizing node ext | our forecasts as expected returns | B6 |
| 38 | Cortex dashboard | our SigmaNetwork.jsx + graphology (installed) | — | run_network.py, dashboard/server.py, NetworkPanel.jsx | saved-plan Steps 4-6 + design §3 | B7 |
| 39 | Live per-bar loop integration | existing brain loop / run_brain_loop.py | — | trading/online + brain loop | reflex arc as signal source, paper-first | B8 |

Overlaps resolved: backtesting.py vs vectorbt → vectorbt (in-loop array fitness shape);
tensorneat vs neat-python → neat-python (CPU, revived 2.0); skforecast/darts rollout →
custom loop (avoid abstraction lock-in); pykan vs efficient-kan → efficient-kan.
Gaps (from-scratch, justified): risk-overlay trio, barrier labeler, window builder,
encoder transformer (video spec), scratch numpy core (pedagogical by requirement),
order-book gap/block features (~150 lines, nothing packaged matches ccxt L2).
