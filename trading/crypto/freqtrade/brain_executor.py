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
                 symbols: list | None = None, learner=None, segment: str | None = None):
        if decider is None:
            # Default: brain PICKS the best strategy per coin (backtest × brain), or stays flat.
            # Lazy import avoids a module cycle (percoin_decider imports LibraryBrainDecider).
            from trading.crypto.freqtrade.percoin_decider import PerCoinBrainDecider
            decider = PerCoinBrainDecider()
        self.decider = decider
        self._client = client
        self._symbols = symbols
        # Multi-segment engine: which bot this executor drives (futures/spot/options/
        # prediction; None = legacy single-bot). Options/prediction use dedicated cycle
        # logic below — their instruments have no per-coin backtest library data.
        self.segment = segment
        # Optional BrainLearningCycle: its confirmed hypotheses veto entries on strong contrary
        # evidence (advisory feedback — closes the learn→act loop; never forces new entries).
        self.learner = learner
        self._last_picks: dict = {}      # symbol -> chosen-strategy meta (for logs / dashboard)
        self._last_vetoes: list = []     # symbols an entry was blocked on by confirmed evidence
        # Broker-Sense funnel (trading/broker_sense): per-symbol app-derived context
        # (screener lane, candle-image CNN read, screen-mirror bid/ask, discovered learning
        # columns) set before run_once; merged into decision_snapshot as "app_signals".
        self.extra_signals: dict = {}

    def client(self):
        if self._client is None:
            from trading.crypto.engine_client import CryptoEngineClient
            self._client = CryptoEngineClient()
        return self._client

    # Universe cap: how many of the whitelisted pairs the brain evaluates per cycle.
    # Operator goal (2026-07-02): trade "all the symbols, without limit" → the DEFAULT is now
    # UNLIMITED (0 = evaluate every whitelisted pair). env BRAIN_UNIVERSE still caps it for CPU
    # tuning: BRAIN_UNIVERSE=150 evaluates the top 150 by volume, BRAIN_UNIVERSE=0/unset = all.
    # Each evaluated pair runs the per-coin backtest, so all-symbols = more CPU/cycle (fine on the
    # 5m timeframe; if a cycle gets slow, set BRAIN_UNIVERSE to a finite cap or add round-robin).
    def _universe_cap(self) -> int:
        import os
        try:
            v = int(os.environ.get("BRAIN_UNIVERSE", "0"))
        except Exception:
            return 0
        return max(0, v)          # 0 = no limit (all whitelisted pairs)

    def symbols(self) -> list:
        """Default universe = Freqtrade's OWN whitelisted pairs, in the bot's native format
        (futures perps come back as 'BTC/USDT:USDT' — the exact string /forceenter expects).
        No cap by default → every whitelisted symbol is a candidate each cycle."""
        if self._symbols is not None:
            return self._symbols
        cap = self._universe_cap()                       # 0 = unlimited
        # /whitelist returns the live (dynamic) pairlist; show_config().whitelist is empty for
        # VolumePairList, which is why entries silently no-op'd before (spot pair → futures bot).
        wl = self.client().whitelist(segment=self.segment)
        if wl:
            return wl if cap == 0 else wl[:cap]
        try:
            cfg = self.client().show_config()
            base = list(cfg.get("whitelist") or cfg.get("pairs") or [])
            if base:
                return base if cap == 0 else base[:cap]
        except Exception:
            pass
        if self.segment in ("options", "prediction"):
            return []  # dynamic universes only — no meaningful hardcoded fallback
        return ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]

    def sweep_pullbacks(self, cli=None, *, allow_live: bool = False) -> dict:
        """D3: enter every armed pullback entry whose retrace has arrived. Called from
        run_once AND every PULLBACK_SWEEP_SEC by the funnel loop's fast sweeper thread
        (a 0.15-0.5×ATR retrace is often gone within minutes — waiting for the next
        20-40min cycle expired 7/8 armed entries on 2026-07-11). pullback.sweep pops
        triggered rows under the state-file lock, so a row fires exactly once no
        matter how many sweepers race. Never raises."""
        rep: dict = {"entered": [], "queued": []}
        try:
            from trading.direction import pullback as _pb
            if not _pb.enabled():
                return rep
            cli = cli or self.client()
            for _row in _pb.sweep(
                    lambda s: _pb.live_price(s, self.segment or "futures"),
                    segment=self.segment or "futures"):
                try:
                    _psym = cli.tradeable_form(_row["symbol"], self.segment)
                    if _psym is None:
                        continue
                    _res = cli.place_order(
                        symbol=_psym, action="BUY",
                        side=("long" if _row["direction"] == "LONG" else "short"),
                        allow_live=allow_live,
                        enter_tag=str(_row.get("source") or "pullback"),
                        segment=self.segment)
                    if isinstance(_res, dict) and _res.get("ok") is False:
                        continue
                    if isinstance(_res, dict) and _res.get("queued"):
                        rep["queued"].append(_psym)
                    else:
                        rep["entered"].append(_psym)
                    self._record_entry_meta(
                        _psym, _row["direction"], _row.get("source"),
                        {"pullback": {k: _row.get(k) for k in
                                      ("ref_price", "entry_ref", "atr",
                                       "armed_ts")}}, None, explore=True)
                except Exception:
                    continue
        except Exception:
            pass
        return rep

    def run_once(self, *, allow_live: bool = False, deadline: float | None = None) -> dict:
        """One brain→Freqtrade execution cycle. Returns a summary. Never raises.

        `deadline` (time.monotonic value): symbols not yet decided when it passes are
        deferred to the next cycle (reported as `deadline_deferred`) — a caller with a
        wall-clock budget (the Broker-Sense funnel) is never wedged by per-symbol cost."""
        if self.segment == "options":
            return self._run_options_cycle(allow_live=allow_live, deadline=deadline)
        if self.segment == "prediction":
            return self._run_prediction_cycle(allow_live=allow_live)
        cli = self.client()
        try:
            open_pairs = set(cli.open_pairs(segment=self.segment))
        except Exception:
            open_pairs = set()
        # Boss entry policy (trading/brain/boss.py): mode + below-target pressure decide how
        # strict the safety gates are THIS cycle (profit = full strength; data_collect or
        # "open at least N" pressure = gates advisory). Honest: bypasses are recorded.
        try:
            from trading.brain import boss as _boss
            policy = _boss.entry_policy("CRYPTO", self.segment or "futures",
                                        open_now=len(open_pairs))
        except Exception:
            policy = {"uq_advisory": False, "psych_veto": self._PSYCH_VETO, "pressure": False}
        # EXPLORE OPEN-ALL (owner 2026-07-06): until the brain has learned from enough CLOSED
        # trades, open EVERY candidate the broker pickers surface — direction from the symbol's
        # OWN Binance app data — with the veto gates ADVISORY, so the journal fills with richly-
        # labelled trades to learn from. PAPER ONLY; auto-graduates to the selective gate at the
        # threshold. Every bypass is still recorded honestly (decision_snapshot + app_signals).
        explore = (not allow_live) and self._explore_open_all(open_now=len(open_pairs))
        entered, exited, skipped = [], [], 0
        queued: list = []                      # inbox mode: queued-not-yet-filled decisions
        picks: dict = {}
        vetoes: list = []
        deadline_deferred = 0
        # PROFIT TAILGATING pass (owner feature): over EVERY open trade, ratchet the locked-profit
        # floor up with the peak and force an exit when profit falls to the lock — so winners are
        # ridden and gains are locked. The brain learns the trail distance from outcomes (below).
        tailgated = self._tailgate_pass(cli, allow_live=allow_live)
        exited.extend(tailgated)
        armed_n = 0
        # D3 pullback entries (Pillar 27): armed verdicts whose price has pulled back
        # to us fire NOW. Retraces live on second-scale while funnel cycles are
        # minute-scale, so the funnel loop's fast sweeper thread also calls
        # sweep_pullbacks between cycles — this in-cycle pass stays as the fallback.
        _sw = self.sweep_pullbacks(cli, allow_live=allow_live)
        entered.extend(_sw["entered"])
        queued.extend(_sw["queued"])
        syms = self.symbols()
        # Voted candidates FIRST: a budget-starved cycle must spend its remaining
        # seconds on the symbols the funnel's LOOK stage actually voted on —
        # whitelist order let 43/44 decisions defer while the 5 voted candidates
        # never even armed (2026-07-11 06:17 cycle, deadline_deferred=43).
        _voted = set(getattr(self, "extra_signals", {}) or {})
        if _voted:
            syms = sorted(syms, key=lambda s: s not in _voted)
        for i, sym in enumerate(syms):
            if deadline is not None and time.monotonic() > deadline:
                deadline_deferred = len(syms) - i        # honest: deferred, not decided
                break
            try:
                # FAST EXPLORE PATH (owner 2026-07-06): skip the heavy per-symbol ensemble — take
                # the direction straight from the symbol's Binance app data — so ALL candidates open
                # within the cycle budget (the slow decide() only reached ~1/cycle). Records the FULL
                # app_signals as columns; heavy attribution/episode resolve at close. Paper only.
                if explore and sym not in open_pairs:
                    _sig = (getattr(self, "extra_signals", {}) or {}).get(sym, {}) or {}
                    _v = _sig.get("vote") or {}
                    _pup = _v.get("p_up")
                    if _v.get("direction") == "long":
                        _act = "LONG"
                    elif _v.get("direction") == "short":
                        _act = "SHORT"
                    elif _pup is not None:
                        _act = "LONG" if float(_pup) >= 0.5 else "SHORT"
                    else:
                        _act = "LONG"
                    # D2 Mirror Gate (Pillar 27): correct/veto the explore direction with
                    # the source's MEASURED accuracy (this default-LONG path graded 40%).
                    _mg = None
                    try:
                        from trading.direction import mirror_gate
                        from trading.direction.regime import classify as _rg
                        _act, _mg = mirror_gate.apply(
                            _act, source="explore_open_all", symbol=sym,
                            segment=self.segment or "futures", regime=_rg(sym).get("regime"))
                    except Exception:
                        _mg = None
                    if _act is None:                  # proven coin-flip → skip honestly
                        skipped += 1
                        continue
                    # D3: don't chase the spike — arm the verdict; the next sweeps enter
                    # on the k×ATR (pct fallback) retrace. Quote missing → fall through
                    # to the immediate entry (honest degradation, never a silent drop).
                    try:
                        from trading.direction import pullback as _pb
                        if _pb.enabled():
                            _q = _pb.live_price(sym, self.segment or "futures")
                            if not _q:
                                # UI-only mode Nones the quote path and each pair's
                                # feather is fresh only ~half the time (updater
                                # rotation) — but the VERIFY stage fetched this
                                # symbol's order book seconds ago THIS cycle: its mid
                                # is an equally honest arm reference (2026-07-11:
                                # None here dumped ~24 entries/cycle straight to
                                # market with no retrace discount).
                                _bk = _sig.get("book") or {}
                                if _bk.get("bid") and _bk.get("ask"):
                                    _q = (float(_bk["bid"]) + float(_bk["ask"])) / 2
                            if _q and _pb.arm(symbol=sym,
                                              segment=self.segment or "futures",
                                              direction=_act,
                                              source="explore_open_all",
                                              ref_price=float(_q),
                                              atr=_pb.atr_from_feather(
                                                  sym, self.segment or "futures")):
                                armed_n += 1
                                continue
                    except Exception:
                        pass
                    try:
                        # Broker-app picks arrive in the app's own book (ADA/RUB, BSW/TRY —
                        # delisted quote books): route to the engine-tradeable USDT book,
                        # or skip honestly. Fixes phantom "entered" (2026-07-09): a refused
                        # order used to be counted as an entry because the guard's
                        # {"ok": False} reply was never checked.
                        _tsym = cli.tradeable_form(sym, self.segment)
                        if _tsym is None:
                            skipped += 1
                            continue
                        _res = cli.place_order(symbol=_tsym, action="BUY",
                                               side=("long" if _act == "LONG" else "short"),
                                               allow_live=allow_live,
                                               enter_tag="explore_open_all",
                                               segment=self.segment)
                        if isinstance(_res, dict) and _res.get("ok") is False:
                            skipped += 1
                            continue
                        if isinstance(_res, dict) and _res.get("queued"):
                            # inbox mode: queued ≠ filled — meta still recorded (joins by
                            # pair+time at fill), but never booked as an entry
                            queued.append(_tsym)
                            self._record_entry_meta(_tsym, _act, "explore_open_all",
                                                    {"explore": True, "mirror_gate": _mg}, None, explore=True)
                            continue
                        entered.append(_tsym)
                        # #13: use the FULL recorder (psych read + FinMem episode +
                        # attribution + ui_view) so explore trades carry the same
                        # learning columns as selective ones — explore exists to
                        # produce richly-labelled training data, not blank rows.
                        if _tsym != sym and sym in (getattr(self, "extra_signals", {}) or {}):
                            # the entry meta joins by TRADED pair — carry the pick's signals over
                            self.extra_signals[_tsym] = self.extra_signals[sym]
                        self._record_entry_meta(_tsym, _act, "explore_open_all",
                                                {"explore": True, "mirror_gate": _mg}, None, explore=True)
                    except Exception:
                        skipped += 1
                    continue
                # DISTILLED MICRO-POLICY (invent-beyond #4): the nightly-distilled student
                # answers in ~ms from the persisted per-coin winner table + LightGBM student;
                # None (unknown coin / stale teacher / unconfident) falls through to the full
                # 153-strategy tournament below — the exact compute the distill compresses.
                d = None
                try:
                    from trading.crypto.freqtrade.micro_policy import get_micro
                    _mp = get_micro()
                    if _mp is not None:
                        d = _mp.decide(sym, self.decider._ohlcv(sym),
                                       in_position=(sym in open_pairs))
                except Exception:
                    d = None
                if d is None:
                    d = self.decider.decide("CRYPTO", sym, None,
                                            in_position=(sym in open_pairs))
                # CORTEX B8 (CANON-51): OPT-IN shadow lane. Env unset → zero change.
                d = self._cortex_shadow(sym, d, in_position=(sym in open_pairs))
                act = d.get("action")
                tag = d.get("tag")                       # brain's chosen strategy for this coin
                brain = d.get("_brain") or {}
                # ACCOUNT-PATH: when the executor's own ensemble is undecided (FLAT / net-tie) but
                # the funnel's account-first read gave a DECISIVE direction, follow it (it still
                # passes every safety gate below). This makes the connected-account data actually
                # drive entries instead of the executor's split library vote silently skipping.
                if act not in ("LONG", "SHORT") and sym not in open_pairs:
                    _vote = (getattr(self, "extra_signals", {}) or {}).get(sym, {}).get("vote", {})
                    _vdir = (_vote or {}).get("direction")
                    if _vdir == "long":
                        act, tag = "LONG", (tag or "account_path")
                    elif _vdir == "short":
                        act, tag = "SHORT", (tag or "account_path")
                # EXPLORE: still FLAT after the account-path → derive a direction from ALL the
                # symbol's app data (vote p_up lean, else the picker lane) so it opens anyway.
                if explore and act not in ("LONG", "SHORT") and sym not in open_pairs:
                    _sig = (getattr(self, "extra_signals", {}) or {}).get(sym, {}) or {}
                    _vote = _sig.get("vote") or {}
                    _pup = _vote.get("p_up")
                    _lane = str((_sig.get("screener") or {}).get("lane") or "")
                    if _pup is not None:
                        act = "LONG" if float(_pup) >= 0.5 else "SHORT"
                    elif "loser" in _lane or "short" in _lane:
                        act = "SHORT"
                    else:
                        act = "LONG"                     # gainers/movers/unknown → explore long
                    tag = tag or "explore_open_all"
                # D2 Mirror Gate (Pillar 27): every selective entry direction passes the
                # measured per-source gate — invert the reliably-wrong, skip proven noise.
                if act in ("LONG", "SHORT") and sym not in open_pairs:
                    try:
                        from trading.direction import mirror_gate
                        from trading.direction.regime import classify as _rg
                        _gact, _g = mirror_gate.apply(
                            act, source=str(tag or "unknown"), symbol=sym,
                            segment=self.segment or "futures", regime=_rg(sym).get("regime"),
                            confidence=brain.get("confidence"))
                        if _g.get("action") in ("invert", "abstain"):
                            brain = {**brain, "mirror_gate": _g}
                        if _gact is None:
                            skipped += 1
                            continue
                        act = _gact
                        # D6 meta-labeler: calibrated P(side correct). Blocks ONLY a
                        # proven model (holdout AUC ≥ META_MIN_AUC) and never in
                        # explore (explore generates its training data).
                        from trading.direction import meta_labeler as _ml
                        _mg6 = _ml.gate(act, {
                            "ts": time.time(), "symbol": sym, "market": "CRYPTO",
                            "segment": self.segment or "futures",
                            "source": str(tag or "unknown"),
                            "confidence": brain.get("confidence"),
                            "regime": _rg(sym).get("regime"), "taken": True})
                        if _mg6.get("p") is not None:
                            brain = {**brain, "meta_gate": _mg6}
                        if not explore and not _mg6.get("allow", True):
                            vetoes.append(sym)
                            skipped += 1
                            continue
                    except Exception:
                        pass
                if brain.get("chosen_strategy"):
                    picks[sym] = {"strategy": brain.get("chosen_strategy"), "action": act,
                                  "final_score": brain.get("final_score"), "sharpe": brain.get("sharpe"),
                                  "win_rate": brain.get("win_rate"), "p_win": brain.get("p_win")}
                # Closed-loop feedback: block a new entry only when CONFIRMED hypotheses give
                # strong contrary evidence for that direction. Advisory (never forces entries).
                if act in ("LONG", "SHORT") and sym not in open_pairs and not explore \
                        and self._entry_vetoed(sym, act, brain):
                    vetoes.append(sym)
                    skipped += 1
                    continue
                # episodic recall: importance/recency-weighted win-rate of RESOLVED past
                # episodes on this symbol+direction nudges confidence (advisory, never vetoes)
                if act in ("LONG", "SHORT") and sym not in open_pairs:
                    self._apply_decision_memory(sym, act, brain)
                # concept discovery: self-invented features scale confidence (validated lane)
                if act in ("LONG", "SHORT") and sym not in open_pairs:
                    self._apply_discovery(sym, act, brain)
                # order-book trader psychology: live entry signal (boost/dampen/veto)
                psych = None
                if act in ("LONG", "SHORT") and sym not in open_pairs:
                    psych, _pact = self._apply_psychology(
                        sym, act, brain, veto_at=policy.get("psych_veto", self._PSYCH_VETO))
                    if _pact == "FLAT" and not explore:
                        vetoes.append(sym)
                        skipped += 1
                        continue
                    act = _pact if not explore else act   # explore keeps the app-data direction
                # Pillar 17: calibrated conformal gate — the LAST word before capital
                # commits. Runs after every confidence adjuster so p_up reflects the
                # final belief; an abstention is logged as a first-class decision.
                if act in ("LONG", "SHORT") and sym not in open_pairs:
                    uq = self._assess_uq(sym, act, brain, psych)
                    if uq and uq.get("abstain"):
                        if policy.get("uq_advisory") or explore:
                            # boss volume pressure OR explore-open-all: the gate LOGS its
                            # abstention but does not block — recorded honestly.
                            if isinstance(brain, dict):
                                brain["uq_advisory_bypass"] = "explore_open_all" if explore \
                                    else policy.get("reason")
                        else:
                            vetoes.append(sym)
                            skipped += 1
                            continue
                # D8 validate stage (Pillar 27): a regime TRANSITION is the moment
                # stale-regime models are most wrong (SOTA notes §4) — block fresh
                # non-explore entries there unless the source is ledger-TRUSTED.
                if act in ("LONG", "SHORT") and sym not in open_pairs \
                        and not explore and os.environ.get(
                            "REGIME_TRANSITION_BLOCK", "1") in ("1", "true", "yes"):
                    try:
                        from trading.direction import mirror_gate as _mgm
                        from trading.direction.regime import classify as _rgc
                        if _rgc(sym).get("regime") == "transition":
                            _tg = _mgm.decide(act, source=str(tag or "unknown"),
                                              regime="transition")
                            if not (_tg.get("ci_low") or 0) > 0.55:
                                vetoes.append(sym)
                                skipped += 1
                                continue
                    except Exception:
                        pass
                if act in ("LONG", "SHORT") and sym not in open_pairs:
                    # D3: selective entries arm too — same retrace discount, with a
                    # real ATR from the bars the decide() call already fetched.
                    try:
                        from trading.direction import pullback as _pb
                        if _pb.enabled():
                            _atr = None
                            try:
                                _atr = _pb.atr_from_df(self.decider._ohlcv(sym))
                            except Exception:
                                _atr = None
                            _q = _pb.live_price(sym, self.segment or "futures")
                            if _q and _pb.arm(symbol=sym,
                                              segment=self.segment or "futures",
                                              direction=act,
                                              source=str(tag or "unknown"),
                                              ref_price=float(_q), atr=_atr,
                                              confidence=brain.get("confidence")):
                                armed_n += 1
                                continue
                    except Exception:
                        pass
                    # same honesty as the explore path: route to the engine-tradeable book
                    # and count an entry ONLY when the engine accepted the order.
                    tsym = cli.tradeable_form(sym, self.segment)
                    if tsym is None:
                        skipped += 1
                        continue
                    res = cli.place_order(symbol=tsym, action="BUY",
                                          side=("long" if act == "LONG" else "short"),
                                          allow_live=allow_live, enter_tag=tag,
                                          segment=self.segment,
                                          stake_amount=self._meta_kelly_stake(
                                              cli, tag, brain.get("meta_gate")))
                    if isinstance(res, dict) and res.get("ok") is False:
                        skipped += 1
                        continue
                    if tsym != sym and sym in (getattr(self, "extra_signals", {}) or {}):
                        self.extra_signals[tsym] = self.extra_signals[sym]
                    if isinstance(res, dict) and res.get("queued"):
                        queued.append(tsym)        # inbox mode: queued ≠ filled entry
                        self._record_entry_meta(tsym, act, tag, brain, psych)
                        continue
                    entered.append(tsym)
                    self._record_entry_meta(tsym, act, tag, brain, psych)
                elif act == "EXIT" and sym in open_pairs:
                    cli.close_pair(sym, segment=self.segment)
                    exited.append(sym)
                else:
                    skipped += 1
            except Exception:
                skipped += 1
        self._last_picks = picks
        self._last_vetoes = vetoes
        return {"entered": entered, "exited": exited, "skipped": skipped,
                "queued": queued, "armed": armed_n,
                "universe": len(syms), "picks": picks, "vetoes": vetoes,
                "explore": explore, "deadline_deferred": deadline_deferred}

    def _meta_kelly_stake(self, cli, tag: str | None, meta_gate) -> float | None:
        """D8 sizing (Pillar 27): scale the bandit/base stake by the meta-labeler's
        calibrated P(correct) — fractional-Kelly-inspired linear map
        mult = clamp(1 + KELLY_SCALE·(p−0.5), 0.4, 1.8). Applies ONLY while the
        model is PROVEN (its gate ran non-advisory); otherwise the bandit stake (or
        engine default) stands untouched — sizing never moves on an unproven model."""
        import os as _os
        base = self._bandit_stake(cli, tag)
        try:
            g = meta_gate if isinstance(meta_gate, dict) else None
            if not g or g.get("advisory", True) or g.get("p") is None:
                return base
            scale = float(_os.environ.get("KELLY_SCALE", "4") or 4)
            mult = max(0.4, min(1.8, 1 + scale * (float(g["p"]) - 0.5)))
            if abs(mult - 1.0) < 0.05:
                return base
            if base is None:                       # need an honest engine base to scale
                now = time.monotonic()
                cache = getattr(self, "_stake_cache", None)
                if cache is None or now - cache[0] > 3600:
                    eng = (cli.show_config() or {}).get("stake_amount")
                    cache = (now, float(eng) if isinstance(eng, (int, float))
                             and eng > 0 else None)
                    self._stake_cache = cache
                base = cache[1]
            return round(base * mult, 2) if base else None
        except Exception:
            return base

    def _bandit_stake(self, cli, tag: str | None) -> float | None:
        """Champion-bandit stake scaling (invent-beyond #3): a SELECTIVE entry attributed to a
        library strategy gets the bandit's Thompson-sampled multiplier applied to the ENGINE'S
        OWN base stake (show_config truth, cached 1h — config.settings is stale-cached at
        startup, so we ask the running bot). None = engine default, returned for: unknown/
        blank tag, scale ≈ 1, unlimited base stake, CHAMPION_BANDIT=0, or any failure —
        sizing is never changed silently on an error path. PAPER shaping only today; live
        promotion rides the existing allow_live/W3 gates."""
        import os as _os
        if not tag or _os.environ.get("CHAMPION_BANDIT", "1") not in ("1", "true", "TRUE", "yes"):
            return None
        try:
            from trading.strategy import champion_bandit as _cb
            scale = _cb.stake_scale("CRYPTO", tag)
            if abs(scale - 1.0) < 0.05:
                return None
            now = time.monotonic()
            cache = getattr(self, "_stake_cache", None)
            if cache is None or now - cache[0] > 3600:
                base = (cli.show_config() or {}).get("stake_amount")
                cache = (now, float(base) if isinstance(base, (int, float)) and base > 0
                         else None)                     # "unlimited"/0 → no honest base to scale
                self._stake_cache = cache
            base = cache[1]
            return round(base * scale, 2) if base else None
        except Exception:
            return None

    def _explore_open_all(self, *, open_now: int = 0) -> bool:
        """PAPER explore-open-all (owner 2026-07-06): open EVERY candidate the pickers surface —
        direction from the symbol's own Binance app data, vetoes ADVISORY — until the brain is
        CONSISTENTLY PICKING PROFITABLE / CORRECT-DIRECTION trades, then AUTO-GRADUATE to the
        selective gate. Never returns True in live (caller gates on `not allow_live`).

        Graduation signal (owner 2026-07-06 refinement): NOT a raw trade COUNT — the box already
        holds thousands of trades yet a big count proves nothing about skill. Graduate on the
        brain's ROLLING WIN-RATE instead: over the last `BRAIN_EXPLORE_GRADUATE_WINDOW` closed
        trades, once the profitable-fraction (a profitable directional trade == a correct entry
        direction) holds at/above `BRAIN_EXPLORE_GRADUATE_ACC`, the brain has earned selectivity.

        Env knobs:
          BRAIN_EXPLORE_OPEN_ALL       on/off master flag (default ON)
          BRAIN_EXPLORE_GRADUATE_ACC   win-rate to graduate at, e.g. 0.55 (default 0.0 = never)
          BRAIN_EXPLORE_GRADUATE_WINDOW recent closed trades to score over (default 50)
          BRAIN_EXPLORE_GRADUATE_N     legacy count gate; used only when ACC is unset (default 0)

        Default keeps exploring (ACC=0) — the paper learn-lab: blowups are training data, every
        entry is fully labelled; graduation is opt-in the moment the win-rate proves it out."""
        import os
        if os.environ.get("BRAIN_EXPLORE_OPEN_ALL", "1") not in ("1", "true", "TRUE", "yes", "on"):
            return False
        # ── profitability-based graduation (preferred) ──────────────────────────────
        try:
            acc = float(os.environ.get("BRAIN_EXPLORE_GRADUATE_ACC", "0") or 0)
        except Exception:
            acc = 0.0
        if acc > 0:
            try:
                window = int(os.environ.get("BRAIN_EXPLORE_GRADUATE_WINDOW", "50"))
            except Exception:
                window = 50
            window = max(1, window)
            wr = self._recent_win_rate(window)
            # need a full window of evidence AND the win-rate at/above target to graduate
            if wr is None or wr[1] < window:
                return True                          # not enough closed trades yet → keep exploring
            return wr[0] < acc                       # below target → explore; at/above → graduate
        # ── legacy count gate (only if a positive N is set) ─────────────────────────
        try:
            n = int(os.environ.get("BRAIN_EXPLORE_GRADUATE_N", "0"))
        except Exception:
            n = 0
        if n <= 0:
            return True
        try:
            from trading.journal.journal import TradeJournal
            return len(TradeJournal(state_file="journal.json", persist=True).trades) < n
        except Exception:
            return True                              # no journal yet → explore

    @staticmethod
    def _recent_win_rate(window: int) -> tuple[float, int] | None:
        """Return (win_rate, n_scored) over the last `window` CLOSED trades, where a "win" is a
        profitable trade (net_pnl > 0) — a profitable directional trade means the brain called the
        entry direction correctly. Returns None if the journal can't be read. n_scored is capped at
        `window`; callers require it to equal `window` before trusting the rate (full evidence)."""
        try:
            from trading.journal.journal import TradeJournal
            trades = TradeJournal(state_file="journal.json", persist=True).trades
        except Exception:
            return None
        recent = trades[-window:]
        if not recent:
            return (0.0, 0)
        def _pnl(t) -> float:
            v = getattr(t, "net_pnl_crypto", None)
            if v is None:
                v = getattr(t, "net_pnl", 0.0)
            return float(v or 0.0)
        wins = sum(1 for t in recent if _pnl(t) > 0)
        return (wins / len(recent), len(recent))

    # ── options segment (Deribit, paper) ──────────────────────────────────────
    # The brain decides the DIRECTION on the underlying perp (where it has full data +
    # backtests), then expresses it with a long option: bullish → buy a call, bearish →
    # buy a put. Contract choice: nearest expiry, median strike (≈ATM — Deribit lists
    # strikes around spot). Long-options-only: max loss = premium, no margin surprises.
    @staticmethod
    def _parse_option(sym: str) -> dict | None:
        # ccxt Deribit option symbol: "BTC/USDC:USDC-260703-60000-P"
        try:
            base = sym.split("/")[0]
            tail = sym.split(":", 1)[1]              # "USDC-260703-60000-P"
            _, expiry, strike, kind = tail.rsplit("-", 3)
            return {"symbol": sym, "base": base, "expiry": expiry,
                    "strike": float(strike), "kind": kind.upper()}
        except Exception:
            return None

    def _option_book_ok(self, symbol: str) -> bool:
        """LIQUIDITY GUARD: refuse a market entry into a hollow option book.

        2026-07-10: the first real option entry filled at ask 300.0 while the bid was
        0.2 — the mark instantly read the bid → stop_loss at -99.9% in 5 seconds.
        Thin daily contracts do this routinely; a market order there is a guaranteed
        loss, not a trade. Require a live bid AND a sane spread before entering.
        Levers: OPTIONS_LIQ_GUARD=0 disables, OPTIONS_MAX_SPREAD_PCT (default 12 —
        a market entry fills at the ask while the mark reads ~mid, an instant hit of
        ~spread/2; 12% keeps that inside the −10% stoploss, 25% insta-stopped).
        Fail-CLOSED on an unreadable book — market-entering blind is the exact harm."""
        if os.environ.get("OPTIONS_LIQ_GUARD", "1") in ("0", "false", "no"):
            return True
        try:
            import ccxt
            ex = getattr(self, "_opt_book_ex", None)
            if ex is None:
                ex = self._opt_book_ex = ccxt.deribit()
            ob = ex.fetch_order_book(symbol, limit=1)
            bid = (ob.get("bids") or [[0]])[0][0] or 0.0
            ask = (ob.get("asks") or [[0]])[0][0] or 0.0
            if bid <= 0 or ask <= 0:
                return False
            max_spread = float(os.environ.get("OPTIONS_MAX_SPREAD_PCT", "12"))
            return (ask - bid) / ((ask + bid) / 2.0) * 100.0 <= max_spread
        except Exception:
            return False

    def _run_options_cycle(self, *, allow_live: bool = False,
                           deadline: float | None = None) -> dict:
        cli = self.client()
        opts = [o for o in (self._parse_option(s) for s in self.symbols()) if o]
        open_pairs = set(cli.open_pairs(segment="options"))
        entered, exited, skipped = [], [], 0
        queued: list = []                      # inbox mode: queued-not-yet-filled decisions
        # per-reason skip counts so an all-skipped cycle is diagnosable from its log line
        # (no_direction / positioned / no_candidates / hollow_book / refused / error)
        reasons: dict = {}

        def _skip(why: str):
            nonlocal skipped
            skipped += 1
            reasons[why] = reasons.get(why, 0) + 1
        picks: dict = {}
        bases = sorted({o["base"] for o in opts})
        for i, base in enumerate(bases):
            # honest time box (2026-07-11): decide() per underlying can be model-heavy
            # (a TabPFN pass held this loop 30+ min, freezing the whole funnel process);
            # like the futures path, undecided bases DEFER to the next cycle, never wedge.
            if deadline is not None and time.monotonic() > deadline:
                reasons["deadline_deferred"] = len(bases) - i
                break
            try:
                under = f"{base}/USDT:USDT"          # decide on the perp (full brain data)
                d = self.decider.decide("CRYPTO", under, None, in_position=False)
                act = d.get("action")
                if act in ("LONG", "SHORT"):
                    try:                              # D1: options side = a claim on the perp
                        from trading.direction import truth_ledger
                        truth_ledger.record(symbol=under, market="CRYPTO",
                                            segment="options", direction=act,
                                            source=str(d.get("strategy")
                                                       or "percoin_decider"),
                                            confidence=d.get("confidence"))
                    except Exception:
                        pass
                    try:                              # D2: CE/PE side through the same gate
                        from trading.direction import mirror_gate
                        from trading.direction.regime import classify as _rg
                        act, _ = mirror_gate.apply(
                            act, source=str(d.get("strategy") or "percoin_decider"),
                            symbol=under, segment="options", regime=_rg(under).get("regime"),
                            confidence=d.get("confidence"))
                    except Exception:
                        pass
                held = [s for s in open_pairs if s.startswith(f"{base}/")]
                want = {"LONG": "C", "SHORT": "P"}.get(act)
                if want is None:
                    # no directional view → close held options on this underlying
                    for s in held:
                        cli.close_pair(s, segment="options")
                        exited.append(s)
                    _skip("no_direction")
                    continue
                if any((self._parse_option(s) or {}).get("kind") == want for s in held):
                    _skip("positioned")
                    continue                          # already positioned this direction
                for s in held:                        # flip: exit wrong-direction options
                    cli.close_pair(s, segment="options")
                    exited.append(s)
                cands = [o for o in opts if o["base"] == base and o["kind"] == want]
                if not cands:
                    _skip("no_candidates")
                    continue
                nearest = min(o["expiry"] for o in cands)
                atm = sorted((o for o in cands if o["expiry"] == nearest),
                             key=lambda o: o["strike"])
                pick = atm[len(atm) // 2]             # median strike ≈ ATM
                if not self._option_book_ok(pick["symbol"]):
                    _skip("hollow_book")      # hollow/unreadable book → honest skip
                    continue
                res = cli.place_order(symbol=pick["symbol"], action="BUY", side="long",
                                      allow_live=allow_live, segment="options",
                                      enter_tag=f"opt-{act.lower()}-{base}")
                if isinstance(res, dict) and res.get("ok") is False:
                    _skip("refused")          # refused (guard/engine) is NOT an entry
                    continue
                picks[pick["symbol"]] = {"strategy": f"underlying-{act}", "action": act}
                if isinstance(res, dict) and res.get("queued"):
                    queued.append(pick["symbol"])   # inbox mode: queued ≠ filled entry
                    continue
                entered.append(pick["symbol"])
            except Exception:
                _skip("error")
        self._last_picks = picks
        return {"entered": entered, "exited": exited, "skipped": skipped, "queued": queued,
                "skip_reasons": reasons, "universe": len(opts), "picks": picks, "vetoes": []}

    # ── prediction segment (Polymarket, paper) ────────────────────────────────
    # Outcome prices live in [0,1]; real 5m candles come from the CLOB history through the
    # engine. Simple honest momentum: price above SMA20 by a margin → buy YES; drop below
    # SMA20 → exit. Long-only (short = buying the other outcome, a later step).
    def _run_prediction_cycle(self, *, allow_live: bool = False) -> dict:
        cli = self.client()
        open_pairs = set(cli.open_pairs(segment="prediction"))
        entered, exited, skipped = [], [], 0
        picks: dict = {}
        for sym in self.symbols():
            try:
                rows = cli.pair_candles(sym, "5m", limit=60, segment="prediction")
                closes = [r[4] for r in rows if isinstance(r, (list, tuple)) and len(r) > 4]
                if len(closes) < 25:
                    skipped += 1
                    continue
                sma20 = sum(closes[-20:]) / 20.0
                last = float(closes[-1])
                if sym not in open_pairs and last > sma20 * 1.02 and 0.03 < last < 0.95:
                    res = cli.place_order(symbol=sym, action="BUY", side="long",
                                          allow_live=allow_live, segment="prediction",
                                          enter_tag="pred-momentum")
                    if isinstance(res, dict) and res.get("ok") is False:
                        skipped += 1          # refused (guard/engine) is NOT an entry
                        continue
                    entered.append(sym)
                    picks[sym] = {"strategy": "pred-momentum", "action": "LONG"}
                elif sym in open_pairs and last < sma20:
                    cli.close_pair(sym, segment="prediction")
                    exited.append(sym)
                else:
                    skipped += 1
            except Exception:
                skipped += 1
        self._last_picks = picks
        return {"entered": entered, "exited": exited, "skipped": skipped,
                "universe": len(self.symbols()), "picks": picks, "vetoes": []}

    # ── CORTEX B8: shadow signal lane (CANON-51) ──────────────────────────────
    def _cortex_shadow(self, sym: str, d: dict, *, in_position: bool) -> dict:
        """OPT-IN CORTEX signal alongside the existing decider.

        CORTEX_SIGNAL=1 : consult CortexSignalSource, LOG both decisions and
                          persist the comparison (shadow mode) — the existing
                          decider's decision still trades.
        CORTEX_TRADE=1  : (additionally) the CORTEX decision REPLACES the
                          decider's (paper-first; execution path unchanged).
        Env unset → returns `d` untouched. Never raises."""
        if os.environ.get("CORTEX_SIGNAL", "") not in ("1", "true", "TRUE", "yes"):
            return d
        try:
            from trading import cortex_signal as cx
            src = cx.get_cortex_source()
            df = self.decider._ohlcv(sym)
            sig = src.signal(sym, df)
            print(f"[cortex:{self.segment}] {sym} shadow side={sig.get('side')} "
                  f"frac={sig.get('size_fraction')} conf={sig.get('confidence')} "
                  f"tier={sig.get('tier_reached')} experts={sig.get('experts_fired')} "
                  f"regime={sig.get('regime_label')} reason={sig.get('reason')} "
                  f"| decider={d.get('action')}", flush=True)
            cx.record_shadow(self.segment, sym, sig, d.get("action"))
            if sig.get("side") in ("long", "short"):
                # remember the fired experts → trust feedback on trade close
                cx.record_pending(sym, sig["side"], sig.get("experts_fired") or [])
            if os.environ.get("CORTEX_TRADE", "") in ("1", "true", "TRUE", "yes"):
                meta = {"source": "cortex_b8", **{k: sig.get(k) for k in
                        ("confidence", "tier_reached", "experts_fired",
                         "regime_probs", "regime_label", "reason")}}
                if sig.get("side") == "long":
                    return {"action": "LONG", "size": sig.get("size_fraction", 1.0),
                            "tag": "cortex", "_brain": meta}
                if sig.get("side") == "short":
                    return {"action": "SHORT", "size": sig.get("size_fraction", 1.0),
                            "tag": "cortex", "_brain": meta}
                # cortex says flat: exit an open position, else stay out
                return {"action": ("EXIT" if in_position else "FLAT"),
                        "tag": "cortex", "_brain": meta}
        except Exception as e:
            print(f"[cortex:{self.segment}] shadow error for {sym}: {e!r}", flush=True)
        return d

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

    # crowd-psychology veto threshold (mirrors LiveTradeLoop._PSYCH_VETO — full-signal mode)
    _PSYCH_VETO = 0.6

    def _apply_psychology(self, sym: str, act: str, brain: dict,
                          veto_at: float | None = None) -> tuple[dict | None, str]:
        """Order-book trader psychology as a LIVE entry signal (trading/brain/psychology.py).

        Boosts/dampens the brain's confidence by crowd alignment and returns act='FLAT'
        when the crowd strongly opposes the direction. `veto_at` overrides the veto
        threshold (boss entry policy: profit mode tightens, pressure loosens).
        Best-effort: no depth → unchanged."""
        try:
            from trading.brain.psychology import get_engine
            psych = get_engine().evaluate("CRYPTO", sym, segment=self.segment or "futures")
            if not psych:
                return None, act
            sign = 1.0 if act == "LONG" else -1.0
            alignment = float(psych["trader_psychology"]) * sign
            if isinstance(brain, dict):
                brain["psych_alignment"] = round(alignment, 4)
                if brain.get("confidence") is not None:
                    brain["confidence"] = float(min(1.0, max(0.0,
                        float(brain["confidence"]) * (1.0 + 0.3 * alignment))))
            if alignment < -(self._PSYCH_VETO if veto_at is None else float(veto_at)):
                return psych, "FLAT"
            return psych, act
        except Exception:
            return None, act

    def _apply_decision_memory(self, sym: str, act: str, brain: dict) -> None:
        """FinMem-style recall: past resolved episodes on this symbol+direction scale the
        brain's confidence (win-rate bias ∈ [-1,1] → ±20%). Advisory only."""
        try:
            from trading.brain.decision_memory import get_memory
            b = get_memory().bias(sym, act)
            if b["n"] >= 3 and isinstance(brain, dict) and brain.get("confidence") is not None:
                brain["confidence"] = float(min(1.0, max(0.0,
                    float(brain["confidence"]) * (1.0 + 0.2 * b["bias"]))))
                brain["memory_bias"] = b["bias"]
                brain["memory_n"] = b["n"]
        except Exception:
            pass

    def _apply_discovery(self, sym: str, act: str, brain: dict) -> None:
        """Concept Discovery Engine: the brain's SELF-INVENTED features on this symbol's
        current window produce a directional signal ∈ [-1,1]. The VALIDATED lane (proof-gated,
        OOS-stable) scales confidence (±25%); the EXPERIMENT lane is shadow-logged only.
        Non-blocking (fits per-symbol engines in the background). Advisory — never vetoes."""
        try:
            from trading.brain.discovery import signal as disc
            df = self._ohlcv(sym)
            if df is None or len(df) < 80:
                return
            closes = df["close"].to_numpy(dtype=float)
            s = disc.signal(sym, closes)
            if not isinstance(brain, dict):
                return
            brain["concept_signal"] = round(float(s["validated"]), 4)      # proof-gated
            brain["concept_experiment"] = round(float(s["experiment"]), 4)  # shadow (log-only)
            brain["concept_n"] = {"val": s["n_val"], "exp": s["n_exp"], "ready": s["ready"]}
            if s["n_val"] > 0 and brain.get("confidence") is not None:
                align = float(s["validated"]) * (1.0 if act == "LONG" else -1.0)
                brain["confidence"] = float(min(1.0, max(0.0,
                    float(brain["confidence"]) * (1.0 + 0.25 * align))))
        except Exception:
            pass

    def _assess_uq(self, sym: str, act: str, brain, psych) -> dict | None:
        """Pillar 17: conformal p_up + coverage interval + abstention for THIS entry
        (trading/uq). The assessment is stored on the brain dict so it travels into
        decision_snapshot + the journal's p_up/interval_width/self_uncertainty
        columns. Best-effort: a UQ failure never blocks trading (logged degraded)."""
        try:
            from trading.uq import get_uq
            b = brain if isinstance(brain, dict) else {}
            uq = get_uq().assess(
                confidence=b.get("confidence"), direction=act, market="CRYPTO",
                psych=(psych or {}).get("trader_psychology") if isinstance(psych, dict) else None,
                longs=b.get("longs"), shorts=b.get("shorts"), symbol=sym)
            if isinstance(brain, dict):
                brain["uq"] = uq
            return uq
        except Exception:
            return None

    def _tailgate_pass(self, cli, *, allow_live: bool = False) -> list:
        """Profit-tailgating over every OPEN trade: ratchet the locked-profit floor up with the
        peak; force-exit when live profit falls to the lock. Env PROFIT_TAILGATE=1 (default on for
        paper). Never raises. Returns the symbols it exited."""
        import os
        if os.environ.get("PROFIT_TAILGATE", "1") not in ("1", "true", "TRUE", "yes"):
            return []
        exited = []

        def _num(v):
            try:
                return float(v) if v is not None else 0.0
            except (TypeError, ValueError):
                return 0.0
        try:
            from trading.execution import profit_tailgate as pt
            st = cli.status()
            trades = st if isinstance(st, list) else []
            for t in trades:
                pair = t.get("pair")
                if not pair:
                    continue
                prof = t.get("profit_ratio")
                profit_pct = float(prof) * 100.0 if prof is not None else None
                # peak% from Freqtrade's tracked max_rate vs open_rate (direction-aware).
                # LEVERAGE-AWARE: profit_ratio is scaled by leverage (5x → a 1% price move
                # reads 5%), so the rate-derived peak MUST be too — mixing bases ratcheted
                # locks from two different units (seen live: locked > peak in the lock file).
                op, mx = _num(t.get("open_rate")), _num(t.get("max_rate"))
                lev = _num(t.get("leverage")) or 1.0
                peak_pct = None
                if op and mx:
                    peak_pct = ((op - mx) / op if t.get("is_short")
                                else (mx - op) / op) * lev * 100.0
                    peak_pct = max(peak_pct, profit_pct or 0.0)
                tid = str(t.get("trade_id") or pair)
                dec = pt.locked_profit("crypto", self.segment or "futures", trade_id=tid,
                                       profit_pct=profit_pct, peak_profit_pct=peak_pct)
                if dec.get("exit"):
                    try:
                        cli.close_pair(pair, segment=self.segment)
                        exited.append(pair)
                        pt.learn("crypto", self.segment or "futures",
                                 peak_profit_pct=peak_pct, captured_pct=profit_pct)
                        pt.clear_lock(tid)
                        from trading.brain import mind_events
                        mind_events.emit("trade_credit",
                                         f"Profit tailgate locked {profit_pct:.2f}% on {pair} "
                                         f"(peak {peak_pct:.2f}%)", salience=0.6)
                    except Exception:
                        pass
            # PRUNE stale locks (2026-07-10): clear_lock only fires on tailgate exits, so
            # trades closed any other way (stop, strategy, manual) left their entries behind
            # forever — 166 entries vs 19 open, with pre-fix mixed-unit values still being
            # served to the dashboard overlay. /status returns every worker's trades, so any
            # pure-numeric lock id not open anymore is a closed trade's leftover. Sandbox
            # locks ("sb:SYM") are the sandbox engine's to clear — never touched here.
            try:
                open_ids = {str(t.get("trade_id")) for t in trades if t.get("trade_id")}
                from trading import state as _st
                locks = _st.load_json("profit_tailgate_locks.json", {}) or {}
                stale = [k for k in locks if k.isdigit() and k not in open_ids]
                if stale:
                    for k in stale:
                        locks.pop(k, None)
                    _st.save_json("profit_tailgate_locks.json", locks)
            except Exception:
                pass
        except Exception:
            pass
        return exited

    def _record_entry_meta(self, sym: str, act: str, tag, brain: dict, psych,
                           explore: bool = False) -> None:
        """Persist the FULL decision context of this entry to the sidecar store so
        freqtrade_ingest can fill the psychology + decision_snapshot journal columns."""
        try:
            from trading.crypto.freqtrade import entry_meta
            if psych is None:
                # #13 connectivity fix: even fast-path (explore) entries RECORD the
                # order-book psychology read (advisory context, never a gate here) —
                # previously explore entries carried psychology=None, so the journal's
                # psych_* learning columns stayed empty for the very trades meant to
                # teach the brain. Best-effort, ~cached-book cost.
                try:
                    from trading.brain.psychology import get_engine
                    psych = get_engine().evaluate("CRYPTO", sym,
                                                  segment=self.segment or "futures")
                except Exception:
                    psych = None
            snapshot = {
                "market": "CRYPTO", "symbol": sym,
                "segment": self.segment or "futures",
                "direction": act, "strategy": tag,
                "brain": brain if isinstance(brain, dict) else None,
                "psychology": psych,
                "engine": "freqtrade",
            }
            if explore:
                snapshot["explore"] = True
            if self.extra_signals.get(sym):
                snapshot["app_signals"] = self.extra_signals[sym]
            # decision-memory episode + SHAP attribution (resolved at ingest time when
            # the trade closes; episode_id travels via this sidecar)
            episode_id, attribution = "", {}
            try:
                from trading.brain.attribution import explain_trade
                from trading.brain.decision_memory import get_memory
                from trading.journal.journal import TradeJournal
                closed = [t.to_dict() for t in TradeJournal().trades[-200:]]
                attribution = explain_trade({
                    "symbol": sym, "direction": act, "exchange": "binance",
                    "brain_confidence_entry": (brain or {}).get("confidence"),
                    "decision_snapshot": snapshot}, closed, fast=True)
                episode_id = get_memory().open_episode(
                    symbol=sym, market="CRYPTO", segment=self.segment or "futures",
                    direction=act, strategy=str(tag or ""), engine="freqtrade",
                    decision_snapshot=snapshot, attribution=attribution)
            except Exception:
                pass
            entry_meta.record(sym, self.segment, {
                "psychology": psych,
                "episode_id": episode_id,
                "feature_attribution": attribution,
                "decision_snapshot": snapshot,
                "uq": (brain or {}).get("uq") if isinstance(brain, dict) else None,
            })
            # D1 Truth Ledger (Pillar 27): the OPENED trade is a directional claim by its
            # strategy — record it for fixed-horizon truth labeling (exit-independent).
            from trading.direction import truth_ledger
            truth_ledger.record(symbol=sym, market="CRYPTO",
                                segment=self.segment or "futures", direction=act,
                                source=str(tag or "unknown"),
                                confidence=(brain or {}).get("confidence")
                                if isinstance(brain, dict) else None,
                                taken=True)
        except Exception:
            pass
