"""trading/brain/pipeline.py — end-to-end brain trading pipeline (T8.9 finale).

Stitches every T8 capability into ONE traced, safety-gated decision per market:

  features (T8.1) → regime (T8.6) → pattern/anomaly (T8.6) → news sentiment (T8.7)
    → evolved-strategy signal (T8.1-3) → experience recall bias (T8.4)
    → regime/anomaly-gated entry decision (T8.6) → safety gate (T3 kill-switch + breaker)

Every step is recorded by the BrainTracer (T8.8) → Stream-of-Mind, and the final action
is BLOCKED to FLAT if the kill-switch is engaged or the daily circuit breaker has tripped.
All components are INJECTED, so the pipeline is offline-testable and drives both the NSE
and Crypto markets from the same code. Paper-first: it only emits a decision; the T3
execution engine (guarded, paper unless explicitly live) places orders downstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from trading.brain.entryexit import EntryExitPolicy
from trading.brain.experience import ExperienceBank
from trading.brain.news import NewsResearcher, NewsSentimentNode
from trading.brain.observability import BrainTracer
from trading.brain.patterns import PatternScanner
from trading.brain.hypothesis import HypothesisLedger
from trading.brain.regime import RegimeModel
from trading.brain.worldmodel import ImaginationPlanner
from trading.strategy.features import compute_features


@dataclass
class BrainTradingPipeline:
    """One market's brain: composes the T8 stack into a single safety-gated decision."""

    market: str = "CRYPTO"
    evolved_strategy: object = None                 # a Strategy (T8.1-3), optional
    regime_model: RegimeModel | None = None
    pattern_scanner: PatternScanner = field(default_factory=PatternScanner)
    news: NewsResearcher | None = None
    experience: ExperienceBank | None = None
    entryexit: EntryExitPolicy | None = None
    tracer: BrainTracer | None = None
    planner: ImaginationPlanner | None = None       # world-model imagination, optional
    hypotheses: HypothesisLedger | None = None      # confirmed-hypothesis support, optional
    kill_switch: object = None                      # T3 KillSwitch, optional
    breaker: object = None                          # T3 DailyCircuitBreaker, optional

    def __post_init__(self) -> None:
        self.entryexit = self.entryexit or EntryExitPolicy()
        self.tracer = self.tracer or BrainTracer()

    def _safety_blocked(self) -> tuple[bool, str]:
        if self.kill_switch is not None and getattr(self.kill_switch, "engaged", False):
            return True, "kill-switch engaged"
        if self.breaker is not None and not self.breaker.allow_new_order():
            return True, f"circuit breaker tripped ({getattr(self.breaker, 'trip_reason', '')})"
        return False, ""

    def decide(self, symbol: str, ohlcv: pd.DataFrame, *, universe=None,
               news_items=None, position_side: str | None = None) -> dict:
        """Run the full T8 stack for `symbol` → one traced, safety-gated decision.

        `position_side` (LONG/SHORT) switches to EXIT-management: the entry/exit policy's
        should_exit fires on signal-reversal / regime-change / anomaly / kill-switch.
        """
        tr = self.tracer
        feats = compute_features(ohlcv)

        # 1) regime
        regime = (self.regime_model.current_regime(ohlcv)
                  if self.regime_model is not None else "neutral")
        tr.record("regime", outputs={"regime": regime})

        # 2) pattern / anomaly
        scan = self.pattern_scanner.scan(ohlcv)
        anomaly = scan["anomaly_score"]
        tr.record("pattern_scan", outputs={"anomaly_score": anomaly,
                                           "anomalies": len(scan["anomalies"])})

        # 3) news sentiment
        news_compound = 0.0
        if self.news is not None:
            res = self.news.research(symbol, items=news_items)
            news_compound = res["avg_compound"]
            tr.record("news_sentiment", outputs={"avg_compound": news_compound,
                                                 "label": res["label"]})
        news_p = NewsSentimentNode().predict_proba([[news_compound]])[0]

        # 4) evolved-strategy signal
        signal = 0
        if self.evolved_strategy is not None:
            sig = self.evolved_strategy.signal(feats)
            signal = int(sig.iloc[-1]) if len(sig) else 0
        tr.record("strategy_signal", outputs={"signal": signal})

        # 5) experience recall bias
        recall_bias = 0.0
        recall_conf = 0.0
        if self.experience is not None:
            q = {"market": self.market, "symbol": symbol,
                 "direction": "LONG" if signal > 0 else ("SHORT" if signal < 0 else ""),
                 "india_vix_entry": 0.0}
            rc = self.experience.recall(q, k=10)
            recall_bias, recall_conf = rc.bias, rc.confidence
            tr.record("experience_recall", outputs={"bias": recall_bias, "n": rc.n})

        # 5.5) imagination — roll the learned world-model forward (MuZero MCTS) to
        #      test entry/direction/stop/trailing in imagined R BEFORE acting. Advisory:
        #      it is recorded + surfaced and lightly nudges confidence; it never overrides
        #      the safety gate or the entry/exit policy.
        imagination = None
        if self.planner is not None:
            try:
                imagination = self.planner.plan(ohlcv, position_side=position_side)
                tr.record("imagination", outputs={"action": imagination["action"],
                                                  "expected_R": imagination["expected_R"],
                                                  "backend": imagination["backend"]})
            except Exception as e:                       # never let imagination break a decision
                tr.record("imagination", outputs={"error": str(e)[:120]})

        # 5.6) confirmed-hypothesis support — does the brain's evidence-backed research
        #      (HypothesisLedger) endorse this regime/direction? Advisory: recorded +
        #      lightly nudges confidence; never overrides safety or entry/exit.
        hypothesis_support = None
        if self.hypotheses is not None:
            try:
                ctx = {"market": self.market, "symbol": symbol,
                       "market_regime_entry": regime,
                       "direction": "LONG" if signal > 0 else ("SHORT" if signal < 0 else "")}
                hypothesis_support = self.hypotheses.support(ctx)
                tr.record("hypothesis_support", outputs={"bias": hypothesis_support["bias"],
                                                         "n": hypothesis_support["n"]})
            except Exception as e:
                tr.record("hypothesis_support", outputs={"error": str(e)[:120]})

        # 6) safety gate (T3) — blocks both entries and (forces) exits
        blocked, reason = self._safety_blocked()

        # 7) decide: EXIT-management when a position is open, else ENTRY
        if position_side:
            if blocked:
                gate = {"exit": True, "reason": reason}
            else:
                gate = self.entryexit.should_exit(position_side=position_side, signal=signal,
                                                  regime=regime, anomaly_score=anomaly)
            action = "EXIT" if gate.get("exit") else "HOLD"
            entry = gate
        else:
            entry = self.entryexit.should_enter(signal=signal, regime=regime,
                                                anomaly_score=anomaly)
            if blocked:
                action = "FLAT"
                entry = {"enter": False, "reason": reason}
            else:
                action = entry.get("side", "FLAT") if entry.get("enter") else "FLAT"

        # blended confidence in the ACTION (0..1): conviction by signal STRENGTH (symmetric
        # long/short) + news & recall support ALIGNED to the action's direction.
        direction = 1 if signal > 0 else (-1 if signal < 0 else 0)
        conviction = 0.7 if direction != 0 else 0.5
        news_support = news_p if direction > 0 else ((1.0 - news_p) if direction < 0 else 0.5)
        recall_support = (0.5 + 0.5 * recall_bias) if direction > 0 else \
            ((0.5 - 0.5 * recall_bias) if direction < 0 else 0.5)
        confidence = round(max(0.0, min(1.0,
                          0.5 * conviction + 0.3 * news_support + 0.2 * recall_support)), 4)

        # imagination nudge: if the world-model agrees with the action direction and
        # imagines positive R, lift confidence slightly; if it imagines negative R, trim it.
        imagined_R = float(imagination["expected_R"]) if imagination else 0.0
        if imagination is not None and action not in ("FLAT", "HOLD"):
            agree = (imagination["action"] in (action, f"ENTER_{action}")) or imagined_R > 0
            confidence = round(max(0.0, min(1.0,
                              confidence + (0.05 if agree and imagined_R > 0 else
                                            -0.05 if imagined_R < 0 else 0.0))), 4)

        # hypothesis nudge: confirmed evidence aligned with the action direction lifts
        # confidence in proportion to its bias (advisory, capped at ±0.05).
        if hypothesis_support is not None and hypothesis_support["n"] and direction != 0:
            confidence = round(max(0.0, min(1.0,
                              confidence + max(-0.05, min(0.05,
                                  0.05 * hypothesis_support["bias"] * direction)))), 4)

        decision = {
            "symbol": symbol, "market": self.market, "regime": regime,
            "position_side": position_side,
            "anomaly_score": anomaly, "news_compound": news_compound, "news_p": round(news_p, 4),
            "signal": signal, "recall_bias": recall_bias, "recall_confidence": recall_conf,
            "entry": entry, "action": action, "confidence": confidence,
            "imagination": imagination,
            "hypothesis_support": hypothesis_support,
            "safety_blocked": blocked, "safety_reason": reason,
        }
        tr.record("decision", outputs={"action": action, "confidence": confidence,
                                       "blocked": blocked})
        return decision

    def safety_review(self) -> dict:
        """Audit the safety posture before any live capital (paper-first guarantees)."""
        checks = []

        def chk(name, ok, detail=""):
            checks.append({"check": name, "ok": bool(ok), "detail": detail})

        chk("kill_switch_present", self.kill_switch is not None,
            "T3 KillSwitch wired" if self.kill_switch else "no kill-switch injected")
        chk("circuit_breaker_present", self.breaker is not None,
            "T3 DailyCircuitBreaker wired" if self.breaker else "no breaker injected")
        blocked, reason = self._safety_blocked()
        chk("not_currently_blocked", not blocked, reason or "clear")
        chk("entry_gating_active", self.entryexit is not None, "regime/anomaly gate on entry")
        chk("tracer_active", self.tracer is not None, f"backend={self.tracer.backend}")
        # `passed` = the safety MACHINERY is wired (structural readiness).
        # `currently_blocked` = a halt is active right now (a SAFE state, machinery working).
        # `safe_to_trade` = machinery ready AND not currently halted — gate go-live on THIS.
        structural = all(c["ok"] for c in checks if c["check"] != "not_currently_blocked")
        return {"market": self.market, "passed": structural,
                "currently_blocked": blocked, "block_reason": reason,
                "safe_to_trade": structural and not blocked, "checks": checks}

    def status(self) -> dict:
        return {
            "market": self.market,
            "has_strategy": self.evolved_strategy is not None,
            "has_regime_model": self.regime_model is not None,
            "has_news": self.news is not None,
            "has_experience": self.experience is not None,
            "has_imagination": self.planner is not None,
            "has_hypotheses": self.hypotheses is not None,
            "safety": self.safety_review(),
            "stream_of_mind": self.tracer.stream_of_mind(10),
        }
