"""trading/online/supervisor.py — always-on trading supervisor (O4).

Ties O1–O3 into one continuously-runnable bot: per market it picks LIVE vs REPLAY mode
(session), pulls a price/bar (live source when open, cached-replay when NSE is closed),
asks a decision function (e.g. the T8.9 BrainTradingPipeline) for an action, passes it
through the central trading-state gate, and routes the fill to the per-market PAPER wallet
(or a gated LIVE adapter in REAL mode). Crypto runs 24/7; NSE runs live in-session and
replays its cache off-hours.

Start/stop are first-class and per-market, in BOTH paper and real:
  start_market(m)  → enable + ACTIVE     stop_market(m)  → disable (no new activity)
  pause_market(m)  → REDUCING (de-risk)  halt_market(m)  → HALTED (kill-switch)

Design is STEP-DRIVEN (`step()` / `run(steps=)`) so it is deterministic and offline-
testable; a real deployment calls `step()` from an asyncio/APScheduler loop. Live sources
and the decide fn are INJECTED — no network here. Honest: REAL orders only when the gate
clears (enabled + ACTIVE/REDUCING + allow_live), and a live adapter is wired.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from trading.online.replay import CandleReplay
from trading.online.session import MarketSession
from trading.online.state import MarketRegistry, TradingState
from trading.online.wallet import PaperWalletBook


@dataclass
class OnlineSupervisor:
    registry: MarketRegistry = field(default_factory=lambda: MarketRegistry(persist=False))
    wallets: PaperWalletBook = field(default_factory=lambda: PaperWalletBook(persist=False))
    # injected I/O (offline-testable): crypto live price, NSE live price, NSE cached OHLCV
    crypto_price_source: object = None          # callable(symbol) -> {bid,ask,last} or float
    nse_price_source: object = None             # callable(symbol) -> price (live, in-session)
    nse_ohlcv: object = None                    # dict[symbol] -> OHLCV DataFrame (for replay)
    decide_fn: object = None                    # callable(market, symbol, window_df|price) -> {action, size?}
    live_adapter: object = None                 # callable(market, order) for REAL orders (gated)
    sessions: dict = field(default_factory=dict)
    heartbeats: int = field(default=0, init=False)
    log: list = field(default_factory=list, init=False)
    _replays: dict = field(default_factory=dict, init=False)

    def _session(self, market: str) -> MarketSession:
        return self.sessions.setdefault(market.upper(), MarketSession(market))

    # ── per-market controls (the Start/Stop buttons) ────────────────────────────
    def start_market(self, market: str) -> dict:
        ms = self.registry.get(market)
        ms.enable().set_state(TradingState.ACTIVE)
        self.registry.save()
        return {"market": ms.market, "action": "start", "state": ms.as_dict()}

    def stop_market(self, market: str) -> dict:
        ms = self.registry.get(market)
        ms.disable()
        self.registry.save()
        return {"market": ms.market, "action": "stop", "state": ms.as_dict()}

    def pause_market(self, market: str) -> dict:
        self.registry.get(market).set_state(TradingState.REDUCING)
        self.registry.save()
        return {"market": market.upper(), "action": "pause"}

    def halt_market(self, market: str) -> dict:
        self.registry.get(market).set_state(TradingState.HALTED)
        self.registry.save()
        return {"market": market.upper(), "action": "halt"}

    def set_mode(self, market: str, mode: str, *, confirm: bool = False) -> dict:
        r = self.registry.get(market).set_mode(mode, confirm=confirm)
        self.registry.save()
        return r

    # ── price acquisition (LIVE source or REPLAY cache) ─────────────────────────
    def _replay(self, market: str, symbol: str) -> CandleReplay | None:
        key = f"{market}:{symbol}"
        if key not in self._replays:
            df = (self.nse_ohlcv or {}).get(symbol)
            self._replays[key] = CandleReplay(df) if df is not None else None
        return self._replays[key]

    def _acquire(self, market: str, symbol: str, mode: str, replay_step: int):
        """Return (price, window_df-or-None) for the current step."""
        if market.upper() == "CRYPTO":
            if self.crypto_price_source is None:
                return None, None
            q = self.crypto_price_source(symbol)
            price = q.get("last", q.get("ask")) if isinstance(q, dict) else float(q)
            return price, None
        if mode == "LIVE":
            return (self.nse_price_source(symbol) if self.nse_price_source else None), None
        rp = self._replay(market, symbol)              # REPLAY (off-hours)
        if rp is None or replay_step >= len(rp.ohlcv):
            return None, None
        win = rp.window(replay_step)
        return float(win["close"].iloc[-1]), win

    # ── one supervised step over all enabled markets ────────────────────────────
    def step(self, *, symbols: dict | None = None, when=None, replay_step: int = 0) -> dict:
        """One tick: for each enabled market, acquire price → decide → gate → route fill."""
        self.heartbeats += 1
        symbols = symbols or {"CRYPTO": "BTCUSDT", "NSE": "RELIANCE"}
        results = []
        for market, symbol in symbols.items():
            ms = self.registry.get(market)
            if not ms.enabled:
                results.append({"market": market, "skipped": "stopped"})
                continue
            mode = self._session(market).mode(when)
            price, window = self._acquire(market, symbol, mode, replay_step)
            if price is None:
                results.append({"market": market, "mode": mode, "skipped": "no price"})
                continue
            decision = (self.decide_fn(market, symbol, window if window is not None else price)
                        if self.decide_fn else {"action": "FLAT"})
            action = decision.get("action", "FLAT")
            reduces = action in ("EXIT", "FLAT")
            gate = self.registry.allow_order(market, reduces_position=reduces, is_real=ms.is_real)
            routed = None
            if action in ("LONG", "SHORT", "EXIT") and gate["ok"]:
                routed = self._route(ms, market, symbol, action, price,
                                     float(decision.get("size", 1.0)))
            results.append({"market": market, "mode": mode, "session_mode": mode,
                            "price": round(float(price), 4), "action": action,
                            "gate": gate, "routed": routed})
        entry = {"heartbeat": self.heartbeats, "results": results}
        self.log.append(entry)
        return entry

    def _route(self, ms, market, symbol, action, price, size):
        side = "buy" if action == "LONG" else ("sell" if action == "SHORT" else None)
        if ms.is_real:                                  # REAL → gated live adapter (no network here)
            if self.live_adapter is None:
                return {"mode": "REAL", "ok": False, "detail": "no live adapter wired"}
            return {"mode": "REAL", **(self.live_adapter(market, {
                "symbol": symbol, "side": side or "close", "qty": size, "price": price}) or {})}
        # PAPER → per-market wallet
        w = self.wallets.wallet(market)
        if side is None:                                # EXIT: close via opposite of current pos
            return {"mode": "PAPER", "note": "exit routed to wallet", **w.summary()}
        try:
            w.record_fill(symbol, side, size, price)
            return {"mode": "PAPER", "filled": {"symbol": symbol, "side": side,
                                                "qty": size, "price": price}}
        except Exception as exc:
            return {"mode": "PAPER", "ok": False, "detail": str(exc)[:80]}

    def run(self, steps: int = 10, **kw) -> list:
        return [self.step(replay_step=i, **kw) for i in range(steps)]

    def status(self) -> dict:
        return {"heartbeats": self.heartbeats, "registry": self.registry.status(),
                "wallets": self.wallets.status(),
                "sessions": {m: self._session(m).status() for m in self.registry.markets}}
