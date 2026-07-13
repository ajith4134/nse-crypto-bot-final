"""trading/brain/self_evaluation.py — the brain grades ITSELF, honestly
(Brain Ultra Upgrade R3, R22, R23, R28 + agentic time horizon; GOAL.md Pillar 5).

Four standing measurements, all computed from REAL recorded evidence (neuron stats,
exam history, mind-event heartbeats) — no metric here is ever synthesized:

  independent_learning_test (R3): hand the brain a topic it has ZERO neurons on → it
    must research the web itself (librarian), study the results into lesson neurons,
    distill an instruction, and pass a quiz on what it just learned — unaided.
  genius_use (R22): knowledge-USE rates per domain (trading, navigation, research…)
    from record_use() evidence across ALL neuron kinds — not just trades.
  llm_parity (R23): same hidden-action task given to (a) the brain = its own recall,
    and (b) a raw LLM with NO memory; graded identically against the hidden action.
    Proves the BRAIN is intelligent, not the LLMs it calls.
  accumulation (R28): the web must GROW (store.growth) and old exams must not decay
    (score trend per level from school history).
  time_horizon: how long the brain has been running autonomously — measured from real
    mind-event timestamps (a gap > GAP_SECS breaks the run).

Reports persist to trading/state/self_evaluation.json for the dashboard (honest wiring).
"""
from __future__ import annotations

import os
import time

from memory.neurons import NeuronStore, _jaccard, _words, get_store
from trading import state

REPORT_FILE = "self_evaluation.json"
GAP_SECS = 600.0                                      # >10min silence breaks a run
PARITY_N = 6


def _default_llm(prompt: str) -> str | None:
    try:
        from core.llm import chat
        return chat([{"role": "user", "content": prompt}], max_tokens=250,
                    temperature=0.2)
    except Exception:
        return None


class SelfEvaluation:
    def __init__(self, store: NeuronStore | None = None, *, llm=None,
                 librarian=None):
        self.store = store or get_store()
        self.llm = llm or _default_llm
        self._librarian = librarian                   # injected in tests

    # ── R3: independent learning — zero-neuron topic → learned, unaided ───────
    def independent_learning_test(self, topic: str, *, max_items: int = 5,
                                  now: float | None = None) -> dict:
        return self._persist_il(self._il_run(topic, max_items=max_items, now=now))

    def _persist_il(self, result: dict) -> dict:
        # every outcome — success OR failure — lands in the report the dashboard
        # reads, so a failed run is never silently invisible
        self._merge_report({"independent_learning": result})
        return result

    def _il_run(self, topic: str, *, max_items: int, now: float | None) -> dict:
        ts = time.time() if now is None else float(now)
        prior = self.store.search(topic, k=3)
        known = prior and max(
            _jaccard(_words(topic), _words(h["title"])) for h in prior) >= 0.5
        if known:
            return {"topic": topic, "ok": False, "ts": ts,
                    "note": "topic not unknown — brain already has strong neurons on it",
                    "prior_hits": [h["title"] for h in prior]}
        lib = self._librarian or self._make_librarian()
        if lib is None:
            return {"topic": topic, "ok": False, "ts": ts,
                    "note": "librarian unavailable (no ddgs/network) — test cannot run"}
        try:
            items = lib.discover(topic, max_per=max_items)
        except Exception as exc:
            return {"topic": topic, "ok": False, "ts": ts,
                    "note": f"research failed: {exc!r}"[:200]}
        texts = []
        for it in (items or []):
            body = str(it.get("body") or it.get("text") or it.get("summary") or "")
            if it.get("source") == "web" and it.get("url") and len(body) < 300:
                try:                                  # full-text extract, same as feed()
                    body = getattr(lib, "extractor", lambda u: "")(it["url"]) or body
                except Exception:
                    pass
            if body.strip():
                texts.append({"title": it.get("title") or topic, "body": body,
                              "ref": it.get("url") or ""})
        if not texts:
            return {"topic": topic, "ok": False, "ts": ts,
                    "note": "research returned no readable text"}
        from trading.brain.school import School
        school = School(self.store)
        studied = school.study(topic, texts, now=ts)
        # distill ONE instruction from what was just learned (knowledge → action, R14)
        lessons = [self.store.get(i) for i in studied["neurons"]]
        steps = [f"{i + 1}) {l.action}" for i, l in enumerate(lessons) if l]
        instr = self.store.add(
            "instruction", f"how to apply: {topic}"[:200], "\n".join(steps),
            f"Follow when '{topic}' is relevant; learned unaided at ts={ts:.0f}. "
            f"Verify each step against its source neuron before trusting.",
            origin="research", ref=f"independent-learning:{topic}", now=ts,
            auto_link=False)
        for l in lessons:
            if l:
                self.store.link(instr.id, l.id, "derived-from", now=ts)
        quiz = [school.quiz.quiz_one(l.id, l.body[:400]) for l in lessons if l]
        graded = [q for q in quiz if "skipped" not in q]
        score = (sum(1 for q in graded if q["correct"]) / len(graded)) if graded else None
        return {"topic": topic, "ok": True, "neurons_created": len(studied["neurons"]),
                "instruction": instr.id, "quiz_score": score,
                "secs": round(time.time() - ts, 1), "ts": ts}

    def _make_librarian(self):
        try:
            from memory.brain import get_brain
            from memory.librarian import Librarian
            return Librarian(brain=get_brain())
        except Exception:
            return None

    # ── R22: genius-use on ALL the things ──────────────────────────────────────
    # kinds meant to inform live decisions — the honest denominator for genius-use.
    # (episode/source/exam are historical/provenance records rarely re-consulted, so
    # including them in the denominator deflates the metric misleadingly.)
    ACTIONABLE_KINDS = {"strategy", "instruction", "finding", "lesson", "skill", "concept",
                        "fact"}

    def genius_use(self) -> dict:
        by_domain: dict[str, dict] = {}
        used = total = 0
        act_used = act_total = 0
        for n in self.store.all_neurons():
            if n.kind == "exam":
                continue
            total += 1
            tu = int(n.stats.get("times_used", 0))
            if tu:
                used += 1
            if n.kind in self.ACTIONABLE_KINDS:            # honest denominator
                act_total += 1
                if tu:
                    act_used += 1
            for dom, rec in (n.stats.get("by_domain") or {}).items():
                if not isinstance(rec, dict):         # legacy int = uses only
                    rec = {"uses": int(rec or 0), "wins": 0, "losses": 0}
                d = by_domain.setdefault(dom, {"uses": 0, "neurons": 0, "wins": 0,
                                               "losses": 0})
                d["uses"] += int(rec.get("uses", 0))
                d["neurons"] += 1
                d["wins"] += int(rec.get("wins", 0))      # per-domain outcomes only —
                d["losses"] += int(rec.get("losses", 0))  # never the neuron's totals
        out = {"knowledge_use_rate": round(used / total, 4) if total else 0.0,
               "actionable_use_rate": round(act_used / act_total, 4) if act_total else 0.0,
               "neurons_ever_used": used, "neurons_total": total,
               "actionable_total": act_total, "by_domain": by_domain}
        self._merge_report({"genius_use": out})
        return out

    # ── R23: brain vs raw LLM on the hidden-action task ───────────────────────
    def llm_parity(self, *, n: int = PARITY_N, now: float | None = None) -> dict:
        ts = time.time() if now is None else float(now)
        pool = [x for x in self.store.all_neurons()
                if x.kind in ("fact", "concept", "strategy", "finding")
                and len(x.action) > 60 and len(x.body) > 80]
        pool.sort(key=lambda x: x.updated, reverse=True)
        sample = pool[: n * 3][:n] if pool else []
        if len(sample) < 3:
            return {"ok": False, "note": "not enough rich neurons for the benchmark"}
        brain_scores, llm_scores = [], []
        llm_alive = True
        for x in sample:
            related = [h for h in self.store.search(f"{x.title} {x.body[:120]}", k=5)
                       if h["id"] != x.id]
            brain_ans = " ".join(h["action"] for h in related)
            brain_scores.append(_jaccard(_words(brain_ans), _words(x.action)))
            if llm_alive:
                reply = self.llm(
                    "Given this market knowledge, state concisely how a trader should "
                    f"USE it (when it applies, what to do, how to verify).\n"
                    f"TITLE: {x.title}\nKNOWLEDGE: {x.body[:600]}")
                if reply is None:
                    llm_alive = False
                else:
                    llm_scores.append(_jaccard(_words(reply), _words(x.action)))
        brain = round(sum(brain_scores) / len(brain_scores), 4)
        llm = round(sum(llm_scores) / len(llm_scores), 4) if llm_scores else None
        out = {"ok": True, "n": len(sample), "brain_score": brain, "llm_score": llm,
               "parity": (llm is not None and brain >= llm) or None if llm is None
               else brain >= llm,
               "note": None if llm is not None else "no LLM reachable — brain side only",
               "ts": ts}
        self._merge_report({"llm_parity": out})
        return out

    # ── R28: accumulation + exam-decay ─────────────────────────────────────────
    def accumulation(self, *, now: float | None = None) -> dict:
        growth = self.store.growth(buckets=14, now=now)
        recent = sum(b["neurons"] for b in growth[-7:])
        prior = sum(b["neurons"] for b in growth[:7])
        exams = (state.load_json("school.json", {}) or {}).get("exams", [])
        decay: dict[str, list] = {}
        for e in exams:
            a = (e.get("track_a") or {}).get("score")
            if a is not None:
                decay.setdefault(e["level"], []).append(a)
        trends = {lvl: {"first": s[0], "last": s[-1], "n": len(s),
                        "decayed": s[-1] < s[0] - 0.05}
                  for lvl, s in decay.items() if len(s) >= 2}
        out = {"growth_14d": growth, "neurons_last7d": recent,
               "neurons_prior7d": prior, "growing": recent >= max(1, prior // 4),
               "exam_trends": trends}
        self._merge_report({"accumulation": {k: v for k, v in out.items()
                                             if k != "growth_14d"}})
        return out

    # ── agentic time horizon from real heartbeats ──────────────────────────────
    def time_horizon(self, *, now: float | None = None) -> dict:
        ts = time.time() if now is None else float(now)
        events = (state.load_json("mind_events.json", {}) or {}).get("events", [])
        stamps = sorted(float(e["ts"]) for e in events if e.get("ts"))
        if not stamps:
            return {"ok": False, "note": "no mind events recorded yet"}
        runs, start = [], stamps[0]
        for prev, cur in zip(stamps, stamps[1:]):
            if cur - prev > GAP_SECS:
                runs.append(prev - start)
                start = cur
        live_gap = ts - stamps[-1]
        runs.append((stamps[-1] if live_gap > GAP_SECS else ts) - start)
        out = {"ok": True, "current_run_secs": round(runs[-1] if live_gap <= GAP_SECS
                                                     else 0.0),
               "longest_run_secs": round(max(runs)), "runs": len(runs),
               "last_event_age_secs": round(live_gap)}
        self._merge_report({"time_horizon": out})
        return out

    # ── R23/R28 TRENDING: append a compact snapshot each cron tick ─────────────
    def snapshot_history(self, *, run_parity: bool = False, now: float | None = None,
                         cap: int = 90) -> dict:
        """The standing cron's unit of work: append a compact metrics snapshot so
        genius-use / accumulation / parity / time-horizon TREND over time instead of only
        showing 'now'. Cheap metrics every call; llm_parity only when run_parity (it costs
        an LLM round-trip — the caller gates its cadence). Honest: every value is measured."""
        ts = time.time() if now is None else float(now)
        gu = self.genius_use()
        acc = self.accumulation(now=now)
        th = self.time_horizon(now=now)
        st = self.store.status()
        snap = {"ts": round(ts, 2),
                "knowledge_use_rate": gu.get("knowledge_use_rate"),
                "neurons_ever_used": gu.get("neurons_ever_used"),
                "neurons": st.get("neurons"), "links": st.get("links"),
                "neurons_last7d": acc.get("neurons_last7d"),
                "longest_run_secs": th.get("longest_run_secs") if th.get("ok") else None}
        if run_parity:
            lp = self.llm_parity(now=now)
            if lp.get("ok"):
                snap["parity_brain"] = lp.get("brain_score")
                snap["parity_llm"] = lp.get("llm_score")

        def _append(d):
            d = d or {}
            hist = list(d.get("history", []))
            hist.append(snap)
            d["history"] = hist[-cap:]
            return d
        state.mutate_json(REPORT_FILE, _append, default={})
        return snap

    # ── does APPLYING an instruction lift win-rate? (R22/R27 knowledge-application) ──
    def apply_lift(self, *, lookback: int = 2000) -> dict:
        """Observational cohort deltas: compare the win-rate of closed trades whose decision
        APPLIED an instruction (recorded in decision_snapshot…neurons.applied) against the
        baseline, bucketed by the applied instruction's confidence. Honest — this is the
        live applied-instruction cohort, not a randomised A/B; `tilt_enabled` says whether
        the instruction actually moved the decision (INSTRUCTION_APPLY_TILT=1) or was pure
        attribution. Populates as trades close after instruction-application shipped."""
        rows = (state.load_json("journal.json", []) or [])[-int(lookback):]

        def wr(rs):
            return round(sum(1 for r in rs if (r.get("net_pnl") or 0) > 0) / len(rs), 4) \
                if rs else None
        applied, hi, lo = [], [], []
        for r in rows:
            neu = ((((r.get("decision_snapshot") or {}).get("app_signals") or {})
                    .get("indicator_fusion") or {}).get("neurons") or {})
            a = neu.get("applied")
            if isinstance(a, dict) and a.get("id"):
                applied.append(r)
                (hi if float(a.get("confidence") or 0) >= 0.6 else lo).append(r)
        base = wr(rows)
        out = {"baseline_win_rate": base, "n_trades": len(rows),
               "applied": {"n": len(applied), "win_rate": wr(applied)},
               "applied_high_conf": {"n": len(hi), "win_rate": wr(hi)},
               "applied_low_conf": {"n": len(lo), "win_rate": wr(lo)},
               "tilt_enabled": os.environ.get("INSTRUCTION_APPLY_TILT") == "1"}
        if base is not None and applied and wr(applied) is not None:
            out["lift"] = round(wr(applied) - base, 4)
        self._merge_report({"apply_lift": out})
        return out

    # ── the standing report ────────────────────────────────────────────────────
    def full_report(self, *, now: float | None = None) -> dict:
        return {"genius_use": self.genius_use(),
                "llm_parity": self.llm_parity(now=now),
                "accumulation": self.accumulation(now=now),
                "time_horizon": self.time_horizon(now=now),
                "independent_learning":
                    (state.load_json(REPORT_FILE, {}) or {}).get("independent_learning"),
                "store": self.store.status()}

    def _merge_report(self, updates: dict) -> None:
        try:
            state.update_json(REPORT_FILE, updates)
        except Exception:
            pass                                      # metric still returned to caller
