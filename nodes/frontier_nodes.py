"""Frontier nodes: quantum-inspired kernels, a reinforcement-learning policy, and
option-implied-volatility analytics — all behind the project NodeProtocol.

Reuse-first: instead of re-copying the readout boilerplate, this module imports
the proven `_HeadBase`/`_WindowFeat`/`_readout` machinery from `nodes.quant_nodes`
(the task-aware readout; `predict_output` returns per-class probs or `[value]`;
binary stays `[1-p, p]`; degenerate single-class fits are guarded). Each node is a
class plus a NO-ARG factory. CPU only — the one quantum node uses PennyLane's
`default.qubit` simulator (no GPU); slowness is acceptable, a GPU requirement is
the only thing that would justify skipping a node.

Nodes
-----
* `QuantumKernelNode`  (kind="quantum") — small 3-qubit quantum feature map
  (AngleEmbedding of 3 PCA features) → fidelity/overlap kernel → precomputed-kernel
  SVC / KernelRidge readout. O(n) statevector evals + O(n^2) numpy overlaps.
  Robust fallback to an RBF SVC if PennyLane errors.
* `RLPolicyNode`       (kind="policy")  — contextual-bandit / tabular-Q policy.
  DIFFERENT PARADIGM: it outputs a DECISION/ACTION (down/up), not a calibrated
  probabilistic forecast — it really belongs to a policy/execution layer, but is
  exposed here as a node for completeness. The chosen action's value is mapped to
  class probabilities so it conforms to the contract.
* `OptionIVNode`       (kind="quant")   — QuantLib Black-Scholes analytics on a
  DOWNLOADED Deribit BTC option-chain snapshot (free, no API key). HONEST LIMIT:
  Deribit gives a CURRENT snapshot, NOT history aligned to our X->y price series,
  so the snapshot analytics are a STANDALONE capability. For the NodeProtocol
  train/verify path the node falls back to a Black-Scholes implied-vol feature
  derived from the price series' own realized vol, so it still conforms + trains.
"""
from __future__ import annotations

import json
import os
import ssl
import time
import urllib.request
import warnings

import numpy as np

from core.node_protocol import IOSchema, Labels, Matrix, Vector
# Reuse the audited readout/window machinery rather than re-copying it.
from nodes.quant_nodes import _HeadBase, _WindowFeat, _readout

warnings.filterwarnings("ignore")
try:                                              # silence PennyLane deprecations
    from pennylane import PennyLaneDeprecationWarning
    warnings.simplefilter("ignore", PennyLaneDeprecationWarning)
except Exception:
    pass


# --------------------------------------------------------------------------- #
#  1. QuantumKernelNode (kind="quantum")
# --------------------------------------------------------------------------- #
class QuantumKernelNode(_HeadBase):
    """Quantum-kernel classifier on a CPU statevector simulator (no GPU).

    Pipeline: StandardScaler + PCA(->3) reduces each row to 3 features, which are
    angle-embedded on a 3-qubit `default.qubit` device to a statevector |phi(x)>.
    The quantum (fidelity / overlap) kernel is K(x_i, x_j) = |<phi(x_i)|phi(x_j)>|^2.
    We compute it as O(n) statevector evaluations followed by O(n^2) numpy inner
    products (instead of O(n^2) circuit runs), then hand the precomputed Gram
    matrix to an SVC (classification) or KernelRidge (regression).

    Training is subsampled to <= `max_train` rows because the kernel is O(n^2)
    (FLAG the fit time if it crosses the budget). Robust fallback to an RBF SVC if
    PennyLane raises for any reason.
    """

    kind = "quantum"

    def __init__(self, name="quantum_kernel", n_qubits=3, max_train=180):
        super().__init__(
            name,
            "3-qubit AngleEmbedding fidelity kernel (CPU sim) + precomputed-kernel SVC.",
        )
        self.kind = "quantum"
        self.n_qubits = int(n_qubits)
        self.max_train = int(max_train)
        self._mode = "quantum"
        self._state_fn = None
        self._ref_states = None
        self._Xref = None
        self._reduce = None

    # -- quantum feature map -------------------------------------------------- #
    def _build_kernel(self, nq: int) -> None:
        import pennylane as qml
        dev = qml.device("default.qubit", wires=nq)

        @qml.qnode(dev)
        def _state(x):
            qml.AngleEmbedding(x, wires=range(nq))
            return qml.state()

        self._state_fn = _state

    def _states(self, X: np.ndarray) -> np.ndarray:
        return np.asarray([np.asarray(self._state_fn(row)) for row in X])

    def _kernel_vs_ref(self, X: np.ndarray) -> np.ndarray:
        qs = self._states(X)
        return np.abs(qs @ self._ref_states.conj().T) ** 2

    # -- contract ------------------------------------------------------------- #
    def fit(self, X: Matrix, y: Labels) -> "QuantumKernelNode":
        from sklearn.decomposition import PCA
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler

        ya = np.asarray(y)
        self.schema = IOSchema(len(X[0]), f"{len(X[0])} numeric features", self.task)
        if self.task != "regression":
            self._classes = sorted(set(int(v) for v in ya))
            if len(self._classes) < 2:        # degenerate guard
                return self

        Xa = np.asarray(X, float)
        ncomp = min(self.n_qubits, Xa.shape[1])
        self._reduce = make_pipeline(StandardScaler(), PCA(n_components=ncomp))
        Xr = self._reduce.fit_transform(Xa)

        n = len(Xr)                            # subsample: kernel is O(n^2)
        m = min(self.max_train, n)
        if m < n:
            idx = np.sort(np.random.default_rng(0).choice(n, size=m, replace=False))
        else:
            idx = np.arange(n)
        self._Xref, y_sub = Xr[idx], ya[idx]

        self._mode = "quantum"
        try:
            self._build_kernel(ncomp)
            self._ref_states = self._states(self._Xref)
            Ktr = np.abs(self._ref_states @ self._ref_states.conj().T) ** 2
        except Exception:                      # robust fallback to classical RBF
            self._mode = "rbf"
            self.summary += " [fallback: RBF SVC]"

        if self.task == "regression":
            from sklearn.kernel_ridge import KernelRidge
            self._ro = KernelRidge(kernel="precomputed" if self._mode == "quantum" else "rbf")
        else:
            from sklearn.svm import SVC
            self._ro = SVC(kernel="precomputed" if self._mode == "quantum" else "rbf",
                           probability=True, random_state=0)
        self._ro.fit(Ktr if self._mode == "quantum" else self._Xref, y_sub)
        return self

    def _augment(self, X: Matrix) -> np.ndarray:
        Xr = self._reduce.transform(np.asarray(X, float))
        return self._kernel_vs_ref(Xr) if self._mode == "quantum" else Xr


# --------------------------------------------------------------------------- #
#  2. RLPolicyNode (kind="policy")
# --------------------------------------------------------------------------- #
class RLPolicyNode(_HeadBase):
    """Contextual-bandit / tabular-Q trading policy.

    DIFFERENT PARADIGM (read this): unlike the forecasting nodes, this learns a
    *decision rule*. It discretizes the state by the sign of a few recent
    return-like features, then learns action-values Q[state][action] for the two
    actions {0=down, 1=up} by an incremental Q-update toward the (counterfactual)
    full-information reward r(a)=1[a==y]. At convergence Q[s][up] = P(up | s), so
    the value of the chosen "up" action doubles as a class-1 probability — that's
    how a policy's confidence is mapped onto the probabilistic node contract.

    Conceptually this belongs to a policy / execution layer (it emits actions, not
    calibrated forecasts); it is surfaced here as a node only for completeness.
    For non-binary heads it gracefully delegates to a standard task-aware readout
    on the raw features so it still trains and conforms.
    """

    kind = "policy"

    def __init__(self, name="rl_policy", cols=(0, 3), alpha=0.2, epochs=5):
        super().__init__(
            name,
            "Tabular-Q / contextual-bandit policy: state=sign(recent returns), actions={down,up}.",
        )
        self.kind = "policy"
        self.cols = tuple(int(c) for c in cols)
        self.alpha = float(alpha)
        self.epochs = int(epochs)
        self._mode = "policy"
        self._Q: dict[tuple, list[float]] = {}

    def _state(self, row) -> tuple:
        cols = [c for c in self.cols if c < len(row)] or [0]
        return tuple(1 if float(row[c]) > 0 else 0 for c in cols)

    def fit(self, X: Matrix, y: Labels) -> "RLPolicyNode":
        ya = np.asarray(y)
        self.schema = IOSchema(len(X[0]), f"{len(X[0])} numeric features", self.task)
        if self.task != "regression":
            self._classes = sorted(set(int(v) for v in ya))
            if len(self._classes) < 2:        # degenerate guard
                return self

        if self.task == "binary":
            self._mode = "policy"
            up = self._classes[-1]            # larger label == "up" action
            self._Q = {}
            rng = np.random.default_rng(0)
            order = np.arange(len(X))
            for _ in range(self.epochs):       # epsilon-soft Q-learning sweeps
                rng.shuffle(order)
                for i in order:
                    s = self._state(X[i])
                    q = self._Q.setdefault(s, [0.5, 0.5])
                    lbl_up = 1 if int(ya[i]) == up else 0
                    for a, r in ((1, lbl_up), (0, 1 - lbl_up)):
                        q[a] += self.alpha * (r - q[a])   # incremental update
            return self

        # non-binary: delegate to the audited task-aware readout on raw features
        self._mode = "readout"
        self._ro = _readout(self.task)
        self._ro.fit(self._augment(X), ya)
        return self

    def _augment(self, X: Matrix) -> np.ndarray:
        return np.asarray([[float(v) for v in row] for row in X], float)

    def predict_proba(self, X: Matrix) -> Vector:
        if self.task == "binary" and self._mode == "policy":
            if len(self._classes) < 2:
                return [float(self._classes[0] if self._classes else 0.0)] * len(X)
            out = []
            for row in X:
                qd, qu = self._Q.get(self._state(row), [0.5, 0.5])
                tot = qd + qu
                out.append(float(qu / tot) if tot > 0 else 0.5)
            return out
        return super().predict_proba(X)


# --------------------------------------------------------------------------- #
#  3. OptionIVNode (kind="quant")
# --------------------------------------------------------------------------- #
_CACHE_DIR = "/home/karan18190164/data/cache"
_CACHE_PATH = os.path.join(_CACHE_DIR, "deribit_options.json")
_DERIBIT = "https://www.deribit.com/api/v2/public"
_MS_PER_YEAR = 365.0 * 24 * 3600 * 1000.0


def _http_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.load(r)


class OptionIVNode(_WindowFeat):
    """Option implied-volatility analytics (QuantLib Black-Scholes + Deribit data).

    Two capabilities, deliberately separated because the data sources don't align:

    1. STANDALONE snapshot analytics (`download_snapshot` + `snapshot_features`):
       downloads the CURRENT Deribit BTC option chain (public, no key) and uses
       QuantLib Black-Scholes to compute a volatility-smile slope & curvature, the
       25-delta risk reversal, ATM IV, and a model-vs-mark price sanity check.

    2. NodeProtocol train/verify path (`fit`/`predict_*`, inherited): the Deribit
       snapshot is a single point in time and is NOT aligned to our historical
       X->y price series, and free historical option data does not exist — so for
       training the node FALLS BACK to a Black-Scholes implied-vol feature derived
       from the price series' OWN trailing realized volatility (annualized realized
       vol + the BS price of a 30-day ATM call at that vol), appended per row. This
       keeps the node conforming and trainable.

    HONEST LIMITATION: capability (1) cannot train on our historical X->y because
    the snapshot has no aligned history; (2) is what actually feeds fit().
    """

    kind = "quant"
    NFEAT = 2

    def __init__(self, name="option_iv", col=0, W=64):
        super().__init__(
            name,
            "BS implied-vol features (realized-vol fallback) + standalone Deribit smile analytics.",
            col, W,
        )
        self.kind = "quant"

    # -- (2) NodeProtocol train/verify feature: BS-IV proxy from realized vol -- #
    def _bs_atm_call(self, sigma: float) -> float:
        import QuantLib as ql
        T = 30.0 / 365.0
        std = max(float(sigma), 1e-6) * np.sqrt(T)
        try:                                   # fwd=spot=1, K=1, r=0 -> discount=1
            return float(ql.blackFormula(ql.Option.Call, 1.0, 1.0, std, 1.0))
        except Exception:
            return 0.0

    def _features(self, win):
        r = np.asarray(win, float)
        rv = float(np.std(r)) * np.sqrt(252.0)   # annualized realized-vol proxy
        return [rv, self._bs_atm_call(rv)]

    # -- (1) standalone snapshot analytics ----------------------------------- #
    @staticmethod
    def download_snapshot(force: bool = False) -> dict:
        """Download + cache the current Deribit BTC option chain (free/no-key).

        Returns {instruments, summary, underlying_price, ts}. On network failure
        falls back to the cached file if one exists.
        """
        if not force and os.path.exists(_CACHE_PATH):
            try:
                with open(_CACHE_PATH) as fh:
                    return json.load(fh)
            except Exception:
                pass
        snap = {"instruments": [], "summary": [], "underlying_price": None,
                "ts": int(time.time() * 1000)}
        try:
            inst = _http_json(f"{_DERIBIT}/get_instruments?currency=BTC&kind=option")
            summ = _http_json(f"{_DERIBIT}/get_book_summary_by_currency?currency=BTC&kind=option")
            snap["instruments"] = inst.get("result", [])
            snap["summary"] = summ.get("result", [])
            ups = [s.get("underlying_price") for s in snap["summary"] if s.get("underlying_price")]
            snap["underlying_price"] = float(np.median(ups)) if ups else None
            os.makedirs(_CACHE_DIR, exist_ok=True)
            with open(_CACHE_PATH, "w") as fh:
                json.dump(snap, fh)
        except Exception as exc:               # offline: reuse cache if present
            if os.path.exists(_CACHE_PATH):
                with open(_CACHE_PATH) as fh:
                    return json.load(fh)
            snap["error"] = str(exc)
        return snap

    def snapshot_features(self, snap: dict | None = None) -> dict:
        """QuantLib Black-Scholes analytics on the Deribit snapshot (standalone)."""
        import QuantLib as ql
        if snap is None:
            snap = self.download_snapshot()
        meta = {i["instrument_name"]: i for i in snap.get("instruments", [])}
        now = int(time.time() * 1000)

        rows = []
        for s in snap.get("summary", []):
            iv = s.get("mark_iv")
            m = meta.get(s.get("instrument_name"))
            S = s.get("underlying_price")
            if iv is None or m is None or not S:
                continue
            T = (m["expiration_timestamp"] - now) / _MS_PER_YEAR
            if T <= 0:
                continue
            rows.append({
                "K": float(m["strike"]), "S": float(S), "iv": float(iv) / 100.0,
                "T": T, "type": m["option_type"], "exp": m["expiration_timestamp"],
                "mark": s.get("mark_price"),
            })
        if not rows:
            return {"ok": False, "reason": "no usable rows", "n_instruments": len(meta)}

        # nearest future expiry with enough strikes
        from collections import Counter
        # prefer the nearest expiry that is >= ~1 day out (skip the about-to-expire
        # front contract, whose smile is degenerate) and has enough strikes.
        min_T = 1.0 / 365.0
        exp_counts = Counter(r["exp"] for r in rows)
        T_by_exp = {r["exp"]: r["T"] for r in rows}
        cand = [e for e, c in exp_counts.items() if c >= 5 and T_by_exp[e] >= min_T]
        if not cand:
            cand = [e for e, c in exp_counts.items() if c >= 5]
        exp = min(cand) if cand else min(exp_counts, key=exp_counts.get)
        sel = [r for r in rows if r["exp"] == exp]
        S = sel[0]["S"]
        T = sel[0]["T"]

        # smile: IV vs log-moneyness -> slope (linear) & curvature (quadratic)
        k = np.array([np.log(r["K"] / r["S"]) for r in sel])
        ivv = np.array([r["iv"] for r in sel])
        order = np.argsort(k)
        k, ivv = k[order], ivv[order]
        slope = curv = float("nan")
        if len(k) >= 3:
            c2, c1, _ = np.polyfit(k, ivv, 2)
            curv, slope = float(2 * c2), float(c1)
        atm_iv = float(ivv[np.argmin(np.abs(k))])

        # 25-delta risk reversal via QuantLib BlackCalculator deltas
        calls, puts = [], []
        mark_err = []
        for r in sel:
            std = r["iv"] * np.sqrt(r["T"])
            otype = ql.Option.Call if r["type"] == "call" else ql.Option.Put
            try:
                calc = ql.BlackCalculator(ql.PlainVanillaPayoff(otype, r["K"]),
                                          r["S"], std, 1.0)
                d = calc.delta(r["S"])
                # model price is in coin terms (Deribit marks are coin-denominated)
                if r.get("mark") is not None:
                    mark_err.append(abs(calc.value() / r["S"] - r["mark"]))
            except Exception:
                continue
            (calls if r["type"] == "call" else puts).append((d, r["iv"]))

        def _iv_at(points, target):
            if len(points) < 2:
                return float("nan")
            pts = sorted(points, key=lambda p: p[0])
            ds = np.array([p[0] for p in pts])
            iv = np.array([p[1] for p in pts])
            return float(np.interp(target, ds, iv))

        rr25 = _iv_at(calls, 0.25) - _iv_at(puts, -0.25)
        return {
            "ok": True, "n_instruments": len(meta), "n_smile_strikes": len(sel),
            "underlying_price": float(S), "expiry_T_years": float(T),
            "atm_iv": atm_iv, "smile_slope": slope, "smile_curvature": curv,
            "rr_25delta": float(rr25),
            "model_vs_mark_mae": float(np.mean(mark_err)) if mark_err else float("nan"),
        }


# --------------------------------------------------------------------------- #
#  NO-ARG factories
# --------------------------------------------------------------------------- #
def quantum_kernel_node(name="quantum_kernel"): return QuantumKernelNode(name)
def rl_policy_node(name="rl_policy"): return RLPolicyNode(name)
def option_iv_node(name="option_iv"): return OptionIVNode(name)
