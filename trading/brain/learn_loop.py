"""trading/brain/learn_loop.py — CONTINUOUS autonomous learning loop.

Glue over existing, already-integrated OSS components (no new deps):
  • trading/brain/learner.py  — learn_topic (arXiv pypdf + ddgs/trafilatura articles)
  • memory/self_quiz.py       — FSRS mastery self-evaluation (via learner.self_evaluate)
  • trading/brain/activity_feed.py — ephemeral "what I'm doing" events for the panel

Every `interval` seconds it picks ONE topic — operator queue first, then retry topics
whose last attempt errored, then a rotating trading curriculum — learns it (2 papers +
2 articles into the persistent KnowledgeBrain), and every `eval_every` cycles quizzes
itself on the recent topics so the mastery curve stays honest. State (enabled flag,
queue, history) persists in trading/state/learn_loop.json, so the loop resumes across
restarts. Start/stop/queue via /api/brain/learn (op=loop_on|loop_off|queue).
"""
from __future__ import annotations

import os
import threading
import time

_STATE_FILE = "learn_loop.json"

# Rotating default curriculum — trading-first, but broad (the brain learns generally).
CURRICULUM = [
    "market microstructure", "order flow imbalance trading", "volatility modeling GARCH",
    "options greeks hedging", "stochastic calculus for finance", "kelly criterion position sizing",
    "market regime detection hidden markov", "statistical arbitrage pairs trading",
    "market making inventory risk", "reinforcement learning for trading",
    "portfolio optimization risk parity", "limit order book dynamics",
    "momentum and mean reversion strategies", "risk management drawdown control",
    "commodity futures term structure", "crypto perpetual funding rate strategies",
]


class LearnLoop:
    """Background continuous-learning driver. Honest: every cycle is journaled and
    surfaced in the activity feed; failures are recorded, never swallowed."""

    def __init__(self, learner=None, interval: float | None = None, eval_every: int = 5):
        self._learner = learner
        self.interval = float(interval if interval is not None
                              else os.environ.get("BRAIN_LEARN_INTERVAL_SEC", 1800))
        self.eval_every = int(eval_every)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # ── deps (lazy) ───────────────────────────────────────────────────────────
    def learner(self):
        if self._learner is None:
            from trading.brain.learner import get_learner
            self._learner = get_learner()
        return self._learner

    # ── persisted state ───────────────────────────────────────────────────────
    def _load(self) -> dict:
        from trading import state
        return state.load_json(_STATE_FILE, {"enabled": False, "queue": [], "done": [],
                                             "cycles": 0, "last": None, "errors": []})

    def _save(self, st: dict) -> None:
        from trading import state
        st["done"] = st.get("done", [])[-100:]
        st["errors"] = st.get("errors", [])[-40:]
        state.save_json(_STATE_FILE, st)

    # ── controls ─────────────────────────────────────────────────────────────
    def enable(self, on: bool = True) -> dict:
        st = self._load()
        st["enabled"] = bool(on)
        self._save(st)
        if on:
            self.start()
        else:
            self.stop()
        return self.status()

    def queue_topic(self, topic: str) -> dict:
        topic = str(topic or "").strip()
        st = self._load()
        if topic and topic not in st["queue"]:
            st["queue"].append(topic)
            self._save(st)
        return self.status()

    # ── topic selection: queue → erroring retries → curriculum rotation ──────
    def pick_topic(self, st: dict) -> str:
        if st.get("queue"):
            return st["queue"][0]
        for e in reversed(st.get("errors", [])):        # retry the most recent failure once
            t = e.get("topic")
            if t and t not in [d.get("topic") for d in st.get("done", [])[-10:]]:
                return t
        recent = {d.get("topic") for d in st.get("done", [])[-len(CURRICULUM) + 1:]}
        for t in CURRICULUM:
            if t not in recent:
                return t
        return CURRICULUM[st.get("cycles", 0) % len(CURRICULUM)]

    # ── one learning cycle (also used directly by tests) ─────────────────────
    def run_once(self) -> dict:
        from trading.brain import activity_feed as feed
        st = self._load()
        topic = self.pick_topic(st)
        if topic in st.get("queue", []):
            st["queue"].remove(topic)
        out = {}
        try:
            out = self.learner().learn_topic(topic, papers=2, articles=2)
        except Exception as e:                           # loop must survive any cycle
            out = {"topic": topic, "n": 0, "errors": [f"{type(e).__name__}: {e}"[:120]]}
        st["cycles"] = int(st.get("cycles", 0)) + 1
        # self-healing wiring watchdog: piggyback a cheap connectivity scan each learn cycle so a
        # newly-disconnected module/endpoint is caught automatically (emits a mind-event on regress)
        try:
            from trading.brain import connectivity_monitor
            connectivity_monitor.scan()
        except Exception:
            pass
        rec = {"topic": topic, "n": out.get("n", 0), "ts": time.time()}
        st["done"].append(rec)
        st["last"] = rec
        if out.get("errors"):
            st["errors"].append({"topic": topic, "errors": out["errors"], "ts": time.time()})
        # periodic self-evaluation on what was recently studied (FSRS mastery curve)
        if st["cycles"] % self.eval_every == 0:
            try:
                topics = [d["topic"] for d in st["done"][-self.eval_every:]]
                ev = self.learner().self_evaluate(topics)
                st["last_eval"] = {"ts": time.time(),
                                   "final_retention": ev.get("final_retention"),
                                   "rising": ev.get("rising")}
                feed.emit("learned", "Self-evaluation (FSRS quiz)",
                          learned=f"retention={ev.get('final_retention')} rising={ev.get('rising')}")
            except Exception:
                pass
        # Pillar 17: nightly-grade conformal recalibration (time-gated to every 6h
        # inside maybe_recalibrate — the loop runs each 30m cycle, the refit doesn't).
        try:
            from trading.uq import get_uq
            uq_sum = get_uq().maybe_recalibrate(max_age_h=6.0)
            if uq_sum:
                st["last_uq"] = {"ts": uq_sum.get("ts"), "engine": uq_sum.get("engine"),
                                 "coverage_aci": uq_sum.get("coverage_holdout_aci"),
                                 "ece_p_up": uq_sum.get("ece_p_up"),
                                 "n_trades": uq_sum.get("n_trades")}
                self._save(st)
                feed.emit("learned", "Conformal recalibration (Pillar 17)",
                          learned=f"engine={uq_sum.get('engine')} "
                                  f"coverage={uq_sum.get('coverage_holdout_aci')} "
                                  f"ECE={uq_sum.get('ece_p_up')}")
        except Exception:
            pass
        self._save(st)
        return {"topic": topic, "ingested": out.get("n", 0), "cycle": st["cycles"],
                "errors": out.get("errors", [])}

    # ── thread lifecycle ──────────────────────────────────────────────────────
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()

        def _run():
            while not self._stop.is_set():
                if self._load().get("enabled"):
                    try:
                        self.run_once()
                    except Exception:
                        pass                             # never let the loop die
                self._stop.wait(self.interval)

        self._thread = threading.Thread(target=_run, daemon=True, name="brain-learn-loop")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> dict:
        st = self._load()
        return {"enabled": bool(st.get("enabled")), "running": bool(self._thread and self._thread.is_alive()),
                "interval_sec": self.interval, "cycles": st.get("cycles", 0),
                "queue": st.get("queue", []), "last": st.get("last"),
                "last_eval": st.get("last_eval"), "recent_errors": st.get("errors", [])[-3:],
                "curriculum_size": len(CURRICULUM)}


_LOOP: LearnLoop | None = None


def get_learn_loop() -> LearnLoop:
    global _LOOP
    if _LOOP is None:
        _LOOP = LearnLoop()
    return _LOOP


def ensure_started() -> None:
    """Start the loop thread if the persisted flag (or BRAIN_LEARN_LOOP=1) says so —
    called once at dashboard boot so continuous learning resumes across restarts."""
    lp = get_learn_loop()
    if os.environ.get("BRAIN_LEARN_LOOP") == "1":
        lp.enable(True)
    elif lp._load().get("enabled"):
        lp.start()
