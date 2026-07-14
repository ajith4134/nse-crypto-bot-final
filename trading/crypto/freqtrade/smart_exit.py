"""trading/crypto/freqtrade/smart_exit.py — intelligent open-trade EXIT beyond SL / target.

The engine already exits on: stop-loss (disaster), ROI/target, the profit-tailgate lock (rides &
locks a gain), and a library-ensemble *flip*. What it lacked was a FORWARD-LOOKING exit that uses the
new rich signals to notice a position has genuinely TURNED — before the stop is hit and without
waiting for the slow library ensemble to flip. This adds exactly that, as a higher-quality reason:

  1. Symbol-Move Net reversal — the two-head net now predicts the symbol moving AGAINST the open
     side (p_up crosses to the other side of its band AND expected_move_pct is a meaningful move the
     wrong way). This is the strongest new signal: it forecasts the symbol's forward move, not a
     lagging vote.
  2. Fused-direction flip — learned_direction (the reliability-weighted meta-learner) now calls the
     OPPOSITE side with real edge (not an abstain). A proven directional source turning against the
     trade is a real exit, not noise.
  3. UQ collapse (advisory) — conformal p_up for the held side drops below the abstain gate: the
     brain no longer has a calibrated reason to be in the trade. Counts toward, never forces, an exit.

Design: paper-first, kill-switched (SMART_EXIT=1 default; SMART_EXIT=0 disables), pure/O(1) per call
(one cached move-net forward pass; the fused re-check only runs when the caller already has the live
readings, so no extra collection on the exit path). Never raises. It ADDS exits, it never blocks the
stop-loss or tailgate. Requires >= SMART_EXIT_MIN_SIGNALS *strong* reversals (move-net or dir-flip;
UQ alone is advisory) so a single noisy cycle can't churn a position out.

Env knobs:
  SMART_EXIT=1                 master switch
  SMART_EXIT_MIN_SIGNALS=1     strong reversals required to exit (move_net | dir_flip)
  SMART_EXIT_PDOWN=0.42        LONG exit needs p_up below this (SHORT: p_up above 1-this)
  SMART_EXIT_MOVE_PCT=1.0      |expected_move_pct| the wrong way must clear this (%)
"""
from __future__ import annotations

import os


def _flag(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def should_exit(symbol: str, side: str, *, market: str = "CRYPTO", segment: str = "futures",
                regime: str | None = None, readings=None, decision_snapshot=None) -> dict:
    """Return {exit, reason, signals} — does the new evidence say this open position has TURNED?

    `side` is the OPEN side (LONG/SHORT). `readings` (optional) is the live [(source, p_up)] list
    the caller already collected; when present the fused-direction re-check reuses it (no 2nd
    collect). Never raises — any lens error is skipped and simply doesn't vote.
    """
    out = {"exit": False, "reason": "", "signals": {}}
    if not _flag("SMART_EXIT_ON"):                    # compute switch (default on); the CALLER
        return out                                    # decides act-vs-shadow (SMART_EXIT=trade)
    s = (side or "").upper()
    if s not in ("LONG", "SHORT"):
        return out
    strong: list[str] = []
    advisory: list[str] = []
    sig = out["signals"]

    p_down = _f("SMART_EXIT_PDOWN", 0.42)
    move_th = _f("SMART_EXIT_MOVE_PCT", 1.0)

    # 1) Symbol-Move Net reversal (the strongest, cheapest new signal) ─────────────────
    try:
        from trading.brain import symbol_move_net as _smn
        sm = _smn.consult({"symbol": symbol, "direction": s, "market": market,
                           "exchange": "binance", "market_regime_entry": regime or "",
                           "decision_snapshot": decision_snapshot or {}})
        if sm.get("trained"):
            pu, mv = sm.get("p_up"), sm.get("expected_move_pct")
            sig["move_net"] = {"p_up": pu, "move_pct": mv}
            if pu is not None and mv is not None:
                if s == "LONG" and pu < p_down and mv < -move_th:
                    strong.append("move_net_reversal")
                elif s == "SHORT" and pu > (1.0 - p_down) and mv > move_th:
                    strong.append("move_net_reversal")
    except Exception:
        pass

    # 2) Fused-direction flip — learned_direction now calls the opposite side with real edge ──
    try:
        if readings:
            from trading.direction import learned_direction as _ld
            d = _ld.decide(readings, market=market, segment=segment, regime=regime, symbol=symbol)
            sig["fused"] = {"direction": d.get("direction"), "p_up": d.get("p_up"),
                            "abstained": d.get("abstained")}
            if not d.get("abstained"):
                flipped = (s == "LONG" and d.get("direction") == "short") or \
                          (s == "SHORT" and d.get("direction") == "long")
                if flipped:
                    strong.append("direction_flip")
    except Exception:
        pass

    # 3) UQ collapse (advisory) — conformal p_up for the held side below the abstain gate ────
    try:
        from trading.uq import conformal as _uq
        held_p = None
        if sig.get("fused", {}).get("p_up") is not None:
            fp = sig["fused"]["p_up"]
            held_p = fp if s == "LONG" else (1.0 - fp)
        if held_p is not None and hasattr(_uq, "gate_theta"):
            if held_p < _uq.gate_theta():
                advisory.append("uq_collapse")
                sig["uq"] = {"held_p": round(held_p, 4), "theta": _uq.gate_theta()}
    except Exception:
        pass

    need = int(_f("SMART_EXIT_MIN_SIGNALS", 1))
    out["exit"] = len(strong) >= max(1, need)
    out["reason"] = "smart_exit:" + ",".join(strong + advisory) if (strong or advisory) else ""
    out["strong"], out["advisory"] = strong, advisory
    return out
