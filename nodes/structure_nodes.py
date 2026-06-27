"""Structure / graph / topology nodes — visibility graphs, multifractal spectrum,
optimal transport, tensor decomposition. Wraps ts2vg / MFDFA / POT / tensorly
behind NodeProtocol, reusing the task-aware _HeadBase + _WindowFeat from
nodes.quant_nodes (causal trailing windows, no look-ahead).
"""
from __future__ import annotations

import warnings

import numpy as np

from nodes.quant_nodes import _HeadBase, _WindowFeat


class VisibilityGraphNode(_WindowFeat):
    """ts2vg natural visibility graph of the window → graph-topology features
    (degree distribution, density, assortativity, transitivity)."""
    NFEAT = 5

    def __init__(self, name="visibility_graph", col=0, W=64):
        super().__init__(name, "ts2vg natural-visibility-graph topology features.", col, W)
        self.kind = "graph"

    def _features(self, win):
        import networkx as nx
        from ts2vg import NaturalVG
        g = NaturalVG().build(np.asarray(win, float)).as_networkx()
        if g.number_of_nodes() < 3:
            return [0.0] * 5
        degs = [d for _, d in g.degree()]
        try:
            assort = float(nx.degree_assortativity_coefficient(g)) if g.number_of_edges() > 1 else 0.0
        except Exception:
            assort = 0.0
        if not np.isfinite(assort):
            assort = 0.0
        return [float(np.mean(degs)), float(np.var(degs)), float(nx.density(g)),
                assort, float(nx.transitivity(g))]


class MultifractalNode(_WindowFeat):
    """MFDFA multifractal detrended fluctuation analysis → spectrum width and
    generalized-Hurst features (multifractality is structure beyond single-DFA)."""
    NFEAT = 3

    def __init__(self, name="multifractal", col=0, W=160):
        super().__init__(name, "MFDFA multifractal spectrum width / generalized Hurst.", col, W)
        self.kind = "chaos"

    def _features(self, win):
        from MFDFA import MFDFA
        x = np.asarray(win, float)
        if len(x) < 40:
            return [0.0, 0.0, 0.0]
        lag = np.unique(np.logspace(0.7, np.log10(len(x) // 4), 12).astype(int))
        q = np.linspace(-5, 5, 11)
        lag2, dfa = MFDFA(x, lag=lag, q=q, order=1)
        H = []
        for i in range(dfa.shape[1]):
            y = dfa[:, i]
            ok = y > 0
            if ok.sum() > 2:
                H.append(float(np.polyfit(np.log(lag2[ok]), np.log(y[ok]), 1)[0]))
        if not H:
            return [0.0, 0.0, 0.0]
        H = np.asarray(H)
        return [float(H.max() - H.min()), float(np.median(H)), float(H[-1] - H[0])]


class OptimalTransportNode(_WindowFeat):
    """POT 1-D Wasserstein distance between the two halves of the window +
    energy distance — distributional drift / regime-morphing within the window."""
    NFEAT = 2

    def __init__(self, name="optimal_transport", col=0, W=96):
        super().__init__(name, "POT Wasserstein / energy-distance distributional-drift features.", col, W)
        self.kind = "math"

    def _features(self, win):
        import ot
        from scipy.stats import energy_distance
        x = np.asarray(win, float)
        h = len(x) // 2
        a, b = x[:h], x[h:]
        if len(a) < 5 or len(b) < 5:
            return [0.0, 0.0]
        try:
            w1 = float(ot.wasserstein_1d(a, b))
        except Exception:
            w1 = float(abs(a.mean() - b.mean()))
        return [w1, float(energy_distance(a, b))]


class TensorDecompNode(_HeadBase):
    """tensorly CP (PARAFAC) decomposition of a multichannel trailing window
    (time × features folded into a 3-way tensor) → latent factor weights +
    reconstruction norm. Uses ALL feature columns."""

    kind = "math"

    def __init__(self, name="tensor_decomp", W=48, rank=2):
        super().__init__(name, "tensorly CP-decomposition latent factors of the multichannel window.")
        self.W, self.rank = W, rank

    def _augment(self, X):
        import tensorly as tl
        from tensorly.decomposition import parafac
        Xa = np.asarray(X, float)
        n, d = Xa.shape
        out = []
        for i in range(n):
            w = Xa[max(0, i - self.W + 1): i + 1]
            feats = [0.0] * (self.rank + 1)
            with warnings.catch_warnings(), np.errstate(all="ignore"):
                warnings.simplefilter("ignore")
                if w.shape[0] >= 6:
                    try:
                        blk = (w.shape[0] // 2) * 2
                        ten = w[:blk].reshape(blk // 2, 2, d)
                        weights, _ = parafac(tl.tensor(ten), rank=self.rank, n_iter_max=40)
                        wv = sorted([float(v) for v in np.abs(weights)], reverse=True)[:self.rank]
                        feats = wv + [0.0] * (self.rank - len(wv)) + [float(np.linalg.norm(ten))]
                    except Exception:
                        pass
            out.append([float(v) for v in Xa[i]] + feats)
        return np.asarray(out, float)


def visibility_graph_node(name="visibility_graph"): return VisibilityGraphNode(name)
def multifractal_node(name="multifractal"): return MultifractalNode(name)
def optimal_transport_node(name="optimal_transport"): return OptimalTransportNode(name)
def tensor_decomp_node(name="tensor_decomp"): return TensorDecompNode(name)
