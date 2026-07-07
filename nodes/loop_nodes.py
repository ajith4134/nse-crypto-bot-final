"""nodes/loop_nodes.py — autoload shims for the trading-side LOOP nodes (#13 fix).

Two long-built nodes lived outside nodes/ and never reached the live registry
(register_self_evolve() was defined but never called; the W6 RL node is new):

  SelfEvolveLoopNode — P(a profitable evolved strategy is available) from the
                       SkillLibrary (trading/strategy/self_evolve.py).
  RlExecPolicyNode   — P(long) from the trained PPO execution policy
                       (trading/rl/exec_policy.py, vp2 design).

Both are thin, no-required-arg BaseNode faces so nodes/autoload discovers them like
every other node family (dashboard-sync: they appear honestly in the census)."""
from __future__ import annotations

from core.node_protocol import BaseNode, IOSchema


class SelfEvolveLoopNode(BaseNode):
    name = "self_evolving_loop"
    kind = "evolution"
    summary = ("Lifelong loop: evolve strategies → admit guardrail-passed winners "
               "into the growing skill library")
    task = "binary"
    head = "y"

    def __init__(self):
        self.schema = IOSchema(1, "market context",
                               "p(profitable evolved strategy available)")
        self._impl = None

    def _node(self):
        if self._impl is None:
            from trading.strategy.self_evolve import SelfEvolveNode
            self._impl = SelfEvolveNode()
        return self._impl

    def fit(self, X, y):
        self._node().fit(X, y)
        return self

    def predict_proba(self, X):
        return self._node().predict_proba(X)


class RlExecPolicyNode(BaseNode):
    name = "rl_exec_policy"
    kind = "rl"
    summary = ("PPO execution policy: learned (direction, SL, TP) trade specs "
               "(vp2 design; honest 0.5 while untrained)")
    task = "binary"
    head = "y"

    def __init__(self):
        self.schema = IOSchema(1, "market context",
                               "p(long per trained exec policy)")
        self._impl = None

    def _node(self):
        if self._impl is None:
            from trading.rl.exec_policy import RLExecPolicyNode as _R
            self._impl = _R()
        return self._impl

    def fit(self, X, y):
        return self

    def predict_proba(self, X):
        return self._node().predict_proba(X)
