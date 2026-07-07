"""trading/goal.py — W1 goal scoreboard: score EVERY trade + segment against goal.yaml.

Owner goal 2026-07-07 ("no vibes, just numbers", videos vp0/self-improving-agent):
success AND failure are DEFINED numerically per segment in `trading/goal.yaml`; every
closed trade gets a toward-goal score, and every segment gets a trailing-30-day
scoreboard (return vs target, drawdown vs limit, Sharpe vs bar, failure line) with an
honest verdict. The self-evolve / learning loops treat this as THE optimization target;
dashboards read the persisted snapshot (state: goal_score.json).

Pure stdlib + PyYAML; journal is the single source of truth (no fabricated numbers —
segments with no trades report verdict "no-data", never a fake 0.0 score).
"""
from __future__ import annotations

import datetime as dt
import math
import os
import time

from trading import state

_GOAL_FILE = os.path.join(os.path.dirname(__file__), "goal.yaml")
_SNAPSHOT = "goal_score.json"
_WINDOW_DAYS = 30

_DEF_SEG = {"capital_base": 10000.0, "target_return_30d": 0.10, "max_drawdown": 0.20,
            "min_sharpe": 1.0, "failure_below": -0.05}


# ── config ────────────────────────────────────────────────────────────────────────────
def load_goals() -> dict:
    """goal.yaml as a dict (re-read every call — the owner may edit it live).
    Falls back to built-in defaults when the file is missing/unparseable (honest note)."""
    try:
        import yaml
        with open(_GOAL_FILE) as fh:
            d = yaml.safe_load(fh) or {}
        d.setdefault("defaults", {})
        return d
    except Exception as e:
        return {"defaults": {"reflection_every_days": 7, "one_variable_only": True},
                "_error": f"goal.yaml unavailable ({e!r}) — built-in defaults in use"}


def segment_goal(market: str, segment: str) -> dict:
    """The numeric goal block for one market/segment (merged over defaults)."""
    g = load_goals()
    seg = ((g.get(market.lower()) or {}).get(segment.lower()) or {})
    out = dict(_DEF_SEG)
    out.update({k: v for k, v in seg.items() if v is not None})
    out["reflection_every_days"] = (g.get("defaults") or {}).get("reflection_every_days", 7)
    out["one_variable_only"] = bool((g.get("defaults") or {}).get("one_variable_only", True))
    return out


# ── per-trade scoring ─────────────────────────────────────────────────────────────────
def _seg_of(row: dict) -> tuple[str, str]:
    """(market, segment) for a journal row/dict — same rules the journal uses."""
    exch = (row.get("exchange") or "").lower()
    market = "crypto" if exch in ("binance", "bybit", "okx", "kucoin") or \
        (row.get("instrument_type") in ("PERP", "SPOT") and "usdt" in
         (row.get("symbol") or "").lower()) else "nse"
    seg = (row.get("bot_segment") or "").lower()
    if not seg:
        it = (row.get("instrument_type") or "").upper()
        seg = {"PERP": "futures", "SPOT": "spot", "FUT": "futures",
               "CE": "options", "PE": "options", "OPT": "options"}.get(it, "equity")
    if market == "nse" and seg in ("futures", "spot"):
        seg = {"spot": "equity"}.get(seg, seg)
    return market, seg


def score_trade(row: dict) -> dict:
    """Score ONE closed trade against its segment goal.

    score = the trade's net PnL as a fraction of the segment's DAILY goal pace
    (capital_base * target_return_30d / 30): +1.0 ≈ "this one trade earned a whole
    day of the goal". toward_goal is the plain sign. Never raises."""
    try:
        market, seg = _seg_of(row)
        g = segment_goal(market, seg)
        pnl = float(row.get("net_pnl") or 0.0)
        daily_pace = max(1e-9, float(g["capital_base"]) * float(g["target_return_30d"]) / 30.0)
        score = pnl / daily_pace
        return {"market": market, "segment": seg, "net_pnl": pnl,
                "goal_score": round(score, 4), "toward_goal": pnl > 0,
                "daily_goal_pace": round(daily_pace, 4)}
    except Exception as e:
        return {"goal_score": None, "toward_goal": None, "error": str(e)[:80]}


# ── segment scoreboard ────────────────────────────────────────────────────────────────
def _parse_ts(s: str) -> float | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(str(s)[:19], fmt).timestamp()
        except Exception:
            continue
    return None


def _daily_series(rows: list[dict]) -> dict[str, float]:
    days: dict[str, float] = {}
    for r in rows:
        d = str(r.get("exit_datetime") or r.get("entry_datetime") or "")[:10]
        if d:
            days[d] = days.get(d, 0.0) + float(r.get("net_pnl") or 0.0)
    return dict(sorted(days.items()))


def _max_drawdown(daily: dict[str, float], base: float) -> float:
    eq, peak, mdd = 0.0, 0.0, 0.0
    for v in daily.values():
        eq += v
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / max(base, 1e-9))
    return mdd


def _sharpe(daily: dict[str, float], base: float) -> float | None:
    rets = [v / max(base, 1e-9) for v in daily.values()]
    if len(rets) < 5:
        return None
    mu = sum(rets) / len(rets)
    var = sum((r - mu) ** 2 for r in rets) / max(1, len(rets) - 1)
    sd = math.sqrt(var)
    if sd <= 0:
        return None
    return (mu / sd) * math.sqrt(365.0)


def scoreboard(trades: list | None = None, window_days: int = _WINDOW_DAYS) -> dict:
    """Trailing-window scoreboard for EVERY market/segment with trades + configured goals.

    trades: optional pre-fetched list of journal rows (dicts or ClosedTrade); default =
    the canonical journal. Returns {segments: {market.segment: {...verdict...}},
    generated_ts} and persists it to state (goal_score.json) for cheap dashboard reads."""
    if trades is None:
        from trading.journal import TradeJournal
        trades = [t.to_dict() for t in TradeJournal(state_file="journal.json",
                                                    persist=True).trades]
    rows = [t if isinstance(t, dict) else t.to_dict() for t in trades]
    cutoff = time.time() - window_days * 86400.0
    recent = [r for r in rows
              if (_parse_ts(r.get("exit_datetime") or r.get("entry_datetime") or "")
                  or 0) >= cutoff]

    goals = load_goals()
    seg_rows: dict[tuple, list] = {}
    for r in recent:
        seg_rows.setdefault(_seg_of(r), []).append(r)
    # configured segments always appear (even with 0 trades — verdict no-data, honest)
    for market in ("crypto", "nse"):
        for seg in (goals.get(market) or {}):
            seg_rows.setdefault((market, seg), [])

    out: dict = {"window_days": window_days, "generated_ts": time.time(), "segments": {}}
    for (market, seg), rs in sorted(seg_rows.items()):
        g = segment_goal(market, seg)
        base = float(g["capital_base"])
        pnl = sum(float(r.get("net_pnl") or 0.0) for r in rs)
        ret = pnl / max(base, 1e-9)
        daily = _daily_series(rs)
        mdd = _max_drawdown(daily, base)
        sharpe = _sharpe(daily, base)
        target = float(g["target_return_30d"])
        if not rs:
            verdict = "no-data"
        elif ret <= float(g["failure_below"]):
            verdict = "failing"
        elif mdd > float(g["max_drawdown"]):
            verdict = "drawdown-breach"
        elif ret >= target:
            verdict = "goal-met"
        elif ret > 0:
            verdict = "toward-goal"
        else:
            verdict = "off-track"
        out["segments"][f"{market}.{seg}"] = {
            "n_trades": len(rs), "pnl": round(pnl, 4), "capital_base": base,
            "return_window": round(ret, 6), "target_return_30d": target,
            "progress_to_target": round(ret / target, 4) if target else None,
            "max_drawdown": round(mdd, 6), "dd_limit": float(g["max_drawdown"]),
            "sharpe": round(sharpe, 3) if sharpe is not None else None,
            "min_sharpe": float(g["min_sharpe"]),
            "failure_below": float(g["failure_below"]),
            "verdict": verdict,
        }
    if "_error" in goals:
        out["config_note"] = goals["_error"]
    try:
        state.save_json(_SNAPSHOT, out)
    except Exception:
        pass
    return out


def last_scoreboard() -> dict:
    """The persisted snapshot (cheap read for panels/boss); {} when never computed."""
    try:
        return state.load_json(_SNAPSHOT, {})
    except Exception:
        return {}
