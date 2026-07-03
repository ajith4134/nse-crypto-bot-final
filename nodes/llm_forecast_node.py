"""LLMForecastNode — cloud-LLM as a reasoning-based directional forecaster.

Feeds a compact summary of the recent price window to the brain's 12-provider cloud-LLM
failover (core/llm.chat) and parses a directional score in [-1, 1], appended as a feature
to the task-aware readout. This is the "use the cloud LLMs" forecaster: weaker than the
dedicated TS foundation models for raw numeric prediction, but it reasons over context and
can later be given news/psychology text. Every call is telemetered (core/llm_telemetry) so
the dashboard shows per-provider hit-rate / calls / cooldown.

Robustness: caching by window signature keeps calls bounded; any LLM error falls back to a
momentum heuristic (never blocks). Gated out of the growth pool (network latency) like the FMs.
"""
from __future__ import annotations

import json
import re
import warnings

import numpy as np

from nodes.quant_nodes import _HeadBase


class LLMForecastNode(_HeadBase):
    kind = "foundation"
    W = 24                       # window of recent closes summarized to the LLM
    MAX_CALLS = 40               # hard cap on LLM calls per fit (cost/latency guard)

    def __init__(self, name="llm_forecast", col=0):
        super().__init__(name, "Cloud-LLM directional forecaster (reasons over recent window).", col)
        self._cache: dict = {}
        self._calls = 0

    # ---- LLM directional score in [-1, 1] for a window of closes -------------- #
    def _llm_score(self, win: np.ndarray) -> float:
        key = round(float(win[-1]), 4), round(float(win.mean()), 4), len(win)
        if key in self._cache:
            return self._cache[key]
        if self._calls >= self.MAX_CALLS:
            return self._momentum(win)
        try:
            from core import llm
            series = ", ".join(f"{v:.4f}" for v in win[-self.W:])
            msg = [
                {"role": "system", "content":
                 "You are a quantitative price forecaster. Given a recent price series, "
                 "predict the NEXT-step direction. Reply with ONLY compact JSON: "
                 '{"dir": <float in [-1,1]>, "conf": <float in [0,1]>}. '
                 "dir>0 = up, dir<0 = down, magnitude = strength."},
                {"role": "user", "content": f"Recent prices (oldest→newest): {series}"},
            ]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                txt = llm.chat(msg, max_tokens=40, temperature=0.2, timeout=20)
            self._calls += 1
            score = self._parse(txt)
        except Exception:
            score = self._momentum(win)
        self._cache[key] = score
        return score

    @staticmethod
    def _parse(txt: str) -> float:
        m = re.search(r"\{.*\}", txt, re.S)
        if m:
            try:
                obj = json.loads(m.group(0))
                d = float(obj.get("dir", 0.0))
                c = float(obj.get("conf", 1.0))
                return float(np.clip(d * c, -1.0, 1.0))
            except Exception:
                pass
        t = (txt or "").lower()                            # no/failed JSON → text heuristic
        if "up" in t or "bull" in t:
            return 0.5
        if "down" in t or "bear" in t:
            return -0.5
        return 0.0

    @staticmethod
    def _momentum(win: np.ndarray) -> float:
        if len(win) < 3:
            return 0.0
        r = np.diff(win[-6:])
        s = float(np.tanh(np.sum(r) / (np.std(win[-6:]) + 1e-9)))
        return float(np.clip(s, -1.0, 1.0))

    def _augment(self, X):
        base = np.asarray([[float(v) for v in r] for r in X], float)
        col = base[:, self.col]
        scores = np.zeros((len(base), 1))
        for i in range(len(base)):
            win = col[max(0, i - self.W + 1): i + 1]
            scores[i, 0] = self._llm_score(win) if len(win) >= 3 else 0.0
        return np.hstack([base, scores])
