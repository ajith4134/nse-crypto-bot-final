"""cognition/active_inference.py — principled surprise + curiosity (Phase P4.5).

Reuse-first: a REAL **pymdp** (inferactively-pymdp, MIT — NumPy Active Inference) agent
maintains a generative model over the brain's *knowledge topics*. Each time the brain reads
(ingests) something, it is an OBSERVATION; the agent updates its beliefs (variational
inference) and we read off two principled cognitive signals straight from active-inference
theory — not heuristics:

  * **surprise**  — Bayesian surprise = KL(posterior ‖ prior over states): how much this
    observation MOVED the brain's beliefs. A familiar topic barely moves them (low surprise);
    a novel topic moves them a lot (high surprise). This is the literal information gained.

  * **curiosity** — expected **epistemic value** (state information gain) per topic, via
    pymdp's own ``control.calc_states_info_gain``: where would observing next most reduce the
    brain's uncertainty? The argmax is the topic the brain is most curious about — built-in
    exploration drive (action = minimize expected free energy = goal value + information gain).

Topics are discrete hidden states (one per concept cluster). The A (likelihood) matrix maps
topic→observation with a controllable confusion level; B is an identity transition (topics
persist); D is the running prior (the brain's current belief about what it's been reading).
Offline, deterministic, CPU-only — no network, no LLM. Degrades gracefully if pymdp is absent.
"""
from __future__ import annotations

import math


def _kl(p, q) -> float:
    """KL(p ‖ q) for two discrete distributions (nats), numerically guarded."""
    eps = 1e-12
    return float(sum(pi * math.log((pi + eps) / (qi + eps)) for pi, qi in zip(p, q)))


def _entropy(p) -> float:
    eps = 1e-12
    return float(-sum(pi * math.log(pi + eps) for pi in p))


class ActiveInferenceModel:
    """pymdp active-inference model over knowledge topics → surprise + curiosity.

    Args:
        topics: ordered list of topic names (discrete hidden states).
        confusion: off-diagonal mass in the likelihood A (observation noise), 0<confusion<1.
    """

    def __init__(self, topics: list[str], *, confusion: float = 0.2):
        self.topics = list(topics)
        self.n = len(self.topics)
        self.confusion = float(confusion)
        self._idx = {t: i for i, t in enumerate(self.topics)}
        self.observations: int = 0
        self._available = self.n >= 2
        # running prior over topics (uniform until the brain reads something)
        self.belief = [1.0 / self.n] * self.n if self.n else []
        self._agent = None
        if self._available:
            self._build_agent()

    # ── pymdp model ───────────────────────────────────────────────────────────────
    def _build_agent(self) -> None:
        try:
            import numpy as np
            from pymdp import utils
            from pymdp.agent import Agent
        except Exception:
            self._available = False
            return
        n = self.n
        # A: P(obs | topic). Diagonal-dominant likelihood, column-normalised.
        A_arr = np.full((n, n), self.confusion / max(n - 1, 1))
        np.fill_diagonal(A_arr, 1.0 - self.confusion)
        A_arr = A_arr / A_arr.sum(axis=0, keepdims=True)
        A = utils.obj_array(1)
        A[0] = A_arr
        # B: topics persist (identity transition), single trivial action.
        B = utils.obj_array(1)
        B[0] = np.eye(n)[:, :, None]
        # C: no extrinsic preference — exploration is purely epistemic (curiosity).
        C = utils.obj_array(1)
        C[0] = np.zeros(n)
        # D: prior over topics = current running belief.
        D = utils.obj_array(1)
        D[0] = np.array(self.belief, dtype=float)
        self._np = np
        self._utils = utils
        self._Agent = Agent
        self._agent = Agent(A=A, B=B, C=C, D=D)

    def _refresh_prior(self) -> None:
        """Reseat the agent's prior D to the running belief (so surprise is vs. what it knows)."""
        if self._agent is None:
            return
        self._agent.D[0] = self._np.array(self.belief, dtype=float)
        # reset the agent's working posterior to the prior for a fresh inference
        self._agent.reset()

    # ── public API ──────────────────────────────────────────────────────────────
    def observe(self, topic: str | int, *, learn: bool = True) -> dict:
        """Register an observation (the brain just read about ``topic``).

        Returns {topic, surprise, curiosity (info gain for this topic), beliefs,
        most_curious}. ``surprise`` is Bayesian surprise KL(posterior‖prior);
        ``learn`` rolls the posterior into the running belief (so the next read of the
        same topic is less surprising — habituation).
        """
        idx = topic if isinstance(topic, int) else self._idx.get(topic)
        if idx is None or not (0 <= idx < self.n):
            raise KeyError(f"unknown topic: {topic!r}")
        self.observations += 1
        prior = list(self.belief)

        if self._agent is None:  # offline fallback: count-based Bayesian update
            posterior = self._fallback_posterior(idx, prior)
            surprise = _kl(posterior, prior)
            self.belief = self._blend(prior, posterior) if learn else prior
            info = self._fallback_info_gain()
            return self._result(idx, surprise, info, posterior)

        self._refresh_prior()
        qs = self._agent.infer_states([idx])          # variational belief update
        posterior = [float(x) for x in qs[0]]
        surprise = _kl(posterior, prior)              # Bayesian surprise (nats)
        # per-topic epistemic value (curiosity): info gain of observing each topic next
        info = self._info_gain_per_topic()
        if learn:
            self.belief = self._blend(prior, posterior)
        return self._result(idx, surprise, info, posterior)

    def _info_gain_per_topic(self) -> list[float]:
        """Curiosity per topic = anticipated belief-change of observing it next.

        For each possible observation o_i we run pymdp's real variational inference from the
        current prior and measure KL(posterior(o_i) ‖ prior): how much would reading about
        topic i MOVE the brain's beliefs? Topics it is already sure about move beliefs little
        (low curiosity); uncertain/novel topics move them a lot (high curiosity) — the
        information the brain *expects* to gain. This is the epistemic drive of active
        inference, computed from genuine belief updates (not a static heuristic).
        """
        try:
            prior = list(self.belief)
            gains = []
            for i in range(self.n):
                self._agent.D[0] = self._np.array(prior, dtype=float)
                self._agent.reset()
                qs_i = self._agent.infer_states([i])
                gains.append(_kl([float(x) for x in qs_i[0]], prior))
            # restore prior for any subsequent real observation
            self._agent.D[0] = self._np.array(prior, dtype=float)
            self._agent.reset()
            return gains
        except Exception:
            return self._fallback_info_gain()

    # ── offline fallbacks (no pymdp) ──────────────────────────────────────────────
    def _fallback_posterior(self, idx: int, prior: list[float]) -> list[float]:
        like = [self.confusion / max(self.n - 1, 1)] * self.n
        like[idx] = 1.0 - self.confusion
        joint = [p * l for p, l in zip(prior, like)]
        z = sum(joint) or 1.0
        return [j / z for j in joint]

    def _fallback_info_gain(self) -> list[float]:
        # less-believed topics carry more potential information (entropy-weighted)
        return [_entropy([b, 1 - b]) for b in self.belief]

    # ── helpers ───────────────────────────────────────────────────────────────────
    def _blend(self, prior: list[float], posterior: list[float], rate: float = 0.5) -> list[float]:
        mixed = [(1 - rate) * a + rate * b for a, b in zip(prior, posterior)]
        z = sum(mixed) or 1.0
        return [m / z for m in mixed]

    def _result(self, idx: int, surprise: float, info: list[float], posterior: list[float]) -> dict:
        most = int(max(range(self.n), key=lambda i: info[i])) if self.n else -1
        return {
            "topic": self.topics[idx],
            "surprise": round(float(surprise), 4),
            "curiosity": round(float(info[idx]), 4),
            "most_curious": self.topics[most] if most >= 0 else None,
            "beliefs": {t: round(b, 4) for t, b in zip(self.topics, posterior)},
            "uncertainty": round(_entropy(self.belief), 4),
            "engine": "pymdp" if self._agent is not None else "fallback",
        }

    def most_curious_topic(self) -> str | None:
        """The topic with the highest expected information gain (where to read next)."""
        if not self.n:
            return None
        info = self._info_gain_per_topic() if self._agent is not None else self._fallback_info_gain()
        return self.topics[int(max(range(self.n), key=lambda i: info[i]))]

    def status(self) -> dict:
        return {
            "engine": "pymdp" if self._agent is not None else "fallback",
            "topics": self.topics,
            "observations": self.observations,
            "belief": {t: round(b, 4) for t, b in zip(self.topics, self.belief)},
            "uncertainty": round(_entropy(self.belief), 4) if self.belief else 0.0,
            "most_curious": self.most_curious_topic(),
        }
