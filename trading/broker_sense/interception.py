"""trading/broker_sense/interception.py — the brain's peripheral nerve: capture the broker
app's OWN internal API traffic as it navigates, so it reads the exact numbers the app itself
renders (no DOM scraping, no pixel-guessing) and remembers WHERE each data kind comes from.

Two pieces:

  EndpointRegistry — persisted per-broker map of internal API endpoints the app calls
                     (URL pattern → data kind → freshness → n_seen). This is the "golden
                     path" the Ocular Cortex recalls: once we've seen that Binance depth
                     lives at fapi/v1/depth, we know to read there next time.

  NetworkRecorder  — attaches page.on("response") to a live Playwright page; every internal
                     JSON response is classified, recorded to the registry, and its latest
                     body cached in-memory per (broker, kind) so a read is FREE (the app
                     already fetched it — we just keep the answer).

Pure-Python + offline-testable: Playwright is only touched inside attach(); the registry and
classification are plain functions with no browser dependency. Read-only by construction — we
observe responses, we never issue requests or actions."""
from __future__ import annotations

import time
from urllib.parse import urlsplit

from trading import state

_REGISTRY_FILE = "broker_endpoints.json"
_MAX_BODY_BYTES = 400_000          # skip huge payloads (charts blobs) — we want JSON data
_CACHE_TTL_S = 90.0                # a cached body older than this is stale for a live read

# URL/keyword → data kind. Ordered: first hit wins. Kept honest — anything unmatched is
# "unknown" (recorded, but never claimed to be something it isn't).
_KIND_RULES = [
    # ACCOUNT paths first (2026-07-10): Upstox's portfolio/v4/orderbook = the user's ORDER
    # HISTORY, not market depth — the "orderbook" needle stole it and recorded a FALSE
    # market-depth route. Anything under an account-ish path prefix is positions/balance.
    ("positions", ("portfolio/", "/holdings", "portfolio-insights", "portfolio-streamer")),
    ("balance", ("funds/", "jfunds/", "payin/", "payout/")),
    ("orderbook", ("depth", "orderbook", "order-book", "marketdepth", "book?")),
    # index/mark price + basis MUST precede "candles" (their *Klines* variants contain "klines")
    # and precede "funding"/"ticker" so they classify distinctly. Binance web fires
    # fapi/v1/markPriceKlines, fapi/v1/indexPriceKlines, .../future/data/basis (verified live).
    ("mark_price", ("markprice", "mark-price", "markpriceklines", "premiumindexklines")),
    ("index_price", ("indexprice", "index-price", "indexpriceklines", "spotindexprice",
                     "constituents")),
    ("basis", ("future/data/basis", "/basis?", "futures/basis", "basisdata")),
    ("candles", ("kline", "klines", "candle", "ohlc", "history?resolution", "/tvc/", "udf/history")),
    # recent executed trades tape — Binance: fapi/v1/aggTrades, api/v3/trades, .../historicalTrades.
    # BEFORE the generic "ticker" rule; "trades" is specific enough not to collide with the rules above.
    ("recent_trades", ("aggtrades", "aggtrade", "recenttrades", "recent-trades", "historicaltrades",
                       "markettrades", "/trades?", "/trades/", "tradehistory", "matches?")),
    # instrument/contract metadata (tick size, lot size, filters) — Binance: fapi/v1/exchangeInfo,
    # api/v3/exchangeInfo, bapi/.../symbolConfig. Placed before "ticker" so it isn't mislabelled.
    ("symbol_info", ("exchangeinfo", "exchange-info", "symbolconfig", "contractinfo",
                     "instruments?", "instrument/", "symbols?", "/products")),
    # option chain — Binance web fires bapi/eoptions/v1/public/eoptions/market/* (verified live
    # 2026-07-06); "eoptions" must be here BEFORE the ticker rule so market/ticker isn't mislabelled.
    ("option_chain", ("option-chain", "optionchain", "opt-chain", "greeks", "option_chain",
                      "eoptions")),
    ("funding", ("funding", "premiumindex", "premium-index")),
    # taker buy/sell volume — Binance: .../future/data/taker-long-short-ratio (verified live). MUST
    # come BEFORE long_short: that URL also contains "long-short", so long_short would steal it.
    ("taker_volume", ("taker-long-short", "takerlongshort", "taker-buy-sell", "takerbuysell",
                      "taker-volume", "takervolume")),
    ("open_interest", ("openinterest", "open-interest", "oi-spurts", "open-interest-stats")),
    ("long_short", ("longshort", "long-short", "globallongshort", "topltsaccount")),
    ("liquidation", ("liquidation", "forceorder", "allforceorders", "forceorder@arr")),
    # margin BORROW/interest data (leverage sentiment) — Binance: bapi/margin/v1/friendly/margin/
    # interest-rate, .../isolated-margin/interest-rate, .../margin/pair (verified live). Placed
    # BEFORE the generic 'balance' rule (which also contains "margin") so it classifies distinctly.
    ("margin", ("friendly/margin", "friendly/isolated-margin", "margin/interest-rate",
                "isolated-margin/interest-rate", "margin/pair", "margin/max-leverage")),
    ("movers", ("gainers", "losers", "topmovers", "top-movers", "movers", "mostactive",
                "most-active", "spurts")),
    ("screener", ("screener", "scanner", "screen", "filter?")),
    # "market-data-feeder" = Upstox Pro's live quote websocket (wss://market-data.upstox.com/
    # market-data-feeder/v2/feeds — protobuf frames, classified by URL; verified live 2026-07-10)
    ("ticker", ("ticker", "quote", "snapquote", "ltp", "24hr", "marketdata",
                "market-data-feeder")),
    ("positions", ("positions", "holdings", "portfolio", "position?")),
    ("balance", ("balance", "funds", "margin", "wallet", "account")),
    ("news", ("news", "announcement", "feed")),
]


def _url_pattern(url: str) -> str:
    """Normalize a URL to a stable pattern: drop the query string and collapse numeric /
    hash-like path segments to {v}, so /api/depth?symbol=BTC and /api/depth?symbol=ETH map to
    one endpoint key (host + templated path)."""
    try:
        u = urlsplit(url)
    except Exception:
        return url[:200]
    segs = []
    for s in u.path.split("/"):
        if not s:
            continue
        # numeric id, or long hex/hash token → template placeholder
        if s.isdigit() or (len(s) >= 12 and all(c in "0123456789abcdefABCDEF-" for c in s)):
            segs.append("{v}")
        else:
            segs.append(s)
    return f"{u.netloc}/{'/'.join(segs)}"


def classify(url: str, body=None) -> str:
    """Best-effort data-kind for an endpoint from its URL (+ optional parsed body shape)."""
    low = url.lower()
    for kind, needles in _KIND_RULES:
        if any(n in low for n in needles):
            return kind
    # shape hints when the URL is opaque
    if isinstance(body, dict):
        keys = {k.lower() for k in body.keys()}
        if {"bids", "asks"} & keys:
            return "orderbook"
        if {"markprice", "mark_price"} & keys:
            return "mark_price"
        if {"indexprice", "index_price"} & keys:
            return "index_price"
        if {"symbols", "instruments", "contracts"} & keys:
            return "symbol_info"
        if {"lastprice", "last_price", "ltp"} & keys:
            return "ticker"
        flat = " ".join(keys)
        # option-chain shape: strikes + call/put (CE/PE) legs — Indian brokers (Upstox Pro:
        # service.upstox.com/…, URL opaque) nest it as {strikePrice, callOption, putOption}
        # or {strikes: [...]}; the STRIKE+CE/PE pairing is distinctive (2026-07-10 fix —
        # Upstox routes never classified, App School stuck at 10%).
        if "strike" in flat and ({"ce", "pe"} & keys or "call" in flat or "put" in flat):
            return "option_chain"
    # many Indian-broker payloads wrap the rows: {"data": [...]} / {"data": {...}}
    rows = body
    if isinstance(body, dict):
        inner = body.get("data")
        if isinstance(inner, (list, dict)):
            rows = inner
            if isinstance(inner, dict):
                ik = {k.lower() for k in inner.keys()}
                iflat = " ".join(ik)
                if {"bids", "asks"} & ik:
                    return "orderbook"
                if "strike" in iflat and ({"ce", "pe"} & ik or "call" in iflat
                                          or "put" in iflat):
                    return "option_chain"
                if {"lastprice", "last_price", "ltp"} & ik:
                    return "ticker"
    if isinstance(rows, list) and rows and isinstance(rows[0], (list, dict)):
        if isinstance(rows[0], list):
            return "candles"
        k0 = {k.lower() for k in rows[0].keys()}
        # list of trade dicts: {price, qty, time} / Binance aggTrade {p, q, T, m}
        if ({"price", "qty"} <= k0) or ({"p", "q"} <= k0 and ("t" in k0 or "m" in k0)):
            return "recent_trades"
        f0 = " ".join(k0)
        if "strike" in f0 and ({"ce", "pe"} & k0 or "call" in f0 or "put" in f0):
            return "option_chain"
        # quote rows: an instrument name + a last price / %change — the generic "ticker"
        # kind, which grounds movers/spot_symbols/futures/currency/commodities goals too
        if ({"symbol", "tradingsymbol", "trading_symbol", "scripname", "instrumentkey",
             "instrument_key", "isin"} & k0) and (
                {"ltp", "lastprice", "last_price", "close"} & k0
                or "change" in f0 or "chg" in f0):
            return "ticker"
        return "unknown"
    return "unknown"


def _sample_keys(body) -> list[str]:
    if isinstance(body, dict):
        return sorted(body.keys())[:20]
    if isinstance(body, list) and body and isinstance(body[0], dict):
        return sorted(body[0].keys())[:20]
    return []


class EndpointRegistry:
    """Persisted per-broker endpoint knowledge. broker → pattern → metadata."""

    _AUTOSAVE_EVERY = 25          # records between saves (throttle; file is small)
    _AUTOSAVE_MAX_S = 60.0        # …or at most this long between saves

    def __init__(self):
        self._data: dict = state.load_json(_REGISTRY_FILE, {})
        self._unsaved = 0
        self._last_save = 0.0

    def record(self, broker: str, url: str, *, method: str = "GET",
               content_type: str = "", body=None) -> str:
        pat = _url_pattern(url)
        kind = classify(url, body)
        b = self._data.setdefault(broker, {})
        row = b.get(pat)
        now = time.time()
        if row is None:
            row = {"kind": kind, "method": method, "content_type": content_type,
                   "sample_keys": _sample_keys(body), "n_seen": 0,
                   "first_seen": now, "last_seen": now}
            b[pat] = row
        row["n_seen"] += 1
        row["last_seen"] = now
        if kind != "unknown":                 # upgrade a previously-unknown classification
            row["kind"] = kind
        if body is not None and not row.get("sample_keys"):
            row["sample_keys"] = _sample_keys(body)
        # THROTTLED AUTOSAVE (2026-07-10): nothing ever called flush(), so the registry —
        # the ground truth of every URL an app really emits (incl. 'unknown' ones with
        # sample keys, the source for future classifier needles) — evaporated with every
        # restart and broker_endpoints.json never existed on disk.
        self._unsaved += 1
        if self._unsaved >= self._AUTOSAVE_EVERY or now - self._last_save > self._AUTOSAVE_MAX_S:
            try:
                self.save()
                self._unsaved, self._last_save = 0, now
            except Exception:
                pass
        return kind

    def known(self, broker: str) -> dict:
        return dict(self._data.get(broker, {}))

    def find(self, broker: str, kind: str) -> list[str]:
        """URL patterns for a data kind on a broker, most-seen first (the reliable one)."""
        rows = self._data.get(broker, {})
        hits = [(p, r) for p, r in rows.items() if r.get("kind") == kind]
        hits.sort(key=lambda pr: pr[1].get("n_seen", 0), reverse=True)
        return [p for p, _ in hits]

    def save(self) -> None:
        state.save_json(_REGISTRY_FILE, self._data)

    def status(self) -> dict:
        return {b: {"endpoints": len(rows),
                    "kinds": sorted({r.get("kind") for r in rows.values()})}
                for b, rows in self._data.items()}


class NetworkRecorder:
    """Attaches to Playwright pages and keeps the freshest internal JSON per (broker, kind).

    The registry persists WHERE data lives; the live cache holds WHAT was last seen there,
    so the funnel can read app-computed values for free (the browser already paid for them)."""

    def __init__(self, registry: EndpointRegistry | None = None):
        self.registry = registry or EndpointRegistry()
        self._cache: dict[tuple[str, str], dict] = {}     # (broker, kind) → {body, ts, url}
        self.captured = 0

    def attach(self, page, broker: str) -> None:
        """Hook response + websocket capture onto a live page. Best-effort; never raises."""
        def _on_response(resp):
            try:
                self._handle(resp, broker)
            except Exception:
                pass
        try:
            page.on("response", _on_response)
        except Exception:
            pass
        # WEBSOCKET capture — some feeds are streamed ONLY over ws (e.g. Binance futures liquidations
        # !forceOrder@arr, depth, mark-price), never as a REST response. Classify each frame by its
        # ws URL first, then by the frame payload (combined streams carry the event type in the body,
        # e.g. {"e":"forceOrder",...}), and cache it so the school can learn that route. Throttled:
        # one capture per (broker, kind) per _WS_THROTTLE_S so high-rate frames don't burn CPU.
        def _on_ws(ws):
            def _on_frame(payload):
                try:
                    self._handle_ws(ws.url, payload, broker)
                except Exception:
                    pass
            try:
                ws.on("framereceived", _on_frame)
            except Exception:
                pass
        try:
            page.on("websocket", _on_ws)
        except Exception:
            pass

    _WS_THROTTLE_S = 3.0

    def _handle_ws(self, url: str, payload, broker: str) -> None:
        snippet = (payload if isinstance(payload, str) else str(payload))[:400]
        # classify the FRAME first: a combined ws stream (one URL) carries many event types, and the
        # specific one is in the payload (e.g. {"e":"forceOrder"} → liquidation). URL is the fallback.
        kind = classify(snippet)
        if kind == "unknown":
            kind = classify(url)
        if kind == "unknown":
            # STILL record the ws URL (2026-07-10): binary/protobuf streams (Upstox Pro
            # market data) never classify from payload text, and skipping them here left
            # the registry blind to the very URLs we need to write needles for. Throttled
            # by the same per-(broker,kind) window via a dedicated marker key.
            prev = self._cache.get((broker, "_ws_unknown"))
            if not prev or time.time() - prev["ts"] >= self._WS_THROTTLE_S:
                self.registry.record(broker, url, method="WS", content_type="ws",
                                     body=None)
                self._cache[(broker, "_ws_unknown")] = {"body": None, "ts": time.time(),
                                                        "url": url}
            return
        prev = self._cache.get((broker, kind))
        if prev and time.time() - prev["ts"] < self._WS_THROTTLE_S:
            return                            # already have a fresh capture — skip (rate-limit)
        body = {"ws": True, "frame": snippet}
        try:
            import json as _json
            if snippet[:1] in "{[":
                body = _json.loads((payload if isinstance(payload, str) else snippet))
        except Exception:
            pass
        self.registry.record(broker, url, method="WS", content_type="ws", body=None)
        self._cache[(broker, kind)] = {"body": body, "ts": time.time(), "url": url}
        self.captured += 1

    def _handle(self, resp, broker: str) -> None:
        url = resp.url
        ct = ""
        try:
            ct = (resp.headers or {}).get("content-type", "")
        except Exception:
            pass
        low_ct = ct.lower()
        is_jsonish = "json" in low_ct or ("/api" in url.lower() and "html" not in low_ct)
        if not is_jsonish:
            return
        body = None
        try:                                   # enforce the size cap on the ACTUAL bytes, so a
            raw = resp.body()                  # chunked response with no content-length header
            if raw and len(raw) <= _MAX_BODY_BYTES:   # can't sneak a multi-MB payload past us
                import json as _json
                body = _json.loads(raw)
        except Exception:
            body = None
        method = "GET"
        try:
            method = resp.request.method
        except Exception:
            pass
        kind = self.registry.record(broker, url, method=method, content_type=ct, body=body)
        self.captured += 1
        if body is not None and kind != "unknown":
            self._cache[(broker, kind)] = {"body": body, "ts": time.time(), "url": url}
            if self.captured % 25 == 0:            # cheap periodic cross-process snapshot
                self._persist_freshness()
            if kind == "candles":
                # UI-ONLY DATA (owner 2026-07-07): index the app's own kline payloads by
                # (symbol, tf) so the funnel can trade on what the EYES see — no polling.
                try:
                    from trading.broker_sense import ui_data
                    ui_data.feed_capture(broker, url, body)
                except Exception:
                    pass

    def latest(self, broker: str, kind: str, *, max_age_s: float = _CACHE_TTL_S):
        """Freshest captured body for (broker, kind), or None if absent/stale."""
        row = self._cache.get((broker, kind))
        if row is None:
            return None
        if time.time() - row["ts"] > max_age_s:
            return None
        return row["body"]

    def flush(self) -> None:
        self.registry.save()

    def status(self) -> dict:
        fresh = {f"{b}:{k}": round(time.time() - v["ts"], 1)
                 for (b, k), v in self._cache.items()}
        out = {"captured": self.captured, "live_kinds": fresh,
               "registry": self.registry.status()}
        # cross-process freshness snapshot (owner #10 health check runs in another
        # process and can't see this RAM cache) — persist per (broker, kind) ts.
        try:
            from trading import state
            snap = {f"{b}|{k}": v["ts"] for (b, k), v in self._cache.items()}
            if snap:
                state.save_json("interception_freshness.json",
                                {"ts": time.time(), "kinds": snap})
        except Exception:
            pass
        return out

    def _persist_freshness(self) -> None:
        """Called from the capture path so a cross-process reader (ui_health) sees fresh
        eyes even when status() isn't polled."""
        try:
            from trading import state
            snap = {f"{b}|{k}": v["ts"] for (b, k), v in self._cache.items()}
            if snap:
                state.save_json("interception_freshness.json",
                                {"ts": time.time(), "kinds": snap})
        except Exception:
            pass


_RECORDER: NetworkRecorder | None = None


def get_recorder() -> NetworkRecorder:
    global _RECORDER
    if _RECORDER is None:
        _RECORDER = NetworkRecorder()
    return _RECORDER
