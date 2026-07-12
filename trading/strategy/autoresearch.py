"""trading/strategy/autoresearch.py — the LIVE autoresearch champion loop (invent-beyond #5).

vp1's Karpathy-style autoresearch, activated: the strategy-generator portfolio (DEAP +
LLM-mutation + symbolic + quality-diversity + Optuna + alpha-mining + RD-Agent) already
exists behind ONE CPCV+DSR+FWER gate with the W5 leak tripwire and champion/challenger
lineage — this module is the missing DRIVER that runs it continuously on REAL market data
and keeps score, so strategy research compounds without anyone pressing a button.

  run_cycle() — one research cycle: pick a representative symbol per market (rotating
                through the eyes' UI-covered symbols for diversity), build OHLCV frames
                honoring UI-only mode (data_failsafe → eyes' captures; honest skip when
                a market has no fresh data), call evolved_link.breed() (DEAP + the full
                portfolio through the shared guardrail into the SkillLibrary), and
                persist an honest per-cycle record.
  status()    — the Trading-Researcher read: driver state + champion lineage + leak
                tripwire tail + library size, for /api/trading/researcher.

State: autoresearch.json (bounded history). W7 wiring: every cycle bumps the
'autoresearch' track record and appends a meta-note (what ran, what was admitted, cost).
Paper-first by design: admitted strategies only ever enter the SkillLibrary the paper
brain trades from; live promotion stays behind the W3 autonomy gates.

Env knobs:
  AUTORESEARCH_INTERVAL_S   driver cadence, seconds (default 900)
  AUTORESEARCH_BUDGET       candidates per generator per cycle (default 8)
  AUTORESEARCH_GENERATIONS  DEAP generations per cycle (default 2)
  AUTORESEARCH_POP          DEAP population per cycle (default 12)
  AUTORESEARCH_TF           timeframe researched (default 15m — the eyes' densest capture)
  AUTORESEARCH_SYMBOLS_CRYPTO / _NSE  comma lists overriding symbol rotation
"""
from __future__ import annotations

import logging
import os
import time

from trading import state

log = logging.getLogger("autoresearch")

_FILE = "autoresearch.json"
_HISTORY_MAX = 100
_MIN_ROWS = 60                    # guardrail minimum — below this a market is skipped


def _cfg_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except Exception:
        return default


def _store() -> dict:
    d = state.load_json(_FILE, {})
    d.setdefault("cycles", 0)
    t = d.setdefault("totals", {})
    for k in ("admitted", "tested", "errors", "skipped_markets"):
        t.setdefault(k, 0)              # repair subkeys too (partial/older state files)
    d.setdefault("history", [])
    return d


def _save(d: dict) -> None:
    d["history"] = d["history"][-_HISTORY_MAX:]
    state.save_json(_FILE, d)


# ── symbol rotation ──────────────────────────────────────────────────────────────────
def _crypto_symbols() -> list[str]:
    """Rotation pool: env override, else the symbols the eyes actually cover (UI-only
    compliant — research runs on the same data the brain trades on), else BTC."""
    env = os.environ.get("AUTORESEARCH_SYMBOLS_CRYPTO", "")
    if env.strip():
        return [s.strip() for s in env.split(",") if s.strip()]
    try:
        from trading.broker_sense import ui_data
        detail = ui_data.coverage().get("detail") or {}
        tf = os.environ.get("AUTORESEARCH_TF", "15m")
        syms = [s for s, e in detail.items()
                if tf in (e.get("tfs") or {}) and e.get("broker") != "upstox"]
        if syms:
            return sorted(syms)
    except Exception:
        pass
    return ["BTC/USDT"]


def _nse_symbols() -> list[str]:
    env = os.environ.get("AUTORESEARCH_SYMBOLS_NSE", "")
    if env.strip():
        return [s.strip() for s in env.split(",") if s.strip()]
    # UI-only mode: the eyes key Upstox captures by instrument_key ('NSE_EQ|INE…') —
    # ticker names would never match, so rotate over what the eyes actually cover.
    try:
        from trading.broker_sense import ui_data
        if ui_data.enabled():
            tf = os.environ.get("AUTORESEARCH_TF", "15m")
            detail = ui_data.coverage().get("detail") or {}
            syms = [s for s, e in detail.items()
                    if e.get("broker") == "upstox" and tf in (e.get("tfs") or {})]
            return sorted(syms)         # may be [] outside market hours — honest skip
    except Exception:
        pass
    try:  # API mode: the funnel's liquid F&O universe (static list; no API call here)
        from trading.screener.universe import NSE_FO_STOCKS
        syms = sorted(NSE_FO_STOCKS)[:20]
        if syms:
            return syms
    except Exception:
        pass
    return ["RELIANCE", "HDFCBANK", "TCS"]


def _pick(symbols: list[str], cycle: int) -> str:
    return symbols[cycle % len(symbols)] if symbols else ""


# ── data ─────────────────────────────────────────────────────────────────────────────
def _frame(symbol: str, market: str, timeframe: str):
    """[[ts,o,h,l,c,v],…] → the lowercase OHLCV DataFrame the guardrail/backtest expects.
    Returns (df|None, reason). Honors UI-only mode via data_failsafe (eyes' captures or
    an honest None — never a hidden API fallback)."""
    try:
        from trading.broker_sense.data_failsafe import ohlcv
        rows = ohlcv(symbol, market, timeframe=timeframe, limit=500)
    except Exception as e:
        return None, f"fetch error: {type(e).__name__}: {e}"[:120]
    if not rows or len(rows) < _MIN_ROWS:
        return None, f"insufficient data ({0 if not rows else len(rows)} rows < {_MIN_ROWS})"
    import pandas as pd
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    if len(df) < _MIN_ROWS:
        return None, f"insufficient clean rows ({len(df)})"
    df = df.reset_index(drop=True)
    # BINANCE-FILTER FEATURES (owner 2026-07-12: 'research strategies that use Binance's built-in
    # filters to pick symbols/direction'). Splice the app's OWN screener/order-flow signals —
    # funding, OI, taker buy/sell, long/short (retail + smart), captured from the account web app
    # (orderflow_store) — onto the candle frame by timestamp, so the strategy generators can BREED
    # rules over Binance's filter data, not just price. Same enrichment the direction equation uses;
    # bars before the store began carry NaN and are ignored. Best-effort — bare OHLCV if absent.
    if market == "crypto" and os.environ.get("AUTORESEARCH_BINANCE_FEATURES", "1") not in (
            "0", "false", "off"):
        try:
            df["ts"] = pd.to_numeric(df["date"], errors="coerce")
            from trading.strategy.direction_equation import features_bus
            enriched = features_bus(df, symbol=symbol, market="crypto")
            if enriched is not None and len(enriched) == len(df):
                df = enriched
        except Exception:
            pass
    return df, "ok"


# ── the cycle ────────────────────────────────────────────────────────────────────────
def run_cycle() -> dict:
    """One autoresearch cycle. Never raises; every outcome (including gated-off and
    no-data) is recorded honestly in autoresearch.json."""
    t0 = time.time()
    d = _store()
    cycle = d["cycles"] + 1
    tf = os.environ.get("AUTORESEARCH_TF", "15m")
    rec: dict = {"cycle": cycle, "ts": t0, "tf": tf, "markets": {}, "admitted": 0,
                 "tested": 0}

    ohlcv_by_market: dict = {}
    for market, picker in (("CRYPTO", _crypto_symbols), ("NSE", _nse_symbols)):
        sym = _pick(picker(), cycle)
        df, why = _frame(sym, market.lower(), tf) if sym else (None, "no symbols")
        rec["markets"][market] = {"symbol": sym, "data": why,
                                  "rows": 0 if df is None else int(len(df))}
        if df is not None:
            ohlcv_by_market[market] = df

    if not ohlcv_by_market:
        rec["result"] = "skipped: no market had fresh data (honest miss — see markets)"
        d["totals"]["skipped_markets"] += 1
    else:
        try:
            from trading.strategy import evolved_link
            res = evolved_link.breed(
                ohlcv_by_market,
                generations=_cfg_int("AUTORESEARCH_GENERATIONS", 2),
                pop_size=_cfg_int("AUTORESEARCH_POP", 12),
                seed=cycle)                        # deterministic per-cycle diversity
            if res.get("gated"):
                rec["result"] = "gated: strategy evolution OFF (trading.strategy.control)"
            else:
                # breed() already totals admissions (DEAP + portfolio) — reuse, don't re-derive
                admitted = int(res.get("admitted_total", 0) or 0)
                tested = 0
                for m in (res.get("markets") or {}).values():
                    tested += int((m or {}).get("evaluated", 0) or 0)   # DEAP candidates
                for m in (res.get("portfolio", {}).get("markets") or {}).values():
                    if isinstance(m, dict):
                        for g in m.values():
                            if isinstance(g, dict):
                                tested += int(g.get("tested", 0) or 0)
                rec["admitted"], rec["tested"] = admitted, tested
                rec["portfolio_generators"] = res.get("portfolio", {}).get("generators")
                rec["result"] = "ok"
                d["totals"]["admitted"] += admitted
                d["totals"]["tested"] += tested
        except Exception as e:
            rec["result"] = f"error: {type(e).__name__}: {e}"[:160]
            d["totals"]["errors"] += 1
            log.exception("autoresearch cycle %s failed", cycle)

    rec["took_s"] = round(time.time() - t0, 2)
    d["cycles"] = cycle
    d["last"] = rec
    d["interval_s"] = _cfg_int("AUTORESEARCH_INTERVAL_S", 900)  # the RUNNER's env is the
    d["history"].append(rec)                                    # truth for liveness math
    _save(d)

    # W7: the researcher keeps its own track record + meta-article trail.
    try:
        from trading.brain import track_record
        track_record.bump("autoresearch", kind="cycle",
                          win=(rec.get("admitted", 0) > 0) if rec["result"] == "ok" else None,
                          cost_cpu_s=rec["took_s"])
        track_record.meta_note(
            "autoresearch",
            what=f"cycle {cycle}: tested {rec.get('tested', 0)}, admitted "
                 f"{rec.get('admitted', 0)} ({rec['result']})",
            why=f"continuous strategy research on {tf} "
                f"{[m['symbol'] for m in rec['markets'].values() if m.get('symbol')]}",
            cost=f"{rec['took_s']}s CPU")
    except Exception:
        pass
    return rec


# ── the researcher view ──────────────────────────────────────────────────────────────
def status() -> dict:
    """Everything the Trading-Researcher panel shows — all read from real state."""
    d = _store()
    out = {"driver": {"cycles": d["cycles"], "totals": d["totals"],
                      "last": d.get("last"),
                      "recent": d["history"][-12:]},
           "champion_lineage": state.load_json("champion_lineage.json", {}),
           "leak_tripwire": state.load_json("leak_tripwire.json", [])[-15:]}
    # NOTE: deliberately NO evolved_link.status() here — that loads the SkillLibrary and
    # the generator stack, and this runs inside dashboard request threads (524 GIL-wedge
    # root cause). Library/generator detail lives on /api/trading/generators.
    try:
        from trading.strategy.control import evolution_enabled
        out["evolution_enabled"] = bool(evolution_enabled())
    except Exception:
        pass
    # Champion-bandit allocator (invent-beyond #3) — status() is dashboard-thread-safe by
    # design (persisted arms only, no SkillLibrary import).
    try:
        from trading.strategy import champion_bandit
        out["bandit"] = champion_bandit.status()
    except Exception:
        pass
    # Distilled micro-policy (invent-beyond #4) — status() reads persisted state only.
    try:
        from trading.crypto.freqtrade import micro_policy
        out["micro_policy"] = micro_policy.status()
    except Exception:
        pass
    # honest liveness: the last cycle is younger than 2 intervals, judged against the
    # interval the DAEMON recorded at cycle time (env can differ across processes)
    last_ts = (d.get("last") or {}).get("ts")
    interval = int(d.get("interval_s") or _cfg_int("AUTORESEARCH_INTERVAL_S", 900))
    out["driver"]["interval_s"] = interval
    out["driver"]["live"] = bool(last_ts and (time.time() - last_ts) < 2 * interval)
    return out
