# GitHub Projects → Nodes — deep-search catalog (2026)

> From 4 parallel GitHub/PyPI research passes. Each row is a STANDALONE project
> wrappable as a `NodeProtocol` node (predictor X→y, feature-extractor→readout,
> or structure/anomaly). Verified at build time by install+import+run. Rule:
> only GPU-only projects are skipped (never-skip §13); copyleft is flagged, not
> auto-excluded. Backtest/allocation/RL/explainer tooling is listed separately —
> it is NOT a prediction node.

## TIER 1 — build first (permissive, CPU, mature, genuinely new)
| Project | pip | Node type | License | Why |
|---|---|---|---|---|
| **River** ⭐ | `river` | online predictor + anomaly + drift | BSD-3 | Incremental `learn_one`/`predict_one` — THE fit for a growing/streaming brain (no retrain). Absorbed creme + scikit-multiflow. |
| **skforecast** | `skforecast` | recursive forecaster | BSD-3 | Turns any sklearn/xgb/lgbm regressor into a multi-step forecaster node |
| **NGBoost** | `ngboost` | probabilistic predictor | Apache-2.0 | Calibrated predictive distribution (mean+variance) — uncertainty our boosters lack |
| **CatBoost** | `catboost` | GBM predictor | Apache-2.0 | Categorical-strong boosting, ordered boosting — completes xgb/lgbm trio |
| **interpret (EBM)** | `interpret` | glassbox predictor | MIT | Explainable Boosting Machine — blackbox accuracy, per-feature shape functions free |
| **TA-Lib** | `TA-Lib` (needs C lib) | feature-extractor | BSD-2 | 150+ indicators + candlestick **pattern recognition** (we lack patterns) |
| **NeuroKit2** | `neurokit2` | feature-extractor | MIT | Physiological signal + HRV + complexity — best ROI for the **ECG** dataset |
| **librosa** | `librosa` | spectral feature-extractor | ISC | MFCC/chroma/spectral-contrast on any 1-D series — fills a spectral gap |
| **EntropyHub** | `EntropyHub` | feature-extractor | Apache-2.0 | ~40 entropy measures (multivariate/multiscale/cross) beyond antropy/nolds |
| **TSFEL** | `tsfel` | feature-extractor | BSD-3 | statistical+temporal+**spectral+fractal** feature sets (complements tsfresh) |
| **fracdiff** | `fracdiff` | transform/feature | BSD-3 | López-de-Prado fractional differentiation — stationary yet memory-keeping |

## TIER 2 — high value, secondary (heavier, niche, or copyleft-flagged)
| Project | pip | Node type | License | Note |
|---|---|---|---|---|
| deeptime | `deeptime` | Koopman/VAMP/MSM predictor | LGPL-3.0 | rigorous slow-dynamics; linking-safe |
| pomegranate | `pomegranate` | HMM/GMM/Bayes-net | MIT | pulls torch-CPU; probabilistic sequence/density node |
| pgmpy | `pgmpy` | Bayesian-network inference | MIT | reasoning node (complements causal-learn/tigramite discovery) |
| EconML | `econml` | causal treatment-effect (CATE) | MIT | DML/causal-forest effect-prediction node |
| ssqueezepy | `ssqueezepy` | synchrosqueezed TF features | MIT | sharper than PyWavelets |
| feature-engine | `feature-engine` | feature transforms | BSD-3 | clean sklearn fit/transform nodes |
| mlforecast / functime | `mlforecast`/`functime` | GBM global forecaster | Apache | fast CPU forecasters |
| FLAML / AutoTS / pyaf | `flaml`/`autots`/`pyaf` | AutoML predictor | MIT/BSD | self-tuning forecaster nodes |
| ADTK | `adtk` | anomaly | MPL-2.0 | lightweight rule-based detectors |
| scikit-dimension | `scikit-dimension` | intrinsic-dimension feature | BSD-3 | new feature type |
| pykalman / simdkalman | `pykalman`/`simdkalman` | state-estimation predictor | BSD/MIT | extends filterpy; simdkalman batches |
| node2vec | `node2vec` | graph embedding feature | MIT | permissive (vs GPL karateclub) |
| qlib | `pyqlib` | Alpha158/360 factors + GBDT | MIT | rich factor library; heavier integration spike |
| stockstats / pandas-ta-classic / ta | `stockstats`/`pandas-ta-classic`/`ta` | indicator features | BSD/MIT | broad TA (may overlap our pandas TA) |

## NOT prediction nodes (keep as downstream eval/allocation/explain stages)
- **Backtest engines**: vectorbt (⚠ Commons-Clause non-permissive), backtrader (GPL), zipline-reloaded.
- **Analytics/eval**: alphalens, pyfolio, quantstats, empyrical (unmaintained), ffn.
- **Allocation/optimization**: PyPortfolioOpt, skfolio, Riskfolio-Lib.
- **RL (different paradigm)**: FinRL, deep-river is online-NN (node-ok), but RL agents = policy layer.
- **Explainers**: SHAP, LIME, DoWhy (causal assumptions), mapie (we have — wrapper).
- **Data/benchmark**: dysts (chaotic-systems generator — use as data, not a node).

## License / maturity traps (verified)
- **Paid/proprietary**: mlfinlab (subscription). **No-license**: WorldQuant alpha101 (reimplement formulas).
- **Non-OSI**: vectorbt (Commons-Clause), PyCaret 4.0 control-plane (BUSL-1.1).
- **Copyleft**: giotto-tda (AGPL-3.0 — avoid if distributing), karateclub/teaspoon/catch22/backtrader (GPL), TPOT (LGPL), emd (GPL), deeptime (LGPL, linking-ok).
- **Dead / env-incompatible**: auto-sklearn (no py3.13), scikit-multiflow (→River), sktime-dl/tods (dead), h2o (needs JVM).
- **GPU-leaning** (CPU-usable only for tiny models): neuralforecast, pytorch-forecasting, tsai, GluonTS, DeepTime.

## Recommended first build batch (distinct capability, permissive, CPU)
1. **River** — online/incremental node (growing brain) ⭐
2. **skforecast** — recursive forecaster over our existing regressors
3. **NGBoost** — probabilistic/uncertainty predictor
4. **CatBoost** — categorical GBM
5. **interpret/EBM** — glassbox predictor
6. **NeuroKit2** — physiological features (ECG dataset)
7. **librosa** + **EntropyHub** + **TSFEL** — spectral/entropy/fractal feature nodes
8. **fracdiff** — stationarity transform feeding downstream nodes
9. **TA-Lib** — indicators + candlestick patterns (needs system C lib)
