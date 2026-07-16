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
    # lot-based near-month FUT carry positions (NFO/MCX · NRML). options is intentionally absent —
    # it needs direction→CE/PE + strike/expiry selection, which live_loop owns; _route_nse returns
    # None for it so place() reports an honest "not executable here" instead of a wrong order.
    _NSE_SEG_ROUTE = {
        "equity": ("NSE", "MIS", "EQ"), "intraday": ("NSE", "MIS", "EQ"),
        "delivery": ("NSE", "CNC", "EQ"), "mtf": ("NSE", "CNC", "EQ"),
        "futures": ("NFO", "NRML", "FUT"), "fno": ("NFO", "NRML", "FUT"),
        "commodities": ("MCX", "NRML", "FUT"),
    }
    _DEFAULT_LOT = {"futures": 50, "fno": 50, "commodities": 100}

    def _route_nse(self, base: str, segment: str | None, *, lots: int = 1):
        """Resolve (tradesymbol, exchange, product, quantity) for an NSE order, or None when the
        segment isn't executable by the broker-sense funnel (options). Reuses the near-month FUT
        resolver + OpenAlgo's real lot size so F&O orders hit the correct contract in whole lots."""
        seg = (segment or "equity").lower()
        route = self._NSE_SEG_ROUTE.get(seg)
        if route is None:                                    # options / prediction / unknown
            return None
        exch, product, instrument = route
        if instrument == "EQ":                               # equity: whole shares, symbol as-is
            return (base, exch, product, max(1, int(lots)))
        # F&O: resolve the near-month FUT contract (reuse the exact-base resolver) + size in LOTS
        try:
            from trading.screener.commodities import resolve_near_month_fut
            pick = resolve_near_month_fut(self._nse_cli()._client(), base, exchange=exch)
        except Exception:
            pick = None
        if not pick or not pick.get("symbol"):
            return None                                      # no live contract → don't guess a symbol
        tradesym = pick["symbol"]
        lot = None
        try:
            lot = self._nse_cli().lot_size(tradesym, exchange=exch)   # REAL master-contract lot
        except Exception:
            lot = None
        lot = lot or self._DEFAULT_LOT.get(seg, 1)
        return (tradesym, exch, product, max(1, int(lots)) * lot)

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
            routed = self._route_nse(symbol.split("/")[0], segment, lots=quantity or 1)
            if routed is None:                                # not executable here (e.g. options)
                entry = {"market": market, "symbol": symbol, "action": action, "segment": segment,
                         "live": False, "broker": None, "ok": False,
                         "blocked": f"segment {segment!r} not executable by broker-sense "
                                    f"(options/strike selection → live_loop)"}
                self.log = (self.log + [entry])[-50:]
                return {"placed": False, **entry}
            tradesym, exch, product, qty = routed
            res = self._nse_cli().place_order(
                symbol=tradesym, action=action, exchange=exch, product=product,
                quantity=qty, allow_live=live)
        entry = {"market": market, "symbol": symbol, "action": action, "segment": segment,
                 "live": live, "broker": broker, "ok": bool(res),
                 **({"traded_symbol": routed[0], "exchange": routed[1], "product": routed[2],
                     "quantity": routed[3]} if market != "crypto" and routed else {})}
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
