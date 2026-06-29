"""cognition/neuro_symbolic.py — traceable logic + causal reasoning (Phase P4.5).

Two real, reused reasoning engines that complement the neural recall layer:

1. ``SymbolicReasoner`` — **pyDatalog** (pure-Python Datalog, LGPL) runs genuine logic
   inference over the brain's **knowledge graph**: ``link(a,b)`` facts come from the graph's
   concept↔concept (``co_occurs``) and doc→concept (``about``) edges, and a transitive
   ``related/2`` rule derives *indirect* relationships the neural layer never stored
   explicitly. Every answer carries a **derivation trace** (the proof chain), so the brain's
   reasoning is inspectable — not a black box. (Scallop is the blueprint's first pick for this
   layer but ships no PyPI wheel and needs a Rust/maturin toolchain that isn't on this CPU box;
   ``_scallop_program`` is a real adapter that activates automatically if ``scallopy`` is ever
   installed, otherwise pyDatalog provides the equivalent traceable-Datalog capability.)

2. ``CausalAnalyzer`` — **DoWhy** (causal effect estimation + **refutation** robustness checks)
   and **causal-learn** (PC structure discovery). Lets the brain ask *"does X actually cause
   Y, or merely correlate?"* over a numeric table and get an effect estimate that has survived
   placebo/random-common-cause refuters — real causal inference, pure-CPU.

Both are offline and deterministic. pyDatalog uses a single global engine, so each query
rebuilds an isolated fact base via ``clear()`` (single-threaded reasoning — cheap, no leakage).
"""
from __future__ import annotations

import threading

_DATALOG_LOCK = threading.Lock()   # pyDatalog has one global engine — serialise rebuilds


def _scallop_available() -> bool:
    try:
        import scallopy  # noqa: F401
        return True
    except Exception:
        return False


class SymbolicReasoner:
    """Traceable transitive reasoning over the knowledge graph (pyDatalog / scallop)."""

    def __init__(self, edges: list[tuple[str, str]] | None = None, *, symmetric: bool = True):
        # edges = directed link(a,b) facts; symmetric mirrors them (graph relations are mutual)
        self.edges: list[tuple[str, str]] = []
        self.symmetric = symmetric
        if edges:
            self.add_edges(edges)
        self.engine = "scallop" if _scallop_available() else "pyDatalog"

    # ── build the fact base from a brain's knowledge graph ──────────────────────────
    @classmethod
    def from_brain(cls, brain, **kw) -> "SymbolicReasoner":
        """Pull concept↔concept and doc→concept edges out of a KnowledgeBrain.graph."""
        edges: list[tuple[str, str]] = []
        g = getattr(brain, "graph", None)
        try:
            raw = g.snapshot() if g is not None else {}
            for e in raw.get("edges", []):
                s, t = e.get("source") or e.get("from"), e.get("target") or e.get("to")
                rel = e.get("rel") or e.get("label") or ""
                if not s or not t:
                    continue
                if rel in ("co_occurs", "about", "related"):
                    edges.append((cls._name(s), cls._name(t)))
        except Exception:
            pass
        return cls(edges, **kw)

    @staticmethod
    def _name(node: str) -> str:
        # "concept:gradient" / "doc:foo" -> "gradient" / "foo"; sanitise for Datalog atoms
        n = node.split(":", 1)[-1] if ":" in node else node
        return n.replace("-", "_").replace("#", "_").replace(" ", "_") or "x"

    def add_edges(self, edges: list[tuple[str, str]]) -> None:
        for a, b in edges:
            self.edges.append((self._name(a), self._name(b)))

    # ── scallop adapter (dormant unless scallopy is installed) ──────────────────────
    def _scallop_related(self, start: str) -> set[str] | None:
        try:
            import scallopy
            ctx = scallopy.ScallopContext()
            ctx.add_relation("link", (str, str))
            for a, b in self._all_edges():
                ctx.add_facts("link", [(a, b)])
            ctx.add_rule("related(a, c) = link(a, c)")
            ctx.add_rule("related(a, c) = link(a, b), related(b, c)")
            ctx.run()
            return {c for (a, c) in ctx.relation("related") if a == start}
        except Exception:
            return None

    def _all_edges(self) -> list[tuple[str, str]]:
        es = list(self.edges)
        if self.symmetric:
            es += [(b, a) for a, b in self.edges]
        # dedupe, drop self-loops
        return sorted({(a, b) for a, b in es if a != b})

    # ── pyDatalog inference (the working engine) ────────────────────────────────────
    def related(self, start: str) -> dict:
        """Concepts transitively related to ``start``, with a derivation trace (proof chains)."""
        start = self._name(start)
        edges = self._all_edges()
        if _scallop_available():
            sc = self._scallop_related(start)
            if sc is not None:
                return {"start": start, "engine": "scallop",
                        "related": sorted(sc - {start}),
                        "trace": self._traces(start, edges, sc - {start})}

        with _DATALOG_LOCK:
            from pyDatalog import pyDatalog
            pyDatalog.clear()
            pyDatalog.create_terms("link, related, X, Y, Z")
            for a, b in edges:
                pyDatalog.assert_fact("link", a, b)
            pyDatalog.load("related(X, Y) <= link(X, Y)")
            pyDatalog.load("related(X, Y) <= link(X, Z) & related(Z, Y)")
            ans = pyDatalog.ask(f"related('{start}', Y)")
            # only Y is free → each answer is a 1-tuple of the related concept
            reachable = {row[0] for row in ans.answers} if ans else set()
            pyDatalog.clear()
        reachable.discard(start)
        return {"start": start, "engine": "pyDatalog", "related": sorted(reachable),
                "trace": self._traces(start, edges, reachable)}

    @staticmethod
    def _traces(start: str, edges: list[tuple[str, str]], targets: set[str]) -> dict:
        """Reconstruct one shortest proof chain per target (BFS over the same fact base)."""
        from collections import deque
        adj: dict[str, list[str]] = {}
        for a, b in edges:
            adj.setdefault(a, []).append(b)
        paths, q, seen = {}, deque([(start, [start])]), {start}
        while q:
            node, path = q.popleft()
            for nxt in adj.get(node, []):
                if nxt in seen:
                    continue
                seen.add(nxt)
                if nxt in targets:
                    paths[nxt] = " -> ".join(path + [nxt])
                q.append((nxt, path + [nxt]))
        return paths

    def status(self) -> dict:
        return {"engine": self.engine, "facts": len(self.edges),
                "symmetric": self.symmetric, "scallop": _scallop_available()}


class CausalAnalyzer:
    """Causal effect (DoWhy + refutation) and structure discovery (causal-learn)."""

    def estimate_effect(self, df, treatment: str, outcome: str,
                        common_causes: list[str], *, refute: bool = True) -> dict:
        """ATE of ``treatment`` on ``outcome`` adjusting for ``common_causes``, with refutation."""
        from dowhy import CausalModel
        model = CausalModel(data=df, treatment=treatment, outcome=outcome,
                            common_causes=common_causes)
        ident = model.identify_effect(proceed_when_unidentifiable=True)
        est = model.estimate_effect(ident, method_name="backdoor.linear_regression")
        out = {"treatment": treatment, "outcome": outcome, "ate": round(float(est.value), 4),
               "adjusted_for": list(common_causes), "engine": "dowhy"}
        if refute:
            out["refutations"] = self._refute(model, ident, est)
            out["robust"] = all(r.get("passed") for r in out["refutations"])
        return out

    @staticmethod
    def _refute(model, ident, est) -> list[dict]:
        # each refuter has a DIFFERENT robustness signature:
        #  - placebo: replace the treatment with noise → a real effect should COLLAPSE to ~0
        #  - random_common_cause: add a random confounder → a real effect should STAY STABLE
        checks = [("placebo_treatment_refuter", {"placebo_type": "permute"}, "collapse"),
                  ("random_common_cause", {}, "stable")]
        orig = abs(float(est.value)) or 1e-9
        results = []
        for method, kw, mode in checks:
            try:
                r = model.refute_estimate(ident, est, method_name=method, **kw)
                new = float(getattr(r, "new_effect", float("nan")))
                if mode == "collapse":
                    passed = abs(new) < orig * 0.25            # effect vanished under placebo
                else:
                    passed = abs(abs(new) - orig) < orig * 0.25  # effect held under random cause
                results.append({"method": method, "new_effect": round(new, 4),
                                "expect": mode, "passed": bool(passed)})
            except Exception as e:
                results.append({"method": method, "error": f"{type(e).__name__}: {e}"[:80]})
        return results

    def discover(self, df, *, alpha: float = 0.05) -> dict:
        """PC structure discovery: which variables are causally adjacent (causal-learn)."""
        import numpy as np
        from causallearn.search.ConstraintBased.PC import pc
        cols = list(df.columns)
        cg = pc(np.asarray(df.values, dtype=float), alpha, show_progress=False)
        G = cg.G.graph
        edges = []
        n = len(cols)
        for i in range(n):
            for j in range(i + 1, n):
                if G[i][j] != 0 or G[j][i] != 0:
                    edges.append((cols[i], cols[j]))
        return {"variables": cols, "edges": edges, "engine": "causal-learn", "alpha": alpha}
