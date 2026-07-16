"""trading/broker_sense/exec_adapter.py — APIs are used ONLY here (owner's step 8).

Everything upstream of this file is perception (browser/vision/OCR); every order — paper
or real — goes through exactly two API doors:

  crypto → CryptoEngineClient (Freqtrade). dry-run = Binance paper; real = Binance ONLY
           (owner decision #2) and only with CRYPTO_ALLOW_LIVE=1 + the engine's own guard.
  NSE    → OpenAlgoClient. analyzer/sandbox = Zerodha paper; real = the ONE broker the
           owner picks (angelone/upstox/groww, brokers.set_real_nse_broker) — until then
           any live NSE order raises RoleViolation.

The screening apps (Bybit, Coinbase, TradingView, the unchosen NSE brokers) have no path
into this file at all — role enforcement is structural (brokers.assert_can_execute).
"""
from __future__ import annotations

import os

from trading.broker_sense.brokers import EXEC_REAL, assert_can_execute, real_broker


class ExecAdapter:
    """The single execution door for the Broker-Sense funnel."""

    def __init__(self, crypto_client=None, nse_client=None):
        self._crypto = crypto_client
        self._nse = nse_client
        self.log: list[dict] = []

    def _crypto_cli(self):
        if self._crypto is None:
            from trading.crypto.engine_client import CryptoEngineClient
            self._crypto = CryptoEngineClient()
        return self._crypto

    def _nse_cli(self):
        if self._nse is None:
            from trading.openalgo_client import OpenAlgoClient
            self._nse = OpenAlgoClient()
        return self._nse

    # NSE segment → (OpenAlgo exchange, product, instrument). Mirrors live_loop._seg_instrument /
    # the NSE F&O engine: equity trades whole shares intraday (NSE/MIS); futures & commodities are
    # lot-based near-month FUT carry positions (NFO/MCX · NRML). options is NOT in this static map —
    # its exchange (NFO/BFO) + contract are resolved dynamically in _route_nse_option (direction →
    # CE/PE, ATM/OTM strike, nearest-weekly expiry).
    _NSE_SEG_ROUTE = {
        "equity": ("NSE", "MIS", "EQ"), "intraday": ("NSE", "MIS", "EQ"),
        "delivery": ("NSE", "CNC", "EQ"), "mtf": ("NSE", "CNC", "EQ"),
        "futures": ("NFO", "NRML", "FUT"), "fno": ("NFO", "NRML", "FUT"),
        "commodities": ("MCX", "NRML", "FUT"),
    }
    _DEFAULT_LOT = {"futures": 50, "fno": 50, "commodities": 100}

    def _route_nse(self, base: str, segment: str | None, action: str, *, lots: int = 1):
        """Resolve (tradesymbol, exchange, product, quantity, order_action) for an NSE order, or
        None when it can't be executed (no live contract). Reuses the near-month FUT resolver, the
        single-leg option selector, and OpenAlgo's real lot size so F&O/options hit the correct
        contract in whole lots. `action` is the DIRECTION (BUY=long / SELL=short); the returned
        order_action is what actually goes to the broker (BUY for equity/futures per direction; for
        options we always BUY the premium and encode direction in CE vs PE)."""
        seg = (segment or "equity").lower()
        act = str(action).upper()
        if seg in ("options", "opt", "option"):
            return self._route_nse_option(base, act, lots=lots)
        route = self._NSE_SEG_ROUTE.get(seg)
        if route is None:                                    # prediction / unknown
            return None
        exch, product, instrument = route
        if instrument == "EQ":                               # equity: whole shares, symbol as-is
            return (base, exch, product, max(1, int(lots)), act)
        # F&O: resolve the near-month FUT contract (reuse the exact-base resolver) + size in LOTS
        try:
            from trading.screener.commodities import resolve_near_month_fut
            pick = resolve_near_month_fut(self._nse_cli()._client(), base, exchange=exch)
        except Exception:
            pick = None
        if not pick or not pick.get("symbol"):
            return None                                      # no live contract → don't guess a symbol
        tradesym = pick["symbol"]
        lot = self._nse_lot(tradesym, exch) or self._DEFAULT_LOT.get(seg, 1)
        return (tradesym, exch, product, max(1, int(lots)) * lot, act)

    def _route_nse_option(self, base: str, action: str, *, lots: int = 1):
        """Single-leg NSE option: direction → BUY CE (long) / BUY PE (short) at the nearest-weekly
        expiry, strike = ATM (default) or OTM (NSE_OPT_MONEYNESS=otm, NSE_OPT_OTM_STEPS strikes).
        We always BUY the option (defined risk = premium paid). Reuses screener.options for the
        chain search + ATM/expiry math. Returns None if no live contract or no underlying LTP —
        never guesses a strike/symbol."""
        from trading.screener.options import (_norm_rows, _opt_exch, _strike_step,
                                              atm_strike, nearest_expiry)
        opt_type = "CE" if action.upper() == "BUY" else "PE"   # long→CALL, short→PUT
        exch = _opt_exch(base)                                  # NFO (NSE) / BFO (SENSEX·BANKEX)
        ltp = self._underlying_ltp(base, exch)
        if not ltp:
            return None                                        # can't pick a strike without spot
        try:
            rows = _norm_rows(self._nse_cli()._client().search(query=base, exchange=exch))
        except Exception:
            rows = []
        rows = [r for r in rows if r.get("opt_type") == opt_type and r.get("strike")]
        if not rows:
            return None
        exp = nearest_expiry([r.get("expiry") for r in rows])  # nearest weekly (earliest date)
        near = [r for r in rows if str(r.get("expiry")) == str(exp)]
        strikes = [float(r["strike"]) for r in near]
        atm = atm_strike(ltp, strikes)
        if atm is None:
            return None
        target = atm
        if (os.environ.get("NSE_OPT_MONEYNESS", "atm") or "atm").lower() == "otm":
            step = _strike_step(strikes) or 0.0
            n = int(os.environ.get("NSE_OPT_OTM_STEPS", "1") or 1)
            target = atm + n * step if opt_type == "CE" else atm - n * step   # OTM side by CE/PE
        row = min(near, key=lambda r: abs(float(r["strike"]) - target))
        tradesym = row["symbol"]
        lot = self._nse_lot(tradesym, exch) or self._DEFAULT_LOT.get("options", 1)
        return (tradesym, exch, "NRML", max(1, int(lots)) * lot, "BUY")   # always BUY the option

    @staticmethod
    def _stream_position(tradesym: str, exchange: str) -> None:
        """Stream every contract we hold, so its MTM comes off the WS instead of Zerodha's REST.

        WHY (live-diagnosed 2026-07-16): OpenAlgo's sandbox positionbook recomputes MTM on EVERY
        call and checks its WebSocket cache FIRST, falling back to the REST quote API only for
        symbols the cache lacks. The mirror streamed the equity underlyings but never the F&O
        CONTRACTS we hold, so with 70 open positions each Positions-page poll fetched ~70 REST
        quotes — 256 multiquotes calls in 19 min — until Zerodha answered "Too many requests" and
        positionbook hung (page spinner). Our subscribe makes the proxy publish those ticks, which
        fills OpenAlgo's MarketDataService → the WS cache hits → no REST, no rate limit.
        Best-effort: a mirror that's off/cold just means the old REST path. Never raises.
        """
        try:
            from trading.broker_sense import kite_stream
            if kite_stream.enabled():
                kite_stream.get_kite_mirror().subscribe_symbols([tradesym], exchange=exchange)
        except Exception:
            pass

    def _nse_lot(self, symbol: str, exchange: str) -> int | None:
        try:
            return self._nse_cli().lot_size(symbol, exchange=exchange)      # REAL master-contract lot
        except Exception:
            return None

    def _underlying_ltp(self, base: str, opt_exch: str) -> float:
        """Underlying spot for the ATM strike. The Zerodha in-RAM mirror first (warm in the funnel
        process — stock underlyings), then a direct OpenAlgo spot quote on the right exchange
        (index→NSE_INDEX, stock→NSE) — this is an EXECUTION-time read (like the FUT/chain search),
        so it's exempt from the UI-only SELECTION gate. 0.0 → abstain (never pick a blind strike)."""
        try:
            from trading.broker_sense import kite_stream
            t = kite_stream.ticker(base) or {}
            if t.get("last"):
                return float(t["last"])
        except Exception:
            pass
        try:
            from trading.screener.options import _spot_exch
            r = self._nse_cli().quote(base, exchange=_spot_exch(base))
            d = r.get("data", r) if isinstance(r, dict) else {}
            if isinstance(d, dict):
                return float(d.get("ltp") or d.get("last_price") or 0.0)
        except Exception:
            pass
        return 0.0

    @staticmethod
    def _live_allowed(market: str) -> bool:
        flag = "CRYPTO_ALLOW_LIVE" if market == "crypto" else "NSE_ALLOW_LIVE"
        return os.environ.get(flag, "") in ("1", "true", "TRUE", "yes")

    def place(self, *, market: str, symbol: str, action: str, segment: str | None = None,
              price: float | None = None, enter_tag: str | None = None,
              quantity: int | None = None, live: bool = False) -> dict:
        """Place one order. live=False (the default, and the only mode until the owner's
        explicit go) rides the existing paper stacks."""
        market = (market or "").lower()                      # normalize: "CRYPTO"→"crypto"
        # STRUCTURAL market↔symbol guard (multi-market isolation): a crypto-shaped symbol can
        # never reach the NSE/OpenAlgo door, nor an NSE symbol the crypto engine — regardless
        # of a wrong upstream tag. Returns an honest failure instead of placing.
        try:
            from trading.market_guard import assert_market_symbol, is_instrument_key
            assert_market_symbol("CRYPTO" if market == "crypto" else "NSE", symbol)
            if market != "crypto" and is_instrument_key(symbol):
                raise ValueError(f"instrument-key {symbol!r} is not a tradeable OpenAlgo symbol")
        except Exception as exc:
            entry = {"market": market, "symbol": symbol, "action": action, "segment": segment,
                     "live": False, "broker": None, "ok": False, "blocked": str(exc)}
            self.log = (self.log + [entry])[-50:]
            return {"placed": False, **entry}
        live = bool(live) and self._live_allowed(market)
        broker = (EXEC_REAL["crypto"] if market == "crypto" else
                  (real_broker("nse") or "zerodha-sandbox"))
        assert_can_execute(broker, market, live=live)        # structural role gate
        if market == "crypto":
            res = self._crypto_cli().place_order(
                symbol=symbol, action=action, price=price, enter_tag=enter_tag,
                segment=segment, allow_live=live)
        else:
            routed = self._route_nse(symbol.split("/")[0], segment, action, lots=quantity or 1)
            if routed is None:                                # no live contract / no spot → abstain
                entry = {"market": market, "symbol": symbol, "action": action, "segment": segment,
                         "live": False, "broker": None, "ok": False,
                         "blocked": f"no tradeable {segment!r} contract resolved for {symbol!r}"}
                self.log = (self.log + [entry])[-50:]
                return {"placed": False, **entry}
            tradesym, exch, product, qty, order_action = routed
            res = self._nse_cli().place_order(
                symbol=tradesym, action=order_action, exchange=exch, product=product,
                quantity=qty, allow_live=live)
            self._stream_position(tradesym, exch)
        entry = {"market": market, "symbol": symbol, "action": action, "segment": segment,
                 "live": live, "broker": broker, "ok": bool(res),
                 **({"traded_symbol": routed[0], "exchange": routed[1], "product": routed[2],
                     "quantity": routed[3], "order_action": routed[4]}
                    if market != "crypto" and routed else {})}
        self.log = (self.log + [entry])[-50:]
        return {"placed": True, **entry, "engine_response": res}

    def status(self) -> dict:
        return {
            "paper": {"crypto": "binance dry-run (Freqtrade)",
                      "nse": "zerodha sandbox (OpenAlgo analyzer)"},
            "real": {"crypto": EXEC_REAL["crypto"],
                     "nse": real_broker("nse") or "UNSET (owner picks at go-live)"},
            "live_env": {"crypto": self._live_allowed("crypto"),
                         "nse": self._live_allowed("nse")},
            "recent_orders": self.log[-10:],
        }
