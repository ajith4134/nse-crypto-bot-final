"""AI-scientist idea #8 — RL execution agent (SB3-PPO order slicing over ExecutionEnv).

Learns a slicing policy that minimizes implementation shortfall by reading the short-lived
predictive signal — beyond a static TWAP / closed-form Almgren-Chriss schedule. Execution cost is
often the whole edge, so a learned slicer that beats TWAP is real alpha on the cost side.

Reuse-first: Stable-Baselines3 PPO (the standard, well-tested on-policy RL implementation) over the
gymnasium ``ExecutionEnv``. Degrades honestly: if SB3/gymnasium is absent, ``available`` is False and
``plan()`` returns the TWAP schedule (never a fake RL result).
"""
from __future__ import annotations

import numpy as np

from trading.execution.rl_exec_env import ExecutionEnv, twap_episode_reward

try:
    from stable_baselines3 import PPO
    _HAS_SB3 = True
except Exception:
    _HAS_SB3 = False


class RLExecutionAgent:
    """Trains an SB3-PPO slicing policy over ExecutionEnv; plans schedules; benchmarks vs TWAP."""

    def __init__(self, n_steps: int = 10, eta: float = 0.05, gamma: float = 0.01,
                 vol: float = 0.02, seed: int = 0):
        self.n_steps = int(n_steps)
        self.params = dict(n_steps=n_steps, eta=eta, gamma=gamma, vol=vol)
        self.seed = int(seed)
        self._model = None
        self.trained = False

    @property
    def available(self) -> bool:
        return _HAS_SB3

    def _env(self, seed=None):
        return ExecutionEnv(seed=self.seed if seed is None else seed, **self.params)

    def train(self, total_timesteps: int = 6000):
        if not _HAS_SB3:
            return self
        env = self._env()
        self._model = PPO("MlpPolicy", env, seed=self.seed, verbose=0,
                          n_steps=256, batch_size=64, gae_lambda=0.95, ent_coef=0.0)
        self._model.learn(total_timesteps=int(total_timesteps))
        self.trained = True
        return self

    def _policy_action(self, obs):
        if self._model is None:                       # untrained → TWAP-equivalent heuristic
            inv, tleft = float(obs[0]), float(obs[1])
            steps_left = max(1, round(tleft * self.n_steps))
            return (1.0 / self.n_steps) / max(inv, 1e-9) if steps_left > 1 else 1.0
        a, _ = self._model.predict(np.asarray(obs, np.float32), deterministic=True)
        return float(np.clip(np.asarray(a).reshape(-1)[0], 0.0, 1.0))

    def plan(self, seed: int = 123) -> dict:
        """Roll out the (deterministic) policy → the per-step slicing schedule + realized shortfall."""
        env = self._env(seed=seed)
        obs, _ = env.reset(seed=seed)
        schedule, total = [], 0.0
        for _ in range(self.n_steps):
            a = self._policy_action(obs)
            sold_frac_of_remaining = 1.0 if env.t >= env.n_steps - 1 else a
            schedule.append(round(sold_frac_of_remaining * env.inv, 4))   # frac of ORIGINAL sold now
            obs, r, done, _, _ = env.step([a])
            total += r
            if done:
                break
        return {"schedule": schedule, "reward": round(total, 6), "trained": self.trained}

    def compare_to_twap(self, episodes: int = 40) -> dict:
        """Average episode reward of the learned policy vs TWAP over the SAME seeds (paired)."""
        rl, tw = [], []
        for i in range(episodes):
            seed = 1000 + i
            env = self._env(seed=seed)
            obs, _ = env.reset(seed=seed)
            tot = 0.0
            for _ in range(self.n_steps):
                obs, r, done, _, _ = env.step([self._policy_action(obs)])
                tot += r
                if done:
                    break
            rl.append(tot)
            tw.append(twap_episode_reward(self._env(seed=seed), seed=seed))
        rl_m, tw_m = float(np.mean(rl)), float(np.mean(tw))
        return {"rl_mean_reward": round(rl_m, 6), "twap_mean_reward": round(tw_m, 6),
                "rl_beats_twap": rl_m >= tw_m, "edge": round(rl_m - tw_m, 6),
                "episodes": episodes, "trained": self.trained}
