"""Remaining catalog ADDs (the MED/LOW-priority nodes skipped in passes 1–4).

Reuse-first, NodeProtocol-conformant, self-guarding imports, CPU-first. Completes the
node-shaped ADDs from research/model-catalog-22parts.md.

  B  TiDENode / TimesNetNode /   — more Nixtla neuralforecast forecasters (Crossformer is
     TimeMixerNode                 absent in this NF build; substituted TimesNet/TimeMixer)
  G  MambaNode                   — selective state-space sequence model (mambapy, CPU)
  C  NormFlowNode                — nflows normalizing-flow return-density feature
     BayesianTorchNode           — Bayesian NN (variational) w/ predictive-uncertainty feature
  E  LiNGAMNode                  — DirectLiNGAM linear non-Gaussian causal ordering → ancestor selection
"""
from __future__ import annotations

import warnings

import numpy as np

from core.node_protocol import IOSchema, Labels, Matrix, Vector
from nodes.quant_nodes import _HeadBase
from nodes.foundation_nodes import _NFForecastBase


# =========================================================================== #
#  GROUP B — additional neuralforecast forecasters
# =========================================================================== #
class TiDENode(_NFForecastBase):
    """TiDE — efficient MLP encoder-decoder, a strong cheap long-horizon baseline."""

    def __init__(self, name="tide", col=0):
        super().__init__(name, "Nixtla TiDE MLP encoder-decoder forecaster (CPU-tiny).", col)

    def _make_model(self):
        from neuralforecast.models import TiDE
        return TiDE(h=1, input_size=self.INPUT, max_steps=self.MAX_STEPS,
                    scaler_type="robust", enable_progress_bar=False,
                    accelerator="cpu", logger=False)


class TimesNetNode(_NFForecastBase):
    """TimesNet — 2D temporal-variation forecaster (period-folded convolutions)."""

    def __init__(self, name="timesnet", col=0):
        super().__init__(name, "Nixtla TimesNet 2D temporal-variation forecaster (CPU-tiny).", col)

    def _make_model(self):
        from neuralforecast.models import TimesNet
        return TimesNet(h=1, input_size=self.INPUT, max_steps=self.MAX_STEPS,
                        scaler_type="robust", enable_progress_bar=False,
                        accelerator="cpu", logger=False)


class TimeMixerNode(_NFForecastBase):
    """TimeMixer — multiscale MLP-mixer forecaster."""

    def __init__(self, name="timemixer", col=0):
        super().__init__(name, "Nixtla TimeMixer multiscale MLP-mixer forecaster (CPU-tiny).", col)

    def _make_model(self):
        from neuralforecast.models import TimeMixer
        return TimeMixer(h=1, input_size=self.INPUT, n_series=1, max_steps=self.MAX_STEPS,
                         scaler_type="robust", enable_progress_bar=False,
                         accelerator="cpu", logger=False)


# =========================================================================== #
#  GROUP G — Mamba selective state-space model
# =========================================================================== #
class MambaNode(_HeadBase):
    """mambapy Mamba selective state-space sequence model — linear-time long-context
    encoder. Encodes the trailing window; final state feeds the task-aware readout."""

    kind = "deep_learning"
    DMODEL = 16
    EPOCHS = 20
    W = 16

    def __init__(self, name="mamba", col=0):
        super().__init__(name, "mambapy selective state-space sequence model (CPU).", col)
        self._model = None

    def _windows(self, A):
        n, d = A.shape
        seqs = np.zeros((n, self.W, d), float)
        for i in range(n):
            w = A[max(0, i - self.W + 1): i + 1]
            seqs[i, self.W - len(w):] = w
        return seqs

    def fit(self, X: Matrix, y: Labels) -> "MambaNode":
        import torch
        import torch.nn as nn
        from mambapy.mamba import Mamba, MambaConfig
        A = np.asarray([[float(v) for v in r] for r in X], float)
        A[~np.isfinite(A)] = 0.0
        self._mu, self._sd = A.mean(0), A.std(0) + 1e-9
        A = (A - self._mu) / self._sd
        ya = np.asarray(y, float).reshape(-1)
        self._ymu, self._ysd = float(ya.mean()), float(ya.std()) + 1e-9
        d = A.shape[1]
        try:
            cfg = MambaConfig(d_model=self.DMODEL, n_layers=2)

            class _Net(nn.Module):
                def __init__(s):
                    super().__init__()
                    s.emb = nn.Linear(d, MambaNode.DMODEL)
                    s.mamba = Mamba(cfg)
                    s.head = nn.Linear(MambaNode.DMODEL, 1)

                def forward(s, x):
                    h = s.mamba(s.emb(x))
                    return s.head(h[:, -1])

            self._model = _Net()
            xt = torch.tensor(self._windows(A), dtype=torch.float32)
            yt = torch.tensor(((ya - self._ymu) / self._ysd).reshape(-1, 1), dtype=torch.float32)
            opt = torch.optim.Adam(self._model.parameters(), lr=0.02)
            lossf = nn.MSELoss()
            self._model.train()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                for _ in range(self.EPOCHS):
                    opt.zero_grad(); loss = lossf(self._model(xt), yt); loss.backward(); opt.step()
            self._model.eval()
        except Exception:
            self._model = None
        return super().fit(X, y)

    def _augment(self, X: Matrix) -> np.ndarray:
        import torch
        base = np.asarray([[float(v) for v in r] for r in X], float)
        if self._model is None:
            return base
        A = (np.nan_to_num(base) - self._mu) / self._sd
        with torch.no_grad():
            v = self._model(torch.tensor(self._windows(A), dtype=torch.float32)).numpy().reshape(-1)
        return np.hstack([base, (v * self._ysd + self._ymu).reshape(-1, 1)])


# =========================================================================== #
#  GROUP C — normalizing-flow density + Bayesian-NN uncertainty
# =========================================================================== #
class NormFlowNode(_HeadBase):
    """nflows normalizing-flow density model of the target-return distribution. The
    per-row log-density (a novelty / tail signal) is appended to the readout."""

    kind = "probabilistic"
    EPOCHS = 150

    def __init__(self, name="normflow", col=0):
        super().__init__(name, "nflows normalizing-flow return-density (log-prob feature).", col)
        self._flow = None

    def fit(self, X: Matrix, y: Labels) -> "NormFlowNode":
        import torch
        from nflows.flows.base import Flow
        from nflows.distributions.normal import StandardNormal
        from nflows.transforms.base import CompositeTransform
        from nflows.transforms.autoregressive import MaskedAffineAutoregressiveTransform
        from nflows.transforms.permutations import ReversePermutation
        feats = np.asarray([[float(v) for v in r] for r in X], float)
        feats[~np.isfinite(feats)] = 0.0
        self._mu, self._sd = feats.mean(0), feats.std(0) + 1e-9
        dim = feats.shape[1]
        try:
            transforms = []
            for _ in range(3):
                transforms.append(ReversePermutation(features=dim))
                transforms.append(MaskedAffineAutoregressiveTransform(features=dim, hidden_features=16))
            self._flow = Flow(CompositeTransform(transforms), StandardNormal([dim]))
            xt = torch.tensor((feats - self._mu) / self._sd, dtype=torch.float32)
            opt = torch.optim.Adam(self._flow.parameters(), lr=0.01)
            self._flow.train()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                for _ in range(self.EPOCHS):
                    opt.zero_grad(); loss = -self._flow.log_prob(xt).mean(); loss.backward(); opt.step()
            self._flow.eval()
        except Exception:
            self._flow = None
        return super().fit(X, y)

    def _augment(self, X: Matrix) -> np.ndarray:
        import torch
        base = np.asarray([[float(v) for v in r] for r in X], float)
        if self._flow is None:
            return base
        xt = torch.tensor((np.nan_to_num(base) - self._mu) / self._sd, dtype=torch.float32)
        with torch.no_grad():
            lp = self._flow.log_prob(xt).numpy().reshape(-1, 1)
        lp[~np.isfinite(lp)] = 0.0
        return np.hstack([base, lp])


class BayesianTorchNode(_HeadBase):
    """bayesian-torch variational Bayesian MLP. Trains a reparameterized net and appends
    the predictive MEAN and STD (epistemic uncertainty) as features — the calibrated-
    confidence signal Laplace would give (laplace-torch is env-broken here)."""

    kind = "probabilistic"
    HID = 24
    EPOCHS = 60
    MC = 10

    def __init__(self, name="bayesian_nn", col=0):
        super().__init__(name, "bayesian-torch variational NN (predictive mean + uncertainty).", col)
        self._model = None

    def fit(self, X: Matrix, y: Labels) -> "BayesianTorchNode":
        import torch
        import torch.nn as nn
        from bayesian_torch.layers import LinearReparameterization
        A = np.asarray([[float(v) for v in r] for r in X], float)
        A[~np.isfinite(A)] = 0.0
        self._mu, self._sd = A.mean(0), A.std(0) + 1e-9
        A = (A - self._mu) / self._sd
        ya = np.asarray(y, float).reshape(-1)
        self._ymu, self._ysd = float(ya.mean()), float(ya.std()) + 1e-9
        d = A.shape[1]
        try:
            class _BNN(nn.Module):
                def __init__(s):
                    super().__init__()
                    s.l1 = LinearReparameterization(d, BayesianTorchNode.HID)
                    s.l2 = LinearReparameterization(BayesianTorchNode.HID, 1)

                def forward(s, x):
                    h, k1 = s.l1(x)
                    h = torch.relu(h)
                    o, k2 = s.l2(h)
                    return o, (k1 + k2)

            self._model = _BNN()
            xt = torch.tensor(A, dtype=torch.float32)
            yt = torch.tensor(((ya - self._ymu) / self._ysd).reshape(-1, 1), dtype=torch.float32)
            opt = torch.optim.Adam(self._model.parameters(), lr=0.02)
            self._model.train()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                for _ in range(self.EPOCHS):
                    opt.zero_grad()
                    out, kl = self._model(xt)
                    loss = ((out - yt) ** 2).mean() + 1e-3 * kl / len(xt)
                    loss.backward(); opt.step()
            self._model.eval()
        except Exception:
            self._model = None
        return super().fit(X, y)

    def _augment(self, X: Matrix) -> np.ndarray:
        import torch
        base = np.asarray([[float(v) for v in r] for r in X], float)
        if self._model is None:
            return base
        A = (np.nan_to_num(base) - self._mu) / self._sd
        xt = torch.tensor(A, dtype=torch.float32)
        preds = []
        with torch.no_grad():
            for _ in range(self.MC):                          # MC sampling over weight posterior
                out, _ = self._model(xt)
                preds.append(out.numpy().reshape(-1))
        P = np.stack(preds)
        mean = P.mean(0) * self._ysd + self._ymu
        std = P.std(0) * self._ysd
        return np.hstack([base, mean.reshape(-1, 1), std.reshape(-1, 1)])


# =========================================================================== #
#  GROUP E — DirectLiNGAM linear non-Gaussian causal ordering
# =========================================================================== #
class LiNGAMNode(_HeadBase):
    """DirectLiNGAM (lingam) recovers a linear non-Gaussian causal order over the features
    + target; keeps only features that are causal ANCESTORS of the target and reads out on
    them (complements Tigramite's PCMCI+ with a non-Gaussian structural view)."""

    kind = "causal"
    MAXF = 12

    def __init__(self, name="lingam", col=0):
        super().__init__(name, "DirectLiNGAM causal-ancestor feature selection.", col)
        self._sel = None

    def fit(self, X: Matrix, y: Labels) -> "LiNGAMNode":
        try:
            from lingam import DirectLiNGAM
            A = np.asarray([[float(v) for v in r] for r in X], float)
            A[~np.isfinite(A)] = 0.0
            cols = list(range(min(self.MAXF, A.shape[1])))
            data = np.column_stack([A[:, cols], np.asarray(y, float).reshape(-1)])
            tgt = data.shape[1] - 1
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = DirectLiNGAM()
                model.fit(data)
            B = np.asarray(model.adjacency_matrix_, float)     # B[i,j]: j -> i
            # features with a nonzero causal path coefficient into target
            sel = [j for j in cols if abs(B[tgt, j]) > 1e-6]
            self._sel = sel or cols[: max(1, len(cols) // 2)]
        except Exception:
            self._sel = list(range(len(X[0])))
        return super().fit(X, y)

    def _augment(self, X: Matrix) -> np.ndarray:
        A = np.asarray([[float(v) for v in r] for r in X], float)
        A[~np.isfinite(A)] = 0.0
        sel = [j for j in (self._sel or []) if j < A.shape[1]] or [0]
        return A[:, sel]
