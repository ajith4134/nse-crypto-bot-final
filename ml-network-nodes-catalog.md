# Node Catalog — OSS to wrap as NodeProtocol nodes (CPU-first)

> Grounded by 4 parallel web-research passes (PyPI/GitHub, mid-2026), verified at
> build time by install+import+run. Theme: prediction · trading/quant ·
> randomness · pattern-detection · signal-in-noise · chaos. Each library becomes
> a node (predictor X→y, feature-extractor→readout, or structure/equation
> discovery). License flags matter only if we redistribute as a service.

## TIER 1 — build first (highest fit, permissive, CPU-light, fits current data/heads)
| Library | pip | Node type | License | Why first |
|---|---|---|---|---|
| **PySINDy** | `pysindy` | equation-discovery | MIT | Recovers governing equations; Mackey-Glass/logistic are textbook SINDy — flagship for the "discover structure" theme |
| **STUMPY** | `stumpy` | feature-extractor / anomaly | BSD-3 | Matrix profile: motif (pattern) + discord (anomaly) discovery — the flagship signal-in-noise finder |
| **pyunicorn** | `pyunicorn` | feature-extractor | BSD-3 | RQA + recurrence networks — closes the plan's recurrence gap (only a stdlib miniature today) |
| **ordpy + antropy** | `ordpy` `antropy` | feature-extractor | MIT / BSD | Permutation entropy + complexity-entropy plane — cleanly separates chaos vs noise; tiny & fast |
| **arch** | `arch` | predictor (volatility) | permissive | GARCH conditional volatility → feeds the `volatility` head directly; #1 quant pick |
| **PyOD** | `pyod` | predictor (anomaly score) | BSD-2 | 60+ anomaly detectors (IForest/ECOD/COPOD) — signal-vs-noise outliers (avoid its torch deep ones) |
| **sklearn GP** | (have) | predictor + uncertainty | BSD-3 | GaussianProcessRegressor — calibrated uncertainty, perfect for ≤2k rows |
| **statsforecast** | `statsforecast` | predictor | Apache-2.0 | AutoARIMA/ETS/Theta, numba, no torch, sub-second — classical forecasting nodes |
| **PyWavelets** | `PyWavelets` | feature-extractor | MIT | Wavelet multiresolution + denoising features |
| **filterpy** | `filterpy` | predictor (state est.) | MIT | Kalman + particle filter — state/signal from noise |
| **Marchenko-Pastur** | (numpy recipe) | structure-discovery | — | ~30-line RMT: eigenvalues above λ₊ = signal vs noise; no lib needed |

## TIER 2 — high value, slightly heavier or license-flagged
| Library | pip | Node type | License | Note |
|---|---|---|---|---|
| PyDMD | `pydmd` | predictor (Koopman/DMD) | MIT | Linear Koopman modes; nonlinear lift via pykoopman |
| pyextremes | `pyextremes` | feature/predictor (tail risk) | MIT | Extreme-value theory — P(big move); needs long history |
| statsmodels | `statsmodels` | structure + state-space | BSD-3 | Cointegration (pairs) + UnobservedComponents (Kalman structural TS) |
| pycatch22 | `pycatch22` | feature-extractor | **GPL-3.0** | 22 C-speed canonical features — fast, but copyleft |
| tsfresh | `tsfresh` | feature-extractor | MIT | 780 features; ~1000× slower than catch22 |
| PyEMD | `EMD-signal` | feature-extractor | Apache-2.0 | Empirical mode decomposition (use this, NOT GPL `emd`) |
| pyts (SSA) | `pyts` | feature/structure | BSD-3 | Singular spectrum analysis (univariate) |
| ripser + persim | `ripser` `persim` | feature-extractor (TDA) | MIT | Permissive topological data analysis (giotto-tda is AGPL) |
| causal-learn | `causal-learn` | structure-discovery | MIT | Causal discovery (tigramite is GPL + slow) |
| pyinform / PyIF | `pyinform` `PyIF` | feature (transfer entropy) | MIT | Directional info flow (discretize first) |
| Darts | `darts` | predictor (deep seq) | Apache-2.0 | TCN / N-HiTS on CPU torch (already installed); seconds–min on ~2k rows |
| python-control + SIPPY | `control` `sippy` | predictor (state-space/sys-ID) | BSD / LGPL | Control + subspace system identification |
| nistrng | `nistrng` | feature (randomness scores) | MIT | NIST SP800-22 battery (binarize series first) |

## TIER 3 — defer (need extra data, heavy, or unmaintained)
- **QuantLib** (`QuantLib`) — needs option-chain data, not OHLCV. Defer until options ingested.
- **tick / Hawkes** (`tick`) — needs event timestamps (trades / threshold-crossings), not bars.
- **Microstructure OFI/VPIN** — no free lib (mlfinlab went paid); roll-your-own, and OHLCV gives only proxies (real signal needs L2).
- **DeepXDE PINNs** (`deepxde`) — CPU-feasible but slow, LGPL, pulls a DL backend. Optional.
- **pymc** — MCMC slowest predictor; needs a C compiler.
- **AVOID**: `luckystarufo/pySINDy` (deprecated → use `dynamicslab/pysindy`), `neurodiffeq` (inactive >12mo), GPflow (pulls TensorFlow).

## License watch (copyleft — fine internally, swap if redistributing)
GPL/AGPL/LGPL: pycatch22 (GPL), giotto-tda (AGPL), tigramite (GPL), IDTxl (GPL),
DeepXDE (LGPL), SIPPY (LGPL), `emd` (GPL). Permissive alternatives noted above.
