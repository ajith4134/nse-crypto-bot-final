"""trading/brain/postmortem.py — Trade Post-Mortem & Excursion Engine.

Owner ask (2026-07-13): mine the common patterns / similarities / anomalies across ALL
winning trades vs ALL losing trades so the brain knows *why* a trade closed in profit or
in loss; on close, record the peak profit (MFE) and peak loss (MAE) reached AFTER entry —
with the time each peak occurred relative to entry — and derive an "ideal entry offset"
that says how much better the entry point could have been; then feed both back into the
entry decision so future entries actually improve. Both markets, kept market-isolated.

This does NOT reinvent anything already in the tree. It stands on:
  • trading/journal/schema.py  — ClosedTrade already carries mae/mfe(+time/pct), efficiency,
    decision_snapshot, market_regime_entry, psych_*, p_up, etc.
  • trading/journal/journal.py — the single closed-trade store (crypto ingest + NSE loop).
  • trading/direction/truth_ledger.py — Wilson hit-rates + local-feather price access; the
    `postmortem_pattern` source we emit is scored here like any other directional lens.
  • trading/direction/learned_direction.py — weights each source by its MEASURED edge, so the
    pattern signal self-corrects with zero retraining once the ledger scores its outcomes.

Three capabilities:
  1. mine_patterns(market) — pysubgroup Subgroup Discovery over the captured entry features
     with the binary target `win` (net_pnl>0): the winning subgroups are the feature combos
     whose win-rate deviates MOST above the base rate, the losing subgroups most below. Human
     readable rules (`regime=trend AND confluence≥0.6 → 78% win vs 33% base`). A pure-pandas
     grouped-commonality pass runs alongside as an always-available fallback (never data-gates).
  2. excursion(trade) — MFE/MAE peak magnitude + the minutes-after-entry each peak occurred
     (5m feather replay using high/low, so the true intrabar extreme is caught), and the
     ideal-entry-offset = the adverse heat taken before the favourable run began. Aggregated
     per (symbol, regime) so the entry can be nudged toward the better price.
  3. pattern_signal(features, market, regime) — match a live candidate against the mined
     winning/losing subgroups → a directional p_up + a size multiplier. Registered as the
     `postmortem_pattern` truth-ledger source and folded into indicator_fusion, gated by
     POSTMORTEM_FEEDBACK so it is report-only until you switch it on.

Everything is market-keyed; a crypto pattern never touches an NSE decision and vice-versa.
Flags: POSTMORTEM=1 (engine on), POSTMORTEM_FEEDBACK=0 (close-the-loop gate, default off).
Pure/offline except the one-shot feather reads; never raises into a trading loop.
"""
from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from trading import state

# per-market persisted artefacts (mined patterns + excursion aggregates)
_PATTERNS = "postmortem_patterns.json"      # {market: {mined_at, n, base_rate, winning[], losing[], commonality[]}}
_EXCURSION = "postmortem_excursion.json"    # {market: {"SYM|regime": {n, ideal_entry_offset_pct, ...}}}

_MIN_TRADES = 40          # need at least this many closed trades in a market to mine
_MIN_SUBGROUP = 12        # a rule must cover at least this many trades to be trusted
_RESULT_SET = 14          # top-N subgroups kept per (win / loss) search
_DEPTH = 3                # max conjuncts per rule
_NBINS = 4                # interval selectors per numeric feature


def _enabled() -> bool:
    return os.environ.get("POSTMORTEM", "1") in ("1", "true", "TRUE", "yes", "on")


def feedback_enabled() -> bool:
    """Close-the-loop gate. Default OFF: the engine reports until you switch it on."""
    # Default ON since 2026-07-16 (B2 + CONVENTIONS §15 no-shadow-on-paper): the loop was fully
    # wired into fusion sizing/entry yet inert — computed, shown, never acting. Paper is the
    # experiment; a mined pattern either earns its keep or gets graded out, but it must ACT.
    return os.environ.get("POSTMORTEM_FEEDBACK", "1") in ("1", "true", "TRUE", "yes", "on")


# ── market key (shared with the isolation boundary) ──────────────────────────────────
def _market_of(trade: dict) -> str:
    """CRYPTO / NSE for a journal row, matching truth_ledger's rule."""
    m = (trade.get("market") or "").upper()
    if m in ("CRYPTO", "NSE"):
        return m
    ex = (trade.get("exchange") or "").lower()
    if ex in ("binance", "bybit", "okx", "kucoin", "coinbase", "kraken", "bitget"):
        return "CRYPTO"
    it = (trade.get("instrument_type") or "").upper()
    return "CRYPTO" if it in ("PERP", "SPOT", "QUARTERLY") else "NSE"


# ── feature extraction (single source of truth for BOTH mining and live matching) ────
# Only features available at DECISION time are used, so a rule mined on closed trades can be
# evaluated on a live candidate with the same keys. Numerics stay numeric (pysubgroup makes
# interval selectors); categoricals are low-cardinality on purpose (readable, non-overfit).
# NB: setup_type / exit_reason / holding_duration are KNOWN ONLY AT EXIT — mining on them is
# target leakage (`setup=roi → 99% win` is tautological) and useless for improving the ENTRY, so
# they are deliberately excluded. Only entry-time context is mineable.
_CAT_FEATURES = ("direction", "segment", "regime", "strategy",
                 "filter_preset", "psych_label")
_NUM_FEATURES = ("leverage", "filter_score", "screener_score", "funding_rate",
                 "pct_change", "brain_confidence", "p_up", "self_uncertainty",
                 "confluence", "psych_obi", "psych_ofi", "psych_fear", "rel_volume",
                 "entry_hour", "quote_volume_24h", "pct_change_24h")

# every all-market filter/screener kind (app_signals), captured from RAM into the entry snapshot's
# market_context.filters — each rides in as a numeric p_up feature `flt_<kind>` so the miner can find
# patterns over the FULL filter set, not just the momentum preset (owner ask 2026-07-13).
_FILTER_KINDS = ("momentum", "funding", "taker", "book_imbalance", "longshort",
                 "oi_trend", "liquidations", "pcr")


def _num(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _snap(trade: dict) -> dict:
    ds = trade.get("decision_snapshot")
    if isinstance(ds, str):
        try:
            ds = json.loads(ds)
        except (json.JSONDecodeError, TypeError):
            ds = {}
    return ds if isinstance(ds, dict) else {}


def trade_features(trade: dict) -> dict:
    """Flat entry-context features for one journal row. Values are None when unknown; the
    caller drops all-None columns. Reads journal columns first, decision_snapshot second."""
    ds = _snap(trade)
    brain = ds.get("brain") if isinstance(ds.get("brain"), dict) else {}
    filt = brain.get("filter") if isinstance(brain.get("filter"), dict) else {}
    fus = ((ds.get("app_signals") or {}).get("indicator_fusion")
           if isinstance(ds.get("app_signals"), dict) else None)
    fus = fus if isinstance(fus, dict) else (ds.get("indicator_fusion")
                                             if isinstance(ds.get("indicator_fusion"), dict) else {})

    hour = trade.get("entry_hour")
    if hour is None:
        dt = _parse_dt(trade.get("entry_datetime") or "")
        hour = datetime.fromtimestamp(dt, timezone.utc).hour if dt else None

    regime = (trade.get("market_regime_entry") or ds.get("market_regime")
              or ds.get("regime") or fus.get("regime") or brain.get("regime") or "")
    feats = {
        "direction": (trade.get("direction") or ds.get("direction") or "").upper() or None,
        "segment": (trade.get("segment") if trade.get("segment") else ds.get("segment")) or None,
        "regime": str(regime).lower() or None,
        "strategy": (trade.get("strategy_name") or ds.get("strategy") or "").strip() or None,
        "filter_preset": (filt.get("filter_preset") or "").strip() or None,
        "psych_label": (trade.get("psych_label") or "").strip() or None,
        "leverage": _num(trade.get("leverage") or ds.get("leverage")),
        "filter_score": _num(filt.get("filter_score")),
        "screener_score": _num(ds.get("screener_score")),
        "funding_rate": _num(trade.get("funding_rate_entry") or filt.get("funding_rate")),
        "pct_change": _num(filt.get("pct_change")),
        "brain_confidence": _num(trade.get("brain_confidence_entry")),
        "p_up": _num(trade.get("p_up") or fus.get("p_up")),
        "self_uncertainty": _num(trade.get("self_uncertainty")),
        "confluence": _num(fus.get("confluence")),
        "psych_obi": _num(trade.get("psych_obi")),
        "psych_ofi": _num(trade.get("psych_ofi")),
        "psych_fear": _num(trade.get("psych_fear")),
        "rel_volume": _num(trade.get("relative_volume")),
        "entry_hour": _num(hour),
    }
    # RAM market context (all filters/screeners + 24h volume captured at entry, owner 2026-07-13):
    # every app_signals filter kind as its own numeric p_up feature + the mirror's 24h volume stats.
    mctx = ds.get("market_context") if isinstance(ds.get("market_context"), dict) else {}
    if mctx:
        flt = mctx.get("filters") if isinstance(mctx.get("filters"), dict) else {}
        for kind in _FILTER_KINDS:
            feats[f"flt_{kind}"] = _num(flt.get(f"filter:{kind}"))
        feats["quote_volume_24h"] = _num(mctx.get("quote_volume_24h"))
        feats["pct_change_24h"] = _num(mctx.get("pct_change_24h"))
    return feats


def _win_of(trade: dict) -> bool | None:
    """Outcome label: net profit after charges. None when the trade has no realised P&L."""
    for k in ("net_pnl", "net_pnl_crypto"):
        v = trade.get(k)
        if v is not None:
            try:
                return float(v) > 0
            except (TypeError, ValueError):
                pass
    return None


# ── local-feather price path (reuse truth_ledger's pair→feather mapping) ──────────────
_OHLC_CACHE: dict[str, tuple[float, object]] = {}
_OHLC_CACHE_MAX = 24


def _ohlc(symbol: str, segment: str):
    """(ts, high, low, close) numpy arrays for a pair's 5m feather, or None. LRU by mtime.
    Reuses truth_ledger._feather_for so spot/perp/options mapping stays in ONE place."""
    try:
        from trading.direction.truth_ledger import _feather_for
        path, _basis = _feather_for(symbol, segment)
    except Exception:
        return None
    if path is None:
        return None
    key = str(path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    hit = _OHLC_CACHE.get(key)
    if hit and hit[0] == mtime:
        return hit[1]
    try:
        import pandas as pd
        df = pd.read_feather(path, columns=["date", "high", "low", "close"])
        ts = (df["date"].astype("int64") // 10**9).to_numpy()
        out = (ts, df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy())
    except Exception:
        return None
    if len(_OHLC_CACHE) >= _OHLC_CACHE_MAX:
        _OHLC_CACHE.pop(next(iter(_OHLC_CACHE)))
    _OHLC_CACHE[key] = (mtime, out)
    return out


def _parse_dt(s) -> float | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


# ── excursion: peak profit/loss AFTER entry, their times, and the ideal entry offset ──
def excursion(trade: dict) -> dict:
    """MFE/MAE peak + when each peak occurred (minutes after entry) + the ideal-entry-offset.

    Prefers a REAL 5m-feather replay between entry and exit (catches the true intrabar
    extreme via high/low). Falls back to the mae/mfe magnitudes the journal already stored
    (crypto ingest fills them from Freqtrade's max/min rate) when no local candles exist.

    ideal_entry_offset_pct: for a LONG, the max drawdown BELOW entry that occurred before the
    favourable peak — i.e. the entry could have been that much cheaper. Positive means "you
    could have entered better"; it is the adverse heat the trade suffered before it worked.
    Signed per side so LONG and SHORT read the same ("enter this % better"). Returns {} when
    nothing is computable (never faked). market-agnostic; NSE simply lacks feathers → fallback.
    """
    direction = (trade.get("direction") or "").upper()
    entry = _num(trade.get("entry_price"))
    if direction not in ("LONG", "SHORT") or not entry:
        return {}
    entry_ts = _parse_dt(trade.get("entry_datetime"))
    exit_ts = _parse_dt(trade.get("exit_datetime")) or (
        (entry_ts + 24 * 3600) if entry_ts else None)
    segment = (trade.get("segment") or _snap(trade).get("segment") or "futures").lower()
    symbol = trade.get("symbol") or ""

    out = _replay_excursion(symbol, segment, direction, entry, entry_ts, exit_ts)
    if out:
        out["basis"] = "feather_replay"
        return out

    # fallback: use stored currency excursions → % of entry (no timing available honestly)
    qty = abs(_num(trade.get("quantity")) or 0.0)
    mfe, mae = _num(trade.get("mfe")), _num(trade.get("mae"))
    if qty and (mfe is not None or mae is not None):
        res = {"basis": "journal_stored"}
        if mfe is not None:
            res["mfe_pct"] = round(abs(mfe) / qty / entry * 100.0, 4)
        if mae is not None:
            res["mae_pct"] = round(abs(mae) / qty / entry * 100.0, 4)
            res["ideal_entry_offset_pct"] = res["mae_pct"]     # adverse heat ≈ entry improvement
        res["minutes_to_mfe"] = None
        res["minutes_to_mae"] = None
        return res
    return {}


def _replay_excursion(symbol, segment, direction, entry, entry_ts, exit_ts) -> dict:
    data = _ohlc(symbol, segment)
    if not data or entry_ts is None:
        return {}
    ts, high, low, close = data
    import bisect
    tl = ts.tolist()
    i0 = bisect.bisect_left(tl, int(entry_ts))
    i1 = bisect.bisect_right(tl, int(exit_ts if exit_ts else entry_ts + 24 * 3600))
    if i1 <= i0 or i0 >= len(ts):
        return {}
    i1 = min(i1, len(ts))
    is_long = direction == "LONG"
    # pass 1 — locate the FAVOURABLE peak (highest high for a long / lowest low for a short) and
    # the OVERALL adverse extreme (MAE). Two passes so the ideal entry can look back over the whole
    # window up to the peak, not just the bars seen before the running peak moved.
    peak_fav, peak_idx = -1e18, i0
    max_adverse, max_adverse_t = 0.0, None
    for i in range(i0, i1):
        fav = (float(high[i]) - entry) if is_long else (entry - float(low[i]))
        if fav > peak_fav:
            peak_fav, peak_idx = fav, i
        adv = (entry - float(low[i])) if is_long else (float(high[i]) - entry)
        if adv > max_adverse:
            max_adverse, max_adverse_t = adv, ts[i]
    peak_fav_t = ts[peak_idx]
    # pass 2 — the IDEAL entry: the best price actually available between entry and the favourable
    # peak (a long could have bought the lowest low, a short sold the highest high before the run),
    # and the adverse heat suffered on the way to that peak.
    ideal_entry = entry
    adv_before_peak = 0.0
    for i in range(i0, peak_idx + 1):
        cand_entry = float(low[i]) if is_long else float(high[i])
        if (cand_entry < ideal_entry) if is_long else (cand_entry > ideal_entry):
            ideal_entry = cand_entry
        adv = (entry - float(low[i])) if is_long else (float(high[i]) - entry)
        adv_before_peak = max(adv_before_peak, adv)
    if peak_fav < 0:
        peak_fav = 0.0
    mfe_pct = round(max(0.0, peak_fav) / entry * 100.0, 4)
    mae_pct = round(max(0.0, max_adverse) / entry * 100.0, 4)
    ideal_off = round(abs(entry - ideal_entry) / entry * 100.0, 4)
    return {
        "mfe_pct": mfe_pct,
        "mae_pct": mae_pct,
        "minutes_to_mfe": round((peak_fav_t - entry_ts) / 60.0, 1) if peak_fav_t else None,
        "minutes_to_mae": round((max_adverse_t - entry_ts) / 60.0, 1) if max_adverse_t else None,
        "adverse_before_peak_pct": round(max(0.0, adv_before_peak) / entry * 100.0, 4),
        "ideal_entry_offset_pct": ideal_off,
        "bars": i1 - i0,
    }


# ── mining: pysubgroup subgroup discovery + a pure-pandas commonality fallback ────────
def _build_frame(trades: list, market: str):
    """DataFrame of features + `win` for one market's labelled closed trades, plus the raw
    per-row symbol (kept out of the search space — high cardinality overfits — used only for
    commonality). Returns (df_or_None, base_rate, n)."""
    try:
        import pandas as pd
    except Exception:
        return None, None, 0
    rows, syms = [], []
    for t in trades:
        if _market_of(t) != market:
            continue
        win = _win_of(t)
        if win is None:
            continue
        f = trade_features(t)
        f["win"] = bool(win)
        rows.append(f)
        syms.append((t.get("symbol") or "").split("/")[0].split(":")[0] or "?")
    if len(rows) < _MIN_TRADES:
        return None, None, len(rows)
    df = pd.DataFrame(rows)
    # drop columns that are entirely empty for this market (e.g. NSE never has funding_rate)
    keep = [c for c in df.columns
            if c == "win" or df[c].notna().sum() >= max(_MIN_SUBGROUP, len(df) * 0.1)]
    df = df[keep]
    # pysubgroup's EqualitySelector rejects None/NaN — fill categorical gaps with an explicit
    # sentinel so "feature unknown" is itself a mineable value (numeric NaN is fine: interval
    # selectors skip it). Applied before both the subgroup search and the commonality pass.
    for c in df.columns:
        if c != "win" and df[c].dtype == object:
            df[c] = df[c].where(df[c].notna(), "NA")
    df["_symbol"] = syms
    base = float(df["win"].mean())
    return df, base, len(df)


def _selector_predicates(sg) -> list:
    """Serialise a pysubgroup subgroup into JSON predicates matchable WITHOUT pandas.
    Each predicate: {feature, op, value} where op ∈ {eq, ge, le, between}."""
    conj = getattr(sg, "selectors", None) or [sg]
    preds = []
    for sel in conj:
        attr = getattr(sel, "attribute_name", None)
        if attr is None or attr.startswith("_"):
            continue
        val = getattr(sel, "attribute_value", None)
        lo = getattr(sel, "lower_bound", None)
        hi = getattr(sel, "upper_bound", None)
        if isinstance(val, float) and math.isnan(val):
            continue                                    # "feature is missing" — noise for live matching
        if val is not None:
            preds.append({"feature": attr, "op": "eq", "value": val})
        elif lo is not None or hi is not None:
            neg_inf = lo is None or lo == float("-inf")
            pos_inf = hi is None or hi == float("inf")
            if neg_inf and not pos_inf:
                preds.append({"feature": attr, "op": "lt", "value": float(hi)})
            elif pos_inf and not neg_inf:
                preds.append({"feature": attr, "op": "ge", "value": float(lo)})
            else:
                preds.append({"feature": attr, "op": "between",
                              "value": [float(lo), float(hi)]})
    return preds


def _cover_from_preds(df, preds):
    """Boolean mask of rows satisfying every (cleaned) predicate — recomputed from the
    displayed predicates so the rule text and its n/win-rate always describe the SAME set."""
    mask = None
    for p in preds:
        col = df.get(p["feature"])
        if col is None:
            return None
        op, v = p["op"], p["value"]
        if op == "eq":
            m = col.astype("string").str.lower() == str(v).lower()
        elif op == "ge":
            m = col.astype("float64") >= v
        elif op == "lt":
            m = col.astype("float64") < v
        elif op == "between":
            f = col.astype("float64")
            m = (f >= v[0]) & (f < v[1])
        else:
            return None
        m = m.fillna(False)
        mask = m if mask is None else (mask & m)
    return mask


def _rule_text(preds: list) -> str:
    parts = []
    for p in preds:
        f, op, v = p["feature"], p["op"], p["value"]
        if op == "eq":
            parts.append(f"{f}={v}")
        elif op == "ge":
            parts.append(f"{f}≥{v:.3g}")
        elif op == "lt":
            parts.append(f"{f}<{v:.3g}")
        elif op == "between":
            parts.append(f"{v[0]:.3g}≤{f}<{v[1]:.3g}")
    return " AND ".join(parts) if parts else "(all trades)"


def _discover(df, base_rate: float, target_win: bool) -> list:
    """Top subgroups for target `win==target_win` via pysubgroup BeamSearch (WRAcc). Returns
    rule dicts sorted by |lift| desc. Empty list when pysubgroup is absent → caller uses stats."""
    try:
        import pysubgroup as ps
    except Exception:
        return []
    search_df = df.drop(columns=[c for c in ("_symbol",) if c in df.columns])
    try:
        target = ps.BinaryTarget("win", target_win)
        ss = ps.create_selectors(search_df, ignore=["win"], nbins=_NBINS)
        task = ps.SubgroupDiscoveryTask(search_df, target, ss,
                                        result_set_size=_RESULT_SET, depth=_DEPTH,
                                        qf=ps.WRAccQF())
        result = ps.BeamSearch(beam_width=max(20, _RESULT_SET * 2)).execute(task)
    except Exception:
        return []
    rules = []
    seen: set = set()
    for tup in result.to_descriptions():
        sg = tup[1]
        preds = _selector_predicates(sg)
        if not preds:
            continue                                    # empty root, or all-NaN-equality → drop
        sig = frozenset((p["feature"], p["op"], str(p["value"])) for p in preds)
        if sig in seen:
            continue                                    # nested duplicate (same real predicates)
        seen.add(sig)
        cover = _cover_from_preds(search_df, preds)     # from CLEANED preds → text↔stats agree
        if cover is None:
            continue
        n = int(cover.sum())
        if n < _MIN_SUBGROUP:
            continue
        sub_win = float(search_df["win"][cover].mean())
        rules.append({
            "rule": _rule_text(preds),
            "predicates": preds,
            "n": n,
            "win_rate": round(sub_win, 4),
            "base_rate": round(base_rate, 4),
            "lift": round(sub_win - base_rate, 4),
            "coverage_pct": round(n / len(search_df) * 100.0, 2),
        })
    # collapse rules with IDENTICAL coverage (same n & win-rate ⇒ a nested variant whose extra
    # conjunct is redundant) to the most GENERAL one (fewest predicates) — cleaner, non-repetitive.
    by_cov: dict = {}
    for r in rules:
        k = (r["n"], r["win_rate"])
        if k not in by_cov or len(r["predicates"]) < len(by_cov[k]["predicates"]):
            by_cov[k] = r
    rules = list(by_cov.values())
    rules.sort(key=lambda r: -abs(r["lift"]))
    return rules


def _commonality(df, base_rate: float) -> list:
    """Always-available fallback + companion to the subgroup rules: for every feature value
    (categoricals) and every numeric quartile, the win-rate vs the base rate — the raw
    'what do winners share' table. Pure pandas, no external dep."""
    out = []
    n_all = len(df)
    for col in df.columns:
        if col in ("win", "_symbol"):
            continue
        s = df[col]
        try:
            if s.dtype.kind in "biufc" and s.notna().sum() >= _MIN_SUBGROUP:
                import pandas as pd
                q = pd.qcut(s, 4, duplicates="drop")
                grp = df.groupby(q, observed=True)["win"]
            else:
                grp = df.groupby(s.astype("string"), observed=True)["win"]
        except Exception:
            continue
        for val, g in grp:
            n = int(g.count())
            if n < _MIN_SUBGROUP:
                continue
            wr = float(g.mean())
            out.append({"feature": col, "value": str(val), "n": n,
                        "win_rate": round(wr, 4), "lift": round(wr - base_rate, 4),
                        "coverage_pct": round(n / n_all * 100.0, 2)})
    out.sort(key=lambda r: -abs(r["lift"]))
    return out[:60]


def mine_patterns(market: str | None = None) -> dict:
    """Mine winning + losing patterns per market and persist them. `market` None → both.
    Returns a small report. Safe to call repeatedly (fully replaces that market's artefact)."""
    rep: dict = {}
    if not _enabled():
        return {"enabled": False}
    from trading.journal.journal import TradeJournal
    trades = [t.to_dict() for t in TradeJournal().trades]
    markets = [market.upper()] if market else ["CRYPTO", "NSE"]
    store = state.load_json(_PATTERNS, {})
    if not isinstance(store, dict):
        store = {}
    for mk in markets:
        df, base, n = _build_frame(trades, mk)
        if df is None:
            store[mk] = {"mined_at": time.time(), "n": n, "insufficient": True,
                         "min_trades": _MIN_TRADES, "winning": [], "losing": [],
                         "commonality": []}
            rep[mk] = {"n": n, "insufficient": True}
            continue
        winning = _discover(df, base, True)
        losing = _discover(df, base, False)
        common = _commonality(df, base)
        store[mk] = {
            "mined_at": time.time(), "n": n, "base_rate": round(base, 4),
            "method": "pysubgroup+commonality" if (winning or losing) else "commonality",
            "winning": winning, "losing": losing, "commonality": common,
            "features_used": [c for c in df.columns if c not in ("win", "_symbol")],
        }
        rep[mk] = {"n": n, "base_rate": round(base, 4),
                   "winning": len(winning), "losing": len(losing),
                   "commonality": len(common)}
    state.save_json(_PATTERNS, store)
    return rep


def patterns(market: str) -> dict:
    """Read the persisted mined patterns for one market (never raises)."""
    store = state.load_json(_PATTERNS, {})
    return (store.get((market or "").upper()) or {}) if isinstance(store, dict) else {}


# ── per-trade attribution: why did THIS trade win / lose? ─────────────────────────────
def _match(features: dict, preds: list) -> bool:
    """True when the feature dict satisfies every predicate (missing feature → no match)."""
    for p in preds:
        v = features.get(p["feature"])
        if v is None:
            return False
        op = p["op"]
        try:
            if op == "eq":
                if str(v).lower() != str(p["value"]).lower():
                    return False
            elif op == "ge":
                if float(v) < p["value"]:
                    return False
            elif op == "lt":
                if float(v) >= p["value"]:
                    return False
            elif op == "between":
                lo, hi = p["value"]
                if not (lo <= float(v) < hi):
                    return False
        except (TypeError, ValueError):
            return False
    return True


def explain_trade(trade: dict) -> dict:
    """Human-readable reason a closed trade won/lost: the mined winning/losing subgroups it
    matches (ranked by lift) + its excursion. Uses the stored feature_attribution (SHAP top
    drivers) when present. Read-only; safe on any trade dict."""
    market = _market_of(trade)
    feats = trade_features(trade)
    pat = patterns(market)
    won = _win_of(trade)
    matched_win = [r for r in (pat.get("winning") or []) if _match(feats, r["predicates"])]
    matched_loss = [r for r in (pat.get("losing") or []) if _match(feats, r["predicates"])]
    matched_win.sort(key=lambda r: -r["lift"])
    matched_loss.sort(key=lambda r: r["lift"])
    reasons = []
    for r in (matched_loss if won is False else matched_win)[:3]:
        verb = "loses" if won is False else "wins"
        reasons.append(f"matches «{r['rule']}» → that group {verb} "
                       f"{r['win_rate']*100:.0f}% vs {r['base_rate']*100:.0f}% base "
                       f"(n={r['n']})")
    shap = trade.get("feature_attribution")
    drivers = []
    if isinstance(shap, dict):
        items = sorted(shap.items(), key=lambda kv: -abs(_num(kv[1]) or 0))[:5]
        drivers = [{"feature": k, "value": v} for k, v in items]
    return {
        "market": market, "won": won,
        "reasons": reasons or ["no strong mined pattern matched this trade"],
        "matched_winning": matched_win[:4], "matched_losing": matched_loss[:4],
        "shap_drivers": drivers,
        "excursion": excursion(trade),
        "features": {k: v for k, v in feats.items() if v is not None},
    }


# ── close-the-loop: a directional + sizing signal from the mined patterns ─────────────
def pattern_signal(features: dict, market: str, regime: str | None = None) -> dict:
    """Score a live candidate against the mined patterns → a directional lens.

    Aggregates the lift of every winning subgroup it matches (pushes toward the trade) minus
    every losing subgroup it matches (pushes away), each weighted by √coverage so a broad,
    well-supported rule counts more than a narrow one. Maps the net to p_up via a logistic and
    to a size multiplier. Returns {p_up, size_mult, score, matched_win, matched_loss, n_rules}.
    p_up is None (abstain) when no rule matches. Never raises."""
    try:
        pat = patterns((market or "").upper())
        if not pat or pat.get("insufficient"):
            return {"p_up": None, "size_mult": 1.0, "score": 0.0, "abstained": True}
        mw = [r for r in (pat.get("winning") or []) if _match(features, r["predicates"])]
        ml = [r for r in (pat.get("losing") or []) if _match(features, r["predicates"])]
        if not mw and not ml:
            return {"p_up": None, "size_mult": 1.0, "score": 0.0, "abstained": True}
        score = 0.0
        for r in mw:
            score += r["lift"] * math.sqrt(max(1.0, r["n"]))
        for r in ml:
            score += r["lift"] * math.sqrt(max(1.0, r["n"]))   # losing lift is negative already
        norm = score / 40.0                                     # gentle scaling to a sane range
        p_up = 1.0 / (1.0 + math.exp(-norm))
        # size: shrink toward 0.5 confidence; a strong losing match caps size hard
        worst = min([r["lift"] for r in ml], default=0.0)
        size_mult = 1.0
        if worst < -0.15:
            size_mult = max(0.3, 1.0 + worst)                   # -0.4 lift → 0.6×, floored 0.3×
        best = max([r["lift"] for r in mw], default=0.0)
        if best > 0.15 and worst >= -0.05:
            size_mult = min(1.3, size_mult + best)              # confirmed winner → up to 1.3×
        return {
            "p_up": round(p_up, 4), "size_mult": round(size_mult, 3),
            "score": round(score, 4), "abstained": False,
            "matched_win": [r["rule"] for r in mw[:3]],
            "matched_loss": [r["rule"] for r in ml[:3]],
            "n_rules": len(mw) + len(ml),
        }
    except Exception:
        return {"p_up": None, "size_mult": 1.0, "score": 0.0, "abstained": True}


def entry_offset(symbol: str, regime: str | None, market: str) -> dict:
    """Ideal-entry-offset for a (symbol, regime) from the aggregated excursions: how much
    better (%) entries on this symbol/regime have historically been available just after the
    signal. {offset_pct, n} or {} when unmeasured. Used to nudge the fusion entry price."""
    store = state.load_json(_EXCURSION, {})
    if not isinstance(store, dict):
        return {}
    mk = store.get((market or "").upper()) or {}
    base = (symbol or "").split("/")[0].split(":")[0]
    for key in (f"{base}|{(regime or '').lower()}", f"{base}|any"):
        row = mk.get(key)
        if row and row.get("n", 0) >= 5:
            return {"offset_pct": row.get("ideal_entry_offset_pct"),
                    "adverse_before_peak_pct": row.get("adverse_before_peak_pct"),
                    "n": row["n"]}
    return {}


def build_excursion_aggregates(market: str | None = None, limit: int | None = None) -> dict:
    """Fold every closed trade's excursion into per-(symbol, regime) medians and persist. This
    is the data behind entry_offset(). Idempotent full rebuild. Returns a report."""
    if not _enabled():
        return {"enabled": False}
    from trading.journal.journal import TradeJournal
    trades = [t.to_dict() for t in TradeJournal().trades]
    if limit:
        trades = trades[-limit:]
    markets = [market.upper()] if market else ["CRYPTO", "NSE"]
    acc: dict = {mk: {} for mk in markets}
    counts = {mk: 0 for mk in markets}
    for t in trades:
        mk = _market_of(t)
        if mk not in acc:
            continue
        ex = excursion(t)
        off = ex.get("ideal_entry_offset_pct")
        if off is None:
            continue
        base = (t.get("symbol") or "").split("/")[0].split(":")[0] or "?"
        regime = str(t.get("market_regime_entry") or _snap(t).get("regime") or "any").lower()
        counts[mk] += 1
        for key in (f"{base}|{regime}", f"{base}|any"):
            b = acc[mk].setdefault(key, {"offs": [], "advs": [], "mfe": [], "m_mfe": []})
            b["offs"].append(off)
            if ex.get("adverse_before_peak_pct") is not None:
                b["advs"].append(ex["adverse_before_peak_pct"])
            if ex.get("mfe_pct") is not None:
                b["mfe"].append(ex["mfe_pct"])
            if ex.get("minutes_to_mfe") is not None:
                b["m_mfe"].append(ex["minutes_to_mfe"])
    def _med(xs):
        return round(sorted(xs)[len(xs) // 2], 4) if xs else None
    store = state.load_json(_EXCURSION, {})
    if not isinstance(store, dict):
        store = {}
    for mk in markets:
        store[mk] = {k: {"n": len(v["offs"]),
                         "ideal_entry_offset_pct": _med(v["offs"]),
                         "adverse_before_peak_pct": _med(v["advs"]),
                         "median_mfe_pct": _med(v["mfe"]),
                         "median_minutes_to_mfe": _med(v["m_mfe"])}
                     for k, v in acc[mk].items() if v["offs"]}
        store[mk]["_meta"] = {"built_at": time.time(), "trades": counts[mk]}
    state.save_json(_EXCURSION, store)
    return {mk: counts[mk] for mk in markets}


def backfill(limit: int | None = None) -> dict:
    """One-shot: mine patterns + build excursion aggregates from the existing journal so the
    engine ships with real data (backfill-before-wire). Returns both reports."""
    return {"patterns": mine_patterns(), "excursion": build_excursion_aggregates(limit=limit)}


# ── dashboard snapshot ────────────────────────────────────────────────────────────────
def status(market: str | None = None) -> dict:
    """Everything the panel renders: mined winning/losing patterns + commonality + excursion
    aggregates, per market. Read-only from the persisted artefacts."""
    pstore = state.load_json(_PATTERNS, {})
    estore = state.load_json(_EXCURSION, {})
    pstore = pstore if isinstance(pstore, dict) else {}
    estore = estore if isinstance(estore, dict) else {}
    markets = [market.upper()] if market else ["CRYPTO", "NSE"]
    out = {"enabled": _enabled(), "feedback": feedback_enabled(), "markets": {}}
    for mk in markets:
        pat = pstore.get(mk) or {}
        exc = estore.get(mk) or {}
        # top ideal-entry offsets (biggest achievable improvement first)
        offs = [{"key": k, **v} for k, v in exc.items()
                if k != "_meta" and v.get("ideal_entry_offset_pct") is not None
                and v.get("n", 0) >= 5]
        offs.sort(key=lambda r: -(r.get("ideal_entry_offset_pct") or 0))
        out["markets"][mk] = {
            "n_trades": pat.get("n"), "base_rate": pat.get("base_rate"),
            "mined_at": pat.get("mined_at"), "method": pat.get("method"),
            "insufficient": pat.get("insufficient", False),
            "winning": (pat.get("winning") or [])[:10],
            "losing": (pat.get("losing") or [])[:10],
            "commonality": (pat.get("commonality") or [])[:20],
            "excursion_top": offs[:20],
            "excursion_meta": exc.get("_meta"),
        }
    return out
