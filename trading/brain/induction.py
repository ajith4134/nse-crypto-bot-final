"""trading/brain/induction.py — Agent-Workflow-Memory induction (R7/R12/R13).

Distil SUCCESSFUL trajectories into reusable INSTRUCTION neurons, so the brain grows its
own how-to library from what actually worked — the material the instruction evolver
(trading/brain/evolution.py) then mutates, promotes, and retires. Two sources:

  induce_from_nav(goal, market, trace, completed=…) — a completed navigation becomes a
      route instruction (the Binance/Upstox golden paths the brain must master, R12/R13).
  induce_from_trade(strategy, regime, direction, win=…, …) — the recipe a closed trade
      used becomes an entry instruction, graded with the trade's REAL outcome.

Deterministic ids = idempotent: re-seeing the SAME pattern never dupes, it records another
outcome (record_use). So a recipe that keeps winning climbs in confidence and gets promoted;
one that starts losing drops below the floor and becomes an evolver VARY candidate — closing
the trajectory → instruction → evolution loop with live evidence. Fail-open: induction must
never break a trade or navigation cycle (every entry point swallows its own errors).
"""
from __future__ import annotations

import hashlib
import re

from memory.neurons import get_store

_WORD = re.compile(r"[a-z0-9]+")


def _key(*parts: str) -> str:
    raw = "|".join(str(p).strip().lower() for p in parts)
    return "n-" + hashlib.sha1(("induction:" + raw).encode()).hexdigest()[:12]


def _upsert_instruction(nid: str, title: str, body: str, action: str, *,
                        success: bool, pnl: float, domain: str, ref: str,
                        fail_reason: str = "") -> str | None:
    """Create the instruction on first sight; every sighting records the real outcome via
    InstructionEngine.grade — so losses leave a failure TRACE, which is exactly the material
    the evolver's (offline, deterministic) mutation needs to improve the recipe."""
    try:
        from trading.brain.instructions import InstructionEngine
        store = get_store()
        if store.get(nid) is None:
            store.add("instruction", title[:200], body, action, level="L4",
                      origin="induction", ref=ref, confidence=0.5, nid=nid,
                      auto_link=False)
        InstructionEngine(store).grade(nid, success=success, pnl=pnl, domain=domain,
                                       failure_reason=fail_reason)
        return nid
    except Exception:
        return None                                              # fail-open


def induce_from_nav(goal: str, market: str, trace, *, completed: bool) -> str | None:
    """A completed navigation → a reusable route instruction (reinforced on each success)."""
    if not completed:
        return None                                             # only successful routes
    steps = []
    for step in (trace or []):
        if not (isinstance(step, dict) and step.get("ok")):
            continue
        act = step.get("action")
        label = (act.get("target") or act.get("kind") or str(act)) if isinstance(act, dict) \
            else str(act)
        steps.append(str(label)[:120])
    if not steps:
        return None
    body = "\n".join(f"{i + 1}) {s}" for i, s in enumerate(steps))
    action = (f"Use to '{goal}' on the {market} web app. Follow the steps in order; "
              f"verify: the target screen for '{goal}' is reached. Induced from a "
              f"successful navigation.")
    return _upsert_instruction(
        _key("nav", market, goal), f"Navigate {market}: {goal}", body, action,
        success=True, pnl=0.0, domain="navigation", ref=f"nav:{market}")


def induce_from_trade(*, strategy: str, regime: str, direction: str, win: bool,
                      net_pnl: float = 0.0, signals=None, symbol: str = "") -> str | None:
    """The recipe a closed trade used → an entry instruction, graded with the real outcome.

    Called on EVERY close (win or loss) so a recipe's confidence tracks its live win-rate;
    losers sinking below the floor become material for the evolver to mutate."""
    strategy = str(strategy or "").strip()
    if not strategy:
        return None                                             # need a named recipe
    regime = str(regime or "any").strip()
    direction = str(direction or "either").strip().lower()
    sig_txt = ", ".join(str(s) for s in (signals or [])[:5]) or "the fused confluence"
    body = (f"1) Confirm the market regime is {regime}.\n"
            f"2) Wait for the {strategy} setup to fire.\n"
            f"3) Confirm supporting signals: {sig_txt}.\n"
            f"4) Size within the risk cap, then enter {direction}.")
    action = (f"Use when {strategy} fires in a {regime} regime for a {direction} entry; "
              f"verify: p_win clears the gate and the signals above are present. Induced "
              f"from a closed trade and graded on its real outcome.")
    fail_reason = (f"lost: {strategy} in a {regime} regime for a {direction} entry"
                   if not win else "")
    return _upsert_instruction(
        _key("trade", strategy, regime, direction),
        f"Enter {direction} in {regime} via {strategy}", body, action,
        success=bool(win), pnl=float(net_pnl or 0.0), domain="trading",
        ref=f"trade:{symbol}", fail_reason=fail_reason)
