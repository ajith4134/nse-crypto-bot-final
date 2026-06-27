"""GrowingBrain — grows the network by keeping only nodes that help.

Greedy forward selection. Two combiners decide whether a candidate 'helps':
  • "mean"   — held-out mean-vote accuracy (conservative; plateaus fast).
  • "router" — held-out DCS local-accuracy routing (regime-aware): a candidate
               is kept if it raises the ROUTER's validation accuracy. Because a
               router can send each input to a different specialist, this rewards
               diversity and grows a larger, complementary network.

Candidate nodes are trained ONCE; routing reuses cached predictions + native
nearest-neighbour search, so growth stays fast.
"""
from __future__ import annotations

from core.node_protocol import Labels, Matrix, NodeFactory, Vector
from eval.golden import accuracy
from native import fastops as _fo

VOL_IDX = 8  # vol10 feature -> regime/roughness score


def _roughness(x: list[float]) -> float:
    vol = x[VOL_IDX] if len(x) > VOL_IDX else 0.0
    return vol + 0.5 * abs(x[0] - 2 * x[1] + x[2])


def _mean(proba_list: list[Vector], idxs: list[int]) -> Vector:
    n = len(proba_list[0])
    return [sum(proba_list[j][i] for j in idxs) / len(idxs) for i in range(n)]


class GrowingBrain:
    def __init__(self, candidate_factories: list[NodeFactory], names: list[str] | None = None):
        self.factories = candidate_factories
        self.names = names or [f().name for f in candidate_factories]
        self.trained = []
        self.selected: list[int] = []
        self.combiner = "mean"

    def grow(self, Xtr: Matrix, ytr: Labels, Xval: Matrix, yval: Labels,
             tol: float = 1e-9, combiner: str = "mean", regime_aware: bool = True,
             k: int = 25, score_weight: float = 2.0,
             Xg: Matrix | None = None, yg: Labels | None = None,
             patience: int = 2) -> list[dict]:
        self.combiner = combiner
        self.trained = [f().fit(Xtr, ytr) for f in self.factories]
        if combiner == "router":
            return self._grow_routed(Xtr, ytr, Xval, yval, k, regime_aware, score_weight,
                                     tol, Xg, yg, patience)
        return self._grow_mean(Xval, yval, tol)

    # ── mean-vote ──
    def _grow_mean(self, Xval, yval, tol) -> list[dict]:
        valP = [n.predict_proba(Xval) for n in self.trained]
        selected, history, best = [], [], 0.0
        remaining = list(range(len(self.factories)))
        while remaining:
            cand = None
            for j in remaining:
                ens = _mean(valP, selected + [j])
                acc = accuracy([1 if p >= 0.5 else 0 for p in ens], yval)
                if cand is None or acc > cand[1]:
                    cand = (j, acc)
            if cand[1] > best + tol:
                selected.append(cand[0]); remaining.remove(cand[0]); best = cand[1]
                history.append({"added": self.names[cand[0]],
                                "val_accuracy": round(cand[1], 4), "n_nodes": len(selected)})
            else:
                break
        self.selected = selected
        return history

    # ── routed (regime-aware DCS) ──
    def _build_aug(self, Xtr, regime_aware, score_weight):
        d = len(Xtr[0])
        mean = [sum(r[j] for r in Xtr) / len(Xtr) for j in range(d)]
        std = [(sum((r[j] - mean[j]) ** 2 for r in Xtr) / len(Xtr)) ** 0.5 or 1.0
               for j in range(d)]
        smean = sstd = 0.0
        if regime_aware:
            sc = [_roughness(x) for x in Xtr]
            smean = sum(sc) / len(sc)
            sstd = (sum((s - smean) ** 2 for s in sc) / len(sc)) ** 0.5 or 1.0

        def aug(x):
            z = [(x[j] - mean[j]) / std[j] for j in range(d)]
            if regime_aware:
                z = z + [score_weight * (_roughness(x) - smean) / sstd]
            return z
        return aug

    def _eval_tables(self, Xset):
        """Per-point local-accuracy of each candidate + each candidate's labels."""
        C = len(self.trained)
        la = []
        for x in Xset:
            dd = _fo.sqdists_prepared(self._prep, self._aug(x))
            nb = sorted(range(len(dd)), key=lambda i: dd[i])[:self._k]
            la.append([sum(self._train_correct[c][i] for i in nb) for c in range(C)])
        pred = [[1 if p >= 0.5 else 0 for p in n.predict_proba(Xset)] for n in self.trained]
        return la, pred

    @staticmethod
    def _routed_acc(la, pred, y, subset):
        correct = 0
        for v in range(len(y)):
            lav = la[v]
            be, ba = subset[0], -1
            for c in subset:
                if lav[c] > ba:
                    ba, be = lav[c], c
            correct += int(pred[be][v] == y[v])
        return correct / len(y)

    def _grow_routed(self, Xtr, ytr, Xval, yval, k, regime_aware, score_weight,
                     tol, Xg, yg, patience) -> list[dict]:
        self._aug = self._build_aug(Xtr, regime_aware, score_weight)
        self._k = k
        self._prep = _fo.prepare([self._aug(x) for x in Xtr])
        self._train_correct = [[int(p == t) for p, t in zip(n.predict(Xtr), ytr)]
                               for n in self.trained]
        v_la, v_pred = self._eval_tables(Xval)
        guard = Xg is not None and yg is not None
        if guard:
            g_la, g_pred = self._eval_tables(Xg)

        C = len(self.trained)
        selected, history = [], []
        best_val = 0.0
        best_guard, best_selected, no_improve = -1.0, [], 0
        remaining = list(range(C))
        while remaining:
            cand = None                                    # greedy pick by val accuracy
            for j in remaining:
                a = self._routed_acc(v_la, v_pred, yval, selected + [j])
                if cand is None or a > cand[1]:
                    cand = (j, a)
            # No guard -> stop at the val plateau. With a guard -> keep exploring past the
            # plateau (lever 1); the guard + patience decide when to stop and what to keep.
            if not guard and cand[1] <= best_val + tol:
                break
            selected.append(cand[0]); remaining.remove(cand[0])
            best_val = max(best_val, cand[1])
            g = self._routed_acc(g_la, g_pred, yg, selected) if guard else cand[1]
            history.append({"added": self.names[cand[0]], "val_accuracy": round(cand[1], 4),
                            "guard_accuracy": round(g, 4) if guard else None,
                            "n_nodes": len(selected)})
            if g > best_guard + tol:                       # guard improved -> new best config
                best_guard, best_selected, no_improve = g, selected[:], 0
            elif guard:                                    # guard stalled -> count toward early stop
                no_improve += 1
                if no_improve >= patience:
                    break

        self.selected = best_selected if guard else selected
        self._best_n = len(self.selected)
        for h in history:                                  # mark which additions were kept
            h["kept"] = h["n_nodes"] <= self._best_n
        return history

    def selected_names(self) -> list[str]:
        return [self.names[i] for i in self.selected]

    def predict_proba(self, X: Matrix) -> Vector:
        if self.combiner == "router":
            out = []
            for x in X:
                dd = _fo.sqdists_prepared(self._prep, self._aug(x))
                nb = sorted(range(len(dd)), key=lambda i: dd[i])[:self._k]
                be, ba = self.selected[0], -1
                for c in self.selected:
                    a = sum(self._train_correct[c][i] for i in nb)
                    if a > ba:
                        ba, be = a, c
                out.append(self.trained[be].predict_proba([x])[0])
            return out
        P = [self.trained[i].predict_proba(X) for i in self.selected]
        return [sum(P[k][i] for k in range(len(P))) / len(P) for i in range(len(X))]

    def predict(self, X: Matrix) -> Labels:
        return [1 if p >= 0.5 else 0 for p in self.predict_proba(X)]
