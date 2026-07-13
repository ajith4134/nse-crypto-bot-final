"""trading/brain/brain_os.py — the Brain-OS kernel + its own RAM (OS-1).

Owner ask (2026-07-13): "the combined brain must act as an OS with its own RAM."
Design: research/brain-os/DESIGN.md (memory: project-brain-as-os-own-ram).

OS-1 delivers the two foundational pieces — a resident KERNEL and its RAM WORKING
MEMORY — as a cohering layer over what already exists, not a rewrite:

  • WorkingMemory  — the brain's RAM: pinned (never-evicted) hot neurons, an LRU-and-
    byte-BOUNDED "swap-in" set of recently touched neurons, the current focus, a scratch
    blackboard for lobe↔lobe messages, and ring buffers of recent percepts/decisions/
    lessons. bytes_used() is a real, honest estimate; the buffer is bounded so it can
    never starve the box (the 31→42GB swap incident is why every RAM buffer here is capped).
  • BrainKernel   — boots once, holds the WorkingMemory + the existing singletons
    (get_store / get_brain / get_learn_loop / get_evolver), and exposes ONE call surface,
    syscall(name, **args), so lobes stop importing peers ad-hoc. boot() is idempotent and
    restores focus + pins across restarts from trading/state/brain_os.json.

Honest architecture note (DESIGN.md §8): the crypto/NSE funnels and the live-loop are
SEPARATE OS processes, so this in-RAM kernel cannot literally share their objects. The
kernel runs inside the dashboard process (where the store/learn-loop/evolver already live
as threads); cross-process lobes are represented by state-file heartbeats in OS-2's
process table, never by shared memory. OS-1 does not touch other processes.
"""
from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict, deque

_STATE_FILE = "brain_os.json"

DEFAULT_MAX_BYTES = 64 * 1024 * 1024      # 64 MB hot working set cap (bounded RAM)
DEFAULT_RING = 256                        # recent percepts/decisions/lessons kept


def _sizeof(obj) -> int:
    """Cheap, honest byte estimate — JSON length of the serialisable payload."""
    try:
        return len(json.dumps(obj, default=str, ensure_ascii=False).encode("utf-8"))
    except Exception:
        return len(str(obj).encode("utf-8", "ignore"))


class WorkingMemory:
    """The brain's RAM. Bounded, thread-safe, honest about its own size."""

    def __init__(self, *, max_bytes: int = DEFAULT_MAX_BYTES, ring: int = DEFAULT_RING):
        self.max_bytes = int(max_bytes)
        self._lock = threading.RLock()
        self.pinned: "OrderedDict[str, dict]" = OrderedDict()   # never evicted
        self._hot: "OrderedDict[str, dict]" = OrderedDict()     # LRU, evictable
        self.focus: dict = {}                                   # current goal/segment/topic
        self.scratch: dict = {}                                 # blackboard: lobe -> message
        self.percepts: deque = deque(maxlen=ring)
        self.decisions: deque = deque(maxlen=ring)
        self.lessons: deque = deque(maxlen=ring)
        self.evictions = 0

    # ── the hot set (RAM residency) ───────────────────────────────────────────
    def pin(self, nid: str, obj: dict) -> None:
        with self._lock:
            self._hot.pop(nid, None)
            self.pinned[nid] = obj

    def unpin(self, nid: str) -> None:
        with self._lock:
            self.pinned.pop(nid, None)

    def load(self, nid: str, obj: dict) -> None:
        """Swap a neuron into the LRU hot set, evicting coldest over the byte cap."""
        with self._lock:
            if nid in self.pinned:
                return
            self._hot[nid] = obj
            self._hot.move_to_end(nid)
            self._evict_locked()

    def get(self, nid: str) -> dict | None:
        with self._lock:
            if nid in self.pinned:
                return self.pinned[nid]
            if nid in self._hot:
                self._hot.move_to_end(nid)             # touch = most-recently-used
                return self._hot[nid]
            return None

    def _evict_locked(self) -> None:
        while self._hot and self.bytes_used(_locked=True) > self.max_bytes:
            self._hot.popitem(last=False)              # drop least-recently-used
            self.evictions += 1

    # ── focus + blackboard + rings ────────────────────────────────────────────
    def set_focus(self, **kw) -> dict:
        with self._lock:
            self.focus.update({k: v for k, v in kw.items() if v is not None})
            self.focus["ts"] = time.time()
            return dict(self.focus)

    def post(self, lobe: str, message) -> None:
        with self._lock:
            self.scratch[str(lobe)] = {"msg": message, "ts": time.time()}

    def read(self, lobe: str):
        with self._lock:
            return self.scratch.get(str(lobe))

    def remember(self, kind: str, item) -> None:
        buf = {"percept": self.percepts, "decision": self.decisions,
               "lesson": self.lessons}.get(kind)
        if buf is None:
            raise ValueError(f"unknown ring '{kind}' (percept|decision|lesson)")
        with self._lock:
            buf.append({"item": item, "ts": time.time()})

    def recent(self, kind: str, n: int = 20) -> list:
        buf = {"percept": self.percepts, "decision": self.decisions,
               "lesson": self.lessons}.get(kind)
        if buf is None:
            raise ValueError(f"unknown ring '{kind}'")
        with self._lock:
            return list(buf)[-int(n):]

    # ── honest size accounting ────────────────────────────────────────────────
    def bytes_used(self, *, _locked: bool = False) -> int:
        def _sum():
            b = sum(_sizeof(o) for o in self.pinned.values())
            b += sum(_sizeof(o) for o in self._hot.values())
            b += _sizeof(self.focus) + _sizeof(self.scratch)
            b += sum(_sizeof(x) for x in self.percepts)
            b += sum(_sizeof(x) for x in self.decisions)
            b += sum(_sizeof(x) for x in self.lessons)
            return b
        if _locked:
            return _sum()
        with self._lock:
            return _sum()

    def snapshot(self) -> dict:
        with self._lock:
            return {"pinned": len(self.pinned), "hot": len(self._hot),
                    "bytes_used": self.bytes_used(_locked=True), "max_bytes": self.max_bytes,
                    "evictions": self.evictions, "focus": dict(self.focus),
                    "percepts": len(self.percepts), "decisions": len(self.decisions),
                    "lessons": len(self.lessons), "blackboard_keys": list(self.scratch)}


# ── process table (OS-2): honest per-lobe liveness ───────────────────────────
# Cross-process lobes (funnels, live-loop) can't share this RAM — they are represented
# by the freshness of a state file each writes (the flow_health pattern), never faked.
PROCESS_SPECS = [
    {"name": "crypto-funnel", "kind": "funnel",
     "files": ["ui_market.json", "crypto_entry_meta.json"], "budget": 1800},
    {"name": "nse-funnel", "kind": "funnel",
     "files": ["broker_sense_nse_trades.json"], "budget": 3600},
    {"name": "school", "kind": "lobe", "files": ["school.json"], "budget": 86400},
    {"name": "evolution", "kind": "lobe",
     "files": ["instruction_evolution.json"], "budget": 86400},
]


def _file_age(fname: str, now: float) -> float | None:
    import os
    from pathlib import Path
    from trading import state
    p = Path(fname) if str(fname).startswith("/") else state.STATE_DIR / fname
    try:
        return now - os.path.getmtime(p)
    except OSError:
        return None                                    # missing = honest "no heartbeat"


def _proc_state(age: float | None, budget: float) -> str:
    if age is None:
        return "STOPPED"                               # no heartbeat file at all
    if age <= budget:
        return "RUNNING"
    if age <= 3 * budget:
        return "SLEEPING"                              # stale but recent — likely idle
    return "DEAD"                                      # long past budget (loop_keeper may respawn)


# ── attention scheduler (OS-3): pick the next lobe to attend by focus + fairness ──
# The brain can't be everywhere at once; tick() ranks its lobes and picks ONE to attend
# next. A lobe matching the current focus is boosted; a lobe not attended in a while is
# boosted too (round-robin fairness) so nothing starves. This is advisory scheduling —
# the in-process learn-loop ticks it live; cross-process funnels read next_lobe() to yield.
FOCUS_BOOST = 10.0
FAIRNESS = 0.5
SCHED_LOBES = [
    {"name": "crypto-funnel", "match": {"segment": "crypto"}, "base": 2.0},
    {"name": "nse-funnel", "match": {"segment": "nse"}, "base": 2.0},
    {"name": "learn-loop", "match": {"topic": "learn"}, "base": 1.5},
    {"name": "school", "match": {"topic": "study"}, "base": 1.0},
    {"name": "evolution", "match": {"topic": "evolve"}, "base": 1.0},
]


def _focus_match(lobe: dict, focus: dict) -> bool:
    return bool(lobe["match"]) and all(focus.get(k) == v for k, v in lobe["match"].items())


class BrainKernel:
    """Resident kernel: one working memory + one syscall surface over the lobes."""

    def __init__(self, store=None, *, max_bytes: int = DEFAULT_MAX_BYTES):
        self._store = store
        self._evolver = None
        self.wm = WorkingMemory(max_bytes=max_bytes)
        self.booted_ts: float | None = None
        self.boots = 0
        self.tick_no = 0
        self.last_sched: dict = {}                      # lobe -> tick it was last attended
        self._lock = threading.RLock()

    # ── lazy access to the existing singletons (reuse-first) ──────────────────
    @property
    def store(self):
        if self._store is None:
            from memory.neurons import get_store
            self._store = get_store()
        return self._store

    def evolver(self):
        if self._evolver is None:
            from trading.brain.evolution import InstructionEvolver
            from trading.brain.instructions import InstructionEngine
            self._evolver = InstructionEvolver(InstructionEngine(self.store))
        return self._evolver

    # ── boot: idempotent; warms the store, restores RAM from disk ─────────────
    def boot(self, *, now: float | None = None) -> dict:
        now = time.time() if now is None else float(now)
        with self._lock:
            _ = self.store.status()                    # warm the RAM-cached store
            st = self._load_state()
            if st.get("focus"):
                self.wm.set_focus(**{k: v for k, v in st["focus"].items() if k != "ts"})
            for nid in st.get("pinned", []):
                n = self.store.get(nid)
                if n is not None:
                    self.wm.pin(nid, n.to_dict())      # re-pin surviving neurons
            self.boots = int(st.get("boots", 0)) + 1
            if self.booted_ts is None:
                self.booted_ts = now
            self._persist()
        return self.top()

    def uptime_secs(self, *, now: float | None = None) -> float:
        if self.booted_ts is None:
            return 0.0
        return round((time.time() if now is None else float(now)) - self.booted_ts, 1)

    # ── the ONE call surface (DESIGN.md §4 syscall table) ─────────────────────
    def syscall(self, name: str, **args):
        fn = getattr(self, f"_sys_{name}", None)
        if fn is None:
            raise ValueError(f"unknown syscall '{name}'")
        return fn(**args)

    def _sys_recall(self, query: str, k: int = 5, kind: str | None = None):
        hits = self.store.search(query, k=k, kind=kind)
        for h in hits:
            self.wm.load(h["id"], h)                    # swap results into RAM
        return hits

    def _sys_remember(self, kind: str, title: str, body: str, action: str, **kw):
        n = self.store.add(kind, title, body, action, **kw)
        self.wm.load(n.id, n.to_dict())
        self.wm.remember("lesson", {"remembered": n.id, "title": title[:80]})
        return {"id": n.id}

    def _sys_consult(self, query: str, domain: str, k: int = 3, kind: str | None = None):
        from trading.brain import consult as _c
        out = _c.consult(query, domain=domain, k=k, kind=kind)
        for nid in out.get("ids", []):
            n = self.store.get(nid)
            if n is not None:
                self.wm.load(nid, n.to_dict())
        return out

    def _sys_grade(self, ids, win: bool, pnl: float = 0.0, domain: str = ""):
        from trading.brain import consult as _c
        return _c.grade(ids, win=win, pnl=pnl, domain=domain)

    def _sys_evolve(self):
        return self.evolver().evolve_once()

    def _sys_focus(self, **kw):
        f = self.wm.set_focus(**kw)
        self._persist()
        return f

    def _sys_pin(self, nid: str):
        n = self.store.get(nid)
        if n is None:
            return {"pinned": False, "reason": "no such neuron"}
        self.wm.pin(nid, n.to_dict())
        self._persist()
        return {"pinned": True, "id": nid}

    def _sys_recent(self, kind: str = "decision", n: int = 20):
        return self.wm.recent(kind, n)

    def _sys_ps(self):
        return self.ps()

    def _sys_top(self):
        return self.top()

    def _sys_tick(self):
        return self.tick()

    def _sys_next(self):
        return self.next_lobe()

    # ── attention scheduler (OS-3) ────────────────────────────────────────────
    def schedule_ranking(self) -> list[dict]:
        """Score every lobe by focus-match + fairness (ticks since last attended)."""
        focus = self.wm.focus
        out = []
        for lobe in SCHED_LOBES:
            fair = FAIRNESS * (self.tick_no - self.last_sched.get(lobe["name"], 0))
            focus_hit = _focus_match(lobe, focus)
            score = lobe["base"] + fair + (FOCUS_BOOST if focus_hit else 0.0)
            out.append({"name": lobe["name"], "score": round(score, 3),
                        "focus_match": focus_hit,
                        "last_attended_tick": self.last_sched.get(lobe["name"], 0)})
        out.sort(key=lambda x: x["score"], reverse=True)
        return out

    def tick(self) -> dict:
        """Advance one scheduling step: pick the top-ranked lobe to attend next."""
        with self._lock:
            self.tick_no += 1
            ranking = self.schedule_ranking()
            nxt = ranking[0]["name"] if ranking else None
            if nxt is not None:
                self.last_sched[nxt] = self.tick_no
            self.wm.post("scheduler", {"tick": self.tick_no, "next": nxt})
        return {"tick": self.tick_no, "next": nxt, "ranking": ranking}

    def next_lobe(self) -> dict:
        """The current pick WITHOUT advancing (cross-process lobes poll this to yield)."""
        ranking = self.schedule_ranking()
        return {"tick": self.tick_no, "next": ranking[0]["name"] if ranking else None,
                "ranking": ranking}

    # ── process table (OS-2): kernel + in-process threads + file-heartbeat lobes ──
    def ps(self, *, now: float | None = None) -> list[dict]:
        now = time.time() if now is None else float(now)
        wm = self.wm.snapshot()
        procs = [{"name": "brain-kernel", "kind": "kernel", "state": "RUNNING",
                  "age_secs": 0,
                  "detail": f"uptime {self.uptime_secs(now=now)}s · {wm['bytes_used']}B RAM"}]
        try:                                             # in-process learn loop: its own truth
            from trading.brain.learn_loop import get_learn_loop
            ls = get_learn_loop().status()
            procs.append({"name": "learn-loop", "kind": "lobe",
                          "state": "RUNNING" if ls.get("running") else "STOPPED",
                          "age_secs": 0 if ls.get("running") else None,
                          "detail": f"cycles {ls.get('cycles')} · enabled {ls.get('enabled')}"})
        except Exception:
            pass
        for spec in PROCESS_SPECS:                       # cross-process: file heartbeats
            ages = [a for a in (_file_age(f, now) for f in spec["files"]) if a is not None]
            age = min(ages) if ages else None
            procs.append({"name": spec["name"], "kind": spec["kind"],
                          "state": _proc_state(age, spec["budget"]),
                          "age_secs": None if age is None else round(age),
                          "detail": f"heartbeat {spec['files'][0]}"})
        return procs

    # ── "top": honest resource view ──────────────────────────────────────────
    def top(self) -> dict:
        store_status = self.store.status()
        return {"booted": self.booted_ts is not None, "boots": self.boots,
                "uptime_secs": self.uptime_secs(),
                "working_memory": self.wm.snapshot(),
                "processes": self.ps(),
                "scheduler": self.next_lobe(),             # OS-3: who the brain attends next
                "store": {"neurons": store_status.get("neurons"),
                          "links": store_status.get("links"),
                          "ram_resident": True},           # NeuronStore is RAM-cached
                "syscalls": [n[5:] for n in dir(self) if n.startswith("_sys_")]}

    # ── persistence (OS init restores focus + pins) ───────────────────────────
    def _load_state(self) -> dict:
        from trading import state
        return state.load_json(_STATE_FILE, {"focus": {}, "pinned": [], "boots": 0}) or {}

    def _persist(self) -> None:
        from trading import state
        state.save_json(_STATE_FILE, {"focus": dict(self.wm.focus),
                                      "pinned": list(self.wm.pinned),
                                      "boots": self.boots})


_KERNEL: BrainKernel | None = None
_KERNEL_LOCK = threading.Lock()


def get_kernel() -> BrainKernel:
    """Process-wide resident kernel (same singleton discipline as get_store)."""
    global _KERNEL
    with _KERNEL_LOCK:
        if _KERNEL is None:
            _KERNEL = BrainKernel()
            _KERNEL.boot()
        return _KERNEL


def ensure_kernel() -> BrainKernel:
    """Boot the resident kernel at dashboard startup (idempotent) — so the brain OS is
    already RAM-resident before any request thread touches it (never boot in-request)."""
    return get_kernel()


# ── OS-4: the single call surface lobes use instead of importing peers ad-hoc ──
# Every lobe that touches shared knowledge routes through the OS here, so consults land
# in the kernel's RAM working memory (observability) and there is ONE surface to evolve.
# Behavior-preserving: if the kernel is unavailable for any reason, fall back to the
# direct consult bridge — the hot trading path must never regress.
def consult(query: str, *, domain: str, k: int = 3, kind: str | None = None) -> dict:
    """Kernel-routed recall+record_use. Same shape as trading.brain.consult.consult."""
    try:
        return get_kernel().syscall("consult", query=query, domain=domain, k=k, kind=kind)
    except Exception:
        from trading.brain import consult as _c
        return _c.consult(query, domain=domain, k=k, kind=kind)


def grade(ids, *, win: bool, pnl: float = 0.0, domain: str = "") -> int:
    """Kernel-routed outcome credit for previously-consulted neurons."""
    try:
        return get_kernel().syscall("grade", ids=ids, win=win, pnl=pnl, domain=domain)
    except Exception:
        from trading.brain import consult as _c
        return _c.grade(ids, win=win, pnl=pnl, domain=domain)
