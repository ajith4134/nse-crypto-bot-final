"""trading/scouts.py — W4 smart-money scout swarm + consensus oracle + dispatcher.

Owner goal 2026-07-07 (video vp6 "Insider Routines"): NAMED scouts each watch ONE
smart-money signal source; **Sophie, the consensus oracle, never acts on one signal
alone** — she fires a CONSENSUS event only when ≥ DELPHI_MIN_AGREE scouts agree on the
same symbol + direction within DELPHI_WINDOW_DAYS. **Ross, the dispatcher, is the only
outward voice and NEVER trades** — he posts read-only alerts (mind-events / Brain Chat).
The funnel reads consensus as one more advisory signal (smart_money_consensus) fused
into decision_snapshot.

UI-only-data compliant: v1 scouts read feeds the system ALREADY has (the eyes'
interception captures + the funnel's own fusion + order-book psychology) — no new API
polling. Scouts for NSE insider disclosures / FII-DII flows / central-bank speeches
join as the human-UI crawl starts capturing those pages (they register the same way).

State: scout_signals.json (bounded). Honest: a scout that finds nothing reports
{"signals": 0}; consensus with too few active scouts reports "insufficient-scouts",
never a fabricated agreement.
"""
from __future__ import annotations

import os
import time

from trading import state

_FILE = "scout_signals.json"
_MAX = 3000


def _cfg_min_agree() -> int:
    return int(os.environ.get("DELPHI_MIN_AGREE", "2"))       # 2 while the swarm is small


def _cfg_window_s() -> float:
    return float(os.environ.get("DELPHI_WINDOW_DAYS", "7")) * 86400.0


def _store() -> dict:
    d = state.load_json(_FILE, {})
    d.setdefault("signals", [])
    d.setdefault("consensus", [])
    return d


def _save(d: dict) -> None:
    d["signals"] = d["signals"][-_MAX:]
    d["consensus"] = d["consensus"][-300:]
    state.save_json(_FILE, d)


def record_signal(scout: str, *, symbol: str, market: str, direction: str,
                  strength: float, detail: str = "") -> dict:
    """A scout's finding. direction ∈ long|short; strength ∈ (0,1]."""
    sig = {"scout": scout, "symbol": symbol, "market": market,
           "direction": direction, "strength": round(float(strength), 4),
           "detail": detail[:200], "ts": time.time()}
    d = _store()
    d["signals"].append(sig)
    _save(d)
    return sig


# ── the v1 scouts (existing real feeds only) ─────────────────────────────────────────
def run_whale_prints_scout() -> int:
    """'Maya': large-print detection over the eyes' captured recent_trades payloads
    (interception kind recent_trades). A burst of outsized prints on one side = whale
    accumulation/distribution. Zero polling — reads what the apps already showed us."""
    n = 0
    try:
        from trading.broker_sense.interception import get_recorder
        rec = get_recorder()
        for (broker, kind), row in list(rec._cache.items()):
            if kind != "recent_trades" or time.time() - row["ts"] > 900:
                continue
            body = row.get("body")
            trades = body if isinstance(body, list) else \
                (body or {}).get("data") or (body or {}).get("trades") or []
            if not isinstance(trades, list) or len(trades) < 10:
                continue
            import re
            m = re.search(r"symbol=([A-Za-z0-9]+)", row.get("url", ""))
            sym = m.group(1).upper() if m else None
            if not sym:
                continue
            vals, sides = [], []
            for t in trades[:200]:
                if not isinstance(t, dict):
                    continue
                try:
                    q = float(t.get("qty") or t.get("q") or t.get("quantity") or 0)
                    p = float(t.get("price") or t.get("p") or 0)
                    vals.append(q * p)
                    sides.append(bool(t.get("isBuyerMaker") if "isBuyerMaker" in t
                                      else t.get("m", False)))
                except Exception:
                    continue
            if len(vals) < 10 or not sum(vals):
                continue
            avg = sum(vals) / len(vals)
            big = [(v, s) for v, s in zip(vals, sides) if v >= 5 * avg]
            if len(big) < 3:
                continue
            buy_vol = sum(v for v, maker in big if not maker)   # taker-buy prints
            sell_vol = sum(v for v, maker in big if maker)
            tot = buy_vol + sell_vol
            if not tot:
                continue
            skew = (buy_vol - sell_vol) / tot
            if abs(skew) >= 0.5:
                record_signal("maya-whale-prints", symbol=sym, market="crypto",
                              direction="long" if skew > 0 else "short",
                              strength=min(1.0, abs(skew)),
                              detail=f"{len(big)} outsized prints, skew {skew:+.2f} "
                                     f"({broker})")
                n += 1
    except Exception:
        pass
    return n


def run_crowd_psych_scout() -> int:
    """'Frank': order-book imbalance from the eyes' captured depth payloads
    (interception kind 'book'/'depth') — a strongly one-sided book = crowd pressure.
    Zero polling: reads only what the trading apps already displayed."""
    n = 0
    try:
        import re

        from trading.broker_sense.interception import get_recorder
        rec = get_recorder()
        for (broker, kind), row in list(rec._cache.items()):
            if kind not in ("book", "depth", "orderbook") or \
                    time.time() - row["ts"] > 900:
                continue
            body = row.get("body") or {}
            bids = body.get("bids") or body.get("b") or \
                (body.get("data") or {}).get("bids") if isinstance(body, dict) else None
            asks = body.get("asks") or body.get("a") or \
                (body.get("data") or {}).get("asks") if isinstance(body, dict) else None
            if not bids or not asks:
                continue
            m = re.search(r"symbol=([A-Za-z0-9]+)", row.get("url", ""))
            sym = m.group(1).upper() if m else None
            if not sym:
                continue
            try:
                bv = sum(float(b[1]) for b in bids[:10])
                av = sum(float(a[1]) for a in asks[:10])
            except Exception:
                continue
            tot = bv + av
            if not tot:
                continue
            obi = (bv - av) / tot
            if abs(obi) >= 0.45:
                record_signal("frank-crowd-psych", symbol=sym, market="crypto",
                              direction="long" if obi > 0 else "short",
                              strength=min(1.0, abs(obi)),
                              detail=f"top-10 OBI {obi:+.2f} ({broker})")
                n += 1
    except Exception:
        pass
    return n


def run_fusion_conviction_scout(app_signals: dict | None = None) -> int:
    """'Eddie': the funnel's own multi-TF fusion at HIGH conviction (|confluence|≥0.6)
    counts as one independent voice (it already blends numeric+vision lenses).
    Accepts both raw fuse() dicts and the funnel wrapper {indicator_fusion, vote, …}."""
    n = 0
    for sym, raw in (app_signals or {}).items():
        try:
            if not isinstance(raw, dict):
                continue
            sig = raw.get("indicator_fusion") if isinstance(
                raw.get("indicator_fusion"), dict) else raw
            if not sig.get("available"):
                continue
            conf = float(sig.get("confluence") or 0)
            if abs(conf) >= 0.6 and sig.get("direction") in ("long", "short"):
                record_signal("eddie-fusion-conviction", symbol=sym,
                              market=sig.get("market", "crypto"),
                              direction=sig["direction"], strength=abs(conf),
                              detail=f"confluence {conf:+.2f} regime={sig.get('regime')}")
                n += 1
        except Exception:
            continue
    return n


# ── Sophie: the consensus oracle ─────────────────────────────────────────────────────
def sophie_consensus() -> list[dict]:
    """≥ min_agree DISTINCT scouts agree on symbol+direction inside the window →
    CONSENSUS event (deduped per symbol+direction per window)."""
    d = _store()
    cut = time.time() - _cfg_window_s()
    fresh = [s for s in d["signals"] if s["ts"] >= cut]
    agree: dict[tuple, dict] = {}
    for s in fresh:
        k = (s["symbol"], s["direction"])
        e = agree.setdefault(k, {"scouts": {}, "market": s["market"]})
        prev = e["scouts"].get(s["scout"])
        if prev is None or s["strength"] > prev:
            e["scouts"][s["scout"]] = s["strength"]
    events = []
    fired = {(c["symbol"], c["direction"]) for c in d["consensus"]
             if c["ts"] >= cut}
    for (sym, direction), e in agree.items():
        if len(e["scouts"]) >= _cfg_min_agree() and (sym, direction) not in fired:
            ev = {"symbol": sym, "direction": direction, "market": e["market"],
                  "n_scouts": len(e["scouts"]),
                  "scouts": {k: round(v, 3) for k, v in e["scouts"].items()},
                  "strength": round(sum(e["scouts"].values()) / len(e["scouts"]), 4),
                  "ts": time.time()}
            d["consensus"].append(ev)
            events.append(ev)
    if events:
        _save(d)
        _ross_dispatch(events)
    return events


def consensus_for(symbol: str) -> dict | None:
    """The funnel's read: a fresh consensus event for this symbol, else None."""
    d = _store()
    cut = time.time() - _cfg_window_s()
    for c in reversed(d["consensus"]):
        if c["ts"] >= cut and c["symbol"] in (symbol, symbol.replace("/", "")
                                              .replace(":USDT", "")):
            return c
    return None


# ── Ross: the dispatcher (read-only; NEVER trades) ───────────────────────────────────
def _ross_dispatch(events: list[dict]) -> None:
    try:
        from trading.brain import mind_events
        for ev in events:
            mind_events.emit(
                "smart-money",
                f"[CONSENSUS] {ev['direction'].upper()} {ev['symbol']} — "
                f"{ev['n_scouts']} scouts agree ({', '.join(ev['scouts'])}); "
                f"strength {ev['strength']:.2f}. Ross never places trades — "
                f"the scouts show what's worth looking at.",
                salience=0.85)
    except Exception:
        pass


def run_all(app_signals: dict | None = None) -> dict:
    """One scout sweep + consensus pass (called from the funnel cycle; never raises)."""
    out = {"eddie": run_fusion_conviction_scout(app_signals),
           "maya": run_whale_prints_scout(),
           "frank": run_crowd_psych_scout()}
    out["consensus_events"] = len(sophie_consensus())
    return out


def status() -> dict:
    d = _store()
    cut = time.time() - _cfg_window_s()
    fresh = [s for s in d["signals"] if s["ts"] >= cut]
    per = {}
    for s in fresh:
        per[s["scout"]] = per.get(s["scout"], 0) + 1
    return {"min_agree": _cfg_min_agree(),
            "window_days": _cfg_window_s() / 86400.0,
            "active_scouts": per, "signals_in_window": len(fresh),
            "recent_consensus": d["consensus"][-10:],
            "note": ("insufficient-scouts" if len(per) < _cfg_min_agree() else "ok")}
