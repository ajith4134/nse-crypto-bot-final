"""Tier-1 foundation / SOTA model nodes (groups A–F of research/model-catalog-22parts.md).

Reuse-first wrappers around installed OSS, each conforming to NodeProtocol via the
existing task-aware readout bases (`_HeadBase`, `_PanelNode`). Every heavy import is
guarded so a missing dep just makes that node unavailable (pool.py skips it) — never
breaks the graph. CPU-first: foundation models run frozen/tiny; trainable forecasters
use small step budgets.

Groups:
  A  ChronosNode / TimesFMNode       — Amazon Chronos + Google TimesFM zero-shot TS foundation models
     TinyTimeMixerNode / MoiraiNode  — IBM Granite TTM + Salesforce Moirai + Lag-Llama, VENDORED
     / LagLlamaNode                    (git-cloned into vendor/, pip-unpackageable on py3.13)
  B  PatchTSTNode/ITransformerNode/  — Nixtla neuralforecast SOTA supervised forecasters
     TFTNode
  C  GPyTorchGPNode                  — scalable exact GP w/ calibrated mean (uncertainty)
     GluonTSDeepARNode               — DeepAR probabilistic forecaster
  D  CrossAssetGNNNode               — PyTorch-Geometric GraphSAGE over a kNN feature graph
  E  TigramiteCausalNode             — PCMCI+ time-series causal feature selection
  F  RiskfolioWeightNode/            — portfolio optimizers as target-weight features
     PyPortfolioOptWeightNode
"""
from __future__ import annotations

import os
import sys
import warnings

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector
from nodes.quant_nodes import _HeadBase
from nodes.dl_nodes import _ARFallback
from nodes.cross_sectional_nodes import _PanelNode

# --------------------------------------------------------------------------- #
#  Vendored heavy foundation models (git-cloned into vendor/, see vendor/README)
#  — these three are pip-unpackageable on this py3.13 env, so we vendor + path-insert.
# --------------------------------------------------------------------------- #
_VENDOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor")


def _add_vendor_path(*rel):
    for r in rel:
        p = os.path.join(_VENDOR, r)
        if p not in sys.path:
            sys.path.insert(0, p)


# =========================================================================== #
#  Shared base for external (non-darts) one-step forecasters
# =========================================================================== #
class _ExternalForecastBase(_HeadBase):
    """Fit an external forecaster on the target series; expose its aligned one-step
    forecast as an extra feature to the task-aware `_HeadBase` readout. Mirrors
    dl_nodes._DLForecastBase but for models with their own predict API."""

    kind = "foundation"

    def __init__(self, name: str, summary: str, col: int = 0):
        super().__init__(name, summary, col=col)
        self._ytr = None
        self._fitted = None          # in-sample one-step array aligned to training rows
        self.fell_back = False

    # subclasses implement these two
    def _fit_forecaster(self, y: np.ndarray) -> np.ndarray:
        """Fit and return an in-sample one-step forecast array (length == len(y))."""
        raise NotImplementedError

    def _forecast(self, h: int) -> np.ndarray:
        raise NotImplementedError

    def fit(self, X: Matrix, y: Labels) -> "_ExternalForecastBase":
        self._ytr = np.asarray(y, float).reshape(-1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                fc = np.asarray(self._fit_forecaster(self._ytr), float).reshape(-1)
                if len(fc) != len(self._ytr):
                    raise ValueError("length mismatch")
                self._fitted = fc
            except Exception:
                self._fitted = _ARFallback().fit(self._ytr).insample()
                self.fell_back = True
        return super().fit(X, y)

    def _augment(self, X: Matrix) -> np.ndarray:
        base = np.asarray([[float(v) for v in row] for row in X], float)
        n = len(X)
        if self._fitted is not None and n == len(self._fitted):
            fc = self._fitted
        else:
            try:
                fc = self._forecast(n)
            except Exception:
                last = float(self._ytr[-1]) if self._ytr is not None else 0.0
                fc = np.full(n, last)
        fc = np.asarray(fc, float).reshape(-1)
        if len(fc) != n:
            fc = (fc[:n] if len(fc) > n
                  else np.concatenate([fc, np.full(n - len(fc), fc[-1] if len(fc) else 0.0)]))
        return np.hstack([base, fc.reshape(-1, 1)])


# =========================================================================== #
#  GROUP A — Chronos zero-shot foundation model
# =========================================================================== #
class ChronosNode(_ExternalForecastBase):
    """Amazon Chronos-T5 (tiny, ~8M) zero-shot TS foundation model. No training —
    frozen encoder-decoder produces one-step forecasts from rolling context. The
    biggest capability gap vs our trained-per-node forecasters."""

    _PIPE = None            # class-cached pipeline (load once)
    MODEL = "amazon/chronos-t5-tiny"
    MIN_CTX = 32
    STRIDE = 8              # strided anchors + fill → bounded CPU cost

    def __init__(self, name="chronos", col=0):
        super().__init__(name, "Amazon Chronos-T5 zero-shot TS foundation model (frozen, CPU).", col)

    @classmethod
    def _pipe(cls):
        if cls._PIPE is None:
            import torch
            from chronos import ChronosPipeline
            cls._PIPE = ChronosPipeline.from_pretrained(
                cls.MODEL, device_map="cpu", torch_dtype=torch.float32)
        return cls._PIPE

    def _fit_forecaster(self, y: np.ndarray) -> np.ndarray:
        import torch
        pipe = self._pipe()
        n = len(y)
        anchors = list(range(self.MIN_CTX, n, self.STRIDE))
        if not anchors:
            return np.concatenate([y[:1], y[:-1]])          # trivial shift for short series
        contexts = [torch.tensor(y[:a], dtype=torch.float32) for a in anchors]
        # batched median one-step forecast at each anchor
        fc = pipe.predict(contexts, prediction_length=1, limit_prediction_length=False)
        preds = [float(np.median(np.asarray(f).reshape(-1))) for f in fc]
        out = np.empty(n, float)
        out[:anchors[0]] = y[:anchors[0]]                   # warm-up: use actuals
        for i, a in enumerate(anchors):
            end = anchors[i + 1] if i + 1 < len(anchors) else n
            out[a:end] = preds[i]                           # forward-fill to next anchor
        return out

    def _forecast(self, h: int) -> np.ndarray:
        import torch
        pipe = self._pipe()
        ctx = torch.tensor(self._ytr, dtype=torch.float32)
        f = pipe.predict(ctx, prediction_length=max(1, h), limit_prediction_length=False)
        return np.median(np.asarray(f[0]), axis=0).reshape(-1)[:h]


class TimesFMNode(_ExternalForecastBase):
    """Google TimesFM 2.5 (200M, torch) zero-shot TS foundation model. Frozen decoder
    produces one-step forecasts from rolling context — the second pretrained FM channel
    alongside Chronos. Checkpoint downloads once from HF; CPU inference ~0.2s/call."""

    _MODEL = None
    REPO = "google/timesfm-2.5-200m-pytorch"
    MIN_CTX = 32
    STRIDE = 8
    MAX_CTX = 256

    def __init__(self, name="timesfm", col=0):
        super().__init__(name, "Google TimesFM 2.5 zero-shot TS foundation model (frozen, CPU).", col)

    @classmethod
    def _model(cls):
        if cls._MODEL is None:
            import timesfm
            m = timesfm.TimesFM_2p5_200M_torch.from_pretrained(cls.REPO)
            m.compile(timesfm.ForecastConfig(
                max_context=cls.MAX_CTX, max_horizon=8, normalize_inputs=True))
            cls._MODEL = m
        return cls._MODEL

    def _fit_forecaster(self, y: np.ndarray) -> np.ndarray:
        m = self._model()
        n = len(y)
        anchors = list(range(self.MIN_CTX, n, self.STRIDE))
        if not anchors:
            return np.concatenate([y[:1], y[:-1]])
        inputs = [y[max(0, a - self.MAX_CTX):a].tolist() for a in anchors]
        pf, _ = m.forecast(horizon=1, inputs=inputs)
        preds = np.asarray(pf, float).reshape(len(anchors), -1)[:, 0]
        out = np.empty(n, float)
        out[:anchors[0]] = y[:anchors[0]]
        for i, a in enumerate(anchors):
            end = anchors[i + 1] if i + 1 < len(anchors) else n
            out[a:end] = preds[i]
        return out

    def _forecast(self, h: int) -> np.ndarray:
        m = self._model()
        ctx = self._ytr[-self.MAX_CTX:].tolist()
        pf, _ = m.forecast(horizon=max(1, min(h, 8)), inputs=[ctx])
        v = np.asarray(pf, float).reshape(-1)
        if len(v) < h:
            v = np.concatenate([v, np.full(h - len(v), v[-1] if len(v) else 0.0)])
        return v[:h]


class TinyTimeMixerNode(_ExternalForecastBase):
    """IBM Granite TinyTimeMixer (TTM) — tiny (<1M param) pretrained zero-shot forecaster.
    Vendored (vendor/granite_tsfm). Left-pads/truncates the series to the model context."""

    _MODEL = None
    REPO = "ibm-granite/granite-timeseries-ttm-r2"
    CTX = 512
    MIN_CTX = 32
    STRIDE = 16

    def __init__(self, name="tinytimemixer", col=0):
        super().__init__(name, "IBM Granite TinyTimeMixer zero-shot forecaster (vendored, CPU).", col)

    @classmethod
    def _model(cls):
        if cls._MODEL is None:
            _add_vendor_path("granite_tsfm")
            from tsfm_public.models.tinytimemixer import TinyTimeMixerForPrediction
            cls._MODEL = TinyTimeMixerForPrediction.from_pretrained(cls.REPO).eval()
        return cls._MODEL

    def _ctx_tensor(self, series):
        import torch
        s = np.asarray(series, float).reshape(-1)
        if len(s) < self.CTX:
            s = np.concatenate([np.full(self.CTX - len(s), s[0]), s])
        else:
            s = s[-self.CTX:]
        return torch.tensor(s.reshape(1, self.CTX, 1), dtype=torch.float32)

    def _one_step(self, series):
        import torch
        m = self._model()
        with torch.no_grad():
            out = m(past_values=self._ctx_tensor(series))
        pred = out.prediction_outputs if hasattr(out, "prediction_outputs") else out[0]
        return float(np.asarray(pred).reshape(-1)[0])

    def _fit_forecaster(self, y: np.ndarray) -> np.ndarray:
        n = len(y)
        anchors = list(range(self.MIN_CTX, n, self.STRIDE))
        if not anchors:
            return np.concatenate([y[:1], y[:-1]])
        out = np.empty(n, float)
        out[:anchors[0]] = y[:anchors[0]]
        for i, a in enumerate(anchors):
            end = anchors[i + 1] if i + 1 < len(anchors) else n
            out[a:end] = self._one_step(y[:a])
        return out

    def _forecast(self, h: int) -> np.ndarray:
        return np.full(h, self._one_step(self._ytr))


class MoiraiNode(_ExternalForecastBase):
    """Salesforce Moirai — universal masked-encoder TS foundation model. Vendored
    (vendor/uni2ts). Uses MoiraiForecast one-step median over rolling context."""

    _MODULE = None
    REPO = "Salesforce/moirai-1.1-R-small"
    CTX = 128
    MIN_CTX = 32
    STRIDE = 16
    PSZ = 16

    def __init__(self, name="moirai", col=0):
        super().__init__(name, "Salesforce Moirai universal TS foundation model (vendored, CPU).", col)

    @classmethod
    def _module(cls):
        if cls._MODULE is None:
            _add_vendor_path(os.path.join("uni2ts", "src"))
            from uni2ts.model.moirai import MoiraiModule
            cls._MODULE = MoiraiModule.from_pretrained(cls.REPO)
        return cls._MODULE

    def _forecaster(self, ctx_len):
        _add_vendor_path(os.path.join("uni2ts", "src"))
        from uni2ts.model.moirai import MoiraiForecast
        return MoiraiForecast(module=self._module(), prediction_length=1,
                              context_length=ctx_len, patch_size=self.PSZ,
                              num_samples=20, target_dim=1, feat_dynamic_real_dim=0,
                              past_feat_dynamic_real_dim=0).create_predictor(batch_size=32)

    def _one_step_batch(self, series, anchors):
        import torch
        import pandas as pd
        from gluonts.dataset.common import ListDataset
        ds = ListDataset(
            [{"start": pd.Period("2020-01-01", "D"),
              "target": series[max(0, a - self.CTX):a]} for a in anchors], freq="D")
        pred = self._forecaster(self.CTX)
        with torch.no_grad():
            fcs = list(pred.predict(ds))
        return [float(np.median(f.samples)) for f in fcs]

    def _fit_forecaster(self, y: np.ndarray) -> np.ndarray:
        n = len(y)
        anchors = list(range(self.MIN_CTX, n, self.STRIDE))
        if not anchors:
            return np.concatenate([y[:1], y[:-1]])
        preds = self._one_step_batch(y.tolist(), anchors)
        out = np.empty(n, float)
        out[:anchors[0]] = y[:anchors[0]]
        for i, a in enumerate(anchors):
            end = anchors[i + 1] if i + 1 < len(anchors) else n
            out[a:end] = preds[i]
        return out

    def _forecast(self, h: int) -> np.ndarray:
        v = self._one_step_batch(self._ytr.tolist(), [len(self._ytr)])[0]
        return np.full(h, v)


class LagLlamaNode(_ExternalForecastBase):
    """Lag-Llama — decoder-only probabilistic TS foundation model. Vendored
    (vendor/lag_llama, with a gluonts-loss compat shim + data→ll_data rename).
    Downloads its checkpoint from HF once, then rolling one-step median."""

    _PRED = None
    CKPT_REPO = "time-series-foundation-models/Lag-Llama"
    CKPT_FILE = "lag-llama.ckpt"
    CTX = 32
    MIN_CTX = 32
    STRIDE = 16

    def __init__(self, name="lag_llama", col=0):
        super().__init__(name, "Lag-Llama decoder-only probabilistic TS foundation model (vendored, CPU).", col)

    @classmethod
    def _estimator(cls):
        import types
        import torch
        from huggingface_hub import hf_hub_download
        _add_vendor_path("lag_llama")
        from lag_llama.gluon.estimator import LagLlamaEstimator
        # The published checkpoint pickles references to gluonts.torch.modules.loss
        # (removed in newer gluonts). Alias our compat shim under the old dotted path
        # so torch.load can unpickle it.
        import _gluonts_compat as _gc
        for name in ("gluonts.torch.modules", "gluonts.torch.modules.loss"):
            if name not in sys.modules:
                sys.modules[name] = _gc if name.endswith("loss") else types.ModuleType(name)
        ckpt = hf_hub_download(repo_id=cls.CKPT_REPO, filename=cls.CKPT_FILE)
        est_args = torch.load(ckpt, map_location="cpu", weights_only=False)["hyper_parameters"]["model_kwargs"]
        return LagLlamaEstimator(
            ckpt_path=ckpt, prediction_length=1, context_length=cls.CTX,
            input_size=est_args["input_size"], n_layer=est_args["n_layer"],
            n_embd_per_head=est_args["n_embd_per_head"], n_head=est_args["n_head"],
            scaling=est_args["scaling"], time_feat=est_args["time_feat"],
            nonnegative_pred_samples=True, num_parallel_samples=20,
            device=torch.device("cpu"))

    def _predictor(self):
        if LagLlamaNode._PRED is None:
            est = self._estimator()
            LagLlamaNode._PRED = est.create_predictor(est.create_transformation(),
                                                      est.create_lightning_module())
        return LagLlamaNode._PRED

    def _one_step_batch(self, series, anchors):
        import pandas as pd
        from gluonts.dataset.common import ListDataset
        ds = ListDataset(
            [{"start": pd.Period("2020-01-01", "D"),
              "target": series[max(0, a - self.CTX):a]} for a in anchors], freq="D")
        with _TorchLoadTrusted():
            fcs = list(self._predictor().predict(ds))
        return [float(np.median(f.samples)) for f in fcs]

    def _fit_forecaster(self, y: np.ndarray) -> np.ndarray:
        n = len(y)
        anchors = list(range(self.MIN_CTX, n, self.STRIDE))
        if not anchors:
            return np.concatenate([y[:1], y[:-1]])
        preds = self._one_step_batch(y.tolist(), anchors)
        out = np.empty(n, float)
        out[:anchors[0]] = y[:anchors[0]]
        for i, a in enumerate(anchors):
            end = anchors[i + 1] if i + 1 < len(anchors) else n
            out[a:end] = preds[i]
        return out

    def _forecast(self, h: int) -> np.ndarray:
        v = self._one_step_batch(self._ytr.tolist(), [len(self._ytr)])[0]
        return np.full(h, v)


# =========================================================================== #
#  GROUP B — Nixtla neuralforecast SOTA supervised forecasters
# =========================================================================== #
class _NFForecastBase(_ExternalForecastBase):
    """Base for Nixtla neuralforecast models (PatchTST / iTransformer / TFT).
    Trains a tiny model on the target series, uses in-sample fitted values as the
    aligned one-step feature. Small step budget keeps it CPU-fast."""

    kind = "foundation"
    INPUT = 16
    MAX_STEPS = 40

    def _make_model(self):
        raise NotImplementedError

    def _fit_forecaster(self, y: np.ndarray) -> np.ndarray:
        import pandas as pd
        from neuralforecast import NeuralForecast
        n = len(y)
        df = pd.DataFrame({"unique_id": "s", "ds": np.arange(n), "y": y})
        self._nf = NeuralForecast(models=[self._make_model()], freq=1)
        # cross_validation (refit=False) works for uni- AND multivariate models and
        # yields genuine one-step out-of-sample forecasts (predict_insample is not
        # supported for multivariate models like iTransformer).
        K = max(1, n - self.INPUT - 1)
        cv = self._nf.cross_validation(df, n_windows=K, step_size=1, refit=False)
        col = [c for c in cv.columns if c not in ("unique_id", "ds", "cutoff", "y")][0]
        self._col = col
        vals = np.asarray(cv[col].values, float).reshape(-1)
        out = np.empty(n, float)
        pad = n - len(vals)
        out[:pad] = y[:pad] if pad > 0 else vals[:1]
        out[pad:] = vals[-(n - pad):] if pad >= 0 else vals[-n:]
        out[~np.isfinite(out)] = 0.0
        return out

    def _forecast(self, h: int) -> np.ndarray:
        fc = self._nf.predict()
        v = np.asarray(fc[self._col].values, float).reshape(-1)
        if len(v) < h:
            v = np.concatenate([v, np.full(h - len(v), v[-1] if len(v) else 0.0)])
        return v[:h]


class PatchTSTNode(_NFForecastBase):
    """PatchTST (patch transformer) — long-horizon SOTA supervised forecaster."""

    def __init__(self, name="patchtst", col=0):
        super().__init__(name, "Nixtla PatchTST patch-transformer forecaster (CPU-tiny).", col)

    def _make_model(self):
        from neuralforecast.models import PatchTST
        return PatchTST(h=1, input_size=self.INPUT, max_steps=self.MAX_STEPS,
                        scaler_type="robust", enable_progress_bar=False,
                        accelerator="cpu", logger=False)


class ITransformerNode(_NFForecastBase):
    """iTransformer (inverted attention) — multivariate-SOTA forecaster."""

    def __init__(self, name="itransformer", col=0):
        super().__init__(name, "Nixtla iTransformer inverted-attention forecaster (CPU-tiny).", col)

    def _make_model(self):
        from neuralforecast.models import iTransformer
        return iTransformer(h=1, input_size=self.INPUT, n_series=1,
                            max_steps=self.MAX_STEPS, scaler_type="robust",
                            enable_progress_bar=False, accelerator="cpu", logger=False)


class TFTNode(_NFForecastBase):
    """Temporal Fusion Transformer — interpretable multi-horizon forecaster."""

    def __init__(self, name="tft", col=0):
        super().__init__(name, "Nixtla Temporal Fusion Transformer forecaster (CPU-tiny).", col)

    def _make_model(self):
        from neuralforecast.models import TFT
        return TFT(h=1, input_size=self.INPUT, max_steps=self.MAX_STEPS,
                   scaler_type="robust", enable_progress_bar=False,
                   accelerator="cpu", logger=False)


# =========================================================================== #
#  GROUP C — uncertainty: GPyTorch scalable GP + GluonTS DeepAR
# =========================================================================== #
class GPyTorchGPNode(BaseNode):
    """GPyTorch exact GP with a calibrated posterior mean. Replaces the sklearn
    GaussianProcessNode's O(n^3) 800-row ceiling with a torch GP that scales
    further and exposes predictive variance (uncertainty for sizing)."""

    kind = "probabilistic"
    MAX_ROWS = 1200
    ITERS = 60

    def __init__(self, name="gpytorch_gp", col=0):
        self.name, self.summary = name, "GPyTorch exact GP w/ calibrated mean + variance."
        self.task, self.head = "regression", "y"
        self.col = col
        self._model = None
        self._var = None
        self.schema = IOSchema(0, "features", "gp mean")

    def _prep(self, X):
        A = np.asarray([[float(v) for v in r] for r in X], float)
        A[~np.isfinite(A)] = 0.0
        return A

    def fit(self, X: Matrix, y: Labels) -> "GPyTorchGPNode":
        import torch
        import gpytorch
        A = self._prep(X)
        ya = np.asarray(y, float).reshape(-1)
        self.task = "regression" if len(set(ya.tolist())) > 3 else "binary"
        self.schema = IOSchema(len(X[0]), f"{len(X[0])} numeric features", "gp mean")
        if len(A) > self.MAX_ROWS:                          # subsample for O(n^3) safety
            idx = np.linspace(0, len(A) - 1, self.MAX_ROWS).astype(int)
            A, ya = A[idx], ya[idx]
        self._mu, self._sd = A.mean(0), A.std(0) + 1e-9
        self._ymu, self._ysd = float(ya.mean()), float(ya.std()) + 1e-9
        Xt = torch.tensor((A - self._mu) / self._sd, dtype=torch.float32)
        yt = torch.tensor((ya - self._ymu) / self._ysd, dtype=torch.float32)

        class _GP(gpytorch.models.ExactGP):
            def __init__(s, xtr, ytr, lik):
                super().__init__(xtr, ytr, lik)
                s.mean_module = gpytorch.means.ConstantMean()
                s.covar_module = gpytorch.kernels.ScaleKernel(gpytorch.kernels.RBFKernel())

            def forward(s, x):
                return gpytorch.distributions.MultivariateNormal(
                    s.mean_module(x), s.covar_module(x))

        self._lik = gpytorch.likelihoods.GaussianLikelihood()
        self._model = _GP(Xt, yt, self._lik)
        self._model.train(); self._lik.train()
        opt = torch.optim.Adam(self._model.parameters(), lr=0.1)
        mll = gpytorch.mlls.ExactMarginalLogLikelihood(self._lik, self._model)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for _ in range(self.ITERS):
                opt.zero_grad()
                loss = -mll(self._model(Xt), yt)
                loss.backward(); opt.step()
        self._model.eval(); self._lik.eval()
        return self

    def _posterior(self, X):
        import torch
        import gpytorch
        A = self._prep(X)
        Xt = torch.tensor((A - self._mu) / self._sd, dtype=torch.float32)
        with torch.no_grad(), gpytorch.settings.fast_pred_var(), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            post = self._lik(self._model(Xt))
        mean = post.mean.numpy() * self._ysd + self._ymu
        std = post.variance.clamp_min(1e-9).sqrt().numpy() * self._ysd
        self._var = std
        return mean, std

    def predict_output(self, X: Matrix) -> list[list[float]]:
        if self._model is None:
            return [[0.0]] * len(X)
        mean, _ = self._posterior(X)
        return [[float(v)] for v in mean]

    def predict_proba(self, X: Matrix) -> Vector:
        if self._model is None:
            return [0.5] * len(X)
        mean, _ = self._posterior(X)
        lo, hi = float(mean.min()), float(mean.max())
        return [float((v - lo) / (hi - lo)) if hi > lo else 0.5 for v in mean]

    def predict(self, X: Matrix) -> Labels:
        if self.task == "regression":
            return [int(round(r[0])) for r in self.predict_output(X)]
        return [1 if p >= 0.5 else 0 for p in self.predict_proba(X)]


class _TorchLoadTrusted:
    """Context: force torch.load(weights_only=False) so GluonTS can reload its own
    best checkpoint under PyTorch>=2.6 (whose default weights_only=True rejects the
    pickled globals). Scoped — only affects loads inside the with-block."""

    def __enter__(self):
        import torch
        self._orig = torch.load

        def _patched(*a, **k):
            k["weights_only"] = False
            return self._orig(*a, **k)
        torch.load = _patched
        return self

    def __exit__(self, *exc):
        import torch
        torch.load = self._orig
        return False


class GluonTSDeepARNode(_ExternalForecastBase):
    """GluonTS DeepAR — autoregressive probabilistic forecaster; the one-step
    predictive median feeds the readout (full distribution available for sizing)."""

    kind = "probabilistic"
    CTX = 16
    EPOCHS = 5

    def __init__(self, name="gluonts_deepar", col=0):
        super().__init__(name, "GluonTS DeepAR probabilistic forecaster (CPU, tiny).", col)

    def _fit_forecaster(self, y: np.ndarray) -> np.ndarray:
        from gluonts.dataset.common import ListDataset
        from gluonts.torch import DeepAREstimator
        n = len(y)
        ds = ListDataset([{"start": "2020-01-01", "target": y.tolist()}], freq="D")
        est = DeepAREstimator(prediction_length=1, context_length=self.CTX, freq="D",
                              trainer_kwargs={"max_epochs": self.EPOCHS,
                                              "accelerator": "cpu", "enable_progress_bar": False,
                                              "logger": False})
        with _TorchLoadTrusted():
            self._pred = est.train(ds)
            # in-sample one-step: quick strided rolling median
            preds = np.empty(n, float)
            preds[: self.CTX] = y[: self.CTX]
            step = max(1, n // 120)
            anchors = list(range(self.CTX, n, step))
            ctxs = ListDataset(
                [{"start": "2020-01-01", "target": y[:a].tolist()} for a in anchors], freq="D")
            fcs = list(self._pred.predict(ctxs))
        for i, a in enumerate(anchors):
            end = anchors[i + 1] if i + 1 < len(anchors) else n
            preds[a:end] = float(np.median(fcs[i].samples))
        self._last_ctx = y
        return preds

    def _forecast(self, h: int) -> np.ndarray:
        from gluonts.dataset.common import ListDataset
        ds = ListDataset([{"start": "2020-01-01", "target": self._ytr.tolist()}], freq="D")
        with _TorchLoadTrusted():
            f = next(iter(self._pred.predict(ds)))
        v = np.median(f.samples, axis=0).reshape(-1)
        return np.full(h, float(v[0]) if len(v) else float(self._ytr[-1]))


# =========================================================================== #
#  GROUP D — cross-asset relational GNN (PyTorch Geometric)
# =========================================================================== #
class CrossAssetGNNNode(_HeadBase):
    """PyTorch-Geometric GraphSAGE over a kNN graph of the feature rows. Learns
    relational structure our per-series nodes cannot; the learned node embedding
    is concatenated as features for the task-aware readout. Transductive: test
    rows attach to their nearest training rows."""

    kind = "graph"
    K = 8
    HID = 16
    EPOCHS = 40

    def __init__(self, name="graphsage_xasset", col=0):
        super().__init__(name, "PyTorch-Geometric GraphSAGE relational embedding node.", col)
        self._emb_dim = 0

    def _knn_edges(self, A):
        from sklearn.neighbors import NearestNeighbors
        k = int(min(self.K + 1, len(A)))
        nn = NearestNeighbors(n_neighbors=k).fit(A)
        _, idx = nn.kneighbors(A)
        src, dst = [], []
        for i, row in enumerate(idx):
            for j in row[1:]:
                src += [i, int(j)]; dst += [int(j), i]      # undirected
        return np.array([src, dst], dtype=np.int64)

    def _embed(self, A):
        import torch
        from torch_geometric.data import Data
        edge = torch.tensor(self._knn_edges(A), dtype=torch.long)
        x = torch.tensor(A, dtype=torch.float32)
        with torch.no_grad():
            z = self._model(x, edge).numpy()
        return z

    def fit(self, X: Matrix, y: Labels) -> "CrossAssetGNNNode":
        import torch
        import torch.nn as nn
        from torch_geometric.nn import SAGEConv
        A = np.asarray([[float(v) for v in r] for r in X], float)
        A[~np.isfinite(A)] = 0.0
        self._mu, self._sd = A.mean(0), A.std(0) + 1e-9
        A = (A - self._mu) / self._sd
        self._Atr = A
        ya = np.asarray(y)
        self.task = "regression" if len(set(ya.tolist())) > 3 else "binary"

        din = A.shape[1]

        class _Net(nn.Module):
            def __init__(s):
                super().__init__()
                s.c1 = SAGEConv(din, CrossAssetGNNNode.HID)
                s.c2 = SAGEConv(CrossAssetGNNNode.HID, CrossAssetGNNNode.HID)

            def forward(s, x, e):
                h = torch.relu(s.c1(x, e))
                return torch.relu(s.c2(h, e))

        self._model = _Net()
        # brief self-supervised-ish train: predict y from embedding via a linear head
        from torch_geometric.data import Data
        edge = torch.tensor(self._knn_edges(A), dtype=torch.long)
        x = torch.tensor(A, dtype=torch.float32)
        head = nn.Linear(self.HID, 1)
        yt = torch.tensor(ya.astype(float), dtype=torch.float32).reshape(-1, 1)
        opt = torch.optim.Adam(list(self._model.parameters()) + list(head.parameters()), lr=0.01)
        lossf = nn.MSELoss()
        self._model.train()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for _ in range(self.EPOCHS):
                opt.zero_grad()
                z = self._model(x, edge)
                loss = lossf(head(z), yt)
                loss.backward(); opt.step()
        self._model.eval()
        self._emb_dim = self.HID
        return super().fit(X, y)

    def _augment(self, X: Matrix) -> np.ndarray:
        base = np.asarray([[float(v) for v in r] for r in X], float)
        A = base.copy()
        A[~np.isfinite(A)] = 0.0
        A = (A - self._mu) / self._sd
        # attach test rows to the training manifold by embedding train∪test together
        if not np.array_equal(A, self._Atr):
            stacked = np.vstack([self._Atr, A])
            z = self._embed(stacked)[len(self._Atr):]
        else:
            z = self._embed(A)
        return np.hstack([base, z])


# =========================================================================== #
#  GROUP E — time-series causal feature selection (Tigramite PCMCI+)
# =========================================================================== #
class TigramiteCausalNode(_HeadBase):
    """PCMCI+ (Tigramite) selects the lagged causal parents of the target among
    the features, then reads out on only those columns — cause, not correlation.
    Feature count is capped to bound conditional-independence tests on CPU."""

    kind = "causal"
    TAU_MAX = 3
    MAXF = 12
    ALPHA = 0.05

    def __init__(self, name="tigramite_pcmci", col=0):
        super().__init__(name, "Tigramite PCMCI+ time-series causal feature selection.", col)
        self._sel = None

    def _select(self, X, y):
        from tigramite.data_processing import DataFrame as TgDataFrame
        from tigramite.pcmci import PCMCI
        from tigramite.independence_tests.parcorr import ParCorr
        A = np.asarray([[float(v) for v in r] for r in X], float)
        A[~np.isfinite(A)] = 0.0
        cols = list(range(min(self.MAXF, A.shape[1])))
        data = np.column_stack([A[:, cols], np.asarray(y, float).reshape(-1)])
        tgt = data.shape[1] - 1
        dfr = TgDataFrame(data)
        pcmci = PCMCI(dataframe=dfr, cond_ind_test=ParCorr(), verbosity=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = pcmci.run_pcmci(tau_max=self.TAU_MAX, pc_alpha=self.ALPHA)
        p = res["p_matrix"]                                 # [vars, vars, lags+1]
        sel = []
        for j in cols:
            # j causes target at any lag?
            if np.nanmin(p[j, tgt, :]) < self.ALPHA:
                sel.append(j)
        return sel or cols[: max(1, len(cols) // 2)]        # fallback: half the features

    def fit(self, X: Matrix, y: Labels) -> "TigramiteCausalNode":
        try:
            self._sel = self._select(X, y)
        except Exception:
            self._sel = list(range(len(X[0])))
        return super().fit(X, y)

    def _augment(self, X: Matrix) -> np.ndarray:
        A = np.asarray([[float(v) for v in r] for r in X], float)
        A[~np.isfinite(A)] = 0.0
        sel = self._sel if self._sel else list(range(A.shape[1]))
        sel = [j for j in sel if j < A.shape[1]] or [0]
        return A[:, sel]


# =========================================================================== #
#  GROUP F — portfolio optimizers as target-weight features (panel nodes)
# =========================================================================== #
class RiskfolioWeightNode(_PanelNode):
    """Riskfolio-Lib CVaR/risk-parity portfolio weight of the TARGET asset over a
    rolling window, aligned as a feature. Falls back to inverse-variance weights."""

    W, STRIDE = 90, 5

    def __init__(self, panel: dict):
        super().__init__(panel, "riskfolio_w",
                         "Riskfolio-Lib CVaR portfolio weight of target (rolling).")

    def _rp_weights(self, win_R: np.ndarray) -> np.ndarray:
        import pandas as pd
        import riskfolio as rp
        df = pd.DataFrame(win_R)
        port = rp.Portfolio(returns=df)
        port.assets_stats(method_mu="hist", method_cov="ledoit")
        w = port.optimization(model="Classic", rm="CVaR", obj="Sharpe", hist=True)
        if w is None or w.empty:
            raise ValueError("no solution")
        return np.asarray(w["weights"].values, float).reshape(-1)

    def _panel_feats(self) -> np.ndarray:
        R, W, tgt = self.R, self.W, self.tgt
        T, N = R.shape
        out = np.full((T, 1), 1.0 / N)
        last = np.full(N, 1.0 / N)
        for t in range(T):
            if t >= W and t % self.STRIDE == 0:
                try:
                    last = self._rp_weights(R[t - W:t])
                except Exception:
                    v = 1.0 / (np.nanvar(R[t - W:t], axis=0) + 1e-9)
                    last = v / v.sum()
            out[t, 0] = last[tgt] if tgt < len(last) else 1.0 / N
        return out


class PyPortfolioOptWeightNode(_PanelNode):
    """PyPortfolioOpt max-Sharpe (Ledoit-Wolf) portfolio weight of the TARGET asset
    over a rolling window, aligned as a feature. Falls back to equal weight."""

    W, STRIDE = 90, 5

    def __init__(self, panel: dict):
        super().__init__(panel, "pypfopt_w",
                         "PyPortfolioOpt max-Sharpe weight of target (rolling).")

    def _ef_weights(self, win_R: np.ndarray) -> np.ndarray:
        import pandas as pd
        from pypfopt import expected_returns, risk_models
        from pypfopt.efficient_frontier import EfficientFrontier
        df = pd.DataFrame(win_R)
        mu = expected_returns.mean_historical_return(df, returns_data=True)
        S = risk_models.CovarianceShrinkage(df, returns_data=True).ledoit_wolf()
        ef = EfficientFrontier(mu, S)
        ef.max_sharpe()
        w = ef.clean_weights()
        return np.asarray([w[i] for i in range(win_R.shape[1])], float)

    def _panel_feats(self) -> np.ndarray:
        R, W, tgt = self.R, self.W, self.tgt
        T, N = R.shape
        out = np.full((T, 1), 1.0 / N)
        last = np.full(N, 1.0 / N)
        for t in range(T):
            if t >= W and t % self.STRIDE == 0:
                try:
                    last = self._ef_weights(R[t - W:t])
                except Exception:
                    last = np.full(N, 1.0 / N)
            out[t, 0] = last[tgt] if tgt < len(last) else 1.0 / N
        return out
