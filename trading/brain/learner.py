"""trading/brain/learner.py — the brain's self-directed LEARNING + SELF-EVALUATION.

Stage 4 (learn): download & read books/papers/articles — arXiv papers (PDF via pypdf),
web articles (trafilatura) — on math / finance / markets AND non-trading topics, ingesting
them into the KnowledgeBrain so recall + the trading pipeline get smarter over time.

Stage 5 (self-evaluate): quiz ITSELF on what it ingested (incl. non-trading topics) via the
FSRS MasteryQuiz and track a rising mastery curve — the honest "is it actually learning?" test.

Reuse-first GLUE over: memory/librarian.py (arxiv/ddgs/trafilatura), memory/brain.py
(KnowledgeBrain ingest/recall/stats), memory/self_quiz.py (MasteryQuiz), pypdf (PDF text).
Emits ephemeral feed events ("read paper X → learned Y"). Best-effort; never raises.
"""
from __future__ import annotations

import time

_LOG_FILE = "learning_log.json"


class KnowledgeLearner:
    def __init__(self):
        self._brain = None

    def brain(self):
        if self._brain is None:
            from memory.brain import KnowledgeBrain
            self._brain = KnowledgeBrain()
        return self._brain

    # ── persistence of what it has learned ──────────────────────────────────────
    def _log(self, entry: dict) -> None:
        try:
            from trading import state
            blob = state.load_json(_LOG_FILE, {"learned": []})
            blob["learned"] = (blob.get("learned", []) + [entry])[-200:]
            state.save_json(_LOG_FILE, blob)
        except Exception:
            pass

    def _log_all(self) -> list:
        try:
            from trading import state
            return state.load_json(_LOG_FILE, {"learned": []}).get("learned", [])
        except Exception:
            return []

    # ── Stage 4: download + read → ingest ───────────────────────────────────────
    def _read_pdf(self, path: str) -> str:
        try:
            from pypdf import PdfReader
            r = PdfReader(path)
            return "\n".join((p.extract_text() or "") for p in r.pages[:40])   # cap 40 pages
        except Exception:
            return ""

    def ingest_pdf(self, url_or_path: str, title: str = "") -> dict:
        """Download (if URL) + read a PDF (books/papers) → ingest into KnowledgeBrain."""
        import os, tempfile
        from trading.brain import activity_feed as feed
        path = url_or_path
        tmp = None
        try:
            if url_or_path.startswith("http"):
                import urllib.request
                tmp = tempfile.mktemp(suffix=".pdf")
                req = urllib.request.Request(url_or_path, headers={
                    "User-Agent": "Mozilla/5.0", "Accept": "application/pdf,*/*"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    ctype = (r.headers.get_content_type() or "").lower()
                    blob = r.read()
                if not (ctype == "application/pdf" or blob[:5] == b"%PDF-"):
                    return {"ok": False, "reason": f"not a pdf (content-type {ctype})",
                            "source": url_or_path}
                with open(tmp, "wb") as f:
                    f.write(blob)
                path = tmp
            text = self._read_pdf(path)
            if len(text) < 200:
                return {"ok": False, "reason": "no extractable text", "source": url_or_path}
            ttl = title or os.path.basename(url_or_path)[:80]
            self.brain().ingest_text(ttl, text[:200000])
            entry = {"kind": "pdf", "title": ttl, "chars": len(text), "source": url_or_path,
                     "ts": time.time()}
            self._log(entry)
            feed.emit("learned", f"Read PDF: {ttl}", learned=f"ingested {len(text)} chars into memory")
            return {"ok": True, **entry}
        except Exception as e:
            return {"ok": False, "reason": str(e)[:160], "source": url_or_path}
        finally:
            if tmp:
                try: os.remove(tmp)
                except Exception: pass

    def learn_topic(self, topic: str, *, papers: int = 1, articles: int = 1) -> dict:
        """Autonomously learn a topic (trading OR general): pull arXiv papers (PDF) + web
        articles, ingest into KnowledgeBrain. Returns what it learned."""
        from trading.brain import activity_feed as feed
        from memory import librarian as lib
        ingested = []
        # arXiv papers — _arxiv_search returns {title, url(=abs page), body(=abstract)}.
        # Derive the PDF URL from the abs URL (/abs/ → /pdf/); if the PDF fetch fails, ingest
        # the abstract text (always available) so learning never silently no-ops.
        try:
            for p in (lib._arxiv_search(topic, max_results=papers) or [])[:papers]:
                abs_url = p.get("url") or ""
                title = (p.get("title") or topic)[:80]
                pdf_url = abs_url.replace("/abs/", "/pdf/") if "/abs/" in abs_url else ""
                r = self.ingest_pdf(pdf_url, title=title) if pdf_url else {"ok": False}
                if r.get("ok"):
                    ingested.append({"type": "paper", "title": title})
                elif p.get("body"):                       # reliable fallback: the abstract
                    self.brain().ingest_text(title, p["body"])
                    ingested.append({"type": "abstract", "title": title})
        except Exception:
            pass
        # web articles (trafilatura clean-text)
        try:
            for r in (lib._ddgs_search(topic, max_results=articles + 2) or [])[:articles]:
                url = r.get("href") or r.get("url") or ""
                txt = lib._trafilatura_extract(url) if url else ""
                if len(txt) > 300:
                    self.brain().ingest_text((r.get("title") or topic)[:80], txt[:60000])
                    ingested.append({"type": "article", "title": (r.get("title") or topic)[:60]})
        except Exception:
            pass
        self._log({"kind": "topic", "topic": topic, "ingested": ingested, "ts": time.time()})
        feed.emit("learned", f"Studied: {topic}", learned=f"ingested {len(ingested)} sources")
        return {"topic": topic, "ingested": ingested, "n": len(ingested)}

    # ── Stage 5: self-evaluation (incl. non-trading) ────────────────────────────
    def self_evaluate(self, topics: list[str] | None = None, *, rounds: int = 5) -> dict:
        """Quiz itself (FSRS MasteryQuiz) on ingested knowledge across topics (trading AND
        non-trading) → rising mastery curve. Honest 'is it learning?' metric."""
        try:
            from memory.self_quiz import MasteryQuiz
        except Exception as e:
            return {"available": False, "reason": str(e)[:120]}
        topics = topics or ["market microstructure", "probability", "options greeks",
                            "reinforcement learning", "world history"]
        items = []
        for t in topics:
            try:
                hits = self.brain().recall(t, k=1)
                if hits:
                    items.append((t, hits[0].get("snippet") or hits[0].get("text", "")))
            except Exception:
                continue
        if not items:
            return {"available": True, "n_topics": 0,
                    "note": "no ingested knowledge yet — run learn_topic first"}
        try:
            q = MasteryQuiz(brain=self.brain())           # dataclass requires the brain (recall)
            curve = q.mastery_curve(items, rounds=rounds)
            last = curve[-1] if isinstance(curve, list) and curve else {}
            return {"available": True, "n_topics": len(items), "topics": [t for t, _ in items],
                    "rounds": len(curve) if isinstance(curve, list) else 0,
                    "mastery_curve": curve,
                    "final_accuracy": last.get("accuracy"),
                    "final_retention": last.get("retention_at_horizon"),
                    "rising": bool(isinstance(curve, list) and len(curve) >= 2
                                   and curve[-1].get("retention_at_horizon", 0)
                                   >= curve[0].get("retention_at_horizon", 0))}
        except Exception as e:
            return {"available": True, "n_topics": len(items), "error": str(e)[:120]}

    def status(self) -> dict:
        """NON-BLOCKING: reports KnowledgeBrain stats only if it's ALREADY warm (building it
        loads a heavy embedding model — never do that in a status/request path). The learning
        log is cheap file state and always available."""
        log = self._log_all()
        stats, warming = {}, False
        if self._brain is not None:
            try:
                stats = self._brain.stats()
            except Exception:
                stats = {}
        else:
            warming = True
        return {"knowledge_stats": stats, "brain_warming": warming, "n_learned": len(log),
                "recent": [{"kind": e.get("kind"), "title": e.get("title") or e.get("topic"),
                            "ts": e.get("ts")} for e in log[-10:][::-1]]}


_LEARNER: KnowledgeLearner | None = None


def get_learner() -> KnowledgeLearner:
    global _LEARNER
    if _LEARNER is None:
        _LEARNER = KnowledgeLearner()
    return _LEARNER
