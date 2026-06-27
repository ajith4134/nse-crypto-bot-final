"""NoiseRegimeRouter (ii) — route by detected noise/chaos regime, learning which
expert wins in each regime (no hardcoded assignment).

Estimates a per-input roughness score (short-term volatility + local curvature),
then searches a threshold that splits inputs into low/high-roughness regimes AND
assigns each side the expert that is most accurate THERE on training data. This
automatically discovers, e.g., 'recurrence in calm, reservoir under noise' rather
than assuming it.
"""
from __future__ import annotations

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, NodeFactory, Vector
from eval.golden import accuracy

VOL_IDX = 8  # vol10 feature


class NoiseRegimeRouter(BaseNode):
    kind = "router"
    summary = "Noise-regime router: learns the best expert for calm vs noisy inputs."

    def __init__(self, expert_factories: list[NodeFactory], name: str = "noise_router"):
        self.name = name
        self.expert_factories = expert_factories
        self.schema = IOSchema(0, "features", "p(class=1) [regime-routed]")
        self.thresh = 0.0
        self.low_e = self.high_e = 0
        self.routed = {}

    @staticmethod
    def _score(x: list[float]) -> float:
        vol = x[VOL_IDX] if len(x) > VOL_IDX else 0.0
        curv = abs(x[0] - 2 * x[1] + x[2])
        return vol + 0.5 * curv

    def fit(self, X: Matrix, y: Labels) -> "NoiseRegimeRouter":
        self.schema = IOSchema(len(X[0]), f"{len(X[0])} features", "p(class=1) [regime-routed]")
        self.experts = [f().fit(X, y) for f in self.expert_factories]
        self.expert_names = [e.name for e in self.experts]
        preds = [e.predict(X) for e in self.experts]
        scores = [self._score(x) for x in X]

        def best_expert(idxs):
            best_e, best_a = 0, -1.0
            for e in range(len(self.experts)):
                a = accuracy([preds[e][i] for i in idxs], [y[i] for i in idxs])
                if a > best_a:
                    best_a, best_e = a, e
            return best_e, best_a

        cands = sorted(set(scores))
        step = max(1, len(cands) // 40)
        best = (cands[0], -1.0, 0, 0)
        n = len(X)
        for t in cands[::step]:
            low = [i for i in range(n) if scores[i] <= t]
            high = [i for i in range(n) if scores[i] > t]
            if not low or not high:
                continue
            le, _ = best_expert(low)
            he, _ = best_expert(high)
            correct = sum(int(preds[le][i] == y[i]) for i in low) + \
                      sum(int(preds[he][i] == y[i]) for i in high)
            a = correct / n
            if a > best[1]:
                best = (t, a, le, he)
        self.thresh, _, self.low_e, self.high_e = best
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        ep = [e.predict_proba(X) for e in self.experts]
        self.routed = {self.expert_names[self.low_e]: 0, self.expert_names[self.high_e]: 0}
        out = []
        for i, x in enumerate(X):
            e = self.high_e if self._score(x) > self.thresh else self.low_e
            self.routed[self.expert_names[e]] = self.routed.get(self.expert_names[e], 0) + 1
            out.append(ep[e][i])
        return out

    def assignment(self) -> dict:
        return {"calm_expert": self.expert_names[self.low_e],
                "noisy_expert": self.expert_names[self.high_e],
                "threshold": round(self.thresh, 4)}
