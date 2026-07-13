"""trading/broker_sense/upstox_feed.py — decode the Upstox web app's protobuf WS frames.

THE MOTTO (2026-07-12): NSE market data must come from navigating the Upstox account
web app. Upstox Pro streams its quotes over a protobuf WebSocket
(wss://market-data.upstox.com/market-data-feeder/…) — interception captures the binary
frames but text classification is blind to them (audit gap E). This module decodes them
with Upstox's OFFICIAL schema (vendor/upstox_proto: MarketDataFeedV3.proto downloaded
from github.com/upstox/upstox-python, compiled with grpc-tools; the older v2 generated
pb2 vendored beside it — the web feeder speaks v2, the docs feed v3, so we try both)
and feeds the doors:

  ltpc                → ui_market ticker (last, prev-close → pct_change)
  marketLevel depth   → ui_market orderbook (5/30-level bid/ask)
  marketOHLC bars     → ui_data candles (per interval: I1→1m, I30→30m, 1d)
  oi / optionGreeks   → ui_market open_interest / option_chain

Honest by construction: proto3 parses garbage into empty messages, so a frame only
counts when it carries at least one plausible value (ltp>0 / a valid bar / depth).
Never raises into the interception hot path.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_PROTO_DIR = Path(__file__).resolve().parents[2] / "vendor" / "upstox_proto"
_MODS: list | None = None

_TF_MAP = {"I1": "1m", "I5": "5m", "I15": "15m", "I30": "30m", "I60": "1h",
           "1d": "1d", "1D": "1d", "d": "1d"}


def _pb_modules() -> list:
    """Lazy-import the vendored generated modules (V3 first, then legacy V2)."""
    global _MODS
    if _MODS is not None:
        return _MODS
    mods = []
    if _PROTO_DIR.is_dir():
        sys.path.insert(0, str(_PROTO_DIR))
        for name in ("MarketDataFeedV3_pb2", "MarketDataFeed_pb2"):
            try:
                mods.append(__import__(name))
            except Exception:
                pass
    _MODS = mods
    return mods


def matches(url: str) -> bool:
    """Is this WS a candidate Upstox market-data feed?"""
    low = (url or "").lower()
    return "market-data-feeder" in low or ("upstox" in low and "feed" in low)


def _parse(raw: bytes):
    """FeedResponse from the first schema that yields non-empty feeds, else None."""
    for pb in _pb_modules():
        try:
            fr = pb.FeedResponse()
            fr.ParseFromString(raw)
            if fr.feeds:
                return fr
        except Exception:
            continue
    return None


def _feed_parts(feed):
    """Normalize the Feed oneof to (ltpc, depth_quotes, ohlc_rows, oi, greeks, iv).
    Handles BOTH schemas: V3 names the full-feed member `fullFeed`, V2 names it `ff`
    (verified against the vendored generated modules — V2 Feed oneof = ltpc|ff|oc)."""
    ltpc = depth = ohlc = greeks = None
    oi = iv = None
    which = None
    try:
        which = feed.WhichOneof("FeedUnion")
    except Exception:
        pass
    if which == "ltpc":
        ltpc = feed.ltpc
    elif which in ("fullFeed", "ff"):
        full = getattr(feed, which)
        ffu = None
        try:
            ffu = full.WhichOneof("FullFeedUnion")
        except Exception:
            pass
        ff = getattr(full, ffu) if ffu else None
        if ff is not None:
            ltpc = getattr(ff, "ltpc", None)
            ml = getattr(ff, "marketLevel", None)
            depth = list(ml.bidAskQuote) if ml is not None else None
            mo = getattr(ff, "marketOHLC", None)
            ohlc = list(mo.ohlc) if mo is not None else None
            oi = getattr(ff, "oi", None)
            iv = getattr(ff, "iv", None)
            greeks = getattr(ff, "optionGreeks", None)
    elif which == "firstLevelWithGreeks":
        fl = feed.firstLevelWithGreeks
        ltpc = getattr(fl, "ltpc", None)
        fd = getattr(fl, "firstDepth", None)
        depth = [fd] if fd is not None else None
        oi = getattr(fl, "oi", None)
        iv = getattr(fl, "iv", None)
        greeks = getattr(fl, "optionGreeks", None)
    return ltpc, depth, ohlc, oi, greeks, iv


def _q(quote, *names) -> float:
    """First non-zero field among V3/V2 spellings (V3: bidP/askP; V2: bp/ap …)."""
    for n in names:
        v = getattr(quote, n, 0)
        if v:
            return float(v)
    return 0.0


def decode_frame(broker: str, url: str, raw: bytes) -> int:
    """Decode one binary frame and feed the doors. Returns records stored (0 = not ours /
    nothing plausible — the caller then falls through to its normal unknown handling)."""
    if not raw or len(raw) > 512_000:
        return 0
    fr = _parse(raw)
    if fr is None:
        _selfheal(broker, url, 0, raw)      # frame arrived but decoded to nothing → maybe drift
        return 0
    from trading.broker_sense import ui_data, ui_market
    stored = 0
    for key, feed in fr.feeds.items():
        try:
            ltpc, depth, ohlc, oi, greeks, iv = _feed_parts(feed)
            if ltpc is not None and getattr(ltpc, "ltp", 0.0) > 0:
                cp = getattr(ltpc, "cp", 0.0)
                pct = round((ltpc.ltp - cp) / cp * 100.0, 4) if cp else None
                stored += ui_market.feed_capture(broker, "ticker", url, {
                    "instrument_key": key, "ltp": ltpc.ltp,
                    "priceChangePercent": pct})
            if depth:
                bids = [{"price": _q(q, "bidP", "bp"), "quantity": _q(q, "bidQ", "bq")}
                        for q in depth if _q(q, "bidP", "bp") > 0]
                asks = [{"price": _q(q, "askP", "ap"), "quantity": _q(q, "askQ", "aq")}
                        for q in depth if _q(q, "askP", "ap") > 0]
                if bids or asks:
                    stored += ui_market.feed_capture(broker, "orderbook", url, {
                        "instrument_key": key, "bids": bids, "asks": asks})
            for bar in (ohlc or []):
                tf = _TF_MAP.get(getattr(bar, "interval", ""), None)
                ts = int(getattr(bar, "ts", 0) or 0)
                if ts and ts < 10**12:
                    ts *= 1000                          # epoch-seconds feed → ms
                if not tf or ts <= 0 or bar.close <= 0 or bar.high < bar.low:
                    continue
                vol = getattr(bar, "vol", 0) or getattr(bar, "volume", 0)  # V3: vol, V2: volume
                if ui_data.feed_ws_kline(broker, url, {
                        "s": key, "k": {"t": ts, "o": bar.open, "h": bar.high,
                                        "l": bar.low, "c": bar.close,
                                        "v": vol, "i": tf}}):
                    stored += 1
            if oi:
                stored += ui_market.feed_capture(broker, "open_interest", url, {
                    "instrument_key": key, "openInterest": oi})
            if greeks is not None and any(getattr(greeks, f, 0.0)
                                          for f in ("delta", "theta", "gamma", "vega")):
                stored += ui_market.feed_capture(broker, "option_chain", url, {
                    "instrument_key": key, "iv": iv,
                    "greeks": {f: getattr(greeks, f, 0.0)
                               for f in ("delta", "theta", "gamma", "vega", "rho")},
                    "ts": time.time()})
        except Exception:
            continue
    _selfheal(broker, url, stored, raw)
    return stored


def _selfheal(broker: str, url: str, stored: int, raw: bytes) -> None:
    """Feed the schema-drift watcher (adopt item 2) — only for real Upstox feed URLs, so a
    non-Upstox binary frame that legitimately decodes to 0 never trips a false drift alert."""
    try:
        if matches(url):
            from trading.broker_sense import feed_selfheal
            feed_selfheal.note(broker, stored=stored, raw=raw)
    except Exception:
        pass
