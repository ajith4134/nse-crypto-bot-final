"""CPU-practical deep-learning / transformer time-series PREDICTOR nodes.

Wraps Darts (CPU-only) neural forecasters + a small PyTorch autoencoder behind
the project NodeProtocol, reusing the task-aware `_HeadBase` readout machinery
from `nodes.quant_nodes` (binary [1-p, p]; degenerate single-class guard;
multiclass / regression overrides).

Design (mirrors the fit-once forecast nodes in quant_nodes — NO per-row refits):
  * Build a darts TimeSeries from the TRAINING target series.
  * Fit the neural model ONCE on CPU (accelerator="cpu", no GPU).
  * Produce a one-step-ahead forecast aligned per row: in-sample
    `historical_forecasts` for the training rows, recursive out-of-sample
    `predict(h)` for later rows.
  * That forecast value is appended as an extra feature; the `_HeadBase`
    readout maps it to class probabilities (logistic on the predicted value)
    for classification heads, or returns the value for regression.

Robustness: every neural fit is wrapped + TIMED (`self.fit_seconds`). On any
error it falls back to a darts LinearRegressionModel, then to a numpy AR model
(`self.fell_back = True`). Models are kept TINY (input_chunk_length~16,
output 1, n_epochs<=20, small layers) so each fits in well under ~25s on
~600-800 rows.

CPU NOTE: the research flagged TFT / Neural-ODE / full-attention Transformers
as too slow on CPU — those are deliberately NOT built here.
"""
from __future__ import annotations

import time
import warnings

import numpy as np

from core.node_protocol import IOSchema, Labels, Matrix, Vector
from nodes.quant_nodes import _HeadBase

# CPU-only Lightning trainer config shared by every neural node (NO GPU).
_PL_KWARGS = {
    "accelerator": "cpu",
    "enable_progress_bar": False,
    "logger": False,
    "enable_model_summary": False,
    "enable_checkpointing": False,
}


def _silence():
    warnings.filterwarnings("ignore")
    try:
        import logging
        logging.getLogger("pytorch_lightning").setLevel(logging.ERROR)
        logging.getLogger("lightning.pytorch").setLevel(logging.ERROR)
    except Exception:
        pass


def _timeseries(y):
    from darts import TimeSeries
    return TimeSeries.from_values(np.asarray(y, float).reshape(-1))


# --------------------------------------------------------------------------- #
#  numpy AR final-fallback (no deps) — used only if both torch & linear fail
# --------------------------------------------------------------------------- #
class _ARFallback:
    def __init__(self, p: int = 8):
        self.p = p

    def fit(self, y):
        y = np.asarray(y, float).reshape(-1)
        p = int(min(self.p, max(2, len(y) // 4)))
        self.p = p
        rows = np.stack([y[i:i + p] for i in range(len(y) - p)]) if len(y) > p \
            else np.zeros((1, p))
        target = y[p:] if len(y) > p else y[:1]
        design = np.hstack([rows, np.ones((len(rows), 1))])
        self.beta, *_ = np.linalg.lstsq(design, target, rcond=None)
        self._y = y
        self.last = y[-p:].copy()
        return self

    def insample(self):
        y, p = self._y, self.p
        out = y.copy()
        for i in range(p, len(y)):
            out[i] = float(np.dot(self.beta[:-1], y[i - p:i]) + self.beta[-1])
        return out

    def forecast(self, h: int):
        buf = list(self.last)
        out = []
        for _ in range(h):
            v = float(np.dot(self.beta[:-1], buf[-self.p:]) + self.beta[-1])
            out.append(v)
            buf.append(v)
        return np.asarray(out, float)


# --------------------------------------------------------------------------- #
#  Base for darts neural forecast nodes
# --------------------------------------------------------------------------- #
class _DLForecastBase(_HeadBase):
    """Fit a tiny darts neural forecaster once on the target series; expose the
    aligned one-step forecast as a feature for the task-aware readout."""

    kind = "deep_learning"
    INPUT = 16          # input_chunk_length — kept small for CPU speed
    EPOCHS = 15         # <= 20

    def __init__(self, name: str, summary: str, col: int = 0):
        super().__init__(name, summary, col=col)
        self.fit_seconds = 0.0
        self.fell_back = False
        self._model = None
        self._is_ar = False
        self._ar = None
        self._fitted_train = None
        self._ytr = None

    # subclasses build their specific tiny darts model
    def _build_model(self):
        raise NotImplementedError

    def _make_linear(self):
        from darts.models import LinearRegressionModel
        return LinearRegressionModel(lags=self.INPUT)

    # one-step in-sample forecasts aligned to the training rows (front-padded)
    def _insample(self, ts) -> np.ndarray:
        n = len(ts)
        hf = self._model.historical_forecasts(
            ts, retrain=False, forecast_horizon=1, start=self.INPUT,
            stride=1, last_points_only=True, verbose=False,
        )
        vals = np.asarray(hf.values(), float).reshape(-1)
        out = np.empty(n, float)
        pad = n - len(vals)
        out[:pad] = self._ytr[:pad] if pad > 0 else vals[:1]
        out[pad:] = vals
        return out

    def _forecast(self, h: int) -> np.ndarray:
        if self._is_ar:
            fc = self._ar.forecast(h)
        else:
            fc = np.asarray(self._model.predict(h).values(), float).reshape(-1)
        if len(fc) < h:
            fc = np.concatenate([fc, np.full(h - len(fc), fc[-1] if len(fc) else 0.0)])
        return fc[:h]

    def fit(self, X: Matrix, y: Labels) -> "_DLForecastBase":
        _silence()
        self._ytr = np.asarray(y, float).reshape(-1)
        ts = _timeseries(self._ytr)
        t0 = time.time()
        ok = False
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:                                            # 1) tiny neural model
                self._model = self._build_model()
                self._model.fit(ts)
                self._fitted_train = self._insample(ts)
                ok = True
            except Exception:
                ok = False
            if not ok:                                      # 2) darts linear
                try:
                    self._model = self._make_linear()
                    self._model.fit(ts)
                    self._fitted_train = self._insample(ts)
                    self.fell_back = True
                    ok = True
                except Exception:
                    ok = False
            if not ok:                                      # 3) numpy AR
                self._is_ar = True
                self._ar = _ARFallback().fit(self._ytr)
                self._fitted_train = self._ar.insample()
                self.fell_back = True
        self.fit_seconds = time.time() - t0
        return super().fit(X, y)

    def _augment(self, X: Matrix) -> np.ndarray:
        base = np.asarray([[float(v) for v in row] for row in X], float)
        n = len(X)
        if self._fitted_train is not None and n == len(self._fitted_train):
            fc = self._fitted_train                         # training rows
        else:
            try:
                fc = self._forecast(n)                      # out-of-sample
            except Exception:
                last = float(self._ytr[-1]) if self._ytr is not None else 0.0
                fc = np.full(n, last)
        return np.hstack([base, np.asarray(fc, float).reshape(-1, 1)])


# --------------------------------------------------------------------------- #
#  Concrete neural forecast nodes
# --------------------------------------------------------------------------- #
class NHiTSNode(_DLForecastBase):
    """darts NHiTSModel — the research's top CPU pick for neural forecasting."""

    def __init__(self, name="nhits", col=0):
        super().__init__(name, "darts NHiTS neural forecaster (tiny, CPU one-step).", col)

    def _build_model(self):
        from darts.models import NHiTSModel
        return NHiTSModel(
            input_chunk_length=self.INPUT, output_chunk_length=1,
            num_stacks=2, num_blocks=1, num_layers=2, layer_widths=64,
            n_epochs=self.EPOCHS, batch_size=32, random_state=0,
            pl_trainer_kwargs=_PL_KWARGS,
        )


class TCNNode(_DLForecastBase):
    """darts TCNModel — dilated causal temporal-convolution forecaster."""

    def __init__(self, name="tcn", col=0):
        super().__init__(name, "darts TCN dilated-conv neural forecaster (tiny, CPU).", col)

    def _build_model(self):
        from darts.models import TCNModel
        return TCNModel(
            input_chunk_length=self.INPUT, output_chunk_length=1,
            kernel_size=3, num_filters=4, dilation_base=2, num_layers=2,
            dropout=0.0, n_epochs=self.EPOCHS, batch_size=32, random_state=0,
            pl_trainer_kwargs=_PL_KWARGS,
        )


class NBEATSNode(_DLForecastBase):
    """darts NBEATSModel — basis-expansion deep forecaster (generic stacks)."""

    def __init__(self, name="nbeats", col=0):
        super().__init__(name, "darts N-BEATS neural forecaster (tiny, CPU).", col)

    def _build_model(self):
        from darts.models import NBEATSModel
        return NBEATSModel(
            input_chunk_length=self.INPUT, output_chunk_length=1,
            generic_architecture=True, num_stacks=2, num_blocks=1,
            num_layers=2, layer_widths=64,
            n_epochs=self.EPOCHS, batch_size=32, random_state=0,
            pl_trainer_kwargs=_PL_KWARGS,
        )


class TSMixerNode(_DLForecastBase):
    """darts TSMixerModel (MLP-Mixer for time series) if available, else the
    lighter DLinearModel as a drop-in."""

    def __init__(self, name="tsmixer", col=0):
        super().__init__(name, "darts TSMixer (or DLinear fallback) neural forecaster (tiny, CPU).", col)

    def _build_model(self):
        import darts.models as M
        if hasattr(M, "TSMixerModel"):
            return M.TSMixerModel(
                input_chunk_length=self.INPUT, output_chunk_length=1,
                hidden_size=32, ff_size=32, num_blocks=1, dropout=0.0,
                n_epochs=self.EPOCHS, batch_size=32, random_state=0,
                pl_trainer_kwargs=_PL_KWARGS,
            )
        return M.DLinearModel(
            input_chunk_length=self.INPUT, output_chunk_length=1,
            n_epochs=self.EPOCHS, batch_size=32, random_state=0,
            pl_trainer_kwargs=_PL_KWARGS,
        )


class GRUNode(_DLForecastBase):
    """darts RNNModel(model="GRU") — small gated-recurrent forecaster."""

    def __init__(self, name="gru", col=0):
        super().__init__(name, "darts GRU recurrent neural forecaster (tiny, CPU).", col)

    def _build_model(self):
        from darts.models import RNNModel
        return RNNModel(
            model="GRU", input_chunk_length=self.INPUT,
            training_length=self.INPUT + 4, hidden_dim=16, n_rnn_layers=1,
            dropout=0.0, n_epochs=self.EPOCHS, batch_size=32, random_state=0,
            pl_trainer_kwargs=_PL_KWARGS,
        )


# --------------------------------------------------------------------------- #
#  PyTorch dense autoencoder anomaly feature-extractor (no darts)
# --------------------------------------------------------------------------- #
class AEAnomalyNode(_HeadBase):
    """Small PyTorch dense autoencoder (CPU). Trains on TRAIN trailing-window
    feature vectors of the signal; the per-row reconstruction error is an
    anomaly feature appended for the task-aware readout. Feature-extractor."""

    kind = "deep_learning"

    def __init__(self, name="ae_anomaly", col=0, W=16, hidden=8, epochs=30):
        super().__init__(name, "PyTorch dense autoencoder reconstruction-error anomaly feature (CPU).",
                         col=col, W=W)
        self.hidden = hidden
        self.epochs = epochs
        self.fit_seconds = 0.0
        self.fell_back = False
        self._net = None
        self._mu = None
        self._sd = None

    def _windows(self, X: Matrix) -> np.ndarray:
        col = [float(r[self.col]) for r in X]
        W = self.W
        rows = []
        for i in range(len(col)):
            seg = col[max(0, i - W + 1): i + 1]
            if len(seg) < W:                                # causal front-pad
                seg = [seg[0]] * (W - len(seg)) + seg
            rows.append(seg)
        return np.asarray(rows, float)

    def fit(self, X: Matrix, y: Labels) -> "AEAnomalyNode":
        t0 = time.time()
        wins = self._windows(X)
        self._mu = wins.mean(axis=0)
        self._sd = wins.std(axis=0) + 1e-8
        Z = (wins - self._mu) / self._sd
        try:
            import torch
            import torch.nn as nn
            torch.manual_seed(0)
            W = self.W
            net = nn.Sequential(
                nn.Linear(W, self.hidden), nn.ReLU(),
                nn.Linear(self.hidden, W),
            )
            opt = torch.optim.Adam(net.parameters(), lr=1e-2)
            lossf = nn.MSELoss()
            t = torch.tensor(Z, dtype=torch.float32)
            net.train()
            for _ in range(self.epochs):
                opt.zero_grad()
                loss = lossf(net(t), t)
                loss.backward()
                opt.step()
            net.eval()
            self._net = net
        except Exception:                                  # numpy fallback
            self._net = None
            self.fell_back = True
        self.fit_seconds = time.time() - t0
        return super().fit(X, y)

    def _recon_error(self, X: Matrix) -> np.ndarray:
        wins = self._windows(X)
        Z = (wins - self._mu) / self._sd
        if self._net is None:                               # deviation-from-mean
            return ((Z - Z.mean(axis=1, keepdims=True)) ** 2).mean(axis=1)
        import torch
        with torch.no_grad():
            t = torch.tensor(Z, dtype=torch.float32)
            rec = self._net(t).numpy()
        return ((Z - rec) ** 2).mean(axis=1)

    def _augment(self, X: Matrix) -> np.ndarray:
        base = np.asarray([[float(v) for v in row] for row in X], float)
        err = self._recon_error(X).reshape(-1, 1)
        return np.hstack([base, err])


# --------------------------------------------------------------------------- #
#  Factories
# --------------------------------------------------------------------------- #
def nhits_node(name="nhits"): return NHiTSNode(name)
def tcn_node(name="tcn"): return TCNNode(name)
def nbeats_node(name="nbeats"): return NBEATSNode(name)
def tsmixer_node(name="tsmixer"): return TSMixerNode(name)
def gru_node(name="gru"): return GRUNode(name)
def ae_anomaly_node(name="ae_anomaly"): return AEAnomalyNode(name)
