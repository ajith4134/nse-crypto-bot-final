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

# E9 (2026-07-17): LibraryBrainDecider lives in library_decider.py (leaf) — re-exported
# here so existing imports keep working; percoin_decider/micro_policy import the leaf.
from trading.crypto.freqtrade.library_decider import (   # noqa: F401
    _LOOKBACK, _TF, LibraryBrainDecider, _spot, library_brain_decider)

# Last-N closed trades for attribution context, TTL-cached (2026-07-16 — THE cycle bottleneck).
# py-spy on the live funnel caught the loop blocked in:
#   open_filter_lane -> _record_entry_meta -> TradeJournal.__init__ -> _load -> from_dict -> fields()
# TradeJournal() parses EVERY row (7,318 dataclass builds + a confidence update each) and the caller
# used only [-200:] — and it ran PER RECORDED ENTRY inside the placement loop (~100 entries/cycle
# => ~730k dataclass constructions per cycle to read 200 rows). This — not the crawl (76.5s->7s
# changed nothing), not the tournament (already capped, not even in this path), not the lane budget
# (cutting it made cycles WORSE) — is why cycles ran 16 min. It also explains why `execute` jumped
# 26s->119s the moment futures started opening: before the routing fix nothing entered, so this
# never ran. More entries => more full-journal reloads.
# The tail is attribution CONTEXT (what recently closed), not a per-pick input, so a short TTL is
# honest: 60s is far fresher than the 5m bar the brain reasons on.
_CLOSED_TAIL: dict = {"ts": 0.0, "n": 0, "rows": []}
_CLOSED_TAIL_TTL_S = float(os.environ.get("CLOSED_TAIL_TTL_S", "60") or 60)


def _closed_tail(n: int = 200) -> list:
    """The last `n` closed trades as dicts. TTL-cached; never raises (attribution is advisory)."""
    now = time.time()
    if (now - _CLOSED_TAIL["ts"] <= _CLOSED_TAIL_TTL_S) and _CLOSED_TAIL["n"] >= n:
        return _CLOSED_TAIL["rows"][-n:]
    try:
        from trading.journal.journal import TradeJournal
        rows = [t.to_dict() for t in TradeJournal().trades[-n:]]
    except Exception:
        return _CLOSED_TAIL["rows"][-n:]          # serve the last good tail on a read failure
    _CLOSED_TAIL.update({"ts": now, "n": n, "rows": rows})
    return rows


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

    def _move_net_direction(self, under: str) -> str | None:
        """RAM SymbolMoveNet direction for an underlying — the options fallback when the per-coin
        tournament gives no side (owner 2026-07-13). Builds the feature ctx from RAM (all app_signals
        filters + the mirror's 24h volume) so the net predicts on real data; returns LONG/SHORT only
        when both heads agree (else None → the driver keeps its honest no_direction). Never raises."""
        try:
            from trading.brain import symbol_move_net as _smn
            if not _smn.enabled():
                return None
            flt = {}
            try:
                from trading.direction import app_signals as _asig
                flt = {s: p for s, p in (_asig.collect(under, market="crypto").get("signals") or [])}
            except Exception:
                flt = {}
            vol = 0.0
            try:
                from trading.broker_sense.binance_stream import get_mirror
                vol = float((get_mirror().ticker(under) or {}).get("quote_volume") or 0.0)
            except Exception:
                vol = 0.0
            out = _smn.consult({"symbol": under, "direction": "LONG", "market": "CRYPTO",
                                "exchange": "binance",
                                "decision_snapshot": {"market_context": {
                                    "filters": flt, "quote_volume_24h": vol}}})
            if out.get("trained") and out.get("direction") in ("LONG", "SHORT"):
                return out["direction"]
        except Exception:
            return None
        return None

    def _armable(self, sym: str) -> bool:
        """Safety guard (2026-07-12): only arm a pullback for a symbol that's in THIS segment's
        tradeable whitelist, so a symbol that isn't executable can't waste an arming slot on an
        entry that can never open. (Note: NVDA/CRCL/BZ/CL etc. ARE real Binance perps and pass —
        the 2026-07-12 no-open incident was a wedged engine, not leaked symbols.) Per-cycle cached
        set; falls open (returns True) if the whitelist can't be read, so it never over-blocks."""
        try:
            wl = getattr(self, "_arm_wl", None)
            if wl is None:
                wl = self._arm_wl = set(self.symbols() or [])
            return (not wl) or (sym in wl)
        except Exception:
            return True

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

    def sweep_pullbacks(self, cli=None, *, allow_live: bool = False,
                        price_fn=None) -> dict:
        """D3: enter every armed pullback entry whose retrace has arrived. Called from
        run_once, the polling sweeper, AND the Reflex lane (websocket ticks — R2), which
        passes its own tick-fresh price_fn. pullback.sweep pops triggered rows under
        the state-file lock, so a row fires exactly once no matter how many sweepers
        race. Never raises."""
        rep: dict = {"entered": [], "queued": []}
        try:
            from trading.direction import pullback as _pb
            if not _pb.enabled():
                return rep
            cli = cli or self.client()
            for _row in _pb.sweep(
                    price_fn or (lambda s: _pb.live_price(s, self.segment or "futures")),
                    segment=self.segment or "futures"):
                try:
                    _psym = cli.tradeable_form(_row["symbol"], self.segment)
                    if _psym is None:
                        # HONEST DROP LOG (2026-07-12): a triggered pullback that never opens used to
                        # vanish here silently — this is where non-tradeable/leaked symbols (e.g. the
                        # NVDA/CRCL/BZ/CL account-path junk) die. Now it's visible.
                        print(f"[pullback-drop:{self.segment}] {_row['symbol']} "
                              f"src={_row.get('source')} reason=not_tradeable", flush=True)
                        continue
                    # D10 Learned Direction on the REFLEX lane (owner 2026-07-12): the fast lane is
                    # the real live driver, but it fires the pullback's ARMED direction as-is. Gate
                    # it here — invert when the arming source is measured reliably WRONG (same
                    # Wilson-honest bar as the selective loop); a no-edge source still opens
                    # (exploration), so trade flow is never reduced. Flip is re-tagged + recorded so
                    # it earns its own measured track record.
                    _dir = _row["direction"]
                    _ltag = str(_row.get("source") or "pullback")
                    # DEEP-SCAN FIX (2026-07-17, the JCT case): an armed pullback's trend premise
                    # can DIE between arm time and trigger — JCT was armed on the 11:20-25 pump
                    # and fired 11:32 into the fade (MFE=0, entered at the top of a falling bar).
                    # Re-validate at FIRE time from RAM: a LONG firing while price sits at the TOP
                    # of its prior-30m range (or SHORT at the bottom) is chasing a move that
                    # already left (measured: top-entries 40% win vs bottom-entries 90%, n=35).
                    # The refusal is RECORDED (source reflex_poscut, taken=False) so the truth
                    # labeler scores the counterfactual — the gate proves itself or gets removed.
                    # REFLEX_POS_GATE=0 disables; threshold REFLEX_POS_MAX (0.85).
                    if os.environ.get("REFLEX_POS_GATE", "1") in ("1", "true", "TRUE", "yes", "on"):
                        try:
                            from trading.direction import truth_ledger as _tlrp
                            _rp = _tlrp.range_position(_row["symbol"])
                            _pmax = float(os.environ.get("REFLEX_POS_MAX", "0.85") or 0.85)
                            _adverse = (_rp is not None and
                                        ((_dir == "LONG" and _rp > _pmax) or
                                         (_dir == "SHORT" and _rp < 1.0 - _pmax)))
                            if _adverse:
                                _tlrp.record(symbol=_row["symbol"], market="CRYPTO",
                                             segment=self.segment or "futures",
                                             direction=_dir, source="reflex_poscut",
                                             taken=False)
                                print(f"[reflex-poscut:{self.segment}] {_row['symbol']} "
                                      f"{_dir} refused at range-pos {_rp:.2f} "
                                      f"(armed by {_ltag})", flush=True)
                                continue
                        except Exception:
                            pass
                    if os.environ.get("LEARNED_DIRECTION", "1") in ("1", "true", "TRUE", "yes", "on"):
                        try:
                            from trading.direction import learned_direction as _ld
                            from trading.direction.regime import classify as _ldrg
                            _lreg = (_ldrg(_row["symbol"]) or {}).get("regime")
                            _cd, _ci = _ld.correct_direction(
                                _dir, source=_ltag, market="CRYPTO",
                                segment=self.segment or "futures", regime=_lreg,
                                symbol=_row["symbol"])
                            if _ci.get("action") == "invert":
                                # teach the ledger: the ORIGINAL source's own (overridden) call is
                                # recorded as a SKIPPED claim so it earns its honest track record —
                                # the very signal that proved it wrong keeps sharpening. The entered
                                # (inverted) claim is recorded taken=True below under the
                                # "learned_direction" tag. No double-count, no mis-attribution.
                                try:
                                    from trading.direction import truth_ledger as _ldtl
                                    _ldtl.record(symbol=_row["symbol"], market="CRYPTO",
                                                 segment=self.segment or "futures",
                                                 direction=_ci.get("from"), source=_ltag,
                                                 taken=False, regime=_lreg)
                                except Exception:
                                    pass
                                print(f"[reflex-learned:{self.segment}] {_row['symbol']} "
                                      f"{_ci.get('from')}→{_cd} (src={_ci.get('source')} "
                                      f"rate={_ci.get('rate')} n={_ci.get('n')})", flush=True)
                                _dir, _ltag = _cd, "learned_direction"
                        except Exception:
                            pass
                    _res = cli.place_order(
                        symbol=_psym, action="BUY",
                        side=("long" if _dir == "LONG" else "short"),
                        allow_live=allow_live,
                        enter_tag=_ltag,
                        segment=self.segment)
                    if isinstance(_res, dict) and _res.get("ok") is False:
                        print(f"[pullback-drop:{self.segment}] {_psym} src={_row.get('source')} "
                              f"reason=refused:{(_res.get('reason') or _res.get('error') or _res)!s:.80}",
                              flush=True)
                        continue
                    if isinstance(_res, dict) and _res.get("queued"):
                        rep["queued"].append(_psym)
                    else:
                        rep["entered"].append(_psym)
                    self._record_entry_meta(
                        _psym, _dir, _ltag,
                        {"pullback": {k: _row.get(k) for k in
                                      ("ref_price", "entry_ref", "atr",
                                       "armed_ts")}}, None, explore=True)
                except Exception:
                    continue
        except Exception:
            pass
        return rep

    def _filter_side(self, pick: dict, preset: str) -> str:
        """Initial SIDE for a Binance-filter pick, BEFORE learned_direction correction. momentum =
        continue the move (sign of %chg); funding_extreme = fade the crowded funding; default long."""
        pct = pick.get("pct_change")
        fund = pick.get("funding_rate")
        if preset == "funding_extreme" and fund is not None:
            return "SHORT" if float(fund) > 0 else "LONG"      # longs pay funding → fade
        if pct is not None:
            return "LONG" if float(pct) >= 0 else "SHORT"
        return "LONG"

    def _lens_reads(self, psym: str, *, base: list, regime: str | None,
                    signals: list | None = None, features: dict | None = None,
                    fast: bool = True) -> tuple[list, dict | None]:
        """ONE lens family for EVERY decision lane (2026-07-17). Until now the breadth lane read
        ~15 sources while the selective lane — the lane that actually opened most trades — read
        only 4 (funnel vote + fusion + strategy_library + direction_model); a lens could earn
        weight in a lane that rarely fires and never influence the lane that does. This helper is
        the single place lenses are collected so the two lanes can't drift apart again.

        Appends to `base` (returned list is a new object): the bull/bear debate (LLM — deep lane
        only, fast=False), symbol-move net, strategy-tournament table, brain sources (hypothesis/
        experience/news/river + worldmodel/concept in the deep lane), opening-range VP events and
        cross-symbol market state. Every source is truth-ledger-recorded by its own module or here,
        so it EARNS weight by measured edge (CONVENTIONS §16). Returns (reads, strategy_table_row).
        Never raises; each lens fails open."""
        _reads = list(base)
        features = features or {}
        try:                                          # E6: prioritize this symbol on the depth
            from trading.broker_sense.binance_stream import get_mirror   # stream so dobi book
            get_mirror().request_depth([psym])        # features exist where decisions happen
        except Exception:
            pass
        try:                                          # proposal E: the bull/bear/risk debate
            if not fast \
                    and os.environ.get("DEBATE_DIRECTION", "1") in ("1", "true", "TRUE", "yes", "on") \
                    and _reads:                       # CONTESTS the preliminary lean (LLM — deep lane)
                from trading.brain import debate_gate as _dbg
                _prelim = "long" if (sum(p for _, p in _reads) / len(_reads)) >= 0.5 else "short"
                _dfeats = dict(features)
                try:                                  # B2 fix: past lessons finally get a reader
                    from trading.brain import lesson_recall as _lr
                    _lsn = _lr.recent(psym, k=2)
                    if _lsn:
                        _dfeats["past_lessons"] = " | ".join(_lsn)[:400]
                except Exception:
                    pass
                _dc = _dbg.get_debate_gate().contest(psym, _prelim, features=_dfeats)
                if _dc.get("direction") != "neutral":
                    _reads.append(("debate", _dc["p_up"]))
        except Exception:
            pass
        # NB: the post-mortem miner is a WIN-QUALITY / sizing signal, not a directional source,
        # so it is intentionally NOT added to these directional readings — it closes the loop via
        # fusion's size_mult + ideal-entry nudge instead (see indicator_fusion + postmortem.py).
        try:                                          # SYMBOL-MOVE NET (owner 2026-07-13): the
            from trading.brain import symbol_move_net as _smn   # multi-head net's p_up is a genuine
            if _smn.enabled():                        # P(price up) → a real directional reading
                _flt = {s: p for s, p in (signals or [])}
                _mv = 0.0
                try:
                    from trading.broker_sense.binance_stream import get_mirror
                    _mv = float((get_mirror().ticker(psym) or {}).get("quote_volume") or 0.0)
                except Exception:
                    _mv = 0.0
                _ctx = {"symbol": psym, "direction": "LONG", "market": "CRYPTO",
                        "exchange": "binance", "market_regime_entry": regime,
                        "decision_snapshot": {"market_context": {
                            "filters": _flt, "quote_volume_24h": _mv}}}
                _sm = _smn.consult(_ctx)
                if _sm.get("p_up") is not None and _sm.get("trained"):
                    _reads.append(("symbol_move_net", _sm["p_up"]))
                    try:                              # measure its direction hit-rate in the ledger
                        from trading.direction import truth_ledger as _tl3
                        _tl3.record(symbol=psym, market="CRYPTO",
                                    segment=self.segment or "futures",
                                    direction=("LONG" if _sm["p_up"] >= 0.5 else "SHORT"),
                                    source="symbol_move_net", confidence=_sm["p_up"],
                                    regime=regime)
                    except Exception:
                        pass
        except Exception:
            pass
        # STRATEGY-TABLE SYNERGY (2026-07-13, gated STRATEGY_DIRECTION=1): fold the per-coin
        # tournament's best library/created/evolved/researched strategy into the direction fusion
        # as a MEASURED source (weighted by its own truth-ledger edge, like every other lens), and
        # let a gate-clearing strategy that AGREES with the fused side own the enter_tag — so the
        # created/evolved/researched strategies both INFLUENCE and DRIVE breadth entries, and the
        # Strategy column shows the real strategy that led. O(1) table read — NO tournament here.
        _bf = None
        if os.environ.get("STRATEGY_DIRECTION", "1") in ("1", "true", "TRUE", "yes", "on"):
            try:
                from trading.crypto.freqtrade import strategy_table as _stab
                _bf = _stab.lookup(psym)
                if _bf and _bf.get("signal") in ("LONG", "SHORT"):
                    _p = ((0.82 if _bf.get("cleared_gate") else 0.66)
                          if _bf["signal"] == "LONG"
                          else (0.18 if _bf.get("cleared_gate") else 0.34))
                    _reads.append(("strategy_tournament", _p))
                    try:                          # measure its direction hit-rate in the ledger
                        from trading.direction import truth_ledger as _tl4
                        _tl4.record(symbol=psym, market="CRYPTO",
                                    segment=self.segment or "futures",
                                    direction=_bf["signal"], source="strategy_tournament",
                                    confidence=_p if _bf["signal"] == "LONG" else 1.0 - _p,
                                    regime=regime)
                    except Exception:
                        pass
            except Exception:
                _bf = None
        # BRAIN LENSES AS MEASURED SOURCES (2026-07-14): fold the formerly-advisory brain
        # outputs — confirmed hypotheses, experience recall, news sentiment (+ world-model &
        # concept-discovery in the deep lane) — into the SAME fusion as every other lens, each
        # recorded to the truth ledger so it EARNS weight by measured edge (unproven ⇒ ~0 weight,
        # cannot move a trade until it proves right). Cheap lenses only in the fast breadth lane
        # (fast=True) so a 50-coin cycle keeps its deadline.
        try:
            from trading.direction import brain_sources as _bsrc
            _prelim = ("LONG" if _reads and (sum(p for _, p in _reads) / len(_reads)) >= 0.5
                       else "SHORT")
            _reads.extend(_bsrc.collect(
                psym, market="CRYPTO", segment=self.segment or "futures", regime=regime,
                direction_hint=_prelim, features=features, fast=fast))
        except Exception:
            pass
        # VIDEO-DERIVED LENSES (2026-07-17): opening-range value-area events (trap /
        # acceptance-pullback, per session anchor) + cross-symbol market state (leader
        # spillover, seesaw, breadth tilt). RAM-only reads; never raise.
        try:
            from trading.direction import vp_events as _vpe
            _reads.extend(_vpe.readings(psym, segment=self.segment or "futures",
                                        regime=regime))
        except Exception:
            pass
        try:
            from trading.direction import market_state as _mst
            _reads.extend(_mst.readings(psym, segment=self.segment or "futures",
                                        regime=regime))
        except Exception:
            pass
        try:                                          # E4 (2026-07-17): the distilled-lesson
            from trading.direction import lesson_prior as _lp   # prior — O(1) table read;
            _reads.extend(_lp.readings(psym, segment=self.segment or "futures",   # the LLM
                                       regime=regime))          # distiller runs on the
        except Exception:                                       # learning cadence only
            pass
        try:                                          # E5 (2026-07-17): on-chain flow lane
            from trading.direction import onchain_source as _oc   # (cached snapshot read;
            _reads.extend(_oc.readings(psym, segment=self.segment or "futures",   # fetches
                                       regime=regime))          # live on the learn cadence)
        except Exception:
            pass
        return _reads, _bf

    def _learned_filter_side(self, pick: dict, preset: str,
                             regime: str | None, *, fast: bool = False) -> tuple:
        """Stage 3: the LEARNED per-pick side. Fuse the cheap UI direction mini-lenses through the
        reliability-weighted decider; use its side when it has a proven edge (tag 'learned_direction'),
        else EXPLORE on the momentum prior (tag 'filter:<preset>') so the lane still opens and
        generates the labels the decider learns from. Returns (side, enter_tag, decide_out|None).

        fast=True (the TOP-N breadth lane, owner 2026-07-13): SKIP the bull/bear/risk debate — it is
        an LLM round per pick, fatal across 50 candidates (only ~5 got processed before the cycle
        deadline). The RAM lenses (app_signals + direction_model + symbol_move_net + learned_direction)
        stay; the decide_out carries the collected signals so the caller reuses them (no 2nd collect)."""
        try:
            from trading.direction import learned_direction as _ld
            from trading.direction import app_signals as _asig
            _psym = (pick.get("symbol") if isinstance(pick, dict) else "") or ""
            # ALL captured filters/screeners (not just momentum): book/taker/OI/long-short/
            # liquidations/funding/PCR — each weighted by its MEASURED edge (owner 2026-07-13).
            _col = _asig.collect(_psym, market="crypto",
                                 row=pick if isinstance(pick, dict) else None)
            _reads = list(_col["signals"])
            try:                                          # proposal B: the direction model as a
                from trading.direction import direction_model as _dm   # measured source
                _pm = _dm.predict(_asig.feature_dict(_col["signals"]))
                if _pm is not None:
                    _reads.append((_dm.SOURCE, _pm))
            except Exception:
                pass
            _reads, _bf = self._lens_reads(_psym, base=_reads, regime=regime,
                                           signals=_col.get("signals"),
                                           features=_asig.feature_dict(_col.get("signals") or []),
                                           fast=fast)
            # MISSION control lane (2026-07-17): deterministic ~20% of (symbol, UTC-day)
            # keeps the pre-mission decider under tag learned_direction_ctl — the permanent
            # benchmark. Live variant additionally passes the X-C cost gate at its emitted
            # horizon; a refused trade falls through to the explore prior (labels keep
            # flowing; only the LEARNED override is withheld).
            import zlib as _zl
            _var = ("control" if _zl.crc32(
                f"{_psym}{time.strftime('%Y%m%d', time.gmtime())}".encode()) % 5 == 0
                else "live")
            out = _ld.decide(_reads, market="CRYPTO",
                             segment=self.segment or "futures", regime=regime,
                             symbol=_psym, coverage=_col["coverage"], variant=_var,
                             extra_conditioners={"sel": str(preset or "breadth")})
            out["_signals"] = _col.get("signals")     # reused by the lane's record batch (no 2nd collect)
            try:                                      # write-only vote log (B1 diversity study)
                from trading.direction import vote_log as _vlog
                _vlog.log(symbol=_psym, market="CRYPTO", segment=self.segment or "futures",
                          lane="breadth", reads=_reads, regime=regime,
                          decided=(out.get("direction") or "abstain"),
                          preset=str(preset or ""))
            except Exception:
                pass
            if not out.get("abstained") and out.get("direction") in ("long", "short") \
                    and _var == "live":
                _cg = _ld.cost_gate(out.get("p_up") or 0.5, symbol=_psym,
                                    horizon=out.get("horizon") or "1h")
                out["cost_gate"] = _cg
                if not _cg.get("pass"):
                    try:                          # verdict-2 evidence: the REFUSED side gets
                        from trading.direction import truth_ledger as _tlcg   # its own ledger
                        _tlcg.record(symbol=_psym, market="CRYPTO",           # identity so the
                                     segment=self.segment or "futures",       # labeler scores
                                     direction=out["direction"].upper(),      # the counterfactual
                                     source="learned_direction_costcut",
                                     confidence=out.get("p_up"), regime=regime)
                    except Exception:
                        pass
                    out["abstained"] = True
                    out["direction"] = "neutral"
            if not out.get("abstained") and out.get("direction") in ("long", "short"):
                _side = out["direction"].upper()
                # a gate-clearing strategy that AGREES with the fused side DRIVES → tag = its name
                if (_bf and _bf.get("cleared_gate") and _bf.get("best_strategy")
                        and _bf.get("signal") == _side):
                    out["strategy_drove"] = _bf["best_strategy"]
                    return _side, _bf["best_strategy"], out
                return _side, ("learned_direction" if _var == "live"
                               else "learned_direction_ctl"), out
        except Exception:
            pass
        return self._filter_side(pick, preset), f"filter:{preset}", None

    def open_filter_lane(self, *, allow_live: bool = False,
                         deadline: float | None = None) -> dict:
        """Stage 1b — the Binance-filter TOP-N breadth lane (owner idea, APPROVED 2026-07-12).

        Reads the WHOLE UI-captured universe (ui_market), ranks it by the active filter preset, and
        opens the adaptive top-N that aren't already open. Each pick's SIDE is derived from the
        filter then passed through learned_direction.correct_direction, so a preset measured
        reliably-wrong is inverted and every preset earns its own truth-ledger track record (the
        input Stage 2's learned combo-selector will rank on). A NEW PARALLEL lane, kill-switched by
        BINANCE_FILTER_LANE — it never touches the funnel screen. Never raises. Paper-first."""
        rep: dict = {"entered": [], "skipped": 0, "preset": None, "ranked": 0}
        try:
            from trading.broker_sense import binance_filter_lane as _bfl
            if not _bfl.enabled():
                return rep
            # MULTI-PRESET breadth (owner 2026-07-13): the lane ran ONLY 'momentum', so the same
            # top movers churned and the concurrent count plateaued. Union the top-N across SEVERAL
            # presets (momentum + squeeze + funding_extreme + liquidity) so each cycle surfaces a
            # DIVERSE candidate set — different dislocations, different symbols. Deduped by symbol,
            # remembering which preset surfaced each (its side derivation uses that preset). Single
            # preset still available via BINANCE_FILTER_PRESET; BINANCE_FILTER_PRESETS overrides the list.
            _plist = [p.strip() for p in os.environ.get(
                "BINANCE_FILTER_PRESETS", "momentum,squeeze,funding_extreme,liquidity").split(",")
                if p.strip()] or [os.environ.get("BINANCE_FILTER_PRESET", "momentum")]
            _seen: set = set()
            picks = []
            for _pr in _plist:
                try:
                    for _pk in _bfl.top_picks(self.segment or "futures", preset=_pr):
                        _s = _pk.get("symbol")
                        if _s and _s not in _seen:
                            _seen.add(_s)
                            picks.append({**_pk, "_preset": _pr})
                except Exception:
                    continue
            preset = _plist[0]
            rep["preset"], rep["ranked"] = ",".join(_plist), len(picks)
            cli = self.client()
            try:
                open_pairs = set(cli.open_pairs(segment=self.segment))
            except Exception:
                open_pairs = set()
            from concurrent.futures import ThreadPoolExecutor
            from trading.direction.regime import classify as _rgc
            # THROUGHPUT (owner 2026-07-13): the old loop did per-pick LLM debate + duplicate
            # app_signals + ~10 blocking truth-ledger writes, so only ~5 of 50 ranked picks got
            # processed before the cycle deadline. Three levers: (1) fast=True side derivation
            # skips the LLM debate; (2) the compute-heavy side derivation runs in a THREAD POOL
            # (RAM lenses + pure decider — no browser, no shared client mutation); (3) the learning
            # records are BATCHED and written AFTER placement (off the entry hot path). Order
            # placement stays sequential + open_pairs-guarded (controlled, no order-client race).
            _workers = max(1, int(os.environ.get("FILTER_LANE_WORKERS", "8") or 8))

            def _derive(pick):
                sym = pick.get("symbol")
                if not sym:
                    return None
                # eyes surface FLAT tickers ('DODOXUSDT'); the engine trades slashed pairs.
                _psym = cli.tradeable_form(_bfl.to_pair(sym, self.segment or "futures"), self.segment)
                if _psym is None or _psym in open_pairs:
                    return ("skip", pick, _psym, None, None, [])
                _reg = (_rgc(sym) or {}).get("regime")
                _side, _tag, _ldout = self._learned_filter_side(
                    pick, pick.get("_preset", preset), _reg, fast=True)
                recs = []                                  # deferred learning records
                try:
                    from trading.direction import app_signals as _asig2
                    from trading.direction import direction_model as _dmodel
                    _rich = (_ldout or {}).get("_signals") or _asig2.signals(
                        sym, market="crypto", row=pick if isinstance(pick, dict) else None)
                    _fd = _asig2.feature_dict(_rich)
                    for _msrc, _mp in _rich:
                        recs.append((sym, "LONG" if _mp >= 0.5 else "SHORT", _msrc, _mp, _reg, _fd))
                    _pm = _dmodel.predict(_fd)
                    if _pm is not None:
                        recs.append((sym, "LONG" if _pm >= 0.5 else "SHORT",
                                     _dmodel.SOURCE, _pm, _reg, _fd))
                except Exception:
                    pass
                return ("ok", pick, _psym, _side, _tag, recs)

            with ThreadPoolExecutor(max_workers=_workers) as _ex:   # parallel side derivation
                derived = [d for d in _ex.map(_derive, picks) if d]
            all_recs: list = []
            for kind, pick, _psym, _side, _tag, recs in derived:    # sequential guarded placement
                all_recs.extend(recs)
                if kind == "skip" or _psym in open_pairs:
                    rep["skipped"] += 1
                    continue
                if deadline is not None and time.monotonic() > deadline:
                    break
                # SEGMENT VALIDITY (2026-07-16). The lane ranks the whole UI/mirror-captured
                # universe and derives a side from learned_direction — neither step knows what the
                # TARGET SEGMENT can actually accept, so every cycle burned its budget on entries
                # Freqtrade rejected outright. Measured live: futures logged entered=[] skipped=0
                # with err="Symbol does not exist or market is not active", and spot with
                # "Can't go short on Spot markets". Both are refusals the engine can only answer
                # AFTER a REST round-trip, so the lane paid full latency to be told no.
                #
                # 1) SPOT CANNOT SHORT. A SHORT read on spot means "do not buy" — so SKIP it.
                # ONE BAD SYMBOL MUST NOT KILL THE CYCLE (root cause of "futures never opens",
                # 2026-07-16). place_order -> engine_client._check RAISES FreqtradeError on any
                # API-level refusal. This loop caught the RETURNED refusal ({"ok": False}, our own
                # tradeability guard) but never the RAISED one, so the exception escaped to the
                # outer `except` and aborted every remaining candidate. The logs prove it:
                # `ranked=90 entered=[] skipped=0 err=forceenter failed: Symbol does not exist or
                # market is not active` — skipped=0 means it died on candidate #1 and never reached
                # #2. Spot survived only because its 5 static pairs happen to validate cleanly.
                #
                # Why the pre-check does not prevent this: _derive() DOES call tradeable_form()
                # (line ~574), but _pair_tradeable FAILS OPEN by design on lookup failure AND
                # validates against raw ccxt "active" markets, which are WIDER than Freqtrade's own
                # internal pairlist. So the engine can still legitimately refuse a symbol we
                # consider tradeable. Per-pick isolation is the honest fix: refusals are data
                # (logged + skipped), not a cycle-ending fault.
                #
                # SPOT CANNOT SHORT: a SHORT read on spot means "do not buy" -> skip. Never flip it
                # to long — that would fabricate a direction the brain did not choose. This refusal
                # ("Can't go short on Spot markets") was already non-fatal, just wasted slots.
                if _side == "SHORT" and (self.segment or "futures") == "spot":
                    rep["skipped"] += 1
                    continue
                try:
                    _res = cli.place_order(
                        symbol=_psym, action="BUY", side=("long" if _side == "LONG" else "short"),
                        allow_live=allow_live, enter_tag=_tag, segment=self.segment)
                except Exception as _oe:               # engine refusal / transport fault
                    print(f"[filter-lane-drop:{self.segment}] {_psym} preset={preset} "
                          f"reason=raised:{_oe!s:.80}", flush=True)
                    rep["skipped"] += 1
                    continue
                if isinstance(_res, dict) and _res.get("ok") is False:
                    print(f"[filter-lane-drop:{self.segment}] {_psym} preset={preset} "
                          f"reason=refused:{(_res.get('reason') or _res.get('error') or _res)!s:.60}",
                          flush=True)
                    rep["skipped"] += 1
                    continue
                rep["entered"].append(_psym)
                open_pairs.add(_psym)
                self._record_entry_meta(
                    _psym, _side, _tag,
                    {"filter": {k: pick.get(k) for k in
                                ("filter_preset", "filter_score", "pct_change",
                                 "funding_rate")},
                     # MISSION X-B: the decide() output (incl. horizon + cost gate + variant)
                     # travels with the trade so exits and post-mortem can consume it
                     "learned_direction": {k: v for k, v in (_ldout or {}).items()
                                           if k != "_signals"} or None},
                    None, explore=True)
            if all_recs:                                    # BATCH the learning records off the hot path
                try:
                    from trading.direction import truth_ledger as _tl
                    for _sym, _d, _src, _mp, _reg2, _fd2 in all_recs:
                        _tl.record(symbol=_sym, market="CRYPTO", segment=self.segment or "futures",
                                   direction=_d, source=_src, confidence=_mp, regime=_reg2,
                                   taken=False, features=_fd2)
                except Exception:
                    pass
            if rep["ranked"]:            # ALWAYS log when the lane ran (an all-skipped cycle must
                                         # never look identical to a dead lane — debug-error lesson)
                print(f"[filter-lane:{self.segment}] preset={preset} ranked={rep['ranked']} "
                      f"entered={rep['entered']} skipped={rep['skipped']}", flush=True)
        except Exception as e:
            rep["error"] = str(e)[:150]
        return rep

    def open_lens_lane(self, *, allow_live: bool = False) -> dict:
        """Stage 1c — the B3 LENS PAPER LANE (owner-ordered 2026-07-16).

        Every orphaned directional lens (cortex, world-model, concept discovery, experience
        recall, news, river, debate, dir-exit read, hypothesis) nominates its strongest
        conviction from a rotating universe slice and OPENS it as a real paper trade under its
        own identity: enter_tag="lens:<name>" → journal strategy_name → per-lens realized P&L,
        plus a taken=True truth-ledger claim per entry. Kill-switched by LENS_LANE (default ON —
        paper is the experiment, CONVENTIONS §15). Never raises. Crypto executor only."""
        rep: dict = {"entered": [], "skipped": 0, "nominated": 0}
        try:
            from trading.brain import lens_lane as _lla
            if not _lla.enabled():
                return rep
            from trading.direction import app_signals as _asig2
            from trading.direction.regime import classify as _rgc2

            def _feats(sym: str) -> dict:
                return _asig2.feature_dict(_asig2.signals(sym) or [])

            noms = _lla.nominations(
                symbols=self.symbols(), segment=self.segment or "futures",
                ohlcv_fn=self.decider._ohlcv, features_fn=_feats,
                regime_fn=lambda s: (_rgc2(s) or {}).get("regime"))
            rep["nominated"] = len(noms)
            if not noms:
                # an all-abstained cycle must never look identical to a dead lane
                print(f"[lens-lane:{self.segment}] nominated=0 (all lenses abstained)",
                      flush=True)
                return rep
            cli = self.client()
            try:
                open_pairs = set(cli.open_pairs(segment=self.segment))
            except Exception:
                open_pairs = set()
            rep["skip_reasons"] = []
            for n in noms:
                sym, act, tag = n["symbol"], n["direction"], f"lens:{n['lens']}"
                try:
                    tsym = cli.tradeable_form(sym, self.segment)
                    if tsym is None or tsym in open_pairs or sym in open_pairs:
                        rep["skipped"] += 1
                        rep["skip_reasons"].append(
                            f"{tag}:{sym}:" + ("untradeable" if tsym is None else "already-open"))
                        continue
                    res = cli.place_order(symbol=tsym, action="BUY",
                                          side=("long" if act == "LONG" else "short"),
                                          allow_live=allow_live, enter_tag=tag,
                                          segment=self.segment)
                    if not isinstance(res, dict) or res.get("ok") is False:
                        rep["skipped"] += 1
                        rep["skip_reasons"].append(
                            f"{tag}:{sym}:refused:{str((res or {}).get('error'))[:60]}")
                        continue
                    try:                          # identity claim: the lens owns this call
                        from trading.direction import truth_ledger as _tl5
                        _tl5.record(symbol=sym, market="CRYPTO",
                                    segment=self.segment or "futures", direction=act,
                                    source=tag, confidence=n["p_up"] if act == "LONG"
                                    else 1.0 - n["p_up"], taken=True)
                    except Exception:
                        pass
                    self._record_entry_meta(tsym, act, tag,
                                            {"lens_lane": {**n}}, None, explore=True)
                    if res.get("queued"):
                        rep["skipped"] += 1       # inbox mode: queued ≠ filled
                        continue
                    rep["entered"].append(tsym)
                    open_pairs.add(tsym)
                except Exception:
                    rep["skipped"] += 1
            if rep["nominated"]:                  # an all-skipped cycle must never look dead
                print(f"[lens-lane:{self.segment}] nominated={rep['nominated']} "
                      f"entered={rep['entered']} skipped={rep['skipped']} "
                      f"reasons={rep.get('skip_reasons')}", flush=True)
        except Exception as e:
            rep["error"] = str(e)[:150]
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
        self._arm_wl = None                    # per-cycle fresh tradeable set for _armable (B-fix)
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
        self._cortex_sigs: dict = {}           # per-cycle CORTEX signals → stacking features
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
                            if _q and self._armable(sym) and _pb.arm(symbol=sym,
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
                        # LAZY OHLCV (W2 perf, 2026-07-12): pass a fetch callable, not a
                        # pre-fetched df — the ~60% of coins the tournament gated OUT return
                        # their verdict from the table alone and never trigger the per-coin
                        # network fetch, cutting the serial OHLCV cost of the scan.
                        d = _mp.decide(sym, df_fn=lambda s=sym: self.decider._ohlcv(s),
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
                    # PREFER the rich indicator_fusion lens (multi-TF confluence + vision +
                    # order-flow + volume-profile + YOLO + direction-equation + on-chain) over the
                    # raw mtf vote — it is a strictly richer read and, tagged "indicator_fusion",
                    # passes through the mirror_gate below so its measured reliability governs it
                    # (wired 2026-07-12: fusion was computed every cycle but never drove entries).
                    _fz = (getattr(self, "extra_signals", {}) or {}).get(sym, {}).get("indicator_fusion") or {}
                    _fdir = _fz.get("direction") if _fz.get("available") else None
                    _vote = (getattr(self, "extra_signals", {}) or {}).get(sym, {}).get("vote", {})
                    _vdir = (_vote or {}).get("direction")
                    if _fdir == "long":
                        act, tag = "LONG", (tag or "indicator_fusion")
                    elif _fdir == "short":
                        act, tag = "SHORT", (tag or "indicator_fusion")
                    elif _vdir == "long":
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
                # D10 Learned Direction Driver (Pillar 27, owner 2026-07-12: "the votes are
                # unreliable — replace them with something that learns from being wrong"):
                # re-decide the side from the per-symbol lenses (vote + indicator_fusion +
                # strategy_library) weighted by each source's MEASURED truth-ledger edge, regime-
                # aware. The ~47% mtf vote (an anti-signal in trends) is ignored or INVERTED; a
                # lens is trusted only once its Wilson CI clears chance. Overrides the chosen side
                # ONLY on a confident, significant read; abstains → the existing decision stands,
                # so exploration/trade-flow is never starved. Tagged "learned_direction" so the
                # flip earns its own measured track record (never grades its own homework).
                if os.environ.get("LEARNED_DIRECTION", "1") in ("1", "true", "TRUE", "yes", "on") \
                        and sym not in open_pairs:
                    try:
                        from trading.direction import learned_direction as _ld
                        from trading.direction.regime import classify as _ldrg
                        _lsig = (getattr(self, "extra_signals", {}) or {}).get(sym, {}) or {}
                        _lreg = (_ldrg(sym) or {}).get("regime")
                        _reads = []
                        _lv = _lsig.get("vote") or {}
                        if _lv.get("p_up") is not None:
                            _reads.append(("funnel_mtf_vote", _lv.get("p_up")))
                        for _lsrc in ("indicator_fusion", "strategy_library"):
                            _ll = _lsig.get(_lsrc) or {}
                            if _ll.get("available") and _ll.get("p_up") is not None:
                                _reads.append((_lsrc, _ll.get("p_up")))
                        _ff = {}
                        try:                          # B fix: the direction model as a source
                            from trading.direction import direction_model as _dmod   # HERE its
                            from trading.direction import meta_labeler as _mlab       # f_* features
                            _ff = _mlab.lens_features(_lsig.get("indicator_fusion")) or {}
                            _pmf = _dmod.predict(_ff)
                            if _pmf is not None:
                                _reads.append((_dmod.SOURCE, _pmf))
                        except Exception:
                            pass
                        try:                          # 2026-07-17 lens parity: the DOMINANT entry
                            # lane finally reads the same lens family as breadth (SMN, strategy
                            # tournament, brain sources, VP events, market state) PLUS the deep
                            # lenses (debate + flag-gated worldmodel/concept) — affordable here
                            # because this lane decides a shortlist, not 50 picks.
                            _reads, _ = self._lens_reads(sym, base=_reads, regime=_lreg,
                                                         features=_ff, fast=False)
                        except Exception:
                            pass
                        # MISSION control lane (2026-07-17): a deterministic ~20% of
                        # (symbol, UTC-day) keeps the pre-mission decider (cumulative
                        # weights, no cost gate) under its own tag — the permanent
                        # benchmark every improvement must beat. Never delete it.
                        import zlib as _zl
                        _var = ("control" if _zl.crc32(
                            f"{sym}{time.strftime('%Y%m%d', time.gmtime())}".encode())
                            % 5 == 0 else "live")
                        _ldo = _ld.decide(_reads, market="CRYPTO",
                                          segment=self.segment or "futures", regime=_lreg,
                                          symbol=sym, variant=_var,
                                          extra_conditioners={"sel": "selective"})
                        try:                          # write-only vote log (B1 diversity study)
                            from trading.direction import vote_log as _vlog
                            _vlog.log(symbol=sym, market="CRYPTO",
                                      segment=self.segment or "futures", lane="selective",
                                      reads=_reads, regime=_lreg,
                                      decided=(_ldo.get("direction") or "abstain"))
                        except Exception:
                            pass
                        if not _ldo.get("abstained") and _ldo.get("direction") in ("long", "short") \
                                and _var == "live":
                            # X-C: the live variant's edge must clear costs at its horizon
                            _cg = _ld.cost_gate(_ldo.get("p_up") or 0.5, symbol=sym,
                                                horizon=_ldo.get("horizon") or "1h")
                            _ldo["cost_gate"] = _cg
                            if not _cg.get("pass"):
                                try:              # verdict-2 evidence (see breadth lane)
                                    from trading.direction import truth_ledger as _tlcg
                                    _tlcg.record(symbol=sym, market="CRYPTO",
                                                 segment=self.segment or "futures",
                                                 direction=_ldo["direction"].upper(),
                                                 source="learned_direction_costcut",
                                                 confidence=_ldo.get("p_up"), regime=_lreg)
                                except Exception:
                                    pass
                                _ldo["abstained"] = True
                                _ldo["direction"] = "neutral"
                        if not _ldo.get("abstained") and _ldo.get("direction") in ("long", "short"):
                            _lact = _ldo["direction"].upper()
                            _lsrc_name = ("learned_direction" if _var == "live"
                                          else "learned_direction_ctl")
                            try:
                                from trading.direction import truth_ledger as _ldtl
                                _ldtl.record(symbol=sym, market="CRYPTO",
                                             segment=self.segment or "futures",
                                             direction=_lact, source=_lsrc_name,
                                             confidence=_ldo.get("p_up"), regime=_lreg,
                                             conditioners={"sel": "selective"})
                            except Exception:
                                pass
                            brain = {**brain, "learned_direction": _ldo}
                            act = _lact
                            tag = tag or _lsrc_name
                    except Exception:
                        pass
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
                            "regime": _rg(sym).get("regime"), "taken": True,
                            "features": self._stack_features(sym)})   # M1 stacking: lenses + cortex
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
                # indicator fusion: the rich multi-lens signal (order-flow/VP/YOLO/direction-eq/
                # on-chain/vision) scales confidence by its agreement with the chosen side,
                # weighted by its own conviction (advisory; measured as a source via truth_ledger).
                if act in ("LONG", "SHORT") and sym not in open_pairs:
                    self._apply_fusion(sym, act, brain)
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
                            if _q and self._armable(sym) and _pb.arm(symbol=sym,
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
                    # MIN-HOLD guard (owner 2026-07-12: 'exiting too soon'): don't strategy-exit a
                    # trade younger than EXIT_MIN_HOLD_S — give the thesis time to play out; the
                    # stoploss + profit tailgate still protect it in the meantime. 0 disables.
                    if self._too_young_to_exit(cli, sym):
                        skipped += 1
                    else:
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
            # BUG FIX (2026-07-13): the options are BINANCE USDC contracts — the old ccxt.deribit()
            # returned an EMPTY book for every Binance symbol (bid=0) → fail-closed hollow_book on
            # ALL options → none ever opened. Read the real book from Binance's own eapi depth.
            from trading.broker_sense import binance_options as _bo
            native = self._to_binance_option(symbol)
            bk = _bo.option_book(native) if native else None
            if not bk:
                return False
            bid, ask = bk
            if bid <= 0 or ask <= 0:
                return False
            max_spread = float(os.environ.get("OPTIONS_MAX_SPREAD_PCT", "12"))
            return (ask - bid) / ((ask + bid) / 2.0) * 100.0 <= max_spread
        except Exception:
            return False

    @staticmethod
    def _to_binance_option(sym: str) -> str | None:
        """ccxt option symbol 'AVAX/USDC:USDC-260714-6.5-P' → Binance native 'AVAX-260714-6.5-P'
        (the eapi depth format). None when it isn't a well-formed option symbol."""
        try:
            base = sym.split("/", 1)[0]
            parts = sym.split(":", 1)[1].split("-")     # [SETTLE, EXPIRY, STRIKE, TYPE]
            if len(parts) < 4:
                return None
            return f"{base}-{parts[1]}-{parts[2]}-{parts[3]}"
        except (IndexError, AttributeError):
            return None

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
                if act not in ("LONG", "SHORT"):          # tournament inconclusive → RAM move-net 2nd opinion
                    _mn = self._move_net_direction(under)  # SymbolMoveNet on RAM features (owner 2026-07-13)
                    if _mn:
                        act = _mn
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
            try:                                   # stash for the stacking meta-learner features
                self._cortex_sigs[sym] = sig
            except Exception:
                pass
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

    def _apply_fusion(self, sym: str, act: str, brain: dict) -> dict | None:
        """Wire the rich indicator_fusion lens INTO the live decision (2026-07-12).

        Research (deep-connect audit): calibrated, reliability-weighted combination of
        heterogeneous alphas beats simple averaging (López de Prado meta-labeling). So fusion
        is a NAMED source: its AGREEMENT with the chosen side scales confidence (bounded ±25%,
        weighted by its own conviction |confluence|), and its directional claim is measured by
        the truth ledger (source="indicator_fusion") so the mirror gate can invert it if it ever
        becomes an anti-signal. Advisory on confidence; never forces an entry here (the FLAT
        fallback above already adopts its direction under the mirror gate). Returns the fusion
        dict for provenance, else None."""
        try:
            fz = (getattr(self, "extra_signals", {}) or {}).get(sym, {}).get("indicator_fusion") or {}
            if not fz or not fz.get("available"):
                return None
            fdir = fz.get("direction")                       # long / short / neutral
            conf = abs(float(fz.get("confluence") or 0.0))   # 0..1 conviction
            if fdir in ("long", "short") and isinstance(brain, dict) \
                    and brain.get("confidence") is not None:
                agree = (fdir == "long" and act == "LONG") or (fdir == "short" and act == "SHORT")
                factor = 1.0 + (0.25 if agree else -0.25) * min(1.0, conf)
                brain["confidence"] = float(min(1.0, max(0.0, float(brain["confidence"]) * factor)))
                brain["fusion_agree"] = agree
            brain["fusion_dir"] = fdir
            brain["fusion_p_up"] = fz.get("p_up")
            brain["fusion_confluence"] = fz.get("confluence")
            return fz
        except Exception:
            return None

    def _exit_context(self, pair: str) -> tuple:
        """(atr_pct, regime) for `pair` from its entry decision snapshot — fusion.barriers.atr as
        a % of entry price + fusion.regime. Cheap (reads the cached sidecar); ('',None) on miss."""
        try:
            from trading.crypto.freqtrade import entry_meta
            for seg in (self.segment or "futures", "futures", "spot"):
                row = entry_meta.lookup(pair, seg)
                if not row:
                    continue
                ds = ((row or {}).get("meta") or {}).get("decision_snapshot") or {}
                fz = (ds.get("app_signals") or {}).get("indicator_fusion") or {}
                bar = fz.get("barriers") or {}
                atr, entry = bar.get("atr"), bar.get("entry")
                atr_pct = (float(atr) / float(entry) * 100.0) if (atr and entry) else None
                return atr_pct, fz.get("regime") or ""
        except Exception:
            pass
        return None, ""

    def _too_young_to_exit(self, cli, sym: str) -> bool:
        """True if the open trade `sym` is younger than EXIT_MIN_HOLD_S (default 600s) — so a
        noisy same-cycle ensemble flip can't force-exit a just-opened trade before its thesis
        develops. Stoploss + tailgate still act regardless. Best-effort; never blocks on error."""
        try:
            hold_s = float(os.environ.get("EXIT_MIN_HOLD_S", "600") or 600)
        except ValueError:
            hold_s = 600.0
        if hold_s <= 0:
            return False
        try:
            import datetime as _dt
            for t in (cli.status() or []):
                if isinstance(t, dict) and (t.get("pair") == sym):
                    od = t.get("open_date")
                    if not od:
                        return False
                    o = _dt.datetime.fromisoformat(str(od).replace("Z", "").split("+")[0])
                    age = (_dt.datetime.utcnow() - o).total_seconds()
                    return 0 <= age < hold_s
        except Exception:
            return False
        return False

    def _stack_features(self, sym: str) -> dict:
        """Full stacking feature vector for `sym`: the indicator_fusion lenses + the CORTEX ensemble
        signal. Shared by the meta-gate (predict) and the entry truth-claim (train) so there is no
        train/serve skew — the model sees the same features it learns from. Never raises."""
        try:
            from trading.direction import meta_labeler as _mlx
            esig = (getattr(self, "extra_signals", {}) or {}).get(sym, {})
            fz = esig.get("indicator_fusion")
            cx = (getattr(self, "_cortex_sigs", {}) or {}).get(sym)
            sl = esig.get("strategy_library")           # the 239-strategy ensemble lens
            return {**_mlx.lens_features(fz), **_mlx.cortex_features(cx),
                    **_mlx.strategy_features(sl)}
        except Exception:
            return {}

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
            try:                                      # E6: every OPEN position keeps priority
                from trading.broker_sense.binance_stream import get_mirror   # depth coverage
                get_mirror().request_depth(
                    [t.get("pair") for t in trades if isinstance(t, dict) and t.get("pair")])
            except Exception:
                pass
            try:                                      # E7: grade realized fills vs the logged
                from trading.execution import exec_choice as _xc   # decision-time mid
                _xc.grade_fills(trades)
            except Exception:
                pass
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
                # ATR% + regime for the scaled arm/trail (ideas ①/②) — read from the trade's
                # OWN entry decision snapshot (fusion.barriers.atr + fusion.regime), so no
                # per-poll recompute. Best-effort; None → the tailgate uses its fixed defaults.
                _atr_pct, _regime = self._exit_context(pair)
                # E2 EXIT-POLICY BANDIT (2026-07-17): each trade is managed by ONE Thompson-
                # sampled exit arm (ratchet / direction / ratchet_direction / forecast /
                # va_trail / scale_out) so the exit style is LEARNED per regime instead of a
                # fixed stack. Assignment is lazy (first poll after open) — covers every entry
                # lane without touching the entry paths. EXIT_POLICY=0 restores the old stack.
                _arm = None
                try:
                    from trading.execution import exit_policy as _xp
                    if _xp.enabled():
                        _rec = _xp.assignment(tid)
                        if _rec is None:
                            _hz = None            # X-B: the direction brain's emitted horizon
                            try:                  # travels from the entry sidecar to the exit
                                from trading.crypto.freqtrade import entry_meta as _em
                                _m0 = _em.lookup(pair, self.segment or "futures",
                                                 t.get("open_date"))
                                _hz = ((((_m0 or {}).get("meta") or {}).get("brain") or {})
                                       .get("learned_direction") or {}).get("horizon")
                            except Exception:
                                _hz = None
                            _arm = _xp.assign(tid, regime=_regime,
                                              lane=str(t.get("enter_tag") or ""),
                                              symbol=pair, atr_pct=_atr_pct, horizon=_hz)
                        else:
                            _arm = _rec.get("arm")
                except Exception:
                    _arm = None
                if _arm in ("va_trail", "scale_out"):
                    try:
                        _tp = _xp.evaluate_trail(
                            tid, symbol=pair,
                            direction=("SHORT" if t.get("is_short") else "LONG"),
                            profit_pct=profit_pct,
                            price=_num(t.get("current_rate")) or None)
                        if _tp.get("partial"):
                            cli.close_partial(pair, _tp["partial"], segment=self.segment)
                            from trading.brain import mind_events
                            mind_events.emit("trade_credit",
                                             f"Scale-out took {_tp['partial']:.0%} off {pair}: "
                                             f"{_tp.get('reason')}", salience=0.55)
                        if _tp.get("exit"):
                            cli.close_pair(pair, segment=self.segment)
                            exited.append(pair)
                            pt.clear_lock(tid)
                            from trading.brain import mind_events
                            mind_events.emit("trade_credit",
                                             f"Exit-policy {_arm} closed {pair}: "
                                             f"{_tp.get('reason')}", salience=0.6)
                            continue
                    except Exception:
                        pass
                if _arm == "early_abort":
                    # E6b arm: cut the trade the moment price runs XP_ABORT_BPS against
                    # entry (losers run 202bps median, winners bounce at 35bps —
                    # experiments-20260717). Survivors fall through to the normal ratchet.
                    try:
                        _ab = _xp.evaluate_abort(
                            tid, direction=("SHORT" if t.get("is_short") else "LONG"),
                            open_rate=_num(t.get("open_rate")) or None,
                            price=_num(t.get("current_rate")) or None)
                        if _ab.get("exit"):
                            cli.close_pair(pair, segment=self.segment)
                            exited.append(pair)
                            pt.clear_lock(tid)
                            from trading.brain import mind_events
                            mind_events.emit("trade_debit",
                                             f"Exit-policy early_abort cut {pair}: "
                                             f"{_ab.get('reason')}", salience=0.6)
                            continue
                    except Exception:
                        pass
                if _arm is not None and _arm not in ("ratchet", "ratchet_direction",
                                                     "early_abort"):
                    dec = {"exit": False}          # this trade's arm doesn't ratchet
                else:
                    dec = pt.locked_profit("crypto", self.segment or "futures", trade_id=tid,
                                           profit_pct=profit_pct, peak_profit_pct=peak_pct,
                                           regime=_regime, atr_pct=_atr_pct)
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
                    continue                          # already exiting → skip dir-exit
                # D-EXIT (Pillar 27): the tailgate only manages WINNERS (arms on +profit).
                # A trade that went straight underwater never arms it and just bleeds while
                # its direction thesis is dead. The Truth Ledger proved this leak (entry
                # direction 54-69% right at 1h, ~33% by exit). Cut when the CALIBRATED
                # direction read has flipped against the position. Shadow by default —
                # records a "dir_exit" claim + advisory, acts only under DIR_EXIT=trade.
                try:
                    from trading.direction import dir_exit
                    if _arm is not None and _arm not in ("direction", "ratchet_direction"):
                        raise StopIteration        # this trade's arm doesn't direction-cut
                    de = dir_exit.evaluate(
                        symbol=pair, direction=("SHORT" if t.get("is_short") else "LONG"),
                        market="CRYPTO", segment=self.segment or "futures",
                        ref_price=_num(t.get("current_rate")) or _num(t.get("open_rate")) or None,
                        trade_id=tid)
                    if de.get("exit"):
                        cli.close_pair(pair, segment=self.segment)
                        exited.append(pair)
                        pt.clear_lock(tid)
                        from trading.brain import mind_events
                        mind_events.emit("trade_debit",
                                         f"Direction-exit cut {pair}: {de.get('reason')}",
                                         salience=0.55)
                        continue
                except Exception:
                    pass
                # SMART EXIT (owner 2026-07-14): forward-looking exit — the Symbol-Move Net now
                # forecasts the symbol moving AGAINST the open side (p_up crossed its band AND
                # expected_move_pct is a real move the wrong way). This adds a MAGNITUDE forecast
                # that dir_exit (direction-only) and the ensemble-flip lack, before the stop is hit.
                # Shadow by default (records a mind advisory); SMART_EXIT=trade acts. Respects
                # min-hold so it never cuts a just-opened trade.
                try:
                    if not self._too_young_to_exit(cli, pair) and _arm in (None, "forecast"):
                        from trading.crypto.freqtrade import smart_exit as _sx
                        _se = _sx.should_exit(
                            pair, ("SHORT" if t.get("is_short") else "LONG"),
                            market="CRYPTO", segment=self.segment or "futures", regime=_regime)
                        if _se.get("exit"):
                            from trading.brain import mind_events as _me
                            # the 'forecast' ARM acts (its assignment IS the authorization —
                            # paper is the experiment); unassigned trades keep the old
                            # SMART_EXIT env gate.
                            if _arm == "forecast" or os.environ.get("SMART_EXIT") == "trade":
                                cli.close_pair(pair, segment=self.segment)
                                exited.append(pair)
                                pt.clear_lock(tid)
                                _me.emit("trade_debit",
                                         f"Smart-exit cut {pair}: {_se.get('reason')}", salience=0.55)
                                continue
                            _me.emit("thought",            # shadow: advisory only
                                     f"Smart-exit WOULD cut {pair}: {_se.get('reason')} "
                                     f"(shadow; set SMART_EXIT=trade to act)", salience=0.35)
                except Exception:
                    pass
                # VISION-READ EXIT (idea ③, motto-native): the local VLM's read of the REAL app
                # chart argues to close (flipped against us / reversal pattern). Respects the
                # min-hold so it can't cut a just-opened trade. Shadow by default (logs an
                # advisory); VISION_EXIT=trade acts. CPU = the brain's eyes reading the web chart.
                try:
                    if not self._too_young_to_exit(cli, pair):
                        from trading.broker_sense import vision_worker as _vw
                        vx = _vw.vision_exit_signal(
                            pair, "SHORT" if t.get("is_short") else "LONG")
                        if vx.get("exit"):
                            from trading.brain import mind_events
                            if os.environ.get("VISION_EXIT", "shadow") == "trade":
                                cli.close_pair(pair, segment=self.segment)
                                exited.append(pair)
                                pt.clear_lock(tid)
                                mind_events.emit("trade_debit",
                                                 f"Vision-exit cut {pair}: {vx.get('reason')}",
                                                 salience=0.55)
                            else:
                                mind_events.emit("vision_exit_shadow",
                                                 f"Vision-exit (shadow) would cut {pair}: "
                                                 f"{vx.get('reason')}", salience=0.35)
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
            # BEST-FIT STRATEGY (2026-07-13): the per-coin tournament's top library / created /
            # evolved / researched strategy for THIS coin, read O(1) from the strategy_table producer
            # (the tournament itself NEVER runs in the entry path). Attribution is ON for every lane,
            # so the Strategy column shows a real strategy even when a generic driver
            # (learned_direction / explore / filter:*) opened the trade. Pure learning — it records
            # what the tournament thinks; it changes no entry decision here (that is the gated synergy).
            try:
                from trading.crypto.freqtrade import strategy_table as _stab
                _bf = _stab.lookup(sym)
                if _bf and _bf.get("best_strategy"):
                    snapshot["best_fit"] = {
                        "strategy": _bf.get("best_strategy"),
                        "score": _bf.get("score"),
                        "signal": _bf.get("signal"),
                        "cleared_gate": bool(_bf.get("cleared_gate")),
                        "agrees": (_bf.get("signal") == act) if act in ("LONG", "SHORT") else None,
                        "is_driver": str(tag or "") == str(_bf.get("best_strategy")),
                    }
            except Exception:
                pass
            if self.extra_signals.get(sym):
                snapshot["app_signals"] = self.extra_signals[sym]
            # RAM market context (owner 2026-07-13): capture EVERY filter/screener signal we have for
            # this symbol from RAM (app_signals: momentum/funding/taker/book_imbalance/longshort/
            # oi_trend/liquidations/pcr) + the mirror's 24h volume/high/low/%change/trade-count — so
            # the trade carries the FULL RAM signal set, the post-mortem miner can mine patterns over
            # ALL filters, and NO value came from an API. Best-effort, RAM-only; never blocks entry.
            try:
                from trading.broker_sense.binance_stream import get_mirror
                from trading.direction import app_signals as _asig
                _col = _asig.collect(sym, market="crypto")
                _tk = get_mirror().ticker(sym) or {}
                snapshot["market_context"] = {
                    "filters": {s: round(float(p), 4) for s, p in (_col.get("signals") or [])},
                    "coverage": _col.get("coverage"),
                    "quote_volume_24h": _tk.get("quote_volume"),
                    "pct_change_24h": _tk.get("pct_change"),
                    "high_24h": _tk.get("high"), "low_24h": _tk.get("low"),
                    "trade_count_24h": _tk.get("count"),
                    "source": "ram",
                }
            except Exception:
                pass
            # decision-memory episode + SHAP attribution (resolved at ingest time when
            # the trade closes; episode_id travels via this sidecar)
            episode_id, attribution = "", {}
            try:
                from trading.brain.attribution import explain_trade
                from trading.brain.decision_memory import get_memory
                closed = _closed_tail(200)
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
                                taken=True,
                                features=self._stack_features(sym))   # aligned stacking signal
        except Exception:
            pass
