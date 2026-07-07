"""trading/strategy/generators/llm_mutation.py — generator ②: LLM-as-mutation-operator.

Research shortlist #2 (FunSearch / AlphaEvolve pattern): instead of DEAP's blind bit-flip
mutation, a cloud LLM proposes *hypothesis-driven* edits to a strategy expressed in our GP DSL
— it knows what "add a momentum confirmation" or "gate on RSI" means, so its variants beat
random mutation per evaluation. We keep NSGA-II's honesty by scoring every LLM variant through
the SAME CPCV+Deflated-Sharpe+PBO guardrail (base.evaluate_and_admit), so the LLM can never
narrate its way past validation.

Reuse: the LLM call is `core.llm.chat` (our 12-provider free-first failover; keys in .env,
never logged). The DSL + validation reuse `trading.strategy.genome` (get_pset + PrimitiveTree
parse), so an LLM variant that does not compile to a valid typed tree is discarded before it
ever reaches the gate.

Grammar the LLM must emit (string form of a DEAP typed-GP tree, BoolS root):
  bool ops : and_(B,B) or_(B,B)              logic
  compares : gt(F,F) lt(F,F) xup(F,F) xdn(F,F)   (xup/xdn = cross up/down)
  vs const : gtc(F, c) ltc(F, c)             c ∈ the constant grid tokens below
  features : the market's feature names (FloatS terminals)
  consts   : c_m2_0 c_m1_5 c_m1_0 c_m0_5 c_0_0 c_0_5 c_1_0 c_1_5 c_2_0   (z-score space)
  bool term: TRUE FALSE
Features are z-scored, so a comparison like gt(rsi, sma_fast) is scale-free.
"""
from __future__ import annotations

import json
import os
import re

import numpy as np

from trading.strategy.generators.base import StrategyGenerator

_CONST_TOKENS = ["c_m2_0", "c_m1_5", "c_m1_0", "c_m0_5", "c_0_0",
                 "c_0_5", "c_1_0", "c_1_5", "c_2_0"]


def _valid_src(src, features) -> bool:
    """True if `src` parses to a valid typed GP tree over `features` (else discard)."""
    if not src or not isinstance(src, str):
        return False
    try:
        from deap import gp
        from trading.strategy.genome import get_pset
        gp.PrimitiveTree.from_string(src, get_pset(features))
        return True
    except Exception:
        return False


def _extract_json(text: str):
    """Pull the first JSON array/object out of an LLM reply (tolerates ``` fences + prose)."""
    if not text:
        return None
    m = re.search(r"\[.*\]", text, re.DOTALL) or re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


class LLMMutationGenerator(StrategyGenerator):
    """LLM proposes new strategies in our GP DSL; we validate + gate them."""

    name = "llm_mutation"

    def available(self) -> bool:
        if os.environ.get("LLM_MUTATION", "1") not in ("1", "true", "TRUE", "yes", "on"):
            return False
        try:
            from core import llm
            return llm.active_model() is not None
        except Exception:
            return False

    def _parents(self, features, market, seed, k=3):
        """A few seed strategies to show the LLM as the current population to improve."""
        from trading.strategy.genome import random_strategy
        rng = np.random.default_rng(seed)
        out = []
        for i in range(k):
            s = random_strategy(features, rng, market=market, strat_id=f"seed_{i}")
            out.append({"long_src": s.long_src, "short_src": s.short_src})
        return out

    def _prompt(self, features, market, parents, n):
        feat_list = ", ".join(features)
        ex = parents[0] if parents else {"long_src": "gt(rsi, sma_fast)", "short_src": "lt(rsi, sma_fast)"}
        return [
            {"role": "system", "content":
             "You are a quant strategist that writes trading rules in a tiny typed grammar. "
             "Return ONLY valid JSON — a list of objects, each {\"long_src\": str, \"short_src\": "
             "str|null, \"rationale\": str}. No prose outside the JSON."},
            {"role": "user", "content":
             f"Market: {market}. Features (z-scored, FloatS terminals): {feat_list}.\n"
             f"Grammar (string form of a boolean-root tree):\n"
             f"  logic: and_(B,B) or_(B,B)\n"
             f"  compare: gt(F,F) lt(F,F) xup(F,F) xdn(F,F)  (xup/xdn = cross up/down)\n"
             f"  vs const: gtc(F,c) ltc(F,c)  with c in {_CONST_TOKENS}\n"
             f"  bool terminals: TRUE FALSE\n"
             f"F must be a feature name; B must be a boolean sub-expression. Nest freely.\n"
             f"Current population to IMPROVE (propose smarter variants — add confirmations, "
             f"regime gates, crossovers; avoid trivially-true rules):\n{json.dumps(parents)}\n"
             f"Example valid item: {json.dumps({'long_src': ex['long_src'], 'short_src': ex['short_src'], 'rationale': 'momentum with trend filter'})}\n"
             f"Return {n} NEW, DISTINCT, tradeable rules as JSON."}]

    def generate(self, ohlcv, market, *, features=None, budget=12, seed=0, **kw):
        from trading.strategy.operators import market_features
        flist = market_features(market)
        parents = self._parents(flist, market, seed, k=3)
        n = max(4, min(int(budget), 12))
        try:
            from core import llm
            reply = llm.chat(self._prompt(flist, market, parents, n),
                             max_tokens=900, temperature=0.75)
        except Exception:
            return []
        items = _extract_json(reply) or []
        if isinstance(items, dict):
            items = items.get("strategies") or items.get("rules") or [items]
        from trading.strategy.genome import Strategy
        out = []
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                continue
            long_src = it.get("long_src")
            short_src = it.get("short_src") or None
            if not _valid_src(long_src, flist):
                continue
            if short_src is not None and not _valid_src(short_src, flist):
                short_src = None
            out.append(Strategy(
                market=market, long_src=long_src, features=list(flist),
                short_src=short_src, allow_short=short_src is not None,
                stop_atr=2.0, target_atr=3.0, id=f"llm_{market.lower()}_{seed}_{i}",
                provenance={"generation": 0, "parents": [p.get("long_src") for p in parents],
                            "mutations": ["llm"], "rationale": str(it.get("rationale", ""))[:200]}))
        return out
