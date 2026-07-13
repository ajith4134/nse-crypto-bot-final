"""trading/brain/researcher.py — Phase-T8 (deferred A2): lightweight autonomous web research.

Why custom (not gpt-researcher): the heavy `gpt-researcher` package would downgrade numpy
and pull ~60 transitive deps. We deliver the same capability — autonomously search the web,
read snippets, and synthesise a finance-research brief — from pieces already installed:

  • Web search  → `ddgs` (DuckDuckGo): `DDGS().text(q, max_results=n)` → dicts
                  {title, href, body}. Live network, used only when actually searching.
  • Summarising → the project's own LLM client `core/llm.py` (`llm.chat(...)`), which
                  auto-selects whichever provider key is present in the gitignored .env.

Offline-first / honest: both the searcher and summariser are INJECTED, so tests run with
stubs (no network, no LLM). Defaults wire the real pieces lazily (imported inside the
default callables) so `import` itself never touches the network. If no LLM is configured we
fall back to a concatenated EXTRACTIVE digest of the snippets (still useful) and report
`llm_used=False`; if no sources are found we report `available=False`. Secrets-safe: LLM
keys live in core.llm/.env and are never logged or returned.
"""
from __future__ import annotations


def _default_searcher(query: str, *, max_results: int = 6) -> list[dict]:
    """Real web search via ddgs (lazy import; network). Degrades to [] on any failure."""
    try:
        from ddgs import DDGS
        rows = DDGS().text(query, max_results=max_results) or []
    except Exception:
        return []
    out: list[dict] = []
    for r in rows:
        out.append({
            "title": (r.get("title") or "").strip(),
            "href": (r.get("href") or r.get("url") or "").strip(),
            "body": (r.get("body") or "").strip(),
        })
    return out


def _default_summarizer(prompt: str) -> str:
    """Real summarisation via core.llm (lazy import). Returns "" when no LLM configured."""
    try:
        from core import llm
        try:
            return (llm.chat([{"role": "user", "content": prompt}],
                             max_tokens=600, temperature=0.3) or "").strip()
        except llm.NoLLMConfigured:
            return ""
    except Exception:
        return ""


class AutonomousResearcher:
    """Search the web for a query, read the snippets, and synthesise a finance brief.

    Both dependencies are injectable for offline testing:
      • searcher(query)   -> list[{title, href, body}]   (default: ddgs, try/except -> [])
      • summarizer(prompt) -> str                          (default: core.llm.chat, "" if none)
    """

    def __init__(self, searcher=None, summarizer=None, *, max_results: int = 6):
        self.max_results = max_results
        self._searcher_injected = searcher is not None
        self._summarizer_injected = summarizer is not None
        if searcher is None:
            searcher = lambda q: _default_searcher(q, max_results=self.max_results)
        self.searcher = searcher
        self.summarizer = summarizer if summarizer is not None else _default_summarizer

    # --- search -----------------------------------------------------------------
    def search(self, query: str) -> list[dict]:
        """Run the (gated) web search → list of {title, href, body}. [] offline w/o searcher."""
        try:
            results = self.searcher(query) or []
        except Exception:
            return []
        cleaned: list[dict] = []
        for r in results:
            cleaned.append({
                "title": str(r.get("title", "")).strip(),
                "href": str(r.get("href", r.get("url", ""))).strip(),
                "body": str(r.get("body", "")).strip(),
            })
        return cleaned[: self.max_results]

    # --- research ---------------------------------------------------------------
    @staticmethod
    def _prompt(query: str, results: list[dict]) -> str:
        snippets = "\n".join(
            f"[{i+1}] {r['title']}\n{r['body']}\n({r['href']})"
            for i, r in enumerate(results)
        )
        return (
            "You are a financial research analyst. Using ONLY the web snippets below, write a "
            "concise, factual brief that answers the research question. Cover key catalysts, "
            "risks, sentiment, and any notable numbers. Cite snippet numbers like [1], [2]. "
            "If the snippets are insufficient, say so plainly.\n\n"
            f"Research question: {query}\n\nWeb snippets:\n{snippets}\n\nBrief:"
        )

    @staticmethod
    def _extractive_digest(query: str, results: list[dict]) -> str:
        """No-LLM fallback: a concatenated extractive digest of the snippets."""
        lines = [f"Research digest for: {query}", f"(extractive — no LLM; {len(results)} sources)"]
        for i, r in enumerate(results):
            body = r["body"][:400]
            title = r["title"] or "(untitled)"
            lines.append(f"[{i+1}] {title}: {body}".rstrip())
        return "\n".join(lines)

    def research(self, query: str) -> dict:
        """Search → synthesise a finance brief (LLM) or extractive digest (no LLM)."""
        # recall-before-research (Brain Ultra Upgrade R22): what does the brain already
        # KNOW about this? Records the use; known context rides in the result so callers
        # (and the researcher's own prompt) can build on prior knowledge, not restart it.
        known = None
        try:
            from trading.brain import brain_os as _bos       # OS-4: kernel-routed surface
            known = _bos.consult(query, domain="research", k=3)
            if not known["ids"]:
                known = None
        except Exception:
            known = None
        results = self.search(query)
        sources = [{"title": r["title"], "href": r["href"]} for r in results]
        available = len(results) > 0

        if not available:
            return {
                "query": query, "n_sources": 0, "summary": "",
                "sources": [], "available": False, "llm_used": False,
                "prior_knowledge": known,
            }

        summary = ""
        try:
            summary = (self.summarizer(self._prompt(query, results)) or "").strip()
        except Exception:
            summary = ""
        llm_used = bool(summary)
        if not summary:
            summary = self._extractive_digest(query, results)

        return {
            "query": query, "n_sources": len(results), "summary": summary,
            "sources": sources, "available": True, "llm_used": llm_used,
            "prior_knowledge": known,
        }

    # --- deep research (gpt-researcher, Phase D upgrade) --------------------------
    # gpt-researcher is now installed and importable (approved 2026-07-02); per the
    # dep-weight-by-capability rule the heavy engine (multi-source cited reports) is
    # PREFERRED when configured, and this method degrades to research() otherwise.
    def deep_research(self, query: str, *, report_type: str = "research_report",
                      reflect: bool = True, heavy: bool | None = None) -> dict:
        """Autonomous multi-source cited research via gpt-researcher; falls back to
        the light ddgs+LLM path when the heavy engine is unavailable/unconfigured.
        With reflect=True the report gets a Reflexion-style self-critique pass
        (pattern from vendor/reflexion) through the same summarizer LLM."""
        import os
        report, sources, engine = "", [], "light"
        if heavy is None:                                  # enabled-when-configured gate
            heavy = bool(os.environ.get("OPENAI_API_KEY") or
                         os.environ.get("GPT_RESEARCHER") == "1")
        try:
            if not heavy:
                raise RuntimeError("heavy engine not configured")
            import asyncio
            from gpt_researcher import GPTResearcher
            os.environ.setdefault("RETRIEVER", "duckduckgo")   # keyless retriever

            async def _run():
                gr = GPTResearcher(query=query, report_type=report_type)
                await gr.conduct_research()
                return await gr.write_report(), gr.get_source_urls()

            report, sources = asyncio.run(_run())
            engine = "gpt-researcher"
        except Exception:
            pass
        if not (report or "").strip():                     # degrade, never drop capability
            light = self.research(query)
            report = light["summary"]
            sources = [s["href"] for s in light["sources"]]
            engine = "light(ddgs+llm)" if light["llm_used"] else "light(extractive)"
        critique = ""
        if reflect and report:
            try:                                            # Reflexion loop: critique→revise
                critique = (self.summarizer(
                    "You are a Reflexion critic. In <=5 terse lines list weaknesses, missing "
                    "angles or unsupported claims in this research report:\n\n" + report[:4000])
                    or "").strip()
            except Exception:
                critique = ""
        return {"query": query, "report": report, "sources": sources,
                "engine": engine, "critique": critique,
                "available": bool((report or "").strip())}

    def research_symbol(self, symbol: str, market: str = "stock") -> dict:
        """Convenience: research a tradeable symbol's recent news/catalysts."""
        m = (market or "stock").lower()
        if m in ("crypto", "coin", "spot", "futures", "perp"):
            query = f"{symbol} crypto news catalysts price outlook"
        else:
            query = f"{symbol} stock news catalysts earnings outlook"
        out = self.research(query)
        out["symbol"] = symbol
        out["market"] = m
        return out

    # --- status -----------------------------------------------------------------
    def status(self) -> dict:
        """JSON-able status: which searcher and which LLM model are wired."""
        if self._searcher_injected:
            searcher = "injected"
        else:
            try:
                import importlib.util
                searcher = "ddgs" if importlib.util.find_spec("ddgs") else "none"
            except Exception:
                searcher = "none"

        if self._summarizer_injected:
            llm_name = "injected"
        else:
            llm_name = None
            try:
                from core import llm
                am = llm.active_model()
                llm_name = am[0] if am else None
            except Exception:
                llm_name = None

        return {"searcher": searcher, "llm": llm_name}
