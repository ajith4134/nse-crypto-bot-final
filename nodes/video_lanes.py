"""Video framework lanes — faithful implementations, every one a neuron.

CORTEX B2 (research/ultra-network-design.md §2, cortex-stitch-map rows 7-10/12/15):
* build_windows      — shared sliding-window tensor builder, np.moveaxis pattern
                       with mandatory shape verification (CANON-10; LSTM-10/11,
                       TFM-14..16).
* TCNProbNode        — pytorch-tcn causal TCN over a 64-bar window -> last-step
                       Linear -> sigmoid next-bar up-probability, BCE/Adam,
                       streaming-capable (CANON-19/27; JKA-04/05/06).
* EncoderTransformerNode — the exact TFM custom module: Linear(F->64) +
                       learnable pos-emb + nn.TransformerEncoder(2L/8H/FF256/
                       dropout .1/relu) + last-step pool + Linear(64->1),
                       MSE/Adam(1e-3), lookback 30 (CANON-18; TFM-18..27).
* LSTMLaneNode       — nn.LSTM(F,150)+Linear(150,1) Keras twin, MSE/Adam,
                       backcandles 30 (CANON-17; LSTM-13/14).
* SkMLPLaneNode / TorchMLPLaneNode — sklearn MLPClassifier video-faithful lane
                       (relu, max_iter=1000, random_state=100; PNP topologies)
                       + a small torch MLP twin (CANON-16).
* DLinearNode        — vendored trivial DLinear (moving-average decomposition +
                       two Linears) as the honesty floor (CANON-36 floor).

Discipline shared by all lanes: chronological order assumed (no shuffled
splits, CANON-30); scalers are fit ONLY on the data passed to fit() — i.e. the
TRAIN slice (CANON-08, fixing the videos' own full-data leak); torch runs on
CPU with small default epochs. Nothing registers in pool.py here (B8 wires
pools).
"""
from __future__ import annotations

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector


# --------------------------------------------------------------------------- #
#  Shared window builder (CANON-10) — the videos' np.moveaxis pattern
# --------------------------------------------------------------------------- #
def build_windows(X_2d, lookback: int, target_col: int | None = None,
                  horizon: int = 1):
    """Sliding-window supervised tensor builder.

    X_2d (rows, F) chronological -> X3d (N, lookback, F) where window i covers
    rows [i, i+lookback) ; y[i] = X_2d[i+lookback+horizon-1, target_col]
    (None target -> y is None). N = rows - lookback - horizon + 1.

    Built with the LSTM-10 per-feature-list + np.moveaxis pattern, then shape
    verification is MANDATORY (LSTM-11: "if you feed the model with the wrong
    dimensions it's not going to work").
    """
    A = np.asarray(X_2d, float)
    assert A.ndim == 2, f"X_2d must be 2-D, got shape {A.shape}"
    rows, F = A.shape
    lookback, horizon = int(lookback), int(horizon)
    assert lookback >= 1 and horizon >= 1
    n = rows - lookback - horizon + 1
    assert n >= 1, f"need > lookback+horizon-1 rows, got {rows}"
    X = []                                                    # video pattern:
    for j in range(F):                                        # per-feature list
        X.append([A[i - lookback:i, j] for i in range(lookback, lookback + n)])
    X = np.moveaxis(np.asarray(X), [0], [2])                  # F axis 0 -> 2
    assert X.shape == (n, lookback, F), \
        f"window tensor {X.shape} != {(n, lookback, F)}"      # CANON-10 verify
    y = None
    if target_col is not None:
        y = A[lookback + horizon - 1: lookback + horizon - 1 + n,
              int(target_col)].copy()
        assert y.shape == (n,), f"y shape {y.shape} != ({n},)"
    return X, y


# --------------------------------------------------------------------------- #
#  Shared lane base: train-only scaling + per-row window padding
# --------------------------------------------------------------------------- #
class _LaneBase(BaseNode):
    """Common machinery: standardize with stats from fit() data ONLY
    (CANON-08), and pad the row stream at the front so predict returns one
    value per input row (NodeProtocol contract)."""

    kind = "video_lane"

    def __init__(self, name: str, lookback: int):
        self.name = name
        self.lookback = int(lookback)
        self._mu = self._sd = None

    def _fit_scaler(self, A):
        self._mu = A.mean(axis=0)                             # TRAIN slice only
        self._sd = A.std(axis=0) + 1e-9

    def _scale(self, A):
        return (A - self._mu) / self._sd

    def _padded_windows(self, A):
        """One (lookback, F) window ending at every row (front rows repeat
        row 0 so early rows still get a window)."""
        pad = np.repeat(A[:1], self.lookback, axis=0)
        B = np.vstack([pad, A])
        W, _ = build_windows(B, self.lookback, target_col=None)
        return W[: len(A)]

    @staticmethod
    def _torch():
        import torch
        torch.set_num_threads(max(1, torch.get_num_threads()))
        return torch

    def _train_torch(self, model, X3d, target, loss_fn, epochs, lr,
                     batch: int = 64, seed: int = 0):
        torch = self._torch()
        torch.manual_seed(seed)
        opt = torch.optim.Adam(model.parameters(), lr=lr)
        Xt = torch.tensor(X3d, dtype=torch.float32)
        yt = torch.tensor(np.asarray(target, float).reshape(-1, 1),
                          dtype=torch.float32)
        model.train()
        for _ in range(int(epochs)):
            for s in range(0, len(Xt), batch):                # chronological
                opt.zero_grad()
                out = model(Xt[s:s + batch])
                loss = loss_fn(out, yt[s:s + batch])
                loss.backward()
                opt.step()
        model.eval()

    def _infer_torch(self, model, X3d):
        torch = self._torch()
        with torch.no_grad():
            return model(torch.tensor(X3d, dtype=torch.float32)) \
                .numpy().reshape(-1)


# --------------------------------------------------------------------------- #
#  Causal TCN probability lane (CANON-19/27; JKA spec)
# --------------------------------------------------------------------------- #
class TCNProbNode(_LaneBase):
    """pytorch-tcn causal TCN over the feature window (no future leakage) ->
    last-step Linear -> sigmoid next-bar up-probability. BCE, Adam. Default
    window 64 (JKA-04: 64-bar lookback). Streaming-capable via pytorch-tcn's
    inference buffers (predict_stream_step)."""

    summary = "causal TCN 64-bar window -> next-bar up-probability (pytorch-tcn, BCE)"

    def __init__(self, name: str = "tcn_prob", lookback: int = 64,
                 channels=(16, 16, 16), epochs: int = 5, lr: float = 1e-3):
        super().__init__(name, lookback)
        self.channels = list(int(c) for c in channels)
        self.epochs, self.lr = int(epochs), float(lr)
        self._model = None

    def _build(self, F):
        torch = self._torch()
        from pytorch_tcn import TCN

        class _TCNProb(torch.nn.Module):
            def __init__(s, channels):
                super().__init__()
                s.tcn = TCN(num_inputs=F, num_channels=channels,
                            causal=True, input_shape="NLC")   # (N, L, C) in/out
                s.head = torch.nn.Linear(channels[-1], 1)

            def forward(s, x, inference: bool = False):
                h = s.tcn(x, inference=inference)             # (N, L, ch)
                return s.head(h[:, -1, :])                    # last step logit

        return _TCNProb(self.channels)

    def fit(self, X: Matrix, y: Labels) -> "TCNProbNode":
        A = np.asarray(X, float)
        self.schema = IOSchema(A.shape[1], f"{A.shape[1]} numeric features",
                               "p(next-bar up)")
        self._fit_scaler(A)
        W = self._padded_windows(self._scale(A))
        torch = self._torch()
        self._model = self._build(A.shape[1])
        self._train_torch(self._model, W, np.asarray(y, float),
                          torch.nn.BCEWithLogitsLoss(), self.epochs, self.lr)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        A = self._scale(np.asarray(X, float))
        logits = self._infer_torch(self._model, self._padded_windows(A))
        return [float(p) for p in 1.0 / (1.0 + np.exp(-logits))]

    # ---- streaming mode (CANON-19: per-bar online inference) --------------- #
    def reset_stream(self):
        self._model.tcn.reset_buffers()

    def predict_stream_step(self, row) -> float:
        """Feed ONE new bar; pytorch-tcn's causal inference buffers carry the
        receptive-field history."""
        torch = self._torch()
        x = self._scale(np.asarray(row, float).reshape(1, -1))
        with torch.no_grad():
            logit = self._model(torch.tensor(x[None, ...], dtype=torch.float32),
                                inference=True).numpy().reshape(-1)[0]
        return float(1.0 / (1.0 + np.exp(-logit)))


# --------------------------------------------------------------------------- #
#  Encoder-only time-series Transformer (CANON-18) — the exact TFM module
# --------------------------------------------------------------------------- #
class EncoderTransformerNode(_LaneBase):
    """TFM-18..27 verbatim: feature_size->d_model Linear projection, learnable
    positional embedding (1, seq_length, d_model), nn.TransformerEncoder with
    num_layers=2 / nhead=8 / dim_feedforward=256 / dropout=0.1 / relu, last-
    timestep pooling, Linear(d_model, prediction_length). Sizing convention
    TFM-19: nhead(8) x 8 = d_model(64); FF = 4 x d_model = 256. MSE/Adam(1e-3),
    seq_length 30."""

    summary = "encoder-only TS transformer (2L/8H/d64/FF256, learnable pos-emb, last-step pool)"

    def __init__(self, name: str = "encoder_transformer", lookback: int = 30,
                 d_model: int = 64, nhead: int = 8, num_layers: int = 2,
                 dim_feedforward: int = 256, dropout: float = 0.1,
                 epochs: int = 5, lr: float = 1e-3):
        super().__init__(name, lookback)
        self.cfg = dict(d_model=d_model, nhead=nhead, num_layers=num_layers,
                        dim_feedforward=dim_feedforward, dropout=dropout)
        self.epochs, self.lr = int(epochs), float(lr)
        self._model = None

    def _build(self, F):
        torch = self._torch()
        cfg, seq_length = self.cfg, self.lookback

        # Architecture (TFM-27): input (B, L, F) -> Linear proj -> +pos-emb ->
        # TransformerEncoder -> last step -> Linear -> (B, prediction_length)
        class TimeSeriesTransformer(torch.nn.Module):
            def __init__(s, feature_size, num_layers, d_model, nhead,
                         dim_feedforward, dropout, seq_length,
                         prediction_length=1):
                super().__init__()
                s.input_fc = torch.nn.Linear(feature_size, d_model)   # TFM-22
                s.pos_embedding = torch.nn.Parameter(                 # TFM-23
                    torch.zeros(1, seq_length, d_model))
                encoder_layer = torch.nn.TransformerEncoderLayer(     # TFM-24
                    d_model=d_model, nhead=nhead,
                    dim_feedforward=dim_feedforward, dropout=dropout,
                    activation="relu", batch_first=True)
                s.encoder = torch.nn.TransformerEncoder(
                    encoder_layer, num_layers=num_layers)
                s.fc_out = torch.nn.Linear(d_model, prediction_length)  # TFM-25

            def forward(s, src):                                      # TFM-26
                x = s.input_fc(src)                    # (B, L, d_model)
                x = x + s.pos_embedding[:, : x.size(1), :]
                encoded = s.encoder(x)
                last_step = encoded[:, -1, :]          # last-step pooling
                return s.fc_out(last_step)

        return TimeSeriesTransformer(F, cfg["num_layers"], cfg["d_model"],
                                     cfg["nhead"], cfg["dim_feedforward"],
                                     cfg["dropout"], seq_length)

    def fit(self, X: Matrix, y: Labels) -> "EncoderTransformerNode":
        A = np.asarray(X, float)
        self.schema = IOSchema(A.shape[1], f"{A.shape[1]} numeric features",
                               "p(class=1)")
        self._fit_scaler(A)
        W = self._padded_windows(self._scale(A))
        torch = self._torch()
        self._model = self._build(A.shape[1])
        self._train_torch(self._model, W, np.asarray(y, float),
                          torch.nn.MSELoss(), self.epochs, self.lr)  # TFM: MSE
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        A = self._scale(np.asarray(X, float))
        out = self._infer_torch(self._model, self._padded_windows(A))
        return [float(v) for v in np.clip(out, 0.0, 1.0)]


# --------------------------------------------------------------------------- #
#  LSTM lane (CANON-17) — twin of the Keras LSTM(150) -> Dense(1) spec
# --------------------------------------------------------------------------- #
class LSTMLaneNode(_LaneBase):
    """nn.LSTM(F, 150) + Linear(150, 1), linear activation, MSE/Adam — the
    torch twin of LSTM-13/14's Keras functional model. Default backcandles=30
    (the video's better run, LSTM-18)."""

    summary = "LSTM(150)+Linear(1) Keras twin, backcandles window, MSE/Adam (CANON-17)"

    def __init__(self, name: str = "lstm_lane", backcandles: int = 30,
                 units: int = 150, epochs: int = 5, lr: float = 1e-3):
        super().__init__(name, backcandles)
        self.units = int(units)
        self.epochs, self.lr = int(epochs), float(lr)
        self._model = None

    def _build(self, F):
        torch = self._torch()

        class _LSTMLane(torch.nn.Module):
            def __init__(s, units):
                super().__init__()
                s.lstm = torch.nn.LSTM(F, units, batch_first=True)  # LSTM(150)
                s.dense = torch.nn.Linear(units, 1)                 # Dense(1)

            def forward(s, x):
                out, _ = s.lstm(x)
                return s.dense(out[:, -1, :])          # linear activation

        return _LSTMLane(self.units)

    def fit(self, X: Matrix, y: Labels) -> "LSTMLaneNode":
        A = np.asarray(X, float)
        self.schema = IOSchema(A.shape[1], f"{A.shape[1]} numeric features",
                               "p(class=1)")
        self._fit_scaler(A)
        W = self._padded_windows(self._scale(A))
        torch = self._torch()
        self._model = self._build(A.shape[1])
        self._train_torch(self._model, W, np.asarray(y, float),
                          torch.nn.MSELoss(), self.epochs, self.lr)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        A = self._scale(np.asarray(X, float))
        out = self._infer_torch(self._model, self._padded_windows(A))
        return [float(v) for v in np.clip(out, 0.0, 1.0)]


# --------------------------------------------------------------------------- #
#  MLP lanes (CANON-16) — sklearn video-faithful + torch twin
# --------------------------------------------------------------------------- #
class SkMLPLaneNode(BaseNode):
    """PNP-19 faithful: sklearn MLPClassifier(hidden_layer_sizes=cfg,
    activation='relu', max_iter=1000, random_state=100). Default topology
    (20, 20, 10, 10) — the video's first serious attempt."""

    kind = "video_lane"
    summary = "sklearn MLPClassifier video-faithful lane (relu, max_iter=1000, rs=100)"

    def __init__(self, name: str = "mlp_lane_sk",
                 hidden_layer_sizes=(20, 20, 10, 10)):
        self.name = name
        self.hidden_layer_sizes = tuple(int(h) for h in hidden_layer_sizes)
        self._clf = None
        self._mu = self._sd = None
        self._classes = [0, 1]

    def fit(self, X: Matrix, y: Labels) -> "SkMLPLaneNode":
        from sklearn.neural_network import MLPClassifier
        A = np.asarray(X, float)
        self.schema = IOSchema(A.shape[1], f"{A.shape[1]} numeric features",
                               "p(class=1)")
        self._mu = A.mean(axis=0)                             # train-only scale
        self._sd = A.std(axis=0) + 1e-9
        self._clf = MLPClassifier(hidden_layer_sizes=self.hidden_layer_sizes,
                                  activation="relu", max_iter=1000,
                                  random_state=100)
        self._clf.fit((A - self._mu) / self._sd, np.asarray(y, int))
        self._classes = list(self._clf.classes_)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        A = (np.asarray(X, float) - self._mu) / self._sd
        P = self._clf.predict_proba(A)
        if 1 not in self._classes:                            # degenerate guard
            return [0.0] * len(A)
        return [float(p) for p in P[:, self._classes.index(1)]]


class TorchMLPLaneNode(_LaneBase):
    """Small torch MLP twin of the sklearn lane (same topology, ReLU, BCE)."""

    summary = "torch MLP twin of the sklearn lane (relu stack, BCE/Adam)"

    def __init__(self, name: str = "mlp_lane_torch",
                 hidden_layer_sizes=(20, 20, 10, 10), epochs: int = 30,
                 lr: float = 1e-3):
        super().__init__(name, lookback=1)                    # no window: rows
        self.hidden_layer_sizes = tuple(int(h) for h in hidden_layer_sizes)
        self.epochs, self.lr = int(epochs), float(lr)
        self._model = None

    def _build(self, F):
        torch = self._torch()
        layers, prev = [], F
        for h in self.hidden_layer_sizes:
            layers += [torch.nn.Linear(prev, h), torch.nn.ReLU()]
            prev = h
        layers.append(torch.nn.Linear(prev, 1))
        return torch.nn.Sequential(*layers)

    def fit(self, X: Matrix, y: Labels) -> "TorchMLPLaneNode":
        A = np.asarray(X, float)
        self.schema = IOSchema(A.shape[1], f"{A.shape[1]} numeric features",
                               "p(class=1)")
        self._fit_scaler(A)
        torch = self._torch()
        self._model = self._build(A.shape[1])
        self._train_torch(self._model, self._scale(A), np.asarray(y, float),
                          torch.nn.BCEWithLogitsLoss(), self.epochs, self.lr)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        torch = self._torch()
        A = self._scale(np.asarray(X, float))
        with torch.no_grad():
            logits = self._model(torch.tensor(A, dtype=torch.float32)) \
                .numpy().reshape(-1)
        return [float(p) for p in 1.0 / (1.0 + np.exp(-logits))]


# --------------------------------------------------------------------------- #
#  DLinear honesty floor (CANON-36 floor)
# --------------------------------------------------------------------------- #
# Vendored (trivially adapted) from github.com/cure-lab/LTSF-Linear
# (models/DLinear.py, Apache-2.0): series decomposition via moving average +
# one Linear on the seasonal part + one Linear on the trend part, summed.
# "A shockingly simple baseline" — if a lane can't beat this, it earns no trust.
def _build_dlinear(seq_len: int, pred_len: int, kernel_size: int = 25):
    import torch

    class moving_avg(torch.nn.Module):
        def __init__(s, kernel_size, stride):
            super().__init__()
            s.kernel_size = kernel_size
            s.avg = torch.nn.AvgPool1d(kernel_size=kernel_size, stride=stride,
                                       padding=0)

        def forward(s, x):                                   # (B, L, C)
            front = x[:, 0:1, :].repeat(1, (s.kernel_size - 1) // 2, 1)
            end = x[:, -1:, :].repeat(1, (s.kernel_size - 1) // 2, 1)
            x = torch.cat([front, x, end], dim=1)
            return s.avg(x.permute(0, 2, 1)).permute(0, 2, 1)

    class series_decomp(torch.nn.Module):
        def __init__(s, kernel_size):
            super().__init__()
            s.moving_avg = moving_avg(kernel_size, stride=1)

        def forward(s, x):
            moving_mean = s.moving_avg(x)
            return x - moving_mean, moving_mean              # residual, trend

    class DLinear(torch.nn.Module):
        def __init__(s):
            super().__init__()
            s.decompsition = series_decomp(kernel_size)
            s.Linear_Seasonal = torch.nn.Linear(seq_len, pred_len)
            s.Linear_Trend = torch.nn.Linear(seq_len, pred_len)

        def forward(s, x):                                   # (B, L, 1)
            seasonal_init, trend_init = s.decompsition(x)
            seasonal_init = seasonal_init.permute(0, 2, 1)
            trend_init = trend_init.permute(0, 2, 1)
            out = s.Linear_Seasonal(seasonal_init) + s.Linear_Trend(trend_init)
            return out.permute(0, 2, 1)[:, :, 0]             # (B, pred_len)

    return DLinear()


class DLinearNode(_LaneBase):
    """Univariate DLinear over the target-column history — the honesty floor
    every fancy lane must beat (CANON-36). target_col picks which feature
    column is the series."""

    summary = "DLinear honesty floor (moving-avg decomposition + two Linears, LTSF-Linear)"

    def __init__(self, name: str = "dlinear_floor", lookback: int = 30,
                 pred_len: int = 1, target_col: int = 0, epochs: int = 10,
                 lr: float = 1e-3, kernel_size: int = 25):
        super().__init__(name, lookback)
        self.pred_len, self.target_col = int(pred_len), int(target_col)
        self.epochs, self.lr, self.kernel_size = int(epochs), float(lr), \
            int(kernel_size)
        self._model = None
        self.task = "regression"
        self.head = "ret"

    def fit(self, X: Matrix, y: Labels) -> "DLinearNode":
        A = np.asarray(X, float)
        self.schema = IOSchema(A.shape[1], f"{A.shape[1]} numeric features",
                               "next value (regression floor)")
        self._fit_scaler(A)
        series = self._scale(A)[:, self.target_col:self.target_col + 1]
        W = self._padded_windows(series)                     # (N, L, 1)
        torch = self._torch()
        self._model = _build_dlinear(self.lookback, self.pred_len,
                                     self.kernel_size)
        tgt = np.asarray(y, float)
        self._train_torch(self._model, W, tgt, torch.nn.MSELoss(),
                          self.epochs, self.lr)
        return self

    def _raw(self, X):
        A = np.asarray(X, float)
        series = self._scale(A)[:, self.target_col:self.target_col + 1]
        return self._infer_torch(self._model, self._padded_windows(series))

    def predict_proba(self, X: Matrix) -> Vector:
        return [float(v) for v in np.clip(self._raw(X), 0.0, 1.0)]

    def predict_output(self, X: Matrix) -> list[list[float]]:
        return [[float(v)] for v in self._raw(X)]            # regression rows

    def rollout_step(self, window_1d):
        """Predict the next value from a raw (lookback,) window — used by
        trading.rollout as the DLinear floor hook."""
        torch = self._torch()
        w = np.asarray(window_1d, float).reshape(1, -1, 1)
        assert w.shape[1] == self.lookback
        with torch.no_grad():
            return float(self._model(torch.tensor(w, dtype=torch.float32))
                         .numpy().reshape(-1)[0])


# --------------------------------------------------------------------------- #
#  Factories (pool wiring happens in B8, not here)
# --------------------------------------------------------------------------- #
def tcn_prob_node(name: str = "tcn_prob") -> TCNProbNode:
    return TCNProbNode(name)


def encoder_transformer_node(name: str = "encoder_transformer") \
        -> EncoderTransformerNode:
    return EncoderTransformerNode(name)


def lstm_lane_node(name: str = "lstm_lane") -> LSTMLaneNode:
    return LSTMLaneNode(name)


def mlp_lane_sklearn_node(name: str = "mlp_lane_sk") -> SkMLPLaneNode:
    return SkMLPLaneNode(name)


def mlp_lane_torch_node(name: str = "mlp_lane_torch") -> TorchMLPLaneNode:
    return TorchMLPLaneNode(name)


def dlinear_node(name: str = "dlinear_floor") -> DLinearNode:
    return DLinearNode(name)
