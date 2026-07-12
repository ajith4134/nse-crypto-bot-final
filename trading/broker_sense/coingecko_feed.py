"""trading/broker_sense/coingecko_feed.py — the BULK multi-bar candle door (owner 2026-07-12).

Binance's web exposes only ~1 bar/symbol in bulk (get-product-dynamic). CoinGecko is the only
web source that returns a MULTI-BAR series for MANY coins in ONE request: coins/markets?sparkline
=true → each coin carries `sparkline_in_7d.price` = 168 HOURLY points, up to 250 coins/page. One
web visit → hundreds of symbols' hourly price series.

Motto framing: CoinGecko is a third-party DATA aggregator, NOT the owner's Binance/Upstox account,
so this is data-source *diversification* for BREADTH — execution stays Binance, and the fine 5m
entry candles stay on the account's parked tabs. It IS web (fetched from inside the brain's browser
page, using the browser's own origin — not a keyed server API), free, and login-free.

  refresh(sessions) — navigate CoinGecko in the brain's browser, fetch N pages of coins/markets,
                      convert each 168-pt hourly sparkline into 1h OHLC candles, and feed them into
                      ui_data keyed by the Binance symbol spelling (btc → BTCUSDT). fast_candles /
                      indicator_fusion then get a broad HOURLY direction + regime read across the
                      whole market, so the brain knows WHERE to point its Binance 5m eyes.

Owner-thread only (Playwright is thread-bound). Sparkline updates every ~6h, so refresh on a slow
cadence. Best-effort; never raises into the loop. Kill switch: COINGECKO_FEED=0.
"""
from __future__ import annotations

import os
import time

from trading import state

_STATUS_FILE = "coingecko_feed.json"
_API = "https://api.coingecko.com/api/v3/coins/markets"


def enabled() -> bool:
    return os.getenv("COINGECKO_FEED", "1").strip().lower() not in ("0", "false", "off")


def _pages() -> int:
    try:
        return max(1, int(os.getenv("COINGECKO_PAGES", "2")))     # 2×250 = 500 coins
    except ValueError:
        return 2


def _sym_to_binance(sym: str) -> str:
    """CoinGecko symbol (btc, eth) → the Binance USDT spelling the doors index by. Best-effort;
    ui_data resolves the /:USDT variants itself."""
    s = (sym or "").upper().strip()
    return f"{s}USDT" if s and not s.endswith(("USDT", "USDC", "USD")) else s


def _sparkline_to_1h_rows(prices: list) -> list | None:
    """168 hourly close points → [[ts,o,h,l,c,v], …] synthetic 1h OHLC (no intra-hour H/L in a
    sparkline, so H/L bracket the open→close — enough for an EMA/momentum direction read). Newest
    last; rejects nonsense so ui_data's validator accepts it."""
    try:
        p = [float(x) for x in prices if x is not None]
    except (TypeError, ValueError):
        return None
    if len(p) < 20:
        return None
    now_ms = int(time.time() * 1000)
    step = 3_600_000
    rows = []
    for i in range(1, len(p)):
        o, c = p[i - 1], p[i]
        if c <= 0 or o <= 0:
            continue
        ts = now_ms - (len(p) - 1 - i) * step
        rows.append([ts, o, max(o, c), min(o, c), c, 0.0])
    return rows if len(rows) >= 15 else None


def refresh(sessions, *, broker: str = "binance", deadline: float | None = None) -> dict:
    """Fetch CoinGecko bulk sparklines via the brain's browser and feed them into ui_data as 1h
    candles. Returns an honest report. Owner-thread only; never raises."""
    rep = {"fed": 0, "pages": 0, "errors": []}
    if not enabled():
        rep["errors"].append("disabled (COINGECKO_FEED=0)")
        return rep
    # Open a RAW page in the broker's browser context — NOT sessions.page(), which runs the
    # broker LOGIN flow (it mis-detected coingecko.com's search box as a login form and hung on
    # fill(), 2026-07-12). CoinGecko needs no login; we just need the browser's origin to fetch.
    pg = None
    try:
        if not sessions._own_thread():
            rep["errors"].append("not owner thread")
            return rep
        ctx = sessions.context(broker)
        pg = ctx.new_page()
        try:
            pg.goto("https://www.coingecko.com/", timeout=20000, wait_until="domcontentloaded")
        except Exception:
            pass                                       # a partial load is fine — we fetch via JS
    except Exception as e:
        rep["errors"].append(f"page: {type(e).__name__}: {str(e)[:60]}")
        if pg is not None:
            try:
                pg.close()
            except Exception:
                pass
        return rep
    from trading.broker_sense import ui_data
    try:
        for page_n in range(1, _pages() + 1):
            if deadline is not None and time.monotonic() > deadline:
                break
            url = (f"{_API}?vs_currency=usd&order=market_cap_desc&per_page=250"
                   f"&page={page_n}&sparkline=true")
            try:
                # fetch from INSIDE the browser page (its origin, not a keyed server call)
                data = pg.evaluate(
                    "async (u) => { try { const r = await fetch(u); if(!r.ok) return null;"
                    " return await r.json(); } catch(e){ return null; } }", url)
            except Exception as e:
                rep["errors"].append(f"p{page_n}: {type(e).__name__}: {str(e)[:50]}")
                continue
            if not isinstance(data, list):
                rep["errors"].append(f"p{page_n}: no data")
                continue
            rep["pages"] += 1
            for coin in data:
                try:
                    spark = ((coin.get("sparkline_in_7d") or {}).get("price")) or []
                    rows = _sparkline_to_1h_rows(spark)
                    if not rows:
                        continue
                    sym = _sym_to_binance(coin.get("symbol") or "")
                    if not sym:
                        continue
                    # synthetic capture URL carrying the symbol + interval so ui_data.feed_capture
                    # extracts them (it reads ?symbol= / ?interval=); ui_data resolves /:USDT itself
                    fake_url = f"https://coingecko/klines?symbol={sym}&interval=1h"
                    if ui_data.feed_capture(broker, fake_url, rows):
                        rep["fed"] += 1
                except Exception:
                    continue
        state.update_json(_STATUS_FILE, {"ts": time.time(), "fed": rep["fed"],
                                         "pages": rep["pages"], "errors": rep["errors"][-3:]})
    except Exception as e:
        rep["errors"].append(f"{type(e).__name__}: {str(e)[:80]}")
    finally:
        try:
            pg.close()                                 # it's a scratch tab — never leave it open
        except Exception:
            pass
    return rep


def status() -> dict:
    return state.load_json(_STATUS_FILE, {})
