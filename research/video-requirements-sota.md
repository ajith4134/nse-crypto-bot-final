# Video Requirements → SOTA OSS Selection (Phase-1 SELECT)

Date: 2026-07-03 · Scope: README-level research only (no cloning/source-reading).
Source spec: `research/video/MASTER-REQUIREMENTS.md` (211 REQs / 63 CANONs / 20 research questions).
Constraint: CPU-first Python; PyTorch-CPU + numpy preferred; sklearn/xgboost/keras-free preferred.
Companion detail files (agent outputs): `research/tcn-transformer-lstm-oss-candidates.md`,
`research/neat-rollout-diffusion-oss-scan.md`.

## 0. What we ALREADY have (no new deps for these)

Installed in `.venv` (Python 3.13.5): torch 2.9.1+cpu, darts 0.45.0, gluonts 0.16.3,
neuralforecast 3.1.9, chronos-forecasting 2.3.1, timesfm 2.0.2, arch **8.0.0**,
vectorbt **1.0.0**, quantstats 0.0.81 (original, unmaintained), riskfolio-lib 7.3.0,
pyportfolioopt 1.6.0, skfolio **0.20.1**, pandas-ta-classic **0.6.52**, ft-pandas-ta 0.3.16,
ta 0.11.0, statsmodels 0.14.6, crepes 0.9.1, optuna, shap.

Existing node coverage:
- `nodes/dl_nodes.py`: darts-wrapped TCNNode / LSTMNode / GRUNode / NHiTS / NBEATS / TSMixer —
  **univariate one-step regression only**.
- `nodes/foundation_nodes.py`: Chronos-T5, TimesFM 2.5, TinyTimeMixer, Moirai, Lag-Llama,
  neuralforecast PatchTST/iTransformer/TFT, GluonTS DeepAR, GPyTorch GP, Riskfolio/PyPortfolioOpt
  weight nodes.
- `trading/psychology` module: OBI/OFI/microprice/walls/fear already custom-built.
- crepes conformal UQ gate (Pillar 17) already live (`trading/uq`).

Gap the videos add: **multivariate windowed direction-probability lanes** (JKA 64×12 TCN,
TFM 30×9 transformer), NEAT topology search, barrier labeling, in-loop mark-to-market fitness,
order-matching simulator, risk overlay.

---

## Q1 — Causal TCN for next-bar up-probability (JKA-05/06, CANON-19)

| Project | Repo | Key features | Activity | CPU-fit | Verdict |
|---|---|---|---|---|---|
| **pytorch-tcn** | github.com/paul-krug/pytorch-tcn (pip `pytorch-tcn`) | Bai-et-al TCN + WaveNet skips; togglable **causal** convs w/ auto-padding; configurable dilations + dilation reset; weight/batch/layer norm; GLU; NCL & NLC layouts; **block-wise streaming inference**; ONNX | 203★, v1.2.3 Apr 2025, active | 10 | **pip (WINNER)** |
| locuslab/TCN | github.com/locuslab/TCN | Original Bai reference, not a package | 4.5k★, stale ~2018 | 8 | skip |
| keras-tcn | philipperemy/keras-tcn | Keras/TF | maintained | 2 | skip (framework) |
| neuralforecast/tsai TCN | Nixtla / timeseriesAI | TCN inside lightning/fastai frameworks | active | 4–5 | skip for this node |

Glue: `TCN(num_inputs=12, causal=True, input_shape='NLC')` → last-step `Linear→sigmoid`.
Streaming mode is a real bonus for per-bar live inference (JKA-03).
Note: existing darts TCNNode stays for univariate forecasting; this is the new probability lane.

## Q2 — Encoder-only TS transformer (TFM spec 30×9, CANON-18)

| Project | Repo | Key features | Activity | CPU-fit | Verdict |
|---|---|---|---|---|---|
| **Custom ~60-line module** | in-repo | Exact spec: Linear(9→64) + learnable pos-emb (1,30,64) + nn.TransformerEncoder 2L/8H/FF256 + last-step pool + head; zero deps | — | 10 | **custom (WINNER)** |
| yuqinie98/PatchTST | official | ICLR'23 research scripts, not a library | 2.6k★, post-paper quiet | 6 | skip |
| thuml/iTransformer | official (+lucidrains pip `iTransformer`) | variate-as-token; many-var long-horizon focus | 2.2k★ | 6 | skip (already have via neuralforecast) |
| thuml/Time-Series-Library | TSLib | 40+ models, clone-only, maintainers in low-bandwidth mode | 12.5k★ | 5 | vendor single files only if baselines wanted |
| HF transformers PatchTST | huggingface | PatchTSTForPrediction/Classification | maintained | 5 | glue only if transformers already loaded |
| tsai | timeseriesAI/tsai (pip) | 30+ models incl. PatchTST; v1.0.1 May 2026 — freshest TS lib | 6.1k★ | 6 (fastai dep) | fallback only |

Verdict: build the specified custom module — every pip route costs more than 60 lines save.
CPU-light PatchTST/iTransformer already covered by installed neuralforecast nodes.

## Q3 — LSTM/RNN price lanes (CANON-15/17)

| Option | Detail | CPU-fit | Verdict |
|---|---|---|---|
| **Custom nn.LSTM** | `nn.LSTM(n_feat,150)+Linear(150,1)` = exact PyTorch twin of Keras LSTM(150)→Dense(1); ~15 lines | 10 | **custom (WINNER)** |
| Existing darts LSTMNode/GRUNode | already in nodes/dl_nodes.py — covers univariate forecast lane only | 9 | keep |
| pytorch-forecasting | lightning framework | 4 | skip |
| xLSTM (NX-AI/xlstm, pip `xlstm`) | v2.0.4 May 2025; CUDA kernels optional, native torch fallback CPU-OK for small configs | 5 | optional later experimental node |
| KAN: pykan vs Blealtan/efficient-kan | pykan dep-heavy; efficient-kan = single torch-only file, ~31% faster, stale-but-finished | 5/7 | vendor efficient-kan single file if KAN node wanted |

Foundation nodes do NOT cover the videos' lane: they are univariate/one-step; the videos need
multivariate windowed (N, lookback, features) tensors with regression AND classification heads —
new custom lane. The from-scratch NumPy RNN/NN core (CANON-11..15) is pedagogical-by-requirement:
must be hand-written (GRC/NNM), no OSS applies by design.

## Q4 — NEAT with modern maintenance (RBT-05, CANON-20/59, bounded per KRF-11)

| Project | Repo | Key features | Activity | CPU-fit | Verdict |
|---|---|---|---|---|---|
| **neat-python** | CodeReclaimers/neat-python (pip `neat-python`) | Pure-Python, **zero runtime deps**, speciation+crossover+config mutation, FeedForward+CTRNN, checkpointing, parallel evaluators, py3.8–3.14 | 1,571★; **v2.0.0 Mar 2026, v2.0.1 tag Mar 2026; pushed May 2026** — revived by original author | 10 | **pip (WINNER)** |
| tensorneat | EMI-Group/tensorneat | JAX-tensorized, GECCO'24 best paper; 500× speedup is GPU-only | 409★, active | 5 | skip (JAX stack buys nothing at pop≈200 on CPU) |
| evotorch | pip `evotorch` v0.6.1 | CMA-ES/PGPE/GA on torch — **fixed topology, no NEAT** | 1,144★, active | 8 | skip for this area |
| pureples | ukuleleplayer/pureples | HyperNEAT/ES-HyperNEAT on neat-python | 121★, 2017 | 6 | skip |

Custom glue: ~50 lines subclassing DefaultGenome/DefaultReproduction for per-operator counters
(RBT-02) + displayed complexity scalar (RBT-05). Fitness fed from Q5's mark-to-market
evaluator (CANON-41 gate); bounded to topology/feature search per KRF-11.

## Q5 — Barrier labeling + mark-to-market backtest fitness (CANON-28/36/38–41)

Labeling (mlfinlab confirmed CLOSED — repo is all-rights-reserved paywall):

| Project | Repo | Key features | Activity | CPU-fit | Verdict |
|---|---|---|---|---|---|
| mlfinpy | baobach/mlfinpy (pip) | Open AFML port: triple-barrier + meta-labeling, dollar/volume bars, sample weights | ~100★, v0.1.2 <1yr | 9 | pip if meta-labeling wanted |
| triple-barrier | mchiuminatto/triple_barrier (pip) | Vectorized TB labeler, SL/TP/time/dynamic exits, close-reason records | 12★, v1.0.1 Jun 2025 | 9 | vendor (tiny) |
| **~50-line custom numpy** | in-repo | ±barrier within N bars → {up,down,unclear} + class-balance histogram (PNP-14/15 exact spec) | — | 10 | **custom (WINNER now)**; add mlfinpy when meta-labeling arrives |

Fitness engine + scorecard:

| Project | Repo | Key features | Activity | CPU-fit | Verdict |
|---|---|---|---|---|---|
| **vectorbt** | polakowo/vectorbt (pip, ALREADY INSTALLED 1.0.0) | Numba(+optional Rust)-vectorized Portfolio.from_signals: fees/slippage, **mark-to-market equity**, Sharpe/Sortino/MaxDD/expectancy/win-rate `.stats()`, thousands of param combos/run | ~5k★; **v1.0.0 Apr 2026 OSS revival**, py3.10–3.13 | 10 | **already installed (WINNER)** |
| quantstats-lumi | Lumiwealth/quantstats_lumi (pip) | Maintained quantstats fork: CAGR/Sharpe/Sortino/DD/expectancy + HTML tearsheets | v1.1.5 ~Dec 2025 | 10 | **pip — replace stale quantstats 0.0.81** |
| backtesting.py | kernc (pip `backtesting`) | Event-loop backtester; v0.6.5 Jul 2025, alive again | ~7k★ | 8 | skip (event loop wrong shape for in-loop fitness) |
| pyfolio-/empyrical-reloaded | stefan-jansen | metrics functions, py3.13/np2 OK | v0.9.9 Jul 2025 | 9 | optional fallback |
| bt/ffn, zipline-reloaded, nautilus_trader | — | — | — | 5–7 | skip (heavy/wrong shape) |

Honesty gates = custom glue on top: persistence baseline (shift-1 signal through the same
Portfolio call, ~10 lines), CAGR/MaxDD-vs-buy-and-hold gate (NNM-24), underwater fitness
$/trade × 1/(1+avg-underwater) (RBT-03) from vectorbt's drawdown series.

## Q6 — Indicators (CANON-24/25)

pandas-ta drama confirmed: twopirllc deleted the repo; PyPI `pandas-ta` changed hands, history
wiped, releases after Jul 2025 are paid. Community successor = pandas-ta-classic.

| Project | pip | Key features | Activity | CPU-fit | Verdict |
|---|---|---|---|---|---|
| **pandas-ta-classic** | `pandas-ta-classic` (ALREADY INSTALLED 0.6.52) | 193 indicators + **62 pure-Python candle patterns** (engulfing/hammer/star → fixes PNP-11/13 missing detectors); RSI/EMA/SMA/BBands/PSAR/Williams-fractals; MIT | **v0.6.52 Jun 24 2026**, py3.10–3.14 | 10 | **already installed (WINNER)** |
| TA-Lib | `ta-lib` | 150+ C indicators + 61 CDL* patterns; since 0.6.5 manylinux wheels bundle the C lib — pip just works on Debian | v0.6.8 Oct 2025, very active | 9 | optional pip (fast C cross-check) |
| talipp | `talipp` | **O(1) incremental** updates — live per-candle loop | v2.7.0 Sep 2025 | 9 | optional pip for live loop |
| ta (bukosabino) | `ta` (installed) | 40+ indicators | stalled Nov 2023 | 7 | keep but deprecate |
| pandas-ta (current PyPI) / finta / pandas_talib | — | post-takeover paid / dead | — | — | skip |

Fractal S/R (PNP-10): pandas-ta-classic Williams Fractals + ~20-line monotonicity extension.

## Q7 — Order-book blocks/gaps features + matching simulator (KRF-01/03/06, CANON-01/03)

Feature extraction (ADD on top of existing OBI/OFI/microprice/walls module):

| Project | Repo | Key features | Activity | CPU-fit | Verdict |
|---|---|---|---|---|---|
| **Custom ~150 lines** | extend trading psychology module | per-level gap sizes, block detection (size > k·median), cumulative imbalance map @ depth 1/5/10/20, PIN-lite | — | 10 | **custom (WINNER)** — nothing packaged matches ccxt L2 snapshots |
| LOB-feature-analysis | nicolezattarin/… | PIN, size distributions, OFI — recipe source only (private .so deps) | 272★, stale | 8 | recipe reference |
| LOB-Bench | lobbench.github.io (pip `lob-bench`) | reference spread/imbalance/inter-arrival stat definitions | 2025 | 6 | recipe reference |
| lobster-tools / LOBFrame / MeatPy | — | LOBSTER/ITCH file formats, not live L2 | mixed | 6–7 | skip |

Order-matching simulator (KRF-06 psychology-free environment):

| Project | Repo | Key features | Activity | CPU-fit | Verdict |
|---|---|---|---|---|---|
| **order-matching** | khrapovs/OrderBookMatchingEngine (pip) | price-time priority, limit/market, cancel/expiry, py3.10–3.14 | **v0.4.0 Jul 3 2026 (today)** | 10 | **pip (WINNER, tier-1)** |
| **hftbacktest** | nkaz001/hftbacktest (pip) | L2/L3 reconstruction, **queue-position fill model**, feed/order latency, tick replay, Binance/Bybit | 4.2k★, v2.4.4 Dec 2025 | 9 (Rust core, py3.11+ — venv is 3.13 ✓) | **pip (tier-2, realistic fills)** |
| ABIDES-Markets | jpmorganchase/abides-jpmc-public | multi-agent market ecology (value/momentum/noise agents) | archived Jun 2025, complete | 7 | vendor later only if synthetic order-flow ecology needed |
| PyLOB & friends | — | abandoned pre-2020 | — | 8 | skip |

## Q8 — Risk overlay + vol forecaster (JKA-07..10, NNM-26/31, CANON-49/50)

| Concern | Winner | Notes |
|---|---|---|
| σ̂ forecaster | **arch 8.0.0 (ALREADY INSTALLED)** | canonical GARCH/EGARCH/TARCH + built-in EWMA/RiskMetrics; GARCH(1,1) fit = ms on CPU; keep 15-line numpy EWMA/Parkinson fallback for short histories |
| Inverse-vol sizing + dead-band + exposure cap | **~50-line custom** | no OSS packages this trio; CVXPY dead weight; feed σ̂ from arch; calibrate dead-band from journal EV-after-costs (RQ-9) |
| LSTM+Markowitz 4-asset rebalancer (NNM-31) | **skfolio 0.20.1 (ALREADY INSTALLED)** | sklearn-style, accepts our own return forecasts, cvxpy-base+clarabel only, v0.20.1 Apr 2026; PyPortfolioOpt 1.6.0 (installed, revived Feb 2026) = simpler alternative; riskfolio-lib reserved for the later portfolio-risk pillar |

statsmodels has no first-class GARCH (defers to arch); pyflux/mgarch dead.

## Q9 — Multi-horizon autoregressive rollout (KRF-18/21/22, CANON-47/48)

| Option | Notes | Verdict |
|---|---|---|
| **Custom ~30–80-line loop** | predict→append→repeat k; direct multi-output head = extra output dims; per-horizon MAE/RMSE over (n,k) error matrix | **custom (WINNER)** |
| skforecast 0.22.0 | cleanest recursive-vs-direct API design — **copy the semantics, not the dep** (sklearn-centric) | skip |
| darts 0.45.0 (installed) | rollout exists inside TimeSeries abstraction lock-in | keep for existing nodes, don't route rollout through it |
| gluonts 0.16.3 (installed) | its `evaluation` module = per-horizon-metrics reference | recipe reference |
| neuralforecast (installed) | lightning weight, models we already have | skip |

Anti-drift (RQ-15): scheduled sampling in the custom trainer + direct multi-output head as
comparison lane — both custom.

## Q10 — Remaining research-question verdicts

- **RQ-5 persistence-gate stats**: pip **`dieboldmariano`** (zero-dep, Harvey small-sample
  correction; statsmodels confirmed has NO DM test) + 1-line numpy persistence baseline.
- **RQ-6 calibrated confidence**: existing crepes conformal gate (Pillar 17) — no new dep.
- **RQ-12/13 barrier bug + missing detectors**: custom TB labeler (Q5) + pandas-ta-classic
  candle patterns (Q6) resolve both.
- **RQ-16 order-book data**: multi-venue pool already ban-proofed; new gap/block features (Q7)
  consume the same L2 snapshots within budgets.
- **RQ-17 diffusion (KRF-23, future lane)**: park; when opened, **vendor TSDiff**
  (amazon-science/unconditional-time-series-diffusion — only CPU-plausible, clean-design TS
  diffusion; frozen Jan 2024). TimeGrad/pytorch-ts dep-rotted; CSDI imputation-shaped;
  Diffusion-TS requires CUDA (valid GPU-only skip). Chronos-Bolt confirmed NOT diffusion.
- **RQ-7 CPU-class arch benchmark**: contenders all available after this plan — pytorch-tcn,
  custom transformer, custom nn.LSTM, installed foundation/neuralforecast nodes, optional
  xlstm/efficient-kan — benchmark under CANON-61 budget with the Q5 fitness engine.
- **RQ-19 ensembles**: existing Hellsemble/column-network — no new dep.
- **CANON-11..15 from-scratch NumPy core**: hand-written by requirement (no OSS by design);
  MNIST/Fashion-MNIST via torchvision datasets (already installed).
- **CANON-16 MLP baseline**: sklearn MLPClassifier already installed (video-faithful lane);
  PyTorch MLP custom for the keras-free lane.

---

## FINAL DEP LIST

New pip deps to approve (core, 5): **pytorch-tcn, neat-python, order-matching, hftbacktest,
dieboldmariano** — all CPU-pure, first three tiny.
Optional pips (4): quantstats-lumi (replace stale quantstats), talipp (O(1) live indicators),
ta-lib (C cross-check, wheels now bundled), mlfinpy (meta-labeling later).
Optional later: xlstm (pip) · vendor efficient-kan single file · vendor TSDiff (diffusion lane)
· vendor ABIDES (market ecology).
Zero new deps needed for: transformer, LSTM, rollout, risk overlay, GARCH, Markowitz, indicators,
fitness engine — covered by custom modules + already-installed packages.
