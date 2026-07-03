"""Name the discovered concepts — the auto-interp step.

Feed each dictionary feature's max-activating market windows (as compact stats) to the brain's
cloud-LLM failover (core.llm.chat) and ask for a short human-readable NAME + description, like
OpenAI's neuron-explainer. Falls back to a deterministic stats-based name when no LLM is
configured, so discovery always produces named features.
"""
from __future__ import annotations

import json
import re

import numpy as np


def _window_stats(win: np.ndarray) -> dict:
    w = np.asarray(win, float).reshape(-1)
    if len(w) < 2:
        return {"trend": 0.0, "vol": 0.0, "range": 0.0}
    d = np.diff(w)
    return {"trend": round(float(np.tanh(np.sum(d) / (np.std(w) + 1e-9))), 3),
            "vol": round(float(np.std(d) / (np.mean(np.abs(w)) + 1e-9)), 4),
            "range": round(float((w.max() - w.min()) / (np.mean(np.abs(w)) + 1e-9)), 4),
            "accel": round(float(np.tanh(np.sum(np.diff(d)))), 3)}


def _fallback_name(stats: list[dict], fid: int) -> dict:
    if not stats:
        return {"name": f"concept-{fid}", "description": "unlabeled latent concept"}
    tr = float(np.mean([s["trend"] for s in stats]))
    vo = float(np.mean([s["vol"] for s in stats]))
    rg = float(np.mean([s["range"] for s in stats]))
    dir_ = "up-trend" if tr > 0.2 else "down-trend" if tr < -0.2 else "range-bound"
    volq = "high-vol" if vo > np.median([s["vol"] for s in stats] + [vo]) else "low-vol"
    name = f"{dir_} · {volq}"
    return {"name": name,
            "description": f"windows with mean trend {tr:+.2f}, vol {vo:.3f}, range {rg:.2f}"}


def name_feature(fid: int, windows: list[np.ndarray], use_llm: bool = True) -> dict:
    """Name one discovered feature from its max-activating windows."""
    stats = [_window_stats(w) for w in windows if w is not None and len(np.asarray(w).reshape(-1)) >= 2]
    if not use_llm:
        return _fallback_name(stats, fid)
    try:
        from core import llm
        msg = [
            {"role": "system", "content":
             "You label latent features a market-analysis neural net invented. Given summary "
             "stats of the price windows that most activate one feature, name the concept it "
             'detects. Reply ONLY compact JSON: {"name": "<=4 words", "description": "one line"}.'},
            {"role": "user", "content":
             "Max-activating window stats (trend∈[-1,1], vol, range, accel):\n" +
             json.dumps(stats[:5])},
        ]
        txt = llm.chat(msg, max_tokens=60, temperature=0.3, timeout=20)
        m = re.search(r"\{.*\}", txt, re.S)
        obj = json.loads(m.group(0)) if m else {}
        name = str(obj.get("name") or "").strip()[:48]
        desc = str(obj.get("description") or "").strip()[:160]
        if name:
            return {"name": name, "description": desc or "(no description)"}
    except Exception:
        pass
    return _fallback_name(stats, fid)
