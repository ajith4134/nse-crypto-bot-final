"""trading/brain/worldmodel.py — learned market world-model + imagination planner.

THE missing brain capability (see research/brain-stitch-gap-map.md): "imagine before
acting". Adapted reuse-first from MuZero (vendor/muzero_general): its **MCTS** search
(`Node`/`MinMaxStats`/`ucb_score`/`backpropagate`) and its **learned dynamics** idea
(representation→dynamics→prediction). We keep the algorithm faithful but make it
CPU-first and trading-shaped:

  - MarketWorldModel  : a LEARNED forward model of market dynamics in feature space —
                        transition T(f_t)->f_{t+1} and a next-return head g(f_t)->r.
                        torch backend (MuZero-style MLPs, scalar value/reward) when
                        torch is installed; numpy ridge-regression fallback otherwise
                        (never-skip — imagination works either way).
  - ImaginationPlanner: MuZero MCTS that rolls the world model forward over a TRADE
                        action set {HOLD, ENTER_LONG, ENTER_SHORT, EXIT, TIGHTEN_STOP,
                        SCALE_OUT}, scoring entry/direction/stoploss/profit-trailing in
                        imagined R-multiples BEFORE acting. Returns the best action, the
                        imagined trajectory, the visit-count policy and predicted R.
  - WorldModelNode    : NodeProtocol face so the planner lives in the node network /
                        registry / dashboard. predict_proba = P(next-return > 0).

Inputs:  feature vectors (one row per bar) + OHLCV frames for dynamics fitting.
Outputs: imagined plans (dict) and class-1 (up) probabilities (Vector).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from core.node_protocol import BaseNode, IOSchema

try:                                    # heavy-OK-if-it-wins, but never blocking
    import torch
    import torch.nn as _nn
    _HAS_TORCH = True
except Exception:                       # pragma: no cover - exercised when torch absent
    _HAS_TORCH = False

# ---- trade action space (the planner's "moves") ------------------------------
HOLD, ENTER_LONG, ENTER_SHORT, EXIT, TIGHTEN_STOP, SCALE_OUT = range(6)
ACTION_NAMES = ["HOLD", "ENTER_LONG", "ENTER_SHORT", "EXIT", "TIGHTEN_STOP", "SCALE_OUT"]
N_ACTIONS = len(ACTION_NAMES)

FEATURE_DIM = 8  # observation features built from an OHLCV window (see market_features)


# ============================================================================ #
#  Observation features — OHLCV window -> a compact numeric state vector        #
# ============================================================================ #
def market_features(ohlcv: pd.DataFrame) -> np.ndarray:
    """Last-bar feature vector (length FEATURE_DIM) describing market state.

    Pure numpy/pandas so it never couples to the heavier strategy feature stack.
    Features: r1, mean(r5), mean(r20), vol20, rsi14_norm, mom10, px/sma20-1, atr/px.
    """
    rows = _feature_matrix(ohlcv)
    return rows[-1] if len(rows) else np.zeros(FEATURE_DIM, dtype=float)


def _feature_matrix(ohlcv: pd.DataFrame) -> np.ndarray:
    """Per-bar feature rows for the whole frame (used to FIT the dynamics)."""
    if ohlcv is None or len(ohlcv) < 25:
        return np.zeros((0, FEATURE_DIM), dtype=float)
    close = pd.to_numeric(ohlcv["close"], errors="coerce").astype(float)
    high = pd.to_numeric(ohlcv.get("high", close), errors="coerce").astype(float)
    low = pd.to_numeric(ohlcv.get("low", close), errors="coerce").astype(float)
    logret = np.log(close).diff()
    r1 = logret
    r5 = logret.rolling(5).mean()
    r20 = logret.rolling(20).mean()
    vol20 = logret.rolling(20).std()
    delta = close.diff()
    up = delta.clip(lower=0).rolling(14).mean()
    dn = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    rsi_norm = (rsi - 50) / 50
    mom10 = close / close.shift(10) - 1
    sma20 = close.rolling(20).mean()
    px_sma = close / sma20 - 1
    tr = (high - low).abs()
    atr = tr.rolling(14).mean()
    atr_px = atr / close
    mat = np.column_stack([r1, r5, r20, vol20, rsi_norm, mom10, px_sma, atr_px])
    mat = np.nan_to_num(mat, nan=0.0, posinf=0.0, neginf=0.0)
    return mat[24:]  # drop warmup rows


# ============================================================================ #
#  MarketWorldModel — the LEARNED dynamics (torch backend + numpy fallback)     #
# ============================================================================ #
class MarketWorldModel:
    """Learns market dynamics in feature space: T(f)->f' and g(f)->next log-return.

    This is the "world model": once fit, `step(f)` imagines the next state + the
    market's next-period return without touching live data. The planner rolls this
    forward many steps to test trade actions. `atr_px` (feature 7) supplies the
    volatility used for stop placement, so stoploss learning is grounded in the model.
    """

    def __init__(self, encoding_size: int = 16, seed: int = 0):
        self.encoding_size = encoding_size
        self.seed = seed
        self.fitted = False
        self._backend = "untrained"
        self._mu = np.zeros(FEATURE_DIM)
        self._sd = np.ones(FEATURE_DIM)
        # numpy fallback params (ridge):  f' = f @ Wt + bt ;  ret = f @ wr + br
        self._Wt = np.eye(FEATURE_DIM)
        self._bt = np.zeros(FEATURE_DIM)
        self._wr = np.zeros(FEATURE_DIM)
        self._br = 0.0
        self._torch = None

    # ---- fitting -----------------------------------------------------------
    def fit(self, ohlcv: pd.DataFrame) -> "MarketWorldModel":
        """Fit transition + return heads from a single OHLCV history."""
        X = _feature_matrix(ohlcv)
        if len(X) < 30:
            return self
        self._mu, self._sd = X.mean(0), X.std(0) + 1e-8
        Z = (X - self._mu) / self._sd
        f, f_next = Z[:-1], Z[1:]
        ret_next = X[1:, 0]                     # next-bar log-return (raw feature r1)
        if _HAS_TORCH:
            self._fit_torch(f, f_next, ret_next)
            self._backend = "torch"
        else:
            self._fit_numpy(f, f_next, ret_next)
            self._backend = "numpy"
        self.fitted = True
        return self

    def _fit_numpy(self, f, f_next, ret_next, ridge: float = 1.0):
        A = np.hstack([f, np.ones((len(f), 1))])
        G = A.T @ A + ridge * np.eye(A.shape[1])
        Wt_full = np.linalg.solve(G, A.T @ f_next)       # (d+1, d)
        self._Wt, self._bt = Wt_full[:-1], Wt_full[-1]
        wr_full = np.linalg.solve(G, A.T @ ret_next)     # (d+1,)
        self._wr, self._br = wr_full[:-1], float(wr_full[-1])

    def _fit_torch(self, f, f_next, ret_next, epochs: int = 150):
        torch.manual_seed(self.seed)
        d, e = FEATURE_DIM, self.encoding_size
        # representation f->h, dynamics h->h', heads h->(ret, value) — MuZero-shaped.
        self._repr = _nn.Sequential(_nn.Linear(d, e), _nn.Tanh())
        self._dyn = _nn.Sequential(_nn.Linear(e, e), _nn.Tanh(), _nn.Linear(e, e))
        self._dec = _nn.Linear(e, d)                     # h' -> next feature (for grounding)
        self._ret_head = _nn.Linear(e, 1)                # h -> next return
        params = (list(self._repr.parameters()) + list(self._dyn.parameters())
                  + list(self._dec.parameters()) + list(self._ret_head.parameters()))
        opt = torch.optim.Adam(params, lr=1e-2)
        ft = torch.tensor(f, dtype=torch.float32)
        fnt = torch.tensor(f_next, dtype=torch.float32)
        rt = torch.tensor(ret_next, dtype=torch.float32).unsqueeze(1)
        lossf = _nn.MSELoss()
        for _ in range(epochs):
            opt.zero_grad()
            h = self._repr(ft)
            hn = self._dyn(h)
            loss = lossf(self._dec(hn), fnt) + lossf(self._ret_head(h), rt)
            loss.backward()
            opt.step()
        self._torch = True
        for m in (self._repr, self._dyn, self._dec, self._ret_head):
            m.eval()

    # ---- one imagined step -------------------------------------------------
    def step(self, f_norm: np.ndarray) -> tuple[np.ndarray, float]:
        """Imagine one step: (normalized features) -> (next normalized features, next return)."""
        if self._backend == "torch" and self._torch:
            with torch.no_grad():
                h = self._repr(torch.tensor(f_norm, dtype=torch.float32))
                hn = self._dyn(h)
                f_next = self._dec(hn).numpy()
                ret = float(self._ret_head(h).item())
            return f_next, ret
        # numpy ridge fallback
        f_next = f_norm @ self._Wt + self._bt
        ret = float(f_norm @ self._wr + self._br)
        return f_next, ret

    def normalize(self, f_raw: np.ndarray) -> np.ndarray:
        return (f_raw - self._mu) / self._sd

    def atr_px_of(self, f_norm: np.ndarray) -> float:
        """Recover atr/price (feature 7) from a normalized state for stop sizing."""
        return float(abs(f_norm[7] * self._sd[7] + self._mu[7])) or 0.01


# ============================================================================ #
#  MCTS — adapted from vendor/muzero_general/self_play.py (single-player)       #
# ============================================================================ #
class _MinMax:
    def __init__(self):
        self.maximum, self.minimum = -math.inf, math.inf

    def update(self, v):
        self.maximum, self.minimum = max(self.maximum, v), min(self.minimum, v)

    def normalize(self, v):
        if self.maximum > self.minimum:
            return (v - self.minimum) / (self.maximum - self.minimum)
        return v


class _MCTSNode:
    """One search node — carries the imagined (world-state, position-state)."""
    def __init__(self, prior: float):
        self.visit_count = 0
        self.prior = prior
        self.value_sum = 0.0
        self.reward = 0.0
        self.children: dict[int, "_MCTSNode"] = {}
        self.state = None          # (f_norm, PositionState, price)

    def expanded(self) -> bool:
        return len(self.children) > 0

    def value(self) -> float:
        return 0.0 if self.visit_count == 0 else self.value_sum / self.visit_count


@dataclass
class PositionState:
    """The imagined trade book the planner manages while rolling forward."""
    side: int = 0          # +1 long, -1 short, 0 flat
    entry: float = 0.0
    stop: float = 0.0
    size: float = 0.0
    realized_R: float = 0.0
    risk: float = 0.0      # initial risk in price units (1R)

    def copy(self) -> "PositionState":
        return PositionState(self.side, self.entry, self.stop, self.size,
                             self.realized_R, self.risk)


# ============================================================================ #
#  ImaginationPlanner — MuZero search over trade actions through the model      #
# ============================================================================ #
@dataclass
class ImaginationPlanner:
    model: MarketWorldModel
    num_simulations: int = 40
    horizon: int = 12
    discount: float = 0.98
    pb_c_base: float = 19652.0
    pb_c_init: float = 1.25
    stop_atr_mult: float = 1.5
    cost: float = 0.0005          # per round-trip imagined cost in R-fraction
    seed: int = 0

    def __post_init__(self):
        self._rng = np.random.default_rng(self.seed)

    # ---- legal actions given a position ------------------------------------
    def _legal(self, pos: PositionState) -> list[int]:
        if pos.side == 0:
            return [HOLD, ENTER_LONG, ENTER_SHORT]
        return [HOLD, EXIT, TIGHTEN_STOP, SCALE_OUT]

    # ---- apply action + advance the world one imagined step -----------------
    def _transition(self, state, action):
        f_norm, pos, price = state
        pos = pos.copy()
        atr = self.model.atr_px_of(f_norm) * price
        reward = 0.0
        # 1) apply the action to the trade book
        if action == ENTER_LONG and pos.side == 0:
            pos.side, pos.entry, pos.size = 1, price, 1.0
            pos.risk = max(atr * self.stop_atr_mult, 1e-9)
            pos.stop = price - pos.risk
            reward -= self.cost
        elif action == ENTER_SHORT and pos.side == 0:
            pos.side, pos.entry, pos.size = -1, price, 1.0
            pos.risk = max(atr * self.stop_atr_mult, 1e-9)
            pos.stop = price + pos.risk
            reward -= self.cost
        elif action == EXIT and pos.side != 0:
            reward += self._mark_R(pos, price) - self.cost
            pos = PositionState(realized_R=pos.realized_R + reward)
        elif action == TIGHTEN_STOP and pos.side != 0:        # tail-gating: lock gains
            if pos.side == 1:
                pos.stop = max(pos.stop, price - 0.5 * pos.risk)
            else:
                pos.stop = min(pos.stop, price + 0.5 * pos.risk)
        elif action == SCALE_OUT and pos.side != 0 and pos.size > 0.5:
            half = self._mark_R(pos, price) * 0.5
            pos.realized_R += half
            pos.size *= 0.5
            reward += half - self.cost

        # 2) advance the market one imagined step via the learned model
        f_next, ret = self.model.step(f_norm)
        new_price = price * math.exp(ret)

        # 3) stop-out check on the imagined path
        if pos.side == 1 and new_price <= pos.stop:
            reward += self._mark_R(pos, pos.stop)
            pos = PositionState(realized_R=pos.realized_R + reward)
        elif pos.side == -1 and new_price >= pos.stop:
            reward += self._mark_R(pos, pos.stop)
            pos = PositionState(realized_R=pos.realized_R + reward)

        return (f_next, pos, new_price), reward

    def _mark_R(self, pos: PositionState, price: float) -> float:
        """Mark-to-market profit of the open position in R-multiples."""
        if pos.side == 0 or pos.risk <= 0:
            return 0.0
        return pos.side * (price - pos.entry) / pos.risk * pos.size

    def _leaf_value(self, state) -> float:
        f_norm, pos, price = state
        return self._mark_R(pos, price)        # unrealized R at the imagined leaf

    # ---- MCTS (faithful to muzero-general, single-player, learned model) ----
    def plan(self, ohlcv: pd.DataFrame, *, position_side: str | None = None) -> dict:
        """Imagine forward and recommend the best trade action.

        position_side None  -> entry/direction decision (flat book).
        position_side LONG/SHORT -> exit-management decision (open book).
        """
        if not self.model.fitted:
            self.model.fit(ohlcv)
        f_raw = market_features(ohlcv)
        f_norm = self.model.normalize(f_raw)
        price = float(pd.to_numeric(ohlcv["close"], errors="coerce").iloc[-1])
        side = {"LONG": 1, "SHORT": -1}.get((position_side or "").upper(), 0)
        atr0 = self.model.atr_px_of(f_norm) * price
        pos = PositionState()
        if side != 0:                              # seed an already-open book
            pos = PositionState(side=side, entry=price, size=1.0,
                                risk=max(atr0 * self.stop_atr_mult, 1e-9),
                                stop=price - side * max(atr0 * self.stop_atr_mult, 1e-9))
        root = _MCTSNode(0.0)
        root.state = (f_norm, pos, price)
        self._expand(root)
        mm = _MinMax()

        for _ in range(self.num_simulations):
            node, path, depth = root, [root], 0
            while node.expanded() and depth < self.horizon:
                action, node = self._select_child(node, mm)
                path.append(node)
                depth += 1
            parent = path[-2]
            state, reward = self._transition(parent.state, node._action)
            node.state, node.reward = state, reward
            self._expand(node)
            self._backprop(path, self._leaf_value(state), mm)

        # recommend by visit count (MuZero policy); report imagined R per action
        visits = {a: c.visit_count for a, c in root.children.items()}
        q = {a: c.value() for a, c in root.children.items()}
        best = max(visits, key=lambda a: visits[a]) if visits else HOLD
        traj = self._greedy_rollout(root)
        total = sum(visits.values()) or 1
        return {
            "action": ACTION_NAMES[best],
            "action_id": int(best),
            "position_side": position_side,
            "policy": {ACTION_NAMES[a]: round(v / total, 4) for a, v in visits.items()},
            "imagined_R": {ACTION_NAMES[a]: round(float(q.get(a, 0.0)), 4) for a in visits},
            "expected_R": round(float(q.get(best, 0.0)), 4),
            "imagined_trajectory": traj,
            "backend": self.model._backend,
            "num_simulations": self.num_simulations,
            "horizon": self.horizon,
        }

    def _expand(self, node: _MCTSNode):
        if node.state is None:
            return
        _, pos, _ = node.state
        legal = self._legal(pos)
        prior = 1.0 / len(legal)
        for a in legal:
            child = _MCTSNode(prior)
            child._action = a
            node.children[a] = child

    def _select_child(self, node, mm):
        best_score, best_a, best_c = -math.inf, None, None
        for a, child in node.children.items():
            score = self._ucb(node, child, mm)
            if score > best_score:
                best_score, best_a, best_c = score, a, child
        return best_a, best_c

    def _ucb(self, parent, child, mm):
        pb_c = (math.log((parent.visit_count + self.pb_c_base + 1) / self.pb_c_base)
                + self.pb_c_init)
        pb_c *= math.sqrt(parent.visit_count + 1) / (child.visit_count + 1)
        prior_score = pb_c * child.prior
        value_score = mm.normalize(child.reward + self.discount * child.value()) \
            if child.visit_count > 0 else 0.0
        return prior_score + value_score

    def _backprop(self, path, value, mm):
        for node in reversed(path):
            node.value_sum += value
            node.visit_count += 1
            mm.update(node.reward + self.discount * node.value())
            value = node.reward + self.discount * value

    def _greedy_rollout(self, root, steps: int = 6) -> list[dict]:
        """Most-visited path = the brain's imagined plan, for the dashboard."""
        out, node = [], root
        while node.expanded() and len(out) < steps:
            a = max(node.children, key=lambda x: node.children[x].visit_count)
            child = node.children[a]
            out.append({"step": len(out) + 1, "action": ACTION_NAMES[a],
                        "reward_R": round(float(child.reward), 4),
                        "value_R": round(float(child.value()), 4)})
            if not child.expanded():
                break
            node = child
        return out


# ============================================================================ #
#  WorldModelNode — NodeProtocol face (registry + dashboard)                    #
# ============================================================================ #
class WorldModelNode(BaseNode):
    """NodeProtocol face for the world-model: predict_proba = P(next return > 0).

    Lets the imagination capability live in the node network/registry/dashboard.
    fit(X, y) trains a light logistic direction head on the feature rows; the
    full dynamics is fit from OHLCV via `world_model.fit(ohlcv)`.
    """
    name = "world_model_imagination"
    kind = "world_model"
    summary = "MuZero imagination: learned market dynamics + MCTS planning of entry/exit/stop/trailing"
    schema = IOSchema(FEATURE_DIM, "market state features", "p(next-return > 0)")
    task = "binary"
    head = "y"

    def __init__(self):
        self.world_model = MarketWorldModel()
        self._w = np.zeros(FEATURE_DIM)
        self._b = 0.0
        self._trained = False

    def fit(self, X, y):
        Xa = np.asarray(X, dtype=float)
        ya = np.asarray(y, dtype=float)
        if len(Xa) and len(set(ya.tolist())) > 1:       # ridge-logistic (closed form-ish)
            mu, sd = Xa.mean(0), Xa.std(0) + 1e-8
            Z = (Xa - mu) / sd
            # one Newton-ish step from zero is enough as a light direction prior
            p = np.full(len(Z), 0.5)
            grad = Z.T @ (ya - p)
            self._w = 0.01 * grad / (np.abs(grad).max() + 1e-9)
            self._b = float(np.log((ya.mean() + 1e-6) / (1 - ya.mean() + 1e-6)))
            self._mu, self._sd = mu, sd
            self._trained = True
        return self

    def predict_proba(self, X):
        Xa = np.asarray(X, dtype=float)
        if not self._trained:
            return [0.5] * len(Xa)
        Z = (Xa - getattr(self, "_mu", 0.0)) / getattr(self, "_sd", 1.0)
        z = Z @ self._w + self._b
        return [float(1.0 / (1.0 + math.exp(-max(-30, min(30, v))))) for v in z]


def build_planner(ohlcv: pd.DataFrame | None = None, **kw) -> ImaginationPlanner:
    """Convenience factory: a fitted planner ready to imagine."""
    wm = MarketWorldModel()
    if ohlcv is not None:
        wm.fit(ohlcv)
    return ImaginationPlanner(model=wm, **kw)


def register_world_model() -> WorldModelNode:
    """Self-register on the live node registry (dashboard-sync). Idempotent."""
    from core import registry
    node = WorldModelNode()
    try:
        registry.register(node, summary=node.summary)
    except Exception:
        pass
    return node
