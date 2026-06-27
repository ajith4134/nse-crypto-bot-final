# Pattern-in-Noise Node Catalog — deep search (2026)

> Focused on the project's core theme: **finding & extracting patterns from
> noise/randomness, separating signal from noise, and testing random-vs-structured.**
> 3 parallel GitHub/PyPI research passes (separation · discovery · detection).
> Each row = a standalone project wrappable as a CPU `NodeProtocol` node. Only
> GPU-only items are skip candidates (never-skip §13); copyleft flagged.

## A. SIGNAL ↔ NOISE SEPARATION / DECOMPOSITION / DENOISING
| Project | pip | Node type | License | Why (new structure) |
|---|---|---|---|---|
| **signal-decomposition** (Boyd) | `sig-decomp` | transform → named components | BSD-3 | splits a series into smooth + periodic + sparse + low-rank components (handles gaps) |
| **Robust PCA** | `rpca` / vendor `r_pca` | low-rank + sparse split | MIT | clean signal (low-rank) vs spike noise (sparse) — Hankel-embed a series |
| **python-picard** | `python-picard` | ICA / blind source sep | BSD-3 | faster/robuster than FastICA — unmix independent sources from mixtures |
| **VMD** | via `sktime` (vmdpy) | adaptive band modes | MIT | variational mode decomposition (cleaner than EMD) |
| **ewtpy** | `ewtpy` | adaptive wavelet modes | MIT | empirical wavelet transform (data-driven bands) |
| **SPORCO** | `sporco` | sparse coding / dict learning + TV + RPCA | BSD-3 | learned-dictionary sparse codes as features |
| **PyLops** | `pylops` | compressed-sensing / sparse inversion | LGPL-3.0 ⚠ | recover sparse signal from noisy/underdetermined data |
| sklearn/scipy/skimage builtins | (have) | FastICA, DictionaryLearning, TruncatedSVD, `savgol_filter`, `denoise_tv/wavelet` | BSD | no new dep — direct denoise/decompose nodes |

## B. RANDOM-vs-STRUCTURED & WEAK-SIGNAL DETECTION
| Project | pip | Node type | License | Why |
|---|---|---|---|---|
| **nolitsa** | git | surrogate (AAFT/IAAFT) hypothesis test | BSD-3 | the rigorous "is the structure REAL or just noise?" wrapper around any metric ⭐ |
| **scikit-rmt** | `scikit-rmt` | Marchenko-Pastur denoiser | BSD-3 | maintained RMT signal/noise eigenvalue cleaning (upgrades our numpy recipe) |
| **astropy LombScargle** | `astropy` (have) | periodic significance (FAP) | BSD-3 | false-alarm probability for periodic weak signals (uneven data) |
| **multitaper** | `multitaper` | harmonic F-test | MIT | Thomson F-test: deterministic sinusoid buried in noise |
| **EQcorrscan** / scipy | `eqcorrscan` / scipy | matched filter / template xcorr | LGPL / BSD | pull a known template out of noise (SNR score) |
| **IDTxl** | git | multivariate transfer-entropy network | GPL-3 ⚠ | validated directed info-flow (beyond pyinform pairwise) |
| **fathon** | `fathon` | DCCA / MF-DCCA cross-correlation | GPL-3 ⚠ | scale-dependent shared structure between two series |
| **bayesian_changepoint_detection** | `bayesian-changepoint-detection` | online BOCPD | MIT | per-step probability a regime break occurred |
| self-implement (no good lib) | — | 0-1 chaos test, NCD via `lzma`, stochastic-resonance Langevin | — | ~15-30 lines each; orphaned/unlicensed repos → roll our own |

## C. PATTERN / MOTIF / REPRESENTATION DISCOVERY
| Project | pip | Node type | License | Why |
|---|---|---|---|---|
| **claspy** (ClaSP) | `claspy` | recurring-state segmentation | BSD-3 | parameter-free change points + recurring latent "state" motifs ⭐ |
| **tslearn** | `tslearn` | SAX / shapelets / soft-DTW | BSD-2 | symbolic codes + shapelet features + DTW distances |
| **TS2Vec** | clone (MIT) | self-supervised TS embedding | MIT | contrastive dilated-TCN embeddings — CPU-feasible (device='cpu') |
| **pykoopman** | `pykoopman` | Koopman operator embedding | MIT | linear eigenmodes of nonlinear dynamics |
| **scikit-sequitur** | `scikit-sequitur` | grammar-induction motif mining | Apache-2.0 | + our SAX layer → rule/grammar patterns |
| **pyscamp-cpu** | `pyscamp-cpu` | faster matrix profile | MIT | speed alt to STUMPY (only if perf-bound) |

## FLAGGED — avoid as deps
- **GPL/AGPL/no-license**: SPAMS (GPL), saxpy (GPL-2), giotto-tda (AGPL → use ripser/persim), JIDT/PyCBC/mtspec (GPL/Java/deprecated), TNC (no license), alpha101 (no license).
- **Dead/archived**: matrixprofile(-ts), mass-ts, GrammarViz (Java), changefinder, pyncd, sksfa (use deeptime VAMP/TICA), fbpca (use sklearn randomized_svd).
- **GPU-preferred** (CPU-possible but slow): denoising autoencoders, MOMENT-large, Chronos-large, TF-C; TS2Vec is the CPU-feasible SSL pick.

## Recommended build batch (new, permissive, CPU, distinct, on-theme)
1. **nolitsa** — surrogate/IAAFT "real-vs-noise" hypothesis test (the flagship gap) ⭐
2. **Robust PCA** (rpca) — low-rank signal vs sparse noise
3. **signal-decomposition** (Boyd) — named-component split
4. **python-picard** — ICA blind source separation
5. **VMD** (sktime) + **ewtpy** — adaptive mode decomposition
6. **scikit-rmt** — RMT denoiser (upgrade the recipe)
7. **multitaper** F-test + **astropy** Lomb-Scargle FAP — weak-signal significance
8. **claspy** + **tslearn** (SAX/shapelets) — recurring-state + symbolic motifs
9. **bayesian_changepoint_detection** — online break probability
10. self-implemented: **0-1 chaos test**, **NCD (lzma)**, **stochastic-resonance** detector
(+ sklearn FastICA/DictionaryLearning, scipy savgol, skimage TV/wavelet denoise — no new deps)
