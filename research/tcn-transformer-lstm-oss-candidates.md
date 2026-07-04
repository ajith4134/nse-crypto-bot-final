# OSS candidates: TCN / encoder-only TS transformer / LSTM (CPU-first PyTorch)

Researched 2026-07-03 (README-level only, per /research-projects Phase 1).
Context: next-bar direction probability nodes; PyTorch-CPU + numpy; avoid sklearn/keras/lightning weight where possible.

## AREA 1 — Causal TCN (64 bars x 12 feats -> up-probability)

| Project | Repo | pip | Key features | Stars | Recency | CPU fit | Verdict |
|---|---|---|---|---|---|---|---|
| pytorch-tcn (paul-krug) | github.com/paul-krug/pytorch-tcn | `pytorch-tcn` | Bai et al. TCN + WaveNet skip conns; togglable causal TemporalConv1d/TransposeConv1d w/ auto padding; dilation patterns + dilation-reset for deep nets; weight/batch/layer norm; configurable activations/inits; gated linear units; NCL & NLC input; block-wise streaming inference (internal buffers, bs=1); ONNX export | 203 | v1.2.3 Apr 7 2025; active | 10 | **pip — WINNER** |
| locuslab/TCN | github.com/locuslab/TCN | none | Original Bai et al. reference; TemporalConvNet + benchmark tasks only; not a package | 4.5k | Stale (research artifact, ~2018-2019 era; "PyTorch>1.3 recommended") | 8 (tiny code) | skip (superseded by pytorch-tcn which packages the same arch) |
| keras-tcn | github.com/philipperemy/keras-tcn | `keras-tcn` | Mature TCN but Keras/TF backend | ~1.9k | maintained | 2 (wrong framework) | skip |
| Nixtla neuralforecast TCN | nixtlaverse.nixtla.io | `neuralforecast` | TCN among many models, but drags pytorch-lightning + full forecasting framework | 3k+ | active | 4 (heavy deps) | skip for this node |
| tsai TCN | github.com/timeseriesAI/tsai | `tsai` | TCN among 30+ models; fastai dependency | 6.1k | v1.0.1 May 27 2026 | 5 (fastai dep) | skip for TCN (see Area 2) |

**Recommendation (Area 1):** `pip install pytorch-tcn` (v1.2.3, Apr 2025) is the clear winner: it is exactly the requested architecture (causal dilated convs, weight-norm option, dropout, skip connections) as a clean nn.Module with only a torch dependency, plus streaming inference for live next-bar use and ONNX export. locuslab/TCN is the un-packaged ancestor of the same design; keras-tcn is the wrong framework. Glue needed is trivial: `TCN(num_inputs=12, num_channels=[...], causal=True, input_shape='NLC')` + a `Linear(ch,1)+sigmoid` head over the last timestep.

## AREA 2 — Encoder-only time-series transformer (custom 60-line vs pip)

| Project | Repo | pip | Key features | Stars | Recency | CPU fit | Verdict |
|---|---|---|---|---|---|---|---|
| Custom module (ours) | in-repo | n/a | Linear(9->64) + learnable pos-emb (1,30,64) + nn.TransformerEncoder 2L/8H/FF256 + last-step pool + head; zero deps beyond torch | n/a | n/a | 10 | **build custom — WINNER** |
| yuqinie98/PatchTST (official) | github.com/yuqinie98/PatchTST | none | Official ICLR'23 code; supervised + self-supervised; research scripts, not a library | 2.6k | Low activity since paper era | 6 | skip (use a packaged port if PatchTST wanted) |
| thuml/iTransformer (official) | github.com/thuml/iTransformer | `iTransformer` (lucidrains port, May 2024) | Inverted (variate-token) transformer; arbitrary #variables; pip package exists but is lucidrains' re-impl | 2.2k | Moderate; integrations into GluonTS/NeuralForecast | 6 | skip for now (variate-token design suits multivariate long-horizon, not 30-step next-bar) |
| thuml/Time-Series-Library | github.com/thuml/Time-Series-Library | none (clone-only) | 40+ models incl. PatchTST/iTransformer/TimesNet/DLinear; correct baselines | 12.5k | Active-ish 2026.04 but "will not actively add features", limited bandwidth | 5 (framework-shaped, clone-only) | vendor-single-file only if we later want many baselines |
| HF transformers PatchTST/PatchTSMixer | huggingface.co/docs/transformers | `transformers` | PatchTSTForPrediction/Classification, PatchTSMixer; maintained by HF | n/a | Actively maintained in transformers | 5 (heavy import/startup for one small model) | write-custom-glue only if transformers already imported in-process |
| tsai (unofficial PatchTST + TST) | github.com/timeseriesAI/tsai | `tsai` | PatchTST, TST, TSTPlus, 30+ models; Python 3.10+ | 6.1k | v1.0.1 May 27 2026 — best-maintained TS lib right now | 6 (fastai dep, but "hard deps only" install) | fallback pip if we want packaged PatchTST |

**Recommendation (Area 2):** Custom is clearly right. The specified module is ~60 lines of pure `torch.nn` with zero extra dependencies — every pip alternative costs more (transformers import weight, fastai via tsai, lightning via neuralforecast, or clone-only research code from TSLib/official PatchTST) and none matches the exact spec (9-feat, 30-step, last-step pooling). If we later want PatchTST on CPU, the lightest paths are (a) tsai's `PatchTST` (only fastai extra) or (b) HF `PatchTSTForPrediction` if transformers is already loaded; iTransformer's variate-as-token design targets many-variable long-horizon forecasting and is a poor fit for a 30-bar window.

## AREA 3 — LSTM/RNN price prediction (PyTorch)

| Project | Repo | pip | Key features | Stars | Recency | CPU fit | Verdict |
|---|---|---|---|---|---|---|---|
| Custom nn.LSTM | in-repo | n/a | nn.LSTM(input,150)+Linear(150,1) = exact PyTorch equivalent of the Keras LSTM(150)->Dense(1); ~15 lines | n/a | n/a | 10 | **build custom — WINNER** |
| pytorch-forecasting | github.com/sktime/pytorch-forecasting | `pytorch-forecasting` | LSTM/GRU/DeepAR/TFT with high-level API; sktime-org maintained | ~4k | actively maintained (sktime org) | 4 (pytorch-lightning + pandas framework lock-in) | skip for a single LSTM head |
| ProsperNN | (PyPI prospernn) | `prospernn` | ECNN/HCNN/CRCNN niche architectures in PyTorch | small | 2024 paper release | 6 | skip (niche, low adoption) |
| NX-AI/xlstm | github.com/NX-AI/xlstm | `xlstm` | Official sLSTM/mLSTM; v2.0.4 May 28 2025; sLSTM CUDA kernels need CC>=8.0; native PyTorch fallback exists (slower) | 2.2k | active | 5 (CUDA-first; PyTorch fallback OK for small models) | vendor/pip LATER as experimental node, not the baseline |
| pykan | github.com/KindXiaoming/pykan | `pykan` | Official KAN + KAN 2.0; interpretability-first, author ran sweeps on CPU; NOT perf-optimized; pulls sklearn/sympy | 16.3k | v0.2.8 Nov 14 2024 | 5 | skip as predictor (deps + speed) |
| efficient-kan | github.com/Blealtan/efficient-kan | none on PyPI (has pyproject) | Memory-efficient KAN reformulation (~31% faster inference than pykan), single-file, MIT | 4.7k | Stale (last meaningful commit May 2024, 18 commits, no releases) | 7 (tiny, torch-only) | vendor single file if a KAN node is wanted |

**Recommendation (Area 3):** Custom `nn.LSTM` is obviously correct — the Keras LSTM(150)->Dense(1) reference translates to ~15 lines of torch with nothing to gain from pytorch-forecasting's lightning framework for a single small model. For modern alternatives: xLSTM has a real pip package (`xlstm` v2.0.4, May 2025) and a native-PyTorch path that works on CPU for small configs (CUDA kernels are only for the sLSTM fast path / 7B model), so it's a reasonable *experimental* second node later. KAN: pykan is maintained but interpretability-first and dep-heavy; efficient-kan is the CPU-fast variant but effectively unmaintained since May 2024 — if a KAN node is desired, vendor efficient-kan's single file rather than pip pykan.

## Cross-area summary
- Pip: `pytorch-tcn==1.2.3` (only new dependency actually recommended now).
- Custom: encoder transformer (as specced) + nn.LSTM head.
- Later/optional: `xlstm` pip (experimental node), vendor efficient-kan single file, tsai as the packaged-PatchTST fallback.
