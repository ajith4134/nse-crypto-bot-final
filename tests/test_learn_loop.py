"""Continuous learning loop (trading/brain/learn_loop.py) — deterministic unit tests.

Stubbed learner (no network), isolated STATE_DIR. Verifies: queue-first topic pick,
curriculum rotation without repeats, error recording + retry, periodic self-eval,
enable-flag persistence across instances (restart survival).
Run: pytest tests/test_learn_loop.py
"""
import tempfile
from pathlib import Path

import trading.state as _state

_state.STATE_DIR = Path(tempfile.mkdtemp())  # isolate: never touch live state


class _StubLearner:
    def __init__(self, fail_topics=()):
        self.calls = []
        self.fail = set(fail_topics)

    def learn_topic(self, topic, *, papers=1, articles=1):
        self.calls.append(topic)
        if topic in self.fail:
            return {"topic": topic, "n": 0, "errors": ["web: boom"]}
        return {"topic": topic, "n": 2, "errors": []}

    def self_evaluate(self, topics=None, **kw):
        return {"final_retention": 0.8, "rising": True}


def _fresh_loop(**kw):
    import trading.brain.learn_loop as m
    (_state.STATE_DIR / "learn_loop.json").unlink(missing_ok=True)
    return m.LearnLoop(learner=_StubLearner(**kw), interval=9999, eval_every=3)


def test_queue_topic_learned_first_then_curriculum():
    from trading.brain.learn_loop import CURRICULUM
    lp = _fresh_loop()
    lp.queue_topic("my special topic")
    r1 = lp.run_once()
    assert r1["topic"] == "my special topic" and r1["ingested"] == 2
    r2 = lp.run_once()
    assert r2["topic"] == CURRICULUM[0]          # queue drained → curriculum
    r3 = lp.run_once()
    assert r3["topic"] == CURRICULUM[1]          # rotates, no repeat


def test_errors_recorded_and_status_honest():
    lp = _fresh_loop(fail_topics={"market microstructure"})
    out = lp.run_once()                          # curriculum[0] fails
    assert out["errors"], "failure not surfaced"
    st = lp.status()
    assert st["cycles"] == 1
    assert st["recent_errors"] and st["recent_errors"][-1]["topic"] == "market microstructure"


def test_self_eval_fires_on_schedule():
    lp = _fresh_loop()
    for _ in range(3):                           # eval_every=3
        lp.run_once()
    st = lp.status()
    assert st["last_eval"] and st["last_eval"]["rising"] is True


def test_enabled_flag_persists_across_instances():
    lp = _fresh_loop()
    lp.enable(True)
    lp.stop()
    import trading.brain.learn_loop as m
    lp2 = m.LearnLoop(learner=_StubLearner(), interval=9999)
    assert lp2.status()["enabled"] is True       # restart survival
    lp2.enable(False)
    assert lp2.status()["enabled"] is False
