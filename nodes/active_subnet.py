"""HierarchicalGateNode — CORTEX T4: hierarchical per-input active subnetwork.

Saved-plan Step 2 (cryptic-painting-lamport) / design §1 T4, stitch row 19.
Top-k token-choice routing made HIERARCHICAL over **Leiden competence
communities** discovered from the experts' own co-activation graph:

  fit:  OOF expert outputs (leakage-safe, reuse gated_node kfold discipline)
        → flat sparse gate → per-input active masks → co-activation matrix
        (run_active.py pattern) → Leiden communities (igraph
        ``community_leiden(objective_function="modularity")``; networkx
        greedy-modularity fallback) → TWO-LEVEL gate: a top gate over community
        outputs + one sub-gate per community, all trained by the SAME
        ``gate_train`` primitive. Brain context rides the gate input only
        (option-D pattern from column_network) and the brain's TrustLedger
        biases every member gate via ``prior_bias`` (T7 → T4).

  predict: top gate picks top-k communities per input, sub-gates pick top-k
        members inside — the active subnetwork is chosen PER INPUT.

Honest wiring: ``firing_records`` / ``graph_snapshot`` expose only real trained
weights, real communities and real per-input routing (SigmaNetwork contract).
"""
from __future__ import annotations

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, NodeFactory, Vector
from nodes.gated_node import (gate_combine, gate_train, gate_weights, kfold_indices,
                              standardize_fit)


# --------------------------------------------------------------------------- #
#  Community detection over the co-activation graph
# --------------------------------------------------------------------------- #
def _igraph_communities(coact: np.ndarray) -> list[int]:
    """Leiden communities (modularity objective) via python-igraph."""
    import igraph as ig
    W = np.asarray(coact, dtype=float).copy()
    np.fill_diagonal(W, 0.0)
    g = ig.Graph.Weighted_Adjacency(W.tolist(), mode="undirected", attr="weight",
                                    loops=False)
    part = g.community_leiden(objective_function="modularity", weights="weight")
    return list(part.membership)


def _nx_communities(coact: np.ndarray) -> list[int]:
    """Greedy-modularity fallback (NetworkX) — same pattern as run_active.py."""
    E = coact.shape[0]
    try:
        import networkx as nx
        g = nx.Graph()
        g.add_nodes_from(range(E))
        for i in range(E):
            for j in range(i + 1, E):
                if coact[i, j] > 0.05:
                    g.add_edge(i, j, weight=float(coact[i, j]))
        comms = nx.community.greedy_modularity_communities(g, weight="weight")
        cid = {}
        for c, members in enumerate(comms):
            for k in members:
                cid[k] = c
        return [cid.get(i, 0) for i in range(E)]
    except Exception:
        return [0] * E


def detect_communities(coact: np.ndarray) -> list[int]:
    """Leiden (igraph) with networkx greedy-modularity fallback."""
    try:
        return _igraph_communities(coact)
    except Exception:
        return _nx_communities(coact)


class HierarchicalGateNode(BaseNode):
    kind = "hgate"
    summary = ("Two-level trained gate over Leiden co-activation communities; "
               "per-input active subnetwork with trust-biased routing.")

    def __init__(self, expert_factories: list[NodeFactory],
                 top_k_communities: int = 2, top_k_members: int = 0,
                 flat_top_k: int = 4, epochs: int = 150, lr: float = 0.05,
                 balance_coef: float = 0.01, noisy: bool = True, folds: int = 3,
                 seed: int = 7, task: str = "binary", head: str = "y",
                 brain_ctx_dim: int = 0, trust=None, trust_beta: float = 1.0,
                 name: str = "hgate"):
        self.name = name
        self.expert_factories = expert_factories
        self.top_k_communities = top_k_communities
        self.top_k_members = top_k_members          # 0 = dense sub-gates
        self.flat_top_k = flat_top_k                # sparsity of the discovery gate
        self.epochs = epochs
        self.lr = lr
        self.balance_coef = balance_coef
        self.noisy = noisy
        self.folds = folds
        self.seed = seed
        self.task = task
        self.head = head
        self.brain_ctx_dim = brain_ctx_dim
        self.trust = trust                          # core.trust.TrustLedger | None
        self.trust_beta = trust_beta
        self.schema = IOSchema(0, "features", f"{task} output [hgate]")

    # ── shared helpers (gated_node / column_network patterns) ────────────────
    def _new_expert(self, f):
        e = f()
        e.head, e.task = self.head, self.task
        return e

    def _outputs(self, experts, X_list) -> np.ndarray:
        return np.stack([np.asarray(e.predict_output(X_list), dtype=float)
                         for e in experts], axis=1)

    def _gate_input(self, X: np.ndarray, brain_ctx) -> np.ndarray:
        """Gate input = raw features (+ brain context — option-D pattern)."""
        if self.brain_ctx_dim and brain_ctx is not None:
            return np.concatenate([X, np.asarray(brain_ctx, dtype=float)], axis=1)
        return X

    def _trust_bias(self, names: list[str]):
        if self.trust is None:
            return None
        return self.trust.bias_vector(names, beta=self.trust_beta)

    # ── fit ──────────────────────────────────────────────────────────────────
    def fit(self, X: Matrix, y: Labels, brain_ctx: Matrix | None = None
            ) -> "HierarchicalGateNode":
        self._cls = self.task in ("binary", "multiclass")
        Xa, ya = np.asarray(X, dtype=float), np.asarray(y)
        n, d = Xa.shape
        K = (int(ya.max()) + 1) if self._cls else 1

        # keep only experts whose output width matches the head
        m = max(1, int(n * 0.8))
        facs, probe_names = [], []
        for f in self.expert_factories:
            try:
                e = self._new_expert(f).fit(Xa[:m].tolist(), ya[:m].tolist())
                if len(e.predict_output(Xa[m:m + 3].tolist())[0]) == K:
                    facs.append(f)
                    probe_names.append(e.name)
            except Exception:
                pass
        if not facs:
            raise ValueError(f"no experts emit width {K} for head '{self.head}'")
        E = len(facs)

        # out-of-fold expert outputs (leakage-safe for every gate level)
        meta = np.zeros((n, E, K), dtype=float)
        for val_idx in kfold_indices(n, self.folds):
            tr = [i for i in range(n) if i not in set(val_idx)]
            experts = [self._new_expert(f).fit(Xa[tr].tolist(), ya[tr].tolist())
                       for f in facs]
            meta[val_idx] = self._outputs(experts, Xa[val_idx].tolist())

        gin = self._gate_input(Xa, brain_ctx)
        self._mean, self._std = standardize_fit(gin)
        Xz = (gin - self._mean) / self._std
        bias_all = self._trust_bias(probe_names)

        # 1) FLAT discovery gate → per-input active masks → co-activation graph
        fk = self.flat_top_k if 0 < self.flat_top_k < E else max(1, E // 2)
        flat_gate, flat_noise = gate_train(Xz, meta, ya, self._cls, self.epochs,
                                           self.lr, self.balance_coef, self.noisy,
                                           fk, self.seed, prior_bias=bias_all)
        w_flat = gate_weights(flat_gate, flat_noise, Xz, fk, E, prior_bias=bias_all)
        active = w_flat > 1e-6
        coact = (active.astype(float).T @ active.astype(float)) / max(n, 1)

        # 2) Leiden competence communities (igraph → networkx fallback)
        comm = detect_communities(coact)
        self.communities = [int(c) for c in comm]
        keys = sorted(set(self.communities))
        self.community_keys = keys
        self.groups = {c: [i for i in range(E) if self.communities[i] == c]
                       for c in keys}

        # 3) two-level gate: sub-gate per community (trust-biased) + top gate
        C = len(keys)
        self._subs = {}
        comm_meta = np.zeros((n, C, K), dtype=float)
        for ci, c in enumerate(keys):
            idx = self.groups[c]
            sub_meta = meta[:, idx, :]
            sub_bias = (bias_all[idx] if bias_all is not None else None)
            sk = self.top_k_members if 0 < self.top_k_members < len(idx) else 0
            if len(idx) == 1:                       # single member: identity routing
                self._subs[c] = None
                comm_meta[:, ci, :] = sub_meta[:, 0, :]
                continue
            sg, sn = gate_train(Xz, sub_meta, ya, self._cls, self.epochs, self.lr,
                                self.balance_coef, self.noisy, sk, self.seed,
                                prior_bias=sub_bias)
            self._subs[c] = (sg, sn, sk, sub_bias)
            sw = gate_weights(sg, sn, Xz, sk, len(idx), prior_bias=sub_bias)
            comm_meta[:, ci, :] = gate_combine(sw, sub_meta, self._cls)

        tk = self.top_k_communities if 0 < self.top_k_communities < C else 0
        self._top = gate_train(Xz, comm_meta, ya, self._cls, self.epochs, self.lr,
                               self.balance_coef, self.noisy, tk, self.seed)
        self._top_k_eff = tk

        # refit experts on ALL data for inference
        self.experts = [self._new_expert(f).fit(X, y) for f in facs]
        self.expert_names = [e.name for e in self.experts]
        self._K = K
        self.schema = IOSchema(d, f"{d} numeric features",
                               f"{self.task} output [hgate C{C}]")
        return self

    # ── inference: per-input global routing weights ──────────────────────────
    def _route(self, X: Matrix, brain_ctx=None) -> tuple[np.ndarray, np.ndarray]:
        """Returns (w_global (n,E), w_top (n,C)) — real per-input routing weights."""
        gin = self._gate_input(np.asarray(X, dtype=float), brain_ctx)
        Xz = (gin - self._mean) / self._std
        n, E, C = len(Xz), len(self.experts), len(self.community_keys)
        w_top = gate_weights(self._top[0], self._top[1], Xz, self._top_k_eff, C)
        w_global = np.zeros((n, E), dtype=float)
        for ci, c in enumerate(self.community_keys):
            idx = self.groups[c]
            if self._subs[c] is None:
                sw = np.ones((n, 1), dtype=float)
            else:
                sg, sn, sk, sb = self._subs[c]
                sw = gate_weights(sg, sn, Xz, sk, len(idx), prior_bias=sb)
            w_global[:, idx] = w_top[:, ci:ci + 1] * sw
        return w_global, w_top

    def predict_output(self, X: Matrix, brain_ctx: Matrix | None = None
                       ) -> list[list[float]]:
        w_global, _ = self._route(X, brain_ctx)
        meta = self._outputs(self.experts, X)
        return gate_combine(w_global, meta, self._cls).tolist()

    def predict_proba(self, X: Matrix) -> Vector:
        rows = self.predict_output(X)
        return ([float(r[1]) for r in rows] if self.task == "binary"
                else [float(max(r)) for r in rows])

    def predict(self, X: Matrix) -> Labels:
        rows = self.predict_output(X)
        if self.task == "regression":
            return [int(round(float(r[0]))) for r in rows]
        return [int(np.argmax(r)) for r in rows]

    def active_subnetwork(self, X: Matrix, brain_ctx=None
                          ) -> tuple[np.ndarray, np.ndarray]:
        """Per-input (weights (n,E), active mask (n,E)) — chosen PER INPUT."""
        w, _ = self._route(X, brain_ctx)
        return w, (w > 1e-6)

    # ── dashboard contracts (honest wiring) ──────────────────────────────────
    def firing_records(self, X: Matrix, y: Labels, n_samples: int = 48) -> list[dict]:
        """SigmaNetwork firing contract: [{i, active, weights, community_path, correct}]."""
        w, w_top = self._route(X)
        active = w > 1e-6
        pred = self.predict(X)
        samples = np.linspace(0, len(X) - 1, min(n_samples, len(X))).astype(int)
        out = []
        for k in samples:
            act = [int(i) for i in range(len(self.experts)) if active[k, i]]
            path = [int(self.community_keys[ci])
                    for ci in np.argsort(-w_top[k]) if w_top[k, ci] > 1e-6]
            out.append({"i": int(k), "active": act,
                        "weights": [round(float(w[k, i]), 3) for i in act],
                        "community_path": path,
                        "correct": bool(pred[k] == y[k])})
        return out

    def graph_snapshot(self, X: Matrix) -> dict:
        """{nodes, edges, communities, active_subnet} from REAL trained weights only."""
        w, w_top = self._route(X)
        active = w > 1e-6
        usage, meanw = active.mean(0), w.mean(0)
        top_mean = w_top.mean(0)
        nodes = [{"name": nm, "kind": "base", "community": int(self.communities[i]),
                  "usage": round(float(usage[i]), 3),
                  "mean_weight": round(float(meanw[i]), 4)}
                 for i, nm in enumerate(self.expert_names)]
        edges = []
        for ci, c in enumerate(self.community_keys):
            cname = f"community_{c}"
            nodes.append({"name": cname, "kind": "community_gate",
                          "community": int(c), "usage": 1.0,
                          "mean_weight": round(float(top_mean[ci]), 4)})
            edges.append({"source": cname, "target": self.name,
                          "weight": round(float(top_mean[ci]), 4)})
            for i in self.groups[c]:
                edges.append({"source": self.expert_names[i], "target": cname,
                              "weight": round(float(meanw[i]), 4)})
        nodes.append({"name": self.name, "kind": self.kind, "community": -1,
                      "usage": 1.0, "mean_weight": 1.0})
        return {"nodes": nodes, "edges": edges,
                "communities": {nm: int(self.communities[i])
                                for i, nm in enumerate(self.expert_names)},
                "active_subnet": {"top_k_communities": self.top_k_communities,
                                  "top_k_members": self.top_k_members,
                                  "n_experts": len(self.experts),
                                  "n_communities": len(self.community_keys),
                                  "mean_active": round(float(active.sum(1).mean()), 2)}}
