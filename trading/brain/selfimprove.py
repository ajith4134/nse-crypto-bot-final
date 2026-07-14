"""trading/brain/selfimprove.py — self-improvement (T8.8).

Two complementary self-improvement engines:

  • SelfImprover (CPU, real, offline) — hill-climbs a parameter set against ANY metric
    (e.g. T8.2 fitness over entry/exit thresholds or strategy weights), proving the
    metric improves from its starting point. Deterministic with an injected rng.

  • DSPyOptimizer (gated) — **DSPy/GEPA** optimise an LLM reasoning program (a trade-
    decision module) against a metric/few-shot set. This is the step that introduces an
    LLM reasoning component, so the previously-deferred GEPA/DSPy live HERE. Activates
    when DSPY_ENABLED=1 + an OpenAI-compatible key is in the env; otherwise returns an
    honest "not configured" note (the CPU SelfImprover still works offline).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np


@dataclass
class SelfImprover:
    """Deterministic hill-climb optimiser: improves params against a metric (CPU, offline)."""
    n_iter: int = 50
    sigma_frac: float = 0.2
    maximize: bool = True

    def optimize(self, param_space: dict, metric_fn, *, rng: np.random.Generator | None = None,
                 start: dict | None = None) -> dict:
        """param_space: {name: (lo, hi)}; metric_fn(params)->float. Returns best + history."""
        rng = rng or np.random.default_rng(0)
        cur = start or {k: (lo + hi) / 2.0 for k, (lo, hi) in param_space.items()}
        cur = {k: float(np.clip(cur.get(k, (lo + hi) / 2.0), lo, hi))
               for k, (lo, hi) in param_space.items()}
        best, best_score = dict(cur), float(metric_fn(cur))
        start_score = best_score
        history = [round(best_score, 6)]
        better = (lambda a, b: a > b) if self.maximize else (lambda a, b: a < b)
        for _ in range(self.n_iter):
            cand = {k: float(np.clip(best[k] + rng.normal(0, (hi - lo) * self.sigma_frac), lo, hi))
                    for k, (lo, hi) in param_space.items()}
            s = float(metric_fn(cand))
            if better(s, best_score):
                best, best_score = cand, s
            history.append(round(best_score, 6))
        return {"best_params": best, "best_score": round(best_score, 6),
                "start_score": round(start_score, 6),
                "improved": better(best_score, start_score), "history": history,
                "iterations": self.n_iter}


class DSPyOptimizer:
    """Gated DSPy/GEPA optimiser for an LLM trade-decision program."""

    def __init__(self, *, enabled: bool | None = None, model: str | None = None):
        want = (str(os.environ.get("DSPY_ENABLED", "")).lower() in ("1", "true", "yes")
                if enabled is None else enabled)
        self._lm = None
        self._dspy = None
        self.note = "DSPy disabled (set DSPY_ENABLED=1 + an OpenAI-compatible key to enable)"
        if want:
            self._configure(model)

    # OpenAI-compatible providers DSPy/LiteLLM can drive directly from their own env key, in
    # preference order. Lets self-improvement run on the 12-provider failover already configured
    # (see core/llm.py + [[llm-providers-configured]]) instead of hard-requiring OPENAI_API_KEY.
    _PROVIDERS = (
        ("OPENAI_API_KEY", "openai/gpt-4o-mini"),
        ("OPENROUTER_API_KEY", "openrouter/openai/gpt-4o-mini"),
        ("GROQ_API_KEY", "groq/llama-3.3-70b-versatile"),
        ("CEREBRAS_API_KEY", "cerebras/llama-3.3-70b"),
        ("TOGETHER_API_KEY", "together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    )

    def _configure(self, model: str | None) -> None:
        try:
            import dspy
            # explicit model override wins; else pick the first provider whose key is present
            chosen = model or os.environ.get("DSPY_MODEL")
            kw = {}
            if not chosen:
                for env_key, lm_id in self._PROVIDERS:
                    if os.environ.get(env_key):
                        chosen = lm_id
                        break
            if not chosen:
                self.note = ("DSPY_ENABLED but no OpenAI-compatible key found "
                             "(OPENAI/OPENROUTER/GROQ/CEREBRAS/TOGETHER)")
                return
            # LiteLLM reads the provider key from env by prefix; pass OPENAI_BASE_URL through
            # only for the raw-openai path (proxies / local gateways).
            if chosen.startswith("openai/") and os.environ.get("OPENAI_API_KEY"):
                kw["api_key"] = os.environ["OPENAI_API_KEY"]
                base = os.environ.get("OPENAI_BASE_URL")
                if base:
                    kw["api_base"] = base
            self._lm = dspy.LM(chosen, **kw)
            dspy.configure(lm=self._lm)
            self._dspy = dspy
            self.note = f"DSPy active ({chosen})"
        except Exception as exc:  # pragma: no cover
            self.note = f"DSPy init failed: {str(exc)[:100]}"

    def available(self) -> bool:
        return self._lm is not None and self._dspy is not None

    def build_decider(self):
        """A dspy trade-decision module (context → UP/DOWN/FLAT). None if unavailable."""
        if not self.available():
            return None
        dspy = self._dspy

        class TradeDecision(dspy.Signature):
            """Decide trade direction from market context."""
            context = dspy.InputField(desc="market features, regime, news sentiment")
            decision = dspy.OutputField(desc="one of UP, DOWN, FLAT")

        return dspy.Predict(TradeDecision)

    def optimize(self, trainset, metric, *, method: str = "bootstrap") -> dict:
        """Optimise the decider against `metric` using DSPy BootstrapFewShot or GEPA."""
        if not self.available():
            return {"available": False, "note": self.note}
        dspy = self._dspy
        module = self.build_decider()
        try:  # pragma: no cover - needs live LLM
            if method == "gepa":
                opt = dspy.GEPA(metric=metric, auto="light")
            else:
                opt = dspy.BootstrapFewShot(metric=metric)
            compiled = opt.compile(module, trainset=trainset)
            return {"available": True, "method": method, "compiled": True}
        except Exception as exc:
            return {"available": True, "method": method, "compiled": False,
                    "error": str(exc)[:120]}

    def status(self) -> dict:
        return {"available": self.available(), "note": self.note}
