# OSS scan: NEAT neuroevolution / multi-horizon rollout / TS diffusion (README-level, 2026-07-03)

CPU-first Python project (torch-CPU + numpy). Verdicts: pip / vendor / custom-glue / skip.

## AREA 1 — NEAT topology/feature search (pop ~200, speciation, crossover, operator counters)

| Name | Repo | pip | Key features | Stars | Recency | Health | CPU-fit | Verdict |
|---|---|---|---|---|---|---|---|---|
| neat-python | github.com/CodeReclaimers/neat-python | `neat-python` (2.0.0 on PyPI, uploaded 2026-03-02; v2.0.1 tag 2026-03-14) | Pure-Python NEAT, ZERO runtime deps (stdlib only), speciation, crossover, config-file genome params, FeedForward+CTRNN (v2.0 adds evolvable per-node time constants), py3.8–3.14 + pypy3, checkpointing, parallel/threaded evaluators | 1,571 | pushed 2026-05-23 | RESURRECTED: dormant ~2017-2023, active again 2024-2026 (v1.1.0 Dec, v2.0.0/2.0.1 Mar 2026); original author maintains | 10 | **pip** |
| tensorneat | github.com/EMI-Group/tensorneat | none (git install only) | JAX-vectorized NEAT, HyperNEAT/CPPN, batch inference, GECCO'24 best paper, 500x GPU speedup claim; jax>=0.4.28; CPU JAX works (pip `jax` wheel ~90MB w/ jaxlib, moderate not huge) | 409 | pushed 2026-05-01 | Active-ish, research-group project, no PyPI release | 5 | skip (new dep stack JAX+XLA compile overhead for pop=200 not worth it on CPU) |
| evotorch | github.com/nnaisense/evotorch | `evotorch` (v0.6.1, May 2026) | PGPE/XNES/CMA-ES/SNES/CEM/GA/CoSyNE/MAPElites on torch; **NO NEAT / no topology evolution** — fixed-topology only; Ray optional | 1,144 | pushed 2026-06-03 | Healthy, corporate-backed | 8 | skip for NEAT (maybe later for fixed-topology weight-evolution lane) |
| pureples | github.com/ukuleleplayer/pureples | `pureples` | HyperNEAT + ES-HyperNEAT on TOP of neat-python | 121 | last release v0.0-alpha 2017, ~41 commits | Dormant | 6 | skip (only relevant if we want substrate HyperNEAT; would vendor then) |
| misc forks (KrupaPrag/neat, SirBob01/NEAT-Python, bennr01/neat-python, goktug97/NEAT) | various | none | Small/edu forks or stale mirrors, none beats upstream | <100 ea | stale | Low | – | skip |

**Recommendation (Area 1):** `pip install neat-python` (2.0.x). It is exactly the asked-for shape: pure-Python, zero-dependency, actively maintained again in 2025-2026 by the original author (v2.0.0 Mar 2026), py3.14-ready, with speciation + crossover + config-driven mutation rates built in. Population 200 on CPU is its home turf. Per-operator counters aren't exposed as a first-class feature — add them as custom-glue (subclass `DefaultReproduction`/`DefaultGenome` mutate hooks, ~50 lines). tensorneat only pays off with a GPU + JAX stack we don't want; evotorch cannot evolve topology at all; pureples is dead but is the vendor-target later IF we ever want HyperNEAT substrates.

## AREA 2 — Multi-horizon autoregressive rollout (feed-back k candles, direct heads, per-horizon errors)

| Name | Repo | pip | Key features | Stars | Recency | Health | CPU-fit | Verdict |
|---|---|---|---|---|---|---|---|---|
| skforecast | github.com/skforecast/skforecast | `skforecast` (0.22.0, 2026-04-23) | ForecasterRecursive + ForecasterDirect (both strategies as classes), backtesting w/ per-fold metrics, works with ANY sklearn-API estimator (LightGBM/XGBoost/torch-wrapped), NumFOCUS-affiliated, prod-stable | 1,505 | pushed 2026-07-03 | Very healthy | 8 (sklearn-centric API; our models are torch, would need wrapper) | skip → borrow design only |
| darts | github.com/unit8co/darts | `darts` (0.45.0, 2026-06-19) | historical_forecasts backtesting, per-horizon metrics, recursive+direct; NOTE: torch/lightgbm/prophet are now EXTRAS not core (`darts` base, `darts[torch]`, `notorch` flavor) — but still drags sklearn+lightning ecosystem for useful paths; py>=3.10 | 9,443 | pushed 2026-07-01 | Very healthy | 6 | skip (framework lock-in: requires wrapping our models in TimeSeries/ForecastingModel abstractions to get the one loop we need) |
| neuralforecast | github.com/Nixtla/neuralforecast | `neuralforecast` (3.1.9, 2026-05-28) | 25+ neural models, recursive+direct, CPU works but drags pytorch-lightning (+optional ray/spark); models we already have | 4,184 | pushed 2026-07-03 | Very healthy | 6 | skip |
| gluonts | github.com/awslabs/gluonts | `gluonts` (0.16.3, 2026-06-29) | torch backend is default now (`gluonts[torch]`), mxnet legacy optional; strong eval/backtest utilities; heavy dataset/transform abstraction | ~4.9k | active | Healthy | 6 | skip as framework (its `evaluation` module is the reference for per-horizon metrics) |
| custom rollout loop | — | — | ~30-line loop: predict candle → append to window → repeat k; direct head = extra output dims; per-horizon MAE/RMSE = numpy one-liner over a (n, k) error matrix | — | — | — | 10 | **custom-glue** |

**Recommendation (Area 2):** custom-glue. Every framework here exists to bring you MODELS wrapped in its own dataset/series abstraction; we already have the models, and the actual deliverable (recursive rollout + direct multi-output head + per-horizon error table) is ~30-80 lines of numpy/torch with zero new deps. skforecast is the best-designed of the group (explicit ForecasterRecursive vs ForecasterDirect split, 0.22.0 Apr 2026) — copy its STRATEGY semantics (recursive re-featurization, direct one-model-per-horizon option, backtest fold layout) but not the dependency. If we ever want a framework anyway, skforecast > darts > neuralforecast for our CPU budget.

## AREA 3 — CPU-viable TS diffusion forecaster (future lane, low priority)

| Name | Repo | pip | Key features | Stars | Recency | Health | CPU-fit | Verdict |
|---|---|---|---|---|---|---|---|---|
| TSDiff | github.com/amazon-science/unconditional-time-series-diffusion | none (editable install) | NeurIPS'23; unconditional diffusion + observation self-guidance → forecast/refine/synthesize; torch+gluonts; small models, CPU plausible | 254 | pushed 2024-01-30 | Frozen research code | 6 | **vendor later** (best capability match) |
| TimeGrad (pytorch-ts) | github.com/zalandoresearch/pytorch-ts | `pytorchts` (0.6.0, Apr 2022) | Pioneer autoregressive diffusion (RNN cond.), CPU fallback in examples; pinned to OLD gluonts; 97 open issues | 1,369 | pushed 2024-06 | Stale/abandoned | 4 | skip (dep rot; if TimeGrad wanted, re-implement head on our stack) |
| CSDI | github.com/ermongroup/CSDI | none | NeurIPS'21 score-based; imputation-first (forecast=mask), transformer x2; 7 commits, mostly notebooks | 458 | pushed 2024-03 | Frozen | 5 | skip |
| Diffusion-TS | github.com/Y-debug-sys/Diffusion-TS | none | ICLR'24 encoder-decoder transformer diffusion, gen+forecast+impute; README REQUIRES a CUDA GPU; 95% notebooks | 472 | update 2025-02 | Semi-active | 3 | skip (GPU-required is our sole allowed skip reason) |
| chronos / chronos-bolt | github.com/amazon-science/chronos-forecasting | `chronos-forecasting` (v2.3.1, 2026-07-02) | NOT diffusion (confirmed): Chronos = token-LM, Bolt = direct multi-patch regression; very healthy, CPU inference fine | 5,500 | active | Excellent | 8 | out-of-scope for diffusion (already covered by foundation-model lane) |

**Recommendation (Area 3):** park it; when the diffusion lane opens, vendor **TSDiff** — it is the only candidate that is (a) genuinely a forecast-capable diffusion model with a clean single-model design, (b) torch-based with small enough nets to be CPU-trainable on candle windows, (c) Apache-licensed Amazon research code that, while frozen since Jan 2024, has no exotic deps beyond gluonts+torch. TimeGrad's home repo (pytorch-ts) is dep-rotted since 2022; CSDI is imputation-shaped notebook code; Diffusion-TS states a hard CUDA requirement. Confirmed: chronos-bolt is NOT diffusion (token-LM / direct patch regression).
