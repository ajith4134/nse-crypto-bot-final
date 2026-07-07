"""trading/broker_sense/screeners.py — the whole-universe screen runs on OTHER people's servers.

Savers A + J: as many filter conditions as possible are pushed INSIDE each screener's own
query so the broker's/TradingView's servers scan thousands of symbols for free and we only
receive a small pre-qualified shortlist.

Two lanes, both "their compute, not ours":
  • TV lane  — tradingview-screener (official scanner API, no login): SQL-like pushdown over
    NSE stocks + crypto with volume/%change/RSI/volatility conditions. Robust, structured,
    always available → the guaranteed floor under the funnel (owner decision #1).
  • APP lane — the broker apps' own built-in screener/mover pages opened in the brain's
    browser (sessions.py): what the owner asked for — the app's ALREADY-BUILT screens
    (top gainers/losers/volume shockers…). Parsed from the rendered page; anything the app
    shows beyond our schema is handed to learning_columns as discovered data (decision #6).

PresetStore: named pushdown presets per segment; each remembers how its picks traded so the
funnel ROTATES toward what's been working per regime (saver A, second half).
"""
from __future__ import annotations

import re
import time

from trading import state
from trading.broker_sense.brokers import screening_brokers

_PRESET_FILE = "broker_sense_presets.json"
_ROW = re.compile(r"([A-Z][A-Z0-9&\-\.]{1,19})\s*[\n\t ]+.*?(-?\d+\.?\d*)\s*%")
_CRYPTO_BASE = re.compile(r"^[A-Z0-9]{2,12}$")     # sane exchange base tokens only


_OTHER_QUOTES = ("USDC", "BUSD", "FDUSD", "TUSD", "TRY", "EUR", "GBP", "BTC", "ETH",
                 "BNB", "INR", "DAI", "USD")


def _crypto_pair(raw: str) -> str | None:
    """'XRP' / 'XRPUSDT' → 'XRP/USDT:USDT'; non-USDT-quoted pairs + junk tokens → None
    (we execute USDT-margined futures only — a 'VANRYTRY' pick would be a fake pair)."""
    if raw.endswith("USDT"):
        base = raw[:-4]
    elif len(raw) > 5 and raw.endswith(_OTHER_QUOTES):
        return None                        # BASE+other-quote ticker, not tradeable for us
    else:
        base = raw                         # bare base token (broker movers pages)
    if not _CRYPTO_BASE.match(base) or base in {"USD", "USDC", "INR", "BUSD"}:
        return None
    return f"{base}/USDT:USDT"


# ── TV lane: server-side pushdown (saver A) ─────────────────────────────────────────
# preset name -> (markets, builder). Conditions run ON TradingView's scanner servers.
def _tv_query(preset: str, market: str, limit: int):
    from tradingview_screener import Query, col
    if market == "nse":
        q = Query().select("name", "close", "volume", "change", "relative_volume_10d_calc",
                           "RSI", "ATR").limit(limit)
        q = q.set_markets("india").where(col("exchange") == "NSE")
        liq = col("volume") > 100_000
        chg, rsi, rvol = col("change"), col("RSI"), col("relative_volume_10d_calc")
        chg_field, mom_rvol, brk_rvol = "change", 1.5, 2.5
    else:
        # v3 gotcha: the crypto scanner is its own endpoint with its own field names —
        # a generic Query().set_markets("crypto") with equity fields matches NOTHING.
        # The lib's prebuilt crypto() Query carries the right URL + CEX filter.
        from tradingview_screener.screeners import crypto as crypto_base
        q = crypto_base().limit(limit).where(col("exchange") == "BINANCE")
        liq = col("24h_vol|5") > 1_000_000                # $1M+ traded in 24h
        chg, rsi, rvol = (col("24h_close_change|5"), col("RSI"),
                          col("24h_vol_change|5"))        # rvol here = 24h volume Δ%
        chg_field, mom_rvol, brk_rvol = "24h_close_change|5", 20, 100
    if preset == "momentum":
        return q.where(liq, chg > 1.5, rvol > mom_rvol)
    if preset == "oversold_bounce":
        return q.where(liq, rsi < 32, chg > 0)
    if preset == "overbought_fade":
        return q.where(liq, rsi > 68, chg < 0)
    if preset == "volatility_breakout":
        return q.where(liq, rvol > brk_rvol)
    return q.where(liq).order_by(chg_field, ascending=False)  # "top_movers" default


TV_PRESETS = ("momentum", "oversold_bounce", "overbought_fade", "volatility_breakout",
              "top_movers")


def tv_screen(market: str, preset: str = "top_movers", limit: int = 30) -> list[dict]:
    """Run one pushdown screen on TradingView's servers → [{symbol, close, change, …}].
    Empty list (never raises) when offline — the funnel treats lanes as best-effort."""
    try:
        n, df = _tv_query(preset, market, limit).get_scanner_data()
    except Exception:
        return []
    rows = []
    for _, r in df.iterrows():
        d = {k: (None if str(v) == "nan" else v) for k, v in r.items()}
        sym = str(d.get("ticker", "")).split(":")[-1]
        if market == "crypto":
            sym = _crypto_pair(sym.replace(".P", "")) or ""
            if not sym:
                continue
            # normalize the crypto scanner's own field names to the funnel schema
            if d.get("change") is None:
                d["change"] = d.get("24h_close_change|5")
            if d.get("volume") is None:
                d["volume"] = d.get("24h_vol|5")
        d["symbol"] = sym
        d["lane"], d["preset"] = "tradingview", preset
        rows.append(d)
    return rows


# ── APP lane: the broker app's own built-in screens (owner's step 3) ───────────────
def _parse_screen_page(broker, sessions, url: str, *, limit: int, preset: str) -> list[dict]:
    """Open `url` in the broker's (logged-in) browser context and parse the shortlist it shows.
    Extra labelled numbers on the page → learning_columns discovery. [] on any miss."""
    picks: list[dict] = []
    try:
        pg = sessions.page(broker.name, url, timeout_ms=15000)
        if pg is None:                       # login pending / page unavailable
            return []
        pg.wait_for_timeout(2500)
        body = pg.inner_text("body") or ""
        pg.close()
    except Exception:
        return []
    for m in _ROW.finditer(body[:20000]):
        sym, chg = m.group(1), float(m.group(2))
        if sym in {"NSE", "BSE", "USDT", "INR", "USD", "TOP", "ALL"} or len(picks) >= limit:
            continue
        if broker.market == "crypto":
            sym = _crypto_pair(sym) or ""
            if not sym:
                continue
        picks.append({"symbol": sym, "change": chg, "lane": broker.name, "preset": preset})
    try:                                     # decision #6: mine the page for NEW data fields
        from trading.broker_sense.learning_columns import discover_from_text
        discover_from_text(broker.name, body)
    except Exception:
        pass
    return picks


def app_screen(broker, sessions, *, limit: int = 20) -> list[dict]:
    """PUBLIC lane: the broker's built-in public screener/movers page (works without login)."""
    return _parse_screen_page(broker, sessions, broker.screener_url,
                              limit=limit, preset="app_builtin")


def account_screen(broker, sessions, *, limit: int = 20) -> list[dict]:
    """ACCOUNT lane: screen from the broker's LOGGED-IN markets/movers page (owner's account-first
    idea). Requires the connected account — returns [] (so the login ask stands) until then. The
    page to open is the LEARNED route (App Driving School) to the movers/screener data, NOT the
    account dashboard — so we land where the symbols actually are; the interception layer captures
    the account-gated data once the page loads logged-in."""
    try:
        from trading.brain.credentials import get_vault
        from trading.broker_sense.sessions import has_session
        # connected = saved vault login OR a saved browser session on disk (QR logins — e.g.
        # Upstox "scan with the app" — produce a session with no credentials ever typed)
        if not ((get_vault().get(broker.site) or {}).get("username")
                or has_session(broker.name)):
            return []                        # not connected yet → no account data
    except Exception:
        return []
    # FAST production read: the app's OWN market data via a direct call (~300ms), no heavy page
    # render — so account-first screening actually finishes inside the funnel's screen budget.
    try:
        from trading.broker_sense.app_school import get_school
        fast = get_school().fast_movers(broker.name, broker.market, limit=limit)
        if fast:
            return fast
    except Exception:
        pass
    # fallback ONLY if the fast read yielded nothing: navigate the learned markets page (slow)
    url = ""
    try:
        from trading.broker_sense.app_school import get_school
        route = get_school().route_to(broker.name, "movers") or \
            get_school().route_to(broker.name, "screener")
        if route:
            url = route.get("url", "")
    except Exception:
        url = ""
    url = url or broker.screener_url or broker.home_url
    return _parse_screen_page(broker, sessions, url, limit=limit, preset="account")


# ── preset performance memory + rotation (saver A) ──────────────────────────────────
class PresetStore:
    """Remembers, per (market, preset), how screened picks worked out; `pick()` rotates
    toward the best performer with an exploration floor so presets keep getting re-tried."""

    def __init__(self):
        self.data = state.load_json(_PRESET_FILE, {})

    def record(self, market: str, preset: str, *, traded: int, wins: int, pnl: float) -> None:
        k = f"{market}|{preset}"
        d = self.data.setdefault(k, {"traded": 0, "wins": 0, "pnl": 0.0, "used": 0})
        d["traded"] += traded; d["wins"] += wins; d["pnl"] += pnl
        d["used"] += 1; d["last_used"] = time.time()
        state.save_json(_PRESET_FILE, self.data)

    def pick(self, market: str, cycle_n: int = 0) -> str:
        if cycle_n % 5 == 4:                             # 1-in-5 exploration turn
            return TV_PRESETS[cycle_n // 5 % len(TV_PRESETS)]
        best, score = "top_movers", float("-inf")
        for p in TV_PRESETS:
            d = self.data.get(f"{market}|{p}")
            s = 0.0 if not d else (d["pnl"] / max(1, d["used"]))
            if s > score:
                best, score = p, s
        return best

    def status(self) -> dict:
        return dict(self.data)


def screen_all(market: str, sessions, *, preset: str, per_lane: int = 20,
               deadline: float | None = None) -> list[dict]:
    """Union of every screening lane for `market` (TV pushdown + each broker app's built-in
    screen), deduped by symbol, ranked by |%change|. All lanes best-effort — a broken/
    unlogged app never blocks the cycle (owner decision #1). `deadline` (time.monotonic,
    saver I): app lanes still pending when it passes are skipped THIS cycle — the TV lane
    (structured, fast) is the guaranteed floor, and skipped apps get their turn next bar."""
    from trading.broker_sense.data_sources import account_first, primary_broker, public_enabled
    # the market's primary account broker (state-backed, owner-switchable — e.g. nse→upstox
    # after Angel One blocked automated logins). When its PUBLIC data is switched OFF, go
    # account-first — drop the TradingView public floor too.
    primary = primary_broker(market)
    # ACCOUNT-ONLY mode: when the primary is account-first, screen ONLY that account (drop the
    # other exchanges' public lanes) so trades open from THE connected account's data alone.
    account_only = account_first(primary)
    rows = tv_screen(market, preset, limit=per_lane) if public_enabled(primary) else []
    for app in screening_brokers(market):
        if app.name == "tradingview":
            continue
        if account_only and app.name != primary:
            continue                                     # binance-account-only: skip other venues
        if deadline is not None and time.monotonic() > deadline:
            break                                        # bounded by construction
        if public_enabled(app.name):
            rows += app_screen(app, sessions, limit=per_lane)     # public screener page
        else:
            rows += account_screen(app, sessions, limit=per_lane)  # logged-in account page
    # NSE: keep only the liquid, F&O-eligible universe — the app/TV movers lanes surface
    # illiquid micro-caps (DBSTOCKBRO, IOLCP, TARC…) the brain rightly abstains on; the owner
    # wants the liquid 500+ intraday names. Falls back to the raw union if the liquid set is
    # unavailable or filters everything out (never go empty). (2026-07-07 fix)
    if market == "nse":
        # seed the reliable liquid F&O universe (ranked by live OpenAlgo momentum) so the
        # funnel always has deep-liquidity candidates even if the TV/app lanes are thin.
        # Best-effort — MUST NOT swallow the liquid FILTER below (kept in its own try so a
        # seeding failure can never let micro-caps slip through). (2026-07-07 fix)
        try:
            from trading.screener.universe import liquid_movers
            from trading.screener.sources import LiveNSESource
            src = LiveNSESource()
            for m in liquid_movers(src._oa_quote, limit=40):
                rows.append({"symbol": m["symbol"], "change": m.get("pct_change", 0.0),
                             "lane": "liquid_universe"})
        except Exception:
            pass
        # ALWAYS filter to the liquid, F&O-eligible universe (independent of the seed).
        try:
            from trading.screener.universe import is_liquid
            liq_rows = [r for r in rows if is_liquid(r.get("symbol", ""))]
            if liq_rows:
                rows = liq_rows
        except Exception:
            pass
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: abs(float(r.get("change") or 0)), reverse=True):
        if r["symbol"] not in seen:
            seen.add(r["symbol"])
            out.append(r)
    return out
