"""trading/strategy/generators/rd_agent.py — generator ⑦: RD-Agent(Q)-style factor researcher.

Research shortlist #5 (NeurIPS-2025 R&D-Agent-Quant, vendor/RD-Agent): an autonomous
research→develop→feedback loop — an LLM proposes a factor HYPOTHESIS given the running history
of past hypotheses + their measured feedback, DEVELOPS it into a concrete factor expression,
which is evaluated, and the result feeds the next round. Over cycles the research compounds
(the Trace), converging on factors that actually predict returns.

We reuse that LOOP PATTERN (RD-Agent/rdagent/scenarios/qlib/proposal/factor_proposal.py:
FactorHypothesisGen → Hypothesis2Experiment → feedback → Trace) with OUR LLM (core.llm) and OUR
formulaic-alpha grammar (alpha_ops), over OUR OHLCV — rather than RD-Agent's Docker + Qlib-China
data + multi-LLM orchestration, which can't run inside a per-cycle CPU loop. The R&D Trace is
persisted (trading.state) so hypotheses accumulate across cycles (the AgentRxiv idea). Factors
become ExpressionStrategy(kind='alpha') and face the SAME CPCV+DSR+PBO + family-wise gate.
"""
from __future__ import annotations

import json
import os
import re

import numpy as np

from trading.strategy.generators.base import StrategyGenerator
from trading.strategy.generators.expression import ExpressionStrategy, eval_expression

_TRACE_FILE = "rd_agent_trace.json"
_FIELDS = ["open", "high", "low", "close", "volume", "vwap"]
_OPS = ("Abs Sign Log Add Sub Mul Div Pow Greater Less Ref(x,d) Delta(x,d) Mean(x,d) Sum(x,d) "
        "Std(x,d) Var(x,d) Skew(x,d) Kurt(x,d) Max(x,d) Min(x,d) Med(x,d) Mad(x,d) Rank(x,d) "
        "WMA(x,d) EMA(x,d) Corr(x,y,d) Cov(x,y,d)")


def _extract_json(text):
    if not text:
        return None
    m = re.search(r"\[.*\]", text, re.DOTALL) or re.search(r"\{.*\}", text, re.DOTALL)
    try:
        return json.loads(m.group(0)) if m else None
    except Exception:
        return None


class RDAgentGenerator(StrategyGenerator):
    """LLM research→develop→feedback loop that invents formulaic-alpha factors, compounding
    over a persisted Trace. Emits ExpressionStrategy(alpha) candidates for the shared gate."""

    name = "rd_agent"

    def available(self) -> bool:
        if os.environ.get("RD_AGENT", "1") not in ("1", "true", "TRUE", "yes", "on"):
            return False
        try:
            from core import llm
            return llm.active_model() is not None
        except Exception:
            return False

    # ── persisted R&D trace (compounds across cycles) ────────────────────────────
    def _load_trace(self):
        try:
            from trading import state
            return state.load_json(_TRACE_FILE, []) or []
        except Exception:
            return []

    def _save_trace(self, trace):
        try:
            from trading import state
            state.save_json(_TRACE_FILE, trace[-200:])
        except Exception:
            pass

    def _prompt(self, market, trace, n):
        # feedback from the best past hypotheses (RD-Agent's hypothesis_and_feedback context)
        past = sorted([t for t in trace if t.get("market") == market],
                      key=lambda t: abs(t.get("ic", 0.0)), reverse=True)[:8]
        fb = "\n".join(f"- hypothesis: {t.get('hypothesis','')[:120]} | factor: {t.get('expr','')} "
                       f"| measured IC: {t.get('ic')}" for t in past) or "None yet (first round)."
        return [
            {"role": "system", "content":
             "You are R&D-Agent-Quant: an autonomous quant factor researcher. Each round you (R) "
             "propose a market HYPOTHESIS for why a factor predicts next-bar return, then (D) "
             "DEVELOP it into a factor expression. Build on the feedback — beat the best IC so "
             "far, do NOT repeat past factors. Return ONLY JSON."},
            {"role": "user", "content":
             f"Market: {market}. Fields: {_FIELDS}. Operators (d=window int, x/y=sub-expr): {_OPS}.\n"
             f"Past hypotheses + their measured rank-IC (higher |IC| = better):\n{fb}\n\n"
             f"Propose {n} NEW, DISTINCT factors as a JSON list of objects "
             f"{{\"hypothesis\": str, \"factor_expr\": str}} where factor_expr uses ONLY the "
             f"fields + operators above (e.g. Div(Delta(close,5), Std(close,20)) or "
             f"Corr(close, volume, 10)). Prefer economically-motivated factors "
             f"(momentum, mean-reversion, volume-price, volatility, microstructure)."}]

    def generate(self, ohlcv, market, *, features=None, budget=12, seed=0, **kw):
        df = features if features is not None else __import__(
            "trading.strategy.features", fromlist=["compute_features"]).compute_features(ohlcv)
        if "close" not in df.columns:
            return []
        n = max(2, min(int(budget) // 2, 6))
        try:
            from core import llm
            reply = llm.chat(self._prompt(market, self._load_trace(), n),
                             max_tokens=900, temperature=0.6)
        except Exception:
            return []
        items = _extract_json(reply) or []
        if isinstance(items, dict):
            items = items.get("factors") or [items]
        from trading.strategy.guardrails import information_coefficient
        fwd = df["close"].pct_change().shift(-1).to_numpy(dtype=float)
        trace = self._load_trace()
        out = []
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                continue
            expr = str(it.get("factor_expr") or "").strip()
            hyp = str(it.get("hypothesis") or "")[:200]
            if not expr or "(" not in expr:
                continue
            try:
                vals = eval_expression(expr, "alpha", df, _FIELDS).to_numpy(dtype=float)
                ic = information_coefficient(vals, fwd)
            except Exception:
                continue
            if not np.isfinite(ic) or abs(ic) < 0.01:
                continue
            trace.append({"market": market, "hypothesis": hyp, "expr": expr,
                          "ic": round(float(ic), 4)})
            long_thr, short_thr = (0.5, -0.5) if ic >= 0 else (-0.5, 0.5)
            out.append(ExpressionStrategy(
                market=market, features=list(_FIELDS), expr=expr, kind="alpha",
                long_thr=long_thr, short_thr=short_thr, id=f"rdagent_{market.lower()}_{seed}_{i}",
                provenance={"generation": 0, "parents": [], "mutations": ["rd_agent"],
                            "hypothesis": hyp, "ic": round(float(ic), 4)}))
        self._save_trace(trace)
        return out
