"""trading/broker_sense/app_school.py — the brain LEARNS to drive a broker app (self-driving-car
style) instead of visiting hardcoded pages.

The brain opens the LOGGED-IN app and, read-only, clicks the labelled features (Markets, Spot,
Futures, Options, Screener, filters…). After each click it looks at the app's OWN network
traffic (interception) to learn TRUTHFULLY which page exposed which market-data kind — then
records the golden ROUTE to that data (url + which control led there + the endpoint). Over
sessions it reuses what it knows (habit) and explores what it doesn't (curiosity), covering more
of the app each time. Nothing is hardcoded: SEED_ROUTES are only a cold-start fallback that a
learned route immediately overrides.

Stitches, does not reinvent:
  • sessions.SessionManager  — opens the logged-in persistent-profile page
  • interception.NetworkRecorder — the ground truth of which data lives where
  • ocular_cortex.OcularCortex   — LayoutMemory (golden paths) + novelty
  • computer_use (_find_control / _control_forbidden) — the SAFE click primitive (never buy/sell)
  • app_explorer.FeatureCatalog  — the running catalogue of every feature seen

Read-only: it clicks to LOOK; execution stays in exec_adapter (APIs). Budget-bounded so a cycle
can't wedge."""
from __future__ import annotations

import datetime
import os
import time
import zoneinfo

from trading import state
from trading.broker_sense.brokers import REGISTRY

_IST = zoneinfo.ZoneInfo("Asia/Kolkata")


def market_status(broker: str) -> dict:
    """Is this broker's market live NOW? The school can only LEARN market-data routes from live
    traffic, so an honest badge tells the dashboard WHY a broker isn't progressing. Binance (crypto)
    = 24/7; Upstox (NSE) = weekdays 09:15–15:30 IST."""
    if broker == "upstox":
        now = datetime.datetime.now(_IST)
        weekday = now.weekday() < 5
        opn = now.replace(hour=9, minute=15, second=0, microsecond=0)
        cls = now.replace(hour=15, minute=30, second=0, microsecond=0)
        is_open = weekday and opn <= now <= cls
        note = ("NSE open — learning live" if is_open else
                "NSE closed — learning resumes 09:15 IST (Mon–Fri); no live feed after hours")
        return {"open": is_open, "note": note, "hours": "09:15–15:30 IST"}
    return {"open": True, "note": "Crypto 24/7 — always learnable", "hours": "24/7"}

_MAP_FILE = "app_school_map.json"
_CLICKS_PER_PAGE = 6                     # breadth-first: click a few controls per page, then move on

# Popup / ad / cookie / modal dismissal (owner: "if stuck on a popup or ad, close it via the X
# and keep going"). Selectors for the close affordance; text hints for consent/skip buttons.
_POPUP_CLOSE_SEL = (
    "[aria-label='Close'], [aria-label='close'], [aria-label*='dismiss' i], "
    "button[title='Close'], .modal-close, .close-button, .btn-close, [data-dismiss], "
    "[class*='close' i][role=button], [class*='CloseButton' i], [class*='modal' i] [class*='close' i]")
_POPUP_CLOSE_TEXT = ("×", "✕", "✖", "x", "close", "no thanks", "not now", "maybe later",
                     "skip", "dismiss", "got it", "accept", "accept all", "i agree",
                     "allow all", "continue", "ok", "okay")
# text that means "this is a real popup/ad we should close" (avoid closing the app itself)
_POPUP_HINTS = ("popup", "modal", "dialog", "overlay", "advertisement", "promo", "cookie",
                "notification", "download the app", "install", "subscribe", "offer")

# Frontier steering (owner: reach ALL the DATA pages, not waste budget on download/legal/blog).
# URL/text tokens that mean "this is a market-DATA page" (crawl these FIRST) …
_DATA_URL_HINTS = ("market", "future", "option", "spot", "trade", "derivativ", "screen",
                   "discover", "chart", "watchlist", "movers", "gainer", "loser", "depth",
                   "orderbook", "order-book", "liquidation", "funding", "open-interest",
                   "long-short", "heatmap", "eoptions", "convert", "earn", "stocks", "fno",
                   "positions", "holdings", "orders", "funds", "portfolio", "ticker", "price")
# … and tokens that mean "junk for our purpose" (never enqueue — download/legal/marketing/help)
_JUNK_URL_HINTS = ("download", "/app", "install", "career", "job", "legal", "privacy", "terms",
                   "cookie", "about", "blog", "news/", "press", "support", "help", "faq",
                   "contact", "community", "referral", "affiliate", "academy", "learn/", "guide",
                   "campaign", "promotion", "gift", "reward", "verify", "kyc", "signup",
                   "register", "sign-up", "login", "logout", "setting", "profile", "notification",
                   "square", "windows", "linux", "ios", "android", "macos", "chrome", "api-docs")

# The market-data GOALS the brain must find to trade a segment fully — expressed as the data
# KINDS (interception classifications) + human label hints that usually lead there. These are
# GOALS (what to look for), not routes (where it is) — the brain learns the routes itself.
DATA_GOALS = {
    "binance": {
        "movers": {"kinds": ["movers", "ticker"],
                   "labels": ["markets", "gainers", "losers", "hot", "top movers", "24h", "volume"]},
        "spot_symbols": {"kinds": ["ticker"], "labels": ["spot", "markets", "all coins", "trade"]},
        "futures": {"kinds": ["funding", "open_interest", "ticker"],
                    "labels": ["futures", "perpetual", "usd-m", "coin-m", "derivatives"]},
        "options": {"kinds": ["option_chain"], "labels": ["options", "eoptions", "rfq"]},
        # NOTE: Binance has NO distinct "screener" product (the Markets page = movers/gainers, already
        # a goal) — removed 2026-07-06 after live endpoint audit found no screener feed. Upstox keeps
        # its screener goal (Dartstock is a real screener).
        "orderbook": {"kinds": ["orderbook"], "labels": ["order book", "depth", "trade"]},
        "long_short": {"kinds": ["long_short"], "labels": ["long", "short", "ratio", "sentiment"]},
        "liquidation": {"kinds": ["liquidation"], "labels": ["liquidation", "heatmap"]},
        # additional capabilities (feature audit 2026-07-06) — richer futures + margin signals
        "taker_volume": {"kinds": ["taker_volume"],
                         "labels": ["taker", "buy/sell volume", "taker buy sell", "trading data"]},
        "open_interest": {"kinds": ["open_interest"],
                          "labels": ["open interest", "oi", "trading data"]},
        "margin": {"kinds": ["margin"],
                   "labels": ["margin", "borrow", "cross margin", "isolated", "interest rate"]},
        # per-symbol decision data (feature audit 2026-07-06) — all fire on a futures TRADE page,
        # classified by trading/broker_sense/interception. These feed the indicator-fusion engine.
        "recent_trades": {"kinds": ["recent_trades"],
                          "labels": ["trades", "market trades", "recent trades", "trade history"]},
        "mark_price": {"kinds": ["mark_price"],
                       "labels": ["mark price", "mark", "premium index"]},
        "index_price": {"kinds": ["index_price"],
                        "labels": ["index price", "index", "spot index"]},
        "basis": {"kinds": ["basis"], "labels": ["basis", "annualized basis", "trading data"]},
        "symbol_info": {"kinds": ["symbol_info"],
                        "labels": ["contract", "specification", "info", "instrument", "details"]},
    },
    # Upstox (NSE equity + F&O) — its OWN goal set so the brain never confuses it with Binance.
    # Learned from the logged-in Upstox Pro app's own traffic (QR-login session on disk).
    "upstox": {
        "movers": {"kinds": ["movers", "ticker"],
                   "labels": ["gainers", "losers", "top gainers", "top losers", "most active",
                              "market movers", "discover"]},
        "spot_symbols": {"kinds": ["ticker"], "labels": ["watchlist", "stocks", "equity", "nifty",
                                                          "my list", "markets"]},
        "futures": {"kinds": ["ticker", "open_interest"],
                    "labels": ["f&o", "futures", "derivatives", "option chain", "fno"]},
        "options": {"kinds": ["option_chain"], "labels": ["option chain", "options", "oc"]},
        "screener": {"kinds": ["screener", "movers"],
                     "labels": ["screener", "scanner", "filter", "discover", "ideas"]},
        "orderbook": {"kinds": ["orderbook"], "labels": ["market depth", "depth", "order book",
                                                         "buy/sell"]},
        # additional capabilities (feature audit 2026-07-06) — whole segments + F&O analytics.
        # Validated at NSE market hours (09:15–15:30 IST); after-hours there's no live feed.
        "commodities": {"kinds": ["ticker", "open_interest"],
                        "labels": ["commodit", "mcx", "ncdex", "gold", "crude", "silver", "gas"]},
        "currency": {"kinds": ["ticker"],
                     "labels": ["currency", "usdinr", "forex", "cds", "eurinr", "gbpinr"]},
        "greeks": {"kinds": ["option_chain"],
                   "labels": ["greek", "delta", "gamma", "theta", "vega", "iv", "implied"]},
        "pcr": {"kinds": ["option_chain"],
                "labels": ["pcr", "put call", "max pain", "india vix", "oi"]},
    },
}

# Cold-start ONLY: a first place to look before anything is learned. A learned route (grounded
# in real traffic) overrides these immediately. Never treated as truth.
SEED_ROUTES = {
    "binance": {
        "movers": "https://www.binance.com/en/markets/overview",
        "spot_symbols": "https://www.binance.com/en/markets/overview",
        # A futures TRADE page is the data hub — it streams funding, open-interest, the long/short
        # ratio, the liquidation feed AND the order book all at once, so one visit can learn several
        # still-missing goals from real traffic (classified by trading/broker_sense/interception).
        "futures": "https://www.binance.com/en/futures/BTCUSDT",
        "options": "https://www.binance.com/en/eoptions/BTCUSDT",   # a symbol page → option-chain fires
        "orderbook": "https://www.binance.com/en/trade/BTC_USDT",   # spot depth websocket
        # authoritative Futures "Trading Data" hub — streams global + top-trader long/short ratio,
        # open interest and taker buy/sell volume (verified via online feature audit 2026-07-06).
        "long_short": "https://www.binance.com/en/futures/funding-history/perpetual/trading-data",
        "liquidation": "https://www.binance.com/en/futures/BTCUSDT",   # trade page liquidation feed
        # new capabilities — the Trading-Data hub streams taker buy/sell vol + open interest too;
        # margin borrow/interest fires on the margin trading interface.
        "taker_volume": "https://www.binance.com/en/futures/funding-history/perpetual/trading-data",
        "open_interest": "https://www.binance.com/en/futures/funding-history/perpetual/trading-data",
        "margin": "https://www.binance.com/en/trade/BTC_USDT?type=margin",
        # per-symbol decision data — the futures TRADE page streams the trades tape, mark/index price
        # and basis; exchangeInfo (symbol_info) fires on any futures page load.
        "recent_trades": "https://www.binance.com/en/futures/BTCUSDT",
        "mark_price": "https://www.binance.com/en/futures/BTCUSDT",
        "index_price": "https://www.binance.com/en/futures/BTCUSDT",
        "basis": "https://www.binance.com/en/futures/funding-history/perpetual/trading-data",
        "symbol_info": "https://www.binance.com/en/futures/BTCUSDT",
    },
    "upstox": {                          # logged-in Upstox Pro (QR-login session); learned routes override
        "movers": "https://pro.upstox.com/discover",
        "spot_symbols": "https://pro.upstox.com/",
        "futures": "https://pro.upstox.com/options-chain",
        "options": "https://pro.upstox.com/options-chain",
        "screener": "https://pro.upstox.com/discover",
        "orderbook": "https://pro.upstox.com/",
        # new capabilities (reached via the click-nav adapter at market open — deep-links redirect)
        "commodities": "https://pro.upstox.com/trading-charts",
        "currency": "https://pro.upstox.com/trading-charts",
        "greeks": "https://pro.upstox.com/option-chain",
        "pcr": "https://pro.upstox.com/option-chain",
    },
}


class AppMap:
    """Persistent learned routes: broker → data_kind → best route (url, via, endpoint, reliability).
    Plus a visited set so exploration doesn't re-click the same control forever."""

    def __init__(self):
        self._load()

    def _load(self):
        d = state.load_json(_MAP_FILE, {})
        self.routes: dict = d.get("routes", {})       # broker -> kind -> {url, via, endpoint, n, ts}
        self.visited: dict = d.get("visited", {})     # broker -> [labels clicked]
        # FULL SITE MAP (owner: "find ALL pages and links, not only segment pages"):
        self.pages: dict = d.get("pages", {})         # broker -> {url: {title, links, controls, n, ts}}
        self.links: dict = d.get("links", {})         # broker -> {url: {text, seen}}  (every link seen)
        self.stats: dict = d.get("stats", {})         # cumulative counters (survive restarts)

    def reload(self):
        """Re-read the map from disk. The DASHBOARD process reads via this before serving status so
        it mirrors the LEARNING written by the separate explore subprocess / monitor (JSON = single
        source of truth) — otherwise the panel shows a stale snapshot frozen at dashboard start."""
        self._load()

    def record(self, broker: str, kind: str, *, url: str, via: str, endpoint: str = "") -> bool:
        b = self.routes.setdefault(broker, {})
        cur = b.get(kind)
        now = time.time()
        if cur is None:
            b[kind] = {"url": url, "via": via, "endpoint": endpoint, "n": 1,
                       "first_seen": now, "last_seen": now, "confirmed": True}
            return True
        cur["n"] += 1
        cur["last_seen"] = now
        # UPGRADE only from a generic 'home' route to a specific control — never let a later
        # generic click clobber an already-learned specific route (owner: keep the best path)
        if cur.get("via") == "home" and via != "home":
            cur.update({"url": url, "via": via, "endpoint": endpoint or cur.get("endpoint", "")})
        return False

    def best(self, broker: str, kind: str) -> dict | None:
        r = self.routes.get(broker, {}).get(kind)
        return dict(r) if r else None

    def mark_visited(self, broker: str, label: str) -> None:
        v = self.visited.setdefault(broker, [])
        if label not in v:
            v.append(label)
            del v[:-400]

    def is_visited(self, broker: str, label: str) -> bool:
        return label in self.visited.get(broker, [])

    def record_page(self, broker: str, url: str, *, title: str = "", links=None,
                    controls=None) -> bool:
        """Save a VISITED page (full site map) — url + title + the links/controls found on it.
        Returns True the first time this url is seen (a genuinely new page)."""
        if not url:
            return False
        b = self.pages.setdefault(broker, {})
        fresh = url not in b
        now = time.time()
        rec = b.setdefault(url, {"title": title, "links": [], "controls": [], "n": 0,
                                 "first_seen": now})
        rec["title"] = title or rec.get("title", "")
        rec["links"] = sorted(set(rec.get("links", [])) | set(links or []))[:200]
        rec["controls"] = sorted(set(rec.get("controls", [])) | set(controls or []))[:200]
        rec["n"] += 1
        rec["last_seen"] = now
        return fresh

    def record_links(self, broker: str, items) -> int:
        """Catalog every discovered link (url + its anchor text). Returns count of NEW links."""
        b = self.links.setdefault(broker, {})
        new = 0
        for url, text in items:
            if not url:
                continue
            if url not in b:
                new += 1
            e = b.setdefault(url, {"text": text or "", "seen": 0})
            e["text"] = text or e.get("text", "")
            e["seen"] += 1
        # bound the store so it never grows unbounded
        if len(b) > 2000:
            self.links[broker] = dict(list(b.items())[-2000:])
        return new

    def known_pages(self, broker: str) -> set:
        return set(self.pages.get(broker, {}))

    def missing(self, broker: str) -> list[str]:
        goals = set(DATA_GOALS.get(broker, {}))
        have = set(self.routes.get(broker, {}))
        return sorted(goals - have)

    def coverage(self, broker: str) -> dict:
        goals = DATA_GOALS.get(broker, {})
        learned = self.routes.get(broker, {})
        return {"learned": sorted(learned), "missing": sorted(set(goals) - set(learned)),
                "pct": round(100 * len(set(goals) & set(learned)) / max(1, len(goals)))}

    def save(self) -> None:
        state.save_json(_MAP_FILE, {"routes": self.routes, "visited": self.visited,
                                    "pages": self.pages, "links": self.links,
                                    "stats": self.stats})

    def status(self) -> dict:
        # EVERY broker in DATA_GOALS always appears (each with its own routes + coverage) so a
        # per-broker panel (binance, upstox, …) shows its goals immediately, before it explores —
        # and the two schools never share/confuse state (keyed strictly by broker).
        out = {}
        for b in DATA_GOALS:
            kinds = self.routes.get(b, {})
            out[b] = {"routes": {k: {"url": r["url"], "via": r.get("via"), "n": r.get("n"),
                                     "endpoint": r.get("endpoint", "")}
                                 for k, r in kinds.items()},
                      # full site map (owner: "find ALL pages and links"): counts + a sample
                      "pages_found": len(self.pages.get(b, {})),
                      "links_found": len(self.links.get(b, {})),
                      "recent_pages": [{"url": u, "title": (p or {}).get("title", "")}
                                       for u, p in list(self.pages.get(b, {}).items())[-8:]],
                      "market": market_status(b),   # live/closed badge — honest "why no progress"
                      **self.coverage(b)}
        return out


class AppSchool:
    """Autonomous exploration driver — learns to drive the logged-in broker app."""

    def __init__(self, *, sessions=None, cortex=None):
        self._sessions = sessions
        self._cortex = cortex
        self.map = AppMap()
        # stats live IN the map so they persist across restarts (self.map.save writes them)
        self.stats = self.map.stats
        for k in ("explorations", "clicks", "routes_learned", "popups_closed"):
            self.stats.setdefault(k, 0)

    def sessions(self):
        if self._sessions is None:
            from trading.broker_sense.sessions import get_sessions
            self._sessions = get_sessions()
        return self._sessions

    def cortex(self):
        if self._cortex is None:
            from trading.brain.vision.ocular_cortex import get_cortex
            self._cortex = get_cortex()
        return self._cortex

    def recorder(self):
        from trading.broker_sense.interception import get_recorder
        return get_recorder()

    # ── the learned route (habit) — what account_screen etc. call ────────────────
    def route_to(self, broker: str, data_kind: str) -> dict | None:
        """Best LEARNED route to a data kind; falls back to a cold-start seed (marked unconfirmed)
        until the brain has learned the real one."""
        r = self.map.best(broker, data_kind)
        if r:
            return {**r, "source": "learned"}
        seed = SEED_ROUTES.get(broker, {}).get(data_kind)
        if seed:
            return {"url": seed, "via": "seed", "source": "seed", "confirmed": False}
        return None

    # ── FAST read (production) — the app's data direct, no page render ────────────
    def fast_movers(self, broker: str, market: str, *, limit: int = 30,
                    segment: str = "futures") -> list[dict]:
        """Read the whole movers/symbols universe the FAST way the app itself does — one direct
        market-data call, NOT a heavy page render. This is the 'learn the path, then read the data
        directly' production mode: ~300ms vs ~30s, so account-first screening finishes in budget.
        Same numbers the Binance page shows. Crypto via ccxt (Binance spot/futures)."""
        if market != "crypto":
            return []
        try:
            ex = _ccxt_exchange(segment)         # cached + markets pre-loaded → repeat calls ~300ms
            tickers = ex.fetch_tickers()
        except Exception:
            return []
        vmin = _min_quote_volume()               # liquidity floor: skip illiquid micro-caps whose
        rows = []                                # wide spreads the risk rule would cull anyway
        for sym, t in tickers.items():
            pct, vol = t.get("percentage"), t.get("quoteVolume")
            if pct is None:
                continue
            try:
                vol_f = float(vol) if vol is not None else 0.0
                if vol_f < vmin:                 # not liquid enough to trade cleanly
                    continue
                rows.append({"symbol": sym, "change": float(pct), "lane": broker,
                             "preset": "account_fast", "volume": vol_f})
            except (TypeError, ValueError):
                continue
        rows.sort(key=lambda r: abs(r["change"]), reverse=True)
        return rows[:limit]

    # ── the exploration (curiosity) — learn to drive the app ─────────────────────
    def explore(self, broker: str, *, budget_s: float = 90.0, max_clicks: int = 20,
                full_site: bool = True, max_pages: int = 40) -> dict:
        """Explore the logged-in app read-only, learning routes from its OWN traffic.

        full_site=True (owner's ask): a WHOLE-SITE crawl — follow EVERY same-domain link, not just
        segment/goal controls, cataloguing every page + link found; click all safe controls on each
        page; dismiss any popup/ad/cookie modal (press its X) so it never gets stuck. Bounded by
        budget_s + max_pages + max_clicks. Strictly read-only (never a buy/sell/withdraw control)."""
        t0 = time.monotonic()
        rep = {"broker": broker, "clicked": [], "learned": [], "goals_met": [], "error": None,
               "pages_visited": [], "new_pages": 0, "new_links": 0, "popups_closed": 0}
        app = REGISTRY.get(broker)
        if app is None:
            rep["error"] = "unknown broker"
            return rep
        pg = self.sessions().page(broker, app.home_url, timeout_ms=40000)
        if pg is None:
            rep["error"] = "not logged in / page unavailable"
            return rep
        self.stats["explorations"] += 1
        seen_clicks: set = set()
        try:
            from urllib.parse import urlparse
            domain = urlparse(app.home_url).netloc.split(".")[-2:] and \
                ".".join(urlparse(app.home_url).netloc.split(".")[-2:])
            frontier = [pg.url or app.home_url]      # BFS link frontier (same-registrable-domain)
            visited_urls: set = set()
            # SEED SWEEP (owner: reach 100%): before the generic crawl, go STRAIGHT to the known
            # data-hub URL for each STILL-MISSING goal and harvest the route from that page's own
            # traffic. This closes the goals the link-crawl rarely reaches (options / order book /
            # long-short / liquidation live behind deep nav, not top-level links). Grounded + honest:
            # a route is recorded ONLY if the app actually emitted that data kind there.
            self._seed_sweep(broker, pg, domain, rep, t0, budget_s, visited_urls, frontier,
                             full_site=full_site)
            while frontier and time.monotonic() - t0 < budget_s and len(visited_urls) < max_pages:
                url = frontier.pop(0)
                if url in visited_urls:
                    continue
                visited_urls.add(url)
                if pg.url != url:
                    try:
                        pg.goto(url, timeout=25000, wait_until="domcontentloaded")
                        pg.wait_for_timeout(1500)
                    except Exception:
                        continue
                rep["popups_closed"] += self._dismiss_popups(pg)   # clear ads/modals FIRST
                via = "home" if url in (app.home_url, pg.url) and not rep["pages_visited"] else url
                self._harvest(broker, pg, via="home", rep=rep)     # learn goal routes from traffic
                # catalog THIS page + all its links (the full site map the owner wants)
                links = self._collect_links(pg, domain)
                controls = self._controls(broker, pg)
                if self.map.record_page(broker, pg.url, title=self._title(pg),
                                        links=[u for u, _ in links], controls=controls):
                    rep["new_pages"] += 1
                rep["new_links"] += self.map.record_links(broker, links)
                rep["pages_visited"].append(pg.url)
                # click a FEW SAFE controls per page (goal-relevant first) to trigger data traffic,
                # then MOVE ON — a per-page cap keeps the crawl BREADTH-first so it reaches all the
                # data pages instead of burning the whole budget clicking one page's every control.
                page_clicks = 0
                for label in self._rank(broker, controls, full=full_site):
                    if time.monotonic() - t0 > budget_s or len(rep["clicked"]) >= max_clicks \
                            or page_clicks >= _CLICKS_PER_PAGE:
                        break
                    page_clicks += 1
                    key = f"{pg.url}|{label.lower()}"
                    if key in seen_clicks:
                        continue
                    seen_clicks.add(key)
                    if not self._safe_click(pg, label):
                        continue
                    pg.wait_for_timeout(1800)
                    self._dismiss_popups(pg)
                    self.stats["clicks"] += 1
                    rep["clicked"].append(label)
                    before = len(rep["learned"])
                    self._harvest(broker, pg, via=label, rep=rep)
                    if len(rep["learned"]) > before:
                        self.map.mark_visited(broker, label)
                    # SPA nav changes the URL without a page load — capture the new "page" + its
                    # links so a button-driven app (Upstox Pro) is mapped as fully as an href site
                    new_url = pg.url
                    if new_url not in visited_urls:
                        newlinks = self._collect_links(pg, domain)
                        if self.map.record_page(broker, new_url, title=self._title(pg),
                                                links=[u for u, _ in newlinks],
                                                controls=self._controls(broker, pg)):
                            rep["new_pages"] += 1
                        rep["new_links"] += self.map.record_links(broker, newlinks)
                        if new_url not in rep["pages_visited"]:
                            rep["pages_visited"].append(new_url)
                        if full_site:
                            self._enqueue(frontier, newlinks, visited_urls)
                # enqueue newly-found same-domain links to crawl next (full-site only)
                if full_site:
                    self._enqueue(frontier, links, visited_urls)
                    frontier.sort(key=self._url_priority)   # data pages first, junk never
                    del frontier[max_pages * 3:]            # keep the frontier bounded
                self.map.save()
            rep["pages_known"] = len(self.map.known_pages(broker))
            rep["links_known"] = len(self.map.links.get(broker, {}))
        except Exception as e:
            rep["error"] = f"{type(e).__name__}: {str(e)[:140]}"
        finally:
            try:
                pg.close()
            except Exception:
                pass
        self.map.save()
        # DIRECT-FEED fallback (browser closed): for goals that are websocket-only and never appear
        # in the headless app's traffic (Binance liquidation), ground the route on the verified
        # PUBLIC feed instead — record only after a REAL event is observed. Bounded per goal.
        try:
            from trading.broker_sense import direct_feeds
            for goal in list(self.map.missing(broker)):
                if time.monotonic() - t0 > budget_s + 80:
                    break
                if direct_feeds.has_feed(broker, goal):
                    if direct_feeds.verify_and_record(broker, goal, self.map, timeout_s=70.0):
                        self.stats["routes_learned"] += 1
                        rep["learned"].append(goal)
        except Exception as e:
            print(f"[app_school] direct-feed fallback error: {e!r}"[:140], flush=True)
        rep["goals_remaining"] = self.map.missing(broker)
        rep["coverage"] = self.map.coverage(broker)
        return rep

    @staticmethod
    def _title(pg) -> str:
        try:
            return (pg.title() or "")[:120]
        except Exception:
            return ""

    @staticmethod
    def _url_priority(url: str) -> int:
        """Lower = crawl sooner. Market-DATA pages first, everything else after (junk is dropped
        before this by _enqueue). Keeps the budget on the pages that hold tradeable data."""
        u = (url or "").lower()
        if any(h in u for h in _DATA_URL_HINTS):
            return 0
        return 1

    @staticmethod
    def _enqueue(frontier: list, links, visited_urls: set) -> None:
        """Add same-domain links to the frontier, SKIPPING junk (download/legal/help/marketing)
        so the crawl spends its budget on data pages, not the app-download or careers page."""
        for u, _text in links:
            ul = (u or "").lower()
            if u in visited_urls or u in frontier:
                continue
            if any(j in ul for j in _JUNK_URL_HINTS) and not any(d in ul for d in _DATA_URL_HINTS):
                continue                          # pure-junk link → never crawl it
            frontier.append(u)

    def _collect_links(self, pg, domain) -> list:
        """Every same-domain link on the page → [(abs_url, anchor_text)]. Read-only."""
        from urllib.parse import urljoin, urlparse
        out, seen = [], set()
        try:
            for a in pg.query_selector_all("a[href]")[:300]:
                try:
                    href = a.get_attribute("href") or ""
                    if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
                        continue
                    absu = urljoin(pg.url, href).split("#")[0]
                    net = urlparse(absu).netloc
                    if domain and domain not in net:      # stay on the broker's own site
                        continue
                    if absu in seen:
                        continue
                    seen.add(absu)
                    out.append((absu, (a.inner_text() or "").strip()[:60]))
                except Exception:
                    continue
        except Exception:
            pass
        return out

    def _dismiss_popups(self, pg) -> int:
        """Close any popup / ad / cookie / modal by pressing its X (owner: never get stuck on a
        popup). Read-only-safe: never clicks an order control. Returns how many it closed."""
        from trading.brain.vision.computer_use import _control_forbidden
        closed = 0
        for _ in range(4):                    # a page can stack several (cookie + promo + app-nag)
            hit = False
            for sel in (_POPUP_CLOSE_SEL,):
                try:
                    for el in pg.query_selector_all(sel)[:8]:
                        try:
                            if not el.is_visible():
                                continue
                            txt = (el.inner_text() or el.get_attribute("aria-label") or "")
                            if _control_forbidden(txt):
                                continue
                            el.click(timeout=1200)
                            pg.wait_for_timeout(500)
                            closed += 1
                            hit = True
                            break
                        except Exception:
                            continue
                except Exception:
                    pass
            if not hit:                        # try text-labelled close/consent buttons
                try:
                    for el in pg.query_selector_all("button, [role=button]")[:60]:
                        try:
                            t = " ".join((el.inner_text() or "").split()).lower()
                            # exact ("close"/"skip") OR a consent phrase ("okay, i understand",
                            # "accept all cookies") matched by keyword — never an order control
                            match = t and el.is_visible() and not _control_forbidden(t) and (
                                t in _POPUP_CLOSE_TEXT
                                or (len(t) < 40 and any(k in t for k in
                                    ("understand", "accept", "got it", "no thanks", "not now",
                                     "maybe later", "skip", "dismiss", "allow", "agree"))))
                            if match:
                                el.click(timeout=1200)
                                pg.wait_for_timeout(500)
                                closed += 1
                                hit = True
                                break
                        except Exception:
                            continue
                except Exception:
                    pass
            if not hit:
                break
        if closed:
            self.stats["popups_closed"] = self.stats.get("popups_closed", 0) + closed
        return closed

    def _controls(self, broker: str, pg) -> list[str]:
        """Labelled clickable features on the current page (via the Ocular Cortex frame)."""
        try:
            frame = self.cortex().perceive(broker, "explore", page=pg, url=getattr(pg, "url", ""),
                                           capture_screenshot=False)
            return [c.get("label", "") for c in frame.dom_controls if c.get("label")]
        except Exception:
            return []

    def _rank(self, broker: str, controls: list[str], *, full: bool = False) -> list[str]:
        """Curiosity ranking: controls whose label points at a STILL-MISSING data goal first, then
        other segment/market words, then (when full=True) EVERY other safe control — the owner
        wants 100% coverage, not only segment pages. Order = seek-what-we-need, then explore all."""
        missing = self.map.missing(broker)
        goals = DATA_GOALS.get(broker, {})
        wanted_labels = {w for k in missing for w in goals.get(k, {}).get("labels", [])}
        seen, ranked_hi, ranked_mid, ranked_lo = set(), [], [], []
        from trading.brain.vision.computer_use import _control_forbidden
        for c in controls:
            cl = " ".join(c.split()).lower()
            if not cl or cl in seen or _control_forbidden(cl):
                continue
            seen.add(cl)
            if any(w in cl for w in wanted_labels):
                ranked_hi.append(c)
            elif any(w in cl for w in ("market", "spot", "future", "option", "trade", "screen",
                                       "derivativ", "earn", "chart", "watchlist", "discover")):
                ranked_mid.append(c)
            elif full:                              # explore EVERYTHING else too (read-only)
                ranked_lo.append(c)
        return ranked_hi + ranked_mid + ranked_lo

    def _safe_click(self, pg, label: str) -> bool:
        from trading.brain.vision.computer_use import _control_forbidden, _find_control
        if _control_forbidden(label):
            return False
        el = _find_control(pg, label)
        if el is not None:
            try:
                el.click(timeout=2500)
                return True
            except Exception:
                pass
        # SPA fallback: modern apps (Upstox Pro) build nav from <div>/<span> with click handlers —
        # _find_control only scans button/a/role. Match ANY element by exact visible text, still
        # never an order control (double-guarded). This is what lets the crawl reach every tab/page.
        try:
            from playwright.sync_api import TimeoutError as _PWTimeout  # noqa: F401
        except Exception:
            pass
        try:
            loc = pg.get_by_text(label, exact=True).first
            if loc and loc.count() and not _control_forbidden(label):
                loc.click(timeout=2500)
                return True
        except Exception:
            pass
        return False

    def _seed_sweep(self, broker: str, pg, domain, rep: dict, t0: float, budget_s: float,
                    visited_urls: set, frontier: list, *, full_site: bool = True,
                    per_seed_s: float = 16.0) -> None:
        """Directly visit the SEED_ROUTES data-hub URL for each STILL-MISSING goal and harvest its
        route from the page's OWN traffic. One hub page often serves several goals (a futures trade
        page streams funding + long/short + liquidation + depth), so goals are grouped by URL and
        each page is visited once. Read-only; a route is recorded only when real traffic classifies.
        Bounded: at most (budget_s/3) of the total budget is spent here so the full-site crawl still
        runs afterwards."""
        seeds = SEED_ROUTES.get(broker, {})
        by_url: dict = {}
        for goal in self.map.missing(broker):
            u = seeds.get(goal)
            if u:
                by_url.setdefault(u, []).append(goal)
        if not by_url:
            return
        # give the sweep enough room (it IS the point of a focused learning run): up to 2/3 of budget
        sweep_deadline = t0 + min(budget_s, max(per_seed_s * len(by_url), budget_s * 0.66))
        for url, goals in by_url.items():
            if time.monotonic() > sweep_deadline:
                break
            try:
                pg.goto(url, timeout=25000, wait_until="domcontentloaded")
            except Exception:
                continue
            pg.wait_for_timeout(2500)                       # let websockets / XHR start streaming
            rep["popups_closed"] += self._dismiss_popups(pg)
            # NUDGE lazy data: many hub panels (long/short ratio, liquidation feed, option chain)
            # only fetch when scrolled into view or after a beat — scroll down to trigger them, and
            # click any goal-relevant tab on the page (e.g. "Trading Data", "Option Chain").
            try:
                for _ in range(4):
                    pg.mouse.wheel(0, 1400)
                    pg.wait_for_timeout(1200)
                pg.mouse.wheel(0, -4000)
            except Exception:
                pass
            for goals_labels in (goals,):                   # click a tab matching a missing goal
                for g in goals_labels:
                    for lbl in DATA_GOALS.get(broker, {}).get(g, {}).get("labels", [])[:3]:
                        if self._safe_click(pg, lbl):
                            pg.wait_for_timeout(1500)
                            break
            pg.wait_for_timeout(2500)                       # slower streams fire at least once
            visited_urls.add(url)
            visited_urls.add(pg.url)
            # catalog the hub page + its links (full site map), same as the crawl does
            links = self._collect_links(pg, domain)
            if self.map.record_page(broker, pg.url, title=self._title(pg),
                                    links=[u for u, _ in links],
                                    controls=self._controls(broker, pg)):
                rep["new_pages"] += 1
            rep["new_links"] += self.map.record_links(broker, links)
            if pg.url not in rep["pages_visited"]:
                rep["pages_visited"].append(pg.url)
            # harvest via="home" with a WIDE window → trust this KNOWN hub and attribute every goal
            # whose data kind fired here since we landed (still grounded: no traffic → stays unlearned)
            self._harvest(broker, pg, via="home", rep=rep, max_age_s=60.0)
            # EVENT-DRIVEN goals (liquidation = the @forceOrder ws feed) fire sporadically — DWELL on
            # the page, re-harvesting, until the frame arrives or a short budget elapses. This is what
            # gets liquidation over the line without a lucky first-visit hit.
            dwell_goals = [g for g in goals if g in ("liquidation",) and g in self.map.missing(broker)]
            if dwell_goals:
                dwell_end = min(time.monotonic() + 22.0, sweep_deadline)
                while time.monotonic() < dwell_end and any(g in self.map.missing(broker)
                                                           for g in dwell_goals):
                    pg.wait_for_timeout(2500)
                    self._harvest(broker, pg, via="home", rep=rep, max_age_s=60.0)
            if full_site:
                self._enqueue(frontier, links, visited_urls)
            self.map.save()

    def _harvest(self, broker: str, pg, *, via: str, rep: dict, max_age_s: float = 4.0) -> None:
        """Learn from the app's OWN traffic: which market-data kind was just captured on THIS page
        → record the route (grounded truth, not guessing). The clicked control's label GATES which
        goal a page may satisfy, so clicking 'Options' can never be mislabelled as 'movers'.
        `max_age_s` = how fresh a capture must be to count: tight (4s) for the click-crawl so stale
        traffic isn't mis-attributed; wide for the seed-sweep, which trusts a known data-hub page."""
        rec = self.recorder()
        via_l = " ".join(via.split()).lower()
        for goal, spec in DATA_GOALS.get(broker, {}).items():
            # gate: attribute this goal only if we arrived via home OR a control whose label
            # belongs to this goal's segment (kills the generic-ticker cross-pollution)
            if via != "home" and not any(w in via_l for w in spec.get("labels", [])):
                continue
            for kind in spec["kinds"]:
                if rec.latest(broker, kind, max_age_s=max_age_s) is not None:    # captured recently
                    # window so stale traffic from the previous page isn't mislabelled to this one)
                    pats = rec.registry.find(broker, kind)
                    newly = self.map.record(broker, goal, url=getattr(pg, "url", ""), via=via,
                                            endpoint=pats[0] if pats else "")
                    if newly:
                        self.stats["routes_learned"] += 1
                        rep["learned"].append(goal)
                    if goal not in rep["goals_met"]:
                        rep["goals_met"].append(goal)
                    break

    def status(self) -> dict:
        # mirror the LEARNING written by the explore subprocess / monitor (separate process): re-read
        # the map from disk so the dashboard panel is live-accurate, not frozen at dashboard start.
        self.map.reload()
        self.stats = self.map.stats
        try:                                   # per-symbol feature catalog (chart/depth/indicators…)
            from trading.broker_sense.app_explorer import get_catalog
            features = get_catalog().status()
        except Exception:
            features = {}
        return {"stats": dict(self.stats), "map": self.map.status(),
                "goals": {b: sorted(g) for b, g in
                          {bb: set(gg) for bb, gg in DATA_GOALS.items()}.items()},
                "features": features}


_CCXT_EX: dict = {}                              # segment → cached ccxt exchange (markets warm)


def _min_quote_volume() -> float:
    """Min 24h quote volume (USDT) for a mover to be 'tradeable-liquid' — keeps the shortlist to
    tight-spread symbols the funnel can actually enter. Override with FAST_MOVERS_MIN_VOL."""
    try:
        return float(os.environ.get("FAST_MOVERS_MIN_VOL", "20000000"))   # $20M/24h default
    except ValueError:
        return 20_000_000.0


def _ccxt_exchange(segment: str):
    """Cached ccxt Binance exchange (spot/futures) — the first call loads markets (~10s), every
    later call reuses them (~300ms), so per-cycle screening stays fast and within budget."""
    if segment not in _CCXT_EX:
        import ccxt
        cls = ccxt.binanceusdm if segment == "futures" else ccxt.binance
        _CCXT_EX[segment] = cls({"timeout": 8000, "enableRateLimit": True})
    return _CCXT_EX[segment]


_SCHOOL: AppSchool | None = None


def get_school() -> AppSchool:
    global _SCHOOL
    if _SCHOOL is None:
        _SCHOOL = AppSchool()
    return _SCHOOL
