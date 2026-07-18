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
  4. for PAPER: book entries on the per-market `PaperWallet` (the accounting ledger) AND route
     each NSE order through OpenAlgo's SANDBOX so it appears in the real engine's order book —
     paper NSE is no longer a pure in-process sim. On a position CLOSE build a full `ClosedTrade`
     (with the OpenAlgo entry/exit order ids) and persist it to the 110-column `TradeJournal`,
  5. for REAL crypto: BLOCKED by design here (crypto execution moves to Freqtrade in Phase E).
     NSE order routing honours OpenAlgo's own live guard (allow_live) — paper hits the sandbox,
     live hits the real broker only when explicitly armed.

Reuses the shared, persisted singletons (`controls.registry()` / `controls.book()`) so the
dashboard's Start/Stop/mode/balance controls drive THIS loop live. Thread-based; start()/stop().
"""
from __future__ import annotations

import os
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
                pipe = BrainTradingPipeline(market=m)
                self._attach_evolved(pipe, m)      # feed the best bred strategy in (if any)
                self._pipelines[m] = pipe
            except Exception:
                self._unavailable.add(m)
                self._pipelines[m] = None
        return self._pipelines[m]

    # ── evolved-strategy link: keep the pipeline pointed at the best bred survivor ──────
    _EVO_REFRESH_S = 300.0                          # re-read the skill library at most every 5 min

    def _attach_evolved(self, pipe, market: str) -> None:
        """Point the pipeline's `evolved_strategy` at the current best bred Strategy from the
        persisted SkillLibrary (trading.strategy.evolved_link). Gate-aware + best-effort: a
        no-op when evolution is OFF or the library is empty, so it never breaks a decision."""
        try:
            from trading.strategy.evolved_link import attach_to_pipeline
            attach_to_pipeline(pipe, market)
            self._evo_refreshed = time.monotonic()
        except Exception:
            pass

    def _maybe_refresh_evolved(self, market: str) -> None:
        """Periodically re-attach so strategies bred by the learning loop flow into live
        decisions without a restart (throttled — the library read is cached under the hood)."""
        now = time.monotonic()
        if now - getattr(self, "_evo_refreshed", 0.0) < self._EVO_REFRESH_S:
            return
        pipe = self._pipelines.get(market.upper())
        if pipe is not None:
            self._attach_evolved(pipe, market.upper())

    # ── rolling OHLCV window per symbol (seed from REAL history, then live-refresh) ──
    def _seed_window(self, market: str, symbol: str):
        import pandas as pd
        m = market.upper()
        df = None
        try:
            if m == "CRYPTO":
                # candles via the multi-venue pool (budgeted round-robin), not raw Binance;
                # perp symbols carry ':USDT', bare pairs are spot — pick the right pool so
                # spot symbols aren't silently rewritten to perp contracts.
                from trading.crypto.exchange_pool import get_pool
                mt = "swap" if ":" in symbol else "spot"
                raw = get_pool(mt).ohlcv(symbol, timeframe="5m", limit=self._MAXLEN)
                df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
                df = df[self._COLS].astype(float)
            else:
                # NSE candles via data_failsafe, which is UI-gated (NSE_UI_ONLY, 2026-07-13):
                # under the hard gate it returns the Upstox UI / vision-read candles or None
                # (→ empty frame the live ticks grow); off the gate it uses OpenAlgo history.
                from trading.broker_sense import data_failsafe
                raw = data_failsafe.ohlcv(symbol, "NSE", timeframe="5m", limit=self._MAXLEN)
                if raw:
                    df = pd.DataFrame(raw, columns=["ts", "open", "high", "low",
                                                    "close", "volume"])
                    df = df[[c for c in self._COLS if c in df.columns]].astype(float)
                else:
                    df = None                        # UI-only miss → abstain (empty window)
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
            self._maybe_refresh_evolved(market)     # pull in freshly-bred strategies (throttled)
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
            # CORTEX parity with crypto (user mandate 2026-07-04): consult the
            # same 28-feature cortex on every NSE decision. CORTEX_SIGNAL=1 →
            # shadow log + trust pending; CORTEX_TRADE=1 → cortex decides.
            result = _cortex_shadow_nse(market, symbol, window, result, in_position)
            cache[symbol] = (now, result, in_position)
            return result
        except Exception:
            return None     # any failure → loop falls back to momentum for this tick


def _xray_on_open(symbol: str, exchange: str, segment: str) -> None:
    """Background Stock X-Ray capture when a trade opens (never raises into the trade path)."""
    try:
        from trading.broker_sense.stock_xray import capture_on_open
        capture_on_open(symbol, exchange or "NSE", segment or "intraday")
    except Exception:
        pass


def _cortex_shadow_nse(market: str, symbol: str, window, d: dict,
                       in_position: bool) -> dict:
    """NSE twin of brain_executor._cortex_shadow: the SAME CortexSignalSource
    (28-feature bus, reflex abstention, risk sizing) consulted on every NSE
    decision. Shadow by default; CORTEX_TRADE=1 promotes it. Never raises."""
    import os
    if os.environ.get("CORTEX_SIGNAL", "") not in ("1", "true", "TRUE", "yes"):
        return d
    try:
        from trading import cortex_signal as cx
        src = cx.get_cortex_source()
        key = f"{market}:{symbol}"
        sig = src.signal(key, window)
        print(f"[cortex:nse] {symbol} shadow side={sig.get('side')} "
              f"frac={sig.get('size_fraction')} conf={sig.get('confidence')} "
              f"tier={sig.get('tier_reached')} experts={sig.get('experts_fired')} "
              f"reason={sig.get('reason')} | decider={d.get('action')}", flush=True)
        cx.record_shadow("nse", key, sig, d.get("action"))
        if sig.get("side") in ("long", "short"):
            cx.record_pending(key, sig["side"], sig.get("experts_fired") or [])
        if os.environ.get("CORTEX_TRADE", "") in ("1", "true", "TRUE", "yes"):
            meta = {"source": "cortex_nse", **{k: sig.get(k) for k in
                    ("confidence", "tier_reached", "experts_fired", "reason")}}
            if sig.get("side") == "long":
                return {"action": "LONG", "size": sig.get("size_fraction", 1.0), "_brain": meta}
            if sig.get("side") == "short":
                return {"action": "SHORT", "size": sig.get("size_fraction", 1.0), "_brain": meta}
            return {"action": ("EXIT" if in_position else "FLAT"), "_brain": meta}
    except Exception as e:
        print(f"[cortex:nse] shadow error for {symbol}: {e!r}", flush=True)
    return d


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
                 crypto_price=None, nse_price=None, crypto_engine=None):
        self.interval = float(interval)
        self.symbols = symbols or dict(_SYMBOLS)
        self.registry = registry or controls.registry()
        self.book = book or controls.book()
        self._momentum = momentum_decider()
        self._brain = decide_fn or _brain_decider()
        self._journal = journal
        self._crypto_price = crypto_price          # injectable for tests; else lazy ccxt
        self._nse_price = nse_price                # injectable for tests; else lazy OpenAlgo
        # Phase B seam (not yet active): a CryptoEngineClient (Freqtrade) to route crypto fills
        # in Phase E. For now crypto stays on the wallet/ccxt paper path; this is just wired in.
        self._crypto_engine = crypto_engine
        self._sessions: dict[str, MarketSession] = {}
        self._symbol_segments: dict = {}           # (MARKET, symbol) -> segment (Phase 2 screener)
        self._symbol_score: dict = {}              # (MARKET, symbol) -> screener score (auto-open rank)
        self._symbol_oa_exchange: dict = {}        # (MARKET, symbol) -> OpenAlgo exch override (BFO)
        self._open: dict[str, dict] = {}           # (market:symbol) -> open trade dict
        # per-(symbol, direction) timestamps of losing closes — blocks same-direction
        # re-entry for LOOP_LOSS_COOLDOWN_MIN minutes (the wallet lane re-entered one
        # dumping coin 90+ times in a night; a direction FLIP stays allowed)
        self._loss_cooldown: dict[str, float] = {}
        self._marks: dict[str, dict] = {}          # market -> {symbol: price}
        self._last_brain: dict[str, dict] = {}     # symbol -> latest brain decision dict
        self._last_psych: dict[str, dict] = {}     # "MKT:symbol" -> latest psychology dict
        # P2 screener (dynamic watchlist) · P4 sizer · P3 trailing exits — all lazy + offline-safe
        self._screener = None
        self._sizer = None
        self._refresh_every = 12                    # re-screen the watchlist every ~12 ticks (~1 min)
        self._ingest_every = 24                     # ingest Freqtrade closed crypto trades ~every 2 min
        self._atr: dict = {}                        # symbol -> recent ATR estimate (for sizing/trailing)
        # user-tunable strategy config — persisted. Defaults tuned to HOLD trades (intraday,
        # minutes→hours): a wide percentage trailing stop that rides up + a far take-profit cap.
        self.cfg = {"trail_mode": "pct",          # "pct" (wide, predictable) | "atr" (volatility)
                    "trail_pct": 0.035,           # 3.5% trailing distance — rides up, locks gains
                    "take_profit_pct": 0.07,      # 7% far take-profit cap (0 = none, ride trail only)
                    "trail_atr_mult": 2.5,        # used only when trail_mode == "atr"
                    # AUTO-OPEN basket mode (temporary, until the brain takes over): open trades
                    # on the SCREENED candidates with a wide initial stop + profit-tail gating.
                    # Primary = open the TOP-N ranked per segment; FALLBACK = if a segment has
                    # fewer than `min_open_per_segment` open positions, keep opening screened
                    # candidates until that minimum is filled.
                    "enter_all": False,           # master toggle: True → auto-open screened trades
                    "exit_mode": "trail_stop",    # "trail_stop" (has stop) | "profit_only" (no stop)
                    "basket_deploy_pct": 85.0,    # % of cash to spread equally across the basket
                    "top_n_per_segment": 2,       # primary: open this many top-ranked per segment
                    "min_open_per_segment": 0,    # DEFAULT fallback floor: ≥ this many open / segment
                    "min_open_by_segment": {},    # PER-SEGMENT overrides {segment: floor} (beats default)
                    "min_total_open": 0,          # global floor: fill to ≥ this many open trades total
                    "min_capital_per_trade": 0.0, # each trade deploys at least this much capital
                    # brain handoff: manual sliders drive trading NOW; the brain auto-takes over
                    # once the journal has ≥ this many CLOSED trades to learn from.
                    "brain_handoff_trades": 30,
                    # per-segment leverage overrides {segment: x} — beats the built-in defaults.
                    "leverage_by_segment": {},
                    # per-segment LOT SIZE overrides {segment: lot} for lot-based instruments
                    # (F&O / options / commodities) — beats the representative defaults.
                    "lot_size_by_segment": {},
                    # screener filters (surfaced in the UI) — forwarded to the screeners.
                    "screen_min_pct": 0.0,        # min |%change| (NSE movers)
                    "screen_min_quote_volume": 0.0,  # min quote volume (crypto)
                    # NSE options segment: how CE/PE candidates are generated —
                    # "atm" (ATM CE+PE) | "ladder" (ATM + OTM each side) | "chain" (whole chain).
                    "option_mode": "atm",
                    "sizing_method": "kelly_atr",
                    "max_risk_pct": 1.0, "max_position_pct": 25.0, "kelly_fraction": 0.5,
                    # 🤖 AI-Brain unlimited mode (operator toggle, PAPER-ONLY effect): the brain
                    # keeps learning without ever halting on limits — the paper wallet auto
                    # tops-up when cash runs short and per-position budget caps are lifted.
                    # OFF → the manual caps above rule. NEVER affects real-money paths.
                    "brain_unlimited": False}
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
    def _price(self, market: str, symbol: str, mode: str, segment: str = ""):
        m = market.upper()
        try:
            if m == "CRYPTO":
                # Prediction-market symbols (PRED:<slug>) have no ccxt ticker — their "price"
                # is the YES share price (0..1) from the prediction scanner's cache.
                if str(symbol).startswith("PRED:"):
                    from trading.screener.prediction import last_price
                    return last_price(symbol)
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
            # HARD UI-only (NSE_UI_ONLY, owner 2026-07-13, motto): the NSE price comes ONLY
            # from the Upstox web UI feed (ui_market ticker / captured candle close) — never
            # OpenAlgo. A miss is an honest None → the loop ABSTAINS on this symbol.
            from trading.broker_sense.ui_data import nse_ui_only
            if nse_ui_only():
                from trading.broker_sense import data_failsafe
                q = data_failsafe.quote(symbol, "nse")   # gated → ui_market/ui_data or None
                return float(q["last"]) if q and q.get("last") is not None else None
            if mode != "LIVE":
                return None                         # off-hours: no live NSE feed → skip
            if self.ticks < self._nse_skip_until:   # backing off after a broker-auth failure
                return None
            # Quote on the RIGHT exchange for this segment: equity→NSE, F&O→NFO,
            # commodities→MCX. Hardcoding "NSE" meant MCX commodities (GOLD/CRUDEOIL…) and
            # NFO futures/options were quoted on NSE, always failed → "no price" → those
            # segments never traded even while their market was open (commodities bug).
            oa_exch = self._oa_exch_for(symbol, segment)
            q = self._openalgo().quote(symbol, exchange=oa_exch)
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

    # ── OpenAlgo order routing (NSE) — sandbox in paper, real broker in live ──────────
    # OpenAlgo exchange code per segment (equity→NSE, F&O/options→NFO, commodities→MCX).
    _OA_EXCHANGE = {"intraday": "NSE", "mtf": "NSE", "delivery": "NSE",
                    "futures": "NFO", "fno": "NFO", "options": "NFO", "commodities": "MCX"}
    # BSE index derivatives live on the BFO exchange, not NFO — SENSEX/BANKEX options
    # (and futures) must be quoted + routed on BFO or every order 'not found' (2026-07-07).
    _BSE_FNO_PREFIXES = ("SENSEX", "BANKEX")

    def _oa_exch_for(self, symbol: str, segment: str) -> str:
        """OpenAlgo exchange for this symbol+segment — BFO for BSE index F&O, else the
        per-segment default (options/futures→NFO, equity→NSE, commodities→MCX)."""
        seg = (segment or "").lower()
        # explicit screener hint (set on BSE option candidates) wins
        overrides = getattr(self, "_symbol_oa_exchange", None) or {}
        for m in ("NSE", "CRYPTO"):
            ex = overrides.get((m, symbol))
            if ex:
                return ex
        if seg in ("options", "futures", "fno") and \
                str(symbol or "").upper().startswith(self._BSE_FNO_PREFIXES):
            return "BFO"
        return self._OA_EXCHANGE.get(seg, "NSE")
    # OpenAlgo product code (valid set MIS/CNC/NRML); MTF≈leveraged delivery→CNC.
    _OA_PRODUCT = {"MIS": "MIS", "MTF": "CNC", "CNC": "CNC", "NRML": "NRML"}

    def _openalgo(self):
        """Lazy OpenAlgoClient, synced ONCE so its analyzer (sandbox) matches TRADING_MODE
        (paper→sandbox ON, live→sandbox OFF). Reused by _price() and order routing."""
        if getattr(self, "_oa", None) is None:
            from trading.openalgo_client import OpenAlgoClient
            self._oa = OpenAlgoClient()
        if not getattr(self, "_oa_synced", False):
            try:
                self._oa.sync_mode()
                self._oa_synced = True
            except Exception:
                pass                          # server may be down; _submit_nse_order stays honest
        return self._oa

    def _submit_nse_order(self, symbol, action, segment, qty, product, *, allow_live) -> tuple:
        """Best-effort route an NSE order through OpenAlgo. Paper mode hits OpenAlgo's SANDBOX
        (no broker); live hits the real broker (guarded by allow_live). NEVER raises — returns
        (order_id, status) so the loop/journal stay honest when OpenAlgo is down/unconfigured."""
        from trading.config import trading_config
        # STRUCTURAL guard: a crypto-shaped symbol must NEVER reach the OpenAlgo/Kite door,
        # whatever upstream tagged it NSE (multi-market isolation, 2026-07-13).
        try:
            from trading.market_guard import assert_market_symbol, is_instrument_key
            assert_market_symbol("NSE", symbol)
            # a data-feed INSTRUMENT KEY (Upstox 'NSE_FO|51380') is not an OpenAlgo tradingsymbol
            # → it 404s ("not found on NSE"). Reject at the door so it never reaches the broker.
            if is_instrument_key(symbol):
                raise ValueError(f"instrument-key {symbol!r} is not a tradeable OpenAlgo symbol")
        except Exception as exc:
            self._note_error(f"blocked non-tradeable/cross-market NSE order: {str(exc)[:80]}")
            return "", f"blocked (bad symbol: {symbol})"
        if not trading_config.is_configured:
            return "", "sim-only (OpenAlgo not configured)"
        exch = self._oa_exch_for(symbol, segment)
        prod = self._OA_PRODUCT.get((product or "MIS").upper(), "MIS")
        try:
            resp = self._openalgo().place_order(
                symbol=symbol, action=str(action).upper(), exchange=exch,
                quantity=int(max(1, round(float(qty)))), product=prod,
                price_type="MARKET", allow_live=bool(allow_live))
            oid = str((resp or {}).get("orderid") or (resp or {}).get("order_id") or "")
            tag = "sandbox" if not trading_config.is_live else "live"
            return oid, (f"{tag}:{oid}" if oid else tag)
        except Exception as e:
            self._note_error(f"NSE order via OpenAlgo failed: {type(e).__name__}: {str(e)[:60]}")
            return "", f"sim-only ({type(e).__name__})"

    def _ingest_freqtrade(self) -> dict:
        """Record any new Freqtrade closed crypto trades into the journal (trade→NN bridge).
        Never raises.

        Runs regardless of the registry's CRYPTO enabled flag: that flag gates whether
        THIS loop may place crypto ORDERS (the funnel owns crypto trading, so it stays
        off), but ingest is read-only learning — gating it on the same flag silently
        starved the journal of every explore-mode closed trade (found 2026-07-09)."""
        from trading.crypto.freqtrade_ingest import ingest_closed
        res = ingest_closed(self.journal(), self._crypto_engine)
        if res.get("ingested"):
            self.trades_closed += int(res["ingested"])   # reflect crypto closes in the counters
        # D1 exit-horizon labels (2026-07-16): backfill_journal() had NO production caller,
        # so the truth ledger's `exit` bucket froze for 5 days while 3k+ trades closed.
        # This ingest seam is where closed trades ENTER the journal, so label them here:
        # after any ingest (throttled), and at worst every 2h even on quiet ticks.
        try:
            import os
            now = time.time()
            last = float(getattr(self, "_exit_backfill_ts", 0.0) or 0.0)
            min_gap = float(os.environ.get("EXIT_BACKFILL_MIN_S", "900") or 900)
            if (res.get("ingested") and now - last >= min_gap) or now - last >= 7200:
                self._exit_backfill_ts = now
                from trading.direction import truth_ledger
                bf = truth_ledger.backfill_journal(journal=self.journal())
                if bf.get("labeled"):
                    res["exit_labels"] = bf["labeled"]
        except Exception:
            pass                                         # labeling must never break the loop
        return res

    # ── Phase E: crypto execution is owned by Freqtrade (retire the home-grown wallet sim) ──
    def _crypto_engine_client(self):
        """The Freqtrade CryptoEngineClient — injected (tests) or lazily built. None if absent."""
        if self._crypto_engine is None:
            try:
                from trading.crypto.engine_client import CryptoEngineClient
                self._crypto_engine = CryptoEngineClient()
            except Exception:
                self._crypto_engine = False
        return self._crypto_engine or None

    def _crypto_exec_enabled(self) -> bool:
        """True when Freqtrade should own crypto execution: REST creds present AND reachable.
        Reachability + open-pairs are cached for ~12 ticks (don't ping every tick/symbol)."""
        try:
            from trading.crypto.config import crypto_config
            if not crypto_config.ft_configured:
                return False
        except Exception:
            return False
        if not hasattr(self, "_ft_reach") or getattr(self, "_ft_reach_tick", -999) + 12 <= self.ticks:
            eng = self._crypto_engine_client()
            self._ft_reach = bool(eng and eng.ping().connected)
            self._ft_reach_tick = self.ticks
            self._ft_open_pairs = set(eng.open_pairs()) if self._ft_reach else set()
        return self._ft_reach

    def flush_market(self, market: str) -> int:
        """Drop the loop's in-memory open-position entries for a market. MUST be called when the
        paper wallet is reset/re-based — otherwise the loop still believes the wiped positions
        are open (in_position=True) and never re-opens anything (observed 2026-07-02)."""
        market = market.upper()
        keys = [k for k in self._open if k.startswith(f"{market}:")]
        for k in keys:
            self._open.pop(k, None)
        return len(keys)

    def _ft_trading_mode(self) -> str:
        """Freqtrade's CURRENT trading_mode ('spot'|'futures') from the live config.json —
        the segment that routes to the engine; all other segments stay on the wallet paper
        path. Cached ~12 ticks (config.json is the truth; root config.settings is stale)."""
        if getattr(self, "_ftm_tick", -999) + 12 > self.ticks and hasattr(self, "_ftm"):
            return self._ftm
        mode = "futures"
        try:
            from trading.crypto.freqtrade.control import status as _ft_status
            mode = str(_ft_status().get("segment") or "futures").lower()
        except Exception:
            pass
        self._ftm, self._ftm_tick = mode, self.ticks
        return mode

    def _route_crypto_engine(self, symbol, seg, want_open, do_exit, decision) -> dict:
        """Route a crypto brain/momentum signal to Freqtrade. forceenter on entry, force-close on
        exit. crypto_options stays on the ccxt path (Freqtrade is spot/perp only). Never raises."""
        if (seg or "").lower() == "options":
            return {"skipped": "crypto_options on ccxt (Freqtrade = spot/perp only)"}
        # STRUCTURAL guard: an NSE-shaped symbol must never reach the crypto engine.
        try:
            from trading.market_guard import assert_market_symbol
            assert_market_symbol("CRYPTO", symbol)
        except Exception as exc:
            self._note_error(f"blocked cross-market crypto order: {str(exc)[:80]}")
            return {"blocked": f"cross-market: {symbol}"}
        eng = self._crypto_engine_client()
        if eng is None:
            return {"skipped": "engine unavailable"}
        open_pairs = getattr(self, "_ft_open_pairs", set())
        try:
            if want_open and symbol not in open_pairs:
                side = "short" if decision.get("action") == "SHORT" else "long"
                # DEEP-SCAN FIX (2026-07-17): this router placed with NO enter_tag, so its
                # trades landed as freqtrade's default "force_entry" — 318 of 633 clean closed
                # trades (the BEST-performing lane, 60.4% win) were invisible to per-source
                # attribution. The decision's own strategy/tag now travels with the order.
                _tag = str(decision.get("tag") or decision.get("strategy")
                           or (decision.get("_brain") or {}).get("source")
                           or "live_loop")[:60]
                eng.place_order(symbol=symbol, action="BUY", side=side, enter_tag=_tag)
                open_pairs.add(symbol)
                return {"forceenter": symbol, "side": side, "ok": True, "tag": _tag}
            if do_exit and symbol in open_pairs:
                eng.close_pair(symbol)
                open_pairs.discard(symbol)
                return {"forceexit": symbol, "ok": True}
        except Exception as e:
            self._note_error(f"crypto engine {symbol}: {type(e).__name__}: {str(e)[:50]}")
            return {"error": type(e).__name__}
        return {"noop": True, "open_in_engine": symbol in open_pairs}

    def _decide(self, market: str, symbol: str, price, *, in_position: bool) -> dict:
        if self._brain is not None:
            try:
                d = self._brain(market, symbol, price, in_position=in_position)
                if isinstance(d, dict) and d.get("action"):
                    if isinstance(d.get("_brain"), dict):
                        self._last_brain[symbol] = d["_brain"]   # for journal context
                    self._apply_decision_memory(symbol, d)
                    return self._apply_psychology(market, symbol, d, in_position=in_position)
            except Exception:
                pass
        d = self._momentum(market, symbol, price, in_position=in_position)
        # X14 (2026-07-18): the SMA fallback is STRUCTURALLY LONG-ONLY — it cannot return
        # SHORT at any price. Whenever the brain path is absent or throws, this lane
        # therefore fabricates a LONG regardless of what the market is doing. MEASURED
        # over 24h: the router opened 91% LONGs (606) vs 9% SHORTs while the brain funnel
        # beside it ran 68% SHORT on the same market; its wrong-from-start losses split
        # 141 LONG / 14 SHORT and cost −2,318 (49% of ALL wrong-direction losses).
        # CONVENTIONS §16 (direction must be EARNED): a side no evidence chose is not a
        # claim, so the fallback no longer OPENS. It still manages EXIT/FLAT, so open
        # positions stay protected when the brain is down. ROUTER_MOMENTUM_ENTRIES=1
        # restores the old long-only entries.
        if d.get("action") == "LONG" and not in_position and \
                os.getenv("ROUTER_MOMENTUM_ENTRIES", "0") not in ("1", "true", "yes", "on"):
            try:
                from trading.direction import truth_ledger as _x14tl
                _x14tl.record(symbol=symbol, market=market.upper(),
                              segment="futures" if market.upper() == "CRYPTO" else "equity",
                              direction="LONG", source="momentum_longonly_cut", taken=False)
            except Exception:
                pass
            d = {"action": "FLAT", "size": 0.0, "detail": "X14: long-only fallback stood down"}
        self._apply_decision_memory(symbol, d)
        return self._apply_psychology(market, symbol, d, in_position=in_position)

    def _apply_decision_memory(self, symbol: str, d: dict) -> None:
        """Episodic recall (trading/brain/decision_memory.py): the importance/recency-
        weighted win-rate of past RESOLVED episodes on this symbol+direction nudges the
        brain's confidence ±20%. Advisory only — never vetoes (psychology handles vetoes)."""
        try:
            if d.get("action") not in ("LONG", "SHORT"):
                return
            from trading.brain.decision_memory import get_memory
            b = get_memory().bias(symbol, d["action"])
            brain = d.get("_brain")
            if b["n"] >= 3 and isinstance(brain, dict) and brain.get("confidence") is not None:
                brain["confidence"] = float(min(1.0, max(0.0,
                    float(brain["confidence"]) * (1.0 + 0.2 * b["bias"]))))
                brain["memory_bias"], brain["memory_n"] = b["bias"], b["n"]
        except Exception:
            pass

    # crowd-psychology veto threshold: an entry whose direction the order-book crowd
    # opposes this strongly is skipped (full-signal mode; paper-safe)
    _PSYCH_VETO = 0.6

    def _apply_psychology(self, market: str, symbol: str, d: dict, *,
                          in_position: bool) -> dict:
        """Order-book trader psychology as a LIVE entry signal (trading/brain/psychology.py).

        Aligned crowd pressure boosts brain confidence, opposing pressure dampens it, and a
        strongly opposing crowd (|score| > _PSYCH_VETO against the trade) vetoes the entry.
        Exits/holds are never blocked. Best-effort: no depth → decision unchanged."""
        try:
            if in_position or d.get("action") not in ("LONG", "SHORT"):
                return d
            from trading.brain.psychology import get_engine
            seg = self._segment_of(market, symbol)
            exch = self._OA_EXCHANGE.get(seg, "NSE") if market.upper() == "NSE" else None
            psych = get_engine().evaluate(market, symbol, segment=seg, exchange=exch)
            if not psych:
                return d
            self._last_psych[f"{market.upper()}:{symbol}"] = psych
            sign = 1.0 if d["action"] == "LONG" else -1.0
            alignment = float(psych["trader_psychology"]) * sign
            brain = d.get("_brain")
            if isinstance(brain, dict) and brain.get("confidence") is not None:
                brain["confidence"] = float(min(1.0, max(0.0,
                    float(brain["confidence"]) * (1.0 + 0.3 * alignment))))
                brain["psych_alignment"] = round(alignment, 4)
            d["_psych"] = psych
            if alignment < -self._PSYCH_VETO:
                return {"action": "FLAT", "size": 0.0, "_brain": brain, "_psych": psych,
                        "psych_veto": f"crowd opposes {d['action']} "
                                      f"(psych={psych['trader_psychology']})"}
            return d
        except Exception:
            return d

    # map a (market, symbol) to its trade-type segment (default watchlist; Phase 2 tags
    # screened symbols with their real segment).
    _SEG_DEFAULT = {"CRYPTO": "spot", "NSE": "intraday"}

    def _segment_of(self, market: str, symbol: str) -> str:
        return self._symbol_segments.get((market.upper(), symbol),
                                         self._SEG_DEFAULT.get(market.upper(), ""))

    # per-segment leverage (paper, honest defaults). 1.0 = unleveraged (spot/CNC delivery).
    _LEVERAGE = {("CRYPTO", "spot"): 1.0, ("CRYPTO", "futures"): 3.0, ("CRYPTO", "options"): 1.0,
                 ("CRYPTO", "prediction"): 1.0,     # YES/NO shares 0..1 — no leverage, ever
                 ("NSE", "intraday"): 5.0, ("NSE", "mtf"): 4.0, ("NSE", "delivery"): 1.0,
                 ("NSE", "futures"): 5.0, ("NSE", "fno"): 5.0, ("NSE", "options"): 1.0,
                 ("NSE", "commodities"): 5.0}
    # MAX leverage allowed per segment in LIVE markets — user overrides are clamped to these.
    #   NSE equity intraday ≈5× (post-SEBI peak-margin); MTF ≈5×; index/stock futures ≈10×;
    #   MCX commodities ≈10×; long options/spot = 1× (no margin leverage); crypto perp up to
    #   the Binance USDⓢ-M ceiling 125× (research: crypto-futures-perp). Honest live caps.
    #   crypto SPOT margin up to 5× (Binance cross/isolated margin borrowing).
    # MARKET-AWARE so NSE `futures` (≤10×) never inherits crypto `futures` (125×).
    _MAX_LEVERAGE = {
        ("NSE", "intraday"): 5.0, ("NSE", "mtf"): 5.0, ("NSE", "delivery"): 1.0,
        ("NSE", "futures"): 10.0, ("NSE", "fno"): 10.0, ("NSE", "options"): 1.0,
        ("NSE", "commodities"): 10.0,
        ("CRYPTO", "spot"): 5.0, ("CRYPTO", "futures"): 125.0, ("CRYPTO", "options"): 1.0,
        ("CRYPTO", "prediction"): 1.0,
    }

    def max_leverage_of(self, segment: str, market: str = "NSE") -> float:
        return float(self._MAX_LEVERAGE.get((market.upper(), (segment or "").lower()), 10.0))

    def _leverage_of(self, market: str, segment: str) -> float:
        """Per-segment leverage — the user override (cfg['leverage_by_segment']) if set, else
        the built-in default. Segment names are unique across markets so a flat dict is safe."""
        seg = (segment or "").lower()
        by = self.cfg.get("leverage_by_segment") or {}
        if isinstance(by, dict) and seg in by:
            try:
                return max(1.0, min(float(by[seg]), self.max_leverage_of(seg, market)))
            except (TypeError, ValueError):
                pass
        return float(self._LEVERAGE.get((market.upper(), seg), 1.0))

    def _session_for(self, market: str, segment: str) -> MarketSession:
        """Per-segment market session. NSE commodities (MCX) get a LATER session window
        (≈09:00–23:30 IST) instead of equity hours, so the bot doesn't treat them as closed
        at 15:30 like the other NSE segments."""
        m = market.upper()
        is_comm = (m == "NSE" and (segment or "").lower() == "commodities")
        key = f"{m}:COMMODITIES" if is_comm else m
        s = self._sessions.get(key)
        if s is None:
            s = MarketSession(market, commodities=is_comm)
            self._sessions[key] = s
        return s

    def _holds_overnight(self, market: str, segment: str) -> bool:
        """Can this trade type be carried overnight? Crypto is 24/7; NSE intraday (MIS)
        MUST be squared off by market close — everything else (delivery/mtf/fno/commodities)
        carries. Drives the at-close square-off (research: online-nse-offhours-paper-trading)."""
        if market.upper() == "CRYPTO":
            return True
        return (segment or "").lower() != "intraday"

    # map a trade segment → the charges.py NSE segment key (eq_intraday/eq_delivery/fut/opt).
    _CHARGE_SEG = {"intraday": "eq_intraday", "mtf": "eq_delivery", "delivery": "eq_delivery",
                   "fno": "fut", "futures": "fut", "commodities": "fut", "options": "opt"}

    def _est_charges(self, market: str, segment: str, notional: float) -> float:
        """Estimated ROUND-TRIP transaction cost for an open trade (entry+exit), so the
        dashboard can show a Fees column. Reuses trading/journal/charges.py (the same math
        that finalises closed trades). Best-effort: 0.0 if anything is off."""
        try:
            from trading.journal import charges as _ch
            if market.upper() == "CRYPTO":
                return float(_ch.crypto_charges(entry_notional=notional,
                                                exit_notional=notional)["total_charges"])
            seg = self._CHARGE_SEG.get((segment or "").lower(), "eq_intraday")
            return float(_ch.nse_charges(seg, buy_value=notional,
                                         sell_value=notional)["total_charges"])
        except Exception:
            return 0.0

    # ── brain handoff: manual sliders now → brain takes over once it has learned ──────
    def brain_in_control(self) -> bool:
        """True once the brain decider is wired AND the journal has enough CLOSED trades
        to have learned from (>= cfg['brain_handoff_trades']). Until then trading follows
        the operator's manual Strategy & Sizing settings (and the auto-open basket)."""
        try:
            need = int(self.cfg.get("brain_handoff_trades", 30) or 0)
        except Exception:
            need = 30
        return bool(self._brain is not None and need > 0 and self.trades_closed >= need)

    def _screen_filters(self) -> dict:
        """Build the screener filter dict from the user-tunable config (UI filter bar)."""
        f = {}
        try:
            mp = float(self.cfg.get("screen_min_pct", 0.0) or 0.0)
            if mp > 0:
                f["min_pct_change"] = mp
            mv = float(self.cfg.get("screen_min_quote_volume", 0.0) or 0.0)
            if mv > 0:
                f["min_quote_volume"] = mv
        except Exception:
            pass
        # NSE options CE/PE generation mode → forwarded to screen_nse_options.
        f["option_mode"] = str(self.cfg.get("option_mode", "atm") or "atm").lower()
        return f

    # ── auto-open basket (manual phase) ──────────────────────────────────────────────
    def _auto_open_active(self) -> bool:
        """Basket auto-open runs while the operator is in control (enter_all on) and the
        brain has NOT yet taken over. Once the brain is in control its own LONG signals
        drive entries (and this stays off)."""
        return bool(self.cfg.get("enter_all")) and not self.brain_in_control()

    def _min_open_for(self, seg: str) -> int:
        """Per-segment min-open floor: the explicit override for this segment if set,
        else the global default (min_open_per_segment)."""
        by = self.cfg.get("min_open_by_segment") or {}
        if isinstance(by, dict) and seg in by:
            try:
                return int(by[seg] or 0)
            except (TypeError, ValueError):
                pass
        return int(self.cfg.get("min_open_per_segment", 0) or 0)

    def _segment_open_count(self, market: str, seg: str) -> int:
        return sum(1 for ot in self._open.values()
                   if ot.get("market") == market.upper() and (ot.get("segment") or "") == seg)

    def _is_top_ranked(self, market: str, symbol: str, seg: str, n: int) -> bool:
        syms = [s for s in (self.symbols.get(market) or [])
                if self._segment_of(market, s) == seg]
        syms.sort(key=lambda s: self._symbol_score.get((market.upper(), s), 0.0), reverse=True)
        return symbol in syms[:max(1, n)]

    def _basket_wants(self, market: str, symbol: str, seg: str) -> bool:
        """Open this screened symbol now? PRIMARY = the top-N ranked per segment; FALLBACK =
        if the segment has fewer than `min_open_per_segment` open positions, keep opening
        screened candidates until that floor is filled (operator's two-tier request)."""
        if not seg:
            return False
        # GLOBAL floor: keep opening best-ranked screened candidates until the total number
        # of open trades reaches min_total_open (across all markets/segments).
        if len(self._open) < int(self.cfg.get("min_total_open", 0) or 0):
            return True
        count = self._segment_open_count(market, seg)
        floor = self._min_open_for(seg)
        topn = int(self.cfg.get("top_n_per_segment", 2) or 0)
        if count < floor:
            return True                                  # fallback: fill segment to the minimum
        if topn > 0 and count < topn and self._is_top_ranked(market, symbol, seg, topn):
            return True                                  # primary: open the top-N ranked
        return False

    def close_all(self, *, reason: str = "manual close-all") -> dict:
        """Flatten EVERY open position at the last known mark (operator 'close all' button).
        Journals each close like any normal exit. Returns a summary."""
        closed = []
        for key, ot in list(self._open.items()):
            market, sym = ot.get("market", ""), ot.get("symbol", "")
            mark = self._marks.get(market, {}).get(sym, ot.get("entry_price"))
            res = self._close_trade(market, sym, mark, ot.get("mode", "LIVE"))
            if isinstance(res, dict) and res.get("ok"):
                res["exit_reason"] = reason
                closed.append({"symbol": sym, "market": market, **res})
        return {"ok": True, "closed": len(closed), "trades": closed}

    def _square_off_intraday(self, when=None) -> list[dict]:
        """Force-flat NSE INTRADAY (MIS) positions once the market is closed — they cannot
        be carried overnight. Overnight-allowed trade types (delivery/mtf/fno/commodities)
        and crypto (24/7) are left to hold. Closes at the last known mark."""
        done = []
        for key, ot in list(self._open.items()):
            market = ot.get("market", "")
            if market == "CRYPTO" or ot.get("holds_overnight", True):
                continue
            sess = self._session_for(market, ot.get("segment"))
            if sess.is_open(when):
                continue                                 # market open → normal exit handling
            mark = self._marks.get(market, {}).get(ot["symbol"], ot["entry_price"])
            res = self._close_trade(market, ot["symbol"], mark, "REPLAY")
            if isinstance(res, dict) and res.get("ok"):
                res["exit_reason"] = "market-close square-off (intraday)"
                done.append({"symbol": ot["symbol"], "market": market, **res})
        return done

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
        _str_keys = ("sizing_method", "trail_mode", "exit_mode", "option_mode")
        _int_keys = ("top_n_per_segment", "min_open_per_segment", "min_total_open",
                     "brain_handoff_trades")
        _bool_keys = ("enter_all", "brain_unlimited")
        for k, v in kw.items():
            if k in self.cfg and v is not None:
                if k in ("min_open_by_segment", "leverage_by_segment", "lot_size_by_segment"):
                    # {segment: number} — coerce values, drop blanks/invalid.
                    # Keys pass through normalize_segment so legacy 'fno' entries land on
                    # 'futures' instead of a dead key the floor lookup never reads.
                    from trading.online.state import normalize_segment
                    if isinstance(v, dict):
                        clean = {}
                        for seg, n in v.items():
                            seg = normalize_segment(str(seg))
                            try:
                                if k == "min_open_by_segment":
                                    clean[str(seg)] = max(0, int(float(n)))
                                elif k == "lot_size_by_segment":
                                    clean[str(seg)] = max(1, int(float(n)))
                                else:   # leverage: clamp to [1, per-segment live max]
                                    clean[str(seg)] = max(1.0, min(float(n),
                                                                   self.max_leverage_of(seg)))
                            except (TypeError, ValueError):
                                continue
                        self.cfg[k] = clean
                elif k in _str_keys:
                    self.cfg[k] = str(v)
                elif k in _bool_keys:
                    self.cfg[k] = bool(v) if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
                elif k in _int_keys:
                    self.cfg[k] = max(0, int(float(v)))
                else:
                    self.cfg[k] = float(v)
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

    # Floor the ATR proxy at a fraction of price so the trailing stop is never absurdly tight:
    # raw 5s-tick true-range decays toward ~0 on flat ticks, which made positions stop out in
    # seconds (so "open trades" looked empty). 0.4% floor → ~1% stop at 2.5×ATR, keeping
    # positions open through normal noise.
    _ATR_FLOOR = 0.004

    def _update_atr(self, symbol: str, price: float) -> float:
        """Cheap EMA True-Range proxy per symbol (for sizing + ATR trailing), floored so the
        trailing stop stays sane on slow/flat real ticks."""
        a = self._atr.get(symbol)
        ema = price * 0.006 if a is None else 0.9 * a["atr"] + 0.1 * abs(price - a["prev"])
        atr = max(ema, price * self._ATR_FLOOR)
        self._atr[symbol] = {"atr": atr, "prev": price}
        return atr

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
            # Watchlist depth is config-driven so the loop can actually hold the whole
            # tradeable universe — the liquid intraday equity list AND every index's
            # options at once. The old per_segment=6 / [:16] caps truncated options to
            # 4 (dropping FinNifty/Sensex) and left almost no room for equity, which is
            # why only NIFTY options ever opened (2026-07-07 fix).
            # Bounded so the in-process loop can't GIL-starve the dashboard HTTP server
            # (memory: dashboard-524-wedge). 14/segment fits all 6 index-option pairs (12)
            # + a liquid equity slice, and keeps per-tick OpenAlgo pricing under the tick
            # interval. Raise via watchlist_per_segment only if the loop runs standalone.
            per_seg = int(self.cfg.get("watchlist_per_segment") or 14)
            cap = int(self.cfg.get("watchlist_cap")
                      or max(42, per_seg * max(1, len(segs)) + 6))
            try:
                wl = sc.watchlist(market, segs, per_segment=per_seg,
                                  filters=self._screen_filters())
            except Exception:
                continue
            syms = []
            for c in wl:
                sym, seg = c.get("symbol"), c.get("segment")
                if sym:
                    syms.append(sym)
                    self._symbol_segments[(market.upper(), sym)] = seg
                    self._symbol_score[(market.upper(), sym)] = float(c.get("score") or 0.0)
                    meta = c.get("metrics") or {}
                    if meta.get("oa_exchange"):       # BSE options → route on BFO
                        self._symbol_oa_exchange[(market.upper(), sym)] = meta["oa_exchange"]
            if syms:
                self.symbols[market] = syms[:cap]    # cap the per-market watchlist

    # ── one tick ─────────────────────────────────────────────────────────────────────
    def tick(self, *, when=None) -> dict:
        self.ticks += 1
        # periodically re-screen the watchlist (skip tick 1 so seeding is offline-friendly)
        if self._refresh_every and self.ticks > 1 and self.ticks % self._refresh_every == 0:
            try:
                self._refresh_watchlist()
            except Exception:
                pass
        # Phase D: pull Freqtrade's CLOSED crypto trades into the journal so the trade→NN bridge
        # keeps learning from crypto (idempotent; only when CRYPTO is enabled). Best-effort.
        if self._ingest_every and self.ticks % self._ingest_every == 0:
            try:
                self._ingest_freqtrade()
            except Exception:
                pass
        # square off NSE intraday (MIS) positions when the market is closed (overnight types hold)
        squared = []
        try:
            squared = self._square_off_intraday(when)
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
            sess = self._session_for(market, seg)
            mode = sess.mode(when)
            price = self._price(market, symbol, mode, seg)
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
                # far TAKE-PROFIT cap — book the trade only on a big win (lets it run long)
                tp = float(self.cfg.get("take_profit_pct", 0.0) or 0.0)
                cap = ot.get("capital") or (ot["entry_price"] * ot["quantity"])
                if tp > 0 and cap and (upnl / cap) >= tp:
                    trail_exit = trail_exit or "take-profit"
                # PROFIT TAILGATE on EVERY trade (owner goal 2026-07-07: "profit tailgating
                # for every crypto and nse trades") — the shared brain-learned ratchet:
                # lock a rising floor under the peak profit%, exit when profit falls to it.
                # Columns (tailgate_*) are stamped on the open trade here and carried to
                # the journal row at close by _close_trade.
                try:
                    from trading.execution import profit_tailgate as _pt
                    if cap:
                        _ppct = upnl / cap * 100.0
                        _peak = max(ot.get("tailgate_peak_profit_pct") or 0.0, _ppct)
                        ot["tailgate_peak_profit_pct"] = round(_peak, 4)
                        _dec = _pt.locked_profit(market.lower(), (seg or "equity"),
                                                 trade_id=str(ot.get("trade_id") or key),
                                                 profit_pct=_ppct, peak_profit_pct=_peak)
                        ot["tailgate_locked_profit_pct"] = _dec.get("locked_profit_pct")
                        ot["tailgate_distance_pct"] = round(
                            _dec.get("distance_pct", 0) * 100, 2)
                        # exit on the RATCHET's own decision — the same locked value the
                        # table shows. A separate should_exit() recomputes peak×(1−dist)
                        # fresh, which sits BELOW a ratcheted lock once the learned dist
                        # loosens — trades touched their displayed lock without exiting.
                        if _dec.get("exit"):
                            trail_exit = trail_exit or "profit-tailgate"
                            ot["tailgate_triggered"] = True
                            ot["tailgate_captured_pct"] = round(_ppct, 4)
                except Exception:
                    pass
                # D-EXIT (Pillar 27): cut when the CALIBRATED direction read has flipped
                # against the open position — the tailgate only manages winners, so a
                # trade that went underwater has no directional stop. Crypto-native lanes;
                # shadow by default (records a "dir_exit" claim + advisory, no forced exit
                # unless DIR_EXIT=trade). Runs alongside the tailgate as a trail source.
                if not trail_exit and market.upper() == "CRYPTO":
                    try:
                        from trading.direction import dir_exit
                        _de = dir_exit.evaluate(
                            symbol=symbol, direction=ot["direction"], market="CRYPTO",
                            segment=(seg or "futures"), ref_price=price,
                            trade_id=str(ot.get("trade_id") or key))
                        if _de.get("exit"):
                            trail_exit = "dir-exit"
                            ot["dir_exit_reason"] = _de.get("reason")
                    except Exception:
                        pass
            decision = self._decide(market, symbol, price, in_position=in_pos)
            action = decision.get("action", "FLAT")
            size = float(decision.get("size", 1.0))
            # EXIT policy: when a position has a trailing stop attached, let the TRAILING STOP
            # manage the exit (ride the trend) — don't flip out on every SMA dip. The momentum
            # EXIT only applies as a fallback when there's no trailing engine. This keeps
            # positions open meaningfully (observable) instead of scalping out in seconds.
            has_trail = in_pos and self._open.get(key, {}).get("trail") is not None
            do_exit = bool(trail_exit) or (action == "EXIT" and not has_trail)
            # AUTO-OPEN: open on a momentum/brain LONG, OR (manual phase) when the basket
            # wants this screened candidate — top-N ranked per segment + min-open-floor fill.
            want_open = (action == "LONG")
            if not in_pos and not want_open and not do_exit and self._auto_open_active():
                want_open = self._basket_wants(market, symbol, seg)
            reduces = do_exit
            gate = self.registry.allow_order(market, reduces_position=reduces, is_real=ms.is_real)
            routed = None
            # Phase F+: ONE Freqtrade instance runs in ONE trading_mode (spot OR futures) — route
            # to it ONLY the segment matching that mode. Every other selected crypto segment
            # (spot-while-bot-is-futures, options, prediction) trades on the wallet PAPER path so
            # all 4 segments can run at once on the shared wallet. Previously all non-options
            # crypto went to Freqtrade, so SPOT signals hit the FUTURES bot and silently no-op'd.
            if (market.upper() == "CRYPTO" and (seg or "").lower() == self._ft_trading_mode()
                    and gate["ok"] and self._crypto_exec_enabled()):
                routed = self._route_crypto_engine(symbol, seg, want_open, do_exit, decision)
                results.append({"market": market, "mode": mode, "price": round(price, 4),
                                "action": action, "engine": "freqtrade", "routed": routed})
                continue
            if ms.is_real:
                # paper-only execution by operator choice: honour the gate but never place real orders
                routed = {"mode": "REAL", "blocked": True,
                          "detail": "real-money execution disabled (paper-only build)"}
            elif want_open and not in_pos and gate["ok"]:
                routed = self._open_trade(market, symbol, "LONG", price, size, mode, atr=atr,
                                          brain=decision.get("_brain"))
            elif do_exit and in_pos and gate["ok"]:
                routed = self._close_trade(market, symbol, price, mode)
                if isinstance(routed, dict):
                    routed["exit_reason"] = trail_exit or "momentum"
            results.append({"market": market, "mode": mode, "price": round(price, 4),
                            "action": action, "in_position": in_pos,
                            "gate_ok": gate["ok"], "routed": routed})
        self.last_tick = {"tick": self.ticks, "results": results,
                          "squared_off": squared,
                          "auto_open": self._auto_open_active(),
                          "control": "BRAIN" if self.brain_in_control() else "MANUAL"}
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
            uq = brain.get("uq") if isinstance(brain, dict) else None
            out = sz.size(capital=cap, entry_price=float(price), atr=atr, side=direction,
                          prob=prob, market=market.upper(), uq=uq)
            qty = abs(float(out.get("qty") or 0.0))
            return qty if qty > 0 else None
        except Exception:
            return None

    def _make_trail(self, direction, price, atr):
        """P3: attach the direction-aware WIDE trailing STOP for the position — a percentage
        trail by default (rides up, predictable width) so trades hold; ATR mode optional."""
        try:
            from trading.exits import make_exit
            purpose = "stop" if direction == "LONG" else "loss"
            side = "long" if direction == "LONG" else "short"
            if self.cfg.get("trail_mode", "pct") == "atr":
                return make_exit(side, purpose, entry_price=float(price), mode="atr",
                                 atr_mult=float(self.cfg.get("trail_atr_mult", 2.5)))
            return make_exit(side, purpose, entry_price=float(price), mode="pct",
                             trail_pct=float(self.cfg.get("trail_pct", 0.035)))
        except Exception:
            return None

    # ── real market-context snapshot AT ENTRY (cached, guarded, offline-safe) ──────────
    _CTX_CACHE: dict = {}        # key -> (monotonic_ts, value)

    def _ctx_cached(self, key: str, ttl: float, fn):
        """Memoise a possibly-network context value for `ttl` seconds (best-effort)."""
        hit = self._CTX_CACHE.get(key)
        now = time.monotonic()
        if hit and (now - hit[0]) < ttl:
            return hit[1]
        try:
            val = fn()
        except Exception:
            val = None
        self._CTX_CACHE[key] = (now, val)
        return val

    def _entry_context(self, market: str, symbol: str, brain) -> dict:
        """Snapshot the REAL market context at entry → the journal's context columns.
        Each source is cached + guarded so an entry never blocks or fails on the network.
        india_vix/nifty stay None (no free live source per blueprint) — honest."""
        is_crypto = market.upper() == "CRYPTO"
        ctx: dict = {}
        # crypto Fear & Greed (free, no key) — hourly cache
        ctx["fear_greed_index"] = self._ctx_cached("fng", 3600, lambda: float(
            __import__("trading.advintel.onchain", fromlist=["OnChainMetrics"])
            .OnChainMetrics().fear_greed().get("value")))
        # BTC reference price — from a live mark if we have one, else a 60s-cached ticker
        btc = (self._marks.get("CRYPTO", {}) or {}).get("BTC/USDT")
        if btc is None:
            btc = self._ctx_cached("btc", 60, lambda: float(
                __import__("trading.crypto.exchange_client", fromlist=["ExchangeClient"])
                .ExchangeClient("binance").ticker("BTC/USDT").get("last")))
        ctx["btc_price_entry"] = btc
        if is_crypto:
            # perp funding rate (None for SPOT — honest) — 5-min cache
            ctx["funding_rate_entry"] = self._ctx_cached(
                f"fund:{symbol}", 300, lambda: float(
                    __import__("trading.crypto.funding", fromlist=["FundingMonitor"])
                    .FundingMonitor().fetch(symbol, "binance").get("funding_rate")))
            vol = self._ctx_cached(f"vol:{symbol}", 60, lambda: float(
                __import__("trading.crypto.exchange_client", fromlist=["ExchangeClient"])
                .ExchangeClient("binance").ticker(symbol).get("baseVolume")))
            ctx["volume_entry"] = vol
        if isinstance(brain, dict):
            rc = brain.get("regime_confidence", brain.get("recall_confidence"))
            if rc is not None:
                ctx["regime_confidence"] = float(rc)
        return ctx

    def _instrument_product(self, market: str, segment: str) -> tuple[str, str]:
        """Map the screened SEGMENT → (instrument, product) so trade_type/leverage/charges
        reflect the real trade class (intraday MIS · MTF · delivery CNC · F&O · crypto perp)."""
        m, s = market.upper(), (segment or "").lower()
        if m == "CRYPTO":
            return {"spot": ("SPOT", "SPOT"), "futures": ("PERP", "PERP"),
                    "options": ("OPT", "OPT")}.get(s, ("SPOT", "SPOT"))
        return {"intraday": ("EQ", "MIS"), "mtf": ("EQ", "MTF"), "delivery": ("EQ", "CNC"),
                "futures": ("FUT", "NRML"), "fno": ("FUT", "NRML"), "commodities": ("FUT", "NRML"),
                "options": ("OPT", "NRML")}.get(s, ("EQ", "MIS"))

    # FALLBACK lot sizes for lot-based NSE segments (tunable via cfg['lot_size_by_segment']),
    # used only when OpenAlgo's real per-symbol lotsize is unavailable. Real lots vary per
    # underlying and change on expiry — the master-contract lookup in _lot_size_of is truth.
    _DEFAULT_LOT = {"futures": 50, "fno": 50, "options": 50, "commodities": 100}

    def _is_lot_based(self, market: str, segment: str) -> bool:
        """F&O / options / commodities trade in whole LOTS (qty = num_lots × lot_size).
        Equity is whole shares (lot 1); crypto is continuous (fractional, no lot rounding)."""
        return market.upper() == "NSE" and (segment or "").lower() in (
            "futures", "fno", "options", "commodities")

    def _lot_size_of(self, market: str, segment: str, symbol: str | None = None) -> int:
        """Lot size: REAL per-symbol lotsize from OpenAlgo's master contract → user
        override → representative default. 1 for equity.

        The real lookup matters: exchanges revise lots on rollover (NIFTY 65 ·
        BANKNIFTY 30 as of Jul-2026) and OpenAlgo's sandbox REJECTS any F&O order
        whose qty isn't a lot multiple — the segment-level guess (50) meant every
        NFO entry bounced with "Quantity must be in multiples of lot size"."""
        seg = (segment or "").lower()
        if not self._is_lot_based(market, seg):
            return 1
        if symbol:
            try:
                exch = self._OA_EXCHANGE.get(seg, "NSE")
                real = self._openalgo().lot_size(symbol, exch)
                if real and real > 0:
                    return int(real)
            except Exception:
                pass                       # server down/unconfigured → fall back below
        by = self.cfg.get("lot_size_by_segment") or {}
        if isinstance(by, dict) and seg in by:
            try:
                return max(1, int(float(by[seg])))
            except (TypeError, ValueError):
                pass
        return int(self._DEFAULT_LOT.get(seg, 1))

    def _assess_uq(self, market, symbol, direction, brain) -> dict | None:
        """Pillar 17: conformal p_up/interval/abstention for THIS candidate entry.
        Stored on the brain dict so it reaches the decision snapshot + journal
        columns. Best-effort — a UQ failure never blocks the loop (degraded)."""
        try:
            from trading.uq import get_uq
            b = brain if isinstance(brain, dict) else {}
            psych = self._last_psych.get(f"{market.upper()}:{symbol}") or {}
            uq = get_uq().assess(
                confidence=b.get("confidence"), direction=direction,
                market=market.upper(), psych=psych.get("trader_psychology"),
                longs=b.get("longs"), shorts=b.get("shorts"), symbol=symbol)
            if isinstance(brain, dict):
                brain["uq"] = uq
            return uq
        except Exception:
            return None

    def _open_trade(self, market, symbol, direction, price, size, mode, *, atr=None, brain=None) -> dict:
        is_crypto = market.upper() == "CRYPTO"
        seg = self._segment_of(market, symbol)
        # Pillar 17: the calibrated abstention gate is the FIRST check before any
        # capital math — an abstention is a first-class decision, logged by TradeUQ.
        uq = self._assess_uq(market, symbol, direction, brain)
        if uq and uq.get("abstain"):
            return {"ok": False, "abstain": True,
                    "detail": f"UQ abstain: {uq.get('abstain_reason')}"}
        # X13 (2026-07-18): COST GATE for the ROUTER lane. X12 raised the gate to
        # lambda×cost but both call sites live in the funnel's learned_direction path —
        # this lane, the measured biggest bleeder (live_loop −76 per 3h), never cost-checked
        # at all. Same gate, same counterfactual discipline: refusals record a
        # live_loop_costcut claim so the ledger adjudicates whether the gate helps.
        # Crypto only (fees here are the measured 31%-of-losses drag); p_up from the UQ
        # assessment, else brain confidence; missing probability → no gate (fail-open).
        if is_crypto and os.getenv("ROUTER_COST_GATE", "1") in ("1", "true", "yes", "on"):
            _p = (uq or {}).get("p_up")
            if _p is None:
                _p = (brain or {}).get("confidence")
            try:
                _p = float(_p) if _p is not None else None
            except (TypeError, ValueError):
                _p = None
            if _p is not None:
                try:
                    from trading.direction import learned_direction as _rld
                    _rcg = _rld.cost_gate(_p, symbol=symbol,
                                          horizon=str((brain or {}).get("horizon") or "1h"))
                    if not _rcg.get("pass"):
                        try:                    # counterfactual — the labeler scores it
                            from trading.direction import truth_ledger as _rtl
                            _rtl.record(symbol=symbol, market=market.upper(),
                                        segment=seg or "futures", direction=direction,
                                        source="live_loop_costcut", confidence=_p,
                                        taken=False)
                        except Exception:
                            pass
                        return {"ok": False, "abstain": True,
                                "detail": f"cost-gate: EV {_rcg.get('ev_bps')}bps under "
                                          f"{_rcg.get('lambda')}x cost {_rcg.get('cost_bps')}bps"}
                except Exception:
                    pass                        # fail-open like every other router guard
        # loss cooldown: don't re-enter the SAME symbol in the SAME direction right after
        # a losing close (revenge-loop guard); flipping direction is a new claim and allowed
        try:
            import os as _os
            _cd_min = float(_os.getenv("LOOP_LOSS_COOLDOWN_MIN", "45") or 0)
        except (TypeError, ValueError):
            _cd_min = 45.0
        if _cd_min > 0:
            _t0 = self._loss_cooldown.get(f"{market.upper()}:{symbol}:{direction}")
            if _t0 and (time.time() - _t0) < _cd_min * 60:
                return {"ok": False, "abstain": True,
                        "detail": f"loss-cooldown: {symbol} {direction} "
                                  f"{int((_cd_min * 60 - (time.time() - _t0)) / 60)}m left"}
        # D1/D2/D9 (Pillar 27): every NSE/options/BSE entry is a directional claim —
        # record it for fixed-horizon truth labeling and pass it through the Mirror
        # Gate (invert reliably-wrong sources / skip proven coin-flips). CE/PE map to
        # the underlying's LONG/SHORT inside record(). Never raises.
        try:
            from trading.direction import mirror_gate as _dmg
            _src = str((brain or {}).get("tag") or (brain or {}).get("source")
                       or (brain or {}).get("strategy") or "live_loop")[:80]
            _gd, _gi = _dmg.apply(direction, source=_src, symbol=symbol,
                                  market=market.upper(), segment=seg or "equity",
                                  confidence=(brain or {}).get("confidence"))
            if _gd is None:
                return {"ok": False, "abstain": True,
                        "detail": f"mirror-gate abstain: {_src} is a proven coin-flip"}
            direction = _gd
            from trading.direction import truth_ledger as _dtl
            _dtl.record(symbol=symbol, market=market.upper(),
                        segment=seg or "equity", direction=direction, source=_src,
                        confidence=(brain or {}).get("confidence"), taken=True,
                        ref_price=float(price) if price else None)
        except Exception:
            pass
        instrument, product = self._instrument_product(market, seg)
        leverage = self._leverage_of(market, seg)
        # P4: size the trade with the PositionSizer (capital, ATR-stop, edge) — not a fixed 1.
        size = self._size_trade(market, symbol, direction, price, atr, brain) or size
        w = self.book.wallet(market)
        # MINIMUM CAPITAL per trade (interpreted as min MARGIN) → bump size to meet it,
        # then cap by available cash so the basket can't over-deploy (budget guard).
        try:
            cash = float(w.cash())
        except Exception:
            cash = 0.0
        min_cap = float(self.cfg.get("min_capital_per_trade", 0.0) or 0.0)
        if price > 0:
            if min_cap > 0 and price * size < min_cap * leverage:
                size = (min_cap * leverage) / price            # ≥ min margin
            # 🤖 brain_unlimited (PAPER only): never halt learning on a cash shortfall — the
            # paper wallet auto-tops-up the missing margin instead of shrinking/skipping the
            # trade. Deposits are visible in the wallet ledger (honest sim, not silent money).
            need = (price * size) / max(leverage, 1e-9)
            if (self.cfg.get("brain_unlimited") and mode != "REAL"
                    and cash < need and price > 0):
                try:
                    w.top_up(round(need - max(cash, 0.0) + 1.0, 2))
                    cash = float(w.cash())
                except Exception:
                    pass
            if cash > 0 and price * size > cash * leverage:
                size = (cash * leverage) / price               # ≤ affordable margin
        # LOT SIZING: F&O / options / commodities trade in whole lots; equity in whole shares;
        # crypto stays fractional. num_lots × lot_size = the order quantity.
        lot = self._lot_size_of(market, seg, symbol)
        num_lots = None
        if self._is_lot_based(market, seg):
            num_lots = int(size // lot)                        # whole lots only
            if num_lots < 1:
                # round UP to 1 lot only if affordable (margin ≤ cash), else can't trade it
                one_lot_margin = (lot * price) / leverage if leverage else lot * price
                if cash <= 0 or one_lot_margin <= cash:
                    num_lots = 1
                else:
                    return {"ok": False,
                            "detail": f"1 lot ({lot}×{symbol}) needs {one_lot_margin:.0f} > cash {cash:.0f}"}
            size = num_lots * lot
        elif not is_crypto:
            size = float(int(size))                            # NSE equity = whole shares
            if size < 1:
                size = 1.0
        if size <= 0:
            return {"ok": False, "detail": "no size / insufficient capital"}
        try:
            # crypto engine genuinely reserves margin (= notional/leverage); NSE is a cash ledger
            w.record_fill(symbol, "buy" if direction == "LONG" else "sell", size, price,
                          leverage=leverage)
        except Exception as e:
            return {"ok": False, "detail": str(e)[:80]}
        # Route NSE entries through OpenAlgo (sandbox in paper, real broker when armed); crypto
        # stays on the wallet ledger until Phase E (Freqtrade). Best-effort — wallet is truth.
        entry_order_id, broker_status = "", "paper-wallet"
        if not is_crypto:
            ms = self.registry.get(market)
            entry_order_id, broker_status = self._submit_nse_order(
                symbol, "BUY" if direction == "LONG" else "SELL", seg, size, product,
                allow_live=bool(getattr(ms, "allow_live", False)))
        import datetime as _dt
        # P3: attach the direction-aware trailing STOP exit (ATR-multiple) for this position
        trail = self._make_trail(direction, price, atr)
        sgn = 1.0 if direction == "LONG" else -1.0
        # initial protective stop (ATR-multiple if known, else 1%) → enables R-multiple/efficiency
        stop_dist = (atr * float(self.cfg.get("trail_atr_mult", 2.5))) if atr else (price * 0.01)
        initial_sl = round(price - sgn * stop_dist, 6)
        initial_target = round(price + sgn * stop_dist * 2.0, 6)
        notional = price * size                       # full position value (Capital)
        margin = notional / leverage if leverage else notional   # capital actually locked
        overnight = self._holds_overnight(market, seg)
        self._open[f"{market.upper()}:{symbol}"] = {
            "market": market.upper(), "symbol": symbol, "direction": direction,
            "quantity": size, "entry_price": price, "entry_dt": _dt.datetime.now().isoformat(),
            "mode": mode, "segment": seg,
            "entry_order_id": entry_order_id, "broker_status": broker_status,
            "lot_size": lot, "num_lots": (num_lots if num_lots is not None else None),
            "instrument": instrument, "product": product,
            "trade_type": trade_type(market, instrument, product, _EXCHANGE.get(market.upper(), "")),
            "capital": round(notional, 2),            # CAPITAL = full position value (notional)
            "notional": round(notional, 2),
            "margin": round(margin, 2),               # MARGIN = capital locked (notional/leverage)
            "est_charges": round(self._est_charges(market, seg, notional), 4),  # round-trip fee est
            "holds_overnight": overnight,
            "peak_profit": 0.0, "peak_loss": 0.0,     # MFE / MAE in currency (tracked live)
            "trail": trail, "stop_level": initial_sl,
            "leverage": leverage, "margin_mode": "isolated" if is_crypto else "",
            "initial_sl": initial_sl, "initial_target": initial_target,
            "capital_at_risk": round(stop_dist * size, 4), "risk_reward": 2.0,
            # real market context AT ENTRY (fear&greed / btc / funding / volume / regime)
            "ctx": self._entry_context(market, symbol, brain),
            # snapshot the brain decision that produced THIS entry (if any) for the journal
            "brain_entry": dict(brain) if isinstance(brain, dict) else None}
        # X-RAY: on trade-open, capture the stock's full fused snapshot (multi-TF candles +
        # indicators + depth + circuit + demand/supply zones) in the background so it never
        # slows the entry. NSE only (OpenAlgo-backed). See trading/broker_sense/stock_xray.py.
        if not is_crypto:
            try:
                import threading as _xth
                _xth.Thread(target=lambda: _xray_on_open(symbol, _EXCHANGE.get("NSE", "NSE"), seg),
                            daemon=True, name=f"xray:{symbol}").start()
            except Exception:
                pass
        ot = self._open[f"{market.upper()}:{symbol}"]
        # order-book trader psychology at entry (computed at decide time; refetch if absent)
        ot["psych"] = self._psych_at_entry(market, symbol, seg)
        # decision_snapshot: EVERY datum the brain considered for THIS entry (journal JSON)
        ot["decision_snapshot"] = self._build_decision_snapshot(
            market, symbol, seg, direction, price, size, mode, atr=atr, brain=brain, ot=ot)
        # decision-memory episode: entry context + SHAP attribution recorded PENDING,
        # resolved with the outcome (+ reflection) when the trade closes.
        try:
            from trading.brain.attribution import explain_trade
            from trading.brain.decision_memory import get_memory
            closed = [t.to_dict() for t in self.journal().trades[-200:]]
            attribution = explain_trade({**ot, "brain_confidence_entry":
                                         (brain or {}).get("confidence") if isinstance(brain, dict) else None},
                                        closed, fast=True)   # never retrain on the tick thread
            ot["feature_attribution"] = attribution
            ot["episode_id"] = get_memory().open_episode(
                symbol=symbol, market=market, segment=seg, direction=direction,
                entry_price=price, strategy=(ot.get("decision_snapshot") or {}).get("strategy", ""),
                engine="loop", decision_snapshot=ot["decision_snapshot"],
                attribution=attribution)
        except Exception as e:
            self.errors.append(f"decision_memory: {type(e).__name__}: {str(e)[:60]}")
        self.trades_opened += 1
        return {"ok": True, "opened": direction, "price": price, "qty": size}

    def _psych_at_entry(self, market: str, symbol: str, seg: str) -> dict | None:
        """Latest psychology for this symbol — decide-time value, else a fresh evaluate."""
        psych = self._last_psych.get(f"{market.upper()}:{symbol}")
        if psych:
            return psych
        try:
            from trading.brain.psychology import get_engine
            exch = self._OA_EXCHANGE.get(seg, "NSE") if market.upper() == "NSE" else None
            return get_engine().evaluate(market, symbol, segment=seg, exchange=exch)
        except Exception:
            return None

    def _build_decision_snapshot(self, market, symbol, seg, direction, price, size, mode,
                                 *, atr, brain, ot) -> dict:
        """All data considered at entry, JSON-safe — the closed-trade learning context."""
        def _safe(v):
            if isinstance(v, dict):
                return {k: _safe(x) for k, x in v.items()}
            if isinstance(v, (list, tuple)):
                return [_safe(x) for x in v]
            if isinstance(v, (str, int, bool)) or v is None:
                return v
            try:
                f = float(v)
                return f if f == f and abs(f) != float("inf") else None
            except (TypeError, ValueError):
                return str(v)[:200]
        snap = {
            "ts": ot.get("entry_dt"),
            "market": market.upper(), "symbol": symbol, "segment": seg,
            "direction": direction, "mode": mode,
            "price": price, "quantity": size, "atr": atr,
            "leverage": ot.get("leverage"), "instrument": ot.get("instrument"),
            "product": ot.get("product"), "lot_size": ot.get("lot_size"),
            "num_lots": ot.get("num_lots"),
            "capital": ot.get("capital"), "margin": ot.get("margin"),
            "initial_sl": ot.get("initial_sl"), "initial_target": ot.get("initial_target"),
            "capital_at_risk": ot.get("capital_at_risk"),
            "screener_score": (self._symbol_score.get((market.upper(), symbol))
                               if hasattr(self, "_symbol_score") else None),
            "strategy": "brain" if isinstance(brain, dict) else "momentum",
            "brain": brain if isinstance(brain, dict) else None,   # full decision dict
            "market_context": ot.get("ctx"),
            "psychology": ot.get("psych"),
        }
        # The entry microstructure vector (2026-07-16, step 1 of the quality-gate rebuild). The gate
        # it will replace is a measured no-op with ZERO correlation to profit, and its replacement —
        # a calibrated forecast of THIS trade's outcome — cannot be fitted from what we recorded
        # before today. Field choice is evidence-driven (research/gate-rebuild/): book STATE leads,
        # order flow is demoted, and liquidity_regime + clock_phase are recorded as the CONDITIONERS
        # a flat pooled model was missing. RAM-only, so it costs the decision path no network call;
        # a fault here must never block a trade.
        # price/size/fill-side come from HERE because only the executor knows them, and without them
        # the Tier-5 label + cost fields cannot be built: barriers need the entry price [14], and the
        # square-root slippage term needs the intended notional Q [52]. Fee-only costing overstates
        # returns by ~58% [72], and the maker/taker assumption can flip the sign of the result [89].
        try:
            from trading.brain.entry_vector import entry_vector
            _sz = None
            try:
                _sz = abs(float(price) * float(size)) if price and size else None
            except (TypeError, ValueError):
                _sz = None
            ev = entry_vector(symbol, market=market, price=price, size_usd=_sz,
                              entry_type=str(ot.get("entry_type") or "taker"))
            if ev:
                snap["entry_vector"] = ev
        except Exception:
            pass
        return _safe(snap)

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
        # Route the NSE exit through OpenAlgo too (sandbox/live), mirroring the entry.
        exit_order_id, exit_status = "", "paper-wallet"
        if ot["market"] != "CRYPTO":
            ms = self.registry.get(ot["market"])
            exit_order_id, exit_status = self._submit_nse_order(
                symbol, close_side.upper(), ot.get("segment"), ot["quantity"],
                ot.get("product", "MIS"), allow_live=bool(getattr(ms, "allow_live", False)))
        self.trades_closed += 1
        try:
            if float(fill.get("realized_pnl") or 0) < 0:
                self._loss_cooldown[f"{ot['market']}:{symbol}:{ot['direction']}"] = time.time()
        except (TypeError, ValueError):
            pass
        self._journal_close(ot, price, fill.get("realized_pnl"),
                            entry_order_id=ot.get("entry_order_id", ""),
                            exit_order_id=exit_order_id)
        return {"ok": True, "closed": ot["direction"], "exit": price,
                "realized": fill.get("realized_pnl"), "broker_status": exit_status}

    def _journal_close(self, ot: dict, exit_price: float, realized,
                       *, entry_order_id: str = "", exit_order_id: str = "") -> None:
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
            # OpenAlgo order references (empty when crypto / sim-only) — honest audit trail
            if entry_order_id:
                t.entry_order_id = str(entry_order_id)
            if exit_order_id:
                t.exit_order_id = str(exit_order_id)
            if realized is not None:
                t.gross_pnl = float(realized)
            # peak profit (MFE) / peak loss (MAE, stored positive) + capital placed — tracked live
            t.mfe = round(float(ot.get("peak_profit", 0.0)), 4)
            t.mae = round(abs(float(ot.get("peak_loss", 0.0))), 4)
            t.margin_used = float(ot.get("margin", ot.get("capital", ot["entry_price"] * ot["quantity"])))
            # ── risk & sizing (enables quality.py r_multiple / efficiency / RR) ──
            if ot.get("initial_sl") is not None:
                t.initial_sl_price = float(ot["initial_sl"])
            if ot.get("initial_target") is not None:
                t.initial_target_price = float(ot["initial_target"])
            t.leverage = float(ot.get("leverage", 1.0))
            t.margin_mode = ot.get("margin_mode", "")
            if ot.get("lot_size") is not None:
                t.lot_size = int(ot["lot_size"])
            if ot.get("num_lots") is not None:
                t.num_lots = float(ot["num_lots"])
            if ot.get("capital_at_risk") is not None:
                t.capital_at_risk = float(ot["capital_at_risk"])
            if ot.get("risk_reward") is not None:
                t.risk_reward = float(ot["risk_reward"])
            # ── real market context snapshotted at entry → the schema's context columns ──
            ctx = ot.get("ctx") or {}
            for k in ("fear_greed_index", "btc_price_entry", "funding_rate_entry",
                      "volume_entry", "relative_volume", "regime_confidence"):
                if ctx.get(k) is not None:
                    setattr(t, k, float(ctx[k]))
            # ── brain / market-context fields (only those present in the schema) ──
            # parity with freqtrade ingest: every row states its signal source — the
            # strategy-library decider is the baseline, upgraded to "brain" below.
            t.signal_source = "momentum"
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
                # Pillar 17: calibrated uncertainty at entry → its own columns
                uq = brain.get("uq")
                if isinstance(uq, dict):
                    if uq.get("p_up") is not None:
                        t.p_up = float(uq["p_up"])
                    if uq.get("interval_width") is not None:
                        t.interval_width = float(uq["interval_width"])
                    if uq.get("self_uncertainty") is not None:
                        t.self_uncertainty = float(uq["self_uncertainty"])
                    t.abstain_reason = str(uq.get("abstain_reason") or "")
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
            # ── profit-tailgate columns on EVERY trade (owner goal 2026-07-07) + learn ──
            for _tk in ("tailgate_locked_profit_pct", "tailgate_distance_pct",
                        "tailgate_peak_profit_pct", "tailgate_triggered",
                        "tailgate_captured_pct"):
                if ot.get(_tk) is not None:
                    setattr(t, _tk, ot[_tk])
            try:
                from trading.execution import profit_tailgate as _pt
                cap0 = float(ot.get("capital") or (ot["entry_price"] * ot["quantity"]) or 0)
                peak = ot.get("tailgate_peak_profit_pct")
                if cap0 and peak and realized is not None:
                    _pt.learn(ot["market"].lower(), (ot.get("segment") or "equity"),
                              peak_profit_pct=float(peak),
                              captured_pct=float(realized) / cap0 * 100.0)
                _pt.clear_lock(str(ot.get("trade_id")
                                   or f"{ot['market'].upper()}:{ot['symbol']}"))
            except Exception:
                pass
            # (W1 goal_score/toward_goal columns are stamped centrally in journal.record()
            #  once net_pnl is final — one scorer for every engine.)
            # ── order-book trader psychology at entry → its journal columns ──
            psych = ot.get("psych")
            if isinstance(psych, dict):
                from trading.brain.psychology import psych_columns
                for k, v in psych_columns(psych).items():
                    setattr(t, k, v)
            # ── the FULL decision context the brain considered at entry (JSON column) ──
            if isinstance(ot.get("decision_snapshot"), dict):
                t.decision_snapshot = ot["decision_snapshot"]
            self.journal().record(t)          # derives charges→net P&L, quality, behaviour, persists
            # ── decision-memory closure: resolve the entry episode with the REAL outcome
            # (post-record so net_pnl/r_multiple are the derived values) + reflection ──
            try:
                from trading.brain.decision_memory import get_memory
                if ot.get("episode_id"):
                    t.episode_id = ot["episode_id"]
                    if isinstance(ot.get("feature_attribution"), dict):
                        t.feature_attribution = ot["feature_attribution"]
                    if t.brain_prediction in ("UP", "DOWN") and t.exit_price and t.entry_price:
                        t.brain_correct = (t.brain_prediction == "UP") == (t.exit_price > t.entry_price)
                    ep = get_memory().resolve(
                        episode_id=ot["episode_id"], net_pnl=float(t.net_pnl or 0.0),
                        r_multiple=t.r_multiple, exit_price=t.exit_price,
                        exit_reason=t.setup_type or "", brain_correct=t.brain_correct)
                    if ep and ep.get("reflection"):
                        t.exit_reflection = ep["reflection"]
                    self.journal()._save()    # persist the enriched columns on the recorded row
            except Exception as e:
                self.errors.append(f"decision_memory: {type(e).__name__}: {str(e)[:60]}")
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
        # ensure OpenAlgo's analyzer (sandbox) matches TRADING_MODE before the first NSE order
        if "NSE" in self.symbols:
            try:
                self._openalgo()
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
            # drop non-JSON-serialisable internals (the trailing engine + raw brain dict)
            clean = {k: v for k, v in ot.items() if k not in ("trail", "brain_entry")}
            # flatten the brain decision to closed-trade keys so the outcome-net (and the
            # dashboard Confidence column) can read it without the raw object
            be = ot.get("brain_entry")
            if isinstance(be, dict):
                if be.get("confidence") is not None:
                    clean["brain_confidence_entry"] = be["confidence"]
                if be.get("regime"):
                    clean["market_regime_entry"] = be["regime"]
                if isinstance(be.get("uq"), dict):   # Pillar 17 columns for the open table
                    clean["uq"] = be["uq"]
                clean["node_contributions"] = [{
                    "source": "brain_pipeline", "anomaly_score": be.get("anomaly_score"),
                    "news_compound": be.get("news_compound"), "recall_bias": be.get("recall_bias"),
                }]
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
                # brain handoff: MANUAL (operator sliders + auto-open basket) until the brain
                # has learned from enough closed trades, then BRAIN takes control.
                "control": "BRAIN" if self.brain_in_control() else "MANUAL",
                "auto_open": self._auto_open_active(),
                # per-segment leverage: live max caps + current defaults (UI shows/enforces these)
                # NOTE: both dicts are keyed by a (market, segment) TUPLE — flatten to
                # "MARKET:segment" strings; a tuple key makes json.dumps raise
                # "keys must be str ... not tuple", which 500'd the whole loop endpoint.
                "leverage_limits": {f"{m}:{s}": v for (m, s), v in self._MAX_LEVERAGE.items()},
                "leverage_defaults": {f"{m}:{s}": v for (m, s), v in self._LEVERAGE.items()},
                # lot-based segments (F&O/options/commodities) + representative default lots
                "lot_defaults": dict(self._DEFAULT_LOT),
                "handoff": {"closed": self.trades_closed,
                            "needed": int(self.cfg.get("brain_handoff_trades", 30) or 0),
                            "in_control": self.brain_in_control()},
                "config": dict(self.cfg),
                "nse_broker_auth": nse_auth, "crypto_feed": self._crypto_feed_status(),
                "errors": self.errors[-5:], "last_tick": self.last_tick}

    @staticmethod
    def _crypto_feed_status():
        """Honest crypto data-plane health: per-venue calls/errors/budget of the
        multi-venue pool (ban-proofing), or the single-exchange fallback label."""
        try:
            from trading.crypto.exchange_pool import _POOLS, pool_enabled
            if not pool_enabled():
                return "ccxt (single-exchange; pool disabled)"
            pools = {k: p.status() for k, p in _POOLS.items()}
            return {"mode": "multi-venue pool (binance/bybit/okx/kucoin)",
                    "pools": pools} if pools else "multi-venue pool (idle)"
        except Exception:
            return "ccxt (live)"


# ── module-level singleton so the dashboard + read endpoints share ONE running loop ──
_LOOP: LiveTradeLoop | None = None


def get_loop() -> LiveTradeLoop:
    global _LOOP
    if _LOOP is None:
        _LOOP = LiveTradeLoop()
    return _LOOP


def start_loop() -> LiveTradeLoop:
    return get_loop().start()
