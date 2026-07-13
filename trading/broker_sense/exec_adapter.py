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
            from trading.market_guard import assert_market_symbol
            assert_market_symbol("CRYPTO" if market == "crypto" else "NSE", symbol)
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
            res = self._nse_cli().place_order(
                symbol=symbol.split("/")[0], action=action,
                quantity=quantity or 1, allow_live=live)
        entry = {"market": market, "symbol": symbol, "action": action, "segment": segment,
                 "live": live, "broker": broker, "ok": bool(res)}
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
