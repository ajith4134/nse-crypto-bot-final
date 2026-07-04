"""AI-scientist idea #10 — Intermarket Graph Neural Net (PyG).

Models cross-asset lead-lag / contagion as a GRAPH and message-passes over it. The feature bus is
already an intermarket vector (NSE + crypto + macro signals side by side), so we learn the
relationship graph over the FEATURES: nodes = features, edges = strong |correlation| pairs
(kNN-per-node from the training data). A GCN then lets each feature's representation absorb its
correlated neighbours (the contagion/lead-lag structure) before a graph-level readout → logistic
head predicts the target.

Uses PyTorch-Geometric (``torch_geometric.nn.GCNConv``) — reuse-first, the library the idea named.
Graceful degradation: if torch/PyG is absent it falls back to a plain logistic on the raw features
(still a valid NodeProtocol node). CPU-sized by default.
"""
from __future__ import annotations

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector

try:
    import torch
    import torch.nn as nn
    from torch_geometric.data import Batch, Data
    from torch_geometric.nn import GCNConv, global_mean_pool
    _HAS_PYG = True
except Exception:
    _HAS_PYG = False


def _knn_edges(corr: np.ndarray, k: int) -> np.ndarray:
    """Directed kNN edges per node from a |correlation| matrix → edge_index (2, E)."""
    d = corr.shape[0]
    src, dst = [], []
    for i in range(d):
        order = np.argsort(-corr[i])            # strongest correlation first
        nbrs = [j for j in order if j != i][:k]
        for j in nbrs:
            src.append(i); dst.append(j)
            src.append(j); dst.append(i)        # undirected
    if not src:                                 # d==1 edge case
        src, dst = [0], [0]
    return np.asarray([src, dst], dtype=np.int64)


if _HAS_PYG:
    class _GCN(nn.Module):
        def __init__(self, num_nodes: int, hidden: int, layers: int = 2):
            super().__init__()
            self.embed = nn.Linear(1, hidden)             # scalar node signal → hidden
            # per-feature IDENTITY embedding — lets the GNN tell feature-node i from j (without it,
            # equal values on different features are indistinguishable and mean-pool erases the graph)
            self.id_emb = nn.Embedding(num_nodes, hidden)
            self.convs = nn.ModuleList([GCNConv(hidden, hidden) for _ in range(layers)])
            self.head = nn.Sequential(nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, 1))

        def forward(self, x, edge_index, batch, node_id):
            h = torch.relu(self.embed(x) + self.id_emb(node_id))
            for conv in self.convs:
                h = torch.relu(conv(h, edge_index))
            g = global_mean_pool(h, batch)                # graph-level readout
            return self.head(g).squeeze(-1)               # (num_graphs,)


class IntermarketGNNNode(BaseNode):
    """GCN over the learned cross-feature relationship graph → p(class=1)."""

    kind = "intermarket_gnn"

    def __init__(self, name: str = "intermarket_gnn", hidden: int = 16, layers: int = 2,
                 k: int = 3, epochs: int = 60, max_rows: int = 1500):
        self.name = name
        self.summary = ("Intermarket GNN (PyG GCN): message-passes over the learned cross-feature "
                        "lead-lag/contagion graph before predicting.")
        self.hidden = int(hidden)
        self.layers = int(layers)
        self.k = int(k)
        self.epochs = int(epochs)
        self.max_rows = int(max_rows)
        self.task = "binary"
        self.head = "y"
        self.schema = IOSchema(0, "intermarket feature rows", "p(class=1)")
        self._net = None
        self._edge_index = None
        self._mean = None
        self._std = None
        self._clf = None
        self.fell_back = False

    def _z(self, A):
        return (A - self._mean) / self._std

    def _batch(self, Az: np.ndarray):
        """Build a PyG Batch: one graph per row, shared topology, node signal = feature values,
        plus a per-node identity index so the GNN can distinguish the features."""
        ei = torch.as_tensor(self._edge_index, dtype=torch.long)
        nid = torch.arange(Az.shape[1], dtype=torch.long)
        data = [Data(x=torch.as_tensor(row.reshape(-1, 1), dtype=torch.float32),
                     edge_index=ei, node_id=nid) for row in Az]
        return Batch.from_data_list(data)

    def fit(self, X: Matrix, y: Labels) -> "IntermarketGNNNode":
        A = np.asarray(X, dtype=np.float32)
        ya = np.asarray(y).astype(int)
        self.schema = IOSchema(A.shape[1], f"{A.shape[1]} intermarket features", "p(class=1)")
        self._mean = A.mean(0); self._std = A.std(0) + 1e-8
        if len(A) > self.max_rows:                              # cap for CPU training
            idx = np.random.default_rng(0).permutation(len(A))[: self.max_rows]; idx.sort()
            A, ya = A[idx], ya[idx]
        Az = self._z(A)

        if not _HAS_PYG or len(set(ya.tolist())) < 2 or A.shape[1] < 2:
            from sklearn.linear_model import LogisticRegression
            self.fell_back = True
            self._clf = LogisticRegression(max_iter=500).fit(Az, ya) if len(set(ya.tolist())) >= 2 else None
            return self

        # learn the intermarket graph: |corr| between features on the train data
        corr = np.abs(np.corrcoef(Az, rowvar=False))
        corr = np.nan_to_num(corr)
        self._edge_index = _knn_edges(corr, min(self.k, A.shape[1] - 1))

        torch.manual_seed(0)
        self._net = _GCN(A.shape[1], self.hidden, self.layers)
        opt = torch.optim.Adam(self._net.parameters(), lr=5e-3)
        batch = self._batch(Az)
        yt = torch.as_tensor(ya, dtype=torch.float32)
        lossf = nn.BCEWithLogitsLoss()
        self._net.train()
        for _ in range(self.epochs):
            opt.zero_grad()
            logits = self._net(batch.x, batch.edge_index, batch.batch, batch.node_id)
            lossf(logits, yt).backward()
            opt.step()
        self._net.eval()
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        A = np.asarray(X, dtype=np.float32)
        Az = self._z(A)
        if self.fell_back or self._net is None:
            if self._clf is None:
                return [0.5] * len(A)
            return self._clf.predict_proba(Az)[:, 1].tolist()
        with torch.no_grad():
            b = self._batch(Az)
            p = torch.sigmoid(self._net(b.x, b.edge_index, b.batch, b.node_id)).cpu().numpy()
        return p.tolist()

    def predict(self, X: Matrix) -> Labels:
        return [1 if p >= 0.5 else 0 for p in self.predict_proba(X)]


def intermarket_gnn_node(name: str = "intermarket_gnn") -> IntermarketGNNNode:
    """Zero-arg factory (pool + autoload convention)."""
    return IntermarketGNNNode(name=name)
