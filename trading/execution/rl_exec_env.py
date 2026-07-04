"""AI-scientist idea #8 — order-execution environment (gymnasium) for the RL slicing agent.

Liquidate one unit of inventory over N steps while minimizing implementation shortfall under an
Almgren-Chriss-style impact model (temporary impact = per-trade slippage, permanent impact = price
drift from your own selling). A short-lived predictive ``signal`` in the observation means TIMING
matters — an agent that reads it can beat static TWAP/Almgren-Chriss schedules.

  obs    = [remaining_inventory, time_left_frac, price − arrival, signal]
  action = fraction of the REMAINING inventory to execute this step (Box[0,1]); the final step
           force-liquidates whatever is left.
  reward = (realized_price − arrival_price) · sold   (summed = negated implementation shortfall)
"""
from __future__ import annotations

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
    _HAS_GYM = True
    _Base = gym.Env
except Exception:                                    # gymnasium absent → plain base (env still usable)
    _HAS_GYM = False
    _Base = object


class ExecutionEnv(_Base):
    """Single-asset optimal-execution env (sell 1 unit over n_steps)."""

    metadata = {"render_modes": []}

    def __init__(self, n_steps: int = 10, eta: float = 0.05, gamma: float = 0.01,
                 vol: float = 0.02, signal_strength: float = 2.0, seed: int = 0):
        self.n_steps = int(n_steps)
        self.eta = float(eta)                        # temporary impact (slippage per unit sold)
        self.gamma = float(gamma)                    # permanent impact (price drift per unit sold)
        self.vol = float(vol)
        self.signal_strength = float(signal_strength)
        self._rng = np.random.default_rng(seed)
        if _HAS_GYM:
            self.observation_space = spaces.Box(low=-5.0, high=5.0, shape=(4,), dtype=np.float32)
            self.action_space = spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32)

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        self.t = 0
        self.inv = 1.0
        self.arrival = 1.0
        self.price = 1.0
        self.signal = float(self._rng.normal(0.0, 1.0))   # hints the near-future price move
        return self._obs(), {}

    def _obs(self):
        return np.array([self.inv, 1.0 - self.t / self.n_steps,
                         self.price - self.arrival, self.signal], dtype=np.float32)

    def step(self, action):
        a = float(np.clip(np.asarray(action).reshape(-1)[0], 0.0, 1.0))
        if self.t >= self.n_steps - 1:               # final step: force-liquidate
            a = 1.0
        sold = a * self.inv
        realized = self.price - self.eta * sold      # temporary impact = slippage
        reward = (realized - self.arrival) * sold    # vs arrival price (shortfall, negated)
        self.inv -= sold
        # permanent impact + noise + the (decaying) predictable signal drift
        self.price += (-self.gamma * sold + self.vol * float(self._rng.normal())
                       + self.signal_strength * self.vol * self.signal)
        self.signal *= 0.7
        self.t += 1
        done = self.t >= self.n_steps or self.inv <= 1e-9
        return self._obs(), float(reward), bool(done), False, {}


def twap_episode_reward(env: ExecutionEnv, seed: int) -> float:
    """Total reward of the TWAP baseline (sell 1/N of the ORIGINAL inventory each step)."""
    env.reset(seed=seed)
    total = 0.0
    for t in range(env.n_steps):
        # fraction of REMAINING that liquidates 1/N of the original this step
        a = 1.0 if t >= env.n_steps - 1 else (1.0 / env.n_steps) / max(env.inv, 1e-9)
        _, r, done, _, _ = env.step([a])
        total += r
        if done:
            break
    return total
