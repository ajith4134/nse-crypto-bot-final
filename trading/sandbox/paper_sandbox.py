"""trading/sandbox/paper_sandbox.py — the brain's FAST paper-trading sandbox.

Owner's decision: for now, trade in a lightweight in-dashboard simulator (fast, unlimited trades,
no framework friction) so the brain LEARNS quickly; graduate to Freqtrade for the real-money path
once results are good. HONEST: these numbers are for LEARNING, not for predicting live results —
fills use a simple synthetic book off the live ticker (not the full exchange order book / fees /
funding that Freqtrade models faithfully).

Reuses the project's real PaperEngine (crypto/paper_engine.py — position/leverage/liquidation/PnL
math, order-book fills) so the simulation isn't naive.

SIGNAL SOURCE (owner ask 2026-07-06 — "make it"): the sandbox now drives its picks from the SAME
real brain decision engine the live crypto loop uses — PerCoinBrainDecider (per-coin backtest ×
TradeOutcomeNet brain-weight × deflated-Sharpe gate) with the cortex-B8 shadow overlay reused from
BrainExecutor — instead of the old plain top-movers momentum. `signal_mode` selects "brain"
(default) or "momentum" (the fast fallback). When the brain engine can't build at all (import/data
failure) a tick auto-falls back to momentum so the learn-lab never goes dead — and says so honestly
in `brain_note`. Exits combine the brain's own EXIT instruction with the profit-tailgate ratchet +
hard stop. Broker-feature account-path fusion is a LIVE-funnel concern (needs the running funnel to
populate extra_signals) and is intentionally NOT faked here.

HONEST: brain mode fetches per-coin OHLCV + backtests, so a tick is slower than momentum's single
fetch_tickers call (bounded by SANDBOX_BRAIN_DEADLINE). Numbers are for LEARNING, not for predicting
live results — fills use a simple synthetic book off the live ticker (not the full exchange order
book / fees / funding that Freqtrade models faithfully; Freqtrade is the faithful money bridge).

State is isolated in trading/state/sandbox_*.json — it never touches the Freqtrade journal/wallet.
"""
from __future__ import annotations

import os
import time

from trading import state
from trading.crypto.paper_engine import PaperEngine

_STATE_FILE = "sandbox_state.json"
_TRADES_FILE = "sandbox_trades.json"
_EXCHANGE = "binance"
_QUOTE = "USDT"
# Sandbox = learn-lab: a LOWER score floor than live (CRYPTO_MIN_SCORE=0.5) so the brain opens many
# trades to learn from. env-tunable; still the REAL per-coin brain gate, just a lower bar.
_SANDBOX_MIN_SCORE = float(os.environ.get("SANDBOX_MIN_SCORE", "0.15"))
_SANDBOX_MIN_PSR = float(os.environ.get("SANDBOX_MIN_PSR", "0.10"))
# wall-clock budget for the per-coin brain pass (per tick) — candidates not decided in time defer
# to the next tick (honest: reported in brain_note), so a slow tick never wedges the loop.
_BRAIN_DEADLINE_S = float(os.environ.get("SANDBOX_BRAIN_DEADLINE", "12"))


def _book_from_price(price: float, *, spread: float = 0.0005, depth: float = 1e9) -> dict:
    """A minimal synthetic order book off the last price (simple, fast). bid/ask = price ∓ spread;
    deep enough to fill any sandbox size. This is the 'simple' part — honest, not exchange-exact."""
    bid, ask = price * (1 - spread), price * (1 + spread)
    return {"bids": [[bid, depth]], "asks": [[ask, depth]]}


class PaperSandbox:
    """Fast, unlimited paper-trading sandbox. One shared instance (singleton via get_sandbox)."""

    def __init__(self):
        self._decider = None       # lazy PerCoinBrainDecider (built on first brain tick)
        self._executor = None      # lazy BrainExecutor — reused ONLY for its cortex-B8 shadow overlay
        self.brain_note = ""       # honest one-liner about the last tick's signal source / fallback
        self._load_state()

    def _load_state(self):
        """(Re)load persisted state from disk — the JSON is the single source of truth shared across
        the dashboard process (reads + control POSTs) and the run_sandbox_loop process (ticks). Called
        at init and via _reload() so a control changed in the UI actually reaches the ticking loop,
        and the dashboard mirrors the loop's latest trades. Engine positions are NOT rebuilt here (the
        ticking process owns them in-memory); the dashboard reads open_trades/balances for display."""
        st = state.load_json(_STATE_FILE, {})
        self.engine = PaperEngine(starting_balance=float(st.get("starting_balance", 100_000.0)),
                                  quote=_QUOTE)
        # restore balances (positions are re-derived from open trades on load)
        self.engine.balance = float(st.get("balance", self.engine.starting_balance))
        self.engine.used_margin = float(st.get("used_margin", 0.0))
        self.engine.realized_pnl = float(st.get("realized_pnl", 0.0))
        self.open_trades: dict = st.get("open_trades", {})     # symbol -> {side, entry, qty, ts, peak}
        self.closed: list = state.load_json(_TRADES_FILE, {}).get("closed", [])
        self.enabled = bool(st.get("enabled", False))
        self.leverage = float(st.get("leverage", 5.0))
        self.stake = float(st.get("stake", 200.0))
        self.max_open = int(st.get("max_open", 0))             # 0 = unlimited (owner's ask)
        self.cycles = int(st.get("cycles", 0))
        # signal source: "brain" (real PerCoinBrainDecider + cortex shadow) or "momentum" (fallback)
        self.signal_mode = str(st.get("signal_mode", "brain")).lower()

    def _reload(self):
        """Re-sync from disk (keeps the ephemeral decider/executor/brain_note in memory)."""
        note = self.brain_note
        self._load_state()
        self.brain_note = note

    # ── persistence ──────────────────────────────────────────────────────────────
    def _save(self):
        state.save_json(_STATE_FILE, {
            "starting_balance": self.engine.starting_balance, "balance": self.engine.balance,
            "used_margin": self.engine.used_margin, "realized_pnl": self.engine.realized_pnl,
            "open_trades": self.open_trades, "enabled": self.enabled, "leverage": self.leverage,
            "stake": self.stake, "max_open": self.max_open, "cycles": self.cycles,
            "signal_mode": self.signal_mode})
        state.save_json(_TRADES_FILE, {"closed": self.closed[-2000:]})

    # ── one tick: pick coins (brain or momentum), open entries, ratchet/brain exits ─
    def tick(self, *, universe_limit: int = 500) -> dict:
        self._reload()          # honor UI control changes (enable/mode/params/reset) before ticking
        if not self.enabled:
            return {"enabled": False}
        self.cycles += 1
        opened, closed = [], []
        movers = self._fast_universe(universe_limit)
        prices = {m["symbol"]: m["price"] for m in movers if m.get("price")}
        # DECISIONS: the REAL brain engine (per-coin backtest × brain-weight + cortex) by default,
        # or plain momentum. decisions[sym] = {"action": LONG|SHORT|EXIT|FLAT, "tag", "conf", ...}.
        decisions = self._decisions(movers, prices)
        # 1) manage exits: brain EXIT instruction FIRST, then the profit-tailgate ratchet + hard stop
        for sym in list(self.open_trades):
            px = prices.get(sym) or self._price(sym)
            if not px:
                continue
            dec = decisions.get(sym)
            if dec and dec.get("action") == "EXIT":
                self._close(sym, px, "brain-exit")
                closed.append(sym)
                continue
            if self._manage_exit(sym, px):
                closed.append(sym)
        # 2) open new entries the decider says LONG/SHORT (unlimited unless max_open set)
        for m in movers:
            if self.max_open and len(self.open_trades) >= self.max_open:
                break
            sym, px = m["symbol"], m.get("price")
            if not px or sym in self.open_trades:
                continue
            dec = decisions.get(sym)
            if not dec or dec.get("action") not in ("LONG", "SHORT"):
                continue
            side = "long" if dec["action"] == "LONG" else "short"
            if self._open(sym, side, px, dec):
                opened.append(sym)
        self._save()
        return {"enabled": True, "cycle": self.cycles, "opened": opened, "closed": closed,
                "mode": self.signal_mode, "note": self.brain_note,
                "open_now": len(self.open_trades), "equity": round(self._equity(prices), 2)}

    # ── decision routing: real brain engine, or momentum fallback ───────────────────
    def _decisions(self, movers: list, prices: dict) -> dict:
        """{symbol: decision} for open positions (in_position=True → may EXIT) and candidates
        (in_position=False → may LONG/SHORT). Brain by default; momentum if selected or on a hard
        brain-build failure (honest fallback noted in self.brain_note)."""
        if self.signal_mode == "momentum":
            self.brain_note = "momentum: top |%change| movers (fast, not the full brain)"
            return self._momentum_decisions(movers)
        decider = self._brain_decider()
        if decider is None:
            self.brain_note = "brain engine unavailable → momentum fallback this tick (honest)"
            return self._momentum_decisions(movers)
        return self._brain_decisions(decider, movers, prices)

    def _open(self, symbol: str, side: str, price: float, dec: dict | None = None) -> bool:
        qty = (self.stake * self.leverage) / price
        r = self.engine.market_order(symbol=symbol, exchange=_EXCHANGE, side=side, amount=qty,
                                     order_book=_book_from_price(price), leverage=self.leverage)
        if r.get("status") != "filled":
            return False
        dec = dec or {}
        self.open_trades[symbol] = {"side": side, "entry": r["avg_price"], "qty": qty,
                                    "ts": time.time(), "peak_pct": 0.0,
                                    # carry the brain's reasoning onto the trade (shown + logged)
                                    "signal": dec.get("source", self.signal_mode),
                                    "tag": dec.get("tag"), "conf": dec.get("conf")}
        return True

    def _manage_exit(self, symbol: str, price: float) -> bool:
        """Profit-tailgate ratchet + hard -8% stop. Returns True if it closed the position."""
        t = self.open_trades.get(symbol)
        if not t:
            return False
        entry, side = t["entry"], t["side"]
        pnl_pct = ((price - entry) / entry if side == "long" else (entry - price) / entry) * 100.0
        t["peak_pct"] = max(t.get("peak_pct", 0.0), pnl_pct)
        # profit tailgate ratchet (reuse the shared learned logic) + hard -8% stop
        exit_now, reason = False, ""
        try:
            from trading.execution import profit_tailgate as pt
            dec = pt.locked_profit("sandbox", "crypto", trade_id=f"sb:{symbol}",
                                   profit_pct=pnl_pct, peak_profit_pct=t["peak_pct"])
            if dec.get("exit"):
                exit_now, reason = True, "tailgate"
        except Exception:
            pass
        if pnl_pct <= -8.0:
            exit_now, reason = True, "stop"
        if not exit_now:
            return False
        self._close(symbol, price, reason)
        return True

    def _close(self, symbol: str, price: float, reason: str) -> None:
        """Close a position in the engine, learn the tailgate distance, append a closed record.
        Shared by the brain-EXIT path and the tailgate/stop path so both book trades identically."""
        t = self.open_trades.get(symbol)
        if not t:
            return
        entry, side = t["entry"], t["side"]
        pnl_pct = ((price - entry) / entry if side == "long" else (entry - price) / entry) * 100.0
        peak = max(t.get("peak_pct", 0.0), pnl_pct)
        self.engine.close(symbol, _EXCHANGE, _book_from_price(price))
        try:
            from trading.execution import profit_tailgate as pt
            pt.learn("sandbox", "crypto", peak_profit_pct=peak, captured_pct=pnl_pct)
            pt.clear_lock(f"sb:{symbol}")
        except Exception:
            pass
        self.closed.append({"symbol": symbol, "side": side, "entry": entry, "exit": price,
                            "pnl_pct": round(pnl_pct, 3), "peak_pct": round(peak, 3),
                            "reason": reason, "closed_ts": time.time(),
                            "held_s": round(time.time() - t["ts"]),
                            # provenance: which signal opened it + the brain's chosen strategy
                            "signal": t.get("signal"), "tag": t.get("tag"), "conf": t.get("conf")})
        self.open_trades.pop(symbol, None)

    # ── real brain decision engine (per-coin backtest × brain-weight + cortex) ──────
    def _brain_decider(self):
        """Lazily build the SAME PerCoinBrainDecider the live crypto loop uses, tuned for the
        learn-lab (lower score/PSR floors → more trades). Returns None on hard build failure so the
        tick honestly falls back to momentum. Also builds a BrainExecutor purely to reuse its
        cortex-B8 shadow overlay (opt-in via CORTEX_SIGNAL — unset → zero change)."""
        if self._decider is not None:
            return self._decider
        try:
            from trading.crypto.freqtrade.percoin_decider import PerCoinBrainDecider
            self._decider = PerCoinBrainDecider(min_final_score=_SANDBOX_MIN_SCORE,
                                                dsr_min=_SANDBOX_MIN_PSR)
            try:
                from trading.crypto.freqtrade.brain_executor import BrainExecutor
                self._executor = BrainExecutor(decider=self._decider, segment="futures")
            except Exception:
                self._executor = None
            return self._decider
        except Exception as e:
            print(f"[sandbox] brain decider build failed: {type(e).__name__}: {e}"[:200], flush=True)
            self._decider = None
            return None

    def _cortex_overlay(self, sym: str, d: dict, *, in_position: bool) -> dict:
        """Reuse BrainExecutor._cortex_shadow verbatim (opt-in). No-op when CORTEX_SIGNAL is unset."""
        if self._executor is None:
            return d
        try:
            return self._executor._cortex_shadow(sym, d, in_position=in_position)
        except Exception:
            return d

    def _brain_decisions(self, decider, movers: list, prices: dict) -> dict:
        """Ask the real brain decider for each open position (in_position=True → EXIT/hold) and each
        candidate mover (in_position=False → LONG/SHORT/flat). Bounded by _BRAIN_DEADLINE_S — coins
        not decided in time defer to the next tick (honest). Returns {symbol: normalized decision}."""
        deadline = time.monotonic() + _BRAIN_DEADLINE_S
        out: dict = {}
        n_ok = n_flat = deferred = 0
        # open positions first — never starve exit decisions on a slow tick
        for sym in list(self.open_trades):
            px = prices.get(sym) or self.open_trades[sym]["entry"]
            d = self._decide_one(decider, sym, px, in_position=True)
            if d is not None:
                out[sym] = d
                n_ok += 1
        # then candidates (skip ones already open)
        for m in movers:
            sym, px = m["symbol"], m.get("price")
            if not px or sym in self.open_trades:
                continue
            if time.monotonic() > deadline:
                deferred += 1
                continue
            d = self._decide_one(decider, sym, px, in_position=False)
            if d is None:
                continue
            out[sym] = d
            if d["action"] in ("LONG", "SHORT"):
                n_ok += 1
            else:
                n_flat += 1
        actionable = sum(1 for d in out.values() if d["action"] in ("LONG", "SHORT", "EXIT"))
        self.brain_note = (f"brain: per-coin backtest × brain-weight + cortex — {actionable} "
                           f"actionable, {n_flat} flat"
                           + (f", {deferred} deferred (deadline)" if deferred else ""))
        return out

    def _decide_one(self, decider, sym: str, price, *, in_position: bool) -> dict | None:
        """One real brain decision + cortex overlay, normalized to the sandbox's decision dict.
        Returns None if the decider errors for this coin (skip — do not fabricate a signal)."""
        try:
            d = decider.decide("CRYPTO", sym, price, in_position=in_position)
            d = self._cortex_overlay(sym, d, in_position=in_position)
        except Exception:
            return None
        meta = d.get("_brain") or {}
        return {"action": d.get("action", "FLAT"), "tag": d.get("tag"),
                "conf": meta.get("confidence"), "source": meta.get("source", "brain")}

    def _momentum_decisions(self, movers: list) -> dict:
        """Fallback: the old plain-momentum signal (top |%change| movers → long/short) as a decision
        map, so the same open/exit machinery drives it. Momentum has no EXIT view — the tailgate
        ratchet + hard stop own exits here."""
        out: dict = {}
        for m in movers:
            chg = m.get("change", 0)
            if abs(chg) < 1.0:
                continue
            out[m["symbol"]] = {"action": "LONG" if chg > 0 else "SHORT",
                                "tag": "momentum", "conf": round(min(1.0, abs(chg) / 10.0), 3),
                                "source": "momentum"}
        return out

    # ── data (fast, ban-safe via the multi-venue pool) ─────────────────────────────
    def _fast_universe(self, limit: int) -> list:
        """Top movers WITH price in ONE ccxt fetch_tickers call (change=percentage, price=last).
        Ban-safe: reuses the App School's cached futures exchange; ranked by |change|."""
        try:
            from trading.broker_sense.app_school import _ccxt_exchange
            ex = _ccxt_exchange("futures")
            tickers = ex.fetch_tickers()
            out = []
            for sym, t in tickers.items():
                if ":USDT" not in sym:                # perps only
                    continue
                pct, last = t.get("percentage"), t.get("last")
                vol = t.get("quoteVolume") or 0
                if pct is None or not last or vol < 1_000_000:
                    continue
                out.append({"symbol": sym, "change": float(pct), "price": float(last)})
            out.sort(key=lambda r: -abs(r["change"]))
            return out[:limit]
        except Exception:
            return []

    def _price(self, symbol: str):
        try:
            from trading.broker_sense import data_failsafe
            q = data_failsafe.quote(symbol, "crypto")
            return float(q.get("last") or q.get("price") or 0) or None
        except Exception:
            return None

    def _equity(self, prices: dict) -> float:
        marks = {self.engine._key(_EXCHANGE, s): (prices.get(s) or self.open_trades[s]["entry"])
                 for s in self.open_trades}
        try:
            return self.engine.equity(marks)
        except Exception:
            return self.engine.balance

    # ── controls + view ───────────────────────────────────────────────────────────
    # NOTE: control POSTs run in the DASHBOARD process; the ticking loop is a SEPARATE process.
    # Each control reloads the loop's latest snapshot from disk BEFORE mutating, so it never clobbers
    # the loop's live trades — it flips one control field on top of fresh state and saves. The loop
    # picks the change up on its next tick (which reloads too). JSON = single source of truth.
    def set_enabled(self, on: bool) -> dict:
        self._reload(); self.enabled = bool(on); self._save(); return self.status()

    def set_mode(self, mode) -> dict:
        """Switch the signal source: "brain" (real per-coin brain engine, default) or "momentum"
        (fast fallback). Anything else is ignored (keeps the current mode)."""
        m = str(mode or "").lower()
        if m in ("brain", "momentum"):
            self._reload()
            self.signal_mode = m
            self._save()
        return self.status()

    def set_params(self, *, starting_balance: float | None = None,
                   stake: float | None = None, leverage: float | None = None) -> dict:
        """Update editable params. starting_balance resets the wallet but keeps trade history.
        max_open is always 0 (unlimited) — owner's directive."""
        self._reload()
        if starting_balance is not None and starting_balance > 0:
            diff = starting_balance - self.engine.starting_balance
            self.engine.starting_balance = starting_balance
            self.engine.balance += diff          # adjust free cash proportionally
        if stake is not None and stake > 0:
            self.stake = float(stake)
        if leverage is not None and leverage > 0:
            self.leverage = float(leverage)
        self.max_open = 0                        # always unlimited
        self._save()
        return self.status()

    def reset(self) -> dict:
        self._reload()          # clear the loop's LATEST state, not a stale snapshot
        self.engine = PaperEngine(starting_balance=self.engine.starting_balance, quote=_QUOTE)
        self.open_trades, self.closed, self.cycles = {}, [], 0
        self.enabled = False    # loop reloads enabled=False next tick → stops (no trade-clobber)
        self._save()
        return self.status()

    def status(self) -> dict:
        self._reload()          # mirror the ticking loop's latest trades/balances for display
        prices = self._all_prices()          # 5s cache — fast
        equity = self._equity(prices)
        unrealized = equity - self.engine.balance - self.engine.used_margin
        wins = [c for c in self.closed if c["pnl_pct"] > 0]
        return {"enabled": self.enabled, "starting_balance": self.engine.starting_balance,
                # wallet breakdown — shown in the panel so the user can see where every USDT is
                "balance": round(self.engine.balance, 2),           # free: not in any trade
                "used_margin": round(self.engine.used_margin, 2),   # locked: margin for open positions
                "unrealized_pnl": round(unrealized, 2),             # open-trade mark-to-market gain/loss
                "realized_pnl": round(self.engine.realized_pnl, 2), # booked from closed trades
                "equity": round(equity, 2),                         # free + margin + unrealized = total
                "open_trades": len(self.open_trades), "max_open": self.max_open or "unlimited",
                "leverage": self.leverage, "stake": self.stake, "cycles": self.cycles,
                "closed_count": len(self.closed),
                "win_rate": round(len(wins) / max(1, len(self.closed)), 3),
                # signal source: which engine is picking coins + the last tick's honest one-liner
                "signal_mode": self.signal_mode, "brain_note": self.brain_note,
                "note": "LEARNING SANDBOX — fast simple fills, not live-accurate (Freqtrade is the "
                        "faithful bridge to real money)"}

    def open_view(self) -> list:
        prices = self._all_prices()               # ONE batched fetch, not per-symbol (fast API)
        # REAL tailgate state (read-only — never mutates the lock file): the ratchet only ARMS once
        # peak ≥ _MIN_ARM_PROFIT, and only exits a POSITIVE trade that retraced to the lock. Show the
        # honest state so "profit below lock" always matches whether an exit is actually pending.
        try:
            from trading.execution import profit_tailgate as pt
            arm = pt._MIN_ARM_PROFIT
            dist = pt.learned_distance("sandbox", "crypto")     # learned trail (~0.30 default → 0.50)
        except Exception:
            arm, dist = 0.5, 0.30
        out = []
        for sym, t in self.open_trades.items():
            px = prices.get(sym) or t["entry"]
            pnl_pct = ((px - t["entry"]) / t["entry"] if t["side"] == "long"
                       else (t["entry"] - px) / t["entry"]) * 100.0
            peak = t.get("peak_pct", 0.0)
            armed = peak >= arm                                  # ratchet engaged?
            locked = round(peak * (1.0 - dist), 3) if armed else None   # None → no active lock yet
            # what will close this trade next: tailgate (armed + positive) vs the −8% hard stop
            exit_by = ("tailgate" if armed else "stop") if pnl_pct <= 0 or armed else "riding"
            if armed and pnl_pct > 0 and pnl_pct <= locked:
                exit_by = "tailgate-pending"                     # should close on the next tick
            out.append({"symbol": sym, "side": t["side"], "entry": round(t["entry"], 6),
                        "price": round(px, 6), "pnl_pct": round(pnl_pct, 3),
                        "peak_pct": round(peak, 3),
                        # honest tailgate fields: locked only when armed; else null + armed flag
                        "tailgate_locked_pct": locked, "tailgate_armed": armed,
                        "tailgate_dist_pct": round(dist * 100, 1), "exit_by": exit_by,
                        # provenance: signal source + brain's chosen strategy + confidence
                        "signal": t.get("signal", "?"), "tag": t.get("tag"),
                        "conf": t.get("conf")})
        return sorted(out, key=lambda r: -r["pnl_pct"])

    _PRICE_CACHE: dict = {}

    def _all_prices(self) -> dict:
        """All open-symbol prices in ONE fetch_tickers call, cached 5s (keeps the GET fast)."""
        hit = PaperSandbox._PRICE_CACHE
        if hit.get("ts") and time.time() - hit["ts"] < 5:
            return hit["prices"]
        prices = {}
        try:
            from trading.broker_sense.app_school import _ccxt_exchange
            tk = _ccxt_exchange("futures").fetch_tickers()
            prices = {s: t.get("last") for s, t in tk.items() if t.get("last")}
        except Exception:
            pass
        PaperSandbox._PRICE_CACHE = {"ts": time.time(), "prices": prices}
        return prices


_SANDBOX: PaperSandbox | None = None


def get_sandbox() -> PaperSandbox:
    global _SANDBOX
    if _SANDBOX is None:
        _SANDBOX = PaperSandbox()
    return _SANDBOX
