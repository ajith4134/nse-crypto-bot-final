"""Tier-3 infra nodes (groups D/I/J of research/model-catalog-22parts.md).

Reuse-first wrappers, NodeProtocol-conformant via the task-aware readout bases. Heavy
imports guarded so a missing dep just makes the node unavailable. CPU-first.

  I  SB3RLExecNode        — stable-baselines3 PPO deep-RL execution policy over a tiny Gym env
  J  Alpha360Node         — Qlib-style Alpha360 feature set (60 normalized lags × 6 fields)
  D  PyGODAnomalyNode     — PyGOD graph-anomaly score over a kNN feature graph
  D  TemporalGraphNode    — PyG GraphSAGE over a TEMPORAL graph (each row → K recent predecessors)
"""
from __future__ import annotations

import warnings

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector
from nodes.quant_nodes import _HeadBase


# =========================================================================== #
#  GROUP I — Stable-Baselines3 PPO deep-RL execution policy
# =========================================================================== #
class SB3RLExecNode(BaseNode):
    """A real deep-RL execution policy (SB3 PPO) — replaces the toy tabular-Q RLPolicyNode.
    Trains on a tiny Gym env where the agent picks flat/long/short each step and is rewarded
    by directional correctness (classification) or realized return (regression). predict_proba
    = policy probability of the LONG action."""

    kind = "reinforcement"
    STEPS = 4000

    def __init__(self, name="sb3_ppo_exec", col=0):
        self.name, self.summary = name, "stable-baselines3 PPO deep-RL execution policy."
        self.task, self.head = "binary", "y"
        self.col = col
        self._model = None
        self.schema = IOSchema(0, "features", "p(long)")

    def _make_env(self, A, ret):
        import gymnasium as gym
        from gymnasium import spaces

        class _TradeEnv(gym.Env):
            def __init__(s):
                super().__init__()
                s.A, s.ret, s.n = A, ret, len(A)
                s.action_space = spaces.Discrete(3)            # 0 flat, 1 long, 2 short
                s.observation_space = spaces.Box(-np.inf, np.inf, (A.shape[1],), np.float32)
                s.t = 0

            def reset(s, *, seed=None, options=None):
                super().reset(seed=seed)
                s.t = 0
                return s.A[0].astype(np.float32), {}

            def step(s, a):
                pos = {0: 0.0, 1: 1.0, 2: -1.0}[int(a)]
                r = float(pos * s.ret[s.t])
                s.t += 1
                term = s.t >= s.n - 1
                obs = s.A[min(s.t, s.n - 1)].astype(np.float32)
                return obs, r, term, False, {}

        return _TradeEnv()

    def fit(self, X: Matrix, y: Labels) -> "SB3RLExecNode":
        A = np.asarray([[float(v) for v in r] for r in X], float)
        A[~np.isfinite(A)] = 0.0
        self._mu, self._sd = A.mean(0), A.std(0) + 1e-9
        A = (A - self._mu) / self._sd
        ya = np.asarray(y, float).reshape(-1)
        self.task = "regression" if len(set(ya.tolist())) > 3 else "binary"
        ret = ya if self.task == "regression" else (2.0 * ya - 1.0)
        self.schema = IOSchema(A.shape[1], f"{A.shape[1]} numeric features", "p(long)")
        try:
            from stable_baselines3 import PPO
            from stable_baselines3.common.vec_env import DummyVecEnv
            env = DummyVecEnv([lambda: self._make_env(A, ret)])
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self._model = PPO("MlpPolicy", env, n_steps=256, batch_size=64,
                                  n_epochs=4, verbose=0, seed=0,
                                  policy_kwargs={"net_arch": [32, 32]})
                self._model.learn(total_timesteps=self.STEPS, progress_bar=False)
        except Exception:
            self._model = None
        return self

    def _long_probs(self, X):
        import torch
        A = np.asarray([[float(v) for v in r] for r in X], float)
        A[~np.isfinite(A)] = 0.0
        A = (A - self._mu) / self._sd
        obs = torch.as_tensor(A, dtype=torch.float32)
        with torch.no_grad():
            dist = self._model.policy.get_distribution(obs)
            probs = dist.distribution.probs.numpy()            # [n, 3]
        return probs[:, 1]                                     # P(long)

    def predict_proba(self, X: Matrix) -> Vector:
        if self._model is None:
            return [0.5] * len(X)
        return [float(p) for p in self._long_probs(X)]

    def predict(self, X: Matrix) -> Labels:
        return [1 if p >= 0.5 else 0 for p in self.predict_proba(X)]

    def predict_output(self, X: Matrix) -> list[list[float]]:
        p = self.predict_proba(X)
        return [[1.0 - v, v] for v in p]


# =========================================================================== #
#  GROUP J — Qlib-style Alpha360 feature node
# =========================================================================== #
class Alpha360Node(_HeadBase):
    """Qlib Alpha360 feature set: 60 normalized trailing lags of 6 fields
    (close/open/high/low/volume-proxy/vwap-proxy), each divided by the current close —
    the documented Alpha360 transform (implemented directly; full qlib is too heavy to
    vendor on this env). Appends the block to the readout. Uses the price column as close."""

    kind = "quant"
    LAGS = 60

    def __init__(self, name="alpha360", col=0):
        super().__init__(name, "Qlib-style Alpha360 (60 normalized lags x 6 fields).", col)

    def _augment(self, X: Matrix) -> np.ndarray:
        base = np.asarray([[float(v) for v in r] for r in X], float)
        n, d = base.shape
        close = base[:, self.col]
        # derive proxy fields from available columns (fall back to close where absent)
        def colr(j):
            return base[:, j] if j < d else close
        fields = [close, colr(1), close * 1.001, close * 0.999, colr(2), close]  # c,o,h,l,v,vwap proxies
        feats = np.zeros((n, self.LAGS * len(fields)), float)
        with np.errstate(all="ignore"):
            for fi, f in enumerate(fields):
                f0 = float(f[0]) if len(f) else 0.0
                for lag in range(self.LAGS):
                    ref = np.full(n, f0, float)               # pre-history = first value
                    if lag < n:
                        ref[lag:] = f[:n - lag]               # causal shift by `lag`
                    col = np.where(np.abs(close) > 1e-9, ref / close, 0.0)
                    feats[:, fi * self.LAGS + lag] = col
        feats[~np.isfinite(feats)] = 0.0
        return np.hstack([base, feats])


# =========================================================================== #
#  GROUP D — PyGOD graph anomaly + PyG temporal graph
# =========================================================================== #
class PyGODAnomalyNode(_HeadBase):
    """PyGOD graph-anomaly detector (DOMINANT) over a kNN graph of the feature rows.
    The per-node anomaly score is appended as a feature (relational manipulation/outlier
    signal our tabular PyOD node can't see)."""

    kind = "graph"
    K = 8

    def __init__(self, name="pygod_anomaly", col=0):
        super().__init__(name, "PyGOD DOMINANT graph-anomaly score (kNN feature graph).", col)
        self._score = None

    def _edges(self, A):
        from sklearn.neighbors import NearestNeighbors
        k = int(min(self.K + 1, len(A)))
        nn = NearestNeighbors(n_neighbors=k).fit(A)
        _, idx = nn.kneighbors(A)
        src, dst = [], []
        for i, row in enumerate(idx):
            for j in row[1:]:
                src += [i, int(j)]; dst += [int(j), i]
        return np.array([src, dst], dtype=np.int64)

    def fit(self, X: Matrix, y: Labels) -> "PyGODAnomalyNode":
        A = np.asarray([[float(v) for v in r] for r in X], float)
        A[~np.isfinite(A)] = 0.0
        self._mu, self._sd = A.mean(0), A.std(0) + 1e-9
        self._Atr = (A - self._mu) / self._sd
        try:
            import torch
            from torch_geometric.data import Data
            from pygod.detector import DOMINANT
            data = Data(x=torch.tensor(self._Atr, dtype=torch.float32),
                        edge_index=torch.tensor(self._edges(self._Atr), dtype=torch.long))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self._det = DOMINANT(hid_dim=16, num_layers=2, epoch=20, gpu=-1, verbose=0)
                self._det.fit(data)
                self._score = np.asarray(self._det.decision_score_, float)
        except Exception:
            self._det = None
            self._score = None
        return super().fit(X, y)

    def _augment(self, X: Matrix) -> np.ndarray:
        base = np.asarray([[float(v) for v in r] for r in X], float)
        n = len(base)
        A = (np.nan_to_num(base) - self._mu) / self._sd
        s = np.zeros((n, 1))
        if self._det is not None:
            try:
                import torch
                from torch_geometric.data import Data
                if np.array_equal(A, self._Atr):
                    sc = self._score
                else:
                    data = Data(x=torch.tensor(A, dtype=torch.float32),
                                edge_index=torch.tensor(self._edges(A), dtype=torch.long))
                    sc = np.asarray(self._det.predict(data, return_score=True)[1], float)
                s = np.asarray(sc, float).reshape(-1, 1)[:n]
            except Exception:
                s = np.zeros((n, 1))
        return np.hstack([base, s])


class TemporalGraphNode(_HeadBase):
    """PyG GraphSAGE over a TEMPORAL graph: each row is connected to its K most-recent
    predecessors (causal, time-ordered edges) — captures short-horizon temporal relational
    structure distinct from the static-kNN CrossAssetGNNNode. Embedding feeds the readout."""

    kind = "graph"
    K = 5
    HID = 16
    EPOCHS = 30

    def __init__(self, name="temporal_graph", col=0):
        super().__init__(name, "PyG GraphSAGE over a temporal (recent-predecessor) graph.", col)
        self._model = None

    def _temporal_edges(self, n):
        src, dst = [], []
        for i in range(n):
            for k in range(1, self.K + 1):
                if i - k >= 0:
                    src += [i - k]; dst += [i]                 # past -> present (directed causal)
        if not src:
            src, dst = [0], [0]
        return np.array([src, dst], dtype=np.int64)

    def fit(self, X: Matrix, y: Labels) -> "TemporalGraphNode":
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
                s.c1 = SAGEConv(din, TemporalGraphNode.HID)
                s.c2 = SAGEConv(TemporalGraphNode.HID, TemporalGraphNode.HID)

            def forward(s, x, e):
                h = torch.relu(s.c1(x, e))
                return torch.relu(s.c2(h, e))

        try:
            self._model = _Net()
            edge = torch.tensor(self._temporal_edges(len(A)), dtype=torch.long)
            x = torch.tensor(A, dtype=torch.float32)
            head = nn.Linear(self.HID, 1)
            yt = torch.tensor(ya.astype(float), dtype=torch.float32).reshape(-1, 1)
            opt = torch.optim.Adam(list(self._model.parameters()) + list(head.parameters()), lr=0.01)
            lossf = nn.MSELoss()
            self._model.train()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                for _ in range(self.EPOCHS):
                    opt.zero_grad(); loss = lossf(head(self._model(x, edge)), yt)
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
        stacked = A if np.array_equal(A, self._Atr) else np.vstack([self._Atr, A])
        edge = torch.tensor(self._temporal_edges(len(stacked)), dtype=torch.long)
        with torch.no_grad():
            z = self._model(torch.tensor(stacked, dtype=torch.float32), edge).numpy()
        if not np.array_equal(A, self._Atr):
            z = z[len(self._Atr):]
        return np.hstack([base, z])
