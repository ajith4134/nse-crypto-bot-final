"""CORTEX B4 — Brain hub: the meta-controller (design §1 T7).

Composes, per bar, the five things the brain hub owns:

  * jumpmodels soft regime probabilities (flap-free via the jump penalty) — condition
    every gate and the trust ledger; fall back to a volatility-tercile regime if the
    jumpmodels wheel is unavailable.
  * TrustLedger (reused from B3 core/trust.py) — AdaHedge/EXP3 per-node trust with
    BOCD run-length-collapse resets to regime priors.
  * river ADWIN per-node drift sentries — flag ONLY the neuron whose loss stream drifted.
  * frouros input-drift early warning on the feature stream (CANON-42) — fires before
    PnL degrades; optional, degrades to a river ADWIN proxy.
  * a ChaCha-style champion–challenger manager — picks the k neurons allowed to train
    online in the current regime (resource-bounded, per-regime champion memory).
  * the vendored DFA broadcaster — one realized trade-outcome error projected through
    fixed random feedback to every gate/glue layer (T6 plasticity signal 2).

Every heavy dependency is optional: missing wheels degrade to an honest lighter path,
never a crash (same pattern as nodes/active_subnet.py's Leiden fallback).
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np

from core.trust import TrustLedger
from vendor.dfa import DFABroadcaster

# ── optional heavy deps (honest fallback if a wheel is missing) ───────────────
try:
    from jumpmodels.jump import JumpModel
    _HAS_JUMP = True
except Exception:                                                    # pragma: no cover
    JumpModel = None
    _HAS_JUMP = False

try:
    from river import drift as _river_drift
    _HAS_RIVER = True
except Exception:                                                    # pragma: no cover
    _river_drift = None
    _HAS_RIVER = False

try:
    from frouros.detectors.concept_drift import ADWIN as _FrourosADWIN
    _HAS_FROUROS = True
except Exception:                                                    # pragma: no cover
    _FrourosADWIN = None
    _HAS_FROUROS = False

_REGIME_LABELS = ("bear", "range", "bull")


# ═══════════════════════════════════════════════════════════════════════════
# Regime — jumpmodels soft probabilities, flap-free
# ═══════════════════════════════════════════════════════════════════════════
class JumpRegime:
    """Flap-free soft regime probabilities over a feature matrix.

    Uses jumpmodels' statistical Jump Model — the jump penalty penalises regime
    switches so the online path does not flap bar-to-bar. Falls back to a
    volatility-tercile assignment when jumpmodels is unavailable.
    """

    def __init__(self, n_regimes: int = 3, *, jump_penalty: float = 50.0,
                 cont: bool = True, seed: int = 0):
        self.n_regimes = int(n_regimes)
        self.jump_penalty = float(jump_penalty)
        self.cont = bool(cont)
        self.seed = int(seed)
        self._model = None
        self._fitted = False
        self._last_proba = np.full(self.n_regimes, 1.0 / self.n_regimes)

    def fit(self, features: np.ndarray) -> "JumpRegime":
        X = np.asarray(features, dtype=float)
        if X.ndim != 2 or X.shape[0] < max(5, self.n_regimes):
            self._fitted = False
            return self
        if _HAS_JUMP:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    self._model = JumpModel(
                        n_components=self.n_regimes, jump_penalty=self.jump_penalty,
                        cont=self.cont, random_state=self.seed)
                    self._model.fit(X)
                self._fitted = True
                self._last_proba = self._proba_from_model(X[-1:])
                return self
            except Exception:                                        # pragma: no cover
                self._model = None
        # fallback: volatility tercile on the first feature column
        self._fit_fallback(X)
        self._fitted = True
        return self

    def _proba_from_model(self, X_row: np.ndarray) -> np.ndarray:
        try:
            if self.cont and hasattr(self._model, "predict_proba_online"):
                p = np.asarray(self._model.predict_proba_online(X_row))[-1]
            elif hasattr(self._model, "predict_proba"):
                p = np.asarray(self._model.predict_proba(X_row))[-1]
            else:                                                    # hard labels only
                lab = int(np.asarray(self._model.predict(X_row))[-1])
                p = np.eye(self.n_regimes)[lab]
            p = np.clip(p, 1e-9, None)
            return p / p.sum()
        except Exception:                                            # pragma: no cover
            return self._last_proba

    def _fit_fallback(self, X: np.ndarray) -> None:
        col = X[:, 0]
        self._edges = np.quantile(col, np.linspace(0, 1, self.n_regimes + 1)[1:-1])
        self._last_proba = self._proba_fallback(X[-1, 0])

    def _proba_fallback(self, x0: float) -> np.ndarray:
        idx = int(np.searchsorted(self._edges, x0))
        idx = min(idx, self.n_regimes - 1)
        p = np.full(self.n_regimes, 0.1)
        p[idx] = 1.0
        return p / p.sum()

    def proba_online(self, feature_row: np.ndarray) -> np.ndarray:
        """Soft regime probabilities for the newest bar."""
        row = np.asarray(feature_row, dtype=float).reshape(1, -1)
        if not self._fitted:
            return self._last_proba
        self._last_proba = (self._proba_from_model(row) if self._model is not None
                            else self._proba_fallback(row[0, 0]))
        return self._last_proba

    def label(self, proba: np.ndarray | None = None) -> str:
        p = self._last_proba if proba is None else proba
        i = int(np.argmax(p))
        return _REGIME_LABELS[i] if self.n_regimes == 3 else f"regime{i}"


# ═══════════════════════════════════════════════════════════════════════════
# Drift — per-node loss sentries + input-drift early warning
# ═══════════════════════════════════════════════════════════════════════════
class DriftSentry:
    """river ADWIN per node on its loss stream + one frouros input-drift detector."""

    def __init__(self, *, delta: float = 0.002):
        self.delta = float(delta)
        self._node: dict[str, object] = {}
        self._input = self._new_input_detector()

    def _new_node_detector(self):
        if _HAS_RIVER:
            return _river_drift.ADWIN(delta=self.delta)
        return _EwmaDrift()

    def _new_input_detector(self):
        if _HAS_FROUROS:
            try:
                return ("frouros", _FrourosADWIN())
            except Exception:                                        # pragma: no cover
                pass
        if _HAS_RIVER:
            return ("river", _river_drift.ADWIN(delta=self.delta))
        return ("ewma", _EwmaDrift())

    def update_node(self, node: str, loss: float) -> bool:
        det = self._node.get(node)
        if det is None:
            det = self._node[node] = self._new_node_detector()
        return _feed(det, float(loss))

    def update_input(self, feature_row: np.ndarray) -> bool:
        kind, det = self._input
        # summarise the input row to one scalar (mean feature magnitude) for the stream
        x = float(np.mean(np.abs(np.asarray(feature_row, dtype=float))))
        if kind == "frouros":
            det.update(value=x)
            return bool(getattr(det.status, "get", lambda *_: det.status)("drift")
                        if isinstance(det.status, dict) else det.status.get("drift", False))
        return _feed(det, x)


class _EwmaDrift:
    """Dependency-free drift fallback: |EWMA short − EWMA long| over threshold."""

    def __init__(self, fast: float = 0.3, slow: float = 0.03, thresh: float = 0.25):
        self.fast, self.slow, self.thresh = fast, slow, thresh
        self._f = self._s = None
        self.drift_detected = False

    def update(self, x: float) -> None:
        self._f = x if self._f is None else (1 - self.fast) * self._f + self.fast * x
        self._s = x if self._s is None else (1 - self.slow) * self._s + self.slow * x
        self.drift_detected = abs(self._f - self._s) > self.thresh


def _feed(det, x: float) -> bool:
    """Push one value into a river/EWMA detector; return whether it flagged drift."""
    det.update(x)
    return bool(getattr(det, "drift_detected", False))


# ═══════════════════════════════════════════════════════════════════════════
# Champion–challenger — the k neurons allowed to train online per regime
# ═══════════════════════════════════════════════════════════════════════════
class ChampionManager:
    """ChaCha-style resource-bounded champion set, remembered per regime.

    Only ``k`` neurons may train online at once. Each regime keeps its own champion
    roster; a challenger with lower windowed loss than the weakest champion is promoted.
    (FLAML's ChaCha is the reference; node-selection is implemented directly since
    AutoVW schedules hyper-configs, not neurons.)
    """

    def __init__(self, node_names, *, k: int = 4, window: int = 32):
        self.names = list(node_names)
        self.k = int(min(k, len(self.names))) if self.names else int(k)
        self.window = int(window)
        self._loss: dict[str, list[float]] = {n: [] for n in self.names}
        self._champions: dict[str, list[str]] = {}

    def _mean_loss(self, n: str) -> float:
        h = self._loss.get(n)
        return float(np.mean(h)) if h else 1.0                       # unseen = worst prior

    def observe(self, node: str, loss: float) -> None:
        h = self._loss.setdefault(node, [])
        h.append(float(np.clip(loss, 0.0, 1.0)))
        if len(h) > self.window:
            del h[: len(h) - self.window]
        if node not in self.names:
            self.names.append(node)

    def champions(self, regime: str) -> list[str]:
        """The k lowest-windowed-loss neurons for ``regime`` (sticky per regime)."""
        ranked = sorted(self.names, key=self._mean_loss)
        fresh = ranked[: self.k]
        prev = self._champions.get(regime, [])
        # sticky promotion: keep a prior champion unless a challenger genuinely beats it
        keep = [n for n in prev if n in fresh]
        for n in fresh:
            if n not in keep and len(keep) < self.k:
                keep.append(n)
        self._champions[regime] = keep
        return list(keep)


# ═══════════════════════════════════════════════════════════════════════════
# Brain hub — the composed meta-controller
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class HubDecision:
    regime_probs: np.ndarray
    regime_label: str
    trust_bias: dict                       # node -> gate prior logit
    trust: dict                            # node -> trust weight ∈ [0,1]
    drifted_nodes: list                    # nodes whose loss stream drifted
    input_drift: bool                      # feature-distribution drift early warning
    champions: list                        # k neurons allowed to train online now
    dfa_deltas: dict = field(default_factory=dict)   # node -> DFA pseudo-grad scalar


class BrainHub:
    """Per-bar meta-controller over a set of named neurons/gates."""

    def __init__(self, node_names, *, n_regimes: int = 3, jump_penalty: float = 50.0,
                 k_online: int = 4, trust_path: str | None = None, exp3: bool = False,
                 seed: int = 0):
        self.node_names = list(node_names)
        self.regime = JumpRegime(n_regimes, jump_penalty=jump_penalty, seed=seed)
        self.trust = TrustLedger(path=trust_path, exp3=exp3)
        self.sentry = DriftSentry()
        self.champion = ChampionManager(self.node_names, k=k_online)
        self.dfa = DFABroadcaster(error_dim=1, seed=seed)
        self.dfa.register_all({n: 1 for n in self.node_names})
        self._n_regimes = int(n_regimes)

    def fit_regime(self, features: np.ndarray) -> "BrainHub":
        self.regime.fit(features)
        return self

    def step(self, node_losses: dict, *, feature_row=None, trade_error: float | None = None,
             perf_signal: float | None = None) -> HubDecision:
        """Advance the hub one bar.

        node_losses : {node: realized loss ∈ [0,1]} for the just-closed bar.
        feature_row : current feature vector (drives regime probs + input drift).
        trade_error : signed realized-minus-predicted error to DFA-broadcast (optional).
        perf_signal : scalar performance stream feeding BOCD trust resets (optional).
        """
        names = sorted(set(self.node_names) | set(node_losses))

        # 1. trust + per-node drift sentries from realized losses
        drifted = []
        for n, loss in node_losses.items():
            self.trust.update(n, loss)
            self.champion.observe(n, loss)
            if self.sentry.update_node(n, loss):
                drifted.append(n)

        # 2. BOCD trust reset toward regime priors on performance-stream collapse
        if perf_signal is not None:
            self.trust.observe_regime_signal(float(perf_signal))

        # 3. regime probabilities + input-drift early warning
        if feature_row is not None:
            probs = self.regime.proba_online(feature_row)
            input_drift = self.sentry.update_input(feature_row)
        else:
            probs = self.regime._last_proba
            input_drift = False
        label = self.regime.label(probs)

        # 4. DFA broadcast of the realized trade-outcome error to every gate
        dfa_deltas = {}
        if trade_error is not None:
            for n in names:
                self.dfa.register(n, 1)
            dfa_deltas = {n: float(v[0]) for n, v in
                          self.dfa.broadcast(trade_error).items()}

        # 5. which neurons may train online this regime
        champions = self.champion.champions(label)

        bias = self.trust.bias_vector(names)
        return HubDecision(
            regime_probs=np.asarray(probs, dtype=float),
            regime_label=label,
            trust_bias={n: float(b) for n, b in zip(names, bias)},
            trust={n: self.trust.trust(n) for n in names},
            drifted_nodes=drifted,
            input_drift=bool(input_drift),
            champions=champions,
            dfa_deltas=dfa_deltas,
        )

    def status(self) -> dict:
        return {
            "regimes": self._n_regimes,
            "regime_label": self.regime.label(),
            "regime_probs": [round(float(x), 4) for x in self.regime._last_proba],
            "trust": self.trust.snapshot(),
            "champions_by_regime": self.champion._champions,
            "backends": {
                "jumpmodels": _HAS_JUMP, "river": _HAS_RIVER, "frouros": _HAS_FROUROS,
            },
        }
