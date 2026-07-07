"""trading/crypto/freqtrade/brain_learning.py — the brain's CLOSED LEARNING LOOP.

The trade-execution loop (BrainExecutor) makes decisions; this runs the AI-scientist side
ALONGSIDE it, interval-gated and fully off the critical path (every call is guarded — it can
never break execution). Each cycle:

  • LEARN     — HypothesisLedger.run_cycle() over the REAL closed-trade journal: propose →
                Bayesian-test → confirm/refute → persist (trading/state/hypotheses.json).
  • RESEARCH  — AutonomousResearcher.research_symbol() per top symbol: live ddgs web search →
                LLM synthesis (core/llm failover chain) → a finance brief, persisted to
                trading/state/research_findings.json.  (SEARCH ONLINE + UNDERSTAND)
  • IMAGINE   — ImaginationPlanner rolls the learned world-model forward (MuZero MCTS) on a
                top symbol's live OHLCV to sanity-check direction in imagined R.

`support(context)` exposes the confirmed-hypothesis bias so the executor can let evidence
FEED BACK into entries (advisory veto on strong contrary evidence) — closing the loop:
learn → research → understand → act → learn.
"""
from __future__ import annotations

import os
import time


class BrainLearningCycle:
    """Runs the brain's learn/research/imagine cycle on an interval; holds the ledger so its
    confirmed hypotheses can bias live entries. All steps are best-effort and never raise."""

    FINDINGS_FILE = "research_findings.json"

    def __init__(self, *, interval_sec: float | None = None, research_top: int = 3):
        self.interval = float(interval_sec if interval_sec is not None
                              else os.environ.get("BRAIN_LEARN_SEC", "900"))
        self.research_top = int(os.environ.get("BRAIN_RESEARCH_TOP", str(research_top)))
        self._last_run = 0.0
        self._ledger = None            # lazy (imports numpy/scipy)
        self._researcher = None
        self._foundry = None
        self.last_summary: dict = {}

    def foundry(self):
        if self._foundry is None:
            from trading.strategy.foundry import StrategyFoundry
            self._foundry = StrategyFoundry(persist=True)
        return self._foundry

    # ── lazy components ──────────────────────────────────────────────────────────
    def ledger(self):
        if self._ledger is None:
            from trading.brain.hypothesis import HypothesisLedger
            self._ledger = HypothesisLedger(persist=True)
        return self._ledger

    def researcher(self):
        if self._researcher is None:
            from trading.brain.researcher import AutonomousResearcher
            self._researcher = AutonomousResearcher()
        return self._researcher

    def _trades(self) -> list[dict]:
        """The REAL closed-trade journal (rich 110-col rows the ledger reasons over)."""
        try:
            from trading.journal.journal import TradeJournal
            jr = TradeJournal(state_file="journal.json", persist=True)
            return [t.to_dict() for t in jr.trades]
        except Exception:
            return []

    # ── decision feedback ────────────────────────────────────────────────────────
    def support(self, context: dict) -> dict:
        """Confirmed-hypothesis bias in [-1,1] for a trade context (advisory). {} on failure."""
        try:
            return self.ledger().support(context)
        except Exception:
            return {"bias": 0.0, "n": 0, "statements": []}

    # ── the cycle ─────────────────────────────────────────────────────────────────
    def maybe_run(self, symbols: list | None = None) -> dict | None:
        """Interval-gated. Returns a summary dict when it ran this call, else None."""
        now = time.monotonic()
        if (now - self._last_run) < self.interval:
            return None
        self._last_run = now
        return self._run(symbols or [])

    def _run(self, symbols: list) -> dict:
        summary: dict = {"learned": None, "research": [], "imagined": None,
                         "foundry": None, "evolved": None}
        trades = self._trades()

        # 0) GOAL SCOREBOARD (W1, owner goal 2026-07-07) — refresh the trailing-30d
        #    per-segment verdicts BEFORE learning so every downstream step (hypotheses,
        #    foundry, evolution) sees where we stand vs goal.yaml. "No vibes, just numbers."
        try:
            from trading import goal
            sb = goal.scoreboard()
            summary["goal"] = {k: v.get("verdict")
                               for k, v in (sb.get("segments") or {}).items()}
        except Exception as e:
            summary["goal"] = {"error": f"{type(e).__name__}: {e}"[:120]}

        # 1) LEARN — hypothesis ledger over real outcomes
        try:
            summary["learned"] = self.ledger().run_cycle(trades)
        except Exception as e:
            summary["learned"] = {"error": f"{type(e).__name__}: {e}"[:160]}

        # 2) RESEARCH — live web search + LLM synthesis per top symbol
        briefs = []
        for sym in list(symbols)[: self.research_top]:
            try:
                r = self.researcher().research_symbol(str(sym).split(":")[0], market="crypto")
                briefs.append({"symbol": sym, "n_sources": r.get("n_sources", 0),
                               "llm_used": r.get("llm_used", False),
                               "summary": (r.get("summary") or "")[:2000],
                               "sources": r.get("sources", [])[:6]})
            except Exception as e:
                briefs.append({"symbol": sym, "error": f"{type(e).__name__}: {e}"[:160]})
        summary["research"] = [{"symbol": b["symbol"], "n_sources": b.get("n_sources", 0),
                                "llm_used": b.get("llm_used", False)} for b in briefs]
        self._persist_findings(briefs)

        # 3) IMAGINE — world-model MCTS rollout on a top symbol (sanity-check direction)
        try:
            import dashboard.brain_live as _bl  # reuse the cached ccxt OHLCV fetch
            from trading.brain.worldmodel import build_planner
            top = (str(symbols[0]).split(":")[0] if symbols else "BTC/USDT")
            ohlcv = _bl._real_ohlcv(top, "5m", 200)
            plan = build_planner(ohlcv, num_simulations=48, horizon=10).plan(ohlcv)
            summary["imagined"] = {"symbol": top, "action": plan.get("action"),
                                   "expected_R": plan.get("expected_R"),
                                   "backend": plan.get("backend")}
        except Exception as e:
            summary["imagined"] = {"error": f"{type(e).__name__}: {e}"[:160]}

        # 4) STRATEGY FOUNDRY — discover new ultra-advanced strategies online + backtest/track
        #    the executable ones (unique id → performance ledger → keep-the-best).
        try:
            fdry = self.foundry()
            discovered = 0
            for seg in ("crypto_futures", "nse_futures", "nse_options"):
                discovered += len(fdry.research_segment(seg))
            import dashboard.brain_live as _bl
            ohlcv = {}
            for sym in list(symbols)[: self.research_top]:
                base = str(sym).split(":")[0]
                try:
                    ohlcv[base] = _bl._real_ohlcv(base, "5m", 400)
                except Exception:
                    pass
            from trading.strategy.foundry_strategies import (
                backtest_and_track, funding_rate_arb_eval, statarb_pairs_eval)
            tracked = backtest_and_track(fdry, ohlcv) if ohlcv else []
            # advanced data-backed strategies on real data (ccxt funding + cointegration)
            fr = funding_rate_arb_eval(fdry, [str(s) for s in symbols[:12]])
            pairs = statarb_pairs_eval(fdry, {k: v["close"] for k, v in ohlcv.items()
                                              if v is not None and "close" in v}) if ohlcv else []
            # advanced real-data families (L2 microstructure, arb, Deribit options greeks)
            try:
                from trading.strategy.foundry_advanced import run_all_advanced
                adv = run_all_advanced(fdry)
            except Exception:
                adv = {}
            fdry.promote(keep=5)
            summary["foundry"] = {"discovered": discovered,
                                  "tracked": len(tracked) + (1 if fr else 0) + (1 if pairs else 0)
                                  + sum(1 for v in adv.values() if v),
                                  "funding": bool(fr), "pairs": len(pairs),
                                  "advanced": {k: v for k, v in adv.items() if v},
                                  "n_specs": len(fdry.specs)}
        except Exception as e:
            summary["foundry"] = {"error": f"{type(e).__name__}: {e}"[:160]}

        # 6) SELF-EVOLVE — the genetic CREATION/MUTATION engine (DEAP NSGA-II) breeds new
        #    strategies on real OHLCV, admits guardrail-passed survivors into the persisted
        #    SkillLibrary, and retires stale ones. Gate-aware (trading.strategy.control): a
        #    clean {"gated": True} when disabled. The best survivor is what the brain pipeline
        #    picks up via trading.strategy.evolved_link.attach_to_pipeline — closing the loop
        #    create → breed → admit → the brain trades it.
        try:
            from trading.strategy.evolved_link import breed
            evo_ohlcv = {}
            import dashboard.brain_live as _bl
            base = (str(symbols[0]).split(":")[0] if symbols else "BTC/USDT")
            try:
                evo_ohlcv["CRYPTO"] = _bl._real_ohlcv(base, "5m", 400)
            except Exception:
                pass
            summary["evolved"] = breed(evo_ohlcv, hypotheses=self.ledger()) if evo_ohlcv \
                else {"ran": False, "reason": "no OHLCV"}
        except Exception as e:
            summary["evolved"] = {"error": f"{type(e).__name__}: {e}"[:160]}

        # 5) AUTONOMOUS WEB (opt-in via WEB_SCREEN=1): browse open web read-only to fill a
        #    knowledge gap — one gap-browse per cycle, emits to the ephemeral feed. Off by
        #    default so it never overloads the loop with browser launches.
        if os.environ.get("WEB_SCREEN", "") in ("1", "true", "TRUE", "yes"):
            try:
                from trading.brain.gui.web_screener import get_screener
                topic = (summary.get("research") or [{}])[0].get("symbol") or "market microstructure"
                g = get_screener().google_gap(f"{topic} trading strategy explained", max_sites=1)
                summary["web"] = {"query_ok": bool(g.get("available")),
                                  "screened": len(g.get("screened") or [])}
            except Exception as e:
                summary["web"] = {"error": f"{type(e).__name__}: {e}"[:120]}

        self.last_summary = summary
        return summary

    def _persist_findings(self, briefs: list) -> None:
        """Write the research briefs to trading/state so the dashboard/brain can read them."""
        try:
            from trading import state
            state.save_json(self.FINDINGS_FILE, {"updated_at": time.time(), "briefs": briefs})
        except Exception:
            pass
