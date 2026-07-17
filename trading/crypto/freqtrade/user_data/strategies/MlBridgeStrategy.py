"""MlBridgeStrategy — minimal placeholder Freqtrade strategy (T-split B).

A VALID, runnable IStrategy that emits no automatic entries by default, so a fresh Freqtrade
bot stands up cleanly in dry-run and waits for orders driven via the REST API
(`CryptoEngineClient.place_order` → /forceenter). The real signal logic arrives in Phase C, when
the strategy library (241 static/institutional + 311 brain-created as of 2026-07-16) is translated
into Freqtrade strategies by an adapter.

This file is loaded by the Freqtrade process (not by this repo's package), so importing
`freqtrade`/`pandas` here is fine — those are Freqtrade's own runtime deps.
"""
from __future__ import annotations

from pandas import DataFrame
from freqtrade.strategy import IStrategy


class MlBridgeStrategy(IStrategy):
    """No-auto-entry baseline. Exits are managed by stoploss + REST /forceexit."""

    INTERFACE_VERSION = 3
    timeframe = "5m"

    # Wide, permissive risk frame — real per-trade exits come from the library adapter (Phase C).
    minimal_roi = {"0": 0.10}        # take 10% if it ever gets there
    stoploss = -0.10                 # 10% hard stop (placeholder)
    # MARKET orders (owner's preference): guaranteed immediate fill on entry AND exit — the brain
    # already picks the entry timing, so it wants the fill now, not a resting limit that may miss.
    # /forceenter passes order_type=market too; this keeps exits + stoploss consistent.
    order_types = {"entry": "market", "exit": "market", "stoploss": "market",
                   "stoploss_on_exchange": False}
    trailing_stop = False
    process_only_new_candles = True
    startup_candle_count = 30
    can_short = True                 # futures: allow SHORTs so the brain can trade down-movers
                                     # (most account-first movers are falling — long-only skipped them)

    def leverage(self, pair, current_time, current_rate, proposed_leverage,
                 max_leverage, entry_tag, side, **kwargs):
        """Operator-set leverage from config (futures only); clamp to the exchange max."""
        lev = float(self.config.get("ml_leverage", 1.0) or 1.0)
        return max(1.0, min(lev, max_leverage))

    # ── mlnb X8 (2026-07-17): vol-scaled hard stop, per-trade A/B against the fixed stop ──
    # Live evidence: with the fixed −3%-of-stake stop (0.6% price at 5x), 6 of the first 8
    # matured brain-era closes stopped at 0.7–1.4% price adverse — inside ONE 5m candle of
    # noise on high-vol perps (the research brief's predicted failure: stop must derive from
    # the symbol's volatility, not a fixed number across a universe whose ATR% spans 10x).
    # A/B by trade-id parity: EVEN ids keep the config stoploss (control), ODD ids get
    # K×ATR14(5m) in price space, leverage-scaled into freqtrade's profit-ratio basis and
    # clamped to [ml_stop_min, ml_stop_max] of stake. Scoreboards recover the arm from
    # trade_id % 2 — no extra state. Any failure returns None (keep the default stop).
    use_custom_stoploss = True
    _atr_cache: dict = {}                 # pair -> (monotonic_ts, atr_pct)

    def _atr_pct(self, pair: str) -> float | None:
        import time as _t
        hit = self._atr_cache.get(pair)
        if hit and _t.monotonic() - hit[0] < 120:
            return hit[1]
        try:
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if df is None or len(df) < 20:
                return None
            tail = df.tail(15)
            highs, lows, closes = tail["high"].values, tail["low"].values, tail["close"].values
            trs = []
            for i in range(1, len(tail)):
                trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]),
                               abs(lows[i] - closes[i - 1])))
            atr_pct = 100.0 * (sum(trs) / len(trs)) / float(closes[-1]) if closes[-1] else None
        except Exception:
            atr_pct = None
        self._atr_cache[pair] = (_t.monotonic(), atr_pct)
        return atr_pct

    def custom_stoploss(self, pair, trade, current_time, current_rate, current_profit,
                        after_fill: bool = False, **kwargs):
        try:
            from freqtrade.strategy import stoploss_from_open
            lev = float(getattr(trade, "leverage", 1.0) or 1.0)
            fixed = abs(float(self.config.get("ml_stop_fixed", 0.03) or 0.03))
            # NB: the static `stoploss` attr is freqtrade's WIDEST bound (custom_stoploss can
            # only tighten from it) — it is set to the ml_stop_max backstop in the config, and
            # BOTH arms are enforced here.
            if not bool(self.config.get("ml_stop_ab", True)) or int(trade.id) % 2 == 0:
                return stoploss_from_open(-fixed, current_profit,
                                          is_short=trade.is_short, leverage=lev)
            atr = self._atr_pct(pair)
            if not atr or atr <= 0:                           # no vol read → fixed arm
                return stoploss_from_open(-fixed, current_profit,
                                          is_short=trade.is_short, leverage=lev)
            k = float(self.config.get("ml_stop_atr_k", 1.5) or 1.5)
            lo = abs(float(self.config.get("ml_stop_min", 0.02) or 0.02))
            hi = abs(float(self.config.get("ml_stop_max", 0.08) or 0.08))
            stake_stop = max(lo, min(hi, k * (atr / 100.0) * lev))
            return stoploss_from_open(-stake_stop, current_profit,
                                      is_short=trade.is_short, leverage=lev)
        except Exception:
            return None

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        """mlnb E1 (2026-07-10): IN-ENGINE profit-tailgate enforcement.

        The brain's funnel ratchets a locked-profit floor per open trade into
        profit_tailgate_locks.json, but its own exit pass only runs once per funnel
        cycle (2–4 min) — trades gapped through their locks between passes. This hook
        runs on EVERY bot iteration (~throttle seconds), so the lock the UI shows is
        enforced at engine cadence. The funnel still OWNS the ratchet + the learned
        trail distance; the engine only reads and enforces. `current_profit` is
        Freqtrade's leverage-scaled ratio — the same basis the lock file uses.
        Kill-switch: "mlnb_tailgate_enforce": false in config.json. Never raises.
        """
        try:
            if not self.config.get("mlnb_tailgate_enforce", True):
                return None
            from freqtrade.rpc.api_server.mlnb_sidecar import load_state_json
            lk = (load_state_json(self.config, "profit_tailgate_locks.json", {}) or {}).get(
                str(trade.id))
            locked = lk.get("locked") if isinstance(lk, dict) else None
            if locked is None or float(locked) <= 0:
                return None                         # no armed lock → other exits rule
            # X9: a lock below round-trip fee drag closes red — don't enforce sub-floor locks
            if float(locked) < float(self.config.get("ml_tailgate_min_lock", 0.0) or 0.0):
                return None
            if current_profit * 100.0 <= float(locked):
                return "tailgate_lock"              # engine force-exits at the lock
        except Exception:
            return None                             # sidecar trouble must never block exits
        return None

    def informative_pairs(self):
        """Make extra timeframes available to the LIVE chart (/pair_candles) for every whitelist pair.

        GATED OFF by default: with a 300-pair VolumePairList this loads 300×N extra dataframes every
        loop (network + rate-limit heavy) and can slow live trading. The dashboard chart already falls
        back to /pair_history (disk) for non-strategy timeframes, so this is rarely needed. Enable by
        setting "ml_chart_informatives": ["15m","1h","4h"] (or true → a sane default set) in config.json.
        """
        cfg = self.config.get("ml_chart_informatives")
        if not cfg:
            return []
        tfs = cfg if isinstance(cfg, list) else ["15m", "1h", "4h"]
        tfs = [tf for tf in tfs if tf and tf != self.timeframe]
        try:
            pairs = self.dp.current_whitelist()
        except Exception:
            return []
        return [(pair, tf) for pair in pairs for tf in tfs]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No automatic entries — entries come via REST /forceenter for now.
        dataframe["enter_long"] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        return dataframe
