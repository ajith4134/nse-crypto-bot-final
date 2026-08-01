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

import sys

# Freqtrade is launched as a console script (.venv/bin/freqtrade), so sys.path[0] is .venv/bin
# and the repo root is NOT on the path — a bare `import trading` raises ModuleNotFoundError in
# this process (confirmed 2026-07-21: the Practice Notebook gate was silently failing OPEN because
# confirm_trade_entry's `from trading.brain.practice_gate import gate_decision` raised and the
# except returned True). The lib_* strategies bootstrap the path the same way; do it here too so
# the gate actually loads and can DENY un-confirmed entries.
_PROOT = "/home/karan18190164"
if _PROOT not in sys.path:
    sys.path.insert(0, _PROOT)

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
        """Operator-set leverage from config (futures only); clamp to the exchange max.

        X24: the DIP-REVERSION lane runs at 1x by design. Its edge needs a ~2%-of-PRICE stop
        to survive (measured: a 0.8% stop halves it, +0.185% vs +0.444% net), and at 5x that
        would be 10% of stake. At 1x the same price stop costs 2% of stake — the risk the
        edge was measured under.
        """
        if str(entry_tag or "").startswith(("dip_revert", "spike_fade", "wm_")):
            # spike_fade (2026-07-22): same reasoning — its 3% price stop was measured at 1x.
            # wm_ (owner's window-movers experiment): 1x so its 1% price stop = 1% of stake
            # and the bandit's P&L labels are pure price moves, not leverage artifacts.
            return 1.0
        lev = float(self.config.get("ml_leverage", 1.0) or 1.0)
        return max(1.0, min(lev, max_leverage))

    # ── PRACTICE NOTEBOOK gate (2026-07-21 owner) ──────────────────────────────
    # The brain's "rough paper": a pick only opens once realised price DOUBLE-CONFIRMS the
    # predicted direction. This is the hard, cross-path gate — it fires for EVERY entry
    # (bot + REST /forceenter, freqtradebot.py mode=="initial"). It reads the notebook's
    # confirmed set from a state file (import-safe, no WS mirror in this process); a pick that
    # isn't confirmed yet registers a request (the notebook runner starts the confirm clock)
    # and is denied for now. LONG-only opening + abstention are enforced inside gate_decision.
    # Fails OPEN if the gate module can't load (paper learn-lab) — never wedges the engine.
    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force,
                            current_time, entry_tag, side, **kwargs) -> bool:
        # MOMENTUM+VOLATILITY gate (owner 2026-07-22: "only momentum and volatile
        # stocks to open"): a pair that is neither MOVING nor VOLATILE right now may
        # not open, whatever lane picked it. Runs BEFORE the notebook gate so a quiet
        # symbol never even starts a confirmation clock. Unmeasurable = DENY (the
        # "only" is literal); an unexpected code error fails OPEN like the gate below.
        try:
            ok, why = self._momvol_gate(pair)
            if not ok:
                print(f"[momvol-gate] DENY {pair} {side} tag={entry_tag} ({why})",
                      flush=True)
                return False
        except Exception as e:
            print(f"[momvol-gate] error, fail-open {pair}: "
                  f"{type(e).__name__}: {e}", flush=True)
        try:
            from trading.brain.practice_gate import gate_decision
            return bool(gate_decision(pair, side))
        except Exception:
            return True

    # ── MOMENTUM+VOLATILITY entry gate (owner 2026-07-22) ─────────────────────
    # Primary read (local candles, free): MULTI-WINDOW momentum — |move| over the
    # last 5m / 15m / 30m / 1h (owner 2026-07-22: "measured by the last 5m, 15m,
    # 30min and 1hr — if ANY of these timeframes is momentum ... then open"). Each
    # window has its own threshold (shorter window = smaller bar); ONE passing
    # window = momentum. Volatility stays ATR14(5m)% (reuses _atr_pct's cache).
    # Fallback when this process has no candles for the pair yet (fresh forceenter
    # outside the analyzed set): the exchange 24h ticker — |24h change|% as momentum,
    # 24h (high−low)/last% as volatility. Thresholds and both/either mode come from
    # config (ml_momvol_* ← ML_MOMVOL_* env at engine start). Decisions cached
    # 90s/pair; each verdict is journaled to state/momvol_gate.json so "why did
    # nothing open?" has an honest answer.
    _momvol_cache: dict = {}              # pair -> (monotonic_ts, ok, why)

    @staticmethod
    def _momvol_windows(cfg) -> list[tuple[int, float]]:
        """Parse ml_momvol_windows 'minutes:min_pct,...' → [(minutes, min_pct)]."""
        raw = str(cfg.get("ml_momvol_windows", "") or
                  "5:0.3,15:0.45,30:0.6,60:0.8")
        out = []
        for part in raw.split(","):
            try:
                m, thr = part.strip().split(":")
                out.append((int(m), float(thr)))
            except Exception:
                continue
        return out or [(5, 0.3), (15, 0.45), (30, 0.6), (60, 0.8)]

    def _momvol_gate(self, pair: str) -> tuple[bool, str]:
        import time as _t
        cfg = self.config
        if not cfg.get("ml_momvol_gate", True):
            return True, "gate off"
        hit = self._momvol_cache.get(pair)
        if hit and _t.monotonic() - hit[0] < 90:
            return hit[1], hit[2]
        min_atr = float(cfg.get("ml_momvol_min_atr_pct", 0.20) or 0.20)
        atr = self._atr_pct(pair)
        moms: list[str] = []              # per-window read-outs for the why string
        m_ok = None                       # None = no window computable
        try:
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if df is not None and len(df) >= 2:
                c = df["close"].values
                for mins, thr in self._momvol_windows(cfg):
                    n = max(1, mins // 5)             # 5m candles in this window
                    if len(c) < n + 1 or not float(c[-(n + 1)]):
                        continue
                    mom = 100.0 * abs(float(c[-1]) / float(c[-(n + 1)]) - 1.0)
                    hit_w = mom >= thr
                    m_ok = bool(m_ok) or hit_w
                    moms.append(f"{mins}m={mom:.2f}{'✓' if hit_w else ''}(min {thr})")
        except Exception:
            m_ok = None
        v_ok = (atr >= min_atr) if atr is not None else None
        why_m = f"mom[{' '.join(moms)}]" if m_ok is not None else None
        why_v = f"atr5m={atr:.2f}%(min {min_atr})" if atr is not None else None
        # Ticker fills ONLY the missing half (candle reads are never discarded):
        # 24h |change| stands in for momentum, 24h (high−low)/last for volatility.
        if m_ok is None or v_ok is None:
            try:
                tk = self.dp.ticker(pair)
                if m_ok is None:
                    chg = abs(float(tk.get("percentage") or 0.0))
                    min24 = float(cfg.get("ml_momvol_min_mom_24h_pct", 5.0) or 5.0)
                    m_ok = chg >= min24
                    why_m = f"24h_chg={chg:.1f}%(min {min24})"
                if v_ok is None:
                    last = float(tk.get("last") or 0.0)
                    rng = (100.0 * (float(tk.get("high") or 0.0) -
                                    float(tk.get("low") or 0.0)) / last) if last else 0.0
                    minrng = float(cfg.get("ml_momvol_min_range_24h_pct", 6.0) or 6.0)
                    v_ok = rng >= minrng
                    why_v = f"24h_range={rng:.1f}%(min {minrng})"
            except Exception as e:
                # can't measure momentum or volatility → not provably a mover → deny
                why = f"unmeasurable ({type(e).__name__}) — deny"
                self._momvol_cache[pair] = (_t.monotonic(), False, why)
                self._momvol_note(pair, False, why)
                return False, why
        why = f"{why_m} {why_v}"
        mode = str(cfg.get("ml_momvol_mode", "both") or "both").strip().lower()
        ok = (m_ok or v_ok) if mode == "either" else (m_ok and v_ok)
        self._momvol_cache[pair] = (_t.monotonic(), ok, why)
        self._momvol_note(pair, ok, why)
        return ok, why

    def _momvol_note(self, pair: str, ok: bool, why: str) -> None:
        """Rolling verdict journal (state/momvol_gate.json) — dashboard/status honesty."""
        try:
            import time as _t
            from trading import state as _st

            def _upd(d):
                d = d or {}
                d["allow" if ok else "deny"] = int(d.get("allow" if ok else "deny", 0)) + 1
                rec = d.get("recent") or []
                rec.append({"pair": pair, "ok": ok, "why": why, "ts": _t.time()})
                d["recent"] = rec[-30:]
                return d
            _st.mutate_json("momvol_gate.json", _upd, default={})
        except Exception:
            pass

    # ── mlnb X8 (2026-07-17): vol-scaled hard stop, per-trade A/B against the fixed stop ──
    # Live evidence: with the fixed −3%-of-stake stop (0.6% price at 5x), 6 of the first 8
    # matured brain-era closes stopped at 0.7–1.4% price adverse — inside ONE 5m candle of
    # noise on high-vol perps (the research brief's predicted failure: stop must derive from
    # the symbol's volatility, not a fixed number across a universe whose ATR% spans 10x).
    # A/B by trade-id parity: EVEN ids keep the config stoploss (control), ODD ids get
    # K×ATR14(5m) in price space, leverage-scaled into freqtrade's profit-ratio basis and
    # clamped to [ml_stop_min, ml_stop_max] of stake. Scoreboards recover the arm from
    # trade_id % 2 — no extra state. Any failure returns None (keep the default stop).
    # X8 VERDICT (2026-07-18, n≈190/arm): vol beat fixed on net (−127 vs −339), green
    # (.40 vs .29) and stop-rate (.33 vs .60) → ml_stop_mode "vol" promotes the ATR stop
    # to ALL trades; "ab" keeps the parity split for re-checks; "fixed" is pre-X8.
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
            # X24 dip lane: its own stop, in PRICE terms. Measured optimum ~2% of price
            # (35% hit-rate, +0.444% net); our normal 4%-of-stake clamp at 5x is 0.8% of
            # price and would stop out 62.6% of these winners before the reversion lands.
            if str(getattr(trade, "enter_tag", "") or "").startswith("dip_revert"):
                dip_stop = abs(float(self.config.get("ml_dip_stop_price_pct", 2.0) or 2.0))
                return stoploss_from_open(-(dip_stop / 100.0) * lev, current_profit,
                                          is_short=trade.is_short, leverage=lev)
            # spike_fade (2026-07-22): 3% PRICE stop — measured: a 2% stop makes the fade
            # ~breakeven (squeeze-through rate 45-55%), 3% keeps +0.09..0.13%/trade.
            if str(getattr(trade, "enter_tag", "") or "").startswith("spike_fade"):
                sp_stop = abs(float(self.config.get("ml_spike_stop_price_pct", 3.0) or 3.0))
                return stoploss_from_open(-(sp_stop / 100.0) * lev, current_profit,
                                          is_short=trade.is_short, leverage=lev)
            # wm_ window-movers (owner 2026-07-22): the owner's 1% price stop, at 1x.
            if str(getattr(trade, "enter_tag", "") or "").startswith("wm_"):
                wm_stop = abs(float(self.config.get("ml_wm_stop_price_pct", 1.0) or 1.0))
                return stoploss_from_open(-(wm_stop / 100.0) * lev, current_profit,
                                          is_short=trade.is_short, leverage=lev)
            fixed = abs(float(self.config.get("ml_stop_fixed", 0.03) or 0.03))
            # NB: the static `stoploss` attr is freqtrade's WIDEST bound (custom_stoploss can
            # only tighten from it) — it is set to the ml_stop_max backstop in the config, and
            # BOTH arms are enforced here.
            mode = str(self.config.get("ml_stop_mode",
                       "ab" if bool(self.config.get("ml_stop_ab", True)) else "fixed")).lower()
            # "price" mode (owner 2026-07-22: "tighten the stoploss to 1%"): the stop is a
            # FIXED PERCENT OF PRICE, so changing ml_leverage no longer silently changes the
            # price-room (the 10x bump had halved every stop to 0.8% of price). The static
            # `stoploss` attr in config must stay WIDER than ml_stop_price_pct × leverage.
            if mode == "price":
                ppct = abs(float(self.config.get("ml_stop_price_pct", 1.0) or 1.0))
                return stoploss_from_open(-(ppct / 100.0) * lev, current_profit,
                                          is_short=trade.is_short, leverage=lev)
            if mode == "fixed" or (mode != "vol" and int(trade.id) % 2 == 0):
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
        # X15 (2026-07-18): ENGINE-SIDE RATCHET — protection that does not depend on the
        # funnel's file. MEASURED: 134 trades in 24h peaked at >=2% of stake (median +3.49%,
        # max +10.42%) and still closed RED, costing -1,225; 56 of them rode from profit all
        # the way to the hard stop. Root cause: profit_tailgate_locks.json is written ONLY by
        # the funnel, whose cycles now take 400-655s (the docstring below assumed 2-4 min), so
        # a fast mover peaks and dies between passes and NO lock ever exists for the engine to
        # enforce. freqtrade tracks max_rate/min_rate on every iteration, so the ratchet can be
        # derived here at engine cadence. Uses the same arm/distance semantics as the funnel;
        # the funnel's file lock still wins when it is HIGHER (it carries the learned distance).
        # Kill switch: ml_engine_ratchet=false.
        # X24 DIP LANE: no ratchet, no tailgate — a TIME exit instead. MEASURED: every
        # take-profit level DESTROYS this edge (hold-full-hour +0.538%; TP at 1.5% -> +0.167%;
        # TP at 3% -> +0.386%; stop+TP combined -> −0.070%). The reversion needs room to
        # complete, so the winners must run and the exit is the clock, not a profit target.
        try:
            if str(getattr(trade, "enter_tag", "") or "").startswith("dip_revert"):
                hold_min = float(self.config.get("ml_dip_hold_min", 60) or 60)
                age = (current_time - trade.open_date_utc).total_seconds() / 60.0
                if age >= hold_min:
                    return "dip_time_exit"
                return None                 # never let the ratchet/tailgate touch this lane
            # spike_fade: same clock-not-target exit — the fade needs the hour to complete.
            if str(getattr(trade, "enter_tag", "") or "").startswith("spike_fade"):
                hold_min = float(self.config.get("ml_spike_hold_min", 60) or 60)
                age = (current_time - trade.open_date_utc).total_seconds() / 60.0
                if age >= hold_min:
                    return "spike_time_exit"
                return None                 # never let the ratchet/tailgate touch this lane
            # wm_ window-movers: fixed 60m horizon so every bandit label is comparable.
            if str(getattr(trade, "enter_tag", "") or "").startswith("wm_"):
                hold_min = float(self.config.get("ml_wm_hold_min", 60) or 60)
                age = (current_time - trade.open_date_utc).total_seconds() / 60.0
                if age >= hold_min:
                    return "wm_time_exit"
                return None                 # clean labels: no ratchet/tailgate interference
        except Exception:
            return None
        _eng_lock = 0.0
        try:
            if self.config.get("ml_engine_ratchet", True):
                lev = float(getattr(trade, "leverage", 1.0) or 1.0)
                op = float(getattr(trade, "open_rate", 0.0) or 0.0)
                if op > 0:
                    if trade.is_short:
                        ext = float(getattr(trade, "min_rate", 0.0) or 0.0)
                        peak = ((op - ext) / op * lev * 100.0) if ext > 0 else 0.0
                    else:
                        ext = float(getattr(trade, "max_rate", 0.0) or 0.0)
                        peak = ((ext - op) / op * lev * 100.0) if ext > 0 else 0.0
                    peak = max(peak, current_profit * 100.0)
                    arm = float(self.config.get("ml_ratchet_arm_pct", 1.0) or 1.0)
                    dist = float(self.config.get("ml_ratchet_dist", 0.2) or 0.2)
                    if peak >= arm:
                        _eng_lock = peak * (1.0 - dist)
                        if current_profit * 100.0 <= _eng_lock:
                            return "engine_ratchet"
        except Exception:
            pass                                # never block exits
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
