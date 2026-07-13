"""trading/direction/dir_exit.py — D-exit: the directional EXIT oracle (Pillar 27).

The Truth Ledger proved WHERE the losses come from. Entry direction is right at the
1h/4h horizons on the good lanes (54-69%), but by the ACTUAL exit it collapses to
~33% — trades are held past the window where their direction was correct, straight
into the reversal, round-tripping the gain. The profit-tailgate exit is PROFIT-shaped
(arm at +0.5%, retrace off the peak); it has no idea whether the direction THESIS that
justified the trade is still alive.

This oracle answers one question for an OPEN position: is the calibrated direction read
still on our side, or has it flipped against us? It reuses the SAME machinery the entry
side already proved out — the D4 micro-feature lanes for the live read, the D2 Mirror
Gate's calibration so an anti-signal lane is counted the RIGHT way round, and the D5
regime as the bucket. When the calibrated OPPOSING evidence clears a bar, the reason we
entered is gone → cut, capturing the correct window instead of round-tripping it.

Discipline (identical to the rest of the program — shadow → prove → promote):
  * SHADOW by default (DIR_EXIT=shadow): record the current read as a "dir_exit"
    Truth-Ledger claim + return an ADVISORY flag, but NEVER force an exit — so we
    MEASURE whether acting would have helped before it earns any live weight. The
    "dir_exit" source then earns its own measured hit-rate: when it said the direction
    had flipped to X, was X actually correct over the next hour? If yes, cutting a
    position that was opposite X was justified.
  * DIR_EXIT=trade: act, but ONLY when the OPPOSING read is itself CALIBRATED (lanes
    with n >= MIRROR_MIN_N whose Wilson interval beats chance). An uncalibrated read
    stays advisory even in trade mode — exploration is never cut on a hunch.
  * DIR_EXIT=0 disables entirely (pure hold — the tailgate/stop still run).

Read-only advisory: returns a decision the exec layer acts on; it never places an order.
Crypto-native (the micro lanes are crypto feathers/venues); other markets get an honest
no-signal read until their own lanes land.

Levers: DIR_EXIT (shadow|trade|0, default shadow), DIR_EXIT_STRENGTH (net opposing
weight in [0,1] to fire, default 0.6), DIR_EXIT_HORIZON (default 1h — the same
fixed-horizon truth the Mirror Gate judges sources on, never the exit-polluted labels).
"""
from __future__ import annotations

import os


def _env_f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def mode() -> str:
    """'off' | 'shadow' | 'trade'. Default shadow (measure before it earns weight)."""
    v = (os.environ.get("DIR_EXIT", "shadow") or "shadow").strip().lower()
    if v in ("0", "off", "false", "no"):
        return "off"
    if v in ("trade", "live", "act", "on", "1", "true", "yes"):
        return "trade"
    return "shadow"


def _horizon() -> str | None:
    """Single-horizon override for the calibration read; None → let the Mirror Gate
    pool its clean horizons (the honest default — tighter, stable-error CIs)."""
    return os.environ.get("DIR_EXIT_HORIZON") or None


def read(symbol: str, market: str = "CRYPTO", segment: str = "futures", *,
         regime: str | None = None, include_network: bool = True) -> dict:
    """Calibrated live directional read for one symbol. Each D4 micro lane votes; the
    Mirror Gate corrects the vote for the lane's MEASURED reliability (an anti-signal
    lane flips, a proven coin-flip abstains) and hands back the Wilson calibration.
    Lane weights are aggregated into a net strength in [-1, 1] (+ = LONG).

    Returns {direction, strength, cal_strength, n_lanes, n_calibrated, regime, votes[]}.
    A "calibrated" lane is one with n >= MIRROR_MIN_N whose interval beats chance — only
    those move cal_strength, the number trade-mode is allowed to ACT on."""
    out = {"symbol": symbol, "direction": None, "strength": 0.0, "cal_strength": 0.0,
           "n_lanes": 0, "n_calibrated": 0, "regime": regime, "votes": []}
    try:
        from trading.direction import micro_features, mirror_gate
        if regime is None:
            try:
                from trading.direction.regime import classify
                regime = classify(symbol, (segment or "futures").lower()).get("regime")
            except Exception:
                regime = None
        out["regime"] = regime
        snap = micro_features.snapshot(symbol, segment, include_network=include_network)
        hz = _horizon()
        min_n = int(_env_f("MIRROR_MIN_N", 30))
        net = 0.0
        cal_net = 0.0
        total_w = 0.0
        cal_total = 0.0
        for lane in micro_features.LANES:
            raw = (snap.get(lane) or {}).get("vote")
            if raw not in ("LONG", "SHORT"):
                continue
            conf = (snap.get(lane) or {}).get("conf") or 0.0
            g = mirror_gate.decide(raw, source=lane, regime=regime, horizon=hz, market=market)
            corrected = g.get("direction")
            if corrected not in ("LONG", "SHORT"):
                continue                              # gate abstained → no vote
            sgn = 1.0 if corrected == "LONG" else -1.0
            w = max(0.15, min(1.0, float(conf) or 0.3))
            n = int(g.get("n") or 0)
            rate = g.get("rate")
            ci_low = g.get("ci_low")
            # calibrated = enough evidence AND the interval clears chance for the
            # direction we'll actually count (an inverted lane clears via ci_high<invert
            # which the gate already resolved into `corrected`; a trusted lane via ci_low)
            calibrated = n >= min_n and (
                g.get("action") == "invert"
                or (ci_low is not None and ci_low > 0.5))
            if calibrated and rate is not None:
                edge = min(1.0, abs(float(rate) - 0.5) * 2.0)   # 0..1 distance from chance
                w *= (0.5 + edge)                                 # measured lanes count more
                cal_net += sgn * w
                cal_total += w
            net += sgn * w
            total_w += w
            out["n_lanes"] += 1
            if calibrated:
                out["n_calibrated"] += 1
            out["votes"].append({"lane": lane, "raw": raw, "corrected": corrected,
                                 "weight": round(w, 3), "calibrated": calibrated,
                                 "n": n, "rate": rate, "action": g.get("action")})
        if total_w > 0:
            out["strength"] = round(net / total_w, 4)
        if cal_total > 0:
            out["cal_strength"] = round(cal_net / cal_total, 4)
        s = out["strength"]
        out["direction"] = "LONG" if s > 0 else "SHORT" if s < 0 else None
    except Exception:
        pass                                          # trading-loop safety: never raise
    return out


def evaluate(*, symbol: str, direction: str, market: str = "CRYPTO",
             segment: str = "futures", regime: str | None = None,
             ref_price: float | None = None, trade_id: str | None = None,
             include_network: bool = True, record: bool = True) -> dict:
    """Directional-exit decision for ONE open position (direction LONG/SHORT).

    Records the current calibrated read as a "dir_exit" Truth-Ledger claim (so the
    oracle earns its own measured accuracy), then decides:
      shadow → exit=False, advisory_exit reflects whether the OPPOSING read cleared the
               bar (what trade-mode WOULD have done, for measurement).
      trade  → exit=True only when the CALIBRATED opposing read clears the bar.

    Returns {exit, advisory_exit, mode, opposing, cal_opposing, strength, direction,
             reason, n_calibrated, regime, read}. Never raises."""
    m = mode()
    pos = (direction or "").strip().upper()
    res = {"exit": False, "advisory_exit": False, "mode": m, "opposing": 0.0,
           "cal_opposing": 0.0, "strength": 0.0, "direction": None,
           "reason": "off" if m == "off" else "no-read", "n_calibrated": 0,
           "regime": regime, "read": None}
    if m == "off" or pos not in ("LONG", "SHORT"):
        return res
    try:
        r = read(symbol, market, segment, regime=regime, include_network=include_network)
        res["read"] = r
        res["strength"] = r["strength"]
        res["direction"] = r["direction"]
        res["regime"] = r["regime"]
        res["n_calibrated"] = r["n_calibrated"]
        pos_sgn = 1.0 if pos == "LONG" else -1.0
        # opposing > 0 means the read points AGAINST the open position
        opposing = round(-pos_sgn * r["strength"], 4)
        cal_opposing = round(-pos_sgn * r["cal_strength"], 4)
        res["opposing"] = opposing
        res["cal_opposing"] = cal_opposing
        thr = _env_f("DIR_EXIT_STRENGTH", 0.6)
        # shadow claim: the read's current direction, so "dir_exit" earns a hit-rate.
        if record and r["direction"] in ("LONG", "SHORT"):
            try:
                from trading.direction import truth_ledger
                truth_ledger.record(symbol=symbol, market=market, segment=segment,
                                    direction=r["direction"], source="dir_exit",
                                    regime=r["regime"], confidence=abs(r["strength"]),
                                    ref_price=ref_price, trade_id=trade_id)
            except Exception:
                pass
        advisory = opposing >= thr
        res["advisory_exit"] = advisory
        calibrated_exit = cal_opposing >= thr and r["n_calibrated"] >= 1
        if m == "trade" and calibrated_exit:
            res["exit"] = True
            res["reason"] = (f"dir-exit: calibrated read flipped to {r['direction']} vs "
                             f"{pos} (opposing {cal_opposing:.2f} >= {thr:.2f}, "
                             f"{r['n_calibrated']} calibrated lane(s))")
        elif advisory:
            res["reason"] = (f"advisory: read {r['direction']} opposes {pos} "
                             f"(opposing {opposing:.2f} >= {thr:.2f}; "
                             + ("uncalibrated — held" if m == "trade" else "shadow")
                             + ")")
        else:
            res["reason"] = f"thesis intact (opposing {opposing:.2f} < {thr:.2f})"
    except Exception:
        pass
    return res


def status() -> dict:
    """Dashboard/inspection snapshot: current mode + thresholds."""
    return {"mode": mode(), "horizon": _horizon() or "pooled",
            "strength_bar": _env_f("DIR_EXIT_STRENGTH", 0.6),
            "min_n": int(_env_f("MIRROR_MIN_N", 30))}
