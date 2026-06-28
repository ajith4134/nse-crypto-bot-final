"""StructureSearchNode — P3.9: LEARN THE WIRING (differentiable architecture search).

Instead of wiring in all experts, this LEARNS which experts belong in the network. It is
the DARTS / lottery-ticket recipe the research kept surfacing: put a learnable weight on
every candidate expert-edge, train it by gradient descent, then PRUNE to a discrete active
subnetwork.

  effective weight w_i(x) = softmax(gate(x))_i · σ(α_i)        (α = per-expert architecture gate)
  loss = task_loss + λ·Σ σ(α_i)                                 (L1 sparsity → unused α→0)

After training, experts whose architecture gate σ(α_i) stays above a threshold are KEPT; the
rest are pruned. The committed network is then a GatedMoENode over only the kept experts —
so the search outputs a smaller, learned wiring that (ideally) matches the full pool. CPU-only,
reuses the P3.5 gate primitives + the OOF discipline from nodes.stacking_node. Task-aware.

(The gradient-free alternative — Nevergrad/NEAT evolving a discrete expert mask — is a drop-in
swap for this search step; this differentiable version needs no extra dependency.)
"""
from __future__ import annotations

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, NodeFactory, Vector
from nodes.gated_node import GatedMoENode, kfold_indices, standardize_fit


class StructureSearchNode(BaseNode):
    kind = "search"
    summary = "Differentiable architecture search (learns + prunes the expert wiring)."

    def __init__(self, expert_factories: list[NodeFactory], epochs: int = 300,
                 lr: float = 0.05, l1: float = 0.01, keep_frac: float = 0.5,
                 min_keep: int = 2, max_keep: int | None = None, folds: int = 5,
                 top_k: int = 0, seed: int = 7, task: str = "binary", head: str = "y",
                 name: str = "structure_search"):
        self.name = name
        self.expert_factories = expert_factories
        self.epochs = epochs
        self.lr = lr
        self.l1 = l1
        self.keep_frac = keep_frac        # keep experts with importance >= keep_frac * max
        self.min_keep = min_keep
        self.max_keep = max_keep          # cap kept set to the top-max_keep by importance
        self.folds = folds
        self.top_k = top_k
        self.seed = seed
        self.task = task
        self.head = head
        self.schema = IOSchema(0, "features", f"{task} output [structure-search]")

    def _new(self, f):
        e = f()
        e.head, e.task = self.head, self.task
        return e

    def fit(self, X: Matrix, y: Labels) -> "StructureSearchNode":
        import torch
        torch.manual_seed(self.seed)
        self._cls = self.task in ("binary", "multiclass")
        Xa, ya = np.asarray(X, dtype=float), np.asarray(y)
        n, d = Xa.shape
        K = (int(ya.max()) + 1) if self._cls else 1

        # width-filter candidate experts to the head
        m = max(1, int(n * 0.8))
        facs = []
        for f in self.expert_factories:
            try:
                e = self._new(f).fit(Xa[:m].tolist(), ya[:m].tolist())
                if len(e.predict_output(Xa[m:m + 3].tolist())[0]) == K:
                    facs.append(f)
            except Exception:
                pass
        if not facs:
            raise ValueError(f"no experts emit width {K} for head '{self.head}'")
        E = len(facs)

        # OOF expert outputs (leakage-safe)
        meta = np.zeros((n, E, K), dtype=float)
        for val_idx in kfold_indices(n, self.folds):
            tr = [i for i in range(n) if i not in set(val_idx)]
            experts = [self._new(f).fit(Xa[tr].tolist(), ya[tr].tolist()) for f in facs]
            meta[val_idx] = np.stack([np.asarray(e.predict_output(Xa[val_idx].tolist()), dtype=float)
                                      for e in experts], axis=1)

        mean, std = standardize_fit(Xa)
        Xt = torch.tensor((Xa - mean) / std, dtype=torch.float32)
        Mt = torch.tensor(meta, dtype=torch.float32)
        yt = (torch.tensor(ya.astype(int), dtype=torch.long) if self._cls
              else torch.tensor(ya.astype(float), dtype=torch.float32))

        gate = torch.nn.Linear(d, E)
        alpha = torch.nn.Parameter(torch.zeros(E))             # architecture gates (σ(α)≈0.5 init)
        opt = torch.optim.Adam(list(gate.parameters()) + [alpha], lr=self.lr)
        for _ in range(self.epochs):
            opt.zero_grad()
            gw = torch.softmax(gate(Xt), dim=1)                # per-input router
            a = torch.sigmoid(alpha)                           # per-expert architecture keep-gate
            w = gw * a
            w = w / (w.sum(dim=1, keepdim=True) + 1e-9)
            combined = (w.unsqueeze(-1) * Mt).sum(dim=1)
            if self._cls:
                p = combined.clamp_min(1e-9)
                p = p / p.sum(dim=1, keepdim=True)
                loss = torch.nn.functional.nll_loss(torch.log(p), yt)
            else:
                loss = torch.nn.functional.mse_loss(combined[:, 0], yt)
            loss = loss + self.l1 * a.mean()                   # L1 sparsity → prune unused experts
            loss.backward()
            opt.step()

        importance = torch.sigmoid(alpha).detach().numpy()     # learned architecture weight per expert
        order = list(np.argsort(-importance))                  # strongest first
        cutoff = self.keep_frac * float(importance.max())      # relative to the strongest expert
        above = [i for i in order if importance[i] >= cutoff]
        if len(above) < self.min_keep:                         # floor: keep the min_keep strongest
            above = order[:self.min_keep]
        if self.max_keep:                                      # cap: top max_keep by importance
            above = above[:self.max_keep]
        keep = sorted(above)

        self.all_names = [self._new(f).name for f in facs]
        self.kept_names = [self.all_names[i] for i in keep]
        self.pruned_names = [self.all_names[i] for i in range(E) if i not in keep]
        self.importance = {self.all_names[i]: round(float(importance[i]), 4) for i in range(E)}

        # commit a gate over ONLY the kept experts (the searched discrete subnetwork)
        kept_factories = [facs[i] for i in keep]
        self._final = GatedMoENode(kept_factories, top_k=self.top_k, epochs=self.epochs,
                                   task=self.task, head=self.head,
                                   name=f"{self.name}__committed").fit(X, y)
        self.schema = IOSchema(d, f"{d} numeric features",
                               f"{self.task} output [searched: {len(keep)}/{E} experts]")
        return self

    def predict_output(self, X: Matrix) -> list[list[float]]:
        return self._final.predict_output(X)

    def architecture(self) -> dict:
        """The learned wiring: which experts were kept vs pruned + per-expert importance."""
        return {"kept": self.kept_names, "pruned": self.pruned_names,
                "n_kept": len(self.kept_names), "n_total": len(self.all_names),
                "importance": self.importance}

    def predict_proba(self, X: Matrix) -> Vector:
        return self._final.predict_proba(X)

    def predict(self, X: Matrix) -> Labels:
        return self._final.predict(X)
