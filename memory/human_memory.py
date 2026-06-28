"""memory/human_memory.py — human-like memory: decay, tiers, dreaming (Phase P4.2).

Wraps the existing KnowledgeBrain (which already does PPR + RRF associative recall) with
the human-like dynamics the blueprint asks for:

  • Importance + recall-count metadata per memory.
  • Ebbinghaus forgetting curve: retention R = exp(-Δt / S), where stability S GROWS with
    importance and how often a memory has been recalled (spacing effect) — so unused
    memories fade, reinforced ones persist.
  • Letta-style TIERS: core / recall / archival, assigned by a salience score.
  • auto_dream consolidation: a periodic pass that decays strengths, FORGETS weak archival
    memories, PROMOTES strong ones to core, and merges near-duplicates.
  • Optional FlashRank reranker (gated): rerank recall candidates; offline → identity order.

Reuse-first: composes KnowledgeBrain (no changes to it). Time is INJECTED (epoch `now`) so
decay/dreaming are fully deterministic and offline-testable. FlashRank's model downloads on
first use, so it stays OFF unless explicitly enabled.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

_EULER_DAY = 86400.0


@dataclass
class MemMeta:
    created: float
    last_recalled: float
    recall_count: int = 0
    importance: float = 0.5          # 0..1
    tier: str = "recall"             # core | recall | archival


class HumanMemory:
    """Decay + tiers + dreaming over a KnowledgeBrain's chunk memory."""

    def __init__(self, brain, *, now: float = 0.0, base_stability_days: float = 3.0,
                 forget_threshold: float = 0.15, use_reranker: bool = False):
        self.brain = brain
        self.base_stability_days = base_stability_days
        self.forget_threshold = forget_threshold
        self.meta: dict[str, MemMeta] = {}
        self._reranker = None
        if use_reranker:
            self._init_reranker()
        self._sync_meta(now)

    # ── metadata lifecycle ──────────────────────────────────────────────────────
    def _chunks(self) -> dict:
        return getattr(self.brain, "mem", self.brain).chunks

    def _unit_key(self, cid: str, ch: dict | None = None) -> str:
        """A memory unit = a document (its title); recall() returns titles, so we key on them."""
        ch = ch if ch is not None else self._chunks().get(cid, {})
        return ch.get("title") or cid

    def _sync_meta(self, now: float) -> None:
        for cid, ch in self._chunks().items():
            self.meta.setdefault(self._unit_key(cid, ch), MemMeta(created=now, last_recalled=now))

    def remember(self, cid: str, *, now: float, importance: float | None = None) -> None:
        m = self.meta.setdefault(cid, MemMeta(created=now, last_recalled=now))
        if importance is not None:
            m.importance = max(m.importance, float(importance))

    def _note_recall(self, cid: str, now: float) -> None:
        m = self.meta.get(cid)
        if m is None:
            return
        m.recall_count += 1
        m.last_recalled = now
        m.importance = min(1.0, m.importance + 0.05)      # recalled → more salient

    # ── Ebbinghaus decay ────────────────────────────────────────────────────────
    def stability(self, m: MemMeta) -> float:
        """Days of stability — grows with recall count (spacing) and importance."""
        return self.base_stability_days * (1.0 + m.recall_count) * (0.5 + m.importance)

    def strength(self, cid: str, now: float) -> float:
        """Retention R = exp(-Δdays / stability) in [0,1]. Unknown → 0."""
        m = self.meta.get(cid)
        if m is None:
            return 0.0
        dt_days = max(0.0, (now - m.last_recalled) / _EULER_DAY)
        return math.exp(-dt_days / max(1e-6, self.stability(m)))

    # ── tiers (Letta model) ─────────────────────────────────────────────────────
    def _salience(self, cid: str, now: float) -> float:
        m = self.meta.get(cid)
        if m is None:
            return 0.0
        return 0.5 * m.importance + 0.3 * self.strength(cid, now) + \
            0.2 * min(1.0, m.recall_count / 10.0)

    def assign_tiers(self, now: float, *, core_q: float = 0.8, archival_q: float = 0.35) -> None:
        for cid, m in self.meta.items():
            s = self._salience(cid, now)
            m.tier = "core" if s >= core_q else ("archival" if s < archival_q else "recall")

    # ── reranker (gated) ────────────────────────────────────────────────────────
    def _init_reranker(self) -> None:
        try:  # pragma: no cover - downloads a model on first use
            from flashrank import Ranker
            self._reranker = Ranker(max_length=256)
        except Exception:
            self._reranker = None

    def _rerank(self, query: str, hits: list[dict]) -> list[dict]:
        if self._reranker is None or not hits:
            return hits
        try:  # pragma: no cover
            from flashrank import RerankRequest
            passages = [{"id": i, "text": h.get("snippet", "") or h.get("title", "")}
                        for i, h in enumerate(hits)]
            ranked = self._reranker.rerank(RerankRequest(query=query, passages=passages))
            return [hits[r["id"]] for r in ranked]
        except Exception:
            return hits

    # ── recall (decay-aware) ────────────────────────────────────────────────────
    def recall(self, query: str, k: int = 4, *, now: float = 0.0, reinforce: bool = True) -> list[dict]:
        self._sync_meta(now)
        cand = self.brain.recall(query, k=max(k * 3, 12))
        if not cand:
            return []
        cand = self._rerank(query, cand)
        for h in cand:                                    # blend retrieval score with decay
            cid = h.get("id") or h.get("cid") or h.get("title")
            st = self.strength(cid, now) if cid else 0.5
            h["strength"] = round(st, 4)
            h["tier"] = self.meta.get(cid, MemMeta(now, now)).tier if cid else "recall"
            h["combined"] = float(h.get("score", 0.0)) * (0.5 + 0.5 * st)
        cand.sort(key=lambda h: h.get("combined", 0.0), reverse=True)
        top = cand[:k]
        if reinforce:
            for h in top:
                cid = h.get("id") or h.get("cid") or h.get("title")
                if cid:
                    self._note_recall(cid, now)
        return top

    # ── auto_dream consolidation ────────────────────────────────────────────────
    def dream(self, now: float, *, consolidate: bool = True) -> dict:
        """Periodic sleep: decay → forget weak archival → promote strong → merge dupes."""
        self._sync_meta(now)
        self.assign_tiers(now)
        forgotten, promoted = [], []
        for cid in list(self.meta):
            m = self.meta[cid]
            s = self.strength(cid, now)
            # Forget only TRIVIA: decayed, never-recalled, low-importance. Rehearsed or
            # important memories CONSOLIDATE to long-term and are never auto-deleted.
            if (m.tier == "archival" and s < self.forget_threshold
                    and m.recall_count == 0 and m.importance < 0.6):
                self._forget(cid)
                forgotten.append(cid)
            elif self._salience(cid, now) >= 0.85 and m.tier != "core":
                m.tier = "core"
                promoted.append(cid)
        merged = self._consolidate(now) if consolidate else []
        return {"forgotten": len(forgotten), "promoted": len(promoted),
                "consolidated": len(merged), "remaining": len(self.meta)}

    def _forget(self, unit: str) -> None:
        """Forget a memory unit (document): drop all its chunks + meta."""
        chunks = self._chunks()
        for cid in [c for c, ch in list(chunks.items()) if self._unit_key(c, ch) == unit]:
            chunks.pop(cid, None)
            g = getattr(self.brain, "graph", None)
            if g is not None and hasattr(g, "remove_node"):
                try:
                    g.remove_node(cid)
                except Exception:
                    pass
        self.meta.pop(unit, None)

    def _consolidate(self, now: float) -> list:
        """Merge near-duplicate memory units (titles sharing a prefix) into the most salient."""
        groups: dict[str, list] = {}
        for unit in list(self.meta):
            groups.setdefault(unit[:48].lower(), []).append(unit)
        merged = []
        for key, units in groups.items():
            if not key or len(units) < 2:
                continue
            keep = max(units, key=lambda u: self._salience(u, now))
            for unit in units:
                if unit != keep:
                    km, dm = self.meta.get(keep), self.meta.get(unit)
                    if km and dm:                          # fold salience into the survivor
                        km.recall_count += dm.recall_count
                        km.importance = min(1.0, max(km.importance, dm.importance))
                    self._forget(unit)
                    merged.append(unit)
        return merged

    def status(self, now: float = 0.0) -> dict:
        tiers = {"core": 0, "recall": 0, "archival": 0}
        self.assign_tiers(now)
        for m in self.meta.values():
            tiers[m.tier] = tiers.get(m.tier, 0) + 1
        return {"n_memories": len(self.meta), "tiers": tiers,
                "reranker": "flashrank" if self._reranker is not None else "off",
                "base_stability_days": self.base_stability_days}
