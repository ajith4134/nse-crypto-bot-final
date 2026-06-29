"""trading/online/live_loop.py — the always-on LIVE trade loop (the missing daemon).

The agents' diagnosis: `controls.start()` only flips an enabled/ACTIVE flag — nothing ever
ticked `OnlineSupervisor.step()`, the price sources + decide_fn were `None`, and the PAPER EXIT
path was a stub, so no paper trade ever filled or closed. This module is that missing piece: a
continuously-running background loop, wired to REAL market data, that actually executes and
JOURNALS paper trades.

What it does each tick (default 5s), per enabled market:
  1. pull a REAL price — crypto via ccxt ``fetch_ticker`` (24/7), NSE via the OpenAlgo live
     quote when the market is open (skips cleanly off-hours),
  2. ask ``decide_fn`` for an action — the T8 Brain pipeline if it loads, else a real built-in
     momentum strategy (price vs its SMA) — so trades visibly happen,
  3. pass it through the SAME central trading-state gate (`registry.allow_order`),
  4. for PAPER: book entries on the per-market `PaperWallet`, and on a position CLOSE build a
     full `ClosedTrade` and persist it to the 110-column `TradeJournal` (this is what was
     missing — closes are now real and journaled),
  5. for REAL: BLOCKED by design here (paper-only execution per the operator's choice) — the
     allow_live+confirm gate is honoured but no real broker order is placed.

Reuses the shared, persisted singletons (`controls.registry()` / `controls.book()`) so the
dashboard's Start/Stop/mode/balance controls drive THIS loop live. Thread-based; start()/stop().
"""
from __future__ import annotations

import threading
import time
from collections import deque

from trading.online import controls
from trading.online.session import MarketSession
from trading.online.state import TradingState

# default instrument per market (overridable)
_SYMBOLS = {"CRYPTO": "BTC/USDT", "NSE": "RELIANCE"}
_EXCHANGE = {"CRYPTO": "binance", "NSE": "NSE"}


def trade_type(market: str, instrument: str = "", product: str = "", exchange: str = "") -> str:
    """Human-readable trade class: Crypto Spot/Futures · Options · Futures · NSE Intraday/
    Delivery · Commodities — derived from market + instrument + product + exchange."""
    m, it, pt, ex = (market or "").upper(), (instrument or "").upper(), \
        (product or "").upper(), (exchange or "").upper()
    if m == "CRYPTO" or ex in ("BINANCE", "BYBIT", "OKX", "KUCOIN", "COINBASE", "KRAKEN"):
        return "Crypto Futures" if it in ("PERP", "FUTURES", "QUARTERLY") else "Crypto Spot"
    if it in ("CE", "PE", "OPT"):
        return "Options"
    if it == "FUT":
        return "Futures"
    if ex == "MCX":
        return "Commodities"
    if it in ("EQ", "STK", ""):
        return "NSE Intraday" if pt == "MIS" else "NSE Delivery"
    return f"{ex or m} {it}".strip()


def momentum_decider(window: int = 12, band: float = 0.00015):
    """A real, simple momentum strategy: go/stay LONG above the SMA, EXIT below it.

    Stateful per symbol (keeps a rolling price window). Deterministic given the price stream.
    Returns {action, size} where action ∈ LONG / EXIT / FLAT.
    """
    hist: dict[str, deque] = {}

    def decide(market: str, symbol: str, price_or_window, *, in_position: bool) -> dict:
        price = (float(price_or_window["close"].iloc[-1])
                 if hasattr(price_or_window, "columns") else float(price_or_window))
        h = hist.setdefault(symbol, deque(maxlen=window))
        h.append(price)
        if len(h) < max(5, window // 2):
            return {"action": "FLAT", "size": 0.0}
        sma = sum(h) / len(h)
        size = 1.0 if market.upper() == "CRYPTO" else 1.0
        if price > sma * (1 + band) and not in_position:
            return {"action": "LONG", "size": size}
        if price < sma * (1 - band) and in_position:
            return {"action": "EXIT", "size": size}
        return {"action": "FLAT", "size": 0.0}

    return decide


class BrainDecider:
    """The T8 Brain pipeline wired as a live-loop decider (momentum is the fallback).

    Per market it lazily builds ONE ``BrainTradingPipeline`` and keeps a rolling OHLCV
    pandas window per symbol — SEEDED once from REAL exchange/broker history (so regime +
    pattern have their ~60-bar context immediately), then refreshed each tick from the live
    price. ``__call__`` runs ``pipeline.decide(...)`` and maps its action to the loop's
    LONG/SHORT/EXIT/FLAT vocabulary, attaching the full brain decision under ``_brain``.

    BEST-EFFORT BY DESIGN: any construction or per-tick failure returns ``None`` so the
    live loop transparently falls back to the momentum strategy for that tick — it never
    breaks the loop, and stays fully offline-safe.
    """

    _COLS = ["open", "high", "low", "close", "volume"]
    _MAXLEN = 200

    def __init__(self, *, maxlen: int = 200):
        self._MAXLEN = int(maxlen)
        self._pipelines: dict[str, object] = {}     # market -> BrainTradingPipeline (or None)
        self._unavailable: set[str] = set()         # markets whose pipeline build failed
        self._windows: dict[str, object] = {}       # symbol -> pandas OHLCV DataFrame
        self._seeded: set[str] = set()              # symbols already history-seeded

    # ── pipeline per market (lazy, guarded) ─────────────────────────────────────────
    def _pipeline(self, market: str):
        m = market.upper()
        if m in self._unavailable:
            return None
        if m not in self._pipelines:
            try:
                from trading.brain.pipeline import BrainTradingPipeline
                self._pipelines[m] = BrainTradingPipeline(market=m)
            except Exception:
                self._unavailable.add(m)
                self._pipelines[m] = None
        return self._pipelines[m]

    # ── rolling OHLCV window per symbol (seed from REAL history, then live-refresh) ──
    def _seed_window(self, market: str, symbol: str):
        import pandas as pd
        m = market.upper()
        df = None
        try:
            if m == "CRYPTO":
                from trading.crypto.exchange_client import ExchangeClient
                raw = ExchangeClient("binance")._client().fetch_ohlcv(
                    symbol, timeframe="5m", limit=self._MAXLEN)
                df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
                df = df[self._COLS].astype(float)
            else:
                import datetime as _dt
                from trading.openalgo_client import OpenAlgoClient
                end = _dt.date.today()
                start = end - _dt.timedelta(days=10)
                h = OpenAlgoClient()._client().history(
                    symbol=symbol, exchange="NSE", interval="5m",
                    start_date=start.isoformat(), end_date=end.isoformat())
                df = pd.DataFrame(h)
                df = df[[c for c in self._COLS if c in df.columns]].astype(float)
        except Exception:
            df = None
        if df is None or len(df) == 0:
            # offline / off-hours fallback: an empty frame the live ticks will grow
            df = pd.DataFrame(columns=self._COLS)
        self._windows[symbol] = df.tail(self._MAXLEN).reset_index(drop=True)
        self._seeded.add(symbol)

    def _refresh(self, market: str, symbol: str, price: float):
        import pandas as pd
        if symbol not in self._seeded:
            self._seed_window(market, symbol)
        df = self._windows.get(symbol)
        if df is None:
            df = pd.DataFrame(columns=self._COLS)
        price = float(price)
        if len(df) == 0:
            row = {"open": price, "high": price, "low": price, "close": price, "volume": 0.0}
            df = pd.DataFrame([row], columns=self._COLS)
        else:
            # refresh the latest bar in place from the live price (synthetic intra-bar update)
            i = df.index[-1]
            df.at[i, "close"] = price
            df.at[i, "high"] = max(float(df.at[i, "high"]), price)
            df.at[i, "low"] = min(float(df.at[i, "low"]), price)
        self._windows[symbol] = df.tail(self._MAXLEN).reset_index(drop=True)
        return self._windows[symbol]

    # ── the decider entrypoint ──────────────────────────────────────────────────────
    # the full T8 pipeline (features+regime+pattern+news+recall) is heavy; run it at most
    # once per THROTTLE_S per symbol and cache the decision between — keeps the loop's thread
    # from holding the GIL every tick and bogging the dashboard HTTP server it shares.
    _THROTTLE_S = 30.0

    def __call__(self, market: str, symbol: str, price, *, in_position: bool):
        try:
            pipe = self._pipeline(market)
            if pipe is None:
                return None
            now = time.monotonic()
            cache = getattr(self, "_decision_cache", None)
            if cache is None:
                self._decision_cache = cache = {}
            hit = cache.get(symbol)
            # reuse a recent decision unless it's stale OR we just opened/closed (in_position flip)
            if hit and (now - hit[0]) < self._THROTTLE_S and hit[2] == in_position:
                return hit[1]
            window = self._refresh(market, symbol, price)
            if window is None or len(window) < 5:
                return None
            side = "LONG" if in_position else None
            decision = pipe.decide(symbol, window, position_side=side)
            raw = decision.get("action", "FLAT")
            action = "FLAT" if raw in ("HOLD", "FLAT") else raw   # LONG/SHORT/EXIT pass through
            result = {"action": action, "size": 1.0, "_brain": decision}
            cache[symbol] = (now, result, in_position)
            return result
        except Exception:
            return None     # any failure → loop falls back to momentum for this tick


def _brain_decider():
    """Wire the T8 Brain pipeline as the live decider — OPT-IN via BRAIN_LOOP=1.

    The full pipeline (features+regime+pattern[stumpy]+news+recall) is heavy; running it in
    the always-on loop on every symbol slows the shared dashboard server and floods logs. By
    default we return None → the loop uses the fast, real momentum strategy (observable trades,
    responsive dashboard). Set BRAIN_LOOP=1 to engage the brain (throttled to 30s/symbol); it
    still falls back to momentum per-tick on any error.
    """
    import os
    if os.getenv("BRAIN_LOOP") != "1":
        return None
    try:
        return BrainDecider()
    except Exception:
        return None


class LiveTradeLoop:
    """Continuously ticks real-data PAPER trading and journals closed trades."""

    def __init__(self, *, interval: float = 5.0, symbols: dict | None = None,
                 decide_fn=None, journal=None, registry=None, book=None,
                 crypto_price=None, nse_price=None):
        self.interval = float(interval)
        self.symbols = symbols or dict(_SYMBOLS)
        self.registry = registry or controls.registry()
        self.book = book or controls.book()
        self._momentum = momentum_decider()
        self._brain = decide_fn or _brain_decider()
        self._journal = journal
        self._crypto_price = crypto_price          # injectable for tests; else lazy ccxt
        self._nse_price = nse_price                # injectable for tests; else lazy OpenAlgo
        self._sessions: dict[str, MarketSession] = {}
        self._symbol_segments: dict = {}           # (MARKET, symbol) -> segment (Phase 2 screener)
        self._open: dict[str, dict] = {}           # (market:symbol) -> open trade dict
        self._marks: dict[str, dict] = {}          # market -> {symbol: price}
        self._last_brain: dict[str, dict] = {}     # symbol -> latest brain decision dict
        # P2 screener (dynamic watchlist) · P4 sizer · P3 trailing exits — all lazy + offline-safe
        self._screener = None
        self._sizer = None
        self._refresh_every = 60                    # re-screen the watchlist every ~60 ticks (5 min)
        self._atr: dict = {}                        # symbol -> recent ATR estimate (for sizing/trailing)
        # user-tunable strategy config (trailing ATR multiple · sizing method/risk/caps) — persisted
        self.cfg = {"trail_atr_mult": 2.5, "sizing_method": "kelly_atr",
                    "max_risk_pct": 1.0, "max_position_pct": 25.0, "kelly_fraction": 0.5}
        try:
            from trading import state as _st
            saved = _st.load_json("strategy_config.json", {})
            if isinstance(saved, dict):
                self.cfg.update({k: v for k, v in saved.items() if k in self.cfg})
        except Exception:
            pass
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.ticks = 0
        self.trades_opened = 0
        self.trades_closed = 0
        self.last_tick: dict = {}
        self.errors: list[str] = []
        self._nse_auth_ok: bool | None = None       # None=unknown, False=expired, True=ok
        self._nse_skip_until = 0                     # tick number to retry NSE after a backoff

    def _note_error(self, msg: str) -> None:
        """Append an error, de-duplicated against the most recent (avoid 5s-spam)."""
        if not self.errors or self.errors[-1] != msg:
            self.errors.append(msg)
        del self.errors[:-12]

    # ── journal (lazy, persisted) ───────────────────────────────────────────────────
    def journal(self):
        if self._journal is None:
            from trading.journal.journal import TradeJournal
            self._journal = TradeJournal(state_file="journal.json", persist=True)
        return self._journal

    # ── real price sources (lazy, guarded) ──────────────────────────────────────────
    def _price(self, market: str, symbol: str, mode: str):
        m = market.upper()
        try:
            if m == "CRYPTO":
                if self._crypto_price is not None:
                    return float(self._crypto_price(symbol))
                from trading.crypto.exchange_client import ExchangeClient
                if not hasattr(self, "_xc"):
                    self._xc = ExchangeClient(_EXCHANGE["CRYPTO"])
                t = self._xc.ticker(symbol)
                return float(t.get("last") or t.get("close") or t.get("ask"))
            # NSE — live quote only when the session says LIVE (market open)
            if self._nse_price is not None:
                return float(self._nse_price(symbol))
            if mode != "LIVE":
                return None                         # off-hours: no live NSE feed → skip
            if self.ticks < self._nse_skip_until:   # backing off after a broker-auth failure
                return None
            from trading.openalgo_client import OpenAlgoClient
            if not hasattr(self, "_oa"):
                self._oa = OpenAlgoClient()
            q = self._oa.quote(symbol, exchange="NSE")
            self._nse_auth_ok = True
            # OpenAlgo returns {"data": {"ltp": ...}, "status": "success"}
            d = q.get("data", q) if isinstance(q, dict) else {}
            return float(d.get("ltp") or d.get("last_price") or d.get("last") or 0.0) or None
        except Exception as e:
            msg = str(e)
            if "api_key" in msg or "access_token" in msg or "token" in msg.lower():
                # Zerodha session expired (daily) → needs broker re-login at the OpenAlgo UI.
                self._nse_auth_ok = False
                self._nse_skip_until = self.ticks + 60      # back off ~5 min (don't hammer)
                self._note_error("NSE broker auth expired — re-login Zerodha at OpenAlgo "
                                 "(http://127.0.0.1:5000). Live NSE quotes paused until then.")
            else:
                self._note_error(f"{m} price: {type(e).__name__}: {str(e)[:60]}")
            return None

    def _decide(self, market: str, symbol: str, price, *, in_position: bool) -> dict:
        if self._brain is not None:
            try:
                d = self._brain(market, symbol, price, in_position=in_position)
                if isinstance(d, dict) and d.get("action"):
                    if isinstance(d.get("_brain"), dict):
                        self._last_brain[symbol] = d["_brain"]   # for journal context
                    return d
            except Exception:
                pass
        return self._momentum(market, symbol, price, in_position=in_position)

    # map a (market, symbol) to its trade-type segment (default watchlist; Phase 2 tags
    # screened symbols with their real segment).
    _SEG_DEFAULT = {"CRYPTO": "spot", "NSE": "intraday"}

    def _segment_of(self, market: str, symbol: str) -> str:
        return self._symbol_segments.get((market.upper(), symbol),
                                         self._SEG_DEFAULT.get(market.upper(), ""))

    # ── P2 screener / P4 sizer (lazy, offline-safe) ────────────────────────────────
    def screener(self):
        if self._screener is None:
            try:
                from trading.screener import Screener
                self._screener = Screener()
            except Exception:
                self._screener = False
        return self._screener or None

    def sizer(self):
        if self._sizer is None:
            try:
                from trading.sizing import PositionSizer
                self._sizer = PositionSizer(method=self.cfg["sizing_method"],
                                            max_risk_pct=self.cfg["max_risk_pct"],
                                            max_position_pct=self.cfg["max_position_pct"],
                                            kelly_fraction=self.cfg["kelly_fraction"])
            except Exception:
                self._sizer = False
        return self._sizer or None

    def set_config(self, **kw) -> dict:
        """Update strategy config (trail_atr_mult / sizing_method / max_risk_pct /
        max_position_pct / kelly_fraction), rebuild the sizer, and persist."""
        for k, v in kw.items():
            if k in self.cfg and v is not None:
                self.cfg[k] = float(v) if k != "sizing_method" else str(v)
        self._sizer = None                          # rebuild with new params on next use
        try:
            from trading import state as _st
            _st.save_json("strategy_config.json", self.cfg)
        except Exception:
            pass
        return dict(self.cfg)

    def watchlist_view(self) -> dict:
        """Current per-market watchlist (symbol + segment) the loop is trading — for the UI."""
        out = {}
        for market, syms in self.symbols.items():
            items = []
            for s in (syms if isinstance(syms, (list, tuple)) else [syms]):
                items.append({"symbol": s, "segment": self._segment_of(market, s),
                              "last": self._marks.get(market.upper(), {}).get(s)})
            out[market] = items
        return out

    def _update_atr(self, symbol: str, price: float) -> float:
        """Cheap EMA True-Range proxy per symbol (for sizing + ATR trailing)."""
        a = self._atr.get(symbol)
        if a is None:
            self._atr[symbol] = {"atr": max(price * 0.005, 1e-9), "prev": price}
        else:
            self._atr[symbol] = {"atr": 0.9 * a["atr"] + 0.1 * abs(price - a["prev"]),
                                 "prev": price}
        return self._atr[symbol]["atr"]

    def _pairs(self):
        """Flatten the watchlist: self.symbols values may be a single symbol or a list."""
        out = []
        for market, syms in self.symbols.items():
            for s in (syms if isinstance(syms, (list, tuple)) else [syms]):
                out.append((market, s))
        return out

    def _refresh_watchlist(self) -> None:
        """Re-screen each enabled market's SELECTED segments → dynamic symbol watchlist."""
        sc = self.screener()
        if sc is None:
            return
        for market in list(self.symbols):
            ms = self.registry.get(market)
            segs = list(getattr(ms, "segments", []) or [])
            if not ms.enabled or not segs:
                continue
            try:
                wl = sc.watchlist(market, segs, per_segment=3)
            except Exception:
                continue
            syms = []
            for c in wl:
                sym, seg = c.get("symbol"), c.get("segment")
                if sym:
                    syms.append(sym)
                    self._symbol_segments[(market.upper(), sym)] = seg
            if syms:
                self.symbols[market] = syms[:8]      # cap the per-market watchlist

    # ── one tick ─────────────────────────────────────────────────────────────────────
    def tick(self, *, when=None) -> dict:
        self.ticks += 1
        # periodically re-screen the watchlist (skip tick 1 so seeding is offline-friendly)
        if self._refresh_every and self.ticks > 1 and self.ticks % self._refresh_every == 0:
            try:
                self._refresh_watchlist()
            except Exception:
                pass
        results = []
        for market, symbol in self._pairs():
            ms = self.registry.get(market)
            if not ms.enabled:
                results.append({"market": market, "skipped": "stopped"})
                continue
            # only trade SELECTED segments (Phase 2 screeners feed per-segment symbols;
            # here the default symbol maps to its segment).
            seg = self._segment_of(market, symbol)
            if seg and not ms.has_segment(seg):
                results.append({"market": market, "segment": seg, "skipped": "segment off"})
                continue
            sess = self._sessions.setdefault(market.upper(), MarketSession(market))
            mode = sess.mode(when)
            price = self._price(market, symbol, mode)
            if price is None:
                results.append({"market": market, "mode": mode, "skipped": "no price"})
                continue
            self._marks.setdefault(market.upper(), {})[symbol] = price
            key = f"{market.upper()}:{symbol}"
            in_pos = key in self._open
            atr = self._update_atr(symbol, price)     # ATR proxy for sizing + trailing
            trail_exit = None
            if in_pos:                                # track peak profit/loss + the trailing exit
                ot = self._open[key]
                sgn = 1.0 if ot["direction"] == "LONG" else -1.0
                upnl = sgn * (price - ot["entry_price"]) * ot["quantity"]
                ot["peak_profit"] = round(max(ot.get("peak_profit", 0.0), upnl), 4)
                ot["peak_loss"] = round(min(ot.get("peak_loss", 0.0), upnl), 4)
                eng = ot.get("trail")
                if eng is not None:
                    try:
                        tr = eng.update(price, atr=atr)
                        ot["stop_level"] = tr.get("stop")
                        if tr.get("exit"):
                            trail_exit = tr.get("reason", "trailing-stop")
                    except Exception:
                        pass
            decision = self._decide(market, symbol, price, in_position=in_pos)
            action = decision.get("action", "FLAT")
            size = float(decision.get("size", 1.0))
            reduces = action in ("EXIT", "FLAT") or bool(trail_exit)
            gate = self.registry.allow_order(market, reduces_position=reduces, is_real=ms.is_real)
            routed = None
            if ms.is_real:
                # paper-only execution by operator choice: honour the gate but never place real orders
                routed = {"mode": "REAL", "blocked": True,
                          "detail": "real-money execution disabled (paper-only build)"}
            elif action == "LONG" and not in_pos and gate["ok"]:
                routed = self._open_trade(market, symbol, "LONG", price, size, mode, atr=atr,
                                          brain=decision.get("_brain"))
            elif (action == "EXIT" or trail_exit) and in_pos and gate["ok"]:
                routed = self._close_trade(market, symbol, price, mode)
                if isinstance(routed, dict) and trail_exit:
                    routed["exit_reason"] = trail_exit
            results.append({"market": market, "mode": mode, "price": round(price, 4),
                            "action": action, "in_position": in_pos,
                            "gate_ok": gate["ok"], "routed": routed})
        self.last_tick = {"tick": self.ticks, "results": results}
        return self.last_tick

    def _size_trade(self, market, symbol, direction, price, atr, brain) -> float | None:
        """P4: position size from {capital, entry, ATR-stop, edge} via the PositionSizer."""
        sz = self.sizer()
        if sz is None:
            return None
        try:
            w = self.book.wallet(market)
            cap = float(w.cash())
            prob = brain.get("confidence") if isinstance(brain, dict) else None
            out = sz.size(capital=cap, entry_price=float(price), atr=atr, side=direction,
                          prob=prob, market=market.upper())
            qty = abs(float(out.get("qty") or 0.0))
            return qty if qty > 0 else None
        except Exception:
            return None

    def _make_trail(self, direction, price, atr):
        """P3: attach the direction-aware ATR trailing STOP for the position."""
        try:
            from trading.exits import make_exit
            purpose = "stop" if direction == "LONG" else "loss"
            return make_exit("long" if direction == "LONG" else "short", purpose,
                             entry_price=float(price), mode="atr",
                             atr_mult=float(self.cfg.get("trail_atr_mult", 2.5)))
        except Exception:
            return None

    def _open_trade(self, market, symbol, direction, price, size, mode, *, atr=None, brain=None) -> dict:
        # P4: size the trade with the PositionSizer (capital, ATR-stop, edge) — not a fixed 1.
        size = self._size_trade(market, symbol, direction, price, atr, brain) or size
        w = self.book.wallet(market)
        try:
            w.record_fill(symbol, "buy" if direction == "LONG" else "sell", size, price)
        except Exception as e:
            return {"ok": False, "detail": str(e)[:80]}
        import datetime as _dt
        is_crypto = market.upper() == "CRYPTO"
        instrument = "SPOT" if is_crypto else "EQ"
        product = "SPOT" if is_crypto else "MIS"
        # P3: attach the direction-aware trailing STOP exit (ATR-multiple) for this position
        trail = self._make_trail(direction, price, atr)
        self._open[f"{market.upper()}:{symbol}"] = {
            "market": market.upper(), "symbol": symbol, "direction": direction,
            "quantity": size, "entry_price": price, "entry_dt": _dt.datetime.now().isoformat(),
            "mode": mode,
            "instrument": instrument, "product": product,
            "trade_type": trade_type(market, instrument, product, _EXCHANGE.get(market.upper(), "")),
            "capital": round(price * size, 2),       # capital placed on the trade (notional)
            "peak_profit": 0.0, "peak_loss": 0.0,     # MFE / MAE in currency (tracked live)
            "trail": trail, "stop_level": None,
            # snapshot the brain decision that produced THIS entry (if any) for the journal
            "brain_entry": dict(brain) if isinstance(brain, dict) else None}
        self.trades_opened += 1
        return {"ok": True, "opened": direction, "price": price, "qty": size}

    def _close_trade(self, market, symbol, price, mode) -> dict:
        key = f"{market.upper()}:{symbol}"
        ot = self._open.pop(key, None)
        if ot is None:
            return {"ok": False, "detail": "no open trade"}
        w = self.book.wallet(market)
        close_side = "sell" if ot["direction"] == "LONG" else "buy"
        try:
            fill = w.record_fill(symbol, close_side, ot["quantity"], price)
        except Exception as e:
            self._open[key] = ot
            return {"ok": False, "detail": str(e)[:80]}
        self.trades_closed += 1
        self._journal_close(ot, price, fill.get("realized_pnl"))
        return {"ok": True, "closed": ot["direction"], "exit": price,
                "realized": fill.get("realized_pnl")}

    def _journal_close(self, ot: dict, exit_price: float, realized) -> None:
        """Build a full ClosedTrade and persist it to the 110-column journal."""
        try:
            import datetime as _dt

            from trading.journal.schema import ClosedTrade
            is_crypto = ot["market"] == "CRYPTO"
            # the brain decision that produced this entry (preferred), else the latest seen
            brain = ot.get("brain_entry") or self._last_brain.get(ot["symbol"])
            brain_driven = isinstance(ot.get("brain_entry"), dict)
            t = ClosedTrade(
                trade_id=f"L{self.trades_closed}-{ot['symbol'].replace('/', '')}",
                symbol=ot["symbol"],
                exchange=_EXCHANGE.get(ot["market"], ot["market"]),
                instrument_type=ot.get("instrument", "SPOT" if is_crypto else "EQ"),
                direction=ot["direction"],
                product_type=ot.get("product", "SPOT" if is_crypto else "MIS"),
                strategy_name="brain" if brain_driven else "momentum",
                setup_type="Momentum",
                market_session=ot.get("mode", "LIVE"),
                broker_used="binance" if is_crypto else "zerodha",
                entry_datetime=ot["entry_dt"],
                exit_datetime=_dt.datetime.now().isoformat(),
                quantity=float(ot["quantity"]),
                entry_price=float(ot["entry_price"]),
                exit_price=float(exit_price),
                entry_order_type="MARKET", exit_order_type="MARKET",
            )
            if realized is not None:
                t.gross_pnl = float(realized)
            # peak profit (MFE) / peak loss (MAE, stored positive) + capital placed — tracked live
            t.mfe = round(float(ot.get("peak_profit", 0.0)), 4)
            t.mae = round(abs(float(ot.get("peak_loss", 0.0))), 4)
            t.margin_used = float(ot.get("capital", ot["entry_price"] * ot["quantity"]))
            # ── brain / market-context fields (only those present in the schema) ──
            if isinstance(brain, dict):
                regime = brain.get("regime")
                if regime:
                    t.market_regime_entry = str(regime)
                conf = brain.get("confidence")
                if conf is not None:
                    t.brain_confidence_entry = float(conf)
                act = brain.get("action")
                t.brain_prediction = ({"LONG": "UP", "SHORT": "DOWN"}
                                      .get(act, "NEUTRAL"))
                t.signal_source = "brain"
                # record the richer brain telemetry (anomaly/news/signal/recall) as a
                # node_contribution entry — the schema's JSON sidecar for AI metadata.
                t.node_contributions = [{
                    "source": "brain_pipeline",
                    "signal": brain.get("signal"),
                    "anomaly_score": brain.get("anomaly_score"),
                    "news_compound": brain.get("news_compound"),
                    "recall_bias": brain.get("recall_bias"),
                    "safety_blocked": brain.get("safety_blocked"),
                    "safety_reason": brain.get("safety_reason"),
                }]
            self.journal().record(t)          # derives charges→net P&L, quality, behaviour, persists
        except Exception as e:
            self.errors.append(f"journal: {type(e).__name__}: {str(e)[:70]}")

    # ── thread control ───────────────────────────────────────────────────────────────
    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as e:
                self.errors.append(f"tick: {type(e).__name__}: {str(e)[:70]}")
            self._stop.wait(self.interval)

    def start(self) -> "LiveTradeLoop":
        if self._thread and self._thread.is_alive():
            return self
        # eager-enumerate the per-market wallets so balances/equity show in the dashboard
        # immediately (not only after the first trade/edit touches them).
        for market in self.symbols:
            try:
                self.book.wallet(market)
            except Exception:
                pass
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="live-trade-loop", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def open_positions(self) -> list[dict]:
        """Live open paper positions across markets (marked at last price)."""
        rows = []
        for key, ot in self._open.items():
            mark = self._marks.get(ot["market"], {}).get(ot["symbol"], ot["entry_price"])
            sign = 1.0 if ot["direction"] == "LONG" else -1.0
            # drop non-JSON-serialisable internals (the trailing engine + brain dict)
            clean = {k: v for k, v in ot.items() if k not in ("trail", "brain_entry")}
            rows.append({**clean, "mark_price": mark,
                         "unrealized_pnl": round(sign * (mark - ot["entry_price"]) * ot["quantity"], 4)})
        return rows

    def ticks_snapshot(self) -> dict:
        out = {}
        for market, marks in self._marks.items():
            for sym, px in marks.items():
                out[f"{market}:{sym}"] = {"symbol": sym, "market": market, "last": px}
        return out

    def status(self) -> dict:
        nse_auth = ("ok" if self._nse_auth_ok else
                    "expired — re-login Zerodha at OpenAlgo (http://127.0.0.1:5000)"
                    if self._nse_auth_ok is False else "unknown")
        segs = {}
        for m in self.symbols:
            try:
                segs[m] = list(getattr(self.registry.get(m), "segments", []) or [])
            except Exception:
                segs[m] = []
        return {"running": bool(self._thread and self._thread.is_alive()),
                "interval_s": self.interval, "ticks": self.ticks,
                "trades_opened": self.trades_opened, "trades_closed": self.trades_closed,
                "open_positions": len(self._open), "symbols": self.symbols,
                "decider": "brain" if self._brain else "momentum",
                "execution": "paper-only (real-money blocked)",
                "selected_segments": segs,
                "screener": "active" if self.screener() else "off",
                "sizer": "active" if self.sizer() else "off",
                "trailing_exits": "ATR trailing-stop per position",
                "config": dict(self.cfg),
                "nse_broker_auth": nse_auth, "crypto_feed": "ccxt (live)",
                "errors": self.errors[-5:], "last_tick": self.last_tick}


# ── module-level singleton so the dashboard + read endpoints share ONE running loop ──
_LOOP: LiveTradeLoop | None = None


def get_loop() -> LiveTradeLoop:
    global _LOOP
    if _LOOP is None:
        _LOOP = LiveTradeLoop()
    return _LOOP


def start_loop() -> LiveTradeLoop:
    return get_loop().start()
