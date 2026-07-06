"""trading/broker_sense/app_explorer.py — use EVERY feature a trading app offers (decision #6).

A human trader on a broker web app doesn't just read one chart: they flip timeframes, add
indicators, open market depth, skim the news tab, check the technicals gauge, the option
chain, delivery %, OI… This module makes the brain do the same, systematically:

  • FeatureCatalog — per app, a persistent map of everything the app's UI offers
    (buttons/tabs/menus/links found on its pages). Every crawl updates it; NEW features are
    announced on the mind stream, so the catalog grows the way a human's familiarity does.
  • explore(broker) — read-only crawl of the app's main surfaces (home, screener, a chart,
    depth/news tabs when present): catalogs features + hands every labelled number on the
    page to learning_columns (discovered data → learning).
  • human_checklist(symbol, broker) — the pre-trade routine a human runs, assembled from
    the app itself: multi-timeframe chart read (chart_vision), indicator values the app
    prints, top-of-book (book_monitor), headlines. Returns the app_signals dict that rides
    decision_snapshot into the journal.

Reuses the Voyager-style GuiSkillLibrary + Reflexion reflector from trading/brain/gui so
what works on each app compounds as skills/lessons. Strictly read-only: navigation + typing
into FILTER/search boxes only — the sessions/web_screener forbidden-click guard stays law.
"""
from __future__ import annotations

import time

from trading import state
from trading.broker_sense.brokers import REGISTRY, BrokerApp
from trading.broker_sense.learning_columns import discover_from_text, get_registry

_FILE = "broker_sense_features.json"
_TABS = ("chart", "depth", "news", "technicals", "analytics", "option", "overview",
         "fundamentals", "events", "f&o", "similar", "market depth")

# Auto-typing of discovered controls (owner ask: find ALL features, don't hardcode the named
# list). First keyword hit wins; anything unmatched stays an honest "control" (recorded, never
# claimed to be something it isn't). This is how the brain names what it clicks the way a human
# builds familiarity with an app's surface.
_FEATURE_KINDS = [
    ("indicator", ("indicator", "ema", "sma", "moving average", "bollinger", "supertrend",
                   "rsi", "macd", "sar", "stochastic", "ichimoku", "vwap", "pivot", "study")),
    ("pattern", ("pattern", "candlestick", "engulf", "doji", "harmonic", "elliott")),
    ("depth", ("depth", "order book", "orderbook", "market depth", "bids", "asks")),
    ("trades", ("trades", "time & sales", "recent trades", "tape", "market trades")),
    ("chart", ("chart", "timeframe", "interval", "1m", "5m", "candles", "tradingview", "kline")),
    ("technicals", ("technical", "gauge", "summary", "oscillator", "signal", "rating")),
    ("option_chain", ("option chain", "option-chain", "greeks", "oi", "put call", "strike")),
    ("news", ("news", "announcement", "square", "feed", "headline")),
    ("screener", ("screener", "scanner", "filter", "discover", "ideas", "movers", "gainers")),
    ("funding", ("funding", "premium", "basis", "mark price", "index price")),
    ("info", ("info", "about", "overview", "fundamentals", "specification", "contract")),
]


def classify_feature(label: str) -> str:
    low = (label or "").lower()
    for kind, needles in _FEATURE_KINDS:
        if any(n in low for n in needles):
            return kind
    return "control"


class FeatureCatalog:
    """What each app offers, learned by looking — persisted + honest."""

    def __init__(self):
        self.data = state.load_json(_FILE, {})       # app -> {features: {label: {...}}, ...}

    def note(self, app: str, label: str, kind: str, where: str, url: str = "") -> bool:
        label = label.strip()[:60]
        if not label:
            return False
        # auto-type when the caller passed the generic "control" — record the RICHER kind
        if kind == "control":
            kind = classify_feature(label)
        entry = self.data.setdefault(app, {"features": {}, "last_crawl": 0})
        new = label not in entry["features"]
        f = entry["features"].setdefault(label, {"kind": kind, "where": where,
                                                 "first_seen": time.time(), "n_seen": 0})
        f["n_seen"] += 1
        f["kind"] = kind                             # upgrade a previously-generic classification
        if where:
            f["where"] = where
        if url:                                      # the REAL page URL the feature lives on
            f["url"] = url[:300]
            f["last_seen"] = time.time()
        return new

    def save(self, app: str) -> None:
        self.data.setdefault(app, {"features": {}})["last_crawl"] = time.time()
        state.save_json(_FILE, self.data)

    def status(self) -> dict:
        out = {}
        for app, d in self.data.items():
            feats = d.get("features", {})
            kinds: dict = {}
            n_real = 0                               # features grounded on a REAL page URL (not test)
            for meta in feats.values():
                kinds[meta.get("kind", "control")] = kinds.get(meta.get("kind", "control"), 0) + 1
                if meta.get("url"):
                    n_real += 1
            out[app] = {"n_features": len(feats), "n_with_url": n_real,
                        "last_crawl": d.get("last_crawl"),
                        "by_kind": dict(sorted(kinds.items(), key=lambda kv: -kv[1])),
                        "sample": sorted(feats)[:12]}
        return out


_CAT: FeatureCatalog | None = None


def get_catalog() -> FeatureCatalog:
    global _CAT
    if _CAT is None:
        _CAT = FeatureCatalog()
    return _CAT


def _crawl_page(app: BrokerApp, pg, where: str, cat: FeatureCatalog,
                symbol: str | None = None) -> dict:
    """Read one open page like a curious human: catalog its controls/tabs, mine its numbers."""
    found_new = []
    try:
        body = pg.inner_text("body") or ""
    except Exception:
        body = ""
    try:
        page_url = pg.url or ""
    except Exception:
        page_url = ""
    for el in pg.query_selector_all("button, a[role=button], [role=tab], nav a")[:80]:
        try:
            t = (el.inner_text() or "").strip()
            if t and len(t) < 60 and cat.note(app.name, t, "control", where, url=page_url):
                found_new.append(t)
        except Exception:
            continue
    cols = discover_from_text(app.name, body, symbol=symbol)
    return {"where": where, "new_features": found_new, "new_columns": cols,
            "text_len": len(body)}


def explore(broker: str, sessions, *, symbol: str | None = None,
            max_tabs: int = 4) -> dict:
    """Read-only exploration of one app: home + screener + (symbol page and its tabs when a
    symbol is given). Every crawl grows the feature catalog + learning columns."""
    app = REGISTRY[broker]
    cat = get_catalog()
    visits: list[dict] = []
    try:
        pg = sessions.page(broker, app.screener_url or app.home_url)
        if pg is None:
            return {"app": broker, "ok": False, "reason": "login pending (asked in chat)"}
        visits.append(_crawl_page(app, pg, "screener", cat))
        if symbol and app.chart_url:
            url = app.chart_url.format(symbol=symbol.split("/")[0], interval="5")
            pg.goto(url, timeout=30000, wait_until="domcontentloaded")
            pg.wait_for_timeout(2500)
            visits.append(_crawl_page(app, pg, f"symbol:{symbol}", cat, symbol=symbol))
            # open the tabs a human would (depth / news / technicals / option chain …)
            opened = 0
            for el in pg.query_selector_all("[role=tab], button, a")[:120]:
                if opened >= max_tabs:
                    break
                try:
                    t = (el.inner_text() or "").strip().lower()
                except Exception:
                    continue
                if any(k in t for k in _TABS) and len(t) < 30:
                    try:
                        el.click(timeout=2000)
                        pg.wait_for_timeout(1500)
                        visits.append(_crawl_page(app, pg, f"tab:{t}", cat, symbol=symbol))
                        opened += 1
                    except Exception:
                        continue
        pg.close()
    except Exception as e:
        return {"app": broker, "ok": False, "reason": str(e)[:160], "visits": visits}
    cat.save(broker)
    new_feats = [f for v in visits for f in v["new_features"]]
    if new_feats:
        try:
            from trading.brain import mind_events
            mind_events.emit("discovery",
                             f"Learned {len(new_feats)} new {broker} feature(s): "
                             f"{', '.join(new_feats[:6])}", salience=0.6,
                             data={"app": broker, "features": new_feats[:20]})
        except Exception:
            pass
    return {"app": broker, "ok": True, "visits": visits,
            "n_new_features": len(new_feats)}


def human_checklist(symbol: str, market: str, sessions, *, chart=None, book=None) -> dict:
    """The pre-trade routine a human runs on the app, packaged as app_signals for the
    journal. chart/book results are passed in by the funnel (already computed there)."""
    sig: dict = {"checked_at": time.time(), "symbol": symbol, "market": market}
    if chart:
        sig["chart"] = {tf: {"direction": c.get("direction"), "p_up": c.get("p_up"),
                             "source": c.get("source")} for tf, c in chart.items()}
    if book:
        sig["book"] = {k: book.get(k) for k in ("bid", "ask", "spread_pct", "source",
                                                "consistent")}
    sig.update({k: v for k, v in get_registry().snapshot(symbol).items()
                if not k.startswith("_")})
    return sig
