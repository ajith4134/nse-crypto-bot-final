"""memory/neuron_web.py — converters: EVERY existing brain store → the web of neurons (R15).

Owner requirement R15 (research/brain-ultra-upgrade/OWNER_MESSAGE_VERBATIM.md): "convert
all the data — strategies, research, books it studied, news it read, findings, inventions,
knowledge, memory" into the ONE common language. This module is the migration layer: each
converter reads a real store (read-only — old stores keep working) and up-serts neurons
with DETERMINISTIC ids (sha1 of source+key), so re-running is idempotent: unchanged rows
are skipped, changed rows update in place, nothing duplicates.

Every produced neuron's `action` facet (R24) is DERIVED FROM THE ROW'S OWN DATA (its
lesson_learned, mistake_type, hypothesis operator, strategy idea…) — never invented.

Bulk adds run with auto_link=False (O(n²) pairwise linking would take minutes at ~6k
neurons); `weave()` then builds the web in one O(n·tokens) pass over an inverted index
of title tokens, linking neurons that share a RARE token (shared "BTCUSDT" is signal,
shared "price" is noise).

CLI: `python -m memory.neuron_web` → convert everything + weave + print status.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import defaultdict
from pathlib import Path

from memory.neurons import REPO_ROOT, NeuronStore, _words, get_store

STATE_DIR = REPO_ROOT / "trading" / "state"
BRAIN_MEMORY = REPO_ROOT / "brain_memory"
RESEARCH_DIR = REPO_ROOT / "research"

_FILE_TYPE_KIND = {"user": "fact", "feedback": "lesson", "project": "fact",
                   "reference": "source", "lesson": "lesson"}
_KIND_LEVEL = {"fact": "L1", "concept": "L2", "lesson": "L2", "episode": "L2",
               "skill": "L3", "strategy": "L3", "source": "L1", "news": "L1",
               "finding": "L5", "invention": "L5", "book-chapter": "L3", "exam": "L0"}


def _det_id(source: str, key: str) -> str:
    return "n-" + hashlib.sha1(f"{source}:{key}".encode()).hexdigest()[:12]


def _load(name: str):
    p = STATE_DIR / name
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except Exception:
        return None


def _num(v, nd=2):
    try:
        return round(float(v), nd)
    except (TypeError, ValueError):
        return None


# ── FEATURE CATALOG: the brain's own capabilities as instruction-shaped skills ──
# Every shipped feature the brain can USE. Each carries a mandatory action facet (R24):
# when it applies, how to activate it, how to verify it helped. Append new features here.
_FEATURE_CATALOG = [
    # ── web-data / perception resilience (sibling adopt-plan, live 2026-07-13) ──
    {"key": "feed_selfheal", "title": "Feed schema-drift self-heal",
     "body": "Auto-repairs web-feed decoding when a broker silently changes its wire "
             "schema — Upstox protobuf field shifts + Binance JSON key renames. Wired in "
             "upstox_feed + binance_stream; loads in the funnel.",
     "action": "Rely on it when a live feed starts returning empty/garbled ticks after a "
               "broker update — it re-derives the mapping instead of going blind. Verify: "
               "tick flow resumes without a code change; check the self-heal log entry.",
     "ref": "trading/broker_sense (upstox_feed, binance_stream)"},
    {"key": "vision_is_context", "title": "Vision = context, not a direction vote",
     "body": "Local chart vision supplies CONTEXT (regime, structure, notable levels) to "
             "fuse(); it does NOT emit a hardcoded long/short vote. Prevents a single "
             "vision call from overriding the learned direction driver.",
     "action": "Read vision output as situational context that weights other lenses; never "
               "treat it as a standalone entry signal. Verify: fuse() confluence shifts "
               "with vision context but direction still comes from learned_direction.",
     "ref": "trading/broker_sense/indicator_fusion.fuse"},
    {"key": "endpoint_discovery", "title": "Endpoint discovery over capture registry",
     "body": "Discovers usable broker/data API endpoints by mining our own captured-traffic "
             "registry (both markets) — finds the real data doors the UI actually calls.",
     "action": "Use to locate a data endpoint for a needed kind before hardcoding a URL; "
               "prefer a discovered endpoint over a guess. Verify: discovered endpoint "
               "returns the expected payload shape on a live probe.",
     "ref": "endpoint discovery (both markets)"},
    {"key": "patchright_stealth", "title": "Patchright stealth browser (flagged)",
     "body": "A stealth-hardened browser backend for Binance + Upstox logins, behind a flag. "
             "Off by default (active engine = playwright).",
     "action": "Flip STEALTH_BROWSER=patchright ONLY when a login is being bot-detected/"
               "challenged on playwright; leave default otherwise. Verify: the flagged login "
               "advances past the challenge that blocked playwright.",
     "ref": "STEALTH_BROWSER=patchright"},
    {"key": "tv_feed", "title": "TradingView-WS supplementary data lane (flagged)",
     "body": "An optional TradingView websocket lane for supplementary market data. Off by "
             "default.",
     "action": "Enable only as a supplementary cross-check when a primary venue feed is "
               "degraded; it is not a primary execution-data source (motto: data = web nav). "
               "Verify: lane delivers frames and agrees with the primary feed.",
     "ref": "tv_feed (default off)"},
    {"key": "uitars_last_resort", "title": "UI-TARS visual grounder (selective last-resort)",
     "body": "A vision grounder that locates UI targets from a screenshot, wired as a "
             "SELECTIVE last-resort OFF the hot path — used only when DOM/registry locating "
             "fails. State-flag activated (last_resort()=True, model pulled).",
     "action": "Fall back to it only when normal element-locating fails on a broker screen; "
               "never on the hot path (it is slow). Verify: it returns coordinates that "
               "click the intended control; a funnel started before activation needs a "
               "restart to read the flag.",
     "ref": "UI-TARS grounder (state-flag activated)"},
    # ── brain-ultra-upgrade + brain-os core (this workstream) ──
    {"key": "neuron_web", "title": "Web of neurons — one common language",
     "body": "Every kind of brain data (strategies, research, news, findings, lessons, "
             "episodes, features) is one instruction-shaped Neuron in one graph.",
     "action": "Store any new knowledge as a neuron with a how-to-use action facet; recall "
               "via consult() before acting. Verify: /api/brain/neurons count grows and "
               "action_coverage stays 1.0.",
     "ref": "memory/neurons.py"},
    {"key": "instruction_evolution", "title": "Instruction evolution loop",
     "body": "Underperforming instruction neurons are mutated; a child that beats its parent "
             "on graded evidence is promoted and the parent retired (lineage kept).",
     "action": "Let the learn-loop evolve instructions; consult the Pareto archive for the "
               "best current variant. Verify: /api/brain/evolution shows proven lineages.",
     "ref": "trading/brain/evolution.py"},
    {"key": "brain_os", "title": "Brain-OS — resident kernel with its own RAM",
     "body": "A resident kernel holds working memory in RAM, runs a process table of the "
             "lobes, an attention scheduler, and one syscall surface.",
     "action": "Route recall/remember/consult/evolve through kernel.syscall(); read "
               "next_lobe() to know what to attend. Verify: /api/brain/os shows RESIDENT + "
               "an honest process table.",
     "ref": "trading/brain/brain_os.py"},
]


class NeuronWeb:
    """Runs all converters against a NeuronStore and weaves the links."""

    def __init__(self, store: NeuronStore | None = None):
        self.store = store or get_store()

    # ── upsert helper: deterministic + skip-unchanged ─────────────────────────
    def _upsert(self, source: str, key: str, kind: str, title: str, body: str,
                action: str, *, origin: str, ref: str = "",
                confidence: float = 0.5, now: float | None = None) -> str | None:
        """Never raises: one bad row must not abort its converter generator (a raise
        inside the generator would silently skip every remaining row of that source)."""
        try:
            nid = _det_id(source, key)
            old = self.store.get(nid)
            if (old is not None and old.body == body.strip()
                    and old.action == action.strip()):
                return None                          # unchanged → skip (idempotent)
            self.store.add(kind, title, body, action,
                           level=_KIND_LEVEL.get(kind, "L1"), origin=origin, ref=ref,
                           confidence=confidence, nid=nid, now=now, auto_link=False)
            return nid
        except Exception:
            return "ERR"                             # counted, migration continues

    def _run(self, fn) -> dict:
        added = errors = 0
        try:
            for ok in fn():
                if ok == "ERR":
                    errors += 1
                elif ok:
                    added += 1
        except Exception as exc:                     # a broken store never kills the run
            return {"added": added, "errors": errors + 1, "error": repr(exc)[:200]}
        return {"added": added, "errors": errors}

    # ── converters (each yields truthy per upserted neuron) ───────────────────
    def conv_file_memory(self):
        """brain_memory/*.md (FileMemory notes) → fact/lesson/source neurons."""
        from memory.file_memory import FileMemory
        fm = FileMemory(BRAIN_MEMORY)
        for note in fm.load_all():
            body = note["body"]
            m = re.search(r"\*?\*?How to apply:?\*?\*?:?\s*(.+)", body)
            action = (m.group(1).strip() if m else
                      f"Recall '{note['name']}' when its topic comes up; it records: "
                      f"{(note['description'] or body.splitlines()[0])[:200]}")
            yield self._upsert("file_memory", note["name"],
                               _FILE_TYPE_KIND.get(note["type"], "fact"),
                               note["name"].replace("-", " "),
                               body[:2000], action, origin="lesson",
                               ref=f"brain_memory/{note['file']}")

    def conv_skill_library(self):
        """skill_library.json (admitted evolved strategies) → skill neurons."""
        rows = _load("skill_library.json") or []
        for r in rows:
            if not isinstance(r, dict) or not r.get("id"):
                continue
            name = r.get("name") or r["id"]
            metric = _num(r.get("metric"))
            body = (f"Admitted {r.get('kind', 'strategy')} for market={r.get('market')} "
                    f"gen={r.get('generation')} metric={metric} "
                    f"metrics={json.dumps(r.get('metrics') or {})[:400]}\n"
                    f"payload: {json.dumps(r.get('payload') or {})[:800]}")
            action = (f"Deploy '{name}' on {r.get('market') or 'its market'} when its "
                      f"regime fits; admitted with metric={metric} from "
                      f"{r.get('source') or 'evolution'} — retrieve via SkillLibrary and "
                      f"track outcome to update this neuron.")
            yield self._upsert("skill_library", str(r["id"]), "skill", str(name)[:200],
                               body, action, origin="experiment",
                               ref="trading/state/skill_library.json",
                               confidence=min(0.9, 0.5 + (metric or 0) / 10))

    def conv_strategy_foundry(self):
        """strategy_foundry.json specs (institutional strategy library) → strategy neurons."""
        d = _load("strategy_foundry.json") or {}
        for spec in d.get("specs", []):
            sid = spec.get("sid") or spec.get("name")
            if not sid:
                continue
            idea = str(spec.get("idea") or "")
            body = (f"{idea}\nfamily={spec.get('family')} segment={spec.get('segment')} "
                    f"status={spec.get('status')} data_req={spec.get('data_req')} "
                    f"reference={spec.get('reference')}")
            action = (f"Run '{spec.get('name')}' on segment {spec.get('segment')} when the "
                      f"family ({spec.get('family')}) matches the regime; core idea: "
                      f"{idea[:220] or 'see body'}.")
            yield self._upsert("foundry", str(sid), "strategy",
                               str(spec.get("name") or sid)[:200], body, action,
                               origin="book", ref="trading/state/strategy_foundry.json")

    def conv_hypotheses(self):
        """hypotheses.json (hypothesis ledger) → finding (tested) / lesson (failed)."""
        d = _load("hypotheses.json") or {}
        for h in d.get("hypotheses", []):
            hid = h.get("hid")
            if not hid:
                continue
            stmt = str(h.get("statement") or "")
            body = (f"{stmt}\nstatus={h.get('status')} credence={_num(h.get('credence'))} "
                    f"effect_size={_num(h.get('effect_size'), 4)} p={_num(h.get('p_value'), 4)} "
                    f"win_rate cond/ctrl={_num(h.get('win_rate_cond'), 3)}/"
                    f"{_num(h.get('win_rate_ctrl'), 3)} field={h.get('field')} "
                    f"{h.get('op')} {h.get('value')}")
            action = (f"When '{h.get('field')}' {h.get('op')} {h.get('value')} holds, this "
                      f"hypothesis ({h.get('status')}, credence {_num(h.get('credence'))}) "
                      f"says: {stmt[:200]} — weight the signal accordingly.")
            yield self._upsert("hypotheses", str(hid), "finding", stmt[:200] or str(hid),
                               body, action, origin="experiment",
                               ref="trading/state/hypotheses.json",
                               confidence=float(h.get("credence") or 0.5))
        for f in d.get("failures", []):
            hid = f.get("hid")
            if not hid:
                continue
            stmt = str(f.get("statement") or "")
            yield self._upsert(
                "hypotheses_failed", str(hid), "lesson", f"FAILED: {stmt[:180]}",
                f"{stmt}\ncredence={_num(f.get('credence'))} "
                f"effect_size={_num(f.get('effect_size'), 4)} — rejected by the ledger.",
                f"Do NOT trade on this: '{stmt[:200]}' failed validation; if it "
                f"resurfaces in research, demand fresh evidence first.",
                origin="experiment", ref="trading/state/hypotheses.json",
                confidence=0.2)

    def conv_news(self):
        """news_memory.json items → news neurons."""
        d = _load("news_memory.json") or {}
        for it in d.get("items", []):
            url = it.get("url") or it.get("title")
            if not url:
                continue
            syms = ",".join(it.get("symbols") or [])
            body = (f"{it.get('title')}\nsource={it.get('source')} symbols={syms} "
                    f"sentiment(compound)={_num(it.get('compound'), 3)} ts={it.get('ts')}")
            action = (f"Factor this into sentiment for [{syms or 'the broad market'}]: "
                      f"compound={_num(it.get('compound'), 3)} — bias entries in that "
                      f"direction only with signal confluence; stale after ~48h.")
            yield self._upsert("news", str(url), "news",
                               str(it.get("title") or url)[:200], body, action,
                               origin="url", ref=str(it.get("url") or ""),
                               now=float(it["ts"]) if it.get("ts") else None)

    def conv_journal(self):
        """journal.json closed trades (85-col journal) → episode neurons."""
        rows = _load("journal.json") or []
        for r in rows:
            tid = r.get("trade_id") or r.get("episode_id")
            if not tid or not r.get("exit_datetime"):
                continue                              # only closed trades are episodes
            pnl = _num(r.get("net_pnl")) if r.get("net_pnl") is not None else _num(r.get("net_pnl_crypto"))
            sym, direc = r.get("symbol"), r.get("direction")
            body = (f"{sym} {direc} via {r.get('strategy_name')} "
                    f"({r.get('signal_source')}) entry={r.get('entry_price')} "
                    f"exit={r.get('exit_price')} pnl={pnl} R={_num(r.get('r_multiple'))} "
                    f"regime={r.get('market_regime_entry')} setup={r.get('setup_type')} "
                    f"mistake={r.get('mistake_type')} "
                    f"reflection={str(r.get('exit_reflection') or '')[:300]}")
            lesson = str(r.get("lesson_learned") or "").strip()
            verdict = "REPEAT" if (pnl or 0) > 0 else "AVOID"
            action = (f"{verdict} this setup: {sym} {direc} "
                      f"[{r.get('strategy_name')}/{r.get('setup_type')}] in regime "
                      f"'{r.get('market_regime_entry')}' → pnl {pnl}."
                      + (f" Lesson: {lesson[:250]}" if lesson else ""))
            yield self._upsert("journal", str(tid), "episode",
                               f"{sym} {direc} {str(r.get('entry_datetime') or '')[:10]} "
                               f"pnl {pnl}", body, action, origin="trade",
                               ref=f"journal:{tid}")

    def conv_decision_episodes(self):
        """decision_episodes.json (FinMem decision memory) → episode neurons."""
        d = _load("decision_episodes.json") or {}
        for e in d.get("episodes", []):
            eid = e.get("episode_id")
            if not eid:
                continue
            outcome = e.get("outcome") if isinstance(e.get("outcome"), dict) else {}
            pnl = _num(outcome.get("pnl") if outcome else None)
            body = (f"{e.get('market')} {e.get('direction')} decision="
                    f"{str(e.get('decision') or '')[:300]} outcome={json.dumps(outcome)[:300]} "
                    f"importance={_num(e.get('importance'), 3)} layer={e.get('layer')}")
            action = (f"When deciding {e.get('market')} {e.get('direction')} again, recall "
                      f"this episode (pnl {pnl}); "
                      f"{'repeat what worked' if (pnl or 0) > 0 else 'check what went wrong first'}.")
            yield self._upsert("decision_mem", str(eid), "episode",
                               f"decision {e.get('market')} {e.get('direction')} {eid}"[:200],
                               body, action, origin="trade",
                               ref="trading/state/decision_episodes.json")

    def conv_research_docs(self):
        """research/*.md (top-level research corpus) → source neurons."""
        for p in sorted(RESEARCH_DIR.glob("*.md")):
            try:
                text = p.read_text()[:4000]
            except OSError:
                continue
            first = next((ln.lstrip("# ").strip() for ln in text.splitlines()
                          if ln.strip()), p.stem)
            topic = p.stem.replace("-", " ")
            yield self._upsert(
                "research", p.name, "source", first[:200], text[:2000],
                f"Consult research/{p.name} when working on '{topic}'; it records: "
                f"{first[:180]}.",
                origin="research", ref=f"research/{p.name}")

    def conv_learning_log(self):
        """learning_log.json (auto-learn daemon) → lesson neurons."""
        d = _load("learning_log.json") or {}
        for it in d.get("learned", []):
            key = f"{it.get('topic')}:{it.get('ts')}"
            if not it.get("topic"):
                continue
            yield self._upsert(
                "learning_log", key, "lesson",
                f"studied: {str(it.get('topic'))[:180]}",
                f"Auto-learn ingested topic '{it.get('topic')}' kind={it.get('kind')} "
                f"ingested={it.get('ingested')} errors={it.get('errors')} ts={it.get('ts')}",
                f"The brain already studied '{it.get('topic')}' — recall before re-studying; "
                f"re-study only if the exam score on it has decayed.",
                origin="lesson", ref="trading/state/learning_log.json",
                now=float(it["ts"]) if it.get("ts") else None)

    # ── the full migration ─────────────────────────────────────────────────────
    def conv_features(self):
        """Implemented brain/trading FEATURES → skill neurons (R1 stitch, R24 action facet).

        The brain can only USE a capability it knows exists. This registers each shipped
        feature as an instruction-shaped skill neuron: what it is, and — the mandatory
        action facet — when to use it, how to activate it (flag), and how to verify. New
        features get appended here as they land so the web of neurons stays the single
        source of 'what this brain can do'."""
        for f in _FEATURE_CATALOG:
            yield self._upsert(
                "features", f["key"], "skill", f["title"][:200], f["body"],
                f["action"], origin="feature-registry", ref=f.get("ref", ""),
                confidence=0.6)

    def convert_all(self) -> dict:
        t0 = time.time()
        report = {name.removeprefix("conv_"): self._run(fn) for name, fn in [
            ("conv_file_memory", self.conv_file_memory),
            ("conv_skill_library", self.conv_skill_library),
            ("conv_strategy_foundry", self.conv_strategy_foundry),
            ("conv_hypotheses", self.conv_hypotheses),
            ("conv_news", self.conv_news),
            ("conv_journal", self.conv_journal),
            ("conv_decision_episodes", self.conv_decision_episodes),
            ("conv_research_docs", self.conv_research_docs),
            ("conv_learning_log", self.conv_learning_log),
            ("conv_features", self.conv_features),
        ]}
        report["secs"] = round(time.time() - t0, 2)
        report["store"] = self.store.status()
        return report

    # ── weave: fast one-pass linking over rare shared title tokens (R16) ──────
    def weave(self, *, max_df: int = 25, per_neuron: int = 6) -> dict:
        """Link neurons sharing a RARE title token (entity), capped per neuron."""
        t0 = time.time()
        index: dict[str, list[str]] = defaultdict(list)
        for n in self.store.all_neurons():
            for tok in _words(n.title):
                index[tok].append(n.id)
        made = 0
        counts: dict[str, int] = defaultdict(int)
        for tok, ids in index.items():
            if len(ids) < 2 or len(ids) > max_df:     # too common = noise, not entity
                continue
            anchor = ids[0]
            for other in ids[1:]:
                if counts[anchor] >= per_neuron and counts[other] >= per_neuron:
                    continue
                if self.store.link(anchor, other, "related"):
                    made += 1
                    counts[anchor] += 1
                    counts[other] += 1
        return {"links_made": made, "tokens_indexed": len(index),
                "secs": round(time.time() - t0, 2)}


def backfill(store: NeuronStore | None = None) -> dict:
    """Convert every store + weave the web. Idempotent; safe to re-run any time."""
    web = NeuronWeb(store)
    report = web.convert_all()
    report["weave"] = web.weave()
    report["store"] = web.store.status()
    return report


if __name__ == "__main__":                            # pragma: no cover
    print(json.dumps(backfill(), indent=2, default=str))
