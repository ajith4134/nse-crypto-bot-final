"""cognition/stream_of_mind.py — Stream-of-Mind + Global Workspace (Phase P4.6).

The brain's live, EPHEMERAL state of mind — and the working-memory → long-term-memory pipeline
behind it. Two real mechanisms, both honestly wired to the brain's actual reasoning loop:

1. ``GlobalWorkspace`` — the missing **selective-attention / consolidation gate** (Global
   Workspace Theory). Each *tick*, candidate thoughts COMPETE for a single limited broadcast
   slot on a **salience** score; only the winner is "broadcast" (the conscious focus), and a
   winner above the consolidation threshold is written to **long-term memory**
   (``KnowledgeBrain.ingest_text``). Salience fuses real signals: Generative-Agents poignancy
   (vendored ``default_importance_fn``), active-inference **surprise**, **curiosity**, and the
   thought's **confidence** — so what survives is genuinely what mattered.

2. ``StreamOfMind`` — wraps a ``Thinker`` and turns one ``think()`` cycle into a STREAM of real
   thought-events (the ReAct/ToT steps, the active-inference surprise/curiosity, the
   confidence/uncertainty, the goal/subgoal, the constitution verdict, and the Global-Workspace
   winner each tick). Each thought carries a salience and a TTL; the dashboard panel fades them
   (~18s) and the salient ones are consolidated to the KnowledgeBrain — a VISIBLE working-memory
   → long-term-memory pipeline. A bounded ring buffer holds the recent thoughts for the panel,
   and ``stream()`` yields NDJSON-ready events for the live ``/api/brain/stream`` endpoint.

Every think cycle is also recorded as a durable **Langfuse** trace (``core.observability``) —
a no-op offline, a replayable thought-history when keys are set. CPU-first, offline-safe,
deterministic with injected stubs (no network, no LLM) — exactly like P4.1–P4.5.
"""
from __future__ import annotations

import itertools
from collections import deque

from core import observability as obs

# default TTL for an ephemeral thought in the panel (ms) — matches StreamOfMind.jsx
_TTL_MS = 18000


def _ga_importance(text: str) -> float:
    """Generative-Agents poignancy in [0,1] (vendored, deterministic, offline)."""
    try:
        from vendor.generative_agents_memory.memory_stream import default_importance_fn
        return max(0.0, min(1.0, default_importance_fn(text) / 10.0))
    except Exception:
        # offline heuristic fallback: longer + cue-bearing thoughts are more salient
        cues = ("surprise", "novel", "alert", "critical", "important", "won", "lost", "risk")
        t = (text or "").lower()
        return min(1.0, 0.2 + 0.1 * sum(c in t for c in cues) + min(len(t) // 120, 2) * 0.1)


class Thought:
    """One ephemeral thought-event in the stream."""

    __slots__ = ("id", "text", "kind", "salience", "ts", "ttl_ms", "consolidated", "meta")

    def __init__(self, tid, text, kind, salience, ts, *, ttl_ms=_TTL_MS, meta=None):
        self.id = tid
        self.text = text
        self.kind = kind                # react | surprise | curiosity | confidence | goal | winner | verdict
        self.salience = round(float(salience), 4)
        self.ts = ts                    # logical tick (deterministic) or wall-clock ms (live)
        self.ttl_ms = ttl_ms
        self.consolidated = False
        self.meta = meta or {}

    def as_dict(self) -> dict:
        return {"id": self.id, "text": self.text, "kind": self.kind,
                "salience": self.salience, "ts": self.ts, "ttl_ms": self.ttl_ms,
                "consolidated": self.consolidated, **({"meta": self.meta} if self.meta else {})}


class GlobalWorkspace:
    """Attention competition: thoughts compete for one broadcast slot; winners consolidate.

    Args:
        brain: a KnowledgeBrain (or None) — salient winners are ingested into it (long-term memory).
        consolidate_threshold: salience ≥ this → the winner is written to long-term memory.
        broadcast_bandwidth: how many top thoughts are "broadcast" per tick (GWT = small; default 1).
    """

    def __init__(self, brain=None, *, consolidate_threshold: float = 0.35,
                 broadcast_bandwidth: int = 1):
        self.brain = brain
        self.consolidate_threshold = float(consolidate_threshold)
        self.broadcast_bandwidth = int(broadcast_bandwidth)
        self.ticks = 0
        self.broadcasts: list[dict] = []     # history of winners (for status/inspection)
        self.consolidated = 0

    @staticmethod
    def salience(text: str, *, surprise: float = 0.0, curiosity: float = 0.0,
                 confidence: float = 0.0) -> float:
        """Fuse the brain's COGNITIVE signals + GA poignancy into one salience in [0,1].

        Reasoning thoughts rarely trip Generative-Agents' life-event poignancy cues, so the
        brain's own active-inference signals lead: a high-SURPRISE belief update or a CONFIDENT
        verdict is what deserves to survive the fade and consolidate to long-term memory; GA
        poignancy is a secondary booster (it lights up for genuinely charged content).
        """
        imp = _ga_importance(text)
        s = min(1.0, max(0.0, surprise))            # Bayesian surprise (nats) → [0,1]
        c = min(1.0, max(0.0, curiosity))
        conf = min(1.0, max(0.0, confidence))
        return round(min(1.0, 0.5 * s + 0.2 * conf + 0.15 * c + 0.15 * imp), 4)

    def compete(self, candidates: list[Thought]) -> list[Thought]:
        """Run one tick: the highest-salience candidate(s) win the broadcast; salient ones consolidate.

        Returns the winning Thought(s) (marked .consolidated if written to long-term memory).
        """
        if not candidates:
            return []
        self.ticks += 1
        ranked = sorted(candidates, key=lambda t: -t.salience)
        winners = ranked[: self.broadcast_bandwidth]
        for w in winners:
            self.broadcasts.append({"tick": self.ticks, "text": w.text[:120],
                                    "kind": w.kind, "salience": w.salience})
            if w.salience >= self.consolidate_threshold:
                if self._consolidate(w):
                    w.consolidated = True
                    self.consolidated += 1
        return winners

    def _consolidate(self, thought: Thought) -> bool:
        """Write a salient thought to long-term memory (KnowledgeBrain). True if ingested."""
        if self.brain is None:
            return True                       # no brain wired → count as "would consolidate"
        try:
            title = f"thought:{thought.kind}:{thought.id}"
            self.brain.ingest_text(title, thought.text)
            return True
        except Exception:
            return False

    def status(self) -> dict:
        return {"ticks": self.ticks, "consolidated": self.consolidated,
                "consolidate_threshold": self.consolidate_threshold,
                "broadcast_bandwidth": self.broadcast_bandwidth,
                "recent_winners": self.broadcasts[-5:]}


class StreamOfMind:
    """Turns a Thinker's think() cycle into an ephemeral thought-stream + LTM consolidation."""

    def __init__(self, thinker=None, *, brain=None, workspace: GlobalWorkspace | None = None,
                 buffer: int = 60, clock=None):
        self.thinker = thinker
        # consolidate into the SAME brain the thinker reasons over, unless told otherwise
        brain = brain if brain is not None else getattr(thinker, "brain", None)
        self.workspace = workspace or GlobalWorkspace(brain)
        self.recent: deque = deque(maxlen=buffer)
        self._seq = itertools.count(1)
        # injected logical clock (deterministic tests) → returns an int "ts"; default wall-ms
        self._clock = clock or self._wall_ms
        self.cycles = 0

    @staticmethod
    def _wall_ms() -> int:
        import time
        return int(time.time() * 1000)

    def _emit(self, text: str, kind: str, *, surprise=0.0, curiosity=0.0,
              confidence=0.0, meta=None) -> Thought:
        sal = GlobalWorkspace.salience(text, surprise=surprise, curiosity=curiosity,
                                       confidence=confidence)
        t = Thought(f"{self._clock()}-{next(self._seq)}", text, kind, sal, self._clock(), meta=meta)
        self.recent.append(t)
        return t

    def _thought_events(self, query: str, result: dict) -> list[Thought]:
        """Decompose one REAL think() result into ordered thought-events (no fabrication)."""
        ev: list[Thought] = []
        conf = float(result.get("confidence") or 0.0)
        surprise = float(result.get("surprise") or 0.0)
        refl = result.get("reflection") or {}
        curiosity_topic = result.get("curiosity")
        uncertainty = float(refl.get("uncertainty") or 0.0)

        # goal/subgoal
        ev.append(self._emit(f"Goal: answer — {query}", "goal", confidence=conf))
        # ReAct/ToT steps (the brain acting on its own memory)
        for i, step in enumerate(result.get("reasoning", {}).get("steps") or []):
            thought = step.get("thought") if isinstance(step, dict) else str(step)
            action = step.get("action") if isinstance(step, dict) else ""
            nh = step.get("n_hits") if isinstance(step, dict) else ""
            ev.append(self._emit(f"{thought} (recall: {action!r} → {nh} hits)", "react",
                                 confidence=conf, meta={"step": i}))
        # active-inference surprise + curiosity
        if surprise:
            ev.append(self._emit(f"Surprise {surprise:.3f} updating beliefs (uncertainty {uncertainty:.2f}).",
                                 "surprise", surprise=surprise))
        if curiosity_topic:
            ev.append(self._emit(f"Most curious about: {curiosity_topic}.", "curiosity",
                                 curiosity=0.8))
        # symbolic insight (traceable)
        sym = result.get("symbolic")
        if sym and sym.get("related"):
            ev.append(self._emit(f"{sym['concept']} relates to {', '.join(sym['related'][:4])}.",
                                 "symbolic", confidence=conf))
        # calibration verdict
        cal = result.get("calibration") or {}
        if result.get("abstained"):
            ev.append(self._emit(f"Not confident enough ({result.get('calibrated_confidence')}) "
                                 "— asking the human.", "verdict", confidence=conf))
        else:
            ev.append(self._emit(f"Confident enough ({result.get('calibrated_confidence')}) — answering.",
                                 "verdict", confidence=conf, surprise=surprise))
        return ev

    def think(self, query: str, *, strategy: str = "react") -> dict:
        """Run one think() cycle, stream its real thoughts through the workspace, consolidate winners."""
        self.cycles += 1
        with obs.trace("stream-of-mind", phase="P4.6", query=query) as tr:
            if self.thinker is None:
                base = {"query": query, "answer": "(no thinker attached)", "confidence": 0.0}
            else:
                with tr.span("think", strategy=strategy):
                    base = self.thinker.think(query, strategy=strategy)
            events = self._thought_events(query, base)
            # ONE global-workspace competition per cycle: the cycle's thoughts compete against
            # EACH OTHER for the single broadcast slot; the salient PEAK wins and consolidates
            # if it clears the absolute floor (so a confident cycle keeps its best insight while
            # a low-salience abstained cycle keeps nothing). Robust to absolute-salience scale.
            with tr.span("workspace", as_type="agent", candidates=len(events)):
                winners = self.workspace.compete(events)
                for t in events:
                    tr.event(t.kind, salience=t.salience, consolidated=t.consolidated)
            tr.update(output=base.get("answer", ""),
                      metadata={"consolidated": len(winners), "thoughts": len(events)})
        obs.flush()
        return {
            "query": query,
            "answer": base.get("answer", ""),
            "abstained": base.get("abstained", False),
            "thoughts": [t.as_dict() for t in events],
            "consolidated": [t.as_dict() for t in events if t.consolidated],
            "n_thoughts": len(events),
            "n_consolidated": sum(t.consolidated for t in events),
            "workspace": self.workspace.status(),
            "observability": obs.status(),
        }

    def stream(self, query: str, *, strategy: str = "react"):
        """Generator of NDJSON-ready events for /api/brain/stream (one think cycle, live)."""
        out = self.think(query, strategy=strategy)
        for t in out["thoughts"]:
            yield {"type": "thought", "text": t["text"], "kind": t["kind"],
                   "salience": t["salience"], "consolidated": t["consolidated"]}
        yield {"type": "answer", "text": out["answer"], "abstained": out["abstained"],
               "consolidated": out["n_consolidated"]}
        yield {"type": "done"}

    def recent_thoughts(self) -> list[dict]:
        return [t.as_dict() for t in self.recent]

    def status(self) -> dict:
        return {"cycles": self.cycles, "buffered": len(self.recent),
                "workspace": self.workspace.status(), "observability": obs.status(),
                "has_thinker": self.thinker is not None}
