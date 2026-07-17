"""trading/crypto/freqtrade/library_decider.py — the library-ensemble decider (leaf module).

E9 (2026-07-17): extracted VERBATIM from brain_executor.py to break the one STRUCTURAL import
cycle in the executor cluster — percoin_decider subclasses LibraryBrainDecider, so its
top-level `from brain_executor import LibraryBrainDecider` made
brain_executor ↔ percoin_decider a hard import-time loop (every other edge in the cluster is
a lazy function-level import). This module imports nothing from the cluster; brain_executor
re-exports these names, so every existing import path keeps working.
"""
from __future__ import annotations

import os
import time

import pandas as pd

_TF = "5m"
_LOOKBACK = 200


def _spot(symbol: str) -> str:
    """ccxt spot OHLCV uses the base pair; strip a futures settle suffix (BTC/USDT:USDT → BTC/USDT)."""
    return str(symbol or "").split(":")[0]


class LibraryBrainDecider:
    """Ensemble the library's signal strategies into a live entry/exit instruction per symbol."""

    def __init__(self, strategies=None, *, exchange: str = "binance", timeframe: str = _TF,
                 lookback: int = _LOOKBACK, min_votes: int = 1):
        self._exchange = exchange
        self._tf = timeframe
        self._lookback = lookback
        self._min_votes = min_votes
        # exit only on a REAL reversal (ensemble flips against the position by this many net
        # votes), not merely turning neutral — stops the too-soon force-exits. EXIT_MIN_VOTES.
        try:
            self._exit_votes = max(1, int(os.environ.get("EXIT_MIN_VOTES", "2") or 2))
        except ValueError:
            self._exit_votes = 2
        self._strats = strategies            # None → resolve all executable crypto signal strategies
        self._ccxt = None
        self._ohlcv_cache: dict = {}         # symbol -> (monotonic_ts, df)

    # ── strategy set ────────────────────────────────────────────────────────────
    def strategies(self) -> list:
        # FULL library universe (operator ask 2026-07-02): every executable strategy
        # with a signal competes per coin — signals are generic over OHLCV features,
        # so equity/commodity-tagged strategies are scoreable on crypto bars too.
        # The per-coin backtest×brain ranking is what filters bad fits, not the tag.
        if self._strats is None:
            from trading.strategy.library.registry import get_registry
            self._strats = [s for s in get_registry().executable()
                            if s.signal is not None]
        return self._strats

    # ── live data (real ccxt OHLCV, short-cached) ───────────────────────────────
    def _client(self):
        if self._ccxt is None:
            from trading.crypto.exchange_client import ExchangeClient
            self._ccxt = ExchangeClient(self._exchange, market_type="spot")
        return self._ccxt

    def _ohlcv(self, symbol: str) -> pd.DataFrame | None:
        hit = self._ohlcv_cache.get(symbol)
        now = time.monotonic()
        if hit and (now - hit[0]) < 20:
            return hit[1]
        # THE MOTTO (2026-07-12): the eyes' captured candles serve the DECISION bars
        # first — this was the last ungated ccxt read in the entry path (audit gap C).
        # In UI-only mode a capture miss OR an error is an honest None (FLAT), never an
        # API poll — the env backstop keeps that true even if the door itself errors.
        raw = None
        ui_on = os.environ.get("UI_ONLY_DATA", "") in ("1", "true", "TRUE", "yes")
        try:
            from trading.broker_sense import ui_data
            ui_on = ui_data.enabled()
            raw = ui_data.ui_ohlcv(_spot(symbol), timeframe=self._tf,
                                   limit=self._lookback)
            if raw is not None and len(raw) < 40:
                raw = None                        # too thin for the strategies
        except Exception:
            raw = None
        if raw is None:
            # RAM mirror candles (owner 2026-07-13): the in-RAM WS-mirror multi-TF OHLC — web-sourced
            # (motto-pure, NO API) — is the last-mile decision-bar fallback BEFORE any ccxt, and is
            # allowed under UI-only (the mirror IS the eyes' websocket feed). Only the TFs it aggregates.
            try:
                from trading.broker_sense import binance_stream as _bs
                mrows = _bs.ohlcv(symbol, self._tf, self._lookback)
                if mrows and len(mrows) >= 40:
                    raw = mrows
            except Exception:
                pass
        if raw is None and ui_on:
            return None                           # UI-only: eyes + mirror both missed → honest FLAT
        if raw is None:
            try:
                # last resort only (flag off): the spot ccxt feed even when trading futures perps.
                raw = self._client()._client().fetch_ohlcv(_spot(symbol), self._tf,
                                                           limit=self._lookback)
            except Exception:
                return None
        if not raw:
            return None
        df = pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "volume"])
        self._ohlcv_cache[symbol] = (now, df)
        return df

    # ── the instruction: ensemble vote over the library ─────────────────────────
    def decide(self, market: str, symbol: str, price, *, in_position: bool) -> dict:
        """Run every active library strategy on `symbol`'s live bars; net their last signals into
        a LONG / SHORT / EXIT / FLAT instruction. Offline-safe (FLAT when data/strategies absent)."""
        if str(market).upper() != "CRYPTO":
            return {"action": "FLAT"}
        df = self._ohlcv(symbol)
        if df is None or len(df) < 40:
            return {"action": "FLAT", "_brain": {"reason": "no live bars"}}
        from trading.strategy.library.features_ext import compute_features_ext
        try:
            feats = compute_features_ext(df[["open", "high", "low", "close", "volume"]])
        except Exception:
            return {"action": "FLAT", "_brain": {"reason": "feature build failed"}}

        longs = shorts = 0
        contributors = []
        for s in self.strategies():
            try:
                last = int(s.make_signal(feats).iloc[-1])
            except Exception:
                continue
            if last > 0:
                longs += 1; contributors.append((s.name, 1))
            elif last < 0:
                shorts += 1; contributors.append((s.name, -1))
        net = longs - shorts
        total = max(1, longs + shorts)
        # decision: open on a net long majority; exit only on a REAL reversal (owner 2026-07-12:
        # 'trades force-exit too soon'). The old `net <= 0` closed a winner the instant the
        # ensemble merely turned NEUTRAL (a single noisy cycle at 92s), undercutting the profit
        # tailgate that's meant to ride + lock the gain. Now exit needs the ensemble to flip
        # against the position by EXIT_MIN_VOTES (default 2), not just go flat — so stoploss +
        # tailgate handle the normal give-back and the strategy exit fires only on a genuine turn.
        action = "FLAT"
        exit_votes = self._exit_votes
        if in_position:
            action = "EXIT" if net <= -exit_votes else "FLAT"
        elif net >= self._min_votes:
            action = "LONG"
        elif net <= -self._min_votes:
            action = "SHORT"
        brain = {"source": "library_ensemble", "longs": longs, "shorts": shorts, "net": net,
                 "confidence": round(abs(net) / total, 3), "n_strategies": longs + shorts,
                 "top": [c[0] for c in contributors[:6]],
                 "action": {"LONG": "UP", "SHORT": "DOWN"}.get(action, "NEUTRAL")}
        return {"action": action, "size": 1.0, "_brain": brain}


def library_brain_decider(**kw):
    """Factory returning a decide_fn compatible with LiveTradeLoop(decide_fn=...)."""
    dec = LibraryBrainDecider(**kw)
    return dec.decide


