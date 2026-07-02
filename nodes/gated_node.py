"""GatedMoENode — P3.5: the DIFFERENTIABLE GATE (the real neural-network loop).

The first piece of the trainable model-graph (see ml-network-trainable-architecture.md).
Frozen expert nodes are the "neurons"; a small input-conditioned gate is the learnable
"connection weights", trained by REAL backprop (PyTorch-CPU) on the combined output:

        y = Σ_i  g_i(x) · e_i(x)          (MoE: gradient to the gate never needs ∂e_i,
             └gate┘  └frozen node┘         so non-differentiable experts work natively)

A genuine forward → loss → backprop → optimize → iterate loop run on the WIRING:
  forward    : x → gate softmax over E experts → weighted-combine expert predict_output
  loss       : cross-entropy (classification) / MSE (regression) + a load-balance aux loss
  backward   : autograd through the gate only (expert outputs are detached constants)
  optimize   : Adam on the gate weights
  iterate    : epochs to convergence

Leakage discipline (reuse of nodes.stacking_node): the gate trains on OUT-OF-FOLD expert
outputs (k-fold), then experts are refit on all data for inference. The Switch-style
importance loss stops the gate collapsing onto a few of the ~320 experts.

The gate training/inference primitives (`gate_train`, `gate_weights`, `gate_combine`) are
module-level so the deep cascade (P3.6, nodes.cascade_node) reuses the SAME gate.

Task-aware (binary | multiclass | regression) so it plugs into the multi-output heads.
"""
from __future__ import annotations

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, NodeFactory, Vector


def kfold_indices(n: int, folds: int) -> list[list[int]]:
    return [list(range(i, n, folds)) for i in range(folds)]


def standardize_fit(Xa: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = Xa.mean(0)
    std = Xa.std(0)
    std[std == 0] = 1.0
    return mean, std


# --------------------------------------------------------------------------- #
#  Reusable differentiable-gate primitives (shared by GatedMoENode + cascade)
# --------------------------------------------------------------------------- #
def gate_train(Xz: np.ndarray, meta: np.ndarray, y: np.ndarray, cls: bool,
               epochs: int, lr: float, balance_coef: float, noisy: bool,
               top_k: int, seed: int):
    """Train a softmax gate g(x) over E experts by backprop. Returns (gate, noise).

    Xz   : (n, d) standardized gate inputs.
    meta : (n, E, K) frozen expert outputs (detached constants).
    """
    import torch
    torch.manual_seed(seed)
    n, d = Xz.shape
    E = meta.shape[1]
    Xt = torch.tensor(Xz, dtype=torch.float32)
    Mt = torch.tensor(meta, dtype=torch.float32)
    yt = (torch.tensor(y.astype(int), dtype=torch.long) if cls
          else torch.tensor(y.astype(float), dtype=torch.float32))
    gate = torch.nn.Linear(d, E)
    noise = torch.nn.Linear(d, E) if noisy else None
    params = list(gate.parameters()) + (list(noise.parameters()) if noise else [])
    opt = torch.optim.Adam(params, lr=lr)
    for _ in range(epochs):
        opt.zero_grad()
        logits = gate(Xt)
        if noise is not None:                                   # noisy gating → spreads load
            logits = logits + torch.randn_like(logits) * torch.nn.functional.softplus(noise(Xt))
        if top_k and 0 < top_k < E:                             # optional sparse routing
            topv, topi = torch.topk(logits, top_k, dim=1)
            logits = torch.full_like(logits, float("-inf")).scatter(1, topi, topv)
        w = torch.softmax(logits, dim=1)
        combined = (w.unsqueeze(-1) * Mt).sum(dim=1)
        if cls:
            p = combined.clamp_min(1e-9)
            p = p / p.sum(dim=1, keepdim=True)
            loss = torch.nn.functional.nll_loss(torch.log(p), yt)
        else:
            loss = torch.nn.functional.mse_loss(combined[:, 0], yt)
        importance = w.sum(0)                                   # Switch-style load balance
        # std() is unbiased (n-1) → NaN for a single expert; no load to balance then.
        bal = ((importance.std() / (importance.mean() + 1e-9)) ** 2 if E > 1
               else importance.sum() * 0.0)
        (loss + balance_coef * bal).backward()
        opt.step()
    return gate, noise


def gate_weights(gate, noise, Xz: np.ndarray, top_k: int, E: int) -> np.ndarray:
    """Per-input gate weights (n, E) at inference (no noise)."""
    import torch
    with torch.no_grad():
        logits = gate(torch.tensor(Xz, dtype=torch.float32))
        if top_k and 0 < top_k < E:
            topv, topi = torch.topk(logits, top_k, dim=1)
            logits = torch.full_like(logits, float("-inf")).scatter(1, topi, topv)
        return torch.softmax(logits, dim=1).numpy()


def gate_combine(w: np.ndarray, meta: np.ndarray, cls: bool) -> np.ndarray:
    """Weighted-combine expert outputs; renormalize to a clean prob row for classification."""
    combined = (w[:, :, None] * meta).sum(axis=1)
    if cls:
        combined = np.clip(combined, 1e-9, None)
        combined = combined / combined.sum(axis=1, keepdims=True)
    return combined


class GatedMoENode(BaseNode):
    kind = "gate"
    summary = "Differentiable MoE gate over frozen experts (trained by backprop; load-balanced)."

    def __init__(self, expert_factories: list[NodeFactory], epochs: int = 250,
                 lr: float = 0.05, top_k: int = 0, noisy: bool = True,
                 balance_coef: float = 0.01, folds: int = 5, seed: int = 7,
                 task: str = "binary", head: str = "y", name: str = "gated_moe"):
        self.name = name
        self.expert_factories = expert_factories
        self.epochs = epochs
        self.lr = lr
        self.top_k = top_k                    # 0 = dense soft gate (experts already computed)
        self.noisy = noisy
        self.balance_coef = balance_coef
        self.folds = folds
        self.seed = seed
        self.task = task
        self.head = head
        self.schema = IOSchema(0, "features", f"{task} output [gated-moe]")

    def _new_expert(self, f):
        e = f()
        e.head, e.task = self.head, self.task
        return e

    def _outputs(self, experts, X) -> np.ndarray:
        """(n, E, K) tensor of expert predict_output rows, K = head output width."""
        return np.stack([np.asarray(e.predict_output(X), dtype=float) for e in experts], axis=1)

    def fit(self, X: Matrix, y: Labels) -> "GatedMoENode":
        self._cls = self.task in ("binary", "multiclass")
        n, d = len(X), len(X[0])
        Xa = np.asarray(X, dtype=float)
        ya = np.asarray(y)
        K = (int(ya.max()) + 1) if self._cls else 1                 # expected head output width

        # ── keep only experts whose output width matches the head (cf. run_multi) ──
        m = max(1, int(n * 0.8))
        facs = []
        for f in self.expert_factories:
            try:
                e = self._new_expert(f).fit(Xa[:m].tolist(), ya[:m].tolist())
                if len(e.predict_output(Xa[m:m + 3].tolist())[0]) == K:
                    facs.append(f)
            except Exception:
                pass
        if not facs:
            raise ValueError(f"no experts emit width {K} for head '{self.head}'")
        E = len(facs)

        # ── out-of-fold expert outputs (leakage-safe gate training set) ──
        meta = np.zeros((n, E, K), dtype=float)
        for val_idx in kfold_indices(n, self.folds):
            tr_idx = [i for i in range(n) if i not in set(val_idx)]
            experts = [self._new_expert(f).fit(Xa[tr_idx].tolist(), ya[tr_idx].tolist())
                       for f in facs]
            meta[val_idx] = self._outputs(experts, Xa[val_idx].tolist())

        self._mean, self._std = standardize_fit(Xa)
        Xz = (Xa - self._mean) / self._std
        self._gate, self._noise = gate_train(Xz, meta, ya, self._cls, self.epochs, self.lr,
                                              self.balance_coef, self.noisy, self.top_k, self.seed)
        # ── refit kept experts on ALL data for inference ──
        self.experts = [self._new_expert(f).fit(X, y) for f in facs]
        self.expert_names = [e.name for e in self.experts]
        self._K = K
        self.schema = IOSchema(d, f"{d} numeric features", f"{self.task} output [gated-moe]")
        return self

    def _w(self, X: Matrix) -> np.ndarray:
        Xz = (np.asarray(X, dtype=float) - self._mean) / self._std
        return gate_weights(self._gate, self._noise, Xz, self.top_k, len(self.experts))

    def predict_output(self, X: Matrix) -> list[list[float]]:
        return gate_combine(self._w(X), self._outputs(self.experts, X), self._cls).tolist()

    def gate_weights(self, X: Matrix) -> dict:
        """Mean learned gate weight per expert — the trained wiring, for the dashboard."""
        w = self._w(X).mean(axis=0)
        return {n: round(float(v), 4) for n, v in zip(self.expert_names, w)}

    def active_subnetwork(self, X: Matrix) -> tuple[np.ndarray, np.ndarray]:
        """Per-input routing: returns (weights (n,E), active mask (n,E)).

        With top_k>0 the gate fires only the top-k experts per input — the active
        subnetwork is chosen PER INPUT (not statically pruned), so a node useless on
        average but expert on a few inputs is kept and fired exactly when needed.
        """
        w = self._w(X)
        return w, (w > 1e-6)

    def predict_proba(self, X: Matrix) -> Vector:
        rows = self.predict_output(X)
        return [float(r[1]) for r in rows] if self.task == "binary" else [float(max(r)) for r in rows]

    def predict(self, X: Matrix) -> Labels:
        rows = self.predict_output(X)
        if self.task == "regression":
            return [int(round(float(r[0]))) for r in rows]
        return [int(np.argmax(r)) for r in rows]
