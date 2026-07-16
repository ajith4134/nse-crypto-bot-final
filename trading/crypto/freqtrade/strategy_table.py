"""trading/crypto/freqtrade/strategy_table.py — the per-coin BEST-STRATEGY table (2026-07-13).

Closes the last gap in the strategy-creator loop. The foundry + 6 generators + DEAP evolution +
autoresearch all admit survivors into the SkillLibrary, and `library.created` merges them into the
tournament's registry (218 executable strategies). The per-coin tournament (`PerCoinBrainDecider`)
ranks all of them × brain-confidence per coin — but it is EXPENSIVE (~7.5s/coin: ~142 strategies ×
backtest + TabPFN), so the live Binance-filter breadth lane (which opens most trades, up to 50/cycle)
deliberately SKIPS it and tags every trade `learned_direction`. Result: the created / evolved /
researched strategies never touched — or appeared on — the breadth trades.

This module is the PRODUCER that fixes that without paying the cost in the hot entry path: a small
`nice-10` background pass runs the (already per-5m-bar-memoized) tournament over the covered universe
and writes ONE state file — `per_coin_strategy.json`:

    { "BTC/USDT:USDT": {"best_strategy": "pysr_crypto_0_4", "score": 1.83, "signal": "LONG",
                         "cleared_gate": true, "psr": 0.71, "sharpe": 2.1, "win_rate": 0.58,
                         "n_candidates": 214, "ts": 1783980000.0}, ... }

Consumers read it O(1):
  • attribution   — `_record_entry_meta` stamps best_fit_* onto EVERY trade (all lanes) → the
                    Strategy column shows a real library/created strategy, never a bare driver.
  • synergy       — the breadth lane feeds the best strategy's signal into `learned_direction`
                    (a measured source) and lets a gate-clearing strategy DRIVE the entry
                    (STRATEGY_DIRECTION flag). The truth-ledger then grades it → created/evolved/
                    researched strategies earn or lose trust from real outcomes. Loop closed.

Reuse-first: the ranking is `PerCoinBrainDecider.tournament()` verbatim (its SCAN_MEMO cache means
a coin the selective lane already scored this bar costs ~0 here). No new ML — this is the wiring /
persistence the capability was missing.

Env knobs:
  STRATEGY_TABLE_INTERVAL_S  producer cadence, seconds (default 300 = one 5m bar)
  STRATEGY_TABLE_BATCH       coins refreshed per pass (default 40) — round-robins the universe
  STRATEGY_TABLE_TTL_S       a coin's row is 'fresh' for this long (default 1800 = 30m)
  STRATEGY_TABLE_SYMBOLS     comma list overriding the coin universe (else eyes' coverage)
"""
from __future__ import annotations

import logging
import os
import time

from trading import state

log = logging.getLogger("strategy_table")

_FILE = "per_coin_strategy.json"
_DECIDER = None                      # lazily-built PerCoinBrainDecider (heavy import), reused
_ROTATE = 0                          # round-robin cursor across the universe


def _cfg_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default


def ttl_s() -> int:
    return _cfg_int("STRATEGY_TABLE_TTL_S", 1800)


# ── the coin universe (same source autoresearch rotates over: the eyes' coverage) ──────
def _universe() -> list[str]:
    env = os.environ.get("STRATEGY_TABLE_SYMBOLS", "")
    if env.strip():
        return [s.strip() for s in env.split(",") if s.strip()]
    try:
        from trading.broker_sense import ui_data
        detail = ui_data.coverage().get("detail") or {}
        syms = [s for s, e in detail.items() if e.get("broker") != "upstox"]
        if syms:
            return sorted(syms)
    except Exception:
        pass
    return ["BTC/USDT:USDT", "ETH/USDT:USDT"]


def _open_pairs() -> list[str]:
    """Coins with a live open trade are ALWAYS refreshed first — those are the rows the
    Strategy column is showing right now, so they must never be stale."""
    try:
        from trading.crypto.engine_client import CryptoEngineClient
        return [p for p in CryptoEngineClient().open_pairs() if p]
    except Exception:
        return []


def _decider():
    global _DECIDER
    if _DECIDER is None:
        from trading.crypto.freqtrade.percoin_decider import PerCoinBrainDecider
        _DECIDER = PerCoinBrainDecider()
    return _DECIDER


# ── one row from the tournament (reuses the memoized ranking) ───────────────────────────
def _row_for(coin: str, decider) -> dict | None:
    """Run (or reuse this bar's cached) tournament for `coin` → the persisted row, or None on an
    honest miss (no bars / no scorable strategy). Never raises."""
    try:
        t = decider.tournament(coin)
    except Exception as e:
        log.debug("tournament(%s) failed: %s", coin, e)
        return None
    if not isinstance(t, dict) or t.get("error"):
        return None
    best = t.get("best") or {}
    if not best.get("name"):
        return None
    last = best.get("last", 0) or 0
    signal = "LONG" if last > 0 else "SHORT" if last < 0 else "FLAT"
    try:
        min_final = float(getattr(decider, "_min_final", 0.5))
    except Exception:
        min_final = 0.5
    cleared = bool(t.get("deflated_ok")) and float(best.get("final", 0) or 0) >= min_final and last != 0
    return {"best_strategy": best["name"],
            "score": round(float(best.get("final", 0) or 0), 4),
            "signal": signal,
            "cleared_gate": cleared,
            "psr": round(float(t.get("deflated_psr", 0) or 0), 4),
            "sharpe": best.get("sharpe"),
            "win_rate": best.get("win_rate"),
            "n_candidates": len(t.get("ranked") or []),
            "runners_up": [r.get("name") for r in (t.get("ranked") or [])[1:4]],
            "ts": time.time()}


# ── the producer pass ──────────────────────────────────────────────────────────────────
def refresh(coins: list[str] | None = None, *, batch: int | None = None) -> dict:
    """Refresh up to `batch` coins' best-strategy rows and persist. Open-trade coins first, then
    round-robin the rest of the universe so every coin is covered across passes. Returns a summary
    record. Never raises — an unreachable coin simply keeps its previous (aging) row."""
    global _ROTATE
    t0 = time.time()
    batch = batch if batch is not None else _cfg_int("STRATEGY_TABLE_BATCH", 40)
    universe = coins if coins is not None else _universe()
    opens = [c for c in _open_pairs() if c in universe] if coins is None else []
    # open coins always; then a rotating window of the rest (so the whole universe cycles)
    rest = [c for c in universe if c not in opens]
    if rest:
        _ROTATE %= len(rest)
        window = (rest[_ROTATE:] + rest[:_ROTATE])[:max(0, batch - len(opens))]
    else:
        window = []
    todo = opens + window

    decider = _decider()
    table = state.load_json(_FILE, {})
    if not isinstance(table, dict):
        table = {}
    # The FIRST tournament call also cold-fits the TabPFN outcome-net (minutes), and this daemon runs
    # nice-10 behind a busy funnel — so ONE pass can be slow. Persist after EACH coin (partial progress
    # survives a restart) and stop at a wall-clock budget (resume the rest next pass). Never blocks the
    # trade loops — it is a background teacher.
    budget_s = float(_cfg_int("STRATEGY_TABLE_BUDGET_S", 240))
    updated = 0
    window_done = 0                                    # window coins actually attempted this pass
    for coin in todo:
        row = _row_for(coin, decider)
        if row is not None:
            table[coin] = row
            updated += 1
            state.save_json(_FILE, table)              # incremental: each coin durable immediately
        if coin in window:
            window_done += 1
        if (time.time() - t0) >= budget_s:
            log.info("[strategy_table] budget %ss hit after %s coins — resume next pass", budget_s, updated)
            break
    # advance the rotation cursor by the window coins we ACTUALLY reached (not the whole planned
    # window) — else a budget-truncated pass would skip the un-scanned tail until a full wrap-around.
    if rest:
        _ROTATE = (_ROTATE + window_done) % len(rest)
    # prune rows for coins that left the universe AND are long dead (keep open coins forever)
    max_age = max(ttl_s() * 4, 7200)
    keep = set(universe) | set(opens)
    pruned = {c: r for c, r in table.items()
              if c in keep or (t0 - (r.get("ts", 0) or 0)) < max_age}
    if len(pruned) != len(table):
        table = pruned
        state.save_json(_FILE, table)

    rec = {"ts": t0, "updated": updated, "attempted": len(todo),
           "open_coins": len(opens), "table_size": len(table),
           "took_s": round(time.time() - t0, 2)}
    log.info("[strategy_table] refreshed %s/%s coins (open=%s) table=%s took=%ss",
             updated, len(todo), len(opens), len(table), rec["took_s"])
    return rec


def _canon(sym: str) -> str:
    """Normalize any crypto symbol notation to ONE key so the eyes-coverage table ('ADAUSDT') and
    the Freqtrade traded pair ('ADA/USDT:USDT') resolve to the same row: uppercase, drop the '/'
    and any ':settle' suffix. 'ADA/USDT:USDT' → 'ADAUSDT'; 'BTC/USDT' → 'BTCUSDT'."""
    s = str(sym or "").upper().split(":")[0]
    return s.replace("/", "")


_CANON_INDEX: tuple[float, dict] | None = None       # (file mtime, {canon_key: coin_key})


def _canon_index(table: dict) -> dict:
    """{canonical_symbol: original_table_key}, rebuilt only when the table file changes — so the
    per-row lookups in a dashboard request don't rescan the table each time."""
    global _CANON_INDEX
    try:
        mt = state._path(_FILE).stat().st_mtime
    except OSError:
        mt = 0.0
    if _CANON_INDEX is not None and _CANON_INDEX[0] == mt:
        return _CANON_INDEX[1]
    idx = {_canon(c): c for c in table}
    _CANON_INDEX = (mt, idx)
    return idx


# ── the O(1) consumer read (hot path — file-cached by trading.state) ────────────────────
def lookup(coin: str) -> dict | None:
    """The best-strategy row for `coin`, or None if absent/stale. O(1) — cached JSON read + mtime-
    cached canonical index, NO tournament. Accepts any notation ('BTC/USDT:USDT', 'BTCUSDT', …)."""
    if not coin:
        return None
    table = state.load_json(_FILE, {})
    if not isinstance(table, dict):
        return None
    row = table.get(coin)
    if row is None:
        key = _canon_index(table).get(_canon(coin))
        row = table.get(key) if key else None
    if not isinstance(row, dict):
        return None
    if (time.time() - (row.get("ts", 0) or 0)) > ttl_s():
        return None                                  # too stale to attribute honestly
    return row


def status() -> dict:
    """Dashboard/health read — table freshness, coverage, last-pass summary. State-file only."""
    table = state.load_json(_FILE, {})
    if not isinstance(table, dict):
        table = {}
    now = time.time()
    fresh = sum(1 for r in table.values()
                if isinstance(r, dict) and (now - (r.get("ts", 0) or 0)) <= ttl_s())
    cleared = sum(1 for r in table.values()
                  if isinstance(r, dict) and r.get("cleared_gate"))
    last_ts = max((r.get("ts", 0) or 0 for r in table.values()), default=0)
    return {"size": len(table), "fresh": fresh, "gate_clearing": cleared,
            "last_ts": last_ts, "ttl_s": ttl_s(),
            "live": bool(last_ts and (now - last_ts) < 2 * _cfg_int("STRATEGY_TABLE_INTERVAL_S", 300))}
