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


_LEARN_SEEN_FILE = "close_learn_seen.json"   # trade ids whose close-time learning already ran
_LEARN_SEEN: list | None = None              # per-process cache (insertion order, for trimming)
_LEARN_SEEN_SET: set = set()                 # O(1) membership twin (closed_view maps 100s/poll)


def _learn_from_close(ft: dict, t) -> None:
    """ONE-SHOT close-time learning, idempotent by Freqtrade trade id.

    map_trade() runs on EVERY dashboard poll via closed_view() (SWR refresh), not only on
    journal ingest — so learning side-effects placed inline there re-credited the same
    closed trade on every poll. That silently inflated the picker-fusion sample counts
    (FeaturePerf.record has no dedupe) and would corrupt the champion bandit's Beta
    posteriors the same way. This guard makes close-time learning fire exactly once per
    trade regardless of which caller maps it first. (Each process keeps its own cache of
    the shared seen-file, so a cross-process race can at worst double-credit one trade
    once — bounded, and vastly better than once per poll.)

    Learns two things per closed trade:
      • picker stacking credit (#3 broker-features): every built-in picker whose latest
        snapshot listed the symbol gets the win/loss.
      • champion-bandit posterior (invent-beyond #3): the library strategy the entry was
        attributed to (enter_tag) gets a win/loss in the CURRENT regime bucket — the
        allocation itself learns which champion works in which regime.
    """
    global _LEARN_SEEN, _LEARN_SEEN_SET
    tid = ft.get("trade_id")
    if tid is None:
        return
    key = f"FT-{tid}"
    from trading import state
    if _LEARN_SEEN is None:
        _LEARN_SEEN = list(state.load_json(_LEARN_SEEN_FILE, {}).get("ids", []))
        _LEARN_SEEN_SET = set(_LEARN_SEEN)
    if key in _LEARN_SEEN_SET:
        return
    win = _f(t.net_pnl) > 0
    try:
        from trading.broker_sense import broker_features as _bf
        _bf.credit_symbol("binance", ft.get("pair", ""), win=win, pnl=_f(t.net_pnl))
    except Exception:
        pass
    try:
        from trading.strategy import champion_bandit as _cb
        _cb.update("crypto", str(t.strategy_name or ""), win=win)
    except Exception:
        pass
    _LEARN_SEEN.append(key)                       # insertion order → trim drops OLDEST first
    _LEARN_SEEN = _LEARN_SEEN[-8000:]
    _LEARN_SEEN_SET = set(_LEARN_SEEN)
    state.save_json(_LEARN_SEEN_FILE, {"ids": _LEARN_SEEN})


def _f(v, default=0.0) -> float:
    try:
        return float(v) if v is not None else float(default)
    except (TypeError, ValueError):
        return float(default)


_CTX_CACHE: dict = {}                    # (pair, seg) -> (ts, context)  — 60s TTL, ban-safe


def _broker_context(pair: str, seg: str) -> dict:
    """The broker's OWN market-context fields for `pair` (App-School-discovered columns:
    mark/index price, funding interval, 24h high/low/turnover). Read the fast API ticker +
    funding rate (ccxt, cached 60s). Best-effort — empty dict on any miss, never blocks ingest."""
    key = (pair, seg)
    hit = _CTX_CACHE.get(key)
    if hit and _time.time() - hit[0] < 60:
        return hit[1]
    ctx: dict = {}
    try:
        from trading.broker_sense.app_school import _ccxt_exchange
        ex = _ccxt_exchange("futures" if seg in ("futures", "prediction") else "spot")
        t = ex.fetch_ticker(pair)
        if t:
            ctx["high_24h_entry"] = _f(t.get("high")) or None
            ctx["low_24h_entry"] = _f(t.get("low")) or None
            ctx["turnover_24h_entry"] = _f(t.get("quoteVolume")) or None
            info = t.get("info") or {}
            ctx["mark_price_entry"] = _f(info.get("markPrice")) or None
            ctx["index_price_entry"] = _f(info.get("indexPrice")) or None
        if seg in ("futures", "prediction"):
            try:
                fr = ex.fetch_funding_rate(pair)
                info = (fr or {}).get("info") or {}
                if ctx.get("mark_price_entry") is None:
                    ctx["mark_price_entry"] = _f((fr or {}).get("markPrice")
                                                 or info.get("markPrice")) or None
                if ctx.get("index_price_entry") is None:
                    ctx["index_price_entry"] = _f((fr or {}).get("indexPrice")
                                                  or info.get("indexPrice")) or None
                iv = info.get("fundingIntervalHours") or info.get("fundingInterval")
                ctx["funding_interval_hours"] = _f(iv) or (8.0 if iv is None else None)
            except Exception:
                ctx.setdefault("funding_interval_hours", 8.0)   # Binance default
    except Exception:
        pass
    ctx = {k: v for k, v in ctx.items() if v is not None}
    _CTX_CACHE[key] = (_time.time(), ctx)
    return ctx


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
        # ACCURACY: 1-minute candles (not 5m) — the true peak lives inside a 5m bar, so 1m highs/
        # lows track the real max-favourable/adverse excursion far more precisely. 1000×1m ≈ 16.7h
        # covers most trades; longer trades fall back to 5m so the window still spans the hold.
        span_min = ((close_ms or int(_time.time() * 1000)) - int(open_ms)) / 60000.0
        tf = "1m" if span_min <= 990 else "5m"
        raw = cli.fetch_ohlcv(pair, tf, since=int(open_ms), limit=1000)  # [ts,o,h,l,c,v]
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


def map_trade(ft: dict, *, broker_ctx: bool = True, bulk: bool = False) -> ClosedTrade:
    """Map ONE Freqtrade trade dict (from /trades) onto a canonical ClosedTrade.

    broker_ctx=False skips the live ticker/funding HTTP context (`_broker_context`).
    Bulk training-data mapping MUST pass False: a live ticker cannot reconstruct
    entry-time context for a trade closed days ago (it would stamp TODAY's 24h
    high/low/mark into `*_entry` columns — wrong training labels), and 2 HTTP calls
    × N closed trades was the 2026-07-07 three-hour funnel-cycle wedge.

    bulk=True additionally resolves the decision-memory episode WITHOUT the per-trade
    LLM reflection (template lesson instead) — an LLM call per row turns a large
    backfill into hours; the outcome/posterior learning itself still runs."""
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
    # ── realized P&L: carry Freqtrade's own numbers (this view never passes through
    # journal.record(), so the schema defaults of 0 were what the dashboard showed).
    # profit_abs is Freqtrade's realized NET (fees + funding already applied).
    fees = _f(ft.get("fee_open_cost")) + _f(ft.get("fee_close_cost"))
    t.total_charges = round(fees, 8)
    t.net_pnl = round(_f(ft.get("profit_abs")), 8)
    t.net_pnl_crypto = t.net_pnl
    t.gross_pnl = round(t.net_pnl + fees, 8)
    t.net_pnl_pct = round(_f(ft.get("profit_ratio")) * 100.0, 4)
    # R multiple from the entry stop distance (same definition as journal quality)
    sl = _f(ft.get("initial_stop_loss_abs"))
    risk = abs(open_rate - sl) * amount if sl else 0.0
    if risk > 0:
        t.r_multiple = round(t.net_pnl / risk, 4)
    # merge the brain's entry-time sidecar metadata (trader psychology + full decision
    # snapshot) recorded at forceenter — Freqtrade itself can't carry it (enter_tag only)
    # Parity with loop-closed rows: every ingested row states its signal source —
    # "freqtrade" baseline, upgraded to "brain" when the entry sidecar proves the
    # brain drove the entry (previously left EMPTY → inconsistent journal column).
    t.signal_source = "freqtrade"
    try:
        from trading.brain.psychology import psych_columns
        from trading.crypto.freqtrade import entry_meta
        seg = "spot" if (ft.get("trading_mode") or "spot") == "spot" else "futures"
        # broker-app market context (App-School-discovered columns) at ingest — best-effort.
        # Only meaningful for FRESH rows (dashboard/live view); bulk historical mapping
        # passes broker_ctx=False (see docstring).
        if broker_ctx:
            try:
                for _k, _v in _broker_context(ft.get("pair", ""), seg).items():
                    setattr(t, _k, _v)
            except Exception:
                pass
        meta = entry_meta.lookup(ft.get("pair", ""), seg, ft.get("open_date", ""))
        if meta:
            t.signal_source = "brain"
            for k, v in psych_columns(meta.get("psychology")).items():
                setattr(t, k, v)
            if isinstance(meta.get("decision_snapshot"), dict):
                t.decision_snapshot = meta["decision_snapshot"]
                # surface the brain decision into its OWN journal columns (previously the
                # snapshot carried it but BRAIN_CONFIDENCE_ENTRY/BRAIN_PREDICTION stayed blank)
                br = meta["decision_snapshot"].get("brain")
                if isinstance(br, dict):
                    if br.get("confidence") is not None:
                        t.brain_confidence_entry = _f(br.get("confidence"))
                    act = str(br.get("action") or meta["decision_snapshot"].get("direction") or "")
                    t.brain_prediction = {"LONG": "UP", "SHORT": "DOWN"}.get(act.upper(), "NEUTRAL")
                    if br.get("regime"):
                        t.market_regime_entry = str(br["regime"])
            if meta.get("episode_id"):
                t.episode_id = str(meta["episode_id"])
            if isinstance(meta.get("feature_attribution"), dict):
                t.feature_attribution = meta["feature_attribution"]
            # Pillar 17: calibrated-uncertainty-at-entry → its own journal columns
            uq = meta.get("uq") or (((meta.get("decision_snapshot") or {}).get("brain")
                                     or {}).get("uq") if isinstance(
                (meta.get("decision_snapshot") or {}).get("brain"), dict) else None)
            if isinstance(uq, dict):
                if uq.get("p_up") is not None:
                    t.p_up = _f(uq["p_up"])
                if uq.get("interval_width") is not None:
                    t.interval_width = _f(uq["interval_width"])
                if uq.get("self_uncertainty") is not None:
                    t.self_uncertainty = _f(uq["self_uncertainty"])
                # executed trades carry a reason only when the gate DOWNGRADED
                # (advisory mode / half-size) — a hard abstention never trades
                t.abstain_reason = str(uq.get("abstain_reason") or "")
    except Exception:
        pass
    # exit-time learning check: did the brain's entry prediction match what price did?
    if t.brain_prediction in ("UP", "DOWN") and close_rate and open_rate:
        actual = "UP" if close_rate > open_rate else "DOWN"
        t.brain_correct = (t.brain_prediction == actual)
    # Close-time learning (picker stacking credit + champion-bandit posterior) — one-shot
    # per trade id; see _learn_from_close for why the guard is load-bearing.
    _learn_from_close(ft, t)
    # decision-memory closure (idempotent: resolve() no-ops on already-resolved episodes,
    # safe under the 30s polling that rebuilds this view)
    if t.episode_id:
        try:
            from trading.brain.decision_memory import get_memory
            ep = get_memory().resolve(
                episode_id=t.episode_id, net_pnl=float(t.net_pnl or 0.0),
                r_multiple=t.r_multiple, exit_price=close_rate,
                exit_reason=ft.get("exit_reason", "") or "", brain_correct=t.brain_correct,
                use_llm=not bulk)
            if ep and ep.get("reflection"):
                t.exit_reflection = ep["reflection"]
        except Exception:
            pass
    return t


def map_open_trade(ft: dict) -> dict:
    """Map a Freqtrade OPEN trade → display row with capital/P&L/peak (MFE/MAE) in USDT."""
    is_short = bool(ft.get("is_short"))
    direction = "SHORT" if is_short else "LONG"
    op = _f(ft.get("open_rate")); cur = _f(ft.get("current_rate"), op)
    amt = _f(ft.get("amount")); lev = _f(ft.get("leverage"), 1.0) or 1.0
    stake = _f(ft.get("stake_amount"))             # capital placed (margin, USDT)
    peaks = _peak_fields(ft)                        # peak profit/loss USDT + their times
    mode = (ft.get("trading_mode") or "spot").lower()
    itype = {"futures": "PERP", "margin": "PERP", "option": "OPT",
             "prediction": "PRED"}.get(mode, "SPOT")
    return {
        "trade_id": f"FT-{ft.get('trade_id')}", "symbol": ft.get("pair", ""),
        "direction": direction, "exchange": ft.get("exchange", "binance"),
        # multi-segment fork: which engine bot owns this trade (futures/spot/options/prediction)
        "segment": ft.get("bot_segment") or "",
        "instrument_type": itype,
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
        # PROFIT TAILGATE: the live LOCKED profit% (ratchets up with the peak, never down) shown
        # in the open-trades table so the owner watches gains getting locked in as price runs.
        **_tailgate_open_cols(ft),
    }


def _tailgate_open_cols(ft: dict) -> dict:
    """Locked-profit ratchet columns for an OPEN trade (read-only view; the executor's pass does
    the ratchet + exit — here we just reflect the current locked value for the table)."""
    try:
        from trading.execution import profit_tailgate as pt
        op, mx = _f(ft.get("open_rate")), _f(ft.get("max_rate"))
        prof = ft.get("profit_ratio")
        profit_pct = float(prof) * 100.0 if prof is not None else None
        # LEVERAGE-AWARE peak: profit_ratio is leverage-scaled, so the rate-derived peak
        # must be on the same basis or the shared lock file ratchets from mixed units
        lev = _f(ft.get("leverage"), 1.0) or 1.0
        peak_pct = None
        if op and mx:
            peak_pct = ((op - mx) / op if ft.get("is_short")
                        else (mx - op) / op) * lev * 100.0
            peak_pct = max(peak_pct, profit_pct or 0.0)
        seg = ft.get("bot_segment") or "futures"
        dec = pt.locked_profit("crypto", seg, trade_id=str(ft.get("trade_id") or ft.get("pair")),
                               profit_pct=profit_pct, peak_profit_pct=peak_pct)
        return {"tailgate_locked_profit_pct": dec.get("locked_profit_pct"),
                "tailgate_peak_profit_pct": round(peak_pct, 3) if peak_pct is not None else None,
                "tailgate_distance_pct": round(dec.get("distance_pct", 0) * 100, 1)}
    except Exception:
        return {"tailgate_locked_profit_pct": None}


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
        # broker_ctx=False: historical rows — live ticker context is wrong for them and
        # cost 2 HTTP calls per trade (the closed view alone hit Binance ~2,200 times).
        # bulk=True: NEVER run LLM episode reflections in a dashboard request thread —
        # after a restart the cold cache rebuild hit hundreds of unresolved episodes and
        # pinned all 32 handler slots behind _CT_LOCK (503 storm, 2026-07-09). Fresh-trade
        # reflections belong to the live_loop ingest tick, not the poll path.
        row = map_trade(ft, broker_ctx=False, bulk=True).to_dict()
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
    now_ms = _time.time() * 1000
    # Batch persistence: journal.record() rewrites the whole journal file every call —
    # fine for the steady one-trade-at-a-time drip, pathological for a backfill (11 MB
    # × N rows). Suspend persist during the loop, write ONCE at the end.
    was_persist = getattr(journal, "persist", False)
    try:
        journal.persist = False
        for ft in ft_trades:
            tid = f"FT-{ft.get('trade_id')}"
            if tid in existing:
                skipped += 1
                continue
            try:
                # Live broker-context reads + LLM reflection ONLY for trades closed in
                # the last 10 minutes: stamping the CURRENT ticker into *_entry columns
                # of a trade that closed hours ago is label-dishonest, and per-row HTTP/
                # LLM is the wedge class from 2026-07-07 — bulk backfill stays pure-CPU.
                fresh = bool(ft.get("close_timestamp")) and \
                    (now_ms - float(ft["close_timestamp"])) < 600_000
                journal.record(map_trade(ft, broker_ctx=fresh, bulk=not fresh))
                ingested += 1
            except Exception:
                skipped += 1
    finally:
        journal.persist = was_persist
        if ingested and was_persist:
            try:
                journal._save()
            except Exception:
                pass
    return {"ingested": ingested, "skipped": skipped, "seen": len(ft_trades)}
