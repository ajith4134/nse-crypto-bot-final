"""DeepCascadeNode — P3.6: the DEEP CASCADE (a deep, grown, gated model-network).

Stacks the differentiable gate (P3.5) into DEPTH, the way Deep-Forest/gcForest builds
"deep learning without neural nets": each layer's frozen experts transform the data, their
out-of-fold outputs are concatenated with the ORIGINAL raw features (skip connection) to
form the next layer's input, and depth GROWS while held-out score improves (Deep-Forest
plateau rule). The final layer's experts feed the trained differentiable gate for the output.

    raw x ─┬─────────────────────────────────────────────┐ (skip: raw re-fed each layer)
           ▼                                              │
        LAYER 0 experts ─ OOF outputs ─► concat(·, raw) ──┤
           ▼                                              │
        LAYER 1 experts ─ OOF outputs ─► concat(·, raw) ──┘
           ▼   ...grow while validation ↑ (patience)...
        LAYER L experts ─► GATE g(x) (backprop) ─► ŷ

Reuse-first: layer feature-augmentation = the gcForest recipe; the gate = P3.5's shared
`nodes.gated_node` primitives (`gate_train`/`gate_weights`/`gate_combine`); OOF discipline =
`nodes.stacking_node`. Leakage-safe (k-fold OOF per layer); depth chosen on an internal
held-out split, then the cascade is REBUILT on all data at that depth. Task-aware
(binary | multiclass | regression).
"""
from __future__ import annotations

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, NodeFactory, Vector
from eval.golden import accuracy
from nodes.gated_node import (gate_combine, gate_train, gate_weights, kfold_indices,
                              standardize_fit)


class DeepCascadeNode(BaseNode):
    kind = "cascade"
    summary = "Deep gated cascade of frozen experts (grown by validation; skip connections)."

    def __init__(self, expert_factories: list[NodeFactory], max_layers: int = 4,
                 folds: int = 3, val_frac: float = 0.25, gate_epochs: int = 200,
                 lr: float = 0.05, balance_coef: float = 0.01, noisy: bool = True,
                 top_k: int = 0, tol: float = 1e-3, patience: int = 1, seed: int = 7,
                 task: str = "binary", head: str = "y", name: str = "deep_cascade"):
        self.name = name
        self.expert_factories = expert_factories
        self.max_layers = max_layers
        self.folds = folds
        self.val_frac = val_frac
        self.gate_epochs = gate_epochs
        self.lr = lr
        self.balance_coef = balance_coef
        self.noisy = noisy
        self.top_k = top_k
        self.tol = tol
        self.patience = patience
        self.seed = seed
        self.task = task
        self.head = head
        self.schema = IOSchema(0, "features", f"{task} output [deep-cascade]")

    # ── helpers ──
    def _new(self, f):
        e = f()
        e.head, e.task = self.head, self.task
        return e

    def _outputs(self, experts, X_list) -> np.ndarray:
        return np.stack([np.asarray(e.predict_output(X_list), dtype=float) for e in experts], axis=1)

    def _layer(self, cur: np.ndarray, y: np.ndarray, facs) -> tuple[np.ndarray, list]:
        """One cascade layer: OOF expert outputs (n,E,K) + experts refit on all rows."""
        n = len(cur)
        E, K = len(facs), self._K
        meta = np.zeros((n, E, K), dtype=float)
        for val_idx in kfold_indices(n, self.folds):
            tr = [i for i in range(n) if i not in set(val_idx)]
            experts = [self._new(f).fit(cur[tr].tolist(), y[tr].tolist()) for f in facs]
            meta[val_idx] = self._outputs(experts, cur[val_idx].tolist())
        full = [self._new(f).fit(cur.tolist(), y.tolist()) for f in facs]
        return meta, full

    def _score(self, pred_rows: np.ndarray, y: np.ndarray) -> float:
        if self._cls:
            return accuracy([int(np.argmax(r)) for r in pred_rows], list(y.astype(int)))
        return -float(np.mean(np.abs(pred_rows[:, 0] - y.astype(float))))   # -MAE (higher=better)

    def _train_gate(self, raw: np.ndarray, meta: np.ndarray, y: np.ndarray, mean, std):
        return gate_train((raw - mean) / std, meta, y, self._cls, self.gate_epochs, self.lr,
                          self.balance_coef, self.noisy, self.top_k, self.seed)

    def fit(self, X: Matrix, y: Labels) -> "DeepCascadeNode":
        self._cls = self.task in ("binary", "multiclass")
        Xa, ya = np.asarray(X, dtype=float), np.asarray(y)
        n, d = Xa.shape
        self._K = (int(ya.max()) + 1) if self._cls else 1

        # ── width-filter experts to the head (cf. run_multi) ──
        m = max(1, int(n * 0.8))
        facs = []
        for f in self.expert_factories:
            try:
                e = self._new(f).fit(Xa[:m].tolist(), ya[:m].tolist())
                if len(e.predict_output(Xa[m:m + 3].tolist())[0]) == self._K:
                    facs.append(f)
            except Exception:
                pass
        if not facs:
            raise ValueError(f"no experts emit width {self._K} for head '{self.head}'")
        self._facs, self._E = facs, len(facs)

        # ── Phase 1: grow on an internal split to pick the depth ──
        idx = list(range(n))
        np.random.RandomState(self.seed).shuffle(idx)
        cut = int(n * (1 - self.val_frac))
        tr, va = idx[:cut], idx[cut:]
        raw_tr, raw_va, ytr, yva = Xa[tr], Xa[va], ya[tr], ya[va]
        gmean, gstd = standardize_fit(raw_tr)
        cur_tr, cur_va = raw_tr, raw_va
        best, best_depth, no_improve = -1e18, 1, 0
        for L in range(self.max_layers):
            meta_tr, experts = self._layer(cur_tr, ytr, facs)
            meta_va = self._outputs(experts, cur_va.tolist())
            gate, noise = self._train_gate(raw_tr, meta_tr, ytr, gmean, gstd)
            w = gate_weights(gate, noise, (raw_va - gmean) / gstd, self.top_k, self._E)
            score = self._score(gate_combine(w, meta_va, self._cls), yva)
            if score > best + self.tol:
                best, best_depth, no_improve = score, L + 1, 0
            else:
                no_improve += 1
                if no_improve >= self.patience:
                    break
            cur_tr = np.concatenate([meta_tr.reshape(len(cur_tr), -1), raw_tr], axis=1)
            cur_va = np.concatenate([meta_va.reshape(len(cur_va), -1), raw_va], axis=1)
        self._depth = best_depth

        # ── Phase 2: rebuild the chosen depth on ALL data ──
        self._gmean, self._gstd = standardize_fit(Xa)
        self.layers: list[list] = []
        cur = Xa
        for L in range(self._depth):
            meta, experts = self._layer(cur, ya, facs)
            self.layers.append(experts)
            if L == self._depth - 1:
                self._gate, self._noise = self._train_gate(Xa, meta, ya, self._gmean, self._gstd)
            else:
                cur = np.concatenate([meta.reshape(n, -1), Xa], axis=1)
        self.expert_names = [e.name for e in self.layers[-1]]
        self.schema = IOSchema(d, f"{d} numeric features",
                               f"{self.task} output [deep-cascade L{self._depth}]")
        return self

    def _final_meta(self, X: Matrix) -> tuple[np.ndarray, np.ndarray]:
        raw = np.asarray(X, dtype=float)
        cur = raw
        for L in range(self._depth):
            meta = self._outputs(self.layers[L], cur.tolist())
            if L == self._depth - 1:
                return raw, meta
            cur = np.concatenate([meta.reshape(len(raw), -1), raw], axis=1)
        return raw, meta                                    # unreachable (depth>=1)

    def predict_output(self, X: Matrix) -> list[list[float]]:
        raw, meta = self._final_meta(X)
        w = gate_weights(self._gate, self._noise, (raw - self._gmean) / self._gstd,
                         self.top_k, self._E)
        return gate_combine(w, meta, self._cls).tolist()

    @property
    def depth(self) -> int:
        return self._depth

    def gate_weights(self, X: Matrix) -> dict:
        """Final-layer learned gate weights (the trained wiring), for the dashboard."""
        raw, _ = self._final_meta(X)
        w = gate_weights(self._gate, self._noise, (raw - self._gmean) / self._gstd,
                         self.top_k, self._E).mean(axis=0)
        return {n: round(float(v), 4) for n, v in zip(self.expert_names, w)}

    def predict_proba(self, X: Matrix) -> Vector:
        rows = self.predict_output(X)
        return [float(r[1]) for r in rows] if self.task == "binary" else [float(max(r)) for r in rows]

    def predict(self, X: Matrix) -> Labels:
        rows = self.predict_output(X)
        if self.task == "regression":
            return [int(round(float(r[0]))) for r in rows]
        return [int(np.argmax(r)) for r in rows]
