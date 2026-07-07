"""trading/rl/exec_policy.py — W6 RL execution-policy (PPO over a trade-spec action space).

Owner goal 2026-07-07 (video vp2): a gym environment where the ACTION is a complete
trade specification — no-trade, or (direction, stop-loss, take-profit) from an
ATR-scaled menu — and the REWARD is the realized PnL of that decision. The risk
parameters are LEARNED, not fixed. vp2's honesty rule is enforced: when one candle
touches both the stop and the target (no tick data — order unknowable), the trade
counts as a LOSS ("so we don't cheat our way around").

Pieces:
  TradingExecEnv   — gymnasium.Env over an OHLCV frame; observation = a window of
                     scale-free features (returns, range/ATR, volume z, RSI);
                     Discrete(1 + 2·|SL|·|TP|) actions; strict no-lookahead stepping.
  train_policy()   — PPO (stable-baselines3, CPU) with a strict train/holdout split
                     (holdout = the LAST fraction, never seen in training); saves the
                     model + honest metrics (train vs holdout equity — vp2's
                     overfitting lesson made visible, never hidden).
  latest_signal()  — the trained policy's trade spec for the newest window.
  RLExecPolicyNode — NodeProtocol face for the cortex (paper-only, advisory).

Data honors UI-only mode via data_failsafe (training is a batch job on stored candles).
"""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

import numpy as np

from trading import state

_SL_MULTS = (1.0, 1.5, 2.0)          # stop distance in ATRs
_TP_MULTS = (1.5, 2.5, 4.0)          # target distance in ATRs
_WINDOW = 32
_TIME_BARRIER = 24                    # bars before a forced flat exit
_FEE_PCT = 0.0005                     # per side (taker-ish), keeps rewards honest


def _feat(ohlcv: np.ndarray) -> np.ndarray:
    """Scale-free features per bar: log-return, (high-low)/close, close-position-in-range,
    volume z-score (rolling), RSI(14)/100. ohlcv columns: ts,o,h,l,c,v."""
    c = ohlcv[:, 4]
    h, low, v = ohlcv[:, 2], ohlcv[:, 3], ohlcv[:, 5]
    ret = np.zeros(len(c))
    ret[1:] = np.diff(np.log(np.maximum(c, 1e-12)))
    rng = (h - low) / np.maximum(c, 1e-12)
    pos = (c - low) / np.maximum(h - low, 1e-12)
    vz = np.zeros(len(v))
    for i in range(len(v)):
        w = v[max(0, i - 20):i + 1]
        sd = w.std() or 1.0
        vz[i] = (v[i] - w.mean()) / sd
    delta = np.diff(c, prepend=c[0])
    up = np.where(delta > 0, delta, 0.0)
    dn = np.where(delta < 0, -delta, 0.0)

    def _ema(x, n=14):
        out = np.zeros_like(x)
        a = 2.0 / (n + 1)
        for i, xv in enumerate(x):
            out[i] = xv if i == 0 else a * xv + (1 - a) * out[i - 1]
        return out
    rs = _ema(up) / np.maximum(_ema(dn), 1e-12)
    rsi = 100 - 100 / (1 + rs)
    return np.column_stack([ret, rng, pos, np.clip(vz, -4, 4) / 4.0, rsi / 100.0])


def _atr(ohlcv: np.ndarray, n: int = 14) -> np.ndarray:
    h, low, c = ohlcv[:, 2], ohlcv[:, 3], ohlcv[:, 4]
    prev_c = np.roll(c, 1)
    prev_c[0] = c[0]
    tr = np.maximum(h - low, np.maximum(abs(h - prev_c), abs(low - prev_c)))
    out = np.zeros_like(tr)
    a = 2.0 / (n + 1)
    for i, x in enumerate(tr):
        out[i] = x if i == 0 else a * x + (1 - a) * out[i - 1]
    return out


import gymnasium as _gym


class TradingExecEnv(_gym.Env):
    """gymnasium.Env: one episode walks the frame; each step decides ONE trade (or skip)."""

    metadata: dict = {}

    def __init__(self, ohlcv: np.ndarray, window: int = _WINDOW):
        import gymnasium as gym
        super().__init__()
        self.ohlcv = np.asarray(ohlcv, dtype=float)
        self.window = window
        self.feats = _feat(self.ohlcv)
        self.atr = _atr(self.ohlcv)
        self.action_map = [None] + [(d, sl, tp) for d in (1, -1)
                                    for sl in _SL_MULTS for tp in _TP_MULTS]
        self.action_space = gym.spaces.Discrete(len(self.action_map))
        self.observation_space = gym.spaces.Box(-np.inf, np.inf,
                                                shape=(window * self.feats.shape[1],),
                                                dtype=np.float32)
        self.i = window
        self.equity = 1.0
        self.trades: list[dict] = []

    # gymnasium API ---------------------------------------------------------------
    def reset(self, *, seed=None, options=None):
        self.i = self.window
        self.equity = 1.0
        self.trades = []
        return self._obs(), {}

    def _obs(self):
        w = self.feats[self.i - self.window:self.i]
        return w.astype(np.float32).ravel()

    def step(self, action: int):
        spec = self.action_map[int(action)]
        reward = 0.0
        if spec is not None:
            reward = self._simulate(spec)
            self.equity *= (1.0 + reward)
        # skip forward: past the trade's bars (or one bar on skip) — no lookahead reuse
        self.i += 1 if spec is None else max(1, self._last_bars)
        done = self.i >= len(self.ohlcv) - 1
        return (self._obs() if not done else
                np.zeros_like(self._obs())), float(reward), done, False, \
            {"equity": self.equity}

    # trade simulation (vp2 rules) --------------------------------------------------
    def _simulate(self, spec) -> float:
        d, slm, tpm = spec
        entry = self.ohlcv[self.i, 4]                   # decide on close of bar i
        atr = self.atr[self.i] or entry * 0.005
        stop = entry - d * slm * atr
        target = entry + d * tpm * atr
        self._last_bars = 1
        for j in range(self.i + 1, min(self.i + 1 + _TIME_BARRIER,
                                       len(self.ohlcv))):
            h, low, c = self.ohlcv[j, 2], self.ohlcv[j, 3], self.ohlcv[j, 4]
            self._last_bars = j - self.i
            hit_stop = (low <= stop) if d > 0 else (h >= stop)
            hit_tp = (h >= target) if d > 0 else (low <= target)
            if hit_stop and hit_tp:
                # vp2 HONESTY RULE: both touched in one candle → count it a LOSS.
                return d * (stop - entry) / entry - 2 * _FEE_PCT
            if hit_stop:
                return d * (stop - entry) / entry - 2 * _FEE_PCT
            if hit_tp:
                return d * (target - entry) / entry - 2 * _FEE_PCT
        exitp = self.ohlcv[min(self.i + _TIME_BARRIER, len(self.ohlcv) - 1), 4]
        return d * (exitp - entry) / entry - 2 * _FEE_PCT

    def run_deterministic(self, model) -> dict:
        """Evaluate a trained policy on THIS env's data. Honest equity + trade stats."""
        obs, _ = self.reset()
        wins = losses = 0
        done = False
        while not done:
            action, _s = model.predict(obs, deterministic=True)
            spec = self.action_map[int(action)]
            obs, r, done, _t, info = self.step(action)
            if spec is not None:
                wins, losses = wins + (r > 0), losses + (r <= 0)
        n = wins + losses
        return {"equity": round(self.equity, 6), "n_trades": int(n),
                "win_rate": round(wins / n, 4) if n else None}


_DIR = Path(state.STATE_DIR) / "rl_exec"


def train_policy(ohlcv, *, timesteps: int = 20000, holdout_frac: float = 0.25,
                 tag: str = "default") -> dict:
    """PPO on the first (1-holdout) of the frame; honest eval on BOTH splits."""
    from stable_baselines3 import PPO
    arr = np.asarray(ohlcv, dtype=float)
    if len(arr) < _WINDOW * 3:
        return {"ok": False, "error": f"need >= {_WINDOW * 3} bars, got {len(arr)}"}
    cut = int(len(arr) * (1 - holdout_frac))
    env_tr = TradingExecEnv(arr[:cut])
    model = PPO("MlpPolicy", env_tr, verbose=0, seed=0,
                n_steps=256, batch_size=64, device="cpu")
    t0 = time.time()
    model.learn(total_timesteps=int(timesteps), progress_bar=False)
    train_eval = TradingExecEnv(arr[:cut]).run_deterministic(model)
    holdout_eval = TradingExecEnv(arr[cut:]).run_deterministic(model)
    _DIR.mkdir(parents=True, exist_ok=True)
    model.save(str(_DIR / f"ppo_{tag}"))
    out = {"ok": True, "tag": tag, "timesteps": int(timesteps),
           "train": train_eval, "holdout": holdout_eval,
           "overfit_gap": round(train_eval["equity"] - holdout_eval["equity"], 6),
           "trained_s": round(time.time() - t0, 1), "bars": len(arr),
           "ts": time.time()}
    meta = state.load_json("rl_exec_meta.json", {})
    meta[tag] = out
    state.save_json("rl_exec_meta.json", meta)
    return out


def latest_signal(ohlcv, *, tag: str = "default") -> dict:
    """The trained policy's trade spec for the newest window. Honest 'untrained' when
    no model exists; advisory only (paper) — execution stays with the funnel/APIs."""
    path = _DIR / f"ppo_{tag}.zip"
    if not path.exists():
        return {"available": False, "reason": "no trained policy"}
    from stable_baselines3 import PPO
    arr = np.asarray(ohlcv, dtype=float)
    if len(arr) < _WINDOW + 2:
        return {"available": False, "reason": "window too short"}
    env = TradingExecEnv(arr)
    env.i = len(arr) - 1
    model = PPO.load(str(path), device="cpu")
    action, _ = model.predict(env._obs(), deterministic=True)
    spec = env.action_map[int(action)]
    if spec is None:
        return {"available": True, "action": "no-trade"}
    d, slm, tpm = spec
    return {"available": True, "action": "long" if d > 0 else "short",
            "sl_atr_mult": slm, "tp_atr_mult": tpm}


class RLExecPolicyNode:
    """NodeProtocol face: P(policy-favors-long) for the cortex; advisory, paper-only."""
    name = "rl_exec_policy"
    kind = "rl"
    summary = "PPO execution policy: learned (direction, SL, TP) trade specs (vp2 design)"
    task = "binary"
    head = "y"

    def __init__(self, tag: str = "default"):
        from core.node_protocol import IOSchema
        self.tag = tag
        self.schema = IOSchema(1, "market context", "p(long per trained exec policy)")

    def fit(self, X, y):
        return self

    def predict_proba(self, X):
        meta = (state.load_json("rl_exec_meta.json", {}) or {}).get(self.tag) or {}
        hold = (meta.get("holdout") or {})
        eq = hold.get("equity")
        p = 0.5 if eq is None else float(1 / (1 + math.exp(-4 * (eq - 1.0))))
        n = len(X) if hasattr(X, "__len__") else 1
        return [p] * n


def register_rl_exec(tag: str = "default"):
    """Self-register on the live node registry (dashboard-sync). Idempotent."""
    node = RLExecPolicyNode(tag)
    try:
        from core import registry
        registry.register(node, summary=node.summary)
    except Exception:
        pass
    return node
