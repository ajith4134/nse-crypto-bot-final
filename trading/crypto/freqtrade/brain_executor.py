"""trading/crypto/freqtrade/brain_executor.py — brain reads strategies as instructions (Phase G).

The unifying execution model: strategies that can't run INSIDE Freqtrade's candle engine
(order-flow, market-making, multi-asset, options-proxy, …) don't have to. The brain RUNS each
library strategy's signal on the real ccxt data layer, reads the +1/-1/0 output as an entry/exit
INSTRUCTION, ensembles them per symbol, and drives Freqtrade over REST (forceenter/forceexit).
Freqtrade is the single execution venue + risk + journal; the brain is the universal signal source.

`LibraryBrainDecider.decide(market, symbol, price, in_position)` returns the same decision dict the
live-loop already routes to Freqtrade via `_route_crypto_engine` (Phase E) — so wiring this in as
the loop's decider makes the brain fully drive Freqtrade with the whole strategy library.

Today this runs the SIGNAL-based strategies (OHLCV-computable). As Waves 1B/1C/3 add live data
(Deribit chains, multi-asset joins, L2/tick), their live signals plug into the same ensemble — the
instruction→execution path doesn't change.
"""
from __future__ import annotations

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
        try:
            # OHLCV comes from the spot ccxt feed even when the bot trades futures perps.
            raw = self._client()._client().fetch_ohlcv(_spot(symbol), self._tf, limit=self._lookback)
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
        # decision: open on a net long majority; exit when the net turns non-positive
        action = "FLAT"
        if in_position:
            action = "EXIT" if net <= 0 else "FLAT"
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


class BrainExecutor:
    """Drives Freqtrade DIRECTLY from the brain's library instructions (full control), independent
    of the segment-gated live-loop. Per cycle: for each symbol, read the ensemble instruction and
    forceenter (open) / close_pair (exit) on Freqtrade. The brain decides; Freqtrade executes."""

    def __init__(self, decider: LibraryBrainDecider | None = None, client=None,
                 symbols: list | None = None, learner=None):
        if decider is None:
            # Default: brain PICKS the best strategy per coin (backtest × brain), or stays flat.
            # Lazy import avoids a module cycle (percoin_decider imports LibraryBrainDecider).
            from trading.crypto.freqtrade.percoin_decider import PerCoinBrainDecider
            decider = PerCoinBrainDecider()
        self.decider = decider
        self._client = client
        self._symbols = symbols
        # Optional BrainLearningCycle: its confirmed hypotheses veto entries on strong contrary
        # evidence (advisory feedback — closes the learn→act loop; never forces new entries).
        self.learner = learner
        self._last_picks: dict = {}      # symbol -> chosen-strategy meta (for logs / dashboard)
        self._last_vetoes: list = []     # symbols an entry was blocked on by confirmed evidence

    def client(self):
        if self._client is None:
            from trading.crypto.engine_client import CryptoEngineClient
            self._client = CryptoEngineClient()
        return self._client

    def symbols(self) -> list:
        """Default universe = Freqtrade's OWN whitelisted pairs, in the bot's native format
        (futures perps come back as 'BTC/USDT:USDT' — the exact string /forceenter expects)."""
        if self._symbols is not None:
            return self._symbols
        # /whitelist returns the live (dynamic) pairlist; show_config().whitelist is empty for
        # VolumePairList, which is why entries silently no-op'd before (spot pair → futures bot).
        wl = self.client().whitelist()
        if wl:
            return wl[:50]
        try:
            cfg = self.client().show_config()
            base = list(cfg.get("whitelist") or cfg.get("pairs") or [])
            if base:
                return base[:50]
        except Exception:
            pass
        return ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]

    def run_once(self, *, allow_live: bool = False) -> dict:
        """One brain→Freqtrade execution cycle. Returns a summary. Never raises."""
        cli = self.client()
        try:
            open_pairs = set(cli.open_pairs())
        except Exception:
            open_pairs = set()
        entered, exited, skipped = [], [], 0
        picks: dict = {}
        vetoes: list = []
        for sym in self.symbols():
            try:
                d = self.decider.decide("CRYPTO", sym, None, in_position=(sym in open_pairs))
                act = d.get("action")
                tag = d.get("tag")                       # brain's chosen strategy for this coin
                brain = d.get("_brain") or {}
                if brain.get("chosen_strategy"):
                    picks[sym] = {"strategy": brain.get("chosen_strategy"), "action": act,
                                  "final_score": brain.get("final_score"), "sharpe": brain.get("sharpe"),
                                  "win_rate": brain.get("win_rate"), "p_win": brain.get("p_win")}
                # Closed-loop feedback: block a new entry only when CONFIRMED hypotheses give
                # strong contrary evidence for that direction. Advisory (never forces entries).
                if act in ("LONG", "SHORT") and sym not in open_pairs \
                        and self._entry_vetoed(sym, act, brain):
                    vetoes.append(sym)
                    skipped += 1
                    continue
                if act == "LONG" and sym not in open_pairs:
                    cli.place_order(symbol=sym, action="BUY", side="long",
                                    allow_live=allow_live, enter_tag=tag)
                    entered.append(sym)
                elif act == "SHORT" and sym not in open_pairs:
                    cli.place_order(symbol=sym, action="BUY", side="short",
                                    allow_live=allow_live, enter_tag=tag)
                    entered.append(sym)
                elif act == "EXIT" and sym in open_pairs:
                    cli.close_pair(sym)
                    exited.append(sym)
                else:
                    skipped += 1
            except Exception:
                skipped += 1
        self._last_picks = picks
        self._last_vetoes = vetoes
        return {"entered": entered, "exited": exited, "skipped": skipped,
                "universe": len(self.symbols()), "picks": picks, "vetoes": vetoes}

    def _entry_vetoed(self, sym: str, act: str, brain: dict) -> bool:
        """True when the learner's CONFIRMED hypotheses strongly contradict this entry.
        Conservative: only a bias ≤ -0.5 AGAINST the action direction (backed by ≥1 confirmed
        hypothesis) blocks it. Never raises; no learner → never vetoes."""
        if self.learner is None:
            return False
        try:
            direction = 1 if act == "LONG" else -1
            ctx = {"market": "CRYPTO", "symbol": sym,
                   "direction": act, "market_regime_entry": brain.get("regime")}
            sup = self.learner.support(ctx)
            if sup.get("n"):
                return (float(sup.get("bias", 0.0)) * direction) <= -0.5
        except Exception:
            pass
        return False
