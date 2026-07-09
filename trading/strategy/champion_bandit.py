"""trading/strategy/champion_bandit.py — regime-contextual champion allocator (#3).

Instead of the single best library strategy taking every selective entry, PAPER capital
is spread across the autoresearch library's champions by a contextual Thompson-sampling
bandit: one Beta(wins+1, losses+1) posterior per (strategy, regime), sampled fresh each
allocation — exploration and exploitation balance themselves, and the allocation ITSELF
becomes a learned edge that shifts with the regime (risk_on / risk_off / neutral).

  suggest_allocation(market) — {strategy_id: weight} over the current champions
                               (weights sum to 1; sampled posteriors, regime-aware)
  stake_scale(market, strategy) — the multiplier the executor applies to its base stake
                               for an entry attributed to `strategy` (bounded [0.5, 2.0]
                               so sizing stays sane while the posteriors are young)
  update(market, strategy, win, regime) — posterior update from a CLOSED trade

State: champion_bandit.json. Paper-first: this shapes PAPER stake only; live promotion
stays behind the W3 autonomy gates. Thompson sampling per Chapelle & Li (2011).
"""
from __future__ import annotations

import os
import time

from trading import state

_FILE = "champion_bandit.json"
_MAX_ARMS = 8                       # top library strategies considered per market
_ARMS_TTL_S = 600                   # _champions() loads the SkillLibrary (heavy) — cache it
_ARMS_CACHE: dict = {}              # market -> (mono_ts, arms)


def _store() -> dict:
    d = state.load_json(_FILE, {})
    d.setdefault("arms", {})        # "market|strategy|regime" -> {"w": int, "l": int}
    return d


def _regime() -> str:
    try:
        from trading.broker_sense.broker_features import current_regime
        return current_regime() or "neutral"
    except Exception:
        return "neutral"


def _champions(market: str) -> list[str]:
    """The current arm set: the champion + the best library strategies for `market`.

    HEAVY on first call (evolved_link._loop() pulls the SkillLibrary + generator stack) —
    TTL-cached so the executor pays it at most once per 10 min, and NEVER called from
    dashboard request threads (status() reads the persisted arm list instead; see the
    524 GIL-wedge note in autoresearch.status)."""
    import time as _t
    hit = _ARMS_CACHE.get(market)
    if hit and _t.monotonic() - hit[0] < _ARMS_TTL_S:
        return hit[1]
    arms: list[str] = []
    try:
        lineage = state.load_json("champion_lineage.json", {})
        champ = ((lineage.get(market.upper()) or {}).get("champion") or {}).get("id")
        if champ:
            arms.append(champ)
    except Exception:
        pass
    try:
        from trading.strategy.evolved_link import _loop
        for sk in _loop().library.retrieve(market=market.upper(), k=_MAX_ARMS):
            name = getattr(sk, "name", None)
            if name and name not in arms:
                arms.append(name)
    except Exception:
        pass
    arms = arms[:_MAX_ARMS]
    _ARMS_CACHE[market] = (_t.monotonic(), arms)
    return arms


def suggest_allocation(market: str, *, regime: str | None = None,
                       arms: list[str] | None = None) -> dict:
    """Thompson draw per arm → normalized weights. Honest empty dict when no champions."""
    import numpy as np
    reg = regime or _regime()
    d = _store()
    if arms is None:
        arms = _champions(market)
        # persist the arm list so status() (dashboard threads) can sample an allocation
        # WITHOUT the heavy SkillLibrary import that _champions() needs
        key = f"last_arms_{market.lower()}"
        if arms and d.get(key) != arms:
            d[key] = arms
            state.save_json(_FILE, d)
    if not arms:
        return {}
    draws = {}
    for a in arms:
        p = d["arms"].get(f"{market.lower()}|{a}|{reg}") \
            or d["arms"].get(f"{market.lower()}|{a}|neutral") or {}
        draws[a] = float(np.random.beta(p.get("w", 0) + 1, p.get("l", 0) + 1))
    total = sum(draws.values()) or 1.0
    return {a: round(v / total, 4) for a, v in draws.items()}


def stake_scale(market: str, strategy: str, *, regime: str | None = None,
                arms: list[str] | None = None) -> float:
    """Executor-facing multiplier: how much of the base stake this strategy's entry gets,
    relative to an equal split across the current arms. Bounded [0.5, 2.0]; 1.0 when the
    strategy isn't an arm (unknown strategies are never punished silently)."""
    alloc = suggest_allocation(market, regime=regime, arms=arms)
    if not alloc or strategy not in alloc:
        return 1.0
    equal = 1.0 / len(alloc)
    return round(max(0.5, min(2.0, alloc[strategy] / equal)), 3)


def update(market: str, strategy: str, *, win: bool, regime: str | None = None) -> None:
    """Posterior update from a CLOSED trade attributed to `strategy`."""
    if not strategy:
        return
    d = _store()
    k = f"{market.lower()}|{strategy}|{regime or _regime()}"
    p = d["arms"].setdefault(k, {"w": 0, "l": 0})
    p["w" if win else "l"] += 1
    d["ts"] = time.time()
    state.save_json(_FILE, d)


def status() -> dict:
    """Panel view: current arms, per-regime posteriors, a sampled allocation.

    CHEAP by design: samples over the arm list PERSISTED by the executor's last
    suggest_allocation() — never _champions() (SkillLibrary import) — because this runs
    inside dashboard request threads (the 524 GIL-wedge lesson)."""
    d = _store()
    out = {"regime": _regime(), "arms": {}, "enabled":
           os.environ.get("CHAMPION_BANDIT", "1") in ("1", "true", "TRUE", "yes")}
    for k, p in d["arms"].items():
        out["arms"][k] = {**p, "mean": round((p["w"] + 1) / (p["w"] + p["l"] + 2), 4)}
    stored = d.get("last_arms_crypto") or []
    try:
        out["allocation_crypto"] = suggest_allocation("CRYPTO", arms=stored) if stored else {}
    except Exception:
        out["allocation_crypto"] = {}
    return out
