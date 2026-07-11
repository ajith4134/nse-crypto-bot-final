"""Decision memory — every trade is a fully-provenanced EPISODE the brain recalls and learns from.

Stitched from vendored donors (map: research/decision-memory-stitch-map.md):
- FinMem (vendor/finmem/puppy/memorydb.py + memory_functions/): layered episodic store
  (shallow/mid/deep) — recency decay ``exp(-delta/recency_factor)``, importance decay
  ``importance *= 0.988``, outcome feedback ``importance += feedback * 5`` (their
  LinearImportanceScoreChange), compound retrieval score ``relevance + recency +
  min(importance,100)/100``, and threshold-based layer jumps (good episodes rise to
  deeper layers and survive longer; bad ones decay out of shallow).
- TradingAgents (vendor/tradingagents/tradingagents/agents/utils/memory.py + graph/
  reflection.py): the outcome-closure lifecycle — a decision is stored PENDING at entry,
  later RESOLVED with realized P&L, and a 2-4 sentence reflection is written and injected
  into future decisions (their get_past_context n_same/n_cross shape).
- Reflexion (vendored in trading/brain/gui) framing: the reflection is a verbal lesson,
  not a score — "gradient-free RL via language".
- qlib recorder pattern: one episode links three records — decision (entry context),
  attribution (which data drove it, from trading/brain/attribution.py), outcome.

Persistence: trading.state (decision_episodes.json). CPU-only, stdlib + core.llm.
"""
from __future__ import annotations

import math
import random
import time

from trading import state

FILE = "decision_episodes.json"

# FinMem layer semantics (vendor/finmem/puppy/memory_functions/decay.py + memorydb.py):
# per-layer recency half-life + importance-jump thresholds. Tuned to trade cadence
# (delta steps are ~hourly decay ticks, not days).
_LAYERS = {
    "shallow": {"recency_factor": 24.0},    # ~a day of relevance
    "mid": {"recency_factor": 24.0 * 7},    # ~a week
    "deep": {"recency_factor": 24.0 * 45},  # ~six weeks
}
_JUMP_UP = {"shallow": 75.0, "mid": 90.0}       # importance >= → promote
_JUMP_DOWN = {"mid": 40.0, "deep": 50.0}        # importance <  → demote
_CLEANUP = {"recency": 0.03, "importance": 4.0}  # both below → forget (shallow/mid only)
_IMPORTANCE_DECAY = 0.988                        # FinMem default importance_factor
_FEEDBACK_SCALE = 5.0                            # FinMem access_counter.py: += counter*5

# FinMem importance_score.py initial-importance sampling for the shallow layer
_INIT_IMPORTANCE = ([50.0] * 50 + [70.0] * 45 + [90.0] * 5)

# TradingAgents graph/reflection.py prompt, adapted from equity ratings to trades
_REFLECT_SYS = (
    "You are a trading analyst reviewing your own past decision now that the outcome is "
    "known. Write exactly 2-4 sentences of plain prose (no bullets, no headers, no "
    "markdown). Cover in order: 1) was the directional call correct (cite the P&L / R "
    "multiple), 2) which part of the entry thesis (signals, order-book psychology, "
    "strategy) held or failed, 3) one concrete lesson to apply to the next similar trade. "
    "Be specific and terse. Your output is stored verbatim in a decision log and will be "
    "read before future trades."
)


def _tokens(text: str) -> set:
    return {w for w in "".join(c.lower() if c.isalnum() else " " for c in str(text)).split()
            if len(w) > 2}


class DecisionMemory:
    """Layered episodic store of trade decisions with outcome closure + recall."""

    def __init__(self, persist: bool = True):
        self.persist = persist
        d = state.load_json(FILE, {}) if persist else {}
        self.episodes: list[dict] = d.get("episodes", [])
        self._seq = int(d.get("seq", 0))
        self._last_step = float(d.get("last_step", 0.0))

    # ── persistence ────────────────────────────────────────────────────────────────
    def _save(self) -> None:
        if self.persist:
            state.save_json(FILE, {"episodes": self.episodes, "seq": self._seq,
                                   "last_step": self._last_step})

    # ── qlib-style record 1: the DECISION (opened pending, TradingAgents lifecycle) ──
    def open_episode(self, *, symbol: str, market: str = "", segment: str = "",
                     direction: str = "", entry_price: float | None = None,
                     strategy: str = "", engine: str = "loop",
                     decision_snapshot: dict | None = None,
                     attribution: dict | None = None,
                     trade_id: str = "") -> str:
        self._seq += 1
        ep = {
            "episode_id": f"EP-{self._seq}",
            "trade_id": trade_id, "engine": engine,
            "ts": time.time(),
            "symbol": symbol, "market": market, "segment": segment,
            "direction": direction, "entry_price": entry_price, "strategy": strategy,
            "decision": decision_snapshot or {},          # record 1: full entry context
            "attribution": attribution or {},             # record 2: which data drove it
            "outcome": None,                              # record 3: filled at resolve()
            "reflection": "",
            "pending": True,
            # FinMem per-record scores — new episodes start shallow, recency 1.0
            "layer": "shallow",
            "importance": random.choice(_INIT_IMPORTANCE),
            "recency": 1.0, "delta": 0, "access": 0,
        }
        self.episodes.append(ep)
        self._save()
        return ep["episode_id"]

    def _claim_resolution(self, episode_id: str) -> bool:
        """Atomically flip pending→False on DISK under flock; True only for the claimant.

        The losing processes sync from the fresh store and skip their emit. Also adopts
        the on-disk episodes list so the claimant's later _save() doesn't resurrect rows
        another process already resolved."""
        import fcntl
        lock = state._path(f"{FILE}.lock")
        with open(lock, "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                d = state.load_json(FILE, {})
                eps = d.get("episodes", [])
                idx = next((i for i, e in enumerate(eps)
                            if e.get("episode_id") == episode_id), None)
                if idx is None or not eps[idx].get("pending"):
                    return False
                # splice MY object over the disk copy: adopting the disk list must not
                # clobber the claimant's un-persisted in-memory mutations (importance/
                # access updates between open and close), and callers holding the object
                # must observe the claim — a naive adopt lost the FinMem layer jump
                # (test_loss_demotes_and_layer_jumps, 2026-07-11).
                mine = next((e for e in self.episodes
                             if e.get("episode_id") == episode_id), None)
                if mine is not None:
                    eps[idx] = mine
                eps[idx]["pending"] = False
                state.save_json(FILE, d)
                self.episodes = eps
                self._seq = int(d.get("seq", self._seq))
                return True
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)

    def find(self, episode_id: str = "", trade_id: str = "") -> dict | None:
        for ep in reversed(self.episodes):
            if (episode_id and ep["episode_id"] == episode_id) or \
               (trade_id and ep.get("trade_id") and ep["trade_id"] == trade_id):
                return ep
        return None

    # ── record 3: OUTCOME closure + reflection (TradingAgents update_with_outcome) ──
    def resolve(self, *, episode_id: str = "", trade_id: str = "",
                net_pnl: float = 0.0, r_multiple: float | None = None,
                exit_price: float | None = None, exit_reason: str = "",
                brain_correct: bool | None = None, use_llm: bool = True) -> dict | None:
        ep = self.find(episode_id, trade_id)
        if ep is None or not ep.get("pending"):
            return ep                          # idempotent: polled ingest paths re-call this
        if self.persist:
            # cross-process idempotency: several loop processes ingest closed trades, each
            # with its own boot-time singleton, so the in-memory pending check alone re-emits
            # the same close once per process (3× duplicate feed events, 2026-07-10)
            if not self._claim_resolution(ep["episode_id"]):
                ep["pending"] = False          # another process already resolved it
                return ep
            ep = self.find(ep["episode_id"]) or ep   # re-find in the freshly adopted store
        ep["outcome"] = {"net_pnl": round(float(net_pnl), 6), "r_multiple": r_multiple,
                         "exit_price": exit_price, "exit_reason": exit_reason,
                         "brain_correct": brain_correct, "closed_ts": time.time()}
        ep["pending"] = False
        # FinMem feedback: winning episodes gain importance (and survive/promote),
        # losers lose it (and decay out) — magnitude scaled by |R| so big outcomes
        # teach more than noise around zero.
        fb = 1.0 if net_pnl > 0 else (-1.0 if net_pnl < 0 else 0.0)
        weight = 1.0 + min(abs(r_multiple or 0.0), 3.0)
        ep["access"] += int(fb)
        ep["importance"] = max(0.0, ep["importance"] + fb * _FEEDBACK_SCALE * weight)
        self._maybe_jump(ep)
        ep["reflection"] = self._reflect(ep, use_llm=use_llm)
        self._save()
        # mind stream: credit assignment on close — WHICH learning/strategy drove this trade
        # and what the brain took away from it (the reflection lesson).
        try:
            from trading.brain import mind_events
            won = float(net_pnl) > 0
            strat = ep.get("strategy") or (ep.get("decision") or {}).get("strategy") or "?"
            mind_events.emit(
                "trade_credit",
                f"{'Profitable' if won else 'Losing'} close: {ep['symbol']} "
                f"{ep['direction']} via {strat} → net {float(net_pnl):+.4f}"
                + (f" (R {r_multiple})" if r_multiple is not None else ""),
                detail=str(ep.get("reflection") or "")[:700],
                salience=0.85 if won else 0.55,
                data={"symbol": ep.get("symbol"), "strategy": strat,
                      "net_pnl": float(net_pnl), "won": won})
        except Exception:
            pass
        return ep

    def _reflect(self, ep: dict, *, use_llm: bool) -> str:
        out, dec = ep["outcome"], ep.get("decision") or {}
        att = ep.get("attribution") or {}
        top = ", ".join(f"{a['feature']} ({a['impact']:+.3f})"
                        for a in (att.get("top") or [])[:3])
        summary = (f"{ep['symbol']} {ep['direction']} @ {ep.get('entry_price')} "
                   f"[{ep.get('strategy') or dec.get('strategy') or '?'}] → "
                   f"net {out['net_pnl']:+.4f} (R {out['r_multiple']}) "
                   f"exit={out.get('exit_reason') or '?'} "
                   f"brain_correct={out.get('brain_correct')}"
                   + (f"; top drivers: {top}" if top else ""))
        if use_llm:
            try:
                from core.llm import chat
                txt = chat([{"role": "system", "content": _REFLECT_SYS},
                            {"role": "user", "content":
                             f"{summary}\n\nEntry decision context (JSON-ish): "
                             f"{str(dec)[:1500]}"}], max_tokens=180, temperature=0.3)
                if txt and len(txt.strip()) > 20:
                    return txt.strip()
            except Exception:
                pass
        # deterministic fallback (no LLM configured / offline): still a real lesson line
        verdict = "correct" if out["net_pnl"] > 0 else "wrong"
        return (f"The {ep['direction']} call on {ep['symbol']} was {verdict} "
                f"(net {out['net_pnl']:+.4f}, R {out['r_multiple']}). "
                + (f"Main drivers at entry: {top}. " if top else "")
                + f"Exit reason: {out.get('exit_reason') or 'n/a'}.")

    # ── FinMem decay + layer maintenance (BrainDB.step) ─────────────────────────────
    def step(self, force: bool = False) -> int:
        """One decay tick (~hourly, self-throttled). Returns episodes forgotten."""
        now = time.time()
        if not force and now - self._last_step < 3600:
            return 0
        self._last_step = now
        dropped = 0
        keep = []
        for ep in self.episodes:
            ep["delta"] += 1
            rf = _LAYERS[ep["layer"]]["recency_factor"]
            ep["recency"] = math.exp(-(ep["delta"] / rf))
            ep["importance"] *= _IMPORTANCE_DECAY
            self._maybe_jump(ep)
            faded = (ep["recency"] < _CLEANUP["recency"]
                     and ep["importance"] < _CLEANUP["importance"])
            if faded and ep["layer"] != "deep" and not ep.get("pending"):
                dropped += 1
                continue
            keep.append(ep)
        self.episodes = keep
        self._save()
        return dropped

    def _maybe_jump(self, ep: dict) -> None:
        lay = ep["layer"]
        if lay in _JUMP_UP and ep["importance"] >= _JUMP_UP[lay]:
            ep["layer"] = {"shallow": "mid", "mid": "deep"}[lay]
            ep["recency"], ep["delta"] = 1.0, 0     # FinMem accept_jump resets recency
        elif lay in _JUMP_DOWN and ep["importance"] < _JUMP_DOWN[lay]:
            ep["layer"] = {"mid": "shallow", "deep": "mid"}[lay]

    # ── recall (FinMem compound score: relevance + recency + importance/100) ────────
    def recall(self, *, symbol: str = "", query: str = "", k: int = 5,
               resolved_only: bool = True) -> list[dict]:
        self.step()
        q = _tokens(f"{symbol} {query}")
        scored = []
        for ep in self.episodes:
            if resolved_only and ep.get("pending"):
                continue
            text = f"{ep['symbol']} {ep['direction']} {ep.get('strategy','')} " \
                   f"{ep.get('reflection','')} {str(ep.get('decision'))[:400]}"
            t = _tokens(text)
            relevance = len(q & t) / (len(q) or 1)
            if symbol and ep["symbol"] == symbol:
                relevance += 0.5                     # same-instrument boost
            score = relevance + ep["recency"] + min(ep["importance"], 100.0) / 100.0
            scored.append((score, ep))
        scored.sort(key=lambda s: -s[0])
        return [dict(ep, _score=round(sc, 4)) for sc, ep in scored[:k]]

    # ── TradingAgents get_past_context: lessons string for LLM prompts ───────────────
    def past_context(self, symbol: str, n_same: int = 5, n_cross: int = 3) -> str:
        done = [e for e in self.episodes if not e.get("pending")]
        same = [e for e in reversed(done) if e["symbol"] == symbol][:n_same]
        cross = [e for e in reversed(done) if e["symbol"] != symbol][:n_cross]
        parts = []
        if same:
            parts.append(f"Past trades on {symbol} (most recent first):")
            parts += [f"- {e['direction']} @{e.get('entry_price')} → "
                      f"{e['outcome']['net_pnl']:+.4f} | {e.get('reflection','')}" for e in same]
        if cross:
            parts.append("Recent cross-symbol lessons:")
            parts += [f"- {e['symbol']}: {e.get('reflection','')[:300]}" for e in cross]
        return "\n".join(parts)

    # ── numeric bias for the non-LLM deciders: recalled win-rate → confidence nudge ──
    def bias(self, symbol: str, direction: str = "") -> dict:
        """Importance·recency-weighted win-rate of similar resolved episodes → [-1, 1]."""
        self.step()
        wins = tot = 0.0
        n = 0
        for ep in self.episodes:
            if ep.get("pending") or ep["symbol"] != symbol:
                continue
            if direction and ep.get("direction") and ep["direction"] != direction:
                continue
            w = ep["recency"] + min(ep["importance"], 100.0) / 100.0
            tot += w
            n += 1
            if (ep["outcome"] or {}).get("net_pnl", 0) > 0:
                wins += w
        if n == 0 or tot <= 0:
            return {"n": 0, "win_rate": None, "bias": 0.0}
        wr = wins / tot
        return {"n": n, "win_rate": round(wr, 4), "bias": round((wr - 0.5) * 2.0, 4)}

    def stats(self) -> dict:
        done = [e for e in self.episodes if not e.get("pending")]
        wins = sum(1 for e in done if (e["outcome"] or {}).get("net_pnl", 0) > 0)
        by_layer = {}
        for e in self.episodes:
            by_layer[e["layer"]] = by_layer.get(e["layer"], 0) + 1
        return {"episodes": len(self.episodes), "pending": len(self.episodes) - len(done),
                "resolved": len(done), "wins": wins,
                "win_rate": round(wins / len(done), 4) if done else None,
                "by_layer": by_layer,
                "reflections": sum(1 for e in done if e.get("reflection"))}


_SINGLETON: DecisionMemory | None = None


def get_memory() -> DecisionMemory:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = DecisionMemory()
    return _SINGLETON
