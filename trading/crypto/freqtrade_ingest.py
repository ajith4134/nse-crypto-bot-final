"""trading/crypto/freqtrade_ingest.py — Freqtrade closed trades → 85-col journal → NN bridge (Phase D).

Freqtrade owns crypto execution; this module pulls its CLOSED trades over REST and records them
into the SAME `TradeJournal` the NSE/live-loop path uses, mapped onto the canonical `ClosedTrade`
schema. Because `TradeOutcomeNet` (`trading.brain.trade_features.get_outcome_net`) trains on the
journal's closed rows, ingesting Freqtrade trades keeps the trade→NN bridge learning from crypto
again after the engine split — no behaviour was lost, just re-sourced.

De-duplicated by `trade_id` (``FT-<id>``) so repeated ingests are idempotent. The journal then
derives charges / quality / behaviour exactly as for any other trade (one schema, one pipeline).
"""
from __future__ import annotations

import time as _time
from datetime import datetime, timezone

from trading.journal.schema import ClosedTrade


def _f(v, default=0.0) -> float:
    try:
        return float(v) if v is not None else float(default)
    except (TypeError, ValueError):
        return float(default)


# ── peak profit/loss WITH timestamps (via 5m candle replay) ─────────────────────────
# Freqtrade tracks max_rate/min_rate but NOT when they occurred. To show the TIME of the
# peak we replay the trade's own 5m candles and read the extreme candle's timestamp; the
# peak USDT amount is recomputed from those same candles so amount and time agree. Cached
# (closed trades are immutable → long TTL; open trades → short TTL since the peak can move).
_PEAK_CACHE: dict = {}        # key -> (expiry_monotonic, dict)
_CCXT: dict = {}              # "spot"/"perp" -> ccxt client


def _peak_client(perp: bool):
    key = "perp" if perp else "spot"
    cli = _CCXT.get(key)
    if cli is None:
        import ccxt
        cli = ccxt.binanceusdm() if perp else ccxt.binance()
        cli.enableRateLimit = True
        _CCXT[key] = cli
    return cli


def _fmt_ms(ms) -> str | None:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None


def _peak_fields(ft: dict, allow_net: bool = True) -> dict:
    """Peak profit/loss in USDT + the time each peak occurred. Falls back to Freqtrade's
    max_rate/min_rate magnitudes (time=None) when candles aren't fetchable. Never raises.

    The magnitude is ALWAYS exact (from Freqtrade's tracked max_rate/min_rate, no network).
    The precise peak *time* needs a per-trade OHLCV fetch (ccxt, rate-limited ~2s each). With
    `allow_net=False` we serve the instant magnitude-only fallback (time=None) instead of making
    that call — closed_view() uses a small per-request network budget so a cold cache can't turn a
    500-trade page into a ~2-minute request (which would stall the dashboard's polling). The cache
    (immutable once closed, 1h TTL) means the times still fill in incrementally across polls."""
    is_short = bool(ft.get("is_short"))
    op = _f(ft.get("open_rate"))
    amt = _f(ft.get("amount"))
    perp = (ft.get("trading_mode") or "spot") != "spot"
    pair = ft.get("pair", "")
    open_ms = ft.get("open_timestamp") or 0
    close_ms = ft.get("close_timestamp") or 0      # 0/None for an open trade

    # max_rate/min_rate fallback amounts (always available, no network)
    max_r, min_r = _f(ft.get("max_rate"), op), _f(ft.get("min_rate"), op)
    if is_short:
        fb_profit, fb_loss = max(0.0, (op - min_r) * amt), max(0.0, (max_r - op) * amt)
    else:
        fb_profit, fb_loss = max(0.0, (max_r - op) * amt), max(0.0, (op - min_r) * amt)
    out = {"peak_profit_usdt": round(fb_profit, 4), "peak_loss_usdt": round(fb_loss, 4),
           "peak_profit_time": None, "peak_loss_time": None}
    if not (pair and amt and op and open_ms):
        return out

    # cache: immutable once closed; short TTL while open
    bucket = close_ms or (int(_time.time()) // 45)
    key = (pair, open_ms, close_ms or "open", round(amt, 8))
    hit = _PEAK_CACHE.get(key)
    now = _time.monotonic()
    if hit and hit[0] > now and (close_ms or hit[2] == bucket):
        return hit[1]
    if not allow_net:
        return out      # instant magnitude-only fallback; leave uncached so a later poll can fill the time

    try:
        cli = _peak_client(perp)
        raw = cli.fetch_ohlcv(pair, "5m", since=int(open_ms), limit=1000)  # [ts,o,h,l,c,v]
        if close_ms:
            raw = [c for c in raw if c[0] <= close_ms]
        if raw:
            hi = max(raw, key=lambda c: c[2])      # highest high
            lo = min(raw, key=lambda c: c[3])      # lowest low
            if is_short:
                profit_usdt = max(0.0, (op - lo[3]) * amt); profit_ts = lo[0]
                loss_usdt = max(0.0, (hi[2] - op) * amt); loss_ts = hi[0]
            else:
                profit_usdt = max(0.0, (hi[2] - op) * amt); profit_ts = hi[0]
                loss_usdt = max(0.0, (op - lo[3]) * amt); loss_ts = lo[0]
            out = {"peak_profit_usdt": round(profit_usdt, 4), "peak_loss_usdt": round(loss_usdt, 4),
                   "peak_profit_time": _fmt_ms(profit_ts), "peak_loss_time": _fmt_ms(loss_ts)}
    except Exception:
        pass  # keep the max_rate/min_rate fallback

    ttl = 3600.0 if close_ms else 45.0
    _PEAK_CACHE[key] = (now + ttl, out, bucket)
    return out


def map_trade(ft: dict) -> ClosedTrade:
    """Map ONE Freqtrade trade dict (from /trades) onto a canonical ClosedTrade."""
    is_short = bool(ft.get("is_short"))
    direction = "SHORT" if is_short else "LONG"
    open_rate = _f(ft.get("open_rate"))
    close_rate = _f(ft.get("close_rate"))
    amount = _f(ft.get("amount"))
    futures = (ft.get("trading_mode") or "spot") != "spot"

    # MFE/MAE in quote currency from Freqtrade's tracked max/min rate (positive magnitudes)
    max_rate, min_rate = _f(ft.get("max_rate"), open_rate), _f(ft.get("min_rate"), open_rate)
    if direction == "LONG":
        mfe = max(0.0, (max_rate - open_rate) * amount)
        mae = max(0.0, (open_rate - min_rate) * amount)
    else:
        mfe = max(0.0, (open_rate - min_rate) * amount)
        mae = max(0.0, (max_rate - open_rate) * amount)

    t = ClosedTrade(
        trade_id=f"FT-{ft.get('trade_id')}",
        symbol=ft.get("pair", ""),
        exchange=(ft.get("exchange") or "binance"),       # → _is_crypto True (crypto path)
        instrument_type=("PERP" if futures else "SPOT"),
        direction=direction,
        product_type=("ISOLATED" if futures else "SPOT"),
        # the brain's chosen library strategy travels in enter_tag; freqtrade's own
        # `strategy` field is always the MlBridgeStrategy shell (not informative)
        strategy_name=ft.get("enter_tag") or ft.get("strategy", "") or "freqtrade",
        setup_type=ft.get("exit_reason", "") or "",
        market_session="LIVE",
        broker_used=(ft.get("exchange") or "binance"),
        entry_datetime=ft.get("open_date", "") or "",
        exit_datetime=ft.get("close_date", "") or "",
        quantity=amount,
        entry_price=open_rate,
        exit_price=close_rate,
        entry_order_type="MARKET", exit_order_type="MARKET",
        # P&L context — journal recomputes gross from prices + crypto charges; we carry the
        # crypto-specific funding so the charge model is honest, plus Freqtrade's realized net.
        funding_pnl=_f(ft.get("funding_fees")),
        # risk & sizing
        margin_used=_f(ft.get("stake_amount")) or None,
        leverage=_f(ft.get("leverage"), 1.0) or 1.0,
        margin_mode=("ISOLATED" if futures else ""),
        initial_sl_price=(_f(ft.get("initial_stop_loss_abs")) or None),
        # quality (currency-denominated excursions; journal derives pct/efficiency/R)
        mfe=round(mfe, 6), mae=round(mae, 6),
    )
    return t


def map_open_trade(ft: dict) -> dict:
    """Map a Freqtrade OPEN trade → display row with capital/P&L/peak (MFE/MAE) in USDT."""
    is_short = bool(ft.get("is_short"))
    direction = "SHORT" if is_short else "LONG"
    op = _f(ft.get("open_rate")); cur = _f(ft.get("current_rate"), op)
    amt = _f(ft.get("amount")); lev = _f(ft.get("leverage"), 1.0) or 1.0
    stake = _f(ft.get("stake_amount"))             # capital placed (margin, USDT)
    peaks = _peak_fields(ft)                        # peak profit/loss USDT + their times
    return {
        "trade_id": f"FT-{ft.get('trade_id')}", "symbol": ft.get("pair", ""),
        "direction": direction, "exchange": ft.get("exchange", "binance"),
        "instrument_type": ("PERP" if (ft.get("trading_mode") or "spot") != "spot" else "SPOT"),
        "leverage": lev, "quantity": amt,
        "entry_price": op, "current_price": cur,
        "capital_usdt": round(stake, 2),                       # capital placed (USDT)
        "notional_usdt": round(amt * op, 2),                   # full position value
        "unrealized_pnl_usdt": round(_f(ft.get("profit_abs")), 4),
        "unrealized_pnl_pct": round(_f(ft.get("profit_ratio")) * 100.0, 3),
        "peak_profit_usdt": peaks["peak_profit_usdt"],         # MFE (USDT)
        "peak_profit_time": peaks["peak_profit_time"],         # when MFE occurred
        "peak_loss_usdt": peaks["peak_loss_usdt"],             # MAE (USDT)
        "peak_loss_time": peaks["peak_loss_time"],             # when MAE occurred
        "funding_usdt": round(_f(ft.get("funding_fees")), 4),
        "entry_datetime": ft.get("open_date", ""),
        "strategy": ft.get("strategy", ""), "enter_tag": ft.get("enter_tag", ""),
        "stop_loss": _f(ft.get("stop_loss_abs")) or None,
    }


def closed_view(client=None, net_budget: int = 8) -> list[dict]:
    """All CLOSED Freqtrade trades as full journal rows ENRICHED with peak profit/loss (USDT)
    and the time each peak occurred. [] on failure.

    `net_budget` caps how many UNCACHED peak-time OHLCV fetches (~2s each, ccxt rate-limited) this
    call may make, so a cold cache over hundreds of trades can't turn one request into a multi-minute
    stall. Cached trades are always served for free; the precise peak *times* for the rest fill in a
    few per poll (magnitudes are exact immediately). Newest trades are enriched first."""
    if client is None:
        from trading.crypto.engine_client import CryptoEngineClient
        client = CryptoEngineClient()
    try:
        fts = client.closed_trades()
    except Exception:
        return []
    # Newest-first so the most-recently-closed trades get the live OHLCV peak-time enrichment first.
    fts = [ft for ft in fts if isinstance(ft, dict)]
    order = sorted(range(len(fts)), key=lambda i: fts[i].get("close_timestamp") or 0, reverse=True)
    rows: list = [None] * len(fts)
    spent = 0
    for i in order:
        ft = fts[i]
        before = len(_PEAK_CACHE)
        peaks = _peak_fields(ft, allow_net=(spent < net_budget))
        if len(_PEAK_CACHE) > before:              # a network fetch happened (new cache entry)
            spent += 1
        row = map_trade(ft).to_dict()
        row.update(peaks)                          # peak_profit_usdt/_time, peak_loss_usdt/_time
        rows[i] = row
    return rows


def open_trades_view(client=None) -> list[dict]:
    """All OPEN Freqtrade trades as display rows (capital/P&L/peak in USDT). [] on failure."""
    if client is None:
        from trading.crypto.engine_client import CryptoEngineClient
        client = CryptoEngineClient()
    try:
        st = client.status()
        rows = st if isinstance(st, list) else st.get("data", [])
        return [map_open_trade(t) for t in rows if isinstance(t, dict)]
    except Exception:
        return []


# ── FIXED column schemas (single source of truth) ──────────────────────────────
# Derived from the mappers/schema themselves so they can NEVER drift from the rows.
# Returned by /api/trading/crypto/trades so the dashboard renders a STABLE column set
# (same contract as the dark dashboard's OPEN_TRADE_COLUMNS) — the column count no longer
# fluctuates as trades open/close.
from dataclasses import fields as _dc_fields  # noqa: E402

OPEN_VIEW_COLUMNS = list(map_open_trade({}).keys())            # 22 fixed open-trade columns
CLOSED_VIEW_COLUMNS = (
    [f.name for f in _dc_fields(ClosedTrade)]                  # full 110-col journal schema
    + ["peak_profit_usdt", "peak_profit_time", "peak_loss_usdt", "peak_loss_time"]  # MFE/MAE enrich
)


def ingest_closed(journal, client=None) -> dict:
    """Record any NEW Freqtrade closed trades into `journal` (idempotent by trade_id).

    Returns {"ingested", "skipped", "seen"}. Best-effort — never raises into a caller loop.
    """
    if client is None:
        from trading.crypto.engine_client import CryptoEngineClient
        client = CryptoEngineClient()
    try:
        ft_trades = client.closed_trades()
    except Exception:
        return {"ingested": 0, "skipped": 0, "seen": 0, "error": "freqtrade unreachable"}

    existing = {t.trade_id for t in journal.trades}
    ingested = skipped = 0
    for ft in ft_trades:
        tid = f"FT-{ft.get('trade_id')}"
        if tid in existing:
            skipped += 1
            continue
        try:
            journal.record(map_trade(ft))     # derives charges/quality → feeds TradeOutcomeNet
            ingested += 1
        except Exception:
            skipped += 1
    return {"ingested": ingested, "skipped": skipped, "seen": len(ft_trades)}
