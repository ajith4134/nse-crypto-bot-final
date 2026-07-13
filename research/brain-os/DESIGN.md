# 🖥️ BRAIN-OS — the combined brain as an operating system with its own RAM

**Status:** DESIGN (propose → approve). No code until the owner approves. · **Requirement source:** owner, 2026-07-13 — *"I need the combined brain we are making to act as an OS with its own RAM."* (memory: `project-brain-as-os-own-ram`) · **Parent goal:** [[brain-ultra-upgrade]] · **Motto:** CPU = the brain's full intelligence · APIs = execution · data = web nav · **RAM for speed**.

---

## 1. What the owner asked (literal reading)

The brain is many features (neuron web, cognitive loop, school, instruction evolution, funnels, vision, memory). Right now they behave like **cold scripts** — each cycle re-reads JSON from disk, imports peers ad-hoc, and there is no single resident "mind" holding state. The owner wants it to behave like an **operating system with its own RAM**: a **resident kernel** that stays running, holds its **working memory in RAM** (not cold disk), schedules its lobes like processes, and exposes a clean call interface — so the brain is *one always-on machine*, not a batch of jobs.

## 2. Design principle — a COHERING LAYER, not a rewrite

Almost every OS part already has a real counterpart in the codebase. Brain-OS **formalizes and makes them resident**, it does not rebuild them. New code is thin: a kernel object, a RAM working-memory buffer, a process table, and one dashboard view.

## 3. OS ↔ Brain mapping (grounded in real modules)

| OS concept | Brain-OS realization | Reuse (already built) | New work |
|---|---|---|---|
| **Kernel / scheduler** | `brain_os.py` — a resident `BrainKernel` that owns the cognitive loop tick and dispatches lobes | cognitive-loop stages in `trading/brain/flow_health.py:STAGES`; loop drivers | kernel object + tick scheduler |
| **RAM (main memory)** | `WorkingMemory` — an in-process RAM buffer: hot/pinned neurons, current focus, attention scratchpad, last-N percepts/decisions, blackboard for inter-lobe messages | `NeuronStore` is already RAM-cached (`memory/neurons.py` `_cache`) | working-memory/attention buffer + blackboard |
| **Process table** | `ProcessTable` — registered lobes with name, kind, PID/thread, heartbeat, state (RUNNING/SLEEPING/STOPPED) | `flow_status()`, `learn_loop.status()`, funnel state files, `pgrep` of `run_funnel_loop`/`run_live_loop` | one registry that unifies them |
| **Syscall API** | `kernel.syscall(name, **args)` — the ONLY way lobes touch shared state: `recall`, `remember`, `consult`, `grade`, `evolve`, `focus`, `spawn`, `ps` | `trading/brain/consult.py` (recall+record_use) is a proto-syscall; `get_store/get_brain` | formalize the call table |
| **Boot / init** | `kernel.boot()` — warms the store, restores working memory, registers lobes, starts the tick; idempotent, resumes across restarts | `learn_loop.ensure_started()`, dashboard boot hook (`server.py`) | boot sequence |
| **Resource monitor (`top`)** | RAM bytes held by the web + working memory, CPU per lobe, uptime, **agentic time-horizon**, tick rate | `SelfEvaluation.time_horizon()`, `psutil`, `NeuronStore.status()` | one aggregated view |
| **Scheduler policy** | which lobe runs next = the curriculum/attention picker (already the brain's "what to do next") | `learn_loop.pick_topic()`, `school`, boss `active_segments` | attention-driven scheduling |
| **Persistence / swap** | disk = the durable store (neurons.db + state JSON); RAM = the hot working set; "swap in" a neuron = load to working memory | `NeuronStore` file+DB mirror | pin/evict policy |

## 4. New components (all thin, reuse-first)

1. **`trading/brain/brain_os.py`**
   - `class WorkingMemory` — RAM buffer: `pinned` (always-hot neuron ids), `focus` (current goal/segment), `scratch` (dict blackboard for lobe↔lobe messages), ring buffers of recent percepts/decisions/lessons. Bounded (LRU + byte cap) so RAM is honest, not unbounded. Exposes `bytes_used()`.
   - `class ProcessTable` — `register(name, kind, heartbeat_fn, control_fn)`, `ps()` → live status (merges thread state + flow_health + funnel mtimes + optional pgrep). No fabrication: a lobe with a stale heartbeat shows SLEEPING/DEAD honestly.
   - `class BrainKernel` — owns `WorkingMemory` + `ProcessTable` + the singletons (`get_store`, `get_brain`, `get_learn_loop`, `get_evolver`). `boot()`, `tick()` (one scheduler step), `syscall(name, **a)`, `top()` (resource view). Singleton `get_kernel()`.
2. **`GET /api/brain/os`** — the "top" snapshot: uptime, RAM used (web + working memory), process table, tick rate, time-horizon, focus. Honest numbers only (`_bg_snapshot` warmer like the other brain routes).
3. **`POST /api/brain/os`** — control ops: `focus`, `pin`, `ps`, `boot`, `stop <lobe>` (paper-safe; execution stays API-only, never flips live).
4. **Dashboard "Brain OS" section** in `BrainPage.jsx` — a `BrainOsPanel` styled like a system monitor (uptime, RAM meter, process table, time-horizon sparkline). (dashboard-visual-qa on build.)

## 5. Architecture (text)

```
                         ┌──────────────────────  BrainKernel (resident)  ──────────────────────┐
   percepts →  PERCEIVE →│  tick(): schedule next lobe by ATTENTION/curriculum                  │
   (eyes/news)           │                                                                      │
                         │   ┌─ WorkingMemory (RAM) ─┐     ┌─ ProcessTable ─┐                    │
                         │   │ pinned neurons        │     │ crypto-funnel   RUNNING            │
   syscall(recall) ──────┼──▶│ focus / goal          │     │ nse-funnel      RUNNING            │
   syscall(consult)      │   │ scratch (blackboard)  │     │ learn-loop      SLEEPING           │
   syscall(remember) ────┼──▶│ recent percepts/decis │     │ school          SLEEPING           │
   syscall(evolve)       │   └───────────┬───────────┘     │ evolution       SLEEPING           │
                         │               │ swap-in/evict   │ live-loop(NSE)  RUNNING            │
                         │        ┌───────▼────────┐        └─────────────────┘                  │
                         │        │  NeuronStore   │  ← durable disk (neurons.db + state JSON)    │
                         │        │  (RAM cache)   │                                             │
                         │        └────────────────┘                                             │
                         └──────────────────────────────────────────────────────────────────────┘
                                   top() → /api/brain/os → Brain OS panel
```

## 6. Phased build (each independently shippable + verified)

- **OS-1 — Kernel + RAM working memory:** `brain_os.py` with `WorkingMemory` + `BrainKernel.boot()/syscall()`; unit tests; no behavior change to lobes yet (they can start calling syscalls opportunistically). *Proves: resident RAM state with a byte-bounded buffer.*
- **OS-2 — Process table + `/api/brain/os` + panel:** unify lobe status; honest "top" view. *Proves: one live process table, no fabrication (dashboard-visual-qa).*
- **OS-3 — Attention scheduler:** `tick()` picks the next lobe from focus/curriculum; funnels & learn-loop register and yield to it. *Proves: scheduling is real (order changes with focus).*
- **OS-4 — Syscall migration:** route `consult`/`recall`/`remember`/`evolve` seams through `kernel.syscall(...)` so lobes stop importing peers ad-hoc. *Proves: single call surface.*

## 7. Acceptance (definition of done)

1. A resident kernel process holds working memory in RAM; `bytes_used()` is real and bounded.
2. `/api/brain/os` shows uptime, RAM, and an honest process table (stale lobe = SLEEPING/DEAD, never faked).
3. `tick()` scheduling order provably changes when `focus` changes.
4. ≥1 lobe (e.g. funnel or learn-loop) reads/writes shared state **only** via `kernel.syscall`.
5. Time-horizon + tick-rate trend on the dashboard.
6. Motto held: all resident in local RAM/CPU; APIs execution-only; no new paid deps.

## 8. Risks / gotchas (from project memory)

- **Two processes, not one address space:** the crypto funnel, NSE funnel, and live-loop are **separate OS processes** (not threads) — a single in-RAM kernel can't literally share objects with them. Honest model: the kernel runs inside the **dashboard process** (where `get_store`/`get_learn_loop`/`get_evolver` already live as threads), and cross-process lobes are represented in the process table via their **state-file heartbeats** (the `flow_health` pattern), not shared memory. This keeps it honest and matches [[nse-three-loop-architecture]].
- `_bg_snapshot` warmers are serial → the OS panel must handle "warming" honestly (like the other brain panels).
- RAM must be **bounded** (LRU + byte cap) — an unbounded working memory would starve the box (the 31→42GB swap incident, [[local-vision-permanent]]).
- `loop_keeper` respawns loops → the process table must treat respawn (new PID) as healthy, not a crash ([[brain-ultra-upgrade]] gotcha #1).

## 9. Not in scope (explicitly)

Not a real microkernel, not process isolation/virtual memory in the CS sense, not replacing the OS. "OS with its own RAM" = a **resident mind with a bounded RAM working set, a process table of its lobes, a scheduler, and a syscall surface** — the useful, honest interpretation.
