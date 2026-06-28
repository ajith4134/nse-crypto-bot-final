"""DynamicBusNode — P3.7: the DYNAMIC I/O BUS (non-fixed inputs & outputs).

Removes the "every expert must emit the head width K" constraint of the gate/cascade
(P3.5/P3.6). Each source — a model-node's output OR the raw feature vector OR a
feature-extractor's arbitrary-width vector — is mapped through its OWN trainable
projection into a shared latent width D, then a count-agnostic ATTENTION POOL
(Set-Transformer PMA with one seed query) aggregates the variable-sized, order-independent
set of projected sources into one fixed vector that a small head turns into the prediction:

    source_i (n, w_i)  ──Linear_i(w_i→D)──►  p_i (n, D) ─┐
                                                          ├─ attention-pool ─► (n, D) ─► head ─► ŷ
    raw x (n, d)       ──Linear_raw(d→D)──►  p_raw (n,D) ─┘   (presence mask + node-dropout)

Why it is "dynamic": sources of DIFFERENT widths coexist (no padding/reshaping), and
training with random source-dropout teaches the pool to predict from ANY subset — so nodes
can be added or removed at inference with no retraining (presence mask). Trained end-to-end
by real backprop (PyTorch-CPU); node outputs are detached constants (frozen experts), only
the projections + pooling query + head learn. Leakage-safe (k-fold OOF). Task-aware.

Reuse-first: OOF discipline from nodes.stacking_node; the attention pool is the Set-Transformer
PMA pattern (~implemented inline, ~40 lines); shares the project's NodeProtocol contract.
"""
from __future__ import annotations

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, NodeFactory, Vector
from nodes.gated_node import kfold_indices, standardize_fit


def _bus_module(widths, D, K, cls, seed):
    """Build the torch bus module: per-source projection + attention pool + head."""
    import torch

    class _Bus(torch.nn.Module):
        def __init__(self):
            super().__init__()
            g = torch.Generator().manual_seed(seed)
            self.proj = torch.nn.ModuleList([torch.nn.Linear(w, D) for w in widths])
            self.q = torch.nn.Parameter(torch.randn(D, generator=g) * 0.1)   # PMA seed query
            self.head = torch.nn.Linear(D, K)
            self.cls = cls

        def forward(self, mats, mask):                 # mats: list[(n,w_i)]; mask: (n,S) bool
            P = [torch.relu(self.proj[i](mats[i])) for i in range(len(mats))]
            Pstack = torch.stack(P, dim=1)             # (n, S, D)
            scores = (Pstack * self.q).sum(-1)         # (n, S)
            scores = scores.masked_fill(~mask, float("-inf"))
            a = torch.softmax(scores, dim=1)           # attention over the source SET
            pooled = (a.unsqueeze(-1) * Pstack).sum(dim=1)     # (n, D)
            return self.head(pooled), a

    return _Bus()


class DynamicBusNode(BaseNode):
    kind = "bus"
    summary = "Dynamic I/O bus: per-source projection + attention pool over heterogeneous-width sources."

    def __init__(self, node_factories: list[NodeFactory], latent_d: int = 16,
                 include_raw: bool = True, epochs: int = 300, lr: float = 0.03,
                 drop_p: float = 0.1, folds: int = 4, seed: int = 7,
                 task: str = "binary", head: str = "y", name: str = "dynamic_bus"):
        self.name = name
        self.node_factories = node_factories
        self.latent_d = latent_d
        self.include_raw = include_raw           # add the raw feature vector as a source
        self.epochs = epochs
        self.lr = lr
        self.drop_p = drop_p                     # source-dropout → robust to add/remove
        self.folds = folds
        self.seed = seed
        self.task = task
        self.head = head
        self.schema = IOSchema(0, "features", f"{task} output [dynamic-bus]")

    def _new(self, f):
        e = f()
        e.head, e.task = self.head, self.task
        return e

    def _sources(self, nodes, X_list, raw: np.ndarray) -> list[np.ndarray]:
        """One (n, w_i) matrix per source (node output, any width) + optional raw."""
        mats = [np.asarray(nd.predict_output(X_list), dtype=float) for nd in nodes]
        if self.include_raw:
            mats.append(raw)
        return mats

    def fit(self, X: Matrix, y: Labels) -> "DynamicBusNode":
        import torch
        torch.manual_seed(self.seed)
        self._cls = self.task in ("binary", "multiclass")
        Xa, ya = np.asarray(X, dtype=float), np.asarray(y)
        n, d = Xa.shape
        K = (int(ya.max()) + 1) if self._cls else 1

        # ── fit nodes; keep any that fit (NO width filter — that's the point) ──
        facs = []
        m = max(1, int(n * 0.8))
        for f in self.node_factories:
            try:
                nd = self._new(f).fit(Xa[:m].tolist(), ya[:m].tolist())
                nd.predict_output(Xa[m:m + 2].tolist())          # must produce output
                facs.append(f)
            except Exception:
                pass
        if not facs:
            raise ValueError("no usable node sources")
        self._facs = facs

        # ── OOF source matrices (leakage-safe), ragged widths allowed ──
        S = len(facs) + (1 if self.include_raw else 0)
        oof = [None] * len(facs)
        for val_idx in kfold_indices(n, self.folds):
            tr = [i for i in range(n) if i not in set(val_idx)]
            nodes = [self._new(f).fit(Xa[tr].tolist(), ya[tr].tolist()) for f in facs]
            outs = self._sources(nodes, Xa[val_idx].tolist(), Xa[val_idx])
            for si in range(len(facs)):
                if oof[si] is None:
                    oof[si] = np.zeros((n, outs[si].shape[1]), dtype=float)
                oof[si][val_idx] = outs[si]
        mats = list(oof) + ([Xa.copy()] if self.include_raw else [])

        # ── per-source standardization (store stats for inference) ──
        self._stats = [standardize_fit(mat) for mat in mats]
        mats = [(mat - mu) / sd for mat, (mu, sd) in zip(mats, self._stats)]
        widths = [mat.shape[1] for mat in mats]
        self._widths = widths

        # ── train the bus by backprop (node-dropout for dynamic robustness) ──
        self._module = _bus_module(widths, self.latent_d, K, self._cls, self.seed)
        mats_t = [torch.tensor(mt, dtype=torch.float32) for mt in mats]
        yt = (torch.tensor(ya.astype(int), dtype=torch.long) if self._cls
              else torch.tensor(ya.astype(float), dtype=torch.float32))
        opt = torch.optim.Adam(self._module.parameters(), lr=self.lr)
        rng = np.random.RandomState(self.seed)
        for _ in range(self.epochs):
            opt.zero_grad()
            mask = np.ones((n, S), dtype=bool)
            if self.drop_p > 0 and S > 1:                        # randomly drop sources
                drop = rng.rand(S) < self.drop_p
                if drop.all():
                    drop[rng.randint(S)] = False
                mask[:, drop] = False
            logits, _ = self._module(mats_t, torch.tensor(mask))
            if self._cls:
                loss = torch.nn.functional.cross_entropy(logits, yt)
            else:
                loss = torch.nn.functional.mse_loss(logits[:, 0], yt)
            loss.backward()
            opt.step()

        self._nodes = [self._new(f).fit(X, y) for f in facs]     # refit on all data
        self.source_names = [nd.name for nd in self._nodes] + (["raw"] if self.include_raw else [])
        self._K = K
        self.schema = IOSchema(d, f"{d} numeric features", f"{self.task} output [dynamic-bus]")
        return self

    def _forward(self, X: Matrix, active: set[str] | None = None):
        import torch
        raw = np.asarray(X, dtype=float)
        mats = self._sources(self._nodes, raw.tolist(), raw)
        mats = [(mt - mu) / sd for mt, (mu, sd) in zip(mats, self._stats)]
        mats_t = [torch.tensor(mt, dtype=torch.float32) for mt in mats]
        n, S = len(X), len(mats)
        mask = np.ones((n, S), dtype=bool)
        if active is not None:                                   # presence mask: drop absent sources
            for si, nm in enumerate(self.source_names):
                if nm not in active:
                    mask[:, si] = False
        with torch.no_grad():
            logits, attn = self._module(mats_t, torch.tensor(mask))
        return logits.numpy(), attn.numpy()

    def predict_output(self, X: Matrix, active: set[str] | None = None) -> list[list[float]]:
        logits, _ = self._forward(X, active)
        if self._cls:
            e = np.exp(logits - logits.max(axis=1, keepdims=True))
            return (e / e.sum(axis=1, keepdims=True)).tolist()
        return [[float(v)] for v in logits[:, 0]]

    def source_attention(self, X: Matrix) -> dict:
        """Mean attention weight per source — the learned dynamic wiring, for the dashboard."""
        _, attn = self._forward(X)
        return {n: round(float(v), 4) for n, v in zip(self.source_names, attn.mean(axis=0))}

    def predict_proba(self, X: Matrix) -> Vector:
        rows = self.predict_output(X)
        return [float(r[1]) for r in rows] if self.task == "binary" else [float(max(r)) for r in rows]

    def predict(self, X: Matrix) -> Labels:
        rows = self.predict_output(X)
        if self.task == "regression":
            return [int(round(float(r[0]))) for r in rows]
        return [int(np.argmax(r)) for r in rows]
