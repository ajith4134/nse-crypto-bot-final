"""trading/screener/screener.py — per-segment ranked screeners (the live-loop entry).

`Screener` produces RANKED candidate symbols + filter metadata per segment, so the
live trade loop can build a dynamic, varied watchlist for the SELECTED segments
(see trading/online/state.py SEGMENTS). It composes the standalone filter algorithms
in `filters.py` over INJECTABLE data sources (`sources.py`), and — being OFFLINE-SAFE
— degrades to the deterministic `stubs.py` list whenever a live source is empty.

    Screener.candidates(market, segment, *, limit, filters) -> ranked [ {symbol,
        segment, market, score, reason, metrics:{...}} ]   (best first)
    Screener.watchlist(market, segments, *, per_segment)    -> deduped union
    Screener.status()                                       -> health snapshot

Standalone composables (used by Screener, callable directly in tests):
    screen_nse_movers(source, segment, ...) · screen_crypto_spot(source, ...)
    screen_crypto_futures(...) · apply_technical_filters(ohlc_df)  (from filters).
"""
from __future__ import annotations

import os
from typing import Any

from trading.screener import filters as F
from trading.screener.stubs import stub_candidates

# valid segments mirror trading/online/state.py SEGMENTS
SEGMENTS = {
    "NSE": ["intraday", "mtf", "futures", "options", "commodities"],
    "CRYPTO": ["spot", "futures", "options", "prediction"],
}


def _cand(symbol: str, segment: str, market: str, score: float, reason: str,
          metrics: dict, source: str) -> dict:
    return {"symbol": symbol, "segment": segment, "market": market,
            "score": round(float(score), 6), "reason": reason,
            "metrics": {**metrics, "source": source}}


# ── standalone NSE composables ────────────────────────────────────────────────
def screen_nse_movers(source: Any, segment: str = "intraday", *, limit: int = 5,
                      filters: dict | None = None) -> list[dict]:
    """Rank NSE equity candidates from gainers/losers + most-active + 52w feeds.

    Score = |% change| (momentum) blended with relative volume when present.
    Returns [] if the live source yields nothing (caller falls back to stub).
    """
    filters = filters or {}
    rows: dict[str, dict] = {}

    def _merge(items: list[dict], tag: str) -> None:
        for r in items:
            sym = str(r.get("symbol", "")).upper()
            if not sym:
                continue
            cur = rows.setdefault(sym, {"symbol": sym, "tags": []})
            cur.update({k: v for k, v in r.items() if k != "symbol"})
            cur["tags"].append(tag)

    # BASE = the liquid NSE F&O stock universe ranked by LIVE OpenAlgo momentum
    # (reliable). The nselib movers below are IP-blocked from the VM and, when they
    # answer, surface illiquid micro-caps the brain rightly abstains on — so the
    # liquid universe is the primary, tradeable intraday set (2026-07-07 fix).
    try:
        _merge(source.liquid_movers(limit=120) if hasattr(source, "liquid_movers")
               else [], "liquid")
    except Exception:
        pass

    try:
        _merge(source.movers("gainers"), "gainer")
        _merge(source.movers("losers"), "loser")
        _merge(source.most_active(), "active")
    except Exception:
        if not rows:
            return []

    # 52-week proximity flag (varied universe / breakout extremes)
    try:
        for r in source.week_52() or []:
            sym = str(r.get("symbol") or r.get("SYMBOL") or "").upper()
            if sym in rows:
                rows[sym]["tags"].append("52w")
    except Exception:
        pass

    # Keep only the liquid, F&O-eligible universe when it is available — this drops
    # illiquid micro-caps (ZSARACOM/KAUSHALYA/TARC…) that nselib surfaces, so the
    # loop only ever trades deep-liquidity intraday names.
    try:
        from trading.screener.universe import is_liquid, _FO_SET
        if _FO_SET:
            liq = {s: r for s, r in rows.items() if is_liquid(s)}
            if liq:
                rows = liq
    except Exception:
        pass

    if not rows:
        return []

    min_pct = filters.get("min_pct_change")

    def score(r: dict) -> float:
        pct = abs(F._get(r, "pct_change"))
        rv = F._get(r, "rvol", default=1.0) or 1.0
        active = 0.5 if "active" in r.get("tags", []) else 0.0
        prox = 0.5 if "52w" in r.get("tags", []) else 0.0
        return pct + 0.3 * max(rv - 1.0, 0.0) * 10 + active + prox

    def reason(r: dict) -> str:
        tags = ",".join(dict.fromkeys(r.get("tags", []))) or "mover"
        return f"NSE {segment}: {tags} {F._get(r, 'pct_change'):+.2f}%"

    cleaned = [r for r in rows.values()
               if min_pct is None or abs(F._get(r, "pct_change")) >= min_pct]
    ranked_all = F.score_rows(cleaned, score, reason)
    # intraday and mtf share the movers universe, but the loop tags each symbol with ONE
    # segment (last write wins) — identical lists meant every dual candidate landed on
    # intraday and mtf never opened a trade. Give mtf the NEXT ranked slice so the two
    # segments hold disjoint symbols (falls back to the top slice when depth runs out).
    if segment == "mtf" and len(ranked_all) > limit:
        ranked = ranked_all[limit:2 * limit] or ranked_all[:limit]
    else:
        ranked = ranked_all[:limit]
    return [_cand(r["symbol"], segment, "NSE", r["score"], r["reason"],
                  {"pct_change": F._get(r, "pct_change"),
                   "rvol": F._get(r, "rvol", default=None) if "rvol" in r else None,
                   "tags": list(dict.fromkeys(r.get("tags", [])))},
                  "nselib") for r in ranked]


def screen_nse_fno(source: Any, *, limit: int = 5, filters: dict | None = None) -> list[dict]:
    """Rank F&O underlyings by live-most-active + option-chain PCR signal.

    Each underlying is resolved to the broker's EXACT near-month NFO FUT contract
    (NIFTY → NIFTY28JUL26FUT) via OpenAlgo search — the same mechanism as MCX
    commodities. Bare underlyings 400 on NFO quotes ("Symbol 'NIFTY' not found"),
    which is exactly why the futures segment never opened a trade."""
    rows = []
    try:
        rows = source.active_underlying() or []
    except Exception:
        rows = []
    if not rows:
        return []
    from trading.screener.commodities import resolve_near_month_fut
    from trading.screener.options import _broker
    client = _broker()
    ranked = F.volume_filter(rows, key="volume")[:limit]
    out = []
    for r in ranked:
        base = str(r.get("symbol") or r.get("underlying") or "").upper()
        if not base:
            continue
        fut = resolve_near_month_fut(client, base, exchange="NFO") if client else None
        if not fut:
            continue          # unresolvable/illiquid underlying — never emit a bare symbol
        out.append(_cand(fut["symbol"], "futures", "NSE", F._get(r, "volume"),
                         f"NSE futures: active underlying {base} near-month {fut['symbol']}",
                         {"volume": F._get(r, "volume"), "underlying": base,
                          "expiry": fut.get("expiry")}, "nselib+openalgo"))
    # re-rank 0..1-ish by volume order
    for i, c in enumerate(out):
        c["score"] = round(1.0 - i / max(len(out), 1) * 0.5, 6)
    return out


def screen_nse_options(source: Any, *, limit: int = 5, filters: dict | None = None) -> list[dict]:
    """Rank single-leg NSE option (CE/PE) candidates.

    Implemented in Phase 2 (trading/screener/options.py) — generates ATM/OTM CE&PE
    contracts for index + top-liquid F&O underlyings via the OpenAlgo broker path
    (nselib's live option-chain endpoint is IP-blocked from the server). Wired here so
    the `options` segment routes correctly; returns [] until Phase 2 is active.
    """
    try:
        from trading.screener.options import screen_nse_options as _impl
        return _impl(source, limit=limit, filters=filters)
    except Exception:
        return []


def screen_nse_ui(segment: str = "intraday", *, limit: int = 20) -> list[dict]:
    """NSE candidates from the Upstox UI ONLY (owner 2026-07-13, NSE_UI_ONLY / motto): the
    Upstox app's OWN movers screener, captured by the eyes into ui_market from the logged-in
    web app — no nselib, no OpenAlgo, no API. `ui_market.movers()` ranks the captured tickers
    by |%chg|; we keep only NSE-shaped symbols (crypto pairs excluded via market_guard). An
    empty return is an HONEST ABSTAIN (the eyes haven't fed NSE tickers fresh enough) — the
    caller must NOT fall back to a stub or an API. Options/commodities candidates come from the
    option-chain UI (a later seam); this composable serves the equity/futures segments."""
    try:
        from trading.broker_sense import ui_market
        from trading.market_guard import CRYPTO, market_of_symbol
    except Exception:
        return []
    seg = (segment or "intraday").lower()
    if seg in ("options", "commodities"):
        return []                                    # sourced from option-chain/commodities UI
    out: list[dict] = []
    for r in ui_market.movers(n=max(limit * 3, 60)):
        sym = str(r.get("symbol") or "").upper()
        if not sym or market_of_symbol(sym) == CRYPTO:   # keep NSE-shaped names only
            continue
        pct = r.get("pct_change")
        try:
            pct = float(pct)
        except (TypeError, ValueError):
            continue
        out.append(_cand(sym, seg, "NSE", abs(pct),
                         f"Upstox UI movers {pct:+.2f}%",
                         {"pct_change": round(pct, 3), "last": r.get("last"),
                          "ui_only": True}, "ui:upstox-movers"))
        if len(out) >= limit:
            break
    for i, c in enumerate(out):                       # normalize score 1..0.5 by rank
        c["score"] = round(1.0 - i / max(len(out), 1) * 0.5, 6)
    return out


# ── standalone crypto composables ─────────────────────────────────────────────
def _ticker_rows(tickers: dict, markets: dict | None = None,
                 want: str | None = None) -> list[dict]:
    """Flatten a ccxt fetch_tickers dict → unified rows, optional market-type filter."""
    rows = []
    for sym, t in (tickers or {}).items():
        if want and markets is not None:
            m = markets.get(sym) or {}
            if m.get("type") != want:
                continue
        rows.append({
            "symbol": sym,
            "pct_change": F._num(t.get("percentage")),
            "quote_volume": F._num(t.get("quoteVolume") or t.get("baseVolume")),
            "last": F._num(t.get("last")),
        })
    return rows


def screen_crypto_spot(source: Any, *, limit: int = 5,
                       filters: dict | None = None) -> list[dict]:
    """Rank crypto SPOT pairs by volume × |%change| (freqtrade Volume+PercentChange)."""
    filters = filters or {}
    quote = (filters.get("quote") or "USDT").upper()
    try:
        tickers = source.tickers("spot")
    except Exception:
        tickers = {}
    rows = [r for r in _ticker_rows(tickers) if r["symbol"].endswith("/" + quote)]
    if not rows:
        return []
    rows = F.volume_filter(rows, key="quote_volume",
                           min_value=filters.get("min_quote_volume"))
    mp = filters.get("min_pct_change")
    if mp:
        rows = [r for r in rows if abs(r.get("pct_change") or 0.0) >= float(mp)]

    # rank: volume order gives the base, |%change| momentum adds the kicker
    top = rows[: max(limit * 3, limit)]
    vmax = max((r["quote_volume"] for r in top), default=1.0) or 1.0
    scored = []
    for r in top:
        s = 0.6 * (r["quote_volume"] / vmax) + 0.4 * min(abs(r["pct_change"]) / 10.0, 1.0)
        scored.append(_cand(r["symbol"], "spot", "CRYPTO", s,
                            f"spot: vol-rank + {r['pct_change']:+.2f}%",
                            {"pct_change": r["pct_change"],
                             "quote_volume": r["quote_volume"]}, "ccxt"))
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:limit]


def screen_crypto_futures(source: Any, *, limit: int = 5,
                          filters: dict | None = None) -> list[dict]:
    """Rank USDⓢ-M perps by volume/%change and tilt by funding rate.

    Universe scan is MIGRATED to the Binance all-market websocket mirror (RAM, Binance-pushed) when
    warm — no per-cycle ccxt fetch_tickers of ~400 symbols; the brain's CPU stays free for ML. Falls
    back to ccxt REST when the mirror is cold (honest degrade). Kill switch: BINANCE_MIRROR_UNIVERSE=0.
    """
    filters = filters or {}
    src_tag, funding = "ccxt", {}
    rows: list[dict] = []
    if os.getenv("BINANCE_MIRROR_UNIVERSE", "1").strip().lower() not in ("0", "false", "off"):
        try:
            from trading.broker_sense import binance_stream as _bs
            m = _bs.get_mirror()
            if _bs.enabled() and not m.is_stale("BTCUSDT"):     # mirror warm → scan from RAM
                mrows = m.futures_rows()
                if mrows:
                    rows = [{"symbol": r["symbol"], "pct_change": r.get("pct_change"),
                             "quote_volume": r.get("quote_volume")} for r in mrows]
                    funding = {r["symbol"]: {"fundingRate": r.get("funding_rate")} for r in mrows}
                    src_tag = "binance-mirror"
        except Exception:
            rows = []
    if not rows:                                                 # cold mirror → ccxt REST fallback
        try:
            tickers = source.tickers("futures")
            funding = source.funding_rates("futures")
        except Exception:
            tickers, funding = {}, {}
        rows = _ticker_rows(tickers)
        rows = [r for r in rows if ":" in r["symbol"] or r["symbol"].endswith("USDT")]
    if not rows:
        return []
    rows = F.volume_filter(rows, key="quote_volume",
                           min_value=filters.get("min_quote_volume"))
    mp = filters.get("min_pct_change")
    if mp:
        rows = [r for r in rows if abs(r.get("pct_change") or 0.0) >= float(mp)]
    rows = rows[: max(limit * 3, limit)]
    vmax = max((r["quote_volume"] for r in rows), default=1.0) or 1.0
    # new-listing catalyst (Binance-native): fresh perps pump on listing flow — boost their
    # discovery so they surface as candidates. Bounded +0.15; one cheap state-file read.
    new_raw: set = set()
    try:
        from trading.broker_sense import binance_catalysts as _bc
        if _bc.enabled():
            new_raw = {n["raw"] for n in _bc.new_listings()}
    except Exception:
        new_raw = set()
    # Binance AI Select picks (its built-in recommender) → surface them as candidates too.
    ai_bases: set = set()
    try:
        from trading.broker_sense import binance_ai_select as _ai
        if _ai.enabled():
            ai_bases = _ai.selected_bases()
    except Exception:
        ai_bases = set()
    out = []
    for r in rows:
        fr = funding.get(r["symbol"]) or {}
        frate = F._num(fr.get("fundingRate")) if isinstance(fr, dict) else 0.0
        s = (0.5 * (r["quote_volume"] / vmax)
             + 0.3 * min(abs(r["pct_change"]) / 10.0, 1.0)
             + 0.2 * min(abs(frate) * 1000, 1.0))
        _b = r["symbol"].split("/")[0]
        if (_b + "USDT") in new_raw:                             # ccxt 'X/USDT:USDT' → raw 'XUSDT'
            s = min(1.0, s + 0.15)
        if _b in ai_bases:                                       # Binance AI-Select pick → surface it
            s = min(1.0, s + 0.12)
        out.append(_cand(r["symbol"], "futures", "CRYPTO", s,
                         f"futures: vol + {r['pct_change']:+.2f}% funding={frate:.4%}",
                         {"pct_change": r["pct_change"],
                          "quote_volume": r["quote_volume"], "funding": frate}, src_tag))
    out.sort(key=lambda c: c["score"], reverse=True)
    return out[:limit]


def screen_crypto_options(source: Any, *, limit: int = 5,
                          filters: dict | None = None) -> list[dict]:
    """Rank options by traded volume (+ mark IV when greeks are available)."""
    try:
        tickers = source.tickers("options")
    except Exception:
        tickers = {}
    rows = _ticker_rows(tickers)
    if not rows:
        return []

    # Drop contracts that expire within ~2h (or already expired): same-day dailies
    # dominate the volume ranking, but they die at 08:00 UTC — the loop then holds a
    # watchlist of dead symbols and the options segment opens NOTHING (2026-07-03).
    # Unified ccxt option symbols embed the expiry: BASE/QUOTE:SETTLE-YYMMDD-STRIKE-C/P.
    def _expiry_ok(sym: str) -> bool:
        import datetime as _dt
        parts = sym.split("-")
        if len(parts) < 3 or not parts[1].isdigit() or len(parts[1]) != 6:
            return True                       # unrecognized format — keep, don't guess
        try:
            exp = _dt.datetime.strptime(parts[1], "%y%m%d").replace(
                hour=8, tzinfo=_dt.timezone.utc)   # Deribit/Binance dailies: 08:00 UTC
        except ValueError:
            return True
        return exp - _dt.datetime.now(_dt.timezone.utc) > _dt.timedelta(hours=2)

    rows = [r for r in rows if _expiry_ok(str(r["symbol"]))]
    if not rows:
        return []
    rows = F.volume_filter(rows, key="quote_volume")[:limit]
    vmax = max((r["quote_volume"] for r in rows), default=1.0) or 1.0
    return [_cand(r["symbol"], "options", "CRYPTO",
                  r["quote_volume"] / vmax,
                  f"options: volume rank {r['symbol']}",
                  {"quote_volume": r["quote_volume"]}, "ccxt") for r in rows]


class Screener:
    """Per-segment ranked screener with offline-safe stub fallback."""

    def __init__(self, nse_source: Any = None, crypto_source: Any = None):
        # Lazy default live sources (degrade internally to []/None).
        if nse_source is None:
            try:
                from trading.screener.sources import LiveNSESource
                nse_source = LiveNSESource()
            except Exception:
                nse_source = None
        if crypto_source is None:
            try:
                from trading.screener.sources import LiveCryptoSource
                crypto_source = LiveCryptoSource()
            except Exception:
                crypto_source = None
        self.nse = nse_source
        self.crypto = crypto_source
        self._last: dict[str, str] = {}   # "MARKET:segment" -> "live"|"stub"

    # ── routing ──────────────────────────────────────────────────────────────
    def _live(self, market: str, segment: str, limit: int,
              filters: dict | None) -> list[dict]:
        m, s = market.upper(), segment.lower()
        if s == "fno":
            s = "futures"   # legacy alias: the old combined F&O segment == futures now
        if m == "NSE":
            # NSE_UI_ONLY (owner 2026-07-13): NSE candidates come ONLY from the Upstox UI —
            # no nselib / OpenAlgo screener. Empty = honest abstain (never a stub/API fallback).
            # Options route through screen_nse_options (internally UI-gated: underlying LTP +
            # option-chain freshness from the Upstox UI; broker search only resolves the exact
            # tradable symbol, which is execution-path). Equity/futures use the UI movers.
            from trading.broker_sense.ui_data import nse_ui_only
            if nse_ui_only():
                if s == "options":
                    return screen_nse_options(self.nse, limit=limit, filters=filters)
                return screen_nse_ui(s, limit=limit)
            if s in ("intraday", "mtf"):
                return screen_nse_movers(self.nse, s, limit=limit, filters=filters)
            if s == "futures":
                return screen_nse_fno(self.nse, limit=limit, filters=filters)
            if s == "options":
                return screen_nse_options(self.nse, limit=limit, filters=filters)
            if s == "commodities":
                # MCX commodities trade as DATED FUTURES (GOLD05AUG26FUT) — resolve each
                # base name to the broker's exact near-month FUT symbol via OpenAlgo search.
                # Bare "GOLD" quotes 400'd → commodities never traded (research §2.4 fix).
                from trading.screener.commodities import screen_mcx_commodities
                return screen_mcx_commodities(self.nse, limit=limit, filters=filters)
        elif m == "CRYPTO":
            if s == "spot":
                return screen_crypto_spot(self.crypto, limit=limit, filters=filters)
            if s == "futures":
                return screen_crypto_futures(self.crypto, limit=limit, filters=filters)
            if s == "options":
                return screen_crypto_options(self.crypto, limit=limit, filters=filters)
            if s == "prediction":
                # Event markets (Polymarket public API; Predict.fun once a key is configured).
                from trading.screener.prediction import screen_crypto_prediction
                return screen_crypto_prediction(limit=limit, filters=filters)
        return []

    def candidates(self, market: str, segment: str, *, limit: int = 5,
                   filters: dict | None = None) -> list[dict]:
        """Ranked candidates for one segment; falls back to the deterministic stub."""
        m, s = market.upper(), segment.lower()
        key = f"{m}:{s}"
        if s not in SEGMENTS.get(m, []):
            self._last[key] = "invalid"
            return []
        # NSE_UI_ONLY (owner 2026-07-13): the Upstox-UI path runs even without an nse API
        # source, and an empty result is a HARD ABSTAIN — never the fake stub, never an API.
        nse_ui = False
        if m == "NSE":
            try:
                from trading.broker_sense.ui_data import nse_ui_only
                nse_ui = nse_ui_only()
            except Exception:
                nse_ui = False
        live: list[dict] = []
        if nse_ui or self.nse is not None or self.crypto is not None:
            try:
                live = self._live(m, s, limit, filters)
            except Exception:
                live = []
        if live:
            self._last[key] = "live"
            return live[:limit]
        if nse_ui:
            self._last[key] = "ui-abstain"       # eyes haven't fed NSE candidates → no trade
            return []
        self._last[key] = "stub"
        return stub_candidates(m, s, limit=limit)

    def watchlist(self, market: str, segments: list[str], *,
                  per_segment: int = 3, filters: dict | None = None) -> list[dict]:
        """Deduped union of candidates across the selected segments (varied basket).

        `filters` (e.g. {min_pct_change, min_quote_volume}) are forwarded to each
        per-segment screener so the dashboard filter bar narrows the candidate set."""
        seen: set[str] = set()
        out: list[dict] = []
        for seg in segments:
            for c in self.candidates(market, seg, limit=per_segment, filters=filters):
                k = f"{c['market']}:{c['segment']}:{c['symbol']}"
                if k in seen:
                    continue
                seen.add(k)
                out.append(c)
        out.sort(key=lambda c: c["score"], reverse=True)
        return out

    def status(self) -> dict:
        """Health snapshot for the dashboard (honest: shows live-vs-stub per segment)."""
        return {
            "ok": True,
            "nse_source": getattr(self.nse, "name", None),
            "crypto_source": getattr(self.crypto, "name", None),
            "segments": SEGMENTS,
            "last_modes": dict(self._last),
        }


def build_demo_screener() -> Screener:
    """Dashboard demo: a Screener with NO live sources → always returns stubs."""
    sc = Screener(nse_source=None, crypto_source=None)
    sc.nse = None          # force pure-offline: never touch the network
    sc.crypto = None
    return sc
