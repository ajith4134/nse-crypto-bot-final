"""Anti-overfit telemetry (CANON-43 / NNM-30).

The videos demand that a model advertise its overfitting exposure honestly:
how many backtests were run (multiple-testing burden), how many free parameters
it has (capacity vs data), and how long it has been in RESEARCH vs live (a model
tuned for months on the same data is suspect). This module surfaces those three
numbers from REAL state (honest-wiring rule): the CORTEX graph's edges are its
learnable gate weights, the backtest counter is a persisted process-wide tally,
and research-time is measured from the network-state age.

`telemetry()` returns the dashboard payload; `register_backtest()` is called by
the sweep/evolve lanes so the count is never silent."""
from __future__ import annotations

import json
import os
import time

__all__ = ["register_backtest", "backtest_count", "param_count", "telemetry"]

_CACHE = os.path.join(os.path.dirname(__file__), os.pardir, "data", "cache")
_COUNTER = os.path.abspath(os.path.join(_CACHE, "antioverfit_counter.json"))
_STATE = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir,
                                      "network_state.json"))


def _read_counter() -> dict:
    try:
        with open(_COUNTER) as fh:
            return json.load(fh)
    except Exception:
        return {"backtests_run": 0, "first_seen": None}


def register_backtest(n: int = 1) -> int:
    """Count n backtests toward the multiple-testing burden (CANON-43).
    Called by trading.sweep / nodes.neat_lane so nothing is evaluated silently."""
    c = _read_counter()
    c["backtests_run"] = int(c.get("backtests_run", 0)) + int(n)
    if not c.get("first_seen"):
        c["first_seen"] = round(time.time(), 3)
    os.makedirs(_CACHE, exist_ok=True)
    with open(_COUNTER, "w") as fh:
        json.dump(c, fh)
    return c["backtests_run"]


def backtest_count() -> int:
    return int(_read_counter().get("backtests_run", 0))


def param_count(state: dict | None = None) -> dict:
    """Structural free-parameter count of the CORTEX graph: each edge is a
    learnable routing/gate weight, each node a frozen expert (0 free params but
    counted as capacity). Returns {'edges','nodes','free_params','capacity'}."""
    state = state if state is not None else _load_state()
    nodes = state.get("nodes", []) or []
    edges = state.get("edges", []) or []
    # free params = gate weights (edges) + per-node scalar trust/bias (kept nodes)
    kept = [n for n in nodes if n.get("kept", True)]
    free = len(edges) + len(kept)
    return {"edges": len(edges), "nodes": len(nodes), "kept_nodes": len(kept),
            "free_params": free}


def _load_state() -> dict:
    try:
        with open(_STATE) as fh:
            return json.load(fh)
    except Exception:
        return {}


def telemetry(state: dict | None = None, now: float | None = None) -> dict:
    """Full CANON-43 payload for the dashboard. Combines backtest burden, param
    count vs dataset size, and research-time age → a single overfit_risk verdict
    (ok | watch | high). Honest: if network_state.json is absent, the counts are
    zeroed and the reason is stated."""
    now = now if now is not None else time.time()
    state = state if state is not None else _load_state()
    pc = param_count(state)
    counter = _read_counter()
    bt = int(counter.get("backtests_run", 0))
    n_obs = 0
    ds = state.get("dataset") or {}
    for key in ("n", "rows", "samples", "n_train", "size"):
        if isinstance(ds, dict) and isinstance(ds.get(key), (int, float)):
            n_obs = int(ds[key]); break

    first = counter.get("first_seen")
    research_days = round((now - first) / 86400, 2) if first else 0.0

    # params-per-observation: >0.1 is classic over-parameterisation territory
    ppo = round(pc["free_params"] / n_obs, 4) if n_obs else None
    flags = []
    if ppo is not None and ppo > 0.1:
        flags.append(f"high capacity: {pc['free_params']} params / {n_obs} obs = {ppo}")
    if bt > 50:
        flags.append(f"multiple-testing burden: {bt} backtests run")
    if research_days > 30:
        flags.append(f"stale research window: {research_days}d on the same data")

    risk = "ok"
    if len(flags) >= 2 or (ppo is not None and ppo > 0.25):
        risk = "high"
    elif flags:
        risk = "watch"

    return {
        "overfit_risk": risk,
        "backtests_run": bt,
        "free_params": pc["free_params"],
        "edges": pc["edges"], "nodes": pc["nodes"], "kept_nodes": pc["kept_nodes"],
        "n_observations": n_obs,
        "params_per_observation": ppo,
        "research_time_days": research_days,
        "flags": flags,
        "note": None if state.get("nodes") else "network_state.json absent — run POST /api/network/refresh",
    }
