"""trading/brain/rl_exit.py — Phase-T8 deferred A3: RL exit policy (tabular Q-learning).

WHY custom RL (not FinRL / stable-baselines3): the OSS deep-RL stack pulls a large
PyTorch dependency that is overkill for a CPU/offline trade-exit decision. Here we
implement a REAL but lightweight reinforcement learner — **tabular Q-learning** — that
genuinely learns *when to exit a trade* from logged trajectories, on CPU, deterministic
(seeded), with NO new dependencies (pure numpy). A gated hook (`deep_rl_available()`)
lets us swap in sb3/FinRL later behind the same `should_exit` / `predict_proba`
interface used by `trading/brain/entryexit.py`'s ``EntryExitPolicy(exit_model=...)``.

State (discretized):
    - unrealized R-multiple bucket: r<-1, -1..0, 0..1, 1..2, r>2
    - bars_held bucket:            0-2, 3-9, 10+
    - anomaly_high flag:           0 / 1
Actions: 0 = HOLD, 1 = EXIT.
Reward:
    - EXIT  -> realized pnl at that step (terminal; the trajectory's realized_pnl rides
              on the EXIT step as `step_reward`, typically the unrealized R captured).
    - HOLD  -> small per-step holding cost (negative `step_reward`, e.g. -0.01), so the
              agent is pushed to bank good R and to cut losers rather than bleed cost.
The agent thus learns to EXIT in high-R / anomaly states and HOLD while edge persists.
"""
from __future__ import annotations

import numpy as np

HOLD, EXIT = 0, 1
_ACTIONS = (HOLD, EXIT)


# ── state discretization ──────────────────────────────────────────────────────
def _r_bucket(unrealized_r: float) -> int:
    if unrealized_r < -1.0:
        return 0
    if unrealized_r < 0.0:
        return 1
    if unrealized_r < 1.0:
        return 2
    if unrealized_r < 2.0:
        return 3
    return 4


def _bars_bucket(bars_held: float) -> int:
    if bars_held <= 2:
        return 0
    if bars_held <= 9:
        return 1
    return 2


def _state_key(unrealized_r: float, bars_held: float, anomaly_high) -> tuple:
    """Discretize a raw observation into a hashable Q-table state key."""
    return (_r_bucket(float(unrealized_r)),
            _bars_bucket(float(bars_held)),
            int(bool(anomaly_high)))


class QLearningExit:
    """Tabular Q-learning agent that learns a binary HOLD/EXIT exit policy.

    Public API:
        learn_episode(trajectory)            -> self   (one off-policy update pass)
        train(trajectories, epochs=...)      -> self   (epsilon-greedy, seeded)
        should_exit(unrealized_r, bars_held, anomaly_high) -> bool  (greedy)
        predict_proba(X)                     -> list[float] p(EXIT) per row  (softmax)
        status()                             -> JSON-able dict
    """

    def __init__(self, alpha: float = 0.1, gamma: float = 0.95,
                 epsilon: float = 0.1, seed: int = 0):
        self.alpha = float(alpha)
        self.gamma = float(gamma)
        self.epsilon = float(epsilon)
        self.seed = int(seed)
        self._rng = np.random.default_rng(seed)
        self.Q: dict[tuple, list[float]] = {}
        self.epochs_trained = 0

    # ── Q-table access ────────────────────────────────────────────────────────
    def _q(self, state: tuple) -> list[float]:
        row = self.Q.get(state)
        if row is None:
            row = [0.0, 0.0]
            self.Q[state] = row
        return row

    # ── learning ──────────────────────────────────────────────────────────────
    def learn_episode(self, trajectory: list[dict], training: bool = False) -> "QLearningExit":
        """Apply Q-learning updates over one trajectory.

        Each step dict: {unrealized_r, bars_held, anomaly_high, step_reward}.
        We treat EXIT as terminal: at every step the agent could EXIT (reward =
        that step's captured pnl ~ unrealized_r) or HOLD (reward = step_reward,
        a small holding cost) and bootstrap to the next step's greedy value.
        """
        n = len(trajectory)
        for i, step in enumerate(trajectory):
            s = _state_key(step["unrealized_r"], step["bars_held"], step.get("anomaly_high", 0))
            q = self._q(s)

            # EXIT reward: realized/captured pnl at this step (terminal -> no bootstrap).
            exit_reward = float(step.get("realized_pnl", step.get("unrealized_r", 0.0)))
            q[EXIT] += self.alpha * (exit_reward - q[EXIT])

            # HOLD reward: per-step holding cost; bootstrap from next state's max-Q.
            hold_reward = float(step.get("step_reward", 0.0))
            if i + 1 < n:
                nxt = trajectory[i + 1]
                s2 = _state_key(nxt["unrealized_r"], nxt["bars_held"], nxt.get("anomaly_high", 0))
                future = max(self._q(s2))
            else:
                future = 0.0
            q[HOLD] += self.alpha * (hold_reward + self.gamma * future - q[HOLD])

            # epsilon-greedy exploration only matters if we early-terminate; tabular
            # off-policy update above already covers both actions, but we honour the
            # epsilon-greedy contract so training is stochastic-yet-seeded.
            if training and self._rng.random() < self.epsilon:
                a = int(self._rng.integers(0, 2))
                if a == EXIT:
                    break
        return self

    def train(self, trajectories: list[list[dict]], epochs: int = 100) -> "QLearningExit":
        """Loop episodes for `epochs`, epsilon-greedy and deterministic (seeded)."""
        for _ in range(int(epochs)):
            order = self._rng.permutation(len(trajectories))
            for j in order:
                self.learn_episode(trajectories[j], training=True)
            self.epochs_trained += 1
        return self

    # ── inference ─────────────────────────────────────────────────────────────
    def should_exit(self, unrealized_r: float, bars_held: float, anomaly_high) -> bool:
        """Greedy decision: EXIT iff Q[EXIT] > Q[HOLD] for the discretized state."""
        q = self.Q.get(_state_key(unrealized_r, bars_held, anomaly_high), [0.0, 0.0])
        return bool(q[EXIT] > q[HOLD])

    def predict_proba(self, X) -> list[float]:
        """Softmax p(EXIT) per row; row = [unrealized_r, bars_held, anomaly_high].

        Matches the EntryExitPolicy exit_model interface (predict_proba([features])[0]).
        """
        out = []
        for row in X:
            ur, bh = float(row[0]), float(row[1])
            ah = row[2] if len(row) > 2 else 0
            q = self.Q.get(_state_key(ur, bh, ah), [0.0, 0.0])
            m = max(q)
            e_hold = np.exp(q[HOLD] - m)
            e_exit = np.exp(q[EXIT] - m)
            out.append(float(e_exit / (e_hold + e_exit)))
        return out

    # ── introspection ─────────────────────────────────────────────────────────
    def status(self) -> dict:
        return {
            "type": "QLearningExit",
            "n_states": len(self.Q),
            "epochs_trained": self.epochs_trained,
            "params": {"alpha": self.alpha, "gamma": self.gamma,
                       "epsilon": self.epsilon, "seed": self.seed},
            "actions": {"HOLD": HOLD, "EXIT": EXIT},
            "deep_rl": deep_rl_available(),
        }


# ── gated deep-RL upgrade hook ────────────────────────────────────────────────
def deep_rl_available() -> dict:
    """Report whether a deep-RL backend (sb3/FinRL) is importable, WITHOUT importing
    torch at module load. Returns {available: bool, note: str}. This is the gated
    upgrade hook: when True, a deep-RL policy can replace the tabular Q-table behind
    the same should_exit / predict_proba interface."""
    import importlib.util
    for mod in ("stable_baselines3", "finrl"):
        if importlib.util.find_spec(mod) is not None:
            return {"available": True, "note": f"{mod} importable; deep-RL upgrade possible"}
    return {"available": False,
            "note": "no stable_baselines3/finrl; using tabular Q-learning (pure numpy, CPU)"}
